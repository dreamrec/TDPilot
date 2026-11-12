# TDPilot 2.6.1 — Windows qualification, 12 November 2026

This patch was installed and exercised locally on Windows 11 Pro, an NVIDIA
GeForce RTX 5090 and TouchDesigner **2025.33230** (embedded Python 3.11.15).
The managed MCP runtime used isolated Python 3.12.9 and MCP SDK 2.3.0.
These are Windows results; the earlier 2.6.0 Mac evidence remains historical.

## Offline evidence

The full Windows suite passed **2,268 tests**, with **43 explicit skips**
(optional corpus data and two unavailable symlink privileges). One additional
sampler regression passed after that suite. Golden evaluation passed all 102
cases. Brain, atlas, skill, plugin, registry, version, API reference, component
freshness, parameter-preflight and parameter-risk audits passed. Ruff checks
and formatting passed.

## Live evidence

- 29 atomic transaction checks passed, including mid-apply and validation failure,
  mixed-state restoration, DAT text/table undo and redo, request deduplication,
  lost replies, cancellation recovery, invalid receipts and intervening-edit refusal.
- Four real MCP sessions passed: stdio and Streamable HTTP, each using protocols
  2026-07-28 and 2025-11-25; all discovered 114 tools.
- All 24 live planning scenarios and three generated-code runtime contracts passed.
- All 16 bounded-control numerical checks passed.
- Integrated incident replay passed five panel callbacks and 12 output-quality
  checks. Its owned scratch component was removed after validation.
- Strict integrated release gate: **226 passed, zero failed or missing**.
- Four HTTP benchmark budgets passed with zero errors (100 core iterations,
  30 capture iterations, plus warmup).
- A 30-second synthetic event soak verified **478 unique events received** from
  478 successful sends, with reconnects and zero drops.
- Six performance samples advanced 158 frames for the project-scope passive
  probe and 166 frames for the forced scratch fixture. Maximum fresh per-node
  CPU cook times were 0.105 ms and 0.092 ms respectively after warmup.

These timings are scoped per-operator CPU cook measurements. They do not certify
whole-show FPS, GPU time, end-to-end latency or arbitrary user projects at 60 fps.
Cached startup timings are excluded only when the node's cook frame did not
advance. Missing fresh timing evidence or a frozen timeline fails the probe.

## Fixes

The family endpoint previously enumerated only types instantiated in the project,
so a sparse Windows project falsely blocked available operators. It now includes
registered classes from the installed TD build, without constructing operators.
Actual construction and hardware operation remain separate qualification steps.

The old performance probes could pass a zero-time container or repeatedly read
startup cook values. Fresh per-node cook timestamps and advancing frames are now
required. The incident probe forces only its owned fixture's TOPs, and deletes
that fixture after collecting its evidence. No user output route is switched.

Windows checkout line endings previously changed source freshness hashes, and
version checks relied on the Windows default text encoding. Python sources now
have explicit LF checkout rules; version reads explicitly use UTF-8.
Two symlink security tests skip only Windows privilege error 1314; the Windows
security settings are preserved and those tests remain active on capable hosts.
Optional DocsBrain corpus tests are explicitly unverified when data is absent.

The 2.6.0 `.plugin` and `.mcpb` release bundles had later upload timestamps than
its checksum manifest and failed verification. That published release was left
unchanged. The asset workflow now refreshes checksums from final uploaded bytes.

## Windows installation

Keep the checkout and its `.venv` isolated. Point the managed `.tdpilot_path`
file at that checkout, register Codex's `touchdesigner` MCP server with
`uv run --directory <checkout> tdpilot`, and use canonical auth bootstrap:
`TD_MCP_REQUIRE_AUTH=1`, `TD_MCP_AUTOGENERATE_SECRET=1`, localhost port 9981.
Do not put a literal secret into a public config or command line.

The canonical component is `<checkout>/td_component/tdpilot.tox`; a convenient
`tdcomponents/tdpilot.tox` copy can be kept beside it. Load it into `/local`.
A current session can be tested with fresh child MCP clients without restarting
other Codex sessions. New Codex sessions load the saved MCP configuration.

Run `scripts/diagnose_live_sync.py --live --pretty` and
`scripts/check_tox_freshness.py` after installation. The component must report
API 2.6.1. Detailed local reports live under the ignored Windows reports folder;
release qualification assets contain a sanitized summary and final provenance.

Rollback covers watched TD graph state, not external I/O, arbitrary callback
side effects or process crashes. Nuitrack node construction was sampled; real
sensor tracking and its hardware/license remain unqualified. The original
project file, TD license/preferences and unrelated jobs were preserved.

**Mac coordinator:** synchronize the Mac runtime and TD component to 2.6.1 after
publication. Do not relabel the 2.6.0 Mac tests as tests of this patch.
