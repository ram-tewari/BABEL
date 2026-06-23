"""Tests for the character graph + glossary builder."""

import json
import os

import pytest

from babel.api import character_graph as cg


@pytest.fixture
def json_dir(tmp_path, monkeypatch):
    """Create a legacy data/json dir with a few chapters and chdir into it."""
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "data" / "json"
    d.mkdir(parents=True)

    def write(name, blocks):
        (d / name).write_text(json.dumps({"blocks": blocks}), encoding="utf-8")

    # Ch 1: Shirone + Amy speak together
    write("001_ch.json", [
        {"type": "dialogue", "speaker": "Shirone", "content": "Hi"},
        {"type": "dialogue", "speaker": "Amy", "content": "Hello"},
        {"type": "thought", "speaker": "Shirone", "content": "..."},
        {"type": "narrator", "speaker": None, "content": "The wind blew."},
    ])
    # Ch 2: Shirone + Amy again (so pair weight = 2), plus a one-off extra
    write("002_ch.json", [
        {"type": "dialogue", "speaker": "Shirone", "content": "Again"},
        {"type": "dialogue", "speaker": "Amy", "content": "Yes"},
        {"type": "dialogue", "speaker": "Extra", "content": "Once"},
    ])
    return d


def test_graph_builds_nodes_and_edges(json_dir):
    result = cg.build_character_graph(min_appearances=2)
    names = {n.name for n in result.nodes}
    # Shirone (3 lines) and Amy (2 lines) qualify; Extra (1 line) filtered out.
    assert names == {"Shirone", "Amy"}
    assert result.chapters_scanned == 2

    edge = next(e for e in result.edges if {e.source, e.target} == {"Amy", "Shirone"})
    assert edge.weight == 2


def test_first_chapter_tracking(json_dir):
    result = cg.build_character_graph(min_appearances=2)
    shirone = next(n for n in result.nodes if n.name == "Shirone")
    assert shirone.first_chapter == 0
    assert shirone.line_count == 3


def test_up_to_chapter_is_spoiler_safe(json_dir):
    # Only scan the first chapter: pair weight should drop to 1, so the
    # default min_appearances=2 edge filter removes the edge.
    result = cg.build_character_graph(up_to_chapter=1, min_appearances=1)
    assert result.chapters_scanned == 1
    edge = next(e for e in result.edges if {e.source, e.target} == {"Amy", "Shirone"})
    assert edge.weight == 1


def test_missing_dir_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = cg.build_character_graph()
    assert result.nodes == []
    assert result.edges == []


def test_glossary_enriches_nodes(json_dir, monkeypatch):
    config_dir = json_dir.parent.parent / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "glossary.yaml").write_text(
        "characters:\n"
        "  Shirone:\n"
        "    faction: Magic School\n"
        "    description: The hero.\n"
        "    aliases: [Shi]\n",
        encoding="utf-8",
    )
    result = cg.build_character_graph(min_appearances=2)
    shirone = next(n for n in result.nodes if n.name == "Shirone")
    assert shirone.faction == "Magic School"
    assert shirone.description == "The hero."
    assert "Shi" in shirone.aliases


def test_load_glossary_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cg.load_glossary() == {}
