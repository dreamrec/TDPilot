from td_mcp.memory import SnapshotManager


def test_snapshot_manager_trims_to_max():
    manager = SnapshotManager(max_snapshots=2)

    manager.add_snapshot({"nodes": {}, "connections": []}, name="a")
    manager.add_snapshot({"nodes": {}, "connections": []}, name="b")
    manager.add_snapshot({"nodes": {}, "connections": []}, name="c")

    listed = manager.list_snapshots(limit=10)

    assert len(listed) == 2
    assert listed[0]["name"] == "c"
    assert listed[1]["name"] == "b"


def test_snapshot_diff_supports_params_and_parameters_keys():
    manager = SnapshotManager()

    snap_a = {
        "nodes": {
            "/project1/noise1": {
                "params": {
                    "amp": {"value": 0.1},
                }
            }
        },
        "connections": [],
    }
    snap_b = {
        "nodes": {
            "/project1/noise1": {
                "parameters": {
                    "amp": {"value": 0.8},
                }
            },
            "/project1/null1": {
                "parameters": {},
            },
        },
        "connections": [],
    }

    diff = manager.diff(snap_a, snap_b)

    assert diff["changed_params"][0]["param"] == "amp"
    assert diff["changed_params"][0]["value_a"] == 0.1
    assert diff["changed_params"][0]["value_b"] == 0.8
    assert "/project1/null1" in diff["added_nodes"]


def test_snapshot_persistence_roundtrip(tmp_path):
    manager = SnapshotManager(max_snapshots=5, storage_dir=str(tmp_path))
    saved = manager.add_snapshot({"nodes": {"/project1/noise1": {}}, "connections": []}, name="persisted")

    reloaded = SnapshotManager(max_snapshots=5, storage_dir=str(tmp_path))
    loaded = reloaded.get_snapshot(saved["snapshot_id"])

    assert loaded is not None
    assert loaded["name"] == "persisted"
    assert loaded["snapshot"]["nodes"] == {"/project1/noise1": {}}
    assert reloaded.stats()["persistence_enabled"] is True


def test_snapshot_trim_removes_old_disk_files(tmp_path):
    manager = SnapshotManager(max_snapshots=1, storage_dir=str(tmp_path))
    first = manager.add_snapshot({"nodes": {"a": {}}, "connections": []}, name="first")
    second = manager.add_snapshot({"nodes": {"b": {}}, "connections": []}, name="second")

    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1
    assert json_files[0].name == f"{second['snapshot_id']}.json"
    assert manager.get_snapshot(first["snapshot_id"]) is None
