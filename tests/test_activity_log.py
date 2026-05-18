"""Tests for the activity_log module — server-side ring buffer of recent
tool calls, surfaced via the new ``td_get_activity_log`` MCP tool and (when
TD is connected) mirrored into an in-TD Table DAT so users can wire agent
activity into their visuals.

The log is **separate** from read_journal:

* ``read_journal`` is keyed by (tool_name, args_fingerprint) and tracks
  whether a *repeat* call returned the same result. Bounded by distinct
  call fingerprints (~500).
* ``activity_log`` is a flat time-ordered ring buffer of *every* call.
  Bounded by total entries (~200). Optimized for "show me the last N
  things the agent did," not for deduplication.
"""

from __future__ import annotations

import pytest

from td_mcp import activity_log


@pytest.fixture(autouse=True)
def _reset_log():
    activity_log.reset()
    yield
    activity_log.reset()


def test_record_appends_entry_with_required_fields():
    activity_log.record(
        tool_name="td_get_nodes",
        args={"path": "/project1"},
        result={"nodes": [{"name": "geo1"}]},
        duration_ms=12.5,
        ok=True,
    )
    entries = activity_log.snapshot()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["tool"] == "td_get_nodes"
    assert entry["ok"] is True
    assert entry["duration_ms"] == 12.5
    assert "ts" in entry
    assert entry["ts"].endswith("Z")  # ISO-8601 UTC


def test_record_truncates_long_args_summary():
    big_args = {"path": "/" + ("x" * 1000)}
    activity_log.record(
        tool_name="t",
        args=big_args,
        result={},
        duration_ms=1.0,
        ok=True,
    )
    entry = activity_log.snapshot()[0]
    # Summary must fit a reasonable width — ~120 chars max so an in-TD
    # Table DAT row stays readable.
    assert len(entry["args_summary"]) <= 120


def test_record_truncates_long_result_summary():
    big_result = {"data": "x" * 5000}
    activity_log.record(
        tool_name="t",
        args={},
        result=big_result,
        duration_ms=1.0,
        ok=True,
    )
    entry = activity_log.snapshot()[0]
    assert len(entry["result_summary"]) <= 120


def test_record_handles_non_dict_args():
    """args may be None or a Pydantic-shaped value."""
    activity_log.record(tool_name="t", args=None, result="ok", duration_ms=0.5, ok=True)
    entry = activity_log.snapshot()[0]
    assert entry["args_summary"] == ""


def test_record_handles_error_path():
    activity_log.record(
        tool_name="td_create_node",
        args={"path": "/bad"},
        result={"error": "not found"},
        duration_ms=2.0,
        ok=False,
    )
    entry = activity_log.snapshot()[0]
    assert entry["ok"] is False


def test_snapshot_returns_recent_first():
    """Most-recent call is element 0."""
    activity_log.record(tool_name="first", args={}, result="r", duration_ms=0.1, ok=True)
    activity_log.record(tool_name="second", args={}, result="r", duration_ms=0.1, ok=True)
    activity_log.record(tool_name="third", args={}, result="r", duration_ms=0.1, ok=True)
    entries = activity_log.snapshot()
    assert [e["tool"] for e in entries] == ["third", "second", "first"]


def test_snapshot_respects_limit():
    for i in range(20):
        activity_log.record(tool_name=f"t{i}", args={}, result="r", duration_ms=0.1, ok=True)
    entries = activity_log.snapshot(limit=5)
    assert len(entries) == 5
    # Most recent first.
    assert entries[0]["tool"] == "t19"


def test_ring_buffer_bounded():
    """Over MAX_ENTRIES, oldest entries are dropped."""
    for i in range(activity_log.MAX_ENTRIES + 50):
        activity_log.record(tool_name=f"t{i}", args={}, result="r", duration_ms=0.1, ok=True)
    entries = activity_log.snapshot(limit=activity_log.MAX_ENTRIES + 100)
    assert len(entries) == activity_log.MAX_ENTRIES


def test_snapshot_returns_independent_copy():
    activity_log.record(tool_name="t", args={}, result="r", duration_ms=0.1, ok=True)
    snap = activity_log.snapshot()
    snap.clear()
    assert len(activity_log.snapshot()) == 1


def test_reset_empties_log():
    activity_log.record(tool_name="t", args={}, result="r", duration_ms=0.1, ok=True)
    activity_log.reset()
    assert activity_log.snapshot() == []


def test_record_filter_by_tool():
    activity_log.record(tool_name="td_get_nodes", args={}, result="r", duration_ms=0.1, ok=True)
    activity_log.record(tool_name="td_create_node", args={}, result="r", duration_ms=0.1, ok=True)
    activity_log.record(tool_name="td_get_nodes", args={}, result="r", duration_ms=0.1, ok=True)
    entries = activity_log.snapshot(tool_filter="td_get_nodes")
    assert len(entries) == 2
    assert all(e["tool"] == "td_get_nodes" for e in entries)


def test_format_tsv_row_produces_tabular_string():
    """The TD-side Table DAT consumes tab-separated rows. The formatter
    must produce a single \\n-terminated TSV row with the required columns."""
    activity_log.record(tool_name="t", args={"a": 1}, result="r", duration_ms=0.5, ok=True)
    entry = activity_log.snapshot()[0]
    row = activity_log.format_tsv_row(entry)
    assert row.endswith("\n")
    # 5 columns: ts, tool, args_summary, duration_ms, ok
    fields = row.rstrip("\n").split("\t")
    assert len(fields) == 5
    assert fields[1] == "t"
    assert fields[4] in ("1", "0")  # ok as 0/1 for DAT consumers


def test_format_tsv_row_strips_embedded_newlines():
    """A multi-line args_summary must not break TSV row boundaries."""
    activity_log.record(tool_name="t", args={"v": "a\nb\nc"}, result="r", duration_ms=0.1, ok=True)
    entry = activity_log.snapshot()[0]
    row = activity_log.format_tsv_row(entry)
    # Exactly one trailing newline; no embedded ones.
    assert row.count("\n") == 1


def test_tsv_header_row_constant():
    """The header is fixed and matches the column order in format_tsv_row."""
    header = activity_log.TSV_HEADER
    assert header.endswith("\n")
    fields = header.rstrip("\n").split("\t")
    assert fields == ["ts", "tool", "args_summary", "duration_ms", "ok"]
