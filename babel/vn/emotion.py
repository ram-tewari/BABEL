"""Which expression each line is said with — rules first, the text model only for the unclear ones.

The rules read what the book already says: the tone the converter detected
(shouted, whispered, sobbed…), the words around the line in the same paragraph
("he smiled", "she trembled", "Klein frowned"), and the line's own punctuation
("What?!"). Lines without a clear cue default to neutral at low confidence and can
be refined in one batched, schema-enforced multiple-choice call per chapter.
"""

from __future__ import annotations

import json
import re

from babel.art.profile import EMOTIONS
from babel.scenario.ask import LETTERS, extract_json

_CUES: list[tuple[str, re.Pattern]] = [(e, re.compile(rx, re.I)) for e, rx in (
    ("laugh", r"\b(laugh\w*|chuckl\w*|giggl\w*|guffaw\w*|snicker\w*|cackl\w*)\b"),
    ("afraid", r"\b(fear\w*|afraid|terrif\w*|trembl\w*|shiver\w*|shudder\w*|panick\w*|frighten\w*|paled|"
               r"turned pale|scared|nervous\w*|stammer\w*|stutter\w*|cower\w*)\b"),
    ("sad", r"\b(sigh\w*|sad\w*|sob\w*|wept|weep\w*|tears?|tearful\w*|choked|lament\w*|bitter\w*|dejected\w*|"
            r"gloom\w*|sorrow\w*|grief|griev\w*|melanchol\w*|mourn\w*)\b"),
    ("angry", r"\b(angr\w*|furious\w*|fury|rage|raging|enraged|glar\w*|snarl\w*|snapped|growl\w*|hiss\w*|"
              r"sneer\w*|scowl\w*|gritted|seethe\w*|seething|indignant\w*|irritat\w*|annoyed)\b"),
    ("surprised", r"\b(surpris\w*|astonish\w*|stunn\w*|shock\w*|startl\w*|taken aback|blurted|gasp\w*|"
                  r"wide-eyed|dumbfounded|baffled|bewildered|puzzled|perplexed|confused)\b"),
    ("happy", r"\b(smil\w*|grin\w*|beam\w*|cheerful\w*|happi\w*|delight\w*|glad\w*|joy\w*|excited\w*|"
              r"eager\w*|warmly|relieved|relief|pleased|elated|amused)\b"),
    ("serious", r"\b(serious\w*|solemn\w*|grave\w*|gravely|stern\w*|cold\w*|coldly|frown\w*|firm\w*|"
                r"earnest\w*|determin\w*|resolute\w*|calmly|composed)\b"),
)]
_TONE = {"laugh": "laugh", "angry": "angry", "sad": "sad", "nervous": "afraid", "cold": "serious", "whisper": None,
         "shout": None}


def rule_emotion(text: str, tone: str | None, context: str) -> tuple[str, float]:
    """(emotion, confidence) for one line from its tone, the words around it, and its punctuation."""
    if tone and _TONE.get(tone):
        return _TONE[tone], 0.85
    for emotion, rx in _CUES:
        if rx.search(context):
            return emotion, 0.68  # a word somewhere in the paragraph: a good hint, worth confirming
    t = text.strip()
    if re.search(r"\?!|!\?", t) or re.match(r"^[\"“]?(what|huh|eh|how|really|impossible)\b[^.]{0,20}[?!]", t, re.I):
        return "surprised", 0.65
    if re.search(r"\b(ha){2,}|\bhehe|\bhaha", t, re.I):
        return "laugh", 0.75
    if tone == "shout" or t.count("!") >= 2:
        return "angry", 0.55  # a shout without other cues: often anger, sometimes alarm — let the model decide
    return "neutral", 0.5


def rule_emotions(blocks: list[dict]) -> dict[int, list]:
    """seg → [emotion, conf, tier] for every dialogue/thought block, from rules."""
    by_para: dict[int, list[dict]] = {}
    for b in blocks:
        by_para.setdefault(b["para"], []).append(b)
    out: dict[int, list] = {}
    for b in blocks:
        if b["type"] not in ("dialogue", "thought"):
            continue
        ctx = " ".join(x["text"] for x in by_para[b["para"]] if x["type"] in ("tag", "action", "narration"))
        e, c = rule_emotion(b["text"], b.get("tone"), ctx)
        out[b["seg"][0]] = [e, round(c, 2), "rule"]
    return out


REFINE_PROMPT = """You help stage a novel as a visual novel. For each marked line, choose the facial expression the
character most likely has while saying or thinking it, from the passage. Answer with one letter per question.
Reply with JSON only: {"choices": ["A", "D", ...]}"""


def refine_messages(blocks: list[dict], targets: list[int], window: int = 2) -> tuple[list[dict], dict, list[int]]:
    """One batched multiple-choice request for the uncertain lines (``targets`` are block indices)."""
    options = "   ".join(f"{LETTERS[i]}) {e}" for i, e in enumerate(EMOTIONS))
    keep: set[int] = set()
    for t in targets:
        keep.update(range(max(0, t - window), min(len(blocks), t + window + 1)))
    marks = {t: n for n, t in enumerate(targets, 1)}
    lines = []
    for i in sorted(keep):
        b = blocks[i]
        who = f"{b['speaker']}: " if b.get("speaker") and b["type"] in ("dialogue", "thought") else ""
        mark = f"⟦Q{marks[i]}⟧" if i in marks else ""
        lines.append(f"{mark}{who}{b['text']}")
    qs = [f"Q{marks[t]}. {blocks[t].get('speaker') or 'The speaker'} — {options}" for t in targets]
    schema = {"type": "object", "properties": {"choices": {
        "type": "array", "items": {"type": "string", "enum": list(LETTERS[:len(EMOTIONS)])},
        "minItems": len(targets), "maxItems": len(targets)}}, "required": ["choices"]}
    user = "PASSAGE\n" + "\n".join(lines) + "\n\nQUESTIONS\n" + "\n".join(qs)
    return [{"role": "system", "content": REFINE_PROMPT}, {"role": "user", "content": user}], schema, targets


def parse_refine(text: str, targets: list[int]) -> dict[int, str]:
    data = extract_json(text)
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or len(choices) != len(targets):
        return {}
    names = list(EMOTIONS)
    out = {}
    for t, c in zip(targets, choices, strict=True):
        c = str(c).strip().upper()[:1]
        if c in LETTERS[:len(names)]:
            out[t] = names[LETTERS.index(c)]
    return out


def dumps(emotions: dict) -> str:
    return json.dumps({str(k): v for k, v in emotions.items()})
