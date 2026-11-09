"""Glossary YAML ⇄ Akashic Record.

Format (compatible with BABEL v1's glossary.yaml)::

    characters:
      Shirone:
        aliases: [Shi]
        gender: m
        faction: Alpheas Magic School
        description: Protagonist. A commoner-born genius.
        color: "#4f8cff"
        side: right
    factions:
      Alpheas Magic School: {color: "#4f8cff", description: The premier magic school.}
    locations: {}
    terms: {}

Importing treats every field as a user edit: the pipeline will never overwrite it.
Syncing into an existing file keeps the file's comments and ordering.
"""

from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from babel.memory.akashic import Akashic

SECTIONS = {"characters": "character", "factions": "faction", "locations": "location", "terms": "term"}


class GlossaryError(ValueError):
    pass


def _yaml() -> YAML:
    y = YAML()
    y.indent(mapping=2, sequence=4, offset=2)
    y.width = 100
    return y


def _entry(ak: Akashic, e: dict) -> CommentedMap:
    m = CommentedMap()
    aliases = [a for a in ak.alias_text.get(e["id"], []) if a.lower() != e["name"].lower()]
    if aliases:
        m["aliases"] = aliases
    if e["kind"] == "character":
        if e.get("gender") in ("m", "f"):
            m["gender"] = e["gender"]
        if e.get("faction_id") in ak.ents:
            m["faction"] = ak.ents[e["faction_id"]]["name"]
    if e.get("note"):
        m["description"] = e["note"]
    if e.get("color"):
        m["color"] = e["color"]
    if e["kind"] == "character" and e.get("side"):
        m["side"] = e["side"]
    if e["id"] == ak.pov_id:
        m["pov"] = True
    return m


def export_yaml(ak: Akashic, min_lines: int = 0) -> str:
    doc = CommentedMap()
    for section, kind in SECTIONS.items():
        sec = CommentedMap()
        ents = sorted((e for e in ak.ents.values() if e["kind"] == kind),
                      key=lambda e: (-(e.get("lines") or 0), e["name"].lower()))
        for e in ents:
            if kind == "character" and (e.get("lines") or 0) < min_lines and not e.get("note") and e["id"] != ak.pov_id:
                continue
            sec[e["name"]] = _entry(ak, e)
        doc[section] = sec
    doc.yaml_set_start_comment("BABEL glossary — the Akashic Record for this novel.\n"
                               "Edit freely and re-import: imported fields are never overwritten by models.")
    buf = io.StringIO()
    _yaml().dump(doc, buf)
    return buf.getvalue()


def parse_yaml(text: str) -> dict:
    try:
        data = _yaml().load(text) or {}
    except Exception as e:
        raise GlossaryError(f"invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise GlossaryError("the glossary must be a mapping with characters/factions/locations/terms")
    problems = []
    for section, body in data.items():
        if section not in SECTIONS:
            problems.append(f"unknown section {section!r}")
            continue
        if body is None:
            continue
        if not isinstance(body, dict):
            problems.append(f"{section} must be a mapping of name → details")
            continue
        for name, entry in body.items():
            if entry is not None and not isinstance(entry, dict):
                problems.append(f"{section}.{name}: details must be a mapping")
            elif entry and "aliases" in entry and not isinstance(entry["aliases"], list):
                problems.append(f"{section}.{name}: aliases must be a list")
            elif entry and entry.get("gender") not in (None, "m", "f", "n"):
                problems.append(f"{section}.{name}: gender must be m, f or n")
    if problems:
        raise GlossaryError("; ".join(problems))
    return data


def import_yaml(ak: Akashic, text: str) -> dict[str, int]:
    """Merge a glossary into memory. Returns counts of created/updated entries."""
    data = parse_yaml(text)
    created = updated = 0
    factions_pending: list[tuple[int, str]] = []
    for section in ("factions", "locations", "terms", "characters"):
        kind = SECTIONS[section]
        for name, entry in (data.get(section) or {}).items():
            entry = entry or {}
            name = str(name).strip()
            eid = ak.lookup(name, kind)
            if eid is None:
                for a in entry.get("aliases") or []:
                    eid = ak.lookup(str(a), kind)
                    if eid is not None:
                        break
            if eid is None:
                eid = ak.create(name, kind)
                created += 1
            else:
                updated += 1
            fields = {"name": name}
            if "description" in entry:
                fields["note"] = entry["description"]
            for k in ("gender", "color", "side"):
                if k in entry:
                    fields[k] = entry[k]
            ak.edit(eid, **fields)
            for a in entry.get("aliases") or []:
                ak.set_alias(eid, str(a))
            if entry.get("faction"):
                factions_pending.append((eid, str(entry["faction"])))
            if entry.get("pov"):
                ak.set_pov(eid)
    for eid, fname in factions_pending:
        fid = ak.lookup(fname, "faction") or ak.create(fname, "faction")
        ak.edit(eid, faction_id=fid)
    ak.reload()
    return {"created": created, "updated": updated}


def sync_file(ak: Akashic, path: Path) -> None:
    """Write memory into an existing YAML file, keeping its comments and order."""
    y = _yaml()
    if path.exists():
        doc = y.load(path.read_text()) or CommentedMap()
    else:
        doc = CommentedMap()
    fresh = y.load(export_yaml(ak))
    for section in SECTIONS:
        target = doc.setdefault(section, CommentedMap())
        if target is None:
            target = doc[section] = CommentedMap()
        for name, entry in (fresh.get(section) or {}).items():
            if name in target and isinstance(target[name], dict):
                for k, v in entry.items():
                    target[name].setdefault(k, v)
            else:
                target[name] = entry
    with path.open("w") as f:
        y.dump(doc, f)
