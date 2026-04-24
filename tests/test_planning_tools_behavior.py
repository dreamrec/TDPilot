"""Behavioral tests for planning tools: td_validate_recipe, td_audit_project.

These tests exercise actual logic paths, not just registration.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import td_mcp.tool_registry as registry
from td_mcp.memory import TechniqueStore
from td_mcp.models import AuditProjectInput, ValidateRecipeInput
from td_mcp.services import ServiceContainer

# ── Helpers ──────────────────────────────────────────────────


class _FakeCardIndex:
    """Minimal card index that knows about a fixed set of operators."""

    def __init__(self, known_ops: dict[str, dict] | None = None):
        self._ops = known_ops or {}

    def get_operator(self, op_type: str):
        return self._ops.get(op_type)

    def get_palette(self, op_type: str):
        return None

    def check_compatibility(self, op_type: str, build: str):
        card = self._ops.get(op_type, {})
        if card.get("incompatible"):
            return {"status": "incompatible", "reason": "test: incompatible build"}
        return {"status": "compatible", "reason": "ok"}


class _AuditClient:
    """Client that returns canned node lists per container path."""

    def __init__(self, tree: dict[str, list[dict[str, Any]]]):
        self._tree = tree

    async def request(self, endpoint: str, body: dict | None = None):
        body = body or {}
        if endpoint == "nodes":
            path = body.get("path", "/")
            return self._tree.get(path, [])
        if endpoint == "node/errors":
            return {"issues": []}
        return {}


def _make_ctx(
    *,
    client=None,
    store: TechniqueStore | None = None,
    card_index=None,
    td_build: str | None = None,
):
    services = ServiceContainer(
        td_client=client or object(),
        technique_store=store,
        preference_store=None,
    )
    if card_index is not None:
        services.card_index = card_index
    if td_build is not None:
        services.td_build = td_build
    lifespan_state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


# ── td_validate_recipe tests ────────────────────────────────


@pytest.mark.asyncio
async def test_validate_recipe_inline_dict_nodes():
    """Validate inline recipe with dict-shaped nodes."""
    idx = _FakeCardIndex({"noiseTOP": {}, "nullTOP": {}})
    ctx = _make_ctx(card_index=idx)

    result = await registry.td_validate_recipe(
        ValidateRecipeInput(
            recipe={
                "name": "test-recipe",
                "nodes": {
                    "/noise1": {"name": "noise1", "type": "noiseTOP"},
                    "/out1": {"name": "out1", "type": "nullTOP"},
                },
            }
        ),
        ctx,
    )
    assert result["success"] is True
    assert result["valid"] is True
    assert result["node_count"] == 2
    assert result["unknown_op_types"] == []


@pytest.mark.asyncio
async def test_validate_recipe_inline_list_nodes():
    """Validate inline recipe with list-shaped nodes."""
    idx = _FakeCardIndex({"noiseTOP": {}})
    ctx = _make_ctx(card_index=idx)

    result = await registry.td_validate_recipe(
        ValidateRecipeInput(
            recipe={
                "name": "list-recipe",
                "nodes": [
                    {"name": "noise1", "type": "noiseTOP"},
                ],
            }
        ),
        ctx,
    )
    assert result["success"] is True
    assert result["valid"] is True
    assert result["node_count"] == 1


@pytest.mark.asyncio
async def test_validate_recipe_unknown_op_types():
    """Unknown op types appear in warnings, not errors (recipe is still valid)."""
    idx = _FakeCardIndex({"noiseTOP": {}})
    ctx = _make_ctx(card_index=idx)

    result = await registry.td_validate_recipe(
        ValidateRecipeInput(
            recipe={
                "name": "unknown-ops",
                "nodes": {
                    "/n1": {"name": "n1", "type": "noiseTOP"},
                    "/n2": {"name": "n2", "type": "magicSuperTOP"},
                },
            }
        ),
        ctx,
    )
    assert result["success"] is True
    assert result["valid"] is True  # unknown ops are warnings, not errors
    assert "magicSuperTOP" in result["unknown_op_types"]
    assert "noiseTOP" not in result["unknown_op_types"]


@pytest.mark.asyncio
async def test_validate_recipe_compat_issues():
    """Incompatible build versions are reported."""
    idx = _FakeCardIndex({"noiseTOP": {"incompatible": True}})
    ctx = _make_ctx(card_index=idx, td_build="2025.32460")

    result = await registry.td_validate_recipe(
        ValidateRecipeInput(
            recipe={
                "name": "compat-test",
                "nodes": {"/n1": {"name": "n1", "type": "noiseTOP"}},
            }
        ),
        ctx,
    )
    assert result["success"] is True
    assert len(result["compat_issues"]) == 1
    assert result["compat_issues"][0]["op_type"] == "noiseTOP"


@pytest.mark.asyncio
async def test_validate_recipe_stored_entry_unwrap(tmp_path):
    """Recipe loaded from store must unwrap the entry envelope correctly."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add(
        {
            "complexity": "small",
            "recipe": {
                "name": "stored-recipe",
                "nodes": {"/n1": {"name": "n1", "type": "noiseTOP"}},
            },
        },
        scope="project",
        name="stored-recipe",
    )
    ctx = _make_ctx(store=store)

    result = await registry.td_validate_recipe(
        ValidateRecipeInput(recipe_id=tid, scope="project"),
        ctx,
    )
    assert result["success"] is True
    assert result["recipe_name"] == "stored-recipe"
    assert result["node_count"] == 1


@pytest.mark.asyncio
async def test_validate_recipe_no_input():
    """Missing both recipe and recipe_id returns error."""
    ctx = _make_ctx()
    result = await registry.td_validate_recipe(
        ValidateRecipeInput(),
        ctx,
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_validate_recipe_missing_fields():
    """Recipe missing 'name' or 'nodes' gets warnings."""
    ctx = _make_ctx()
    result = await registry.td_validate_recipe(
        ValidateRecipeInput(recipe={"description": "no name or nodes"}),
        ctx,
    )
    assert result["success"] is True
    warning_text = " ".join(result["warnings"])
    assert "name" in warning_text
    assert "nodes" in warning_text


# ── td_audit_project tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_audit_project_shallow_tree(monkeypatch):
    """Audit correctly counts immediate children."""
    client = _AuditClient(
        {
            "/project1": [
                {"name": "noise1", "type": "noiseTOP", "family": "TOP", "path": "/project1/noise1"},
                {"name": "null1", "type": "nullTOP", "family": "TOP", "path": "/project1/null1"},
                {"name": "wave1", "type": "waveCHOP", "family": "CHOP", "path": "/project1/wave1"},
            ],
        }
    )
    ctx = _make_ctx(client=client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_audit_project(
        AuditProjectInput(root_path="/project1"),
        ctx,
    )
    assert result["success"] is True
    assert result["total_nodes"] == 3
    assert result["by_family"]["TOP"] == 2
    assert result["by_family"]["CHOP"] == 1
    assert result["by_op_type"]["noiseTOP"] == 1


@pytest.mark.asyncio
async def test_audit_project_recursive_into_comps(monkeypatch):
    """Audit recurses into child COMPs to count the full subtree."""
    client = _AuditClient(
        {
            "/project1": [
                {
                    "name": "comp1",
                    "type": "baseCOMP",
                    "family": "COMP",
                    "path": "/project1/comp1",
                    "isCOMP": True,
                },
                {"name": "noise1", "type": "noiseTOP", "family": "TOP", "path": "/project1/noise1"},
            ],
            "/project1/comp1": [
                {"name": "inner1", "type": "noiseTOP", "family": "TOP", "path": "/project1/comp1/inner1"},
                {"name": "inner2", "type": "levelTOP", "family": "TOP", "path": "/project1/comp1/inner2"},
            ],
        }
    )
    ctx = _make_ctx(client=client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_audit_project(
        AuditProjectInput(root_path="/project1"),
        ctx,
    )
    assert result["success"] is True
    assert result["total_nodes"] == 4  # comp1 + noise1 + inner1 + inner2
    assert result["by_family"]["TOP"] == 3
    assert result["by_family"]["COMP"] == 1


@pytest.mark.asyncio
async def test_audit_project_deep_nesting(monkeypatch):
    """Audit recurses through multiple levels of nesting."""
    client = _AuditClient(
        {
            "/root": [
                {
                    "name": "level1",
                    "type": "baseCOMP",
                    "family": "COMP",
                    "path": "/root/level1",
                    "isCOMP": True,
                },
            ],
            "/root/level1": [
                {
                    "name": "level2",
                    "type": "baseCOMP",
                    "family": "COMP",
                    "path": "/root/level1/level2",
                    "isCOMP": True,
                },
            ],
            "/root/level1/level2": [
                {"name": "leaf", "type": "noiseTOP", "family": "TOP", "path": "/root/level1/level2/leaf"},
            ],
        }
    )
    ctx = _make_ctx(client=client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_audit_project(
        AuditProjectInput(root_path="/root"),
        ctx,
    )
    assert result["success"] is True
    assert result["total_nodes"] == 3  # level1 + level2 + leaf


@pytest.mark.asyncio
async def test_audit_project_unknown_ops_detected(monkeypatch):
    """Audit reports unknown op types when card_index is available."""
    idx = _FakeCardIndex({"noiseTOP": {}})  # only knows noiseTOP
    client = _AuditClient(
        {
            "/project1": [
                {"name": "n1", "type": "noiseTOP", "family": "TOP", "path": "/project1/n1"},
                {"name": "n2", "type": "magicSuperTOP", "family": "TOP", "path": "/project1/n2"},
            ],
        }
    )
    ctx = _make_ctx(client=client, card_index=idx)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_audit_project(
        AuditProjectInput(root_path="/project1"),
        ctx,
    )
    assert result["success"] is True
    assert "magicSuperTOP" in result["unknown_op_types"]
    assert "noiseTOP" not in result["unknown_op_types"]
