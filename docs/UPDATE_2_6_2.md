# TDPilot 2.6.2

This patch fixes realtime HTTP callback overhead, timeline-wrap performance
evidence, and source-path detection on installations whose directory contains
spaces. It retains the 114-tool surface and MCP SDK 2.

Plugin ZIP and MCPB downloads now include all source files used by synchronization
diagnostics. Their fingerprints match the same release's Git installation;
missing packaging files no longer masquerade as modified runtime code.
Process-age checks also respect the one-second resolution of `ps` start times.
Subsecond ordering within the same second cannot prove a source update occurred
after launch; updates in a later second still require reconnection.

## Runtime changes

The Web Server DAT now calls a small `http_dispatch` DAT. That dispatcher loads
the router through `callbacks.module`, allowing TouchDesigner to reuse the
compiled router between requests. The authenticated router still performs every
policy check and native transaction. A missing router returns an error and
cannot execute an operation.

Native transaction receipts initialize on the first transaction request, not
while the DAT module is loaded. They remain in callback-DAT session storage and
survive code reloads; startup values exclude them from saved projects. Rollback
still checks ownership, intervening edits and exact state restoration.

The cooking endpoint reports `cookAbsFrame` and `totalCooks` alongside existing
fields. Performance sampling uses the absolute timestamp and requires a new
cook within every measured interval. Local `cookFrame` remains a conservative
fallback for older components. Missing, stale, malformed or out-of-budget
measurements still fail qualification.

## Qualification scope

Release timing now measures the owned generated-code fixture before removing
it. The incident replay independently measures its ten-output fixture and
exercises all five panel callbacks. Only TOPs inside confirmed owned fixtures
are forced; user callbacks are never forced for timing evidence.

Passive project measurements remain in `project_performance_summary`, with
their actual success or failure. They describe the current user project rather
than the release workload. A passing fixture does not certify whole-show FPS,
GPU rendering capacity, optional hardware, or a user's project.

The frame budget remains **16.667 ms**. All five steady intervals need fresh
target measurements and advancing absolute frames. Warmup spikes are retained
separately, not silently removed from the report.

## Updating

Update the server and canonical `td_component/tdpilot.tox` together. Reconnect
TDPilot clients that were already running. Keep the existing canonical secret;
do not copy secrets into public config files or rotate them merely to update.

For a Git-source installation, run `uv sync --frozen` in the checkout and point
the client at that checkout. The release updater intentionally selects a tag;
it is not the way to install fixes newer than that tag.

See [validation instructions](VALIDATION.md) for the required offline and live
commands. Platform-specific results must be recorded against the actual source
commit and TD build; prior Windows or Mac results are not interchangeable.

## Mac qualification — 12 November 2026

Initial HTTP/transaction qualification: `45cf5ad7bf4edcc4499bd9a2ca25bcc1eecf8d8c`, on macOS
26.6.2 / Apple Silicon with TouchDesigner **2025.33230**. Subsequent documentation
and bundle-closure fixes preserve this HTTP/transaction runtime. The full suite
was rerun with archive fingerprint and process-clock regressions, and live
synchronization was retested from unpacked downloads.

| Check | Result |
| --- | --- |
| Full Python suite | 2,348 passed; no skips |
| Complete release gate | 215 passed, 0 failed, 0 missing; all six reports present |
| Native transactions and guarded rollback | 29 checks passed; scratch cleanup verified |
| SDK 2 | Four stdio/HTTP sessions passed, including legacy protocol negotiation and verified rollback |
| Bounded control bindings | All 16 parameter-value checks passed |
| Live brain planning | 24 scenarios passed |
| Integrated visuals and panels | 13 visual checks and five panel checks passed |
| Timeline wrapping and backward seek | Both passed with five fresh steady intervals each |
| Actual client launch configurations | Eight fresh launches passed; version 2.6.2, 114 tools |
| Packaging | Wheel, npm, plugin ZIP and MCPB built; clean Git clone installed and registry smoke passed |

The integrated generated-code fixture peaked at **0.258 ms** per operator;
the incident fixture peaked at **0.119 ms**. Both retained the 16.667 ms budget.
The large router's compile count stayed constant during subsequent bridge
requests, confirming that the rebuilt component uses the cache.

The empty project's passive measurement correctly remained `missing_metrics`;
it is retained in the report, not represented as measured performance. Existing
project children, other local component IDs, play state, client configuration
and canonical authentication were preserved. The project was not saved or
rewritten. Pre-existing errors in an unrelated POPX component remained unchanged;
the project and TDPilot/local scopes had no errors. These are Mac results, not
a claim of a new Windows live qualification or whole-show performance.
