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
