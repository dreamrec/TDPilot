"""Tests for the error_recovery hint pack and its integration with format_tool_error."""

from __future__ import annotations

import json

from td_mcp.errors import format_tool_error
from td_mcp.hints import ALLOWED_SURFACES, default_registry
from td_mcp.hints.loader import HintMatch
from td_mcp.td_client import TouchDesignerAPIError

# ── Pack loading ──────────────────────────────────────────────────────────


def test_error_recovery_surface_is_allowed():
    """The new error_recovery surface must be registered in ALLOWED_SURFACES."""
    assert "error_recovery" in ALLOWED_SURFACES


def test_error_recovery_pack_loads():
    """The bundled error_recovery.yaml must load without schema errors."""
    reg = default_registry()
    reg.reload()
    pack_names = {p.topic for p in reg.topic_packs}
    assert "error_recovery" in pack_names


def test_error_recovery_pack_has_ten_hints():
    """Pack contains exactly the 10 patterns ported from deepseek-v4."""
    reg = default_registry()
    reg.reload()
    pack = next(p for p in reg.topic_packs if p.topic == "error_recovery")
    assert len(pack.hints) == 10


# ── Matching ──────────────────────────────────────────────────────────────


def test_query_hints_matches_path_not_found():
    """An error message like 'No node at path /foo' must match the path_not_found hint."""
    reg = default_registry()
    reg.reload()
    matches: list[HintMatch] = reg.find(
        surface="error_recovery",
        error_text="No node at path /project1/missing",
    )
    ids = [m.hint.id for m in matches]
    assert "path_not_found" in ids


def test_query_hints_matches_thread_conflict():
    reg = default_registry()
    reg.reload()
    matches: list[HintMatch] = reg.find(
        surface="error_recovery",
        error_text="THREAD CONFLICT: must run on main thread",
    )
    ids = [m.hint.id for m in matches]
    assert "thread_conflict" in ids


def test_query_hints_no_match_returns_empty():
    """An unrecognised error message must return no matches (not all hints)."""
    reg = default_registry()
    reg.reload()
    matches: list[HintMatch] = reg.find(
        surface="error_recovery",
        error_text="some completely unrelated error",
    )
    assert matches == []


# ── format_tool_error integration ─────────────────────────────────────────


def test_format_tool_error_attaches_recovery_hint_on_match():
    """When the error message matches a pattern, the envelope must carry recovery_hints
    at the canonical location: envelope.error.recovery_hints (NOT nested in details)."""
    exc = TouchDesignerAPIError("No node at path /project1/missing", status_code=404)
    envelope_json = format_tool_error(exc)
    envelope = json.loads(envelope_json)
    assert envelope["success"] is False
    # Canonical location only — no fallback. A misplacement bug must fail this test.
    assert "recovery_hints" in envelope["error"], "recovery_hints missing from envelope.error"
    assert "recovery_hints" not in envelope["error"].get("details", {}), (
        "recovery_hints incorrectly nested in details — must be at error.recovery_hints"
    )
    hints = envelope["error"]["recovery_hints"]
    ids = [h["id"] for h in hints]
    assert "path_not_found" in ids


def test_format_tool_error_omits_recovery_hints_on_no_match():
    """No matching pattern -> envelope must NOT carry a recovery_hints field."""
    exc = TouchDesignerAPIError("a totally unique never-seen-before error", status_code=500)
    envelope_json = format_tool_error(exc)
    envelope = json.loads(envelope_json)
    err = envelope["error"]
    assert "recovery_hints" not in err
    assert "recovery_hints" not in err.get("details", {})


def test_format_tool_error_no_hints_on_connection_error():
    """Connection-error envelopes use a fixed message that shouldn't match
    any recovery pattern. If a future hint pack adds a pattern matching
    'connect' or 'TouchDesigner', connection envelopes would carry
    confusing recovery_hints. This test pins the invariant.
    """
    from td_mcp.td_client import TouchDesignerConnectionError

    exc = TouchDesignerConnectionError("connection refused on port 9981")
    envelope_json = format_tool_error(exc)
    envelope = json.loads(envelope_json)
    assert envelope["success"] is False
    # The fixed "Cannot connect to TouchDesigner." message must not match any
    # recovery pattern. If it does in the future, the message or the pack
    # needs adjustment.
    assert "recovery_hints" not in envelope["error"], (
        "Connection-error envelope must not carry recovery hints — the fixed "
        "message text matched a pack pattern (review the patterns)."
    )
