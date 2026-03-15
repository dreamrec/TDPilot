# TDPilot Brain Installer — Design Spec

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan.

**Goal:** Build a modular, dynamic brain installation system that lets users select which knowledge brains to install, with everything adapting at runtime so only selected brains are active — no errors, no dead tools, no broken skills.

**Two-repo split:**
- **TDPilot (public)** — No brains bundled. Clean docs + generic build scripts for "build your own brain."
- **TDPilot-Dreamrec (private)** — One-click shell installer with interactive brain picker, Google Drive hosting, brain manifest.

**Architecture:** A `brains_manifest.json` on Google Drive is the single source of truth for available brains. The installer fetches it, presents a picker, downloads selected brains, and writes `active.json`. At runtime, TDPilot reads `active.json` and only registers tools/skills for active brains. Missing brains = silent skip, zero errors.

---

## 1. Brain Registry — `brains_manifest.json`

### 1.1 Schema

```json
{
  "version": 1,
  "drive_folder": "https://drive.google.com/drive/folders/1lc1S6NBQgpAzA2G2KsHkR0gV7_SdzseO",
  "brains": {
    "<brain_id>": {
      "display_name": "Human-Readable Name",
      "description": "One-line description of what this brain covers",
      "version": "YYYY.MM or semver",
      "size_mb": 164,
      "chunks": 25887,
      "skills": ["skill-id-1"],
      "tools": ["td_tool_name_1", "td_tool_name_2"],
      "files": [
        {
          "name": "filename.db",
          "drive_id": "Google_Drive_File_ID",
          "size_mb": 164
        }
      ]
    }
  }
}
```

### 1.2 Current brains

| brain_id | display_name | size | chunks | skills | key tools |
|----------|-------------|------|--------|--------|-----------|
| `derivative` | TouchDesigner Docs | 164 MB | 25,887 | tdpilot-core | td_search_docs, td_get_operator_doc, td_get_release_delta, td_get_build_compatibility |
| `popx` | POPx Operators | 1.3 MB | 480 | popx-touchdesigner | td_search_popx, td_get_popx_operator |

### 1.3 Where it lives

- **Source of truth:** `TDPilot-Dreamrec/brains_manifest.json` (committed)
- **Google Drive copy:** Uploaded alongside brain DBs (so the shell installer can fetch without repo access)
- **Local copy:** Written to `~/.tdpilot/data/brains/manifest.json` during install (runtime reference)

### 1.4 Adding a new brain

1. Build the brain DB (see Section 5)
2. Upload `.db` + any sidecar files to Google Drive shared folder
3. Get the Drive file IDs
4. Add entry to `brains_manifest.json`
5. Push to Dreamrec repo
6. Re-upload `brains_manifest.json` to Google Drive

---

## 2. Runtime Adaptation — `active.json`

### 2.1 Schema

```json
{
  "installed_brains": ["derivative", "popx"],
  "installed_at": "2026-03-15T14:30:00Z",
  "manifest_version": 1
}
```

**Location:** `~/.tdpilot/data/brains/active.json` (also `data/brains/active.json` relative to project root if running from source).

### 2.2 How TDPilot uses it at startup

#### MCP tool registration

The server reads `active.json`. For each brain NOT listed, its associated tools are never registered via `@mcp.tool()`. A user with only `popx` installed never sees `td_search_docs` — the tool simply doesn't exist in their session.

**Implementation approach in `server.py`:**

```python
def _get_active_brains() -> set[str] | None:
    """Return set of active brain IDs, or None if no active.json (load all)."""
    for candidate in [
        Path.home() / ".tdpilot" / "data" / "brains" / "active.json",
        Path(__file__).parent.parent.parent / "data" / "brains" / "active.json",
    ]:
        if candidate.exists():
            data = json.loads(candidate.read_text())
            return set(data.get("installed_brains", []))
    return None  # No active.json = load everything available


# At registration time:
active = _get_active_brains()

if active is None or "derivative" in active:
    @mcp.tool()
    def td_search_docs(...): ...

if active is None or "popx" in active:
    @mcp.tool()
    def td_search_popx(...): ...
```

#### DocsBrain loader

Already checks if `.db` file exists before loading. `active.json` becomes the primary gate; file-existence is the safety fallback.

#### Skill filtering

The `tdpilot.plugin` ZIP ships all skills (simpler distribution). Skills that reference tools for missing brains are silently inert — the tool doesn't exist, so the skill never fires. No per-install plugin rebuilding needed.

### 2.3 Backwards compatibility

**No `active.json` = load everything available.** If someone installs manually without the Dreamrec installer, TDPilot scans for any `.db` files and loads what it finds. Current behavior is fully preserved.

---

## 3. Shell Installer (TDPilot-Dreamrec)

### 3.1 User experience

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/dreamrec/TDPilot-Dreamrec/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/dreamrec/TDPilot-Dreamrec/main/install.ps1 | iex
```

### 3.2 Installer flow (5 steps)

```
═══════════════════════════════════════════════
  TDPilot Installer
═══════════════════════════════════════════════

[1/5] Checking prerequisites...
  ✓ Python 3.10+
  ✓ Node.js 16+
  ✓ git
  ✗ uv → installing...  ✓ installed

[2/5] Installing TDPilot...
  Cloning to ~/.tdpilot... done

[3/5] Select brains to install:

  Available brains (fetched from Google Drive):

  #  Brain                Size     Description
  ── ──────────────────── ──────── ──────────────────────────────────────
  1  TouchDesigner Docs   164 MB   Official docs — operators, Python, release notes
  2  POPx Operators       1.3 MB   POPx GPU particles — 59 operators, 54 examples
  3  Paketas              12 MB    Paketas workflow library
  4  Elektronaut          8 MB     Community knowledge base

  Enter brain numbers (comma-separated), or 'all':
  > 1,2

  Downloading TouchDesigner Docs (164 MB)...  ✓
  Downloading POPx Operators (1.3 MB)...  ✓

[4/5] Configuring TDPilot for selected brains...
  ✓ active.json written (2 brains)
  ✓ MCP config generated
  ✓ Plugin configured

[5/5] TouchDesigner integration (optional)
  Set up auto-load on TD startup? [y/N]: y
  ✓ TD preferences updated

═══════════════════════════════════════════════
  Done! TDPilot installed with 2 brains.

  Start the MCP server:  npx tdpilot
  Manage brains later:   npx tdpilot brains
═══════════════════════════════════════════════
```

### 3.3 Platform variants

| | macOS / Linux | Windows |
|---|---|---|
| Script | `install.sh` (bash) | `install.ps1` (PowerShell) |
| One-liner | `curl -fsSL ... \| bash` | `irm ... \| iex` |
| Install path | `~/.tdpilot` | `%USERPROFILE%\.tdpilot` |
| uv install | `curl \| sh` | `irm \| iex` |
| Logic | Identical 5-step flow | Same, PowerShell syntax |

### 3.4 `install.sh` structure

```bash
#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.tdpilot"
MANIFEST_URL="https://drive.google.com/uc?export=download&id=MANIFEST_FILE_ID"
REPO_URL="https://github.com/dreamrec/TDPilot.git"

# ── Step 1: Prerequisites ──────────────────────
check_prereqs() {
    check_python    # >= 3.10
    check_node      # >= 16
    check_git
    check_or_install_uv
}

# ── Step 2: Clone/update TDPilot ────────────────
install_tdpilot() {
    if [ -d "$INSTALL_DIR" ]; then
        git -C "$INSTALL_DIR" pull
    else
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
}

# ── Step 3: Brain picker ───────────────────────
select_brains() {
    # Download manifest
    curl -fsSL "$MANIFEST_URL" -o /tmp/brains_manifest.json

    # Parse and display with Python (guaranteed available from step 1)
    python3 - <<'PICKER'
import json, sys

manifest = json.load(open("/tmp/brains_manifest.json"))
brains = manifest["brains"]
keys = list(brains.keys())

print("\n  Available brains:\n")
print(f"  {'#':<4} {'Brain':<22} {'Size':<10} Description")
print(f"  {'──':<4} {'─'*20:<22} {'─'*8:<10} {'─'*38}")

for i, key in enumerate(keys, 1):
    b = brains[key]
    print(f"  {i:<4} {b['display_name']:<22} {b['size_mb']:<8.0f} MB {b['description']}")

print()
choice = input("  Enter brain numbers (comma-separated), or 'all': ").strip()

if choice.lower() == 'all':
    selected = keys
else:
    indices = [int(x.strip()) - 1 for x in choice.split(",")]
    selected = [keys[i] for i in indices if 0 <= i < len(keys)]

# Write selection to temp file for bash to read
with open("/tmp/selected_brains.json", "w") as f:
    json.dump(selected, f)

print(f"\n  Selected: {', '.join(selected)}")
PICKER
}

# ── Step 4: Download & configure ────────────────
download_and_configure() {
    # Download selected brains using the existing download script
    python3 "$INSTALL_DIR/scripts/download_brains.py" \
        --brains-file /tmp/selected_brains.json

    # Write active.json
    python3 - <<'CONFIGURE'
import json
from datetime import datetime, timezone

selected = json.load(open("/tmp/selected_brains.json"))
active = {
    "installed_brains": selected,
    "installed_at": datetime.now(timezone.utc).isoformat(),
    "manifest_version": 1
}

active_path = "$INSTALL_DIR/data/brains/active.json"
import os; os.makedirs(os.path.dirname(active_path), exist_ok=True)
with open(active_path, "w") as f:
    json.dump(active, f, indent=2)
print(f"  ✓ active.json written ({len(selected)} brains)")
CONFIGURE
}

# ── Step 5: TD integration (optional) ──────────
setup_td_integration() {
    read -p "  Set up auto-load on TD startup? [y/N]: " yn
    if [[ "$yn" =~ ^[Yy]$ ]]; then
        node "$INSTALL_DIR/npm/run.js" install
    fi
}

# ── Main ────────────────────────────────────────
main() {
    echo "═══════════════════════════════════════════════"
    echo "  TDPilot Installer"
    echo "═══════════════════════════════════════════════"
    echo
    echo "[1/5] Checking prerequisites..."
    check_prereqs
    echo
    echo "[2/5] Installing TDPilot..."
    install_tdpilot
    echo
    echo "[3/5] Select brains to install:"
    select_brains
    echo
    echo "[4/5] Configuring TDPilot..."
    download_and_configure
    echo
    echo "[5/5] TouchDesigner integration (optional)"
    setup_td_integration
    echo
    echo "═══════════════════════════════════════════════"
    echo "  Done! Start TDPilot: npx tdpilot"
    echo "  Manage brains:       npx tdpilot brains"
    echo "═══════════════════════════════════════════════"
}

main "$@"
```

### 3.5 Post-install brain management

Added as `npx tdpilot brains` subcommand in `npm/run.js`:

```
npx tdpilot brains              # show installed brains
npx tdpilot brains --list       # show all available from Drive
npx tdpilot brains --add popx   # download and activate a brain
npx tdpilot brains --remove popx  # deactivate (optionally delete .db)
```

**Implementation:** A new `brains.js` module in `npm/` that reads `active.json`, fetches the manifest from Drive when needed, and updates both.

---

## 4. Public Repo — Documentation & Build Scripts

### 4.1 `docs/BUILDING_BRAINS.md`

Complete tutorial covering:

1. **What is a brain** — SQLite FTS5 database built from scraped documentation
2. **Architecture** — `Source HTML → Normalizer → Chunker → FTS5 Indexer → brain.db`
3. **Step-by-step: Scrape a website** — wget/httrack examples with docs.derivative.ca as reference
4. **Create a brain config** — Full `data/brains/<name>.yaml` template with all fields explained
5. **Run the build script** — `python scripts/build_brain.py --config ... --source ...`
6. **Register the brain** — Add to `active.json`, restart TDPilot
7. **Verify** — SQL query to check chunk count
8. **Legal notes** — Personal use scraping, fair use, don't redistribute copyrighted content

### 4.2 `scripts/build_brain.py` — Generic brain builder

New script that reads any `data/brains/*.yaml` config and runs the pipeline:

```python
def build_brain(config_path: Path, source_dir: Path, refs_dir: Path | None = None):
    """Generic brain builder.

    Reads a YAML config that defines:
    - content_selector: CSS selector for main content
    - strip_selectors: elements to remove
    - page_rules: per-URL chunking strategy

    Runs the pipeline:
    1. Normalize HTML (extract content, strip noise)
    2. Chunk by sections/headings
    3. Build FTS5 index
    4. Optionally ingest structured refs (catalog.json, markdown)
    """
```

This is the script I'll use in future sessions to build new brains. It generalizes the existing `build_docs_brain.py` and `build_popx_brain.py` patterns.

### 4.3 Existing scripts stay

- `scripts/build_docs_brain.py` — Specialized derivative brain builder (stays, well-tested)
- `scripts/build_popx_brain.py` — Specialized POPx brain builder (stays, well-tested)
- `scripts/build_brain.py` — New generic builder for future brains
- `scripts/download_brains.py` — Stays. Updated to support `--brains-file` flag for installer integration.

---

## 5. How to Create a New Brain — Complete Guide

This section is the reference for building any new brain in future sessions.

### 5.1 Prerequisites

- Python 3.10+ with `beautifulsoup4`
- A scraped copy of the source website (offline HTML mirror)
- Optionally: structured reference data (catalog.json, markdown files)

### 5.2 Step 1 — Scrape the source

```bash
# Example: scrape paketas.com
wget --mirror --convert-links --page-requisites \
     --no-parent --reject "*.js,*.css,*.png,*.jpg,*.gif,*.svg" \
     -P ./scraped https://paketas.com/docs/

# Or use httrack:
httrack https://paketas.com/docs/ -O ./scraped
```

**Important:** Inspect the scraped output. Open a few `.html` files in a browser to verify content is captured. Note the CSS selector for the main content area — you'll need it for the config.

### 5.3 Step 2 — Analyze the HTML structure

Open a representative page in a browser's DevTools. Identify:

1. **Content selector** — The CSS selector that wraps the main article text. Examples:
   - `div.main-content` (POPx)
   - `div#mw-content-text` (MediaWiki / docs.derivative.ca)
   - `article.docs-content` (common pattern)
   - `main` (semantic HTML)

2. **Strip selectors** — Elements within the content area to remove:
   - Navigation: `nav`, `.sidebar`, `.breadcrumbs`
   - UI chrome: `.edit-link`, `.page-actions`, `.toc`
   - Footer: `footer`, `.page-footer`

3. **Page types** — Different URL patterns may need different chunking:
   - `/operators/` → one chunk per operator, extract params
   - `/reference/` → chunk by `<h2>` sections
   - `/tutorials/` → chunk by `<h3>` subsections

### 5.4 Step 3 — Create the brain config

Create `data/brains/<brain_id>.yaml`:

```yaml
name: paketas
display_name: "Paketas Workflows"
source_url: https://paketas.com
version: "2026.03"

# HTML extraction
content_selector: "div.main-content"
strip_selectors:
  - "nav"
  - "footer"
  - ".sidebar"
  - ".breadcrumbs"
  - "script"
  - "style"

# URL-based page rules
page_rules:
  - pattern: "/operators/"
    type: operator
    chunk_by: section          # one chunk per <section> or <h2>
    extract_params: true       # look for structured parameter tables/divs
  - pattern: "/examples/"
    type: example
    chunk_by: page             # one chunk per page
  - pattern: "/guides/"
    type: guide
    chunk_by: heading          # split on <h2> and <h3>
  - pattern: "/"
    type: general
    chunk_by: heading

# FTS5 column weights (BM25 ranking)
weights:
  section_title: 10
  operator_name: 8
  parameter_names: 5
  python_symbols: 3
  content: 1

# Optional: structured refs directory
# refs_format: catalog_json    # expects catalog.json with docs/examples arrays
# refs_format: markdown        # expects *.md files
```

### 5.5 Step 4 — Build the brain

```bash
cd /path/to/TDPilot-main

# Generic builder:
python scripts/build_brain.py \
  --config data/brains/paketas.yaml \
  --source ./scraped/paketas.com/

# With additional structured refs:
python scripts/build_brain.py \
  --config data/brains/paketas.yaml \
  --source ./scraped/paketas.com/ \
  --refs /path/to/paketas-refs/

# Expected output:
# Stage 1: Normalizing HTML files → N pages
# Stage 2: Chunking pages → N chunks
# Stage 3: Building FTS5 index → N chunks indexed
# Done → data/normalized/paketas/paketas_brain.db
```

### 5.6 Step 5 — Verify the brain

```bash
python3 -c "
import sqlite3
db = sqlite3.connect('data/normalized/paketas/paketas_brain.db')
count = db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
print(f'Chunks: {count}')

# Sample a few chunks
for row in db.execute('SELECT url, section_title FROM chunks LIMIT 5'):
    print(f'  {row[0]} — {row[1]}')
db.close()
"
```

### 5.7 Step 6 — Register for runtime

Add to `data/brains/active.json`:
```json
{"installed_brains": ["derivative", "popx", "paketas"]}
```

### 5.8 Step 7 — Upload to Google Drive (Dreamrec only)

```bash
# Copy to Drive mount
cp data/normalized/paketas/paketas_brain.db \
   ~/Library/CloudStorage/GoogleDrive-*/My\ Drive/TDPilot\ Brains/

# Get the Drive file ID after sync (from the Drive web UI)
# Add entry to brains_manifest.json
```

### 5.9 Step 8 — Register brain tools in server.py

For each new brain, add a tool registration block:

```python
if active is None or "paketas" in active:
    brain_paketas = DocsBrain("data/normalized/paketas/paketas_brain.db")

    @mcp.tool()
    def td_search_paketas(query: str, limit: int = 10) -> str:
        """Search Paketas workflow documentation."""
        return brain_paketas.search(query, limit)
```

### 5.9 FTS5 database schema (reference)

Every brain uses the same schema:

```sql
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    url TEXT,
    page_title TEXT,
    section_title TEXT,
    content TEXT,
    chunk_type TEXT,          -- 'operator', 'example', 'guide', 'general'
    operator_name TEXT,       -- NULL if not an operator page
    parameter_names TEXT,     -- comma-separated param names
    python_symbols TEXT,      -- comma-separated class/method names
    source TEXT               -- 'html', 'catalog', 'markdown'
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    section_title,
    operator_name,
    parameter_names,
    python_symbols,
    content,
    content=''               -- contentless, JOIN on rowid
);
```

---

## 6. File Changes Summary

### TDPilot (public repo)

| File | Action | Purpose |
|---|---|---|
| `scripts/build_brain.py` | Create | Generic brain builder from YAML config |
| `docs/BUILDING_BRAINS.md` | Create | Complete "build your own brain" tutorial |
| `src/td_mcp/server.py` | Modify | Read `active.json`, conditionally register brain tools |
| `src/td_mcp/knowledge/docsbrain/` | Modify | Add `active.json` gate before brain loading |
| `data/brains/active.json` | Create (gitignored) | Runtime list of installed brains |
| `scripts/download_brains.py` | Modify | Support `--brains-file` flag for installer |
| `npm/run.js` | Modify | Add `brains` subcommand |
| `npm/brains.js` | Create | Brain management CLI (list, add, remove) |
| `.gitignore` | Modify | Add `data/brains/active.json` |

### TDPilot-Dreamrec (private repo)

| File | Action | Purpose |
|---|---|---|
| `brains_manifest.json` | Create | Master registry of all brains + Drive IDs |
| `install.sh` | Create | macOS/Linux one-click installer |
| `install.ps1` | Create | Windows one-click installer |
| `install_brains.py` | Modify | Support manifest-driven interactive selection |
| `upload_brains.py` | Modify | Also upload `brains_manifest.json` |
| `README.md` | Modify | One-liner install instructions |

### Unchanged

- **`tdpilot.plugin`** — Ships all skills, inert without matching brain
- **`.tox`** — Same binary regardless of brains
- **`build_docs_brain.py`** — Stays as-is (specialized derivative builder)
- **`build_popx_brain.py`** — Stays as-is (specialized POPx builder)

---

## 7. Dependency Flow

```
brains_manifest.json (Dreamrec repo + Google Drive)
        │
        ▼
install.sh / install.ps1 fetches manifest
        │
        ▼
User picks brains from numbered list
        │
        ▼
Downloads selected .db files from Google Drive
        │
        ▼
Writes active.json with selected brain IDs
        │
        ▼
TDPilot server.py reads active.json at startup
        │
        ▼
Only registers @mcp.tool() for active brains
        │
        ▼
Skills in tdpilot.plugin reference tools
  └─ tool exists → skill works
  └─ tool missing → skill silently inert
```

---

## 8. Error Scenarios & Handling

| Scenario | Behavior |
|----------|----------|
| No `active.json` exists | Load all available brains (backwards compatible) |
| `active.json` lists brain but `.db` missing | Skip silently, log warning |
| Brain `.db` is corrupt | DocsBrain loader catches SQLite error, falls back to JSON knowledge cards |
| Google Drive download fails mid-install | Installer retries once, then reports which brains failed |
| User runs `npx tdpilot brains --add X` for unknown brain | Fetches fresh manifest, shows available options |
| Manifest on Drive is outdated vs repo | Installer always fetches fresh from Drive URL |
| Friend has no GitHub access | Only needs the `curl | bash` one-liner — no repo access needed |
