"""The Akashic Record, glossary YAML, metadata sources and the eval harness."""

import httpx
import pytest

from babel.evals.run import evaluate
from babel.memory.akashic import Akashic
from babel.memory.glossary import GlossaryError, export_yaml, import_yaml, parse_yaml, sync_file
from babel.meta.sources import fetch
from babel.models import EntityHint
from babel.scenario.cascade import Cascade


@pytest.fixture
def ak(store):
    return Akashic(store, store.create_novel("N", [("c", "text", "h")]))


def test_resolution_titles_partials_and_pronouns(ak):
    k = ak.resolve("Klein")
    assert ak.resolve("Klein Moretti") == k
    assert ak.lookup("Mr. Klein") == k
    assert ak.resolve("he") is None and ak.resolve("?") is None and ak.resolve("Unknown") is None
    assert ak.gender(ak.resolve("Mrs. Hall")) == "f"


def test_learn_upgrades_names_but_respects_user_edits(ak):
    k = ak.resolve("Klein")
    ak.learn(EntityHint(name="Klein Moretti", aliases=["The Fool"], note="lead", gender="m"))
    assert ak.name(k) == "Klein Moretti" and ak.lookup("the fool") == k and ak.gender(k) == "m"
    ak.edit(k, name="Klein", note="my note")
    ak.learn(EntityHint(name="Klein Moretti Jr", note="model note"))
    assert ak.name(k) == "Klein" and ak.ents[k]["note"] == "my note"


def test_merge_moves_aliases_and_pov(ak):
    a, b = ak.resolve("Zhou Mingrui"), ak.resolve("Klein")
    ak.set_pov(a)
    ak.merge(a, b)
    assert ak.lookup("Zhou Mingrui") == b and ak.pov_id == b and a not in ak.ents


def test_gender_observation(ak):
    eid = ak.resolve("Audrey")
    ak.observe_gender("Audrey smiled as she stood. Audrey lifted her cup.")
    assert ak.gender(eid) == "f"


def test_glossary_hits_for_tooltips(ak):
    city = ak.create("Tingen", "location", note="a city in Loen")
    ak.resolve("Klein")  # no note → no tooltip
    hits = ak.glossary_hits("Klein walked through Tingen at dawn.")
    assert [h["entity_id"] for h in hits] == [city] and hits[0]["terms"] == ["Tingen"]


GLOSSARY = """# my notes — keep me
characters:
  Shirone:
    aliases: [Shi]
    gender: m
    faction: Alpheas Magic School
    description: Protagonist.
    color: "#4f8cff"
    pov: true
factions:
  Alpheas Magic School: {color: "#4f8cff", description: The premier school.}
locations: {}
terms:
  Immortal Function: {description: A mind-expanding spell.}
"""


def test_glossary_roundtrip_and_locking(ak, tmp_path):
    r = import_yaml(ak, GLOSSARY)
    assert r["created"] == 3
    sh = ak.lookup("Shi")
    assert ak.name(sh) == "Shirone" and ak.pov_id == sh and ak.ents[sh]["color"] == "#4f8cff"
    assert ak.ents[ak.ents[sh]["faction_id"]]["name"] == "Alpheas Magic School"
    assert "note" in ak.ents[sh]["locked"]
    ak.learn(EntityHint(name="Shirone", note="model says otherwise"))
    assert ak.ents[sh]["note"] == "Protagonist."
    out = export_yaml(ak)
    assert "Shirone:" in out and "Immortal Function" in out and "pov: true" in out
    f = tmp_path / "g.yaml"
    f.write_text(GLOSSARY)
    ak.create("Amy")
    sync_file(ak, f)
    text = f.read_text()
    assert "# my notes — keep me" in text and "Amy" in text


def test_glossary_validation():
    with pytest.raises(GlossaryError):
        parse_yaml("characters: [a, b]")
    with pytest.raises(GlossaryError):
        parse_yaml("characters:\n  X: {gender: robot}")
    with pytest.raises(GlossaryError):
        parse_yaml("villains: {}")


def test_metadata_openlibrary_and_blocked_sites():
    def handler(req: httpx.Request) -> httpx.Response:
        if "openlibrary.org/search.json" in str(req.url):
            return httpx.Response(200, json={"docs": [{"title": "Lord of Mysteries, Vol. 1", "author_name": ["Cuttlefish"],
                                                       "cover_i": 7, "key": "/works/OL1W", "subject": ["Fantasy"]}]})
        if "openlibrary.org/works" in str(req.url):
            return httpx.Response(200, json={"description": {"value": "Steam and mysticism."}})
        if "royalroad" in str(req.url):
            return httpx.Response(403, text="<title>Just a moment...</title>")
        return httpx.Response(404)

    t = httpx.MockTransport(handler)
    meta, notes = fetch("Lord of Mysteries", ["royalroad", "openlibrary"], transport=t)
    assert "bot protection" in notes[0]
    assert meta.source == "openlibrary" and meta.author == "Cuttlefish" and meta.description == "Steam and mysticism."
    assert meta.cover_url.endswith("/7-L.jpg")


def test_rules_tier_quality_does_not_regress():
    """Guard rail on the gold set: the free, offline tiers alone must stay this good."""
    results = evaluate(Cascade(), mode="rules")
    types = sum(r.type_ok for r in results) / sum(r.total for r in results)
    speakers = sum(r.speaker_ok for r in results) / sum(r.speaker_total for r in results)
    assert types >= 0.97
    assert speakers >= 0.85
