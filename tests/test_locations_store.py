"""Tests for the host-side LocationsStore that backs td_locations.

The tool itself is tested via the live TD runtime (it depends on /api/exec).
This file pins the file-format and CRUD semantics of the underlying store —
which is pure host-side I/O and can be exercised with a tmpdir override.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp import locations_store


@pytest.fixture
def tmp_store(monkeypatch, tmp_path: Path) -> locations_store.LocationsStore:
    monkeypatch.setenv("TDPILOT_HOME", str(tmp_path))
    # Construct the store explicitly so the env var resolves at fixture time.
    return locations_store.LocationsStore()


def _make_id(label: str = "live_visuals_v3") -> tuple[str, str]:
    return locations_store.derive_project_id(label)


def test_derive_project_id_is_stable():
    a = locations_store.derive_project_id("foo")
    b = locations_store.derive_project_id("foo")
    assert a == b


def test_derive_project_id_distinguishes_names():
    a = locations_store.derive_project_id("foo")[0]
    b = locations_store.derive_project_id("bar")[0]
    assert a != b


def test_derive_project_id_handles_none():
    digest, label = locations_store.derive_project_id(None)
    assert label == "untitled"
    assert digest == locations_store.derive_project_id("untitled")[0]


def test_save_creates_entry(tmp_store: locations_store.LocationsStore):
    h, label = _make_id()
    entry = tmp_store.save(
        project_hash=h,
        project_label=label,
        name="lab",
        path="/project1/feedback_chain",
        description="trail decay tuning",
    )
    assert entry["name"] == "lab"
    assert entry["path"] == "/project1/feedback_chain"
    assert entry["description"] == "trail decay tuning"
    assert entry["created_at"]
    assert entry["updated_at"] == entry["created_at"]


def test_save_overwrites_existing_name(tmp_store: locations_store.LocationsStore):
    h, label = _make_id()
    tmp_store.save(project_hash=h, project_label=label, name="lab", path="/a")
    second = tmp_store.save(project_hash=h, project_label=label, name="lab", path="/b")
    assert second["path"] == "/b"
    entries = tmp_store.list_for_project(h)
    assert len(entries) == 1
    assert entries[0]["path"] == "/b"
    # updated_at refreshed
    assert second["updated_at"] >= second["created_at"]


def test_list_returns_empty_for_unknown_project(tmp_store: locations_store.LocationsStore):
    h, _ = _make_id("never_saved_to")
    assert tmp_store.list_for_project(h) == []


def test_get_returns_entry_by_name(tmp_store: locations_store.LocationsStore):
    h, label = _make_id()
    tmp_store.save(project_hash=h, project_label=label, name="lab", path="/x")
    got = tmp_store.get(h, "lab")
    assert got is not None
    assert got["path"] == "/x"


def test_get_returns_none_when_missing(tmp_store: locations_store.LocationsStore):
    h, _ = _make_id()
    assert tmp_store.get(h, "absent") is None


def test_delete_removes_entry(tmp_store: locations_store.LocationsStore):
    h, label = _make_id()
    tmp_store.save(project_hash=h, project_label=label, name="lab", path="/x")
    assert tmp_store.delete(h, "lab") is True
    assert tmp_store.list_for_project(h) == []


def test_delete_returns_false_when_missing(tmp_store: locations_store.LocationsStore):
    h, label = _make_id()
    tmp_store.save(project_hash=h, project_label=label, name="lab", path="/x")
    assert tmp_store.delete(h, "absent") is False


def test_rename_succeeds(tmp_store: locations_store.LocationsStore):
    h, label = _make_id()
    tmp_store.save(project_hash=h, project_label=label, name="lab", path="/x")
    assert tmp_store.rename(h, "lab", "feedback_lab") is True
    entries = tmp_store.list_for_project(h)
    assert entries[0]["name"] == "feedback_lab"


def test_rename_rejects_when_target_exists(tmp_store: locations_store.LocationsStore):
    h, label = _make_id()
    tmp_store.save(project_hash=h, project_label=label, name="a", path="/x")
    tmp_store.save(project_hash=h, project_label=label, name="b", path="/y")
    assert tmp_store.rename(h, "a", "b") is False
    # Both names still distinct
    assert tmp_store.get(h, "a") is not None
    assert tmp_store.get(h, "b") is not None


def test_rename_rejects_when_source_missing(tmp_store: locations_store.LocationsStore):
    h, _ = _make_id()
    assert tmp_store.rename(h, "absent", "anything") is False


def test_corrupt_file_recovers_to_empty(tmp_store: locations_store.LocationsStore, tmp_path: Path):
    h, _ = _make_id()
    bad_path = tmp_store._path(h)
    bad_path.write_text("not-json{{{", encoding="utf-8")
    # Should NOT raise; should return [] and recover on next save.
    assert tmp_store.list_for_project(h) == []


def test_persistence_across_instances(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TDPILOT_HOME", str(tmp_path))
    h, label = _make_id()
    a = locations_store.LocationsStore()
    a.save(project_hash=h, project_label=label, name="lab", path="/p")
    b = locations_store.LocationsStore()
    entries = b.list_for_project(h)
    assert len(entries) == 1
    assert entries[0]["name"] == "lab"


def test_file_layout_round_trip(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TDPILOT_HOME", str(tmp_path))
    h, label = _make_id("round_trip")
    store = locations_store.LocationsStore()
    store.save(project_hash=h, project_label=label, name="lab", path="/p")
    on_disk = json.loads((tmp_path / "locations" / f"{h}.json").read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == locations_store.SCHEMA_VERSION
    assert on_disk["project_hash"] == h
    assert on_disk["project_label"] == label
    assert on_disk["locations"][0]["name"] == "lab"
