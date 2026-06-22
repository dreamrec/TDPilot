"""Typed models for TDPilot's visual programming brain layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    "midi_control",
    "dat_protocol",
    "video_io",
    "concept_compiled",
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
DATA_DOMAINS = set(get_args(DataDomain))
ParamValueKind = Literal["float", "int", "bool", "enum", "op_ref", "path", "string", "tuple", "pulse"]
ParamCookRisk = Literal["low", "medium", "high", "unknown"]
ProbeCostLevel = Literal["cheap", "moderate", "expensive"]
GeneratedCodeLanguage = Literal["python", "glsl"]


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


class CompiledVisualTaskSpec(BaseModel):
    """Deterministic Phase 1 decomposition of a creative TD prompt."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: str = Field(min_length=1)
    target_root: str = "/project1"
    output_top: str | None = None
    domains: list[DataDomain] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)
    time_behavior: list[str] = Field(default_factory=list)
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list)
    candidate_profiles: list[BrainProfile] = Field(default_factory=list)
    candidate_operator_families: list[DataDomain] = Field(default_factory=list)
    validation_needs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    grounding_evidence: list[str] = Field(default_factory=list)
    blocked_questions: list[str] = Field(default_factory=list)


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
    content: dict[str, Any] | None = None
    generated_code: dict[str, Any] | None = None
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


class CandidateConceptGraph(BaseModel):
    """A ranked graph candidate produced from compiler features and patterns."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    compiled_task_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    profiles: list[BrainProfile] = Field(default_factory=list)
    pattern_ids: list[str] = Field(default_factory=list)
    concepts: list[ConceptNode] = Field(default_factory=list)
    edges: list[ConceptEdge] = Field(default_factory=list)
    required_ops: list[str] = Field(default_factory=list)
    optional_ops: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    validation_needs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    grounding_evidence: list[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""

    @field_validator("required_ops")
    @classmethod
    def _required_ops_are_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("candidate graph requires at least one required op")
        return value

    @model_validator(mode="after")
    def _edges_reference_known_concepts(self) -> CandidateConceptGraph:
        ids = {node.id for node in self.concepts}
        for edge in self.edges:
            if edge.source not in ids:
                raise ValueError(f"edge source references unknown concept id: {edge.source}")
            if edge.target not in ids:
                raise ValueError(f"edge target references unknown concept id: {edge.target}")
        return self


class BrainPattern(BaseModel):
    """Reusable, docs-grounded pattern fragment for compiler candidates."""

    model_config = ConfigDict(extra="forbid")

    pattern_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    intent_tags: list[str] = Field(default_factory=list)
    profiles: list[BrainProfile] = Field(default_factory=list)
    required_ops: list[str] = Field(default_factory=list)
    optional_ops: list[str] = Field(default_factory=list)
    concept_nodes: list[ConceptNode] = Field(default_factory=list)
    concept_edges: list[ConceptEdge] = Field(default_factory=list)
    exposes: list[dict[str, Any]] = Field(default_factory=list)
    consumes: list[dict[str, Any]] = Field(default_factory=list)
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    required_addons: list[str] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=dict)
    debug_outputs: list[dict[str, Any]] = Field(default_factory=list)
    safety: Literal["safe_live", "dry_run_only", "device_dependent"] = "safe_live"
    validation_profile: str = "structural_visual_safe"
    validation_probes: list[str] = Field(default_factory=list)
    rollback_risks: list[str] = Field(default_factory=list)
    official_sources: list[str] = Field(default_factory=list)
    promoted_from_trace: str | None = None

    @field_validator("required_ops")
    @classmethod
    def _pattern_requires_ops(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("pattern requires at least one required op")
        return value

    @field_validator("validation_probes")
    @classmethod
    def _pattern_requires_probes(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("pattern requires at least one validation probe")
        # Phase 1 probe registry. Master plan §4.3 requires the schema to reject
        # unknown probe names so a typo cannot silently produce no validation.
        known = {
            "audio_source_present",
            "analysis_stage",
            "range_mapping",
            "audio_signal_activity",
            "feedback_cycle",
            "decay_control",
            "feedback_output_readback",
            "cheap_visual_metrics",
            "shader_source_present",
            "material_assigned",
            "vertex_position_transform",
            "compile_state",
            "sampler_uniforms",
            "nonblack_output",
            "render_top_output",
            "camera_frustum_coverage",
            "camera_present",
            "geometry_present",
            "material_or_default",
            "pop_source_present",
            "pop_output_attached",
            "finite_pop_bounds",
            "attribute_sample_available",
            "topology_capacity",
            "panel_components_present",
            "panel_state_reader",
            "panel_state_readback",
            "control_output",
            "midi_source_present",
            "serial_source_present",
            "osc_source_present",
            "websocket_source_present",
            "mqtt_source_present",
            "udp_source_present",
            "dat_execute_callback_present",
            "callback_guard_present",
            "protocol_table_output",
            "render_switch_table_present",
            "render_switch_index_binding",
            "render_switch_output_present",
            "ndi_source_present",
            "post_fx_stage",
            "top_output_present",
            "output_node_present",
        }
        unknown = sorted(probe for probe in value if probe not in known)
        if unknown:
            raise ValueError(f"unknown validation probes: {unknown}")
        return value

    @field_validator("official_sources")
    @classmethod
    def _sources_must_be_official_derivative_docs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("pattern requires official Derivative docs sources")
        invalid = [item for item in value if not item.startswith("https://docs.derivative.ca/")]
        if invalid:
            raise ValueError("pattern sources must be official Derivative docs URLs")
        return value

    @field_validator("required_addons")
    @classmethod
    def _required_addons_are_named(cls, value: list[str]) -> list[str]:
        blank = [item for item in value if not str(item).strip()]
        if blank:
            raise ValueError("required_addons entries must be non-empty")
        return value

    @model_validator(mode="after")
    def _edges_reference_known_concepts(self) -> BrainPattern:
        ids = {node.id for node in self.concept_nodes}
        for edge in self.concept_edges:
            if edge.source not in ids:
                raise ValueError(f"edge source references unknown concept id: {edge.source}")
            if edge.target not in ids:
                raise ValueError(f"edge target references unknown concept id: {edge.target}")
        self._validate_pattern_dict_domains()
        self._validate_pattern_dict_node_references(ids)
        return self

    def _validate_pattern_dict_domains(self) -> None:
        for collection_name in ("exposes", "consumes", "debug_outputs"):
            for item in getattr(self, collection_name):
                domain = item.get("domain") if isinstance(item, dict) else None
                if domain is not None and domain not in DATA_DOMAINS:
                    raise ValueError(
                        f"invalid pattern domain {domain!r} in {collection_name}; "
                        f"expected one of {sorted(DATA_DOMAINS)}"
                    )

    def _validate_pattern_dict_node_references(self, ids: set[str]) -> None:
        for item in self.exposes:
            node_id = item.get("node_id") if isinstance(item, dict) else None
            if node_id is not None and node_id not in ids:
                raise ValueError(f"pattern exposes references unknown concept id: {node_id}")
        for item in self.consumes:
            node_id = item.get("target_node_id") if isinstance(item, dict) else None
            if node_id is not None and node_id not in ids:
                raise ValueError(f"pattern consumes references unknown concept id: {node_id}")
        for item in self.debug_outputs:
            node_id = item.get("node") if isinstance(item, dict) else None
            if node_id is not None and node_id not in ids:
                raise ValueError(f"pattern debug_outputs references unknown concept id: {node_id}")


class OperatorAvailabilityMatrix(BaseModel):
    """Build/add-on scoped operator availability evidence for planning."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    td_build: str = "unknown"
    platform: str = "unknown"
    generated_at: str
    installed_addons: list[str] = Field(default_factory=list)
    operators: dict[str, dict[str, Any]] = Field(default_factory=dict)
    family_aliases: dict[str, list[str]] = Field(default_factory=dict)
    unavailable_reasons: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _availability_entries_are_consistent(self) -> OperatorAvailabilityMatrix:
        for op_type, data in self.operators.items():
            family = data.get("family") if isinstance(data, dict) else None
            available = data.get("available") if isinstance(data, dict) else None
            if family not in DATA_DOMAINS:
                raise ValueError(f"invalid operator family for {op_type}: {family!r}")
            if not isinstance(available, bool):
                raise ValueError(f"operator availability must be boolean for {op_type}")
            if available is False and not self.unavailable_reasons.get(op_type):
                raise ValueError(f"unavailable operator requires a reason: {op_type}")

        for op_type, reason in self.unavailable_reasons.items():
            data = self.operators.get(op_type)
            if data is None:
                raise ValueError(f"unavailable reason references unknown operator: {op_type}")
            if data.get("available") is True:
                raise ValueError(f"unavailable reason references available operator: {op_type}")
            if not str(reason).strip():
                raise ValueError(f"unavailable operator requires a reason: {op_type}")

        for family, aliases in self.family_aliases.items():
            if family not in DATA_DOMAINS:
                raise ValueError(f"invalid operator family alias: {family!r}")
            for op_type in aliases:
                data = self.operators.get(op_type)
                if data is None:
                    raise ValueError(f"family alias references unknown operator: {op_type}")
                if data.get("family") != family:
                    raise ValueError(f"family alias {family} references {op_type} from {data.get('family')} family")
        return self


class OperatorSubstitutionRule(BaseModel):
    """Official-docs-backed replacement option for an unavailable operator."""

    model_config = ConfigDict(extra="forbid")

    missing_op: str = Field(min_length=1)
    replacement_ops: list[str] = Field(default_factory=list)
    replacement_pattern: str | None = None
    confidence: Literal["low", "medium", "high"]
    tradeoffs: list[str] = Field(default_factory=list)
    official_sources: list[str] = Field(default_factory=list)
    requires_user_approval: bool = False

    @field_validator("replacement_ops")
    @classmethod
    def _replacement_ops_are_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("substitution rule requires at least one replacement op")
        return value

    @field_validator("official_sources")
    @classmethod
    def _sources_must_be_official_derivative_docs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("substitution rule requires official Derivative docs sources")
        invalid = [item for item in value if not item.startswith("https://docs.derivative.ca/")]
        if invalid:
            raise ValueError("substitution sources must be official Derivative docs URLs")
        return value


class AvailabilitySubstitutionExplanation(BaseModel):
    """User-facing explanation for an availability-driven operator substitution."""

    model_config = ConfigDict(extra="forbid")

    missing_op: str = Field(min_length=1)
    replacement_target: str = Field(min_length=1)
    replacement_ops: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]
    requires_approval: bool = False
    approval_state: Literal["not_required", "approved", "pending"] = "not_required"
    approval_evidence: list[str] = Field(default_factory=list)
    availability_reason: str = ""
    tradeoffs: list[str] = Field(default_factory=list)
    official_sources: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("replacement_ops")
    @classmethod
    def _replacement_ops_are_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("substitution explanation requires at least one replacement op")
        return value

    @field_validator("official_sources")
    @classmethod
    def _sources_must_be_official_derivative_docs(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if not item.startswith("https://docs.derivative.ca/")]
        if invalid:
            raise ValueError("substitution explanation sources must be official Derivative docs URLs")
        return value


class ParamSemantics(BaseModel):
    """Docs-grounded contract for one high-risk or typed operator parameter."""

    model_config = ConfigDict(extra="forbid")

    op_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value_kind: ParamValueKind
    expected_family: DataDomain | None = None
    expected_op_type: str | None = None
    tuple_size: int | None = Field(default=None, ge=1)
    unit: str | None = None
    valid_range: tuple[float, float] | None = None
    enum_values: list[str] = Field(default_factory=list)
    default_strategy: str = Field(min_length=1)
    cook_risk: ParamCookRisk = "unknown"
    validation_rule: str | None = None
    official_source: str

    @field_validator("official_source")
    @classmethod
    def _source_must_be_official_derivative_docs(cls, value: str) -> str:
        if not value.startswith("https://docs.derivative.ca/"):
            raise ValueError("param semantics source must be an official Derivative docs URL")
        return value

    @model_validator(mode="after")
    def _contract_is_internally_consistent(self) -> ParamSemantics:
        if self.valid_range is not None:
            low, high = self.valid_range
            if low > high:
                raise ValueError("valid_range lower bound must be <= upper bound")
        if self.value_kind == "enum" and not self.enum_values:
            raise ValueError("enum param semantics require enum_values")
        if self.value_kind == "op_ref" and not (self.expected_family or self.expected_op_type):
            raise ValueError("op_ref param semantics require expected_family or expected_op_type")
        if self.expected_op_type and self.expected_family:
            suffixes = ("TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT")
            if any(self.expected_op_type.endswith(suffix) for suffix in suffixes):
                expected_suffix = "COMP" if self.expected_family == "COMP" else self.expected_family
                if not self.expected_op_type.endswith(str(expected_suffix)):
                    raise ValueError("expected_op_type must match expected_family")
        return self


class ProfileValidationProbe(BaseModel):
    """Profile-specific validation expectation with cost and readback policy."""

    model_config = ConfigDict(extra="forbid")

    probe_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    required_inputs: list[str] = Field(default_factory=list)
    readback_strategy: str = Field(min_length=1)
    metric_names: list[str] = Field(default_factory=list)
    pass_conditions: list[str] = Field(default_factory=list)
    cost_level: ProbeCostLevel = "cheap"
    failure_message: str = Field(min_length=1)
    official_sources: list[str] = Field(default_factory=list)

    @field_validator("metric_names")
    @classmethod
    def _metrics_are_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("profile validation probe requires at least one metric")
        return value

    @field_validator("pass_conditions")
    @classmethod
    def _pass_conditions_are_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("profile validation probe requires at least one pass condition")
        return value

    @field_validator("official_sources")
    @classmethod
    def _sources_must_be_official_derivative_docs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("profile validation probe requires official Derivative docs sources")
        invalid = [item for item in value if not item.startswith("https://docs.derivative.ca/")]
        if invalid:
            raise ValueError("profile validation probe sources must be official Derivative docs URLs")
        return value


class GeneratedCodeBlock(BaseModel):
    """Generated Python/GLSL payload attached to a planned TD operator."""

    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1)
    language: GeneratedCodeLanguage
    target_op: str = Field(min_length=1)
    target_param: str | None = None
    source_kind: str = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)
    code: str = Field(min_length=1)
    static_checks: list[str] = Field(default_factory=list)
    runtime_checks: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    official_sources: list[str] = Field(default_factory=list)

    @field_validator("source_refs")
    @classmethod
    def _source_refs_are_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("generated code block requires at least one source ref")
        return value

    @field_validator("static_checks")
    @classmethod
    def _static_checks_are_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("generated code block requires at least one static check")
        return value

    @model_validator(mode="after")
    def _runtime_contract_is_explicit(self) -> GeneratedCodeBlock:
        if not self.runtime_checks:
            raise ValueError("generated code block requires at least one runtime check")
        if not self.expected_outputs:
            raise ValueError("generated code block requires at least one expected output")
        return self

    @field_validator("official_sources")
    @classmethod
    def _sources_must_be_official_derivative_docs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("generated code block requires official Derivative docs sources")
        invalid = [item for item in value if not item.startswith("https://docs.derivative.ca/")]
        if invalid:
            raise ValueError("generated code sources must be official Derivative docs URLs")
        return value


class AssemblyMacro(BaseModel):
    """Phase 4 macro contract for readable assembled concept-to-node networks."""

    model_config = ConfigDict(extra="forbid")

    macro_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    applies_to_profiles: list[BrainProfile] = Field(default_factory=list)
    layout_strategy: str = Field(min_length=1)
    created_controls: list[dict[str, Any]] = Field(default_factory=list)
    debug_nodes: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    output_contract: list[str] = Field(default_factory=list)
    validation_addons: list[str] = Field(default_factory=list)
    official_sources: list[str] = Field(default_factory=list)

    @field_validator("applies_to_profiles")
    @classmethod
    def _profiles_are_required(cls, value: list[BrainProfile]) -> list[BrainProfile]:
        if not value:
            raise ValueError("assembly macro requires at least one applicable profile")
        return value

    @field_validator("output_contract")
    @classmethod
    def _output_contract_is_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("assembly macro requires an output contract")
        return value

    @field_validator("validation_addons")
    @classmethod
    def _validation_addons_are_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("assembly macro requires validation addons")
        return value

    @field_validator("official_sources")
    @classmethod
    def _sources_must_be_official_derivative_docs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("assembly macro requires official Derivative docs sources")
        invalid = [item for item in value if not item.startswith("https://docs.derivative.ca/")]
        if invalid:
            raise ValueError("assembly macro sources must be official Derivative docs URLs")
        return value


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
    auto_repair: bool = False
    max_repair_attempts: int = Field(default=0, ge=0, le=3)


CorpusEvidenceSource = Literal["exact_operator", "docs_search"]


class CorpusEvidenceRecord(BaseModel):
    """Cited TD corpus fact used to ground a BrainPlan."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    source: CorpusEvidenceSource
    op_type: str | None = None
    family: DataDomain | None = None
    display_name: str = ""
    docs_url: str = ""
    summary: str = ""
    key_params: list[str] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    query: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class BrainPlan(BaseModel):
    """High-level plan that wraps a typed PatchPlan with grounding metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: Literal["brain"] = "brain"
    task: VisualTaskSpec
    concept_graph: ConceptGraph
    patch_plan: PatchPlan
    compiled_task: CompiledVisualTaskSpec | None = None
    candidate_graphs: list[CandidateConceptGraph] = Field(default_factory=list)
    availability_matrix: OperatorAvailabilityMatrix | None = None
    validation_profile: str = "structural_visual_safe"
    blocked_questions: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    grounding_evidence: list[str] = Field(default_factory=list)
    corpus_evidence: list[CorpusEvidenceRecord] = Field(default_factory=list)
    substitution_explanations: list[AvailabilitySubstitutionExplanation] = Field(default_factory=list)
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
    repair_attempts: list[dict[str, Any]] = Field(default_factory=list)
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
    "AssemblyMacro",
    "AvailabilitySubstitutionExplanation",
    "BrainPlan",
    "BrainProfile",
    "BrainPattern",
    "BrainTrace",
    "CandidateConceptGraph",
    "CompiledVisualTaskSpec",
    "ConceptEdge",
    "ConceptGraph",
    "ConceptNode",
    "CorpusEvidenceRecord",
    "CorpusEvidenceSource",
    "DataDomain",
    "GeneratedCodeBlock",
    "GeneratedCodeLanguage",
    "OperatorAvailabilityMatrix",
    "OperatorSubstitutionRule",
    "ParamCookRisk",
    "ParamSemantics",
    "ParamValueKind",
    "ProbeCostLevel",
    "ProfileValidationProbe",
    "TransactionOptions",
    "TransactionResult",
    "ValidationIssue",
    "ValidationReportV2",
    "VisualTaskSpec",
]
