"""ContextInjector: weave the glossary into the transform prompt.

Formats the glossary as a Markdown context block and prepends it to the base
prompt, with token-budgeted truncation that prioritizes characters.

Reconstructed from tests/test_context_injector.py.
"""

import logging
from typing import List

from babel.context.models import Glossary, GlossaryEntry
from babel.context.store import GlossaryStore

# Category label -> model attribute, in injection priority order.
_PRIORITY = (
    ("Characters", "characters"),
    ("Factions", "factions"),
    ("Locations", "locations"),
    ("Terms", "terms"),
)

_HEADER = (
    "## NARRATIVE CONTEXT & GLOSSARY\n\n"
    "**CRITICAL**: You MUST adhere to the following naming conventions and "
    "details for consistency across the adaptation.\n"
)
_FOOTER = (
    "**REMINDER**: Use these exact names and terms consistently with the "
    "glossary above.\n"
)


class ContextInjector:
    """Injects glossary context into a transform prompt."""

    def __init__(self, store: GlossaryStore):
        self.store = store
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _estimate_token_count(text: str) -> int:
        """Rough token estimate: ~4 characters per token."""
        return len(text) // 4

    @staticmethod
    def _format_entry(entry: GlossaryEntry) -> List[str]:
        """Format a single entry as a list of Markdown lines."""
        lines = [f"- **{entry.name}** ({entry.raw})"]
        if entry.aliases:
            lines.append(f"  Aliases: {', '.join(entry.aliases)}")
        if entry.desc:
            lines.append(f"  Context: {entry.desc}")
        return lines

    def _format_glossary_section(self, glossary: Glossary) -> str:
        """Format the full glossary as a Markdown context block."""
        parts = [_HEADER]
        for label, attr in _PRIORITY:
            entries = glossary.get_category(attr)
            if not entries:
                continue
            parts.append(f"\n### {label}\n")
            for entry in entries:
                parts.append("\n".join(self._format_entry(entry)))
        parts.append("\n" + _FOOTER)
        return "\n".join(parts)

    def _truncate_glossary(self, glossary: Glossary, max_tokens: int) -> str:
        """Format the glossary within a token budget, prioritizing characters."""
        total = glossary.total_entries()
        parts = [_HEADER]
        included = 0
        truncated = False

        def fits(extra: str) -> bool:
            notice = f"\n_Truncated: {included} of {total} entries shown._\n"
            candidate = "".join(parts) + extra + notice + "\n" + _FOOTER
            return self._estimate_token_count(candidate) <= max_tokens

        for label, attr in _PRIORITY:
            entries = glossary.get_category(attr)
            if not entries:
                continue
            header_added = False
            for entry in entries:
                block = ("" if header_added else f"\n### {label}\n")
                block += "\n".join(self._format_entry(entry)) + "\n"
                if fits(block):
                    parts.append(block)
                    header_added = True
                    included += 1
                else:
                    truncated = True
                    break
            if truncated:
                break

        result = "".join(parts)
        if truncated or included < total:
            result += f"\n_Truncated: {included} of {total} entries shown._\n"
        result += "\n" + _FOOTER
        return result

    def inject_context(self, base_prompt: str) -> str:
        """Prepend the glossary context block to the base prompt."""
        glossary = self.store.load()
        if glossary.total_entries() == 0:
            return base_prompt
        section = self._format_glossary_section(glossary)
        return f"{section}\n\n{base_prompt}"
