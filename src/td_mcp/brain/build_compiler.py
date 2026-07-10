"""Deterministic minimal visual build compiler.

The compiler is deliberately host-side and side-effect free: it turns a
validated BuildIntent + ModuleGraph into the existing PatchPlan contract and
compact CompilerArtifacts. It never calls TouchDesigner directly.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from td_mcp.models.brain import BrainPattern
from td_mcp.models.build import (
    BuildBatch,
    BuildIntent,
    BuildProgram,
    BuildProgramDiff,
    CompiledModule,
    CompilerArtifacts,
    ModuleAssertion,
    ModuleEdge,
    ModuleGraph,
    SimplificationReport,
    ValidationAssertion,
    ValidationContract,
    VisualModule,
    budget_for_mode,
)
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan

TECHNIQUE_ROOT = Path(__file__).with_name("techniques")
OPERATOR_CARD_ROOT = Path(__file__).parents[1] / "knowledge" / "cards" / "operators"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PLACEHOLDER_RE = re.compile(r"^\$\{(?P<scope>parameters|path)\.(?P<name>[A-Za-z0-9_.-]+)\}$")
_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_]+")


class BuildCompilerError(Exception):
    """Base class for deterministic build-compiler failures."""


class TechniqueNotFoundError(BuildCompilerError):
    pass


class UnresolvedTemplateValueError(BuildCompilerError):
    pass


class ModulePortMismatchError(BuildCompilerError):
    pass


class BuildBudgetExceededError(BuildCompilerError):
    pass


# Backward import alias. BrainPattern schema v2 is the one canonical
# TechniqueSpec; no parallel technique model is maintained.
TechniqueRecord = BrainPattern


def load_compiled_techniques(root: str | Path | None = None) -> dict[str, TechniqueRecord]:
    """Load packaged BrainPattern-v2 technique records."""
    source = Path(root or TECHNIQUE_ROOT)
    records: dict[str, TechniqueRecord] = {}
    for path in sorted(source.glob("*.v2.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 2:
            raise BuildCompilerError(f"unsupported technique schema in {path.name}")
        pattern_id = str(payload.get("pattern_id") or "")
        if not pattern_id:
            raise BuildCompilerError(f"missing pattern_id in {path.name}")
        if pattern_id in records:
            raise BuildCompilerError(f"duplicate technique id: {pattern_id}")
        _validate_technique_payload(payload, path.name)
        records[pattern_id] = BrainPattern.model_validate(payload).bind_packaged_source(
            path,
            packaged=path.resolve().parent == TECHNIQUE_ROOT.resolve(),
        )
    return records


def select_techniques(
    intent: BuildIntent,
    *,
    family: str | None = None,
    limit: int = 3,
    registry: dict[str, TechniqueRecord] | None = None,
) -> list[tuple[TechniqueRecord, float]]:
    """Rank deterministic candidates with the master-plan weights."""
    records = registry or load_compiled_techniques()
    intent_tokens = set(
        _tokens(" ".join([intent.outcome, *intent.visual_keywords, *intent.behavior_keywords]))
    )
    ranked: list[tuple[TechniqueRecord, float]] = []
    for record in records.values():
        tag_tokens = set(_tokens(" ".join(record.intent_tags)))
        intent_match = len(intent_tokens & tag_tokens) / max(1, min(len(intent_tokens), len(tag_tokens)))
        io_compatibility = 1.0 if not family or family in record.families else 0.0
        validated_bonus = 1.0 if record.payload.get("state") == "validated" else 0.0
        preference_match = 1.0 if intent.preferences.prefer_native_ops else 0.5
        node_cost = min(1.0, float(record.payload.get("estimated_nodes") or 0) / 20.0)
        cost_label = str(record.payload.get("estimated_gpu_cost") or "unknown")
        runtime_cost = {"low": 0.2, "medium": 0.5, "high": 1.0, "unknown": 0.7}.get(cost_label, 0.7)
        conflict = 1.0 if family and family not in record.families else 0.0
        score = (
            4.0 * intent_match
            + 3.0 * io_compatibility
            + 2.0 * validated_bonus
            + 1.5 * preference_match
            - node_cost
            - runtime_cost
            - 3.0 * conflict
        )
        ranked.append((record, round(score, 6)))
    ranked.sort(key=lambda item: (-item[1], item[0].pattern_id))
    return ranked[:limit]


def simplify_module_graph(graph: ModuleGraph) -> tuple[ModuleGraph, SimplificationReport]:
    """Remove dead modules and collapse adjacent duplicate utilities."""
    modules_before = len(graph.modules)
    nodes_before = graph.estimated_node_count or sum(
        _technique_node_count(module.technique_id) for module in graph.modules
    )
    changes: list[str] = []
    modules = {module.id: module for module in graph.modules}
    edges = list(graph.edges)

    reachable = _upstream_module_ids(graph.output_module_id, edges)
    reachable.add(graph.output_module_id)
    removed_dead = sorted(set(modules) - reachable)
    if removed_dead:
        changes.append("removed dead modules: " + ", ".join(removed_dead))
        for module_id in removed_dead:
            modules.pop(module_id, None)
        edges = [edge for edge in edges if edge.source_module in modules and edge.target_module in modules]

    # A repeated resolution normalizer or identical utility module is a
    # common planner artifact. Keep the upstream instance and redirect the
    # downstream module's consumers to it.
    collapsed = True
    output_module_id = graph.output_module_id
    while collapsed:
        collapsed = False
        for edge in list(edges):
            source = modules.get(edge.source_module)
            target = modules.get(edge.target_module)
            if not source or not target:
                continue
            if (
                source.role == "utility"
                and target.role == "utility"
                and source.technique_id == target.technique_id
                and source.parameters == target.parameters
            ):
                replacement_edges: list[ModuleEdge] = []
                for candidate in edges:
                    if candidate.source_module == target.id:
                        replacement_edges.append(candidate.model_copy(update={"source_module": source.id}))
                    elif candidate.target_module != target.id:
                        replacement_edges.append(candidate)
                edges = _dedupe_edges(replacement_edges)
                modules.pop(target.id, None)
                if output_module_id == target.id:
                    output_module_id = source.id
                changes.append(f"collapsed duplicate utility {target.id} into {source.id}")
                collapsed = True
                break

    estimated_nodes = sum(_technique_node_count(module.technique_id) for module in modules.values())
    simplified = graph.model_copy(
        update={
            "modules": [modules[module_id] for module_id in sorted(modules)],
            "edges": edges,
            "output_module_id": output_module_id,
            "estimated_node_count": estimated_nodes,
        }
    )
    report = SimplificationReport(
        modules_before=modules_before,
        modules_after=len(simplified.modules),
        estimated_nodes_before=nodes_before,
        estimated_nodes_after=estimated_nodes,
        changes=changes,
    )
    return simplified, report


def compile_module_graph(
    intent: BuildIntent,
    graph: ModuleGraph,
    *,
    existing_names: Iterable[str] = (),
    registry: dict[str, TechniqueRecord] | None = None,
) -> tuple[PatchPlan, CompilerArtifacts]:
    """Compile a ModuleGraph into the existing PatchPlan contract."""
    techniques = registry or load_compiled_techniques()
    simplified, simplification = simplify_module_graph(graph)
    if len(simplified.modules) > 9:
        raise BuildBudgetExceededError("module graph remains above the 9-module simplification limit")
    ordered_modules = _topological_modules(simplified)
    used_names = set(existing_names)
    module_records: dict[str, TechniqueRecord] = {}
    node_paths: dict[str, dict[str, str]] = {}
    module_parameters: dict[str, dict[str, Any]] = {}
    module_operation_indices: dict[str, list[int]] = {module.id: [] for module in ordered_modules}
    operations: list[PatchOperation] = []
    required_ops: list[str] = []

    for module in ordered_modules:
        record = techniques.get(module.technique_id)
        if record is None:
            raise TechniqueNotFoundError(module.technique_id)
        module_records[module.id] = record
        required_ops.extend(record.required_ops)
        defaults = dict(record.payload.get("parameter_defaults") or {})
        defaults.update(module.parameters)
        module_parameters[module.id] = defaults
        local_paths: dict[str, str] = {}
        for node_index, node in enumerate(record.payload.get("nodes") or []):
            local_id = str(node["id"])
            base_name = _safe_name(f"{module.id}_{node.get('name') or local_id}")
            name = _unique_name(base_name, used_names)
            parent_id = node.get("parent")
            if parent_id is not None and str(parent_id) not in local_paths:
                raise BuildCompilerError(
                    f"technique {record.pattern_id} node {local_id} has unresolved parent {parent_id}"
                )
            parent_path = local_paths[str(parent_id)] if parent_id is not None else simplified.target_root
            local_paths[local_id] = _join_path(parent_path, name)
            op_index = len(operations)
            operations.append(
                PatchOperation(
                    kind="create_node",
                    target=parent_path,
                    args={
                        "op_type": str(node["op_type"]),
                        "name": name,
                        "x": node_index * 220,
                        "y": 0,
                    },
                )
            )
            module_operation_indices[module.id].append(op_index)
        node_paths[module.id] = local_paths

    # Packaged source templates are trusted, size-bounded technique data. They
    # are emitted only for Text DAT nodes and never accepted from host drafts.
    for module in ordered_modules:
        record = module_records[module.id]
        for node in record.payload.get("nodes") or []:
            text_template = node.get("text")
            if text_template is None:
                continue
            if not record.packaged:
                raise BuildCompilerError(
                    f"technique {record.pattern_id} cannot emit content outside the packaged registry"
                )
            op_index = len(operations)
            operations.append(
                PatchOperation(
                    kind="set_dat_content",
                    target=node_paths[module.id][str(node["id"])],
                    args={"text": str(text_template)},
                )
            )
            module_operation_indices[module.id].append(op_index)

    # Parameter pass after every target node exists.
    for module in ordered_modules:
        record = module_records[module.id]
        for node in record.payload.get("nodes") or []:
            raw_params = dict(node.get("params") or {})
            if not raw_params:
                continue
            params = _resolve_template_value(
                raw_params,
                parameters=module_parameters[module.id],
                paths=node_paths[module.id],
            )
            op_index = len(operations)
            operations.append(
                PatchOperation(
                    kind="set_params",
                    target=node_paths[module.id][str(node["id"])],
                    args={"params": params},
                )
            )
            module_operation_indices[module.id].append(op_index)

    # Internal data-flow pass.
    for module in ordered_modules:
        record = module_records[module.id]
        for connection in record.payload.get("connections") or []:
            op_index = len(operations)
            operations.append(
                PatchOperation(
                    kind="connect",
                    target=simplified.target_root,
                    args={
                        "from": node_paths[module.id][str(connection["source"])],
                        "to": node_paths[module.id][str(connection["target"])],
                        "from_output": int(connection.get("source_index") or 0),
                        "to_input": int(connection.get("target_index") or 0),
                    },
                )
            )
            module_operation_indices[module.id].append(op_index)

    # Cross-module connections are explicit module interfaces.
    for module in ordered_modules:
        if not module.source_ref or not module.inputs:
            continue
        record = module_records[module.id]
        first_required_port = next((port for port in module.inputs if not port.optional), module.inputs[0])
        target_specs = (record.payload.get("inputs") or {}).get(first_required_port.name) or []
        if not target_specs:
            raise ModulePortMismatchError(
                f"module {module.id} declares source_ref but technique has no {first_required_port.name} input"
            )
        for target_spec in target_specs:
            op_index = len(operations)
            operations.append(
                PatchOperation(
                    kind="connect",
                    target=simplified.target_root,
                    args={
                        "from": module.source_ref,
                        "to": node_paths[module.id][str(target_spec["node"])],
                        "from_output": 0,
                        "to_input": int(target_spec.get("input") or 0),
                    },
                )
            )
            module_operation_indices[module.id].append(op_index)

    for edge in simplified.edges:
        source_record = module_records[edge.source_module]
        target_record = module_records[edge.target_module]
        source_local = (source_record.payload.get("outputs") or {}).get(edge.source_port)
        target_specs = (target_record.payload.get("inputs") or {}).get(edge.target_port)
        if not source_local or not isinstance(target_specs, list) or not target_specs:
            raise ModulePortMismatchError(
                f"uncompiled module edge {edge.source_module}.{edge.source_port} -> "
                f"{edge.target_module}.{edge.target_port}"
            )
        for target_spec in target_specs:
            op_index = len(operations)
            operations.append(
                PatchOperation(
                    kind="connect",
                    target=simplified.target_root,
                    args={
                        "from": node_paths[edge.source_module][str(source_local)],
                        "to": node_paths[edge.target_module][str(target_spec["node"])],
                        "from_output": 0,
                        "to_input": int(target_spec.get("input") or 0),
                    },
                )
            )
            module_operation_indices[edge.source_module].append(op_index)
            module_operation_indices[edge.target_module].append(op_index)

    # Layout is deliberately late and deterministic.
    for column, module in enumerate(ordered_modules):
        for row, path in enumerate(node_paths[module.id].values()):
            op_index = len(operations)
            operations.append(
                PatchOperation(
                    kind="layout",
                    target=path,
                    args={"x": column * 720 + row * 180, "y": -column * 40},
                )
            )
            module_operation_indices[module.id].append(op_index)

    budget = budget_for_mode(intent.mode)
    if len(operations) > budget.maximum_patch_ops:
        raise BuildBudgetExceededError(
            f"compiled {len(operations)} operations, budget is {budget.maximum_patch_ops}"
        )

    output_module = next(module for module in ordered_modules if module.id == simplified.output_module_id)
    output_record = module_records[output_module.id]
    output_mapping = output_record.payload.get("outputs") or {}
    output_port = "image" if "image" in output_mapping else next(iter(output_mapping), None)
    if output_port is None:
        raise ModulePortMismatchError("output module has no compiled output port")
    output_local_id = str(output_mapping[output_port])
    final_output_path = node_paths[output_module.id][output_local_id]
    output_node = next(
        node for node in output_record.payload.get("nodes") or [] if str(node.get("id")) == output_local_id
    )
    capture_frames = [final_output_path] if str(output_node.get("op_type") or "").endswith("TOP") else []

    plan = PatchPlan(
        intent=intent.outcome,
        target_root=simplified.target_root,
        source="operations",
        operations=operations,
        required_ops=sorted(set(required_ops)),
        risk_flags=[f"build-mode:{intent.mode}", "compiler:minimal-visual-v2"],
        undo_label=f"td build compiler: {intent.outcome[:42]}",
        validation_plan=ValidationPlan(
            target_root=simplified.target_root,
            capture_frames=capture_frames,
        ),
    )

    assertions = _compiled_assertions(
        ordered_modules,
        module_records=module_records,
        node_paths=node_paths,
        parameters=module_parameters,
    )
    validation_contract = _validation_contract(
        target_root=simplified.target_root,
        output_path=final_output_path,
        assertions=assertions,
        repair_budget=budget.maximum_repair_loops,
    )
    compiled_modules = [
        CompiledModule(
            module_id=module.id,
            root_path=simplified.target_root,
            operation_indices=sorted(set(module_operation_indices[module.id])),
            output_paths={
                port: node_paths[module.id][str(local_id)]
                for port, local_id in (module_records[module.id].payload.get("outputs") or {}).items()
            },
            exposed_controls=[
                *_technique_controls(
                    module_records[module.id],
                    parameters=module_parameters[module.id],
                    paths=node_paths[module.id],
                ),
                *(control.model_dump(mode="json") for control in module.controls),
            ],
            assertion_ids=[
                assertion.id for assertion in assertions if assertion.id.startswith(f"{module.id}:")
            ],
            fingerprint=_module_fingerprint(module, module_records[module.id]),
        )
        for module in ordered_modules
    ]
    construct_indices = [index for index, operation in enumerate(operations) if operation.kind != "layout"]
    layout_indices = [index for index, operation in enumerate(operations) if operation.kind == "layout"]
    batches = [
        BuildBatch(
            id="construct",
            phase="construct",
            module_ids=[module.id for module in ordered_modules],
            operation_indices=construct_indices,
        ),
        BuildBatch(
            id="layout",
            phase="layout",
            module_ids=[module.id for module in ordered_modules],
            operation_indices=layout_indices,
        ),
        BuildBatch(
            id="validate",
            phase="validate",
            module_ids=[module.id for module in ordered_modules],
            validate_assertion_ids=[assertion.id for assertion in assertions],
        ),
    ]
    program = BuildProgram(
        target_root=simplified.target_root,
        staging_root=(
            f"{simplified.target_root.rstrip('/')}/tdpilot_stage" if intent.mode == "show_safe" else None
        ),
        patch_plan_id=plan.id,
        modules=compiled_modules,
        batches=batches,
        final_output_path=final_output_path,
        snapshot_required=intent.mode != "fast" or bool(intent.constraints.preserve_paths),
        maximum_repair_loops=budget.maximum_repair_loops,
    )
    artifacts = CompilerArtifacts(
        build_intent=intent,
        module_graph=simplified,
        build_program=program,
        validation_contract=validation_contract,
        simplification_report=simplification,
        execution_budget=budget,
    )
    return plan, artifacts


def diff_patch_plans(
    old: PatchPlan,
    new: PatchPlan,
    *,
    owned_paths: Iterable[str] = (),
) -> BuildProgramDiff:
    """Return a deterministic conservative diff for generated plans."""
    owned = set(owned_paths)
    old_by_key = {_operation_key(operation): operation for operation in old.operations}
    new_by_key = {_operation_key(operation): operation for operation in new.operations}
    create_ops: list[dict[str, Any]] = []
    update_ops: list[dict[str, Any]] = []
    delete_ops: list[dict[str, Any]] = []
    reconnect_ops: list[dict[str, Any]] = []
    for key in sorted(new_by_key.keys() - old_by_key.keys()):
        operation = new_by_key[key]
        bucket = (
            reconnect_ops
            if operation.kind == "connect"
            else create_ops
            if operation.kind == "create_node"
            else update_ops
        )
        bucket.append(operation.model_dump(mode="json"))
    for key in sorted(old_by_key.keys() - new_by_key.keys()):
        operation = old_by_key[key]
        path = _created_path(operation)
        if operation.kind == "create_node" and path and path in owned:
            delete_ops.append({"kind": "delete_node", "target": path, "args": {"owned": True}})
    return BuildProgramDiff(
        create_ops=create_ops,
        update_ops=update_ops,
        delete_ops=delete_ops,
        reconnect_ops=reconnect_ops,
        preserved_paths=sorted(owned - {item.get("target") for item in delete_ops}),
    )


def generated_metadata(artifacts: CompilerArtifacts) -> dict[str, Any]:
    """Compact ownership metadata suitable for external component notes."""
    return {
        "schema": 1,
        "program_id": artifacts.build_program.program_id,
        "technique_ids": [module.technique_id for module in artifacts.module_graph.modules],
        "request_summary": artifacts.build_intent.outcome,
        "output_paths": {"primary": artifacts.build_program.final_output_path},
        "controls": [
            control for module in artifacts.build_program.modules for control in module.exposed_controls
        ],
        "fingerprints": {module.module_id: module.fingerprint for module in artifacts.build_program.modules},
    }


def _validate_technique_payload(payload: dict[str, Any], source: str) -> None:
    required = (
        "pattern_id",
        "state",
        "build_compatibility",
        "compiler",
        "nodes",
        "inputs",
        "outputs",
        "tunables",
        "controls",
        "required_ops",
        "failure_modes",
        "validation_defaults",
        "evidence",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise BuildCompilerError(f"{source} missing fields: {', '.join(missing)}")
    if payload.get("state") != "validated":
        raise BuildCompilerError(f"{source} is not validated")
    compiler = payload.get("compiler")
    if not isinstance(compiler, dict) or compiler.get("type") != "packaged_template":
        raise BuildCompilerError(f"{source} requires a packaged_template compiler")
    compatibility = payload.get("build_compatibility")
    if not isinstance(compatibility, dict) or not compatibility.get("minimum"):
        raise BuildCompilerError(f"{source} requires minimum build compatibility")
    nodes = payload.get("nodes") or []
    node_ids = {str(node.get("id") or "") for node in nodes}
    if "" in node_ids or len(node_ids) != len(payload.get("nodes") or []):
        raise BuildCompilerError(f"{source} has missing or duplicate node ids")
    seen_ids: set[str] = set()
    node_types: set[str] = set()
    for node in nodes:
        node_id = str(node.get("id") or "")
        op_type = str(node.get("op_type") or "")
        if not op_type or not node.get("name"):
            raise BuildCompilerError(f"{source} node {node_id} requires op_type and name")
        parent = node.get("parent")
        if parent is not None:
            parent_id = str(parent)
            if parent_id not in seen_ids:
                raise BuildCompilerError(f"{source} node {node_id} parent must reference an earlier node")
            parent_node = next(item for item in nodes if str(item.get("id")) == parent_id)
            if not str(parent_node.get("op_type") or "").endswith("COMP"):
                raise BuildCompilerError(f"{source} node {node_id} parent is not a COMP")
        supported_params = _operator_param_names(op_type)
        if supported_params is None:
            raise BuildCompilerError(f"{source} node {node_id} has no operator card for {op_type}")
        unknown_params = sorted(set(node.get("params") or {}) - supported_params)
        if unknown_params:
            raise BuildCompilerError(
                f"{source} node {node_id} has atlas-unknown params: {', '.join(unknown_params)}"
            )
        if "text" in node:
            text = node.get("text")
            if op_type != "textDAT" or not isinstance(text, str) or not text.strip():
                raise BuildCompilerError(f"{source} node {node_id} has invalid packaged text")
            if len(text.encode("utf-8")) > 16 * 1024 or "\x00" in text:
                raise BuildCompilerError(f"{source} node {node_id} packaged text is unsafe")
        seen_ids.add(node_id)
        node_types.add(op_type)
    required_ops = {str(item) for item in payload.get("required_ops") or []}
    if not node_types.issubset(required_ops):
        missing_ops = sorted(node_types - required_ops)
        raise BuildCompilerError(f"{source} required_ops omits: {', '.join(missing_ops)}")
    for connection in payload.get("connections") or []:
        if str(connection.get("source")) not in node_ids or str(connection.get("target")) not in node_ids:
            raise BuildCompilerError(f"{source} connection references unknown node")
        for key in ("source_index", "target_index"):
            value = connection.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise BuildCompilerError(f"{source} connection has invalid {key}")
    for port, targets in (payload.get("inputs") or {}).items():
        if not str(port).strip() or not isinstance(targets, list) or not targets:
            raise BuildCompilerError(f"{source} has invalid input port {port!r}")
        for target in targets:
            if str(target.get("node")) not in node_ids:
                raise BuildCompilerError(f"{source} input references unknown node")
            input_index = target.get("input", 0)
            if isinstance(input_index, bool) or not isinstance(input_index, int) or input_index < 0:
                raise BuildCompilerError(f"{source} input has invalid connector index")
    for local_id in (payload.get("outputs") or {}).values():
        if str(local_id) not in node_ids:
            raise BuildCompilerError(f"{source} output references unknown node")
    validations = payload.get("validation_defaults")
    if not isinstance(validations, list) or not validations:
        raise BuildCompilerError(f"{source} requires validation defaults")
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict) or not evidence.get("fixture"):
        raise BuildCompilerError(f"{source} requires fixture evidence")
    evidence_ops = {str(item) for item in evidence.get("operator_cards") or []}
    if not node_types.issubset(evidence_ops):
        raise BuildCompilerError(f"{source} evidence omits operator cards")


@lru_cache(maxsize=256)
def _operator_param_names(op_type: str) -> set[str] | None:
    path = OPERATOR_CARD_ROOT / f"{op_type}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("op_type") != op_type:
        return None
    return {str(item.get("name")) for item in payload.get("key_params") or [] if item.get("name")}


def _technique_controls(
    record: TechniqueRecord,
    *,
    parameters: dict[str, Any],
    paths: dict[str, str],
) -> list[dict[str, Any]]:
    return [
        _resolve_template_value(control, parameters=parameters, paths=paths)
        for control in record.payload.get("controls") or []
    ]


def _compiled_assertions(
    modules: list[VisualModule],
    *,
    module_records: dict[str, TechniqueRecord],
    node_paths: dict[str, dict[str, str]],
    parameters: dict[str, dict[str, Any]],
) -> list[ModuleAssertion]:
    assertions: list[ModuleAssertion] = []
    for module in modules:
        raw_defaults = module_records[module.id].payload.get("validation_defaults") or []
        for raw in raw_defaults:
            target = _resolve_template_value(
                raw.get("target"), parameters=parameters[module.id], paths=node_paths[module.id]
            )
            expected = _resolve_template_value(
                raw.get("expected"), parameters=parameters[module.id], paths=node_paths[module.id]
            )
            assertions.append(
                ModuleAssertion(
                    id=f"{module.id}:{raw['id']}",
                    kind=raw["kind"],
                    target=str(target),
                    expected=expected,
                    required=bool(raw.get("required", True)),
                )
            )
        assertions.extend(
            assertion.model_copy(update={"id": f"{module.id}:{assertion.id}"})
            for assertion in module.assertions
        )
    return assertions


def _validation_contract(
    *,
    target_root: str,
    output_path: str,
    assertions: list[ModuleAssertion],
    repair_budget: int,
) -> ValidationContract:
    buckets: dict[str, list[ValidationAssertion]] = {
        "graph": [],
        "runtime": [],
        "visual": [],
        "performance": [],
        "preservation": [],
    }
    for assertion in assertions:
        category, probe, comparator = _assertion_probe(assertion)
        buckets[category].append(
            ValidationAssertion(
                id=assertion.id,
                kind=assertion.kind,
                target=assertion.target,
                required=assertion.required,
                comparator=comparator,
                expected=assertion.expected,
                probe=probe,
            )
        )
    return ValidationContract(
        target_root=target_root,
        output_path=output_path,
        graph_assertions=buckets["graph"],
        runtime_assertions=buckets["runtime"],
        visual_assertions=buckets["visual"],
        performance_assertions=buckets["performance"],
        preservation_assertions=buckets["preservation"],
        repair_budget=repair_budget,
    )


def _assertion_probe(assertion: ModuleAssertion) -> tuple[str, str, str]:
    if assertion.kind in {"not_black", "nonuniform_image", "changing_signal"}:
        return "visual", "frame_metrics", "eq"
    if assertion.kind in {"nonzero_signal", "binding_readback"}:
        return "runtime", "chop_data" if assertion.kind == "nonzero_signal" else "param_query", "eq"
    if assertion.kind == "no_errors":
        return "runtime", "errors", "eq"
    if assertion.kind == "cook_budget":
        return "performance", "cook_info", "lte"
    if assertion.kind == "preserved":
        return "preservation", "node_query", "eq"
    if assertion.kind == "resolution":
        return "graph", "param_query", "eq"
    return "graph", "node_query", "exists" if assertion.kind == "exists" else "eq"


def _resolve_template_value(value: Any, *, parameters: dict[str, Any], paths: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _resolve_template_value(item, parameters=parameters, paths=paths)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve_template_value(item, parameters=parameters, paths=paths) for item in value]
    if not isinstance(value, str):
        return value
    match = _PLACEHOLDER_RE.fullmatch(value)
    if not match:
        return value
    scope = match.group("scope")
    name = match.group("name")
    source = parameters if scope == "parameters" else paths
    if name not in source:
        raise UnresolvedTemplateValueError(f"unresolved {scope} placeholder: {name}")
    return source[name]


def _topological_modules(graph: ModuleGraph) -> list[VisualModule]:
    by_id = {module.id: module for module in graph.modules}
    incoming = {module_id: 0 for module_id in by_id}
    outgoing: dict[str, list[str]] = {module_id: [] for module_id in by_id}
    for edge in graph.edges:
        incoming[edge.target_module] += 1
        outgoing[edge.source_module].append(edge.target_module)
    ready = sorted(module_id for module_id, count in incoming.items() if count == 0)
    ordered: list[VisualModule] = []
    while ready:
        module_id = ready.pop(0)
        ordered.append(by_id[module_id])
        for target in sorted(outgoing[module_id]):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort()
    if len(ordered) != len(by_id):
        raise BuildCompilerError("module graph contains a cycle; feedback must stay inside a technique")
    return ordered


def _upstream_module_ids(output_module_id: str, edges: list[ModuleEdge]) -> set[str]:
    incoming: dict[str, list[str]] = {}
    for edge in edges:
        incoming.setdefault(edge.target_module, []).append(edge.source_module)
    result: set[str] = set()
    stack = list(incoming.get(output_module_id, []))
    while stack:
        module_id = stack.pop()
        if module_id in result:
            continue
        result.add(module_id)
        stack.extend(incoming.get(module_id, []))
    return result


def _dedupe_edges(edges: list[ModuleEdge]) -> list[ModuleEdge]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[ModuleEdge] = []
    for edge in edges:
        key = (edge.source_module, edge.source_port, edge.target_module, edge.target_port)
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return result


def _module_fingerprint(module: VisualModule, record: TechniqueRecord) -> str:
    payload = {
        "module": module.model_dump(mode="json", exclude={"label"}),
        "technique": record.payload,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _technique_node_count(technique_id: str) -> int:
    record = load_compiled_techniques().get(technique_id)
    return int(record.payload.get("estimated_nodes") or 0) if record else 0


def _operation_key(operation: PatchOperation) -> str:
    return json.dumps(operation.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), default=str)


def _created_path(operation: PatchOperation) -> str | None:
    if operation.kind != "create_node" or not operation.args.get("name"):
        return None
    return _join_path(operation.target or "/", str(operation.args["name"]))


def _safe_name(value: str) -> str:
    cleaned = _SAFE_ID_RE.sub("_", value).strip("_").lower()
    return cleaned[:80] or "tdpilot_node"


def _unique_name(base: str, used: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _join_path(parent: str, name: str) -> str:
    return f"{parent.rstrip('/')}/{name}".replace("//", "/")


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.lower())


__all__ = [
    "BuildBudgetExceededError",
    "BuildCompilerError",
    "ModulePortMismatchError",
    "TechniqueNotFoundError",
    "TechniqueRecord",
    "UnresolvedTemplateValueError",
    "compile_module_graph",
    "diff_patch_plans",
    "generated_metadata",
    "load_compiled_techniques",
    "select_techniques",
    "simplify_module_graph",
]
