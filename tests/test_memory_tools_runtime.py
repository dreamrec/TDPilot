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
        MemorySaveInput(
            technique={"node_count": 1, "complexity": "small"},
            scope="project",
            name="demo-technique",
            tags=["demo"],
        ),
        ctx,
    )
    assert saved["status"] == "ok"

    listed = await registry.td_memory_list(MemoryListInput(scope="project"), ctx)
    assert listed["status"] == "ok"
    assert listed["count"] == 1

    recalled = await registry.td_memory_recall(MemoryRecallInput(query="demo"), ctx)
    assert recalled["status"] == "ok"
    assert recalled["count"] == 1

    set_pref = await registry.td_memory_preferences(
        MemoryPreferencesInput(action="set", key="palette", value="warm", scope="project"),
        ctx,
    )
    assert set_pref["status"] == "ok"

    list_pref = await registry.td_memory_preferences(
        MemoryPreferencesInput(action="list", scope="project"),
        ctx,
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
        MemoryReplayInput(
            technique_id=technique_id,
            parent_path="/project1/replay",
            scope="project",
        ),
        ctx,
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
    assert len(connect_payloads) == 1
    assert "source_path" in connect_payloads[0]
    assert "target_path" in connect_payloads[0]
    assert "from" not in connect_payloads[0]
    assert "to" not in connect_payloads[0]
