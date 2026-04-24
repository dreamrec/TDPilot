"""Tests for expanded SnapshotManager.diff() covering connections and expressions."""

from td_mcp.memory import SnapshotManager


def _make_manager():
    return SnapshotManager()


# ---------------------------------------------------------------------------
# Connection diff tests
# ---------------------------------------------------------------------------


def test_diff_added_connections():
    manager = _make_manager()
    snap_a = {"nodes": {}, "connections": []}
    snap_b = {
        "nodes": {},
        "connections": [{"from": "/p/noise1", "to": "/p/null1", "from_index": 0, "to_index": 0}],
    }
    diff = manager.diff(snap_a, snap_b)
    assert len(diff["added_connections"]) == 1
    assert diff["added_connections"][0] == ("/p/noise1", "/p/null1", 0, 0)
    assert len(diff["removed_connections"]) == 0


def test_diff_removed_connections():
    manager = _make_manager()
    snap_a = {
        "nodes": {},
        "connections": [{"from": "/p/noise1", "to": "/p/null1", "from_index": 0, "to_index": 0}],
    }
    snap_b = {"nodes": {}, "connections": []}
    diff = manager.diff(snap_a, snap_b)
    assert len(diff["removed_connections"]) == 1
    assert diff["removed_connections"][0] == ("/p/noise1", "/p/null1", 0, 0)
    assert len(diff["added_connections"]) == 0


def test_diff_rewired_connections():
    manager = _make_manager()
    snap_a = {
        "nodes": {},
        "connections": [{"from": "/p/noise1", "to": "/p/null1", "from_index": 0, "to_index": 0}],
    }
    snap_b = {
        "nodes": {},
        "connections": [{"from": "/p/noise1", "to": "/p/null2", "from_index": 0, "to_index": 0}],
    }
    diff = manager.diff(snap_a, snap_b)
    # old connection removed, new one added
    assert len(diff["removed_connections"]) == 1
    assert diff["removed_connections"][0] == ("/p/noise1", "/p/null1", 0, 0)
    assert len(diff["added_connections"]) == 1
    assert diff["added_connections"][0] == ("/p/noise1", "/p/null2", 0, 0)


# ---------------------------------------------------------------------------
# Expression diff tests
# ---------------------------------------------------------------------------


def test_diff_expression_changes():
    manager = _make_manager()
    snap_a = {
        "nodes": {
            "/p/noise1": {
                "params": {
                    "amp": {"value": 0.5},  # no expression
                }
            }
        },
        "connections": [],
    }
    snap_b = {
        "nodes": {
            "/p/noise1": {
                "params": {
                    "amp": {"value": 0.5, "expression": "me.time.frame / 100"},
                }
            }
        },
        "connections": [],
    }
    diff = manager.diff(snap_a, snap_b)
    assert len(diff["added_expressions"]) == 1
    assert diff["added_expressions"][0]["param"] == "amp"
    assert diff["added_expressions"][0]["expression"] == "me.time.frame / 100"
    assert len(diff["removed_expressions"]) == 0
    assert len(diff["modified_expressions"]) == 0


def test_diff_removed_expressions():
    manager = _make_manager()
    snap_a = {
        "nodes": {
            "/p/noise1": {
                "params": {
                    "amp": {"value": 0.5, "expression": "me.time.frame / 100"},
                }
            }
        },
        "connections": [],
    }
    snap_b = {
        "nodes": {
            "/p/noise1": {
                "params": {
                    "amp": {"value": 0.5},
                }
            }
        },
        "connections": [],
    }
    diff = manager.diff(snap_a, snap_b)
    assert len(diff["removed_expressions"]) == 1
    assert diff["removed_expressions"][0]["param"] == "amp"
    assert len(diff["added_expressions"]) == 0
    assert len(diff["modified_expressions"]) == 0


def test_diff_modified_expressions():
    manager = _make_manager()
    snap_a = {
        "nodes": {
            "/p/noise1": {
                "params": {
                    "amp": {"value": 0.5, "expression": "me.time.frame / 100"},
                }
            }
        },
        "connections": [],
    }
    snap_b = {
        "nodes": {
            "/p/noise1": {
                "params": {
                    "amp": {"value": 0.5, "expression": "me.time.frame / 200"},
                }
            }
        },
        "connections": [],
    }
    diff = manager.diff(snap_a, snap_b)
    assert len(diff["modified_expressions"]) == 1
    assert diff["modified_expressions"][0]["param"] == "amp"
    assert diff["modified_expressions"][0]["expression_a"] == "me.time.frame / 100"
    assert diff["modified_expressions"][0]["expression_b"] == "me.time.frame / 200"
    assert len(diff["added_expressions"]) == 0
    assert len(diff["removed_expressions"]) == 0


# ---------------------------------------------------------------------------
# Summary string includes connection and expression counts
# ---------------------------------------------------------------------------


def test_diff_summary_includes_connections_and_expressions():
    manager = _make_manager()
    snap_a = {
        "nodes": {
            "/p/noise1": {
                "params": {
                    "amp": {"value": 0.5, "expression": "old_expr"},
                }
            }
        },
        "connections": [{"from": "/p/noise1", "to": "/p/null1", "from_index": 0, "to_index": 0}],
    }
    snap_b = {
        "nodes": {
            "/p/noise1": {
                "params": {
                    "amp": {"value": 0.5, "expression": "new_expr"},
                }
            }
        },
        "connections": [{"from": "/p/noise1", "to": "/p/null2", "from_index": 0, "to_index": 0}],
    }
    diff = manager.diff(snap_a, snap_b)
    summary = diff["summary"]
    assert "connection" in summary.lower()
    assert "expression" in summary.lower()
