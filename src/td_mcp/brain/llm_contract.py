"""Deterministic review gate for LLM-proposed concept graph drafts.

Parameter verification tiers (the "param-gating polarity flip")
---------------------------------------------------------------
A draft param value survives the review gate when its NAME is verified by
either of two static tiers; everything else is stripped (never rejected) and
surfaced through ``DraftGraphReview.rewrites`` / ``plan_summary.stripped_params``:

1. ``registry_contract`` — the hand-built ParamSemantics registry knows
   ``(op_type, name)``. The registry stays the sole authority for static VALUE
   contracts (enum values, valid ranges, tuple shapes, op_ref families,
   cook_risk): those are enforced later by
   ``validate_patch_plan_parameter_contract`` inside plan compilation.
2. ``atlas_name_verified`` — the operator's official docs card (the 656-card
   atlas) lists the name in ``key_params`` and cites an official Derivative
   docs URL (``official_card_param_names``). This tier verifies the name only;
   no static value contract exists, so values ride through to the post-apply
   live validation layer (validation probes + live parameter readback — the
   same machinery as ``confirm_param_semantics_drafts_with_live_readback``).
3. ``unverified_stripped`` — neither tier can prove the parameter exists, so
   the value is stripped. Absence of a hand-registry entry alone is no longer
   sufficient reason to strip.

Why no live per-op-type schema tier at review time: the TD component API
(``mcp_webserver_callbacks``) only exposes ``node/params`` for EXISTING node
paths — there is no par-schema-by-optype endpoint, and drafts reference
operators that do not exist as nodes yet. Probing would require creating
scratch nodes, which would violate this gate's read-only contract
(``td_brain_propose`` never mutates TouchDesigner). Live readback therefore
remains the post-apply validation layer it already is.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from td_mcp.brain.param_semantics import semantics_by_op_and_param
from td_mcp.brain.param_semantics_drafts import official_card_param_names
from td_mcp.models.brain import (
    BrainProfile,
    CandidateConceptGraph,
    CompiledVisualTaskSpec,
    ConceptEdge,
    ConceptNode,
)

LLM_CORPUS_CONTRACT: dict[str, Any] = {
    "llm_role": "suggest_draft_intent_and_alternatives",
    "corpus_role": "supply_grounded_touchdesigner_affordances",
    "validator_role": "decide_accept_reject_or_rewrite",
    "required_grounding": ["official_docs", "operator_availability", "parameter_semantics"],
    "proof_layers": ["schema", "official_docs", "availability", "param_semantics", "live_td"],
    "mutation_rule": "drafts_never_mutate_touchdesigner_directly",
    # Param-name verification tiers (see module docstring): registry entries
    # keep value-contract authority; official card key_params verify names;
    # anything else is stripped and surfaced via stripped_params.
    "param_verification_tiers": ["registry_contract", "atlas_name_verified", "unverified_stripped"],
}


class DraftConceptGraph(BaseModel):
    """Untrusted candidate graph shape for future LLM-produced drafts."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    profiles: list[BrainProfile] = Field(default_factory=list)
    concepts: list[ConceptNode] = Field(default_factory=list)
    edges: list[ConceptEdge] = Field(default_factory=list)
    required_ops: list[str] = Field(default_factory=list)
    optional_ops: list[str] = Field(default_factory=list)
    validation_needs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    grounding_evidence: list[str] = Field(default_factory=list)
    explanation: str = ""

    @model_validator(mode="after")
    def _edges_reference_known_concepts(self) -> DraftConceptGraph:
        concept_ids = {concept.id for concept in self.concepts}
        for edge in self.edges:
            if edge.source not in concept_ids:
                raise ValueError(f"edge source references unknown concept id: {edge.source}")
            if edge.target not in concept_ids:
                raise ValueError(f"edge target references unknown concept id: {edge.target}")
        return self


class DraftGraphReview(BaseModel):
    """Machine-readable result of deterministic draft review."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool = False
    status: Literal["accepted", "rejected", "rewritten"] = "rejected"
    candidate_graph: CandidateConceptGraph | None = None
    rejection_reasons: list[str] = Field(default_factory=list)
    rewrites: list[str] = Field(default_factory=list)
    grounding_evidence: list[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    contract: dict[str, Any] = Field(default_factory=lambda: dict(LLM_CORPUS_CONTRACT))


def review_draft_candidate_graph(
    draft: dict[str, Any] | DraftConceptGraph,
    *,
    compiled_task: CompiledVisualTaskSpec,
    available_ops: set[str] | None,
    card_index,
    require_param_semantics: bool = True,
) -> DraftGraphReview:
    """Validate, reject, or rewrite an untrusted draft graph.

    This is intentionally stricter than template planning. A draft can become a
    CandidateConceptGraph only after deterministic validators prove schema
    shape, official docs grounding, operator availability, and parameter
    semantics. That keeps future LLM creativity outside the mutation boundary.
    """
    try:
        draft_model = (
            draft if isinstance(draft, DraftConceptGraph) else DraftConceptGraph.model_validate(draft)
        )
    except ValidationError as exc:
        return DraftGraphReview(
            accepted=False,
            status="rejected",
            rejection_reasons=[f"invalid_schema:{_compact_error(exc)}"],
            grounding_evidence=["draft-review:rejected", "draft-review:invalid-schema"],
        )

    required_ops = _required_ops_for_draft(draft_model)
    if not required_ops:
        return _rejected("missing_required_ops")

    docs_evidence, missing_docs = _docs_evidence(card_index, required_ops)
    unavailable_ops = _unavailable_ops(required_ops, available_ops)
    rejection_reasons = [
        *[f"missing_docs:{op_type}" for op_type in missing_docs],
        *[f"unavailable_op:{op_type}" for op_type in unavailable_ops],
    ]
    if rejection_reasons:
        return DraftGraphReview(
            accepted=False,
            status="rejected",
            rejection_reasons=_dedupe(rejection_reasons),
            grounding_evidence=_dedupe(["draft-review:rejected", *docs_evidence]),
            score=0.0,
        )

    concepts = list(draft_model.concepts)
    rewrites: list[str] = []
    param_tier_evidence: list[str] = []
    if require_param_semantics:
        concepts, rewrites, param_tier_evidence = _rewrite_unverified_params(concepts, card_index)

    grounding = _dedupe(
        [
            "draft-review:accepted",
            "draft-review:rewritten" if rewrites else "",
            *compiled_task.grounding_evidence,
            *draft_model.grounding_evidence,
            *docs_evidence,
            *param_tier_evidence,
        ]
    )
    score = _review_score(required_ops, docs_evidence=docs_evidence, rewrites=rewrites)
    candidate = CandidateConceptGraph(
        compiled_task_id=compiled_task.id,
        label=draft_model.label,
        profiles=draft_model.profiles or compiled_task.candidate_profiles,
        pattern_ids=["llm_draft_candidate"],
        concepts=concepts,
        edges=draft_model.edges,
        required_ops=required_ops,
        optional_ops=draft_model.optional_ops,
        expected_outputs=[
            str(output.get("path"))
            for output in compiled_task.outputs
            if isinstance(output, dict) and output.get("path")
        ],
        validation_needs=_dedupe([*compiled_task.validation_needs, *draft_model.validation_needs]),
        risk_flags=_dedupe(
            [
                *draft_model.risk_flags,
                "llm-draft-reviewed",
                "llm-draft-rewritten" if rewrites else "",
            ]
        ),
        grounding_evidence=grounding,
        score=score,
        explanation=draft_model.explanation,
    )
    return DraftGraphReview(
        accepted=True,
        status="rewritten" if rewrites else "accepted",
        candidate_graph=candidate,
        rewrites=rewrites,
        grounding_evidence=grounding,
        score=score,
    )


def _rejected(reason: str) -> DraftGraphReview:
    return DraftGraphReview(
        accepted=False,
        status="rejected",
        rejection_reasons=[reason],
        grounding_evidence=["draft-review:rejected"],
    )


def _required_ops_for_draft(draft: DraftConceptGraph) -> list[str]:
    concept_ops = [
        str(concept.create_type or concept.op_type)
        for concept in draft.concepts
        if concept.create_type or concept.op_type
    ]
    return _dedupe([*draft.required_ops, *concept_ops])


def _docs_evidence(card_index, required_ops: list[str]) -> tuple[list[str], list[str]]:
    evidence: list[str] = []
    missing: list[str] = []
    for op_type in required_ops:
        card = _safe_get_operator(card_index, op_type)
        if card is None:
            missing.append(op_type)
        else:
            evidence.append(f"docs:{op_type}")
    return evidence, missing


def _safe_get_operator(card_index, op_type: str) -> dict | None:
    if card_index is None:
        return None
    try:
        card = card_index.get_operator(op_type)
    except Exception:
        return None
    return card if isinstance(card, dict) else None


def _unavailable_ops(required_ops: list[str], available_ops: set[str] | None) -> list[str]:
    if available_ops is None:
        return []
    return sorted(op_type for op_type in required_ops if op_type not in available_ops)


def _rewrite_unverified_params(
    concepts: list[ConceptNode],
    card_index,
) -> tuple[list[ConceptNode], list[str], list[str]]:
    """Strip param values whose NAMES no verification tier can prove.

    Tier 1 (``registry_contract``): the hand ParamSemantics registry knows the
    (op_type, name) pair — value contracts are enforced downstream by
    ``validate_patch_plan_parameter_contract``. Tier 2 (``atlas_name_verified``):
    the operator's official docs card lists the name in ``key_params`` — the
    value survives to the post-apply live validation layer. Truly unknown
    names are still stripped (test-encoded contract: strip, never reject).
    """
    semantics = semantics_by_op_and_param()
    rewrites: list[str] = []
    tier_evidence: list[str] = []
    rewritten: list[ConceptNode] = []
    for concept in concepts:
        op_type = concept.create_type or concept.op_type
        if not op_type or not concept.params:
            rewritten.append(concept)
            continue
        card_param_names = official_card_param_names(card_index, op_type)
        cleaned: dict[str, Any] = {}
        for name, value in concept.params.items():
            if (op_type, name) in semantics:
                cleaned[name] = value
                tier_evidence.append(f"param-verified:registry:{op_type}.{name}")
            elif name in card_param_names:
                cleaned[name] = value
                tier_evidence.append(f"param-verified:atlas:{op_type}.{name}")
            else:
                rewrites.append(f"removed_unverified_param:{op_type}.{name}")
        rewritten.append(concept.model_copy(update={"params": cleaned}))
    return rewritten, rewrites, tier_evidence


def _review_score(required_ops: list[str], *, docs_evidence: list[str], rewrites: list[str]) -> float:
    if not required_ops:
        return 0.0
    docs_ratio = len(docs_evidence) / len(required_ops)
    rewrite_penalty = min(0.2, len(rewrites) * 0.04)
    return round(max(0.0, min(1.0, 0.62 + (docs_ratio * 0.34) - rewrite_penalty)), 4)


def _compact_error(exc: ValidationError) -> str:
    first = exc.errors()[0] if exc.errors() else {"msg": str(exc)}
    location = ".".join(str(part) for part in first.get("loc", ())) or "draft"
    return f"{location}:{first.get('msg', 'invalid')}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


__all__ = [
    "DraftConceptGraph",
    "DraftGraphReview",
    "LLM_CORPUS_CONTRACT",
    "review_draft_candidate_graph",
]
