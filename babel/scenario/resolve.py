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
# only in vocative position — "Yes, sir." / "Ma'am, I…" — not "Praise the Lady."
_VOC = r"(?:^[\"“「『«]?\s*|[,.!?…]\s+)(?:my\s+|young\s+)?({})(?=\s*[,.!?…]|\s*[\"”」』»]?\s*$)"
_MALE_ADDRESS = re.compile(_VOC.format("sir|lord|brother|master|mister"), re.I)
_FEMALE_ADDRESS = re.compile(_VOC.format("ma'?am|madam|lady|miss|sister|mistress"), re.I)


@dataclass
class Scene:
    present: dict[str, int] = field(default_factory=dict)  # name -> last paragraph seen
    convo: list[str] = field(default_factory=list)  # recent speakers in the current exchange
    last_speaker: str | None = None
    open_speech: bool = False  # previous paragraph's quote was left open
    last_actor: str | None = None  # subject of the previous narration paragraph ("Okafor stepped out.")
    pending_addressee: str | None = None  # asked a question by name; likely to answer next
    lead: tuple[str, float, str] | None = None  # the previous paragraph introduced this one's speech
    narration_words: int = 0  # narration since the last line of speech

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

    def _is_character(self, name: str) -> bool:
        eid = self.ak.lookup(name, kind=None)
        return eid is not None and self.ak.ents[eid]["kind"] == "character"

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

    def _salient(self, pronoun: str | None, actors: list[str], scene: Scene) -> tuple[str | None, float]:
        """'he'/'she' → the most salient person of that gender: whoever acts in this paragraph,
        then the previous paragraph's actor, the last speaker, the conversation, the scene.
        A unique gender match among everyone present is strong; otherwise recency decides."""
        if pronoun == "i":
            return (self.pov or "Narrator"), 0.93
        want = {"he": "m", "she": "f"}.get(pronoun or "")
        if not want:
            return None, 0.0
        order = [self.canon(a) for a in reversed(actors)] + [scene.last_actor, scene.last_speaker]
        order += [n for n in reversed(scene.convo) if n != "?"] + scene.recent()
        narrator = self.pov if self.first_person else None  # "I" is never "he"/"she"
        order = [n for n in dict.fromkeys(order) if n and n != "?" and n != narrator and self._is_person(n)]
        if not order:
            return None, 0.0
        own = [self.canon(a) for a in reversed(actors)]
        if own and own[0] in order and self.gender(own[0]) in (want, None):
            return own[0], 0.8  # "The bartender spared Klein a glance. “New here?” he asked."
        matching = [n for n in order if self.gender(n) == want]
        if len(matching) == 1:
            return matching[0], 0.86
        if matching:
            return matching[0], 0.76  # several of that gender: the most salient one
        # genders unknown yet: a weak guess from whoever just *acted* (never just the last speaker —
        # "Suki said sweetly. / He didn't answer." is about the listener)
        near = [n for n in [self.canon(a) for a in reversed(actors)] + [scene.last_actor] if n in order]
        if near and self.gender(near[0]) is None:
            return near[0], 0.6
        return None, 0.0

    def _is_person(self, name: str) -> bool:
        eid = self.ak.lookup(name, kind=None)
        return eid is None or self.ak.ents[eid]["kind"] == "character"

    def _lead(self, info: ParaInfo, scene: Scene) -> tuple[str, float, str] | None:
        """A paragraph ending in a speech verb introduces the next paragraph's quote."""
        name, pron, strong = info.lead
        if name:
            return self.canon(name), 0.9 if strong else 0.8, "introduced by the previous paragraph"
        if pron:
            who, score = self._salient(pron, info.actors, scene)
            if who:
                return who, min(score, 0.8), f"introduced by the previous paragraph ('{pron}')"
        return None

    def _focal(self, paras: list[ParaInfo]) -> str | None:
        """The chapter's viewpoint character: the POV entity, or whoever the narration follows most."""
        if self.pov:
            return self.pov
        counts: dict[str, int] = {}
        for info in paras:
            for n in info.actors + ([info.tag_name] if info.tag_name else []):
                c = self.canon(n)
                if c and self._is_person(c):
                    counts[c] = counts.get(c, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: -kv[1])
        if ranked and ranked[0][1] >= 3 and (len(ranked) == 1 or ranked[0][1] >= 1.5 * ranked[1][1]):
            return ranked[0][0]
        return None

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
        self.focal = self._focal(paras)
        for info in paras:
            if any(s.kind == SegmentKind.BREAK for s in info.segs):
                scene = self._new_scene()
                continue
            # only people count as "present": known characters and whoever acts in a sentence
            for n in info.actors + [x for x in info.names if self._is_character(x)]:
                scene.see(self.canon(n), info.idx)

            words = sum(len(s.text.split()) for s in info.segs if s.kind == SegmentKind.PROSE)
            if not info.spoken and not any(decisions[s.id].type == BlockType.ACTION for s in info.segs):
                scene.narration_words += words
                if scene.narration_words > _LONG_NARRATION_WORDS:
                    scene.convo = []  # a long stretch of narration ends the exchange
                    # …and whoever hasn't been seen lately has probably left the scene
                    scene.present = {n: p for n, p in scene.present.items() if p >= info.idx - 3}
                scene.open_speech = False
                scene.lead = self._lead(info, scene)
                if info.actors:
                    scene.last_actor = self.canon(info.actors[-1])
                elif info.subject_pronoun:  # "Then, he lifted up his index finger."
                    who, score = self._salient(info.subject_pronoun, [], scene)
                    if who and score >= 0.76:
                        scene.last_actor = who
                continue

            evidence: dict[str, tuple[float, str]] = {}

            def add(name: str | None, score: float, why: str, evidence: dict = evidence) -> None:
                name = self.canon(name)
                if name and score > evidence.get(name, (0.0, ""))[0]:
                    evidence[name] = (score, why)

            pool = [n for n in reversed(scene.convo) if n != "?"] + scene.recent()
            add(info.tag_name, 0.97, "speech tag")
            if not info.tag_name and info.tag_desc:
                add(info.tag_desc, 0.88, "descriptive speech tag")
            if info.tag_pronoun:
                who, score = self._salient(info.tag_pronoun, list(info.intro_antecedents), scene)
                add(who, score, f"'{info.tag_pronoun}' + gender/POV")
            iname, ipron, istrong = info.intro
            if iname:
                add(iname, 0.92 if istrong else 0.85, "speech verb before the line")
            elif ipron:
                who, score = self._salient(ipron, list(info.intro_antecedents), scene)
                add(who, min(score, 0.84), f"'{ipron}' + speech verb before the line")
            starts_with_quote = bool(info.segs) and info.segs[0].kind == SegmentKind.QUOTE
            if scene.lead and starts_with_quote and not info.tag_name:
                add(*scene.lead)
            add(info.subject, 0.86, "action beat before the line")
            for a in info.actors:
                add(a, 0.8, "acts in the same paragraph")
            if info.subject_pronoun:
                who, score = self._salient(info.subject_pronoun, [], scene)
                add(who, min(score, 0.72), f"'{info.subject_pronoun}' beat + gender")
            if scene.open_speech and starts_with_quote and scene.last_speaker:
                add(scene.last_speaker, 0.9, "speech continues from the previous paragraph")
            for n in info.names:
                if self._is_character(n) or n in info.actors:
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
                elif bare and starts_with_quote and scene.last_actor and scene.last_actor != addressee:
                    # also the last speaker: "…” / Then, he lifted his index finger. / “This is Sequence 8.”
                    add(scene.last_actor, 0.7, "just acted in the previous paragraph")
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
                    actor = self.canon(info.subject) or self._salient(info.subject_pronoun, [], scene)[0]
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
            scene.lead = None
            if spoken:
                scene.narration_words = 0
            if not spoken:  # a beat-only paragraph: "Then, he lifted up his index finger."
                acts = [decisions[s.id].speaker for s in info.segs
                        if decisions[s.id].type == BlockType.ACTION and decisions[s.id].speaker]
                thinkers = [decisions[s.id].speaker for s in info.segs
                            if decisions[s.id].type == BlockType.THOUGHT and decisions[s.id].speaker]
                scene.last_actor = (acts[-1] if acts else self.canon(info.actors[-1]) if info.actors
                                    else thinkers[-1] if thinkers else None)
                scene.lead = self._lead(info, scene)

    def _new_scene(self) -> Scene:
        sc = Scene()
        if self.first_person and self.pov:
            sc.see(self.pov, -1)
        return sc

    def _assign(self, d: Decision, ranked, cands, addressee) -> None:
        if ranked:
            name, (score, why) = ranked[0]
            # two strong but different explanations → less sure
            if len(ranked) > 1 and ranked[1][1][0] >= score - 0.05 and why not in ("speech tag", "descriptive speech tag"):
                score -= 0.15
            d.speaker, d.why = name, why
            d.conf = min(d.conf, score)
            d.tier = (Tier.RULE if why in ("speech tag", "descriptive speech tag", "action beat before the line",
                                           "speech verb before the line") else Tier.MEMORY)
        else:
            d.speaker, d.conf, d.why, d.tier = None, 0.2, "no evidence", Tier.MEMORY
        d.candidates = cands
        d.addressee = addressee

    def _assign_thought(self, d: Decision, info: ParaInfo, ranked, cands) -> None:
        # A named person in the same paragraph is very likely the thinker ("“Our landlord?” the
        # perplexed Klein asked. *Does he own…*"). Score the speaker on that evidence, not on how
        # sure we are that the italics are a thought.
        if info.tag_name or info.thought_tag and ranked and ranked[0][1][1] == "speech tag":
            self._assign(d, ranked, cands, None)
            d.conf = max(d.conf, 0.88) if d.speaker else d.conf
            return
        if ranked and ranked[0][1][1] in ("action beat before the line", "speech verb before the line"):
            self._assign(d, ranked, cands, None)
            d.conf = 0.84 if d.speaker == self.focal else 0.78
            return
        if ranked and ranked[0][1][0] >= 0.7 and "'" in ranked[0][1][1]:  # "he nodded in thought"
            self._assign(d, ranked, cands, None)
            d.conf = min(d.conf, 0.72)
        elif self.focal:
            why = "point-of-view inner voice" if self.focal == self.pov else "the chapter's viewpoint character"
            d.speaker, d.conf, d.why, d.tier = self.focal, min(d.conf, 0.7), why, Tier.MEMORY
            cands = list(dict.fromkeys([self.focal] + cands))[:5]
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


_MALE_NOUNS = {"man", "boy", "guy", "gentleman", "lad", "husband", "father", "son", "brother", "uncle", "king",
               "prince", "monk", "butler", "waiter", "grandfather", "grandpa", "boyfriend", "fisherman", "swordsman"}
_FEMALE_NOUNS = {"woman", "girl", "lady", "lass", "wife", "mother", "daughter", "sister", "aunt", "queen",
                 "princess", "nun", "maid", "waitress", "grandmother", "grandma", "girlfriend", "landlady", "witch"}


def title_gender(name: str) -> str | None:
    words = name.lower().split()
    if not words:
        return None
    if words[0] in _MALE_TITLES or len(words) <= 3 and words[-1] in _MALE_NOUNS:
        return "m"
    if words[0] in _FEMALE_TITLES or len(words) <= 3 and words[-1] in _FEMALE_NOUNS:
        return "f"
    return None


def is_first_person(segments: list[Segment]) -> bool:
    prose = " ".join(s.text for s in segments if s.kind == SegmentKind.PROSE)
    words = max(1, len(prose.split()))
    return len(re.findall(r"\bI\b", prose)) / words > 0.012
