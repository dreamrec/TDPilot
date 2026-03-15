# TDPilot v1.3.2

AI copilot for TouchDesigner — 90 tools for full live control via MCP, with technique memory, POPx inspection, project lifecycle control, and custom parameter authoring.

## Quick start

Add to your MCP desktop client config:

```json
{
  "mcpServers": {
    "touchdesigner": {
      "command": "npx",
      "args": ["-y", "tdpilot"]
    }
  }
}
```

That's it. On first run it installs `uv` and downloads the server automatically.

Useful local commands:

```bash
tdpilot doctor
tdpilot init --client claude-desktop
```

**TouchDesigner side:** Drop `tdpilot_v1_3.tox` into `/local` (persists across project opens).

For full docs, setup guides, and the .tox component: **[github.com/dreamrec/TDPilot](https://github.com/dreamrec/TDPilot)**
