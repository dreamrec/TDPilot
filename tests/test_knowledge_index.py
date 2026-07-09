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

    # -- snippets --
    snip_dir = tmp_path / "snippets"
    snip_dir.mkdir()

    (snip_dir / "GLSL_snippets.json").write_text(
        json.dumps(
            {
                "card_type": "snippet",
                "snippet_id": "GLSL_snippets",
                "family": "GLSL",
                "summary": "TouchDesigner GLSL shader templates.",
                "official_examples": [
                    {
                        "example_id": "op_snippets_glsl_pop_attribute_compute",
                        "display_name": "GLSL POP selected-class attribute compute OP Snippets",
                        "family": "GLSL",
                        "operators": ["glslPOP"],
                        "topics": ["GLSL POP attribute shader", "TDIndex", "TDNumElements"],
                        "source_url": "https://docs.derivative.ca/OP_Snippets",
                    }
                ],
            }
        )
    )

    # -- articles --
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()

    (articles_dir / "write_a_glsl_pop.json").write_text(
        json.dumps(
            {
                "card_type": "article",
                "article_id": "write_a_glsl_pop",
                "title": "Write a GLSL POP",
                "family": "GLSL",
                "families": ["GLSL", "POP"],
                "summary": "Official guide to GLSL POP and GLSL Advanced POP compute shaders.",
                "source_url": "https://docs.derivative.ca/Write_a_GLSL_POP",
                "covered_operators": ["glslPOP", "glsladvancedPOP"],
                "key_concepts": ["TDIndex", "TDNumElements", "Output Attributes"],
            }
        )
    )

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

    def test_search_matches_nested_snippet_metadata_with_related_family(
        self,
        sample_cards_dir: Path,
    ) -> None:
        idx = CardIndex(sample_cards_dir)
        results = idx.search("GLSL POP attribute shader", card_types=["snippets"], family="POP")

        assert results
        assert results[0]["snippet_id"] == "GLSL_snippets"

    def test_search_and_lookup_article_cards(self, sample_cards_dir: Path) -> None:
        idx = CardIndex(sample_cards_dir)
        results = idx.search("TDIndex output attributes", card_types=["articles"], family="POP")

        assert results
        assert results[0]["article_id"] == "write_a_glsl_pop"
        assert idx.get_article("write_a_glsl_pop")["title"] == "Write a GLSL POP"

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


# ---------------------------------------------------------------------------
# v2.0.4: OR-with-AND-boost ranking + synonym expansion (compact default path)
# ---------------------------------------------------------------------------


class TestSynonymModule:
    def test_expand_query_tokens_prepends_original(self) -> None:
        from td_mcp.knowledge.synonyms import expand_query_tokens

        groups = expand_query_tokens(["glow", "noise"])
        assert groups[0][0] == "glow"
        assert "bloom" in groups[0]
        assert groups[1] == ("noise",)

    def test_synonyms_for_unknown_token_is_empty(self) -> None:
        from td_mcp.knowledge.synonyms import synonyms_for

        assert synonyms_for("noise") == ()
        assert "mirror" in synonyms_for("kaleidoscope")


class TestOrRankingAndSynonyms:
    @pytest.fixture
    def retrieval_cards_dir(self, tmp_path: Path) -> Path:
        ops_dir = tmp_path / "operators"
        ops_dir.mkdir()
        cards = [
            {
                "card_type": "operator",
                "op_type": "bloomTOP",
                "family": "TOP",
                "display_name": "Bloom TOP",
                "summary": "Adds a bloom effect to bright areas of the image.",
            },
            {
                "card_type": "operator",
                "op_type": "audiodeviceinCHOP",
                "family": "CHOP",
                "display_name": "Audio Device In CHOP",
                "summary": "Receives audio from a microphone or input device.",
            },
            {
                "card_type": "operator",
                "op_type": "noiseTOP",
                "family": "TOP",
                "display_name": "Noise TOP",
                "summary": "Generates procedural noise patterns.",
            },
            {
                "card_type": "operator",
                "op_type": "feedbacknoiseTOP",
                "family": "TOP",
                "display_name": "Feedback Noise Combo TOP",
                "summary": "Feedback loops combined with noise patterns.",
            },
        ]
        for card in cards:
            (ops_dir / f"{card['op_type']}.json").write_text(json.dumps(card))
        return tmp_path

    def test_synonym_expansion_finds_bloom_for_glow(self, retrieval_cards_dir: Path) -> None:
        idx = CardIndex(retrieval_cards_dir)
        results = idx.search("glow")
        assert results, "synonym expansion should retrieve the bloom card for 'glow'"
        assert results[0]["op_type"] == "bloomTOP"

    def test_synonym_expansion_finds_audio_for_sound(self, retrieval_cards_dir: Path) -> None:
        idx = CardIndex(retrieval_cards_dir)
        results = idx.search("sound input")
        assert any(card["op_type"] == "audiodeviceinCHOP" for card in results)

    def test_multi_token_or_returns_partial_matches(self, retrieval_cards_dir: Path) -> None:
        idx = CardIndex(retrieval_cards_dir)
        results = idx.search("feedback noise")
        names = [card["op_type"] for card in results]
        # AND match ranks first; single-token (OR) match still returned.
        assert names[0] == "feedbacknoiseTOP"
        assert "noiseTOP" in names

    def test_all_token_match_outranks_partial_match(self, retrieval_cards_dir: Path) -> None:
        idx = CardIndex(retrieval_cards_dir)
        results = idx.search("noise patterns procedural")
        assert results[0]["op_type"] == "noiseTOP"


class TestShippedCorpusRetrieval:
    """End-to-end sanity on the real shipped card corpus."""

    @pytest.fixture(scope="class")
    def shipped_index(self) -> CardIndex:
        cards_dir = Path(__file__).resolve().parents[1] / "src" / "td_mcp" / "knowledge" / "cards"
        return CardIndex(cards_dir)

    def test_glow_query_reaches_bloom_top(self, shipped_index: CardIndex) -> None:
        results = shipped_index.search("glow", card_types=["operators"], limit=10)
        assert any(card.get("op_type") == "bloomTOP" for card in results)

    def test_warp_query_reaches_displace_top(self, shipped_index: CardIndex) -> None:
        results = shipped_index.search("warp image", card_types=["operators"], limit=10)
        assert any(card.get("op_type") == "displaceTOP" for card in results)

    def test_particles_query_reaches_pop_family(self, shipped_index: CardIndex) -> None:
        results = shipped_index.search("particles", card_types=["operators"], limit=10)
        assert any(str(card.get("op_type", "")).endswith("POP") for card in results)
