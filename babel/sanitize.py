"""
EPUB sanitization and chapter extraction pipeline.

This module provides functionality to:
- Extract metadata from EPUB files
- Parse EPUB content and extract chapters
- Integrate with the library management system
"""

import json
import logging
import re
import shutil
import tempfile
import warnings
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Sanitization tuning constants.
CHARS_PER_TOKEN = 4
TOKEN_SAFETY_LIMIT = 50_000


class EPUBMetadata:
    """Container for EPUB metadata extracted from an EPUB file."""
    
    def __init__(
        self,
        title: str,
        author: Optional[str] = None,
        chapters: List[Dict[str, Any]] = None
    ):
        self.title = title
        self.author = author
        self.chapters = chapters or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "chapters": self.chapters
        }


class EPUBExtractor:
    """
    Extract metadata and content from EPUB files.
    
    Uses the standard EPUB container format to locate and parse
    OPF package documents, then extracts chapter content.
    """
    
    # EPUB namespace prefixes
    CONTAINER_NS = {"container": "urn:oasis:names:tc:opendocument:xmlns:container"}
    OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}
    DC_NS = {"dc": "http://purl.org/dc/elements/1.1/"}
    NAV_NS = {"nav": "http://www.idpf.org/2007/ops"}
    
    def __init__(self, epub_path: Path):
        """
        Initialize extractor with EPUB file path.
        
        Args:
            epub_path: Path to the EPUB file.
            
        Raises:
            FileNotFoundError: If EPUB file doesn't exist.
            ValueError: If file is not a valid EPUB.
        """
        self.epub_path = Path(epub_path)
        if not self.epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")
        
        self._temp_dir: Optional[Path] = None
        self._opf_path: Optional[Path] = None
        self._opf_data: Optional[Dict[str, Any]] = None
    
    def _extract_to_temp(self) -> Path:
        """
        Extract EPUB contents to a temporary directory.
        
        Returns:
            Path to the temporary directory containing extracted EPUB contents.
        """
        if self._temp_dir is not None:
            return self._temp_dir
        
        self._temp_dir = Path(tempfile.mkdtemp(prefix="babel_epub_"))
        
        with zipfile.ZipFile(self.epub_path, 'r') as epub:
            epub.extractall(self._temp_dir)
        
        return self._temp_dir
    
    def _find_opf_path(self) -> Path:
        """
        Find the OPF package document path.
        
        The EPUB standard requires a META-INF/container.xml file that
        points to the OPF package document.
        
        Returns:
            Path to the OPF file.
            
        Raises:
            ValueError: If OPF path cannot be determined.
        """
        if self._opf_path is not None:
            return self._opf_path
        
        temp_dir = self._extract_to_temp()
        container_path = temp_dir / "META-INF" / "container.xml"
        
        if not container_path.exists():
            raise ValueError("Invalid EPUB: missing container.xml")
        
        tree = ET.parse(container_path)
        root = tree.getroot()
        
        # Find the rootfile element with media-type="application/oebps-package+xml"
        for rootfile in root.findall(".//container:rootfile", self.CONTAINER_NS):
            if rootfile.get("media-type") == "application/oebps-package+xml":
                opf_path = temp_dir / rootfile.get("full-path")
                self._opf_path = opf_path
                return opf_path
        
        raise ValueError("Invalid EPUB: no OPF package document found")
    
    def _parse_opf(self) -> Dict[str, Any]:
        """
        Parse the OPF package document.
        
        Returns:
            Dictionary containing OPF metadata and manifest/spine items.
        """
        if self._opf_data is not None:
            return self._opf_data
        
        opf_path = self._find_opf_path()
        tree = ET.parse(opf_path)
        root = tree.getroot()
        
        # Extract metadata
        metadata = root.find("opf:metadata", self.OPF_NS)
        if metadata is None:
            metadata = root.find("metadata")
        
        # Extract title
        title_elem = metadata.find("dc:title", self.DC_NS) if metadata is not None else None
        if title_elem is None:
            # Try without namespace
            title_elem = metadata.find("title") if metadata is not None else None
        title = title_elem.text if title_elem is not None else None
        
        # Extract author (creator)
        author_elem = metadata.find("dc:creator", self.DC_NS) if metadata is not None else None
        if author_elem is None:
            author_elem = metadata.find("creator") if metadata is not None else None
        author = author_elem.text if author_elem is not None else None
        
        # Extract manifest items
        manifest = {}
        manifest_elem = root.find("opf:manifest", self.OPF_NS)
        if manifest_elem is None:
            # Try with default namespace
            manifest_elem = root.find("{http://www.idpf.org/2007/opf}manifest")
        if manifest_elem is None:
            # Try without namespace
            manifest_elem = root.find("manifest")
        
        if manifest_elem is not None:
            # Find items with or without namespace
            items = manifest_elem.findall("opf:item", self.OPF_NS)
            if not items:
                items = manifest_elem.findall("{http://www.idpf.org/2007/opf}item")
            if not items:
                items = manifest_elem.findall("item")
            
            for item in items:
                item_id = item.get("id")
                item_href = item.get("href")
                item_media_type = item.get("media-type")
                if item_id and item_href:
                    manifest[item_id] = {
                        "href": item_href,
                        "media_type": item_media_type
                    }
        
        # Extract spine items in order
        spine = []
        spine_elem = root.find("opf:spine", self.OPF_NS)
        if spine_elem is None:
            spine_elem = root.find("{http://www.idpf.org/2007/opf}spine")
        if spine_elem is None:
            spine_elem = root.find("spine")
        
        if spine_elem is not None:
            itemrefs = spine_elem.findall("opf:itemref", self.OPF_NS)
            if not itemrefs:
                itemrefs = spine_elem.findall("{http://www.idpf.org/2007/opf}itemref")
            if not itemrefs:
                itemrefs = spine_elem.findall("itemref")
            
            for itemref in itemrefs:
                item_id = itemref.get("idref")
                if item_id and item_id in manifest:
                    spine.append(item_id)
        
        # Determine OPF directory for resolving relative paths
        opf_dir = opf_path.parent
        
        self._opf_data = {
            "title": title,
            "author": author,
            "manifest": manifest,
            "spine": spine,
            "opf_dir": str(opf_dir)
        }
        
        return self._opf_data
    
    def _resolve_href(self, href: str) -> Path:
        """
        Resolve an href relative to the OPF file location.
        
        Args:
            href: The href to resolve.
            
        Returns:
            Absolute path to the referenced file.
        """
        opf_data = self._parse_opf()
        opf_dir = Path(opf_data["opf_dir"])
        return opf_dir / href
    
    def extract_metadata(self) -> EPUBMetadata:
        """
        Extract metadata from the EPUB file.
        
        Returns:
            EPUBMetadata object with title, author, and chapters.
        """
        opf_data = self._parse_opf()
        
        title = opf_data["title"] or self.epub_path.stem
        author = opf_data.get("author")
        
        # Extract chapter content
        chapters = self._extract_chapters()
        
        return EPUBMetadata(
            title=title,
            author=author,
            chapters=chapters
        )
    
    def _extract_chapters(self) -> List[Dict[str, Any]]:
        """
        Extract chapter content from the EPUB.
        
        Returns:
            List of chapter dictionaries with title and content.
        """
        opf_data = self._parse_opf()
        manifest = opf_data["manifest"]
        spine = opf_data["spine"]
        
        chapters = []
        
        for i, item_id in enumerate(spine):
            if item_id not in manifest:
                continue
            
            item = manifest[item_id]
            item_path = self._resolve_href(item["href"])
            
            # Skip non-XHTML content
            if item.get("media_type") and "xhtml" not in item.get("media_type", ""):
                continue
            
            if not item_path.exists():
                continue
            
            try:
                chapter = self._parse_xhtml_chapter(item_path, i + 1)
                if chapter:
                    chapters.append(chapter)
            except Exception as e:
                logger.warning(f"Error parsing chapter {item_id}: {e}")
                continue
        
        return chapters
    
    def _parse_xhtml_chapter(self, xhtml_path: Path, chapter_index: int) -> Optional[Dict[str, Any]]:
        """
        Parse a single XHTML chapter file.
        
        Args:
            xhtml_path: Path to the XHTML file.
            chapter_index: The chapter number.
            
        Returns:
            Chapter dictionary or None if parsing fails.
        """
        try:
            tree = ET.parse(xhtml_path)
            root = tree.getroot()
            
            # Remove namespace for easier parsing
            for elem in root.iter():
                if elem.tag.startswith('{'):
                    elem.tag = elem.tag.split('}', 1)[1]
            
            # Extract title from <title> or <h1>
            title = None
            title_elem = root.find(".//title")
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()
            
            if not title:
                h1 = root.find(".//h1")
                if h1 is not None:
                    title = "".join(h1.itertext()).strip()
            
            if not title:
                title = f"Chapter {chapter_index}"
            
            # Extract body content
            body = root.find(".//body")
            if body is None:
                return None
            
            # Get all text content, preserving some structure
            content_parts = []
            for elem in body.iter():
                if elem.tag in ('p', 'div', 'h1', 'h2', 'h3'):
                    text = "".join(elem.itertext()).strip()
                    if text:
                        content_parts.append(text)
            
            content = "\n\n".join(content_parts)
            
            return {
                "chapter_index": chapter_index,
                "title": title,
                "content": content,
                "filename": xhtml_path.name
            }
            
        except Exception as e:
            logger.error(f"Error parsing XHTML chapter {xhtml_path}: {e}")
            return None
    
    def cleanup(self) -> None:
        """Clean up temporary extraction directory."""
        if self._temp_dir is not None and Path(self._temp_dir).exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
            self._opf_path = None
            self._opf_data = None
    
    def __enter__(self) -> "EPUBExtractor":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup temporary files."""
        self.cleanup()


class ChapterEntry(BaseModel):
    """A single chapter's metadata entry within a ChapterMap manifest."""

    index: int
    filename: str
    title: str
    token_count_est: int
    volume: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChapterMap(BaseModel):
    """Manifest mapping a source file to its extracted/cleaned chapters."""

    source_filename: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chapters: List[ChapterEntry] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.chapters)


def extract_epub_metadata(epub_path: Path) -> EPUBMetadata:
    """
    Convenience function to extract metadata from an EPUB file.
    
    Args:
        epub_path: Path to the EPUB file.
        
    Returns:
        EPUBMetadata object with extracted information.
    """
    with EPUBExtractor(epub_path) as extractor:
        return extractor.extract_metadata()


def sanitize_chapter_text(text: str) -> str:
    """
    Sanitize chapter text for processing.
    
    Performs basic cleanup:
    - Normalizes whitespace
    - Removes excessive newlines
    - Strips leading/trailing whitespace
    
    Args:
        text: Raw chapter text.
        
    Returns:
        Sanitized text.
    """
    if not text:
        return ""
    
    # Normalize whitespace
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Remove excessive newlines (more than 2 becomes 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    
    # Remove empty lines at start and end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    
    return '\n'.join(lines)


def segment_chapters(
    text: str,
    min_chapter_length: int = 500,
    max_chapter_length: int = 10000
) -> List[Dict[str, Any]]:
    """
    Segment chapter text into smaller sections.
    
    Uses simple heuristics to identify chapter boundaries and
    split content into manageable segments.
    
    Args:
        text: Full chapter text.
        min_chapter_length: Minimum length for a chapter segment.
        max_chapter_length: Maximum length for a chapter segment.
        
    Returns:
        List of chapter segments with title and content.
    """
    if not text:
        return []
    
    # Split by chapter markers
    chapter_patterns = [
        r'^Chapter\s+\d+',
        r'^第[一二三四五六七八九十百千]+章',
        r'^\d+\.',
        r'^==+\s*',
    ]
    
    # Try to split into chapters
    lines = text.split('\n')
    chapters = []
    current_chapter = {"title": "Chapter 1", "content": []}
    chapter_num = 1
    
    for line in lines:
        # Check if line is a chapter header
        is_chapter_header = False
        for pattern in chapter_patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                # Save previous chapter if it has content
                if current_chapter["content"]:
                    current_chapter["content"] = '\n'.join(current_chapter["content"])
                    chapters.append(current_chapter)
                
                # Start new chapter
                chapter_num += 1
                current_chapter = {"title": line.strip(), "content": []}
                is_chapter_header = True
                break
        
        if not is_chapter_header:
            current_chapter["content"].append(line)
    
    # Don't forget the last chapter
    if current_chapter["content"]:
        current_chapter["content"] = '\n'.join(current_chapter["content"])
        chapters.append(current_chapter)
    
    # If no chapters were split, treat entire text as one chapter
    if not chapters:
        chapters = [{"title": "Chapter 1", "content": text}]

    return chapters


# ============================================================================
# Phase 0 ingestion pipeline (TXT / EPUB -> cleaned chapters + manifest)
# ============================================================================

class IngestionError(Exception):
    """Raised when a source file cannot be ingested."""


class SafetyLimitExceeded(Warning):
    """Warning emitted when a chapter exceeds the token safety limit."""


class RawChapter(BaseModel):
    """A chapter as extracted from the source, before cleaning."""

    index: int
    title: str
    content: str
    source_location: str
    volume: Optional[str] = None


class CleanChapter(BaseModel):
    """A cleaned chapter ready to be written to disk."""

    index: int
    title: str
    content: str
    token_count_est: int
    filename: str
    volume: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class TextCleaner:
    """Removes webnovel artifacts (URLs, translator notes, watermarks) and
    normalizes whitespace/quotes; detects content tags."""

    _URL_RE = re.compile(r"(?i)(?:https?://|www\.)\S*")
    _TN_RE = re.compile(r"(?im)(?:translator'?s?\s*note|tn)\s*:.*$")
    _WATERMARK_RE = re.compile(r"(?im)read\s+(?:more\s+)?(?:at|on)\b.*$")
    _LITRPG_MARKERS = ("status window", "level up", "[system]")

    @staticmethod
    def _remove_urls(text: str) -> str:
        return TextCleaner._URL_RE.sub("", text)

    @staticmethod
    def _remove_translator_notes(text: str) -> str:
        return TextCleaner._TN_RE.sub("", text)

    @staticmethod
    def _remove_watermarks(text: str) -> str:
        return TextCleaner._WATERMARK_RE.sub("", text)

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    @staticmethod
    def _normalize_quotes(text: str) -> str:
        return (
            text.replace("“", '"').replace("”", '"')
            .replace("‘", "'").replace("’", "'")
        )

    @staticmethod
    def detect_content_tags(text: str) -> List[str]:
        """Return content tags (e.g. 'litrpg', 'stat_sheet') detected in the text."""
        tags: List[str] = []
        low = text.lower()
        if any(marker in low for marker in TextCleaner._LITRPG_MARKERS):
            tags.append("litrpg")
        if "status window" in low or "status:" in low:
            tags.append("stat_sheet")
        return tags

    @classmethod
    def clean(cls, text: str) -> str:
        """Apply the full cleaning pipeline and trim blank edges."""
        if not text:
            return ""
        text = cls._normalize_quotes(text)
        text = cls._remove_urls(text)
        text = cls._remove_translator_notes(text)
        text = cls._remove_watermarks(text)
        text = cls._normalize_whitespace(text)
        lines = [ln.strip() for ln in text.split("\n")]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)


class TXTIngester:
    """Extracts chapters from a plain-text file using fuzzy markers."""

    _MARKER_RE = re.compile(
        r"^[ \t]*(?:chapter|ch\.?|episode|ep\.?)\s+\d+.*$",
        re.IGNORECASE | re.MULTILINE,
    )
    _NUMBER_LINE_RE = re.compile(r"^[ \t]*(\d+)[ \t]*$", re.MULTILINE)

    @staticmethod
    def _boundaries_from_regex(content: str, regex) -> List[Tuple[int, str]]:
        out = []
        for m in regex.finditer(content):
            line_start = content.rfind("\n", 0, m.start()) + 1
            line_end = content.find("\n", m.start())
            if line_end == -1:
                line_end = len(content)
            out.append((line_start, content[line_start:line_end].strip()))
        return out

    @classmethod
    def _detect_chapter_boundaries(cls, content: str) -> List[Tuple[int, str]]:
        return cls._boundaries_from_regex(content, cls._MARKER_RE)

    @classmethod
    def _detect_standalone_numbers(cls, content: str) -> List[Tuple[int, str]]:
        matches = [(m.start(), int(m.group(1))) for m in cls._NUMBER_LINE_RE.finditer(content)]
        if len(matches) < 2:
            return []
        seq = [matches[0]]
        for start, value in matches[1:]:
            if value == seq[-1][1] + 1:
                seq.append((start, value))
            else:
                break
        if len(seq) < 2:
            return []
        return [(start, str(value)) for start, value in seq]

    @staticmethod
    def _validate_chapter_size(chapter: RawChapter) -> None:
        tokens = len(chapter.content) // CHARS_PER_TOKEN
        if tokens > TOKEN_SAFETY_LIMIT:
            warnings.warn(
                f"Chapter '{chapter.title}' (~{tokens} tokens) exceeds safety "
                f"limit of {TOKEN_SAFETY_LIMIT} tokens",
                SafetyLimitExceeded,
                stacklevel=2,
            )

    @classmethod
    def extract_chapters(cls, path, custom_pattern: str = None) -> List[RawChapter]:
        p = Path(path)
        if not p.exists():
            raise IngestionError(f"Input file not found: {path}")

        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = p.read_text(encoding="latin-1")

        if custom_pattern:
            boundaries = cls._boundaries_from_regex(
                text, re.compile(custom_pattern, re.IGNORECASE | re.MULTILINE)
            )
        else:
            boundaries = cls._detect_chapter_boundaries(text)
            if not boundaries:
                boundaries = cls._detect_standalone_numbers(text)

        chapters: List[RawChapter] = []
        if not boundaries:
            chapters.append(RawChapter(
                index=0, title="Chapter 1", content=text.strip(), source_location=str(path)
            ))
        else:
            for i, (start, title) in enumerate(boundaries):
                end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
                # Keep the whole block (title line + body) as the chapter content.
                content = text[start:end].strip()
                chapters.append(RawChapter(
                    index=i, title=title, content=content, source_location=str(path)
                ))

        for chapter in chapters:
            cls._validate_chapter_size(chapter)
        return chapters


class EPUBIngester:
    """Extracts chapters from an EPUB in spine order, preserving titles/volumes."""

    _VOLUME_KEYWORDS = ("volume", "book", "part")

    @staticmethod
    def _parse_html_content(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
        return "\n".join(ln for ln in lines if ln)

    @classmethod
    def _extract_volume_info(cls, book) -> Dict[str, str]:
        volume_map: Dict[str, str] = {}

        def walk(items, current_volume=None):
            if items is None:
                return
            if not isinstance(items, (list, tuple)):
                items = [items]
            for entry in items:
                if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                    section, children = entry[0], entry[1]
                    title = (getattr(section, "title", "") or "")
                    if any(kw in title.lower() for kw in cls._VOLUME_KEYWORDS):
                        current = title
                    else:
                        current = current_volume
                    walk(children, current)
                else:
                    href = getattr(entry, "href", None)
                    if href and current_volume:
                        fn = href.split("/")[-1].split("#")[0]
                        volume_map[fn] = current_volume

        walk(getattr(book, "toc", []))
        return volume_map

    @staticmethod
    def _extract_title_map(book) -> Dict[str, str]:
        title_map: Dict[str, str] = {}

        def walk(items):
            if items is None:
                return
            if not isinstance(items, (list, tuple)):
                items = [items]
            for entry in items:
                if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                    walk(entry[1])
                else:
                    href = getattr(entry, "href", None)
                    title = getattr(entry, "title", None)
                    if href and title:
                        fn = href.split("/")[-1].split("#")[0]
                        title_map[fn] = title

        walk(getattr(book, "toc", []))
        return title_map

    @staticmethod
    def _get_spine_order(book) -> list:
        items = []
        for entry in getattr(book, "spine", []) or []:
            idref = entry[0] if isinstance(entry, (tuple, list)) else entry
            item = book.get_item_with_id(idref)
            if item is not None:
                items.append(item)
        return items

    @classmethod
    def extract_chapters(cls, path) -> List[RawChapter]:
        try:
            book = epub.read_epub(str(path))
        except Exception as e:
            raise IngestionError(f"Cannot read EPUB file '{path}': {e}")

        volume_map = cls._extract_volume_info(book)
        title_map = cls._extract_title_map(book)

        chapters: List[RawChapter] = []
        index = 0
        for item in cls._get_spine_order(book):
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            html = item.get_content().decode("utf-8", errors="replace")
            content = cls._parse_html_content(html)
            if not content.strip():
                continue
            fn = item.get_name().split("/")[-1]
            chapters.append(RawChapter(
                index=index,
                title=title_map.get(fn) or Path(fn).stem,
                content=content,
                source_location=f"{path}:{fn}",
                volume=volume_map.get(fn),
            ))
            index += 1
        return chapters


class FileWriter:
    """Generates safe filenames and writes cleaned chapters to disk."""

    MAX_SLUG = 50

    @staticmethod
    def _generate_filename(index: int, title: str) -> str:
        slug = (title or "").strip().lower()
        slug = re.sub(r"[^a-z0-9 _-]", "", slug)
        slug = slug.replace(" ", "_")
        slug = slug[:FileWriter.MAX_SLUG]
        slug = slug.strip("_-")
        if not slug:
            slug = f"chapter_{index + 1}"
        return f"{index:03d}_{slug}.txt"

    @staticmethod
    def _ensure_directory_exists(path) -> None:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as e:
            raise IOError(f"Cannot create output directory '{path}': {e}")

    @classmethod
    def write_chapters(cls, chapters: List[CleanChapter], output_dir) -> None:
        output_dir = Path(output_dir)
        cls._ensure_directory_exists(output_dir)
        for chapter in chapters:
            file_path = output_dir / chapter.filename
            if file_path.exists():
                logger.warning("Overwriting existing file: %s", file_path)
            try:
                file_path.write_text(chapter.content, encoding="utf-8")
            except OSError as e:
                raise IOError(f"Cannot write file '{file_path}': {e}")


class ManifestGenerator:
    """Builds and writes the chapter_map.json manifest."""

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // CHARS_PER_TOKEN

    @staticmethod
    def generate_manifest(chapters: List[CleanChapter], source_filename: str) -> ChapterMap:
        entries = [
            ChapterEntry(
                index=ch.index,
                filename=ch.filename,
                title=ch.title,
                token_count_est=ch.token_count_est,
                volume=ch.volume,
                metadata={"tags": list(ch.tags)},
            )
            for ch in chapters
        ]
        return ChapterMap(
            source_filename=source_filename,
            processed_at=datetime.now(timezone.utc),
            chapters=entries,
        )

    @staticmethod
    def write_manifest(manifest: ChapterMap, output_dir) -> None:
        output_dir = Path(output_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as e:
            raise IOError(f"Cannot create output directory '{output_dir}': {e}")

        manifest_path = output_dir / "chapter_map.json"
        try:
            manifest_path.write_text(
                json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            raise IOError(f"Cannot write manifest file '{manifest_path}': {e}")


def sanitize(input_path, output_dir, custom_chapter_pattern: str = None) -> ChapterMap:
    """End-to-end sanitization: ingest -> clean -> write chapters + manifest.

    Empty-after-cleaning chapters are excluded. Returns the ChapterMap manifest.
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    if not input_path.exists():
        raise IngestionError(f"Input file not found: {input_path}")

    ext = input_path.suffix.lower()
    if ext == ".epub":
        raw_chapters = EPUBIngester.extract_chapters(input_path)
    elif ext == ".txt":
        raw_chapters = TXTIngester.extract_chapters(input_path, custom_pattern=custom_chapter_pattern)
    else:
        raise IngestionError(f"Unsupported file type: {ext}")

    clean_chapters: List[CleanChapter] = []
    index = 0
    for raw in raw_chapters:
        cleaned = TextCleaner.clean(raw.content)
        if not cleaned.strip():
            continue
        clean_chapters.append(CleanChapter(
            index=index,
            title=raw.title,
            content=cleaned,
            token_count_est=ManifestGenerator._estimate_tokens(cleaned),
            filename=FileWriter._generate_filename(index, raw.title),
            volume=raw.volume,
            tags=TextCleaner.detect_content_tags(cleaned),
        ))
        index += 1

    FileWriter.write_chapters(clean_chapters, output_dir)
    manifest = ManifestGenerator.generate_manifest(clean_chapters, input_path.name)
    ManifestGenerator.write_manifest(manifest, output_dir)
    return manifest
    
    return chapters