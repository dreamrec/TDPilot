"""Tests for the read_journal module — passive observability layer that
annotates tool responses with "you've called this before, result unchanged"
hints so Claude can decide whether to re-fetch.

The journal is NOT a cache. It records call fingerprints and result hashes,
but every call still executes against TD. It exists to let the model build
a session-level mental model of "what have I asked about, and has it moved?"
which is otherwise invisible across MCP request boundaries.
"""

from __future__ import annotations

import time

import pytest

from td_mcp import read_journal


@pytest.fixture(autouse=True)
def _reset_journal():
    """Each test gets a fresh journal."""
    read_journal.reset()
    yield
    read_journal.reset()


def test_first_call_records_count_one():
    hint = read_journal.record_call("td_get_nodes", {"path": "/project1"}, {"nodes": [{"name": "geo1"}]})
    assert hint["call_count"] == 1
    assert hint["result_unchanged"] is None  # no prior to compare
    assert isinstance(hint["first_seen_at"], str)
    assert hint["first_seen_at"].endswith("Z")  # ISO-8601 UTC


def test_repeat_same_args_same_result_marks_unchanged():
    args = {"path": "/project1"}
    result = {"nodes": [{"name": "geo1"}]}
    read_journal.record_call("td_get_nodes", args, result)
    hint = read_journal.record_call("td_get_nodes", args, result)
    assert hint["call_count"] == 2
    assert hint["result_unchanged"] is True


def test_repeat_same_args_different_result_marks_changed():
    args = {"path": "/project1"}
    read_journal.record_call("td_get_nodes", args, {"nodes": [{"name": "geo1"}]})
    hint = read_journal.record_call("td_get_nodes", args, {"nodes": [{"name": "geo1"}, {"name": "geo2"}]})
    assert hint["call_count"] == 2
    assert hint["result_unchanged"] is False


def test_args_dict_order_insensitive():
    """Fingerprint must canonicalize key order — {a:1,b:2} == {b:2,a:1}."""
    read_journal.record_call("t", {"a": 1, "b": 2}, "r")
    hint = read_journal.record_call("t", {"b": 2, "a": 1}, "r")
    assert hint["call_count"] == 2
    assert hint["result_unchanged"] is True


def test_different_args_separate_entries():
    read_journal.record_call("td_get_nodes", {"path": "/a"}, "r1")
    hint = read_journal.record_call("td_get_nodes", {"path": "/b"}, "r2")
    assert hint["call_count"] == 1
    assert hint["result_unchanged"] is None


def test_different_tools_separate_entries():
    read_journal.record_call("td_get_nodes", {"path": "/a"}, "r")
    hint = read_journal.record_call("td_get_params", {"path": "/a"}, "r")
    assert hint["call_count"] == 1


def test_none_args_treated_as_empty_dict():
    """A tool with no args (None) should still be journalable."""
    read_journal.record_call("td_get_info", None, {"build": "2025.32460"})
    hint = read_journal.record_call("td_get_info", None, {"build": "2025.32460"})
    assert hint["call_count"] == 2
    assert hint["result_unchanged"] is True


def test_non_json_serializable_result_does_not_crash():
    """Result objects that contain non-JSON types (e.g. bytes, custom classes)
    must not raise — we coerce via default=str."""

    class Custom:
        def __repr__(self) -> str:
            return "Custom()"

    # Should not raise.
    hint = read_journal.record_call("t", {}, {"obj": Custom()})
    assert hint["call_count"] == 1


def test_journal_bounded_by_max_entries():
    """When over MAX_ENTRIES, oldest by last_seen_at is evicted."""
    # Fill past the limit
    for i in range(read_journal.MAX_ENTRIES + 50):
        read_journal.record_call("t", {"i": i}, "r")
    entries = read_journal.snapshot()
    assert len(entries) == read_journal.MAX_ENTRIES


def test_snapshot_returns_independent_copy():
    """Mutating the snapshot must not affect live journal state."""
    read_journal.record_call("t", {"a": 1}, "r")
    snap = read_journal.snapshot()
    snap.clear()
    snap2 = read_journal.snapshot()
    assert len(snap2) == 1


def test_reset_empties_journal():
    read_journal.record_call("t", {"a": 1}, "r")
    read_journal.reset()
    assert read_journal.snapshot() == []


def test_first_seen_at_preserved_across_calls():
    read_journal.record_call("t", {"a": 1}, "r")
    time.sleep(0.001)
    hint = read_journal.record_call("t", {"a": 1}, "r")
    assert hint["first_seen_at"] <= hint["last_seen_at"]


def test_hint_shape_contract():
    """Hint dict has exactly the documented keys."""
    hint = read_journal.record_call("t", {}, "r")
    assert set(hint.keys()) == {"call_count", "first_seen_at", "last_seen_at", "result_unchanged"}


def test_snapshot_entries_have_tool_and_count():
    """Entries returned by snapshot expose tool name + count for introspection."""
    read_journal.record_call("td_get_nodes", {"path": "/a"}, "r")
    read_journal.record_call("td_get_nodes", {"path": "/a"}, "r")
    snap = read_journal.snapshot()
    assert len(snap) == 1
    entry = snap[0]
    assert entry["tool"] == "td_get_nodes"
    assert entry["call_count"] == 2
    assert "first_seen_at" in entry
    assert "last_seen_at" in entry


def test_attach_hint_to_json_string():
    """attach_hint() splices _read_journal into a JSON-string response."""
    import json
    response = json.dumps({"nodes": []})
    hint = read_journal.record_call("td_get_nodes", {}, {"nodes": []})
    new_response = read_journal.attach_hint(response, hint)
    parsed = json.loads(new_response)
    assert parsed["_read_journal"]["call_count"] == 1


def test_attach_hint_to_dict():
    """attach_hint() splices into a dict response."""
    response = {"nodes": []}
    hint = read_journal.record_call("td_get_nodes", {}, {"nodes": []})
    new_response = read_journal.attach_hint(response, hint)
    assert new_response["_read_journal"]["call_count"] == 1


def test_attach_hint_to_non_dict_string_is_passthrough():
    """If JSON parses to a list (or other non-dict), attach_hint must not crash."""
    import json
    response = json.dumps([1, 2, 3])
    hint = read_journal.record_call("t", {}, [1, 2, 3])
    out = read_journal.attach_hint(response, hint)
    # Should return original string unchanged.
    assert json.loads(out) == [1, 2, 3]


def test_attach_hint_to_non_json_string_is_passthrough():
    """Non-JSON string responses (e.g. markdown) are returned unchanged."""
    response = "## Nodes\n- geo1"
    hint = read_journal.record_call("t", {}, response)
    assert read_journal.attach_hint(response, hint) == response
