"""Coverage audit for the structured operator atlas used by brain profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from td_mcp.brain.planner import _PROFILE_SPECS
from td_mcp.knowledge.card_index import CardIndex


def audit_brain_atlas(root: str | Path) -> dict[str, Any]:
    """Return operator-card coverage for every vNext brain profile."""
    repo_root = Path(root)
    cards_dir = repo_root / "src" / "td_mcp" / "knowledge" / "cards"
    card_index = CardIndex(cards_dir)

    profiles: dict[str, dict[str, Any]] = {}
    required: set[str] = set()
    missing_all: set[str] = set()

    for profile, spec in sorted(_PROFILE_SPECS.items()):
        operators = sorted({str(item["op_type"]) for item in spec.concepts if item.get("op_type")})
        missing = [op_type for op_type in operators if card_index.get_operator(op_type) is None]
        required.update(operators)
        missing_all.update(missing)
        profiles[profile] = {
            "operators": operators,
            "operator_count": len(operators),
            "missing_cards": missing,
            "coverage": 1.0 if not operators else round((len(operators) - len(missing)) / len(operators), 4),
        }

    return {
        "schema_version": 1,
        "ok": not missing_all,
        "card_count": card_index.count(),
        "profile_count": len(profiles),
        "required_operator_count": len(required),
        "missing_operator_cards": sorted(missing_all),
        "profiles": profiles,
    }


__all__ = ["audit_brain_atlas"]
