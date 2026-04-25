"""Behavioral tests for TD 2025 tools: td_component_standardize, td_color_pipeline.

These tools delegate to TD via exec, so we mock the client to return
realistic JSON payloads and verify the code generation + parsing paths.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as registry
from td_mcp.models import ColorPipelineInput, ComponentStandardizeInput
from td_mcp.services import ServiceContainer

# ── Helpers ──────────────────────────────────────────────────


class _ExecClient:
    """Client that intercepts exec calls and returns canned results."""

    def __init__(self, exec_result: dict):
        self._exec_result = exec_result
        self.last_code: str | None = None
        self.calls: list = []

    async def request(self, endpoint: str, body: dict | None = None):
        body = body or {}
        self.calls.append((endpoint, body))
        if endpoint == "exec":
            self.last_code = body.get("code", "")
            return {"result": json.dumps(self._exec_result)}
        if endpoint == "project/lifecycle":
            return {"ok": True}
        return {}


def _make_ctx(*, client=None):
    services = ServiceContainer(
        td_client=client or object(),
        technique_store=None,
        preference_store=None,
    )
    lifespan_state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


# ── td_component_standardize tests ──────────────────────────


@pytest.mark.asyncio
async def test_standardize_audit_clean_comp(monkeypatch):
    """Audit mode on a clean COMP returns zero issues."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")
    client = _ExecClient(
        {
            "path": "/project1/MyComp",
            "issues": [],
            "fixed": [],
            "issue_count": 0,
            "has_extension": True,
            "op_type": "baseCOMP",
        }
    )
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    result = await registry.td_component_standardize(
        ctx,
        path="/project1/MyComp",
        fix=False,
    )
    assert result["issue_count"] == 0
    assert result["has_extension"] is True
    assert result["op_type"] == "baseCOMP"
    # Should NOT have called project/lifecycle (no undo block in audit mode)
    lifecycle_calls = [c for c in client.calls if c[0] == "project/lifecycle"]
    assert len(lifecycle_calls) == 0


@pytest.mark.asyncio
async def test_standardize_audit_missing_params(monkeypatch):
    """Audit mode detects missing custom parameters."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")
    client = _ExecClient(
        {
            "path": "/project1/mycomp",
            "issues": [
                "Missing custom parameter: Version",
                "Missing custom parameter: Help",
                "Name does not start with uppercase: mycomp",
            ],
            "fixed": [],
            "issue_count": 3,
            "has_extension": False,
            "op_type": "baseCOMP",
        }
    )
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    result = await registry.td_component_standardize(
        ctx,
        path="/project1/mycomp",
        fix=False,
    )
    assert result["issue_count"] == 3
    assert "Version" in result["issues"][0]
    assert result["has_extension"] is False


@pytest.mark.asyncio
async def test_standardize_fix_uses_undo_block(monkeypatch):
    """Fix mode wraps the exec call in an undo block."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")
    client = _ExecClient(
        {
            "path": "/project1/mycomp",
            "issues": [],
            "fixed": ["Added parameter: Version", "Added parameter: Help", "Added parameter: Creator"],
            "issue_count": 0,
            "has_extension": False,
            "op_type": "baseCOMP",
        }
    )
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    result = await registry.td_component_standardize(
        ctx,
        path="/project1/mycomp",
        fix=True,
    )
    assert len(result["fixed"]) == 3
    # Should have start_undo_block and end_undo_block calls
    lifecycle_calls = [c for c in client.calls if c[0] == "project/lifecycle"]
    assert len(lifecycle_calls) == 2
    assert lifecycle_calls[0][1]["action"] == "start_undo_block"
    assert lifecycle_calls[1][1]["action"] == "end_undo_block"


@pytest.mark.asyncio
async def test_standardize_exec_off_returns_error(monkeypatch):
    """When exec mode is off, returns an error without calling TD."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "off")
    client = _ExecClient({})
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    result = await registry.td_component_standardize(
        ctx,
        path="/project1/comp1",
        fix=False,
    )
    assert "error" in result
    assert "disabled" in result["error"].lower() or "off" in result["error"].lower()
    # Should NOT have made any client calls
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_standardize_generated_code_contains_path(monkeypatch):
    """The generated Python code references the correct node path."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")
    client = _ExecClient({"path": "/project1/comp1", "issues": [], "fixed": [], "issue_count": 0})
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    await registry.td_component_standardize(
        ctx,
        path="/project1/comp1",
        fix=False,
    )
    assert client.last_code is not None
    assert "/project1/comp1" in client.last_code


@pytest.mark.asyncio
async def test_standardize_fix_code_has_append_custom_page(monkeypatch):
    """Fix mode generates code that uses appendCustomPage without [0] indexing."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")
    client = _ExecClient({"path": "/comp", "issues": [], "fixed": [], "issue_count": 0})
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    await registry.td_component_standardize(
        ctx,
        path="/comp",
        fix=True,
    )
    code = client.last_code
    assert "appendCustomPage" in code
    # Must NOT have the old [0] bug
    assert "appendCustomPage('Meta')[0]" not in code


# ── td_color_pipeline tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_color_pipeline_returns_expected_keys(monkeypatch):
    """Color pipeline returns all expected color management keys."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")
    expected = {
        "defaultParameterColorSpace": "sRGB",
        "workingColorSpace": "linear",
        "editorWindowPixelFormat": "RGBA8Fixed",
        "sdrReferenceWhiteNits": 80.0,
        "hdrReferenceWhiteNits": 200.0,
        "monitorGamma": 2.2,
    }
    client = _ExecClient(expected)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    result = await registry.td_color_pipeline(ctx)
    for key in expected:
        assert key in result
        assert result[key] == expected[key]


@pytest.mark.asyncio
async def test_color_pipeline_exec_off_returns_error(monkeypatch):
    """When exec mode is off, returns an error."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "off")
    client = _ExecClient({})
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    result = await registry.td_color_pipeline(ctx)
    assert "error" in result
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_color_pipeline_uses_exec_endpoint(monkeypatch):
    """Color pipeline sends code via the exec endpoint."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")
    client = _ExecClient({"monitorGamma": 2.2})
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    await registry.td_color_pipeline(ctx)
    exec_calls = [c for c in client.calls if c[0] == "exec"]
    assert len(exec_calls) == 1
    assert "exec_mode" in exec_calls[0][1]
    assert exec_calls[0][1]["exec_mode"] == "standard"


@pytest.mark.asyncio
async def test_color_pipeline_handles_malformed_response(monkeypatch):
    """Color pipeline gracefully handles non-JSON exec response."""
    monkeypatch.setenv("TD_MCP_EXEC_MODE", "standard")

    class _BadClient:
        calls = []

        async def request(self, endpoint, body=None):
            self.calls.append(endpoint)
            if endpoint == "exec":
                return {"result": "not valid json {{"}
            return {}

    client = _BadClient()
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)
    ctx = _make_ctx(client=client)

    result = await registry.td_color_pipeline(ctx)
    # Should return raw content rather than crash
    assert "raw" in result
