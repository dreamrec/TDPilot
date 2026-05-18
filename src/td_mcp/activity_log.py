"""Server-side ring buffer of recent tool-call activity.

Every successful or failed dispatch through :func:`td_mcp.tool_registry._forward`
appends one entry here. The buffer is bounded — older entries are evicted —
and is exposed to MCP clients via the new ``td_get_activity_log`` tool so
Claude can introspect what it's already done across long sessions.

When TD is connected, the same row is also mirrored to a Table DAT named
``activity_log`` inside the ``mcp_server`` COMP. Users can wire that DAT
into their visuals (e.g. ``op('/local/mcp_server/activity_log')`` chained
into a Select DAT → Text TOP) so the AI's actions become a first-class
input to the live patch — agent activity as a visual data stream.

Two separate stores, two separate jobs:

* :mod:`td_mcp.read_journal` — deduped by (tool, args), tracks whether
  repeat reads changed. Optimized for "is this still fresh?"
* :mod:`td_mcp.activity_log` — flat time-ordered. Optimized for "what
  happened recently?"

Thread-safe via :class:`threading.Lock`. FastMCP transports may dispatch
from worker threads.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

MAX_ENTRIES = 200
SUMMARY_MAX_LEN = 120

# Header for the in-TD Table DAT consumer. Column order MUST match
# :func:`format_tsv_row`. Kept as a constant so the build script and the
# DAT consumer can both reference one source of truth.
TSV_HEADER = "ts\ttool\targs_summary\tduration_ms\tok\n"

_lock = threading.Lock()
_entries: deque[dict[str, Any]] = deque(maxlen=MAX_ENTRIES)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _summarize(value: Any) -> str:
    """Compact a value into a single short line for the TD Table DAT.

    Pydantic models, datetimes, custom classes survive via ``default=str``.
    Newlines and tabs are squashed so the value fits in one TSV cell.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str, separators=(",", ":"))
        except Exception:
            text = repr(value)
    text = text.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    if len(text) > SUMMARY_MAX_LEN:
        text = text[: SUMMARY_MAX_LEN - 1] + "…"
    return text


def record(
    *,
    tool_name: str,
    args: Any,
    result: Any,
    duration_ms: float,
    ok: bool,
) -> dict[str, Any]:
    """Append one entry to the ring buffer. Returns the appended entry."""
    entry = {
        "ts": _utc_now_iso(),
        "tool": tool_name,
        "args_summary": _summarize(args),
        "result_summary": _summarize(result),
        "duration_ms": float(duration_ms),
        "ok": bool(ok),
    }
    with _lock:
        _entries.append(entry)
    return entry


def snapshot(
    limit: int | None = None,
    tool_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return entries newest-first.

    * ``limit`` caps the number of returned entries.
    * ``tool_filter`` (exact match) restricts to one tool name.
    """
    with _lock:
        items = [dict(e) for e in _entries]
    items.reverse()  # newest first
    if tool_filter:
        items = [e for e in items if e["tool"] == tool_filter]
    if limit is not None and limit >= 0:
        items = items[:limit]
    return items


def reset() -> None:
    """Clear the log. Test-only — not called from production paths."""
    with _lock:
        _entries.clear()


def format_tsv_row(entry: dict[str, Any]) -> str:
    """Format one entry as a single \\n-terminated TSV row for the TD Table DAT.

    Column order: ``ts, tool, args_summary, duration_ms, ok`` (ok serialized
    as ``1`` / ``0`` for cheap DAT-side filtering). Embedded \\n/\\t/\\r in
    string fields are stripped to keep row boundaries clean.
    """

    def clean(v: Any) -> str:
        s = str(v) if not isinstance(v, str) else v
        return s.replace("\t", " ").replace("\n", " ").replace("\r", " ")

    fields = [
        clean(entry.get("ts", "")),
        clean(entry.get("tool", "")),
        clean(entry.get("args_summary", "")),
        f"{float(entry.get('duration_ms', 0.0)):.2f}",
        "1" if entry.get("ok") else "0",
    ]
    return "\t".join(fields) + "\n"
