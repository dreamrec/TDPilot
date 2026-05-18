"""Session-scoped tool-call journal — passive observability for read tools.

Every tool call routed through :func:`td_mcp.tool_registry._forward` ends up
here. The journal records a fingerprint of the arguments and a hash of the
result. On the next call with the same arguments, the journal returns a hint
saying whether the result is unchanged since last time.

The journal is **not** a cache. Every call still executes against TD. The
hint is purely advisory — Claude can decide whether to re-fetch, but the
underlying call happens regardless. This avoids the worst failure mode of a
transparent cache (silently serving stale data after the scene mutates).

Why a journal beats a cache here:

* Live TD scenes mutate constantly — node creations, parameter writes,
  cooking changes. A cache that doesn't invalidate on every possible
  mutation lies; a cache that invalidates on every mutation is no cache.
* Read tools are cheap. The expensive thing across an MCP session is the
  token cost of re-asking. The journal makes that visible to the model.
* The hint reasonably composes across long sessions: "you've called
  `td_get_nodes('/project1')` 7 times today and the result hasn't moved"
  is information Claude can act on.

Storage shape::

    _entries: dict[(tool_name, args_fingerprint)] -> {
        "tool": str,
        "args_fingerprint": str,
        "first_seen_at": iso8601-UTC,
        "last_seen_at": iso8601-UTC,
        "call_count": int,
        "last_result_hash": str,
    }

Module-level state is thread-safe via :class:`threading.Lock`. MCP tool
handlers may be invoked from worker threads under the FastMCP transport.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any

MAX_ENTRIES = 500

_lock = threading.Lock()
_entries: dict[tuple[str, str], dict[str, Any]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(value: Any) -> str:
    """Stable JSON serialization for fingerprinting.

    Sorted keys + default=str so objects that aren't JSON-native (Pydantic
    models, datetimes, custom classes) still produce a fingerprint without
    raising.
    """
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    canonical = _canonical_json(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _evict_oldest_if_needed() -> None:
    """Trim entries down to MAX_ENTRIES by removing oldest last_seen_at."""
    if len(_entries) <= MAX_ENTRIES:
        return
    # Sort by last_seen_at ascending; drop oldest until at limit.
    ordered = sorted(_entries.items(), key=lambda kv: kv[1]["last_seen_at"])
    excess = len(_entries) - MAX_ENTRIES
    for key, _ in ordered[:excess]:
        _entries.pop(key, None)


def record_call(tool_name: str, args: Any, result: Any) -> dict[str, Any]:
    """Record one tool call and return the hint dict to attach to its response.

    The hint shape is::

        {
            "call_count": int,
            "first_seen_at": iso8601,
            "last_seen_at": iso8601,
            "result_unchanged": True | False | None,
        }

    ``result_unchanged`` is ``None`` on the first call (no prior result to
    compare). ``True`` when the new result's hash equals the previous one,
    ``False`` otherwise.
    """
    args_fp = _fingerprint(args if args is not None else {})
    result_hash = _fingerprint(result)
    now = _utc_now_iso()
    key = (tool_name, args_fp)

    with _lock:
        existing = _entries.get(key)
        if existing is None:
            entry = {
                "tool": tool_name,
                "args_fingerprint": args_fp,
                "first_seen_at": now,
                "last_seen_at": now,
                "call_count": 1,
                "last_result_hash": result_hash,
            }
            _entries[key] = entry
            _evict_oldest_if_needed()
            unchanged: bool | None = None
        else:
            unchanged = existing["last_result_hash"] == result_hash
            existing["call_count"] += 1
            existing["last_seen_at"] = now
            existing["last_result_hash"] = result_hash
            entry = existing

        return {
            "call_count": entry["call_count"],
            "first_seen_at": entry["first_seen_at"],
            "last_seen_at": entry["last_seen_at"],
            "result_unchanged": unchanged,
        }


def snapshot() -> list[dict[str, Any]]:
    """Return a list copy of all journal entries (recent first).

    Entries are public-shape — no internal hashes leak except the args
    fingerprint, which is intentional so callers can correlate.
    """
    with _lock:
        items = [dict(v) for v in _entries.values()]
    items.sort(key=lambda e: e["last_seen_at"], reverse=True)
    return items


def reset() -> None:
    """Clear the journal. Test-only — not called from production paths."""
    with _lock:
        _entries.clear()


def attach_hint(response: Any, hint: dict[str, Any]) -> Any:
    """Splice ``_read_journal: hint`` into a tool response.

    Polymorphic, matching :func:`_attach_hints` in tool_registry:

    * If ``response`` is a JSON string that parses to a dict, return a new
      JSON string with the hint merged.
    * If ``response`` is a dict, return a new dict with the hint merged.
    * Otherwise (non-JSON string, list-shaped JSON, etc.), return the
      response unchanged. A failure to attach must never break a tool call.
    """
    if isinstance(response, dict):
        merged = dict(response)
        merged["_read_journal"] = hint
        return merged

    if isinstance(response, str):
        try:
            parsed = json.loads(response)
        except Exception:
            return response
        if not isinstance(parsed, dict):
            return response
        parsed["_read_journal"] = hint
        return json.dumps(parsed, indent=2, default=str)

    return response
