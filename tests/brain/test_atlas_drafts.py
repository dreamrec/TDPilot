from __future__ import annotations

import json
from pathlib import Path

from td_mcp.brain.atlas_drafts import draft_missing_operator_cards, write_operator_card_drafts
from td_mcp.knowledge.docsbrain.indexer import build_index


def _write_docsbrain(root: Path, chunks: list[dict]) -> None:
    data_dir = root / "data" / "normalized" / "derivative"
    data_dir.mkdir(parents=True)
    chunks_path = data_dir / "chunks.jsonl"
    chunks_path.write_text("\n".join(json.dumps(chunk) for chunk in chunks) + "\n", encoding="utf-8")
    build_index(chunks_path, data_dir / "docsbrain.db")


def _write_existing_card(root: Path, op_type: str, family: str = "TOP") -> None:
    cards_dir = root / "src" / "td_mcp" / "knowledge" / "cards" / "operators"
    cards_dir.mkdir(parents=True, exist_ok=True)
    (cards_dir / f"{op_type}.json").write_text(
        json.dumps(
            {
                "card_type": "operator",
                "op_type": op_type,
                "family": family,
                "display_name": "Existing Operator",
                "docs_url": "https://docs.derivative.ca/Existing_Operator",
                "summary": "Already reviewed.",
                "key_params": [{"name": "existing", "type": "Toggle", "note": "Already reviewed"}],
                "common_gotchas": ["Already reviewed."],
            }
        ),
        encoding="utf-8",
    )


def test_draft_missing_operator_cards_from_docsbrain_chunks(tmp_path: Path) -> None:
    _write_existing_card(tmp_path, "existingTOP")
    _write_docsbrain(
        tmp_path,
        [
            {
                "chunk_id": "direct_display_out_top__summary__0001",
                "page_id": "direct_display_out_top",
                "doc_type": "operator",
                "section_title": "Summary",
                "operator_family": "TOP",
                "operator_name": "Direct Display Out TOP",
                "mentioned_operators": [],
                "parameter_names": ["The Direct Display Out\nTOP\noutputs directly"],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 30,
                "content": (
                    "NOTE License: Only available in TouchDesigner Educational, Commercial and Pro. "
                    "The Direct Display Out TOP outputs directly to a selected display using Vulkan."
                ),
            },
            {
                "chunk_id": "direct_display_out_top__parameters_common_page__0002",
                "page_id": "direct_display_out_top",
                "doc_type": "operator",
                "section_title": "Parameters - Common Page",
                "operator_family": "TOP",
                "operator_name": "Direct Display Out TOP",
                "mentioned_operators": [],
                "parameter_names": [
                    "Output\nResolution\noutputresolution",
                    "Use Input\nuseinput",
                ],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 20,
                "content": "Common TOP parameters should not outrank operator-specific controls.",
            },
            {
                "chunk_id": "direct_display_out_top__parameters_direct_display_out_page__0003",
                "page_id": "direct_display_out_top",
                "doc_type": "operator",
                "section_title": "Parameters - Direct Display Out Page",
                "operator_family": "TOP",
                "operator_name": "Direct Display Out TOP",
                "mentioned_operators": [],
                "parameter_names": [
                    "Active\nactive",
                    "Display\ndisplay",
                    "Hardware\nFrame",
                    "Off",
                ],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 20,
                "content": (
                    "Active\nactive\n- Controls if the output is currently active.\n"
                    "Display\ndisplay\n- Select which display to output to.\n"
                    "Hardware\nFrame\n-Lock\nhwframelock\n- Enables Hardware Frame Lock."
                ),
            },
            {
                "chunk_id": "existing_top__summary__0001",
                "page_id": "existing_top",
                "doc_type": "operator",
                "section_title": "Summary",
                "operator_family": "TOP",
                "operator_name": "Existing TOP",
                "mentioned_operators": [],
                "parameter_names": ["Existing\nexisting"],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 10,
                "content": "Existing card should not be drafted.",
            },
            {
                "chunk_id": "write_a_glsl_top__summary__0001",
                "page_id": "write_a_glsl_top",
                "doc_type": "operator",
                "section_title": "Summary",
                "operator_family": "TOP",
                "operator_name": "Write a GLSL TOP",
                "mentioned_operators": [],
                "parameter_names": [],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 10,
                "content": "Article page, not a creatable operator.",
            },
            {
                "chunk_id": "anatomy_of_a_chop__summary__0001",
                "page_id": "anatomy_of_a_chop",
                "doc_type": "operator",
                "section_title": "Summary",
                "operator_family": "CHOP",
                "operator_name": "Anatomy of a CHOP",
                "mentioned_operators": [],
                "parameter_names": [],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 10,
                "content": "Article page about CHOP structure, not a creatable operator.",
            },
            {
                "chunk_id": "band_eq_chop__summary__0001",
                "page_id": "band_eq_chop",
                "doc_type": "operator",
                "section_title": "Summary",
                "operator_family": "CHOP",
                "operator_name": "Band EQ CHOP",
                "mentioned_operators": [],
                "parameter_names": [],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 10,
                "content": "The Band EQ CHOP has been replaced by the Audio Band EQ CHOP. Please use Audio Band EQ CHOP in the future.",
            },
        ],
    )

    drafts = draft_missing_operator_cards(tmp_path, limit=10)

    assert [draft["op_type"] for draft in drafts] == ["directdisplayoutTOP"]
    draft = drafts[0]
    assert draft["card_type"] == "operator_draft"
    assert draft["target_card_type"] == "operator"
    assert draft["family"] == "TOP"
    assert draft["display_name"] == "Direct Display Out TOP"
    assert draft["docs_url"] == "https://docs.derivative.ca/Direct_Display_Out_TOP"
    assert draft["summary"].startswith("NOTE License")
    assert {param["name"] for param in draft["key_params"]} == {"active", "display", "hwframelock"}
    assert all(param["source"] == "docsbrain" for param in draft["key_params"])
    assert draft["review_status"] == "needs_manual_enrichment"
    assert "manual" in draft["common_gotchas"][0].lower()
    assert "hardware" in " ".join(draft["common_gotchas"]).lower()
    assert draft["provenance"]["summary_chunk_id"] == "direct_display_out_top__summary__0001"
    assert draft["provenance"]["parameter_chunk_ids"] == [
        "direct_display_out_top__parameters_direct_display_out_page__0003"
    ]


def test_draft_missing_operator_cards_can_target_specific_ops(tmp_path: Path) -> None:
    _write_docsbrain(
        tmp_path,
        [
            {
                "chunk_id": "wave_chop__summary__0001",
                "page_id": "wave_chop",
                "doc_type": "operator",
                "section_title": "Summary",
                "operator_family": "CHOP",
                "operator_name": "Wave CHOP",
                "mentioned_operators": [],
                "parameter_names": ["Type\ntype", "Frequency\nfreq"],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 10,
                "content": "Generates waveforms as CHOP channels.",
            },
            {
                "chunk_id": "noise_top__summary__0001",
                "page_id": "noise_top",
                "doc_type": "operator",
                "section_title": "Summary",
                "operator_family": "TOP",
                "operator_name": "Noise TOP",
                "mentioned_operators": [],
                "parameter_names": ["Seed\nseed"],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": 10,
                "content": "Generates image noise.",
            },
        ],
    )

    drafts = draft_missing_operator_cards(tmp_path, op_types=["waveCHOP"])

    assert [draft["op_type"] for draft in drafts] == ["waveCHOP"]
    assert drafts[0]["family"] == "CHOP"


def test_write_operator_card_drafts_keeps_drafts_outside_live_atlas(tmp_path: Path) -> None:
    drafts = [
        {
            "card_type": "operator_draft",
            "target_card_type": "operator",
            "op_type": "directdisplayoutTOP",
            "family": "TOP",
            "display_name": "Direct Display Out TOP",
            "docs_url": "https://docs.derivative.ca/Direct_Display_Out_TOP",
            "summary": "Draft.",
            "key_params": [],
            "common_gotchas": ["Needs review."],
            "related_snippets": ["TOP_snippets"],
            "build_relevance": "unverified-docsbrain",
            "review_status": "needs_manual_enrichment",
            "provenance": {"source": "docsbrain"},
        }
    ]

    manifest = write_operator_card_drafts(drafts, tmp_path / "drafts")

    assert manifest["draft_count"] == 1
    assert manifest["op_types"] == ["directdisplayoutTOP"]
    draft_path = tmp_path / "drafts" / "directdisplayoutTOP.draft.json"
    assert draft_path.exists()
    written = json.loads(draft_path.read_text(encoding="utf-8"))
    assert written["card_type"] == "operator_draft"
    assert not (tmp_path / "src" / "td_mcp" / "knowledge" / "cards" / "operators").exists()


def test_write_operator_card_drafts_prunes_stale_draft_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "drafts"
    output_dir.mkdir()
    (output_dir / "oldTOP.draft.json").write_text("{}", encoding="utf-8")
    (output_dir / "notes.txt").write_text("keep me", encoding="utf-8")
    drafts = [
        {
            "card_type": "operator_draft",
            "target_card_type": "operator",
            "op_type": "newTOP",
            "family": "TOP",
            "display_name": "New TOP",
            "docs_url": "https://docs.derivative.ca/New_TOP",
            "summary": "Draft.",
            "key_params": [],
            "common_gotchas": ["Needs review."],
            "related_snippets": ["TOP_snippets"],
            "build_relevance": "unverified-docsbrain",
            "review_status": "needs_manual_enrichment",
            "provenance": {"source": "docsbrain"},
        }
    ]

    write_operator_card_drafts(drafts, output_dir)

    assert not (output_dir / "oldTOP.draft.json").exists()
    assert (output_dir / "newTOP.draft.json").exists()
    assert (output_dir / "notes.txt").exists()


def test_write_operator_card_drafts_escapes_path_separators_in_op_type(tmp_path: Path) -> None:
    drafts = [
        {
            "card_type": "operator_draft",
            "target_card_type": "operator",
            "op_type": "tcp/ipDAT",
            "family": "DAT",
            "display_name": "TCP/IP DAT",
            "docs_url": "https://docs.derivative.ca/TCP/IP_DAT",
            "summary": "Draft.",
            "key_params": [],
            "common_gotchas": ["Needs review."],
            "related_snippets": ["DAT_snippets"],
            "build_relevance": "unverified-docsbrain",
            "review_status": "needs_manual_enrichment",
            "provenance": {"source": "docsbrain"},
        }
    ]

    manifest = write_operator_card_drafts(drafts, tmp_path / "drafts")

    assert manifest["op_types"] == ["tcp/ipDAT"]
    draft_path = tmp_path / "drafts" / "tcp%2FipDAT.draft.json"
    assert draft_path.exists()
    written = json.loads(draft_path.read_text(encoding="utf-8"))
    assert written["op_type"] == "tcp/ipDAT"
