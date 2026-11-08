"""Tier 0 — the standardized converter.

Turns segments into typed Decisions with confidence, using only patterns:
speech tags, action beats, sound effects, system brackets and tone verbs.
Speakers are attached later by the resolver (``resolve.py``), which has memory.
Everything here is deterministic, instant and free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from babel.models import BlockType, Decision, Segment, SegmentKind, Tier

SPEECH_VERBS = set(
    "said says say asked asks ask replied replies reply answered answers shouted shouts yelled yells "
    "whispered whispers muttered mutters murmured murmurs called calls cried cries exclaimed exclaims "
    "added adds continued continues explained explains responded responds remarked remarks demanded "
    "demands began begins sighed sighs laughed laughs snapped snaps hissed hisses growled growls "
    "stammered stammers stuttered stutters spoke speaks shrieked shrieks screamed screams roared roars "
    "mumbled mumbles interrupted interrupts insisted insists agreed agrees countered counters warned "
    "warns chuckled chuckles grumbled grumbles noted notes urged urges pleaded pleads questioned "
    "questions admitted admits declared declares announced announces groaned groans breathed whimpered "
    "retorted retorts teased teases inquired inquires queried bellowed bellows sneered sneers scoffed "
    "scoffs giggled giggles sobbed sobs wept snarled snarls barked barks drawled drawls echoed echoes "
    "repeated repeats corrected corrects offered offers pressed presses prompted prompts "
    "confirmed confirms joked jokes ordered orders commanded commands concluded concludes cursed curses "
    "chanted chants yelped blurted blurts uttered utters stated states quipped quips praised lamented "
    "laments probed probes guessed summarized summarised disparaged greeted greets reminded reminds "
    "assured assures complained complains protested protests suggested suggests mentioned mentions "
    "reassured grunted grunts gasped gasps rasped croaked boasted boasts mocked mocks taunted taunts "
    "comforted consoled instructed informed acknowledged".split()
)
THOUGHT_VERBS = set("thought thinks think wondered wonders mused muses reflected reflects pondered ponders "
                    "realized realised realizes".split())
_VERBS = "|".join(sorted(SPEECH_VERBS | THOUGHT_VERBS, key=len, reverse=True))
TITLE = r"(?:(?:Mr|Mrs|Ms|Mx|Dr|Prof|Capt|Lt|Sgt|St|Fr|Sr)\.\s+)"
_NAME = rf"({TITLE}?(?:[A-Z][\w'’\-]+)(?:\s+(?:[A-Z][\w'’\-]+|of|de|van|von)){{0,3}})"
NAME_VERB_RE = re.compile(rf"\b{_NAME}\s+(?:\w+ly\s+)?(?:[a-z]+ed\s+and\s+)?(?:{_VERBS})\b")
VERB_NAME_RE = re.compile(rf"\b(?:{_VERBS})\s+{_NAME}\b")
PRONOUN_VERB_RE = re.compile(rf"\b(he|she|they|i|we)\s+(?:\w+ly\s+)?(?:{_VERBS})\b", re.I)
THOUGHT_TAG_RE = re.compile(rf"\b(?:{'|'.join(sorted(THOUGHT_VERBS, key=len, reverse=True))})\b", re.I)
SUBJECT_RE = re.compile(rf"^{TITLE}?(?:[A-Z][\w'’\-]+)(?:\s+[A-Z][\w'’\-]+){{0,2}}(?=[’']s\b|\s+(?:\w+ly\s+)?[a-z])")
_ABBREV_RE = re.compile(r"\b(Mr|Mrs|Ms|Mx|Dr|Prof|Capt|Lt|Sgt|St|Fr|Sr|Jr|vs|etc)\.")


def sentences(text: str) -> list[str]:
    """Split prose into sentences without breaking at 'Mr.' / 'Dr.'."""
    protected = _ABBREV_RE.sub(lambda m: m.group(1) + "\u2024", text)
    return [x.replace("\u2024", ".") for x in re.split(r"(?<=[.!?…])\s+", protected) if x.strip()]
PRONOUN_SUBJECT_RE = re.compile(r"^(?:(?:Then|Next|Finally|Afterwards|Suddenly|Meanwhile|Still|Instead),\s+)?(He|She|They|I|We|he|she|they)\s+[a-z]")

NOT_NAMES = set("""
The A An He She They It I We You His Her Their This That Then But And When While After Before As Now Yes No
Oh Ah Well So If What Why How Who Where Mr Mrs Ms Sir Lady Lord Miss Everyone Someone Nobody Suddenly At In
On Of To For With From By Into Upon Under Over Since Until Though Although Because Once Still Even Just There
Here These Those My Your Our Its Some Every Each Both All Many Most Only Perhaps Maybe Finally Meanwhile Soon
Later Today Tonight Tomorrow Yesterday Inside Outside Without Instead Besides However Moreover Clearly
Obviously Naturally Again Thank Please Sorry Hello Hey Hmm Huh Okay Ok Right Good Not Nothing Something
Anything Everything Somewhere Nowhere Not Hah Haha Damn Wait Look Listen Come Go Let Don't Can't Won't Is Are
Was Were Do Does Did Have Has Had Will Would Could Should May Might Must Like Unlike Despite Through
Chapter Volume Book Part
Having Being Seeing Hearing Saying Knowing Feeling Thinking Looking Turning Taking Getting Making Holding Nodding Smiling Shaking Watching Noticing Realizing Remembering Upon Without Ignoring
""".split())

TONE_VERBS = {
    "shout": "shouted shouts yelled yells roared roars screamed screams bellowed bellows shrieked shrieks barked",
    "whisper": "whispered whispers murmured murmurs muttered mutters breathed mumbled mumbles",
    "angry": "snapped snaps growled growls hissed hisses snarled snarls demanded",
    "sad": "sobbed sobs wept whimpered",
    "laugh": "laughed laughs chuckled chuckles giggled giggles",
    "nervous": "stammered stammers stuttered stutters",
    "cold": "coldly icily sneered sneers scoffed scoffs drawled",
}
_TONE_OF = {w: tone for tone, words in TONE_VERBS.items() for w in words.split()}

_SOUND_WORDS = set(
    "bang boom crash thud thump knock clang clank creak whoosh swoosh slam crack ding dong ring buzz bzz hiss "
    "splash snap pop click clack tap thwack whack smack bam pow zap rumble roar screech beep drip plop rustle "
    "sizzle tick tock woosh zoom vroom thunk clink jingle growl kaboom thwip shing clatter rattle gulp groan "
    "gasp cough sniff clap crunch munch slurp gurgle wham whirr whir squeak squelch ping plink hic achoo".split()
)
_SYSTEM_WORDS = re.compile(
    r"\b(level|lv\.?|skill|quest|status|system|hp|mp|sp|exp|xp|acquired|obtained|reward|title|class|stat|"
    r"notification|warning|alert|rank|achievement|inventory|item|mission|ding|unlocked|learned|"
    r"strength|agility|intelligence|mana)\b", re.I)


_CONTRACTION_RE = re.compile(r"[’'](?:ll|m|ve|d|re|t)$", re.I)


def clean_name(name: str) -> str | None:
    if any(_CONTRACTION_RE.search(w) for w in name.split()):
        return None  # "I’ll", "Don’t" are never names
    name = re.sub(r"[’']s?$", "", name.strip())
    parts = name.split()
    while parts and parts[0] in NOT_NAMES:
        parts.pop(0)
    while parts and parts[-1].lower() in ("of", "de", "van", "von"):
        parts.pop()
    return " ".join(parts) or None


def tag_speaker(text: str) -> str | None:
    """'Tobin said, frowning' / 'asked Old Harrow' → name."""
    for rx in (NAME_VERB_RE, VERB_NAME_RE):
        for m in rx.finditer(text):
            name = clean_name(m.group(1))
            if name:
                return name
    return None


_PAST_VERBS = "|".join(sorted((v for v in SPEECH_VERBS if not v.endswith("s") or v in ("says", "asks")),
                              key=len, reverse=True))
_DESC_TAG_RE = re.compile(
    rf"\b(?:the|a|an)\s+((?:[a-z][\w\-]*\s+){{0,2}}[a-z][\w\-]*)\s+(?:\w+ly\s+)?(?:{_PAST_VERBS})\b"
    rf"|\b(?:{_PAST_VERBS})\s+the\s+((?:[a-z][\w\-]*\s+){{0,2}}[a-z][\w\-]*)\b"
)
_DESC_GLUE = {"and", "or", "but", "then", "with", "to", "of", "in", "as", "at", "while", "who", "that", "was", "had"}
_DESC_STOP = {"smile", "grin", "laugh", "sigh", "nod", "look", "glance", "voice", "words", "sound", "reply", "answer", "question", "door", "wind", "system", "letter", "note"}


def tag_description(text: str) -> str | None:
    """'the circus fortune-teller said' → 'Circus fortune-teller' (an unnamed minor character)."""
    m = _DESC_TAG_RE.search(text)
    if not m:
        return None
    phrase = (m.group(1) or m.group(2) or "").strip()
    words = phrase.split()
    if not words or words[-1] in _DESC_STOP or any(w in _DESC_GLUE for w in words):
        return None
    return phrase[0].upper() + phrase[1:]


# Verbs that introduce speech in a lead-in ("Dunn shouted out to him." / "he turned around to ask,")
_LEAD_VERBS = "|".join(sorted(SPEECH_VERBS | set(
    "say shout ask call speak yell reply answer explain continue add whisper cry mutter murmur respond "
    "saying shouting asking calling speaking yelling replying answering explaining continuing adding "
    "whispering crying muttering murmuring responding".split()), key=len, reverse=True))
_LEAD_VERB_RE = re.compile(rf"\b(?:{_LEAD_VERBS})\b")
_LEAD_NAME_RE = re.compile(rf"\b{_NAME}\s+(?:\w+ly\s+)?(?:out\s+)?(?:{_LEAD_VERBS})\b")
_LEAD_SUBJ_RE = re.compile(
    rf"^(?:[^,\"“”]{{0,60}},\s+)?(?:({TITLE}?[A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){{0,2}})|(he|she|i|He|She|I))"
    rf"\s+(?:\w+ly\s+)?[a-z]")


def lead_speaker(sentence: str) -> tuple[str | None, str | None, bool]:
    """Who a speech-introducing sentence points at: (name, pronoun, strong).

    'strong' means the name sits right before the speech verb ("Dunn shouted"),
    otherwise it is the sentence's subject ("Klein squeezed out a smile and turned to ask,").
    """
    sentence = sentence.strip()
    if len(sentence.split()) > 40 or not _LEAD_VERB_RE.search(sentence):
        return None, None, False
    for m in _LEAD_NAME_RE.finditer(sentence):
        n = clean_name(m.group(1))
        if n:
            return n, None, True
    m = _LEAD_SUBJ_RE.match(sentence)
    if not m:
        return None, None, False
    if m.group(1):
        n = clean_name(m.group(1))
        return (n, None, False) if n else (None, None, False)
    return None, m.group(2).lower(), False


def tag_pronoun(text: str) -> str | None:
    m = PRONOUN_VERB_RE.search(text)
    return m.group(1).lower() if m else None


def subject_name(text: str) -> str | None:
    m = SUBJECT_RE.match(text.strip())
    return clean_name(m.group(0)) if m else None


def is_speech_tag(text: str) -> bool:
    if len(text.split()) > 16:
        return False
    return bool(PRONOUN_VERB_RE.search(text) or NAME_VERB_RE.search(text) or VERB_NAME_RE.search(text)
                or _DESC_TAG_RE.search(text))


def looks_like_sfx(text: str) -> bool:
    t = text.strip().strip("*\"“”「」『』")
    words = re.findall(r"[a-z]+", t.lower())
    if not words or len(t) > 50 or len(words) > 6:
        return False
    end = t.rstrip()[-1:]
    if all(w.rstrip("s") in _SOUND_WORDS or w in _SOUND_WORDS for w in words) and end in "!…~.-—":
        return True
    letters = [c for c in t if c.isalpha()]
    upper = sum(c.isupper() for c in letters) / max(1, len(letters))
    return (upper > 0.85 and len(letters) >= 3 and len(words) <= 3 and end in "!~…") or bool(
        re.search(r"([A-Za-z])\1{3,}", t))


def tone_of(tag_text: str, quote_text: str) -> str | None:
    for w in re.findall(r"[a-z]+", tag_text.lower()):
        if w in _TONE_OF:
            return _TONE_OF[w]
    inner = quote_text.strip("\"“”「」『』")
    caps = [w for w in re.findall(r"[A-Za-z]{3,}", inner) if w.isupper()]
    if inner.count("!") >= 2 or (caps and len(caps) >= max(2, len(inner.split()) // 2)):
        return "shout"
    return None


@dataclass
class ParaInfo:
    """What the converter learned about one paragraph (used by the resolver)."""

    idx: int
    segs: list[Segment]
    tag_name: str | None = None  # name from a speech tag ("Tobin said")
    tag_pronoun: str | None = None  # "she said" → "she"
    tag_desc: str | None = None  # "the fortune-teller said" → "Fortune-teller"
    thought_tag: bool = False
    subject: str | None = None  # "Tobin shook his head." → "Tobin" (first sentence)
    actors: list[str] = field(default_factory=list)  # named subjects of every prose sentence, in order
    subject_pronoun: str | None = None
    names: list[str] = field(default_factory=list)  # capitalized names in the prose
    quotes: list[Segment] = field(default_factory=list)
    spoken: list[Segment] = field(default_factory=list)  # quote / thought segments
    unclosed: bool = False  # speech continues in the next paragraph
    # a speech verb right before a quote in this paragraph ("She lowered her voice and said,")
    intro: tuple[str | None, str | None, bool] = (None, None, False)
    intro_antecedents: tuple[str, ...] = ()  # names before the pronoun ("Just as Klein was vexing, he answered,")
    # a narration paragraph that introduces the next one's speech ("Dunn suddenly shouted out to him.")
    lead: tuple[str | None, str | None, bool] = (None, None, False)
    first_person: bool = False


_CAP_RE = re.compile(r"(?<![.!?]\s)(?<!^)\b((?:(?:Mr|Mrs|Ms|Dr|Prof|Capt)\.\s+)?[A-Z][a-z’'\-]+(?:\s+[A-Z][a-z’'\-]+){0,2})")


def _prose_names(text: str) -> list[str]:
    out = []
    for m in _CAP_RE.finditer(text):
        n = clean_name(m.group(1))
        if n and n.split()[0] not in NOT_NAMES:
            out.append(n)
    s = subject_name(text)
    if s:
        out.insert(0, s)
    return list(dict.fromkeys(out))


_MID_CAP_RE = re.compile(r"(?<=[a-z,;:—–\-]\s)([A-Z][\w'’\-]+)")


def proper_nouns(segments: list[Segment]) -> set[str]:
    """Words that appear capitalized *mid-sentence* somewhere in the chapter — evidence of a name.

    A word that is only ever capitalized at the start of a sentence ("Moments after…",
    "Retracting his hand…") is not trusted as a name.
    """
    words: set[str] = set()
    for s in segments:
        words.update(m.group(1) for m in _MID_CAP_RE.finditer(s.text))
    return words - NOT_NAMES


def _trusted(name: str | None, nouns: set[str]) -> str | None:
    if not name:
        return None
    parts = [p for p in name.replace(".", ". ").split() if p[:1].isupper()]
    core = [p for p in parts if not re.match(TITLE.rstrip("?"), p + " ")]
    if re.match(TITLE, name + " ") or len(core) >= 2 or any(p in nouns for p in core):
        return name
    return None


def convert(segments: list[Segment], known: set[str] | None = None) -> tuple[dict[int, Decision], list[ParaInfo]]:
    """Assign a block type (+ tone, + rule-level evidence) to every segment.

    ``known`` are names the Akashic Record already knows (trusted even at sentence starts).
    """
    nouns = proper_nouns(segments) | {w for k in (known or set()) for w in k.split()}
    # "Tobin said" is evidence that Tobin is a name everywhere in the chapter
    for seg in segments:
        if seg.kind == SegmentKind.PROSE and is_speech_tag(seg.text):
            n = tag_speaker(seg.text)
            if n:
                nouns.update(w for w in n.split() if w[:1].isupper())
    by_para: dict[int, list[Segment]] = {}
    for s in segments:
        by_para.setdefault(s.para, []).append(s)

    decisions: dict[int, Decision] = {}
    paras: list[ParaInfo] = []
    prev_spoken_para = False
    for p in sorted(by_para):
        segs = by_para[p]
        info = ParaInfo(idx=p, segs=segs)
        prose = [s for s in segs if s.kind == SegmentKind.PROSE]
        info.quotes = [s for s in segs if s.kind == SegmentKind.QUOTE and not looks_like_sfx(s.text)]
        emph = [s for s in segs if s.kind == SegmentKind.EMPHASIS and not looks_like_sfx(s.text)]
        prose_text = " ".join(s.text for s in prose)
        info.thought_tag = bool(THOUGHT_TAG_RE.search(prose_text))
        for s in prose:
            info.tag_name = info.tag_name or (tag_speaker(s.text) if is_speech_tag(s.text) else None)
            info.tag_pronoun = info.tag_pronoun or (tag_pronoun(s.text) if is_speech_tag(s.text) else None)
            if len(s.text.split()) <= 16 and not _trusted(subject_name(s.text), nouns):
                info.tag_desc = info.tag_desc or tag_description(s.text)
        for i, s in enumerate(segs[:-1]):
            if (s.kind == SegmentKind.PROSE and segs[i + 1].kind == SegmentKind.QUOTE
                    and s.text.rstrip().endswith((",", ":", "—", "–"))):
                sent = sentences(s.text)[-1]
                name, pron, strong = lead_speaker(sent)
                if name and _trusted(name, nouns) or pron:
                    info.intro = (name, pron, strong)
                    if pron:
                        head = re.split(rf"\b{pron}\b", sent, maxsplit=1, flags=re.I)[0]
                        info.intro_antecedents = tuple(n for n in _prose_names(head) if _trusted(n, nouns))
                    break
        if prose and not info.quotes and not emph and segs[-1].kind == SegmentKind.PROSE:
            last_sent = sentences(prose_text)[-1] if prose_text.strip() else ""
            if last_sent.rstrip().endswith((".", ":", "—", "–")):
                name, pron, strong = lead_speaker(last_sent)
                if name and _trusted(name, nouns) or pron:
                    info.lead = (name, pron, strong)
        if prose:
            info.subject = _trusted(subject_name(prose[0].text), nouns)
            m = PRONOUN_SUBJECT_RE.match(prose[0].text)
            info.subject_pronoun = m.group(1).lower() if m else None
            info.names = [n for n in _prose_names(prose_text) if _trusted(n, nouns)]
            for sent in sentences(prose_text):
                a = _trusted(subject_name(sent), nouns)
                if a:
                    info.actors.append(a)
        info.first_person = bool(re.search(r"\b(I|my|me)\b", prose_text))
        last = segs[-1]
        if last.kind == SegmentKind.QUOTE:
            t = last.text.rstrip()
            info.unclosed = not t.endswith(("”", "」", "』", "»")) and (t.count('"') % 2 == 1 or t[:1] in "“「『«")

        has_speech = bool(info.quotes or emph)
        tag_text = " ".join(s.text for s in prose if is_speech_tag(s.text))
        for s in segs:
            words = len(s.text.split())
            if s.kind == SegmentKind.BREAK:
                d = Decision(type=BlockType.BREAK, conf=1.0)
            elif s.kind == SegmentKind.BRACKET:
                if _SYSTEM_WORDS.search(s.text) or ":" in s.text:
                    d = Decision(type=BlockType.SYSTEM, conf=0.97, why="system-style bracket")
                elif words >= 3:
                    d = Decision(type=BlockType.SYSTEM, conf=0.8, why="bracketed text")
                else:
                    d = Decision(type=BlockType.NARRATION, conf=0.7, why="short bracket")
            elif s.kind == SegmentKind.EMPHASIS:
                if looks_like_sfx(s.text):
                    d = Decision(type=BlockType.SFX, conf=0.85, why="sound word in italics")
                elif info.thought_tag:
                    d = Decision(type=BlockType.THOUGHT, conf=0.95, why="thought tag")
                elif info.quotes:
                    d = Decision(type=BlockType.THOUGHT, conf=0.75, why="italics beside speech")
                elif words > 60:
                    d = Decision(type=BlockType.THOUGHT, conf=0.5, why="long italic passage (letter? flashback?)")
                else:
                    d = Decision(type=BlockType.THOUGHT, conf=0.82, why="italic line")
            elif s.kind == SegmentKind.QUOTE:
                if looks_like_sfx(s.text):
                    d = Decision(type=BlockType.SFX, conf=0.8, why="quoted sound")
                elif info.thought_tag and not info.tag_name and not info.tag_pronoun:
                    d = Decision(type=BlockType.THOUGHT, conf=0.75, why="quoted thought")
                else:
                    d = Decision(type=BlockType.DIALOGUE, conf=0.95, tone=tone_of(tag_text, s.text))
            else:  # prose
                if has_speech and is_speech_tag(s.text):
                    d = Decision(type=BlockType.TAG, conf=0.92, why="speech tag")
                elif looks_like_sfx(s.text):
                    d = Decision(type=BlockType.SFX, conf=0.85, why="sound word")
                elif (info.quotes or prev_spoken_para) and words <= 22 and (
                        _trusted(subject_name(s.text), nouns) or PRONOUN_SUBJECT_RE.match(s.text)):
                    d = Decision(type=BlockType.ACTION, conf=0.8, why="short beat by a character")
                else:
                    d = Decision(type=BlockType.NARRATION, conf=0.95)
            d.tier = Tier.RULE
            decisions[s.id] = d
            if d.type in (BlockType.DIALOGUE, BlockType.THOUGHT):
                info.spoken.append(s)
        prev_spoken_para = bool(info.quotes)
        paras.append(info)
    return decisions, paras
