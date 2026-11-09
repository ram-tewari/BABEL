"""The shared library: faces for minor characters and backgrounds for places, reused across novels.

Minor and unnamed characters ("the bartender", "a guard", Wendy the baker) don't
get a design of their own. Each is matched to an *archetype* (guard, constable, maid,
shopkeeper…) by the words the book uses for them, their gender and age, and given
one of a few faces of that archetype — always the same one for the same character.
Generic places (street, pub, church…) get one background per clothing era. Both are
drawn on demand, checked by the quality checker and picked automatically by score.

The library is stored as a hidden novel so it reuses the design queue, the art
scheduler and the checker unchanged. Its items are keyed by era, so two novels
set in the same period share them.
"""

from __future__ import annotations

import hashlib
import json
import re

from babel.art import designs
from babel.art.profile import FIELDS
from babel.memory.akashic import Akashic
from babel.store.db import Store, now
from babel.vn.scenes import GENERIC

LIBRARY_SOURCE = "__library__"
VARIANTS = 3
DEFAULT_SETS = ("street", "room", "tavern", "office", "church", "parlor", "forest", "mystic")
EXTRA_EMOTIONS = ("neutral", "happy", "angry", "sad", "surprised")
# the nearest expression an extra has, for the ones it doesn't
EXTRA_FALLBACK = {"laugh": "happy", "afraid": "surprised", "serious": "neutral"}

# key → (label, gender, age, outfit, keywords that point to it)
ARCHETYPES: dict[str, tuple[str, str, str, str, str]] = {
    "guard": ("guard", "m", "about 30", "a guard's or soldier's uniform", r"guard|soldier|sentry|knight|warrior|captain"),
    "police": ("police officer", "m", "about 35", "a police constable's uniform with a peaked cap removed",
               r"police|policeman|constable|inspector|officer|detective|sergeant"),
    "maid": ("maid", "f", "about 22", "a housemaid's dress with a white apron", r"maid|servant girl|housekeeper"),
    "butler": ("butler", "m", "about 50", "a butler's black tailcoat", r"butler|servant|footman|valet|steward"),
    "shopkeeper": ("shopkeeper", "m", "about 40", "a shopkeeper's waistcoat and apron",
                   r"shopkeeper|merchant|vendor|peddler|seller|owner|clerk at the|salesman|baker|grocer|tailor"),
    "shopkeeper_f": ("shopkeeper", "f", "about 40", "a plain dress with an apron",
                     r"shopkeeper|merchant|vendor|peddler|seller|owner|saleswoman|baker|landlady"),
    "barkeep": ("bartender", "m", "about 40", "a bartender's rolled-up shirt and apron",
                r"bartender|barkeep|innkeeper|waiter|landlord|tavern keeper|publican"),
    "barmaid": ("barmaid", "f", "about 28", "a barmaid's blouse and apron",
                r"barmaid|waitress|tavern girl|innkeeper|bartender|barkeep"),
    "driver": ("coachman", "m", "about 45", "a coachman's heavy coat", r"driver|coachman|cabbie|carter|conductor"),
    "worker": ("worker", "m", "about 30", "a laborer's rough shirt and braces",
               r"worker|laborer|labourer|porter|sailor|fisherman|farmer|dockworker|miner|hawker|smith|carpenter"),
    "noble": ("nobleman", "m", "about 45", "a rich nobleman's fine suit", r"noble|lord|duke|count|baron|prince|viscount|aristocrat|gentleman"),
    "noble_f": ("noblewoman", "f", "about 35", "a rich noblewoman's elegant gown",
                r"lady|duchess|countess|baroness|princess|madam|noblewoman|aristocrat"),
    "priest": ("priest", "m", "about 50", "a clergyman's black robes", r"priest|bishop|deacon|monk|clergy|archbishop|pastor|father"),
    "nun": ("nun", "f", "about 35", "a nun's habit", r"nun|priestess|sister|abbess"),
    "scholar": ("scholar", "m", "about 40", "a scholar's tweed jacket and spectacles",
                r"scholar|professor|teacher|student|librarian|secretary|clerk|accountant|lawyer|tutor|doctor|physician"),
    "scholar_f": ("scholar", "f", "about 30", "a modest high-collared dress and spectacles",
                  r"teacher|student|librarian|secretary|receptionist|accountant|governess|nurse|doctor"),
    "thug": ("thug", "m", "about 30", "shabby clothes and a scarred face",
             r"thug|bandit|thief|criminal|hooligan|gangster|robber|cultist|assassin|ruffian"),
    "elder": ("old man", "m", "about 70", "plain old-fashioned clothes", r"old man|elder|grandfather|grandpa|old-timer|old gentleman"),
    "elder_f": ("old woman", "f", "about 70", "a plain shawl and dress", r"old woman|granny|grandmother|grandma|old lady|crone"),
    "boy": ("boy", "m", "about 12", "plain children's clothes", r"boy|lad|kid|child|youngster|urchin|newsboy"),
    "girl": ("girl", "f", "about 12", "a plain children's dress", r"girl|lass|kid|child|youngster"),
    "man": ("man", "m", "about 35", "everyday clothes", r"man|guy|stranger|figure|person|customer|passenger"),
    "woman": ("woman", "f", "about 30", "everyday clothes", r"woman|lady|stranger|figure|person|customer|passenger"),
}
_GENERIC_ARCH = {"m": "man", "f": "woman"}
# a few different faces per archetype
_LOOKS = {
    "m": [("short dark brown hair", "brown eyes", "average build", "a plain face with a short beard"),
          ("short black hair", "gray eyes", "stocky build", "a broad clean-shaven face"),
          ("light brown hair", "blue eyes", "lean build", "a narrow face with a mustache")],
    "f": [("dark brown hair in a bun", "brown eyes", "slender", "a soft round face"),
          ("black hair tied back", "gray eyes", "average build", "a sharp oval face"),
          ("auburn hair", "green eyes", "slender", "a freckled face")],
}
_OLD_HAIR = ["thinning gray hair", "white hair", "silver hair"]


def library_novel_id(store: Store) -> int:
    with store.tx() as c:
        row = c.execute("SELECT id FROM novels WHERE source_name=?", (LIBRARY_SOURCE,)).fetchone()
        if row:
            return row["id"]
        ts = now()
        return c.execute("INSERT INTO novels (title, source_name, created_at, updated_at) VALUES (?,?,?,?)",
                         ("Shared art library", LIBRARY_SOURCE, ts, ts)).lastrowid


def era_key(era: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (era or "timeless").lower()).strip("-") or "timeless"


_AGE_FIRST = ("elder", "elder_f", "boy", "girl")  # clear age words outrank occupation ("an old baker" → old woman)
_OLD_WORDS = re.compile(r"\b(old (?:man|woman|lady|gentleman)|granny|grandma|grandpa|grandmother|grandfather|elderly|"
                        r"aged|(?:sixty|seventy|eighty|ninety)[\w-]*(?: years?)?(?:-| )old|white-haired|gray-haired|"
                        r"grey-haired|wrinkled)\b", re.I)
_CHILD_WORDS = re.compile(r"\b(little (?:boy|girl)|child|kid|(?:six|seven|eight|nine|ten|eleven|twelve)[- ]years?[- ]old)\b",
                          re.I)


def classify(name: str, note: str | None, gender: str | None, description: str = "") -> str:
    """Which archetype a minor character is, from the words the book uses for them (name, note, description)."""
    text = f"{name} {note or ''} {description}".lower()
    g = gender if gender in ("m", "f") else None
    if _OLD_WORDS.search(text):
        return "elder_f" if g == "f" else "elder"
    if _CHILD_WORDS.search(text):
        return "girl" if g == "f" else "boy"
    best = None
    for key, (_, ag, _, _, kw) in ARCHETYPES.items():
        if key in _AGE_FIRST:
            continue
        if key in ("man", "woman"):
            continue
        if re.search(rf"\b({kw})(?:e?s)?\b", text) and (g is None or ag == g):
            best = key
            break
    if best is None:
        best = _GENERIC_ARCH.get(g or "", "man")
    return best


_F = re.compile(r"\b(she|her|hers|woman|women|lady|girl|madam|mrs|miss|mother|sister|grandmother|granny)\b", re.I)
_M = re.compile(r"\b(he|him|his|man|men|gentleman|boy|sir|mr|father|brother|grandfather)\b", re.I)


def infer_gender(text: str) -> str | None:
    """From the book's words around an unnamed character ("the woman whose face was painted…")."""
    f, m = len(_F.findall(text)), len(_M.findall(text))
    if f >= 2 * max(1, m) or (f and not m):
        return "f"
    if m >= 2 * max(1, f) or (m and not f):
        return "m"
    return None


def _stable(*parts) -> int:
    return int(hashlib.sha1(":".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def extra_profile(archetype: str, variant: int) -> dict:
    label, gender, age, outfit, _ = ARCHETYPES[archetype]
    hair, eyes, build, face = _LOOKS[gender][variant % len(_LOOKS[gender])]
    if archetype in ("elder", "elder_f"):
        hair = _OLD_HAIR[variant % len(_OLD_HAIR)]
    if archetype in ("boy", "girl"):
        build = "small child's build"
    f = lambda v: {"value": v, "guessed": False, "chapter": None, "quote": ""}  # noqa: E731
    p = {k: f("") for k in FIELDS}
    p.update(age=f(age), hair=f(hair), eyes=f(eyes), build=f(build), face=f(face), skin=f("fair"), outfit=f(outfit))
    p["tags"] = [hair, eyes, label]
    return p


def _library_entity(store: Store, lib: int, name: str, kind: str, gender: str | None = None) -> int:
    with store.tx() as c:  # one transaction: concurrent requests never create the same item twice
        row = c.execute("SELECT id FROM entities WHERE novel_id=? AND name=?", (lib, name)).fetchone()
        if row:
            return row["id"]
        return c.execute("INSERT INTO entities (novel_id, kind, name, gender, created_at) VALUES (?,?,?,?,?)",
                         (lib, kind, name, gender, now())).lastrowid


def _ensure_library_design(store: Store, eid: int, kind: str, spec: dict, profile: dict | None) -> dict:
    d = designs.ensure_design(store, eid)
    if d.get("kind") != kind or not d.get("spec"):
        store.x("UPDATE designs SET kind=?, auto_pick=1, spec=? WHERE id=?", (kind, json.dumps(spec), d["id"]))
        if profile is not None:
            designs.save_profile(store, eid, profile, user=False, status="profiled")
        else:
            store.x("UPDATE designs SET status='profiled' WHERE id=?", (d["id"],))
        d = designs.get_design(store, eid)
    return d


def assign_extra(store: Store, ak: Akashic, eid: int, era: str) -> int:
    """The library face this minor character uses (stable: stored on the character)."""
    e = ak.ents[eid]
    lib = library_novel_id(store)
    if e.get("extra_id") and store.one("SELECT 1 FROM entities WHERE id=? AND novel_id=?", (e["extra_id"], lib)):
        return e["extra_id"]
    from babel.art.profile import gather_evidence

    description = " ".join(x["text"] for x in gather_evidence(store, ak, eid, max_snippets=3, max_chars=1500))
    gender = e.get("gender") if e.get("gender") in ("m", "f") else infer_gender(f"{e['name']} {e.get('note') or ''} "
                                                                                 f"{description}")
    arch = classify(e["name"], e.get("note"), gender, description)
    variant = _stable(ak.novel_id, eid) % VARIANTS
    label, gender = ARCHETYPES[arch][0], ARCHETYPES[arch][1]
    lid = _library_entity(store, lib, f"{era_key(era)} · {arch} · {variant + 1}", "character", gender)
    _ensure_library_design(store, lid, "extra", {"era": era, "archetype": arch, "label": label, "variant": variant},
                           extra_profile(arch, variant))
    store.x("UPDATE entities SET extra_id=? WHERE id=?", (lid, eid))
    e["extra_id"] = lid
    return lid


def other_variant(store: Store, extra_id: int, taken: set[int]) -> int:
    """A different face of the same archetype (two extras in one scene shouldn't be twins)."""
    row = store.one("SELECT e.name, d.spec FROM entities e JOIN designs d ON d.entity_id=e.id WHERE e.id=?", (extra_id,))
    if not row or not row["spec"]:
        return extra_id
    spec = json.loads(row["spec"])
    lib = library_novel_id(store)
    for k in range(1, VARIANTS):
        v = (spec["variant"] + k) % VARIANTS
        lid = _library_entity(store, lib, f"{era_key(spec['era'])} · {spec['archetype']} · {v + 1}", "character",
                              ARCHETYPES[spec["archetype"]][1])
        if lid not in taken:
            _ensure_library_design(store, lid, "extra", {**spec, "variant": v}, extra_profile(spec["archetype"], v))
            return lid
    return extra_id


def ensure_generic_background(store: Store, era: str, key: str) -> int:
    lib = library_novel_id(store)
    lid = _library_entity(store, lib, f"{era_key(era)} · {key}", "location")
    _ensure_library_design(store, lid, "background", {"era": era, "category": key, "label": GENERIC[key][0]}, None)
    return lid


def ensure_named_background(store: Store, ak: Akashic, eid: int, era: str, generic: str | None) -> int:
    """A novel's own named place (e.g. a recurring pub) gets its own background."""
    e = ak.ents[eid]
    label = GENERIC.get(generic or "", GENERIC["street"])[0]
    note = (e.get("note") or "").strip()
    _ensure_library_design(store, eid, "background",
                           {"era": era, "category": generic or "street", "label": label, "name": e["name"],
                            "note": note[:200]}, None)
    return eid


def describe_place(store: Store, ak: Akashic, eid: int, llm) -> dict:
    """Draft a named place's look from the book (one visual sentence) for its background. Keeps the quote it
    relied on when that quote really is in the passages; otherwise the description stands as a guess."""
    from babel.art.profile import place_evidence, place_messages
    from babel.scenario.ask import extract_json

    d = designs.get_design(store, eid)
    spec = json.loads(d["spec"]) if d and d.get("spec") else {}
    if spec.get("description") or llm is None:
        return spec
    evidence = place_evidence(store, ak, eid)
    setting = designs.art_settings(store, ak.novel_id).get("setting", "")
    schema = {"type": "object", "properties": {"description": {"type": "string"}, "quote": {"type": "string"}},
              "required": ["description", "quote"]}
    reply = llm.chat(place_messages(ak.name(eid) or "", setting, evidence), schema=schema, max_tokens=200)
    data = extract_json(reply.content)
    desc = re.sub(r"\s+", " ", str(data.get("description", ""))).strip()[:300]
    quote = str(data.get("quote", "")).strip()
    found = next((e["chapter"] for e in evidence if quote and quote.lower()[:80] in e["text"].lower()), None)
    spec.update(description=desc, quote=quote if found else "", quote_chapter=found, guessed=found is None)
    store.x("UPDATE designs SET spec=? WHERE id=?", (json.dumps(spec), d["id"]))
    store.log_usage(ak.novel_id, None, "local" if getattr(reply, "provider", "") == "ollama" else "cloud",
                    "art-place", reply.provider, reply.model, reply.prompt_tokens, reply.completion_tokens, 0)
    return spec
