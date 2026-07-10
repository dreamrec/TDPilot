from __future__ import annotations

import pytest

from td_mcp.brain.build_compiler import (
    BuildCompilerError,
    compile_module_graph,
    diff_patch_plans,
    generated_metadata,
    load_compiled_techniques,
    select_techniques,
    simplify_module_graph,
)
from td_mcp.models.brain import BrainPattern
from td_mcp.models.build import (
    BuildIntent,
    ModuleEdge,
    ModuleGraph,
    ModulePort,
    VisualModule,
)


def _module(
    module_id: str,
    role: str,
    technique_id: str,
    *,
    source_ref: str | None = None,
    parameters: dict | None = None,
) -> VisualModule:
    inputs = [] if role == "source" else [ModulePort(name="image", domain="TOP")]
    return VisualModule(
        id=module_id,
        role=role,
        technique_id=technique_id,
        label=module_id,
        td_family="TOP",
        inputs=inputs,
        outputs=[ModulePort(name="image", domain="TOP")],
        source_ref=source_ref,
        parameters=parameters or {},
    )


def _feedback_graph() -> ModuleGraph:
    feedback = _module(
        "feedback",
        "simulation",
        "top_feedback_transform",
        source_ref="/project1/input_image",
    )
    grade = _module("grade", "grade", "top_multistage_grade")
    output = _module("output", "output", "stable_output_null")
    return ModuleGraph(
        target_root="/project1/compiled",
        modules=[feedback, grade, output],
        edges=[
            ModuleEdge(
                source_module="feedback",
                source_port="image",
                target_module="grade",
                target_port="image",
            ),
            ModuleEdge(
                source_module="grade",
                source_port="image",
                target_module="output",
                target_port="image",
            ),
        ],
        output_module_id="output",
    )


def test_packaged_phase_one_techniques_load_and_are_ranked():
    registry = load_compiled_techniques()
    assert all(
        isinstance(record, BrainPattern) and record.schema_version == 2 for record in registry.values()
    )
    assert set(registry) == {
        "audio_bands",
        "basic_3d_render",
        "basic_gpu_pop_particles",
        "exposed_control_comp",
        "glsl_top_template",
        "normalized_modulator",
        "render_post_chain",
        "stable_output_null",
        "resolution_normalizer",
        "sop_instancing",
        "top_edge_glow",
        "top_feedback_displacement",
        "top_feedback_transform",
        "top_multistage_grade",
        "transient_envelope",
    }
    ranked = select_techniques(
        BuildIntent(outcome="Build organic animated feedback trails"),
        family="TOP",
        registry=registry,
    )
    assert ranked[0][0].pattern_id == "top_feedback_displacement"


def _single_technique_graph(pattern_id: str) -> ModuleGraph:
    record = load_compiled_techniques()[pattern_id]
    raw_inputs = record.payload["inputs"]
    raw_outputs = record.payload["outputs"]
    family = record.payload["families"][0] if len(record.payload["families"]) == 1 else "mixed"
    module = VisualModule(
        id="subject",
        role=record.payload["role"],
        technique_id=pattern_id,
        label=record.payload["title"],
        td_family=family,
        inputs=[ModulePort(name=name, domain=family) for name in raw_inputs],
        outputs=[ModulePort(name=name, domain=family) for name in raw_outputs],
        source_ref=(f"/project1/fixture_{pattern_id}" if raw_inputs else None),
    )
    return ModuleGraph(
        target_root="/project1/compiled",
        modules=[module],
        output_module_id="subject",
    )


def test_all_packaged_v2_techniques_compile_deterministically():
    registry = load_compiled_techniques()
    assert len(registry) == 15

    for pattern_id, record in registry.items():
        intent = BuildIntent(outcome=f"Fixture compile {pattern_id}", mode="production")
        graph = _single_technique_graph(pattern_id)

        first_plan, first_artifacts = compile_module_graph(intent, graph, registry=registry)
        second_plan, second_artifacts = compile_module_graph(intent, graph, registry=registry)

        assert [operation.model_dump(mode="json") for operation in first_plan.operations] == [
            operation.model_dump(mode="json") for operation in second_plan.operations
        ]
        assert [module.fingerprint for module in first_artifacts.build_program.modules] == [
            module.fingerprint for module in second_artifacts.build_program.modules
        ]
        assert first_plan.required_ops == sorted(set(record.required_ops))
        contract = first_artifacts.validation_contract
        assert any(
            assertion.required
            for assertion in (
                contract.graph_assertions
                + contract.runtime_assertions
                + contract.visual_assertions
                + contract.performance_assertions
                + contract.preservation_assertions
            )
        )
        assert first_artifacts.build_program.final_output_path.startswith("/project1/compiled/")
        assert all("${path:" not in str(operation.args) for operation in first_plan.operations)
        output_port = (
            "image" if "image" in record.payload["outputs"] else next(iter(record.payload["outputs"]))
        )
        output_node_id = record.payload["outputs"][output_port]
        output_node = next(node for node in record.payload["nodes"] if node["id"] == output_node_id)
        if output_node["op_type"].endswith("TOP"):
            assert first_plan.validation_plan.capture_frames == [
                first_artifacts.build_program.final_output_path
            ]
        else:
            assert first_plan.validation_plan.capture_frames == []


def test_packaged_glsl_template_emits_bounded_text_content():
    plan, artifacts = compile_module_graph(
        BuildIntent(outcome="Create an animated GLSL image"),
        _single_technique_graph("glsl_top_template"),
    )

    content_ops = [operation for operation in plan.operations if operation.kind == "set_dat_content"]
    assert len(content_ops) == 1
    assert content_ops[0].target.endswith("/subject_pixel_shader")
    assert "TDOutputSwizzle" in content_ops[0].args["text"]
    assert len(content_ops[0].args["text"].encode("utf-8")) <= 16 * 1024
    assert artifacts.build_program.final_output_path.endswith("/subject_out_shader")


def test_nonpackaged_registry_cannot_emit_dat_content(tmp_path):
    packaged = load_compiled_techniques()["glsl_top_template"]
    copied = tmp_path / "glsl_top_template.v2.json"
    copied.write_text(packaged.source_path.read_text(encoding="utf-8"), encoding="utf-8")
    custom_registry = load_compiled_techniques(tmp_path)

    with pytest.raises(BuildCompilerError, match="cannot emit content outside"):
        compile_module_graph(
            BuildIntent(outcome="Reject untrusted content registry"),
            _single_technique_graph("glsl_top_template"),
            registry=custom_registry,
        )


def test_exposed_control_comp_compiles_nested_paths_and_metadata():
    plan, artifacts = compile_module_graph(
        BuildIntent(outcome="Create reusable controls"),
        _single_technique_graph("exposed_control_comp"),
    )

    created_targets = {
        operation.args["name"]: operation.target
        for operation in plan.operations
        if operation.kind == "create_node"
    }
    assert created_targets["subject_controls"] == "/project1/compiled"
    assert created_targets["subject_values"] == "/project1/compiled/subject_controls"
    assert created_targets["subject_scale"] == "/project1/compiled/subject_controls"
    assert created_targets["subject_out_control"] == "/project1/compiled/subject_controls"

    controls = artifacts.build_program.modules[0].exposed_controls
    assert {control["name"] for control in controls} == {"value", "gain"}
    assert all(control["mapping_target"].startswith("/project1/compiled/") for control in controls)


def test_module_graph_compiles_deterministically_to_existing_patch_plan():
    intent = BuildIntent(
        outcome="Build seeded feedback with a compact grade and stable output",
        mode="production",
    )
    first_plan, first_artifacts = compile_module_graph(intent, _feedback_graph())
    second_plan, second_artifacts = compile_module_graph(intent, _feedback_graph())

    assert [op.model_dump(mode="json") for op in first_plan.operations] == [
        op.model_dump(mode="json") for op in second_plan.operations
    ]
    assert [module.fingerprint for module in first_artifacts.build_program.modules] == [
        module.fingerprint for module in second_artifacts.build_program.modules
    ]
    assert first_plan.source == "operations"
    assert first_artifacts.build_program.patch_plan_id == first_plan.id
    assert first_artifacts.build_program.final_output_path.endswith("/output_out_image")
    assert first_artifacts.execution_budget.maximum_patch_ops == 200

    kinds = [operation.kind for operation in first_plan.operations]
    assert max(index for index, kind in enumerate(kinds) if kind == "create_node") < min(
        index for index, kind in enumerate(kinds) if kind == "set_params"
    )
    assert any(
        operation.kind == "connect" and operation.args.get("from") == "/project1/input_image"
        for operation in first_plan.operations
    )

    metadata = generated_metadata(first_artifacts)
    assert metadata["technique_ids"] == [
        "top_feedback_transform",
        "top_multistage_grade",
        "stable_output_null",
    ]
    assert "primary" in metadata["output_paths"]


def test_simplifier_collapses_duplicate_resolution_modules_without_losing_output():
    first = _module(
        "resolution_a",
        "utility",
        "resolution_normalizer",
        source_ref="/project1/input_image",
        parameters={"width": 1280, "height": 720},
    )
    second = _module(
        "resolution_b",
        "utility",
        "resolution_normalizer",
        parameters={"width": 1280, "height": 720},
    )
    output = _module("output", "output", "stable_output_null")
    graph = ModuleGraph(
        target_root="/project1/compiled",
        modules=[first, second, output],
        edges=[
            ModuleEdge(
                source_module="resolution_a",
                source_port="image",
                target_module="resolution_b",
                target_port="image",
            ),
            ModuleEdge(
                source_module="resolution_b",
                source_port="image",
                target_module="output",
                target_port="image",
            ),
        ],
        output_module_id="output",
    )

    simplified, report = simplify_module_graph(graph)

    assert report.modules_before == 3
    assert report.modules_after == 2
    assert report.estimated_nodes_after < report.estimated_nodes_before
    assert {module.id for module in simplified.modules} == {"resolution_a", "output"}
    assert any(
        edge.source_module == "resolution_a" and edge.target_module == "output" for edge in simplified.edges
    )


def test_patch_diff_deletes_only_explicitly_owned_nodes():
    intent = BuildIntent(outcome="Build feedback")
    old_plan, _ = compile_module_graph(intent, _feedback_graph())
    new_graph = _feedback_graph().model_copy(
        update={
            "modules": [module for module in _feedback_graph().modules if module.id != "grade"],
            "edges": [
                ModuleEdge(
                    source_module="feedback",
                    source_port="image",
                    target_module="output",
                    target_port="image",
                )
            ],
        }
    )
    new_plan, _ = compile_module_graph(intent, new_graph)
    owned = {
        f"{operation.target.rstrip('/')}/{operation.args['name']}"
        for operation in old_plan.operations
        if operation.kind == "create_node" and operation.args.get("name", "").startswith("grade_")
    }

    diff = diff_patch_plans(old_plan, new_plan, owned_paths=owned)

    assert diff.delete_ops
    assert all(item["target"] in owned for item in diff.delete_ops)
