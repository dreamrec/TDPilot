"""Tests for recipe states and validation_result in TechniqueStore."""

import tempfile

from td_mcp.memory.technique_store import TechniqueStore

VALID_STATES = {"reference_only", "candidate", "validated_local", "validated_portable", "deprecated"}


def test_new_technique_has_candidate_state():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        entry = store.get(tid, scope="global")
        assert entry["state"] == "candidate"


def test_technique_state_in_summary():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        results = store.list_techniques(scope="global")
        assert results[0]["state"] == "candidate"


def test_update_state():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        ok = store.update_state(tid, "validated_local", scope="global")
        assert ok
        entry = store.get(tid, scope="global")
        assert entry["state"] == "validated_local"


def test_update_ignores_state():
    """update() must not allow direct state changes; callers must use update_state()."""
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        store.update(tid, {"state": "validated_local"}, scope="global")
        entry = store.get(tid, scope="global")
        assert entry["state"] == "candidate"  # unchanged


def test_validation_result_field():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        vr = {
            "status": "pass",
            "validated_at": "2026-03-14T00:00:00Z",
            "td_build": "2025.32460",
            "errors": [],
            "warnings": [],
        }
        ok = store.update(tid, {"validation_result": vr}, scope="global")
        assert ok
        entry = store.get(tid, scope="global")
        assert entry["validation_result"]["status"] == "pass"
