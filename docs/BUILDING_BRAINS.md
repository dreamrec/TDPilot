# Building Your Own TDPilot Brain

A **brain** is a SQLite FTS5 database that gives TDPilot searchable knowledge about a specific topic — TouchDesigner docs, POPx operators, tutorial sites, or any documentation corpus you want to make available to the AI assistant.

## Architecture

```
Scraped HTML  ──►  Normalizer  ──►  pages.jsonl  ──►  Chunker  ──►  chunks.jsonl  ──►  Indexer  ──►  brain.db (FTS5)
```

Each brain produces:
- `<name>brain.db` — SQLite database with `chunks` table + `chunks_fts` FTS5 virtual table
- `build_manifest.json` — metadata about the build (date, chunk count, etc.)
- `operator_changelog.json` — (optional) per-operator change history

## FTS5 Schema

All brains share the same schema so `DocsBrain` can search them uniformly:

```sql
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    url TEXT,
    page_title TEXT,
    section_title TEXT,
    content TEXT,
    doc_type TEXT,           -- 'operator', 'python_api', 'release_notes', 'palette', 'glossary', etc.
    chunk_type TEXT,
    operator_name TEXT,
    operator_family TEXT,
    parameter_names TEXT DEFAULT '[]',    -- JSON array
    python_symbols TEXT DEFAULT '[]',     -- JSON array
    mentioned_operators TEXT DEFAULT '[]', -- JSON array
    build_number TEXT,
    build_date TEXT,
    change_category TEXT,
    source TEXT DEFAULT 'html'
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    section_title, operator_name, parameter_names, python_symbols, content,
    content=''
);
```

The FTS5 index uses BM25 with column weights: `section_title(10)`, `operator_name(8)`, `parameter_names(5)`, `python_symbols(3)`, `content(1)`.

## Step-by-Step Guide

### 1. Scrape the Documentation

Use any site scraper (`wget --mirror`, `httrack`, `scrapy`, etc.) to download the HTML locally.

```bash
# Example: mirror a documentation site
wget --mirror --convert-links --adjust-extension \
     --page-requisites --no-parent \
     https://docs.example.com/ \
     -P /tmp/example-docs-scrape/
```

**Legal note:** Only scrape sites you have permission to mirror. Check `robots.txt` and the site's terms of service. TDPilot brain files are for personal/private use.

### 2. Create a Brain Config (YAML)

Create a config file that tells the builder how to parse your scraped HTML:

```yaml
# configs/example.yaml
brain_id: "example"
display_name: "Example Docs"
description: "Documentation for Example software"
source_url: "https://docs.example.com/"

# CSS selector for the main content area
content_selector: "div.document-content"

# CSS selectors for elements to strip (nav, ads, etc.)
strip_selectors:
  - "nav"
  - "footer"
  - ".sidebar"
  - ".breadcrumb"

# Rules for classifying pages into doc_type
page_rules:
  - pattern: "*/operators/*"
    doc_type: "operator"
    extract_operator_name: true
  - pattern: "*/api/*"
    doc_type: "python_api"
  - pattern: "*/release-notes/*"
    doc_type: "release_notes"
  - pattern: "*"
    doc_type: "general"
```

### 3. Run the Generic Brain Builder

```bash
python scripts/build_brain.py \
  --config configs/example.yaml \
  --source /tmp/example-docs-scrape/docs.example.com/ \
  --output data/normalized/example/
```

This will:
1. Parse all HTML files using the config's selectors
2. Chunk each page into sections (~500-1000 chars each)
3. Build the FTS5 index
4. Write `examplebrain.db`, `build_manifest.json`

### 4. Existing Builder Scripts

For the two built-in brains, dedicated builders exist:

```bash
# derivative brain (docs.derivative.ca)
python scripts/build_docs_brain.py --source /path/to/docs.derivative.ca/

# POPx brain (popsextension.com)
python scripts/build_popx_brain.py --source /path/to/popx-scrape/
```

### 5. Register Your Brain

#### 5a. Add to `tool_registry.py`

Follow the pattern of the existing POPx brain. In `server_lifespan()`:

```python
# Load your brain
my_brain = None
if brain_is_active(active_brains, "example"):
    try:
        from td_mcp.knowledge.docsbrain import DocsBrain
        brain_dir = Path(__file__).resolve().parent.parent.parent / "data" / "normalized" / "example"
        brain_db = brain_dir / "examplebrain.db"
        if brain_db.exists():
            my_brain = DocsBrain(db_path=brain_db)
            logger.info("Example brain loaded (%d chunks)", my_brain.count())
    except Exception as exc:
        logger.debug("Example brain not available: %s", exc)
```

Add a field to `ServiceContainer` in `src/td_mcp/services.py`:

```python
example_brain: Optional[DocsBrain] = None
```

#### 5b. Add MCP Tools

Create search/lookup tools following the `td_search_popx_docs` pattern:

```python
@mcp.tool(name="td_search_example_docs")
async def td_search_example_docs(ctx: Context, query: str, limit: int = 10):
    """Search Example documentation."""
    brain = getattr(_get_services(ctx), "example_brain", None)
    if brain is None:
        raise RuntimeError("Example brain not loaded")
    results = brain.search(query, limit=limit)
    return {"results": results, "count": len(results)}
```

#### 5c. Update the Manifest

If using the installer system, add your brain to `brains_manifest.json`:

```json
{
  "example": {
    "display_name": "Example Docs",
    "description": "Documentation for Example software",
    "version": "2026.03",
    "size_mb": 50,
    "chunks": 5000,
    "skills": [],
    "tools": ["td_search_example_docs"],
    "files": [
      {
        "name": "examplebrain.db",
        "drive_id": "YOUR_GOOGLE_DRIVE_FILE_ID",
        "size_mb": 50
      },
      {
        "name": "build_manifest.json",
        "drive_id": "YOUR_MANIFEST_DRIVE_ID",
        "size_mb": 0.001
      }
    ]
  }
}
```

### 6. Verify

```bash
# Test the brain loads
uv run python -c "
from td_mcp.knowledge.docsbrain import DocsBrain
brain = DocsBrain(db_path='data/normalized/example/examplebrain.db')
print(f'Chunks: {brain.count()}')
results = brain.search('your test query')
print(f'Results: {len(results)}')
for r in results[:3]:
    print(f'  - {r[\"section_title\"]}: {r[\"content\"][:100]}')
"
```

## Tips

- **Chunk size matters.** Aim for 500-1000 characters per chunk. Too small = no context. Too large = diluted search relevance.
- **doc_type classification** drives intent detection. If you label pages as `operator`, searches for operator names will automatically filter to those chunks.
- **Column weights** in the FTS5 index mean `section_title` and `operator_name` matches rank higher than `content` matches.
- **The same DocsBrain class** works for all brains — no new search code needed.
- **Test incrementally.** Build with a small subset first, verify search quality, then build the full corpus.

## Dependencies

Brain building requires:
- `beautifulsoup4` — HTML parsing
- `lxml` — Fast HTML parser backend (optional but recommended)
- `pyyaml` — Config file parsing (for generic builder)

Install with: `uv pip install beautifulsoup4 lxml pyyaml`
