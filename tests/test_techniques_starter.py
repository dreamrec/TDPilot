"""Starter technique seed recipes — import round-trip + param grounding.

Every file in data/techniques_starter/ must:
1. be valid td_memory_import format (round-trips through
   TechniqueStore.import_library with zero skips),
2. carry replayable full recipes (small/medium complexity, wired connections),
3. use ONLY parameter names verifiable against the operator atlas cards or the
   ParamSemantics registry (value grounding — no invented params), and
4. be honest about verification state: state=candidate, verified_on=null
   (param names are atlas-verified; the recipes have not been replayed against
   a live TD build yet).
"""

from __future__ import annotations

import json
from functools import cache, lru_cache
from pathlib import Path

import pytest

from td_mcp.memory.technique_store import TechniqueStore

ROOT = Path(__file__).resolve().parents[1]
STARTER_DIR = ROOT / "data" / "techniques_starter"
CARDS_DIR = ROOT / "src" / "td_mcp" / "knowledge" / "cards" / "operators"

STARTER_FILES = sorted(STARTER_DIR.glob("*.json"))

# Tuple params appear in atlas cards by base name ('t', 'color'); component
# writes use base+suffix ('tz', 'colorr').
_TUPLE_SUFFIXES = ("x", "y", "z", "w", "r", "g", "b", "a", "1", "2", "3", "4")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@cache
def _card_param_names(op_type: str) -> frozenset[str]:
    card_path = CARDS_DIR / f"{op_type}.json"
    if not card_path.exists():
        return frozenset()
    card = _load(card_path)
    names = {
        str(item.get("name", "")).lower() for item in (card.get("key_params") or []) if isinstance(item, dict)
    }
    return frozenset(name for name in names if name)


@lru_cache(maxsize=1)
def _semantics_params() -> dict[str, frozenset[str]]:
    from td_mcp.brain.param_semantics import semantics_by_op_and_param

    by_op: dict[str, set[str]] = {}
    for op_type, name in semantics_by_op_and_param():
        by_op.setdefault(op_type, set()).add(name.lower())
    return {op: frozenset(names) for op, names in by_op.items()}


def _param_is_verified(op_type: str, param: str) -> bool:
    param_l = param.lower()
    known = _card_param_names(op_type) | _semantics_params().get(op_type, frozenset())
    if param_l in known:
        return True
    # tuple-component expansion: 'tz' verifies against base 't'
    for suffix in _TUPLE_SUFFIXES:
        if param_l.endswith(suffix) and param_l[: -len(suffix)] in known:
            return True
    return False


def test_starter_directory_ships_expected_recipe_count():
    assert 8 <= len(STARTER_FILES) <= 12, (
        f"expected 8-12 starter recipes, found {len(STARTER_FILES)} in {STARTER_DIR}"
    )


@pytest.mark.parametrize("path", STARTER_FILES, ids=lambda p: p.stem)
def test_starter_file_is_td_memory_import_format(path: Path):
    data = _load(path)

    assert data["version"] == 1
    assert data["scope"] == "global"
    techniques = data["techniques"]
    assert isinstance(techniques, dict) and techniques
    assert data["count"] == len(techniques)
    for tid, entry in techniques.items():
        assert entry["id"] == tid
        assert entry["name"]
        assert entry["description"]
        assert entry["tags"] == sorted(set(entry["tags"]))
        assert "technique" in entry


@pytest.mark.parametrize("path", STARTER_FILES, ids=lambda p: p.stem)
def test_starter_file_round_trips_import_validation(path: Path, tmp_path: Path):
    data = _load(path)
    store = TechniqueStore(base_dir=str(tmp_path), project_name="starter_test")

    result = store.import_library(data, scope="global")

    assert result["imported"] == data["count"]
    assert result["skipped"] == 0
    for tid in data["techniques"]:
        assert store.get(tid, scope="global") is not None
    # And the imported entry is discoverable through search.
    name = next(iter(data["techniques"].values()))["name"]
    hits = store.search(query=name, scope="global")
    assert any(hit["id"] in data["techniques"] for hit in hits)


@pytest.mark.parametrize("path", STARTER_FILES, ids=lambda p: p.stem)
def test_starter_recipe_is_replayable_and_wired(path: Path):
    data = _load(path)
    for entry in data["techniques"].values():
        technique = entry["technique"]
        assert technique["complexity"] in {"small", "medium"}, "must stay replayable"
        recipe = technique["recipe"]
        assert recipe, "starter techniques must carry a full recipe"
        nodes = recipe["nodes"]
        assert nodes
        assert technique["node_count"] == len(nodes)
        assert technique["connection_count"] == len(recipe["connections"])
        node_types = sorted({info["type"] for info in nodes.values()})
        assert technique["required_op_types"] == node_types
        assert entry["compatibility"]["required_ops"] == node_types
        for conn in recipe["connections"]:
            assert conn["from"] in nodes, f"dangling connection source {conn['from']}"
            assert conn["to"] in nodes, f"dangling connection target {conn['to']}"
        # Every node must be reachable through at least one wire (no orphans).
        wired = {conn["from"] for conn in recipe["connections"]}
        wired |= {conn["to"] for conn in recipe["connections"]}
        assert set(nodes) == wired, f"orphan nodes in {path.name}: {set(nodes) - wired}"


@pytest.mark.parametrize("path", STARTER_FILES, ids=lambda p: p.stem)
def test_starter_recipe_params_are_atlas_verified(path: Path):
    data = _load(path)
    unverified: list[str] = []
    for entry in data["techniques"].values():
        for rel_path, info in entry["technique"]["recipe"]["nodes"].items():
            op_type = info["type"]
            assert _card_param_names(op_type) or _semantics_params().get(op_type), (
                f"{path.name}: no atlas card or param semantics for {op_type}"
            )
            for param in list(info.get("params", {})) + list(info.get("expressions", {})):
                if not _param_is_verified(op_type, param):
                    unverified.append(f"{path.name}:{rel_path} {op_type}.{param}")
    assert not unverified, f"unverified param names: {unverified}"


@pytest.mark.parametrize("path", STARTER_FILES, ids=lambda p: p.stem)
def test_starter_entries_are_honest_about_verification(path: Path):
    data = _load(path)
    for entry in data["techniques"].values():
        assert entry["state"] == "candidate"
        assert entry["validation_result"] is None
        assert entry["compatibility"]["verified_on"] is None
        assert entry["technique"]["verified_on"] is None
        assert entry["replay_count"] == 0
