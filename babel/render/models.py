"""Render-side view models.

``Chapter`` is a lightweight table-of-contents entry used when building the
navigation/TOC context for the chapter template.

Reconstructed from the render test suite.
"""

from typing import Optional

from pydantic import BaseModel


class Chapter(BaseModel):
    """A single table-of-contents entry for the rendered navigation."""

    index: int
    filename: str
    title: str
    is_current: bool = False
