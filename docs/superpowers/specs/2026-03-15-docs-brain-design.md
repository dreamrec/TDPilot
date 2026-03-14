# Docs Brain — Design Spec

## Goal

Replace TDPilot's 30 hand-curated JSON knowledge cards with a full-corpus docs brain built from the scraped docs.derivative.ca website (3,369 HTML pages). The brain should give TDPilot accurate, searchable knowledge of every operator, Python class, palette component, glossary term, and release note — with cumulative release-notes intelligence so TDPilot always knows the current state of the user's installed TD build.

## Architecture

Three-stage offline pipeline, one runtime search interface:

```
Scrape folder (HTML)
    → Normalize (strip boilerplate, classify, extract text)
    → Chunk (split by headings, extract metadata)
    → Index (SQLite FTS5 with boosted fields)
        → DocsBrain search class (replaces CardIndex)
            → Existing MCP tools (td_search_official_docs, td_get_operator_doc, etc.)
```

Release notes get additional special processing into a build manifest and per-operator changelog.

### Key decisions

- **Search tech:** SQLite FTS5 only (zero dependencies, handles exact matches well, vector search can be layered later)
- **Data location:** `data/normalized/` inside repo, gitignored. Pipeline code versioned, generated data local.
- **Integration:** Replaces `CardIndex` entirely. Same MCP tool names, new backend. Falls back to existing cards if brain hasn't been built.
- **Build detection:** Auto-detect from live TD via `td_get_info`, fall back to assuming latest build when TD isn't running.

---

## Data Flow

### Stage 1: Normalize

**Input:** `*.html` files from the scrape folder (path configured via `TDPILOT_DOCS_SCRAPE_PATH` env var).

**Processing:**
- Extract content from `<div id="mw-content-text">`
- Strip MediaWiki chrome: nav, footer, edit links, TOC, JS/CSS, lingo tooltip spans (keep inner text)
- Skip `File:*.html` pages (image metadata), CSS/JS assets, non-HTML files

**Page classification** (from URL patterns):

| Pattern | `doc_type` |
|---------|-----------|
| `*_TOP.html`, `*_CHOP.html`, `*_SOP.html`, `*_DAT.html`, `*_COMP.html`, `*_MAT.html`, `*_POP.html` | `operator` |
| `*_Class.html`, `*Class.html` | `python_api` |
| `Release_Notes/*.html` | `release_notes` |
| `Palette:*.html` | `palette` |
| `OP_Snippets*.html` | `snippet` |
| `*Glossary*.html` | `glossary` |
| Everything else | `general` |

**Stable page IDs:** Full transformation: strip `.html` suffix, lowercase, replace `/` with `__`, replace `.` with `_` (e.g., `Release_Notes/2025.30000` → `release_notes__2025_30000`). Collisions are theoretically possible but not present in the actual corpus.

**Error handling:** Pages that fail to parse or lack the expected `<div id="mw-content-text">` are logged as warnings and skipped.

**Output:** `data/normalized/pages.jsonl` — one JSON object per line:

```json
{
  "page_id": "composite_top",
  "url": "https://docs.derivative.ca/Composite_TOP",
  "title": "Composite TOP",
  "doc_type": "operator",
  "operator_family": "TOP",
  "headings": ["Parameters", "Inputs", "Info CHOP Channels"],
  "text": "...clean text...",
  "text_hash": "sha256:..."
}
```

### Stage 2: Chunk

**Strategy:** Split on heading boundaries (`<h2>`, `<h3>`, `<h4>`). Merge short sections (under ~100 words) with next sibling.

**Special cases:**
- **Operator pages:** Parameter tables stay as one chunk. Summary is its own chunk.
- **Release notes:** Each build section becomes a chunk. Subsections (New Features, Bug Fixes, Python, Palette, Backward Compat) become sub-chunks. Each bullet tagged with mentioned operators (parsed from `<a>` links).
- **Python class pages:** Method tables stay together. Overview separate from members.
- **Glossary:** One chunk per term definition.

**Metadata extraction per chunk:**

```json
{
  "chunk_id": "composite_top__parameters__0001",
  "page_id": "composite_top",
  "doc_type": "operator",
  "section_title": "Parameters",
  "operator_family": "TOP",
  "operator_name": "Composite TOP",
  "mentioned_operators": [],
  "parameter_names": ["operand", "opacity", "prefit"],
  "python_symbols": [],
  "build_number": null,
  "build_date": null,
  "change_category": null,
  "token_estimate": 420,
  "content": "...section text..."
}
```

Release note chunks get additional fields: `build_number`, `build_date`, `change_category` (one of: `new_feature`, `bug_fix`, `backward_compat`, `python`, `palette`, `other` for unrecognized subsections).

**Chunk ID format:** `{page_id}__{section_title_slug}__{sequence}` where sequence is a zero-padded counter resetting per page. On rebuild, IDs are regenerated deterministically from the same content.

**Token estimate:** `word_count * 1.3` (rough approximation, no external tokenizer dependency).

**Target:** 300-900 words per chunk.

**Output:** `data/normalized/chunks.jsonl`

### Stage 3: Index

**Database:** `data/normalized/docsbrain.db`

```sql
CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    page_id TEXT,
    doc_type TEXT,
    section_title TEXT,
    operator_family TEXT,
    operator_name TEXT,
    mentioned_operators TEXT,   -- JSON array
    parameter_names TEXT,       -- JSON array
    python_symbols TEXT,        -- JSON array
    build_number TEXT,
    build_date TEXT,
    change_category TEXT,
    token_estimate INTEGER,
    content TEXT
);

-- Contentless FTS5 (managed manually, avoids column-sync issues)
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_id UNINDEXED,
    section_title,
    operator_name,
    parameter_names,
    python_symbols,
    content,
    content='',
    tokenize='porter unicode61'
);

-- Schema version tracking
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
-- INSERT INTO meta VALUES ('schema_version', '1');
```

FTS5 uses `content=''` (contentless) — inserts are managed manually during indexing, avoiding column alignment issues. `DocsBrain` checks `meta.schema_version` on startup and prompts for rebuild if stale.

**Ranking weights:** section_title 10x, operator_name 8x, parameter_names 5x, python_symbols 3x, content 1x.

**Query:**
```sql
SELECT chunk_id, rank
FROM chunks_fts
WHERE chunks_fts MATCH '{section_title operator_name parameter_names}:query OR content:query'
ORDER BY bm25(chunks_fts, 10.0, 8.0, 5.0, 3.0, 1.0)
LIMIT ?
-- Then fetch full chunk data from chunks table by chunk_id
```

---

## Release Notes Intelligence

### Build manifest (`data/normalized/build_manifest.json`)

```json
{
  "latest_build": "2025.32460",
  "latest_date": "2026-03-10",
  "builds": [
    {"build": "2025.32460", "date": "2026-03-10", "note": "Hotfix for ray tracing bug"},
    {"build": "2025.32280", "date": "2025-01-20"},
    {"build": "2025.32050", "date": "2025-12-10"},
    {"build": "2025.31760", "date": "2025-11-17"},
    {"build": "2025.31550", "date": "2025-10-30"}
  ]
}
```

### Per-operator changelog (`data/normalized/operator_changelog.json`)

Every release note bullet mentioning an operator, indexed by operator name:

```json
{
  "Trail POP": [
    {
      "build": "2025.32460",
      "category": "bug_fix",
      "text": "Fixed the trail double-transforming when cooking a second time during a frame."
    }
  ],
  "Alembic In POP": [
    {
      "build": "2025.32460",
      "category": "bug_fix",
      "text": "Fixed importing of primitive UV and Normal attributes."
    },
    {
      "build": "2025.32460",
      "category": "new_feature",
      "text": "Added a new 'Load Type' parameter for delayed loading."
    }
  ]
}
```

### Runtime behavior

- `td_get_operator_doc("feedbackTOP")` → returns operator docs + "Recent changes" section from changelog
- `td_get_release_delta(build="2025.32460")` → returns that build's entries organized by category (existing tool name preserved)
- Build detection: `td_get_info` when TD is live, assume latest when offline
- When advising on an operator, the knowledge layer can flag relevant recent fixes/changes

---

## DocsBrain Public API

`DocsBrain` implements the same interface as `CardIndex` so it can be a drop-in replacement. The `ServiceContainer.card_index` field keeps its name and type becomes `Union[CardIndex, DocsBrain]`.

```python
class DocsBrain:
    def __init__(self, db_path: Path, changelog_path: Path, manifest_path: Path) -> None: ...

    # — Same interface as CardIndex —
    def count(self) -> int: ...
    def search(self, query: str, card_types: list[str] | None = None,
               family: str | None = None, limit: int = 10) -> list[dict]: ...
    def get_operator(self, op_type: str) -> dict | None: ...
    def get_palette(self, component_name: str) -> dict | None: ...
    def get_release(self, build: str) -> dict | None: ...
    def check_compatibility(self, op_type: str, current_build: str) -> dict: ...

    # — New methods (used by enhanced tool handlers) —
    def get_operator_changelog(self, operator_name: str) -> list[dict]: ...
    def get_build_manifest(self) -> dict: ...
    def search_release_notes(self, query: str, build: str | None = None, limit: int = 10) -> list[dict]: ...
```

**Return dict shapes** match existing CardIndex patterns so tool handlers don't break:
- `search()` returns list of dicts with keys: `chunk_id`, `doc_type`, `section_title`, `operator_name`, `content`, `score`
- `get_operator()` returns a dict with keys: `op_type`, `family`, `display_name`, `summary`, `parameters`, `docs_url`, `recent_changes` (new — from operator changelog)
- `get_release()` returns a dict with keys: `build`, `date`, `entries` (list of categorized changes)

**Intent routing** happens inside `search()` — callers don't need to know about it.

**Operator name lookup set:** Built during indexing as a distinct set of all `operator_name` values from the `chunks` table. Loaded into memory at `DocsBrain.__init__` for intent detection.

---

## File Structure

### New files

```
src/td_mcp/knowledge/docsbrain/
    __init__.py           # DocsBrain class — main search interface
    normalizer.py         # HTML → pages.jsonl
    chunker.py            # pages.jsonl → chunks.jsonl
    metadata.py           # doc_type classification, operator/param extraction
    release_parser.py     # Release notes parsing, operator changelog, build manifest
    indexer.py            # Build SQLite FTS5 from chunks

scripts/
    build_docs_brain.py   # CLI entry point: --config brain.yaml → full pipeline

data/
    brains/               # versioned — brain config files
        derivative.yaml   # official docs brain config
    normalized/           # gitignored — all generated output
        derivative/       # one subdirectory per brain
            pages.jsonl
            chunks.jsonl
            docsbrain.db
            build_manifest.json
            operator_changelog.json

docs/
    BRAINS.md             # User guide: what brains are, how to build them, templates

tests/
    test_normalizer.py
    test_chunker.py
    test_release_parser.py
    test_search.py
    test_integration.py
```

### Modified files

- `src/td_mcp/knowledge/__init__.py` — export `DocsBrain` alongside `CardIndex`
- `src/td_mcp/services.py` — `ServiceContainer.card_index` field keeps its name; type becomes `Union[CardIndex, DocsBrain]`. Initialization tries `DocsBrain` first (if DB exists), falls back to `CardIndex`.
- `src/td_mcp/tool_registry.py` — `_get_card_index()` helper works unchanged since `DocsBrain` implements the same interface. Tool handlers that want new features (operator changelog, release notes) call additional methods with `hasattr` checks.
- `data/.gitignore` — ignore `normalized/`

### Unchanged

- MCP tool names (no consumer-facing changes)
- Tool response envelope format
- `cards/` directory stays as fallback

---

## Intent-Based Query Routing

Before FTS5 search, classify the query to narrow scope:

| Detected intent | Filter applied |
|----------------|---------------|
| Operator name found in query | `doc_type IN ('operator', 'python_api')` |
| Build number or "what changed" | `doc_type = 'release_notes'` |
| "palette:" prefix | `doc_type = 'palette'` |
| "glossary" or definition-style | `doc_type = 'glossary'` |
| No clear intent | No filter (search all) |

Caching: LRU on normalized query → results. Invalidated on rebuild.

---

## Configuration

### Brain config files (`data/brains/*.yaml`)

Each brain is defined by a YAML config file that specifies: name, trust tier, scrape path, CSS selectors for content extraction, page classification rules, skip patterns, URL template, and optional special parsers.

See `docs/BRAINS.md` for the full config format and template.

### Environment

`TDPILOT_DOCS_SCRAPE_PATH` — convenience shorthand for the derivative brain's scrape folder. Referenced inside `data/brains/derivative.yaml` as `${TDPILOT_DOCS_SCRAPE_PATH}`. If unset, that brain is skipped; falls back to existing CardIndex.

### Multi-brain support

The pipeline and `DocsBrain` class are designed to support multiple brains from day one. Each brain gets its own subdirectory under `data/normalized/<brain_name>/` with its own `docsbrain.db`. At runtime, brains are loaded by trust tier (official → community → personal → experimental) and results are interleaved with source attribution.

**Phase 1 builds only the derivative brain.** The multi-brain loader and YAML config parser are Phase 2 work. But the single-brain architecture is designed so that adding multi-brain later is additive, not a rewrite.

---

## Build Phases

1. **Phase 1:** normalizer + chunker + metadata → `pages.jsonl` + `chunks.jsonl`
2. **Phase 2:** indexer → `docsbrain.db`
3. **Phase 3:** release_parser → `build_manifest.json` + `operator_changelog.json`
4. **Phase 4:** search replaces CardIndex, wire into services + MCP tools
5. **Phase 5:** tests + eval

---

## Incremental Refresh

When the user re-scrapes docs.derivative.ca:

1. Re-run `build_docs_brain.py`
2. Normalizer compares `text_hash` of each page against existing `pages.jsonl`
3. Only changed/new pages get re-normalized and re-chunked
4. FTS5 index rebuilt from full `chunks.jsonl` (fast — SQLite handles thousands of inserts in seconds)
5. Release manifest and operator changelog regenerated
6. LRU cache cleared

Full rebuild from scratch takes seconds for 3,369 pages. Incremental is marginally faster but the full rebuild is cheap enough that incremental is a nice-to-have, not critical.

---

## Testing Strategy

- **test_normalizer.py:** Feed sample HTML files, verify boilerplate stripping, page classification, title extraction, heading extraction, stable page IDs
- **test_chunker.py:** Feed normalized pages, verify chunk boundaries respect headings, short sections merge, parameter tables stay together, chunk sizes in range
- **test_release_parser.py:** Feed the 2025.30000 release notes page, verify build manifest has all builds with correct dates, operator changelog correctly maps bullets to operator names, change categories are correct
- **test_search.py:** Build a small test index, verify exact operator name queries rank the operator page first, parameter name queries find the right chunk, release note queries filter correctly, intent routing works
- **test_integration.py:** End-to-end test: sample HTML files → normalize → chunk → index → search → verify results. Also test the fallback path (no DB → CardIndex used instead)
