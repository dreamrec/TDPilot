"""Two-phase show-safe staging and generated-system ownership contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from td_mcp.models.build import CompilerArtifacts, ValidationAssertion, ValidationContract
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan


class ShowSafeProgram(BaseModel):
    """A stage/validate/commit program; the route swap is never in stage_plan."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    program_id: str
    target_root: str
    staging_root: str
    stage_plan: PatchPlan
    commit_plan: PatchPlan
    validation_contract_id: str
    active_output_path: str
    staged_output_path: str
    route_target_path: str
    route_target_input: int = Field(default=0, ge=0)
    retains_old_path: bool = True


class GeneratedSystemMetadata(BaseModel):
    """Compact external-note payload for generated ownership and partial rebuild."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    owner: Literal["tdpilot"] = "tdpilot"
    program_id: str = Field(min_length=1)
    target_root: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    technique_ids: list[str] = Field(default_factory=list)
    controls: list[dict[str, Any]] = Field(default_factory=list)
    module_fingerprints: dict[str, str] = Field(default_factory=dict)
    owned_paths: list[str] = Field(default_factory=list)
    request_summary: str = Field(default="", max_length=240)

    @field_validator("owned_paths")
    @classmethod
    def _owned_paths_stay_inside_root(cls, value: list[str], info) -> list[str]:
        root = str(info.data.get("target_root") or "").rstrip("/")
        if not root:
            return value
        invalid = [path for path in value if path != root and not path.startswith(root + "/")]
        if invalid:
            raise ValueError(f"owned paths escape target_root: {invalid}")
        return sorted(set(value))

    def to_external_note(self) -> str:
        return "TDPILOT_GENERATED_V1:" + self.model_dump_json(exclude_none=True)


class PartialRebuildDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    affected_module_ids: list[str] = Field(default_factory=list)
    preserve_paths: list[str] = Field(default_factory=list)


def build_show_safe_program(
    plan: PatchPlan,
    artifacts: CompilerArtifacts,
    *,
    active_output_path: str,
    route_target_path: str,
    route_target_input: int = 0,
) -> ShowSafeProgram:
    """Rewrite a compiler plan into isolated staging plus a guarded commit."""
    if artifacts.build_intent.mode != "show_safe":
        raise ValueError("show-safe staging requires BuildIntent.mode='show_safe'")
    root = _normalized_root(plan.target_root)
    for label, path in {
        "active_output_path": active_output_path,
        "route_target_path": route_target_path,
    }.items():
        _require_descendant(path, root=root, label=label)

    seed = hashlib.sha256(
        json.dumps(
            {
                "program": artifacts.build_program.program_id,
                "root": root,
                "route": route_target_path,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:10]
    stage_name = f"tdpilot_stage_{seed}"
    staging_root = f"{root}/{stage_name}"
    staged_output = _rewrite_path(
        artifacts.build_program.final_output_path,
        old_root=root,
        new_root=staging_root,
    )
    stage_ops = [
        PatchOperation(
            kind="create_node",
            target=root,
            args={"op_type": "baseCOMP", "name": stage_name},
        ),
        *[
            _rewrite_operation(operation, old_root=root, new_root=staging_root)
            for operation in plan.operations
        ],
    ]
    if any(operation.kind == "route_swap" for operation in stage_ops):
        raise ValueError("stage plan may not contain a route swap")
    stage_plan = plan.model_copy(
        update={
            "id": f"{plan.id}:stage",
            "target_root": root,
            "operations": stage_ops,
            "required_ops": sorted(set([*plan.required_ops, "baseCOMP"])),
            "risk_flags": [*plan.risk_flags, "show-safe:staging"],
            "undo_label": f"{plan.undo_label} [stage]",
            "validation_plan": ValidationPlan(
                target_root=staging_root,
                capture_frames=[staged_output],
            ),
        }
    )
    commit_plan = PatchPlan(
        id=f"{plan.id}:commit",
        intent=f"Commit validated staged route for {plan.intent or 'generated system'}",
        target_root=root,
        source="operations",
        operations=[
            PatchOperation(
                kind="route_swap",
                target=route_target_path,
                args={
                    "from": staged_output,
                    "to": route_target_path,
                    "old_from": active_output_path,
                    "from_output": 0,
                    "old_from_output": 0,
                    "to_input": route_target_input,
                },
            )
        ],
        required_ops=[],
        risk_flags=["show-safe:guarded-route-swap", "show-safe:retain-old-path"],
        undo_label=f"{plan.undo_label} [commit route]",
        validation_plan=ValidationPlan(
            target_root=root,
            capture_frames=[route_target_path],
        ),
    )
    return ShowSafeProgram(
        program_id=artifacts.build_program.program_id,
        target_root=root,
        staging_root=staging_root,
        stage_plan=stage_plan,
        commit_plan=commit_plan,
        validation_contract_id=artifacts.validation_contract.contract_id,
        active_output_path=active_output_path,
        staged_output_path=staged_output,
        route_target_path=route_target_path,
        route_target_input=route_target_input,
    )


def metadata_from_artifacts(
    artifacts: CompilerArtifacts,
    *,
    owned_paths: Iterable[str],
) -> GeneratedSystemMetadata:
    return GeneratedSystemMetadata(
        program_id=artifacts.build_program.program_id,
        target_root=artifacts.build_program.target_root,
        output_path=artifacts.build_program.final_output_path,
        technique_ids=[module.technique_id for module in artifacts.module_graph.modules],
        controls=[
            control.model_dump(mode="json")
            for module in artifacts.module_graph.modules
            for control in module.controls
        ],
        module_fingerprints={
            module.module_id: module.fingerprint for module in artifacts.build_program.modules
        },
        owned_paths=list(owned_paths),
        request_summary=artifacts.build_intent.outcome,
    )


def staging_validation_contract(
    contract: ValidationContract,
    *,
    target_root: str,
    staging_root: str,
    staged_output_path: str,
) -> ValidationContract:
    """Rebase every compiler assertion to the isolated staging COMP."""

    def rewrite(assertion: ValidationAssertion) -> ValidationAssertion:
        return assertion.model_copy(
            update={
                "target": _rewrite_path(
                    assertion.target,
                    old_root=target_root,
                    new_root=staging_root,
                ),
                "expected": _rewrite_value(
                    assertion.expected,
                    old_root=target_root,
                    new_root=staging_root,
                ),
            }
        )

    return contract.model_copy(
        update={
            "target_root": staging_root,
            "output_path": staged_output_path,
            "graph_assertions": [rewrite(item) for item in contract.graph_assertions],
            "runtime_assertions": [rewrite(item) for item in contract.runtime_assertions],
            "visual_assertions": [rewrite(item) for item in contract.visual_assertions],
            "performance_assertions": [rewrite(item) for item in contract.performance_assertions],
            "preservation_assertions": [rewrite(item) for item in contract.preservation_assertions],
        }
    )


def route_commit_validation_contract(program: ShowSafeProgram) -> ValidationContract:
    """Prove the active target reads from staging and the old path remains."""
    return ValidationContract(
        target_root=program.target_root,
        output_path=program.route_target_path,
        graph_assertions=[
            ValidationAssertion(
                id="show_safe:route_committed",
                kind="connected",
                target=program.route_target_path,
                comparator="eq",
                expected={"path": program.staged_output_path},
                probe="node_query",
            )
        ],
        preservation_assertions=[
            ValidationAssertion(
                id="show_safe:old_path_retained",
                kind="preserved",
                target=program.active_output_path,
                comparator="exists",
                expected=True,
                probe="node_query",
            )
        ],
        repair_budget=0,
    )


def parse_generated_note(value: str) -> GeneratedSystemMetadata | None:
    marker = "TDPILOT_GENERATED_V1:"
    if not value.startswith(marker):
        return None
    try:
        return GeneratedSystemMetadata.model_validate_json(value[len(marker) :])
    except Exception:  # noqa: BLE001 - malformed external notes are untrusted
        return None


def authorize_partial_rebuild(
    metadata: GeneratedSystemMetadata | None,
    artifacts: CompilerArtifacts,
    *,
    live_owned_paths: Iterable[str],
    live_module_fingerprints: Mapping[str, str],
    requested_module_ids: Iterable[str],
    required_preserve_paths: Iterable[str] = (),
) -> PartialRebuildDecision:
    """Refuse partial rebuild unless ownership and preservation are provable."""
    reasons: list[str] = []
    requested = sorted(set(requested_module_ids))
    available_modules = {module.module_id for module in artifacts.build_program.modules}
    unknown_modules = sorted(set(requested) - available_modules)
    if metadata is None:
        reasons.append("missing_or_malformed_generated_metadata")
        return PartialRebuildDecision(allowed=False, reasons=reasons)
    if metadata.target_root != artifacts.build_program.target_root:
        reasons.append("target_root_mismatch")
    if unknown_modules:
        reasons.append("unknown_requested_modules:" + ",".join(unknown_modules))
    live_paths = set(live_owned_paths)
    missing_owned = sorted(set(metadata.owned_paths) - live_paths)
    if missing_owned:
        reasons.append("owned_paths_missing:" + ",".join(missing_owned))
    for module_id in requested:
        expected = metadata.module_fingerprints.get(module_id)
        actual = live_module_fingerprints.get(module_id)
        if not expected or not actual or expected != actual:
            reasons.append(f"fingerprint_unproven:{module_id}")
    preserve = sorted(set(required_preserve_paths) | {metadata.output_path})
    unproven_preserve = [path for path in preserve if path not in live_paths]
    if unproven_preserve:
        reasons.append("preservation_unproven:" + ",".join(unproven_preserve))
    return PartialRebuildDecision(
        allowed=not reasons,
        reasons=reasons,
        affected_module_ids=requested if not reasons else [],
        preserve_paths=preserve,
    )


def _rewrite_operation(operation: PatchOperation, *, old_root: str, new_root: str) -> PatchOperation:
    target = (
        _rewrite_path(operation.target, old_root=old_root, new_root=new_root)
        if operation.target
        else operation.target
    )
    args = _rewrite_value(operation.args, old_root=old_root, new_root=new_root)
    return operation.model_copy(update={"target": target, "args": args})


def _rewrite_value(value: Any, *, old_root: str, new_root: str) -> Any:
    if isinstance(value, dict):
        return {
            key: _rewrite_value(item, old_root=old_root, new_root=new_root) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rewrite_value(item, old_root=old_root, new_root=new_root) for item in value]
    if isinstance(value, str) and (value == old_root or value.startswith(old_root + "/")):
        return _rewrite_path(value, old_root=old_root, new_root=new_root)
    return value


def _rewrite_path(path: str, *, old_root: str, new_root: str) -> str:
    _require_descendant(path, root=old_root, label="compiled path")
    return new_root + path[len(old_root) :]


def _normalized_root(value: str) -> str:
    if not value.startswith("/") or value == "/" or "//" in value or "/../" in f"{value}/":
        raise ValueError("show-safe target_root must be a scoped absolute path")
    return value.rstrip("/")


def _require_descendant(path: str, *, root: str, label: str) -> None:
    if path != root and not path.startswith(root + "/"):
        raise ValueError(f"{label} {path!r} is outside target_root {root!r}")


__all__ = [
    "GeneratedSystemMetadata",
    "PartialRebuildDecision",
    "ShowSafeProgram",
    "authorize_partial_rebuild",
    "build_show_safe_program",
    "metadata_from_artifacts",
    "parse_generated_note",
    "route_commit_validation_contract",
    "staging_validation_contract",
]
