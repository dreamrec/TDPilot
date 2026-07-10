"""Draft candidate concept graphs from retrieved operator atlas cards."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from td_mcp.brain.corpus_bridge import OFFICIAL_DERIVATIVE_DOCS_PREFIX, corpus_evidence_markers
from td_mcp.brain.operator_intents import OperatorIntentRoute, select_operator_intent_route
from td_mcp.models.brain import (
    CandidateConceptGraph,
    CompiledVisualTaskSpec,
    ConceptEdge,
    ConceptNode,
    CorpusEvidenceRecord,
    DataDomain,
    VisualTaskSpec,
)


@dataclass(frozen=True)
class AtlasDraftResult:
    """Review result for a deterministic atlas-grounded topology draft."""

    accepted: bool = False
    candidate_graph: CandidateConceptGraph | None = None
    candidate_graphs: list[CandidateConceptGraph] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    grounding_evidence: list[str] = field(default_factory=list)
    route: OperatorIntentRoute | None = None


@dataclass(frozen=True)
class _TypedBridgeSpec:
    """A grounded cross-family bridge operator discovered from atlas cards."""

    op_type: str
    source_family: str
    target_family: str
    source_param: str


@dataclass(frozen=True)
class _TypedBridgePathDraft:
    """A bounded, corpus-grounded bridge path with role-classified branches."""

    bridges: tuple[_TypedBridgeSpec, ...]
    source_chain: list[str]
    source_roles: dict[str, str]
    intermediate_chains: tuple[list[str], ...]
    intermediate_roles: tuple[dict[str, str], ...]
    target_chain: list[str]
    target_roles: dict[str, str]
    priority: int
    source_relevance: int
    target_relevance: int
    score: float


@dataclass(frozen=True)
class _TopologyRoleRelevance:
    """Intent relevance of the structured roles present in a synthesized topology."""

    source: int = 0
    control: int = 0
    preview: int = 0
    output: int = 0

    def rank_tuple(self) -> tuple[int, int, int, int]:
        return (self.source, self.control, self.preview, self.output)


@dataclass(frozen=True)
class _TopologyValidationFeedback:
    """Atlas-local validation-readiness and prior runtime feedback signal."""

    readiness_score: float
    passed_probe_count: int = 0
    missing_probe_count: int = 0
    failed_probe_count: int = 0
    failed_required_probe_count: int = 0

    def rank_score(self) -> float:
        return round(
            self.readiness_score
            + (0.035 * self.passed_probe_count)
            - (0.09 * self.missing_probe_count)
            - (0.16 * self.failed_probe_count)
            - (0.12 * self.failed_required_probe_count),
            4,
        )


@dataclass(frozen=True)
class _SourcePreviewPathDraft:
    """One corpus-grounded source/process/output role assignment."""

    family: str
    chain: list[str]
    role_by_op: dict[str, str]
    score: float
    source_relevance: int
    process_relevance: int
    process_priority: int
    output_relevance: int
    search_roles: tuple[str, ...] = ("source", "process", "output")


@dataclass(frozen=True)
class _SopExportControlTargetDraft:
    """One docs-grounded SOP parameter candidate for CHOP export binding."""

    op_type: str
    param_name: str
    role: str
    chain_index: int
    param_priority: int
    intent_relevance: int
    score: float


def draft_atlas_candidate_graph(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    corpus_evidence: list[CorpusEvidenceRecord],
    card_index,
) -> AtlasDraftResult:
    """Turn corpus hits into a small candidate graph, or reject with reasons."""
    route = select_operator_intent_route(task.intent, corpus_evidence)
    attempts: list[AtlasDraftResult] = []
    rejection_reasons: list[str] = []
    grounding_evidence: list[str] = []

    if route is None:
        rejection_reasons.append("atlas_draft:no_operator_intent_route")
        grounding_evidence.append("operator-intent:none")
    else:
        route_result = _draft_route_candidate(
            task=task,
            compiled_task=compiled_task,
            corpus_evidence=corpus_evidence,
            card_index=card_index,
            route=route,
        )
        if route_result.accepted:
            attempts.append(route_result)
        else:
            rejection_reasons.extend(route_result.rejection_reasons)
            grounding_evidence.extend(route_result.grounding_evidence)

    synthesis_result = _draft_synthesized_candidate_graph(
        task=task,
        compiled_task=compiled_task,
        corpus_evidence=corpus_evidence,
        card_index=card_index,
        route=route,
    )
    if synthesis_result.accepted:
        attempts.append(_with_matching_route_evidence(synthesis_result, route))
    elif not attempts:
        rejection_reasons.extend(synthesis_result.rejection_reasons)
        grounding_evidence.extend(synthesis_result.grounding_evidence)

    if attempts:
        return max(
            attempts,
            key=lambda result: result.candidate_graph.score if result.candidate_graph is not None else 0.0,
        )

    return AtlasDraftResult(
        accepted=False,
        rejection_reasons=_dedupe(rejection_reasons),
        grounding_evidence=_dedupe(["atlas-draft:rejected", *grounding_evidence]),
        route=route,
    )


def _with_matching_route_evidence(
    result: AtlasDraftResult,
    route: OperatorIntentRoute | None,
) -> AtlasDraftResult:
    if route is None or not result.accepted or result.candidate_graph is None:
        return result
    candidate = result.candidate_graph
    route_ops = set(route.operator_chain)
    if not route_ops or not route_ops.issubset(set(candidate.required_ops)):
        return result
    marker = f"operator-intent:{route.route_id}"
    candidate = candidate.model_copy(
        update={
            "grounding_evidence": _dedupe([marker, *candidate.grounding_evidence]),
            "explanation": (
                candidate.explanation
                if f"atlas_intent:{route.route_id}" in candidate.explanation
                else f"atlas_intent:{route.route_id}; {candidate.explanation}"
            ),
        }
    )
    candidate_graphs = [
        candidate if existing.id == candidate.id else existing for existing in result.candidate_graphs
    ]
    return AtlasDraftResult(
        accepted=result.accepted,
        candidate_graph=candidate,
        candidate_graphs=candidate_graphs,
        rejection_reasons=result.rejection_reasons,
        grounding_evidence=_dedupe([marker, *result.grounding_evidence]),
        route=route,
    )


def _draft_route_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    corpus_evidence: list[CorpusEvidenceRecord],
    card_index,
    route: OperatorIntentRoute,
) -> AtlasDraftResult:
    """Draft the legacy curated route candidate."""

    route_domains = {_domain_for_op(op_type) for op_type in route.operator_chain}
    if len(route_domains) > 1:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=[f"atlas_draft:route_cross_family_requires_synthesis:{route.route_id}"],
            grounding_evidence=[
                "atlas-draft:rejected",
                f"operator-intent:{route.route_id}",
                "atlas-synthesis:required-for-cross-family-route",
            ],
            route=route,
        )

    docs_evidence, missing_docs, cards_by_op = _docs_evidence_for_route(card_index, route)
    if missing_docs:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=[f"atlas_draft:missing_docs:{op_type}" for op_type in missing_docs],
            grounding_evidence=[
                "atlas-draft:rejected",
                f"operator-intent:{route.route_id}",
                *docs_evidence,
            ],
            route=route,
        )

    concepts = _concepts_for_route(route, cards_by_op, corpus_evidence)
    edges = [
        ConceptEdge(source=concepts[index].id, target=concepts[index + 1].id, kind="data")
        for index in range(len(concepts) - 1)
    ]
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            f"operator-intent:{route.route_id}",
            *docs_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:{route.route_id}",
        compiled_task_id=compiled_task.id,
        label=route.label,
        profiles=["generic"],
        pattern_ids=[f"atlas:{route.route_id}"],
        concepts=concepts,
        edges=edges,
        required_ops=list(route.operator_chain),
        expected_outputs=[task.output_top or _default_output_marker(route.operator_chain[-1])],
        validation_needs=list(route.validation_needs),
        risk_flags=list(route.risk_flags),
        grounding_evidence=grounding,
        score=_candidate_score(route=route, corpus_evidence=corpus_evidence),
        explanation=(
            f"atlas_intent:{route.route_id}; "
            f"ranking:curated_route:{route.score:.4f}; "
            f"operators:{','.join(route.operator_chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
        route=route,
    )


def _draft_synthesized_candidate_graph(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    corpus_evidence: list[CorpusEvidenceRecord],
    card_index,
    route: OperatorIntentRoute | None = None,
) -> AtlasDraftResult:
    records, cards_by_op = _official_operator_records(corpus_evidence, card_index)
    if route is not None:
        route_records, route_cards = _official_route_records(route, card_index)
        known_ops = {record.op_type for record in records}
        records.extend(record for record in route_records if record.op_type not in known_ops)
        cards_by_op.update(
            {op_type: card for op_type, card in route_cards.items() if op_type not in cards_by_op}
        )
    if len(records) < 2:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=["atlas_draft:synthesis_insufficient_official_cards"],
            grounding_evidence=["atlas-synthesis:rejected", "atlas-synthesis:insufficient-official-cards"],
        )

    multi_domain_results: list[tuple[int, AtlasDraftResult]] = []
    for order, multi_domain_drafter in enumerate(
        (
            _draft_typed_dat_role_graph_candidate,
            _draft_multi_hop_typed_bridge_graph_candidate,
            _draft_typed_bridge_graph_candidate,
            _draft_chop_export_bound_sop_render_preview_candidate,
            _draft_chop_export_bound_top_candidate,
            _draft_dat_controlled_top_candidate,
            _draft_chop_controlled_top_candidate,
            _draft_typed_source_preview_graph_candidate,
            _draft_sop_render_preview_candidate,
            _draft_source_preview_top_candidate,
            _draft_typed_role_graph_candidate,
        )
    ):
        multi_domain = multi_domain_drafter(
            task=task,
            compiled_task=compiled_task,
            records=records,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        if multi_domain.accepted and multi_domain.candidate_graph is not None:
            multi_domain_results.append((order, multi_domain))

    if multi_domain_results:
        return _rank_synthesized_topology_results(multi_domain_results, intent=task.intent)

    family = _best_synthesis_family(records, intent=task.intent)
    if family is None:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=["atlas_draft:synthesis_no_primary_family"],
            grounding_evidence=["atlas-synthesis:rejected", "atlas-synthesis:no-primary-family"],
        )

    chain, role_by_op = _synthesized_operator_chain(records, family)
    if not chain:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=[f"atlas_draft:synthesis_no_stable_chain:{family}"],
            grounding_evidence=["atlas-synthesis:rejected", f"atlas-synthesis:family:{family.lower()}"],
        )

    concepts = _concepts_for_chain(chain, cards_by_op, corpus_evidence)
    edges = [
        ConceptEdge(source=concepts[index].id, target=concepts[index + 1].id, kind="data")
        for index in range(len(concepts) - 1)
    ]
    role_evidence = [f"atlas-synthesis:{role_by_op[op_type]}:{op_type}" for op_type in chain]
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            f"atlas-synthesis:family:{family.lower()}",
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    score = _synthesis_score(chain, role_by_op, corpus_evidence)
    risk_flags = ["atlas-drafted-open-prompt", "atlas-synthesized-open-prompt"]
    if any(_is_device_source_op(op_type) for op_type in chain):
        risk_flags.append("device-source-required")
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:{family.lower()}",
        compiled_task_id=compiled_task.id,
        label=f"Atlas-synthesized {family} operator chain",
        profiles=["generic"],
        pattern_ids=[f"atlas:synthesized:{family.lower()}_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=list(chain),
        expected_outputs=[task.output_top or _default_output_marker(chain[-1])],
        validation_needs=_validation_needs_for_family(family),
        risk_flags=risk_flags,
        grounding_evidence=grounding,
        score=score,
        explanation=(
            "atlas_synthesis:retrieved_cards; "
            f"family:{family}; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _rank_synthesized_topology_results(
    results: list[tuple[int, AtlasDraftResult]],
    *,
    intent: str,
) -> AtlasDraftResult:
    """Rank accepted atlas synthesis drafters and expose corpus-grounded alternatives."""

    target_family = _requested_output_family(intent)
    ranked_results = sorted(
        results,
        key=lambda item: _synthesized_topology_result_rank_key(
            item[1],
            item[0],
            intent=intent,
            target_family=target_family,
        ),
        reverse=True,
    )
    raw_candidates: list[CandidateConceptGraph] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for _order, result in ranked_results:
        candidates = result.candidate_graphs or (
            [result.candidate_graph] if result.candidate_graph is not None else []
        )
        for candidate in candidates:
            key = (tuple(candidate.pattern_ids), tuple(candidate.required_ops))
            if key in seen:
                continue
            seen.add(key)
            raw_candidates.append(candidate)

    if not raw_candidates:
        return AtlasDraftResult(accepted=False)

    capped_candidates = raw_candidates[:6]
    topology_evidence = _synthesized_topology_search_evidence(capped_candidates, intent=intent)
    ranked_candidates = [
        _candidate_with_synthesis_topology_rank(
            candidate,
            rank=index,
            candidate_count=len(capped_candidates),
            topology_evidence=topology_evidence,
            role_relevance=_candidate_topology_role_relevance(candidate, intent),
        )
        for index, candidate in enumerate(capped_candidates, start=1)
    ]
    selected = ranked_candidates[0]
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=selected,
        candidate_graphs=ranked_candidates,
        grounding_evidence=selected.grounding_evidence,
    )


def _synthesized_topology_result_rank_key(
    result: AtlasDraftResult,
    order: int,
    *,
    intent: str,
    target_family: str | None,
) -> tuple[int, int, float, float, int, int, int, int, int, int]:
    candidate = result.candidate_graph
    if candidate is None:
        return (0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, -order)
    relevance = _candidate_topology_role_relevance(candidate, intent)
    validation_feedback = _candidate_topology_validation_feedback(candidate)
    return (
        _target_family_rank(candidate, target_family),
        _synthesized_topology_priority(candidate),
        validation_feedback.rank_score(),
        float(candidate.score or 0.0),
        *relevance.rank_tuple(),
        len(set(candidate.required_ops)),
        -order,
    )


def _target_family_rank(candidate: CandidateConceptGraph, target_family: str | None) -> int:
    if target_family is None:
        return 1
    return 2 if _candidate_output_family(candidate) == target_family else 0


def _candidate_output_family(candidate: CandidateConceptGraph) -> str | None:
    if not candidate.required_ops:
        return None
    family = _domain_for_op(candidate.required_ops[-1])
    return str(family) if family != "ANY" else None


def _candidate_topology_role_relevance(
    candidate: CandidateConceptGraph,
    intent: str,
) -> _TopologyRoleRelevance:
    families_by_role = _candidate_topology_role_families(candidate)

    return _TopologyRoleRelevance(
        source=_max_family_relevance(intent, families_by_role.get("source", ())),
        control=_max_family_relevance(intent, families_by_role.get("control", ())),
        preview=_max_family_relevance(intent, families_by_role.get("preview", ())),
        output=_max_family_relevance(intent, families_by_role.get("output", ())),
    )


def _candidate_topology_role_families(
    candidate: CandidateConceptGraph,
) -> dict[str, tuple[str, ...]]:
    families: dict[str, list[str]] = {"source": [], "control": [], "preview": [], "output": []}
    evidence = set(candidate.grounding_evidence)
    pattern_text = " ".join(candidate.pattern_ids)
    has_preview_graph = "preview" in pattern_text or any(
        "preview" in item or "render-top-preview" in item for item in evidence
    )
    has_control_graph = (
        "controlled" in pattern_text
        or "export_bound" in pattern_text
        or any("control:" in item or "binding:" in item for item in evidence)
    )

    for concept in candidate.concepts:
        family = _concept_domain_family(concept)
        if family is None:
            continue
        role = str(concept.role or "").lower()
        if role == "source":
            families["source"].append(family)
            if has_control_graph and family in {"CHOP", "DAT"}:
                families["control"].append(family)
        elif role == "control":
            families["control"].append(family)
        elif role == "output":
            families["output"].append(family)
        elif role == "render" or (has_preview_graph and family in {"COMP", "TOP"}):
            families["preview"].append(family)

    output_family = _candidate_output_family(candidate)
    if output_family is not None:
        families["output"].append(output_family)
        if has_preview_graph and output_family == "TOP":
            families["preview"].append(output_family)

    if has_control_graph:
        for op_type in candidate.required_ops:
            family = _domain_for_op(op_type)
            if family in {"CHOP", "DAT"}:
                families["control"].append(str(family))

    return {role: tuple(_dedupe(values)) for role, values in families.items()}


def _concept_domain_family(concept: ConceptNode) -> str | None:
    family = str(concept.domain or "")
    if family in {"TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT"}:
        return family
    if concept.op_type:
        op_family = _domain_for_op(str(concept.op_type))
        if op_family != "ANY":
            return str(op_family)
    return None


def _max_family_relevance(intent: str, families: tuple[str, ...]) -> int:
    if not families:
        return 0
    return max(_family_intent_relevance(intent, family) for family in families)


def _requested_output_family(intent: str) -> str | None:
    scores = {
        family: _family_intent_relevance(intent, family) for family in ("CHOP", "DAT", "POP", "SOP", "TOP")
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked or ranked[0][1] < 2:
        return None
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def _synthesized_topology_priority(candidate: CandidateConceptGraph) -> int:
    pattern_text = " ".join(candidate.pattern_ids)
    evidence = set(candidate.grounding_evidence)
    if "chop_export_bound_sop_render_preview" in pattern_text:
        return 780
    if "chop_export_bound_top" in pattern_text:
        return 770
    if "typed_role_graph_sop_render_preview_top" in pattern_text:
        return 740
    if "sop_render_preview_top" in pattern_text:
        return 730
    if "typed_bridge_graph" in pattern_text:
        return 700
    if "typed_dat_role_graph" in pattern_text:
        return 690
    if "dat_controlled_top" in pattern_text or "chop_controlled_top" in pattern_text:
        return 650
    if "typed_role_graph" in pattern_text:
        return 640
    if "source->preview->output" in evidence:
        return 630
    if "preview_top" in pattern_text:
        return 620
    return 500


_ATLAS_VALIDATION_NEED_WEIGHTS: dict[str, float] = {
    "output_node_present": 0.45,
    "top_output_present": 0.5,
    "control_output": 0.48,
    "protocol_table_output": 0.54,
    "cheap_visual_metrics": 0.58,
    "render_top_output": 0.62,
    "geometry_output_present": 0.5,
    "pop_output_attached": 0.58,
    "finite_pop_bounds": 0.68,
    "chop_export_method_readback": 0.62,
    "render_switch_table_present": 0.55,
}

_ATLAS_RUNTIME_VALIDATION_PREFIXES: tuple[tuple[str, str], ...] = (
    ("pass", "runtime-validation-pass:"),
    ("pass", "runtime_validation_pass:"),
    ("pass", "validation-pass:"),
    ("missing", "runtime-validation-missing:"),
    ("missing", "runtime_validation_missing:"),
    ("missing", "validation-missing:"),
    ("failed", "runtime-validation-failed:"),
    ("failed", "runtime_validation_failed:"),
    ("failed", "validation-failed:"),
    ("failed_required", "runtime-validation-failed-required:"),
    ("failed_required", "runtime_validation_failed_required:"),
    ("failed_required", "validation-failed-required:"),
)


def _candidate_topology_validation_feedback(candidate: CandidateConceptGraph) -> _TopologyValidationFeedback:
    readiness = sum(_ATLAS_VALIDATION_NEED_WEIGHTS.get(need, 0.35) for need in candidate.validation_needs)
    readiness_score = min(1.2, round(readiness / 4.0, 4))
    counts = {
        "pass": 0,
        "missing": 0,
        "failed": 0,
        "failed_required": 0,
    }
    for item in candidate.grounding_evidence:
        marker = str(item)
        for kind, prefix in _ATLAS_RUNTIME_VALIDATION_PREFIXES:
            if marker.startswith(prefix):
                counts[kind] += 1
                break
    return _TopologyValidationFeedback(
        readiness_score=readiness_score,
        passed_probe_count=counts["pass"],
        missing_probe_count=counts["missing"],
        failed_probe_count=counts["failed"],
        failed_required_probe_count=counts["failed_required"],
    )


def _synthesized_topology_search_evidence(
    candidates: list[CandidateConceptGraph],
    *,
    intent: str,
) -> list[str]:
    evidence = [f"atlas-synthesis:topology-candidate-count:{len(candidates)}"]
    for index, candidate in enumerate(candidates, start=1):
        pattern_id = candidate.pattern_ids[0] if candidate.pattern_ids else candidate.id
        marker_kind = "selected" if index == 1 else "alternative"
        relevance = _candidate_topology_role_relevance(candidate, intent)
        validation_feedback = _candidate_topology_validation_feedback(candidate)
        evidence.append(f"atlas-synthesis:topology-{marker_kind}:{index}:{pattern_id}")
        evidence.append(f"atlas-synthesis:topology-candidate:{index}:{pattern_id}:{candidate.score:.4f}")
        evidence.append(
            "atlas-synthesis:validation-feedback:"
            f"{index}:readiness:{validation_feedback.readiness_score:.4f}:"
            f"rank:{validation_feedback.rank_score():.4f}:"
            f"passed:{validation_feedback.passed_probe_count}:"
            f"missing:{validation_feedback.missing_probe_count}:"
            f"failed:{validation_feedback.failed_probe_count}:"
            f"failed_required:{validation_feedback.failed_required_probe_count}"
        )
        for need in candidate.validation_needs:
            evidence.append(f"atlas-synthesis:validation-need:{index}:{need}")
        evidence.append(
            "atlas-synthesis:topology-role-relevance:"
            f"{index}:source:{relevance.source}:control:{relevance.control}:"
            f"preview:{relevance.preview}:output:{relevance.output}"
        )
        for role, families in _candidate_topology_role_families(candidate).items():
            for family in families:
                evidence.append(
                    "atlas-synthesis:topology-role-family:"
                    f"{index}:{role}:{family}:{_family_intent_relevance(intent, family)}"
                )
    return evidence


def _candidate_with_synthesis_topology_rank(
    candidate: CandidateConceptGraph,
    *,
    rank: int,
    candidate_count: int,
    topology_evidence: list[str],
    role_relevance: _TopologyRoleRelevance,
) -> CandidateConceptGraph:
    marker_kind = "selected" if rank == 1 else "alternative"
    validation_feedback = _candidate_topology_validation_feedback(candidate)
    evidence = _dedupe(
        [
            *candidate.grounding_evidence,
            *topology_evidence,
            f"atlas-synthesis:topology-rank:{rank}",
        ]
    )
    explanation_markers = (
        f"topology_candidates:{candidate_count}; "
        f"topology_rank:{rank}; "
        "topology_role_relevance:"
        f"source={role_relevance.source},control={role_relevance.control},"
        f"preview={role_relevance.preview},output={role_relevance.output}; "
        "validation_feedback:"
        f"readiness={validation_feedback.readiness_score:.4f},"
        f"rank={validation_feedback.rank_score():.4f},"
        f"passed={validation_feedback.passed_probe_count},"
        f"missing={validation_feedback.missing_probe_count},"
        f"failed={validation_feedback.failed_probe_count},"
        f"failed_required={validation_feedback.failed_required_probe_count}; "
        f"topology_{marker_kind}:{candidate.pattern_ids[0] if candidate.pattern_ids else candidate.id}"
    )
    explanation = candidate.explanation
    if "topology_rank:" not in explanation:
        explanation = f"{explanation}; {explanation_markers}" if explanation else explanation_markers
    return candidate.model_copy(
        update={
            "grounding_evidence": evidence,
            "explanation": explanation,
        }
    )


def _draft_multi_hop_typed_bridge_graph_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Search retrieved cards for ranked typed bridge paths across families."""

    bridges = _typed_bridge_specs(records)
    if not bridges:
        return AtlasDraftResult(accepted=False)

    candidates = [
        draft
        for bridge_path in _typed_bridge_paths(bridges, max_hops=3, include_single=True)
        if (draft := _draft_typed_bridge_path(bridge_path, task.intent, records, corpus_evidence)) is not None
    ]

    if not candidates:
        return AtlasDraftResult(accepted=False)

    ranked_candidates = sorted(candidates, key=_typed_bridge_path_rank_key, reverse=True)
    candidate_graphs = [
        _candidate_for_typed_bridge_path(
            task=task,
            compiled_task=compiled_task,
            draft=draft,
            ranked_candidates=ranked_candidates,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        for draft in ranked_candidates[:4]
    ]
    candidate = candidate_graphs[0]
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        candidate_graphs=candidate_graphs,
        grounding_evidence=candidate.grounding_evidence,
    )


def _candidate_for_typed_bridge_path(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    draft: _TypedBridgePathDraft,
    ranked_candidates: list[_TypedBridgePathDraft],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> CandidateConceptGraph:
    """Build one candidate graph from a ranked typed bridge path."""

    bridges = draft.bridges
    source_chain = draft.source_chain
    source_roles = draft.source_roles
    target_chain = draft.target_chain
    target_roles = draft.target_roles

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    source_ids = _append_role_chain_concepts(
        concepts=concepts,
        edges=edges,
        chain=source_chain,
        role_by_op=source_roles,
        first_concept_id="source",
        stage_prefix="source_stage",
        family=bridges[0].source_family,
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    )

    previous_output_id = source_ids[-1]
    for index, bridge in enumerate(bridges):
        bridge_id = f"bridge_stage_{_slug(bridge.op_type)}"
        concepts.append(
            _concept_for_op(
                bridge.op_type,
                concept_id=bridge_id,
                label_suffix=f"{bridge.source_family} to {bridge.target_family} bridge",
                role="process",
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            ).model_copy(update={"params": {bridge.source_param: f"${{path:{previous_output_id}}}"}})
        )
        edges.append(ConceptEdge(source=previous_output_id, target=bridge_id, kind="reference"))

        if index < len(bridges) - 1:
            mid_chain = draft.intermediate_chains[index]
            mid_roles = draft.intermediate_roles[index]
            mid_prefix = "mid_stage" if index == 0 else f"mid{index + 1}_stage"
            mid_ids = _append_role_chain_concepts(
                concepts=concepts,
                edges=edges,
                chain=mid_chain,
                role_by_op=mid_roles,
                first_concept_id=f"{mid_prefix}_{_slug(mid_chain[0])}",
                stage_prefix=mid_prefix,
                family=bridge.target_family,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
                initial_source=bridge_id,
            )
            previous_output_id = mid_ids[-1]
            continue

        _append_role_chain_concepts(
            concepts=concepts,
            edges=edges,
            chain=target_chain,
            role_by_op=target_roles,
            first_concept_id=(
                "output"
                if len(target_chain) == 1 and target_roles.get(target_chain[0]) == "output"
                else f"target_stage_{_slug(target_chain[0])}"
            ),
            stage_prefix="target_stage",
            family=bridge.target_family,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
            initial_source=bridge_id,
            final_output_id="output",
        )

    chain = [
        *source_chain,
        *[
            op_type
            for index, bridge in enumerate(bridges)
            for op_type in (
                [bridge.op_type, *draft.intermediate_chains[index]]
                if index < len(bridges) - 1
                else [bridge.op_type]
            )
        ],
        *target_chain,
    ]
    role_by_op = _typed_bridge_path_roles(
        source_roles=source_roles,
        intermediate_roles=draft.intermediate_roles,
        target_roles=target_roles,
        bridges=bridges,
    )
    family_path = [bridges[0].source_family, *[bridge.target_family for bridge in bridges]]
    family_keys = [family.lower() for family in family_path]
    family_id = "_to_".join(family_keys)
    family_evidence = "+".join(family_keys)
    family_label = "-to-".join(family_path)
    role_graph = _typed_bridge_path_role_graph(len(bridges))
    multi_hop = len(bridges) > 1
    path_rank = _typed_bridge_path_rank(ranked_candidates, draft)
    path_evidence = _typed_bridge_path_search_evidence(ranked_candidates, draft)
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:typed-role-graph",
            "atlas-synthesis:typed-role-graph-search",
            "atlas-synthesis:typed-bridge-graph-search",
            *(["atlas-synthesis:typed-bridge-graph-search:multi-hop"] if multi_hop else []),
            f"atlas-synthesis:role-graph:{role_graph}",
            *(
                [f"atlas-synthesis:source-output-before-bridge:{source_chain[-1]}"]
                if source_roles.get(source_chain[-1]) == "output"
                else []
            ),
            *[
                f"atlas-synthesis:source-output-before-bridge:{chain[-1]}"
                for chain in draft.intermediate_chains
                if chain
            ],
            *[
                f"atlas-synthesis:bridge:{bridge.source_family}->{bridge.target_family}:{bridge.op_type}"
                for bridge in bridges
            ],
            *path_evidence,
            f"atlas-synthesis:family:{family_evidence}",
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    risk_flags = [
        "atlas-drafted-open-prompt",
        "atlas-synthesized-open-prompt",
        "atlas-typed-role-graph",
        "atlas-typed-bridge-graph",
    ]
    if multi_hop:
        risk_flags.append("atlas-typed-bridge-graph-multi-hop")
    if any(_is_device_source_op(op_type) for op_type in chain):
        risk_flags.append("device-source-required")
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:typed_bridge_graph_{family_id}",
        compiled_task_id=compiled_task.id,
        label=f"Atlas-synthesized typed {family_label} bridge graph",
        profiles=["generic"],
        pattern_ids=[f"atlas:synthesized:typed_bridge_graph_{family_id}_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker(target_chain[-1])],
        validation_needs=_validation_needs_for_family(bridges[-1].target_family),
        risk_flags=risk_flags,
        grounding_evidence=grounding,
        score=round(draft.score, 4),
        explanation=(
            "atlas_synthesis:typed_graph_search; "
            f"roles:{role_graph}; "
            f"family:{family_evidence}; "
            f"bridges:{','.join(bridge.op_type for bridge in bridges)}; "
            f"candidate_paths:{len(ranked_candidates)}; "
            f"path_rank:{path_rank}; "
            f"source_relevance:{bridges[0].source_family}:{draft.source_relevance}; "
            f"target_relevance:{bridges[-1].target_family}:{draft.target_relevance}; "
            f"{'selected_path' if path_rank == 1 else 'alternative_path'}:{_typed_bridge_path_family_id(draft)}; "
            f"alternatives:{_typed_bridge_path_alternative_summary(ranked_candidates)}; "
            f"ranking:official_cards:{draft.score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return candidate


def _draft_typed_bridge_graph_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Search retrieved cards for a source-family -> bridge -> target-family role graph."""

    bridge = _typed_bridge_spec(records)
    if bridge is None:
        return AtlasDraftResult(accepted=False)

    source_records = [record for record in records if _record_family(record) == bridge.source_family]
    target_records = [
        record
        for record in records
        if _record_family(record) == bridge.target_family and record.op_type != bridge.op_type
    ]
    source_chain, source_roles = _source_branch_operator_chain(
        source_records,
        bridge.source_family,
        task.intent,
    )
    target_chain, target_roles = _target_branch_operator_chain(target_records, bridge.target_family)
    if not source_chain or len(target_chain) < 1:
        return AtlasDraftResult(accepted=False)

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    source_ids: list[str] = []

    for index, op_type in enumerate(source_chain):
        concept_id = "source" if index == 0 else f"source_stage_{_slug(op_type)}"
        role = source_roles.get(op_type, "process")
        suffix = (
            f"{bridge.source_family} source"
            if role == "source"
            else (
                f"stable {bridge.source_family} source output"
                if role == "output"
                else f"{bridge.source_family} processing stage"
            )
        )
        source_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=source_ids[index - 1], target=concept_id, kind="data"))

    bridge_id = f"bridge_stage_{_slug(bridge.op_type)}"
    bridge_params = {bridge.source_param: f"${{path:{source_ids[-1]}}}"}
    concepts.append(
        _concept_for_op(
            bridge.op_type,
            concept_id=bridge_id,
            label_suffix=f"{bridge.source_family} to {bridge.target_family} bridge",
            role="process",
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        ).model_copy(update={"params": bridge_params})
    )
    edges.append(ConceptEdge(source=source_ids[-1], target=bridge_id, kind="reference"))

    previous_id = bridge_id
    target_ids: list[str] = []
    for index, op_type in enumerate(target_chain):
        is_output = index == len(target_chain) - 1 and target_roles.get(op_type) == "output"
        concept_id = "output" if is_output else f"target_stage_{_slug(op_type)}"
        role = "output" if is_output else "process"
        suffix = (
            f"stable {bridge.target_family} output"
            if is_output
            else f"{bridge.target_family} processing stage"
        )
        target_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        edges.append(ConceptEdge(source=previous_id, target=concept_id, kind="data"))
        previous_id = concept_id

    chain = [*source_chain, bridge.op_type, *target_chain]
    role_by_op = {**source_roles, bridge.op_type: "bridge", **target_roles}
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    source_key = bridge.source_family.lower()
    target_key = bridge.target_family.lower()
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:typed-role-graph",
            "atlas-synthesis:typed-role-graph-search",
            "atlas-synthesis:role-graph:source->bridge->process->output",
            *(
                [f"atlas-synthesis:source-output-before-bridge:{source_chain[-1]}"]
                if source_roles.get(source_chain[-1]) == "output"
                else []
            ),
            f"atlas-synthesis:bridge:{bridge.source_family}->{bridge.target_family}:{bridge.op_type}",
            f"atlas-synthesis:family:{source_key}+{target_key}",
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    score = min(
        0.94,
        _synthesis_score(source_chain, source_roles, corpus_evidence) * 0.34
        + _synthesis_score([bridge.op_type, *target_chain], role_by_op, corpus_evidence) * 0.46
        + 0.14,
    )
    risk_flags = [
        "atlas-drafted-open-prompt",
        "atlas-synthesized-open-prompt",
        "atlas-typed-role-graph",
        "atlas-typed-bridge-graph",
    ]
    if any(_is_device_source_op(op_type) for op_type in chain):
        risk_flags.append("device-source-required")
    candidate = CandidateConceptGraph(
        id=(
            f"candidate:{compiled_task.id}:atlas:synthesized:typed_bridge_graph_{source_key}_to_{target_key}"
        ),
        compiled_task_id=compiled_task.id,
        label=f"Atlas-synthesized typed {bridge.source_family}-to-{bridge.target_family} bridge graph",
        profiles=["generic"],
        pattern_ids=[f"atlas:synthesized:typed_bridge_graph_{source_key}_to_{target_key}_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker(target_chain[-1])],
        validation_needs=_validation_needs_for_family(bridge.target_family),
        risk_flags=risk_flags,
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:typed_graph_search; "
            f"roles:{_bridge_role_graph_label(source_chain, source_roles)}; "
            f"family:{bridge.source_family}+{bridge.target_family}; "
            f"bridge:{bridge.op_type}; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _draft_typed_dat_role_graph_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Compose a DAT source -> process -> output graph from grounded operator cards."""

    if not _looks_like_typed_dat_pipeline_prompt(task.intent, records):
        return AtlasDraftResult(accepted=False)

    dat_records = [record for record in records if _record_family(record) == "DAT"]
    chain, role_by_op = _typed_dat_pipeline_operator_chain(dat_records, task.intent)
    if len(chain) < 3:
        return AtlasDraftResult(accepted=False)

    concepts: list[ConceptNode] = []
    concept_ids: list[str] = []
    for op_type in chain:
        role = role_by_op.get(op_type, "process")
        if role == "source":
            concept_id = "dat_source"
            label_suffix = "protocol source"
        elif role == "output":
            concept_id = "output"
            label_suffix = "stable output"
        else:
            concept_id = f"dat_stage_{_slug(op_type)}"
            label_suffix = "table processing stage"
        concept_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=label_suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )

    edges = [
        ConceptEdge(source=concept_ids[index], target=concept_ids[index + 1], kind="data")
        for index in range(len(concept_ids) - 1)
    ]
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:typed-role-graph",
            "atlas-synthesis:role-graph:source->process->output",
            "atlas-synthesis:family:dat",
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    score = max(0.95, _synthesis_score(chain, role_by_op, corpus_evidence))
    risk_flags = [
        "atlas-drafted-open-prompt",
        "atlas-synthesized-open-prompt",
        "atlas-typed-role-graph",
    ]
    if any(_is_device_source_op(op_type) for op_type in chain):
        risk_flags.append("device-source-required")
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:typed_role_graph_dat_pipeline",
        compiled_task_id=compiled_task.id,
        label="Atlas-synthesized typed DAT source-process-output role graph",
        profiles=["generic"],
        pattern_ids=["atlas:synthesized:typed_role_graph_dat_pipeline_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker(chain[-1])],
        validation_needs=["protocol_table_output", "output_node_present"],
        risk_flags=risk_flags,
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:typed_role_graph; "
            "roles:source->process->output; "
            "family:DAT; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _draft_typed_role_graph_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Compose a small typed role graph when cards imply cross-domain flow."""

    if not _looks_like_typed_role_chop_top_prompt(task.intent, records):
        return AtlasDraftResult(accepted=False)

    chop_records = [record for record in records if _record_family(record) == "CHOP"]
    top_records = [record for record in records if _record_family(record) == "TOP"]
    control_chain, control_roles, control_search_evidence = _chop_control_operator_chain_search(
        chop_records,
        task.intent,
        corpus_evidence,
    )
    if len(control_chain) < 2:
        control_chain, control_roles = _synthesized_operator_chain(chop_records, "CHOP")
        control_search_evidence = []
    visual_chain, visual_roles, visual_search_evidence = _source_preview_operator_chain_search(
        top_records,
        "TOP",
        task.intent,
        corpus_evidence,
    )
    if len(visual_chain) < 2:
        visual_chain, visual_roles = _synthesized_operator_chain(top_records, "TOP")
        visual_search_evidence = []
    if len(control_chain) < 2 or len(visual_chain) < 2:
        return AtlasDraftResult(accepted=False)

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    control_ids: list[str] = []
    visual_ids: list[str] = []

    last_control_index = len(control_chain) - 1
    for index, op_type in enumerate(control_chain):
        concept_id = "control_source" if index == 0 else f"control_stage_{_slug(op_type)}"
        role = "source" if index == 0 else ("output" if index == last_control_index else "process")
        suffix = (
            "control source"
            if index == 0
            else ("control output" if index == last_control_index else "control stage")
        )
        control_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=control_ids[index - 1], target=concept_id, kind="data"))

    visual_control_target = ""
    last_visual_index = len(visual_chain) - 1
    for index, op_type in enumerate(visual_chain):
        if index == 0:
            concept_id = "visual_source"
            role = "source"
            suffix = "visual source"
        elif index == last_visual_index:
            concept_id = "output"
            role = "output"
            suffix = "stable output"
        else:
            concept_id = f"visual_stage_{_slug(op_type)}"
            role = "process"
            suffix = "visual stage"
            if not visual_control_target:
                visual_control_target = concept_id
        visual_ids.append(concept_id)
        concept = _concept_for_op(
            op_type,
            concept_id=concept_id,
            label_suffix=suffix,
            role=role,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        concepts.append(concept)
        if index > 0:
            edges.append(ConceptEdge(source=visual_ids[index - 1], target=concept_id, kind="data"))

    if control_ids:
        control_target = visual_control_target or visual_ids[min(1, len(visual_ids) - 1)]
        edges.append(
            ConceptEdge(
                source=control_ids[-1],
                target=control_target,
                kind="control",
                binding=_level_top_control_binding(concepts, control_target),
            )
        )

    chain = [*control_chain, *visual_chain]
    role_by_op = {
        **{op_type: ("output" if role == "output" else "control") for op_type, role in control_roles.items()},
        **visual_roles,
    }
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    score = min(
        0.925,
        _synthesis_score(control_chain, control_roles, corpus_evidence) * 0.42
        + _synthesis_score(visual_chain, visual_roles, corpus_evidence) * 0.42
        + 0.12,
    )
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:typed-role-graph",
            "atlas-synthesis:typed-role-graph-search:v1",
            "atlas-synthesis:role-graph:control->visual",
            "atlas-synthesis:family:chop+top",
            *(
                ["atlas-synthesis:binding:out_chop->levelTOP.brightness1"]
                if "levelTOP" in visual_chain and control_ids
                else []
            ),
            *control_search_evidence,
            *visual_search_evidence,
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:typed_role_graph_chop_top",
        compiled_task_id=compiled_task.id,
        label="Atlas-synthesized typed CHOP-to-TOP role graph",
        profiles=["generic"],
        pattern_ids=["atlas:synthesized:typed_role_graph_chop_top_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker(visual_chain[-1])],
        validation_needs=[
            "output_node_present",
            "control_output",
            "top_output_present",
            "cheap_visual_metrics",
        ],
        risk_flags=[
            "atlas-drafted-open-prompt",
            "atlas-synthesized-open-prompt",
            "atlas-typed-role-graph",
            "atlas-multi-domain-control",
        ],
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:typed_role_graph_search; "
            "roles:control->visual; "
            "family:CHOP+TOP; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _draft_dat_controlled_top_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Draft a tiny DAT control branch plus TOP output branch from official cards."""

    if not _looks_like_dat_controlled_top_prompt(task.intent, records):
        return AtlasDraftResult(accepted=False)

    dat_records = [record for record in records if _record_family(record) == "DAT"]
    top_records = [record for record in records if _record_family(record) == "TOP"]
    if not dat_records or len(top_records) < 2:
        return AtlasDraftResult(accepted=False)

    control_chain, control_roles = _dat_control_operator_chain(dat_records)
    visual_chain, visual_roles, visual_search_evidence = _source_preview_operator_chain_search(
        top_records,
        "TOP",
        task.intent,
        corpus_evidence,
    )
    if len(visual_chain) < 2:
        visual_chain, visual_roles = _synthesized_operator_chain(top_records, "TOP")
        visual_search_evidence = []
    if len(control_chain) < 1 or len(visual_chain) < 2:
        return AtlasDraftResult(accepted=False)

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    control_ids: list[str] = []
    visual_ids: list[str] = []

    for index, op_type in enumerate(control_chain):
        concept_id = "control_source" if index == 0 else f"control_stage_{_slug(op_type)}"
        control_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix="control source" if index == 0 else "control stage",
                role="source" if index == 0 else "process",
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=control_ids[index - 1], target=concept_id, kind="data"))

    last_visual_index = len(visual_chain) - 1
    switch_like_visual_id = ""
    for index, op_type in enumerate(visual_chain):
        if index == 0:
            concept_id = "visual_source"
            role = "source"
            suffix = "visual source"
        elif index == last_visual_index:
            concept_id = "output"
            role = "output"
            suffix = "stable output"
        else:
            concept_id = f"visual_stage_{_slug(op_type)}"
            role = "process"
            suffix = "visual stage"
        if "switch" in _strip_family_suffix(op_type).lower():
            switch_like_visual_id = concept_id
        visual_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=visual_ids[index - 1], target=concept_id, kind="data"))

    if control_ids:
        edges.append(
            ConceptEdge(
                source=control_ids[-1],
                target=switch_like_visual_id or visual_ids[min(1, len(visual_ids) - 1)],
                kind="control",
            )
        )

    chain = [*control_chain, *visual_chain]
    role_by_op = {**control_roles, **visual_roles}
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:multi-domain:dat-to-top",
            "atlas-synthesis:family:dat+top",
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    score = min(0.93, _synthesis_score(visual_chain, visual_roles, corpus_evidence) + 0.045)
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:dat_controlled_top",
        compiled_task_id=compiled_task.id,
        label="Atlas-synthesized DAT-controlled TOP operator chain",
        profiles=["generic"],
        pattern_ids=["atlas:synthesized:dat_controlled_top_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker(visual_chain[-1])],
        validation_needs=[
            "output_node_present",
            "render_switch_table_present",
            "top_output_present",
            "cheap_visual_metrics",
        ],
        risk_flags=[
            "atlas-drafted-open-prompt",
            "atlas-synthesized-open-prompt",
            "atlas-multi-domain-control",
        ],
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:retrieved_cards; "
            "family:DAT+TOP; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _draft_chop_export_bound_sop_render_preview_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Draft CHOP export control into a SOP surface rendered to a TOP preview."""

    if not _looks_like_chop_controlled_sop_preview_prompt(task.intent, records):
        return AtlasDraftResult(accepted=False)

    chop_records = [record for record in records if _record_family(record) == "CHOP"]
    sop_records = [record for record in records if _record_family(record) == "SOP"]
    comp_records = [record for record in records if _record_family(record) == "COMP"]
    top_records = [record for record in records if _record_family(record) == "TOP"]
    if len(chop_records) < 2 or len(sop_records) < 2 or len(comp_records) < 2 or len(top_records) < 2:
        return AtlasDraftResult(accepted=False)

    control_chain, control_roles, control_search_evidence = _chop_export_control_operator_chain_search(
        chop_records,
        cards_by_op,
        task.intent,
        corpus_evidence,
    )
    source_chain, source_roles, source_search_evidence = _source_preview_operator_chain_search(
        sop_records,
        "SOP",
        task.intent,
        corpus_evidence,
    )
    if len(control_chain) < 2 or len(source_chain) < 2:
        return AtlasDraftResult(accepted=False)

    channel_source_op = _first_op_with_param(control_chain, cards_by_op, "channelname")
    export_output_op = _last_op_with_param(control_chain, cards_by_op, "exportmethod")
    if channel_source_op is None or export_output_op is None or export_output_op != control_chain[-1]:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=["atlas_draft:sop_export_binding_missing_channelname_or_exportmethod"],
        )

    sop_target = _sop_export_control_target(
        source_chain,
        source_roles,
        cards_by_op,
        intent=task.intent,
    )
    if sop_target is None:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=["atlas_draft:sop_export_binding_missing_docs_grounded_target_param"],
        )
    target_op = sop_target.op_type
    target_param = sop_target.param_name

    render_top = _record_for_op(top_records, "renderTOP")
    output_top = _record_for_op(top_records, "nullTOP")
    geometry_comp = _record_for_op(comp_records, "geometryCOMP")
    camera_comp = _record_for_op(comp_records, "cameraCOMP")
    light_comp = _record_for_op(comp_records, "lightCOMP")
    if render_top is None or output_top is None or geometry_comp is None or camera_comp is None:
        return AtlasDraftResult(accepted=False)

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    control_ids: list[str] = []
    source_ids: list[str] = []

    target_concept_id = ""
    last_control_index = len(control_chain) - 1
    for index, op_type in enumerate(control_chain):
        concept_id = "control_source" if index == 0 else f"control_stage_{_slug(op_type)}"
        role = "source" if index == 0 else ("output" if index == last_control_index else "process")
        suffix = (
            "control source"
            if index == 0
            else ("control output" if index == last_control_index else "control stage")
        )
        control_ids.append(concept_id)
        concept = _concept_for_op(
            op_type,
            concept_id=concept_id,
            label_suffix=suffix,
            role=role,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        concepts.append(concept)
        if index > 0:
            edges.append(ConceptEdge(source=control_ids[index - 1], target=concept_id, kind="data"))

    for index, op_type in enumerate(source_chain):
        if index == 0:
            concept_id = "source"
            suffix = "SOP source"
            role = "source"
        else:
            concept_id = f"source_stage_{_slug(op_type)}"
            suffix = "SOP output" if index == len(source_chain) - 1 else "SOP stage"
            role = "output" if index == len(source_chain) - 1 else "process"
        if op_type == target_op:
            target_concept_id = concept_id
        source_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=source_ids[index - 1], target=concept_id, kind="data"))

    if not target_concept_id:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=["atlas_draft:sop_export_binding_target_not_in_source_chain"],
        )

    target_path_ref = f"${{path:{target_concept_id}}}:{target_param}"
    concepts = [
        concept.model_copy(update={"params": {"channelname": target_path_ref}})
        if concept.op_type == channel_source_op
        else (
            concept.model_copy(update={"params": {"exportmethod": "Channel Name is Path:Parameter"}})
            if concept.op_type == export_output_op and concept.id == control_ids[-1]
            else concept
        )
        for concept in concepts
    ]
    edges.append(ConceptEdge(source=control_ids[-1], target=target_concept_id, kind="control"))

    geometry = _concept_for_op(
        "geometryCOMP",
        concept_id="preview_geometry",
        label_suffix="SOP render geometry",
        role="render",
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    ).model_copy(update={"params": {"sop": f"${{path:{source_ids[-1]}}}"}})
    camera = _concept_for_op(
        "cameraCOMP",
        concept_id="preview_camera",
        label_suffix="render camera",
        role="render",
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    )
    concepts.extend([geometry, camera])
    edges.extend(
        [
            ConceptEdge(source=source_ids[-1], target="preview_geometry", kind="reference"),
            ConceptEdge(source="preview_geometry", target="preview_render", kind="reference"),
            ConceptEdge(source="preview_camera", target="preview_render", kind="reference"),
        ]
    )

    render_params = {
        "geometry": "${path:preview_geometry}",
        "camera": "${path:preview_camera}",
    }
    comp_chain = ["geometryCOMP", "cameraCOMP"]
    comp_roles = {"geometryCOMP": "render", "cameraCOMP": "render"}
    if light_comp is not None:
        light = _concept_for_op(
            "lightCOMP",
            concept_id="preview_light",
            label_suffix="render light",
            role="render",
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        concepts.append(light)
        edges.append(ConceptEdge(source="preview_light", target="preview_render", kind="reference"))
        render_params["lights"] = "${path:preview_light}"
        comp_chain.append("lightCOMP")
        comp_roles["lightCOMP"] = "render"

    render = _concept_for_op(
        "renderTOP",
        concept_id="preview_render",
        label_suffix="TOP render stage",
        role="process",
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    ).model_copy(update={"params": render_params})
    output = _concept_for_op(
        "nullTOP",
        concept_id="output",
        label_suffix="stable preview output",
        role="output",
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    )
    concepts.extend([render, output])
    edges.append(ConceptEdge(source="preview_render", target="output", kind="data"))

    chain = [*control_chain, *source_chain, *comp_chain, "renderTOP", "nullTOP"]
    control_roles = {
        op_type: ("output" if role == "output" else "control") for op_type, role in control_roles.items()
    }
    role_by_op = {
        **control_roles,
        **source_roles,
        **comp_roles,
        "renderTOP": "process",
        "nullTOP": "output",
    }
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    binding_evidence = f"atlas-synthesis:binding:out_chop->{target_op}.{target_param}"
    score = min(
        0.955,
        _synthesis_score(control_chain, control_roles, corpus_evidence) * 0.28
        + _synthesis_score(source_chain, source_roles, corpus_evidence) * 0.34
        + _synthesis_score(
            ["renderTOP", "nullTOP"], {"renderTOP": "process", "nullTOP": "output"}, corpus_evidence
        )
        * 0.26
        + 0.14,
    )
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:typed-role-graph",
            "atlas-synthesis:typed-role-graph-search:v1",
            "atlas-synthesis:role-graph:control->source->preview->output",
            "atlas-synthesis:multi-domain:chop-export-to-sop-render-top-preview",
            "atlas-synthesis:family:chop+sop+comp+top",
            "atlas-synthesis:chop-export-binding:path-parameter",
            "atlas-synthesis:binding-method:Channel Name is Path:Parameter",
            binding_evidence,
            *control_search_evidence,
            *source_search_evidence,
            *_sop_export_control_target_evidence(
                source_chain,
                source_roles,
                cards_by_op,
                sop_target,
                intent=task.intent,
            ),
            f"atlas-synthesis:channelname-source:{channel_source_op}",
            f"atlas-synthesis:exportmethod-output:{export_output_op}",
            f"atlas-synthesis:sop-control-target:{target_op}.{target_param}",
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:chop_export_bound_sop_render_preview",
        compiled_task_id=compiled_task.id,
        label="Atlas-synthesized CHOP export binding into rendered SOP preview",
        profiles=["generic"],
        pattern_ids=["atlas:synthesized:chop_export_bound_sop_render_preview_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker("nullTOP")],
        validation_needs=[
            "output_node_present",
            "control_output",
            "chop_export_method_readback",
            "export_flag_review",
            "geometry_output_present",
            "render_top_output",
            "top_output_present",
            "cheap_visual_metrics",
        ],
        risk_flags=[
            "atlas-drafted-open-prompt",
            "atlas-synthesized-open-prompt",
            "atlas-typed-role-graph",
            "atlas-multi-domain-control",
            "atlas-multi-domain-preview",
            "atlas-chop-export-binding",
            "export-flag-requires-review",
        ],
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:typed_role_graph; "
            "roles:control->source->preview->output; "
            "family:CHOP+SOP+COMP+TOP; "
            "binding:channel_name_path_parameter_export; "
            f"target:{target_op}.{target_param}; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _draft_chop_export_bound_top_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Draft a CHOP path:parameter export binding into a TOP parameter."""

    if not _looks_like_chop_export_bound_top_prompt(task.intent, records):
        return AtlasDraftResult(accepted=False)

    chop_records = [record for record in records if _record_family(record) == "CHOP"]
    top_records = [record for record in records if _record_family(record) == "TOP"]
    if len(chop_records) < 2 or len(top_records) < 2:
        return AtlasDraftResult(accepted=False)

    control_chain, control_roles, control_search_evidence = _chop_export_control_operator_chain_search(
        chop_records,
        cards_by_op,
        task.intent,
        corpus_evidence,
    )
    visual_chain, visual_roles, visual_search_evidence = _source_preview_operator_chain_search(
        top_records,
        "TOP",
        task.intent,
        corpus_evidence,
    )
    if len(visual_chain) < 2:
        visual_chain, visual_roles = _synthesized_operator_chain(top_records, "TOP")
        visual_search_evidence = []
    if len(control_chain) < 2 or len(visual_chain) < 2:
        return AtlasDraftResult(accepted=False)

    if "levelTOP" not in visual_chain:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=["atlas_draft:chop_export_binding_requires_level_top_target"],
        )

    channel_source_op = _first_op_with_param(control_chain, cards_by_op, "channelname")
    export_output_op = _last_op_with_param(control_chain, cards_by_op, "exportmethod")
    if channel_source_op is None or export_output_op is None:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=["atlas_draft:chop_export_binding_missing_channelname_or_exportmethod"],
        )
    if export_output_op != control_chain[-1]:
        return AtlasDraftResult(
            accepted=False,
            rejection_reasons=["atlas_draft:chop_export_binding_requires_exportable_control_output"],
        )

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    control_ids: list[str] = []
    visual_ids: list[str] = []

    level_target_id = f"visual_stage_{_slug('levelTOP')}"
    level_target_path_ref = f"${{path:{level_target_id}}}:brightness1"
    last_control_index = len(control_chain) - 1
    for index, op_type in enumerate(control_chain):
        concept_id = "control_source" if index == 0 else f"control_stage_{_slug(op_type)}"
        role = "source" if index == 0 else ("output" if index == last_control_index else "process")
        suffix = (
            "control source"
            if index == 0
            else ("control output" if index == last_control_index else "control stage")
        )
        control_ids.append(concept_id)
        concept = _concept_for_op(
            op_type,
            concept_id=concept_id,
            label_suffix=suffix,
            role=role,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        if op_type == channel_source_op:
            concept = concept.model_copy(update={"params": {"channelname": level_target_path_ref}})
        if op_type == export_output_op and index == last_control_index:
            concept = concept.model_copy(
                update={"params": {"exportmethod": "Channel Name is Path:Parameter"}}
            )
        concepts.append(concept)
        if index > 0:
            edges.append(ConceptEdge(source=control_ids[index - 1], target=concept_id, kind="data"))

    last_visual_index = len(visual_chain) - 1
    visual_control_target = ""
    for index, op_type in enumerate(visual_chain):
        if index == 0:
            concept_id = "visual_source"
            role = "source"
            suffix = "visual source"
        elif index == last_visual_index:
            concept_id = "output"
            role = "output"
            suffix = "stable output"
        else:
            concept_id = f"visual_stage_{_slug(op_type)}"
            role = "process"
            suffix = "visual stage"
            if not visual_control_target:
                visual_control_target = concept_id
        visual_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=visual_ids[index - 1], target=concept_id, kind="data"))

    if control_ids:
        control_target = visual_control_target or visual_ids[min(1, len(visual_ids) - 1)]
        edges.append(
            ConceptEdge(
                source=control_ids[-1],
                target=control_target,
                kind="control",
                binding=_level_top_control_binding(concepts, control_target),
            )
        )

    chain = [*control_chain, *visual_chain]
    control_roles = {
        op_type: ("output" if role == "output" else "control") for op_type, role in control_roles.items()
    }
    role_by_op = {**control_roles, **visual_roles}
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    score = min(
        0.935,
        _synthesis_score(visual_chain, visual_roles, corpus_evidence)
        + _synthesis_score(control_chain, control_roles, corpus_evidence) * 0.085
        + 0.04,
    )
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:typed-role-graph-search:v1",
            "atlas-synthesis:multi-domain:chop-export-to-top",
            "atlas-synthesis:family:chop+top",
            "atlas-synthesis:chop-export-binding:path-parameter",
            "atlas-synthesis:binding-method:Channel Name is Path:Parameter",
            "atlas-synthesis:binding:out_chop->levelTOP.brightness1",
            *control_search_evidence,
            *visual_search_evidence,
            f"atlas-synthesis:channelname-source:{channel_source_op}",
            f"atlas-synthesis:exportmethod-output:{export_output_op}",
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:chop_export_bound_top",
        compiled_task_id=compiled_task.id,
        label="Atlas-synthesized CHOP path-parameter export binding into TOP",
        profiles=["generic"],
        pattern_ids=["atlas:synthesized:chop_export_bound_top_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker(visual_chain[-1])],
        validation_needs=[
            "output_node_present",
            "control_output",
            "chop_export_method_readback",
            "export_flag_review",
            "top_output_present",
            "cheap_visual_metrics",
        ],
        risk_flags=[
            "atlas-drafted-open-prompt",
            "atlas-synthesized-open-prompt",
            "atlas-multi-domain-control",
            "atlas-chop-export-binding",
            "export-flag-requires-review",
        ],
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:retrieved_cards; "
            "family:CHOP+TOP; "
            "binding:channel_name_path_parameter_export; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _draft_chop_controlled_top_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Draft a CHOP control branch plus a TOP visual branch from official cards."""

    if not _looks_like_chop_controlled_top_prompt(task.intent, records):
        return AtlasDraftResult(accepted=False)

    chop_records = [record for record in records if _record_family(record) == "CHOP"]
    top_records = [record for record in records if _record_family(record) == "TOP"]
    if len(chop_records) < 2 or len(top_records) < 2:
        return AtlasDraftResult(accepted=False)

    control_chain, control_roles, control_search_evidence = _chop_control_operator_chain_search(
        chop_records,
        task.intent,
        corpus_evidence,
    )
    if len(control_chain) < 2:
        control_chain, control_roles = _synthesized_operator_chain(chop_records, "CHOP")
        control_search_evidence = []
    visual_chain, visual_roles, visual_search_evidence = _source_preview_operator_chain_search(
        top_records,
        "TOP",
        task.intent,
        corpus_evidence,
    )
    if len(visual_chain) < 2:
        visual_chain, visual_roles = _synthesized_operator_chain(top_records, "TOP")
        visual_search_evidence = []
    if len(control_chain) < 2 or len(visual_chain) < 2:
        return AtlasDraftResult(accepted=False)

    control_roles = {
        op_type: ("output" if role == "output" else "control") for op_type, role in control_roles.items()
    }

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    control_ids: list[str] = []
    visual_ids: list[str] = []

    last_control_index = len(control_chain) - 1
    for index, op_type in enumerate(control_chain):
        concept_id = "control_source" if index == 0 else f"control_stage_{_slug(op_type)}"
        role = "source" if index == 0 else ("output" if index == last_control_index else "process")
        suffix = (
            "control source"
            if index == 0
            else ("control output" if index == last_control_index else "control stage")
        )
        control_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=control_ids[index - 1], target=concept_id, kind="data"))

    last_visual_index = len(visual_chain) - 1
    visual_control_target = ""
    for index, op_type in enumerate(visual_chain):
        if index == 0:
            concept_id = "visual_source"
            role = "source"
            suffix = "visual source"
        elif index == last_visual_index:
            concept_id = "output"
            role = "output"
            suffix = "stable output"
        else:
            concept_id = f"visual_stage_{_slug(op_type)}"
            role = "process"
            suffix = "visual stage"
            if not visual_control_target:
                visual_control_target = concept_id
        visual_ids.append(concept_id)
        concept = _concept_for_op(
            op_type,
            concept_id=concept_id,
            label_suffix=suffix,
            role=role,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        concepts.append(concept)
        if index > 0:
            edges.append(ConceptEdge(source=visual_ids[index - 1], target=concept_id, kind="data"))

    if control_ids:
        control_target = visual_control_target or visual_ids[min(1, len(visual_ids) - 1)]
        edges.append(
            ConceptEdge(
                source=control_ids[-1],
                target=control_target,
                kind="control",
                binding=_level_top_control_binding(concepts, control_target),
            )
        )

    chain = [*control_chain, *visual_chain]
    role_by_op = {**control_roles, **visual_roles}
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:typed-role-graph-search:v1",
            "atlas-synthesis:multi-domain:chop-to-top",
            "atlas-synthesis:family:chop+top",
            *(
                ["atlas-synthesis:binding:out_chop->levelTOP.brightness1"]
                if "levelTOP" in visual_chain and control_ids
                else []
            ),
            *control_search_evidence,
            *visual_search_evidence,
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    score = min(
        0.93,
        _synthesis_score(visual_chain, visual_roles, corpus_evidence)
        + _synthesis_score(control_chain, control_roles, corpus_evidence) * 0.08
        + 0.035,
    )
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:chop_controlled_top",
        compiled_task_id=compiled_task.id,
        label="Atlas-synthesized CHOP-controlled TOP operator chain",
        profiles=["generic"],
        pattern_ids=["atlas:synthesized:chop_controlled_top_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker(visual_chain[-1])],
        validation_needs=[
            "output_node_present",
            "control_output",
            "top_output_present",
            "cheap_visual_metrics",
        ],
        risk_flags=[
            "atlas-drafted-open-prompt",
            "atlas-synthesized-open-prompt",
            "atlas-multi-domain-control",
        ],
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:typed_role_graph_search; "
            "family:CHOP+TOP; "
            "roles:control->preview->output; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _draft_sop_render_preview_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Draft SOP geometry plus COMP/TOP render references from official cards."""

    if _preview_source_family(task.intent, records) != "SOP":
        return AtlasDraftResult(accepted=False)

    sop_records = [record for record in records if _record_family(record) == "SOP"]
    comp_records = [record for record in records if _record_family(record) == "COMP"]
    top_records = [record for record in records if _record_family(record) == "TOP"]
    if len(sop_records) < 2 or len(comp_records) < 2 or len(top_records) < 2:
        return AtlasDraftResult(accepted=False)

    source_chain, source_roles, source_search_evidence = _source_preview_operator_chain_search(
        sop_records,
        "SOP",
        task.intent,
        corpus_evidence,
    )
    render_top = _record_for_op(top_records, "renderTOP")
    output_top = _record_for_op(top_records, "nullTOP")
    geometry_comp = _record_for_op(comp_records, "geometryCOMP")
    camera_comp = _record_for_op(comp_records, "cameraCOMP")
    light_comp = _record_for_op(comp_records, "lightCOMP")
    if (
        not source_chain
        or render_top is None
        or output_top is None
        or geometry_comp is None
        or camera_comp is None
    ):
        return AtlasDraftResult(accepted=False)

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    source_ids: list[str] = []

    for index, op_type in enumerate(source_chain):
        if index == 0:
            concept_id = "source"
            suffix = "SOP source"
            role = "source"
        else:
            concept_id = f"source_stage_{_slug(op_type)}"
            suffix = "SOP output" if index == len(source_chain) - 1 else "SOP stage"
            role = "output" if index == len(source_chain) - 1 else "process"
        source_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=source_ids[index - 1], target=concept_id, kind="data"))

    geometry = _concept_for_op(
        "geometryCOMP",
        concept_id="preview_geometry",
        label_suffix="SOP render geometry",
        role="render",
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    ).model_copy(update={"params": {"sop": f"${{path:{source_ids[-1]}}}"}})
    camera = _concept_for_op(
        "cameraCOMP",
        concept_id="preview_camera",
        label_suffix="render camera",
        role="render",
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    )
    concepts.extend([geometry, camera])
    edges.extend(
        [
            ConceptEdge(source=source_ids[-1], target="preview_geometry", kind="reference"),
            ConceptEdge(source="preview_geometry", target="preview_render", kind="reference"),
            ConceptEdge(source="preview_camera", target="preview_render", kind="reference"),
        ]
    )

    render_params = {
        "geometry": "${path:preview_geometry}",
        "camera": "${path:preview_camera}",
    }
    comp_chain = ["geometryCOMP", "cameraCOMP"]
    comp_roles = {"geometryCOMP": "render", "cameraCOMP": "render"}
    if light_comp is not None:
        light = _concept_for_op(
            "lightCOMP",
            concept_id="preview_light",
            label_suffix="render light",
            role="render",
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        concepts.append(light)
        edges.append(ConceptEdge(source="preview_light", target="preview_render", kind="reference"))
        render_params["lights"] = "${path:preview_light}"
        comp_chain.append("lightCOMP")
        comp_roles["lightCOMP"] = "render"

    render = _concept_for_op(
        "renderTOP",
        concept_id="preview_render",
        label_suffix="TOP render stage",
        role="process",
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    ).model_copy(update={"params": render_params})
    output = _concept_for_op(
        "nullTOP",
        concept_id="output",
        label_suffix="stable preview output",
        role="output",
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
    )
    concepts.extend([render, output])
    edges.append(ConceptEdge(source="preview_render", target="output", kind="data"))

    chain = [*source_chain, *comp_chain, "renderTOP", "nullTOP"]
    role_by_op = {**source_roles, **comp_roles, "renderTOP": "process", "nullTOP": "output"}
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            "atlas-synthesis:multi-domain:sop-to-render-top-preview",
            "atlas-synthesis:family:sop+comp+top",
            *source_search_evidence,
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    score = min(
        0.94,
        _synthesis_score(source_chain, source_roles, corpus_evidence) * 0.45
        + _synthesis_score(
            ["renderTOP", "nullTOP"], {"renderTOP": "process", "nullTOP": "output"}, corpus_evidence
        )
        * 0.35
        + 0.18,
    )
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:sop_render_preview_top",
        compiled_task_id=compiled_task.id,
        label="Atlas-synthesized SOP render preview TOP operator chain",
        profiles=["generic"],
        pattern_ids=["atlas:synthesized:sop_render_preview_top_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker("nullTOP")],
        validation_needs=[
            "output_node_present",
            "geometry_output_present",
            "render_top_output",
            "top_output_present",
            "cheap_visual_metrics",
        ],
        risk_flags=[
            "atlas-drafted-open-prompt",
            "atlas-synthesized-open-prompt",
            "atlas-multi-domain-preview",
        ],
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:retrieved_cards; "
            "source_role_search:source->process->output; "
            "family:SOP+COMP+TOP; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _draft_source_preview_top_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Draft a geometry/point source branch plus a TOP preview branch from official cards."""

    source_family = _preview_source_family(task.intent, records)
    if source_family is None:
        return AtlasDraftResult(accepted=False)

    return _draft_source_preview_top_candidate_for_family(
        task=task,
        compiled_task=compiled_task,
        records=records,
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
        source_family=source_family,
    )


def _draft_typed_source_preview_graph_candidate(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> AtlasDraftResult:
    """Compose a typed source->preview->output graph from source and TOP cards."""

    source_family = _typed_source_preview_family(task.intent, records)
    if source_family is None:
        return AtlasDraftResult(accepted=False)

    if source_family == "SOP":
        sop_result = _draft_sop_render_preview_candidate(
            task=task,
            compiled_task=compiled_task,
            records=records,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        if not sop_result.accepted or sop_result.candidate_graph is None:
            return AtlasDraftResult(accepted=False)
        candidate = sop_result.candidate_graph
        score = min(0.95, float(candidate.score or 0.0) + 0.01)
        grounding = _dedupe(
            [
                *candidate.grounding_evidence,
                "atlas-synthesis:typed-role-graph",
                "atlas-synthesis:role-graph:source->preview->output",
            ]
        )
        typed_candidate = candidate.model_copy(
            update={
                "id": f"candidate:{compiled_task.id}:atlas:synthesized:typed_role_graph_sop_render_preview_top",
                "label": "Atlas-synthesized typed SOP-to-render-TOP role graph",
                "pattern_ids": ["atlas:synthesized:typed_role_graph_sop_render_preview_top_card_chain"],
                "grounding_evidence": grounding,
                "risk_flags": _dedupe([*candidate.risk_flags, "atlas-typed-role-graph"]),
                "score": round(score, 4),
                "explanation": (
                    "atlas_synthesis:typed_role_graph; "
                    "roles:source->preview->output; "
                    "family:SOP+COMP+TOP; "
                    f"ranking:official_cards:{score:.4f}; "
                    f"operators:{','.join(candidate.required_ops)}"
                ),
            }
        )
        return AtlasDraftResult(
            accepted=True,
            candidate_graph=typed_candidate,
            grounding_evidence=grounding,
        )

    return _draft_source_preview_top_candidate_for_family(
        task=task,
        compiled_task=compiled_task,
        records=records,
        cards_by_op=cards_by_op,
        corpus_evidence=corpus_evidence,
        source_family=source_family,
        typed_role_graph=True,
    )


def _draft_source_preview_top_candidate_for_family(
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
    source_family: str,
    typed_role_graph: bool = False,
) -> AtlasDraftResult:
    """Draft a source branch plus a TOP preview/output branch for one source family."""

    source_records = [record for record in records if _record_family(record) == source_family]
    top_records = [record for record in records if _record_family(record) == "TOP"]
    if len(source_records) < 2 or len(top_records) < 2:
        return AtlasDraftResult(accepted=False)

    source_chain, source_roles = _source_preview_operator_chain(source_records, source_family)
    preview_chain, preview_roles = _top_preview_operator_chain(top_records)
    if len(source_chain) < 2 or len(preview_chain) < 2:
        return AtlasDraftResult(accepted=False)

    concepts: list[ConceptNode] = []
    edges: list[ConceptEdge] = []
    source_ids: list[str] = []
    preview_ids: list[str] = []

    for index, op_type in enumerate(source_chain):
        if index == 0:
            concept_id = "source"
            suffix = f"{source_family} source"
            role = "source"
        else:
            concept_id = f"source_stage_{_slug(op_type)}"
            suffix = f"{source_family} output" if index == len(source_chain) - 1 else f"{source_family} stage"
            role = "output" if index == len(source_chain) - 1 else "process"
        source_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if index > 0:
            edges.append(ConceptEdge(source=source_ids[index - 1], target=concept_id, kind="data"))

    for index, op_type in enumerate(preview_chain):
        if index == len(preview_chain) - 1:
            concept_id = "output"
            suffix = "stable preview output"
            role = "output"
        else:
            concept_id = f"preview_stage_{_slug(op_type)}"
            suffix = "TOP preview stage"
            role = "process"
        preview_ids.append(concept_id)
        concept = _concept_for_op(
            op_type,
            concept_id=concept_id,
            label_suffix=suffix,
            role=role,
            cards_by_op=cards_by_op,
            corpus_evidence=corpus_evidence,
        )
        if index == 0 and source_family == "POP":
            concept = concept.model_copy(update={"params": {"pop": f"${{path:{source_ids[-1]}}}"}})
        concepts.append(concept)
        if index > 0:
            edges.append(ConceptEdge(source=preview_ids[index - 1], target=concept_id, kind="data"))

    edges.append(ConceptEdge(source=source_ids[-1], target=preview_ids[0], kind="reference"))

    chain = [*source_chain, *preview_chain]
    role_by_op = {**source_roles, **preview_roles}
    role_evidence = [f"atlas-synthesis:{role_by_op.get(op_type, 'process')}:{op_type}" for op_type in chain]
    source_key = source_family.lower()
    grounding = _dedupe(
        [
            "atlas-draft:accepted",
            "atlas-synthesis:accepted",
            *(["atlas-synthesis:typed-role-graph"] if typed_role_graph else []),
            *(["atlas-synthesis:role-graph:source->preview->output"] if typed_role_graph else []),
            f"atlas-synthesis:multi-domain:{source_key}-to-top-preview",
            f"atlas-synthesis:family:{source_key}+top",
            *[f"docs:{op_type}" for op_type in chain],
            *role_evidence,
            *corpus_evidence_markers(corpus_evidence),
        ]
    )
    score = min(
        0.92,
        _synthesis_score(source_chain, source_roles, corpus_evidence) * 0.55
        + _synthesis_score(preview_chain, preview_roles, corpus_evidence) * 0.45
        + 0.045,
    )
    validation_needs = [
        "output_node_present",
        "top_output_present",
        "cheap_visual_metrics",
    ]
    validation_needs.extend(
        ["pop_output_attached", "finite_pop_bounds"]
        if source_family == "POP"
        else ["geometry_output_present"]
    )
    candidate = CandidateConceptGraph(
        id=f"candidate:{compiled_task.id}:atlas:synthesized:{source_key}_preview_top",
        compiled_task_id=compiled_task.id,
        label=f"Atlas-synthesized {source_family} preview TOP operator chain",
        profiles=["generic"],
        pattern_ids=[f"atlas:synthesized:{source_key}_preview_top_card_chain"],
        concepts=concepts,
        edges=edges,
        required_ops=chain,
        expected_outputs=[task.output_top or _default_output_marker(preview_chain[-1])],
        validation_needs=_dedupe(validation_needs),
        risk_flags=[
            "atlas-drafted-open-prompt",
            "atlas-synthesized-open-prompt",
            "atlas-multi-domain-preview",
        ],
        grounding_evidence=grounding,
        score=round(score, 4),
        explanation=(
            "atlas_synthesis:retrieved_cards; "
            f"family:{source_family}+TOP; "
            f"ranking:official_cards:{score:.4f}; "
            f"operators:{','.join(chain)}"
        ),
    )
    if typed_role_graph:
        candidate = candidate.model_copy(
            update={
                "id": f"candidate:{compiled_task.id}:atlas:synthesized:typed_role_graph_{source_key}_preview_top",
                "label": f"Atlas-synthesized typed {source_family}-to-TOP role graph",
                "pattern_ids": [f"atlas:synthesized:typed_role_graph_{source_key}_preview_top_card_chain"],
                "risk_flags": _dedupe([*candidate.risk_flags, "atlas-typed-role-graph"]),
                "score": round(min(0.935, score + 0.025), 4),
                "explanation": (
                    "atlas_synthesis:typed_role_graph; "
                    "roles:source->preview->output; "
                    f"family:{source_family}+TOP; "
                    f"ranking:official_cards:{min(0.935, score + 0.025):.4f}; "
                    f"operators:{','.join(chain)}"
                ),
            }
        )
    return AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        grounding_evidence=grounding,
    )


def _docs_evidence_for_route(
    card_index,
    route: OperatorIntentRoute,
) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
    evidence: list[str] = []
    missing: list[str] = []
    cards: dict[str, dict[str, Any]] = {}
    for op_type in route.operator_chain:
        card = _safe_get_operator(card_index, op_type)
        docs_url = _docs_url(card)
        if card is None or not docs_url:
            missing.append(op_type)
            continue
        evidence.append(f"docs:{op_type}")
        cards[op_type] = card
    return evidence, missing, cards


def _safe_get_operator(card_index, op_type: str) -> dict[str, Any] | None:
    if card_index is None:
        return None
    try:
        card = card_index.get_operator(op_type)
    except Exception:
        return None
    return card if isinstance(card, dict) else None


def _docs_url(card: dict[str, Any] | None) -> str:
    if not isinstance(card, dict):
        return ""
    for key in ("docs_url", "source_url", "url", "href"):
        value = card.get(key)
        if isinstance(value, str) and value.startswith(OFFICIAL_DERIVATIVE_DOCS_PREFIX):
            return value
    return ""


def _official_operator_records(
    records: list[CorpusEvidenceRecord],
    card_index,
) -> tuple[list[CorpusEvidenceRecord], dict[str, dict[str, Any]]]:
    selected: dict[str, CorpusEvidenceRecord] = {}
    cards: dict[str, dict[str, Any]] = {}
    for record in records:
        op_type = str(record.op_type or "").strip()
        if not op_type or _is_external_sink_op(op_type):
            continue
        card = _safe_get_operator(card_index, op_type) or _card_from_record(record)
        if not _docs_url(card):
            continue
        current = selected.get(op_type)
        if current is None or record.score > current.score:
            selected[op_type] = record
            cards[op_type] = card
    return list(selected.values()), cards


def _official_route_records(
    route: OperatorIntentRoute,
    card_index,
) -> tuple[list[CorpusEvidenceRecord], dict[str, dict[str, Any]]]:
    records: list[CorpusEvidenceRecord] = []
    cards: dict[str, dict[str, Any]] = {}
    for op_type in route.operator_chain:
        card = _safe_get_operator(card_index, op_type)
        if not _docs_url(card):
            continue
        records.append(_record_from_card(card, route))
        cards[op_type] = card
    return records, cards


def _card_from_record(record: CorpusEvidenceRecord) -> dict[str, Any]:
    return {
        "op_type": record.op_type,
        "family": record.family,
        "display_name": record.display_name or record.op_type,
        "docs_url": record.docs_url,
        "summary": record.summary,
        "key_params": [{"name": name} for name in record.key_params],
        "key_concepts": list(record.key_concepts),
    }


def _record_from_card(card: dict[str, Any], route: OperatorIntentRoute) -> CorpusEvidenceRecord:
    op_type = str(card.get("op_type") or "")
    family = str(card.get("family") or _domain_for_op(op_type))
    return CorpusEvidenceRecord(
        evidence_id=f"corpus:route:{route.route_id}:{op_type}",
        source="docs_search",
        op_type=op_type,
        family=family,
        display_name=str(card.get("display_name") or op_type),
        docs_url=str(card.get("docs_url") or card.get("source_url") or ""),
        summary=str(card.get("summary") or route.description),
        key_params=[
            str(item.get("name"))
            for item in card.get("key_params", [])
            if isinstance(item, dict) and item.get("name")
        ][:12],
        key_concepts=[str(item) for item in card.get("key_concepts", []) if str(item).strip()][:12],
        matched_terms=list(route.terms[:8]),
        query=route.label,
        score=max(0.86, float(route.score or 0.0)),
    )


def _best_synthesis_family(records: list[CorpusEvidenceRecord], *, intent: str = "") -> str | None:
    scores: dict[str, float] = {}
    for record in records:
        family = _record_family(record)
        if family not in {"TOP", "CHOP", "DAT", "SOP", "POP"}:
            continue
        role = _synthesis_role(record)
        role_bonus = {"source": 0.16, "process": 0.08, "output": 0.18}.get(role, 0.0)
        scores[family] = scores.get(family, 0.0) + float(record.score or 0.0) + role_bonus
    if not scores:
        return None
    relevance = {family: _family_intent_relevance(intent, family) for family in scores}
    return max(scores, key=lambda family: (relevance[family], scores[family], _family_priority(family)))


def _non_bridge_records(records: list[CorpusEvidenceRecord]) -> list[CorpusEvidenceRecord]:
    """Exclude typed conversion operators from ordinary branch synthesis."""

    return [record for record in records if str(record.op_type or "") not in _TYPED_BRIDGE_SPECS]


def _synthesized_operator_chain(
    records: list[CorpusEvidenceRecord],
    family: str,
) -> tuple[list[str], dict[str, str]]:
    family_records = [record for record in _non_bridge_records(records) if _record_family(record) == family]
    if len(family_records) < 2:
        return [], {}

    sources = [record for record in family_records if _synthesis_role(record) == "source"]
    processes = [record for record in family_records if _synthesis_role(record) == "process"]
    outputs = [record for record in family_records if _synthesis_role(record) == "output"]
    if not outputs:
        return [], {}

    source = max(sources or processes, key=_source_rank, default=None)
    output = max(outputs, key=_output_rank, default=None)
    if source is None or output is None or source.op_type == output.op_type:
        return [], {}

    stage_records = [record for record in processes if record.op_type not in {source.op_type, output.op_type}]
    stage_records = sorted(stage_records, key=_stage_rank, reverse=True)[:3]
    chain = _dedupe(
        [
            str(source.op_type),
            *[str(record.op_type) for record in stage_records],
            str(output.op_type),
        ]
    )
    if len(chain) < 2 or chain[-1] != output.op_type:
        return [], {}
    role_by_op = {op_type: "process" for op_type in chain}
    role_by_op[str(source.op_type)] = "source"
    role_by_op[str(output.op_type)] = "output"
    return chain, role_by_op


def _looks_like_dat_controlled_top_prompt(
    intent: str,
    records: list[CorpusEvidenceRecord],
) -> bool:
    text = " ".join([intent, *[_record_search_text(record) for record in records]]).lower()
    control_hit = any(
        token in text
        for token in ("cue", "control", "selector", "select", "scene", "look", "index", "table", "switch")
    )
    has_dat = any(_record_family(record) == "DAT" for record in records)
    has_top = any(_record_family(record) == "TOP" for record in records)
    return control_hit and has_dat and has_top


def _looks_like_chop_controlled_top_prompt(
    intent: str,
    records: list[CorpusEvidenceRecord],
) -> bool:
    text = _topology_request_intent_text(intent).lower()
    control_hit = any(
        token in text
        for token in (
            "control",
            "controlled",
            "modulation",
            "modulate",
            "oscillator",
            "lfo",
            "audio reactive",
            "brightness",
        )
    )
    has_chop = any(_record_family(record) == "CHOP" for record in records)
    has_top = any(_record_family(record) == "TOP" for record in records)
    return control_hit and has_chop and has_top


def _looks_like_chop_export_bound_top_prompt(
    intent: str,
    records: list[CorpusEvidenceRecord],
) -> bool:
    intent_text = intent.lower()
    export_hit = any(
        token in intent_text
        for token in (
            "export",
            "exporting",
            "bind",
            "binding",
            "parameter",
            "override",
        )
    )
    if not export_hit:
        return False
    has_chop = any(_record_family(record) == "CHOP" for record in records)
    has_top = any(_record_family(record) == "TOP" for record in records)
    target_hit = any(
        token in intent_text
        for token in (
            "brightness",
            "level",
            "texture",
            "visual",
            "top",
            "image",
            "wash",
        )
    )
    return target_hit and has_chop and has_top


def _looks_like_chop_controlled_sop_preview_prompt(
    intent: str,
    records: list[CorpusEvidenceRecord],
) -> bool:
    text = " ".join([intent, *[_record_search_text(record) for record in records]]).lower()
    control_hit = any(
        token in text
        for token in (
            "control",
            "controlled",
            "modulation",
            "modulate",
            "oscillator",
            "lfo",
            "audio reactive",
            "drive",
            "driven",
            "reactive",
            "export",
            "binding",
        )
    )
    sop_hit = any(
        token in text
        for token in (
            "sop",
            "surface",
            "terrain",
            "mesh",
            "geometry",
            "displacement",
            "height",
        )
    )
    preview_hit = any(
        token in text
        for token in (
            "preview",
            "render",
            "visual",
            "texture",
            "top output",
            "output",
        )
    )
    families = {_record_family(record) for record in records}
    return control_hit and sop_hit and preview_hit and {"CHOP", "SOP", "COMP", "TOP"}.issubset(families)


def _looks_like_typed_role_chop_top_prompt(
    intent: str,
    records: list[CorpusEvidenceRecord],
) -> bool:
    text = _topology_request_intent_text(intent).lower()
    has_chop = any(_record_family(record) == "CHOP" for record in records)
    has_top = any(_record_family(record) == "TOP" for record in records)
    if not has_chop or not has_top:
        return False
    signal_hit = any(
        token in text
        for token in (
            "signal",
            "waveform",
            "wave",
            "channel",
            "channels",
            "curve",
            "curves",
            "pulse",
            "pulses",
            "range",
            "shaping",
            "shaped",
            "shapes",
            "drive",
            "driven",
            "maps",
            "mapping",
            "reactive",
            "respond",
        )
    )
    visual_hit = any(
        token in text
        for token in (
            "texture",
            "visual",
            "image",
            "top",
            "wash",
            "field",
            "procedural",
            "output",
        )
    )
    return signal_hit and visual_hit


def _preview_source_family(intent: str, records: list[CorpusEvidenceRecord]) -> str | None:
    text = " ".join([intent, *[_record_search_text(record) for record in records]]).lower()
    preview_hit = any(
        token in text
        for token in ("preview", "render", "display", "view", "inspect", "simple top", "top output")
    )
    if not preview_hit or not any(_record_family(record) == "TOP" for record in records):
        return None
    branchable_families: list[str] = []
    for family in ("POP", "SOP"):
        family_records = [record for record in records if _record_family(record) == family]
        source_chain, _source_roles = _source_preview_operator_chain(family_records, family)
        if len(source_chain) >= 2:
            branchable_families.append(family)
    if not branchable_families:
        return None
    return max(
        branchable_families,
        key=lambda family: (_family_intent_relevance(intent, family), _family_priority(family)),
    )


def _typed_source_preview_family(intent: str, records: list[CorpusEvidenceRecord]) -> str | None:
    intent_text = (intent or "").lower()
    if _intent_has_preview_route_terms(intent_text):
        return None

    visual_output_hit = any(
        token in intent_text
        for token in (
            "image",
            "visual",
            "texture",
            "output",
            "result",
            "screen",
            "picture",
        )
    )
    if not visual_output_hit or not any(_record_family(record) == "TOP" for record in records):
        return None

    top_chain, _top_roles = _top_preview_operator_chain(
        [record for record in records if _record_family(record) == "TOP"]
    )
    if len(top_chain) < 2:
        return None

    record_text = " ".join([intent_text, *[_record_search_text(record) for record in records]])
    pop_source_hit = any(
        token in record_text
        for token in (
            "point field",
            "point",
            "points",
            "particle",
            "particles",
            "pop",
        )
    )
    if pop_source_hit:
        pop_chain, _pop_roles = _source_preview_operator_chain(
            [record for record in records if _record_family(record) == "POP"],
            "POP",
        )
        if len(pop_chain) >= 2:
            return "POP"
    sop_source_hit = any(
        token in record_text
        for token in (
            "surface",
            "mesh",
            "sop",
            "geometry",
            "height field",
            "heightfield",
        )
    )
    if not sop_source_hit:
        return None

    sop_records = [record for record in records if _record_family(record) == "SOP"]
    comp_records = [record for record in records if _record_family(record) == "COMP"]
    top_records = [record for record in records if _record_family(record) == "TOP"]
    sop_chain, _sop_roles = _source_preview_operator_chain(sop_records, "SOP")
    if (
        len(sop_chain) >= 2
        and _record_for_op(comp_records, "geometryCOMP") is not None
        and _record_for_op(comp_records, "cameraCOMP") is not None
        and _record_for_op(top_records, "renderTOP") is not None
        and _record_for_op(top_records, "nullTOP") is not None
    ):
        return "SOP"
    return None


def _intent_has_preview_route_terms(intent_text: str) -> bool:
    return any(
        token in intent_text
        for token in ("preview", "render", "display", "view", "inspect", "simple top", "top output")
    )


def _looks_like_typed_dat_pipeline_prompt(
    intent: str,
    records: list[CorpusEvidenceRecord],
) -> bool:
    text = " ".join([intent, *[_record_search_text(record) for record in records]]).lower()
    has_dat = any(_record_family(record) == "DAT" for record in records)
    protocol_hit = any(
        token in text
        for token in (
            "com port",
            "serial",
            "udp",
            "osc",
            "websocket",
            "mqtt",
            "packet",
            "packets",
            "message",
            "messages",
            "sensor",
            "receive",
            "listen",
            "subscribe",
            "read",
        )
    )
    table_hit = any(
        token in text
        for token in (
            "table",
            "row",
            "rows",
            "normalize",
            "normalized",
            "parse",
            "diagnostic",
            "diagnostics",
            "stable output",
        )
    )
    has_stage = any(_dat_pipeline_role(record) == "process" for record in records)
    return has_dat and protocol_hit and table_hit and has_stage


def _typed_dat_pipeline_operator_chain(
    records: list[CorpusEvidenceRecord],
    intent: str = "",
) -> tuple[list[str], dict[str, str]]:
    records = _non_bridge_records(records)
    if len(records) < 3:
        return [], {}

    sources = [record for record in records if _dat_pipeline_role(record) == "source"]
    processes = [record for record in records if _dat_pipeline_role(record) == "process"]
    outputs = [record for record in records if _dat_pipeline_role(record) == "output"]
    if not sources or not processes or not outputs:
        return [], {}

    source = max(sources, key=lambda record: _dat_pipeline_source_rank(record, intent))
    output = max(outputs, key=_output_rank)
    stage_records = [
        record
        for record in sorted(processes, key=_dat_pipeline_stage_rank, reverse=True)
        if record.op_type not in {source.op_type, output.op_type}
    ][:3]
    if not stage_records:
        return [], {}

    chain = _dedupe(
        [
            str(source.op_type),
            *[str(record.op_type) for record in stage_records],
            str(output.op_type),
        ]
    )
    if len(chain) < 3 or chain[0] != source.op_type or chain[-1] != output.op_type:
        return [], {}
    role_by_op = {op_type: "process" for op_type in chain}
    role_by_op[str(source.op_type)] = "source"
    role_by_op[str(output.op_type)] = "output"
    return chain, role_by_op


def _dat_pipeline_role(record: CorpusEvidenceRecord) -> str:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    text = _record_search_text(record)
    if base.startswith("null") or ("stable" in text and "output" in text):
        return "output"
    if _is_protocol_dat_source_record(record):
        return "source"
    if base in {"table", "select", "evaluate", "sort", "shuffle", "convert", "merge"}:
        return "process"
    if any(token in text for token in ("normalize", "normalized", "parse", "processing stage", "diagnostic")):
        return "process"
    if "source" in text or "input" in text:
        return "source"
    return "process"


def _is_protocol_dat_source_record(record: CorpusEvidenceRecord) -> bool:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    text = _record_search_text(record)
    if base in {"udpin", "serial", "oscin", "websocket", "mqttclient", "midiin"}:
        return True
    return base.endswith("in") and any(
        token in text for token in ("dat", "message", "packet", "sensor", "protocol")
    )


def _dat_pipeline_source_rank(record: CorpusEvidenceRecord, intent: str = "") -> tuple[int, int, float, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    order = {
        "serial": 100,
        "udpin": 98,
        "oscin": 96,
        "websocket": 94,
        "mqttclient": 92,
        "midiin": 90,
    }
    rank = max((value for key, value in order.items() if key == base), default=40)
    return (
        _record_intent_relevance(intent, record),
        rank,
        float(record.score or 0.0),
        str(record.op_type or ""),
    )


def _dat_pipeline_stage_rank(record: CorpusEvidenceRecord) -> tuple[int, float, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    order = {
        "table": 100,
        "select": 90,
        "evaluate": 86,
        "convert": 82,
        "sort": 78,
        "shuffle": 74,
        "merge": 70,
    }
    rank = max((value for key, value in order.items() if key == base), default=20)
    return (rank, float(record.score or 0.0), str(record.op_type or ""))


def _dat_control_operator_chain(
    records: list[CorpusEvidenceRecord],
) -> tuple[list[str], dict[str, str]]:
    records = _non_bridge_records(records)
    if not records:
        return [], {}

    sources = [record for record in records if _dat_control_role(record) == "control"]
    stages = [record for record in records if _dat_control_role(record) == "control_stage"]
    source = max(sources or records, key=_dat_control_rank, default=None)
    if source is None:
        return [], {}
    stage_records = [
        record
        for record in sorted(stages, key=_dat_control_rank, reverse=True)
        if record.op_type != source.op_type
    ][:2]
    chain = _dedupe([str(source.op_type), *[str(record.op_type) for record in stage_records]])
    roles = {op_type: "control" for op_type in chain}
    roles[str(source.op_type)] = "control"
    return chain, roles


def _dat_control_role(record: CorpusEvidenceRecord) -> str:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    text = _record_search_text(record)
    if base.startswith("table") or "cue table" in text or ("table" in text and "source" in text):
        return "control"
    if base.startswith(("select", "evaluate", "sort", "shuffle")) or "select" in text:
        return "control_stage"
    return "control_stage"


def _dat_control_rank(record: CorpusEvidenceRecord) -> tuple[int, float, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    order = {
        "table": 90,
        "select": 80,
        "evaluate": 70,
        "sort": 60,
        "shuffle": 55,
    }
    rank = max((value for key, value in order.items() if key in base), default=10)
    return (rank, float(record.score or 0.0), str(record.op_type or ""))


def _top_preview_operator_chain(
    records: list[CorpusEvidenceRecord],
) -> tuple[list[str], dict[str, str]]:
    records = _non_bridge_records(records)
    render_candidates = [record for record in records if _top_preview_role(record) == "process"]
    outputs = [record for record in records if _top_preview_role(record) == "output"]
    if not render_candidates or not outputs:
        return [], {}
    render = max(render_candidates, key=_top_preview_rank)
    output = max(
        [record for record in outputs if record.op_type != render.op_type],
        key=_output_rank,
        default=None,
    )
    if output is None:
        return [], {}
    chain = _dedupe([str(render.op_type), str(output.op_type)])
    if len(chain) < 2:
        return [], {}
    return chain, {str(render.op_type): "process", str(output.op_type): "output"}


def _top_preview_role(record: CorpusEvidenceRecord) -> str:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    text = _record_search_text(record)
    if base.startswith("null") or ("stable" in text and "output" in text):
        return "output"
    if "render" in base or "preview" in text or "display" in text:
        return "process"
    return "other"


def _top_preview_rank(record: CorpusEvidenceRecord) -> tuple[int, float, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    order = {
        "rendersimple": 100,
        "render": 90,
        "geometry": 70,
        "level": 40,
    }
    rank = max((value for key, value in order.items() if key in base), default=10)
    return (rank, float(record.score or 0.0), str(record.op_type or ""))


def _source_preview_operator_chain(
    records: list[CorpusEvidenceRecord],
    family: str,
    search_roles: tuple[str, ...] = ("source", "process", "output"),
) -> tuple[list[str], dict[str, str]]:
    drafts = _source_preview_path_drafts(records, family, "", records, search_roles=search_roles)
    if not drafts:
        return [], {}
    selected = drafts[0]
    return list(selected.chain), dict(selected.role_by_op)


def _source_preview_operator_chain_search(
    records: list[CorpusEvidenceRecord],
    family: str,
    intent: str,
    corpus_evidence: list[CorpusEvidenceRecord],
    search_roles: tuple[str, ...] = ("source", "process", "output"),
) -> tuple[list[str], dict[str, str], list[str]]:
    drafts = _source_preview_path_drafts(
        records,
        family,
        intent,
        corpus_evidence,
        search_roles=search_roles,
    )
    if not drafts:
        return [], {}, []
    selected = drafts[0]
    return (
        list(selected.chain),
        dict(selected.role_by_op),
        _source_preview_path_search_evidence(drafts, selected),
    )


def _chop_export_control_operator_chain_search(
    records: list[CorpusEvidenceRecord],
    cards_by_op: dict[str, dict[str, Any]],
    intent: str,
    corpus_evidence: list[CorpusEvidenceRecord],
) -> tuple[list[str], dict[str, str], list[str]]:
    """Search for an exportable CHOP control branch from retrieved cards."""

    drafts = [
        draft
        for draft in _source_preview_path_drafts(
            records,
            "CHOP",
            intent,
            corpus_evidence,
            search_roles=("control", "process", "output"),
        )
        if _first_op_with_param(draft.chain, cards_by_op, "channelname") is not None
        and _last_op_with_param(draft.chain, cards_by_op, "exportmethod") == draft.chain[-1]
    ]
    if not drafts:
        return [], {}, []
    selected = drafts[0]
    return (
        list(selected.chain),
        dict(selected.role_by_op),
        _chop_export_control_path_search_evidence(drafts, selected, cards_by_op),
    )


def _chop_control_operator_chain_search(
    records: list[CorpusEvidenceRecord],
    intent: str,
    corpus_evidence: list[CorpusEvidenceRecord],
) -> tuple[list[str], dict[str, str], list[str]]:
    """Search for a CHOP control branch from retrieved source/process/output cards."""

    drafts = _source_preview_path_drafts(
        records,
        "CHOP",
        intent,
        corpus_evidence,
        search_roles=("control", "process", "output"),
    )
    if not drafts:
        return [], {}, []
    selected = drafts[0]
    return (
        list(selected.chain),
        dict(selected.role_by_op),
        _chop_control_path_search_evidence(drafts, selected),
    )


def _chop_control_path_search_evidence(
    drafts: list[_SourcePreviewPathDraft],
    selected: _SourcePreviewPathDraft,
) -> list[str]:
    evidence = _typed_role_path_search_evidence_header(drafts, selected)
    for index, draft in enumerate(drafts[:4], start=1):
        marker_kind = "selected" if draft.chain == selected.chain else "alternative"
        evidence.append(
            "atlas-synthesis:role-graph-candidate:"
            f"CHOP:{index}:{marker_kind}:{'>'.join(draft.chain)}:"
            f"{draft.score:.4f}:control:{draft.source_relevance}:"
            f"process:{draft.process_relevance}:process_priority:{draft.process_priority}:"
            f"output:{draft.output_relevance}"
        )
    for op_type in selected.chain:
        role = selected.role_by_op.get(op_type, "process")
        control_role = "output" if role == "output" else "control"
        evidence.append(f"atlas-synthesis:role-node:CHOP:{control_role}:{op_type}")
    return evidence


def _chop_export_control_path_search_evidence(
    drafts: list[_SourcePreviewPathDraft],
    selected: _SourcePreviewPathDraft,
    cards_by_op: dict[str, dict[str, Any]],
) -> list[str]:
    evidence = [
        *_typed_role_path_search_evidence_header(drafts, selected),
        "atlas-synthesis:control-branch-exportable:true",
    ]
    for index, draft in enumerate(drafts[:4], start=1):
        marker_kind = "selected" if draft.chain == selected.chain else "alternative"
        channel_source = _first_op_with_param(draft.chain, cards_by_op, "channelname") or "none"
        export_output = _last_op_with_param(draft.chain, cards_by_op, "exportmethod") or "none"
        evidence.append(
            "atlas-synthesis:role-graph-candidate:"
            f"CHOP:{index}:{marker_kind}:{'>'.join(draft.chain)}:"
            f"{draft.score:.4f}:source:{draft.source_relevance}:"
            f"process:{draft.process_relevance}:output:{draft.output_relevance}:"
            f"channelname:{channel_source}:exportmethod:{export_output}"
        )
    for op_type in selected.chain:
        role = selected.role_by_op.get(op_type, "process")
        control_role = "output" if role == "output" else "control"
        evidence.append(f"atlas-synthesis:role-node:CHOP:{control_role}:{op_type}")
    return evidence


def _source_preview_path_drafts(
    records: list[CorpusEvidenceRecord],
    family: str,
    intent: str,
    corpus_evidence: list[CorpusEvidenceRecord],
    *,
    search_roles: tuple[str, ...] = ("source", "process", "output"),
) -> list[_SourcePreviewPathDraft]:
    return _typed_role_path_drafts(
        records,
        family,
        intent,
        corpus_evidence,
        search_roles=search_roles,
        record_role=lambda record: _source_preview_role(record, family),
        source_rank=_source_preview_source_search_rank,
        process_rank=_source_preview_process_search_rank,
        output_rank=_source_preview_output_search_rank,
        process_priority=_source_preview_process_priority,
    )


def _typed_role_path_drafts(
    records: list[CorpusEvidenceRecord],
    family: str,
    intent: str,
    corpus_evidence: list[CorpusEvidenceRecord],
    *,
    search_roles: tuple[str, ...],
    record_role: Callable[[CorpusEvidenceRecord], str],
    source_rank: Callable[[CorpusEvidenceRecord, str], tuple],
    process_rank: Callable[[CorpusEvidenceRecord, str], tuple],
    output_rank: Callable[[CorpusEvidenceRecord, str], tuple],
    process_priority: Callable[[CorpusEvidenceRecord], int],
) -> list[_SourcePreviewPathDraft]:
    """Enumerate a bounded typed role path from retrieved operator cards."""

    family_records = [record for record in _non_bridge_records(records) if _record_family(record) == family]
    if len(family_records) < 2:
        return []

    canonical_search_roles = search_roles or ("source", "process", "output")
    sources = [record for record in family_records if record_role(record) == "source"]
    processes = [record for record in family_records if record_role(record) == "process"]
    outputs = [record for record in family_records if record_role(record) == "output"]
    ranked_sources = sorted(sources, key=lambda record: source_rank(record, intent), reverse=True)[:4]
    ranked_outputs = sorted(outputs, key=lambda record: output_rank(record, intent), reverse=True)[:3]
    ranked_processes = sorted(
        processes,
        key=lambda record: process_rank(record, intent),
        reverse=True,
    )[:5]
    if not ranked_sources or not ranked_outputs:
        return []

    drafts: list[_SourcePreviewPathDraft] = []
    for source in ranked_sources:
        for output in ranked_outputs:
            if source.op_type == output.op_type:
                continue
            available_processes = [
                record
                for record in ranked_processes
                if record.op_type not in {source.op_type, output.op_type}
            ]
            stage_sets = _source_preview_stage_sets(available_processes, intent)
            for stage_records in stage_sets:
                chain = _dedupe(
                    [
                        str(source.op_type),
                        *[str(record.op_type) for record in stage_records],
                        str(output.op_type),
                    ]
                )
                if len(chain) < 2 or chain[-1] != output.op_type:
                    continue
                role_by_op = {op_type: "process" for op_type in chain}
                role_by_op[str(source.op_type)] = "source"
                role_by_op[str(output.op_type)] = "output"
                source_rel = _record_intent_relevance(intent, source)
                process_rel = max(
                    (_record_intent_relevance(intent, record) for record in stage_records),
                    default=0,
                )
                process_priority_value = max(
                    (process_priority(record) for record in stage_records),
                    default=0,
                )
                output_rel = _record_intent_relevance(intent, output)
                score = _source_preview_path_score(
                    chain,
                    role_by_op,
                    source=source,
                    processes=stage_records,
                    output=output,
                    intent=intent,
                    corpus_evidence=corpus_evidence,
                )
                drafts.append(
                    _SourcePreviewPathDraft(
                        family=family,
                        chain=chain,
                        role_by_op=role_by_op,
                        score=score,
                        source_relevance=source_rel,
                        process_relevance=process_rel,
                        process_priority=process_priority_value,
                        output_relevance=output_rel,
                        search_roles=canonical_search_roles,
                    )
                )
    return sorted(drafts, key=_source_preview_path_rank_key, reverse=True)


def _source_preview_stage_sets(
    processes: list[CorpusEvidenceRecord],
    intent: str,
) -> list[list[CorpusEvidenceRecord]]:
    if not processes:
        return [[]]
    preferred = sorted(
        processes,
        key=lambda record: _source_preview_process_search_rank(record, intent),
        reverse=True,
    )
    stage_sets: list[list[CorpusEvidenceRecord]] = []
    stage_sets.append(preferred[:1])
    if len(preferred) > 1:
        stage_sets.append(preferred[:2])
    for record in preferred[1:4]:
        stage_sets.append([record])
    return _dedupe_record_stage_sets(stage_sets)


def _dedupe_record_stage_sets(
    stage_sets: list[list[CorpusEvidenceRecord]],
) -> list[list[CorpusEvidenceRecord]]:
    seen: set[tuple[str, ...]] = set()
    unique: list[list[CorpusEvidenceRecord]] = []
    for records in stage_sets:
        key = tuple(str(record.op_type or "") for record in records)
        if key in seen:
            continue
        seen.add(key)
        unique.append(records)
    return unique


def _source_preview_source_search_rank(
    record: CorpusEvidenceRecord,
    intent: str,
) -> tuple[int, tuple[int, float, str]]:
    return (_record_intent_relevance(intent, record), _source_preview_source_rank(record))


def _source_preview_process_search_rank(
    record: CorpusEvidenceRecord,
    intent: str,
) -> tuple[int, int, tuple[int, float, str]]:
    return (
        _record_intent_relevance(intent, record),
        _source_preview_process_priority(record),
        _stage_rank(record),
    )


def _source_preview_output_search_rank(
    record: CorpusEvidenceRecord,
    intent: str,
) -> tuple[int, tuple[int, float, str]]:
    return (_record_intent_relevance(intent, record), _output_rank(record))


def _source_preview_path_rank_key(
    draft: _SourcePreviewPathDraft,
) -> tuple[int, int, int, int, int, float, str]:
    return (
        draft.source_relevance,
        draft.process_relevance,
        draft.process_priority,
        draft.output_relevance,
        -len(draft.chain),
        draft.score,
        ",".join(draft.chain),
    )


def _source_preview_path_score(
    chain: list[str],
    role_by_op: dict[str, str],
    *,
    source: CorpusEvidenceRecord,
    processes: list[CorpusEvidenceRecord],
    output: CorpusEvidenceRecord,
    intent: str,
    corpus_evidence: list[CorpusEvidenceRecord],
) -> float:
    process_relevance = max(
        (_record_intent_relevance(intent, record) for record in processes),
        default=0,
    )
    relevance = (
        _record_intent_relevance(intent, source)
        + process_relevance
        + _record_intent_relevance(intent, output)
    )
    return round(
        min(0.96, _synthesis_score(chain, role_by_op, corpus_evidence) + min(0.075, relevance * 0.012)),
        4,
    )


def _source_preview_path_search_evidence(
    drafts: list[_SourcePreviewPathDraft],
    selected: _SourcePreviewPathDraft,
) -> list[str]:
    evidence = _typed_role_path_search_evidence_header(drafts, selected)
    for index, draft in enumerate(drafts[:4], start=1):
        marker_kind = "selected" if draft.chain == selected.chain else "alternative"
        evidence.append(
            "atlas-synthesis:role-graph-candidate:"
            f"{selected.family}:{index}:{marker_kind}:{'>'.join(draft.chain)}:"
            f"{draft.score:.4f}:source:{draft.source_relevance}:"
            f"process:{draft.process_relevance}:process_priority:{draft.process_priority}:"
            f"output:{draft.output_relevance}"
        )
    for op_type in selected.chain:
        evidence.append(
            "atlas-synthesis:role-node:"
            f"{selected.family}:{selected.role_by_op.get(op_type, 'process')}:{op_type}"
        )
    return evidence


def _typed_role_path_search_evidence_header(
    drafts: list[_SourcePreviewPathDraft],
    selected: _SourcePreviewPathDraft,
) -> list[str]:
    role_path = selected.search_roles or ("source", "process", "output")
    role_path_marker = "->".join(role_path)
    rank = _typed_role_path_selected_rank(drafts, selected)
    return [
        "atlas-synthesis:typed-role-path-search:v1",
        (f"atlas-synthesis:typed-role-path-search:v1:{selected.family}:{role_path_marker}"),
        f"atlas-synthesis:role-graph-search:{selected.family}:{role_path_marker}",
        f"atlas-synthesis:role-graph-candidate-count:{selected.family}:{len(drafts)}",
        (f"atlas-synthesis:role-graph-selected:{selected.family}:{rank}:{'>'.join(selected.chain)}"),
    ]


def _typed_role_path_selected_rank(
    drafts: list[_SourcePreviewPathDraft],
    selected: _SourcePreviewPathDraft,
) -> int:
    return next(
        (index for index, draft in enumerate(drafts, start=1) if draft.chain == selected.chain),
        1,
    )


def _source_preview_role(record: CorpusEvidenceRecord, family: str) -> str:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    text = _record_search_text(record)
    if base.startswith("null") or ("stable" in text and "output" in text):
        return "output"
    if family == "POP":
        if base in {"noise", "mathmix", "attributecombine", "transform"}:
            return "process"
        if base in {"circle", "grid", "line", "rectangle", "sphere", "box"} or "point field" in text:
            return "source"
    if family == "SOP":
        if base in {"noise", "transform", "facet", "subdivide", "convert"}:
            return "process"
        if base in {"grid", "sphere", "box", "line", "circle"} or "geometry source" in text:
            return "source"
    return _synthesis_role(record)


def _source_preview_source_rank(record: CorpusEvidenceRecord) -> tuple[int, float, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    order = {
        "circle": 100,
        "grid": 95,
        "sphere": 90,
        "box": 85,
        "line": 80,
        "rectangle": 75,
    }
    rank = max((value for key, value in order.items() if key == base), default=20)
    return (rank, float(record.score or 0.0), str(record.op_type or ""))


def _source_preview_process_priority(record: CorpusEvidenceRecord) -> int:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    text = _record_search_text(record)
    if base in {"noise", "displace", "deform"} or any(
        token in text for token in ("displace", "displacement", "deform")
    ):
        return 95
    if base in {"facet", "subdivide", "convert", "mathmix", "attributecombine"}:
        return 78
    if base in {"level", "color", "composite", "cache", "feedback"}:
        return 70
    if base == "transform":
        return 45
    return 50


def _sop_export_control_target(
    source_chain: list[str],
    source_roles: dict[str, str],
    cards_by_op: dict[str, dict[str, Any]],
    *,
    intent: str,
) -> _SopExportControlTargetDraft | None:
    candidates = _sop_export_control_target_candidates(
        source_chain,
        source_roles,
        cards_by_op,
        intent=intent,
    )
    return candidates[0] if candidates else None


def _sop_export_control_target_candidates(
    source_chain: list[str],
    source_roles: dict[str, str],
    cards_by_op: dict[str, dict[str, Any]],
    *,
    intent: str,
) -> list[_SopExportControlTargetDraft]:
    param_priority = (
        "amp",
        "amplitude",
        "height",
        "strength",
        "amount",
        "scale",
        "offset",
        "ty",
    )
    priority_by_param = {
        param_name: len(param_priority) - index for index, param_name in enumerate(param_priority)
    }
    candidates: list[_SopExportControlTargetDraft] = []
    for index, op_type in enumerate(source_chain):
        role = source_roles.get(op_type)
        if role not in {"process", "source"}:
            continue
        param_names = _card_param_names(cards_by_op.get(op_type))
        if not param_names:
            continue
        intent_relevance = _card_intent_relevance(intent, op_type, cards_by_op.get(op_type))
        role_priority = 2 if role == "process" else 1
        for param_name in param_priority:
            if param_name not in param_names:
                continue
            param_rank = priority_by_param[param_name]
            score = round(
                min(
                    0.99,
                    0.42
                    + (role_priority * 0.12)
                    + (param_rank * 0.018)
                    + min(0.18, intent_relevance * 0.018)
                    + max(0.0, 0.08 - (index * 0.01)),
                ),
                4,
            )
            candidates.append(
                _SopExportControlTargetDraft(
                    op_type=op_type,
                    param_name=param_name,
                    role=role,
                    chain_index=index,
                    param_priority=param_rank,
                    intent_relevance=intent_relevance,
                    score=score,
                )
            )
    return sorted(candidates, key=_sop_export_control_target_rank_key, reverse=True)


def _sop_export_control_target_rank_key(
    candidate: _SopExportControlTargetDraft,
) -> tuple[int, int, int, float, int, str, str]:
    role_priority = 2 if candidate.role == "process" else 1
    return (
        role_priority,
        candidate.param_priority,
        candidate.intent_relevance,
        candidate.score,
        -candidate.chain_index,
        candidate.op_type,
        candidate.param_name,
    )


def _sop_export_control_target_evidence(
    source_chain: list[str],
    source_roles: dict[str, str],
    cards_by_op: dict[str, dict[str, Any]],
    selected: _SopExportControlTargetDraft,
    *,
    intent: str,
) -> list[str]:
    candidates = _sop_export_control_target_candidates(
        source_chain,
        source_roles,
        cards_by_op,
        intent=intent,
    )
    evidence = [
        f"atlas-synthesis:sop-control-target-selected:{selected.op_type}.{selected.param_name}",
        f"atlas-synthesis:sop-control-target-candidate-count:{len(candidates)}",
    ]
    for index, candidate in enumerate(candidates[:4], start=1):
        marker_kind = (
            "selected"
            if candidate.op_type == selected.op_type and candidate.param_name == selected.param_name
            else "alternative"
        )
        evidence.append(
            "atlas-synthesis:sop-control-target-candidate:"
            f"{index}:{marker_kind}:{candidate.op_type}.{candidate.param_name}:"
            f"{candidate.score:.4f}:role:{candidate.role}:"
            f"param_priority:{candidate.param_priority}:intent:{candidate.intent_relevance}"
        )
    return evidence


def _card_intent_relevance(intent: str, op_type: str, card: dict[str, Any] | None) -> int:
    intent_text = _topology_request_intent_text(intent)
    intent_tokens = set(re.findall(r"[a-z0-9]+", intent_text.lower()))
    if not intent_tokens:
        return 0
    card_text = _card_search_text(op_type, card)
    card_tokens = set(re.findall(r"[a-z0-9]+", card_text))
    overlap = len(intent_tokens.intersection(card_tokens))
    phrase_hits = sum(1 for token in intent_tokens if token and token in card_text)
    return overlap + min(4, phrase_hits)


def _card_search_text(op_type: str, card: dict[str, Any] | None) -> str:
    key_params = []
    for item in (card or {}).get("key_params") or []:
        if isinstance(item, dict):
            key_params.append(str(item.get("name") or ""))
    return " ".join(
        [
            op_type,
            str((card or {}).get("display_name") or ""),
            str((card or {}).get("summary") or ""),
            " ".join(str(item) for item in (card or {}).get("key_concepts") or []),
            " ".join(key_params),
        ]
    ).lower()


def _record_family(record: CorpusEvidenceRecord) -> str:
    if record.family:
        return str(record.family).upper()
    op_type = str(record.op_type or "")
    for suffix in ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP"):
        if op_type.endswith(suffix):
            return suffix
    return ""


def _record_for_op(records: list[CorpusEvidenceRecord], op_type: str) -> CorpusEvidenceRecord | None:
    return max(
        [record for record in records if record.op_type == op_type],
        key=lambda record: float(record.score or 0.0),
        default=None,
    )


_TYPED_BRIDGE_SPECS: dict[str, tuple[str, str, str]] = {
    "dattoCHOP": ("DAT", "CHOP", "dat"),
    "dattoSOP": ("DAT", "SOP", "dat"),
    "dattoPOP": ("DAT", "POP", "dat"),
    "choptoDAT": ("CHOP", "DAT", "chop"),
    "choptoTOP": ("CHOP", "TOP", "chop"),
    "choptoSOP": ("CHOP", "SOP", "chop"),
    "soptoCHOP": ("SOP", "CHOP", "sop"),
    "soptoDAT": ("SOP", "DAT", "sop"),
    "soptoPOP": ("SOP", "POP", "sop"),
    "poptoCHOP": ("POP", "CHOP", "pop"),
    "poptoDAT": ("POP", "DAT", "pop"),
    "poptoSOP": ("POP", "SOP", "pop"),
    "poptoTOP": ("POP", "TOP", "pop"),
    "toptoCHOP": ("TOP", "CHOP", "top"),
}


def _typed_bridge_spec(records: list[CorpusEvidenceRecord]) -> _TypedBridgeSpec | None:
    specs = _typed_bridge_specs(records)
    return specs[0] if specs else None


def _typed_bridge_specs(records: list[CorpusEvidenceRecord]) -> list[_TypedBridgeSpec]:
    bridge_records = [record for record in records if str(record.op_type or "") in _TYPED_BRIDGE_SPECS]
    if not bridge_records:
        return []
    families = {_record_family(record) for record in records}
    candidates: list[tuple[int, float, str, _TypedBridgeSpec]] = []
    for record in bridge_records:
        op_type = str(record.op_type or "")
        source_family, target_family, source_param = _TYPED_BRIDGE_SPECS[op_type]
        if source_family not in families or target_family not in families:
            continue
        candidates.append(
            (
                _bridge_family_priority(source_family, target_family),
                float(record.score or 0.0),
                op_type,
                _TypedBridgeSpec(
                    op_type=op_type,
                    source_family=source_family,
                    target_family=target_family,
                    source_param=source_param,
                ),
            )
        )
    if not candidates:
        return []
    return [
        item[3]
        for item in sorted(
            candidates,
            key=lambda item: (item[0], item[1], item[2]),
            reverse=True,
        )
    ]


def _bridge_family_priority(source_family: str, target_family: str) -> int:
    priority = {
        ("DAT", "CHOP"): 100,
        ("CHOP", "TOP"): 95,
        ("POP", "TOP"): 90,
        ("DAT", "SOP"): 85,
        ("SOP", "CHOP"): 80,
    }
    return priority.get((source_family, target_family), 40)


def _typed_bridge_paths(
    bridges: list[_TypedBridgeSpec],
    *,
    max_hops: int,
    include_single: bool = False,
) -> list[tuple[_TypedBridgeSpec, ...]]:
    paths: list[tuple[_TypedBridgeSpec, ...]] = []

    def visit(path: tuple[_TypedBridgeSpec, ...]) -> None:
        if len(path) >= (1 if include_single else 2):
            paths.append(path)
        if len(path) >= max_hops:
            return
        used_ops = {bridge.op_type for bridge in path}
        tail = path[-1]
        for next_bridge in bridges:
            if next_bridge.op_type in used_ops:
                continue
            if tail.target_family != next_bridge.source_family:
                continue
            visit((*path, next_bridge))

    for bridge in bridges:
        visit((bridge,))
    return paths


def _draft_typed_bridge_path(
    bridge_path: tuple[_TypedBridgeSpec, ...],
    intent: str,
    records: list[CorpusEvidenceRecord],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> _TypedBridgePathDraft | None:
    branch_bridge_ops = set(_TYPED_BRIDGE_SPECS)
    first_bridge = bridge_path[0]
    source_records = [
        record
        for record in records
        if _record_family(record) == first_bridge.source_family
        and str(record.op_type or "") not in branch_bridge_ops
    ]
    source_chain, source_roles = _source_branch_operator_chain(
        source_records,
        first_bridge.source_family,
        intent,
    )
    if not source_chain:
        return None

    intermediate_chains: list[list[str]] = []
    intermediate_roles: list[dict[str, str]] = []
    for bridge in bridge_path[:-1]:
        mid_records = [
            record
            for record in records
            if _record_family(record) == bridge.target_family
            and str(record.op_type or "") not in branch_bridge_ops
        ]
        mid_chain, mid_role_by_op = _target_branch_operator_chain(mid_records, bridge.target_family)
        if not mid_chain or mid_role_by_op.get(mid_chain[-1]) != "output":
            return None
        intermediate_chains.append(mid_chain)
        intermediate_roles.append(mid_role_by_op)

    final_bridge = bridge_path[-1]
    target_records = [
        record
        for record in records
        if _record_family(record) == final_bridge.target_family
        and str(record.op_type or "") not in branch_bridge_ops
    ]
    target_chain, target_roles = _target_branch_operator_chain(
        target_records,
        final_bridge.target_family,
    )
    if not target_chain:
        return None

    role_by_op = _typed_bridge_path_roles(
        source_roles=source_roles,
        intermediate_roles=tuple(intermediate_roles),
        target_roles=target_roles,
        bridges=bridge_path,
    )
    chain = [
        *source_chain,
        *[
            op_type
            for index, bridge in enumerate(bridge_path)
            for op_type in (
                [bridge.op_type, *intermediate_chains[index]]
                if index < len(bridge_path) - 1
                else [bridge.op_type]
            )
        ],
        *target_chain,
    ]
    score = _typed_bridge_path_score(
        source_chain=source_chain,
        source_roles=source_roles,
        intermediate_chains=tuple(intermediate_chains),
        intermediate_roles=tuple(intermediate_roles),
        target_chain=target_chain,
        target_roles=target_roles,
        bridges=bridge_path,
        corpus_evidence=corpus_evidence,
    )
    return _TypedBridgePathDraft(
        bridges=bridge_path,
        source_chain=source_chain,
        source_roles=source_roles,
        intermediate_chains=tuple(intermediate_chains),
        intermediate_roles=tuple(intermediate_roles),
        target_chain=target_chain,
        target_roles=target_roles,
        priority=sum(
            _bridge_family_priority(bridge.source_family, bridge.target_family) for bridge in bridge_path
        ),
        source_relevance=_family_intent_relevance(intent, first_bridge.source_family),
        target_relevance=_family_intent_relevance(intent, final_bridge.target_family),
        score=max(score, _synthesis_score(chain, role_by_op, corpus_evidence)),
    )


def _typed_bridge_path_rank_key(item: _TypedBridgePathDraft) -> tuple[int, int, int, float, int, str]:
    return (
        item.source_relevance,
        item.target_relevance,
        item.priority,
        item.score,
        len(item.bridges),
        ",".join(bridge.op_type for bridge in item.bridges),
    )


def _typed_bridge_path_rank(
    candidates: list[_TypedBridgePathDraft],
    candidate: _TypedBridgePathDraft,
) -> int:
    for index, draft in enumerate(candidates, start=1):
        if draft is candidate or draft.bridges == candidate.bridges:
            return index
    return 0


def _typed_bridge_path_search_evidence(
    candidates: list[_TypedBridgePathDraft],
    candidate: _TypedBridgePathDraft,
) -> list[str]:
    if not candidates:
        return []
    ranked = sorted(candidates, key=_typed_bridge_path_rank_key, reverse=True)
    rank = _typed_bridge_path_rank(ranked, candidate)
    evidence = [
        f"atlas-synthesis:typed-bridge-candidate-count:{len(ranked)}",
        (
            "atlas-synthesis:typed-bridge-path:"
            f"{rank}:{_typed_bridge_path_family_id(candidate)}:{_typed_bridge_path_bridge_id(candidate)}"
        ),
        (
            "atlas-synthesis:typed-bridge-source-relevance:"
            f"{candidate.bridges[0].source_family}:{candidate.source_relevance}"
        ),
        (
            "atlas-synthesis:typed-bridge-target-relevance:"
            f"{candidate.bridges[-1].target_family}:{candidate.target_relevance}"
        ),
    ]
    if rank == 1:
        evidence.append(
            "atlas-synthesis:typed-bridge-selected:"
            f"{_typed_bridge_path_family_id(candidate)}:{_typed_bridge_path_bridge_id(candidate)}"
        )
    elif rank > 1:
        evidence.append(
            "atlas-synthesis:typed-bridge-alternative:"
            f"{rank}:{_typed_bridge_path_family_id(candidate)}:{_typed_bridge_path_bridge_id(candidate)}"
        )
    if len(ranked) > 1:
        evidence.append(f"atlas-synthesis:typed-bridge-alternative-count:{len(ranked) - 1}")
    for index, draft in enumerate(ranked[:4], start=1):
        evidence.append(
            "atlas-synthesis:typed-bridge-candidate:"
            f"{index}:{_typed_bridge_path_family_id(draft)}:"
            f"{_typed_bridge_path_bridge_id(draft)}:"
            f"source:{draft.source_relevance}:target:{draft.target_relevance}:{draft.score:.4f}"
        )
    return evidence


def _typed_bridge_path_family_id(draft: _TypedBridgePathDraft) -> str:
    return "_to_".join(
        family.lower()
        for family in [
            draft.bridges[0].source_family,
            *[bridge.target_family for bridge in draft.bridges],
        ]
    )


def _typed_bridge_path_bridge_id(draft: _TypedBridgePathDraft) -> str:
    return "+".join(bridge.op_type for bridge in draft.bridges)


def _typed_bridge_path_alternative_summary(candidates: list[_TypedBridgePathDraft]) -> str:
    alternatives = [
        (
            f"{_typed_bridge_path_family_id(draft)}:{_typed_bridge_path_bridge_id(draft)}:"
            f"s{draft.source_relevance}:t{draft.target_relevance}"
        )
        for draft in candidates[1:4]
    ]
    return ",".join(alternatives) if alternatives else "none"


def _typed_bridge_path_roles(
    *,
    source_roles: dict[str, str],
    intermediate_roles: tuple[dict[str, str], ...],
    target_roles: dict[str, str],
    bridges: tuple[_TypedBridgeSpec, ...],
) -> dict[str, str]:
    role_by_op: dict[str, str] = dict(source_roles)
    for index, bridge in enumerate(bridges):
        role_by_op[bridge.op_type] = "bridge"
        if index < len(intermediate_roles):
            role_by_op.update(intermediate_roles[index])
    role_by_op.update(target_roles)
    return role_by_op


def _typed_bridge_path_score(
    *,
    source_chain: list[str],
    source_roles: dict[str, str],
    intermediate_chains: tuple[list[str], ...],
    intermediate_roles: tuple[dict[str, str], ...],
    target_chain: list[str],
    target_roles: dict[str, str],
    bridges: tuple[_TypedBridgeSpec, ...],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> float:
    branch_scores = [_synthesis_score(source_chain, source_roles, corpus_evidence)]
    for index, chain in enumerate(intermediate_chains):
        bridge = bridges[index]
        roles = {bridge.op_type: "bridge", **intermediate_roles[index]}
        branch_scores.append(_synthesis_score([bridge.op_type, *chain], roles, corpus_evidence))
    final_bridge = bridges[-1]
    final_roles = {final_bridge.op_type: "bridge", **target_roles}
    branch_scores.append(
        _synthesis_score([final_bridge.op_type, *target_chain], final_roles, corpus_evidence)
    )
    average_branch_score = sum(branch_scores) / max(1, len(branch_scores))
    return min(0.97, average_branch_score * 0.78 + min(0.14, 0.035 * len(bridges)) + 0.08)


def _typed_bridge_path_role_graph(bridge_count: int) -> str:
    return "source" + "->bridge->process->output" * bridge_count


def _family_intent_relevance(intent: str, family: str) -> int:
    text = _topology_request_intent_text(intent).lower()
    phrase_terms = {
        "CHOP": ("control channels", "sampled into control", "audio reactive"),
        "DAT": ("table rows", "text table", "data table"),
        "POP": ("point field", "particle field"),
        "SOP": ("geometry mesh", "render geometry"),
        "TOP": ("texture output", "preview texture", "visual output"),
    }
    token_terms = {
        "CHOP": (
            "audio",
            "channel",
            "channels",
            "chop",
            "control",
            "lfo",
            "midi",
            "oscillator",
            "sample",
            "sampled",
            "signal",
        ),
        "COMP": ("component", "comp", "container", "panel", "ui"),
        "DAT": (
            "csv",
            "dat",
            "json",
            "message",
            "mqtt",
            "packet",
            "protocol",
            "row",
            "rows",
            "table",
            "text",
            "udp",
            "websocket",
        ),
        "MAT": ("material", "mat", "shader"),
        "POP": ("field", "particle", "particles", "point", "points", "pop"),
        "SOP": ("curve", "geometry", "mesh", "shape", "sop", "surface"),
        "TOP": (
            "image",
            "pixel",
            "pixels",
            "preview",
            "render",
            "texture",
            "top",
            "video",
            "visual",
        ),
    }
    score = 0
    for phrase in phrase_terms.get(family, ()):
        if phrase in text:
            score += 4
    tokens = set(re.findall(r"[a-z0-9]+", text))
    score += sum(1 for term in token_terms.get(family, ()) if term in tokens)
    return score


def _source_branch_operator_chain(
    records: list[CorpusEvidenceRecord],
    family: str,
    intent: str = "",
) -> tuple[list[str], dict[str, str]]:
    family_records = [record for record in _non_bridge_records(records) if _record_family(record) == family]
    if not family_records:
        return [], {}
    sources = [record for record in family_records if _source_branch_role(record, family) == "source"]
    processes = [record for record in family_records if _source_branch_role(record, family) == "process"]
    outputs = [record for record in family_records if _source_branch_role(record, family) == "output"]
    source = max(sources, key=lambda record: _source_branch_source_rank(record, intent), default=None)
    if source is None:
        return [], {}
    stage_records = [
        record
        for record in sorted(processes, key=_stage_rank, reverse=True)
        if record.op_type != source.op_type
    ][:3]
    output = max(
        [record for record in outputs if record.op_type != source.op_type],
        key=_output_rank,
        default=None,
    )
    chain = _dedupe(
        [
            str(source.op_type),
            *[str(record.op_type) for record in stage_records],
            *([str(output.op_type)] if output is not None else []),
        ]
    )
    role_by_op = {op_type: "process" for op_type in chain}
    role_by_op[str(source.op_type)] = "source"
    if output is not None:
        role_by_op[str(output.op_type)] = "output"
    return chain, role_by_op


def _bridge_role_graph_label(source_chain: list[str], source_roles: dict[str, str]) -> str:
    source_roles_in_chain = [source_roles.get(op_type, "process") for op_type in source_chain]
    if source_roles_in_chain and source_roles_in_chain[-1] == "output":
        return "source->process->output->bridge->process->output"
    return "source->bridge->process->output"


def _append_role_chain_concepts(
    *,
    concepts: list[ConceptNode],
    edges: list[ConceptEdge],
    chain: list[str],
    role_by_op: dict[str, str],
    first_concept_id: str,
    stage_prefix: str,
    family: str,
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
    initial_source: str | None = None,
    final_output_id: str | None = None,
) -> list[str]:
    concept_ids: list[str] = []
    previous_id = initial_source
    last_index = len(chain) - 1
    for index, op_type in enumerate(chain):
        role = role_by_op.get(op_type, "process")
        if index == 0:
            concept_id = first_concept_id
        elif final_output_id and index == last_index and role == "output":
            concept_id = final_output_id
        else:
            concept_id = f"{stage_prefix}_{_slug(op_type)}"
        suffix = (
            f"{family} source"
            if role == "source"
            else (f"stable {family} output" if role == "output" else f"{family} processing stage")
        )
        concept_ids.append(concept_id)
        concepts.append(
            _concept_for_op(
                op_type,
                concept_id=concept_id,
                label_suffix=suffix,
                role=role,
                cards_by_op=cards_by_op,
                corpus_evidence=corpus_evidence,
            )
        )
        if previous_id is not None:
            edges.append(ConceptEdge(source=previous_id, target=concept_id, kind="data"))
        previous_id = concept_id
    return concept_ids


def _source_branch_role(record: CorpusEvidenceRecord, family: str) -> str:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    text = _record_search_text(record)
    if family == "DAT":
        if base in {"select", "evaluate", "sort", "shuffle", "convert", "merge"}:
            return "process"
        if base == "table" and any(
            token in text for token in ("normalize", "normalized", "parse", "processing stage", "diagnostic")
        ):
            return "process"
        if base == "table" and any(token in text for token in ("source", "input", "rows", "sensor")):
            return "source"
        if _is_protocol_dat_source_record(record) or "source" in text or "input" in text:
            return "source"
        return "process"
    if family == "CHOP":
        if base in {"math", "filter", "lag", "limit", "select", "rename"}:
            return "process"
        if base.endswith("in") or base in {"wave", "lfo", "noise", "constant"}:
            return "source"
    if family in {"SOP", "POP"}:
        return _source_preview_role(record, family)
    if "source" in text or "input" in text:
        return "source"
    return _synthesis_role(record)


def _source_branch_source_rank(record: CorpusEvidenceRecord, intent: str = "") -> tuple[int, int, float, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    order = {
        "table": 100,
        "serial": 96,
        "udpin": 94,
        "oscin": 92,
        "websocket": 90,
        "mqttclient": 88,
        "wave": 86,
        "lfo": 84,
        "noise": 82,
        "constant": 80,
        "grid": 78,
        "circle": 76,
    }
    rank = max((value for key, value in order.items() if key == base), default=20)
    return (
        _record_intent_relevance(intent, record),
        rank,
        float(record.score or 0.0),
        str(record.op_type or ""),
    )


def _target_branch_operator_chain(
    records: list[CorpusEvidenceRecord],
    family: str,
) -> tuple[list[str], dict[str, str]]:
    family_records = [record for record in _non_bridge_records(records) if _record_family(record) == family]
    if not family_records:
        return [], {}
    outputs = [record for record in family_records if _target_branch_role(record, family) == "output"]
    output = max(outputs, key=_output_rank, default=None)
    if output is None:
        return [], {}
    processes = [
        record
        for record in sorted(family_records, key=_stage_rank, reverse=True)
        if record.op_type != output.op_type and _target_branch_role(record, family) == "process"
    ][:3]
    chain = _dedupe([*[str(record.op_type) for record in processes], str(output.op_type)])
    role_by_op = {op_type: "process" for op_type in chain}
    role_by_op[str(output.op_type)] = "output"
    return chain, role_by_op


def _target_branch_role(record: CorpusEvidenceRecord, family: str) -> str:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    text = _record_search_text(record)
    if base.startswith("null") or ("stable" in text and "output" in text):
        return "output"
    if family == "TOP" and ("render" in base or "preview" in text or "display" in text):
        return "process"
    if base.endswith("in"):
        return "source"
    return "process"


def _synthesis_role(record: CorpusEvidenceRecord) -> str:
    op_type = str(record.op_type or "")
    base = _strip_family_suffix(op_type).lower()
    text = _record_search_text(record)
    if base.startswith("null") or ("stable" in text and "output" in text):
        return "output"
    if any(token in base for token in ("switch", "select", "level", "transform", "cache", "feedback")):
        return "process"
    if (
        base.endswith("in")
        or "input" in text
        or "source" in text
        or base.startswith(("audiofilein", "moviefilein", "videodevicein", "kinect", "ndiin"))
        or base in {"noise", "constant", "text", "circle", "grid", "pattern", "ramp", "table"}
    ):
        return "source"
    return "process"


def _record_search_text(record: CorpusEvidenceRecord) -> str:
    return " ".join(
        [
            str(record.op_type or ""),
            record.display_name,
            record.summary,
            " ".join(record.key_concepts),
            " ".join(record.matched_terms),
        ]
    ).lower()


def _record_intent_relevance(intent: str, record: CorpusEvidenceRecord) -> int:
    intent_text = _topology_request_intent_text(intent)
    intent_tokens = set(re.findall(r"[a-z0-9]+", intent_text.lower()))
    if not intent_tokens:
        return 0
    record_text = _record_search_text(record)
    record_tokens = set(re.findall(r"[a-z0-9]+", record_text))
    overlap = len(intent_tokens.intersection(record_tokens))
    phrase_hits = sum(1 for token in intent_tokens if token and token in record_text)
    return overlap + min(4, phrase_hits)


def _topology_request_intent_text(intent: str) -> str:
    clauses = re.split(r"(?i)(?:\bwhile\b|\bwhere\b|\bwhen\b|;|,)", intent)
    kept: list[str] = []
    for clause in clauses:
        stripped = clause.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        is_card_context = (
            "distractor" in lower
            or "cards" in lower
            or "card" in lower
            or "docs" in lower
            or "also available" in lower
            or "also present" in lower
        )
        if kept and is_card_context:
            continue
        kept.append(stripped)
    return " ".join(kept) or intent


def _source_rank(record: CorpusEvidenceRecord) -> tuple[float, int, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    source_bonus = 2 if base.endswith("in") or base.startswith(("moviefilein", "videodevicein")) else 0
    procedural_bonus = 1 if base in {"noise", "constant", "text", "circle", "grid", "pattern", "ramp"} else 0
    return (float(record.score or 0.0), source_bonus + procedural_bonus, str(record.op_type or ""))


def _stage_rank(record: CorpusEvidenceRecord) -> tuple[int, float, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    order = {
        "cache": 90,
        "feedback": 85,
        "transform": 75,
        "displace": 70,
        "switch": 68,
        "level": 65,
        "color": 60,
        "composite": 55,
        "math": 50,
        "filter": 45,
        "lag": 40,
    }
    stage_order = max((value for key, value in order.items() if key in base), default=10)
    return (stage_order, float(record.score or 0.0), str(record.op_type or ""))


def _output_rank(record: CorpusEvidenceRecord) -> tuple[int, float, str]:
    base = _strip_family_suffix(str(record.op_type or "")).lower()
    null_bonus = 2 if base.startswith("null") else 0
    text = _record_search_text(record)
    stable_bonus = 1 if "stable" in text and "output" in text else 0
    return (null_bonus + stable_bonus, float(record.score or 0.0), str(record.op_type or ""))


def _family_priority(family: str) -> int:
    return {"TOP": 5, "CHOP": 4, "DAT": 3, "POP": 2, "SOP": 1}.get(family, 0)


def _is_external_sink_op(op_type: str) -> bool:
    base = _strip_family_suffix(op_type).lower()
    return any(
        token in base
        for token in (
            "moviefileout",
            "videodeviceout",
            "audiodeviceout",
            "audiofileout",
            "directdisplayout",
            "directxout",
            "ndiout",
            "syphonout",
            "spoutout",
            "touchout",
        )
    )


def _is_device_source_op(op_type: str) -> bool:
    base = _strip_family_suffix(op_type).lower()
    return any(
        token in base
        for token in (
            "devicein",
            "kinect",
            "ndiin",
            "midiin",
            "serial",
            "oscin",
            "websocket",
            "mqtt",
            "udpin",
        )
    )


def _validation_needs_for_family(family: str) -> list[str]:
    if family == "TOP":
        return ["output_node_present", "top_output_present", "cheap_visual_metrics"]
    if family == "CHOP":
        return ["output_node_present", "control_output"]
    if family == "DAT":
        return ["output_node_present", "protocol_table_output"]
    if family == "POP":
        return ["output_node_present", "pop_output_attached", "finite_pop_bounds"]
    if family == "SOP":
        return ["output_node_present", "geometry_output_present"]
    return ["output_node_present"]


def _synthesis_score(
    chain: list[str],
    role_by_op: dict[str, str],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> float:
    records_by_op = {str(record.op_type): record for record in corpus_evidence if record.op_type}
    chain_scores = [float(records_by_op[op_type].score) for op_type in chain if op_type in records_by_op]
    evidence_score = sum(chain_scores) / len(chain_scores) if chain_scores else 0.0
    role_coverage = len(set(role_by_op.values()).intersection({"source", "process", "output"})) / 3.0
    length_bonus = min(0.08, max(0, len(chain) - 2) * 0.025)
    return round(min(0.88, 0.54 + (evidence_score * 0.22) + (role_coverage * 0.08) + length_bonus), 4)


def _concept_for_op(
    op_type: str,
    *,
    concept_id: str,
    label_suffix: str,
    role: str,
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> ConceptNode:
    card = cards_by_op.get(op_type)
    display = str((card or {}).get("display_name") or op_type)
    return ConceptNode(
        id=concept_id,
        label=f"{display} {label_suffix}",
        role=role,
        domain=_domain_for_op(op_type),
        op_type=op_type,
        evidence=_dedupe([f"docs:{op_type}", *_record_markers_for_op(corpus_evidence, op_type)]),
    )


def _first_op_with_param(
    chain: list[str],
    cards_by_op: dict[str, dict[str, Any]],
    param_name: str,
) -> str | None:
    for op_type in chain:
        if param_name in _card_param_names(cards_by_op.get(op_type)):
            return op_type
    return None


def _last_op_with_param(
    chain: list[str],
    cards_by_op: dict[str, dict[str, Any]],
    param_name: str,
) -> str | None:
    for op_type in reversed(chain):
        if param_name in _card_param_names(cards_by_op.get(op_type)):
            return op_type
    return None


def _card_param_names(card: dict[str, Any] | None) -> set[str]:
    names: set[str] = set()
    for item in (card or {}).get("key_params") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def _concepts_for_route(
    route: OperatorIntentRoute,
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> list[ConceptNode]:
    return _concepts_for_chain(list(route.operator_chain), cards_by_op, corpus_evidence)


def _concepts_for_chain(
    operator_chain: list[str] | tuple[str, ...],
    cards_by_op: dict[str, dict[str, Any]],
    corpus_evidence: list[CorpusEvidenceRecord],
) -> list[ConceptNode]:
    concepts: list[ConceptNode] = []
    last_index = len(operator_chain) - 1
    for index, op_type in enumerate(operator_chain):
        concepts.append(
            ConceptNode(
                id=_concept_id(op_type, index=index, last_index=last_index),
                label=_concept_label(op_type, cards_by_op.get(op_type), index=index, last_index=last_index),
                role=_concept_role(index=index, last_index=last_index),
                domain=_domain_for_op(op_type),
                op_type=op_type,
                evidence=_dedupe([f"docs:{op_type}", *_record_markers_for_op(corpus_evidence, op_type)]),
            )
        )
    return concepts


def _record_markers_for_op(records: list[CorpusEvidenceRecord], op_type: str) -> list[str]:
    return [record.evidence_id for record in records if record.op_type == op_type]


def _concept_id(op_type: str, *, index: int, last_index: int) -> str:
    if index == 0:
        return "source"
    if index == last_index:
        return "output"
    return f"stage_{index}_{_slug(_strip_family_suffix(op_type))}"


def _concept_label(
    op_type: str,
    card: dict[str, Any] | None,
    *,
    index: int,
    last_index: int,
) -> str:
    display = str((card or {}).get("display_name") or op_type)
    if index == 0:
        return f"{display} source"
    if index == last_index:
        return f"Stable {display} output"
    return f"{display} stage"


def _concept_role(*, index: int, last_index: int) -> str:
    if index == 0:
        return "source"
    if index == last_index:
        return "output"
    return "process"


def _domain_for_op(op_type: str) -> DataDomain:
    for suffix in ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP"):
        if op_type.endswith(suffix):
            return suffix  # type: ignore[return-value]
    return "ANY"


def _default_output_marker(op_type: str) -> str:
    domain = _domain_for_op(op_type)
    if domain == "CHOP":
        return "out_chop"
    if domain == "DAT":
        return "out_dat"
    if domain == "POP":
        return "out_pop"
    return "out1"


def _level_top_control_binding(
    concepts: list[ConceptNode],
    target_concept_id: str,
) -> dict[str, Any] | None:
    target = next((item for item in concepts if item.id == target_concept_id), None)
    if target is None or target.op_type != "levelTOP":
        return None
    return {
        "mode": "chop_reference_expression",
        "source_channel": 0,
        "target_param": "brightness1",
    }


def _candidate_score(
    *,
    route: OperatorIntentRoute,
    corpus_evidence: list[CorpusEvidenceRecord],
) -> float:
    route_ops = set(route.operator_chain)
    scored_records = [record.score for record in corpus_evidence if record.op_type in route_ops]
    evidence_score = sum(scored_records) / len(scored_records) if scored_records else 0.0
    return round(min(0.94, 0.58 + (route.score * 0.24) + (evidence_score * 0.12)), 4)


def _strip_family_suffix(op_type: str) -> str:
    for suffix in ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP"):
        if op_type.endswith(suffix):
            return op_type[: -len(suffix)]
    return op_type


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "operator"


def _dedupe(items: list[str]) -> list[str]:
    return [item for item in dict.fromkeys(items) if item]
