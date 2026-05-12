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
    ``self.get_context()``. It returns either:
      - ``list[ContentBlock]`` for tools annotated ``-> dict``
      - ``tuple[list[ContentBlock], dict]`` for tools annotated ``-> str``
    Almost every mainline tool returns a string (via ``_as_json_output``
    or ``format_tool_error``), so the tuple path is the hot path.
    ``_parse_content_blocks`` normalises both shapes before parsing.

Hard caps:
    8 sub-calls per batch (matches the deepseek-v4 schema)
    Nested td_tool_batch rejected per sub-call (fork-bomb guard)
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle: tool_registry.py triggers this module at the end of
# its own import, after ``mcp`` and all helpers are bound as globals.
from td_mcp.tool_registry import mcp

MAX_BATCH_SIZE = 8

# Name of this tool — used to reject nested calls without needing a string literal.
_SELF_NAME = "td_tool_batch"


def _parse_content_blocks(blocks: Any) -> dict[str, Any]:
    """Extract a dict from a FastMCP call_tool result.

    FastMCP 1.26.0 returns different types depending on the dispatched
    tool's return-type annotation:
      - ``-> dict`` tools:  ``list[ContentBlock]``
      - ``-> str`` tools:   ``tuple[list[ContentBlock], dict]``

    Almost every mainline tool uses ``_as_json_output`` or
    ``format_tool_error`` (both return str), so the tuple path is the
    hot path. This function normalises both before parsing.

    FastMCP serialises tool return values as JSON inside a TextContent
    block. We take the first text block and JSON-parse it. If the payload
    isn't JSON or the list is empty, we return the raw text as a fallback.
    """
    # Bug 1 fix: unwrap the tuple returned for str-annotated tools.
    if isinstance(blocks, tuple):
        blocks = blocks[0]

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


def _make_error_envelope(
    tool_name: Any,
    result: dict[str, Any],
    elapsed_ms: int,
) -> dict[str, Any]:
    """Build a per-call error envelope, normalising dict errors to strings.

    ``format_tool_error`` produces ``{"success": False, "error": {"code":
    ..., "message": ..., "details": ..., "recovery_hints": [...]}}``. We
    extract the message so that ``error`` in the envelope is always
    ``str | None``, and forward ``recovery_hints`` when present so agents
    using td_tool_batch get the same error guidance as direct calls.

    ``recovery_hints`` is conditionally present — the key is OMITTED when
    the source error dict carries no hints (matches the discipline in
    ``format_tool_error`` where the field is absent on no-match).
    """
    err_val = result.get("error")
    if isinstance(err_val, dict):
        error_text: str | None = err_val.get("message") or str(err_val)
        hints = err_val.get("recovery_hints")
    elif isinstance(err_val, str):
        error_text = err_val
        hints = None
    else:
        error_text = "tool reported failure without an error message"
        hints = None
    envelope: dict[str, Any] = {
        "tool": tool_name,
        "ok": False,
        "result": None,
        "error": error_text,
        "elapsed_ms": elapsed_ms,
    }
    if hints:
        envelope["recovery_hints"] = hints
    return envelope


def _is_tool_error(result: dict[str, Any]) -> bool:
    """Return True if a parsed result dict represents a tool error.

    Two error conventions exist in mainline:
      1. ``format_tool_error`` shape: ``{"success": False, "error": {dict}}``
      2. Bare-string error shape:     ``{"success": False, "error": "msg"}``

    Some tools include ``"error": None`` in their *success* shape:
      - tools_state.py:248 — ``{"success": True, "error": None, ...}``
      - tools_state.py:380 / :395 — same pattern for location ops
      - tools_notes.py:219   — ``{"error": None, ...}`` on removal

    The old ``"error" in result`` check incorrectly flagged those.
    We now treat ``success is False`` OR ``error`` present and non-None
    as a failure, which correctly classifies all four cases.
    """
    return bool(result.get("success") is False or ("error" in result and result["error"] is not None))


def _validate_call(i: int, call: Any) -> tuple[str, dict] | dict:
    """Validate a sub-call. Returns (tool_name, tool_args) on success,
    or a ready-to-append error-envelope dict on failure."""
    if not isinstance(call, dict):
        return {
            "tool": None,
            "ok": False,
            "result": None,
            "error": f"call[{i}] is not an object",
            "elapsed_ms": 0,
        }
    tool_name = call.get("tool")
    if not isinstance(tool_name, str) or not tool_name.strip():
        return {
            "tool": tool_name,
            "ok": False,
            "result": None,
            "error": f"call[{i}].tool is missing or not a string",
            "elapsed_ms": 0,
        }
    if tool_name == _SELF_NAME:
        return {
            "tool": tool_name,
            "ok": False,
            "result": None,
            "error": "Nested tool_batch is not allowed",
            "elapsed_ms": 0,
        }
    tool_args = call.get("args") or {}
    if not isinstance(tool_args, dict):
        return {
            "tool": tool_name,
            "ok": False,
            "result": None,
            "error": f"call[{i}].args must be an object",
            "elapsed_ms": 0,
        }
    return tool_name, tool_args


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
        return {"error": (f"tool_batch capped at {MAX_BATCH_SIZE} sub-calls (received {len(calls)})")}

    results: list[dict] = []
    for i, call in enumerate(calls):
        validated = _validate_call(i, call)
        if isinstance(validated, dict):
            results.append(validated)
            continue

        tool_name, tool_args = validated

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
            raw_result = asyncio.run(mcp.call_tool(tool_name, tool_args))
            # Bug 1 fix: unwrap tuple returned by str-annotated tools.
            result = _parse_content_blocks(raw_result)
        except Exception as exc:  # noqa: BLE001 — per-call error surface
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            results.append(
                {
                    "tool": tool_name,
                    "ok": False,
                    "result": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_ms": elapsed_ms,
                }
            )
            continue
        elapsed_ms = int((time.monotonic() - t_start) * 1000)

        # Bug 2 fix: use success-key + non-None error as failure signal.
        is_error = _is_tool_error(result)
        if is_error:
            results.append(_make_error_envelope(tool_name, result, elapsed_ms))
        else:
            results.append(
                {
                    "tool": tool_name,
                    "ok": True,
                    "result": result,
                    "error": None,
                    "elapsed_ms": elapsed_ms,
                }
            )

    return {"ok": True, "count": len(results), "results": results}


async def _dispatch_async(calls: list[dict]) -> list[dict]:
    """Async version of the dispatch loop — used by the MCP tool wrapper.

    Runs sub-calls sequentially (TD's Python API isn't thread-safe).
    Each sub-call awaits ``mcp.call_tool`` directly in the running event
    loop, so we avoid nesting ``asyncio.run`` inside an already-running loop.
    """
    results: list[dict] = []
    for i, call in enumerate(calls):
        validated = _validate_call(i, call)
        if isinstance(validated, dict):
            results.append(validated)
            continue

        tool_name, tool_args = validated

        t_start = time.monotonic()
        try:
            raw_result = await mcp.call_tool(tool_name, tool_args)
            # Bug 1 fix: unwrap tuple returned by str-annotated tools.
            result = _parse_content_blocks(raw_result)
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            results.append(
                {
                    "tool": tool_name,
                    "ok": False,
                    "result": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_ms": elapsed_ms,
                }
            )
            continue
        elapsed_ms = int((time.monotonic() - t_start) * 1000)

        # Bug 2 fix: use success-key + non-None error as failure signal.
        is_error = _is_tool_error(result)
        if is_error:
            results.append(_make_error_envelope(tool_name, result, elapsed_ms))
        else:
            results.append(
                {
                    "tool": tool_name,
                    "ok": True,
                    "result": result,
                    "error": None,
                    "elapsed_ms": elapsed_ms,
                }
            )

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

        ``error`` is always ``str | None`` — dict errors from
        ``format_tool_error`` are normalised to their ``message`` field.
    """
    if not isinstance(calls, list) or not calls:
        return {"error": "tool_batch requires non-empty 'calls' list"}

    if len(calls) > MAX_BATCH_SIZE:
        return {"error": (f"tool_batch capped at {MAX_BATCH_SIZE} sub-calls (received {len(calls)})")}

    results = await _dispatch_async(calls)
    return {"ok": True, "count": len(results), "results": results}
