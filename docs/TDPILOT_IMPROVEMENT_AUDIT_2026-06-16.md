# TDPilot Improvement Audit - 2026-06-16

> Archive note: this is a dated audit snapshot. Tool counts and verification
> output in this file reflect the repository state on 2026-06-16; use
> `README.md`, `docs/API_REFERENCE.md`, and `mcp/manifest.json` for the current
> release surface.

This audit combines local repo inspection with current public guidance from OpenAI,
Anthropic, and the MCP specification. The goal is not to chase parity. The goal is
to deepen TDPilot's moat: local-first TouchDesigner rigor, auditability, recovery,
production safety, and creative iteration speed.

## Sources Reviewed

- Local repo: `README.md`, `docs/API_REFERENCE.md`, `docs/MCP_1_1_SURFACE.md`,
  `docs/SECURITY.md`, `docs/BRAINS.md`, `src/td_mcp/**`, `td_component/**`,
  `.claude-plugin/**`, `.mcp.json`, `mcp/profiles/**`, tests, and the untracked
  `plugins/tdpilot/**` Codex plugin scaffold.
- OpenAI Codex MCP docs: https://developers.openai.com/codex/mcp
- OpenAI Codex AGENTS.md docs: https://developers.openai.com/codex/guides/agents-md
- OpenAI Codex Skills docs: https://developers.openai.com/codex/skills
- OpenAI Codex Subagents docs: https://developers.openai.com/codex/subagents
- OpenAI Codex changelog: https://developers.openai.com/codex/changelog
- OpenAI Responses API MCP/connectors docs:
  https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- OpenAI Agents SDK docs: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents observability docs:
  https://developers.openai.com/api/docs/guides/agents/integrations-observability
- OpenAI agent evaluation docs:
  https://developers.openai.com/api/docs/guides/agent-evals
- OpenAI Apps SDK MCP/UI/tool docs:
  https://developers.openai.com/apps-sdk/concepts/mcp-server,
  https://developers.openai.com/apps-sdk/plan/tools,
  https://developers.openai.com/apps-sdk/build/chatgpt-ui
- Anthropic Claude Code MCP docs: https://code.claude.com/docs/en/mcp
- Anthropic Claude Code skills, plugins, subagents, and hooks docs:
  https://code.claude.com/docs/en/skills,
  https://code.claude.com/docs/en/plugins-reference,
  https://code.claude.com/docs/en/sub-agents,
  https://code.claude.com/docs/en/hooks-guide
- MCP 2025-11-25 specification:
  https://modelcontextprotocol.io/specification/2025-11-25

## v2.0.0 Implementation Status

The recommendations below have been implemented into the v2 branch as a
correctness-first brain release:

- Public surface is now 110 tools, 9 resource templates, and 4 static resources.
- Added `td_brain_plan`, `td_brain_execute`, `td_transaction_apply`, and
  `td_cockpit_render`.
- Added MCP prompts, cached live resources, structured brain models,
  transaction defaults, validator profiles, JSONL traces, golden eval fixtures,
  brain skills, Codex/Claude brain agents, deterministic hooks, and plugin
  surface audits.
- Added `scripts/audit_brain_atlas.py`; the structured operator atlas covers
  all 24 operators required by the 8 brain concept profiles.
- The open MCP core remains local-first and has no hosted LLM dependency.

## Pre-Implementation Local Baseline

Verified locally:

- `uv run python scripts/smoke_mcp_registry.py` passed with 106 tools,
  1 static resource, 6 resource templates, and no missing required tools.
- `uv run tdpilot doctor --skip-td-check --json` passed with one expected warning:
  TD port `127.0.0.1:9981` was not reachable because the live TD check was skipped.
- The repo has strong release gates: tool count contracts, schema snapshots,
  tox freshness checks, auth checks, no-personal-path checks, and broad tests.

Strong existing surfaces:

- 106 MCP tools covering graph reads/writes, params, DAT content, screenshots,
  CHOP/SOP/POP inspection, errors, cooking, lifecycle, snapshots, events,
  streaming, optimizer, dynamics, macros, knowledge, technique memory,
  hints, notes, focus, locations, activity log, and self-update.
- Production discipline already exists in `tdpilot-core` and
  `tdpilot-production`: inspect first, undo blocks, snapshots, error checks,
  token-efficient visual checks, technique memory, and rollback awareness.
- Security posture is unusually explicit for a creative tooling MCP:
  duplicated client/server exec scanning, auth bootstrap, restricted/standard/full
  exec modes, CORS/Sec-Fetch handling, and clear threat-model documentation.

Main local gaps:

- No MCP prompt decorators were found. TDPilot has Claude slash command files,
  but it does not expose portable MCP prompts that Claude Code, VS Code, and
  other clients can discover as commands.
- MCP resources are currently static placeholders in
  `src/td_mcp/registry/resources.py`; they mostly tell clients to call tools.
  This underuses Claude Code's resource `@` mentions and the MCP resource model.
- No clear use of `structuredContent`, `outputSchema`, MCP tool annotations,
  `_meta` discovery hints, `anthropic/maxResultSizeChars`, or
  `anthropic/alwaysLoad` was found.
- `td_tool_batch` saves roundtrips but is explicitly sequential and
  non-transactional. `td_patch_apply` uses undo blocks but does not auto-rollback
  on failure; it returns a rollback hint.
- The untracked `plugins/tdpilot/` directory contains a Codex plugin scaffold.
  That is valuable, but currently looks outside the tracked release surface.
- `docs/MCP_1_1_SURFACE.md` still lists several unsolved gaps that are still
  directionally valid: safer batched transactions, severity classification,
  recursive inspection consistency, and richer visual intent.

## Highest-Impact Recommendations

### 1. Add a True Transaction Layer

Build a first-class `td_transaction` or extend typed patch sessions with:

- `preflight=true`
- `snapshot_before=true`
- `rollback_on_failure=true`
- `rollback_on_validation_failure=true`
- `validate={errors,cooking,optional_frames}`
- `dry_run=true`
- `dependency graph` for operation ordering
- structured result with `before_snapshot_id`, `after_snapshot_id`,
  `failed_op`, `rollback_performed`, and `validation_summary`

Why:

- MCP tools are model-controlled and powerful; the MCP spec stresses human
  control, confirmation, logging, and caution for arbitrary tool execution.
- TDPilot's own docs name "No atomic multi-tool transaction layer" as a gap.
- `td_tool_batch` is useful for read sweeps, but it is not a safety primitive.

Implementation shape:

- Reuse `PatchPlan`, `PatchOperation`, `SnapshotManager`, `UndoBlockSentinel`,
  and `td_project_lifecycle`.
- Keep `td_tool_batch` read-biased. Avoid making it a hidden write transaction.
- Prefer typed patch operations over arbitrary `td_exec_python`.

Priority: P0.

### 2. Optimize Tool Metadata for Modern Tool Search

Modern Codex and Claude both lean into deferred tool discovery. OpenAI documents
tool search and remote MCP as ways to load only relevant tools. Claude Code
now defers MCP tools by default and uses server instructions plus tool metadata
to decide which tools to search.

TDPilot had 106 tools at audit time. The v2 implementation raises the public
surface to 110 tools and makes metadata ergonomics part of the release gates.

Add:

- Tool descriptions that start with "Use this when..."
- Short titles where supported.
- `outputSchema` for high-value structured tools.
- MCP annotations such as read-only/destructive/open-world hints where the
  SDK supports them.
- `_meta["anthropic/maxResultSizeChars"]` for intentionally large read tools
  like schema/docs/tree/brain outputs.
- `_meta["anthropic/alwaysLoad"]` only for a tiny core set, if needed:
  `td_get_info`, `td_get_focus`, `td_get_state_vector`, `td_get_errors`,
  `td_tool_batch`.
- A concise first 512 characters of `SERVER_INSTRUCTIONS` focused on when to
  search/use TDPilot tools.

Why:

- OpenAI Apps SDK guidance says good tool design makes discovery accurate and
  outputs predictable.
- Claude Code specifically says server instructions become more important with
  Tool Search and are truncated; critical details should be near the start.

Priority: P0.

### 3. Expose MCP Prompts as Portable Commands

Add MCP prompts for the workflows users actually run:

- `td_health_check`
- `td_snapshot_before_edit`
- `td_production_patch`
- `td_visual_verify`
- `td_debug_errors`
- `td_learn_technique`
- `td_replay_technique`
- `td_optimize_visual_goal`
- `td_release_check`
- `td_recover_from_instability`

Why:

- MCP prompts are user-controlled workflow templates. Claude Code exposes MCP
  prompts as slash commands.
- TDPilot already ships Claude commands `/td-check` and `/td-snapshot`, but
  MCP prompts would make these workflows portable across MCP clients.

Implementation shape:

- Keep existing Claude commands for compatibility.
- Add a prompt registry module parallel to `registry/resources.py`.
- Generate prompt docs from the same source to prevent drift.

Priority: P1.

### 4. Make Resources Dynamic and Useful

Current resources are static redirect hints. Upgrade resources into actual
context objects that users and models can reference:

- `td://project/state` -> compact state vector.
- `td://activity/recent` -> recent activity log.
- `td://node/{path}` -> detail, params summary, errors, connections.
- `td://errors/{path}` -> current classified issues.
- `td://cook/{path}` -> cook stats.
- `td://snapshot/{id}` -> snapshot metadata and diff link.
- `td://top/{path}/analysis` -> low-token frame analysis.
- `td://docs/operator/{op_type}` -> official operator card or docsbrain result.
- `td://memory/technique/{id}` -> technique recipe summary.

Why:

- MCP resources are meant to provide context and data. Claude Code exposes
  resources through `@server:uri` mentions.
- This would reduce repeated tool calls and make TDPilot feel native in clients
  that support resources.

Implementation caution:

- FastMCP context injection limitations caused the current placeholder design.
  If contextful resources remain hard, expose a small local resource cache that
  tools populate and resources read without live TD context.

Priority: P1.

### 5. Add Agent Trace and Eval Infrastructure

TDPilot v1.6.16 added `_read_journal` and `td_get_activity_log`. Turn that into
a trace/eval loop:

- Add `td_export_trace(format=jsonl|otel)` for session-level tool traces.
- Include intent, tool, args summary, result summary, duration, ok/error,
  before/after snapshot IDs, validation report, and rollback outcome.
- Add `td_replay_trace(dry_run=true)` to detect behavioral drift.
- Add `tests/evals/` golden prompts for common TD workflows:
  feedback loop, audio reactive, POP inspect, safe parameter edit, recover
  from warning, self-update, docs lookup.
- Add graders for tool choice, safety steps, snapshot usage, validation usage,
  and final state quality.

Why:

- OpenAI Agents SDK tracing captures model calls, tool calls, handoffs,
  guardrails, and custom spans. OpenAI's agent eval guidance recommends moving
  from traces to repeatable datasets/eval runs.
- TDPilot's differentiator is auditability. This compounds directly with it.

Priority: P1.

### 6. Formalize the Codex Plugin Surface

There is already an untracked `plugins/tdpilot/` with `.codex-plugin/plugin.json`
and copied skills. Decide one of two paths:

1. Track it as a first-class distributable and add release gates.
2. Treat it as generated output and add a deterministic build script plus
   freshness/hash tests.

Also add:

- `mcp/profiles/codex.toml` or a documented `codex mcp add` flow.
- `AGENTS.md` tuned for this repository, pointing Codex to the TDPilot skills,
  release gates, and verification commands.
- Codex-specific skill descriptions that front-load trigger words, because
  Codex skill matching depends heavily on `description` text.

Why:

- Codex supports MCP servers in the CLI and IDE extension, reads server
  instructions, supports plugins and skills, and uses `AGENTS.md` for
  repo-specific instructions.
- Codex now supports subagents and GPT-5.5/GPT-5.4 workflows, making a
  Codex-native TDPilot plugin valuable instead of merely compatible.

Priority: P1.

### 7. Use Claude Plugin Agents and Hooks

The Claude plugin currently ships skills, commands, and MCP config. Claude Code
plugins can also ship agents and hooks.

Add plugin agents:

- `td-auditor`: read-only project health, docs, errors, cook stats.
- `td-production-planner`: plans high-risk edits, no writes.
- `td-visual-critic`: reviews screenshots/analysis and suggests bounded edits.
- `td-release-auditor`: checks manifests, versions, tox freshness, tests.

Add plugin hooks:

- `PreToolUse` hook for dangerous MCP calls (`td_exec_python`, delete, restore,
  self-update, lifecycle load) to require or summarize confirmation.
- `PostToolUse` hook that logs write operations and suggests validation when
  a write occurs without a later `td_get_errors`.
- Optional `UserPromptSubmit` hook to inject compact live TD status when the
  user asks a TouchDesigner question.

Why:

- Claude Code plugin docs now support skills, agents, hooks, MCP servers, LSP
  servers, and monitors. Hooks can run deterministic, prompt, MCP-tool, or
  agent checks around tool use.

Priority: P1.

### 8. Add an Optional MCP Apps / ChatGPT UI Cockpit

Do not build a cloud service. Build a local/open UI surface that can run in
MCP Apps-compatible hosts:

- Project health dashboard.
- Activity log timeline.
- Snapshot/diff browser.
- Current TOP preview and low-token analysis.
- Safe transaction preview and approval pane.
- Technique memory browser.

Why:

- Apps SDK and MCP Apps standardize iframe UI components using `ui/*` bridge
  methods and `_meta.ui.resourceUri`.
- TDPilot already mirrors agent activity into an in-TD Table DAT; an external
  MCP Apps cockpit would make the same rigor visible in ChatGPT-compatible
  clients without replacing TouchDesigner.

Keep this optional and local-first so it does not violate the open-core rule.

Priority: P2.

### 9. Upgrade the Knowledge/Brain System with Local Semantic Search

`docs/BRAINS.md` already names vector search as a future layer. Make it real:

- Add optional local embeddings index for docsbrain/brains.
- Keep SQLite FTS5 as the fallback.
- Use semantic search for user intent queries, not exact operator names.
- Add provenance and source freshness in every result.
- Add eval cases for retrieval quality against known TD questions.

Why:

- TDPilot's knowledge corpus is already a differentiator. Semantic retrieval
  would reduce "right docs but wrong words" failures.
- This can remain open core if the default path uses local embeddings or lets
  users provide their own key without requiring hosted TDPilot infrastructure.

Priority: P2.

### 10. Improve Warning Severity and Error Taxonomy

Add normalized issue severity:

- `blocking_error`
- `runtime_error`
- `static_warning`
- `benign_cycle_warning`
- `inactive_branch_warning`
- `performance_warning`
- `security_warning`

Apply it in:

- `td_get_errors`
- `td_detect_instability`
- `td_patch_validate`
- `td_audit_project`
- hint injection
- final validation summaries

Why:

- TouchDesigner warnings are not equal. The feedback TOP static cycle warning
  is already documented as often non-fatal.
- Agents need to know whether to rollback, screenshot, ignore, or ask.

Priority: P2.

### 11. Add Policy Profiles

Expose user-selectable modes beyond `TD_MCP_EXEC_MODE`:

- `read_only`
- `safe_write`
- `production`
- `performance_debug`
- `creative_explore`
- `full_dev`

Each profile controls:

- allowed tools
- destructive tool confirmation
- default snapshot behavior
- visual capture policy
- max output sizes
- exec mode
- rollback behavior

Why:

- `restricted` is a Python sandbox, not a graph mutation policy. The security
  doc explains this clearly, but clients need a mechanical policy layer.
- Claude and Codex approval systems can use tool policy hints, but TDPilot
  should own its own local safety defaults too.

Priority: P2.

### 12. Make Large Outputs Client-Friendly

Add consistent pagination/resource-link behavior for large data:

- Always include `limit`, `offset`, `has_more`, `next_cursor` where output can
  grow.
- Return resource links for large snapshots, docs, traces, and frame payloads.
- Use `structuredContent` plus compact text summaries where supported.
- Add Anthropic max-result metadata for known large tools.

Why:

- Claude Code persists oversized MCP outputs to disk unless annotated; OpenAI
  remote MCP imports large tool surfaces with token/latency costs.
- TDPilot's broad surface will age better if large data moves through resource
  links and cursors instead of giant text blobs.

Priority: P2.

## Original 4-Release Roadmap

The staged roadmap below is preserved as the original recommendation. The v2
implementation intentionally pulled the correctness-first pieces forward into a
single major release because the brain, transaction layer, atlas coverage,
client packaging, and cockpit are now interdependent public surfaces.

### v1.7.0 - Client Discovery and Safety Metadata

- Rewrite the first 512 characters of server instructions.
- Add annotations/meta/output schemas for high-value tools.
- Add MCP prompts for core workflows.
- Add `mcp/profiles/codex.toml` and decide how to ship the Codex plugin.
- Add registry tests for prompt count, annotation coverage, and output schema
  coverage on selected tools.

### v1.8.0 - Transaction and Validation Layer

- Ship `td_transaction` or transaction-capable typed patch apply.
- Add rollback-on-failure and rollback-on-validation-failure.
- Add severity taxonomy in `td_get_errors` and `td_patch_validate`.
- Add golden eval fixtures for safe edit workflows.

### v1.9.0 - Resources, Traces, and Evals

- Replace static resource placeholders with useful dynamic/cache-backed
  resources.
- Add trace export, trace replay dry-run, and eval dataset scaffolding.
- Add Claude plugin agents/hooks for audit, planning, validation, and release.

### v2.0.0 - Optional UI and Semantic Knowledge

- Add optional MCP Apps cockpit.
- Add local semantic brain search.
- Add richer visual intent memory and temporal/composition metrics.

## What Not to Do

- Do not add hosted account state, paid cloud sync, or TDPilot-owned keys to
  the open MCP core.
- Do not add generic AI adapters just because competitors have them. The agent
  client is already the adapter.
- Do not expand the tool count for every small workflow. Prefer prompts,
  metadata, new params, and existing dispatcher actions where possible.
- Do not make screenshots the default verification path. Keep low-token
  analysis first and user-approved image payloads for targeted checks.

## Bottom Line

TDPilot already has the hard part: a serious TD-native control plane with
snapshots, safety, memory, knowledge, diagnostics, and release discipline.
The next leap is not "more tools." It is better orchestration around the tools:
portable prompts, dynamic resources, transaction semantics, client-aware
metadata, trace/eval loops, and first-class Codex/Claude packaging.

Those improvements compound with TDPilot's current moat instead of diluting it.
