"""Tests for the docs brain chunker."""

from __future__ import annotations

from pathlib import Path

from td_mcp.knowledge.docsbrain.chunker import chunk_page
from td_mcp.knowledge.docsbrain.normalizer import normalize_file

FIXTURES = Path(__file__).parent / "fixtures" / "sample_pages"


class TestChunkPage:
    def test_operator_produces_chunks(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert page is not None
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        assert len(chunks) >= 2  # At least summary + parameters

    def test_chunk_has_required_fields(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        required = {
            "chunk_id",
            "page_id",
            "doc_type",
            "section_title",
            "operator_family",
            "operator_name",
            "mentioned_operators",
            "parameter_names",
            "python_symbols",
            "build_number",
            "build_date",
            "change_category",
            "token_estimate",
            "content",
        }
        for chunk in chunks:
            assert required.issubset(chunk.keys()), f"Missing: {required - chunk.keys()}"

    def test_chunk_ids_are_unique(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_ids_contain_page_id(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["chunk_id"].startswith("composite_top__")

    def test_operator_name_propagated(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["operator_name"] == "Composite TOP"

    def test_token_estimate_reasonable(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["token_estimate"] > 0
            # No chunk should be absurdly large for this small fixture
            assert chunk["token_estimate"] < 5000


class TestReleaseNoteChunks:
    def test_release_notes_produce_chunks(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        assert page is not None
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        assert len(chunks) >= 2

    def test_release_chunks_have_build_numbers(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        # At least some chunks should have build numbers
        build_chunks = [c for c in chunks if c["build_number"]]
        assert len(build_chunks) >= 1

    def test_release_chunks_have_mentioned_operators(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        # At least one chunk should mention operators
        op_chunks = [c for c in chunks if c["mentioned_operators"]]
        assert len(op_chunks) >= 1

    def test_release_chunks_have_change_category(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        cats = {c["change_category"] for c in chunks if c["change_category"]}
        # Should detect at least new_feature and bug_fix
        assert "new_feature" in cats or "bug_fix" in cats
