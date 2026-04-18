"""Tests for the CardIndex, Provenance, and knowledge package."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from td_mcp.knowledge.card_index import CardIndex
from td_mcp.knowledge.freshness import Provenance

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_cards_dir(tmp_path: Path) -> Path:
    """Create a temporary cards directory with sample JSON cards."""
    # -- operators --
    ops_dir = tmp_path / "operators"
    ops_dir.mkdir()

    (ops_dir / "noiseTOP.json").write_text(
        json.dumps(
            {
                "card_type": "operator",
                "op_type": "noiseTOP",
                "family": "TOP",
                "display_name": "Noise TOP",
                "summary": "Generates procedural noise patterns.",
                "build_relevance": "2025.30000+",
                "last_verified": "2026-03-14",
            }
        )
    )

    (ops_dir / "feedbackTOP.json").write_text(
        json.dumps(
            {
                "card_type": "operator",
                "op_type": "feedbackTOP",
                "family": "TOP",
                "display_name": "Feedback TOP",
                "summary": "Creates feedback loops for TOPs.",
                "build_relevance": "2025.30000+",
            }
        )
    )

    (ops_dir / "waveCHOP.json").write_text(
        json.dumps(
            {
                "card_type": "operator",
                "op_type": "waveCHOP",
                "family": "CHOP",
                "display_name": "Wave CHOP",
                "summary": "Generates wave patterns as channel data.",
                "build_relevance": "2023.10000+",
            }
        )
    )

    # -- palette --
    pal_dir = tmp_path / "palette"
    pal_dir.mkdir()

    (pal_dir / "callbacksHelper.json").write_text(
        json.dumps(
            {
                "card_type": "palette",
                "component_name": "callbacksHelper",
                "palette_path": "Tools/callbacksHelper",
                "summary": "Standardized callback plumbing for COMPs.",
                "compatibility": "2025.30000+",
                "last_verified": "2026-03-14",
            }
        )
    )

    # -- release --
    rel_dir = tmp_path / "release"
    rel_dir.mkdir()

    (rel_dir / "2025_32460.json").write_text(
        json.dumps(
            {
                "card_type": "release",
                "build": "2025.32460",
                "highlights": ["Text POP", "Trace POP"],
                "new_ops": [{"type": "textPOP", "family": "POP"}],
            }
        )
    )

    # -- snippets (empty for now) --
    (tmp_path / "snippets").mkdir()

    return tmp_path


# ---------------------------------------------------------------------------
# CardIndex tests
# ---------------------------------------------------------------------------


class TestCardIndex:
    def test_load_count(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        assert idx.count() >= 3

    def test_search_finds_matching(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        results = idx.search("noise")
        assert len(results) >= 1
        assert any(c["op_type"] == "noiseTOP" for c in results)

    def test_search_filters_by_family(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        results = idx.search("wave", family="TOP")
        # waveCHOP is family=CHOP, so should be excluded
        assert all(c.get("family", "").upper() == "TOP" for c in results)

    def test_search_family_match(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        results = idx.search("wave", family="CHOP")
        assert len(results) >= 1
        assert any(c["op_type"] == "waveCHOP" for c in results)

    def test_get_operator_found(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        card = idx.get_operator("noiseTOP")
        assert card is not None
        assert card["op_type"] == "noiseTOP"

    def test_get_operator_missing(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        assert idx.get_operator("nonexistentOP") is None

    def test_get_palette_found(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        card = idx.get_palette("callbacksHelper")
        assert card is not None
        assert card["component_name"] == "callbacksHelper"

    def test_get_palette_missing(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        assert idx.get_palette("doesNotExist") is None

    def test_get_release_found(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        card = idx.get_release("2025.32460")
        assert card is not None
        assert card["build"] == "2025.32460"

    def test_get_release_missing(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        assert idx.get_release("9999.99999") is None

    def test_check_compatibility_compatible(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        result = idx.check_compatibility("noiseTOP", "2025.32460")
        assert "status" in result
        assert result["status"] == "compatible"

    def test_check_compatibility_incompatible(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        result = idx.check_compatibility("noiseTOP", "2024.10000")
        assert "status" in result
        assert result["status"] == "incompatible"

    def test_check_compatibility_missing_op(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        result = idx.check_compatibility("nonexistentOP", "2025.30000")
        assert "status" in result
        assert result["status"] == "caution"


# ---------------------------------------------------------------------------
# Provenance tests
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_verified_recent(self) -> None:
        recent = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        p = Provenance(last_verified=recent)
        assert p.confidence == "verified"

    def test_stale_old(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d")
        p = Provenance(last_verified=old)
        assert p.confidence == "stale"

    def test_unverified_no_date(self) -> None:
        p = Provenance()
        assert p.confidence == "unverified"

    def test_unverified_empty_string(self) -> None:
        p = Provenance(last_verified="")
        assert p.confidence == "unverified"

    def test_to_dict(self) -> None:
        p = Provenance(source="web", last_verified="2026-03-01", td_build="2025.32460")
        d = p.to_dict()
        assert isinstance(d, dict)
        assert d["source"] == "web"
        assert d["td_build"] == "2025.32460"
        assert "confidence" in d

    def test_to_dict_has_all_fields(self) -> None:
        p = Provenance()
        d = p.to_dict()
        expected_keys = {"source", "fetched_at", "last_verified", "td_build", "confidence"}
        assert set(d.keys()) == expected_keys
