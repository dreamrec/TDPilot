---
description: Build a first moving TouchDesigner visual through the grounded concept route and prove it works
---

Build one polished, moving feedback visual in the user's TouchDesigner project,
transactionally and end to end. Finish with one low-quality screenshot of the
verified stable TOP. Do not use a legacy macro template.

1. **Connect and locate.** Call `td_get_info` and `td_get_focus`. On connection
   or authentication failure, run `td_sync_diagnose`, report the concrete fix,
   and stop. Use the focused project root when clear; otherwise use
   `/project1`.
2. **Define the complete intent.** The result must have a visible seeded TOP
   source, bounded recursive feedback/decay, deliberate color, continuous
   non-strobing motion, a stable named TOP output, and validation for nonblack
   content plus temporal change. Keep it compact and tasteful.
3. **Ground the concept.** Call `td_brain_ground` directly with the complete
   intent, target root, desired output, `include_memory=true`, and
   `trace_level="summary"`. Read the `grounding_id`, candidate cards,
   availability, parameter semantics, recalled evidence, and current authoring
   contract.
4. **Author and review.** Draft the smallest graph that covers every required
   facet. Use a real source feeding the feedback/composite chain; do not create
   an unseeded loop. Represent motion with a grounded, registry-valid technique,
   not decorative explanation. Call `td_brain_propose` with the same
   `grounding_id`, `draft_schema_version="2"`, and
   `detail_level="summary"`. Fix proposal rejections or essential stripped
   parameters and re-propose.
5. **Execute transactionally.** Require server-recomputed complete intent
   coverage and no unresolved semantic edges. Execute the accepted `plan_id`
   with rollback on failure. Never accept a partial or legacy macro as the
   finished visual.
6. **Prove the result.** Check the transaction/rollback result, final errors,
   stable output path, and cook health. Analyze the TOP for nonblack/nonuniform
   content and use metadata-only temporal analysis to prove motion. If a known
   assertion fails, make at most one bounded repair and revalidate; otherwise
   roll back and report the blocker.
7. **Show it.** Take one screenshot of the stable output at low quality
   (`quality=0.25`) and include it in the response. Name the created scope,
   explain the signal loop in one short paragraph, give two safe parameters to
   explore, and state the rollback result.

Never claim success from zero TD errors, a black frame, or a static image.
Natural next steps are `/td-audio-reactive` and `/td-explain-patch`.
