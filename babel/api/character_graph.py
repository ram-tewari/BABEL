"""Character relationship graph + glossary API.

Builds an interactive character network straight from the transformed Visual
Scenario JSON: nodes are speakers (sized by how much they speak, coloured by
faction) and edges are co-appearances within the same chapter. Optional
``up_to_chapter`` keeps everything spoiler-safe by only scanning chapters the
reader has already reached. Glossary metadata (faction, aliases, description)
from ``config/glossary.yaml`` is merged in to power hover tooltips.
"""

import re
import logging
from pathlib import Path
from itertools import combinations
from typing import Any, Dict, List, Optional

import json
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["characters"])

# Block types that count as a character "speaking" / being on-stage.
_SPEAKING_TYPES = {"dialogue", "thought", "monologue"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    id: str
    name: str
    line_count: int
    first_chapter: int
    faction: Optional[str] = None
    description: Optional[str] = None
    aliases: List[str] = []
    color: Optional[str] = None  # explicit glossary colour (else frontend derives)


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: int  # number of chapters the pair co-appears in


class CharacterGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    chapters_scanned: int


class GlossaryEntry(BaseModel):
    name: str
    aliases: List[str] = []
    faction: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class GlossaryResponse(BaseModel):
    characters: List[GlossaryEntry]
    factions: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_dir(novel_id: Optional[int]) -> Path:
    """Resolve the directory of transformed JSON for a novel (or legacy)."""
    if novel_id is not None:
        return Path(f"data/json/novel_{novel_id}")
    return Path("data/json")


def _chapter_sort_key(path: Path):
    """Order chapter files by their leading/volume + chapter numbers."""
    matches = re.findall(r"\d+", path.name)
    if not matches:
        return (0, 0)
    if len(matches) == 1:
        return (0, int(matches[0]))
    return (int(matches[0]), int(matches[-1]))


def _glossary_path(novel_id: Optional[int]) -> Path:
    """Prefer a novel-specific glossary, fall back to the shared one."""
    if novel_id is not None:
        novel_specific = Path(f"config/glossary.novel_{novel_id}.yaml")
        if novel_specific.exists():
            return novel_specific
    return Path("config/glossary.yaml")


def load_glossary(novel_id: Optional[int] = None) -> Dict[str, Any]:
    """Load the glossary YAML, returning {} when missing/empty/malformed."""
    path = _glossary_path(novel_id)
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data or {}
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Failed to parse glossary %s: %s", path, e)
        return {}


def _glossary_lookup(glossary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build a name/alias -> entry lookup (case-insensitive)."""
    characters = glossary.get("characters", {}) or {}
    lookup: Dict[str, Dict[str, Any]] = {}
    for name, meta in characters.items():
        meta = meta or {}
        entry = {"name": name, **meta}
        lookup[name.lower()] = entry
        for alias in meta.get("aliases", []) or []:
            lookup[str(alias).lower()] = entry
    return lookup


def build_character_graph(
    novel_id: Optional[int] = None,
    up_to_chapter: Optional[int] = None,
    min_appearances: int = 2,
    max_nodes: int = 80,
) -> CharacterGraphResponse:
    """Compute the character co-appearance graph from transformed JSON."""
    json_dir = _json_dir(novel_id)
    if not json_dir.exists():
        return CharacterGraphResponse(nodes=[], edges=[], chapters_scanned=0)

    files = sorted(json_dir.glob("*.json"), key=_chapter_sort_key)

    line_counts: Dict[str, int] = {}
    first_chapter: Dict[str, int] = {}
    pair_weights: Dict[tuple, int] = {}
    chapters_scanned = 0

    for idx, path in enumerate(files):
        # Spoiler-safety: stop once we pass the reader's current chapter.
        if up_to_chapter is not None and idx >= up_to_chapter:
            break
        chapters_scanned += 1

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Skipping unreadable chapter %s: %s", path.name, e)
            continue

        speakers_here = set()
        for block in data.get("blocks", []):
            speaker = block.get("speaker")
            if not speaker:
                continue
            if block.get("type") in _SPEAKING_TYPES:
                line_counts[speaker] = line_counts.get(speaker, 0) + 1
            speakers_here.add(speaker)
            first_chapter.setdefault(speaker, idx)

        # Co-appearance edges (unordered pairs) within this chapter.
        for a, b in combinations(sorted(speakers_here), 2):
            key = (a, b)
            pair_weights[key] = pair_weights.get(key, 0) + 1

    # Keep meaningful characters: enough appearances, top-N by line count.
    eligible = {
        name: count
        for name, count in line_counts.items()
        if count >= min_appearances
    }
    kept = set(
        sorted(eligible, key=lambda n: eligible[n], reverse=True)[:max_nodes]
    )

    glossary = _glossary_lookup(load_glossary(novel_id))

    nodes: List[GraphNode] = []
    for name in kept:
        meta = glossary.get(name.lower(), {})
        nodes.append(GraphNode(
            id=name,
            name=name,
            line_count=line_counts.get(name, 0),
            first_chapter=first_chapter.get(name, 0),
            faction=meta.get("faction"),
            description=meta.get("description"),
            aliases=meta.get("aliases", []) or [],
            color=meta.get("color"),
        ))

    edges = [
        GraphEdge(source=a, target=b, weight=w)
        for (a, b), w in pair_weights.items()
        if a in kept and b in kept and w >= min_appearances
    ]
    edges.sort(key=lambda e: e.weight, reverse=True)

    return CharacterGraphResponse(
        nodes=nodes, edges=edges, chapters_scanned=chapters_scanned
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/characters/graph", response_model=CharacterGraphResponse)
async def get_character_graph(
    novel_id: Optional[int] = None,
    up_to_chapter: Optional[int] = None,
    min_appearances: int = 2,
    max_nodes: int = 80,
):
    """Character relationship graph, optionally spoiler-limited."""
    try:
        return build_character_graph(
            novel_id=novel_id,
            up_to_chapter=up_to_chapter,
            min_appearances=min_appearances,
            max_nodes=max_nodes,
        )
    except Exception as e:  # pragma: no cover - defensive
        logger.error("Error building character graph: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/glossary", response_model=GlossaryResponse)
async def get_glossary(novel_id: Optional[int] = None):
    """Return glossary characters + factions for tooltips."""
    glossary = load_glossary(novel_id)
    characters = glossary.get("characters", {}) or {}
    entries = [
        GlossaryEntry(
            name=name,
            aliases=(meta or {}).get("aliases", []) or [],
            faction=(meta or {}).get("faction"),
            description=(meta or {}).get("description"),
            color=(meta or {}).get("color"),
        )
        for name, meta in characters.items()
    ]
    return GlossaryResponse(
        characters=entries,
        factions=glossary.get("factions", {}) or {},
    )
