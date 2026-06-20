"""Typed models for TDPilot's visual programming brain layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from td_mcp.models.patch import PatchPlan, PatchPreview, PatchResult

BrainProfile = Literal[
    "generic",
    "feedback",
    "audio_reactive",
    "pop",
    "glsl",
    "glsl_material",
    "glsl_pop",
    "render_pipeline",
    "panel_ui",
    "control_rig",
]

ConceptRole = Literal[
    "source",
    "process",
    "feedback",
    "control",
    "render",
    "output",
    "material",
    "ui",
    "validator",
]

DataDomain = Literal["TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT", "ANY"]


class VisualTaskSpec(BaseModel):
    """Natural-language task plus concrete TD execution boundaries."""

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(min_length=1)
    target_root: str = "/project1"
    output_top: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    preferred_domains: list[DataDomain] = Field(default_factory=list)
    validation_profile: str = "auto"
    include_memory: bool = True
    include_docs: bool = True


class ConceptNode(BaseModel):
    """One semantic building block in a TD visual-programming plan."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    role: ConceptRole
    domain: DataDomain = "ANY"
    op_type: str | None = None
    create_type: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    required: bool = True
    evidence: list[str] = Field(default_factory=list)


class ConceptEdge(BaseModel):
    """A semantic/data-flow edge between concept nodes."""

    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    kind: Literal["data", "control", "reference", "feedback"] = "data"
    source_index: int = Field(default=0, ge=0)
    target_index: int = Field(default=0, ge=0)


class ConceptGraph(BaseModel):
    """Grounded concept graph that explains why a patch plan is valid."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: VisualTaskSpec
    profile: BrainProfile = "generic"
    concepts: list[ConceptNode] = Field(default_factory=list)
    edges: list[ConceptEdge] = Field(default_factory=list)
    operators: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _edges_reference_known_concepts(self) -> ConceptGraph:
        ids = {node.id for node in self.concepts}
        for edge in self.edges:
            if edge.source not in ids:
                raise ValueError(f"edge source references unknown concept id: {edge.source}")
            if edge.target not in ids:
                raise ValueError(f"edge target references unknown concept id: {edge.target}")
        if not self.operators:
            self.operators = sorted({node.op_type for node in self.concepts if node.op_type})
        return self


class ValidationIssue(BaseModel):
    """One validation finding with stable severity."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warning", "error", "critical"]
    code: str
    message: str
    path: str | None = None
    source: str = "tdpilot-brain"


class ValidationReportV2(BaseModel):
    """Profile-aware validation report for brain executions."""

    model_config = ConfigDict(extra="forbid")

    profile: str = "structural_visual_safe"
    concept_profile: str | None = None
    target_root: str
    ok: bool
    checks: list[str] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    cheap_metrics: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class TransactionOptions(BaseModel):
    """Safe defaults for model-directed TD mutations."""

    model_config = ConfigDict(extra="forbid")

    preflight: bool = True
    snapshot_before: bool = True
    rollback_on_apply_failure: bool = True
    rollback_on_validation_failure: bool = True
    dry_run: bool = False
    max_ops: int = Field(default=80, ge=1, le=500)
    validation_profile: str = "structural_visual_safe"


class BrainPlan(BaseModel):
    """High-level plan that wraps a typed PatchPlan with grounding metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: Literal["brain"] = "brain"
    task: VisualTaskSpec
    concept_graph: ConceptGraph
    patch_plan: PatchPlan
    validation_profile: str = "structural_visual_safe"
    blocked_questions: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    grounding_evidence: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TransactionResult(BaseModel):
    """Transactional execution envelope around PatchResult."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    status: Literal["dry_run", "blocked", "clean", "warnings", "broken", "rolled_back"]
    options: TransactionOptions = Field(default_factory=TransactionOptions)
    preview: PatchPreview | None = None
    apply_result: PatchResult | None = None
    before_snapshot_id: str | None = None
    after_snapshot_id: str | None = None
    validation_report: ValidationReportV2 | None = None
    validation_failed: bool = False
    rollback_performed: bool = False
    rollback_error: str | None = None
    needs_manual_recovery: bool = False
    failed_op: int | None = None
    failed_reason: str | None = None
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class BrainTrace(BaseModel):
    """Compact trace record for evals and validated task memory."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: str
    profile: str
    target_root: str
    operators: list[str] = Field(default_factory=list)
    plan_id: str | None = None
    transaction_id: str | None = None
    transaction_status: str | None = None
    validation_ok: bool | None = None
    rollback_performed: bool = False
    learned_memory_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    "BrainPlan",
    "BrainProfile",
    "BrainTrace",
    "ConceptEdge",
    "ConceptGraph",
    "ConceptNode",
    "DataDomain",
    "TransactionOptions",
    "TransactionResult",
    "ValidationIssue",
    "ValidationReportV2",
    "VisualTaskSpec",
]
