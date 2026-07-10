---
description: Build a grounded audio-reactive visual with a real source, explicit binding, and visual proof
---

Build an audio-reactive TouchDesigner visual whose live audio signal is
explicitly bound to a visible TOP parameter. Finish with one low-quality
screenshot of the verified stable output. Do not use a legacy macro template.

1. **Connect and locate.** Call `td_get_info` and `td_get_focus`. On connection
   or authentication failure, follow `td_sync_diagnose` and stop. Resolve the
   target root and intended output from the user's request or focused project.
2. **Find a real audio source.** If the user supplied a file or microphone,
   honor it. Otherwise inspect the target and nearby project scope for existing
   audio-file/device CHOPs and sample likely outputs with `td_chop_data`.
   A cooking CHOP with zero signal is not an active source. If no active source
   or user choice exists, ask the user for an audio file or microphone route and
   do not build a silent placeholder.
3. **Define the complete intent.** Include source, analysis, normalization,
   bounded modulation, a visible TOP chain, a stable output, one explicit
   CHOP-to-parameter binding, signal/readback checks, nonblack content, and
   temporal response. Default the supported binding target to a grounded numeric
   `levelTOP` parameter; do not target MAT, POP, camera, or arbitrary parameters
   unless the current compiler and grounding explicitly support them.
4. **Ground the concept.** Call `td_brain_ground` directly with the complete
   intent, source constraint, target root, desired output,
   `include_memory=true`, and `trace_level="summary"`. Read the `grounding_id`,
   authoring contract, availability, parameter semantics, and recalled evidence.
5. **Author and review.** Draft the smallest complete CHOP + TOP graph. The
   control edge must carry one explicit
   `chop_reference_expression` binding with a safe source channel and a
   registry-backed numeric target parameter. Remove any conflicting static
   value. Call `td_brain_propose` with the same `grounding_id`,
   `draft_schema_version="2"`, and `detail_level="summary"`; repair
   machine-readable rejections and creatively important stripped parameters.
6. **Execute transactionally.** Require complete server-recomputed intent
   coverage and zero unresolved semantic edges, then execute the accepted
   `plan_id` with rollback on failure.
7. **Prove reactivity.** Validate the transaction result, final errors, cook
   health, nonzero source/analysis signal, installed expression or parameter
   readback, nonblack TOP content, and temporal visual change. Use metadata-only
   dynamics for time comparison instead of sending two screenshots. Apply at
   most one assertion-specific repair; otherwise roll back and report the
   blocker.
8. **Show it.** Take one screenshot of the stable output at `quality=0.25`.
   Explain audio → analysis → normalized control → explicit binding → visual,
   name two safe live controls, and state the rollback result and any unverified
   evidence.

Never report an audio-reactive success when the source is silent, the binding is
missing, or visual change was not measured.
