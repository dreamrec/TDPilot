# TDPilot Master Audit

Audit date: 2026-03-14

Repo reviewed:

- Local checkout of `dreamrec/TDPilot`
- Public repo: <https://github.com/dreamrec/TDPilot/tree/main>

Core verification performed:

- `uv run --extra dev pytest tests/ -q` -> `300 passed`
- `uv run python -m compileall src td_component tests`
- `uv run tdpilot doctor --json`
- live TouchDesigner connection checks against build `2025.32460`
- live exec probes for color pipeline, TDResources, and custom parameter behavior

## Executive Verdict

Short version:

- Yes, TDPilot is real.
- Yes, it works well enough to be useful right now.
- No, it is not fully mature or fully trustworthy across all 86 tools.
- The core is strong.
- The newest and most ambitious surfaces still need tighter validation.

If I had to summarize it in one sentence:

TDPilot is a serious TouchDesigner MCP control layer with real value for inspect-build-debug-reuse workflows, but it still behaves more like a strong advanced beta than a polished production platform.

## What It Actually Is

TDPilot is not just "AI for TouchDesigner."

It is really four systems bundled together:

1. A live control bridge between an MCP client and TouchDesigner.
2. A TouchDesigner-side HTTP and WebSocket component that exposes TD operations safely enough to be driven by an AI agent.
3. A lightweight local knowledge system with operator cards, palette cards, snippets, and release metadata.
4. A reusable technique memory system that can save, search, replay, rate, and promote learned subnet patterns.

That split matters, because people often imagine "memory" here as a giant autonomous brain. It is not that. It is a curated combination of:

- saved technique recipes
- saved user preferences
- a small local docs corpus
- the AI client's own reasoning over those pieces

## Is It Working Correctly?

### What is working well

These areas are real and materially useful:

- Basic TD inspection:
  `td_get_info`, `td_get_nodes`, `td_get_node_detail`, `td_get_params`, `td_get_errors`
- Basic graph editing:
  `td_create_node`, `td_connect_nodes`, `td_disconnect`, `td_set_params`, `td_set_content`
- Project safety workflow:
  snapshots, restore, instability checks, parameter bounds
- POP inspection:
  the POP-oriented inspection surface is genuinely better than pretending POPs are just SOPs
- server/runtime ergonomics:
  `doctor`, client config generation, npm wrapper, structured tool surface
- static knowledge lookup:
  operator docs, snippet lookup, palette lookup, recommendation helpers
- the general inspect -> edit -> verify workflow

These are the parts I would trust first in real work.

### What is partly working, but needs care

These areas are useful, but I would treat them as "supervised mode only":

- technique replay
- planning tools
- audit tools
- TD 2025 native inspection tools
- continuous visual monitoring / streaming
- optimization tools

Why:

- they are more indirect
- they depend on broader assumptions
- they can drift away from current TD APIs faster
- the test coverage around them is lighter than the core CRUD/inspection path

### What was rough (now fixed)

The following issues were identified during the original audit and have since been resolved:

- **Replay prerequisite check** — `td_memory_replay` now queries the actual target TD install via `/api/families` instead of the local knowledge corpus. Fixed.
- **appendCustomPage bug** — `td_component_standardize(fix=true)` no longer uses `[0]` indexing on `appendCustomPage()`. Uses the returned `Page` directly. Fixed.
- **Shallow audit** — `td_audit_project` now performs BFS recursive subtree traversal into child COMPs (max depth 10, cycle detection). Fixed.
- **CI fixture** — GitHub Actions release-gate fixture includes all required fields and passes with `--require-complete`. Fixed.
- **API docs drift** — `td_color_pipeline` docs updated to reflect current TD2025-style field names. Fixed.
- **Behavioral test coverage** — 28 new behavioral tests added for planning tools, TD2025 tools, and replay validation. Registration-only tests are no longer the sole protection layer.

Current honest answer to "is it working correctly?":

- The core works well and is well-tested.
- The newer surfaces now have behavioral test coverage and their documentation matches their implementation.

## The Parts With Real Value

If you use TDPilot correctly, the highest-value parts are not all 86 tools equally.

The best value comes from this stack:

1. Inspect the current patch quickly.
2. Ask the AI to propose a narrow change.
3. Let it build in small steps.
4. Force it to check errors and cooking.
5. Save successful patterns into memory.
6. Reuse those patterns later.

That loop can save serious time.

The strongest practical use cases are:

- bootstrapping repetitive patch structures
- refactoring and cleanup
- structured debugging
- turning one-off experiments into reusable subnet recipes
- helping a mediocre or rusty TD user move faster without hand-authoring every operator chain

## The Parts That Are More "Potential" Than "Core"

These are interesting, but not yet where I see the biggest return:

- full autonomous optimization
- broad planning surfaces
- very large always-on monitoring workflows
- trying to make it a complete replacement for real TD craft
- treating the local docs corpus as if it were a full authoritative copy of official documentation

They are directionally useful, but not the reason I would adopt the tool today.

## What TDPilot Is Not

It is not:

- a replacement for artistic judgement
- a replacement for understanding TouchDesigner families and cook behavior
- a one-shot "build me the whole show" machine
- a full self-growing knowledge graph of every tutorial on the internet
- a guarantee that every high-level feature is production-hard

## Maturity Assessment

My maturity rating:

- Core runtime/control layer: strong beta
- Day-to-day TD helper: good and already valuable
- Memory/reuse system: promising and useful if curated well
- Fully autonomous TD copilot: not there yet
- Production release discipline: decent locally, still uneven at the edges

## What I Would Use It For Tomorrow

If I were using it tomorrow on a real project, I would use it for:

- patch inspection and summarization
- node creation and wiring scaffolds
- parameter sweeps with supervision
- error hunting
- saving and replaying small to medium reusable subnet patterns
- building a studio memory of "known-good" structures
- forcing a more disciplined workflow on experimental TD sessions

I would not hand it:

- the entire show architecture in one prompt
- blind optimization without snapshots
- unsupervised parameter mutation in a fragile live project
- a giant legacy patch and expect perfect understanding in one pass

## What I Would Change First

If I were product owner for one week, I would focus on:

1. Tighten trust.
   Fix mismatches between docs, tests, and runtime claims.

2. Reduce surface anxiety.
   Promote a "core 20 tools" workflow and de-emphasize the long tail for normal users.

3. Make memory the center.
   The real long-term value is not one-off tool count. It is reusable studio knowledge.

4. Add behavioral tests for new features.
   Registration tests are not enough.

5. Improve the "target install vs local corpus" distinction.
   That matters a lot for replay, compatibility, and trust.

## Final Judgement

TDPilot is worth using if your goal is:

- faster TD iteration
- more reliable AI-assisted patching
- building a reusable library of subnet techniques
- giving an AI agent real TD inspection and mutation tools

TDPilot is not worth using if your expectation is:

- magic autopilot
- fully trustworthy autonomy across all tools
- zero need for human curation

My honest conclusion:

This repo has real substance. It is not fake, not fluff, and not just a wrapper around a few Python scripts. But the product becomes much better when you stop thinking of it as "86 tools" and start thinking of it as "a disciplined AI-assisted TD workflow with reusable memory."

## Recommended External References

Official TouchDesigner docs:

- Project class: <https://docs.derivative.ca/Project_Class>
- COMP class: <https://docs.derivative.ca/COMP_Class>
- Page class: <https://docs.derivative.ca/Page_Class>
- Web Server DAT: <https://docs.derivative.ca/Web_Server_DAT>
- WebSocket DAT: <https://docs.derivative.ca/WebSocket_DAT>
- Palette: <https://docs.derivative.ca/Palette>
- OP Snippets: <https://docs.derivative.ca/OP_Snippets>
- TDResources: <https://docs.derivative.ca/TDResources>

Learning resources:

- Learn TouchDesigner: <https://docs.derivative.ca/Learn_TouchDesigner>
- Tutorials index: <https://docs.derivative.ca/Tutorials>
- OP Snippets: <https://docs.derivative.ca/OP_Snippets>

MCP background:

- MCP FAQ: <https://modelcontextprotocol.io/faqs>
