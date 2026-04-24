# TDPilot Troubleshooting Guide

## First Step: Run the Doctor

Before digging into specific issues, run the built-in diagnostics:

```bash
tdpilot doctor
```

For machine-readable output:

```bash
tdpilot doctor --json
```

The doctor checks: Python runtime, `uv` availability, repo root detection, `.tox` component presence, transport config, TCP port reachability, and TD health endpoint. A failing check prints `[FAIL]`, a non-critical issue prints `[WARN]`.

If TD is not running yet, skip the live check:

```bash
tdpilot doctor --skip-td-check
```

Use `--strict` to treat warnings as failures (useful in CI):

```bash
tdpilot doctor --strict
```

---

## 1. Connection Failures

**Symptom:** `Cannot reach TouchDesigner at http://127.0.0.1:9981 after 3 attempts.`

### TouchDesigner is not running

The MCP server communicates with TD over HTTP. TD must be open with the TDPilot component loaded.

1. Open TouchDesigner.
2. Drag `td_component/tdpilot.tox` into `/local` (recommended — persists across project opens) or into your project root.
3. Verify the WebServer DAT inside the component is active (green cook indicator).

### Component not loaded or inactive

The `.tox` component contains the WebServer DAT that listens on port 9981. If you deleted it, bypassed it, or it errored on load, the MCP server has nothing to connect to.

- Re-import `td_component/tdpilot.tox` into `/local` (or your project root).
- Check the component's error state in TD (right-click > Info).

### Wrong host or port

The MCP server connects to `http://{TD_MCP_HOST}:{TD_MCP_PORT}`. Defaults are `127.0.0.1:9981`. If TD's WebServer DAT is on a different port or interface:

```bash
TD_MCP_HOST=192.168.1.50 TD_MCP_PORT=8080 npx -y tdpilot
```

Or set these in your MCP client config:

```json
{
  "mcpServers": {
    "touchdesigner": {
      "command": "npx",
      "args": ["-y", "tdpilot"],
      "env": {
        "TD_MCP_HOST": "192.168.1.50",
        "TD_MCP_PORT": "8080"
      }
    }
  }
}
```

### Firewall blocking localhost

On macOS, the first time TD opens a network port you may get a firewall dialog. Click "Allow". If you dismissed it:

- System Settings > Network > Firewall > Options > find TouchDesigner > Allow.

On Windows, check Windows Defender Firewall for inbound rules on port 9981.

### Retry behavior

The client retries failed connections up to 2 times with exponential backoff (1s, 2s). If TD is starting slowly, the retries may still not be enough. Wait for TD to fully load the component, then retry your request.

---

## 2. Port Conflicts

**Symptom:** `Address already in use` on port 9981 or 9982, or the doctor shows `[WARN]` on `port_reachability`.

### Check what is using the port

```bash
# macOS / Linux
lsof -i :9981
lsof -i :9982

# Windows
netstat -ano | findstr :9981
```

### Change ports via environment variables

Set different ports in your MCP client config or shell:

```bash
TD_MCP_PORT=9991 TD_MCP_WS_PORT=9992 npx -y tdpilot
```

You must also update the WebServer DAT port inside the TD component to match `TD_MCP_PORT`, and the WebSocket port to match `TD_MCP_WS_PORT`.

### Multiple TD instances

Each TD instance needs its own port pair. Use unique `TD_MCP_PORT` / `TD_MCP_WS_PORT` values for each.

---

## 3. WebSocket Issues

**Symptom:** `td_subscribe` returns success but `td_get_events` returns no events. Or the server log shows `Could not start event websocket listener on 9982`.

### WebSocket port mismatch

The MCP server opens a WebSocket listener on `TD_MCP_WS_PORT` (default `9982`). The TD component must send events to this same port. Verify both sides agree:

```bash
# Check what port the server is using
tdpilot doctor --json | python3 -c "import sys,json; d=json.load(sys.stdin); print([c for c in d['checks'] if c['name']=='runtime_defaults'])"
```

The output includes `ws=9982` (or your override).

### Port 9982 already in use

Another process may hold port 9982. Find and stop it, or change the WS port:

```bash
TD_MCP_WS_PORT=9992 npx -y tdpilot
```

### Events never arrive

1. Confirm the subscription was created: `td_subscribe` should return a subscription ID.
2. Trigger the event source in TD (e.g., change a parameter you subscribed to).
3. Call `td_get_events` to poll. Events are buffered up to `TD_MCP_EVENT_BUFFER` (default 1000).
4. If the WebSocket listener failed to start on server boot, subscriptions will be provisioned on the TD side but events cannot flow back. Restart the MCP server after freeing the WS port.

---

## 4. Exec Mode Problems

**Symptom:** `PermissionError: restricted mode blocks import statements` or `Python execution is disabled by TD_MCP_EXEC_MODE=off`.

### Understanding exec modes

`TD_MCP_EXEC_MODE` controls what `td_exec_python` is allowed to run. Four levels:

| Mode | Imports | System access | Use case |
|------|---------|---------------|----------|
| `off` | Blocked | Blocked | Fully disable Python exec |
| `restricted` | All blocked | Blocked | Safe read-only probes (default) |
| `standard` | 14 safe modules allowed | Blocked | Data transforms (json, math, re, datetime, collections, itertools, functools, copy, textwrap, string, random, decimal, fractions, statistics) |
| `full` | All allowed | Allowed | Unrestricted (use with caution) |

### Changing exec mode

Set the environment variable:

```bash
TD_MCP_EXEC_MODE=standard npx -y tdpilot
```

Or in your MCP client config:

```json
{
  "env": {
    "TD_MCP_EXEC_MODE": "standard"
  }
}
```

### What gets blocked

**Restricted mode** blocks:
- Any `import` or `from ... import` statement.
- Dangerous function calls and module references: `__import__`, `open(`, `compile(`, `subprocess`, `socket`, `urllib`, `pathlib`, `shutil`, and OS-level shell execution functions.

**Standard mode** additionally blocks:
- Reflection primitives: `setattr`, `delattr`, `__subclasses__`, `__bases__`, `globals(`, `locals(`.
- Code evaluation primitives.
- Any import not in the 14 allowed modules listed above.

**Off mode** rejects all `td_exec_python` calls entirely.

### Recommendation

Start with `restricted` (the default). Move to `standard` if you need data-processing imports like `json` or `math`. Only use `full` for development/debugging sessions where you trust the AI agent completely.

---

## 5. npx / uv Install Issues

### Node.js not found

`npx` requires Node.js. Install it from [nodejs.org](https://nodejs.org/) (LTS recommended, v18+).

Verify:

```bash
node --version
npx --version
```

### uv not found after npx install

The `npx tdpilot` wrapper auto-installs `uv` if missing. If it fails:

1. Install `uv` manually:
   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Ensure `~/.local/bin` is in your `PATH`:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. Open a new terminal and retry.

### npx caching stale version

If `npx` serves an old cached version:

```bash
npx -y tdpilot@latest
```

Or clear the npx cache:

```bash
# npm 7+
npx --yes clear-npx-cache

# Or manually
rm -rf ~/.npm/_npx
```

### Local development setup (without npx)

```bash
git clone https://github.com/dreamrec/TDPilot.git
cd TDPilot
uv sync
uv run tdpilot
```

### git not found during install

Both `install.sh` and `npx tdpilot` fall back to downloading a ZIP archive if `git` is not available. If that also fails, install git first:

```bash
# macOS
xcode-select --install

# Windows
winget install Git.Git
```

---

## 6. TD Version Incompatibility

### Minimum requirements

TDPilot requires a TouchDesigner build that supports the WebServer DAT with JSON POST handling. Generally this means **TD 2023.11000+**. Older builds may lack API endpoints the component depends on.

### Checking TD build via doctor

```bash
tdpilot doctor
```

The `td_health` check contacts TD and reports the health endpoint response. If TD responds but returns unexpected payloads, the build may be too old.

### Checking TD build from inside TD

In TD's Textport:

```python
print(app.build)
print(app.version)
```

### Component version mismatch

Make sure the `.tox` component version matches the MCP server version. The current component is `tdpilot.tox` (ships with server v1.3.x). Using an older `.tox` with a newer server (or vice versa) can cause missing endpoint errors.

---

## 7. Tool Errors

### `TouchDesignerAPIError: ... returned HTTP 404`

The endpoint does not exist on the TD-side component. Likely a component/server version mismatch. Re-import the latest `.tox`.

### `TouchDesignerAPIError: ... returned HTTP 500`

An unhandled error inside TD. Check TD's Textport for the Python traceback. Common causes:
- Referencing a node path that does not exist.
- Passing invalid parameter names to `td_set_params`.
- Running `td_exec_python` code that raises an exception inside TD.

### `td_get_nodes` returns empty

The path argument may point to a container that has no children, or the path does not exist. Verify the path with `td_get_info` first.

### `td_connect_nodes` fails

- Confirm both source and target nodes exist.
- Check that the output/input indices are valid for those operator types.
- SOPs connect to SOPs, CHOPs to CHOPs, etc. Cross-family connections are not allowed in TD.

### `td_create_node` "unknown type"

The operator type string must match TD's internal naming. Use `td_list_families` to see available families, and `td_search_nodes` or `td_python_help` to verify type names.

### `td_screenshot` returns no image

- The node must be a TOP or have a viewer.
- The node must be cooking (not bypassed or errored).
- Very large resolutions may exceed memory or timeout.

---

## 8. Performance

### Slow responses / timeouts

**Symptom:** `Request to /api/... timed out after 15.0s.`

The default HTTP timeout is 15 seconds with a 5-second connect timeout. Heavy operations can exceed this.

**Fixes:**
- Reduce scope: query fewer nodes, smaller data ranges, lower-resolution screenshots.
- Avoid requesting `td_get_nodes` on the root `/` of a large project. Target specific containers.
- For `td_geometry_data`, limit row counts.
- For `td_chop_data`, narrow the channel/sample range.

### Streaming token cost

`td_stream_top` and `td_monitor_visual` can generate large token volumes when `include_image=true`. Start with `include_image=false` and only enable image payloads when visual inspection is required. Use `td_screenshot` for single-shot checks instead of continuous streaming.

Configure stream limits:

```bash
TD_MCP_STREAM_MAX_FPS=5 TD_MCP_CAPTURE_QUALITY=0.2 npx -y tdpilot
```

### Event buffer overflow

The event buffer holds up to `TD_MCP_EVENT_BUFFER` events (default 1000). If events arrive faster than they are consumed via `td_get_events`, older events are dropped. Increase the buffer if needed:

```bash
TD_MCP_EVENT_BUFFER=5000 npx -y tdpilot
```

Or call `td_get_events` more frequently.

---

## Environment Variable Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `TD_MCP_HOST` | `127.0.0.1` | TD WebServer host |
| `TD_MCP_PORT` | `9981` | TD WebServer HTTP port |
| `TD_MCP_WS_PORT` | `9982` | WebSocket event port |
| `TD_MCP_TRANSPORT` | `stdio` | MCP transport (`stdio`, `streamable_http`, `sse`) |
| `TD_MCP_HTTP_HOST` | `127.0.0.1` | HTTP transport bind host |
| `TD_MCP_HTTP_PORT` | `8765` | HTTP transport bind port |
| `TD_MCP_EXEC_MODE` | `restricted` | Python exec safety level |
| `TD_MCP_CAPTURE_QUALITY` | `0.3` | JPEG quality for captures (0-1) |
| `TD_MCP_STREAM_MAX_FPS` | `15.0` | Max FPS for TOP streaming |
| `TD_MCP_EVENT_BUFFER` | `1000` | Max buffered events |
| `TD_MCP_MAX_SNAPSHOTS` | `50` | Max stored snapshots |
| `TD_MCP_SHARED_SECRET` | (none) | Auth secret for TD API |
| `TDPILOT_PROJECT_NAME` | (none) | Per-project memory scope |
| `TDPILOT_MEMORY_DIR` | `~/.tdpilot/memory/` | Memory storage path |

---

## Getting More Help

1. Run `tdpilot doctor --json` and include the output in any bug report.
2. Check TD's Textport for Python errors on the TD side.
3. Set `TD_MCP_AUDIT_LOG` to a file path to capture a log of all tool calls:
   ```bash
   TD_MCP_AUDIT_LOG=/tmp/tdpilot_audit.log npx -y tdpilot
   ```
4. File issues at [github.com/dreamrec/TDPilot](https://github.com/dreamrec/TDPilot/issues).
