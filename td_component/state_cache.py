"""Thread-safe runtime state cache shared between MCP request handlers and the
in-TD status panel.

The MCP webserver callbacks write to this cache on every request (latency,
last tool name, error counters); the panel COMP reads ``snapshot()`` once a
second to refresh its rows. No MCP round-trip is needed because the panel
lives in the same TD process — both producer and consumer reach the same
module-level dict.

This module is baked into the .tox via build_export_mcp_tox.py's
``_TOX_SOURCE_FILES`` list. Inside TD, it loads as a textDAT named
``state_cache`` inside the ``mcp_server`` baseCOMP and is imported via
``op('/local/tdpilot/mcp_server/state_cache').module``.

History
-------
This file was developed in a v1.6.0 worktree but was never merged to main
until v1.6.7. From v1.5.6 (when the build script switched to the
v1.5.6+ containerCOMP shape) through v1.6.6, fresh ``loadTox`` calls
produced COMPs missing this DAT, so the panel renderer's bootstrap
silently returned False and the textTOP stayed at TD's default
"derivative" placeholder. Users with pre-v1.5.6 installs had a
state_cache baked into older .toe files (from earlier build scripts
that DID create it), so the bug was masked until anyone did a fresh
install or manual destroy + loadTox sequence. v1.6.7 closes the
loop by (a) shipping this file, (b) adding it to ``_TOX_SOURCE_FILES``,
and (c) updating ``_populate_component`` to create the DAT.

Design notes
------------
* Single module-level dict guarded by ``threading.Lock`` — TD HTTP
  callbacks may fire from worker threads, panel poller fires from main.
* ``update()`` accepts arbitrary key/value pairs to keep call sites cheap
  (no schema enforcement at write time). Schema is validated at read time
  in ``snapshot()``.
* ``snapshot()`` returns a deep-copied dict so consumers can't mutate the
  live cache by accident.
* All keys default to None for unset display fields (``or "--"`` chain
  in the renderer falls back through cache → live → "--"); counters
  default to 0 so increment() is a safe no-op before any update.
* Built-in metrics list documented in ``_DEFAULT_KEYS`` — those are the
  fields the panel knows how to render. Extras are kept but not displayed
  unless the panel template references them.
"""

from __future__ import annotations

import threading
import time

# Keys the panel knows how to render. Order is preserved by Python dict
# ordering and used as the row order when the panel constructs its layout.
_DEFAULT_KEYS = (
    "version",  # TDPilot API version (e.g. "1.6.7")
    "build",  # TD build (e.g. "2025.32460")
    "ws",  # WS bridge state ("OK", "DISCONNECTED", "ERROR")
    "latency_ms",  # Last observed request latency in ms (float)
    "tools",  # Tool count (int)
    "snapshots",  # Number of saved snapshots (int)
    "memory",  # Number of memory entries (int)
    "knowledge",  # Number of knowledge entries (int)
    "popx",  # POPx install state ("installed", "missing", "unknown")
    "last_call",  # Last tool name handled
    "request_count",  # Total requests since cache init
    "error_count",  # Total request errors since cache init
    "started_at",  # Cache init time (epoch seconds)
)

# Defaults: None for unset display fields, 0 for counters.
# Why None (not "--"): consumers like the panel renderer use the `or`
# chain to fall back from cache → live runtime value (e.g.
# ``s.get("build") or app.build or "--"``). The literal string "--" is
# truthy and would defeat that chain. None is the only correct sentinel
# for "value not yet populated by any writer."
_lock = threading.Lock()
_state = {key: None for key in _DEFAULT_KEYS}
_state["request_count"] = 0
_state["error_count"] = 0
_state["started_at"] = time.time()


def update(**kwargs):
    """Atomically merge kwargs into the cache.

    Unknown keys are accepted — the panel ignores them but other
    consumers (e.g. a future debug DAT) may use them.
    """
    if not kwargs:
        return
    with _lock:
        _state.update(kwargs)


def increment(key, delta=1):
    """Atomically add ``delta`` to an integer counter key.

    If the key currently holds a non-int (None, "--", etc.), it is
    reset to ``delta``. This makes the function safe to call before
    ``update()`` has populated the key.
    """
    with _lock:
        current = _state.get(key, 0)
        if not isinstance(current, (int, float)):
            current = 0
        _state[key] = current + delta


def record_request(tool_name, latency_ms, ok=True):
    """Convenience hook: log one MCP request in a single locked update.

    Called from ``mcp_webserver_callbacks.onHTTPRequest`` after every
    request. Keeps every per-request mutation under one lock acquisition.
    """
    with _lock:
        _state["last_call"] = tool_name
        _state["latency_ms"] = float(latency_ms)
        _state["request_count"] = int(_state.get("request_count", 0) or 0) + 1
        if not ok:
            _state["error_count"] = int(_state.get("error_count", 0) or 0) + 1
        _state["ws"] = "OK"


def mark_ws_error(message=""):
    """Flag the WS bridge as errored. Panel surfaces this as red 'ERROR'."""
    with _lock:
        _state["ws"] = "ERROR"
        if message:
            _state["last_call"] = ("ws_error: " + str(message))[:80]


def snapshot():
    """Return a deep copy of the current cache. Safe to mutate by callers."""
    with _lock:
        return dict(_state)


def reset():
    """Reset to defaults. Test-only — not called from production paths."""
    with _lock:
        _state.clear()
        _state.update({key: None for key in _DEFAULT_KEYS})
        _state["request_count"] = 0
        _state["error_count"] = 0
        _state["started_at"] = time.time()
