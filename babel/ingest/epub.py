"""EPUB ingestion.

Walks the spine in reading order, takes titles from the table of contents,
keeps italics as ``*...*`` (the strongest signal for inner thoughts), turns
<hr>/ornament lines into scene breaks, and splits documents that bundle several
chapters under their own headings.
"""

from __future__ import annotations

import posixpath
import re
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

from babel.ingest import Book, IngestError, RawChapter
from babel.ingest.clean import clean_text, drop_leading_title, is_heading

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")

_BLOCK_TAGS = {"p", "div", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "tr", "section", "article"}
_HEADINGS = {"h1", "h2", "h3"}
_SKIP_TAGS = {"script", "style", "head", "nav", "svg", "sup"}
_FRONT_MATTER_RE = re.compile(
    r"^(?:cover|title ?page|copyright|contents|table of contents|dedication|acknowledg\w*|about the (?:author|publisher)|also by|index)$",
    re.I,
)


_CSS_RULE_RE = re.compile(r"([^{}]+)\{([^}]*)\}")
_CLASS_RE = re.compile(r"\.([A-Za-z_][\w\-]*)\s*$")
_ITALIC_RE = re.compile(r"font-style\s*:\s*(?:italic|oblique)", re.I)
_SUPER_RE = re.compile(r"vertical-align\s*:\s*(?:super|sub)|font-size\s*:\s*0?\.[0-7]", re.I)


def italic_classes(css: str) -> set[str]:
    """Classes styled italic in the book's CSS (many EPUBs use <span class> not <em>)."""
    classes: set[str] = set()
    for selectors, body in _CSS_RULE_RE.findall(css):
        if _ITALIC_RE.search(body) and not _SUPER_RE.search(body):
            for sel in selectors.split(","):
                m = _CLASS_RE.search(sel.strip())
                if m:
                    classes.add(m.group(1))
    return classes


_ITALIC_CLASSES: set[str] = set()


def _is_italic(tag: Tag) -> bool:
    name = tag.name.lower()
    if name in ("em", "i", "cite", "var"):
        return True
    if name != "span":
        return False
    if _ITALIC_RE.search(tag.get("style") or ""):
        return True
    return any(c in _ITALIC_CLASSES for c in tag.get("class") or [])


def _inline(node, out: list[str]) -> None:
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(str(child))
        elif isinstance(child, Tag):
            name = child.name.lower()
            if name in _SKIP_TAGS:
                continue
            if name == "br":
                out.append("\n")
            elif _is_italic(child):
                inner: list[str] = []
                _inline(child, inner)
                s = "".join(inner)
                stripped = s.strip()
                if stripped and "*" not in stripped:
                    lead = s[: len(s) - len(s.lstrip())]
                    trail = s[len(s.rstrip()):]
                    out.append(f"{lead}*{stripped}*{trail}")
                else:
                    out.append(s)
            elif name in _BLOCK_TAGS:
                out.append("\n\n")
                _inline(child, out)
                out.append("\n\n")
            elif name == "hr":
                out.append("\n\n* * *\n\n")
            elif name == "img":
                continue
            else:
                _inline(child, out)


def _html_sections(html: bytes | str) -> list[tuple[str | None, str]]:
    """Return (heading, text) sections. Splits on chapter-like headings when several exist."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    heads = [h for h in body.find_all(list(_HEADINGS)) if is_heading(h.get_text(" ", strip=True))]
    if len(heads) >= 2:
        sections: list[tuple[str | None, str]] = []
        for h in heads:
            parts: list[str] = []
            for sib in h.next_siblings:
                if isinstance(sib, Tag) and any(sib is x for x in heads):
                    break
                if isinstance(sib, Tag):
                    if sib.find(lambda t: any(t is x for x in heads)):
                        break
                    wrapper = BeautifulSoup("<div></div>", "lxml").div
                    wrapper.append(sib.__copy__())
                    _inline(wrapper, parts)
                else:
                    parts.append(str(sib))
            sections.append((h.get_text(" ", strip=True), clean_text("".join(parts))))
        return sections
    first_head = body.find(list(_HEADINGS))
    heading = None
    if first_head is not None:
        heading = first_head.get_text(" ", strip=True)
        # the heading becomes the chapter title; don't repeat it in the body
        if len(heading) <= 120:
            first_head.decompose()
    parts = []
    _inline(body, parts)
    return [(heading, clean_text("".join(parts)))]


def _toc_titles(book) -> dict[str, str]:
    titles: dict[str, str] = {}

    def walk(items):
        for it in items:
            if isinstance(it, tuple):
                section, children = it
                href = getattr(section, "href", None)
                if href and getattr(section, "title", None):
                    titles.setdefault(href.split("#")[0], section.title)
                walk(children)
            elif getattr(it, "href", None):
                titles.setdefault(it.href.split("#")[0], it.title)

    walk(book.toc or [])
    return titles


def _meta(book, field: str) -> str | None:
    try:
        vals = book.get_metadata("DC", field)
    except Exception:
        return None
    if vals and vals[0] and vals[0][0]:
        return str(vals[0][0]).strip() or None
    return None


def _cover(book) -> tuple[bytes | None, str]:
    import ebooklib

    cover_id = None
    try:
        for _, attrs in book.get_metadata("OPF", "cover"):
            cover_id = attrs.get("content")
    except Exception:
        pass
    candidates = []
    if cover_id:
        item = book.get_item_with_id(cover_id)
        if item is not None:
            candidates.append(item)
    candidates += list(book.get_items_of_type(ebooklib.ITEM_COVER))
    candidates += [i for i in book.get_items_of_type(ebooklib.ITEM_IMAGE) if "cover" in i.get_name().lower()]
    for item in candidates:
        name = item.get_name().lower()
        if name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            ext = name.rsplit(".", 1)[-1].replace("jpeg", "jpg")
            return item.get_content(), ext
    return None, "jpg"


def read_epub(path: Path, name: str) -> Book:
    import ebooklib
    from ebooklib import epub

    try:
        book = epub.read_epub(str(path), options={"ignore_ncx": False})
    except Exception as e:
        raise IngestError(f"could not read EPUB: {e}") from e

    global _ITALIC_CLASSES
    css = "\n".join(
        i.get_content().decode("utf-8", "replace") for i in book.get_items_of_type(ebooklib.ITEM_STYLE))
    _ITALIC_CLASSES = italic_classes(css)
    toc = _toc_titles(book)
    chapters: list[RawChapter] = []
    skipped = 0
    for idref, _linear in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        href = item.get_name()
        toc_title = toc.get(href) or toc.get(posixpath.basename(href))
        for heading, text in _html_sections(item.get_content()):
            title = (heading if heading and len(heading) <= 120 else None) or toc_title
            words = len(text.split())
            if title and _FRONT_MATTER_RE.match(title.strip()) and words < 1500:
                skipped += 1
                continue
            if words < 40:  # cover pages, blank separators, image-only pages
                skipped += 1
                continue
            title = title or f"Chapter {len(chapters) + 1}"
            chapters.append(RawChapter(title.strip(), drop_leading_title(text, title)))

    if not chapters:
        raise IngestError("no readable chapters found in the EPUB")
    cover, ext = _cover(book)
    desc = _meta(book, "description")
    if desc:
        desc = BeautifulSoup(desc, "lxml").get_text(" ", strip=True)[:2000]
    b = Book(
        title=_meta(book, "title") or Path(name).stem,
        author=_meta(book, "creator"),
        description=desc,
        language=_meta(book, "language"),
        chapters=chapters,
        cover=cover,
        cover_ext=ext,
    )
    if skipped:
        b.warnings.append(f"skipped {skipped} non-chapter pages")
    return b
