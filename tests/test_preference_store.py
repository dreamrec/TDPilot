"""Tests for PreferenceStore — get/set/list/delete with scoped persistence."""

import pytest

from td_mcp.memory.preference_store import PreferenceStore


@pytest.fixture
def store(tmp_path):
    return PreferenceStore(base_dir=str(tmp_path), project_name="test_project")


class TestGetSet:
    def test_set_and_get(self, store):
        store.set("color_palette", ["#ff0000", "#00ff00"], scope="project")
        assert store.get("color_palette", scope="project") == ["#ff0000", "#00ff00"]

    def test_get_default(self, store):
        assert store.get("missing", default="fallback") == "fallback"

    def test_overwrite(self, store):
        store.set("res", 1080)
        store.set("res", 720)
        assert store.get("res") == 720


class TestListAndDelete:
    def test_list_all(self, store):
        store.set("a", 1)
        store.set("b", 2)
        all_prefs = store.list_all()
        assert all_prefs == {"a": 1, "b": 2}

    def test_delete(self, store):
        store.set("key", "val")
        assert store.delete("key")
        assert store.get("key") is None

    def test_delete_missing(self, store):
        assert store.delete("nonexistent") is False


class TestScopes:
    def test_project_and_global_isolated(self, store):
        store.set("theme", "dark", scope="project")
        store.set("theme", "light", scope="global")
        assert store.get("theme", scope="project") == "dark"
        assert store.get("theme", scope="global") == "light"


class TestPersistence:
    def test_survives_reload(self, tmp_path):
        store1 = PreferenceStore(base_dir=str(tmp_path), project_name="persist_test")
        store1.set("key", "value", scope="project")
        store1.set("gkey", "gval", scope="global")

        store2 = PreferenceStore(base_dir=str(tmp_path), project_name="persist_test")
        assert store2.get("key", scope="project") == "value"
        assert store2.get("gkey", scope="global") == "gval"


class TestStats:
    def test_stats(self, store):
        store.set("a", 1, scope="project")
        store.set("b", 2, scope="global")
        stats = store.stats()
        assert stats["project_count"] == 1
        assert stats["global_count"] == 1
        assert stats["project_name"] == "test_project"
