"""GlossaryStore: load/save/validate the glossary YAML with CRUD + merge.

Fail-soft on a missing/empty file (returns an empty glossary), fail-hard on
YAML syntax errors, and skip individual invalid entries with a warning so one
bad entry never loses the whole glossary.

Reconstructed from tests/test_context_store.py and tests/test_context_properties.py.
"""

import io
import logging
from pathlib import Path
from typing import List

from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from babel.context.models import Glossary, GlossaryEntry

logger = logging.getLogger(__name__)


class GlossaryStore:
    """Read/write access to a glossary YAML file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        # Round-trip mode preserves comments/formatting across load->save.
        self._yaml = YAML()
        self._yaml.default_flow_style = False
        self._yaml.allow_unicode = True
        self._yaml.preserve_quotes = True
        # The last raw round-trip mapping loaded from disk (keeps comments).
        self._raw = None

    # ------------------------------------------------------------------ load
    def load(self) -> Glossary:
        """Load the glossary, skipping invalid entries (fail-soft)."""
        if not self.path.exists():
            logger.warning("Glossary file not found, using empty glossary: %s", self.path)
            self._raw = None
            return Glossary()

        text = self.path.read_text(encoding="utf-8")
        data = self._yaml.load(text)  # raises YAMLError on bad syntax (fail-hard)

        # Keep the round-trip mapping so save() can preserve comments.
        self._raw = data if isinstance(data, dict) else None

        if not data:
            return Glossary()

        glossary = Glossary()
        for category in Glossary.CATEGORIES:
            entries = data.get(category) or []
            target = glossary.get_category(category)
            for raw_entry in entries:
                try:
                    if not isinstance(raw_entry, dict):
                        raise ValueError("entry is not a mapping")
                    target.append(GlossaryEntry(**raw_entry))
                except (ValidationError, ValueError, TypeError) as e:
                    logger.warning(
                        "Skipping invalid %s entry (%r): %s", category, raw_entry, e
                    )

        return glossary

    # ------------------------------------------------------------------ save
    def save(self, glossary: Glossary) -> None:
        """Write the glossary to its YAML file.

        If a round-trip mapping was previously loaded from this file, its
        entry lists are updated in place so comments/formatting are preserved.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if self._raw is not None:
            out = self._raw
            for category in Glossary.CATEGORIES:
                out[category] = [e.model_dump() for e in glossary.get_category(category)]
        else:
            out = glossary.model_dump()

        stream = io.StringIO()
        self._yaml.dump(out, stream)
        self.path.write_text(stream.getvalue(), encoding="utf-8")

    # -------------------------------------------------------------- validate
    def validate(self) -> List[str]:
        """Return a list of error strings (YAML syntax only); [] if OK."""
        if not self.path.exists():
            return [f"Glossary file not found: {self.path}"]

        try:
            self._yaml.load(self.path.read_text(encoding="utf-8"))
        except YAMLError as e:
            return [f"YAML syntax error in {self.path}: {e}"]

        return []

    # ---------------------------------------------------------------- export
    def export_to_json(self) -> dict:
        """Load the glossary and return it as a plain JSON-serializable dict."""
        return self.load().model_dump()

    # ------------------------------------------------------------------- CRUD
    def add_entry(self, category: str, entry: GlossaryEntry) -> Glossary:
        """Add an entry if its name isn't already present, then persist."""
        glossary = self.load()
        target = glossary.get_category(category)
        if not any(e.name == entry.name for e in target):
            target.append(entry)
            self.save(glossary)
        return glossary

    def update_entry(self, category: str, name: str, updated: GlossaryEntry) -> Glossary:
        """Replace the entry matching ``name`` with ``updated``, then persist."""
        glossary = self.load()
        target = glossary.get_category(category)
        for i, e in enumerate(target):
            if e.name == name:
                target[i] = updated
                self.save(glossary)
                break
        return glossary

    def delete_entry(self, category: str, name: str) -> Glossary:
        """Remove the entry matching ``name``, then persist."""
        glossary = self.load()
        target = glossary.get_category(category)
        setattr(glossary, category, [e for e in target if e.name != name])
        self.save(glossary)
        return glossary

    # ------------------------------------------------------------------ merge
    def merge(self, new_glossary: Glossary) -> Glossary:
        """Merge a newly extracted glossary into the stored one.

        On a name collision the user-edited entry is preserved and only its
        ``raw`` field is refreshed from the new extraction; otherwise the new
        entry is appended. Idempotent. Does not persist (caller saves).
        """
        existing = self.load()
        for category in Glossary.CATEGORIES:
            target = existing.get_category(category)
            by_name = {e.name: e for e in target}
            for new_entry in new_glossary.get_category(category):
                if new_entry.name in by_name:
                    by_name[new_entry.name].raw = new_entry.raw
                else:
                    target.append(new_entry)
                    by_name[new_entry.name] = new_entry
        return existing
