"""Tests for DocsBrain search — the runtime query interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp.knowledge.docsbrain import DocsBrain
from td_mcp.knowledge.docsbrain.indexer import build_index


@pytest.fixture
def brain(tmp_path: Path) -> DocsBrain:
    """Build a small DocsBrain from test chunks."""
    chunks = [
        {
            "chunk_id": "composite_top__summary__0001",
            "page_id": "composite_top",
            "doc_type": "operator",
            "section_title": "Composite TOP",
            "operator_family": "TOP",
            "operator_name": "Composite TOP",
            "mentioned_operators": [],
            "parameter_names": ["operand", "opacity"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 50,
            "content": "The Composite TOP combines two or more texture inputs using blend operations like Over, Add, Multiply.",
        },
        {
            "chunk_id": "composite_top__parameters__0002",
            "page_id": "composite_top",
            "doc_type": "operator",
            "section_title": "Parameters",
            "operator_family": "TOP",
            "operator_name": "Composite TOP",
            "mentioned_operators": [],
            "parameter_names": ["operand", "opacity", "prefit"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 30,
            "content": "Operand - Blend mode. Opacity - Master opacity. Pre Fit - Resolution mismatch handling.",
        },
        {
            "chunk_id": "feedback_top__summary__0001",
            "page_id": "feedback_top",
            "doc_type": "operator",
            "section_title": "Feedback TOP",
            "operator_family": "TOP",
            "operator_name": "Feedback TOP",
            "mentioned_operators": [],
            "parameter_names": ["top"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 40,
            "content": "The Feedback TOP creates feedback loops for TOPs. Set the top parameter to reference the downstream node.",
        },
        {
            "chunk_id": "wave_chop__summary__0001",
            "page_id": "wave_chop",
            "doc_type": "operator",
            "section_title": "Wave CHOP",
            "operator_family": "CHOP",
            "operator_name": "Wave CHOP",
            "mentioned_operators": [],
            "parameter_names": ["type", "frequency"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 30,
            "content": "Generates waveforms as channel data. Sine, square, triangle, ramp patterns.",
        },
        {
            "chunk_id": "release_notes__bug_fixes__0001",
            "page_id": "release_notes__2025_30000",
            "doc_type": "release_notes",
            "section_title": "Bug Fixes and Improvements",
            "operator_family": None,
            "operator_name": None,
            "mentioned_operators": ["Trail POP"],
            "parameter_names": [],
            "python_symbols": [],
            "build_number": "2025.32460",
            "build_date": "Mar 10, 2026",
            "change_category": "bug_fix",
            "token_estimate": 20,
            "content": "Trail POP - Fixed double-transforming when cooking a second time.",
        },
        {
            "chunk_id": "palette_camschnappr__summary__0001",
            "page_id": "palette:camschnappr",
            "doc_type": "palette",
            "section_title": "camSchnappr",
            "operator_family": None,
            "operator_name": None,
            "mentioned_operators": [],
            "parameter_names": [],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 25,
            "content": "Camera snapshot tool for capturing and restoring camera positions.",
        },
    ]

    # Write chunks and build index
    chunks_path = tmp_path / "chunks.jsonl"
    with open(chunks_path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")

    db_path = tmp_path / "docsbrain.db"
    build_index(chunks_path, db_path)

    # Write changelog and manifest for DocsBrain
    changelog = {
        "Trail POP": [
            {"build": "2025.32460", "category": "bug_fix",
             "text": "Fixed double-transforming when cooking a second time."}
        ]
    }
    manifest = {
        "latest_build": "2025.32460",
        "latest_date": "Mar 10, 2026",
        "builds": [{"build": "2025.32460", "date": "Mar 10, 2026"}],
    }
    (tmp_path / "operator_changelog.json").write_text(json.dumps(changelog))
    (tmp_path / "build_manifest.json").write_text(json.dumps(manifest))

    return DocsBrain(
        db_path=db_path,
        changelog_path=tmp_path / "operator_changelog.json",
        manifest_path=tmp_path / "build_manifest.json",
    )


class TestDocsBrainSearch:
    def test_search_finds_operator_by_name(self, brain: DocsBrain):
        results = brain.search("Composite TOP")
        assert len(results) >= 1
        assert any(r["operator_name"] == "Composite TOP" for r in results)

    def test_search_finds_by_parameter(self, brain: DocsBrain):
        results = brain.search("opacity")
        assert len(results) >= 1

    def test_search_filters_by_family(self, brain: DocsBrain):
        results = brain.search("wave", family="CHOP")
        assert len(results) >= 1
        assert all(r.get("operator_family") == "CHOP" for r in results if r.get("operator_family"))

    def test_search_limits_results(self, brain: DocsBrain):
        results = brain.search("TOP", limit=2)
        assert len(results) <= 2

    def test_count(self, brain: DocsBrain):
        assert brain.count() >= 5


class TestDocsBrainGetOperator:
    def test_get_operator_found(self, brain: DocsBrain):
        result = brain.get_operator("compositeTOP")
        assert result is not None
        assert result["op_type"] == "compositeTOP"
        assert result["family"] == "TOP"

    def test_get_operator_missing(self, brain: DocsBrain):
        assert brain.get_operator("nonexistentOP") is None

    def test_get_operator_has_recent_changes(self, brain: DocsBrain):
        result = brain.get_operator("compositeTOP")
        if result:
            assert "op_type" in result
            assert "family" in result
            assert "display_name" in result


class TestDocsBrainGetRelease:
    def test_get_release_found(self, brain: DocsBrain):
        result = brain.get_release("2025.32460")
        assert result is not None
        assert result["build"] == "2025.32460"
        assert "entries" in result

    def test_get_release_missing(self, brain: DocsBrain):
        assert brain.get_release("9999.99999") is None


class TestDocsBrainGetPalette:
    def test_get_palette_found(self, brain: DocsBrain):
        result = brain.get_palette("camSchnappr")
        assert result is not None

    def test_get_palette_missing(self, brain: DocsBrain):
        assert brain.get_palette("nonexistent") is None


class TestDocsBrainChangelog:
    def test_get_operator_changelog(self, brain: DocsBrain):
        entries = brain.get_operator_changelog("Trail POP")
        assert len(entries) >= 1
        assert entries[0]["category"] == "bug_fix"

    def test_get_build_manifest(self, brain: DocsBrain):
        manifest = brain.get_build_manifest()
        assert manifest["latest_build"] == "2025.32460"
        assert len(manifest["builds"]) >= 1


class TestDocsBrainCompatibility:
    def test_check_compatibility(self, brain: DocsBrain):
        result = brain.check_compatibility("compositeTOP", "2025.32460")
        assert "status" in result
