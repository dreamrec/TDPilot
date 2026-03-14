# What To Fix In TDPilot

This file is the practical follow-up to the audit.

It answers one question:

What should actually be fixed next, in what order, and why?

## Priority Order

If I were maintaining TDPilot, I would fix things in this order:

1. Trust bugs
2. Runtime bugs in newer tools
3. Doc / claim drift
4. Test depth
5. Product simplification
6. Memory quality improvements

That order matters.

Do not add more tool surface before tightening trust.

## 1. Fix Trust Bugs First

These are the issues that make users stop trusting the system.

### 1.1 Replay prerequisite checks

Current issue:

- `td_memory_replay` currently checks `required_op_types` against the local knowledge corpus, not the actual target TouchDesigner install.

Why this matters:

- it can falsely block valid replay
- it does not do what the README claims
- it weakens confidence in replay and compatibility

What to do:

- add a real target-install capability check
- expose a real endpoint or a reliable exec probe for available operator types
- clearly distinguish:
  - "missing from knowledge corpus"
  - "missing from target TD install"

Best fix:

- create a dedicated TD-side route for available operator types or families
- update replay to use that route
- update docs to reflect the real behavior

### 1.2 Audit semantics vs description

Current issue:

- `td_audit_project` is described like a subtree audit, but behaves more like a shallow root-child audit with an error pass.

Why this matters:

- users will assume they audited more than they really did
- project-level decisions may be based on incomplete information

What to do:

- either make it truly recursive and paginated
- or rename / redocument it as a shallow audit

My preference:

- make it genuinely subtree-aware

## 2. Fix Runtime Bugs In Newer Features

These are real bugs in tool behavior, not just wording problems.

### 2.1 `td_component_standardize(fix=true)`

Current issue:

- the fix path still uses `comp.appendCustomPage('Meta')[0]`
- live TD behavior shows `appendCustomPage()` returns a `Page`, not a list

Why this matters:

- the fix mode can break exactly when it is needed
- it hurts confidence in the newer TD 2025 tool layer

What to do:

- remove the `[0]`
- use the returned `Page` directly
- add a runtime test for:
  - page exists
  - page missing
  - params missing
  - params already present

### 2.2 TD 2025 tool revalidation

Current issue:

- some newer tools were added faster than their runtime validation matured

What to do:

- re-run all TD 2025 tools against a real TD 2025 build
- verify field names against official docs
- verify outputs match current docs

Minimum tools to re-check:

- `td_python_env_status`
- `td_threading_status`
- `td_logger_status`
- `td_tdresources_inspect`
- `td_component_standardize`
- `td_color_pipeline`

## 3. Fix Documentation Drift

This is a major theme in the repo.

### 3.1 Update replay wording

Current issue:

- README says replay blocks on missing operators in the target TD install
- implementation currently checks the local corpus

What to do:

- either fix the code to match the docs
- or fix the docs to match the code

Preferred answer:

- fix the code

### 3.2 Update API docs for `td_color_pipeline`

Current issue:

- API docs still describe older output fields
- implementation now returns current TD2025-style fields

What to do:

- update `docs/API_REFERENCE.md`
- align examples with current runtime output

### 3.3 Re-check audit descriptions

Current issue:

- several tools are described more broadly than they actually behave

What to do:

- review all newer tool descriptions
- remove inflated wording
- prefer exact behavior over marketing tone

## 4. Fix Test Depth

This is one of the biggest structural weaknesses.

The repo has a lot of tests, which is good.

But several newer surfaces are only tested for registration, not behavior.

### 4.1 Add behavioral tests for planning tools

Current problem:

- planning-related tests mostly verify that tool names exist

Need tests for:

- `td_validate_recipe` with:
  - inline recipe dict
  - stored recipe entry
  - dict-shaped `nodes`
  - list-shaped `nodes`
  - incompatibility reporting
- `td_audit_project` with:
  - shallow tree
  - recursive tree
  - unknown operator types
  - compatibility issues

### 4.2 Add behavioral tests for TD 2025 tools

Current problem:

- current tests mostly verify registration only

Need tests for:

- `td_component_standardize` fix path
- `td_color_pipeline` expected output keys
- `td_tdresources_inspect` filtered results

### 4.3 Add npm wrapper tests

Need tests for:

- `--help`
- `doctor`
- `init`
- passthrough argument handling

### 4.4 Add release-gate script tests for CI fixtures

Current issue:

- the GitHub Actions fixture still fails with `--require-complete`

Need tests for:

- incomplete benchmark report
- complete benchmark report
- incomplete soak report
- mixed bench + soak inputs

## 5. Fix Release And CI Discipline

### 5.1 Fix the CI release-gate step

Current issue:

- the CI fixture omits required `error_rate_pct` fields
- the command exits non-zero with `--require-complete`

What to do:

- either add the missing fields to the fixture
- or remove `--require-complete` from that CI check

Preferred answer:

- add complete fixture data

### 5.2 Add one true "release confidence" workflow

Recommended release checklist:

1. tests pass
2. docs pass sanity checks
3. npm wrapper CLI smoke passes
4. replay / memory smoke passes
5. TD-side runtime smoke passes on a real install

Right now the repo is close, but not fully locked down.

## 6. Product And UX Fixes

These are not bugs, but they would improve usefulness fast.

### 6.1 Define a "core 20 tools"

Problem:

- 86 tools is too much for normal users

What to do:

- publish a recommended core workflow
- clearly mark advanced tools as advanced

The core should center on:

- inspect
- build
- set params
- get errors
- snapshot
- restore
- memory learn/save/recall

### 6.2 Reframe the product around memory

Problem:

- tool count is currently more visible than compounding value

What to do:

- move the messaging toward:
  - reusable technique memory
  - safer AI-assisted workflow
  - inspect -> build -> verify -> save

That is the real differentiator.

### 6.3 Add guided examples

Good additions:

- 5 small beginner workflows
- 5 memory-building examples
- 5 debugging examples

That would help adoption more than more feature surface.

## 7. Memory System Improvements

These are high-value medium-term upgrades.

### 7.1 Better compatibility metadata

Improve saved techniques with:

- verified TD build
- replay success history
- known-safe environments
- whether replay required manual fixes

### 7.2 Better search and curation

Improve memory search with:

- favorite-first ranking
- reuse count
- recent success count
- tag normalization

### 7.3 Better quality states

Current state idea is good.

Make it stronger by tracking:

- candidate
- validated_local
- validated_portable
- deprecated
- broken

### 7.4 Team memory workflow

Add guidance or tooling for:

- sharing global memory across projects
- exporting / importing technique libraries
- team review of promoted techniques

## 8. Nice-To-Have Fixes After The Core

Only do these after the trust issues are clean:

- optional live official-doc refresh integration
- richer replay adaptation hints
- stronger diffing of saved techniques
- better visual verification summaries
- more structured portability checks

## The Most Important Principle

The project should not grow by adding more unverified features.

It should grow by:

- making current claims true
- making current tools predictable
- making memory genuinely reusable
- making the normal workflow easier and more trustworthy

## Recommended Fix Sequence

If this were my backlog, I would do:

### Phase 1 (COMPLETE)

- ~~fix `td_component_standardize` page creation bug~~ Done
- ~~fix replay prerequisite logic~~ Done — now queries `/api/families` on target TD install
- ~~fix CI release-gate fixture~~ Done — added `error_rate_pct` fields
- ~~update stale docs for replay and color pipeline~~ Done

### Phase 2 (COMPLETE)

- ~~add behavioral tests for planning tools~~ Done — 11 tests in `test_planning_tools_behavior.py`
- ~~add behavioral tests for TD 2025 tools~~ Done — 10 tests in `test_td2025_tools_behavior.py`
- ~~add behavioral tests for replay validation~~ Done — 7 tests in `test_replay_validation.py`
- ~~make `td_audit_project` truly recursive~~ Done — BFS traversal with depth limit and cycle detection

### Phase 3

- define and document the core workflow
- improve memory compatibility metadata
- improve curation workflow

### Phase 4

- revisit advanced surfaces like planning and optimization
- simplify product story around memory and workflow

## Implementation Plan

This section turns the roadmap into an execution plan.

The goal is not just to know what is wrong.

The goal is to know:

- what to change
- where to change it
- how to verify it
- what order to ship it in

## Guiding Rules For Implementation

Use these rules while fixing the repo:

1. Fix runtime truth before fixing marketing language.
2. Add tests in the same PR as the bug fix whenever possible.
3. Prefer dedicated TD-side endpoints over hidden exec hacks for core runtime checks.
4. Do not expand feature surface until the claimed surface is trustworthy.
5. Every new behavior should have:
   - implementation
   - test
   - docs update
   - at least one smoke verification path

## Workstream 1: Replay Trust

### Goal

Make `td_memory_replay` validate against the actual target TD install, not just the local knowledge corpus.

### Files to change

- `src/td_mcp/tool_registry.py`
- `td_component/mcp_webserver_callbacks.py`
- `src/td_mcp/models.py` if a new route payload needs modeling
- `docs/API_REFERENCE.md`
- `README.md`
- tests:
  - `tests/test_memory_tools_runtime.py`
  - add a new focused replay-validation test file if needed

### Implementation

#### Step 1

Add a TD-side endpoint for install/operator availability.

Suggested route:

- `/api/op_types`

Suggested response shape:

```json
{
  "families": ["TOP", "CHOP", "SOP", "DAT", "COMP", "MAT", "POP"],
  "op_types": ["nullTOP", "textDAT", "waveCHOP", "baseCOMP"],
  "count": 1234
}
```

#### Step 2

Implement the handler in `td_component/mcp_webserver_callbacks.py`.

Requirements:

- no mutation
- no broad try/except that hides logic mistakes
- return stable JSON
- distinguish unavailable family systems cleanly

#### Step 3

Update `td_memory_replay` to:

- query `/api/op_types`
- compare `required_op_types` against returned `op_types`
- block only when the target TD install is actually missing required operator types

#### Step 4

Keep knowledge-corpus checks as a separate warning layer, not as the install truth source.

Suggested response split:

- `missing_ops_on_target`
- `unknown_ops_in_corpus`

### Acceptance criteria

- replay no longer blocks valid built-ins that are absent from the local card corpus
- replay blocks when an op truly does not exist on the target install
- README and API docs describe the real behavior
- tests cover:
  - all ops present
  - missing target op
  - unknown corpus op but valid target op

### Suggested PR title

`fix(memory): validate replay requirements against target TD install`

## Workstream 2: `td_component_standardize` Runtime Fix

### Goal

Make fix mode work reliably on real TouchDesigner builds.

### Files to change

- `src/td_mcp/tool_registry.py`
- tests:
  - `tests/test_td2025_tools.py`
  - ideally add a dedicated behavioral test file for TD2025 tool payload logic

### Implementation

#### Step 1

Replace:

- `comp.appendCustomPage('Meta')[0]`

With:

- direct use of the returned `Page`

#### Step 2

Guard the page-creation path carefully:

- if `Meta` exists, reuse it
- if not, create it once
- append only missing parameters
- do not duplicate existing custom parameters

#### Step 3

Return explicit fix results:

- page created or reused
- which params were added
- which params already existed

Suggested response additions:

- `page_created`
- `page_name`
- `existing_params`

### Acceptance criteria

- fix mode works when `Meta` does not exist
- fix mode works when `Meta` already exists
- fix mode is idempotent
- no duplicate parameters are created
- undo block still wraps mutation

### Suggested PR title

`fix(td2025): make td_component_standardize fix mode robust`

## Workstream 3: Make `td_audit_project` Mean What It Says

### Goal

Make project audit truly subtree-aware or narrow the claim.

### Preferred direction

Implement real recursive audit.

### Files to change

- `src/td_mcp/tool_registry.py`
- maybe `src/td_mcp/memory/analyzer.py` for shared subtree traversal helpers
- `docs/API_REFERENCE.md`
- `README.md`
- tests:
  - `tests/test_planning_tools.py`
  - add focused audit behavior tests

### Implementation

#### Option A: preferred

Make `td_audit_project` recursive.

Suggested approach:

- reuse subtree traversal logic similar to `analyze_network`
- paginate `td_get_nodes`
- aggregate counts across descendants
- keep root path, max depth, and limit configurable

Suggested new inputs:

- `max_depth`
- `max_nodes`

#### Option B: fallback

Keep it shallow, but rename / rewrite docs as:

- "audit direct children of a root COMP"

That is weaker and less useful, so I would avoid it.

### Acceptance criteria

- counts represent more than just immediate children
- unknown op types and compat issues are collected from descendants
- docs explicitly define traversal semantics

### Suggested PR title

`feat(audit): make td_audit_project recursive and paginated`

## Workstream 4: CI And Release Confidence

### Goal

Make CI reflect real release confidence instead of partially passing confidence theater.

### Files to change

- `.github/workflows/ci.yml`
- `scripts/check_release_gates.py`
- `tests/test_release_gates.py`
- optionally add fixture JSON files under `tests/fixtures/`

### Implementation

#### Step 1

Fix the CI fixture.

Add `error_rate_pct` for all benchmark entries in the inline JSON.

#### Step 2

Add tests that mirror the CI fixture exactly.

This prevents future drift between:

- script expectations
- local tests
- GitHub Actions

#### Step 3

Add one explicit smoke section or separate workflow for:

- npm wrapper CLI help
- `doctor`
- basic memory save/recall in a temp directory

### Acceptance criteria

- current CI no longer fails at the release-gate step
- script behavior under `--require-complete` is covered in tests
- fixture changes have a matching test

### Suggested PR title

`fix(ci): align release-gate fixtures with completeness requirements`

## Workstream 5: Documentation Realignment

### Goal

Bring README, API docs, and runtime behavior back into alignment.

### Files to change

- `README.md`
- `docs/API_REFERENCE.md`
- `docs/MANUAL.md`
- `docs/extra/MASTER_AUDIT.md`
- `docs/extra/WHAT_TO_FIX.md`

### Implementation

#### Step 1

Update the replay description.

It should describe:

- install check
- corpus warning check
- what "blocked" means

#### Step 2

Update `td_color_pipeline` output documentation.

Use the current real output keys:

- `defaultParameterColorSpace`
- `workingColorSpace`
- `editorWindowPixelFormat`
- `sdrReferenceWhiteNits`
- `hdrReferenceWhiteNits`
- optional `monitorGamma`

#### Step 3

Re-check all newer tool descriptions for:

- subtree claims
- portability claims
- validation claims
- install-vs-corpus wording

### Acceptance criteria

- docs do not describe behavior that the code does not implement
- new runtime outputs are reflected in the API docs
- README headlines match actual behavior

### Suggested PR title

`docs: realign replay, audit, and td2025 tool descriptions with runtime`

## Workstream 6: Behavioral Test Expansion

### Goal

Make advanced surfaces harder to regress silently.

### Files to change

- `tests/test_planning_tools.py`
- `tests/test_td2025_tools.py`
- `tests/test_memory_tools_runtime.py`
- maybe new files:
  - `tests/test_replay_validation.py`
  - `tests/test_td2025_runtime_logic.py`
  - `tests/test_audit_project.py`

### Implementation

#### Step 1

Upgrade planning-tool tests from registration-only to behavior tests.

Cover:

- stored recipe validation
- inline recipe validation
- dict/list node shapes
- incompatibility status handling

#### Step 2

Upgrade TD2025 tests from registration-only to response-shape and code-path tests.

Cover:

- page-creation logic
- expected color-pipeline keys
- TDResources filter behavior

#### Step 3

Add replay-specific tests around:

- target install op availability
- corpus coverage mismatch
- blocked vs warned response semantics

### Acceptance criteria

- at least one behavioral test exists for every new trust-sensitive tool cluster
- registration-only tests are no longer the main protection layer for planning / TD2025 tools

### Suggested PR title

`test: add behavioral coverage for replay, planning, audit, and td2025 tools`

## Workstream 7: Product Simplification

### Goal

Make TDPilot easier to understand and safer to adopt.

### Files to change

- `README.md`
- `docs/MANUAL.md`
- `docs/extra/MEDIOCRE_USER_MANUAL.md`
- `docs/extra/HONEST_OPINION.md`

### Implementation

#### Step 1

Define a "core workflow" section near the top of the README.

Suggested title:

- `Start With These 20 Tools`

#### Step 2

Group tools into:

- core
- memory
- advanced

#### Step 3

Reduce hero messaging around raw tool count.

Promote instead:

- inspect -> build -> verify -> save
- reusable technique memory
- safer TD patch iteration

### Acceptance criteria

- a new user can understand where to start in under five minutes
- the repo feels less like a wall of features
- the product narrative matches the strongest practical value

### Suggested PR title

`docs(product): refocus TDPilot around core workflow and memory`

## Recommended PR Sequence

Use small PRs.

Recommended order:

1. Replay trust
2. `td_component_standardize` runtime fix
3. CI release-gate fix
4. Docs realignment
5. `td_audit_project` recursion
6. Behavioral test expansion
7. Product simplification

This sequence keeps trust improvements landing early.

## Definition Of Done

The "fix phase" should be considered complete only when all of these are true:

1. Runtime claims in README match implementation.
2. Replay checks target the real TD install.
3. `td_component_standardize(fix=true)` works on a real TD 2025 build.
4. `td_audit_project` traversal semantics are truthful and tested.
5. CI passes with a complete release-gate fixture.
6. Planning and TD2025 features have behavioral tests, not just registration tests.
7. The docs clearly tell normal users where the real value is.

## Final Bottom Line

If you only fix three things first, fix these:

1. replay trust
2. runtime bug in `td_component_standardize`
3. CI / release confidence

If you do that, TDPilot immediately becomes more trustworthy.
