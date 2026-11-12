# TDPilot 2.5 upgrade and qualification

This update targets TouchDesigner 2025.33230 and Python 3.11+. The default MCP
surface remains 114 tools. The local dependency lock was refreshed on
12 November 2026; all 46 registry entries returned zero advisories in the PyPI
version metadata scan. This is a dependency advisory check, not a penetration test.

## TouchDesigner support

The [official 2025.33230 release](https://derivative.ca/UserGuide/Release_Notes)
adds Time Filter POP, Nuitrack operators and native Gaussian-splat loading.
New cards and reviewed parameter semantics cover those changes. Live Mac
inspection corrected documentation discrepancies: Time Filter POP uses
`filtertype`, Nuitrack CHOP uses `maxplayers`, and Noise POP uses `amp0`/`exp0`.
A 37-parameter fixture records names, defaults and menus from the actual build.
Operator creation alone does not qualify Nuitrack tracking, its sensor, license,
or Windows behavior.

## Bounded controls

Control bindings support a CHOP channel index or safe channel name. Added
numeric targets accept finite `scale` and `offset` and always clamp. Optional
`output_range` narrows their default policy interval.
Bounds below are conservative authoring policy, not a guarantee of frame rate.

| Operator | Parameters | Allowed output bounds |
| --- | --- | --- |
| cameraCOMP | tx, ty, tz | -1000 to 1000 |
| cameraCOMP | rx, ry, rz | -3600 to 3600 |
| cameraCOMP | fov | 1 to 179 |
| phongMAT | diffr, diffg, diffb | 0 to 1 |
| phongMAT | shininess | 0 to 128 |
| particlePOP | birthrate | 0 to 10000 |
| particlePOP | life | 0.001 to 60 |
| particlePOP | speed | 0 to 100 |
| noisePOP | amp0 | 0 to 1000 |
| noisePOP | period | 0.001 to 100000 |

For example, a binding with `target_param="tx"`, `scale=2`, `offset=0.25`,
`output_range=[-2,2]` maps and clamps its source. Arbitrary Python expressions,
nonfinite values, unsupported targets and conflicting static parameters fail
preflight. Existing numeric Level TOP bindings remain supported.

Run `uv run python scripts/qualify_control_bindings.py --live --out report.json`
to check transaction validation, expression readback, 16 numerical samples and
a Time Filter POP preview. It removes only its own confirmed scratch component.

## Tool profiles

Set the environment on the MCP server process, for example inside its config:

```json
{"env": {"TD_MCP_TOOL_PROFILE": "build"}}
```

Merge this into the existing server configuration, preserving connection and
authentication settings. Restart the server after changing the profile.

| Profile | Tools | Intended use |
| --- | ---: | --- |
| full | 114 | Existing complete workflow; default |
| inspect | 28 | Inspection, diagnostics and documentation |
| build | 50 | Inspection plus grounded building and validation |

Profiles restrict registered tools and batch dispatch. They are context-size
controls, not a security sandbox; resources and prompts remain available.
`td_get_capabilities` reports the active profile and tool count. Invalid profile
names stop startup instead of silently enabling the full surface.

## Recovery correction

A live test exposed a dangerous previous assumption: a successful
`start_undo_block` request does not keep its block open for later HTTP requests.
[TouchDesigner closes dangling blocks at callback return](https://derivative.ca/UserGuide/Undo_Class).
Blind undo can therefore revert an earlier user action, including loading the
bridge itself.

Transactions now verify owned labels and require the TD component's atomic
history guard. Old components without that guard cannot trigger automatic undo.
If verified recovery cannot complete, the result reports
`needs_manual_recovery=true`. Parameter snapshots cannot recreate deleted
structures. Preserve old output routes and prefer owned staging components.
Generated-code smoke tests use container ownership for cleanup, including the
helper DATs created automatically by GLSL operators.

## Remaining improvement work

- Move the complete typed transaction into one TD callback, with bounded
  execution and cancellation, so native undo can actually encompass its edits.
  The new guard prevents unrelated undo but does not create cross-request undo.
- Migrate MCP SDK v2 deliberately: server class, context, tool calls, wire types
  and protocol compatibility all change. Follow the
  [official migration guide](https://py.sdk.modelcontextprotocol.io/migration/)
  and qualify each supported host before lifting the current `<2` constraint.
- Qualify Windows TD 2025.33230 and Nuitrack with a real sensor. The studio PC
  currently has TD 2025.32280, and its authenticated bridge enrollment check
  flagged a changed network-interface index. Windows validation is pending.
- Expand measured temporal/visual behavior in the golden suite. This release
  has 21 exact-value cases; 65 of 89 nonblocked cases carry parameter writes.
- Qualify the incident replay's panel callbacks under restricted execution;
  keep restricted mode and report unsupported operations rather than relaxing it.

## Codex runtime selection

The Codex wrapper now resolves the managed installation using
`TDPILOT_INSTALL_DIR`, then `~/.tdpilot_path`, then `~/.tdpilot`. It verifies the
project identity, minimum plugin version, source entry point and lockfile before
launching `uv run` there. An unrelated executable named `tdpilot` on PATH can no
longer become the plugin server. The wrapper requires the managed runtime to be
installed; install or update it with the TD component before using the plugin.

## Local qualification on 12 November 2026

- Main Python 3.12 suite: 2,276 passing tests, including the panel, guarded undo and plugin
  launcher regression checks.
- Python 3.11: 63 compatibility checks passed in an isolated environment.
- Golden plans: 102 passed, including 21 cases with exact parameter assertions.
- Live TD 2025.33230 on macOS: 24 planning scenarios, generated shader and DAT
  callback checks, a nonblack output, verified owned-container cleanup,
  16 control samples and Time Filter POP preview all passed.
- Native undo qualification rejected an unrelated label, reverted two owned
  blocks and preserved the preceding history. The recovered project was checked
  for errors after removing all test scratch components.
- Full, inspect and build profiles initialized over real MCP stdio connections
  and read the live TD session. Discovery sizes were 140,899, 30,631 and 61,189
  serialized characters respectively (about 78% / 57% smaller for inspect/build;
  these are character counts, not tokenizer measurements).
- Python wheel, npm tarball, Claude plugin ZIP and MCPB builds passed. Version,
  plugin-mirror, registry, source-format and TD `.tox` freshness checks passed.

Windows, actual Nuitrack hardware tracking and the complete restricted-mode
incident replay remain outside this qualification. Runtime processes already
open before the update must be restarted to load the new Python code.

## Follow-up

Native atomic transactions and MCP SDK 2 migration are implemented in the
2.6 working update. See [the 2.6 report](UPDATE_2_6.md) for its separate
qualification evidence and limits.
