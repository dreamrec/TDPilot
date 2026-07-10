# TDPilot Context

> Shared language and stable architectural decisions for TDPilot — the
> TouchDesigner MCP plugin (114 tools, plus skills, commands, and a `.tox`).
> Consumed by Claude Code sessions before any work on this repo.
>
> A companion `CONTEXT-local.md` (gitignored) captures session-specific
> discoveries that aren't appropriate for public distribution.

## Language

Use these terms exactly. Consistent vocabulary keeps tool names, file
names, and conversation aligned.

**MCP server** — Python FastMCP at `src/td_mcp/server.py`, exposes `td_*`
tools. Runs as `npx tdpilot` for end users, or `uv run python -m td_mcp`
for dev. _Avoid_: backend, daemon, service.

**TD component (`.tox`)** — Binary TouchDesigner container at
`td_component/tdpilot.tox`. Built from the four source files in
`_TOX_SOURCE_FILES` of `build_export_mcp_tox.py`. Rebuildable **only**
from inside a running TD session. _Avoid_: bundle, blob, archive.

**Plugin (`.plugin`)** — Distributable ZIP for Claude Code's plugin
marketplace. Built by `scripts/build_plugin_zip.py`. Contains `skills/`,
`commands/`, `.mcp.json`, `tdpilot.tox`, `src/`, `pyproject.toml`,
`uv.lock`. _Avoid_: package (overloaded with npm/pip), bundle.

**Skill** — Per-task instructions at `skills/<name>/SKILL.md`. Loaded
contextually by Claude. Distinct from a **tool** (capability) and a
**command** (slash entry under `commands/`). _Avoid_: prompt, agent.

**Tool** — A `@mcp.tool()`-decorated function registered from
`src/td_mcp/registry/`,
callable as `td_<name>` from the MCP client. Tool count is enforced by
`EXPECTED_MIN_TOOL_COUNT` in `src/td_mcp/release_gates.py` — the **single
source of truth**. _Avoid_: function (too generic), endpoint, action.

**Snapshot** — A `.toe` save captured by `td_snapshot_scene` for
rollback. Distinct from a **git tag** (release-level) and a `.tox`
(component-level binary). Listed via `td_list_snapshots`, restored via
`td_restore_snapshot`, diffed via `td_diff_snapshots`. _Avoid_: backup
(implies disaster-recovery, not surgical rollback).

**Derived artifact** — A file that depends on other files but is NOT
auto-regenerated: `td_component/tdpilot.tox` (depends on the nine source files
listed by `td_component/build_tdpilot_tox.py`), `tdpilot.plugin` ZIP (depends
on skills + .tox + manifests), the
generated API reference, and public package mirrors. CI gates catch drift; the
artifacts themselves do not refresh on their own. _Avoid_: build output
(misleading — implies an automatic build target).

**Version cascade** — The 8 places a release version lives:
`pyproject.toml`, `src/td_mcp/__init__.py`, `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `npm/package.json`, `mcp/manifest.json`,
plus the `.tox` API_VERSION in `td_component/mcp_webserver_callbacks.py`
and the GitHub repo description. Enforced by `scripts/check_versions.py`.
_Avoid_: bump (it's a procedure, not a noun for the location set).

**Layer** — Where a TD UI bug actually lives, distinct from where the
symptom appears. The named layers (from the v1.6.3–v1.6.8 postmortem):
panel viewport / state cache / renderer / status_text / DAT wrapper /
restricted-exec wrapper / `.tox` payload / build script / distribution
manifest. Most TD bugs are 2–3 layers below the symptom. _Avoid_: spot,
location.

**Probe** — A non-mutating read via `td_get_nodes`, `td_exec_python`
reading a `.par.<name>`, or `td_screenshot`, used to determine the live
state of a node before forming a hypothesis. _Avoid_: check (too vague),
inspect (overloaded with `td_pop_inspect`).

**Recovery hint** — A structured suggestion automatically attached to a
tool's error envelope when its message matches one of the patterns in the
`error_recovery` hint pack. Each hint carries `id`, `priority`, `rule`,
and `next_tools`. The agent reads them in lieu of retrying the same call
blindly. Backport from deepseek-v4 `tdpilot_api_recovery.py`, integrated
into the existing hints system. _Avoid_: error annotation (too generic),
hint (overloaded with the existing topic-pack hints).

**Tool batch** — A single `td_tool_batch` call that dispatches up to 8
sub-calls sequentially in one model roundtrip. Per-call failures don't
abort siblings; each sub-result carries `ok` / `result` / `error` /
`elapsed_ms`. Backport from deepseek-v4. _Avoid_: parallel call (it's
sequential — the win is roundtrip latency, not concurrency), bulk call.

## Relationships

- A **session** loads a **skill** at start, calls **tools** during work,
  optionally captures **snapshots** before destructive operations, and
  persists **memory** at end.
- A **release** = git tag + version-cascade updates + `.tox` rebuild inside TD
  + plugin ZIP/MCPB rebuild + six-report release gate green + GitHub Release
  + npm publish.
- A **bug report** describing a UI/visual symptom in TD almost always
  has its actual cause 2–3 **layers** below the symptom. **Probe before
  hypothesizing** (see ADR-001).
- A **memory entry** under `~/.claude/projects/<this-project>/memory/`
  is loaded into every session; a **CONTEXT entry** (this file) is
  loaded as a public-safe glossary. Local-only details live in
  `CONTEXT-local.md` (gitignored).

## Flagged ambiguities

- "panel" can mean: a TD panelCOMP (UI primitive), the rendered panel
  area visible at runtime, or the TDPilot status panel inside
  `/project1/tdpilot`. Disambiguate with: "panelCOMP", "panel render",
  or "TDPilot status panel".
- ".tox" can mean: the file at `td_component/tdpilot.tox` (specific) or
  any TD component file (generic). Default reading is **specific** in
  this repo.
- "tool" without qualifier means an `@mcp.tool()` function (capability).
  TouchDesigner's own "tool" (rare) is always qualified as
  "TD-built-in tool".

---

## Architectural decision records

These are stable decisions. Don't relitigate without a strong new
reason — and if you do, archive the existing ADR rather than deleting
it.

### ADR-001 — Probe live state before forming any hypothesis

**Status:** Adopted 2026-05-03 after the v1.6.3 → v1.6.8 panel-bug saga.

**Context.** Five releases shipped fixes at the wrong layer because
hypotheses formed before probing the actual node state. Each release
was internally consistent at the layer it touched, but the bug lived
2–3 layers below. Cost: six releases on one bug, ~4 weeks elapsed.

**Decision.** For any UI / visual / rendering bug in TD, Phase 1 of
debugging is mandatory: `td_get_nodes(comp_path)` to enumerate live
children, then `td_exec_python` reading the specific `.par.<name>` of
the suspected node. No hypothesis is allowed before that probe runs.
The `superpowers:systematic-debugging` skill enforces this discipline;
the `diagnose` skill (under `~/.claude/skills/`) lists the canonical
TD probes.

**Consequences.** Adds 30 seconds of probing per bug. Saves 5 wrong
releases per occurrence. Reframes "I think the bug is in X" as a
prediction to be tested, not a conclusion to ship a fix from.

### ADR-002 — Eight version fields, intentionally not consolidated

**Status:** Adopted (constraint, not preference).

**Context.** Each of the 8 version fields lives on a distribution
surface that expects its own metadata format: `pyproject.toml` is read
by `uv`/`pip`, `npm/package.json` by npm, `marketplace.json` by Claude
Code's plugin panel, `mcp/manifest.json` by the generic MCP registry,
and the `.tox` API_VERSION is baked into the TD binary. Consolidating
into a single Python constant would still require generators for every
surface — and the marketplaces parse the manifests directly, not via
us.

**Decision.** Keep the 8 fields as physical sources of truth on their
respective surfaces. Enforce sync via `scripts/check_versions.py` in
CI. Document the full bump list in `CLAUDE.md` so every release-prep
session has the canonical list.

**Consequences.** Every release requires updating 8 files. Drift is
caught by the CI gate before push reaches `main`. The `Update` button
in Claude Code's plugin panel depends on `marketplace.json.plugins[].version`
being current — that's the field that breaks user-visible update
flow when stale.

### ADR-003 — Snapshot before any destructive scene change

**Status:** Adopted.

**Context.** TD has bounded Cmd+Z. A `.tox`-side error can leave the
network in an unrecoverable state. Sessions can lose hours of work to
a single mis-aimed `td_delete_node` or `td_set_content`.

**Decision.** Call `td_snapshot_scene` immediately before any of:
- `td_delete_node`
- `td_set_content` on a non-empty container
- `td_emergency_stabilize`
- any sequence of >3 mutating operations on the same scope

Snapshots are listed via `td_list_snapshots`, restored via
`td_restore_snapshot`, and diffed via `td_diff_snapshots` to bisect
regressions.

**Consequences.** Adds a snapshot file per risky operation. Disk cost
negligible. Recovers entire sessions in cases where the alternative is
re-doing hours of work.

### ADR-004 — Wrapper-DAT pattern for restricted-exec construction

**Status:** Adopted.

**Context.** `td_exec_python` runs in TD's restricted-exec sandbox,
which blocks multi-step network construction operations like
`comp.create(...)` chains and certain `op.create()` patterns.

**Decision.** When `td_exec_python` is blocked, write the construction
Python to a `textDAT` and trigger it via `executeDAT.run()`. The DAT
runs in TD's local Python which has no restricted-exec. Delete the DAT
after use to keep the network clean.

**Consequences.** Multi-step construction works. Adds one transient
artifact per construction sequence. Requires the user to be aware
that wrapper-DATs sometimes survive an interrupted session and should
be cleaned up.

### ADR-005 — Two-tier documentation: public CONTEXT.md, local intricacies

**Status:** Adopted 2026-05-03 per user binding rule.

**Context.** `docs/TD_INTRICACIES_AND_PATTERNS.md` accumulates session-
specific bug postmortems, personal-path examples, and TD internal hacks.
This material is genuinely useful for dev sessions on this repo but
inappropriate to ship to the thousands of plugin users.

**Decision.** Two-tier:
- **Public.** This `CONTEXT.md` (shipped) holds stable vocabulary, ADRs,
  and relationships.
- **Local.** `docs/TD_INTRICACIES_AND_PATTERNS.md` and `CONTEXT-local.md`
  (both gitignored) hold session-specific war stories, personal-path
  examples, and per-session memory cross-links.

New discoveries about TD intricacies append to the **local** doc.
Promotion to public ADR happens only when the discovery has stabilized
into a permanent decision.

**Consequences.** Plugin users get a clean glossary. Dev sessions on this
clone get the full picture. The promotion gate (local → public) is the
single place where personal context can leak into distribution and needs
careful review.

---

## Live pointers

- **Tool reference.** `docs/API_REFERENCE.md` (auto-generatable from
  `@mcp.tool()` decorators), `docs/USER_GUIDE.md` (curated).
- **Version source of truth.** `EXPECTED_MIN_TOOL_COUNT` in
  `src/td_mcp/release_gates.py` for tools; `pyproject.toml` for the
  version-cascade head.
- **CI status.** `gh run list --limit 5 --branch main`.
- **Active branches & tags.** `git tag --list 'v*' | sort -V | tail -5`.
- **Session memory index.** `~/.claude/projects/-Users-visansilviugeorge-Desktop-DREAM-AI-TDPilot-TDPilot-main/memory/MEMORY.md`.

---

## How to update this document

Add to **Language** when a new term enters the vocabulary and is being
used inconsistently. Add to **Relationships** when a new structural
connection becomes load-bearing. Add an **ADR** when a decision is
likely to be re-litigated and the rationale is non-obvious from code.

Don't add session-specific findings — those go in `CONTEXT-local.md` or
`docs/TD_INTRICACIES_AND_PATTERNS.md`.

### ADR-006 — Recovery hints integrate into the existing hints system

**Status:** Adopted 2026-05-12 with v1.6.11.

**Context.** Deepseek-v4's `tdpilot_api_recovery.py` provides a flat
table of `(error_regex, hint_string)` pairs that attach to any error
result. A naive backport would have created a parallel module that
re-implements its own priorities, source citations, and registry.

**Decision.** Recovery hints are authored as a YAML pack under
`src/td_mcp/hints/packs/topics/error_recovery.yaml`, gated behind a new
`error_recovery` response surface registered in `ALLOWED_SURFACES`. The
existing `HintRegistry.find()` API gained regex-mode `error_match`
matching (substring fallback on `re.error`); the existing
`format_tool_error` helper calls it on every envelope and attaches
matching hints to `error.recovery_hints`.

**Consequences.** Recovery hints inherit priority, source citation,
next-tools, and the registry plumbing for free. New recovery patterns
are added by editing the YAML pack — no Python changes required. The
hints system is now used for both contextual injection (per-tool
surfaces) and reactive injection (error envelopes).
