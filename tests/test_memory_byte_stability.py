"""Tests for byte-stable index serialization in memory stores.

Cache-prefix preservation: if the indexes don't serialize deterministically,
prompt-cache hits collapse to zero after every save. The fix is sort_keys +
sorted entry iteration. These tests guard against regressions where a future
edit drops sort_keys silently.

API notes (adapted from plan to match the real constructors/methods):
  - TechniqueStore(base_dir=..., project_name=None) — stores in techniques.json
    not index.json; .add(technique, scope="global", name=...) is the save method.
  - KnowledgeStore(base_dir=..., project_name=None) — stores in index.json;
    .add(body, scope="global", name=...) is the save method.
"""

from __future__ import annotations

import json
from pathlib import Path

from td_mcp.memory import KnowledgeStore, TechniqueStore

# ---------------------------------------------------------------------------
# TechniqueStore byte-stability tests
# ---------------------------------------------------------------------------


def test_technique_store_index_is_byte_stable(tmp_path: Path):
    """Writing the same techniques in different orders must produce identical bytes."""
    # TechniqueStore persists to <base_dir>/global/techniques.json
    a = TechniqueStore(base_dir=str(tmp_path / "a"))
    b = TechniqueStore(base_dir=str(tmp_path / "b"))

    technique_z = {"node_count": 1, "complexity": "low", "ops": ["z-op"]}
    technique_a = {"node_count": 2, "complexity": "medium", "ops": ["a-op"]}

    # Insert in opposite orders — uuid keys will differ, but the sorted-key
    # serialization must produce the same intra-record ordering.
    # We override the uuid by inserting directly into the in-memory store
    # and calling _save_scope so we control the keys.
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    def _insert(store: TechniqueStore, tid: str, technique: dict, name: str) -> None:
        """Directly populate the global in-memory dict and flush to disk."""
        entry = {
            "id": tid,
            "name": name,
            "description": "",
            "tags": [],
            "notes": "",
            "created_at": now,
            "updated_at": now,
            "favorite": False,
            "rating": 0,
            "state": "candidate",
            "validation_result": None,
            "replay_count": 0,
            "last_replayed_at": None,
            "compatibility": {},
            "technique": technique,
        }
        store._global[tid] = entry
        store._save_scope("global")

    # Insert in opposite orders using fixed UUIDs so disk content is comparable.
    _insert(a, "zzz-id", technique_z, "z-technique")
    _insert(a, "aaa-id", technique_a, "a-technique")

    _insert(b, "aaa-id", technique_a, "a-technique")
    _insert(b, "zzz-id", technique_z, "z-technique")

    bytes_a = (tmp_path / "a" / "global" / "techniques.json").read_bytes()
    bytes_b = (tmp_path / "b" / "global" / "techniques.json").read_bytes()

    assert bytes_a == bytes_b, "TechniqueStore bytes diverged due to insertion order"


def test_technique_store_index_sort_keys_in_output(tmp_path: Path):
    """The serialized techniques.json must have alphabetically-sorted keys per record."""
    store = TechniqueStore(base_dir=str(tmp_path))
    store.add(
        {"node_count": 1, "complexity": "low"},
        scope="global",
        name="t1",
        description="d",
    )

    text = (tmp_path / "global" / "techniques.json").read_text(encoding="utf-8")
    data = json.loads(text)
    # Re-serialize with sort_keys=True; if the file is already sorted, it must match.
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2)
    assert text.rstrip() == canonical.rstrip(), (
        "techniques.json keys are not sorted — sort_keys=True missing from _write_file"
    )


# ---------------------------------------------------------------------------
# KnowledgeStore byte-stability tests
# ---------------------------------------------------------------------------


def test_knowledge_store_index_is_byte_stable(tmp_path: Path):
    """Knowledge index must be byte-stable across insertion orders."""
    # KnowledgeStore stores to <base_dir>/global/index.json
    a = KnowledgeStore(base_dir=str(tmp_path / "a"))
    b = KnowledgeStore(base_dir=str(tmp_path / "b"))

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    def _insert(store: KnowledgeStore, eid: str, name: str, body: str) -> None:
        """Directly populate the global in-memory dict and flush to disk."""
        record = {
            "id": eid,
            "name": name,
            "description": "",
            "tags": [],
            "source": "",
            "notes": "",
            "created_at": now,
            "updated_at": now,
            "favorite": False,
            "rating": 0,
            "body_path": f"entries/{eid}.md",
            "body_bytes": len(body.encode("utf-8")),
        }
        # Write the body file so the store stays consistent.
        body_dir = store._global_dir / "entries"
        body_dir.mkdir(parents=True, exist_ok=True)
        (body_dir / f"{eid}.md").write_text(body, encoding="utf-8")

        store._global[eid] = record
        store._save_index("global")

    # Insert in opposite orders with fixed IDs so disk content is comparable.
    _insert(a, "zzz-id", "Z entry", "zbody")
    _insert(a, "aaa-id", "A entry", "abody")

    _insert(b, "aaa-id", "A entry", "abody")
    _insert(b, "zzz-id", "Z entry", "zbody")

    index_a = (tmp_path / "a" / "global" / "index.json").read_bytes()
    index_b = (tmp_path / "b" / "global" / "index.json").read_bytes()

    assert index_a == index_b, "KnowledgeStore index bytes diverged due to insertion order"


def test_knowledge_store_index_sort_keys_in_output(tmp_path: Path):
    """The serialized index.json must have alphabetically-sorted keys per record."""
    store = KnowledgeStore(base_dir=str(tmp_path))
    store.add("hello knowledge", scope="global", name="k1", description="desc")

    text = (tmp_path / "global" / "index.json").read_text(encoding="utf-8")
    data = json.loads(text)
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2)
    assert text.rstrip() == canonical.rstrip(), (
        "index.json keys are not sorted — sort_keys=True missing from _write_json"
    )


# ---------------------------------------------------------------------------
# PreferenceStore byte-stability tests
# ---------------------------------------------------------------------------


def test_preference_store_index_is_byte_stable(tmp_path: Path):
    """Writing the same preferences in different orders must produce identical bytes.

    PreferenceStore persists to <base_dir>/global/preferences.json.
    The public set() API is clean (no UUID generation), so we use it directly
    with two stores rooted at separate directories for isolation.
    """
    from td_mcp.memory import PreferenceStore

    a = PreferenceStore(base_dir=str(tmp_path / "a"))
    b = PreferenceStore(base_dir=str(tmp_path / "b"))

    # Insert the same key-value pairs in opposite orders.
    a.set("z_key", "z_value", scope="global")
    a.set("a_key", "a_value", scope="global")

    b.set("a_key", "a_value", scope="global")
    b.set("z_key", "z_value", scope="global")

    bytes_a = (tmp_path / "a" / "global" / "preferences.json").read_bytes()
    bytes_b = (tmp_path / "b" / "global" / "preferences.json").read_bytes()

    assert bytes_a == bytes_b, "PreferenceStore bytes diverged due to insertion order"


# ---------------------------------------------------------------------------
# SnapshotManager byte-stability tests
# ---------------------------------------------------------------------------


def test_snapshot_manager_index_is_byte_stable(tmp_path: Path):
    """Snapshots with the same content but written via different insertion orders
    must produce byte-identical files on disk.

    SnapshotManager persists each snapshot to <storage_dir>/<snapshot_id>.json.
    add_snapshot() generates a random UUID, so we inject pre-built payloads
    directly into _snapshots/_order and call _persist_snapshot() — the same
    internal-injection pattern used for TechniqueStore above.
    """
    from datetime import datetime, timezone

    from td_mcp.memory import SnapshotManager

    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    a = SnapshotManager(storage_dir=str(dir_a))
    b = SnapshotManager(storage_dir=str(dir_b))

    now = datetime.now(timezone.utc).isoformat()

    # Two fixed snapshot IDs so the filenames match between stores.
    sid_z = "zzzzz-0000-0000-0000-000000000000"
    sid_a = "aaaaa-0000-0000-0000-000000000000"

    payload_z = {
        "snapshot_schema_version": 1,
        "snapshot_id": sid_z,
        "name": "z-snapshot",
        "timestamp": now,
        "snapshot": {"nodes": {"z_node": {"type": "nullTOP"}}, "connections": []},
    }
    payload_a = {
        "snapshot_schema_version": 1,
        "snapshot_id": sid_a,
        "name": "a-snapshot",
        "timestamp": now,
        "snapshot": {"nodes": {"a_node": {"type": "nullTOP"}}, "connections": []},
    }

    def _inject(store: SnapshotManager, sid: str, payload: dict) -> None:
        """Bypass add_snapshot UUID generation; inject and flush via _persist_snapshot."""
        store._snapshots[sid] = payload
        store._order.append(sid)
        store._persist_snapshot(payload)

    # Insert in opposite orders.
    _inject(a, sid_z, payload_z)
    _inject(a, sid_a, payload_a)

    _inject(b, sid_a, payload_a)
    _inject(b, sid_z, payload_z)

    # Each snapshot is its own file; check both files for byte stability.
    for sid in (sid_z, sid_a):
        bytes_a = (dir_a / f"{sid}.json").read_bytes()
        bytes_b = (dir_b / f"{sid}.json").read_bytes()
        assert bytes_a == bytes_b, f"SnapshotManager bytes diverged for snapshot {sid} due to insertion order"
