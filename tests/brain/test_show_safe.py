from __future__ import annotations

import pytest

import td_mcp.server as server  # noqa: F401 - initialize registry before importing tool modules
from td_mcp.brain.build_compiler import compile_module_graph
from td_mcp.brain.show_safe import (
    authorize_partial_rebuild,
    build_show_safe_program,
    metadata_from_artifacts,
    parse_generated_note,
    route_commit_validation_contract,
    staging_validation_contract,
)
from td_mcp.models.brain import BrainPlan, ConceptGraph, TransactionOptions, TransactionResult, VisualTaskSpec
from td_mcp.models.build import BuildIntent, ModuleGraph, ModulePort, VisualModule
from td_mcp.registry import tools_brain


def _compiled_show_safe():
    intent = BuildIntent(outcome="Build a stable staged output", mode="show_safe")
    graph = ModuleGraph(
        target_root="/project1/generated",
        modules=[
            VisualModule(
                id="output",
                role="output",
                technique_id="stable_output_null",
                label="output",
                td_family="TOP",
                inputs=[ModulePort(name="image", domain="TOP")],
                outputs=[ModulePort(name="image", domain="TOP")],
                source_ref="/project1/generated/source",
            )
        ],
        output_module_id="output",
    )
    return compile_module_graph(intent, graph)


def test_show_safe_build_is_two_phase_and_retains_old_route() -> None:
    plan, artifacts = _compiled_show_safe()
    show_safe = build_show_safe_program(
        plan,
        artifacts,
        active_output_path="/project1/generated/old_output",
        route_target_path="/project1/generated/active_route",
    )

    assert show_safe.staging_root.startswith("/project1/generated/tdpilot_stage_")
    assert all(operation.kind != "route_swap" for operation in show_safe.stage_plan.operations)
    assert show_safe.stage_plan.operations[0].args["op_type"] == "baseCOMP"
    assert show_safe.stage_plan.validation_plan.target_root == show_safe.staging_root
    assert len(show_safe.commit_plan.operations) == 1
    swap = show_safe.commit_plan.operations[0]
    assert swap.kind == "route_swap"
    assert swap.args["old_from"] == "/project1/generated/old_output"
    assert swap.args["from"] == show_safe.staged_output_path
    assert show_safe.retains_old_path is True

    staged_contract = staging_validation_contract(
        artifacts.validation_contract,
        target_root=show_safe.target_root,
        staging_root=show_safe.staging_root,
        staged_output_path=show_safe.staged_output_path,
    )
    assert staged_contract.target_root == show_safe.staging_root
    assert all(
        assertion.target.startswith(show_safe.staging_root)
        for assertion in [
            *staged_contract.graph_assertions,
            *staged_contract.runtime_assertions,
            *staged_contract.visual_assertions,
        ]
    )
    commit_contract = route_commit_validation_contract(show_safe)
    assert commit_contract.graph_assertions[0].expected == {"path": show_safe.staged_output_path}
    assert commit_contract.preservation_assertions[0].target == show_safe.active_output_path


def test_show_safe_rejects_route_outside_owned_root() -> None:
    plan, artifacts = _compiled_show_safe()

    try:
        build_show_safe_program(
            plan,
            artifacts,
            active_output_path="/project1/generated/old_output",
            route_target_path="/project1/foreign/active_route",
        )
    except ValueError as exc:
        assert "outside target_root" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unsafe route was accepted")


def test_generated_notes_are_compact_and_gate_partial_rebuild() -> None:
    plan, artifacts = _compiled_show_safe()
    created_paths = [
        f"{operation.target.rstrip('/')}/{operation.args['name']}"
        for operation in plan.operations
        if operation.kind == "create_node"
    ]
    metadata = metadata_from_artifacts(
        artifacts,
        owned_paths=[*created_paths, artifacts.build_program.final_output_path],
    )
    note = metadata.to_external_note()
    parsed = parse_generated_note(note)

    assert len(note.encode("utf-8")) < 4096
    assert parsed == metadata
    assert "prompt" not in note.lower()
    decision = authorize_partial_rebuild(
        parsed,
        artifacts,
        live_owned_paths=metadata.owned_paths,
        live_module_fingerprints=metadata.module_fingerprints,
        requested_module_ids=["output"],
    )
    assert decision.allowed is True
    assert decision.preserve_paths == [metadata.output_path]


def test_partial_rebuild_refuses_missing_ownership_or_fingerprint() -> None:
    _plan, artifacts = _compiled_show_safe()

    missing = authorize_partial_rebuild(
        None,
        artifacts,
        live_owned_paths=[],
        live_module_fingerprints={},
        requested_module_ids=["output"],
    )

    assert missing.allowed is False
    assert missing.reasons == ["missing_or_malformed_generated_metadata"]


@pytest.mark.asyncio
async def test_brain_executor_runs_show_safe_stage_then_guarded_commit(monkeypatch) -> None:
    plan, artifacts = _compiled_show_safe()
    artifacts.build_intent.constraints.active_output_path = "/project1/generated/old_output"
    artifacts.build_intent.constraints.route_target_path = "/project1/generated/active_route"
    task = VisualTaskSpec(intent="Build a stable staged output", target_root="/project1/generated")
    brain_plan = BrainPlan(
        task=task,
        concept_graph=ConceptGraph(task=task),
        patch_plan=plan,
        compiler_artifacts=artifacts,
    )
    calls = []

    async def fake_run(_ctx, patch_plan, options, **kwargs):
        calls.append((patch_plan, options, kwargs))
        return TransactionResult(
            plan_id=patch_plan.id,
            status="clean",
            validation_failed=False,
            undo_blocks_opened=1,
        )

    monkeypatch.setattr(tools_brain, "_run_transaction", fake_run)

    result = await tools_brain._run_brain_plan_transaction(
        None,
        brain_plan,
        TransactionOptions(max_ops=200, auto_repair=True, max_repair_attempts=2),
    )

    assert len(calls) == 2
    stage_plan, _stage_options, stage_kwargs = calls[0]
    commit_plan, commit_options, commit_kwargs = calls[1]
    assert stage_plan.operations[0].args["op_type"] == "baseCOMP"
    assert all(operation.kind != "route_swap" for operation in stage_plan.operations)
    assert stage_kwargs["validation_contract"].target_root.startswith("/project1/generated/tdpilot_stage_")
    assert [operation.kind for operation in commit_plan.operations] == ["route_swap"]
    assert commit_options.auto_repair is False
    assert commit_kwargs["validation_contract"].preservation_assertions
    assert result.status == "clean"
    assert [item["phase"] for item in result.phase_results] == ["stage", "commit"]
