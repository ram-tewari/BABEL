"""Shared HTML rendering of a chapter view for exports (HTML file and EPUB)."""

from __future__ import annotations

import html
import re

from babel.store.db import Store

# 12 hues, chosen to stay readable on both white and near-black pages.
SLOT_COLORS = [
    "#c2410c", "#0369a1", "#15803d", "#a21caf", "#b45309", "#0f766e",
    "#be123c", "#4338ca", "#4d7c0f", "#7e22ce", "#0e7490", "#9f1239",
]

_EM_RE = re.compile(r"\*([^*\n]+)\*")

CSS = """
body { font-family: Georgia, 'Iowan Old Style', serif; line-height: 1.6; margin: 0 auto; max-width: 42em; padding: 0 1em; }
h1.chapter { font-size: 1.4em; text-align: center; margin: 2em 0 1.5em; }
p.nar { margin: 0.9em 0; text-align: left; }
div.line { margin: 0.8em 0; overflow: hidden; }
div.line.right { text-align: right; }
div.line .who { font-family: sans-serif; font-size: 0.75em; font-weight: bold; letter-spacing: 0.03em; text-transform: uppercase; margin-bottom: 0.15em; }
div.line .say { display: inline-block; text-align: left; max-width: 82%; padding: 0.45em 0.8em; border-radius: 0.9em; border: 1px solid; border-left-width: 4px; }
div.line.right .say { border-left-width: 1px; border-right-width: 4px; }
div.line.thought .say { border-style: dashed; font-style: italic; }
div.line.shout .say { font-weight: bold; }
div.line.whisper .say { font-size: 0.9em; opacity: 0.8; }
p.act { font-style: italic; margin: 0.6em 0; padding-left: 1em; border-left: 3px solid; }
p.act.right { text-align: right; padding-left: 0; padding-right: 1em; border-left: 0; border-right: 3px solid; }
p.tag { font-size: 0.8em; opacity: 0.7; margin: -0.4em 0 0.8em; font-style: italic; }
p.tag.right { text-align: right; }
div.sys { font-family: monospace; font-size: 0.9em; border: 1px solid; padding: 0.5em 0.8em; margin: 1em 0; }
p.sfx { text-align: center; font-family: sans-serif; font-weight: bold; letter-spacing: 0.1em; font-size: 1.15em; margin: 1em 0; }
p.brk { text-align: center; margin: 1.5em 0; letter-spacing: 0.6em; }
"""


def color_of(c: dict | None) -> str:
    if not c:
        return "#6b7280"
    col = c.get("color") or ""
    if col.startswith("slot:"):
        return SLOT_COLORS[int(col[5:]) % len(SLOT_COLORS)]
    return col if re.fullmatch(r"#[0-9a-fA-F]{3,8}", col) else "#6b7280"


def _inline(text: str) -> str:
    return _EM_RE.sub(r"<em>\1</em>", html.escape(text))


def render_blocks(view: dict) -> str:
    chars = {c["id"]: c for c in view["characters"]}
    out: list[str] = [f'<h1 class="chapter">{html.escape(view["title"])}</h1>']
    last_side = "left"
    for b in view["blocks"]:
        t = b["type"]
        if t in ("dialogue", "thought"):
            c = chars.get(b["character_id"]) if b["character_id"] else None
            name = c["name"] if c else (b["speaker"] or ("Inner voice" if t == "thought" else "Unknown"))
            side = (c or {}).get("side", "left")
            last_side = side
            col = color_of(c)
            tone = b.get("tone") or ""
            out.append(
                f'<div class="line {side} {t} {tone}"><div class="who" style="color:{col}">{html.escape(name)}'
                + (f' <span style="font-weight:normal;opacity:.7">({tone})</span>' if tone and tone not in ("shout",) else "")
                + '</div>'
                f'<div class="say" style="border-color:{col}">{_inline(b["text"])}</div></div>'
            )
        elif t == "action":
            c = chars.get(b["character_id"]) if b["character_id"] else None
            side = (c or {}).get("side", "left")
            out.append(f'<p class="act {side}" style="border-color:{color_of(c)}">{_inline(b["text"])}</p>')
        elif t == "tag":
            out.append(f'<p class="tag {last_side}">{_inline(b["text"])}</p>')
        elif t == "system":
            out.append(f'<div class="sys">{_inline(b["text"])}</div>')
        elif t == "sfx":
            out.append(f'<p class="sfx">{_inline(b["text"].strip("*"))}</p>')
        elif t == "break":
            out.append('<p class="brk">* * *</p>')
        else:
            out.append(f'<p class="nar">{_inline(b["text"])}</p>')
    return "\n".join(out)


def chapters_in_range(store: Store, novel_id: int, first: int | None, last: int | None) -> list[dict]:
    sql = "SELECT id, idx FROM chapters WHERE novel_id=?"
    args: list = [novel_id]
    if first is not None:
        sql += " AND idx>=?"
        args.append(first)
    if last is not None:
        sql += " AND idx<=?"
        args.append(last)
    return store.q(sql + " ORDER BY idx", args)
