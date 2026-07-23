# TDPilot Effectiveness Roadmap

This note tracks the next gaps after the reviewed operator atlas reached a
zero-concept backlog. The goal is faster, more reliable translation from a
creative concept into actual TouchDesigner nodes, parameters, Python, GLSL, and
validation evidence.

For the deep implementation blueprint, see
`docs/TDPILOT_CONCEPT_TO_NODE_MASTER_PLAN.md`.

## Current Leverage

- 114 local MCP tools for live TD inspection, mutation, validation, memory,
  search, recommendations, safety, snapshots, and transactions.
- 659-card reviewed operator atlas across CHOP, COMP, DAT, MAT, POP, SOP, and
  TOP, with Official Derivative docs URLs, `key_concepts`, `key_params`, and
  `common_gotchas`.
- BrainPlan workflow that keeps planning read-only, executes transactionally,
  validates results, and rolls back failed work.
- Codex and Claude Code plugin add-ons: skills, agents, hooks, MCP config, and
  packaged atlas data.

## Highest-impact Missing Pieces

1. **Concept compiler**
   - Add a richer `VisualTaskSpec` decomposition layer that turns prompts like
     "melting glass terrain driven by music" into domains, constraints, time
     behavior, validation probes, and candidate operator families before node
     selection.
   - Output a ranked concept-to-node explanation so agents can justify why a
     chain uses POP, SOP, TOP, CHOP, DAT, or shader code.

2. **Validated pattern library**
   - Promote successful BrainPlans into reusable, parameterized patterns for
     feedback, particle fields, GL shaders, panel systems, MIDI/OSC/NDI I/O,
     DAT protocol bridges, and render pipelines.
   - Store the pattern intent, required operators, parameter ranges, layout,
     validation profile, and rollback notes.

3. **Build-aware operator availability**
   - Expand live operator sampling into a per-build matrix, including installed
     add-ons such as POPX.
   - Feed availability directly into `td_brain_plan` so plans downgrade,
     substitute, or ask blocked questions before mutation.

4. **Parameter semantics**
   - Extend cards with units, valid ranges, enum meanings, OP-reference types,
     tuple semantics, expensive toggles, and cook/performance implications.
   - Use those semantics to prevent invalid string refs, wrong family links,
     unsafe texture sizes, and unbounded feedback or particle growth.

5. **Profile-specific visual validation**
   - Move beyond generic nonblack/error checks toward profile validators:
     motion energy for audio-reactive systems, particle bounds and density for
     POPs, camera/frustum coverage for render networks, table schema checks for
     DAT protocols, and UI event/readback checks for panels.

6. **Code-generation harness**
   - Treat Python DATs, Execute DATs, GLSL TOP/MAT/POP, callbacks, and extension
     code as first-class build products with compile/run/readback checks.
   - Keep official snippets and atlas concepts connected to generated code,
     then test callbacks inside TD before claiming success.

7. **Fast project assembly**
   - Add higher-level macro patterns that produce readable layouts, color
     groups, notes, debug outputs, and user controls automatically.
   - Make the default build result production-shaped: named outputs, nulls,
     controls, annotations, and diagnostics already wired.

8. **Evaluation corpus**
   - Add golden tasks for complex multi-domain prompts and measure plan quality,
     operator choice, validation strength, runtime cost, and time-to-first-green.
   - Track regressions when operator cards, hints, or planner heuristics change.

## Product Rule

Prefer improvements that deepen the local rigor loop: inspect, plan, execute,
validate, recover, learn. Avoid cloud-gated features or parity-only surfaces
that do not make this loop faster, safer, or easier to audit.
