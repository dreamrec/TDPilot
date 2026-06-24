"""Focused behavioural tests for the thinnest public tool-wrapper modules.

External review flagged tools_safety / tools_state / tools_data as low-coverage
(~17-25%). These are not a coverage crusade — just a small number of tests that
exercise the happy path (correct endpoint forwarded, parseable envelope) and a
validation/error path for the highest-traffic tools in each, so regressions in
the wrappers don't hide.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as _registry
from td_mcp.memory import KnowledgeStore
from td_mcp.registry import (
    tools_data,
    tools_events,
    tools_info,
    tools_knowledge_store,
    tools_notes,
    tools_optimizer,
    tools_safety,
    tools_state,
    tools_system,
)
from td_mcp.safety.manager import SafetyManager
from td_mcp.services import ServiceContainer


class _RecClient:
    """Records request() calls; returns scripted responses (default {})."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict | None]] = []

    async def request(self, endpoint, body=None):
        self.calls.append((endpoint, body))
        response = self.responses.get(endpoint, {})
        if isinstance(response, list):
            if response:
                return response.pop(0)
            return {}
        return response


def _ctx(*, safety_manager=None):
    container = ServiceContainer(td_client=None, safety_manager=safety_manager)
    state = {"services": container}
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=state, lifespan_state=state))


def _use_client(monkeypatch, client):
    # _get_client isinstance-checks for a real TDClient, so inject the recorder.
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)


def _endpoints(client):
    return [c[0] for c in client.calls]


class _JobManager:
    def __init__(self):
        self.runner = None
        self.updates: list[tuple[str, float, dict | None]] = []

    def start_async(self, *, description, runner):
        self.runner = runner
        return {"job_id": "job-1", "description": description, "status": "running"}

    def update_job(self, job_id, *, progress, result=None):
        self.updates.append((job_id, progress, result))


class _Events:
    def get_recent_events(self, limit=200):
        return [{"timestamp": 10.0}, {"timestamp": 11.0}]


class _EventManager:
    def __init__(self):
        self.subscriptions: list[tuple[str, str, dict]] = []
        self.events = [
            {"event_type": "node_error", "path": "/project1/bad", "message": "boom"},
            {"event_type": "cook_complete", "path": "/project1/out1"},
        ]

    def register_subscription(self, path, event_type, body):
        self.subscriptions.append((path, event_type, body))

    def unregister_all_for_path(self, path):
        before = len(self.subscriptions)
        self.subscriptions = [row for row in self.subscriptions if row[0] != path]
        return before - len(self.subscriptions)

    def list_subscriptions(self):
        return list(self.subscriptions)

    def get_recent_events(self, event_type=None, limit=50):
        rows = [row for row in self.events if event_type is None or row["event_type"] == event_type]
        return rows[:limit]

    def stats(self):
        return {"subscriptions": len(self.subscriptions), "events": len(self.events)}


# ── tools_data: thin _forward wrappers ───────────────────────────────


@pytest.mark.asyncio
async def test_td_chop_data_forwards_to_chop_data(monkeypatch):
    client = _RecClient({"chop/data": {"channels": [{"name": "chan1", "values": [1.0, 2.0]}]}})
    _use_client(monkeypatch, client)
    out = await tools_data.td_chop_data(_ctx(), path="/p/c")
    assert "chop/data" in _endpoints(client)
    assert json.loads(out)["channels"][0]["name"] == "chan1"


@pytest.mark.asyncio
async def test_td_cooking_info_forwards_to_cooking(monkeypatch):
    client = _RecClient({"cooking": {"total_cook_ms": 1.5, "stuck": []}})
    _use_client(monkeypatch, client)
    out = await tools_data.td_cooking_info(_ctx(), path="/project1")
    assert "cooking" in _endpoints(client)
    assert json.loads(out)["total_cook_ms"] == 1.5


@pytest.mark.asyncio
async def test_td_get_errors_forwards_to_node_errors(monkeypatch):
    client = _RecClient({"node/errors": {"issues": [{"path": "/p/n", "message": "bad"}]}})
    _use_client(monkeypatch, client)
    out = await tools_data.td_get_errors(_ctx(), path="/project1")
    assert "node/errors" in _endpoints(client)
    assert json.loads(out)["issues"][0]["message"] == "bad"


@pytest.mark.asyncio
async def test_data_forwarders_preserve_payload_shapes(monkeypatch):
    client = _RecClient(
        {
            "screenshot": {"path": "/p/out", "format": "jpeg"},
            "geometry/data": {"points": [[0, 0, 0]]},
            "pop/inspect": {"attributes": {"P": {"size": 3}}},
            "chop/data": {"channels": []},
        }
    )
    _use_client(monkeypatch, client)
    ctx = _ctx()

    await tools_data.td_screenshot(ctx, path="/p/out", quality=0.75)
    await tools_data.td_geometry_data(ctx, path="/p/geo", include_points=False, include_prims=True, limit=12)
    await tools_data.td_pop_inspect(ctx, path="/p/pop", point_attributes=["P"], count=4, delayed=True)
    await tools_data.td_chop_data(ctx, path="/p/chop", channels=["tx"], range=[1, 3])

    assert client.calls[0] == ("screenshot", {"path": "/p/out", "quality": 0.75})
    assert client.calls[1] == (
        "geometry/data",
        {"path": "/p/geo", "include_points": False, "include_prims": True, "limit": 12},
    )
    assert client.calls[2][0] == "pop/inspect"
    assert client.calls[2][1]["point_attributes"] == ["P"]
    assert client.calls[2][1]["delayed"] is True
    assert client.calls[3] == ("chop/data", {"path": "/p/chop", "channels": ["tx"], "range": [1, 3]})


@pytest.mark.asyncio
async def test_td_search_nodes_merges_legacy_and_exec_scopes(monkeypatch):
    client = _RecClient(
        {
            "search": {"results": [{"path": "/p/name", "type": "nullTOP"}]},
            "exec": [
                {"success": True, "result": {"results": [{"path": "/p/dat", "scope": "dat_text"}]}},
                {"success": True, "result": {"results": [{"path": "/p/expr", "scope": "param_exprs"}]}},
            ],
        }
    )
    _use_client(monkeypatch, client)

    out = await tools_data.td_search_nodes(
        _ctx(),
        query="foo",
        path="/project1",
        scopes=["name", "dat_text", "param_exprs"],
        limit=5,
    )
    payload = json.loads(out)

    assert [row["path"] for row in payload["results"]] == ["/p/name", "/p/dat", "/p/expr"]
    assert payload["scopes_searched"] == ["name", "dat_text", "param_exprs"]
    assert payload["scopes_with_errors"] == {}


# ── tools_events/info/system/knowledge_store: remaining thin wrappers ──


@pytest.mark.asyncio
async def test_event_wrappers_provision_and_read_recent_events(monkeypatch):
    client = _RecClient(
        {
            "monitor/subscribe": {"success": True, "td_subscription_id": "sub-1"},
            "monitor/unsubscribe": {"success": True},
        }
    )
    manager = _EventManager()
    _use_client(monkeypatch, client)
    monkeypatch.setattr(_registry, "_get_event_manager", lambda _ctx: manager)
    ctx = _ctx()

    subscribed = json.loads(
        await tools_events.td_subscribe(
            ctx, path="/project1/out1", event_types=["node_error"], rate_limit=0.05
        )
    )
    recent = json.loads(await tools_events.td_get_events(ctx, event_type="node_error", limit=5))
    unsubscribed = json.loads(await tools_events.td_unsubscribe(ctx, path="/project1/out1"))

    assert subscribed["success"] is True
    assert subscribed["active_subscriptions"] == 1
    assert client.calls[0] == (
        "monitor/subscribe",
        {"path": "/project1/out1", "event_types": ["node_error"], "rate_limit": 0.05},
    )
    assert recent["count"] == 1
    assert recent["events"][0]["message"] == "boom"
    assert unsubscribed["success"] is True
    assert client.calls[-1] == ("monitor/unsubscribe", {"path": "/project1/out1"})


@pytest.mark.asyncio
async def test_get_capabilities_reports_live_component_mismatch(monkeypatch):
    client = _RecClient({"info": {"mcp_component_version": "2.0.1"}})
    _use_client(monkeypatch, client)
    monkeypatch.setattr(
        tools_info,
        "detect_capabilities",
        lambda _ctx, td_build="": SimpleNamespace(
            to_dict=lambda: {"supports_sampling": False, "td_build": td_build}
        ),
    )

    out = await tools_info.td_get_capabilities(_ctx())
    payload = json.loads(out)

    assert payload["version"]["component_version"] == "2.0.1"
    assert payload["version"]["mismatch"] is True
    assert payload["client_capabilities"]["supports_sampling"] is False


@pytest.mark.asyncio
async def test_system_exec_wrapper_parses_json_result(monkeypatch):
    client = _RecClient({"exec": {"success": True, "result": '{"python_version": "3.12", "paths": []}'}})
    _use_client(monkeypatch, client)
    monkeypatch.setattr(_registry, "_check_exec_not_off", lambda: None)
    monkeypatch.setattr(_registry, "_check_exec_mode_at_least", lambda _mode, _tool: None)

    payload = await tools_system.td_python_env_status(_ctx())

    assert payload["python_version"] == "3.12"
    assert client.calls[0][0] == "exec"
    assert client.calls[0][1]["exec_mode"] == "full"


@pytest.mark.asyncio
async def test_knowledge_store_wrappers_round_trip(monkeypatch, tmp_path):
    store = KnowledgeStore(base_dir=str(tmp_path), project_name="show")
    monkeypatch.setattr(_registry, "_get_knowledge_store", lambda _ctx: store)
    ctx = _ctx()

    saved = json.loads(
        await tools_knowledge_store.td_knowledge_save(
            ctx,
            body="# Feedback\nUse a level TOP.",
            name="Feedback note",
            description="feedback recipe",
            tags=["Feedback"],
            scope="project",
        )
    )
    recalled = json.loads(
        await tools_knowledge_store.td_knowledge_recall(ctx, query="feedback", scope="project")
    )
    fetched = json.loads(
        await tools_knowledge_store.td_knowledge_get(ctx, entry_id=saved["id"], scope="project")
    )
    listed = json.loads(
        await tools_knowledge_store.td_knowledge_list(ctx, scope="project", tags=["feedback"])
    )

    assert saved["success"] is True
    assert recalled["count"] == 1
    assert fetched["entry"]["body"].startswith("# Feedback")
    assert listed["results"][0]["name"] == "Feedback note"


# ── tools_state: timescale + locations ───────────────────────────────


@pytest.mark.asyncio
async def test_td_get_timescale_state_uses_timeline(monkeypatch):
    client = _RecClient({"timeline": {"frame": 30, "fps": 60, "playing": True}})
    _use_client(monkeypatch, client)
    out = await tools_state.td_get_timescale_state(_ctx(), bpm_hint=120.0)
    assert "timeline" in _endpoints(client)
    payload = json.loads(out)
    assert payload["timeline"]["fps"] == 60
    assert "timescale" in payload


@pytest.mark.asyncio
async def test_td_locations_list_returns_envelope(monkeypatch):
    # The focus probe runs via exec; an empty response makes it fall back to a
    # generic project key. list is read-only, so no store mutation occurs.
    client = _RecClient({"exec": {}})
    _use_client(monkeypatch, client)
    out = await tools_state.td_locations(_ctx(), action="list")
    payload = json.loads(out)
    assert payload["success"] is True
    assert payload["action"] == "list"
    assert "count" in payload


@pytest.mark.asyncio
async def test_td_locations_rejects_invalid_action(monkeypatch):
    client = _RecClient()
    _use_client(monkeypatch, client)
    out = await tools_state.td_locations(_ctx(), action="frobnicate")
    payload = json.loads(out)
    assert payload["success"] is False
    assert "invalid action" in payload["error"]


@pytest.mark.asyncio
async def test_td_get_state_vector_cache_hit_and_force_refresh(monkeypatch):
    calls = []

    async def _build(path, ctx):
        calls.append(path)
        return {"path": path, "health": {"unstable": False}}

    monkeypatch.setattr(_registry, "_build_state_vector", _build)
    monkeypatch.setattr(_registry, "TD_STATE_VECTOR_TTL", 60.0)
    _registry._STATE_VECTOR_CACHE.clear()
    ctx = _ctx()

    first = json.loads(await tools_state.td_get_state_vector(ctx, path="/project1"))
    second = json.loads(await tools_state.td_get_state_vector(ctx, path="/project1"))
    third = json.loads(await tools_state.td_get_state_vector(ctx, path="/project1", force_refresh=True))

    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert third["cache"]["hit"] is False
    assert calls == ["/project1", "/project1"]
    _registry._STATE_VECTOR_CACHE.clear()


@pytest.mark.asyncio
async def test_td_locations_save_rename_go_delete_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("TDPILOT_HOME", str(tmp_path))
    client = _RecClient(
        {
            "exec": [
                {
                    "success": True,
                    "result": {"project_name": "show.toe", "active_pane_path": "/project1/start"},
                },
                {
                    "success": True,
                    "result": {"project_name": "show.toe", "active_pane_path": "/project1/start"},
                },
                {
                    "success": True,
                    "result": {"project_name": "show.toe", "active_pane_path": "/project1/start"},
                },
                {
                    "success": True,
                    "result": {"success": True, "navigated_to": "/project1/start"},
                },
                {
                    "success": True,
                    "result": {"project_name": "show.toe", "active_pane_path": "/project1/start"},
                },
            ]
        }
    )
    _use_client(monkeypatch, client)
    ctx = _ctx()

    saved = json.loads(await tools_state.td_locations(ctx, action="save", name="home"))
    renamed = json.loads(await tools_state.td_locations(ctx, action="rename", name="home", new_name="stage"))
    gone = json.loads(await tools_state.td_locations(ctx, action="go", name="stage"))
    deleted = json.loads(await tools_state.td_locations(ctx, action="delete", name="stage"))

    assert saved["success"] is True
    assert renamed["success"] is True
    assert gone["success"] is True
    assert gone["navigation"]["success"] is True
    assert deleted["success"] is True


# ── tools_safety: param bounds via SafetyManager ─────────────────────


@pytest.mark.asyncio
async def test_td_set_and_clear_param_bounds():
    safety = SafetyManager()
    ctx = _ctx(safety_manager=safety)

    set_out = json.loads(
        await tools_safety.td_set_param_bounds(
            ctx,
            bounds=[{"path": "/p/n", "param": "opacity", "min_val": 0.0, "max_val": 1.0}],
            enforce_mode="clamp",
        )
    )
    assert set_out["success"] is True
    assert set_out["mode"] == "clamp"
    assert set_out["bounds_count"] == 1

    clear_out = json.loads(await tools_safety.td_clear_param_bounds(ctx))
    assert clear_out["success"] is True
    assert clear_out["cleared"] == 1
    assert clear_out["remaining"] == 0


@pytest.mark.asyncio
async def test_td_set_param_bounds_rejects_bad_enforce_mode():
    safety = SafetyManager()
    with pytest.raises(Exception):  # noqa: B017 — SetBoundsInput validator rejects bad mode
        await tools_safety.td_set_param_bounds(
            _ctx(safety_manager=safety),
            bounds=[{"path": "/p/n", "param": "opacity"}],
            enforce_mode="not_a_mode",
        )


@pytest.mark.asyncio
async def test_td_emergency_stabilize_still_pauses_and_clamps_when_snapshot_fails(monkeypatch):
    client = _RecClient({"timeline": {"playing": True}, "timeline/set": {"success": True}})
    safety = SafetyManager()
    safety.set_mode("warn")

    async def _raise_snapshot(*_args, **_kwargs):
        raise RuntimeError("snapshot store unavailable")

    _use_client(monkeypatch, client)
    monkeypatch.setattr(_registry, "_get_safety_manager", lambda _ctx: safety)
    monkeypatch.setattr(_registry, "_get_snapshot_manager", lambda _ctx: object())
    monkeypatch.setattr(_registry, "_capture_snapshot_payload", _raise_snapshot)

    out = await tools_safety.td_emergency_stabilize(_ctx(safety_manager=safety), path="/project1")
    payload = json.loads(out)

    assert payload["success"] is True
    assert "timeline_paused" in payload["actions"]
    assert "safety_mode_clamp" in payload["actions"]
    assert "snapshot store unavailable" in payload["snapshot_warning"]
    assert payload["snapshot"] is None
    assert safety.get_mode() == "clamp"
    assert ("timeline/set", {"action": "pause"}) in client.calls


# ── tools_notes: embed code escaping ─────────────────────────────────


def test_component_notes_embed_code_escapes_python_literals():
    code = tools_notes._embed_code(
        '/project1/comp"quoted"',
        'body with """ triple quotes, backslash \\, and "quotes"',
        ['tag"quoted', "tag\\slash"],
    )

    compile(code, "<tdpilot_notes_embed>", "exec")
    assert 'tag\\"quoted' in code
    assert "tag\\\\slash" in code


@pytest.mark.asyncio
async def test_td_component_notes_crud_summary_and_embed(monkeypatch, tmp_path):
    monkeypatch.setenv("TDPILOT_HOME", str(tmp_path))
    client = _RecClient(
        {
            "exec": [
                {"success": True, "result": {"project_name": "notes_show.toe"}},
                {
                    "success": True,
                    "result": {
                        "success": True,
                        "embedded_at": "/project1/comp/tdpilot_notes",
                        "tags": ["feedback"],
                    },
                },
                {"success": True, "result": {"project_name": "notes_show.toe"}},
                {"success": True, "result": {"project_name": "notes_show.toe"}},
                {"success": True, "result": {"project_name": "notes_show.toe"}},
                {"success": True, "result": {"project_name": "notes_show.toe"}},
                {"success": True, "result": {"project_name": "notes_show.toe"}},
                {"success": True, "result": {"project_name": "notes_show.toe"}},
            ]
        }
    )
    _use_client(monkeypatch, client)
    ctx = _ctx()

    set_out = json.loads(
        await tools_notes.td_component_notes(
            ctx,
            action="set",
            path="/project1/comp",
            body='notes with "quotes"',
            embed=True,
            tags=["feedback"],
        )
    )
    append_out = json.loads(
        await tools_notes.td_component_notes(
            ctx,
            action="append",
            path="/project1/comp",
            body="more context",
            tags=["todo"],
        )
    )
    get_out = json.loads(await tools_notes.td_component_notes(ctx, action="get", path="/project1/comp"))
    index_out = json.loads(await tools_notes.td_component_notes(ctx, action="index"))
    summary_out = json.loads(await tools_notes.td_component_notes(ctx, action="summarize", path="/project1"))
    delete_out = json.loads(await tools_notes.td_component_notes(ctx, action="delete", path="/project1/comp"))

    assert set_out["success"] is True
    assert set_out["embed"]["embedded_at"] == "/project1/comp/tdpilot_notes"
    assert append_out["note"]["tags"] == ["feedback", "todo"]
    assert "more context" in get_out["note"]["body"]
    assert index_out["count"] == 1
    assert "/project1/comp" in summary_out["markdown"]
    assert delete_out["success"] is True


@pytest.mark.asyncio
async def test_optimizer_and_dynamics_start_jobs_and_runner_samples(monkeypatch):
    client = _RecClient(
        {
            "timeline": {"frame": 1, "seconds": 0.1, "playing": True},
            "cooking": {
                "fps": 60.0,
                "target_fps": 60.0,
                "nodes": [{"path": "/project1/heavy", "cookTime": 6.0}],
            },
            "node/errors": {"issues": []},
        }
    )
    jobs = _JobManager()

    async def _raise_snapshot(*_args, **_kwargs):
        raise RuntimeError("snapshot unavailable")

    async def _no_sleep(_delay):
        return None

    _use_client(monkeypatch, client)
    monkeypatch.setattr(_registry, "_get_safety_manager", lambda _ctx: SafetyManager())
    monkeypatch.setattr(_registry, "_get_snapshot_manager", lambda _ctx: object())
    monkeypatch.setattr(_registry, "_get_job_manager", lambda _ctx: jobs)
    monkeypatch.setattr(_registry, "_get_event_manager", lambda _ctx: _Events())
    monkeypatch.setattr(_registry, "_capture_snapshot_payload", _raise_snapshot)
    monkeypatch.setattr(
        tools_optimizer, "detect_capabilities", lambda _ctx: SimpleNamespace(supports_sampling=False)
    )
    monkeypatch.setattr(tools_optimizer.asyncio, "sleep", _no_sleep)

    optimize = json.loads(
        await tools_optimizer.td_optimize_visual(
            _ctx(),
            goal="reduce feedback",
            output_top="/project1/out1",
            adjustable_params=[
                {"path": "/project1/level1", "param": "opacity", "min_val": 0.0, "max_val": 1.0, "step": 0.1}
            ],
        )
    )
    dynamics = json.loads(
        await tools_optimizer.td_describe_dynamics(
            _ctx(),
            path="/project1",
            observation_window=0.5,
            sample_rate=2.0,
        )
    )
    report = await jobs.runner("job-1")

    assert optimize["success"] is True
    assert "snapshot unavailable" in optimize["snapshot_warning"]
    assert dynamics["target_samples"] == 1
    assert report["samples"][0]["heavy_nodes_count"] == 1
    assert jobs.updates[0][1] == 1.0
