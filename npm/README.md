# TDPilot v2.1.1

[![CI](https://github.com/dreamrec/TDPilot/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dreamrec/TDPilot/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/tdpilot?label=npm)](https://www.npmjs.com/package/tdpilot)
[![downloads](https://img.shields.io/npm/dm/tdpilot?label=downloads)](https://www.npmjs.com/package/tdpilot)
[![license](https://img.shields.io/badge/license-MIT-blue)](https://github.com/dreamrec/TDPilot/blob/main/LICENSE)
[![MCP tools](https://img.shields.io/badge/MCP%20tools-114-blueviolet)](https://github.com/dreamrec/TDPilot/blob/main/docs/API_REFERENCE.md)

AI copilot for TouchDesigner — 114 tools for full live control via MCP, with correctness-first BrainPlan transactions, optional cockpit UI, technique memory, knowledge corpus, POPx inspection, project lifecycle control, focus + locations, hint injection, component notes, custom parameter authoring, agent activity log, one-tool self-update, sync-status checks, and sync diagnosis.

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

**TouchDesigner side:** Drop `tdpilot.tox` into `/local` (persists across project opens).

For full docs, setup guides, and the .tox component: **[github.com/dreamrec/TDPilot](https://github.com/dreamrec/TDPilot)**
