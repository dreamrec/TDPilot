"""Tests for the host-side ComponentNotesStore that backs td_component_notes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp import component_notes_store


@pytest.fixture
def tmp_store(monkeypatch, tmp_path: Path) -> component_notes_store.ComponentNotesStore:
    monkeypatch.setenv("TDPILOT_HOME", str(tmp_path))
    return component_notes_store.ComponentNotesStore()


def test_set_creates_entry(tmp_store):
    entry = tmp_store.set(
        project_hash="abc",
        project_label="lab",
        comp_path="/project1/feedback_chain",
        body="Trail decay via level.opacity",
        tags=["feedback", "rd"],
    )
    assert entry["body"] == "Trail decay via level.opacity"
    assert entry["tags"] == ["feedback", "rd"]
    assert entry["embedded"] is False
    assert entry["created_at"] == entry["updated_at"]


def test_set_overwrites_existing(tmp_store):
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/x", body="v1", tags=["a"])
    second = tmp_store.set(project_hash="abc", project_label="lab", comp_path="/x", body="v2", tags=["b"])
    assert second["body"] == "v2"
    assert second["tags"] == ["b"]
    assert tmp_store.get("abc", "/x")["body"] == "v2"


def test_set_with_embed_marks_flag(tmp_store):
    entry = tmp_store.set(
        project_hash="abc",
        project_label="lab",
        comp_path="/x",
        body="...",
        tags=[],
        embedded=True,
    )
    assert entry["embedded"] is True


def test_get_returns_none_when_missing(tmp_store):
    assert tmp_store.get("abc", "/never/written") is None


def test_append_creates_when_absent(tmp_store):
    entry = tmp_store.append(
        project_hash="abc",
        project_label="lab",
        comp_path="/x",
        body="first",
        tags=["t1"],
    )
    assert entry["body"] == "first"
    assert entry["tags"] == ["t1"]


def test_append_extends_existing_with_divider(tmp_store):
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/x", body="initial", tags=["a"])
    appended = tmp_store.append(
        project_hash="abc",
        project_label="lab",
        comp_path="/x",
        body="more",
        tags=["b"],
    )
    assert "initial" in appended["body"]
    assert "more" in appended["body"]
    assert "Appended" in appended["body"]
    # Tags merged uniquely
    assert set(appended["tags"]) == {"a", "b"}


def test_delete_removes_entry(tmp_store):
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/x", body="...")
    assert tmp_store.delete("abc", "/x") is True
    assert tmp_store.get("abc", "/x") is None


def test_delete_returns_false_when_missing(tmp_store):
    assert tmp_store.delete("abc", "/never") is False


def test_index_returns_excerpts(tmp_store):
    tmp_store.set(
        project_hash="abc",
        project_label="lab",
        comp_path="/x",
        body="x" * 250,
        tags=["t1"],
    )
    tmp_store.set(
        project_hash="abc",
        project_label="lab",
        comp_path="/y",
        body="short",
    )
    idx = tmp_store.index("abc")
    assert len(idx) == 2
    long_entry = next(e for e in idx if e["path"] == "/x")
    assert len(long_entry["body_excerpt"]) <= 201  # 200 + "…"
    assert long_entry["body_excerpt"].endswith("…")
    short_entry = next(e for e in idx if e["path"] == "/y")
    assert short_entry["body_excerpt"] == "short"


def test_index_orders_by_updated_at_desc(tmp_store):
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/older", body="a")
    # Bump /newer with a later updated_at by appending
    import time

    time.sleep(0.01)
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/newer", body="b")
    idx = tmp_store.index("abc")
    assert [e["path"] for e in idx] == ["/newer", "/older"]


def test_summarize_filters_by_scope_path(tmp_store):
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/project1/a", body="a")
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/project1/b", body="b")
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/elsewhere/c", body="c")
    md = tmp_store.summarize("abc", scope_path="/project1")
    assert "/project1/a" in md
    assert "/project1/b" in md
    assert "/elsewhere/c" not in md


def test_summarize_empty_scope_returns_friendly_message(tmp_store):
    md = tmp_store.summarize("abc")
    assert "No notes" in md


def test_persistence_across_instances(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TDPILOT_HOME", str(tmp_path))
    a = component_notes_store.ComponentNotesStore()
    a.set(project_hash="abc", project_label="lab", comp_path="/x", body="hi")
    b = component_notes_store.ComponentNotesStore()
    assert b.get("abc", "/x")["body"] == "hi"


def test_corrupt_file_recovers_to_empty(tmp_store, tmp_path: Path):
    bad = tmp_store._path("abc")
    bad.write_text("not-json{{", encoding="utf-8")
    assert tmp_store.index("abc") == []
    # Recovers on next save
    tmp_store.set(project_hash="abc", project_label="lab", comp_path="/x", body="recovered")
    assert tmp_store.get("abc", "/x")["body"] == "recovered"


def test_file_layout_round_trip(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TDPILOT_HOME", str(tmp_path))
    store = component_notes_store.ComponentNotesStore()
    store.set(project_hash="abc", project_label="lab", comp_path="/x", body="hi", tags=["t"])
    on_disk = json.loads((tmp_path / "component_notes" / "abc.json").read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == component_notes_store.SCHEMA_VERSION
    assert on_disk["project_hash"] == "abc"
    assert on_disk["project_label"] == "lab"
    assert "/x" in on_disk["notes"]
