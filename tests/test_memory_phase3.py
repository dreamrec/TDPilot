"""Tests for Phase 3 memory improvements: tag normalization, replay tracking,
reuse-aware ranking, and export/import.
"""

from __future__ import annotations

from td_mcp.memory import TechniqueStore

# ── Tag normalization ────────────────────────────────────────


def test_tags_lowercased_on_add(tmp_path):
    """Tags are lowercased when adding a technique."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add(
        {"complexity": "small"},
        scope="project",
        name="test",
        tags=["Particle", "NOISE", "flow"],
    )
    entry = store.get(tid, scope="project")
    assert entry["tags"] == ["flow", "noise", "particle"]


def test_tags_lowercased_on_update(tmp_path):
    """Tags are lowercased when updating a technique."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add({"complexity": "small"}, scope="project", name="test", tags=["old"])
    store.update(tid, {"tags": ["New", "UPDATED"]}, scope="project")
    entry = store.get(tid, scope="project")
    assert entry["tags"] == ["new", "updated"]


def test_tags_deduped_case_insensitive(tmp_path):
    """Duplicate tags differing only in case are merged."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add(
        {"complexity": "small"},
        scope="project",
        name="test",
        tags=["Noise", "noise", "NOISE"],
    )
    entry = store.get(tid, scope="project")
    assert entry["tags"] == ["noise"]


# ── Replay tracking ─────────────────────────────────────────


def test_record_replay_increments_count(tmp_path):
    """record_replay increments replay_count and sets last_replayed_at."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add({"complexity": "small"}, scope="project", name="test")

    entry = store.get(tid, scope="project")
    assert entry["replay_count"] == 0
    assert entry["last_replayed_at"] is None

    store.record_replay(tid, scope="project")
    entry = store.get(tid, scope="project")
    assert entry["replay_count"] == 1
    assert entry["last_replayed_at"] is not None

    store.record_replay(tid, scope="project")
    entry = store.get(tid, scope="project")
    assert entry["replay_count"] == 2


def test_record_replay_nonexistent_returns_false(tmp_path):
    """record_replay on nonexistent ID returns False."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    assert store.record_replay("nonexistent", scope="project") is False


def test_replay_count_persists(tmp_path):
    """Replay count survives store reload."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add({"complexity": "small"}, scope="project", name="test")
    store.record_replay(tid, scope="project")
    store.record_replay(tid, scope="project")

    # Reload from disk
    store2 = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    entry = store2.get(tid, scope="project")
    assert entry["replay_count"] == 2


# ── Reuse-aware search ranking ──────────────────────────────


def test_search_ranks_by_replay_count(tmp_path):
    """Search results rank higher-replay techniques above lower ones (same rating)."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")

    tid_low = store.add({"complexity": "small"}, scope="project", name="low-replay", tags=["test"])
    tid_high = store.add({"complexity": "small"}, scope="project", name="high-replay", tags=["test"])

    # Give both same rating
    store.set_rating(tid_low, 3, scope="project")
    store.set_rating(tid_high, 3, scope="project")

    # Replay high more
    store.record_replay(tid_high, scope="project")
    store.record_replay(tid_high, scope="project")
    store.record_replay(tid_high, scope="project")
    store.record_replay(tid_low, scope="project")

    results = store.search(tags=["test"], scope="project")
    assert len(results) == 2
    assert results[0]["name"] == "high-replay"
    assert results[1]["name"] == "low-replay"


def test_summary_includes_replay_fields(tmp_path):
    """Summaries include replay_count and last_replayed_at."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add({"complexity": "small"}, scope="project", name="test", tags=["x"])
    store.record_replay(tid, scope="project")

    results = store.search(tags=["x"], scope="project")
    assert results[0]["replay_count"] == 1
    assert results[0]["last_replayed_at"] is not None


# ── Export / Import ──────────────────────────────────────────


def test_export_contains_techniques(tmp_path):
    """Export returns all techniques in the specified scope."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid1 = store.add({"complexity": "small"}, scope="project", name="t1")
    tid2 = store.add({"complexity": "small"}, scope="project", name="t2")

    exported = store.export_library(scope="project")
    assert exported["version"] == 1
    assert exported["count"] == 2
    assert tid1 in exported["techniques"]
    assert tid2 in exported["techniques"]


def test_import_into_empty_store(tmp_path):
    """Import into an empty store adds all techniques."""
    store1 = TechniqueStore(base_dir=str(tmp_path / "src"), project_name="test")
    tid = store1.add({"complexity": "small"}, scope="project", name="portable")
    exported = store1.export_library(scope="project")

    store2 = TechniqueStore(base_dir=str(tmp_path / "dst"), project_name="test")
    result = store2.import_library(exported, scope="project")
    assert result["imported"] == 1
    assert result["skipped"] == 0

    entry = store2.get(tid, scope="project")
    assert entry is not None
    assert entry["name"] == "portable"


def test_import_skips_existing_without_overwrite(tmp_path):
    """Import skips techniques that already exist when overwrite=False."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add({"complexity": "small"}, scope="project", name="original")
    exported = store.export_library(scope="project")

    # Modify the exported name to detect overwrite
    exported["techniques"][tid]["name"] = "modified"

    result = store.import_library(exported, scope="project", overwrite=False)
    assert result["imported"] == 0
    assert result["skipped"] == 1

    # Original name preserved
    entry = store.get(tid, scope="project")
    assert entry["name"] == "original"


def test_import_overwrites_existing_with_flag(tmp_path):
    """Import overwrites techniques when overwrite=True."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    tid = store.add({"complexity": "small"}, scope="project", name="original")
    exported = store.export_library(scope="project")

    exported["techniques"][tid]["name"] = "updated"

    result = store.import_library(exported, scope="project", overwrite=True)
    assert result["imported"] == 1
    assert result["overwritten"] == 1

    entry = store.get(tid, scope="project")
    assert entry["name"] == "updated"


def test_import_invalid_format(tmp_path):
    """Import rejects data where 'techniques' is not a dict."""
    store = TechniqueStore(base_dir=str(tmp_path), project_name="test")
    result = store.import_library({"techniques": "not a dict"}, scope="project")
    assert result["imported"] == 0
    assert "error" in result


def test_roundtrip_export_import(tmp_path):
    """Full roundtrip: export from one store, import to another, verify integrity."""
    store1 = TechniqueStore(base_dir=str(tmp_path / "a"), project_name="test")
    tid = store1.add(
        {"complexity": "small", "recipe": {"nodes": {"/n1": {"type": "noiseTOP"}}}},
        scope="project",
        name="roundtrip",
        tags=["Particle", "FLOW"],
    )
    store1.set_rating(tid, 4, scope="project")
    store1.set_favorite(tid, True, scope="project")
    store1.record_replay(tid, scope="project")

    exported = store1.export_library(scope="project")

    store2 = TechniqueStore(base_dir=str(tmp_path / "b"), project_name="test")
    store2.import_library(exported, scope="project")

    entry = store2.get(tid, scope="project")
    assert entry["name"] == "roundtrip"
    assert entry["tags"] == ["flow", "particle"]  # lowercased
    assert entry["rating"] == 4
    assert entry["favorite"] is True
    assert entry["replay_count"] == 1
    assert entry["technique"]["recipe"]["nodes"]["/n1"]["type"] == "noiseTOP"
