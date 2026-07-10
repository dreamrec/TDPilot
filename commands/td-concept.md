---
description: Turn an artistic TouchDesigner concept into a grounded, reviewed, transactional build
argument-hint: <visual concept>
---

Build the user's concept from `$ARGUMENTS` through TDPilot's concept-authoring
route. If no concept was supplied, ask for one concise visual intention before
continuing.

1. Inspect focus, target root, direct connections, relevant errors, and likely
   output. Ask only when the root/output or an external source remains genuinely
   ambiguous.
2. Extract every required capability, input, output, constraint, spatial
   feature, behavior, quality, binding, and validation need from the concept.
3. Call `td_brain_ground` directly with the complete intent, target root,
   constraints, desired output, `include_memory=true`, and
   `trace_level="summary"`.
4. Author the smallest graph allowed by the returned authoring contract,
   candidates, operator availability, parameter semantics, and relevant local
   recall. Load the builder skill's `references/progressive-drafts.md` only if a
   2D or 3D skeleton helps; live grounding always wins.
5. Call `td_brain_propose` with the returned `grounding_id`,
   `draft_schema_version="2"`, and `detail_level="summary"`. Fix
   machine-readable rejections and essential stripped parameters. Do not
   silently reduce the requested concept.
6. Execute only an accepted `plan_id` whose server-recomputed required coverage
   is complete and whose semantic edges are fully lowered. Use rollback on
   failure.
7. Validate the actual graph, runtime behavior, bindings/references, stable
   output, and requested visual/temporal qualities. Check errors at completion.
   Use one low-quality thumbnail when visual proof is required; ask before
   repeated images or streaming.
8. Report the usable outcome, exact scope, chosen architecture, validation
   evidence, rollback status, and any unavailable evidence or residual risk.

Do not call `td_brain_plan` merely because one keyword resembles a known
pattern. `/td-concept` is specifically for concept-shaped work.
