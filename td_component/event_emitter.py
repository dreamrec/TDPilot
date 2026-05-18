"""Buffered event emitter for TD -> MCP WebSocket delivery.

Usage from other DAT callbacks:
    mod('event_emitter').emit('chop_change', {...}, rate_limit=0.016)
    mod('event_emitter').flush_pending()
"""

import json
import time

WS_DAT_CANDIDATES = (
    "/project1/mcp_server/ws_client",
    "ws_client",
)
MAX_BUFFER = 1000
DEFAULT_RATE_LIMIT = 0.016

_BUFFER = []
_LAST_EMIT = {}
_STATS = {
    "sent": 0,
    "buffered": 0,
    "dropped_rate_limited": 0,
    "dropped_buffer_overflow": 0,
}


def _resolve_ws_dat():
    for path in WS_DAT_CANDIDATES:
        ws = op(path)
        if ws is not None:
            return ws
    return None


def _send_payload(payload):
    ws = _resolve_ws_dat()
    if ws is None or not hasattr(ws, "sendText"):
        return False

    try:
        ws.sendText(json.dumps(payload, separators=(",", ":")))
        _STATS["sent"] += 1
        return True
    except Exception:
        return False


def _append_to_buffer(payload):
    if len(_BUFFER) >= MAX_BUFFER:
        # Drop oldest to keep most-recent context for AI subscribers.
        _BUFFER.pop(0)
        _STATS["dropped_buffer_overflow"] += 1
    _BUFFER.append(payload)
    _STATS["buffered"] += 1


def emit(event_type, data, rate_limit=DEFAULT_RATE_LIMIT, dedupe_key=None):
    """Emit an event with optional per-key rate limiting.

    Returns True when accepted for send/buffer, False when dropped by rate limit.
    """
    now = time.time()
    key = dedupe_key
    if key is None:
        path = data.get("path", "") if isinstance(data, dict) else ""
        channel = data.get("channel", "") if isinstance(data, dict) else ""
        name = data.get("name", "") if isinstance(data, dict) else ""
        key = f"{event_type}:{path}:{channel}:{name}"

    last = _LAST_EMIT.get(key, 0.0)
    if rate_limit and (now - last) < float(rate_limit):
        _STATS["dropped_rate_limited"] += 1
        return False

    _LAST_EMIT[key] = now
    payload = {
        "type": event_type,
        "timestamp": now,
        "data": data,
    }

    if not _send_payload(payload):
        _append_to_buffer(payload)
    return True


def emit_event(payload):
    """Emit a preconstructed event payload dict."""
    if not _send_payload(payload):
        _append_to_buffer(payload)


def flush_pending(limit=200):
    """Try sending queued events.

    Returns number of events flushed.
    """
    sent = 0
    while _BUFFER and sent < limit:
        payload = _BUFFER[0]
        if not _send_payload(payload):
            break
        _BUFFER.pop(0)
        sent += 1
    return sent


def stats():
    """Return current emitter stats and queue depth."""
    result = dict(_STATS)
    result["buffer_depth"] = len(_BUFFER)
    result["dedupe_keys"] = len(_LAST_EMIT)
    return result


# ─────────────────────────────────────────────────────────────
# Activity log mirror (v1.6.16)
# ─────────────────────────────────────────────────────────────
# The MCP server keeps a ring buffer of recent tool calls. When TD is
# connected via the ws_callbacks bridge, ws_callbacks dispatches an
# ``activity`` message into this module's ``append_activity_row`` so the
# same data lands in a Table DAT named ``activity_log`` inside the
# ``mcp_server`` COMP. Users can wire that DAT into their visual patch —
# agent activity becomes an addressable data source.

ACTIVITY_DAT_CANDIDATES = (
    "/local/mcp_server/activity_log",
    "/project1/mcp_server/activity_log",
    "activity_log",
)
ACTIVITY_MAX_ROWS = 200
ACTIVITY_HEADER = ("ts", "tool", "args_summary", "duration_ms", "ok")


def _resolve_activity_dat():
    for path in ACTIVITY_DAT_CANDIDATES:
        dat = op(path)
        if dat is not None:
            return dat
    return None


def append_activity_row(row):
    """Append one row to the in-TD activity_log Table DAT.

    ``row`` is a 5-tuple matching ``ACTIVITY_HEADER``. The DAT is treated
    as a rolling window — when row count exceeds ``ACTIVITY_MAX_ROWS``,
    the oldest non-header row is dropped.

    Returns True when the row was written, False when the DAT can't be
    resolved (TD-side wiring missing) — both cases must not raise.
    """
    dat = _resolve_activity_dat()
    if dat is None:
        return False
    try:
        # If empty, seed with the header row.
        if dat.numRows == 0:
            dat.appendRow(list(ACTIVITY_HEADER))
        dat.appendRow([str(cell) for cell in row])
        # Trim oldest rows (keep header at index 0).
        while dat.numRows > ACTIVITY_MAX_ROWS + 1:
            dat.deleteRow(1)
        return True
    except Exception:
        return False
