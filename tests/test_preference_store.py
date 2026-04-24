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


# ---------------------------------------------------------------------------
# Lazy project-scope rebind (v1.4.4 reliability release)
# If TDPilot starts before TouchDesigner is reachable, the store is
# constructed with project_name=None. Later, when TD becomes reachable and
# we learn the project name, `rebind_project_scope()` mutates the instance
# in place so project-scoped reads/writes work without a server restart.
# ---------------------------------------------------------------------------


class TestRebindProjectScope:
    def test_store_starts_unbound_raises_on_project_save(self, tmp_path):
        store = PreferenceStore(base_dir=str(tmp_path), project_name=None)
        with pytest.raises(ValueError) as exc:
            store.set("x", 1, scope="project")
        assert "TDPILOT_PROJECT_NAME" in str(exc.value)

    def test_rebind_enables_project_scope(self, tmp_path):
        store = PreferenceStore(base_dir=str(tmp_path), project_name=None)
        assert store.stats()["project_name"] is None

        store.rebind_project_scope("LiveProject")

        assert store.stats()["project_name"] == "LiveProject"
        store.set("theme", "dark", scope="project")  # no longer raises
        assert store.get("theme", scope="project") == "dark"

    def test_rebind_sanitizes_filesystem_unsafe_chars(self, tmp_path):
        store = PreferenceStore(base_dir=str(tmp_path), project_name=None)
        store.rebind_project_scope("My Project/v2!")
        store.set("k", "v", scope="project")
        # Unsafe chars become underscores (same convention as __init__)
        assert (tmp_path / "projects" / "My_Project_v2_" / "preferences.json").exists()

    def test_rebind_loads_existing_project_data(self, tmp_path):
        # Seed: pre-bound store writes to disk
        seed = PreferenceStore(base_dir=str(tmp_path), project_name="Preexisting")
        seed.set("already_here", True, scope="project")

        # Fresh store, unbound, then rebind — should see the existing data
        store = PreferenceStore(base_dir=str(tmp_path), project_name=None)
        store.rebind_project_scope("Preexisting")
        assert store.get("already_here", scope="project") is True

    def test_rebind_after_already_bound_updates_to_new_project(self, tmp_path):
        # Rare but worth pinning: re-bind mid-session (e.g. TD loaded a
        # different project). Data from the old project stays on disk; the
        # store now points at the new project's folder.
        store = PreferenceStore(base_dir=str(tmp_path), project_name="A")
        store.set("a_key", "a_val", scope="project")
        store.rebind_project_scope("B")
        assert store.stats()["project_name"] == "B"
        # B has no data yet
        assert store.get("a_key", scope="project") is None
        store.set("b_key", "b_val", scope="project")
        # A's data preserved on disk
        other = PreferenceStore(base_dir=str(tmp_path), project_name="A")
        assert other.get("a_key", scope="project") == "a_val"
