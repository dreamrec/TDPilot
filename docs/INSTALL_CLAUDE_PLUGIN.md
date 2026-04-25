# Installing TDPilot as a Claude Code Plugin

TDPilot ships as a Claude Code plugin via the `dreamrec/TDPilot` marketplace.
You get 97 MCP tools, three skills (`tdpilot-core`, `tdpilot-production`,
`popx-touchdesigner`), two slash commands (`/td-check`, `/td-snapshot`), and
the TD-side `.tox` component all in one install.

## Prerequisites

- **Claude Code** CLI installed and on `PATH` — https://claude.com/claude-code
- **TouchDesigner** 2025.30000+ (earlier TD builds may work but are untested)
- **`uv`** for running the Python MCP server — auto-installed by our scripts if absent

## Pick ONE installer path — don't mix

TDPilot has two separate install flows that should NOT be combined in a
single machine/user install:

| Flow | When to use | What it writes |
|---|---|---|
| **Claude Code plugin** (this doc) | You use Claude Code (CLI) or Claude Preview | `~/.claude/plugins/cache/dreamrec-TDPilot/` |
| **Claude Desktop** (`./install.sh`) | You use the Claude Desktop GUI | `~/Library/Application Support/Claude/claude_desktop_config.json` + generates `TD_MCP_SHARED_SECRET` |

If you run both: two env configurations point at the same TD on port 9981,
each with a different `TD_MCP_SHARED_SECRET`. TD only accepts one. Whichever
flow was used most recently "wins" and the other appears broken. **Pick one
and stick with it.**

To switch: uninstall the other first. See the "Uninstalling" section below.

## Three ways to install

### Option A — One-liner (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/dreamrec/TDPilot/main/scripts/install_claude_plugin.sh | bash
```

This runs `scripts/install_claude_plugin.sh`, which:
1. Verifies the `claude` CLI is on `PATH`.
2. Registers `dreamrec/TDPilot` as a plugin marketplace.
3. Installs the `tdpilot` plugin from it.
4. Prints next-step instructions for the TouchDesigner side.

### Option B — `npx` wrapper

If you already have `npx` handy:

```bash
npx tdpilot plugin-install
```

Same behavior as Option A — just delegates to the `claude` CLI under the hood.
Undo with `npx tdpilot plugin-uninstall`.

### Option C — Manual via Claude Code

Inside any Claude Code session:

```
/plugin marketplace add dreamrec/TDPilot
/plugin install tdpilot@dreamrec-TDPilot
```

Identical result. Use this if you want to see each step explicitly.

## TouchDesigner-side setup (once)

After installing the plugin, the MCP server can run but TouchDesigner doesn't
yet have the `.tox` component loaded. Two options:

**Drag-drop (easiest):**
1. Open Finder to
   `~/.claude/plugins/cache/dreamrec-TDPilot/tdpilot/<version>/td_component/`
2. Drag `tdpilot.tox` into your TD `/local` container.

**Or via TD Textport** — run `setup_mcp_in_td.py` from the plugin cache. Paste
this block into the Textport (it auto-detects the latest installed version):

```python
import os
plugin_root = os.path.expanduser("~/.claude/plugins/cache/dreamrec-TDPilot/tdpilot")
versions = sorted(os.listdir(plugin_root))
os.environ["TD_MCP_REPO_ROOT"] = os.path.join(plugin_root, versions[-1])
script_path = os.path.join(os.environ["TD_MCP_REPO_ROOT"], "setup_mcp_in_td.py")
with open(script_path) as _f:
    _source = _f.read()
compile(_source, script_path, "exec")  # parse check
exec(compile(_source, script_path, "exec"), globals(), globals())  # noqa: S102
```

Either way, `/local/mcp_server` appears with a WebServer on port 9981 listening
for MCP requests from Claude.

## Verifying

In a Claude Code session, type:

```
What's in my TouchDesigner project?
```

Claude will:
1. Auto-start the `touchdesigner` MCP server from the plugin cache.
2. Call `td_get_info` against the running TD.
3. Report the project name, TD build, FPS, and framecount.

If that works, every other `td_*` tool works too. Run `/td-check` for a full
health dump.

## Environment variables the plugin sets

The plugin's bundled `.mcp.json` defaults to:

| Var                      | Default        | Purpose |
| ------------------------ | -------------- | ------- |
| `TD_MCP_HOST`            | `127.0.0.1`    | Where the TD WebServer listens |
| `TD_MCP_PORT`            | `9981`         | TD WebServer port |
| `TD_MCP_WS_PORT`         | `9982`         | TD WebSocket port (events, streaming) |
| `TD_MCP_EXEC_MODE`       | `restricted`   | Python exec sandbox tier — see `docs/SECURITY.md` |
| `TD_MCP_REQUIRE_AUTH`    | `1`            | Require `TD_MCP_SHARED_SECRET` for HTTP auth |

Override any of them in your Claude Code `settings.json` under
`"mcpServers": { "touchdesigner": { "env": {...} } }` if needed. The default
is safe for single-user local sessions.

## Updating

```bash
claude plugin update tdpilot@dreamrec-TDPilot
```

Or `npx tdpilot plugin-install` — reruns are idempotent and pull the latest.

## Uninstalling

```bash
npx tdpilot plugin-uninstall
```

Or:

```
/plugin uninstall tdpilot@dreamrec-TDPilot
/plugin marketplace remove dreamrec-TDPilot
```

To also remove the TD-side `.tox`, destroy `/local/mcp_server` in TouchDesigner
(and re-save the project if it was persisted via `npx tdpilot install`).

## Troubleshooting

- **`claude: command not found`** — Install Claude Code first.
  - https://claude.com/claude-code
- **MCP server fails to start with "uv not found"** — `curl -LsSf https://astral.sh/uv/install.sh | sh` then reopen your terminal.
- **TD returns 401 Unauthorized** — make sure your Claude Code env includes the
  `TD_MCP_SHARED_SECRET` that TD has, or set `TD_MCP_REQUIRE_AUTH=0` for local
  dev. See `docs/SECURITY.md` for the auth model.
- **Zombie `/project1/mcp_server`** — if you've auto-saved a project with an
  old version, destroy it in TD and re-save. Two WebServers on port 9981 cause
  silent auth failures (one binds first, the new one is shadowed).
