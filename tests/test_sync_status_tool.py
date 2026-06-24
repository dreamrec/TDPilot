from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as _registry
from td_mcp import __version__
from td_mcp.registry import tools_meta


class _FakeClient:
    async def request(self, endpoint, body=None):
        if endpoint == "health":
            return {"status": "ok", "api_version": "2.0.1"}
        if endpoint == "info":
            return {"mcp_component_version": "2.0.1"}
        raise AssertionError(endpoint)


@pytest.mark.asyncio
async def test_td_sync_status_reports_public_drift_and_live_mismatch(monkeypatch):
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: _FakeClient())
    monkeypatch.setattr(
        tools_meta,
        "_tox_freshness_status",
        lambda: {"fresh": True, "messages": ["fresh"]},
    )
    monkeypatch.setattr(
        tools_meta,
        "_plugin_cache_versions",
        lambda: [
            {
                "name": "codex",
                "path": "/tmp/cache",
                "versions": ["2.0.2"],
                "contains_server_version": True,
            }
        ],
    )
    monkeypatch.setattr(
        tools_meta,
        "_remote_release_status",
        lambda: {"github_latest": "2.0.2", "npm_latest": "2.0.2", "newer_available": False},
    )
    monkeypatch.setattr(
        tools_meta,
        "_github_repo_description_status",
        lambda: {
            "description": "TDPilot v2.0.1 — stale",
            "expected": "TDPilot v2.0.2 — fresh",
            "matches": False,
        },
    )
    ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context={}))

    out = await tools_meta.td_sync_status(ctx, check_remote=True)
    payload = json.loads(out)

    assert hasattr(_registry, "td_sync_status")
    assert payload["success"] is True
    assert payload["server"]["version"] == __version__
    assert payload["touchdesigner"]["component_version"] == "2.0.1"
    assert payload["touchdesigner"]["matches_server"] is False
    assert payload["tox"]["fresh"] is True
    assert payload["remote"]["github_latest"] == "2.0.2"
    assert payload["github_repo"]["matches"] is False
    assert payload["overall"] == "warning"
    assert any(
        "Reload/export the bundled td_component/tdpilot.tox" in item for item in payload["recommendations"]
    )
