# TDPilot 2.6.0 — 12 November 2026

This release combines native atomic transactions and MCP SDK 2.3.0 with the
[2.5 improvements](UPDATE_2_5.md): updated dependencies, TouchDesigner
2025.33230 support, bounded controls, optional tool profiles, and clearer status
diagnostics. Live qualification used TouchDesigner 2025.33230 on macOS.

## Rollback safety

If a patch changes several things and then fails, TDPilot restores its affected
state and checks the restoration. It refuses automatic undo when later work
changed either the undo history or the affected nodes.

Typed operations execute in one TD callback and one native undo block. Macro
and annotation operations expand into that packet. Exact-name collisions, pulse
parameters, out-of-scope mutations and attempts to delete the serving bridge
are rejected. DAT text/table writes have explicit undo and redo callbacks:
TouchDesigner's ordinary undo block did not restore those writes in live tests.

Receipts identify each request and its component session. A transport retry
cannot apply the same packet twice. Lost responses and cancelled requests are
resolved through the original receipt with bounded recovery. Recovery checks
stored parameter values, expressions and modes, DAT content, layout,
connections, child inventories and deleted subtrees within the watched scope.
It does not claim to reverse external I/O, arbitrary callback side effects or a
process crash. Old components without the native endpoint fail before mutation.
See [endpoint limits](API_REFERENCE.md#native-transaction-http-endpoints-26).

## MCP SDK 2

Migrated imports, protocol model fields, tool annotations, explicit batch
Context, structured/error results, server version reporting, HTTP configuration
and resource subscriptions. Absolute TD operator paths remain valid resource
parameters. Tool input schemas remain compatible; the full profile has 114
tools, inspection 28, and build 50.

See [the practical benefits report](SDK2_AND_UPDATE_BENEFITS.md) for the subagent's
research and links to official SDK documentation.

## Qualification

Reports are in `reports/atomic-sdk2-2026-11-12/` (local, ignored by Git).

- Full suite: **2,308 passed** on the final source.
- Python 3.11 isolated checks: **50 passed**; primary suite uses Python 3.12.
- Golden evaluation: **102 cases passed**.
- Native TD atomic qualification: **29 checks passed**, including exact mixed-state rollback, deliberate mid-patch failure, failed validation, macro expansion, duplicate requests, lost responses and intervening-edit refusal.
- Real MCP clients: **stdio and Streamable HTTP**, each with **2026-07-28 and 2025-11-25** protocol sessions, passed tool discovery, batch context, resource reads and a live failure/rollback transaction.
- Live smoke: **24 planning scenarios** and **three generated GLSL/DAT runtime contracts** passed; all owned scratch was removed.
- Bounded controls: **16 live numerical checks passed**.
- Dependency metadata: **51 locked registry packages checked, zero reported PyPI advisories** at the time of the scan.
- Version, tool-schema, skill, plugin-surface, atlas and parameter-preflight/risk checks passed. `.tox` is rebuilt from the current TD callback source.

Two integration defects were found and fixed during qualification: DAT content
was not covered by ordinary TD undo, and dependency-tracking storage reads
created a callback DAT cook loop. Regression tests cover both.

A further release-gate defect used a fixed operator list from an older TD build.
It now checks the sampled build's bundled release card. All three newly sampled
2025.33230 operators were constructible on this Mac; this does not qualify
Nuitrack sensor tracking.

## Additional release checks and limits

The ten-output incident fixture passed all **five panel callback checks** and
**12 rendered-output quality checks** in a separate owned scratch network. The
core HTTP benchmark passed all four latency/error budgets with zero errors.
A separate six-sample forced-render check of the owned shader fixture advanced
168 frames and measured a maximum per-operator steady cook time of 0.122 ms
after warmup; this is a scoped CPU cook measurement, not whole-project FPS.
A 30-second synthetic WebSocket run sent and received **487 events**, with six
connections and zero dropped events. The installed Codex plugin also launched
2.6.0 successfully and discovered all 114 tools.

The strict `--require-complete` release gate is **not green**. Its all-installation
sync check detects older cached/running clients that need a restart, and its
whole-project steady-state probe includes cached startup cook measurements.
The separate panel/render tests do not replace the gate's integrated incident
replay or qualify an entire show at 60 fps. This release therefore reports
functional transaction/protocol qualification, not complete show-performance
certification. Windows live TD and Nuitrack sensor tracking remain unqualified;
see the 2.5 report for the Windows enrollment blocker.

Owned scratch networks were removed. The user's timeline was restored to its
original paused state and frame after the rendering and latency checks.

## Upgrade

Update the MCP runtime and replace its TouchDesigner component with the bundled
`tdpilot.tox`. Preserve your existing endpoint/authentication configuration and
restart each MCP client to load the new Python code. Native transactions require
the 2.6 component and refuse to run against older components. Python 3.11 or newer
is required. Existing tool input schemas and the full 114-tool profile remain
compatible.

The GitHub release includes the Claude plugin, Desktop MCP bundle and TD
component. The npm launcher installs the matching runtime. See
[client-specific installation](INSTALL_OTHER_CLIENTS.md) or the
[Claude Code installation guide](INSTALL_CLAUDE_PLUGIN.md).
