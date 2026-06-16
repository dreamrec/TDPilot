from __future__ import annotations

from pathlib import Path

from td_mcp.brain.atlas_audit import audit_brain_atlas
from td_mcp.brain.planner import _PROFILE_SPECS
from td_mcp.knowledge.card_index import CardIndex


def test_brain_profile_operators_have_structured_operator_cards():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    required_ops = sorted(
        {
            concept["op_type"]
            for spec in _PROFILE_SPECS.values()
            for concept in spec.concepts
            if concept.get("op_type")
        }
    )

    missing = [op_type for op_type in required_ops if cards.get_operator(op_type) is None]

    assert missing == []


def test_brain_atlas_audit_reports_profile_operator_coverage():
    report = audit_brain_atlas(Path("."))

    assert report["ok"] is True
    assert report["required_operator_count"] == 24
    assert report["missing_operator_cards"] == []
    assert report["profiles"]["feedback"]["missing_cards"] == []
    assert "levelTOP" in report["profiles"]["feedback"]["operators"]
