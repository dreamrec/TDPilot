"""Tests for technique store upgrades — compatibility and validation."""

import tempfile

from td_mcp.memory.technique_store import TechniqueStore


def test_compatibility_field_persists():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        compat = {"min_build": "2025.32460", "required_ops": ["noiseTOP"]}
        tid = store.add({"recipe": {}}, scope="global", name="test", compatibility=compat)
        entry = store.get(tid, scope="global")
        assert entry["compatibility"]["min_build"] == "2025.32460"


def test_update_validation_promotes_candidate():
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
        ok = store.update_validation(tid, vr, scope="global")
        assert ok
        entry = store.get(tid, scope="global")
        assert entry["state"] == "validated_local"
        assert entry["validation_result"]["status"] == "pass"


def test_update_state_validates():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        ok = store.update_state(tid, "validated_portable", scope="global")
        assert ok
        entry = store.get(tid, scope="global")
        assert entry["state"] == "validated_portable"


def test_compatibility_in_summary():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        compat = {"min_build": "2025.32460"}
        tid = store.add({"recipe": {}}, scope="global", name="test", compatibility=compat)
        results = store.list_techniques(scope="global")
        assert results[0].get("compatibility") is not None


def test_update_validation_demotes_on_fail():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        # First promote to validated_local
        store.update_state(tid, "validated_local", scope="global")
        # Then fail it
        vr = {
            "status": "fail",
            "validated_at": "2026-03-14T00:00:00Z",
            "td_build": "2025.32460",
            "errors": ["broken"],
            "warnings": [],
        }
        store.update_validation(tid, vr, scope="global")
        entry = store.get(tid, scope="global")
        assert entry["state"] == "candidate"


def test_update_state_rejects_invalid():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        ok = store.update_state(tid, "bogus_state", scope="global")
        assert not ok


def test_validation_result_in_summary():
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
        store.update_validation(tid, vr, scope="global")
        results = store.list_techniques(scope="global")
        assert results[0]["validation_result"]["status"] == "pass"


def test_compatibility_defaults_to_empty_dict():
    with tempfile.TemporaryDirectory() as d:
        store = TechniqueStore(base_dir=d)
        tid = store.add({"recipe": {}}, scope="global", name="test")
        entry = store.get(tid, scope="global")
        assert entry["compatibility"] == {}
