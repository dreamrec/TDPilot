# TDPilot Auto-Load Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TDPilot auto-load into `/local` on every TouchDesigner launch, with a CLI install command.

**Architecture:** A TD startup Python script reads `~/.tdpilot_path` config, loads the pre-built TOX (or rebuilds from source if stale/missing). An `npx tdpilot install` CLI command writes the config and copies the startup script into TD's Startup folder.

**Tech Stack:** Python (TD startup script), Node.js (CLI install command)

**Spec:** `docs/superpowers/specs/2026-03-14-tdpilot-autoload-design.md`

---

## Chunk 1: TD Startup Script

### Task 1: Create `td_component/tdpilot_startup.py`

**Files:**
- Create: `td_component/tdpilot_startup.py`

This script runs inside TouchDesigner's Python environment on every TD launch. It uses TD-specific APIs (`op()`, `loadTox()`) that are only available inside TD, so it cannot be unit-tested with pytest. Testing is manual (restart TD, check Textport).

- [ ] **Step 1: Create the startup script**

Create `td_component/tdpilot_startup.py` with the full implementation. The script:
- Reads `~/.tdpilot_path` for repo root
- Validates repo markers (`pyproject.toml` + `td_component/mcp_webserver_callbacks.py`)
- Checks TOX staleness by comparing mtime of TOX vs `td_component/*.py`
- Fast path: wraps `op('/local').loadTox(tox_path)` in try/except — if `loadTox` fails (older TD versions), falls through to rebuild
- Fallback: sets `os.environ['TD_MCP_REPO_ROOT'] = repo_root`, then exec's `build_export_mcp_tox.py` (same exec pattern as `setup_mcp_in_td.py` lines 140-151)
- All errors caught at top level — never crashes TD startup
- All output prefixed with `[TDPilot]`
- On success, prints `[TDPilot] v1.3 loaded from <tox_path>` (version hardcoded as "v1.3" matching the TOX filename)

- [ ] **Step 2: Verify the script is valid Python**

Run: `python3 -c "import ast; ast.parse(open('td_component/tdpilot_startup.py').read()); print('OK')"`
Expected: `OK`

Note: The script uses TD-specific APIs (`op()`, `loadTox()`) so it can't be fully run outside TD. We only verify syntax here.

- [ ] **Step 3: Commit**

```bash
git add td_component/tdpilot_startup.py
git commit -m "feat: add TD startup script for auto-loading TDPilot on launch"
```

---

## Chunk 2: CLI Install Command

### Task 2: Create `npm/install.js`

**Files:**
- Create: `npm/install.js`

- [ ] **Step 1: Create the install/uninstall CLI module**

Create `npm/install.js` that exports `install()` and `uninstall()` functions.

`install()`:
- Defines `INSTALL_DIR = join(os.homedir(), ".tdpilot")` (same constant as `run.js`)
- Defines `CONFIG_FILE = join(os.homedir(), ".tdpilot_path")`
- Validates that `INSTALL_DIR/td_component/tdpilot_startup.py` exists
- Writes `INSTALL_DIR` path to `CONFIG_FILE`
- Determines TD Startup folder: `join(os.homedir(), "Documents", "Derivative", "Startup")`
- Creates Startup dir recursively with `mkdirSync` if missing
- Copies startup script with `copyFileSync`
- Prints summary

`uninstall()`:
- Removes startup script and config file (no error if missing)
- Prints confirmation
- Idempotent

Uses only Node.js `fs` built-ins: `existsSync`, `mkdirSync`, `copyFileSync`, `unlinkSync`, `writeFileSync`. No shell commands or child processes needed.

- [ ] **Step 2: Verify syntax**

Run: `node -c npm/install.js`
Expected: no output (valid syntax)

- [ ] **Step 3: Commit**

```bash
git add npm/install.js
git commit -m "feat: add install/uninstall CLI for TD auto-load setup"
```

---

### Task 3: Wire `install`/`uninstall` subcommands into `npm/run.js`

**Files:**
- Modify: `npm/run.js` (insert subcommand routing AFTER `ensureRepo()`, BEFORE env/spawn)

- [ ] **Step 1: Add subcommand routing to run.js**

Insert a subcommand routing block AFTER the existing `ensureRepo();` call (line 98) and BEFORE the `const env = {` block (line 101). This ordering is critical: `install` needs the repo to already exist at `~/.tdpilot` (which `ensureRepo()` ensures).

The block should:
- Read `process.argv[2]` as `subcommand`
- If `"install"` or `"uninstall"`: call `require("./install").install()` or `.uninstall()`, then `process.exit(0)`
- Otherwise: fall through to existing MCP server launch code (env setup + spawn)

**Important:** The existing uv install + `ensureRepo()` logic MUST run before this block, because `install` needs the cloned repo to copy the startup script from.

- [ ] **Step 2: Verify run.js still parses**

Run: `node -c npm/run.js`
Expected: no output (valid syntax)

- [ ] **Step 3: Commit**

```bash
git add npm/run.js
git commit -m "feat: route install/uninstall subcommands in run.js"
```

---

### Task 4: Update `npm/package.json` files array

**Files:**
- Modify: `npm/package.json:16`

- [ ] **Step 1: Add install.js to the files array**

Change `npm/package.json` line 16 from:
```json
  "files": ["run.js", "README.md"],
```
to:
```json
  "files": ["run.js", "install.js", "README.md"],
```

- [ ] **Step 2: Verify valid JSON**

Run: `node -e "JSON.parse(require('fs').readFileSync('npm/package.json','utf-8')); console.log('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add npm/package.json
git commit -m "chore: include install.js in npm package files"
```

---

## Chunk 3: Manual Testing and Docs

### Task 5: Test the full flow in TouchDesigner

This task is manual -- it requires a running TouchDesigner instance.

- [ ] **Step 1: Run install**

In terminal: `node npm/run.js install`

Verify:
- `~/.tdpilot_path` exists and contains the repo path
- `~/Documents/Derivative/Startup/tdpilot_startup.py` exists
- Output shows success messages

- [ ] **Step 2: Restart TouchDesigner**

Quit TD completely, reopen it. Check Textport for `[TDPilot]` messages confirming auto-load. Verify `/local/mcp_server` exists by running in Textport:
```python
print(op('/local/mcp_server'))
```

- [ ] **Step 3: Test staleness detection**

In terminal, touch a source file to make it newer than the TOX:
```bash
touch ~/.tdpilot/td_component/mcp_webserver_callbacks.py
```
Restart TD. Textport should show `[TDPilot] Rebuilding from source...`

- [ ] **Step 4: Test uninstall**

In terminal: `node npm/run.js uninstall`

Verify:
- `~/.tdpilot_path` is removed
- `~/Documents/Derivative/Startup/tdpilot_startup.py` is removed
- Restart TD -- no TDPilot messages in Textport

- [ ] **Step 5: Test idempotent uninstall**

Run again: `node npm/run.js uninstall`
Expected: `[TDPilot] Nothing to uninstall` message, no errors.

### Task 6: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add auto-load entry to CHANGELOG**

Add under the latest version heading (or create a new unreleased section):

```markdown
### Added
- Auto-load on TD startup: `npx tdpilot install` sets up TDPilot to load automatically every time TouchDesigner launches. Run `npx tdpilot uninstall` to remove.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add auto-load feature to CHANGELOG"
```

### Task 7: Note derived artifacts

**Per CLAUDE.md mandatory checklist:**

- [ ] **Step 1: Check if `tdpilot.plugin` needs rebuilding**

Since `td_component/tdpilot_startup.py` is a new file under `td_component/`, the `tdpilot.plugin` ZIP is now stale. Rebuild it before pushing. The `.tox` does NOT need rebuilding (the startup script is not embedded in the TOX -- it lives in TD's Startup folder).

- [ ] **Step 2: Rebuild plugin ZIP if needed**

Follow the project's existing plugin rebuild process. This is a packaging step, not a code change.
