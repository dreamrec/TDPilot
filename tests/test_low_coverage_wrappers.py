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
from td_mcp.registry import tools_data, tools_safety, tools_state
from td_mcp.safety.manager import SafetyManager
from td_mcp.services import ServiceContainer


class _RecClient:
    """Records request() calls; returns scripted responses (default {})."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict | None]] = []

    async def request(self, endpoint, body=None):
        self.calls.append((endpoint, body))
        return self.responses.get(endpoint, {})


def _ctx(*, safety_manager=None):
    container = ServiceContainer(td_client=None, safety_manager=safety_manager)
    state = {"services": container}
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=state, lifespan_state=state))


def _use_client(monkeypatch, client):
    # _get_client isinstance-checks for a real TDClient, so inject the recorder.
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)


def _endpoints(client):
    return [c[0] for c in client.calls]


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
