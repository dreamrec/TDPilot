"""PatchPlan builder. Three input paths — operations > recipe > intent —
with static risk-flag analysis and knowledge-corpus lookups.

See spec §6.1. This module is MCP-free.
"""

from __future__ import annotations

from typing import Any

from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan

# Keyword → (macro_type, summary). Sourced from
# src/td_mcp/registry/tools_planning.py:32 _INTENT_MACRO_KEYWORDS to
# preserve behaviour. If the legacy table moves, update here to match.
_INTENT_MACRO_KEYWORDS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("feedback displ", "feedback-displacement", "feedback_displacement"),
        "feedback_displacement",
        "Classic feedback displacement with source noise and composite merge.",
    ),
    (
        ("feedback", "trail", "echo"),
        "feedback_loop",
        "Classic feedback chain: feedback → level → composite → out.",
    ),
    (
        ("post-process", "post process", "post_processing", "grade", "bloom blur", "color grade"),
        "post_processing",
        "Simple post-FX chain: level → blur → out.",
    ),
    (
        ("audio reactive", "audio-react", "audio_reactive", "audio analysis"),
        "audio_reactive",
        "Audio signal preprocessing chain with gain stage and null output.",
    ),
    (
        ("particle", "gpu particle", "pop simulation", "particles"),
        "particle_gpu",
        "Minimal POP chain: particle → noise → render.",
    ),
)

_MASS_CHANGE_THRESHOLD = 20


async def build_plan(
    td_client=None,
    *,
    target_root: str,
    intent: str | None = None,
    recipe_id: str | None = None,
    operations: list[dict[str, Any]] | None = None,
    undo_label: str | None = None,
    technique_store=None,
    card_index=None,
) -> PatchPlan:
    """Construct a PatchPlan from one of three input paths.

    Precedence (highest priority wins): operations > recipe_id > intent.
    Raises ValueError if none provided.
    """
    if operations:
        ops = [PatchOperation.model_validate(o) for o in operations]
        source = "operations"
        recipe_used: str | None = None
    elif recipe_id:
        if technique_store is None:
            raise ValueError("recipe_id given but technique_store not provided")
        ops = _recipe_to_operations(technique_store.get(recipe_id), target_root)
        source = "recipe"
        recipe_used = recipe_id
    elif intent:
        ops = _intent_to_operations(intent, target_root)
        source = "intent_heuristic"
        recipe_used = None
    else:
        raise ValueError("td_patch_plan requires one of: operations, recipe_id, intent")

    label = undo_label or _derive_label(intent, source)
    req_ops = _collect_required_ops(ops, card_index)
    flags = _static_risk_flags(ops, target_root)

    return PatchPlan(
        intent=intent,
        target_root=target_root,
        source=source,
        source_recipe_id=recipe_used,
        operations=ops,
        required_ops=req_ops,
        risk_flags=flags,
        undo_label=label,
        validation_plan=ValidationPlan(target_root=target_root, capture_frames=[]),
    )


def _recipe_to_operations(recipe: dict | None, target_root: str) -> list[PatchOperation]:
    if not recipe:
        return []
    tech = recipe.get("technique", {}) if isinstance(recipe, dict) else {}
    recipe_data = tech.get("recipe", {}) if isinstance(tech, dict) else {}
    nodes = recipe_data.get("nodes", {})
    if isinstance(nodes, dict):
        nodes = list(nodes.values())
    ops: list[PatchOperation] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        op_type = node.get("type", "")
        if not op_type:
            continue
        ops.append(
            PatchOperation(
                kind="create_node",
                target=target_root,
                args={"op_type": op_type, "name": node.get("name", "")},
            )
        )
    return ops


def _intent_to_operations(intent: str, target_root: str) -> list[PatchOperation]:
    text = (intent or "").lower()
    for keywords, macro_type, summary in _INTENT_MACRO_KEYWORDS:
        if any(k in text for k in keywords):
            return [
                PatchOperation(
                    kind="macro",
                    target=target_root,
                    args={"macro_type": macro_type, "summary": summary},
                )
            ]
    return []


def _collect_required_ops(ops: list[PatchOperation], card_index) -> list[str]:
    required: list[str] = []
    for op in ops:
        if op.kind != "create_node":
            continue
        op_type = op.args.get("op_type")
        if not op_type:
            continue
        if card_index is not None and card_index.get_operator(op_type) is None:
            required.append(f"unknown:{op_type}")
        else:
            required.append(op_type)
    return required


def _static_risk_flags(ops: list[PatchOperation], target_root: str) -> list[str]:
    flags: list[str] = []
    if len(ops) > _MASS_CHANGE_THRESHOLD:
        flags.append("mass-change")
    if target_root == "/":
        flags.append("affects-root")
    return flags


def _derive_label(intent: str | None, source: str) -> str:
    if intent:
        return f"td patch: {intent[:40]}"
    if source == "recipe":
        return "td patch: recipe"
    return "td patch"
