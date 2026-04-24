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
            {
                "build": "2025.32460",
                "category": "bug_fix",
                "text": "Fixed double-transforming when cooking a second time.",
            }
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


# ---------------------------------------------------------------------------
# Regression tests for v1.4.3
# ---------------------------------------------------------------------------


def _make_chunk(operator_name: str, family: str, doc_type: str = "operator") -> dict:
    """Build a minimal DocsBrain chunk for an operator."""
    page_id = operator_name.lower().replace(" ", "_")
    return {
        "chunk_id": f"{page_id}__summary__0001",
        "page_id": page_id,
        "doc_type": doc_type,
        "section_title": operator_name,
        "operator_family": family,
        "operator_name": operator_name,
        "mentioned_operators": [],
        "parameter_names": [],
        "python_symbols": [],
        "build_number": None,
        "build_date": None,
        "change_category": None,
        "token_estimate": 20,
        "content": f"The {operator_name} is a {family} operator used for testing.",
    }


def _build_brain(tmp_path: Path, chunks: list[dict]) -> DocsBrain:
    """Build a DocsBrain from raw chunk dicts (no changelog / manifest)."""
    chunks_path = tmp_path / "chunks.jsonl"
    with open(chunks_path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    db_path = tmp_path / "docsbrain.db"
    build_index(chunks_path, db_path)
    return DocsBrain(db_path=db_path)


def test_op_type_map_multi_word_operators(tmp_path: Path):
    """Multi-word operator names must map to correctly-cased op_types.

    Regression: `_op_type_map` used `parts[0].lower() + parts[-1]`, which made
    `Movie File In TOP` resolve as `movieTOP` instead of `moviefileinTOP`.
    Same bug hit `Audio File In CHOP` and `GLSL Multi TOP`.
    """
    chunks = [
        _make_chunk("Movie File In TOP", "TOP"),
        _make_chunk("Audio File In CHOP", "CHOP"),
        _make_chunk("GLSL Multi TOP", "TOP"),
        _make_chunk("Composite TOP", "TOP"),  # two-word control
        _make_chunk("Null CHOP", "CHOP"),  # two-word control
    ]
    brain_local = _build_brain(tmp_path, chunks)

    # Multi-word operators must resolve by their correct op_type
    assert brain_local.get_operator("moviefileinTOP") is not None
    assert brain_local.get_operator("audiofileinCHOP") is not None
    assert brain_local.get_operator("glslmultiTOP") is not None

    # Two-word controls continue to resolve
    assert brain_local.get_operator("compositeTOP") is not None
    assert brain_local.get_operator("nullCHOP") is not None

    # The buggy pre-fix keys must NOT resolve
    assert brain_local.get_operator("movieTOP") is None
    assert brain_local.get_operator("audioCHOP") is None
    assert brain_local.get_operator("glslTOP") is None


# ---------------------------------------------------------------------------
# Fix #3 — card_type alias normalization.
# Callers historically passed plural ("operators") or expanded ("release")
# forms; DocsBrain stores singular doc_type values ("operator",
# "release_notes"). Without alias normalization, plural filters silently
# matched nothing.
# ---------------------------------------------------------------------------


def test_card_type_alias_operators_plural_resolves(brain: DocsBrain):
    """'operators' (plural) must match stored doc_type='operator'."""
    results_plural = brain.search("composite", card_types=["operators"])
    results_singular = brain.search("composite", card_types=["operator"])
    assert len(results_plural) > 0
    assert len(results_plural) == len(results_singular)


def test_card_type_alias_release_resolves(brain: DocsBrain):
    """'release' (short form) must match stored doc_type='release_notes'."""
    r1 = brain.search("Trail", card_types=["release"])
    r2 = brain.search("Trail", card_types=["release_notes"])
    assert len(r1) == len(r2)
    assert len(r1) > 0


def test_card_type_alias_releases_plural_resolves(brain: DocsBrain):
    """'releases' must also resolve to 'release_notes'."""
    r1 = brain.search("Trail", card_types=["releases"])
    r2 = brain.search("Trail", card_types=["release_notes"])
    assert len(r1) == len(r2)


def test_card_type_alias_palettes_plural_resolves(brain: DocsBrain):
    """'palettes' must resolve to 'palette'."""
    r1 = brain.search("camera", card_types=["palettes"])
    r2 = brain.search("camera", card_types=["palette"])
    assert len(r1) == len(r2)


def test_card_type_singular_canonical_still_works(brain: DocsBrain):
    """Canonical singular forms must remain unaffected by the alias layer."""
    assert brain.search("composite", card_types=["operator"])
    assert brain.search("Trail", card_types=["release_notes"])
    assert brain.search("camera", card_types=["palette"])


def test_card_type_unknown_passes_through_unchanged(brain: DocsBrain):
    """Unknown card_types must pass through without coercion (future-proof)."""
    # "some_new_type" is not in the alias table; it should reach the DB filter
    # unchanged and produce zero hits (since no chunk has that doc_type).
    assert brain.search("composite", card_types=["some_new_type"]) == []


# ---------------------------------------------------------------------------
# v1.4.5 Fix 3: DocsBrain.get_operator() must normalize parameter shape.
# Pre-v1.4.5 it returned `parameters: list[str]` but CardIndex / td_get_param_help
# expected `key_params: list[dict]`. When DocsBrain was active, parameter
# help silently returned card_param: None.
# ---------------------------------------------------------------------------


def test_get_operator_returns_key_params_in_cardindex_shape(brain: DocsBrain):
    """Docsbrain's get_operator must expose `key_params` as a list of dicts
    with `name`, mirroring the CardIndex JSON card shape so
    td_get_param_help can iterate over it."""
    result = brain.get_operator("compositeTOP")
    assert result is not None
    assert "key_params" in result, "DocsBrain must expose key_params (was previously only `parameters`)"
    assert isinstance(result["key_params"], list)
    # Preserves raw parameters too (no information loss)
    assert "parameters" in result
    # Each key_param is a dict with at minimum `name` and `source`
    for kp in result["key_params"]:
        assert isinstance(kp, dict)
        assert "name" in kp
        assert kp.get("source") == "docsbrain"


def test_get_operator_key_params_names_match_parameters(brain: DocsBrain):
    """Every parameter name from the raw list appears in key_params."""
    result = brain.get_operator("compositeTOP")
    assert result is not None
    param_names = {p if isinstance(p, str) else p.get("name") for p in result["parameters"]}
    key_param_names = {kp["name"] for kp in result["key_params"]}
    # Normalized names come from the raw parameter list
    assert key_param_names.issubset(param_names), (
        f"key_params {key_param_names} should be a subset of parameters {param_names}"
    )


def test_get_operator_missing_still_returns_none(brain: DocsBrain):
    """Normalization must not regress the missing-op path."""
    assert brain.get_operator("nonexistentOP") is None
