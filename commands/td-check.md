---
description: Run a comprehensive health check on the current TD project
---

Use the `td_` MCP tools to run a full health check on the current TouchDesigner
project:

1. Call `td_get_info` to confirm the session is alive and grab project name + TD build.
2. Call `td_get_errors` on the project root to surface any cooking or connection errors.
3. Call `td_get_capabilities` to confirm feature availability (vision, memory, safety).
4. Call `td_describe_surface` to report live tool count and server version.

Summarize findings concisely. Flag errors/warnings first, then capability deltas
or version drift.
