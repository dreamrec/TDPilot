"""Tests for TechniqueStore — CRUD, search, promote, favorite."""

import pytest

from td_mcp.memory.technique_store import TechniqueStore


@pytest.fixture
def store(tmp_path):
    return TechniqueStore(base_dir=str(tmp_path), project_name="test_project")


@pytest.fixture
def sample_technique():
    return {
        "source_path": "/project1/feedback",
        "node_count": 5,
        "connection_count": 4,
        "complexity": "small",
        "families": {"TOP": 3, "CHOP": 2},
        "op_types": {"feedbackTOP": 1, "noiseTOP": 1, "compositeTOP": 1, "noiseCHOP": 1, "mathCHOP": 1},
        "recipe": {
            "nodes": {
                "/feedback1": {"name": "feedback1", "type": "feedbackTOP", "family": "TOP", "params": {}},
                "/noise1": {"name": "noise1", "type": "noiseTOP", "family": "TOP", "params": {"seed": 42}},
            },
            "connections": [{"from": "/noise1", "to": "/feedback1", "from_index": 0, "to_index": 0}],
        },
    }


class TestCRUD:
    def test_add_and_get(self, store, sample_technique):
        tid = store.add(
            sample_technique, scope="project", name="feedback loop", tags=["feedback", "generative"]
        )
        assert tid
        entry = store.get(tid, scope="project")
        assert entry is not None
        assert entry["name"] == "feedback loop"
        assert "feedback" in entry["tags"]
        assert entry["technique"]["node_count"] == 5

    def test_get_missing(self, store):
        assert store.get("nonexistent") is None

    def test_update(self, store, sample_technique):
        tid = store.add(sample_technique, name="old name")
        ok = store.update(tid, {"name": "new name", "tags": ["updated"]})
        assert ok
        entry = store.get(tid)
        assert entry["name"] == "new name"
        assert entry["tags"] == ["updated"]

    def test_update_missing(self, store):
        assert store.update("nonexistent", {"name": "x"}) is False

    def test_delete(self, store, sample_technique):
        tid = store.add(sample_technique)
        assert store.delete(tid)
        assert store.get(tid) is None

    def test_delete_missing(self, store):
        assert store.delete("nonexistent") is False


class TestSearch:
    def test_search_by_name(self, store, sample_technique):
        store.add(sample_technique, name="feedback loop", tags=["feedback"])
        store.add(sample_technique, name="noise generator", tags=["noise"])
        results = store.search(query="feedback", scope="project")
        assert len(results) == 1
        assert results[0]["name"] == "feedback loop"

    def test_search_by_tags(self, store, sample_technique):
        store.add(sample_technique, name="a", tags=["feedback"])
        store.add(sample_technique, name="b", tags=["noise"])
        results = store.search(tags=["noise"], scope="project")
        assert len(results) == 1
        assert results[0]["name"] == "b"

    def test_search_all_scopes(self, store, sample_technique):
        store.add(sample_technique, name="project one", scope="project")
        store.add(sample_technique, name="global one", scope="global")
        results = store.search(scope="all")
        assert len(results) == 2

    def test_search_limit(self, store, sample_technique):
        for i in range(10):
            store.add(sample_technique, name=f"tech_{i}")
        results = store.search(scope="project", limit=3)
        assert len(results) == 3


class TestFavoriteAndRating:
    def test_set_favorite(self, store, sample_technique):
        tid = store.add(sample_technique)
        assert store.set_favorite(tid, True)
        entry = store.get(tid)
        assert entry["favorite"] is True

    def test_set_rating(self, store, sample_technique):
        tid = store.add(sample_technique)
        assert store.set_rating(tid, 4)
        entry = store.get(tid)
        assert entry["rating"] == 4

    def test_rating_clamped(self, store, sample_technique):
        tid = store.add(sample_technique)
        store.set_rating(tid, 10)
        assert store.get(tid)["rating"] == 5
        store.set_rating(tid, -5)
        assert store.get(tid)["rating"] == 0


class TestPromote:
    def test_promote_copies_to_global(self, store, sample_technique):
        tid = store.add(sample_technique, scope="project", name="promote me")
        new_id = store.promote(tid)
        assert new_id is not None
        global_entry = store.get(new_id, scope="global")
        assert global_entry is not None
        assert global_entry["name"] == "promote me"
        assert global_entry["promoted_from"] == tid

    def test_promote_missing(self, store):
        assert store.promote("nonexistent") is None


class TestPersistence:
    def test_survives_reload(self, tmp_path, sample_technique):
        store1 = TechniqueStore(base_dir=str(tmp_path), project_name="persist_test")
        tid = store1.add(sample_technique, name="persistent", tags=["test"])

        # Create new store instance pointing to same dir
        store2 = TechniqueStore(base_dir=str(tmp_path), project_name="persist_test")
        entry = store2.get(tid)
        assert entry is not None
        assert entry["name"] == "persistent"


class TestListTechniques:
    def test_list_favorites_only(self, store, sample_technique):
        t1 = store.add(sample_technique, name="fav")
        t2 = store.add(sample_technique, name="not fav")
        store.set_favorite(t1, True)
        results = store.list_techniques(scope="project", favorites_only=True)
        assert len(results) == 1
        assert results[0]["name"] == "fav"

    def test_list_by_tags(self, store, sample_technique):
        store.add(sample_technique, name="a", tags=["x"])
        store.add(sample_technique, name="b", tags=["y"])
        results = store.list_techniques(tags=["x"])
        assert len(results) == 1


class TestStats:
    def test_stats(self, store, sample_technique):
        store.add(sample_technique, scope="project")
        store.add(sample_technique, scope="global")
        stats = store.stats()
        assert stats["project_count"] == 1
        assert stats["global_count"] == 1
        assert stats["project_name"] == "test_project"


# ---------------------------------------------------------------------------
# Lazy project-scope rebind (v1.4.4 reliability release)
# Mirrors the PreferenceStore rebind tests — same mechanism, different store.
# ---------------------------------------------------------------------------


class TestRebindProjectScope:
    def test_store_starts_unbound_raises_on_project_save(self, tmp_path, sample_technique):
        store = TechniqueStore(base_dir=str(tmp_path), project_name=None)
        with pytest.raises(ValueError) as exc:
            store.add(sample_technique, scope="project")
        assert "TDPILOT_PROJECT_NAME" in str(exc.value)

    def test_rebind_enables_project_scope(self, tmp_path, sample_technique):
        store = TechniqueStore(base_dir=str(tmp_path), project_name=None)
        assert store.stats()["project_name"] is None

        store.rebind_project_scope("LiveProject")

        assert store.stats()["project_name"] == "LiveProject"
        tid = store.add(sample_technique, scope="project", name="after-rebind")
        assert store.get(tid, scope="project") is not None

    def test_rebind_sanitizes_filesystem_unsafe_chars(self, tmp_path, sample_technique):
        store = TechniqueStore(base_dir=str(tmp_path), project_name=None)
        store.rebind_project_scope("My Project/v2!")
        store.add(sample_technique, scope="project", name="test")
        assert (tmp_path / "projects" / "My_Project_v2_" / "techniques.json").exists()

    def test_rebind_loads_existing_project_data(self, tmp_path, sample_technique):
        seed = TechniqueStore(base_dir=str(tmp_path), project_name="Preexisting")
        seed_id = seed.add(sample_technique, scope="project", name="seeded")

        store = TechniqueStore(base_dir=str(tmp_path), project_name=None)
        store.rebind_project_scope("Preexisting")
        assert store.get(seed_id, scope="project") is not None
        assert store.get(seed_id, scope="project")["name"] == "seeded"


class TestTokenizedSearchRanking:
    """v2.0.4 search upgrade: tokenized OR-matching ranked by hit count.

    Exact-phrase (legacy substring) matches keep the top rank; entries
    matching only SOME query tokens are still returned (OR), ranked below
    all-token matches.
    """

    def _seed(self, store):
        store.add({"node_count": 1}, name="feedback displacement bloom", tags=["feedback", "bloom"])
        store.add({"node_count": 1}, name="plain feedback loop", tags=["feedback", "trails"])
        store.add({"node_count": 1}, name="edge glow composite", tags=["edge", "glow"])
        store.add({"node_count": 1}, name="lfo param wobble", tags=["lfo", "modulation"])

    def test_or_matching_returns_partial_token_hits(self, store):
        self._seed(store)

        results = store.search(query="feedback glow", scope="project")
        names = [r["name"] for r in results]

        # OR semantics: entries matching either token appear.
        assert "plain feedback loop" in names
        assert "edge glow composite" in names
        assert "lfo param wobble" not in names

    def test_exact_phrase_ranks_highest(self, store):
        self._seed(store)

        results = store.search(query="feedback displacement bloom", scope="project")

        assert results[0]["name"] == "feedback displacement bloom"
        # OR-match: the partial-token entry is still returned, ranked lower.
        assert any(r["name"] == "plain feedback loop" for r in results)

    def test_all_token_match_outranks_single_token_match(self, store):
        self._seed(store)

        results = store.search(query="feedback bloom", scope="project")
        names = [r["name"] for r in results]

        assert names[0] == "feedback displacement bloom"  # both tokens
        assert "plain feedback loop" in names  # one token, ranked below

    def test_no_token_match_returns_nothing(self, store):
        self._seed(store)

        assert store.search(query="quaternion sdf raymarch", scope="project") == []

    def test_single_word_substring_behavior_preserved(self, store):
        self._seed(store)

        results = store.search(query="feedback", scope="project")
        names = {r["name"] for r in results}

        assert names == {"feedback displacement bloom", "plain feedback loop"}

    def test_empty_query_lists_all(self, store):
        self._seed(store)

        assert len(store.search(query="", scope="project")) == 4
