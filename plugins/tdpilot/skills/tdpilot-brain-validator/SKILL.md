---
name: tdpilot-brain-validator
description: >
  Use when checking whether a TDPilot BrainPlan, transaction result, or
  TouchDesigner network is structurally and visually correct.
---

# TDPilot Brain Validator

Use this skill after `td_brain_plan`, after `td_brain_execute`, or whenever the
user asks whether a TouchDesigner network is correct.

## Validator Posture

Be strict and evidence-based. A network is not correct just because tools
returned success. It must match the concept, cook cleanly, and satisfy cheap
visual sanity checks.

## Core Rule

Do not approve correctness from a status flag alone. Validate concept, structure,
runtime health, visual metrics, rollback state, and learning eligibility.

## Validation Checklist

- Plan integrity:
  - `BrainPlan` has no `blocked_questions`.
  - Concept graph edges reference real concept nodes.
  - Patch operations are dependency ordered and under `max_ops`.

- TD grounding:
  - Operator types exist in the live TD family list.
  - Names do not conflict with existing nodes unless the plan explicitly handles it.
  - Parameters are valid for their operator cards or docsbrain evidence.

- Structural checks:
  - Required inputs are connected.
  - Feedback loops contain a safe delay/feedback operator and level control.
  - Render pipelines have camera, geometry, material, light or explicit no-light design, render TOP, and output TOP.
  - Audio-reactive networks contain a CHOP source, analysis stage, modulation mapping, and visual target.
  - POP/POPx networks expose finite bounds and do not leave particle output detached.
  - GLSL networks expose shader source, compile state, uniforms, and output path.
  - Panel UI networks have callbacks/custom parameters wired to actual targets.

- Runtime checks:
  - `td_get_errors` has no critical unacknowledged errors.
  - `td_cooking_info` or transaction validation reports acceptable cook health.
  - Parameter readback confirms important values were applied.
  - Optional visual metrics are plausible: luminance not black/white locked, alpha coverage nonzero, entropy above trivial threshold, frame delta present for animated outputs, POP bounds finite.

## Severity

- `critical`: broken network, failed rollback, missing required operator, hard TD error.
- `error`: concept cannot be considered complete, output is absent, compile/cook failure.
- `warning`: risky default, weak visual metric, missing optional evidence.
- `info`: useful trace detail that does not affect pass/fail.

## Memory Promotion Rule

Only validated outcomes can be learned or promoted. A technique must include
intent, concept graph, operators used, TD build, validation report, rollback
state, cited docs/hints, and a reusable fingerprint.

## Pressure Scenarios

- Pressure: `td_brain_execute` returns success but visual metrics are absent for a visual task. Mark the result incomplete or warning-level until screenshot/TOP analysis proves output quality.
- Pressure: The user wants to promote a useful-looking patch after rollback or warnings. Refuse promotion unless validation passed under compatible TD build and operator constraints.

## Common Mistakes

- Confusing `warnings` with clean validation when the concept requires visual proof.
- Ignoring `family-list-omitted:*` risk flags instead of checking docs or live creatability.
- Approving a network whose output node exists but is disconnected from the intended concept graph.
