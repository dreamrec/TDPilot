"""td_tool_batch — dispatch up to 8 tool calls in one model roundtrip.

Backport from deepseek-v4 tdpilot_api_batch.py. Sub-calls execute
sequentially on the cook thread (TD's Python API isn't thread-safe);
what we save is the chain of model→server→model cycles the agent
would otherwise traverse.

Per-call failures DO NOT abort the batch — each result carries its own
ok/error/result/elapsed_ms field. This matches the recipe-replay
semantics for heterogeneous read-only lookups.

Dispatch approach:
    FastMCP-native (option a). ``mcp.call_tool(name, args)`` is a public
    async method that handles Context injection automatically via
    ``self.get_context()``. It returns a ``Sequence[ContentBlock]``; we
    extract the first TextContent item and JSON-parse the payload back
    into a dict. This avoids any wrapper-registry dict and keeps existing
    existing mcp.tool() call sites untouched.

Hard caps:
    8 sub-calls per batch (matches the deepseek-v4 schema)
    Nested td_tool_batch rejected per sub-call (fork-bomb guard)
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Annotated, Any, Sequence

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle: tool_registry.py triggers this module at the end of
# its own import, after ``mcp`` and all helpers are bound as globals.
from td_mcp.tool_registry import mcp

MAX_BATCH_SIZE = 8

# Name of this tool — used to reject nested calls without needing a string literal.
_SELF_NAME = "td_tool_batch"


def _parse_content_blocks(blocks: Sequence[Any]) -> dict[str, Any]:
    """Extract a dict from a FastMCP call_tool result (list of ContentBlock).

    FastMCP serialises tool return values as JSON inside a TextContent block.
    ``convert_result=True`` is set on the internal ToolManager call so the
    top-level return is always a list of ContentBlock objects. We take the
    first text block and JSON-parse it.  If the payload isn't JSON or the
    list is empty, we return the raw text as a fallback dict.
    """
    if not blocks:
        return {"error": "tool returned empty response"}
    item = blocks[0]
    text = getattr(item, "text", None)
    if text is None:
        return {"raw": str(item)}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        # Scalar / list result — wrap in a value key so callers get a dict
        return {"value": parsed}
    except (json.JSONDecodeError, ValueError):
        return {"text": text}


def handle_tool_batch(body: dict) -> dict:
    """Dispatch a list of tool calls SYNCHRONOUSLY and return all results.

    Tests call this directly (without going through the MCP server) to
    verify the dispatch and error-envelope shape.  Production calls come
    via the ``td_tool_batch`` MCP wrapper below.

    The dispatch path for recognised tool names runs
    ``asyncio.run(mcp.call_tool(...))`` so that the async FastMCP internals
    execute correctly even when called from a synchronous context (unit
    tests, or the synchronous helper path in some TD-side scripts).
    When already inside an event loop the caller (``td_tool_batch``) uses
    ``await`` directly; this function is only called synchronously in tests.
    """
    if not isinstance(body, dict):
        return {"error": "tool_batch body must be a dict"}

    calls = body.get("calls")
    if not isinstance(calls, list) or not calls:
        return {"error": "tool_batch requires non-empty 'calls' list"}

    if len(calls) > MAX_BATCH_SIZE:
        return {
            "error": (
                f"tool_batch capped at {MAX_BATCH_SIZE} sub-calls "
                f"(received {len(calls)})"
            )
        }

    results: list[dict] = []
    for i, call in enumerate(calls):
        if not isinstance(call, dict):
            results.append({
                "tool": None,
                "ok": False,
                "result": None,
                "error": f"call[{i}] is not an object",
                "elapsed_ms": 0,
            })
            continue

        tool_name = call.get("tool")
        if not isinstance(tool_name, str) or not tool_name.strip():
            results.append({
                "tool": tool_name,
                "ok": False,
                "result": None,
                "error": f"call[{i}].tool is missing or not a string",
                "elapsed_ms": 0,
            })
            continue

        if tool_name == _SELF_NAME:
            results.append({
                "tool": tool_name,
                "ok": False,
                "result": None,
                "error": "Nested tool_batch is not allowed",
                "elapsed_ms": 0,
            })
            continue

        tool_args = call.get("args") or {}
        if not isinstance(tool_args, dict):
            results.append({
                "tool": tool_name,
                "ok": False,
                "result": None,
                "error": f"call[{i}].args must be an object",
                "elapsed_ms": 0,
            })
            continue

        # ── FastMCP-native dispatch ──────────────────────────────────────────
        # ``mcp.call_tool`` is an async method. In unit tests this function is
        # called synchronously, so we use ``asyncio.run`` to execute the
        # coroutine in a fresh event loop. In production (inside the MCP
        # server's running loop) the caller is the async ``td_tool_batch``
        # wrapper, which calls ``_dispatch_async`` via ``await`` — that path
        # never reaches this synchronous ``asyncio.run`` branch.
        #
        # Context threading: ``mcp.call_tool`` internally calls
        # ``self.get_context()`` which resolves the current request context
        # from FastMCP's internal ContextVar. Tests run outside any request
        # context, so ``get_context()`` returns a bare Context stub — enough
        # for tools that don't actually connect to TD (which is the case for
        # all guard-path tests). Production sub-calls inherit the live context
        # from the enclosing ``td_tool_batch`` request.
        t_start = time.monotonic()
        try:
            blocks = asyncio.run(mcp.call_tool(tool_name, tool_args))
            result = _parse_content_blocks(blocks)
        except Exception as exc:  # noqa: BLE001 — per-call error surface
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            results.append({
                "tool": tool_name,
                "ok": False,
                "result": None,
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_ms": elapsed_ms,
            })
            continue
        elapsed_ms = int((time.monotonic() - t_start) * 1000)

        is_error = isinstance(result, dict) and "error" in result
        results.append({
            "tool": tool_name,
            "ok": not is_error,
            "result": result if not is_error else None,
            "error": (result.get("error") if is_error else None),
            "elapsed_ms": elapsed_ms,
        })

    return {"ok": True, "count": len(results), "results": results}


async def _dispatch_async(calls: list[dict]) -> list[dict]:
    """Async version of the dispatch loop — used by the MCP tool wrapper.

    Runs sub-calls sequentially (TD's Python API isn't thread-safe).
    Each sub-call awaits ``mcp.call_tool`` directly in the running event
    loop, so we avoid nesting ``asyncio.run`` inside an already-running loop.
    """
    results: list[dict] = []
    for i, call in enumerate(calls):
        # Guard checks (identical to handle_tool_batch's sync guards).
        if not isinstance(call, dict):
            results.append({
                "tool": None, "ok": False, "result": None,
                "error": f"call[{i}] is not an object", "elapsed_ms": 0,
            })
            continue

        tool_name = call.get("tool")
        if not isinstance(tool_name, str) or not tool_name.strip():
            results.append({
                "tool": tool_name, "ok": False, "result": None,
                "error": f"call[{i}].tool is missing or not a string", "elapsed_ms": 0,
            })
            continue

        if tool_name == _SELF_NAME:
            results.append({
                "tool": tool_name, "ok": False, "result": None,
                "error": "Nested tool_batch is not allowed", "elapsed_ms": 0,
            })
            continue

        tool_args = call.get("args") or {}
        if not isinstance(tool_args, dict):
            results.append({
                "tool": tool_name, "ok": False, "result": None,
                "error": f"call[{i}].args must be an object", "elapsed_ms": 0,
            })
            continue

        t_start = time.monotonic()
        try:
            blocks = await mcp.call_tool(tool_name, tool_args)
            result = _parse_content_blocks(blocks)
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            results.append({
                "tool": tool_name, "ok": False, "result": None,
                "error": f"{type(exc).__name__}: {exc}", "elapsed_ms": elapsed_ms,
            })
            continue
        elapsed_ms = int((time.monotonic() - t_start) * 1000)

        is_error = isinstance(result, dict) and "error" in result
        results.append({
            "tool": tool_name,
            "ok": not is_error,
            "result": result if not is_error else None,
            "error": (result.get("error") if is_error else None),
            "elapsed_ms": elapsed_ms,
        })

    return results


@mcp.tool()
async def td_tool_batch(
    ctx: Context,
    calls: Annotated[
        list[dict],
        Field(
            description="List of {tool: str, args: dict} dicts. Max 8 sub-calls.",
            max_length=MAX_BATCH_SIZE,
        ),
    ],
) -> dict:
    """Dispatch up to 8 tool calls in one model roundtrip.

    Each sub-call's result is returned in a structured array — per-call
    failures don't abort siblings. Use this for read-only sweeps
    ("inspect 5 things at once") to save model-to-server-to-model latency.

    Hard constraints:
    - Maximum 8 sub-calls per invocation.
    - Nested ``td_tool_batch`` calls are rejected per-sub-call (fork-bomb guard).
    - Sub-calls execute sequentially (TD's Python API is not thread-safe).

    Returns:
        {"ok": True, "count": int, "results": [
            {"tool": str, "ok": bool, "result": dict|None,
             "error": str|None, "elapsed_ms": int},
            ...
        ]}
    """
    if not isinstance(calls, list) or not calls:
        return {"error": "tool_batch requires non-empty 'calls' list"}

    if len(calls) > MAX_BATCH_SIZE:
        return {
            "error": (
                f"tool_batch capped at {MAX_BATCH_SIZE} sub-calls "
                f"(received {len(calls)})"
            )
        }

    results = await _dispatch_async(calls)
    return {"ok": True, "count": len(results), "results": results}
