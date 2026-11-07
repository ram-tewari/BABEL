"""Rule-based labeling: works offline with no API keys.

Used as the zero-config mode, as the fallback when an LLM call fails, and to
fill in segments an LLM response leaves out. Speaker attribution looks for
speech tags ("..., Klein said" / "Audrey asked, ...") and known character names
in the same paragraph, then falls back to two-speaker alternation.
"""

from __future__ import annotations

import re

from babel.models import BlockType, Segment, SegmentKind

SPEECH_VERBS = (
    "said says say asked asks ask replied replies reply answered answers shouted shouts yelled "
    "yells whispered whispers muttered mutters murmured murmurs called calls cried cries exclaimed "
    "exclaims added adds continued continues explained explains responded responds remarked "
    "demanded demands began begins sighed sighs laughed laughs snapped snaps hissed hisses growled "
    "growls stammered stammers spoke speaks shrieked screamed screams roared roars mumbled mumbles "
    "interrupted interrupts insisted insists agreed agrees countered counters warned warns "
    "chuckled chuckles grumbled grumbles noted notes urged urges pleaded pleads questioned "
    "admitted admits declared declares announced announces groaned groans breathed whimpered "
    "retorted retorts teased teases inquired inquires queried muttered thought thinks wondered wonders"
).split()
_VERB_ALT = "|".join(sorted(set(SPEECH_VERBS), key=len, reverse=True))
_NAME = r"((?:[A-Z][\w'’\-]+)(?:\s+[A-Z][\w'’\-]+){0,2})"
# "Klein said" / "said Klein" / "Klein Moretti asked quietly"
_NAME_VERB_RE = re.compile(rf"\b{_NAME}\s+(?:\w+ly\s+)?(?:{_VERB_ALT})\b")
_VERB_NAME_RE = re.compile(rf"\b(?:{_VERB_ALT})\s+{_NAME}\b")
_PRONOUN_VERB_RE = re.compile(rf"\b(?:he|she|they|I|we)\s+(?:\w+ly\s+)?(?:{_VERB_ALT})\b", re.I)
_NOT_NAMES = {
    "The", "A", "An", "He", "She", "They", "It", "I", "We", "You", "His", "Her", "Their", "This",
    "That", "Then", "But", "And", "When", "While", "After", "Before", "As", "Now", "Yes", "No",
    "Oh", "Ah", "Well", "So", "If", "What", "Why", "How", "Who", "Where", "Mr", "Mrs", "Ms",
    "Sir", "Lady", "Lord", "Miss", "Everyone", "Someone", "Nobody", "Suddenly",
    "At", "In", "On", "Of", "To", "For", "With", "From", "By", "Into", "Upon", "Under", "Over",
    "Since", "Until", "Though", "Although", "Because", "Once", "Still", "Even", "Just",
    "There", "Here", "These", "Those", "My", "Your", "Our", "Its", "Some", "Every", "Each",
    "Both", "All", "Many", "Most", "Only", "Perhaps", "Maybe", "Finally", "Meanwhile", "Soon",
    "Later", "Today", "Tonight", "Tomorrow", "Yesterday", "Inside", "Outside", "Without",
    "Instead", "Besides", "However", "Moreover", "Clearly", "Obviously", "Naturally", "Again",
    "Thank", "Please", "Sorry", "Hello", "Hey", "Hmm", "Huh", "Okay", "Ok", "Right", "Good",
}


def _clean_name(name: str) -> str | None:
    name = re.sub(r"[’']s?$", "", name.strip())
    parts = name.split()
    while parts and parts[0] in _NOT_NAMES:
        parts.pop(0)
    if not parts:
        return None
    return " ".join(parts)


def find_tag_speaker(text: str) -> str | None:
    for rx in (_NAME_VERB_RE, _VERB_NAME_RE):
        m = rx.search(text)
        if m:
            name = _clean_name(m.group(1))
            if name:
                return name
    return None


def is_speech_tag(text: str) -> bool:
    words = text.split()
    if len(words) > 14:
        return False
    return bool(
        _PRONOUN_VERB_RE.search(text) or _NAME_VERB_RE.search(text) or _VERB_NAME_RE.search(text)
    )


_SOUND_WORDS = set(
    "bang boom crash thud thump knock clang clank creak whoosh swoosh slam crack ding dong ring "
    "buzz bzz hiss splash snap pop click clack tap thwack whack smack bam pow zap rumble roar "
    "screech beep drip plop rustle sizzle tick tock woosh zoom vroom thunk clink jingle growl".split()
)


def looks_like_sfx(text: str) -> bool:
    t = text.strip().strip("*")
    words = re.findall(r"[a-z]+", t.lower())
    if words and len(words) <= 6 and all(w.rstrip("s") in _SOUND_WORDS or w in _SOUND_WORDS for w in words) \
            and t.rstrip()[-1:] in "!…~.-—":
        return True
    if len(t) > 40 or len(t.split()) > 4:
        return False
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 2:
        return False
    upper = sum(c.isupper() for c in letters) / len(letters)
    return (upper > 0.85 and len(letters) >= 3 and t.rstrip()[-1:] in "!~…") or bool(
        re.search(r"([A-Za-z])\1{3,}", t)
    )


_SUBJECT_RE = re.compile(r"^(?:[A-Z][\w'’\-]+)(?:\s+[A-Z][\w'’\-]+)?(?=\s+[a-z])")


def subject_name(text: str) -> str | None:
    """'Tobin shook his head.' → 'Tobin' (a capitalized sentence subject)."""
    m = _SUBJECT_RE.match(text.strip())
    return _clean_name(m.group(0)) if m else None


def _known_name_in(text: str, names: list[str]) -> str | None:
    best: tuple[int, str] | None = None
    for name in names:
        m = re.search(rf"\b{re.escape(name)}\b", text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), name)
    return best[1] if best else None


Label = tuple[BlockType, str | None]


def label_segments(segments: list[Segment], known_names: list[str] | None = None) -> dict[int, Label]:
    """Assign (type, speaker) to every segment."""
    names = sorted(known_names or [], key=len, reverse=True)
    labels: dict[int, Label] = {}
    by_para: dict[int, list[Segment]] = {}
    for s in segments:
        by_para.setdefault(s.para, []).append(s)

    recent: list[str] = []  # speakers of recent dialogue paragraphs, for turn-taking

    for para in sorted(by_para):
        segs = by_para[para]
        quotes = [s for s in segs if s.kind == SegmentKind.QUOTE]
        thoughts = [s for s in segs if s.kind == SegmentKind.EMPHASIS and not looks_like_sfx(s.text)]
        prose = [s for s in segs if s.kind == SegmentKind.PROSE]
        spoken = bool(quotes or thoughts)
        # Who speaks in this paragraph? speech tag > known name > sentence subject > turn-taking
        speaker: str | None = None
        for p in prose:
            speaker = find_tag_speaker(p.text)
            if speaker:
                break
        if not speaker and spoken:
            for p in prose:
                speaker = _known_name_in(p.text, names) or subject_name(p.text)
                if speaker:
                    break
        if not speaker and quotes:
            named = [r for r in recent if r != "?"]
            if len(named) >= 2 and named[-1] != named[-2]:
                speaker = named[-2]

        for s in segs:
            if s.kind == SegmentKind.BREAK:
                labels[s.id] = (BlockType.BREAK, None)
            elif s.kind == SegmentKind.BRACKET:
                labels[s.id] = (BlockType.SYSTEM, None)
            elif s.kind == SegmentKind.EMPHASIS:
                if looks_like_sfx(s.text):
                    labels[s.id] = (BlockType.SFX, None)
                else:
                    labels[s.id] = (BlockType.THOUGHT, speaker if not quotes else None)
            elif s.kind == SegmentKind.QUOTE:
                if looks_like_sfx(s.text.strip("\"“”「」『』")):
                    labels[s.id] = (BlockType.SFX, None)
                else:
                    labels[s.id] = (BlockType.DIALOGUE, speaker)
            else:
                if spoken and is_speech_tag(s.text):
                    labels[s.id] = (BlockType.TAG, None)
                elif looks_like_sfx(s.text):
                    labels[s.id] = (BlockType.SFX, None)
                else:
                    labels[s.id] = (BlockType.NARRATION, None)
        if quotes:
            recent.append(speaker or "?")
            recent = recent[-4:]
        elif prose and sum(len(p.text) for p in prose) > 400:
            recent = []  # a long narrative paragraph breaks the exchange
    return labels
