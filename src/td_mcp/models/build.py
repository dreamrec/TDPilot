"""Typed contracts for the minimal visual build compiler.

These models are intentionally independent from the public MCP tool models.
They describe the internal intent -> module graph -> build program ->
validation flow while the existing BrainPlan/PatchPlan wire contracts remain
backward compatible.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BuildMode = Literal["fast", "production", "show_safe"]
BuildOperation = Literal["create", "modify", "repair", "refactor", "optimize", "explain"]
ModuleDomain = Literal["TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT", "mixed"]


class IntentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    domain: Literal["TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT", "device", "unknown"]
    path: str | None = None
    required: bool = True


class IntentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    domain: Literal["TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT"]
    target_path: str | None = None


class BuildConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_fps: float | None = Field(default=None, gt=0)
    target_resolution: tuple[int, int] | None = None
    max_nodes: int | None = Field(default=None, ge=1)
    max_gpu_ms: float | None = Field(default=None, gt=0)
    max_cpu_ms: float | None = Field(default=None, gt=0)
    preserve_paths: list[str] = Field(default_factory=list)
    active_output_path: str | None = None
    route_target_path: str | None = None
    route_target_input: int = Field(default=0, ge=0)
    forbidden_op_types: list[str] = Field(default_factory=list)
    required_op_types: list[str] = Field(default_factory=list)
    external_assets_allowed: bool = False
    custom_python_allowed: bool = True
    glsl_allowed: bool = True

    @field_validator("target_resolution")
    @classmethod
    def _positive_resolution(cls, value: tuple[int, int] | None) -> tuple[int, int] | None:
        if value is not None and (value[0] <= 0 or value[1] <= 0):
            raise ValueError("target_resolution dimensions must be positive")
        return value

    @field_validator("active_output_path", "route_target_path")
    @classmethod
    def _absolute_optional_path(cls, value: str | None) -> str | None:
        if value is not None and (not value.startswith("/") or ".." in value.split("/")):
            raise ValueError("route paths must be absolute TouchDesigner paths")
        return value.rstrip("/") if value else value


class BuildPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefer_native_ops: bool = True
    prefer_reusable_components: bool = True
    prefer_compact_graph: bool = True
    naming_style: str | None = None
    layout_style: Literal["compact", "readable", "presentation"] = "readable"


class SuccessCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=320)
    kind: Literal["graph", "runtime", "visual", "signal", "performance", "preservation"]
    required: bool = True
    threshold: float | int | str | None = None


class BuildIntent(BaseModel):
    """Compact actionable intent produced from a VisualTaskSpec.

    ``compiled_task_id`` links this v2 projection back to the existing
    CompiledVisualTaskSpec instead of creating a second unrelated task record.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    compiled_task_id: str | None = None
    mode: BuildMode = "production"
    target_path: str = "/project1"
    operation: BuildOperation = "create"
    outcome: str = Field(min_length=1, max_length=240)
    visual_keywords: list[str] = Field(default_factory=list, max_length=8)
    behavior_keywords: list[str] = Field(default_factory=list, max_length=8)
    inputs: list[IntentInput] = Field(default_factory=list)
    outputs: list[IntentOutput] = Field(default_factory=list)
    constraints: BuildConstraints = Field(default_factory=BuildConstraints)
    preferences: BuildPreferences = Field(default_factory=BuildPreferences)
    unknowns: list[str] = Field(default_factory=list, max_length=5)
    assumptions: list[str] = Field(default_factory=list, max_length=5)
    success_criteria: list[SuccessCriterion] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class ModulePort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    data_type: str | None = None
    rate: str | None = None
    resolution: tuple[int, int] | None = None
    optional: bool = False


class ExposedControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    type: Literal["float", "int", "toggle", "menu", "pulse", "color", "xy", "string"]
    default: Any
    minimum: float | int | None = None
    maximum: float | int | None = None
    mapping_target: str = Field(min_length=1)


class ModuleAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: Literal[
        "exists",
        "connected",
        "no_errors",
        "nonzero_signal",
        "changing_signal",
        "nonuniform_image",
        "not_black",
        "cook_budget",
        "resolution",
        "operator_count",
        "binding_readback",
        "preserved",
    ]
    target: str = Field(min_length=1)
    expected: Any = None
    required: bool = True


class VisualModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    role: Literal[
        "source",
        "analysis",
        "conditioning",
        "generator",
        "simulation",
        "transform",
        "modulation",
        "render",
        "composite",
        "grade",
        "output",
        "control",
        "utility",
    ]
    technique_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    td_family: ModuleDomain
    inputs: list[ModulePort] = Field(default_factory=list)
    outputs: list[ModulePort] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    controls: list[ExposedControl] = Field(default_factory=list)
    assertions: list[ModuleAssertion] = Field(default_factory=list)
    implementation: Literal["template", "memory", "synthesized"] = "template"
    source_ref: str | None = None


class ModuleEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_module: str
    source_port: str
    target_module: str
    target_port: str


class ModuleGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    graph_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_root: str
    modules: list[VisualModule]
    edges: list[ModuleEdge] = Field(default_factory=list)
    output_module_id: str
    estimated_node_count: int = Field(default=0, ge=0)
    estimated_patch_ops: int = Field(default=0, ge=0)
    risk_level: Literal["low", "medium", "high"] = "low"

    @model_validator(mode="after")
    def _references_known_modules_and_ports(self) -> ModuleGraph:
        by_id = {module.id: module for module in self.modules}
        if len(by_id) != len(self.modules):
            raise ValueError("module ids must be unique")
        if self.output_module_id not in by_id:
            raise ValueError("output_module_id references an unknown module")
        for edge in self.edges:
            if edge.source_module not in by_id or edge.target_module not in by_id:
                raise ValueError("module edge references an unknown module")
            source_ports = {port.name for port in by_id[edge.source_module].outputs}
            target_ports = {port.name for port in by_id[edge.target_module].inputs}
            if edge.source_port not in source_ports:
                raise ValueError(f"unknown source port: {edge.source_module}.{edge.source_port}")
            if edge.target_port not in target_ports:
                raise ValueError(f"unknown target port: {edge.target_module}.{edge.target_port}")
        connected_inputs = {(edge.target_module, edge.target_port) for edge in self.edges}
        for module in self.modules:
            if module.role == "source":
                continue
            for port in module.inputs:
                if (
                    not port.optional
                    and (module.id, port.name) not in connected_inputs
                    and not module.source_ref
                ):
                    raise ValueError(f"required module input is unconnected: {module.id}.{port.name}")
        return self


class CompiledModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str
    root_path: str
    operation_indices: list[int] = Field(default_factory=list)
    output_paths: dict[str, str] = Field(default_factory=dict)
    exposed_controls: list[dict[str, Any]] = Field(default_factory=list)
    assertion_ids: list[str] = Field(default_factory=list)
    fingerprint: str = Field(min_length=1)


class BuildBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    phase: Literal["prepare", "construct", "bind", "layout", "validate", "commit", "cleanup"]
    module_ids: list[str] = Field(default_factory=list)
    operation_indices: list[int] = Field(default_factory=list)
    validate_assertion_ids: list[str] = Field(default_factory=list)


class BuildProgram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    program_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_root: str
    staging_root: str | None = None
    patch_plan_id: str
    modules: list[CompiledModule] = Field(default_factory=list)
    batches: list[BuildBatch] = Field(default_factory=list)
    final_output_path: str
    snapshot_required: bool = True
    rollback_on_failure: bool = True
    maximum_repair_loops: int = Field(default=2, ge=0, le=3)


class ValidationAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    target: str = Field(min_length=1)
    required: bool = True
    comparator: Literal["eq", "ne", "lt", "lte", "gt", "gte", "between", "contains", "exists"]
    expected: Any
    probe: Literal[
        "node_query",
        "param_query",
        "errors",
        "cook_info",
        "chop_data",
        "geometry_data",
        "pop_inspect",
        "frame_metrics",
        "screenshot_critic",
    ]


class ValidationContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    contract_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_root: str
    output_path: str
    graph_assertions: list[ValidationAssertion] = Field(default_factory=list)
    runtime_assertions: list[ValidationAssertion] = Field(default_factory=list)
    visual_assertions: list[ValidationAssertion] = Field(default_factory=list)
    performance_assertions: list[ValidationAssertion] = Field(default_factory=list)
    preservation_assertions: list[ValidationAssertion] = Field(default_factory=list)
    repair_budget: int = Field(default=2, ge=0, le=3)
    pass_policy: Literal["all_required", "weighted"] = "all_required"


class SimplificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modules_before: int = Field(ge=0)
    modules_after: int = Field(ge=0)
    estimated_nodes_before: int = Field(ge=0)
    estimated_nodes_after: int = Field(ge=0)
    changes: list[str] = Field(default_factory=list)


class ExecutionBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maximum_round_trips: int = Field(ge=1)
    maximum_patch_ops: int = Field(ge=1)
    maximum_repair_loops: int = Field(ge=0)
    maximum_screenshots: int = Field(ge=0)
    maximum_doc_queries: int = Field(ge=0)


class BuildProgramDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    create_ops: list[dict[str, Any]] = Field(default_factory=list)
    update_ops: list[dict[str, Any]] = Field(default_factory=list)
    delete_ops: list[dict[str, Any]] = Field(default_factory=list)
    reconnect_ops: list[dict[str, Any]] = Field(default_factory=list)
    preserved_paths: list[str] = Field(default_factory=list)


class CompilerArtifacts(BaseModel):
    """Compact v2 artifacts carried by a BrainPlan.

    Patch operations stay in PatchPlan. BuildProgram refers to those operations
    by index, avoiding a second copy in normal tool responses.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    build_intent: BuildIntent
    module_graph: ModuleGraph
    build_program: BuildProgram
    validation_contract: ValidationContract
    simplification_report: SimplificationReport
    execution_budget: ExecutionBudget


def budget_for_mode(mode: BuildMode) -> ExecutionBudget:
    if mode == "fast":
        return ExecutionBudget(
            maximum_round_trips=12,
            maximum_patch_ops=100,
            maximum_repair_loops=1,
            maximum_screenshots=1,
            maximum_doc_queries=1,
        )
    if mode == "show_safe":
        return ExecutionBudget(
            maximum_round_trips=26,
            maximum_patch_ops=200,
            maximum_repair_loops=2,
            maximum_screenshots=2,
            maximum_doc_queries=2,
        )
    return ExecutionBudget(
        maximum_round_trips=20,
        maximum_patch_ops=200,
        maximum_repair_loops=2,
        maximum_screenshots=2,
        maximum_doc_queries=2,
    )


__all__ = [
    "BuildBatch",
    "BuildConstraints",
    "BuildIntent",
    "BuildMode",
    "BuildOperation",
    "BuildPreferences",
    "BuildProgram",
    "BuildProgramDiff",
    "CompiledModule",
    "CompilerArtifacts",
    "ExecutionBudget",
    "ExposedControl",
    "IntentInput",
    "IntentOutput",
    "ModuleAssertion",
    "ModuleDomain",
    "ModuleEdge",
    "ModuleGraph",
    "ModulePort",
    "SimplificationReport",
    "SuccessCriterion",
    "ValidationAssertion",
    "ValidationContract",
    "VisualModule",
    "budget_for_mode",
]
