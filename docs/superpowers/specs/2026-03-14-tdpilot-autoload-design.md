# TDPilot Auto-Load on TD Startup

**Date:** 2026-03-14
**Status:** Approved

## Problem

TDPilot installs into TouchDesigner's `/local` container, which persists across project opens within a single TD session. However, when TD is quit and reopened, TDPilot is gone. Users must manually re-run the setup script or drag the TOX back in every time.

## Solution

A TD startup script that automatically loads TDPilot into `/local` on every TouchDesigner launch, plus an `npx tdpilot install` CLI command that sets everything up.

## Architecture

### Components

| File | Type | Purpose |
|------|------|---------|
| `td_component/tdpilot_startup.py` | New | Python script for TD's Startup folder. Reads config, loads TOX into `/local`. |
| `npm/install.js` | New | CLI install/uninstall logic. Writes config, copies startup script. |
| `npm/run.js` | Modified | Routes `install`/`uninstall` subcommands to `install.js`. |

### Flow: Installation

```
npx tdpilot install
  1. Determine repo root (INSTALL_DIR = ~/.tdpilot)
  2. Write ~/.tdpilot_path (single line: repo root path)
  3. Create ~/Documents/Derivative/Startup/ if missing
  4. Copy td_component/tdpilot_startup.py to that folder
  5. Print success summary
```

### Flow: TD Launch (after install)

```
TouchDesigner starts
  -> TD auto-runs ~/Documents/Derivative/Startup/tdpilot_startup.py
  1. Read ~/.tdpilot_path -> repo_root
  2. Validate repo_root contains expected markers (pyproject.toml + td_component/)
  3. tox_path = repo_root/td_component/tdpilot_v1_3.tox
  4. Check staleness: compare TOX mtime vs td_component/*.py mtimes
  5. If TOX exists AND fresh -> destroy existing /local/mcp_server, load TOX  [fast path]
  6. If TOX missing OR stale -> set TD_MCP_REPO_ROOT env var, exec build script [rebuild]
  7. Print version + TOX path to Textport
```

### Flow: Uninstall

```
npx tdpilot uninstall
  1. Remove ~/Documents/Derivative/Startup/tdpilot_startup.py (if exists)
  2. Remove ~/.tdpilot_path (if exists)
  3. Print confirmation
```

## Detailed Design

### `td_component/tdpilot_startup.py`

**Config and validation:**
- Reads `~/.tdpilot_path` to find the TDPilot repo root
- Validates the repo root by checking for `pyproject.toml` and `td_component/mcp_webserver_callbacks.py` (same markers as existing `_is_repo_root()` logic)
- If validation fails, prints warning with `npx tdpilot install` hint and exits silently

**TOX loading (fast path):**
- Checks if `td_component/tdpilot_v1_3.tox` exists on disk
- Checks staleness: compares TOX mtime against all `td_component/*.py` source files. If any `.py` is newer than the TOX, triggers rebuild instead
- If fresh: destroys existing `/local/mcp_server` if present, then uses `op('/local').loadTox(tox_path)` to load as a child COMP
- Note: `loadTox` on a COMP in TD 2025+ loads the TOX as a child and returns the new COMP. If this fails (older TD version), falls through to rebuild path

**Rebuild fallback:**
- Sets `os.environ['TD_MCP_REPO_ROOT'] = repo_root` so the build script skips heuristic scanning
- Reads and exec's `build_export_mcp_tox.py` (same pattern as `setup_mcp_in_td.py`)
- The build script handles both TOX export and `/local` installation
- This is a full rebuild: creates temporary container, populates from source, exports, installs. May take a few seconds

**Safety:**
- All errors wrapped in try/except — never crashes TD startup
- Prints `[TDPilot]` prefixed messages to Textport for all outcomes
- On success: prints version and loaded TOX path
- On error: prints the error and suggests re-running `npx tdpilot install`

### `npm/install.js`

- Exports `install()` and `uninstall()` functions
- `install()`:
  - Uses `INSTALL_DIR` (same `~/.tdpilot` constant as `run.js`) as the repo root
  - Writes repo root path to `~/.tdpilot_path`
  - Detects OS for correct Startup folder path:
    - macOS/Linux: `~/Documents/Derivative/Startup/`
    - Windows: `os.homedir()/Documents/Derivative/Startup/` (note: some Windows configs redirect Documents; this is a known limitation)
  - Creates the Startup directory recursively if it doesn't exist
  - Copies `td_component/tdpilot_startup.py` from the repo into the Startup folder
  - Prints a summary of what was done
- `uninstall()`:
  - Removes the startup script from the Startup folder (no error if missing)
  - Removes `~/.tdpilot_path` (no error if missing)
  - Prints confirmation
  - Idempotent: running uninstall when already uninstalled succeeds silently

### `npm/run.js` Changes

- Before the existing MCP server launch logic, check `process.argv[2]`:
  - If `"install"` -> call `require("./install").install()` and exit
  - If `"uninstall"` -> call `require("./install").uninstall()` and exit
  - Otherwise -> proceed with existing MCP server launch (no change)
- Update the `files` array in `npm/package.json` to include `install.js`

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `~/.tdpilot_path` missing | Startup script prints warning, exits silently |
| Repo moved/deleted | Startup script validates markers, prints warning with re-install hint |
| Config path tampered/invalid | Marker validation catches it before any exec |
| `/local/mcp_server` already exists | Destroyed and re-loaded (consistent with build script) |
| TOX exists but stale (source newer) | Triggers rebuild fallback automatically |
| Build script fails | Error caught, printed to Textport, TD continues normally |
| Startup folder doesn't exist | `install` command creates it recursively |
| Already installed, run install again | Overwrites config and script (idempotent) |
| Already uninstalled, run uninstall again | Succeeds silently (idempotent) |
| TD not installed (no Derivative folder) | `install` creates the path; harmless if TD isn't present |
| MCP server not running when TD starts | TOX loads but WebSocket/HTTP fails — existing behavior, not new |

## Derived Artifacts Impact

- `td_component/tdpilot_startup.py` is a new source file — if it changes, `tdpilot.plugin` ZIP needs rebuilding
- `npm/package.json` `files` array must include `install.js` for npm publish
- No tool count change (no new MCP tools added)

## Testing

- Run `npx tdpilot install` -> verify `~/.tdpilot_path` and startup script exist in correct locations
- Restart TouchDesigner -> verify `/local/mcp_server` appears automatically in Textport
- Delete the `.tox` file -> restart TD -> verify rebuild fallback works and TOX is regenerated
- Touch a source `.py` file (make it newer than TOX) -> restart TD -> verify staleness triggers rebuild
- Run `npx tdpilot uninstall` -> verify cleanup of both files
- Run `npx tdpilot uninstall` again -> verify no errors (idempotent)
- Run `npx tdpilot` (no subcommand) -> verify MCP server still launches normally
- Move repo to different path -> restart TD -> verify warning message appears
