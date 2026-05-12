"""Tests for td_tool_batch — dispatch multiple tool calls in one model roundtrip."""

from __future__ import annotations


def test_tool_batch_empty_calls_is_error():
    """An empty calls list must produce a clear error envelope."""
    from td_mcp.registry.tools_batch import handle_tool_batch

    result = handle_tool_batch({"calls": []})
    assert "error" in result
    assert "non-empty" in result["error"].lower()


def test_tool_batch_capped_at_eight():
    """More than 8 sub-calls must be rejected."""
    from td_mcp.registry.tools_batch import handle_tool_batch

    calls = [{"tool": "td_get_info", "args": {}} for _ in range(9)]
    result = handle_tool_batch({"calls": calls})
    assert "error" in result
    assert "capped" in result["error"].lower() or "max" in result["error"].lower()


def test_tool_batch_rejects_nested_batch():
    """A sub-call referencing td_tool_batch must fail (per-sub-call) without aborting siblings."""
    from td_mcp.registry.tools_batch import handle_tool_batch

    result = handle_tool_batch({"calls": [{"tool": "td_tool_batch", "args": {}}]})
    assert result.get("ok") is True
    assert len(result["results"]) == 1
    assert result["results"][0]["ok"] is False
    assert "nested" in result["results"][0]["error"].lower()


def test_tool_batch_sub_call_missing_tool_name():
    """A sub-call without a tool field must fail per-sub-call without aborting siblings."""
    from td_mcp.registry.tools_batch import handle_tool_batch

    result = handle_tool_batch({
        "calls": [
            {"tool": "", "args": {}},
            {"tool": "td_get_info", "args": {}},
        ]
    })
    assert result.get("ok") is True
    assert result["results"][0]["ok"] is False
    assert (
        "missing" in result["results"][0]["error"].lower()
        or "not a string" in result["results"][0]["error"].lower()
    )


def test_tool_batch_dispatch_success():
    """Happy path: one sub-call succeeds, result is properly unwrapped from ContentBlock."""
    import json
    from unittest.mock import AsyncMock, patch

    from mcp.types import TextContent

    from td_mcp.registry.tools_batch import handle_tool_batch

    fake_payload = json.dumps({"success": True, "nodes": [{"name": "n1"}]})
    mock_block = TextContent(type="text", text=fake_payload, annotations=None, meta=None)

    # String-returning tools: FastMCP returns a tuple (list[block], dict)
    with patch(
        "td_mcp.registry.tools_batch.mcp.call_tool",
        new=AsyncMock(return_value=([mock_block], {})),
    ):
        result = handle_tool_batch({
            "calls": [{"tool": "td_get_nodes", "args": {"path": "/root"}}]
        })

    assert result["ok"] is True
    assert result["count"] == 1
    sub = result["results"][0]
    assert sub["tool"] == "td_get_nodes"
    assert sub["ok"] is True, f"expected ok=True, got {sub}"
    assert sub["result"] == {"success": True, "nodes": [{"name": "n1"}]}
    assert sub["error"] is None
    assert isinstance(sub["elapsed_ms"], int)


def test_tool_batch_dispatch_partial_failure():
    """One sub-call raises, sibling still succeeds."""
    import json
    from unittest.mock import patch

    from mcp.types import TextContent

    from td_mcp.registry.tools_batch import handle_tool_batch

    ok_payload = json.dumps({"success": True, "value": 42})
    ok_block = TextContent(type="text", text=ok_payload, annotations=None, meta=None)

    calls_made = []

    async def fake_call(name, args):
        calls_made.append(name)
        if name == "td_will_fail":
            raise RuntimeError("simulated tool crash")
        # String-returning tool path: return tuple
        return ([ok_block], {})

    with patch("td_mcp.registry.tools_batch.mcp.call_tool", new=fake_call):
        result = handle_tool_batch({
            "calls": [
                {"tool": "td_will_fail", "args": {}},
                {"tool": "td_get_nodes", "args": {"path": "/root"}},
            ]
        })

    assert result["ok"] is True
    assert result["count"] == 2
    assert result["results"][0]["ok"] is False
    assert "simulated tool crash" in result["results"][0]["error"]
    assert result["results"][0]["result"] is None
    assert result["results"][1]["ok"] is True
    assert result["results"][1]["result"] == {"success": True, "value": 42}


def test_tool_batch_dispatch_tool_reports_error_with_none_error_field():
    """Regression: a successful tool that explicitly sets error=None must NOT be flagged as failure.

    Affected mainline tools include td_get_focus, td_locations setters, and note removal —
    they all include 'error: None' in their success-shape responses.
    """
    import json
    from unittest.mock import AsyncMock, patch

    from mcp.types import TextContent

    from td_mcp.registry.tools_batch import handle_tool_batch

    # success-shape with explicit error=None (matches tools_state.py:248 etc)
    success_payload = json.dumps({"success": True, "error": None, "navigated_to": "/here"})
    success_block = TextContent(type="text", text=success_payload, annotations=None, meta=None)

    with patch(
        "td_mcp.registry.tools_batch.mcp.call_tool",
        new=AsyncMock(return_value=([success_block], {})),
    ):
        result = handle_tool_batch({
            "calls": [{"tool": "td_get_focus", "args": {}}]
        })

    sub = result["results"][0]
    assert sub["ok"] is True, (
        f"explicit error=None must not be flagged as failure; got {sub}"
    )
    assert sub["result"]["navigated_to"] == "/here"
    assert sub["error"] is None


def test_tool_batch_dispatch_tool_reports_real_error():
    """Real failure: success=False with an error dict (format_tool_error shape)."""
    import json
    from unittest.mock import AsyncMock, patch

    from mcp.types import TextContent

    from td_mcp.registry.tools_batch import handle_tool_batch

    error_payload = json.dumps({
        "success": False,
        "error": {
            "code": "TD_API_ERROR",
            "message": "No node at path /missing",
            "details": {"status_code": 404},
        },
    })
    error_block = TextContent(type="text", text=error_payload, annotations=None, meta=None)

    with patch(
        "td_mcp.registry.tools_batch.mcp.call_tool",
        new=AsyncMock(return_value=([error_block], {})),
    ):
        result = handle_tool_batch({
            "calls": [{"tool": "td_get_nodes", "args": {"path": "/missing"}}]
        })

    sub = result["results"][0]
    assert sub["ok"] is False
    assert sub["result"] is None
    # error should be normalised to the message string (not the dict)
    assert "No node at path" in sub["error"]


def test_tool_batch_forwards_recovery_hints_on_sub_call_failure():
    """Recovery hints from format_tool_error envelopes are surfaced in batch sub-results.

    Regression for cross-task gap discovered in final review of v1.6.11: prior
    behavior dropped recovery_hints when batching a failing sub-call, degrading
    error guidance for the agent.
    """
    import json
    from unittest.mock import AsyncMock, patch

    from mcp.types import TextContent

    from td_mcp.registry.tools_batch import handle_tool_batch

    # Simulate format_tool_error's exact shape — hints nested inside error dict
    error_payload_with_hints = json.dumps({
        "success": False,
        "error": {
            "code": "TD_API_ERROR",
            "message": "No node at path /missing",
            "details": {"status_code": 404},
            "recovery_hints": [
                {
                    "id": "path_not_found",
                    "priority": "critical",
                    "rule": "Call td_get_nodes(path='/parent_path') to list children...",
                    "next_tools": ["td_get_nodes", "td_search_nodes"],
                }
            ],
        },
    })
    error_block = TextContent(type="text", text=error_payload_with_hints, annotations=None, meta=None)

    with patch(
        "td_mcp.registry.tools_batch.mcp.call_tool",
        new=AsyncMock(return_value=([error_block], {})),
    ):
        result = handle_tool_batch({
            "calls": [{"tool": "td_get_nodes", "args": {"path": "/missing"}}]
        })

    sub = result["results"][0]
    assert sub["ok"] is False, f"expected sub-call failure, got {sub}"
    assert "No node at path" in sub["error"]
    assert "recovery_hints" in sub, "recovery_hints must be forwarded into the batch sub-result"
    assert isinstance(sub["recovery_hints"], list)
    assert len(sub["recovery_hints"]) == 1
    assert sub["recovery_hints"][0]["id"] == "path_not_found"
    assert sub["recovery_hints"][0]["next_tools"] == ["td_get_nodes", "td_search_nodes"]


def test_tool_batch_omits_recovery_hints_when_absent():
    """When the sub-call's error has no recovery hints, the field is OMITTED from
    the sub-result (not set to None or []). Mirrors the format_tool_error discipline:
    absent field rather than empty value, so a regression that drops the forward
    fails the regression test cleanly.
    """
    import json
    from unittest.mock import AsyncMock, patch

    from mcp.types import TextContent

    from td_mcp.registry.tools_batch import handle_tool_batch

    # Error without recovery_hints
    error_no_hints = json.dumps({
        "success": False,
        "error": {
            "code": "TD_API_ERROR",
            "message": "some unrecognized failure",
            "details": {},
        },
    })
    block = TextContent(type="text", text=error_no_hints, annotations=None, meta=None)

    with patch(
        "td_mcp.registry.tools_batch.mcp.call_tool",
        new=AsyncMock(return_value=([block], {})),
    ):
        result = handle_tool_batch({
            "calls": [{"tool": "td_get_nodes", "args": {"path": "/missing"}}]
        })

    sub = result["results"][0]
    assert sub["ok"] is False
    assert "some unrecognized failure" in sub["error"]
    # Absent, not None, not []
    assert "recovery_hints" not in sub, (
        f"recovery_hints must be absent when not in source, got: {sub}"
    )
