# TDPilot Concept-To-Node Master Plan

Last reviewed: 2026-06-20

This document is the implementation blueprint for turning TDPilot from an
operator-aware assistant into a fast concept-to-node system for complex
TouchDesigner work. It is intentionally deeper than the short effectiveness
roadmap. The roadmap names the gaps; this plan explains how to close them.

The current system has a strong local foundation: 111 MCP tools, transactional
BrainPlan execution, live TD inspection, rollback, validation, memory, search,
and a 656-card reviewed operator atlas with a zero-concept backlog across CHOP,
COMP, DAT, MAT, POP, SOP, and TOP. The next leap is composition. TDPilot should
not only know what an operator is. It should know how to decompose a creative
intent, choose a small operator chain, bind parameters safely, generate code
when needed, validate the result in TouchDesigner, and promote proven solutions
back into reusable patterns.

## 1. Executive Thesis

TDPilot already has the vocabulary. It now needs grammar, style, and proof.

Vocabulary is the operator atlas: documented operators, key concepts, important
parameters, gotchas, snippets, official docs URLs, and release relevance.
Grammar is the ability to combine those operators into valid multi-domain
systems. Style is the ability to produce readable, maintainable TouchDesigner
networks with controls, debug taps, notes, stable outputs, and safe defaults.
Proof is the local loop that inspects, plans, executes, validates, recovers, and
learns only from verified outcomes.

The target planning architecture is:

```text
Prompt -> ConceptCompiler -> CandidateGraph -> PatternResolver -> Availability Pass -> ParameterBinder -> PatchPlan -> Transaction -> Profile Validators -> Trace Promotion
```

The most important product rule is local rigor. Every improvement should deepen
the loop that already makes TDPilot valuable:

```text
inspect -> plan -> execute -> validate -> recover -> learn
```

Cloud-only features, broad UI polish, or packaging parity work should remain
secondary unless they make that loop faster, safer, or easier to audit.

## 2. Current Architecture

Today, the brain flow is:

```text
VisualTaskSpec -> ConceptGraph -> BrainPlan -> PatchPlan -> TransactionResult
```

`VisualTaskSpec` records the natural-language intent, target root, output TOP,
constraints, preferred domains, validation profile, and whether memory/docs are
included. `ConceptGraph` records the semantic nodes and data-flow edges. A
`BrainPlan` wraps the concept graph with a typed `PatchPlan`, missing facts,
blocked questions, grounding evidence, and risk flags. Transaction execution is
separate from planning so `td_brain_plan` remains read-only and blocked plans do
not mutate TouchDesigner.

The planner is currently safe because it is profile/template driven. It
classifies intents into profiles such as feedback, audio-reactive, POP, GLSL,
GLSL material, GLSL POP, render pipeline, panel UI, control rig, or generic.
Each profile owns a known operator graph and risk flags. This gives the system
good behavior on known classes of requests. It also creates a ceiling: many
creative TouchDesigner projects are multi-profile systems.

Example:

```text
"Make a melting glass terrain driven by music with UI controls"
```

This is not a single profile. It includes:

- CHOP analysis for music.
- SOP or POP geometry for terrain or points.
- GLSL MAT or TOP shader logic for glass and melting.
- Render TOP pipeline for output.
- Panel or custom parameters for controls.
- Validators for audio movement, shader compile state, render coverage, and
  stable output.

The current planner can pick one profile, but the desired system should compose
several patterns, then validate the assembled network.

## 3. Target Architecture

The target system adds intermediate layers before PatchPlan compilation.

```text
Prompt
  -> ConceptCompiler
  -> CompiledVisualTaskSpec
  -> CandidateConceptGraph list
  -> PatternResolver
  -> BrainPattern instances
  -> OperatorAvailabilityMatrix and substitution pass
  -> ParamSemantics and ParameterBinder
  -> PatchPlan
  -> Transaction
  -> ProfileValidationProbe suite
  -> BrainTrace promotion
```

The architecture keeps the current safety model:

- Planning stays read-only.
- Execution accepts only valid BrainPlans or PatchPlans.
- Mutation runs through transaction defaults.
- Validation failures roll back when configured.
- Learning happens only after verified outcomes.

The new layers make the system more expressive without making it less safe.

## 4. Workstream Deep Dives

### 4.1 Concept Compiler

The concept compiler turns free text into a structured intent model before any
operator graph is selected.

Current limitation:

- Intent classification is mostly keyword/profile based.
- A prompt usually maps to one profile.
- Multi-domain prompts lose information before planning.

Goal:

- Parse a creative request into domains, motifs, input sources, outputs, time
  behavior, validation needs, constraints, risks, and candidate operator
  families.
- Produce an explanation of why each domain and operator family was considered.
- Keep the output deterministic enough to test.

Future interface:

```python
class CompiledVisualTaskSpec(BaseModel):
    intent: str
    target_root: str
    output_top: str | None
    domains: list[str]
    motifs: list[str]
    time_behavior: list[str]
    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    constraints: dict[str, Any]
    required_capabilities: list[str]
    candidate_profiles: list[str]
    candidate_operator_families: list[str]
    validation_needs: list[str]
    risk_flags: list[str]
    grounding_evidence: list[str]
```

Example output for "melting glass terrain driven by music":

```text
domains: CHOP, SOP or POP, MAT, TOP, COMP
motifs: terrain, glass, melting, audio-reactive motion
time_behavior: continuous animation, beat or amplitude modulation
inputs: audio file or live audio
outputs: final TOP, debug CHOP, control panel
candidate_profiles: audio_reactive, render_pipeline, glsl_material, control_rig
validation_needs: audio signal movement, shader compile state, render nonblack,
camera coverage, bounded parameter ranges
```

Implementation plan:

1. Add a pure compiler module that accepts intent, constraints, preferred
   domains, and optional current TD state summary.
2. Start with deterministic extraction rules:
   - Domain hints: audio, music, beat, OSC, MIDI, serial, panel, UI, shader,
     particles, POP, render, camera, material, terrain, geometry, texture.
   - Motif hints: glass, fluid, trails, cellular, field, terrain, typography,
     particles, reactive, generative, protocol, control surface.
   - Output hints: TOP output, CHOP control, DAT table, rendered 3D, panel.
3. Query the atlas and docsbrain index for candidate operators.
4. Score profiles and operator families from compiler features.
5. Return blocked questions when the prompt lacks enough intent to select a
   safe route.

Tests:

- Audio plus terrain plus material prompt returns multiple profiles.
- Vague prompt returns blocked facts and no candidate graph.
- Preferred domain constraints affect scores.
- Compiler evidence lists atlas/docsbrain sources when cards are available.
- Compiler output is stable across runs for the same input.

Effort:

- MVP: 3-5 focused days.
- Production useful: 2-3 weeks.

### 4.2 Candidate Concept Graphs

The compiler should not emit one graph immediately. It should produce ranked
candidate graphs so the planner can choose the smallest viable plan and explain
tradeoffs.

Future interface:

```python
class CandidateConceptGraph(BaseModel):
    id: str
    compiled_task_id: str
    label: str
    profiles: list[str]
    concepts: list[ConceptNode]
    edges: list[ConceptEdge]
    required_ops: list[str]
    optional_ops: list[str]
    expected_outputs: list[str]
    validation_needs: list[str]
    risk_flags: list[str]
    score: float
    explanation: str
```

Candidate graph scoring should prefer:

- Fewer operators when visual quality is adequate.
- Operators known to exist in the current TD build.
- Patterns with previous successful traces.
- Official Derivative docs coverage.
- Strong validation probes.
- Stable output and debug taps.

Candidate graph scoring should penalize:

- Missing operators.
- Unbounded feedback or particle growth.
- Shader or Python code without a validation harness.
- Device/network dependencies not available in current state.
- Broad operator pattern matching that could pull in unintended nodes.

Tests:

- Multi-domain prompts produce at least two candidates when multiple viable
  architectures exist.
- Missing operator candidates are ranked lower or blocked.
- Candidate explanations name the relevant profiles and required operators.

Effort:

- MVP: 2-4 focused days after the concept compiler.
- Stronger scoring: 1-2 additional weeks with trace data.

### 4.3 Validated Pattern Library

Patterns are the speed layer. They prevent the planner from rebuilding common
TouchDesigner structures from raw operators every time.

Current limitation:

- Profile specs are embedded in planner code.
- Reusable network shapes are not represented as data.
- Successful BrainPlans are not promoted into parameterized recipes.

Goal:

- Store reusable, parameterized patterns that can be composed into larger
  systems.
- Keep each pattern small enough to validate independently.
- Use patterns as the default building blocks for complex work.

Future interface:

```python
class BrainPattern(BaseModel):
    pattern_id: str
    title: str
    intent_tags: list[str]
    profiles: list[str]
    required_ops: list[str]
    optional_ops: list[str]
    concept_nodes: list[dict[str, Any]]
    concept_edges: list[dict[str, Any]]
    parameters: list[dict[str, Any]]
    layout: dict[str, Any]
    debug_outputs: list[dict[str, Any]]
    validation_profile: str
    validation_probes: list[str]
    rollback_risks: list[str]
    official_sources: list[str]
    promoted_from_trace: str | None
```

First pattern set:

- `audio_file_to_analysis_chop`
- `audio_device_to_analysis_chop`
- `feedback_decay_top_loop`
- `pop_particle_field_preview`
- `glsl_top_shader_with_text_dat`
- `glsl_mat_render_pipeline`
- `render_geo_camera_light_output`
- `panel_controls_to_chop_output`
- `dat_execute_table_change_callback`
- `serial_dat_protocol_bridge`
- `midi_in_to_control_chop`
- `ndi_in_to_post_fx_output`

Pattern composition rules:

- A pattern may expose outputs by domain: TOP, CHOP, DAT, POP, SOP, MAT, COMP.
- A pattern may consume outputs from another pattern by declared port.
- A pattern must name at least one validator.
- A pattern must state whether it is safe in dry run only, safe live, or device
  dependent.
- A pattern must include official source URLs for operator behavior.

Tests:

- Pattern schema rejects missing required ops, invalid domains, and unknown
  validation probes.
- Pattern resolver can compose audio analysis into feedback modulation.
- Pattern resolver blocks device-dependent patterns when no device source is
  available and no fallback is declared.
- Every promoted pattern has at least one eval case.

Effort:

- Schema plus first 8-10 patterns: 1 focused week.
- Useful library of 40-60 patterns: 3-5 focused weeks.

### 4.4 Build-Aware Operator Availability

The planner should know what the running TouchDesigner build can create before
it recommends an operator chain.

Current leverage:

- Live family inspection already exists.
- Operator availability sampling exists for gap review.
- Atlas cards include build relevance and replacement notes for many operators.

Goal:

- Maintain a per-build, per-add-on operator matrix.
- Feed availability into planning, substitution, and blocked questions before
  mutation.

Future interface:

```python
class OperatorAvailabilityMatrix(BaseModel):
    schema_version: int
    td_build: str
    platform: str
    generated_at: str
    installed_addons: list[str]
    operators: dict[str, dict[str, Any]]
    family_aliases: dict[str, list[str]]
    unavailable_reasons: dict[str, str]
```

```python
class OperatorSubstitutionRule(BaseModel):
    missing_op: str
    replacement_ops: list[str]
    replacement_pattern: str | None
    confidence: str
    tradeoffs: list[str]
    official_sources: list[str]
    requires_user_approval: bool
```

Examples:

- If a POP operator is absent but a SOP/TOP fallback can express the intent,
  rank the fallback lower but keep it available.
- If a protocol operator depends on hardware, block or ask for confirmation.
- If a deprecated operator has an official replacement, prefer the replacement.

Tests:

- Missing required operator blocks plan mutation.
- Available replacement lowers risk and produces a new candidate graph.
- Current TD build metadata appears in grounding evidence.
- Add-on availability changes candidate ranking.

Effort:

- MVP: 3-5 focused days.
- Robust build/add-on matrix: 1-2 weeks.

### 4.5 Parameter Semantics

Operator cards now include important parameters, but the next step is
machine-checkable meaning.

Current limitation:

- Parameter guards exist for some official params and reference rules.
- The planner can still set values without knowing units, ranges, enum meaning,
  OP-reference family, tuple shape, or performance risk.

Goal:

- Extend selected operator cards or companion semantic cards with enough
  structure to bind parameters safely.
- Prevent common invalid references and expensive settings.
- Auto-create controls for user-facing parameters.

Future interface:

```python
class ParamSemantics(BaseModel):
    op_type: str
    name: str
    label: str
    value_kind: str
    expected_family: str | None
    expected_op_type: str | None
    tuple_size: int | None
    unit: str | None
    valid_range: tuple[float, float] | None
    enum_values: list[str]
    default_strategy: str
    cook_risk: str
    validation_rule: str | None
    official_source: str
```

Priority operator bands:

- Render and material: `renderTOP`, `geometryCOMP`, `cameraCOMP`, `lightCOMP`,
  `glslMAT`, `pbrMAT`, `phongMAT`.
- GLSL: `glslTOP`, `glslmultiTOP`, `glslPOP`, `glsladvancedPOP`,
  `glslCOMP`.
- Feedback and TOP processing: `feedbackTOP`, `levelTOP`, `compositeTOP`,
  `transformTOP`, `cacheTOP`.
- POP: generators, `noisePOP`, `mathmixPOP`, `attributecombinePOP`,
  `rendersimpleTOP`.
- Audio and control: `audiofileinCHOP`, `audiodeviceinCHOP`, `analyzeCHOP`,
  `mathCHOP`, `filterCHOP`, `lagCHOP`.
- Panels and parameters: `baseCOMP`, `containerCOMP`, `sliderCOMP`,
  `buttonCOMP`, `panelCHOP`, `parameterCOMP`.
- DAT callbacks and protocols: `datexecuteDAT`, `chopexecuteDAT`,
  `executeDAT`, `serialDAT`, `oscinDAT`, `websocketDAT`.

Binding rules:

- OP reference params must point at compatible created or existing nodes.
- Enum params must use official names.
- Tuple params must preserve tuple length.
- Output resolution and sampling settings must respect performance warnings.
- Feedback opacity/decay and particle growth must be bounded.

Tests:

- Invalid OP-family references are caught before mutation.
- Parameter enum validation rejects unknown values.
- Dangerous high-resolution settings produce warning risk flags.
- Top-priority operator cards expose semantics for required params.

Effort:

- Top 50 high-risk operators: 1-2 focused weeks.
- Broad useful coverage: 4-8 focused weeks.

### 4.6 Profile-Specific Visual Validation

Validation should prove behavior, not just absence of obvious errors.

Current leverage:

- Validation profile names already exist.
- Structural checks and severity classification exist.
- Live and dry-run smoke tests exercise the brain loop.

Goal:

- Turn profile check names into real probes.
- Use cheap readbacks by default, expensive readbacks only in explicit
  validation modes.
- Attach validation requirements to patterns and candidate graphs.

Future interface:

```python
class ProfileValidationProbe(BaseModel):
    probe_id: str
    profile: str
    required_inputs: list[str]
    readback_strategy: str
    metric_names: list[str]
    pass_conditions: list[str]
    cost_level: str
    failure_message: str
```

Probe examples:

- Feedback: cycle exists, decay stage is present, output is nonblack, output is
  not saturated, temporal difference exists after a few frames.
- Audio-reactive: source CHOP exists, analysis channel changes over time, range
  shaping maps signal into a bounded control range.
- POP: output has finite bounds, point count is within expected range, render
  preview is nonempty.
- GLSL TOP: shader DAT is attached, compile state is clean, output has valid
  resolution and nonblack pixels.
- GLSL MAT: vertex/pixel DATs exist, material is assigned, camera and geometry
  are referenced by render TOP, render output is visible.
- Panel UI: panel components exist, panelCHOP reads state, generated controls
  map to expected output channels.
- DAT protocol: table schema matches expected columns, callback DAT can be
  invoked safely, high-rate callbacks are guarded.

Official source notes:

- The Official Derivative `TOP Class` page warns that sampling a TOP can stall
  the graphics pipeline and should be used for debugging/non-realtime workflows:
  https://docs.derivative.ca/TOP_Class
- Validation should therefore prefer cheap Info CHOP, metadata, and selective
  readbacks before full texture downloads.

Tests:

- Each concept profile maps to at least one real probe.
- Expensive probes are opt-in or smoke-only.
- Probe failures produce stable issue codes and actionable messages.
- Live smoke reports profile probe names and result summaries.

Effort:

- Strong MVP: 1-2 focused weeks.
- Robust profile coverage: 3-6 focused weeks.

### 4.7 Python And GLSL Code-Generation Harness

Complex TD systems often require Python or GLSL, so generated code must become
a first-class build product.

Current leverage:

- GLSL snippet cards exist.
- Operator cards cover Script CHOP/TOP/DAT/SOP, Execute DATs, GLSL TOP/MAT/POP,
  and callback gotchas.
- Reference-param validation already checks some shader DAT bindings.

Goal:

- Represent generated code explicitly.
- Attach code blocks to operators through typed plan operations.
- Validate syntax, binding, compile state, callback behavior, and readbacks.

Future interface:

```python
class GeneratedCodeBlock(BaseModel):
    block_id: str
    language: str
    target_op: str
    target_param: str | None
    source_kind: str
    source_refs: list[str]
    code: str
    static_checks: list[str]
    runtime_checks: list[str]
    expected_outputs: list[str]
    risk_flags: list[str]
```

Python harness rules:

- Script CHOP, Script DAT, Script SOP, and Script TOP should include expected
  method signatures for their operator family.
- Execute DAT callbacks should use modern callback methods for the TD build.
- Generated callbacks must avoid unguarded writes to the watched operator or
  watched parameter.
- Callback scripts should include a minimal readback or diagnostic output when
  practical.

GLSL harness rules:

- GLSL TOP pixel shaders should use TouchDesigner output conventions and attach
  source DATs through official params.
- GLSL POP compute shaders should guard writes with `TDIndex()` and
  `TDNumElements()` when applicable.
- GLSL MAT shaders should bind vertex/pixel DATs and assign the material to a
  rendered geometry.
- GLSL Advanced POP should be selected when output counts, topology, or multiple
  attribute classes must change.

Official source notes:

- `DAT Execute DAT` monitors DAT contents and, in 2025.30000+ builds, uses
  `onTableChange` for table changes while legacy row/column/cell/size callbacks
  are deprecated: https://docs.derivative.ca/DAT_Execute_DAT
- `Script CHOP` cooks through Python methods and tracks procedural dependencies,
  so generated code must be careful about recook dependencies:
  https://docs.derivative.ca/Script_CHOP
- `Script TOP` can generate images from Python using NumPy arrays:
  https://docs.derivative.ca/Script_TOP
- `GLSL TOP` can pass POP attribute buffers into shaders:
  https://docs.derivative.ca/GLSL_TOP
- `Write a GLSL POP` explains that actual compute threads may exceed requested
  elements and writes should be guarded:
  https://docs.derivative.ca/Write_a_GLSL_POP
- `GLSL MAT` is the custom material route for shader-driven render pipelines:
  https://docs.derivative.ca/GLSL_MAT

Tests:

- Generated Python code passes syntax checks before being written.
- Generated GLSL code is attached to the correct DAT parameter.
- Missing shader DAT references fail before mutation.
- Live smoke can intentionally compile a tiny shader and read a clean result.
- Callback patterns include recursion guards for high-risk execute DATs.

Effort:

- MVP: 2 focused weeks.
- Production-grade code harness: 4-6 focused weeks.

### 4.8 Fast Project Assembly Macros

The default result should look like a production-shaped TouchDesigner
component, not a loose cluster of nodes.

Goal:

- Add assembly macros that wrap selected patterns into readable networks.
- Create named outputs, debug taps, notes, controls, and diagnostics by default.
- Keep the output easy for a human TD artist to inspect and repair.

Future interface:

```python
class AssemblyMacro(BaseModel):
    macro_id: str
    label: str
    applies_to_profiles: list[str]
    layout_strategy: str
    created_controls: list[dict[str, Any]]
    debug_nodes: list[dict[str, Any]]
    notes: list[str]
    output_contract: list[str]
    validation_addons: list[str]
```

Macro examples:

- `make_component_shell`: creates a base COMP shell with clean internal layout.
- `add_named_outputs`: adds stable `out1`, `out_chop`, `out_dat`, or `out_pop`
  nodes as appropriate.
- `add_debug_panel`: adds Info CHOPs, error DATs, and simple readouts.
- `add_user_controls`: creates panel or custom parameters for pattern-exposed
  values.
- `annotate_operator_chain`: adds notes explaining the main concept chain and
  validation assumptions.
- `group_by_domain`: lays out CHOP, TOP, POP, DAT, MAT, and COMP sections in
  predictable bands.

Official source notes:

- The Official Derivative Component Editor handles custom parameters,
  extensions, shortcuts, tags, and storage, so generated components should use
  these concepts instead of hiding important state in ad hoc scripts:
  https://docs.derivative.ca/Component_Editor_Dialog
- Derivative palette guidance for portable scenes recommends working inside a
  child component when custom parameters or extensions may be needed:
  https://docs.derivative.ca/Palette%3AsceneChanger

Tests:

- Assembly macro output has stable named outputs.
- Domain layout is deterministic.
- Debug nodes do not alter primary output.
- Generated controls map to known pattern parameters.
- Notes include evidence references and validation summary.

Effort:

- MVP: 3-5 focused days.
- Refined production assembly: 2-3 focused weeks.

### 4.9 Evaluation Corpus

The eval corpus should measure "idea to working TD network," not only profile
classification.

Future interface:

```python
class ConceptToNodeEvalCase(BaseModel):
    case_id: str
    prompt: str
    expected_domains: list[str]
    expected_profiles: list[str]
    expected_operator_sets: list[list[str]]
    forbidden_ops: list[str]
    required_patterns: list[str]
    validation_expectations: list[str]
    max_plan_ops: int
    live_required: bool
    scoring_weights: dict[str, float]
```

Eval dimensions:

- Intent decomposition correctness.
- Domain coverage.
- Operator choice.
- Pattern selection.
- Parameter binding safety.
- Availability-aware fallback behavior.
- Validation strength.
- Runtime safety.
- Time-to-first-green.
- Human readability of the generated network.

First eval bands:

- Audio reactive TOP feedback with controls.
- Audio reactive 3D render with material modulation.
- POP particle field with render preview.
- GLSL TOP image effect with generated shader DAT.
- GLSL MAT render pipeline.
- DAT table driving a render switch.
- MIDI or OSC control bridge.
- Serial protocol bridge with table diagnostics.
- Panel UI controlling a visual chain.
- Multi-domain "showpiece" prompts combining 3-5 patterns.

Tests:

- Golden eval runner reports decomposition, plan, validation, and time metrics.
- Regression gate fails when expected domains or required profiles disappear.
- Trace replay detects profile/operator drift.
- Live smoke includes at least one multi-pattern dry-run case and one safe live
  planning case when TD is open.

Effort:

- 30 additional complex eval cases: 2-4 focused days.
- Serious corpus with scoring and trace metrics: 2 focused weeks.

## 5. Phased Delivery Plan

The recommended delivery order is designed to produce useful gains quickly
while keeping every phase testable.

### Phase 1: Compiler And Pattern Seed

Duration: 1 focused week.

Deliverables:

- `CompiledVisualTaskSpec` model.
- Concept compiler MVP.
- `CandidateConceptGraph` model.
- Pattern schema.
- First 8-10 `BrainPattern` records.
- 20-30 concept-to-node eval cases.
- Planner evidence showing compiler output and selected pattern IDs.

Acceptance:

- Multi-domain prompts produce multi-domain compiled specs.
- Existing single-profile prompts keep current behavior.
- Vague prompts still block safely.
- Pattern records validate from JSON.
- Focused evals run in CI or local release gates.

### Phase 2: Availability And Parameter Safety

Duration: 1-2 focused weeks.

Deliverables:

- `OperatorAvailabilityMatrix`.
- Add-on/build sampling report.
- `OperatorSubstitutionRule` records.
- `ParamSemantics` for top high-risk operators.
- Parameter binder validation before PatchPlan emission.

Acceptance:

- Plans degrade or block before mutation when operators are unavailable.
- Substitution choices are visible in grounding evidence.
- Invalid OP refs and enum values fail before transaction apply.
- Top render, GLSL, feedback, POP, audio, panel, and DAT callback params have
  semantics coverage.

### Phase 3: Validators And Code Harness

Duration: 2-3 focused weeks.

Deliverables:

- `ProfileValidationProbe` registry.
- Real probes for feedback, audio-reactive, POP, GLSL, render pipeline, panel
  UI, and DAT protocol profiles.
- `GeneratedCodeBlock` model.
- Python syntax and callback checks.
- GLSL attachment and compile/readback checks.

Acceptance:

- Validation reports include profile-specific metrics.
- Generated shader/Python failures produce stable issue codes.
- Expensive validation probes are controlled and documented.
- Live smoke proves at least one generated-code path when TD is available.

### Phase 4: Fast Assembly, Plugin Surface, And Broad Evals

Duration: 2-3 focused weeks.

Deliverables:

- `AssemblyMacro` registry.
- Component shell, named output, debug panel, control panel, notes, and layout
  macros.
- 50-100 concept-to-node eval cases.
- Codex and Claude Code skill updates for the new workflow.
- README/plugin README updates after implementation is real.
- Release gates for pattern coverage, compiler stability, validators, and plugin
  surface packaging.

Acceptance:

- Generated networks are readable by default.
- Complex showpiece prompts produce assembled components rather than loose
  operator chains.
- Plugin instructions tell agents to use compiler, patterns, availability, and
  validation evidence.
- Release gates prove the packaged add-ons include the new workflow.

### Overall Effort

- Major capability jump: 6-9 focused weeks.
- Production-polished breadth: 10-14 weeks.

The shorter estimate assumes one primary engineer/agent loop with occasional
review and a narrow pattern set. The longer estimate assumes broader operator
semantics, richer validators, more live TD testing, and packaged plugin polish.

## 6. Evaluation Strategy

The system should be evaluated on outcomes, not only structural correctness.

Primary metric:

- Time-to-first-green: how many planning/execution/validation cycles are needed
  before a prompt yields a validated TD network.

Secondary metrics:

- Multi-domain decomposition accuracy.
- Required operator coverage.
- Unsupported operator avoidance.
- Substitution quality.
- Parameter safety.
- Generated code compile/runtime success.
- Validation strength.
- Rollback frequency.
- Human readability score.
- Trace replay stability.

Regression gates:

- Compiler golden cases.
- Pattern schema validation.
- Atlas/card-index lookup tests.
- Availability matrix sampling tests with fake TD and optional live TD.
- Parameter semantics tests for high-risk operators.
- Profile probe tests.
- Generated code harness tests.
- Brain smoke dry-run.
- Live smoke when TouchDesigner is open.
- Plugin surface audit once skills/manifests change.

The evaluation corpus should include both "single skill" and "showpiece"
prompts. Single-skill prompts protect focused behavior. Showpiece prompts prove
composition.

## 7. Plugin And Agent Surface

Codex and Claude Code should expose the concept-to-node loop as a workflow, not
only as a list of tools.

Codex-facing guidance:

- The project `AGENTS.md` should continue to emphasize inspect-before-mutate,
  BrainPlan construction, transaction execution, and validation.
- Brain-builder skills should instruct Codex to use the compiler, pattern
  resolver, availability matrix, parameter semantics, and validation probes once
  those features exist.
- Skills should remain focused and progressively disclosed. The official OpenAI
  Codex skills docs describe skills as reusable workflows with optional scripts
  and references, and note that Codex loads full skill instructions only when a
  skill is selected: https://developers.openai.com/codex/skills
- Codex project guidance should stay in `AGENTS.md` because Codex reads layered
  project instructions from AGENTS files:
  https://developers.openai.com/codex/guides/agents-md

Claude Code-facing guidance:

- The Claude plugin should package skills, agents, hooks, and MCP config that
  point users toward the same local brain loop.
- Claude Code plugin docs describe plugins as self-contained directories with
  components such as skills, agents, hooks, MCP servers, LSP servers, and
  monitors: https://code.claude.com/docs/en/plugins-reference
- Hooks can inject context, audit config changes, block unsafe commands, and
  notify users at lifecycle points:
  https://code.claude.com/docs/en/hooks-guide
- TDPilot hooks should remain deterministic and local. They should check release
  gates and packaging consistency rather than doing hidden cloud work.

Plugin surface timing:

- Do not update plugin promises before runtime support exists.
- After Phase 1, update skill docs to say "compiler-backed pattern planning"
  only if compiler/pattern tests are green.
- After Phase 3, update plugin README and manifests to mention generated-code
  validation only if live/dry-run evidence exists.
- After Phase 4, update public surfaces with measured capability claims, not
  aspirational wording.

## 8. Risk Map

### Hallucinated Operator Chains

Risk:

- The agent invents an operator, parameter, or connection pattern.

Mitigation:

- Require atlas/docsbrain evidence for operator choices.
- Use availability matrix before PatchPlan emission.
- Validate parameter semantics before mutation.
- Block when grounding evidence is missing.

### TouchDesigner Build Drift

Risk:

- A plan is valid in one build but invalid in another.

Mitigation:

- Record TD build and platform in availability evidence.
- Store build-specific availability reports.
- Use substitution rules with official replacement sources.
- Keep release-note freshness gates.

### Invalid OP References

Risk:

- Generated parameters point at the wrong family or wrong operator type.

Mitigation:

- Extend `ParamSemantics` for OP reference params.
- Validate created references statically before transaction apply.
- Use live readback after apply.

### Expensive Validation Probes

Risk:

- Validation stalls the project or damages realtime performance.

Mitigation:

- Mark probes by cost level.
- Default to cheap metadata and Info CHOP checks.
- Reserve TOP texture sampling and full readbacks for explicit validation modes.
- Follow Official Derivative warnings about TOP sampling cost.

### Shader And Callback Failures

Risk:

- Generated GLSL or Python compiles poorly, runs recursively, or fails only at
  runtime.

Mitigation:

- Represent generated code as `GeneratedCodeBlock`.
- Run static checks before writing.
- Attach code to official params.
- Validate compile state and callback behavior inside TD.
- Use safe callback templates per operator family.

### Plugin Surface Drift

Risk:

- Codex and Claude Code package docs promise features not shipped or miss new
  workflows.

Mitigation:

- Add tests that assert plugin/README surfaces mention only verified features.
- Run plugin surface audit and package build smoke before release.
- Keep root skills, `.agents` skills, and plugin skills mirrored.

## 9. Research Notes

Official Derivative docs:

- `DAT Execute DAT`: table-change callback behavior and 2025.30000+ callback
  modernization inform the Python callback harness:
  https://docs.derivative.ca/DAT_Execute_DAT
- `Script CHOP`: cook-time Python methods and dependency recook behavior inform
  script-generation risk handling:
  https://docs.derivative.ca/Script_CHOP
- `Script TOP`: Python image generation via NumPy informs Python code-block
  validation for TOP output:
  https://docs.derivative.ca/Script_TOP
- `GLSL TOP`: shader params, buffers, and POP attribute buffer access inform
  GLSL TOP code binding:
  https://docs.derivative.ca/GLSL_TOP
- `Write a GLSL POP`: thread dispatch and guard rules inform GLSL POP template
  safety:
  https://docs.derivative.ca/Write_a_GLSL_POP
- `GLSL POP`: selected attribute-class behavior and fixed element counts inform
  POP shader pattern selection:
  https://docs.derivative.ca/GLSL_POP
- `GLSL Advanced POP`: topology/output-count capability informs when to choose
  Advanced POP instead of GLSL POP:
  https://docs.derivative.ca/GLSL_Advanced_POP
- `GLSL MAT` and `Write a GLSL MAT`: material shader routing informs render
  pipeline and material validation:
  https://docs.derivative.ca/GLSL_MAT
  https://docs.derivative.ca/Write_a_GLSL_MAT
- `TOP Class`: sampling cost informs validation probe cost policy:
  https://docs.derivative.ca/TOP_Class
- `Component Editor Dialog`: custom parameters, extensions, tags, and storage
  inform component assembly macros:
  https://docs.derivative.ca/Component_Editor_Dialog

Official agent-platform docs:

- OpenAI Codex `AGENTS.md` guidance defines how project instructions are
  discovered and layered:
  https://developers.openai.com/codex/guides/agents-md
- OpenAI Codex skills docs define skills as reusable workflows with progressive
  disclosure:
  https://developers.openai.com/codex/skills
- Claude Code plugin reference defines plugin components, including skills,
  agents, hooks, and MCP servers:
  https://code.claude.com/docs/en/plugins-reference
- Claude Code hooks guide defines lifecycle automation use cases:
  https://code.claude.com/docs/en/hooks-guide

Local TDPilot sources:

- The short roadmap remains the lightweight summary:
  `docs/TDPILOT_EFFECTIVENESS_ROADMAP.md`
- The current brain models define the stable safety envelope:
  `src/td_mcp/models/brain.py`
- The current planner shows the profile/template ceiling this plan addresses:
  `src/td_mcp/brain/planner.py`
- The current validators show the check names that should become real probes:
  `src/td_mcp/brain/validators.py`
- The operator atlas provides the local operator vocabulary:
  `src/td_mcp/knowledge/cards/operators/`

## 10. Final Recommendations

Start with Phase 1:

```text
Concept compiler MVP + pattern schema + first validated patterns + eval seed
```

This is the best first slice because it changes the planner from single-profile
selection toward compositional planning while preserving the existing safety
model. It also creates the data structures that every later phase needs.

The first implementation should avoid broad refactors. Add the compiler and
pattern resolver beside the current planner, route only selected prompts through
the new flow, and preserve all current profile tests. A good first success case
is:

```text
"Build an audio-reactive feedback visual with a control panel and debug output"
```

Expected result:

- Compiled task identifies CHOP, TOP, COMP, and UI domains.
- Candidate graph composes audio analysis, feedback loop, panel controls, debug
  outputs, and stable TOP output.
- Availability pass confirms required operators.
- Parameter binder resolves OP references safely.
- PatchPlan remains typed and transactional.
- Validation checks audio movement, feedback output, panel readback, TD errors,
  and cook health.
- Successful trace can be promoted into a pattern candidate.

That path is narrow enough to test, but broad enough to prove the new direction.
