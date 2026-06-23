"""Manifest-driven batch processor with hash-based idempotency.

Reads ``chapter_map.json`` from the clean directory and transforms each chapter,
skipping ones whose source hash already matches the existing output (so a run
can be stopped and resumed without re-calling the LLM). On transform failure a
placeholder JSON preserving the raw text is written so the pipeline never loses
content.

Reconstructed from tests/test_batch_processor.py and tests/test_transform_integration.py.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from babel.transform.gemini_client import GeminiClient
from babel.transform.transformer import Transformer

logger = logging.getLogger(__name__)

FAILED_MODEL_VERSION = "gemini-1.5-flash-failed"


class BatchProcessor:
    """Transforms all chapters listed in a clean directory's chapter manifest."""

    def __init__(self, clean_dir, json_dir, client=None):
        self.clean_dir = Path(clean_dir)
        self.json_dir = Path(json_dir)
        self.json_dir.mkdir(parents=True, exist_ok=True)
        if client is None:
            client = GeminiClient()
        self.transformer = Transformer(client)

    def load_chapter_map(self) -> dict:
        """Load the chapter manifest produced by Phase 0 (sanitize)."""
        manifest_path = self.clean_dir / "chapter_map.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Chapter manifest not found at {manifest_path}. "
                f"Run Phase 0 (sanitize) first to generate chapter_map.json."
            )
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def process_all_chapters(self) -> Tuple[int, int, int]:
        """Process every chapter in the manifest. Returns (processed, skipped, failed)."""
        chapter_map = self.load_chapter_map()
        chapters = chapter_map.get("chapters", [])
        processed = skipped = failed = 0

        for entry in chapters:
            filename = entry.get("filename")
            title = entry.get("title", filename)
            source_path = self.clean_dir / filename
            output_path = self.json_dir / Path(filename).with_suffix(".json").name

            if not source_path.exists():
                logger.error("Source file not found: %s", source_path)
                failed += 1
                continue

            source_text = source_path.read_text(encoding="utf-8")
            source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

            # Idempotency: skip when an existing, valid output has a matching hash.
            if output_path.exists():
                try:
                    existing = json.loads(output_path.read_text(encoding="utf-8"))
                    if existing.get("source_hash") == source_hash:
                        skipped += 1
                        continue
                except (json.JSONDecodeError, OSError):
                    pass  # invalid existing output -> reprocess

            result = self.transformer.transform_chapter(source_text)
            if result is not None:
                output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
                processed += 1
            else:
                self._write_placeholder(output_path, title, source_text, source_hash)
                failed += 1

        total = len(chapters)
        if total > 0 and failed / total > 0.5:
            logger.critical(
                "High failure rate: %d/%d chapters failed (%.0f%%)",
                failed, total, 100 * failed / total,
            )

        logger.info(
            "Batch complete: %d processed, %d skipped, %d failed",
            processed, skipped, failed,
        )
        return processed, skipped, failed

    @staticmethod
    def _write_placeholder(output_path: Path, title: str, source_text: str, source_hash: str) -> None:
        """Write a placeholder JSON that preserves raw text when transform fails."""
        placeholder = {
            "blocks": [
                {
                    "type": "system_notification",
                    "speaker": None,
                    "content": f"[Transformation Failed for {title}]",
                    "tone": None,
                },
                {
                    "type": "action",
                    "speaker": None,
                    "content": source_text,
                    "tone": None,
                },
            ],
            "source_hash": source_hash,
            "model_version": FAILED_MODEL_VERSION,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        output_path.write_text(
            json.dumps(placeholder, indent=2, ensure_ascii=False), encoding="utf-8"
        )
