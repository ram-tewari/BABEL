"""Tier 1 — memory-aware speaker resolution (deterministic, free).

Walks a chapter paragraph by paragraph keeping a small *scene state* — who is
present, who has been talking, whether speech runs on — and combines it with the
Akashic Record (canonical names, aliases, gender, point of view) to score
candidate speakers for every line of dialogue, thought and action beat.

Each decision ends up with a best guess, a confidence and a ranked candidate
list. Confident decisions are final; the rest become multiple-choice questions
for the model tiers — with the candidates already worked out, so the model only
has to pick.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from babel.memory.akashic import Akashic
from babel.models import BlockType, Decision, Segment, SegmentKind, Tier
from babel.scenario.convert import ParaInfo

_LONG_NARRATION_WORDS = 80
_NAME = r"([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+)?)"
# "Pell, you kept…" / "…, Pell." / "You were there, Pell. Tell her." / "Ren."
_VOCATIVES = [
    re.compile(rf"(?:^|[.!?…]\s+)[\"“「『«]?\s*{_NAME}\s*,"),
    re.compile(rf",\s*{_NAME}\s*[.!?…,]"),
    re.compile(rf"^[\"“「『«]?\s*{_NAME}\s*[.!?…]+[\"”」』»]?\s*$"),
]
_MALE_ADDRESS = re.compile(r"\b(sir|lord|brother|master|young master|mister|my lord)\b", re.I)
_FEMALE_ADDRESS = re.compile(r"\b(ma'?am|madam|lady|miss|sister|my lady|mistress)\b", re.I)


@dataclass
class Scene:
    present: dict[str, int] = field(default_factory=dict)  # name -> last paragraph seen
    convo: list[str] = field(default_factory=list)  # recent speakers in the current exchange
    last_speaker: str | None = None
    open_speech: bool = False  # previous paragraph's quote was left open
    last_actor: str | None = None  # subject of the previous narration paragraph ("Okafor stepped out.")
    pending_addressee: str | None = None  # asked a question by name; likely to answer next

    def see(self, name: str | None, para: int) -> None:
        if name:
            self.present[name] = para

    def spoke(self, name: str | None) -> None:
        self.convo.append(name or "?")
        self.convo = self.convo[-6:]
        self.last_speaker = name

    def recent(self) -> list[str]:
        return [n for n, _ in sorted(self.present.items(), key=lambda kv: -kv[1])]


class Resolver:
    def __init__(self, ak: Akashic, first_person: bool = False):
        self.ak = ak
        self.pov = ak.pov_name()
        self.first_person = first_person

    def canon(self, name: str | None) -> str | None:
        if not name:
            return None
        eid = self.ak.lookup(name)
        return self.ak.name(eid) if eid is not None else name

    def gender(self, name: str | None) -> str | None:
        eid = self.ak.lookup(name) if name else None
        g = self.ak.gender(eid)
        if g or not name:
            return g
        if name == self.pov and self.first_person:
            return None
        return title_gender(name)

    def _by_pronoun(self, pronoun: str | None, pool: list[str]) -> str | None:
        if pronoun == "i":
            return self.pov or "Narrator"
        want = {"he": "m", "she": "f"}.get(pronoun or "")
        if not want:
            return None
        matches = [n for n in dict.fromkeys(pool) if n != "?" and self.gender(n) == want]
        return matches[0] if len(matches) == 1 else None

    def _addressee(self, text: str, scene: Scene) -> str | None:
        inner = text.strip()
        for rx in _VOCATIVES:
            for m in rx.finditer(inner):
                name = self.canon(m.group(1))
                if name and (name in scene.present or self.ak.lookup(name) is not None):
                    return name
        # "Yes, sir." / "ma'am" — addressing someone of known gender
        want = "m" if _MALE_ADDRESS.search(inner) else "f" if _FEMALE_ADDRESS.search(inner) else None
        if want:
            match = [n for n in dict.fromkeys(reversed(scene.convo)) if n != "?" and self.gender(n) == want]
            if len(match) == 1:
                return match[0]
        return None

    def run(self, segments: list[Segment], decisions: dict[int, Decision], paras: list[ParaInfo]) -> None:
        scene = self._new_scene()
        for info in paras:
            if any(s.kind == SegmentKind.BREAK for s in info.segs):
                scene = self._new_scene()
                continue
            for n in info.names:
                scene.see(self.canon(n), info.idx)

            words = sum(len(s.text.split()) for s in info.segs if s.kind == SegmentKind.PROSE)
            if not info.spoken and not any(decisions[s.id].type == BlockType.ACTION for s in info.segs):
                if words > _LONG_NARRATION_WORDS:
                    scene.convo = []  # a long stretch of narration ends the exchange
                scene.open_speech = False
                scene.last_actor = self.canon(info.actors[-1]) if info.actors else scene.last_actor
                continue

            evidence: dict[str, tuple[float, str]] = {}

            def add(name: str | None, score: float, why: str, evidence: dict = evidence) -> None:
                name = self.canon(name)
                if name and score > evidence.get(name, (0.0, ""))[0]:
                    evidence[name] = (score, why)

            pool = [n for n in reversed(scene.convo) if n != "?"] + scene.recent()
            add(info.tag_name, 0.97, "speech tag")
            pron = self._by_pronoun(info.tag_pronoun, pool)
            add(pron, 0.86 if info.tag_pronoun != "i" else 0.93, f"'{info.tag_pronoun}' + gender/POV")
            add(info.subject, 0.86, "action beat before the line")
            for a in info.actors:
                add(a, 0.8, "acts in the same paragraph")
            add(self._by_pronoun(info.subject_pronoun, pool), 0.72, f"'{info.subject_pronoun}' beat + gender")
            starts_with_quote = bool(info.segs) and info.segs[0].kind == SegmentKind.QUOTE
            if scene.open_speech and starts_with_quote and scene.last_speaker:
                add(scene.last_speaker, 0.9, "speech continues from the previous paragraph")
            for n in info.names:
                add(n, 0.55, "named in this paragraph")

            addressee = None
            for q in info.quotes:
                addressee = addressee or self._addressee(q.text, scene)
            if addressee and addressee in evidence and evidence[addressee][1] not in ("speech tag",):
                del evidence[addressee]  # you don't call your own name

            two = [n for n in dict.fromkeys(reversed(scene.convo)) if n != "?"][:2]
            if self.first_person and self.pov and len(two) == 1 and two[0] != self.pov:
                two.append(self.pov)  # the narrator is always part of the conversation
            if not evidence or max(v[0] for v in evidence.values()) < 0.7:
                bare = info.quotes and not info.tag_name and not info.actors
                if scene.pending_addressee and bare and scene.pending_addressee != addressee:
                    add(scene.pending_addressee, 0.76, "was just asked a question by name")
                if addressee and len(two) == 2 and addressee in two:
                    add(next(n for n in two if n != addressee), 0.76, f"addresses {addressee} in a two-way exchange")
                elif (bare and scene.last_actor and scene.last_actor not in two[:1]
                      and scene.last_actor != addressee):
                    add(scene.last_actor, 0.66, "just acted in the previous paragraph")
                elif len(two) == 2 and info.quotes and not info.tag_name:
                    add(two[1], 0.68, "turn-taking")
            if not evidence:
                for n in pool:
                    if n not in (addressee,) and n != scene.last_speaker:
                        add(n, 0.35, "present in the scene")
                        break

            ranked = sorted(evidence.items(), key=lambda kv: -kv[1][0])
            cands = list(dict.fromkeys([n for n, _ in ranked] + [n for n in pool if n != addressee] +
                                       ([self.pov] if self.pov else [])))
            cands = [c for c in cands if c and c != "?"][:5]

            for s in info.segs:
                d = decisions[s.id]
                if d.type == BlockType.DIALOGUE:
                    self._assign(d, ranked, cands, addressee)
                elif d.type == BlockType.THOUGHT:
                    self._assign_thought(d, info, ranked, cands)
                elif d.type == BlockType.ACTION:
                    actor = self.canon(info.subject) or self._by_pronoun(info.subject_pronoun, pool)
                    if actor:
                        d.speaker, d.candidates = actor, cands
                    else:
                        d.type, d.conf, d.why = BlockType.NARRATION, 0.85, "beat without a clear actor"

            spoken = [decisions[s.id] for s in info.spoken if decisions[s.id].type == BlockType.DIALOGUE]
            if spoken:
                who = spoken[-1].speaker if spoken[-1].conf >= 0.5 else None
                scene.spoke(who)
                scene.see(who, info.idx)
                asks = any(q.text.rstrip(" \"”」』»").endswith("?") for q in info.quotes)
                scene.pending_addressee = addressee if (addressee and addressee != who and
                                                        (asks or "tell" in " ".join(q.text.lower() for q in info.quotes))) else None
            scene.open_speech = info.unclosed
            scene.last_actor = None

    def _new_scene(self) -> Scene:
        sc = Scene()
        if self.first_person and self.pov:
            sc.see(self.pov, -1)
        return sc

    def _assign(self, d: Decision, ranked, cands, addressee) -> None:
        if ranked:
            name, (score, why) = ranked[0]
            # two strong but different explanations → less sure
            if len(ranked) > 1 and ranked[1][1][0] >= score - 0.05 and why != "speech tag":
                score -= 0.15
            d.speaker, d.why = name, why
            d.conf = min(d.conf, score)
            d.tier = Tier.RULE if why in ("speech tag", "action beat before the line") else Tier.MEMORY
        else:
            d.speaker, d.conf, d.why, d.tier = None, 0.2, "no evidence", Tier.MEMORY
        d.candidates = cands
        d.addressee = addressee

    def _assign_thought(self, d: Decision, info: ParaInfo, ranked, cands) -> None:
        if info.tag_name or info.thought_tag and ranked and ranked[0][1][1] == "speech tag":
            self._assign(d, ranked, cands, None)
            return
        if ranked and ranked[0][1][1] == "action beat before the line":
            self._assign(d, ranked, cands, None)
            d.conf = min(d.conf, 0.78)
            return
        if self.pov:
            d.speaker, d.conf, d.why, d.tier = self.pov, min(d.conf, 0.7), "point-of-view inner voice", Tier.MEMORY
        elif ranked:
            self._assign(d, ranked, cands, None)
            d.conf = min(d.conf, 0.5)
        else:
            d.speaker, d.conf, d.why = None, min(d.conf, 0.3), "unattributed thought"
        d.candidates = cands


_MALE_TITLES = {"mr", "mr.", "sir", "lord", "king", "prince", "duke", "brother", "father", "uncle", "master",
                "count", "baron", "emperor", "grandpa", "grandfather", "monsieur", "señor", "herr"}
_FEMALE_TITLES = {"mrs", "mrs.", "ms", "ms.", "miss", "lady", "queen", "princess", "duchess", "sister", "mother",
                  "aunt", "madam", "madame", "mistress", "countess", "baroness", "empress", "grandma",
                  "grandmother", "señora", "frau"}


def title_gender(name: str) -> str | None:
    first = name.split()[0].lower() if name.split() else ""
    return "m" if first in _MALE_TITLES else "f" if first in _FEMALE_TITLES else None


def is_first_person(segments: list[Segment]) -> bool:
    prose = " ".join(s.text for s in segments if s.kind == SegmentKind.PROSE)
    words = max(1, len(prose.split()))
    return len(re.findall(r"\bI\b", prose)) / words > 0.012
