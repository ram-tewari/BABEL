"""Appearance profiles — what a character looks like, drafted from the book with citations.

The text model never invents a look from nothing: it gets the passages where the
book describes the character (found by alias + appearance words) and fills a fixed
set of fields, citing the chapter and quote for each one and flagging guesses.
The reader can edit and lock any field. Prompts for the image models are then
built *deterministically* from the profile, so the same profile always asks for
the same character.
"""

from __future__ import annotations

import json
import re

from babel.memory.akashic import Akashic
from babel.store.db import Store

FIELDS = ("age", "hair", "eyes", "build", "face", "skin", "outfit", "accessories", "marks")
FIELD_LABELS = {
    "age": "Age", "hair": "Hair", "eyes": "Eyes", "build": "Build / height", "face": "Face",
    "skin": "Skin", "outfit": "Usual outfit", "accessories": "Props / accessories", "marks": "Distinguishing marks",
}

# One sheet per character. "neutral" is the approved base portrait itself; the rest are edits of it.
EMOTIONS: dict[str, str] = {
    "neutral": "a calm, neutral expression",
    "happy": "a warm, genuine smile with slightly narrowed eyes",
    "laugh": "laughing openly: eyes squeezed, mouth open in a laugh",
    "angry": "an angry expression: furrowed brows, glaring eyes, clenched jaw",
    "sad": "a sad expression: downcast eyes, eyebrows raised in the middle, a slight frown",
    "surprised": "a surprised expression: wide eyes, raised eyebrows, mouth slightly open",
    "afraid": "a frightened expression: wide trembling eyes, eyebrows drawn up, lips pressed tight",
    "serious": "a serious, cold expression: level gaze, firm mouth, no smile",
}

STYLES = {
    "manhwa": ("Korean manhwa webtoon illustration, full color digital art, clean crisp lineart, cel shading with "
               "soft gradients, expressive detailed eyes, semi-realistic proportions"),
}
STYLE_TAGS = {"manhwa": "manhwa, webtoon, korean comic style"}
FRAMING = ("one person shown from the head to the waist, facing the viewer, bareheaded, mouth clearly visible, nothing in front "
           "of the face, plain light gray background, no scenery")
NEGATIVE = ("worst quality, low quality, score_1, score_2, score_3, artist name, signature, watermark, text, "
            "speech bubble, blurry, jpeg artifacts, chromatic aberration, extra fingers, deformed hands, "
            "multiple people, cropped head, hat, headwear, object in mouth, pipe in mouth, cigarette, lantern, lamp, "
            "building, city, scenery, landscape, background objects")
NEGATIVE_KEEP_HAT = NEGATIVE.replace("hat, headwear, ", "")

# tags/words about the world rather than the person never go into a portrait prompt
_OFF_CHARACTER = re.compile(
    r"\b(city|town|street|lamp|lamps|lantern|building|architecture|background|scenery|landscape|setting|"
    r"steampunk|atmosphere|mood|symbolism|occult|aesthetic|vibe|theme|world)\b", re.I)
_ERA_ONLY = re.compile(r"\b(era|century|fashion|\d{3,4}s)\b", re.I)  # fine in clothing text, not as a tag
_HAT = re.compile(r"\b(hat|top hat|bowler|cap|bonnet|hood|helmet|headwear)\b", re.I)

_APPEARANCE = re.compile(
    r"\b(hair|hairline|eyes?|face|faced|features|tall|short|slender|thin|plump|stout|build|muscular|complexion|"
    r"skin|beard|mustache|moustache|freckles|scar|wrinkles|glasses|monocle|wore|wearing|dressed|attire|clothes|"
    r"coat|dress|robe|uniform|hat|cap|gloves|cane|years? old|young (?:man|woman|girl|lady)|old (?:man|woman)|"
    r"handsome|pretty|beautiful|figure|appearance|looked like)\b", re.I)

PROFILE_PROMPT = """You describe how a novel's character looks, for an illustrator.
You get the character's name, aliases, the story's setting, and passages from the book.
Fill every field with a short visual description (a few words). For each field give the chapter
number and a short exact quote from the passages that supports it. If the book doesn't say, make
a sensible guess that fits the character and setting, set "guessed": true, and leave chapter/quote empty.
Describe the character's usual, default look — not a one-off disguise. Also give 6–12 lowercase
illustration tags (danbooru style: "black hair", "brown eyes", "trench coat", …) that describe only the
character's own body, face, clothes and props — never the setting, era, mood or background.
Reply with JSON only."""


def profile_schema() -> dict:
    field = {"type": "object", "properties": {
        "value": {"type": "string"}, "chapter": {"type": ["integer", "null"]},
        "quote": {"type": "string"}, "guessed": {"type": "boolean"}},
        "required": ["value", "guessed"]}
    return {"type": "object",
            "properties": {**{f: field for f in FIELDS},
                           "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 20}},
            "required": [*FIELDS, "tags"]}


def gather_evidence(store: Store, ak: Akashic, eid: int, *, max_snippets: int = 24, max_chars: int = 7000) -> list[dict]:
    """Passages that mention the character (any alias) together with appearance words, in book order."""
    names = [ak.name(eid) or ""] + list(ak.alias_text.get(eid, []))
    names = [n for n in dict.fromkeys(names) if n and n.lower() not in ("i", "me")]
    if not names:
        return []
    rx = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b")
    out: list[dict] = []
    total = 0
    rows = store.q("SELECT c.idx, c.source_text FROM chapters c WHERE c.novel_id=? AND c.id IN"
                   " (SELECT chapter_id FROM chapter_cast WHERE entity_id=?) ORDER BY c.idx", (ak.novel_id, eid))
    if not rows:  # not counted yet: scan the start of the book
        rows = store.q("SELECT idx, source_text FROM chapters WHERE novel_id=? ORDER BY idx LIMIT 80", (ak.novel_id,))
    for r in rows:
        paras = [p.strip() for p in r["source_text"].split("\n") if p.strip()]
        for i, p in enumerate(paras):
            if not rx.search(p):
                continue
            # the description often follows in the next paragraph ("…Melissa. / She had reddish-black hair…")
            window = p if _APPEARANCE.search(p) else (paras[i + 1] if i + 1 < len(paras) else "")
            if not window or not _APPEARANCE.search(window) or len(_APPEARANCE.findall(window)) < 2:
                continue
            text = (p if window is p else f"{p} {window}")[:600]
            out.append({"chapter": r["idx"] + 1, "text": text})
            total += len(text)
            if len(out) >= max_snippets or total >= max_chars:
                return out
    return out


def draft_messages(name: str, aliases: list[str], gender: str | None, note: str | None, setting: str,
                   evidence: list[dict]) -> list[dict]:
    lines = [f"CHARACTER: {name}" + (f" (also called: {', '.join(aliases[:8])})" if aliases else "")]
    if gender:
        lines.append(f"GENDER: {dict(m='male', f='female').get(gender, gender)}")
    if note:
        lines.append(f"NOTE: {note}")
    lines.append(f"SETTING: {setting or 'unknown — infer from the passages'}")
    lines.append("PASSAGES:")
    lines += [f"[chapter {e['chapter']}] {e['text']}" for e in evidence] or ["(the book gives no description)"]
    return [{"role": "system", "content": PROFILE_PROMPT}, {"role": "user", "content": "\n".join(lines)}]


def parse_profile(text: str) -> dict:
    from babel.scenario.ask import extract_json

    data = extract_json(text)
    out: dict = {}
    for f in FIELDS:
        v = data.get(f)
        if isinstance(v, str):
            v = {"value": v, "guessed": True}
        if not isinstance(v, dict) or not str(v.get("value", "")).strip():
            out[f] = {"value": "", "guessed": True, "chapter": None, "quote": ""}
            continue
        ch = v.get("chapter")
        out[f] = {"value": str(v["value"]).strip()[:160], "guessed": bool(v.get("guessed", not v.get("quote"))),
                  "chapter": ch if isinstance(ch, int) else None, "quote": str(v.get("quote") or "")[:240]}
    tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    out["tags"] = [t.strip().lower() for t in tags if isinstance(t, str) and 0 < len(t.strip()) <= 40][:20]
    return out


SETTING_PROMPT = """From these opening passages of a novel, describe its visual setting for an illustrator.
"setting": one sentence on era, place and technology level, and typical clothing (e.g. "Victorian-era
steampunk city, 1850s European fashion: frock coats, top hats, long dresses").
"era": 2-5 words naming the clothing period/culture only (e.g. "1880s Victorian", "ancient Chinese
wuxia", "modern-day Korean", "medieval European fantasy").
Reply with JSON only: {"setting": "...", "era": "..."}"""


def setting_messages(sample: str) -> list[dict]:
    return [{"role": "system", "content": SETTING_PROMPT}, {"role": "user", "content": sample[:6000]}]


def gender_tag(gender: str | None) -> str:
    return {"m": "1boy", "f": "1girl"}.get(gender or "", "1other")


def wears_hat(profile: dict) -> bool:
    """A hat stays only when it's part of who they are (listed as a distinguishing mark)."""
    return bool(_HAT.search(profile.get("marks", {}).get("value", "")))


def portrait_tags(profile: dict) -> list[str]:
    keep_hat = wears_hat(profile)
    return [t for t in profile.get("tags") or []
            if not _OFF_CHARACTER.search(t) and not _ERA_ONLY.search(t) and (keep_hat or not _HAT.search(t))]


def describe(profile: dict) -> str:
    keep_hat = wears_hat(profile)
    parts = []
    for f in FIELDS:
        v = profile.get(f, {}).get("value", "")
        if f in ("outfit", "accessories") and not keep_hat:
            v = ", ".join(x.strip() for x in re.split(r",|\band\b|\bwith\b", v) if x.strip() and not _HAT.search(x))
        v = _OFF_CHARACTER.sub("", v).strip(" ,") if f != "age" else v
        if v:
            parts.append(f"{FIELD_LABELS[f].split(' /')[0].lower()}: {v}")
    return "; ".join(parts)


def base_prompt(profile: dict, gender: str | None, art: dict) -> tuple[str, str]:
    """Prompt for a base portrait (Anima: tags + natural language).

    Anima Turbo samples without guidance, so the negative prompt has no effect there:
    anything unwanted (hats, scenery) must be kept out of the positive prompt itself.

    Only the character goes in — the novel's setting shaped the profile (era-appropriate clothes)
    but is never drawn, so no gas lamps on coats or lanterns in mouths.
    """
    style = art.get("style") or "manhwa"
    tags = ", ".join(portrait_tags(profile))
    who = {"m": "a man", "f": "a woman"}.get(gender or "", "a person")
    era = (art.get("era") or "").strip()
    clothes = f" Clothing in {era} style." if era else ""
    prompt = (f"masterpiece, best quality, score_7, safe, {gender_tag(gender)}, solo, upper body, looking at viewer, "
              f"{tags}, {STYLE_TAGS.get(style, '')}, simple background, grey background. "
              f"Half-body illustration of {who}, from the head down to the waist — {describe(profile)}.{clothes} "
              f"{STYLES.get(style, style)}. {FRAMING}.")
    return re.sub(r"(,\s*)+", ", ", prompt), NEGATIVE_KEEP_HAT if wears_hat(profile) else NEGATIVE


def expression_prompt(emotion: str) -> str:
    return ("Keep the exact same character, face, hairstyle, outfit, pose, framing, art style and plain background. "
            f"Change only the facial expression to {EMOTIONS[emotion]}.")


def load(design: dict | None) -> dict | None:
    if not design or not design.get("profile"):
        return None
    return json.loads(design["profile"])
