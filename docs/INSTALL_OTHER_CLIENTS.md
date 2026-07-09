# Installing TDPilot on Claude Desktop, Cursor, Codex, and other MCP clients

TDPilot works with any MCP-compatible host. The Claude Code plugin
([INSTALL_CLAUDE_PLUGIN.md](INSTALL_CLAUDE_PLUGIN.md)) is the richest install
(skills, agents, slash commands ship with it) — but the MCP server itself is
host-agnostic. Pick your client below.

Whatever the client, the TouchDesigner side is the same one-time step at the
end of this page.

## Claude Desktop — one-click `.mcpb` bundle

1. Download `tdpilot.mcpb` from the latest
   [GitHub release](https://github.com/dreamrec/TDPilot/releases/latest).
2. Double-click it (or drag it into Claude Desktop → Settings → Extensions).
   Claude Desktop installs the server and its environment in one step.
3. Restart Claude Desktop, open TouchDesigner, and ask:
   `What's in my TouchDesigner project?`

> Don't mix the Claude Desktop flow and the Claude Code plugin flow on one
> machine unless you know why — they each provision a shared secret, and two
> half-installs are the classic source of 401 errors. If you hit a 401, the
> error message itself now walks you through `td_sync_diagnose`.

## Cursor / Windsurf / other Claude-compatible IDEs

Add TDPilot to the client's MCP config (Cursor: `.cursor/mcp.json` in your
project, or the global MCP settings):

```json
{
  "mcpServers": {
    "touchdesigner": {
      "command": "npx",
      "args": ["-y", "tdpilot"],
      "env": {
        "TD_MCP_HOST": "127.0.0.1",
        "TD_MCP_PORT": "9981",
        "TD_MCP_EXEC_MODE": "restricted",
        "TD_MCP_REQUIRE_AUTH": "1",
        "TD_MCP_AUTOGENERATE_SECRET": "1"
      }
    }
  }
}
```

`npx -y tdpilot` bootstraps the server on first run (it clones the pinned
release into `~/.tdpilot` and runs it with `uv`). No API key, no signup.

## Codex CLI

The repo ships a Codex plugin surface (skills + agents + MCP config) under
`plugins/tdpilot/`. Point Codex at it, or register the server directly with
the same `npx -y tdpilot` command as above in your Codex MCP configuration.

## Any other MCP client

TDPilot is a standard stdio MCP server. Launch command:

```bash
npx -y tdpilot          # easiest — self-bootstraps
# or, from a clone:
uv run --directory /path/to/TDPilot tdpilot
```

Use the same environment variables as the Cursor block above. The full list
lives in the README's Environment Variables section.

## The TouchDesigner side (once per machine)

Every client needs the TD-side component listening on port 9981:

1. Get `tdpilot.tox` — it's bundled in the plugin/bundle installs, attached
   to every GitHub release, and present in `~/.tdpilot/td_component/` after
   an npx bootstrap.
2. Drag it into your project's `/local` container — or run the Textport
   setup block from [INSTALL_CLAUDE_PLUGIN.md](INSTALL_CLAUDE_PLUGIN.md),
   which installs it into `/local` and wires auto-load.
3. Verify from your client: `What's in my TouchDesigner project?` — or, on
   clients with slash commands, `/td-first-wow` for the full two-minute demo.

## Troubleshooting

- **401 Unauthorized** → the error envelope walks you through it; the fix is
  almost always secret drift between the client config and
  `~/.tdpilot/.tdpilot.env`. `td_sync_diagnose` names the mismatched layer.
- **Connection refused** → TouchDesigner isn't running, or the component
  isn't in `/local` (or its WebServer is inactive). Re-run the Textport
  setup block.
- Everything else → [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
