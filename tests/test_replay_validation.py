"""Behavioral tests for td_memory_replay prerequisite validation.

Tests the live TD install check (via /api/families) that replaced
the old card_index corpus check.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

import td_mcp.tool_registry as registry
from td_mcp.memory import TechniqueStore
from td_mcp.services import ServiceContainer


# ── Helpers ──────────────────────────────────────────────────


class _ReplayClient:
    """Client that returns canned families and handles replay node creation."""

    def __init__(
        self,
        families: Dict[str, List[str]] | None = None,
        families_error: bool = False,
    ):
        self._families = families or {}
        self._families_error = families_error
        self.calls: List[tuple] = []

    async def request(self, endpoint: str, body: dict | None = None):
        body = body or {}
        self.calls.append((endpoint, body))
        if endpoint == "families":
            if self._families_error:
                raise ConnectionError("TD not reachable")
            return self._families
        if endpoint == "node/create":
            name = body.get("name", "node1")
            parent = body.get("parent_path", "/")
            return {"node": {"path": f"{parent.rstrip('/')}/{name}"}}
        if endpoint in ("node/params", "set_params"):
            return {"ok": True}
        if endpoint in ("node/connect", "connect"):
            return {"ok": True}
        if endpoint == "project/lifecycle":
            return {"ok": True}
        return {}


def _make_ctx(*, client, store: TechniqueStore):
    services = ServiceContainer(
        td_client=client,
        technique_store=store,
        preference_store=None,
    )
    lifespan_state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


def _save_technique(store: TechniqueStore, *, name: str, required_ops: list, nodes: dict):
    """Save a technique with required_op_types and a recipe."""
    entry = {
        "complexity": "small",
        "required_op_types": required_ops,
        "recipe": {
            "name": name,
            "nodes": nodes,
        },
    }
    return store.add(entry, scope="project", name=name)


# ── Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_replay_blocks_when_ops_missing(tmp_path, monkeypatch):
    """Replay is blocked when required ops are not in the target TD install."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = _save_technique(
        store,
        name="needs-popx",
        required_ops=["popxInstancer", "popxFalloffShape"],
        nodes={"/inst1": {"name": "inst1", "type": "popxInstancer", "family": "COMP"}},
    )

    client = _ReplayClient(families={
        "TOP": ["noiseTOP", "nullTOP"],
        "CHOP": ["waveCHOP"],
        # No popx operators
    })
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client, store=store)

    from td_mcp.models import MemoryReplayInput

    result = await registry.td_memory_replay(
        MemoryReplayInput(
            technique_id=tid,
            parent_path="/project1",
            scope="project",
        ),
        ctx,
    )
    assert result["status"] == "blocked"
    assert "popxInstancer" in result["missing_ops"]
    assert "popxFalloffShape" in result["missing_ops"]


@pytest.mark.asyncio
async def test_replay_proceeds_when_ops_available(tmp_path, monkeypatch):
    """Replay proceeds when all required ops exist in the target TD install."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = _save_technique(
        store,
        name="basic-noise",
        required_ops=["noiseTOP", "nullTOP"],
        nodes={
            "/noise1": {"name": "noise1", "type": "noiseTOP", "family": "TOP"},
            "/null1": {"name": "null1", "type": "nullTOP", "family": "TOP"},
        },
    )

    client = _ReplayClient(families={
        "TOP": ["noiseTOP", "nullTOP", "levelTOP"],
        "CHOP": ["waveCHOP"],
    })
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client, store=store)

    from td_mcp.models import MemoryReplayInput

    result = await registry.td_memory_replay(
        MemoryReplayInput(
            technique_id=tid,
            parent_path="/project1",
            scope="project",
        ),
        ctx,
    )
    # Should NOT be blocked — should proceed to create nodes
    assert result.get("status") != "blocked"
    # Should have called node/create for the recipe nodes
    create_calls = [c for c in client.calls if c[0] == "node/create"]
    assert len(create_calls) >= 1


@pytest.mark.asyncio
async def test_replay_force_skips_validation(tmp_path, monkeypatch):
    """force=True skips the op availability check entirely."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = _save_technique(
        store,
        name="force-replay",
        required_ops=["missingCustomOP"],
        nodes={"/c1": {"name": "c1", "type": "missingCustomOP", "family": "COMP"}},
    )

    client = _ReplayClient(families={"TOP": ["noiseTOP"]})  # Missing the required op
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client, store=store)

    from td_mcp.models import MemoryReplayInput

    result = await registry.td_memory_replay(
        MemoryReplayInput(
            technique_id=tid,
            parent_path="/project1",
            scope="project",
            force=True,
        ),
        ctx,
    )
    # Should NOT be blocked despite missing ops
    assert result.get("status") != "blocked"
    # Should NOT have queried families at all
    families_calls = [c for c in client.calls if c[0] == "families"]
    assert len(families_calls) == 0


@pytest.mark.asyncio
async def test_replay_no_required_ops_skips_check(tmp_path, monkeypatch):
    """Techniques without required_op_types skip the families check."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = _save_technique(
        store,
        name="no-reqs",
        required_ops=[],  # Empty list
        nodes={"/n1": {"name": "n1", "type": "noiseTOP", "family": "TOP"}},
    )

    client = _ReplayClient(families={"TOP": ["noiseTOP"]})
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client, store=store)

    from td_mcp.models import MemoryReplayInput

    result = await registry.td_memory_replay(
        MemoryReplayInput(
            technique_id=tid,
            parent_path="/project1",
            scope="project",
        ),
        ctx,
    )
    assert result.get("status") != "blocked"
    # Should NOT have queried families (no ops to check)
    families_calls = [c for c in client.calls if c[0] == "families"]
    assert len(families_calls) == 0


@pytest.mark.asyncio
async def test_replay_families_error_allows_replay(tmp_path, monkeypatch):
    """If families endpoint fails, replay proceeds (graceful fallback)."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = _save_technique(
        store,
        name="fallback",
        required_ops=["noiseTOP"],
        nodes={"/n1": {"name": "n1", "type": "noiseTOP", "family": "TOP"}},
    )

    client = _ReplayClient(families_error=True)  # Will raise on families call
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client, store=store)

    from td_mcp.models import MemoryReplayInput

    result = await registry.td_memory_replay(
        MemoryReplayInput(
            technique_id=tid,
            parent_path="/project1",
            scope="project",
        ),
        ctx,
    )
    # Should NOT be blocked — error means we allow replay
    assert result.get("status") != "blocked"


@pytest.mark.asyncio
async def test_replay_missing_recipe_returns_error(tmp_path, monkeypatch):
    """Technique without a recipe returns helpful error with key_params."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add(
        {
            "complexity": "large",
            "key_params": {"noise_scale": 2.5},
            "families": ["TOP"],
            "op_types": ["noiseTOP"],
            # No recipe — large networks don't get full recipes
        },
        scope="project",
        name="large-technique",
    )

    client = _ReplayClient(families={"TOP": ["noiseTOP"]})
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client, store=store)

    from td_mcp.models import MemoryReplayInput

    result = await registry.td_memory_replay(
        MemoryReplayInput(
            technique_id=tid,
            parent_path="/project1",
            scope="project",
        ),
        ctx,
    )
    assert result["status"] == "error"
    assert "recipe" in result["message"].lower()
    assert result["key_params"] == {"noise_scale": 2.5}


@pytest.mark.asyncio
async def test_replay_not_found_returns_error(tmp_path, monkeypatch):
    """Non-existent technique ID returns error."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")

    client = _ReplayClient(families={})
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client, store=store)

    from td_mcp.models import MemoryReplayInput

    result = await registry.td_memory_replay(
        MemoryReplayInput(
            technique_id="nonexistent-id-12345",
            parent_path="/project1",
            scope="project",
        ),
        ctx,
    )
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()
