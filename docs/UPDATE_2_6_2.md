# TDPilot 2.6.2

This patch fixes realtime HTTP callback overhead, timeline-wrap performance
evidence, and source-path detection on installations whose directory contains
spaces. It retains the 114-tool surface and MCP SDK 2.

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
