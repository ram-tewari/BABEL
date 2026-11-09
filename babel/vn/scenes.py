"""Scenes and where they happen.

A chapter is split into scenes at scene breaks and where the narration clearly
moves somewhere new ("He walked into the pub…"). Each scene gets a place: a
named location from the Akashic Record when the narration mentions one, otherwise
a generic category (street, room, pub, church…) from the words used, and a time of
day (night is drawn as a lighting overlay, not a separate background). The text
model can refine uncertain scenes with one schema-enforced call per chapter.
"""

from __future__ import annotations

import re

from babel.memory.akashic import Akashic
from babel.scenario.ask import extract_json

# generic places: key → (label for prompts, keywords in the narration)
GENERIC: dict[str, tuple[str, str]] = {
    "street": ("a city street", r"street|road|avenue|alley|lane|town square|city square|market square|crossroads|sidewalk|pavement|"
                         r"boulevard"),  # not a bare "square" (a shape)
    "room": ("a modest rented room", r"room|apartment|bedroom|flat|attic|lodging|bed\b|desk"),
    "parlor": ("an elegant drawing room in a wealthy house", r"parlou?r|drawing room|mansion|manor|villa|salon|estate"),
    "office": ("a wood-panelled office with a desk and bookshelves", r"office|company|bureau|reception|headquarters|study"),
    "tavern": ("a crowded pub", r"pub|tavern|bar\b|inn\b|bartender|saloon"),
    "shop": ("a shop interior", r"shop|store|bakery|market|stall|boutique|pharmacy|herb"),
    "church": ("a church interior", r"church|cathedral|chapel|temple|shrine|altar|nave"),
    "carriage": ("the inside of a horse-drawn carriage", r"carriage|coach|cab\b|wagon"),
    "train": ("a train compartment", r"train|railway|compartment|steam locomotive|platform"),
    "library": ("a library with tall bookshelves", r"library|bookshelves|archive|reading room"),
    "classroom": ("an old lecture hall with wooden benches and a chalkboard", r"classroom|lecture|university|school|academy|campus"),
    "hospital": ("a hospital ward", r"hospital|clinic|infirmary|ward\b"),
    "underground": ("an underground stone corridor", r"underground|basement|cellar|sewer|tunnel|vault|crypt"),
    "harbor": ("a harbor with ships at the dock", r"harbou?r|dock|pier|port\b|wharf|quay"),
    "ship": ("the wooden deck of a sailing ship at sea, masts and rigging", r"ship|aboard|on deck|ship's deck|sailors?|sails|mast|ocean|voyage|at sea"),  # not "deck" (of cards)
    "forest": ("a forest", r"forest|woods|trees|grove|jungle"),
    "countryside": ("open countryside", r"field|countryside|village|farm|meadow|hill|plain"),
    "palace": ("a grand palace hall", r"palace|castle|throne|court\b|great hall"),
    "mystic": ("an otherworldly misty void", r"fog|mist|gray fog|dream|void|spirit world|illusion|vision|astral"),
    "tent": ("the dim inside of a fortune-teller's tent at a travelling circus, draped fabric and a small table",
             r"tent|circus|carnival|fair\b|fairground|booth|troupe"),
}
GENERIC_DEFAULT = "room"
# what the place plaque says (the long GENERIC labels are for the painter)
SHORT = {"street": "A street", "room": "A rented room", "parlor": "A drawing room", "office": "An office",
         "tavern": "A pub", "shop": "A shop", "church": "A church", "carriage": "A carriage", "train": "A train",
         "library": "A library", "classroom": "A lecture hall", "hospital": "A hospital ward",
         "underground": "Underground", "harbor": "The harbour", "ship": "Aboard ship", "forest": "A forest",
         "countryside": "The countryside", "palace": "A palace hall", "mystic": "Beyond the veil",
         "tent": "The fortune-teller's tent"}
INDOOR = {"room", "parlor", "office", "tavern", "shop", "church", "carriage", "train", "library", "classroom",
          "hospital", "underground", "palace", "tent"}
_WEATHER = [("rain", re.compile(r"\b(rain\w*|drizzl\w*|downpour|storm\w*|thunder\w*|wet streets?)\b", re.I)),
            ("snow", re.compile(r"\b(snow\w*|blizzard|sleet|frost\w*)\b", re.I)),
            ("fog", re.compile(r"\b(fog\w*|mist\w*|haze|hazy|smog)\b", re.I))]


def weather_of(text: str) -> str | None:
    """The scene's weather from its narration (drawn as particles over the background)."""
    best, n = None, 0
    for kind, rx in _WEATHER:
        c = len(rx.findall(text))
        if c > n:
            best, n = kind, c
    return best
_NIGHT = re.compile(r"\b(night|midnight|moonlight|moonlit|crimson moon|the moon|darkness|dark sky|nighttime|"
                    r"late at night|stars|starlight|gas lamps? (?:were )?lit)\b", re.I)
_DAY = re.compile(r"\b(morning|noon|afternoon|sunlight|sunshine|daylight|dawn|sunrise|the sun)\b", re.I)
_MOVE = re.compile(r"\b(entered|walked into|stepped into|arrived at|reached|went into|came to|returned to|"
                   r"headed to|made (?:his|her|their) way to|pushed open the door|walked out|stepped out|went out|"
                   r"left the|went downstairs|went upstairs|came out of|exited|set off|walked down|"
                   r"strolled|wandered into|got off|alighted)\b", re.I)
_GENERIC_RX = {k: re.compile(rf"\b({kw})\b", re.I) for k, (_, kw) in GENERIC.items()}


def generic_place(text: str) -> tuple[str | None, int]:
    """The generic category whose words appear most in ``text`` (and how often)."""
    best, n = None, 0
    for key, rx in _GENERIC_RX.items():
        c = len(rx.findall(text))
        if c > n:
            best, n = key, c
    return best, n


def venue_kind(name: str) -> str | None:
    """'Ironcross Street' → street, 'Old Will's Restaurant' → tavern; a bare city/country name → None."""
    extra = {"restaurant": "tavern", "cafe": "tavern", "café": "tavern", "company": "office", "station": "street",
             "university": "classroom", "college": "classroom", "museum": "library", "prison": "underground",
             "cemetery": "countryside", "park": "countryside", "hotel": "room", "apartment": "room", "house": "room"}
    low = name.lower()
    for word, kind in extra.items():
        if re.search(rf"\b{word}\b", low):
            return kind
    kind, _ = generic_place(name)
    return kind


def split_scenes(blocks: list[dict]) -> list[int]:
    """Start indices of scenes: chapter start, after each scene break, and at clear moves to a new place."""
    starts = [0]
    for i, b in enumerate(blocks):
        if i == 0:
            continue
        if b["type"] == "break":
            starts.append(i + 1 if i + 1 < len(blocks) else i)
        elif b["type"] == "narration" and _MOVE.search(b["text"]) and i - starts[-1] >= 8:
            place, n = generic_place(b["text"])
            if place:
                starts.append(i)
    return sorted(set(s for s in starts if s < len(blocks)))


def scene_text(blocks: list[dict], start: int, end: int, limit: int = 12) -> str:
    prose = [b["text"] for b in blocks[start:end] if b["type"] in ("narration", "action", "tag")]
    return " ".join(prose[:limit])


def locate(blocks: list[dict], ak: Akashic) -> list[dict]:
    """Scenes with a place and time of day, from rules."""
    starts = split_scenes(blocks)
    places = {e["id"]: e for e in ak.ents.values() if e["kind"] == "location"}
    scenes = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(blocks)
        text = scene_text(blocks, start, end)
        # a named place is only drawn when its name says what kind of place it is ("Ironcross Street",
        # "Evernight Cathedral") — a city or a country ("Tingen", "Loen Kingdom") isn't a backdrop
        named = ([(eid, kind) for eid, _ in ak.mentioned_in(text, kind="location").most_common()
                  if eid in places and (kind := venue_kind(places[eid]["name"]))] if places else [])
        generic, hits = generic_place(text)
        if named:
            eid, kind = named[0]
            place = {"kind": "named", "id": eid, "name": places[eid]["name"], "generic": kind}
            conf = 0.75
        else:
            place = {"kind": "generic", "key": generic or GENERIC_DEFAULT, "name": SHORT[generic or GENERIC_DEFAULT]}
            conf = 0.7 if hits >= 2 else 0.45
        night = len(_NIGHT.findall(text)) > len(_DAY.findall(text))
        kind = place.get("key") if place["kind"] == "generic" else place.get("generic")
        scenes.append({"start": start, "end": end, "place": place, "night": night, "conf": conf, "tier": "rule",
                       "weather": weather_of(text), "indoor": (kind or GENERIC_DEFAULT) in INDOOR,
                       "category": kind or GENERIC_DEFAULT})
    return scenes


PLACE_PROMPT = """You help stage a novel as a visual novel. For each scene, choose where it takes place from the
allowed options (a named place if the scene is clearly there, otherwise the closest generic kind of place),
and whether it is day or night. Reply with JSON only."""


def refine_messages(blocks: list[dict], scenes: list[dict], ak: Akashic) -> tuple[list[dict], dict]:
    named = sorted({s["place"]["name"] for s in scenes if s["place"]["kind"] == "named"} |
                   {e["name"] for e in ak.ents.values() if e["kind"] == "location" and (e.get("mentions") or 0) >= 3})
    options = [f"place:{n}" for n in named[:12]] + [f"generic:{k}" for k in GENERIC]
    parts = []
    for i, s in enumerate(scenes, 1):
        parts.append(f"SCENE {i}: {scene_text(blocks, s['start'], s['end'], limit=8)[:1200]}")
    item = {"type": "object", "properties": {"place": {"type": "string", "enum": options},
                                             "time": {"type": "string", "enum": ["day", "night"]}},
            "required": ["place", "time"]}
    schema = {"type": "object", "properties": {"scenes": {"type": "array", "items": item, "minItems": len(scenes),
                                                          "maxItems": len(scenes)}}, "required": ["scenes"]}
    legend = "GENERIC PLACES: " + "; ".join(f"generic:{k} = {v[0]}" for k, v in GENERIC.items())
    user = legend + "\n\n" + "\n\n".join(parts) + '\n\nReply as {"scenes": [{"place": "...", "time": "day"}, ...]}'
    return [{"role": "system", "content": PLACE_PROMPT}, {"role": "user", "content": user}], schema


def apply_refine(text: str, scenes: list[dict], ak: Akashic) -> list[dict]:
    data = extract_json(text)
    got = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(got, list) or len(got) != len(scenes):
        return scenes
    for s, g in zip(scenes, got, strict=True):
        if not isinstance(g, dict) or s.get("conf", 0) >= 0.7:
            continue  # the model only decides the places the rules weren't sure about
        p = str(g.get("place", ""))
        if p.startswith("place:"):
            eid = ak.lookup(p[6:], kind="location")
            kind = venue_kind(p[6:]) if eid is not None else None
            if eid is not None and kind:
                s["place"] = {"kind": "named", "id": eid, "name": ak.name(eid), "generic": kind}
                s["category"], s["indoor"] = kind, kind in INDOOR
        elif p.startswith("generic:") and p[8:] in GENERIC:
            s["place"] = {"kind": "generic", "key": p[8:], "name": SHORT[p[8:]]}
            s["category"], s["indoor"] = p[8:], p[8:] in INDOOR
        if g.get("time") in ("day", "night"):
            s["night"] = g["time"] == "night"
        s["tier"], s["conf"] = "local", 0.85
    return scenes
