"""Behavioural tests for the 5 Phase 3 MCP tools.

Uses the same MCP test harness as tests/test_tools_contract.py and
friends. Verifies envelope shapes + interaction with patch.* internals.
"""

from __future__ import annotations

import asyncio

import pytest

import td_mcp.tool_registry as _registry
from td_mcp.registry import tools_patch
from td_mcp.tool_registry import mcp


def _find_tool(name: str):
    tools = asyncio.run(mcp.list_tools())
    for t in tools:
        if t.name == name:
            return t
    raise AssertionError(f"tool not registered: {name}")


def test_td_patch_plan_registered():
    t = _find_tool("td_patch_plan")
    # Schema should be flat (Bug-A discipline)
    props = t.inputSchema.get("properties", {})
    assert "target_root" in props
    assert list(props.keys()) != ["params"]


def test_td_patch_preview_registered():
    t = _find_tool("td_patch_preview")
    assert "plan" in t.inputSchema.get("properties", {})


def test_td_patch_apply_registered():
    t = _find_tool("td_patch_apply")
    props = t.inputSchema.get("properties", {})
    assert "plan" in props
    assert "auto_validate" in props
    assert "transaction_options" in props
    assert "param_semantics_policy" in props


def test_td_patch_validate_registered():
    t = _find_tool("td_patch_validate")
    props = t.inputSchema.get("properties", {})
    assert "target_root" in props
    assert "capture_frames" in props
    # Flat schema — Bug A discipline
    assert list(props.keys()) != ["params"]


def test_td_patch_variations_registered():
    t = _find_tool("td_patch_variations")
    props = t.inputSchema.get("properties", {})
    assert "plan" in props
    assert "n" in props
    assert "strategies" in props
    # Flat schema
    assert list(props.keys()) != ["params"]


# ---------------------------------------------------------------------------
# Behavioural tests (one per tool)
# ---------------------------------------------------------------------------


def _patch_services(monkeypatch, td_client):
    """Monkeypatch _get_client and _get_technique_store on the registry module
    so tools_patch can call them without a real TDClient or TechniqueStore."""
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: td_client)
    monkeypatch.setattr(_registry, "_get_technique_store", lambda _ctx: None)


@pytest.mark.asyncio
async def test_td_patch_plan_requires_one_input(mcp_ctx, td_client, monkeypatch):
    _patch_services(monkeypatch, td_client)
    result = await tools_patch.td_patch_plan(mcp_ctx, target_root="/p")
    assert result["success"] is False
    assert "error" in result
    assert "requires one of" in result["error"].lower() or "one of" in result["error"].lower()


@pytest.mark.asyncio
async def test_td_patch_preview_behavioural(mcp_ctx, td_client, monkeypatch):
    _patch_services(monkeypatch, td_client)
    td_client.responses = {"nodes": {"nodes": []}}
    # First build a plan via td_patch_plan
    plan_result = await tools_patch.td_patch_plan(mcp_ctx, target_root="/p", intent="feedback trail")
    assert plan_result["success"] is True
    plan_dict = plan_result["plan"]

    result = await tools_patch.td_patch_preview(mcp_ctx, plan=plan_dict)
    assert result["success"] is True
    assert "preview" in result
    assert result["preview"]["plan_id"] == plan_dict["id"]
    assert "summary" in result["preview"]
    assert "live_risk_flags" in result["preview"]


@pytest.mark.asyncio
async def test_td_patch_apply_happy_path(mcp_ctx, td_client, monkeypatch):
    _patch_services(monkeypatch, td_client)
    td_client.responses = {
        "node/create": {"path": "/p/n1", "name": "n1"},
        "node/errors": {"issues": []},
        "cooking_info": {"total_cook_ms": 0.5, "stuck": []},
        "project/lifecycle": {"ok": True},
    }
    # Build a plan via td_patch_plan with explicit operations
    plan_result = await tools_patch.td_patch_plan(
        mcp_ctx,
        target_root="/p",
        operations=[{"kind": "create_node", "target": "/p", "args": {"op_type": "noise", "name": "n1"}}],
    )
    plan_dict = plan_result["plan"]

    result = await tools_patch.td_patch_apply(mcp_ctx, plan=plan_dict, auto_validate=True)
    assert result["success"] is True
    assert result["result"]["status"] == "clean"
    assert "/p/n1" in result["result"]["created_paths"]


@pytest.mark.asyncio
async def test_td_patch_apply_transaction_options_dry_run(mcp_ctx, td_client, monkeypatch):
    _patch_services(monkeypatch, td_client)
    td_client.responses = {"nodes": {"nodes": []}}
    plan_result = await tools_patch.td_patch_plan(
        mcp_ctx,
        target_root="/p",
        operations=[{"kind": "create_node", "target": "/p", "args": {"op_type": "noise", "name": "n1"}}],
    )
    plan_dict = plan_result["plan"]

    result = await tools_patch.td_patch_apply(
        mcp_ctx,
        plan=plan_dict,
        transaction_options={"dry_run": True, "snapshot_before": False},
    )

    assert result["success"] is True
    assert result["result"]["status"] == "dry_run"
    assert not any(call[0] == "node/create" for call in td_client.calls)


@pytest.mark.asyncio
async def test_td_patch_apply_can_block_invalid_param_semantics_before_legacy_apply(
    mcp_ctx, td_client, monkeypatch
):
    _patch_services(monkeypatch, td_client)
    plan_result = await tools_patch.td_patch_plan(
        mcp_ctx,
        target_root="/p",
        operations=[
            {"kind": "create_node", "target": "/p", "args": {"op_type": "feedbackTOP", "name": "fb"}},
            {"kind": "set_params", "target": "/p/fb", "args": {"params": {"reset": "yes please"}}},
        ],
    )
    plan_dict = plan_result["plan"]

    result = await tools_patch.td_patch_apply(
        mcp_ctx,
        plan=plan_dict,
        param_semantics_policy="block",
    )

    assert result["success"] is False
    assert result["blocked"] is True
    assert result["param_semantics_status"] == "blocked"
    assert {item["code"] for item in result["param_semantics_warnings"]} == {"invalid_bool_param"}
    assert not any(call[0] in {"node/create", "node/params/set"} for call in td_client.calls)


@pytest.mark.asyncio
async def test_td_patch_apply_uses_shared_direct_param_preflight_for_legacy_apply(
    mcp_ctx, td_client, monkeypatch
):
    _patch_services(monkeypatch, td_client)
    td_client.responses = {
        "node/create": {"path": "/p/level", "name": "level"},
        "node/params/set": {"success": True, "results": {}},
        "node/errors": {"issues": []},
        "cooking_info": {"total_cook_ms": 0.5, "stuck": []},
        "project/lifecycle": {"ok": True},
    }
    calls = []

    def fake_preflight(**kwargs):
        calls.append(kwargs)
        return _registry.DirectParamPreflightResult(
            adjusted_params={"opacity": 0.75},
            safety_warnings=["opacity clamped"],
            param_semantics_warnings=[],
            blocked=False,
        )

    monkeypatch.setattr(_registry, "_preflight_direct_param_write", fake_preflight)
    plan_result = await tools_patch.td_patch_plan(
        mcp_ctx,
        target_root="/p",
        operations=[
            {"kind": "create_node", "target": "/p", "args": {"op_type": "levelTOP", "name": "level"}},
            {"kind": "set_params", "target": "/p/level", "args": {"params": {"opacity": 2.0}}},
        ],
    )

    result = await tools_patch.td_patch_apply(mcp_ctx, plan=plan_result["plan"])

    assert result["success"] is True
    assert calls
    assert calls[0]["path"] == "/p/level"
    assert calls[0]["op_type"] == "levelTOP"
    assert any(
        endpoint == "node/params/set" and body["params"] == {"opacity": 0.75}
        for endpoint, body in td_client.calls
    )


@pytest.mark.asyncio
async def test_td_patch_apply_block_mode_reads_existing_node_type_before_set_params(
    mcp_ctx, td_client, monkeypatch
):
    _patch_services(monkeypatch, td_client)

    def handler(endpoint, body):
        if endpoint == "node/detail":
            return {"path": body["path"], "type": "feedback", "family": "TOP"}
        if endpoint == "project/lifecycle":
            return {"ok": True}
        if endpoint == "node/params/set":
            raise AssertionError("block policy should not mutate existing node params")
        raise AssertionError(f"unexpected endpoint {endpoint}")

    td_client.handler = handler
    plan_result = await tools_patch.td_patch_plan(
        mcp_ctx,
        target_root="/p",
        operations=[
            {
                "kind": "set_params",
                "target": "/p/existing_feedback",
                "args": {"params": {"reset": "yes please"}},
            },
        ],
    )

    result = await tools_patch.td_patch_apply(
        mcp_ctx,
        plan=plan_result["plan"],
        param_semantics_policy="block",
        auto_validate=False,
    )

    assert result["success"] is False
    assert result["blocked"] is True
    assert result["param_semantics_status"] == "blocked"
    assert {item["code"] for item in result["param_semantics_warnings"]} == {"invalid_bool_param"}
    assert td_client.calls == [("node/detail", {"path": "/p/existing_feedback"})]


@pytest.mark.asyncio
async def test_td_patch_validate_clean(mcp_ctx, td_client, monkeypatch):
    _patch_services(monkeypatch, td_client)
    td_client.responses = {
        "node/errors": {"issues": []},
        "cooking_info": {"total_cook_ms": 0.3, "stuck": []},
    }
    result = await tools_patch.td_patch_validate(mcp_ctx, target_root="/project1")
    assert result["success"] is True
    assert result["report"]["ok"] is True
    assert result["report"]["target_root"] == "/project1"


@pytest.mark.asyncio
async def test_td_patch_variations_default_strategy(mcp_ctx, td_client, monkeypatch):
    _patch_services(monkeypatch, td_client)
    plan_result = await tools_patch.td_patch_plan(
        mcp_ctx,
        target_root="/p",
        operations=[{"kind": "set_params", "target": "/p/n1", "args": {"params": {"freq": 1.0}}}],
    )
    plan_dict = plan_result["plan"]
    result = await tools_patch.td_patch_variations(mcp_ctx, plan=plan_dict, n=3, seed=42)
    assert result["success"] is True
    assert len(result["variants"]) > 0
    assert result["skipped_strategies"] == []


@pytest.mark.asyncio
async def test_td_patch_apply_returns_dict_envelope_on_td_connection_error(mcp_ctx, td_client, monkeypatch):
    """Structured-output tools (-> dict) must return a DICT error envelope, not a
    JSON string — a string raises a FastMCP ValidationError and destroys the
    troubleshooting payload exactly on the TD-not-running path. Regression for the
    format_tool_error (str) -> format_tool_error_dict swap."""
    from td_mcp.td_client import TouchDesignerConnectionError

    _patch_services(monkeypatch, td_client)
    plan_result = await tools_patch.td_patch_plan(
        mcp_ctx,
        target_root="/p",
        operations=[{"kind": "create_node", "target": "/p", "args": {"op_type": "noise", "name": "n1"}}],
    )
    plan_dict = plan_result["plan"]

    def _raise_conn(_endpoint, _body):
        raise TouchDesignerConnectionError("TD not running")

    td_client.handler = _raise_conn

    result = await tools_patch.td_patch_apply(mcp_ctx, plan=plan_dict, auto_validate=True)
    assert isinstance(result, dict)  # NOT a str — a str breaks structured_output conversion
    assert result["success"] is False
    assert result["error"]["code"] == "TD_CONNECTION_ERROR"
    assert "troubleshooting" in result["error"]["details"]
