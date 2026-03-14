"""Tests for release notes parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp.knowledge.docsbrain.release_parser import (
    build_release_artifacts,
)


@pytest.fixture
def sample_chunks(tmp_path: Path) -> Path:
    """Create a sample chunks.jsonl with release note chunks."""
    chunks = [
        {
            "chunk_id": "release_notes__2025_30000__new_features__0002",
            "page_id": "release_notes__2025_30000",
            "doc_type": "release_notes",
            "section_title": "New Features",
            "operator_name": None,
            "mentioned_operators": ["Text POP", "Trace POP"],
            "build_number": "2025.32460",
            "build_date": "Mar 10, 2026",
            "change_category": "new_feature",
            "content": "Text POP - A new POP. Trace POP - A new POP for tracing.",
            "operator_family": None,
            "parameter_names": [],
            "python_symbols": [],
            "token_estimate": 20,
        },
        {
            "chunk_id": "release_notes__2025_30000__bug_fixes__0003",
            "page_id": "release_notes__2025_30000",
            "doc_type": "release_notes",
            "section_title": "Bug Fixes and Improvements",
            "operator_name": None,
            "mentioned_operators": ["Trail POP", "Movie File In TOP"],
            "build_number": "2025.32460",
            "build_date": "Mar 10, 2026",
            "change_category": "bug_fix",
            "content": "Trail POP - Fixed double-transforming. Movie File In TOP - Fixed ProRes output.",
            "operator_family": None,
            "parameter_names": [],
            "python_symbols": [],
            "token_estimate": 15,
        },
        {
            "chunk_id": "release_notes__2025_30000__bug_fixes_2__0005",
            "page_id": "release_notes__2025_30000",
            "doc_type": "release_notes",
            "section_title": "Bug Fixes and Improvements",
            "operator_name": None,
            "mentioned_operators": ["Count CHOP"],
            "build_number": "2025.32280",
            "build_date": "Jan 20, 2025",
            "change_category": "bug_fix",
            "content": "Count CHOP - Fixed count down pulse issue.",
            "operator_family": None,
            "parameter_names": [],
            "python_symbols": [],
            "token_estimate": 10,
        },
    ]
    path = tmp_path / "chunks.jsonl"
    with open(path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    return path


class TestBuildReleaseArtifacts:
    def test_manifest_has_builds(self, sample_chunks: Path, tmp_path: Path):
        manifest, changelog = build_release_artifacts(sample_chunks, tmp_path)
        assert manifest["latest_build"] == "2025.32460"
        builds = [b["build"] for b in manifest["builds"]]
        assert "2025.32460" in builds
        assert "2025.32280" in builds

    def test_manifest_sorted_newest_first(self, sample_chunks: Path, tmp_path: Path):
        manifest, _ = build_release_artifacts(sample_chunks, tmp_path)
        builds = manifest["builds"]
        assert builds[0]["build"] == "2025.32460"

    def test_changelog_maps_operators(self, sample_chunks: Path, tmp_path: Path):
        _, changelog = build_release_artifacts(sample_chunks, tmp_path)
        assert "Trail POP" in changelog
        assert changelog["Trail POP"][0]["category"] == "bug_fix"
        assert "double-transforming" in changelog["Trail POP"][0]["text"]

    def test_changelog_multiple_entries(self, sample_chunks: Path, tmp_path: Path):
        _, changelog = build_release_artifacts(sample_chunks, tmp_path)
        # Text POP and Trace POP should both have entries
        assert "Text POP" in changelog
        assert "Trace POP" in changelog

    def test_artifacts_written_to_disk(self, sample_chunks: Path, tmp_path: Path):
        build_release_artifacts(sample_chunks, tmp_path)
        assert (tmp_path / "build_manifest.json").exists()
        assert (tmp_path / "operator_changelog.json").exists()
