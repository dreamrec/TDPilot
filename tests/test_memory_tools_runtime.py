from __future__ import annotations

from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as registry
from td_mcp.memory import PreferenceStore, TechniqueStore
from td_mcp.models import (
    MemoryListInput,
    MemoryPreferencesInput,
    MemoryRecallInput,
    MemoryReplayInput,
    MemorySaveInput,
)
from td_mcp.services import ServiceContainer


def _make_ctx(*, store: TechniqueStore, pref: PreferenceStore):
    services = ServiceContainer(
        td_client=object(),
        technique_store=store,
        preference_store=pref,
    )
    lifespan_state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


@pytest.mark.asyncio
async def test_memory_tools_support_dict_lifespan_context(tmp_path):
    store = TechniqueStore(base_dir=str(tmp_path), project_name="runtime")
    pref = PreferenceStore(base_dir=str(tmp_path), project_name="runtime")
    ctx = _make_ctx(store=store, pref=pref)

    saved = await registry.td_memory_save(
        ctx,
        technique={"node_count": 1, "complexity": "small"},
        scope="project",
        name="demo-technique",
        tags=["demo"],
    )
    assert saved["status"] == "ok"

    listed = await registry.td_memory_list(ctx, scope="project")
    assert listed["status"] == "ok"
    assert listed["count"] == 1

    recalled = await registry.td_memory_recall(ctx, query="demo")
    assert recalled["status"] == "ok"
    assert recalled["count"] == 1

    set_pref = await registry.td_memory_preferences(
        ctx,
        action="set",
        key="palette",
        value="warm",
        scope="project",
    )
    assert set_pref["status"] == "ok"

    list_pref = await registry.td_memory_preferences(
        ctx,
        action="list",
        scope="project",
    )
    assert list_pref["status"] == "ok"
    assert list_pref["preferences"]["palette"] == "warm"


class _RecordingClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self._counter = 0

    async def request(self, endpoint: str, body: dict | None = None):
        payload = body or {}
        self.calls.append((endpoint, payload))
        if endpoint == "node/create":
            self._counter += 1
            return {"success": True, "node": {"path": f"/project1/replay/n{self._counter}"}}
        return {"success": True}


# ---------------------------------------------------------------------------
# Lazy project-scope rebinding (v1.4.4 reliability release)
# If the MCP server starts before TD is reachable, stores are constructed
# with project_name=None and project-scoped tools fail with
# "TDPILOT_PROJECT_NAME is not set" for the entire session. This was
# observed live against the installed server while TD *was* reachable:
# the startup-time resolution skipped the fetch and never re-tried.
# _ensure_project_scope(ctx) demand-binds on the first memory-tool call.
# ---------------------------------------------------------------------------


class _ProjectInfoClient:
    """Fake TD client whose `info` endpoint returns a project_name."""

    def __init__(self, project_name: str | None = "LiveTestProject.toe", raises: bool = False):
        self._project_name = project_name
        self._raises = raises
        self.info_calls = 0

    async def request(self, endpoint: str, body: dict | None = None):
        if endpoint == "info":
            self.info_calls += 1
            if self._raises:
                raise ConnectionError("TD not reachable")
            return {"project_name": self._project_name} if self._project_name else {}
        return {}


def _make_unbound_ctx(tmp_path, *, client):
    store = TechniqueStore(base_dir=str(tmp_path), project_name=None)
    pref = PreferenceStore(base_dir=str(tmp_path), project_name=None)
    services = ServiceContainer(
        td_client=client,
        technique_store=store,
        preference_store=pref,
    )
    lifespan_state = {"services": services}
    ctx = SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )
    return ctx, services, store, pref


@pytest.mark.asyncio
async def test_ensure_project_scope_binds_from_live_td(tmp_path):
    client = _ProjectInfoClient(project_name="LiveTestProject.toe")
    ctx, services, store, pref = _make_unbound_ctx(tmp_path, client=client)

    assert store.stats()["project_name"] is None
    assert pref.stats()["project_name"] is None

    await registry._ensure_project_scope(ctx)

    # .toe suffix is stripped, both stores now bound to the same project
    assert store.stats()["project_name"] == "LiveTestProject"
    assert pref.stats()["project_name"] == "LiveTestProject"
    assert client.info_calls == 1


@pytest.mark.asyncio
async def test_ensure_project_scope_no_op_when_already_bound(tmp_path):
    client = _ProjectInfoClient(project_name="ShouldNotFetch.toe")
    ctx, services, store, pref = _make_unbound_ctx(tmp_path, client=client)
    # Pre-bind both stores as if startup had succeeded
    store.rebind_project_scope("PreBoundProject")
    pref.rebind_project_scope("PreBoundProject")

    await registry._ensure_project_scope(ctx)

    assert store.stats()["project_name"] == "PreBoundProject"
    assert client.info_calls == 0  # no TD round-trip


@pytest.mark.asyncio
async def test_ensure_project_scope_silent_on_td_unreachable(tmp_path):
    client = _ProjectInfoClient(raises=True)
    ctx, services, store, pref = _make_unbound_ctx(tmp_path, client=client)

    # Must not raise — TD being down is expected during early startup
    await registry._ensure_project_scope(ctx)

    assert store.stats()["project_name"] is None
    assert pref.stats()["project_name"] is None
    assert client.info_calls == 1


@pytest.mark.asyncio
async def test_ensure_project_scope_silent_when_info_lacks_project_name(tmp_path):
    client = _ProjectInfoClient(project_name=None)
    ctx, services, store, pref = _make_unbound_ctx(tmp_path, client=client)

    await registry._ensure_project_scope(ctx)

    assert store.stats()["project_name"] is None
    assert pref.stats()["project_name"] is None
    assert client.info_calls == 1


@pytest.mark.asyncio
async def test_memory_save_rebinds_and_succeeds_after_startup_miss(tmp_path):
    """End-to-end: server started unbound, TD later reachable, save works."""
    client = _ProjectInfoClient(project_name="BelatedProject.toe")
    ctx, services, store, pref = _make_unbound_ctx(tmp_path, client=client)

    # Before the fix: this raised "TDPILOT_PROJECT_NAME is not set". After:
    # the tool auto-rebinds via _ensure_project_scope and the save succeeds.
    result = await registry.td_memory_save(
        ctx,
        technique={"node_count": 1, "complexity": "small"},
        scope="project",
        name="belated",
        tags=["v1.4.4"],
    )
    assert result["status"] == "ok"
    assert store.stats()["project_name"] == "BelatedProject"


@pytest.mark.asyncio
async def test_memory_replay_uses_live_endpoint_contract(tmp_path, monkeypatch):
    store = TechniqueStore(base_dir=str(tmp_path), project_name="runtime")
    pref = PreferenceStore(base_dir=str(tmp_path), project_name="runtime")
    ctx = _make_ctx(store=store, pref=pref)

    technique_id = store.add(
        {
            "complexity": "small",
            "recipe": {
                "nodes": {
                    "/": {"name": "root", "type": "baseCOMP", "family": "COMP", "params": {}},
                    "/noise1": {
                        "name": "noise1",
                        "type": "noiseTOP",
                        "family": "TOP",
                        "params": {"period": 2.0},
                        "expressions": {"seed": "absTime.frame"},
                    },
                    "/out1": {
                        "name": "out1",
                        "type": "nullTOP",
                        "family": "TOP",
                        "params": {},
                    },
                },
                "connections": [
                    {"from": "/noise1", "to": "/out1", "from_index": 0, "to_index": 0},
                ],
            },
        },
        scope="project",
        name="replay-contract",
    )

    recording_client = _RecordingClient()
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: recording_client)

    replayed = await registry.td_memory_replay(
        ctx,
        technique_id=technique_id,
        parent_path="/project1/replay",
        scope="project",
    )

    assert replayed["status"] == "ok"
    assert replayed["nodes_created"] == 2
    assert replayed["connections_wired"] == 1

    endpoints = [endpoint for endpoint, _ in recording_client.calls]
    assert "node/parameters/set" not in endpoints
    assert "node/params/set" in endpoints

    create_payloads = [payload for endpoint, payload in recording_client.calls if endpoint == "node/create"]
    assert create_payloads
    for payload in create_payloads:
        assert "parent_path" in payload
        assert "node_type" in payload
        assert "parent" not in payload
        assert "type" not in payload

    connect_payloads = [payload for endpoint, payload in recording_client.calls if endpoint == "node/connect"]
    assert len(connect_payloads) >= 1
    assert "source_path" in connect_payloads[0]
    assert "target_path" in connect_payloads[0]
    assert "from" not in connect_payloads[0]
    assert "to" not in connect_payloads[0]
