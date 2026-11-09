import io

import pytest
from ebooklib import epub
from PIL import Image

from babel.ingest import IngestError, load_book
from babel.ingest.clean import clean_text
from babel.ingest.epub import italic_classes
from babel.ingest.txt import split_chapters


def _cover_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (60, 90), (120, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()


def make_epub(path):
    book = epub.EpubBook()
    book.set_identifier("t1")
    book.set_title("The Test Tower")
    book.set_language("en")
    book.add_author("A. Writer")
    book.set_cover("cover.jpg", _cover_bytes())
    css = epub.EpubItem(uid="css", file_name="s.css", media_type="text/css",
                        content=".think { font-style: italic } .fn { font-style: italic; vertical-align: super }")
    book.add_item(css)
    filler = " ".join(["The tower hummed."] * 20)
    toc = epub.EpubHtml(title="Contents", file_name="toc.xhtml")
    toc.content = "<h1>Contents</h1><p>Chapter 1</p>"
    c1 = epub.EpubHtml(title="Chapter 1: Waking", file_name="c1.xhtml")
    c1.content = (f"<h2>Chapter 1:<br/><span>Waking</span></h2><p>{filler}</p>"
                  "<p><span class='think'>Where am I?</span> Kai sat up.</p><hr/>"
                  "<p>“Hello,” said <i>Mira</i>.</p>")
    combo = epub.EpubHtml(title="More", file_name="c23.xhtml")
    combo.content = (f"<h2>Chapter 2: Two</h2><p>{filler}</p><p>Second.</p>"
                     f"<h2>Chapter 3: Three</h2><p>{filler}</p><p>Third.</p>")
    for item in (toc, c1, combo):
        item.add_item(css)
        book.add_item(item)
    book.toc = [c1, combo]
    book.spine = [toc, c1, combo]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)


def test_epub_ingestion(tmp_path):
    p = tmp_path / "t.epub"
    make_epub(p)
    b = load_book(p)
    assert b.title == "The Test Tower" and b.author == "A. Writer" and b.cover
    assert [c.title for c in b.chapters] == ["Chapter 1: Waking", "Chapter 2: Two", "Chapter 3: Three"]
    c1 = b.chapters[0].text
    assert "*Where am I?*" in c1  # CSS-class italics preserved as emphasis
    assert "* * *" in c1  # <hr> → scene break
    assert not c1.startswith("Chapter 1")  # heading not repeated in the body
    assert "*Mira*" in c1
    assert b.chapters[2].text.endswith("Third.")


def test_italic_classes():
    assert italic_classes(".a{font-style:italic} p.b, .c { color:red; font-style: oblique } .d{font-style:italic;vertical-align:super}") == {"a", "b", "c"}


def test_txt_headings_and_cleanup(tmp_path):
    text = ("Read more at www.novelfull.com\n\nChapter 1: Start\n\nHello there.\n\nhttps://spam.example\n\n"
            "Chapter 2 - Next\n\nSecond body.\n\n第3章 三\n\n中文内容。")
    p = tmp_path / "My_Novel.txt"
    p.write_text(text)
    b = load_book(p)
    assert b.title == "My Novel"
    assert [c.title for c in b.chapters] == ["Chapter 1: Start", "Chapter 2 - Next", "第3章 三"]
    assert "novelfull" not in b.chapters[0].text and "spam" not in b.chapters[0].text


def test_txt_without_headings_splits_by_size():
    text = "\n\n".join(["word " * 500] * 13)
    parts = split_chapters(text)
    assert len(parts) >= 2 and parts[0].title == "Part 1"


def test_clean_text_normalizes():
    assert clean_text("a  b\r\n\r\n\r\n\r\nc​") == "a b\n\nc"


def test_unsupported_type(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF")
    with pytest.raises(IngestError):
        load_book(p)
