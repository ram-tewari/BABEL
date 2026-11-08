"""The quality-first, cost-last cascade for one chapter.

    segments ─▶ convert (rules) ─▶ discover names ─▶ resolve (memory)
                                      │ classify new names (local → cloud)
             ┌────────────────────────┘
             ▼
    uncertain decisions ─▶ local model (free) ─▶ still uncertain / disputed ─▶ cloud model
             ▼
    final decisions + summary + memory updates + usage

Each tier only sees what the previous one couldn't settle, phrased as
multiple-choice questions with the candidates already worked out.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass, field

from babel.llm.providers import LLMError, LocalModel, Reply, Router
from babel.memory.akashic import Akashic, valid_label
from babel.models import BlockType, Decision, EntityHint, Segment, Tier
from babel.scenario.ask import (
    Answer,
    ParseError,
    Plan,
    answer_schema,
    build_batches,
    extract_json,
    kind_ok,
    parse_answers,
    plan,
)
from babel.scenario.convert import NOT_NAMES, ParaInfo, convert, sentences
from babel.scenario.resolve import Resolver, is_first_person
from babel.scenario.segment import segment_text
from babel.store.db import Store

log = logging.getLogger(__name__)


@dataclass
class Policy:
    accept: float = 0.9  # decisions at/above this are final without asking anyone
    escalate: float = 0.75  # after the local pass, anything below goes to the cloud
    review: float = 0.6  # below this a human should look (review queue)
    weak: float = 0.78  # resolver guesses below this are heuristics a local model may overrule
    summaries: str = "local"  # local | cloud | off — "story so far" memory
    entities: bool = True  # classify newly seen names with a model
    max_entity_questions: int = 12


@dataclass
class Outcome:
    decisions: dict[int, list]  # seg -> compact Decision
    summary: str | None
    review_count: int
    tiers: dict[str, int]
    stats: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class TransformFailed(Exception):
    pass


ENTITY_SCHEMA = {
    "type": "object",
    "properties": {"entities": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"},
        "kind": {"type": "string", "enum": ["person", "place", "group", "term", "not_a_name"]},
        "gender": {"type": "string", "enum": ["m", "f", "u"]},
        "same_as": {"type": "string"},
        "note": {"type": "string"},
    }, "required": ["name", "kind"]}}},
    "required": ["entities"],
}
_KIND = {"person": "character", "place": "location", "group": "faction", "term": "term"}

ENTITY_PROMPT = """You maintain the character list for a novel. For each NEW NAME, decide:
- kind: person | place | group (faction, organization, family) | term (a named skill, item, title, language,
  deity or concept specific to this story) | not_a_name
  Use not_a_name for ordinary words that are only capitalized because they start a sentence or for
  emphasis ("Between", "Using", "Western", "Immediately"), and for generic nouns.
- gender (persons only): m | f | u (unknown)
- same_as: if it is just another name for someone in KNOWN, that exact KNOWN name; otherwise ""
- note: at most 8 words on who/what it is, from the text only
Reply JSON: {"entities":[{"name":"...","kind":"person","gender":"f","same_as":"","note":"..."}]}"""

SUMMARY_PROMPT = """Summarize this chapter of a novel in at most two sentences for a reader's
"previously on" notes: who did what, and any new fact that matters later. Use names.
Reply JSON: {"summary":"..."}"""
SUMMARY_SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}


class Cascade:
    def __init__(self, local: LocalModel | None = None, cloud: Router | None = None,
                 policy: Policy | None = None, summary_window: int = 3):
        self.local = local
        self.cloud = cloud if cloud and cloud.providers else None
        self.policy = policy or Policy()
        self.summary_window = summary_window
        self.memory_lock = threading.RLock()

    @property
    def label(self) -> str:
        parts = ["rules", "memory"]
        if self.local:
            parts.append(self.local.label)
        if self.cloud:
            parts.append(self.cloud.label)
        return " → ".join(parts)

    # ── model calls ───────────────────────────────────────────────────────
    def _call(self, tier: str, messages: list[dict], schema: dict, store: Store, ch: dict, purpose: str,
              questions: int, max_tokens: int = 1024) -> Reply:
        model = self.local if tier == "local" else self.cloud
        assert model is not None
        reply = model.chat(messages, schema=schema, max_tokens=max_tokens)
        store.log_usage(ch["novel_id"], ch["id"], tier, purpose, reply.provider, reply.model,
                        reply.prompt_tokens, reply.completion_tokens, questions)
        return reply

    def _ask(self, tier: str, batches, store, ch, warnings, *, rebuild=None) -> list[Answer]:
        answers: list[Answer] = []
        for b in batches:
            for attempt in range(2):
                try:
                    reply = self._call(tier, b.messages, answer_schema(b), store, ch, "decide", len(b.questions),
                                       max_tokens=40 + 12 * len(b.questions))
                    answers += parse_answers(reply.content, b)
                    break
                except ParseError as e:
                    if attempt == 0:
                        continue
                    if rebuild and len(b.questions) > 3:
                        # a long batch confused the model: ask again in two smaller halves
                        half = len(b.questions) // 2
                        parts = [rebuild(b.questions[:half]), rebuild(b.questions[half:])]
                        answers += self._ask(tier, [x for p in parts for x in p], store, ch, warnings)
                    else:
                        warnings.append(f"{tier}: unusable answer ({e})")
                except LLMError as e:
                    warnings.append(f"{tier}: {e}")
                    break
        return answers

    # ── stages ────────────────────────────────────────────────────────────
    def _discover(self, ak: Akashic, paras: list[ParaInfo], segments: list[Segment]) -> tuple[list[str], dict[str, str]]:
        """Capitalized names this chapter uses that memory doesn't know yet."""
        counts: Counter[str] = Counter()
        for info in paras:
            for n in info.names + ([info.tag_name] if info.tag_name else []):
                if n and n.split()[0] not in NOT_NAMES and ak.lookup(n, kind=None) is None:
                    counts[n] += 3 if n in (info.tag_name, info.subject) else 1
        text = " ".join(s.text for s in segments)
        for n in list(counts):
            counts[n] += len(re.findall(rf"\b{re.escape(n)}\b", text)) - 1
        # "Mira" and "Mira Vell" are one person: credit the full name, keep the short one as an alias
        short_forms: dict[str, str] = {}
        for short in sorted(counts, key=len):
            longer = [m for m in counts if m != short and set(short.split()) < set(m.split())]
            if len(longer) == 1:
                counts[longer[0]] += counts.pop(short)
                short_forms[short] = longer[0]
        return [n for n, c in counts.most_common(self.policy.max_entity_questions) if c >= 2], short_forms

    def _classify(self, names: list[str], short_forms: dict[str, str], ak: Akashic, segments: list[Segment],
                  store, ch, warnings) -> None:
        tier = "local" if self.local else "cloud" if self.cloud else None
        if not names:
            return
        if tier is None or not self.policy.entities:
            return  # without a model, speakers become characters when they first speak
        text = " ".join(s.text for s in segments)
        sents = sentences(text)
        lines = []
        for n in names:
            ex = [s for s in sents if re.search(rf"\b{re.escape(n)}\b", s)][:2]
            lines.append(f"- {n}: " + " / ".join(e[:160] for e in ex))
        known = [ak.brief(c["id"]) for c in sorted(ak.characters, key=lambda c: -(c.get("lines") or 0))[:20]]
        user = ("KNOWN\n" + ("\n".join(f"- {k}" for k in known) or "(none yet)") +
                "\n\nNEW NAMES (with example sentences)\n" + "\n".join(lines))
        msgs = [{"role": "system", "content": ENTITY_PROMPT}, {"role": "user", "content": user}]
        try:
            reply = self._call(tier, msgs, ENTITY_SCHEMA, store, ch, "entities", len(names), max_tokens=80 + 40 * len(names))
            data = extract_json(reply.content).get("entities") or []
        except (LLMError, ParseError) as e:
            warnings.append(f"entity pass: {e}")
            return
        allowed = {n.lower() for n in names}
        for e in data:
            if not isinstance(e, dict) or str(e.get("name", "")).lower() not in allowed:
                continue
            kind = _KIND.get(e.get("kind"))
            if kind is None:
                continue
            same = (e.get("same_as") or "").strip()
            with self.memory_lock:
                target = ak.lookup(same) if same else None
                if target is not None and kind == "character":
                    ak.set_alias(target, e["name"])
                else:
                    g = e.get("gender") if e.get("gender") in ("m", "f") else None
                    note = (e.get("note") or "").strip()[:120] or None
                    aliases = [k for k, v in short_forms.items() if v == e["name"]]
                    ak.learn(EntityHint(name=e["name"], kind=kind, gender=g, note=note, aliases=aliases), ch["idx"])

    def _summarize(self, text: str, store, ch, warnings) -> str | None:
        mode = self.policy.summaries
        tier = "local" if mode == "local" and self.local else "cloud" if mode == "cloud" and self.cloud else None
        if tier is None:
            return None
        words = text.split()
        if len(words) > 4500:
            text = " ".join(words[:3000]) + " … " + " ".join(words[-1500:])
        msgs = [{"role": "system", "content": SUMMARY_PROMPT}, {"role": "user", "content": text}]
        try:
            reply = self._call(tier, msgs, SUMMARY_SCHEMA, store, ch, "summary", 0, max_tokens=160)
            s = extract_json(reply.content).get("summary")
            return s.strip()[:500] if isinstance(s, str) and s.strip() else None
        except (LLMError, ParseError) as e:
            warnings.append(f"summary: {e}")
            return None

    def _apply(self, answers: list[Answer], decisions: dict[int, Decision], segs: dict[int, Segment],
               tier: Tier, resolver: Resolver) -> set[int]:
        """Merge a tier's answers. Returns segments where it disagreed with the current guess."""
        disputed: set[int] = set()
        trust = 0.93 if tier == Tier.CLOUD else 0.9
        for a in answers:
            d = decisions[a.seg]
            if a.kind == "type":
                bt = BlockType.parse(a.value)
                if bt is None or not kind_ok(segs[a.seg], bt):
                    continue
                if bt == d.type:
                    d.conf = max(d.conf, trust) if d.speaker or bt not in (BlockType.DIALOGUE, BlockType.THOUGHT) else d.conf
                else:
                    d.type, d.tier = bt, tier
                    if bt not in (BlockType.DIALOGUE, BlockType.THOUGHT, BlockType.ACTION):
                        d.speaker, d.conf = None, 0.8 if tier == Tier.LOCAL else trust
                    else:
                        disputed.add(a.seg)
                continue
            if a.other and valid_label(a.value):
                with self.memory_lock:  # a fuller name for someone known upgrades memory ("Mira" → "Mira Vell")
                    resolver.ak.resolve(a.value, create=False)
            name = resolver.canon(a.value) if a.value else None
            if not valid_label(name):
                continue
            if d.speaker and name == d.speaker:
                d.conf, d.why, d.tier = max(d.conf, trust), f"{d.why or 'guess'}; confirmed by {tier.value} model", tier
            elif tier == Tier.CLOUD or d.conf < self.policy.weak:
                # The cloud has the final word. The local model overrides only weak heuristic
                # guesses (turn-taking, scene presence) — measured on the gold set, it is right
                # far more often than they are, but strong textual evidence (tags, beats) wins.
                prev = d.speaker
                d.speaker, d.tier = name, tier
                d.conf = trust if tier == Tier.CLOUD else 0.72
                d.why = f"{tier.value} model chose {name}" + (f" over {prev} ({d.why})" if prev else "")
                if prev and prev not in d.candidates:
                    d.candidates.insert(1, prev)
                if tier == Tier.LOCAL and prev:
                    disputed.add(a.seg)
            else:
                disputed.add(a.seg)
                d.why = f"{d.why}; local model said {name}"
                if name not in d.candidates:
                    d.candidates.insert(1, name)
                d.conf = min(d.conf, 0.7)
        return disputed

    # ── main ──────────────────────────────────────────────────────────────
    def transform(self, store: Store, ak: Akashic, ch: dict, mode: str = "auto") -> Outcome:
        """mode: auto (all available tiers) | rules (no models) | local | cloud (skip local)."""
        if mode == "cloud" and not self.cloud:
            raise TransformFailed("no cloud provider configured")
        if mode == "local" and not self.local:
            raise TransformFailed("no local model available (install Ollama and `ollama pull qwen3:8b`)")
        use_local = self.local is not None and mode in ("auto", "local")
        use_cloud = self.cloud is not None and mode in ("auto", "cloud")
        warnings: list[str] = []
        segments = segment_text(ch["source_text"])
        segs = {s.id: s for s in segments}
        with self.memory_lock:
            known = set(ak.character_names())
        decisions, paras = convert(segments, known)
        text = ch["source_text"]

        saved_local, saved_cloud = self.local, self.cloud
        try:
            if not use_local:
                self.local = None
            if not use_cloud:
                self.cloud = None
            with self.memory_lock:
                ak.observe_gender(text)
                new_names, short_forms = self._discover(ak, paras, segments)
            self._classify(new_names, short_forms, ak, segments, store, ch, warnings)
            with self.memory_lock:
                ak.observe_gender(text)
                resolver = Resolver(ak, first_person=is_first_person(segments))
                resolver.run(segments, decisions, paras)
                cast = self._cast_lines(ak, decisions, text)
                story = store.recent_summaries(ch["novel_id"], ch["idx"], self.summary_window)

            pol = self.policy
            asked = {"local": 0, "cloud": 0}
            if self.local:
                p = plan(decisions, pol.accept)
                batches = build_batches(segments, decisions, p, cast_lines=cast, story=story, title=ch["title"])
                asked["local"] = sum(len(b.questions) for b in batches)
                disputed = self._apply(self._ask("local", batches, store, ch, warnings,
                                                 rebuild=self._rebuilder(segments, decisions, cast, story, ch)),
                                       decisions, segs, Tier.LOCAL, resolver)
            else:
                disputed = set()
            if self.cloud:
                threshold = pol.escalate if self.local else pol.accept
                p = plan(decisions, threshold)
                p.speaker = sorted(set(p.speaker) | {s for s in disputed if decisions[s].type in
                                                       (BlockType.DIALOGUE, BlockType.THOUGHT, BlockType.ACTION)})
                batches = build_batches(segments, decisions, p, cast_lines=cast, story=story, title=ch["title"])
                asked["cloud"] = sum(len(b.questions) for b in batches)
                self._apply(self._ask("cloud", batches, store, ch, warnings,
                                      rebuild=self._rebuilder(segments, decisions, cast, story, ch)),
                            decisions, segs, Tier.CLOUD, resolver)

            summary = self._summarize(text, store, ch, warnings)
        finally:
            self.local, self.cloud = saved_local, saved_cloud

        with self.memory_lock:
            for d in decisions.values():
                if d.speaker and d.type in (BlockType.DIALOGUE, BlockType.THOUGHT, BlockType.ACTION):
                    other = ak.lookup(d.speaker, kind=None)
                    if other is not None and ak.ents[other]["kind"] != "character":
                        # places and terms don't talk: send it to review instead of inventing a character
                        d.why = f"{d.speaker} is a {ak.ents[other]['kind']}, not a character"
                        d.speaker, d.conf = None, min(d.conf, 0.4)
                        continue
                    if d.type == BlockType.ACTION:
                        continue
                    eid = ak.resolve(d.speaker, ch["idx"])
                    if eid is not None:
                        d.speaker = ak.name(eid)

        relevant = [d for d in decisions.values() if d.type in (BlockType.DIALOGUE, BlockType.THOUGHT)]
        tiers = Counter(d.tier.value for d in relevant)
        review = sum(1 for d in decisions.values() if d.conf < pol.review)
        return Outcome(
            decisions={i: d.compact() for i, d in decisions.items()},
            summary=summary,
            review_count=review,
            tiers=dict(tiers),
            stats={"segments": len(segments), "lines": len(relevant), "asked": asked, "new_names": new_names,
                   "warnings": warnings[:10]},
            warnings=warnings,
        )

    @staticmethod
    def _rebuilder(segments, decisions, cast, story, ch):
        def rebuild(questions):
            p = Plan(speaker=[q.seg for q in questions if q.kind == "speaker"],
                     type=[q.seg for q in questions if q.kind == "type"])
            return build_batches(segments, decisions, p, cast_lines=cast, story=story, title=ch["title"])
        return rebuild

    @staticmethod
    def _cast_lines(ak: Akashic, decisions: dict[int, Decision], text: str) -> list[str]:
        names = {c for d in decisions.values() for c in [d.speaker, *d.candidates] if c}
        ids = [ak.lookup(n) for n in names]
        ids += [eid for eid, _ in ak.mentioned_in(text).most_common(12)]
        seen, lines = set(), []
        for eid in ids:
            if eid is not None and eid not in seen and eid in ak.ents:
                seen.add(eid)
                lines.append(ak.brief(eid))
        return lines[:20]
