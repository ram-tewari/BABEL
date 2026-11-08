"""Turn uncertain decisions into small multiple-choice questions, and parse answers.

The model never sees the whole chapter or writes text. It gets a short passage
with the lines in question marked ⟦Q1⟧, ⟦Q2⟧…, a compact character list from the
Akashic Record, and closed options:

    Q1. Who says ⟦Q1⟧ “Not yet.”?   A) Tobin   B) Mira Vell   C) Old Harrow   D) someone else
    Q2. What is ⟦Q2⟧ *Odd.*?         A) inner thought   B) spoken aloud   C) sound effect   D) narration

and must reply {"answers":[{"q":1,"choice":"A"}, {"q":2,"choice":"D"}]} — a
JSON schema enforces it where the backend supports structured output.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from babel.models import BlockType, Decision, Segment, SegmentKind

LETTERS = "ABCDEFGH"
OTHER = "someone else (give the name)"

TYPE_OPTIONS = [
    ("inner thought", BlockType.THOUGHT),
    ("spoken aloud", BlockType.DIALOGUE),
    ("sound effect", BlockType.SFX),
    ("system/game window or written text", BlockType.SYSTEM),
    ("narration (not speech)", BlockType.NARRATION),
]

SYSTEM_PROMPT = """You help turn a novel into a chat-style script. You will see a short passage where some
lines are marked ⟦Q1⟧, ⟦Q2⟧, … and a multiple-choice question about each marked line.

- "Who says/thinks" questions: pick who speaks that exact line. Use speech tags, who acts in the same
  paragraph, turn-taking in conversations, and who is being addressed by name (people don't call
  their own name). Prefer the listed names. Only choose "someone else" if no option fits, and then
  give the name used in the text.
- "What is" questions: classify the marked line.

Reply with JSON only — one letter per question, in order, plus names for any "someone else" picks:
{"choices":["A","D","B"],"names":{"2":"Old Harrow"}}"""


@dataclass
class Question:
    n: int
    seg: int
    kind: str  # "speaker" | "type"
    options: list[str]  # speaker names, or type labels
    para: int
    current: str | None  # the resolver's current best guess (speaker name or type value)


@dataclass
class Batch:
    questions: list[Question]
    messages: list[dict]


@dataclass
class Answer:
    seg: int
    kind: str
    value: str | None  # speaker name, or BlockType value
    other: bool = False


@dataclass
class Plan:
    """Which segments to ask about at a tier, and why."""

    speaker: list[int] = field(default_factory=list)
    type: list[int] = field(default_factory=list)


def plan(decisions: dict[int, Decision], threshold: float, type_threshold: float = 0.7) -> Plan:
    p = Plan()
    for sid, d in decisions.items():
        if d.type in (BlockType.DIALOGUE, BlockType.THOUGHT, BlockType.ACTION) and d.conf < threshold:
            p.speaker.append(sid)
        if d.type in (BlockType.THOUGHT, BlockType.SFX, BlockType.SYSTEM) and d.conf < type_threshold:
            p.type.append(sid)
    return p


def _clip(text: str, keep: bool) -> str:
    words = text.split()
    if keep or len(words) <= 60:
        return text
    return " ".join(words[:30]) + " … " + " ".join(words[-15:])


def _verb(d: Decision) -> str:
    return {BlockType.THOUGHT: "thinks", BlockType.ACTION: "does"}.get(d.type, "says")


def dedupe_names(names: list[str]) -> list[str]:
    """One option per person: 'Aldric' and 'Brother Aldric' collapse into the fuller name."""
    out: list[str] = []
    for n in names:
        toks = set(re.findall(r"\w+", n.lower()))
        hit = next((i for i, o in enumerate(out) if toks <= set(re.findall(r"\w+", o.lower()))
                    or set(re.findall(r"\w+", o.lower())) <= toks), None)
        if hit is None:
            out.append(n)
        elif len(n) > len(out[hit]):
            out[hit] = n
    return out


def build_batches(
    segments: list[Segment],
    decisions: dict[int, Decision],
    p: Plan,
    *,
    cast_lines: list[str],
    story: list[str],
    title: str,
    max_questions: int = 20,
    max_span: int = 40,
) -> list[Batch]:
    by_id = {s.id: s for s in segments}
    items = sorted({(by_id[s].para, s, "type") for s in p.type} | {(by_id[s].para, s, "speaker") for s in p.speaker})
    groups: list[list[tuple[int, int, str]]] = []
    for it in items:
        if groups and len(groups[-1]) < max_questions and it[0] - groups[-1][0][0] <= max_span:
            groups[-1].append(it)
        else:
            groups.append([it])

    paras: dict[int, list[Segment]] = {}
    for s in segments:
        paras.setdefault(s.para, []).append(s)

    batches = []
    for g in groups:
        qs: list[Question] = []
        marks: dict[int, int] = {}
        for i, (para, sid, kind) in enumerate(g, 1):
            d = decisions[sid]
            if kind == "speaker":
                opts = dedupe_names([c for c in ([d.speaker] if d.speaker else []) + d.candidates if c])[:5]
                qs.append(Question(i, sid, kind, opts + [OTHER], para, d.speaker))
            else:
                qs.append(Question(i, sid, kind, type_options(by_id[sid].kind), para, d.type.value))
            marks.setdefault(sid, i)
        lo = max(0, g[0][0] - 3)
        hi = g[-1][0] + 1
        lines = []
        for pn in range(lo, hi + 1):
            if pn not in paras:
                continue
            parts = []
            for s in paras[pn]:
                t = s.text
                if s.id in marks:
                    t = f"⟦Q{marks[s.id]}⟧{t}"
                parts.append(t)
            text = " ".join(parts)
            lines.append(f"[{pn}] " + _clip(text, keep=any(s.id in marks for s in paras[pn])))
        qlines = []
        for q in qs:
            seg = by_id[q.seg]
            quote = seg.text if len(seg.text) <= 90 else seg.text[:87] + "…"
            if q.kind == "speaker":
                ask = f"Who {_verb(decisions[q.seg])} ⟦Q{q.n}⟧ {quote}"
            else:
                ask = f"What is ⟦Q{q.n}⟧ {quote}"
            opts = "   ".join(f"{LETTERS[i]}) {o}" for i, o in enumerate(q.options))
            qlines.append(f"Q{q.n}. {ask}\n    {opts}")
        user = []
        if cast_lines:
            user.append("CHARACTERS\n" + "\n".join(f"- {c}" for c in cast_lines))
        if story:
            user.append("STORY SO FAR\n" + "\n".join(f"- {s}" for s in story[-3:]))
        user.append(f"PASSAGE from “{title}”\n" + "\n".join(lines))
        user.append("QUESTIONS\n" + "\n".join(qlines))
        batches.append(Batch(qs, [{"role": "system", "content": SYSTEM_PROMPT},
                                  {"role": "user", "content": "\n\n".join(user)}]))
    return batches


def answer_schema(batch: Batch) -> dict:
    """Exactly one letter per question (enforced by the local model's grammar)."""
    n = len(batch.questions)
    return {
        "type": "object",
        "properties": {
            "choices": {"type": "array", "items": {"type": "string", "enum": list(LETTERS[:6])},
                        "minItems": n, "maxItems": n},
            "names": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "required": ["choices"],
    }


class ParseError(ValueError):
    pass


def extract_json(text: str) -> dict:
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```\s*$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ParseError("no JSON object in reply")
    t = t[start:end + 1]
    for candidate in (t, re.sub(r",\s*([}\]])", r"\1", t)):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    raise ParseError("invalid JSON in reply")


def parse_answers(text: str, batch: Batch) -> list[Answer]:
    data = extract_json(text)
    raw = data.get("answers")
    if raw is None and isinstance(data.get("choices"), list):  # compact form
        if len(data["choices"]) != len(batch.questions):
            raise ParseError(f"expected {len(batch.questions)} choices, got {len(data['choices'])}")
        names = data.get("names") if isinstance(data.get("names"), dict) else {}
        raw = [{"q": q.n, "choice": c, "name": names.get(str(q.n))} for q, c in zip(batch.questions, data["choices"], strict=True)]
    if not isinstance(raw, list):
        raise ParseError("no answers in reply")
    by_n = {q.n: q for q in batch.questions}
    out: list[Answer] = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        try:
            q = by_n[int(a.get("q"))]
        except (TypeError, ValueError, KeyError):
            continue
        choice = str(a.get("choice", "")).strip().upper()[:1]
        if choice not in LETTERS[: len(q.options)]:
            continue
        opt = q.options[LETTERS.index(choice)]
        if q.kind == "speaker":
            if opt == OTHER:
                name = str(a.get("name") or "").strip()
                if name and len(name) <= 60:
                    out.append(Answer(q.seg, "speaker", name, other=True))
            else:
                out.append(Answer(q.seg, "speaker", opt))
        else:
            out.append(Answer(q.seg, "type", dict(TYPE_OPTIONS)[opt].value))
    if not out and batch.questions:
        raise ParseError("no usable answers")
    return out


def type_options(kind: SegmentKind) -> list[str]:
    """Only the types a segment of this kind can be: unquoted italics are never speech."""
    return [label for label, bt in TYPE_OPTIONS if bt != BlockType.DIALOGUE or kind == SegmentKind.QUOTE]


def kind_ok(segment: Segment, btype: BlockType) -> bool:
    """Guard rails: a model can't turn prose or italics into dialogue, etc."""
    if btype == BlockType.DIALOGUE and segment.kind != SegmentKind.QUOTE:
        return False
    return True
