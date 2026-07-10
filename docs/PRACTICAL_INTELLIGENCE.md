# Practical Intelligence in TDPilot v2.4

Practical Intelligence is TDPilot's evidence-driven path from a creative
request to a usable TouchDesigner result. It is additive: all 114 tools,
legacy plans, primitive edits, draft schemas, and macros remain available.

## Routing contract

Use the shortest route that can truthfully cover the request:

| Request | Route |
|---|---|
| One proven edit at a known path | Targeted inspection → typed primitive edit |
| Exact validated topology or technique composition | `td_brain_plan` → `td_brain_execute` |
| Artistic, multi-domain, spatial, camera/depth/fog, or implicit architecture | `td_brain_ground` → author → `td_brain_propose` → execute |
| Unsupported or ambiguous combination | Ground/propose or clarify; never execute a partial fallback |
| Generated-system modification | Ownership metadata → `BuildProgramDiff` → affected-module rebuild |
| Failed runtime result | Validation → bounded assertion-specific repair or rollback |

Every material capability, input, output, behavior, constraint, spatial or
quality requirement, binding, and validation requirement must map to coverage
evidence. The server recomputes coverage; host-provided `complete=true` is not
trusted.

## Grounding and authoring

`td_brain_ground` gathers a compact, cached context from the relevant live TD
scope, official operator cards, compatible validated techniques, knowledge
summaries, and promoted validated traces. Knowledge prose is advisory. Only
validated techniques and promoted patterns may compile automatically.

The returned `grounding_id` binds a subsequent proposal to the original
request. `td_brain_propose` accepts legacy operator-level drafts and v2
module-level drafts, then recomputes coverage and semantic-edge realizability.

## Deterministic build compiler

The v2 compiler converts `BuildIntent` and a compact `ModuleGraph` into a
deterministic `BuildProgram` and existing `PatchPlan`. Patch operations are
stored once; modules and batches reference operation indices. Normalized equal
input produces stable names, ordering, fingerprints, outputs, and controls.

The packaged compiler set contains 15 techniques:

- stable output Null and resolution normalization
- feedback transform and displacement
- multistage grade and edge glow
- audio bands, transient envelope, and normalized modulator
- SOP instancing and basic GPU POP particles
- basic 3D render and render post chain
- GLSL TOP template and exposed-control COMP

Every technique carries compatibility, ports, tunables, costs, failure modes,
validation defaults, atlas-verified parameters, and fixture evidence.

## Bindings and semantic edges

New executable control edges must carry exactly one `ControlBindingSpec`.
TDPilot v2.4 proves one bounded cross-domain compiler path: a safe CHOP channel
reference expression targeting registry-backed numeric `levelTOP` parameters.
Unsupported audio-to-MAT, POP, camera, SOP, DAT-to-TOP, or arbitrary parameter
bindings block rather than silently becoming static values.

Reference edges must become explicit operator-reference parameters. No v2
semantic edge may be ignored during compilation or execution.

## Validation and repair

Validation reads actual post-apply state:

- graph: nodes, types, connections, references, bindings, outputs, ownership
- runtime: TD errors, cook health, CHOP activity, geometry/POP counts, readback
- visual: luminance, alpha, uniformity, and temporal motion
- performance: cook hotspots, frame trend, resolution, viewers/always-cook
- preservation: protected nodes, old output path, and required signal/image tolerances

Unavailable probes are reported as unavailable, not passed. Repairs are tied to
the failed assertion and bounded by execution mode: fast permits one repair;
production and show-safe permit two. Unknown failures or exhausted budgets
roll back or retain the last validated state.

## Show-safe and partial rebuilds

Show-safe execution builds inside a staging COMP, validates staging, and commits
through a guarded `route_swap`. The old route is retained after success;
deletion is a separate explicit operation. Partial rebuild requires compact
ownership and fingerprint metadata and refuses to proceed when preservation
evidence is insufficient.

## Compatibility and response size

- `detail_level="full"` remains the API default for compatibility.
- Shipped prompts use compact summaries and execute by cached `plan_id`.
- Legacy plans without `intent_coverage` remain accepted under legacy rules.
- Legacy `feedback_loop` and `audio_reactive` macros remain available as
  scaffolds, with truthful input/output metadata and deprecation warnings when
  requested as complete visuals.
- The public MCP surface remains exactly 114 tools and has no hosted-model
  dependency.

## Release evidence

Repository release gates require unit tests, 102 golden cases, deterministic
dry smoke, live transactional smoke, operator availability, plugin closure,
parameter-semantics risk, version/tox freshness, and real plugin/MCPB archive
inspection. Efficiency claims additionally require frozen measured baseline
and current benchmark observations; the benchmark harness refuses to infer
improvement from missing evidence.
