"""ChapterRenderer: turn transformed chapter JSON into self-contained HTML.

Loads ``ChapterData`` (with validation), builds a Jinja2 template context with
deterministic character colors/lanes and prev/next navigation, and writes a
standalone HTML file. Templates live in ``templates/`` (chapter.jinja2).

Reconstructed from tests/test_renderer.py, tests/test_renderer_css.py and
tests/test_render_properties.py.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

from babel.transform.models import ChapterData
from babel.render.style import (
    get_character_color,
    get_character_lane,
    get_char_class,
    get_tone_emoji,
)

logger = logging.getLogger(__name__)


class ChapterRenderer:
    """Renders transformed chapter JSON to standalone HTML via Jinja2."""

    def __init__(
        self,
        template_dir: Path = Path("templates"),
        template_name: str = "chapter.html",
    ):
        self.template_dir = Path(template_dir)
        self.template_name = template_name
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml", "jinja2"]),
        )
        # Compiled once and cached by the Jinja2 Environment for the instance.
        self.template = self.env.get_template(template_name)

    # ------------------------------------------------------------------ load
    def _load_chapter_data(self, json_path: Path) -> ChapterData:
        """Load and validate a chapter JSON file into a ChapterData model."""
        json_path = Path(json_path)

        if not json_path.exists():
            msg = f"JSON file not found: {json_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        raw = json_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON syntax in %s: %s", json_path.name, e)
            raise

        try:
            chapter = ChapterData(**data)
        except ValidationError as e:
            logger.error("Validation failed for %s: %s", json_path.name, e)
            raise

        logger.debug(
            "Loaded chapter data from %s: %d blocks", json_path.name, len(chapter.blocks)
        )
        return chapter

    # --------------------------------------------------------------- context
    @staticmethod
    def _entries(chapter_map: Any) -> List[Any]:
        """Return the chapter entries of a chapter map (object or dict), or []."""
        if chapter_map is None:
            return []
        chapters = getattr(chapter_map, "chapters", None)
        if chapters is None and isinstance(chapter_map, dict):
            chapters = chapter_map.get("chapters", [])
        return chapters or []

    @staticmethod
    def _field(entry: Any, name: str) -> Any:
        """Read a field from a chapter entry that may be an object or a dict."""
        if isinstance(entry, dict):
            return entry.get(name)
        return getattr(entry, name, None)

    def _build_navigation(self, chapter_map: Any, json_path: Path) -> Dict[str, Optional[str]]:
        """Compute prev/next HTML links for the current chapter."""
        entries = self._entries(chapter_map)
        if not entries:
            return {"prev": None, "next": None}

        stem = Path(json_path).stem
        idx = next(
            (i for i, e in enumerate(entries) if Path(self._field(e, "filename") or "").stem == stem),
            None,
        )
        if idx is None:
            return {"prev": None, "next": None}

        def html_of(entry: Any) -> str:
            return Path(self._field(entry, "filename") or "").stem + ".html"

        return {
            "prev": html_of(entries[idx - 1]) if idx > 0 else None,
            "next": html_of(entries[idx + 1]) if idx < len(entries) - 1 else None,
        }

    def _build_toc(self, chapter_map: Any, json_path: Path) -> List[Dict[str, Any]]:
        """Build the table-of-contents context for the sidebar."""
        stem = Path(json_path).stem
        toc = []
        for e in self._entries(chapter_map):
            fn_stem = Path(self._field(e, "filename") or "").stem
            toc.append({
                "index": self._field(e, "index"),
                "filename": f"{fn_stem}.html",
                "title": self._field(e, "title") or fn_stem,
                "is_current": fn_stem == stem,
            })
        return toc

    def _derive_title(self, chapter_map: Any, json_path: Path) -> str:
        """Pick a human title from the chapter map, else humanize the filename."""
        stem = Path(json_path).stem
        for e in self._entries(chapter_map):
            if Path(self._field(e, "filename") or "").stem == stem:
                title = self._field(e, "title")
                if title:
                    return str(title)
        humanized = stem.replace("_", " ").replace("-", " ").strip()
        return humanized or "Chapter"

    def _prepare_context(
        self, chapter_data: ChapterData, chapter_map: Any, json_path: Path
    ) -> Dict[str, Any]:
        """Build the full Jinja2 render context for a chapter."""
        json_path = Path(json_path)

        blocks_ctx: List[Dict[str, Any]] = []
        character_styles: Dict[str, Dict[str, Any]] = {}

        for block in chapter_data.blocks:
            speaker = block.speaker
            color = get_character_color(speaker) if speaker else None
            lane = get_character_lane(speaker)
            char_class = get_char_class(speaker)

            blocks_ctx.append({
                "type": block.type.value,
                "content": block.content,
                "speaker": speaker,
                "tone": block.tone,
                "lane": lane,
                "color": color,
                "char_class": char_class,
                "tone_emoji": get_tone_emoji(block.tone),
            })

            if speaker and speaker not in character_styles:
                character_styles[speaker] = {
                    "color": color,
                    "lane": lane,
                    "char_class": char_class,
                }

        processed_at = chapter_data.processed_at
        if isinstance(processed_at, datetime):
            processed_at = processed_at.isoformat()

        return {
            "title": self._derive_title(chapter_map, json_path),
            "blocks": blocks_ctx,
            "character_styles": character_styles,
            "navigation": self._build_navigation(chapter_map, json_path),
            "toc": self._build_toc(chapter_map, json_path),
            "metadata": {
                "source_hash": chapter_data.source_hash,
                "model_version": chapter_data.model_version,
                "processed_at": processed_at,
            },
        }

    # ---------------------------------------------------------------- render
    def render_chapter(
        self, json_path: Path, output_path: Path, chapter_map: Any = None
    ) -> Path:
        """Render a single chapter JSON file to an HTML file."""
        json_path = Path(json_path)
        output_path = Path(output_path)

        chapter_data = self._load_chapter_data(json_path)
        context = self._prepare_context(chapter_data, chapter_map, json_path)
        html = self.template.render(**context)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Rendered %s", output_path.name)
        return output_path

    def render_batch(
        self, json_dir: Path, output_dir: Path, chapter_map: Any = None
    ) -> Dict[str, int]:
        """Render every chapter JSON in a directory; return run statistics."""
        json_dir = Path(json_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stats = {"rendered": 0, "failed": 0, "skipped": 0}

        json_files = sorted(json_dir.glob("*.json"))
        logger.info("Processing %d chapters", len(json_files))

        for json_path in json_files:
            output_path = output_dir / f"{json_path.stem}.html"
            try:
                self.render_chapter(json_path, output_path, chapter_map)
                stats["rendered"] += 1
            except Exception as e:
                logger.error("Failed to render %s: %s", json_path.name, e)
                stats["failed"] += 1

        logger.info(
            "Batch complete: %d rendered, %d failed, %d skipped",
            stats["rendered"], stats["failed"], stats["skipped"],
        )
        return stats

    # Backwards-compatible alias used by some callers.
    def render_all(self, json_dir: Path = Path("data/json"), output_dir: Path = Path("data/render")) -> Dict[str, int]:
        """Render all chapters under the default data directories."""
        return self.render_batch(json_dir, output_dir)
