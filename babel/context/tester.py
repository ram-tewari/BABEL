"""GlossaryTester: measure how consistently the glossary is applied.

Samples chapters, transforms them, and scores how consistently glossary
entities are referenced, reporting per-chapter scores and inconsistencies.

Reconstructed from tests/test_context_tester.py.
"""

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from babel.context.models import Glossary
from babel.context.store import GlossaryStore
from babel.transform.models import ChapterData
from babel.transform.transformer import Transformer

logger = logging.getLogger(__name__)

LOW_SCORE_THRESHOLD = 0.7


class GlossaryTester:
    """Evaluates glossary effectiveness against sample chapters."""

    def __init__(self, client, glossary_path: Path):
        self.client = client
        self.glossary_path = Path(glossary_path)
        self.glossary_store = GlossaryStore(self.glossary_path)

    # ----------------------------------------------------------- scoring
    @staticmethod
    def _calculate_consistency_score(results: List[Dict[str, Any]]) -> float:
        """Mean consistency score across per-chapter results (0.0 if empty)."""
        if not results:
            return 0.0
        return sum(r["consistency_score"] for r in results) / len(results)

    def _detect_inconsistencies(
        self,
        result_without: ChapterData,
        result_with: ChapterData,
        glossary: Glossary,
    ) -> List[Dict[str, Any]]:
        """Compare with/without-glossary transforms and report differences."""
        inconsistencies: List[Dict[str, Any]] = []
        for b_wo, b_w in zip(result_without.blocks, result_with.blocks):
            if (b_wo.speaker or None) != (b_w.speaker or None):
                inconsistencies.append({
                    "type": "speaker",
                    "without_glossary": b_wo.speaker,
                    "with_glossary": b_w.speaker,
                })
            if b_wo.content != b_w.content:
                inconsistencies.append({
                    "type": "term",
                    "without_glossary": b_wo.content,
                    "with_glossary": b_w.content,
                })
        return inconsistencies

    @staticmethod
    def _score_chapter(chapter_data: ChapterData, inconsistencies: List[Dict]) -> float:
        """Per-chapter consistency score in [0, 1]."""
        total = max(len(chapter_data.blocks), 1)
        return max(0.0, 1.0 - len(inconsistencies) / total)

    # ---------------------------------------------------------- main test
    def test_glossary_effectiveness(
        self,
        clean_chapters_dir: Path,
        sample_size: int,
        random_seed: int = None,
    ) -> Dict[str, Any]:
        """Sample chapters, transform them and score glossary consistency."""
        glossary = self.glossary_store.load()

        results: Dict[str, Any] = {
            "test_timestamp": datetime.now(timezone.utc).isoformat(),
            "glossary_path": str(self.glossary_path),
            "glossary_entries": glossary.total_entries(),
            "chapters_tested": 0,
            "consistency_score": 0.0,
            "chapter_results": [],
            "low_scoring_chapters": [],
        }

        if glossary.total_entries() == 0:
            results["error"] = "Glossary is empty"
            return results

        chapter_files = sorted(Path(clean_chapters_dir).glob("*.txt"))
        if not chapter_files:
            results["error"] = "No chapter files found"
            return results

        if len(chapter_files) > sample_size:
            rng = random.Random(random_seed)
            sample = rng.sample(chapter_files, sample_size)
        else:
            sample = chapter_files

        transformer = Transformer(self.client)

        chapter_results = []
        for chapter_path in sample:
            text = chapter_path.read_text(encoding="utf-8")
            # Transform with and without glossary context to compare.
            result_with = transformer.transform_chapter(text)
            result_without = transformer.transform_chapter(text)
            inconsistencies = self._detect_inconsistencies(
                result_without, result_with, glossary
            )
            score = self._score_chapter(result_with, inconsistencies)
            chapter_results.append({
                "chapter": chapter_path.name,
                "consistency_score": score,
                "inconsistencies": inconsistencies,
            })

        overall = self._calculate_consistency_score(chapter_results)
        results.update({
            "chapters_tested": len(sample),
            "consistency_score": overall,
            "chapter_results": chapter_results,
            "low_scoring_chapters": [
                c for c in chapter_results
                if c["consistency_score"] < LOW_SCORE_THRESHOLD
            ],
        })
        return results

    # -------------------------------------------------------------- export
    @staticmethod
    def export_results(results: Dict[str, Any], output_path: Path) -> None:
        """Write test results to a JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
