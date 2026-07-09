"""Smoke tests for KnowledgeStore — local-only markdown knowledge entries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp.memory.knowledge_store import MAX_BODY_BYTES, KnowledgeStore


@pytest.fixture
def store(tmp_path: Path) -> KnowledgeStore:
    return KnowledgeStore(base_dir=str(tmp_path), project_name="UnitTestProj")


def test_add_get_roundtrip(store: KnowledgeStore) -> None:
    body = "# Title\n\nSome **markdown** body with `code` and an equation: $x^2 + y^2 = z^2$."
    eid = store.add(
        body,
        name="Pythagorean essay",
        description="Classic identity",
        tags=["math", "geometry"],
        source="textbook",
    )
    assert isinstance(eid, str) and len(eid) > 8

    fetched = store.get(eid, scope="project")
    assert fetched is not None
    assert fetched["body"] == body
    assert fetched["name"] == "Pythagorean essay"
    assert fetched["description"] == "Classic identity"
    assert fetched["tags"] == ["geometry", "math"]  # sorted lowercased
    assert fetched["source"] == "textbook"
    assert fetched["body_bytes"] == len(body.encode("utf-8"))


def test_search_metadata_only(store: KnowledgeStore) -> None:
    a = store.add("body A", name="alpha", tags=["foo"])
    b = store.add("body B", name="beta", tags=["bar"])
    c = store.add("body C", name="gamma", tags=["foo", "bar"])

    by_query = store.search(query="alpha")
    assert {r["id"] for r in by_query} == {a}

    by_tag = store.search(tags=["foo"])
    assert {r["id"] for r in by_tag} == {a, c}

    both = store.search(tags=["bar"], query="gamma")
    assert {r["id"] for r in both} == {c}

    none = store.search(query="zzzz")
    assert none == []
    _ = b  # suppress unused warning


def test_search_full_text_reads_body(store: KnowledgeStore) -> None:
    eid = store.add("the magic word is foobarbaz", name="needle", tags=[])
    assert store.search(query="foobarbaz") == []  # not in metadata
    full = store.search(query="foobarbaz", full_text=True)
    assert len(full) == 1 and full[0]["id"] == eid


def test_update_metadata_and_body(store: KnowledgeStore) -> None:
    eid = store.add("v1", name="orig")
    assert store.update(eid, {"name": "renamed", "tags": ["X", "Y"]})
    after = store.get(eid)
    assert after is not None and after["name"] == "renamed"
    assert after["tags"] == ["x", "y"]

    assert store.update_body(eid, "v2 markdown")
    after2 = store.get(eid)
    assert after2 is not None and after2["body"] == "v2 markdown"
    assert after2["body_bytes"] == len(b"v2 markdown")


def test_delete_removes_body_file(store: KnowledgeStore) -> None:
    eid = store.add("to delete")
    body_path = (
        Path(store._project_dir)  # type: ignore[arg-type]
        / "entries"
        / f"{eid}.md"
    )
    assert body_path.exists()
    assert store.delete(eid)
    assert not body_path.exists()
    assert store.get(eid) is None


def test_promote_project_to_global(store: KnowledgeStore) -> None:
    eid = store.add("for global", name="winner", tags=["good"])
    new_id = store.promote(eid)
    assert new_id is not None
    assert new_id != eid
    promoted = store.get(new_id, scope="global")
    assert promoted is not None
    assert promoted["body"] == "for global"
    assert promoted["promoted_from"] == eid
    # Project copy still exists.
    assert store.get(eid, scope="project") is not None


def test_favorite_and_rating(store: KnowledgeStore) -> None:
    eid = store.add("rate me")
    assert store.set_favorite(eid, True)
    assert store.set_rating(eid, 4)
    summary = store.list_entries()[0]
    assert summary["favorite"] is True
    assert summary["rating"] == 4
    assert store.set_rating(eid, 99)  # gets clamped
    assert store.list_entries()[0]["rating"] == 5


def test_body_size_cap_enforced(store: KnowledgeStore) -> None:
    huge = "x" * (MAX_BODY_BYTES + 1)
    with pytest.raises(ValueError):
        store.add(huge)


def test_persistence_across_instances(tmp_path: Path) -> None:
    s1 = KnowledgeStore(base_dir=str(tmp_path), project_name="ProjectX")
    eid = s1.add(
        "persist me",
        name="memory test",
        tags=["persistence"],
    )
    s2 = KnowledgeStore(base_dir=str(tmp_path), project_name="ProjectX")
    again = s2.get(eid)
    assert again is not None and again["body"] == "persist me"
    assert again["name"] == "memory test"


def test_index_json_format(store: KnowledgeStore) -> None:
    eid = store.add("body", name="x", tags=["t"])
    index_path = Path(store._project_dir) / "index.json"  # type: ignore[arg-type]
    raw = json.loads(index_path.read_text())
    assert eid in raw
    rec = raw[eid]
    assert rec["body_path"] == f"entries/{eid}.md"
    assert "created_at" in rec
    assert rec["tags"] == ["t"]


def test_list_entries_filters(store: KnowledgeStore) -> None:
    a = store.add("a", name="A", tags=["x"])
    b = store.add("b", name="B", tags=["y"])
    store.set_favorite(b, True)

    favs = store.list_entries(favorites_only=True)
    assert {r["id"] for r in favs} == {b}

    by_tag = store.list_entries(tags=["x"])
    assert {r["id"] for r in by_tag} == {a}


def test_default_base_dir_is_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ensures the default storage path is always under the user's home."""
    home = tmp_path / "fake_home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # windows expanduser
    s = KnowledgeStore(project_name="LocalCheck")
    assert str(s._base).startswith(str(home))
    assert "tdpilot/knowledge" in str(s._base).replace("\\", "/")
