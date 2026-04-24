"""Tests for the _with_undo_block async helper in tool_registry."""

import asyncio
import pathlib
import re
import sys
import types
from unittest.mock import AsyncMock, call

import pytest


def _load_undo_helper():
    """Load _with_undo_block from tool_registry without triggering MCP decorators."""
    src_path = pathlib.Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "tool_registry.py"
    source = src_path.read_text()
    # Cut before the first @mcp. decorator to avoid server registration
    cut = source.find("\n@mcp.")
    if cut != -1:
        source = source[:cut]
    mod = types.ModuleType("_undo_helpers")
    mod.__dict__["re"] = re
    mod.__dict__["os"] = __import__("os")
    mod.__dict__["sys"] = sys
    mod.__dict__["__name__"] = "_undo_helpers"
    mod.__dict__["__file__"] = str(src_path)
    mod.__dict__["Optional"] = None
    mod.__dict__["Dict"] = None
    mod.__dict__["List"] = None
    mod.__dict__["Any"] = None
    mod.__dict__["Tuple"] = None
    code_obj = compile(source, str(src_path), "exec")
    builtins = __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__
    builtins["eval"](code_obj, mod.__dict__)
    return mod


_helpers = _load_undo_helper()
_with_undo_block = _helpers._with_undo_block


def _run(coro):
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


def test_with_undo_block_calls_lifecycle():
    """start_undo_block and end_undo_block must both be called in order."""
    td_client = AsyncMock()
    td_client.request = AsyncMock(return_value={"ok": True})

    async def my_op():
        return "result"

    result = _run(_with_undo_block(td_client, "my_label", my_op))

    assert result == "result"
    assert td_client.request.call_count == 2
    calls = td_client.request.call_args_list
    assert calls[0] == call("project/lifecycle", {"action": "start_undo_block", "name": "my_label"})
    assert calls[1] == call("project/lifecycle", {"action": "end_undo_block"})


def test_with_undo_block_calls_end_on_error():
    """end_undo_block must be called even when the wrapped function raises."""
    td_client = AsyncMock()
    td_client.request = AsyncMock(return_value={"ok": True})

    async def failing_op():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _run(_with_undo_block(td_client, "err_label", failing_op))

    # start + end both called despite the exception
    assert td_client.request.call_count == 2
    calls = td_client.request.call_args_list
    assert calls[0] == call("project/lifecycle", {"action": "start_undo_block", "name": "err_label"})
    assert calls[1] == call("project/lifecycle", {"action": "end_undo_block"})
