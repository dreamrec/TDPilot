# Brain Installer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular brain installation system with dynamic manifest, interactive brain picker, runtime adaptation via `active.json`, and shell installers for cross-platform one-click setup.

**Architecture:** `brains_manifest.json` (Google Drive + Dreamrec repo) is the source of truth for available brains. The installer fetches it, presents a picker, downloads selected brains, and writes `active.json`. At startup, TDPilot reads `active.json` and only registers tools for active brains. No `active.json` = backwards-compatible (load everything).

**Tech Stack:** Python 3.10+ (brain tools, download script), Node.js 16+ (brains CLI), Bash/PowerShell (installers), SQLite FTS5 (brain DBs)

**Spec:** `docs/superpowers/specs/2026-03-15-brain-installer-design.md`

---

## Chunk 1: Runtime Adaptation

### Task 1: Add `active.json` support to brain loading

**Files:**
- Modify: `src/td_mcp/tool_registry.py:302-325` (lifespan brain loading)
- Modify: `.gitignore`
- Test: `tests/test_active_brains.py`

This is the most critical task — it gates which brain tools get loaded based on `active.json`.

- [ ] **Step 1: Write the test file**

Create `tests/test_active_brains.py`:

```python
"""Tests for active.json brain gating."""

import json
import tempfile
from pathlib import Path

import pytest


def _write_active(tmp: Path, brains: list[str]) -> Path:
    """Write an active.json file and return its path."""
    active_path = tmp / "data" / "brains" / "active.json"
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(json.dumps({
        "installed_brains": brains,
        "installed_at": "2026-03-15T00:00:00Z",
        "manifest_version": 1,
    }))
    return active_path


def test_get_active_brains_returns_none_when_no_file():
    """No active.json = None = load everything."""
    from td_mcp.tool_registry import _get_active_brains
    with tempfile.TemporaryDirectory() as tmp:
        result = _get_active_brains(search_paths=[Path(tmp) / "nonexistent"])
    assert result is None


def test_get_active_brains_returns_set_from_file():
    """active.json with brains returns a set."""
    from td_mcp.tool_registry import _get_active_brains
    with tempfile.TemporaryDirectory() as tmp:
        active_path = _write_active(Path(tmp), ["derivative", "popx"])
        result = _get_active_brains(search_paths=[active_path])
    assert result == {"derivative", "popx"}


def test_get_active_brains_empty_list():
    """active.json with empty list = no brains."""
    from td_mcp.tool_registry import _get_active_brains
    with tempfile.TemporaryDirectory() as tmp:
        active_path = _write_active(Path(tmp), [])
        result = _get_active_brains(search_paths=[active_path])
    assert result == set()


def test_get_active_brains_corrupt_json_returns_none():
    """Corrupt active.json = graceful fallback to None."""
    from td_mcp.tool_registry import _get_active_brains
    with tempfile.TemporaryDirectory() as tmp:
        active_path = Path(tmp) / "data" / "brains" / "active.json"
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text("NOT JSON")
        result = _get_active_brains(search_paths=[active_path])
    assert result is None


def test_brain_is_active_helper():
    """brain_is_active() returns True when brain is in active set or active is None."""
    from td_mcp.tool_registry import brain_is_active
    assert brain_is_active(None, "derivative") is True
    assert brain_is_active({"derivative"}, "derivative") is True
    assert brain_is_active({"derivative"}, "popx") is False
    assert brain_is_active(set(), "derivative") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_active_brains.py -v`
Expected: FAIL — `_get_active_brains` and `brain_is_active` don't exist yet

- [ ] **Step 3: Implement `_get_active_brains` and `brain_is_active` in tool_registry.py**

Add near the top of `tool_registry.py` (after imports, before `server_lifespan`):

```python
def _get_active_brains(search_paths: list[Path] | None = None) -> set[str] | None:
    """Return set of active brain IDs, or None if no active.json (load all).

    Checks paths in order:
    1. ~/.tdpilot/data/brains/active.json (installer path)
    2. <project-root>/data/brains/active.json (dev path)

    Returns None if no active.json found — caller should load all available brains.
    """
    if search_paths is None:
        search_paths = [
            Path.home() / ".tdpilot" / "data" / "brains" / "active.json",
            Path(__file__).resolve().parent.parent.parent / "data" / "brains" / "active.json",
        ]
    for candidate in search_paths:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text("utf-8"))
                return set(data.get("installed_brains", []))
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt active.json at %s, ignoring", candidate)
                return None
    return None


def brain_is_active(active_set: set[str] | None, brain_id: str) -> bool:
    """Check if a brain should be loaded. None means all brains are active."""
    if active_set is None:
        return True
    return brain_id in active_set
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_active_brains.py -v`
Expected: 5 passed

- [ ] **Step 5: Wire `_get_active_brains` into `server_lifespan`**

In `tool_registry.py`, find the `# Knowledge corpus` section (~line 302). Add active brains check:

Find:
```python
    # Knowledge corpus
    card_index = None
    try:
        from td_mcp.knowledge.docsbrain import DocsBrain
        brain_dir = Path(__file__).resolve().parent.parent.parent / "data" / "normalized" / "derivative"
        db_path = brain_dir / "docsbrain.db"
        if db_path.exists():
```

Replace with:
```python
    # Knowledge corpus — gated by active.json
    active_brains = _get_active_brains()
    card_index = None
    if brain_is_active(active_brains, "derivative"):
        try:
            from td_mcp.knowledge.docsbrain import DocsBrain
            brain_dir = Path(__file__).resolve().parent.parent.parent / "data" / "normalized" / "derivative"
            db_path = brain_dir / "docsbrain.db"
            if db_path.exists():
```

The rest of the block stays unchanged.

- [ ] **Step 6: Add `data/brains/active.json` and `data/normalized/` to `.gitignore`**

Append to `.gitignore`:
```
# Brain runtime config (generated by installer, not tracked)
data/brains/active.json
data/normalized/
```

- [ ] **Step 7: Run full test suite**

Run: `cd <REPO_ROOT> && python -m pytest tests/ -x -q`
Expected: All pass (no regressions — `active_brains` returns None without file, so everything loads as before)

- [ ] **Step 8: Commit**

```bash
git add tests/test_active_brains.py src/td_mcp/tool_registry.py .gitignore
git commit -m "feat: add active.json brain gating for conditional tool registration"
```

---

### Task 2: POPx brain MCP tools

**Files:**
- Modify: `src/td_mcp/tool_registry.py` (add POPx tool section after derivative tools)
- Modify: `src/td_mcp/services.py` (add `popx_brain` field)
- Test: `tests/test_popx_brain_tools.py`

The POPx brain DB exists (`data/normalized/popx/popxbrain.db`) but has no MCP tools yet.

- [ ] **Step 1: Write the test**

Create `tests/test_popx_brain_tools.py`:

```python
"""Tests for POPx brain — DocsBrain can read POPx FTS5 databases."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


def _create_test_popx_db(tmp_dir: Path) -> Path:
    """Create a minimal POPx brain DB for testing."""
    db_path = tmp_dir / "popxbrain.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY, url TEXT, page_title TEXT, section_title TEXT,
            content TEXT, doc_type TEXT, chunk_type TEXT, operator_name TEXT,
            operator_family TEXT, parameter_names TEXT DEFAULT '[]',
            python_symbols TEXT DEFAULT '[]', mentioned_operators TEXT DEFAULT '[]',
            build_number TEXT, build_date TEXT, change_category TEXT, source TEXT DEFAULT 'html'
        );
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            section_title, operator_name, parameter_names, python_symbols, content, content=''
        );
        INSERT INTO chunks (url, page_title, section_title, content, doc_type, chunk_type, operator_name, operator_family)
        VALUES ('https://popsextension.com/particle', 'Particle', 'Overview',
                'GPU particle simulation with SPH, PBF, Grains modes', 'operator', 'operator', 'Particle SIM', 'SIM');
        INSERT INTO chunks_fts (rowid, section_title, operator_name, parameter_names, python_symbols, content)
        VALUES (1, 'Overview', 'Particle SIM', '[]', '[]', 'GPU particle simulation with SPH, PBF, Grains modes');
    """)
    conn.close()
    return db_path


def test_popx_brain_search():
    from td_mcp.knowledge.docsbrain import DocsBrain
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _create_test_popx_db(Path(tmp))
        brain = DocsBrain(db_path=db_path)
        results = brain.search("particle simulation")
        assert len(results) >= 1
        assert "particle" in results[0]["content"].lower()


def test_popx_brain_count():
    from td_mcp.knowledge.docsbrain import DocsBrain
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _create_test_popx_db(Path(tmp))
        brain = DocsBrain(db_path=db_path)
        assert brain.count() == 1
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/test_popx_brain_tools.py -v`
Expected: PASS (DocsBrain is generic)

- [ ] **Step 3: Add `popx_brain` to ServiceContainer**

In `src/td_mcp/services.py`, add after `card_index`:
```python
    popx_brain: Optional[DocsBrain] = None
```

- [ ] **Step 4: Add POPx brain loading to `server_lifespan`**

After the derivative brain block in `tool_registry.py`, add:

```python
    # POPx brain — loaded only if active
    popx_brain = None
    if brain_is_active(active_brains, "popx"):
        try:
            from td_mcp.knowledge.docsbrain import DocsBrain as PopxBrain
            popx_dir = Path(__file__).resolve().parent.parent.parent / "data" / "normalized" / "popx"
            popx_db = popx_dir / "popxbrain.db"
            if popx_db.exists():
                popx_brain = PopxBrain(
                    db_path=popx_db,
                    changelog_path=popx_dir / "operator_changelog.json",
                    manifest_path=popx_dir / "build_manifest.json",
                )
                logger.info("POPx brain loaded (%d chunks)", popx_brain.count())
        except Exception as exc:
            logger.debug("POPx brain not available: %s", exc)
```

Add `popx_brain=popx_brain` to the `ServiceContainer(...)` constructor call.

- [ ] **Step 5: Add POPx MCP tools**

After the derivative brain tools (after `td_get_build_compatibility` ~line 3738):

```python
# ── POPx Brain Tools ─────────────────────────────────────────────────


def _get_popx_brain(ctx: Context):
    svc = _get_services(ctx)
    brain = getattr(svc, "popx_brain", None)
    if brain is None:
        raise RuntimeError("POPx brain not loaded")
    return brain


@mcp.tool(name="td_search_popx_docs")
async def td_search_popx_docs(
    ctx: Context,
    query: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """Search POPx operator documentation — GPU particles, falloffs, simulations."""
    brain = _get_popx_brain(ctx)
    results = brain.search(query, limit=limit)
    svc = _get_services(ctx)
    provenance = Provenance(source="popx_brain", td_build=svc.td_build)
    return {"results": results, "count": len(results), "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_popx_operator")
async def td_get_popx_operator(
    ctx: Context,
    operator_name: str,
) -> Dict[str, Any]:
    """Get full documentation for a POPx operator (e.g. 'Particle SIM', 'Shape Falloff')."""
    brain = _get_popx_brain(ctx)
    results = brain.search(operator_name, limit=5)
    op_results = [r for r in results if r.get("operator_name", "").lower() == operator_name.lower()]
    if not op_results:
        op_results = results
    svc = _get_services(ctx)
    provenance = Provenance(source="popx_brain", td_build=svc.td_build)
    if op_results:
        return {"operator": op_results[0], "related": op_results[1:], "provenance": provenance.to_dict()}
    return {"error": f"No POPx operator found for '{operator_name}'", "provenance": provenance.to_dict()}
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_popx_brain_tools.py tests/test_active_brains.py -v`
Expected: All pass

- [ ] **Step 7: Update tool count 88 → 90**

Update all files from CLAUDE.md's tool count list (find `88`, replace with `90`).

- [ ] **Step 8: Commit**

```bash
git add src/td_mcp/tool_registry.py src/td_mcp/services.py tests/test_popx_brain_tools.py
git commit -m "feat: add POPx brain MCP tools (td_search_popx_docs, td_get_popx_operator)"
```

---

## Chunk 2: Download Script & Brain Management CLI

### Task 3: Refactor `download_brains.py` for manifest support

**Files:**
- Modify: `scripts/download_brains.py`

- [ ] **Step 1: Read current script**

Review `scripts/download_brains.py` — understand the `BRAINS` dict, `download_brain()`, and `main()`.

- [ ] **Step 2: Add `_load_brains_from_manifest()` function**

```python
def _load_brains_from_manifest(manifest_path: Path) -> dict:
    """Load brain definitions from a manifest JSON file."""
    manifest = json.loads(manifest_path.read_text("utf-8"))
    brains = {}
    for brain_id, brain_data in manifest.get("brains", {}).items():
        brains[brain_id] = {
            "description": f"{brain_data['display_name']} — {brain_data['description']}",
            "output_dir": f"data/normalized/{brain_id}",
            "files": brain_data["files"],
        }
    return brains
```

- [ ] **Step 3: Add `--manifest` and `--brains-file` args**

```python
    parser.add_argument("--manifest", type=Path, help="Path to brains_manifest.json")
    parser.add_argument("--brains-file", type=Path, help="JSON file listing brain IDs to download")
```

- [ ] **Step 4: Update `main()` to use manifest when provided**

After parsing args:
```python
    brains_registry = BRAINS
    if args.manifest and args.manifest.exists():
        brains_registry = _load_brains_from_manifest(args.manifest)

    if args.brains_file and args.brains_file.exists():
        selected = json.loads(args.brains_file.read_text("utf-8"))
        brains_to_download = [b for b in selected if b in brains_registry]
    elif args.brain:
        brains_to_download = [args.brain]
    else:
        brains_to_download = list(brains_registry.keys())
```

Update `download_brain()` to accept optional `brains_registry` parameter.

- [ ] **Step 5: Test standalone still works**

Run: `python scripts/download_brains.py --list`
Expected: Same output as before

- [ ] **Step 6: Commit**

```bash
git add scripts/download_brains.py
git commit -m "feat: add --manifest and --brains-file flags to download_brains.py"
```

---

### Task 4: Brain management CLI (`npm/brains.js`)

**Files:**
- Create: `npm/brains.js`
- Modify: `npm/run.js`
- Modify: `npm/package.json`

- [ ] **Step 1: Create `npm/brains.js`**

Brain manager module with functions: `readActive()`, `writeActive()`, `fetchManifest()`, `showInstalled()`, `showAvailable()`, `addBrain()`, `removeBrain()`, `main()`.

Key constants:
```javascript
const INSTALL_DIR = join(os.homedir(), ".tdpilot");
const ACTIVE_PATH = join(INSTALL_DIR, "data", "brains", "active.json");
const MANIFEST_CACHE = join(INSTALL_DIR, "data", "brains", "manifest.json");
const MANIFEST_DRIVE_ID = "MANIFEST_FILE_ID"; // replace after Drive upload
```

For downloading brains, use `spawnSync` (not `execSync`) with array arguments to avoid shell injection:
```javascript
const { spawnSync } = require("child_process");
spawnSync("python3", [
  join(INSTALL_DIR, "scripts", "download_brains.py"),
  "--manifest", manifestPath,
  "--brains-file", brainsFile,
], { stdio: "inherit", cwd: INSTALL_DIR });
```

- [ ] **Step 2: Add `brains` subcommand routing in `npm/run.js`**

Before the existing `install`/`uninstall` check:
```javascript
if (subcommand === "brains") {
  const { main: brainsMain } = require("./brains");
  brainsMain(process.argv.slice(3));
  return;
}
```

- [ ] **Step 3: Update `npm/package.json`**

Add `brains.js` to the files array.

- [ ] **Step 4: Test**

Run: `node npm/run.js brains`
Expected: Shows installed brains or "no active.json" message

- [ ] **Step 5: Commit**

```bash
git add npm/brains.js npm/run.js npm/package.json
git commit -m "feat: add 'npx tdpilot brains' CLI for brain management"
```

---

## Chunk 3: Public Docs & Generic Brain Builder

### Task 5: Write `docs/BUILDING_BRAINS.md`

**Files:**
- Create: `docs/BUILDING_BRAINS.md`

- [ ] **Step 1: Write the doc**

Follow spec Sections 4.1 and 5.1–5.10. Include:
- What is a brain, architecture diagram
- Step-by-step scraping, config, building, registering, verifying
- FTS5 schema reference
- Legal notes

- [ ] **Step 2: Commit**

```bash
git add docs/BUILDING_BRAINS.md
git commit -m "docs: add complete brain building tutorial"
```

---

### Task 6: Create generic `scripts/build_brain.py`

**Files:**
- Create: `scripts/build_brain.py`

- [ ] **Step 1: Read existing builders for patterns**

Read `scripts/build_docs_brain.py` and `scripts/build_popx_brain.py`.

- [ ] **Step 2: Create the generic builder**

Config-driven pipeline: `load_config()` → `normalize_html()` → `chunk_page()` → `build_fts_index()` → optionally `ingest_refs()`.

Reads YAML config with `content_selector`, `strip_selectors`, `page_rules`. Creates output at `data/normalized/<name>/<name>_brain.db`.

Dependencies: `beautifulsoup4`, `pyyaml`.

- [ ] **Step 3: Test help output**

Run: `python scripts/build_brain.py --help`
Expected: Shows `--config`, `--source`, `--refs` flags

- [ ] **Step 4: Commit**

```bash
git add scripts/build_brain.py
git commit -m "feat: add generic config-driven brain builder"
```

---

## Chunk 4: Dreamrec Installer

### Task 7: Create `brains_manifest.json`

**Files:**
- Create: `/tmp/TDPilot-Dreamrec/brains_manifest.json`

- [ ] **Step 1: Create manifest with current 2 brains**

JSON with `version`, `drive_folder`, and entries for `derivative` and `popx` matching the Drive file IDs from `scripts/download_brains.py`.

- [ ] **Step 2: Commit**

```bash
cd /tmp/TDPilot-Dreamrec && git add brains_manifest.json && git commit -m "feat: add brains manifest"
```

---

### Task 8: Create `install.sh`

**Files:**
- Create: `/tmp/TDPilot-Dreamrec/install.sh`

- [ ] **Step 1: Write the installer**

5-step flow from spec Section 3.4:
1. `check_prereqs()` — Python 3.10+, Node 16+, git, uv
2. `install_tdpilot()` — clone/pull to `~/.tdpilot`
3. `select_brains()` — fetch manifest, Python picker in heredoc
4. `download_and_configure()` — call `download_brains.py`, write `active.json`
5. `setup_td_integration()` — optional TD auto-load

Use `INSTALL_DIR` env var for Python heredocs. `chmod +x`.

- [ ] **Step 2: Test locally**

Run: `bash /tmp/TDPilot-Dreamrec/install.sh`

- [ ] **Step 3: Commit**

```bash
cd /tmp/TDPilot-Dreamrec && chmod +x install.sh && git add install.sh && git commit -m "feat: add macOS/Linux installer"
```

---

### Task 9: Create `install.ps1`

**Files:**
- Create: `/tmp/TDPilot-Dreamrec/install.ps1`

- [ ] **Step 1: Write the PowerShell installer**

Same 5-step flow, PowerShell syntax. `$INSTALL_DIR = "$env:USERPROFILE\.tdpilot"`.

- [ ] **Step 2: Commit**

```bash
cd /tmp/TDPilot-Dreamrec && git add install.ps1 && git commit -m "feat: add Windows PowerShell installer"
```

---

### Task 10: Update Dreamrec README + upload script

**Files:**
- Modify: `/tmp/TDPilot-Dreamrec/README.md`
- Modify: `/tmp/TDPilot-Dreamrec/upload_brains.py`

- [ ] **Step 1: Add one-click install section to README**
- [ ] **Step 2: Update `upload_brains.py` to also upload manifest**
- [ ] **Step 3: Commit and push**

```bash
cd /tmp/TDPilot-Dreamrec && git add README.md upload_brains.py && git commit -m "feat: one-click install docs, manifest upload" && git push
```

---

### Task 11: Upload manifest to Google Drive (manual)

- [ ] **Step 1: Copy `brains_manifest.json` to Drive mount**
- [ ] **Step 2: Get Drive file ID after sync**
- [ ] **Step 3: Update `MANIFEST_FILE_ID` placeholder in `install.sh`, `install.ps1`, `npm/brains.js`**
- [ ] **Step 4: Commit ID updates in both repos**

---

## Chunk 5: Final Integration

### Task 12: CHANGELOG + push

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add v1.3.4 entry**

```markdown
## [1.3.4] - 2026-03-15

### Added
- Brain installer system with dynamic manifest and interactive picker
- POPx brain MCP tools: td_search_popx_docs, td_get_popx_operator (90 tools)
- Brain management CLI: npx tdpilot brains
- Generic brain builder: scripts/build_brain.py
- Brain building tutorial: docs/BUILDING_BRAINS.md
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -x -q`

- [ ] **Step 3: Commit and push**

---

## Build Sequence

| Task | What | Depends On |
|------|------|-----------|
| 1 | `active.json` + brain gating | — |
| 2 | POPx brain MCP tools | Task 1 |
| 3 | `download_brains.py` manifest support | — |
| 4 | `npm/brains.js` CLI | Task 3 |
| 5 | `BUILDING_BRAINS.md` docs | — |
| 6 | `build_brain.py` generic builder | — |
| 7 | `brains_manifest.json` | — |
| 8 | `install.sh` | Tasks 3, 7 |
| 9 | `install.ps1` | Tasks 3, 7 |
| 10 | Dreamrec README + upload | Tasks 7, 8, 9 |
| 11 | Upload manifest to Drive | Task 10 |
| 12 | CHANGELOG + push | All |

**Parallelizable:** Tasks 1, 3, 5, 6, 7 are independent. Tasks 2, 4, 8, 9 depend on group 1. Tasks 10-12 are sequential.
