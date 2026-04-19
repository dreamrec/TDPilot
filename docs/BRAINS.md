# TDPilot Knowledge Brains

## What is a Brain?

A **brain** is a structured, searchable knowledge corpus built from a specific source. TDPilot can load multiple brains simultaneously, each providing expertise from a different origin — official documentation, community tutorials, personal notes, or any other scraped/structured content.

Each brain is a self-contained SQLite FTS5 database with normalized chunks, metadata, and search capabilities.

## Brain Hierarchy

Brains have a **trust tier** that determines how their results are prioritized:

| Tier | Trust Level | Example | Behavior |
|------|-------------|---------|----------|
| **official** | Ground truth | Derivative docs (docs.derivative.ca) | Always consulted first. Results treated as authoritative. Overrides conflicting info from lower tiers. |
| **community** | Trusted reference | Paketa tutorials, Matthew Ragan's blog, Interactive & Immersive HQ | Consulted after official. Great for workflows, creative techniques, and practical examples not covered in official docs. |
| **personal** | User-specific | Your own notes, project logs, workshop materials | Consulted on request or when other tiers don't have an answer. |
| **experimental** | Unverified | Forum scrapes, Discord archives, AI-generated content | Only consulted when explicitly requested. Results flagged as unverified. |

When multiple brains return results for the same query, results are interleaved by tier — official first, then community, then personal/experimental.

## Available Brains

### derivative (official)
- **Source:** Scraped docs.derivative.ca website
- **Content:** ~3,369 pages — every operator, Python class, palette component, glossary term, release note
- **Trust tier:** official
- **Special features:** Release notes intelligence with per-operator changelog, build-aware search
- **Build command:** `python scripts/build_docs_brain.py --source ~/path/to/docs.derivative.ca_offline/docs.derivative.ca/`

### popx (licensed)
- **Source:** Scraped popsextension.com + TDPilot-popx-refs catalog
- **Content:** 58 pages + 54 examples + curated markdown → 480 chunks, 59 operators
- **Trust tier:** licensed (POPx is a paid plugin — content is copyrighted)
- **Special features:** Structured parameter extraction from HTML, example node topology from catalog
- **Build command:** `python scripts/build_popx_brain.py --source ~/path/to/popsextension.com/ --refs ~/path/to/TDPilot-popx-refs/`

### Downloading pre-built brains

Both brains are hosted on Google Drive for easy installation:

```bash
# Download all brains (~165MB)
python scripts/download_brains.py

# Download just one
python scripts/download_brains.py --brain derivative
python scripts/download_brains.py --brain popx

# List available brains
python scripts/download_brains.py --list
```

Shared folder: https://drive.google.com/drive/folders/1lc1S6NBQgpAzA2G2KsHkR0gV7_SdzseO

### Adding your own brains
See [Building a Brain](#building-a-brain) below.

---

## How Brains Are Used at Runtime

### Automatic (default behavior)
When you ask TDPilot a TouchDesigner question, the knowledge layer:
1. Queries the **official** brain first
2. If confidence is high, returns that answer
3. If confidence is low or no results found, queries **community** brains
4. Results include source attribution so you know where the answer came from

### Explicit brain selection
You can target a specific brain in your query:
- "Search the derivative docs for feedbackTOP parameters"
- "What does Paketa's tutorial say about instancing?"
- "Search all brains for audio-reactive techniques"

### Source attribution
Every result includes:
```
Source: derivative (official) — Feedback TOP > Parameters
URL: https://docs.derivative.ca/Feedback_TOP
```

---

## Building a Brain

### Prerequisites
- A folder of scraped HTML files (the brain's raw source material)
- Each HTML file should be a self-contained page from the source

### Step 1: Create a brain config

Create a YAML file describing your brain. Save it in `data/brains/`:

```yaml
# data/brains/derivative.yaml
name: derivative
display_name: "Derivative Official Docs"
trust_tier: official          # official | community | personal | experimental
version: "1.0"
source_url: "https://docs.derivative.ca"
description: "Official TouchDesigner documentation from Derivative"

# Where to find the scraped HTML files
scrape_path: "${TDPILOT_DOCS_SCRAPE_PATH}"
# Or an absolute path:
# scrape_path: "~/Desktop/docs.derivative.ca_offline/docs.derivative.ca/"

# Content extraction
content_selector: "#mw-content-text"    # CSS selector for main content
strip_selectors:                         # CSS selectors to remove
  - "#toc"                               # table of contents
  - ".mw-editsection"                    # edit links
  - ".noprint"                           # print-hidden elements
  - "script"
  - "style"
  - ".mw-lingo-term"                     # keep inner text, strip wrapper

# Page classification rules (matched against filename)
page_rules:
  - pattern: "*_TOP.html|*_CHOP.html|*_SOP.html|*_DAT.html|*_COMP.html|*_MAT.html|*_POP.html"
    doc_type: operator
  - pattern: "*_Class.html|*Class.html"
    doc_type: python_api
  - pattern: "Release_Notes/*.html"
    doc_type: release_notes
  - pattern: "Palette:*.html"
    doc_type: palette
  - pattern: "OP_Snippets*.html"
    doc_type: snippet
  - pattern: "*Glossary*.html"
    doc_type: glossary
  - pattern: "*"
    doc_type: general

# Pages to skip
skip_patterns:
  - "File:*.html"
  - "*.css"
  - "*.js"

# URL reconstruction (for source links in results)
url_template: "https://docs.derivative.ca/{page_name}"

# Optional: special parsers (for brains with unique structure)
special_parsers:
  release_notes: true        # Enable release notes intelligence
  operator_changelog: true   # Build per-operator change tracking
```

### Step 2: Build the brain

```bash
python scripts/build_docs_brain.py --config data/brains/derivative.yaml
```

This runs the full pipeline:
1. **Normalize** — reads HTML files, strips boilerplate, classifies pages, extracts clean text
2. **Chunk** — splits pages by headings into searchable chunks with metadata
3. **Index** — builds SQLite FTS5 database with boosted search fields
4. **Special parsers** — (if enabled) builds release note manifest and operator changelog

Output goes to `data/normalized/<brain_name>/`:
```
data/normalized/derivative/
    pages.jsonl
    chunks.jsonl
    docsbrain.db
    build_manifest.json        # (if release_notes parser enabled)
    operator_changelog.json    # (if operator_changelog parser enabled)
```

### Step 3: Register the brain

The brain is automatically discovered on next TDPilot startup if its config exists in `data/brains/` and its database exists in `data/normalized/<brain_name>/`.

---

## Brain Config Template for Community Sources

Here's a template for building a brain from a community tutorial source:

```yaml
# data/brains/paketa.yaml
name: paketa
display_name: "Paketa12 Tutorials"
trust_tier: community
version: "1.0"
source_url: "https://www.youtube.com/@paketa12"
description: "TouchDesigner tutorials by Paketa — creative coding, generative art, audio-reactive visuals"

scrape_path: "~/Desktop/paketa_tutorials/"

# For YouTube transcript scrapes or blog posts, the selectors will differ
content_selector: "body"           # or ".post-content", ".article-body", etc.
strip_selectors:
  - "nav"
  - "footer"
  - ".sidebar"
  - "script"
  - "style"

page_rules:
  - pattern: "*"
    doc_type: tutorial

skip_patterns:
  - "*.css"
  - "*.js"
  - "*.png"
  - "*.jpg"

url_template: "https://paketa12.com/{page_name}"

special_parsers:
  release_notes: false
  operator_changelog: false
```

### Tips for community brains

- **YouTube tutorials:** Scrape auto-generated transcripts or manually cleaned transcripts. One file per video works well.
- **Blog posts:** Scrape the article content. One HTML file per post.
- **Forum threads:** Be selective — scrape only high-quality solved threads, not noise.
- **Workshop notes:** Markdown or HTML files, one per session/topic.

---

## Multiple Brain Examples

### Scenario: Artist with official docs + community tutorials

```
data/brains/
    derivative.yaml      # official — ground truth
    paketa.yaml          # community — creative techniques
    elekktronaut.yaml    # community — instancing, particles
    my_notes.yaml        # personal — workshop notes

data/normalized/
    derivative/          # ~3,369 pages, official tier
    paketa/              # ~200 tutorials, community tier
    elekktronaut/        # ~150 tutorials, community tier
    my_notes/            # ~50 notes, personal tier
```

When you ask: "How do I create an audio-reactive particle system?"
1. **derivative** brain returns: Particle POP docs, Audio Spectrum CHOP docs, relevant parameters
2. **paketa** brain returns: Tutorial on audio-reactive setups with specific node chains
3. **elekktronaut** brain returns: Advanced instancing tutorial with audio input
4. Results are presented with clear source attribution and tier ordering

### Scenario: Developer building a hardware installation

```
data/brains/
    derivative.yaml      # official
    hardware_notes.yaml  # personal — DMX, LED, laser setup notes from past projects
```

---

## How the Brain Pipeline Works (Technical)

```
                    ┌─────────────┐
                    │  brain.yaml │  (config)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  HTML files  │  (scraped source)
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │     1. NORMALIZE        │
              │  Strip boilerplate      │
              │  Classify pages         │
              │  Extract clean text     │
              │  Generate stable IDs    │
              └────────────┬────────────┘
                           │
                    pages.jsonl
                           │
              ┌────────────▼────────────┐
              │      2. CHUNK           │
              │  Split by headings      │
              │  Extract metadata       │
              │  Tag operators/params   │
              │  Merge short sections   │
              └────────────┬────────────┘
                           │
                    chunks.jsonl
                           │
              ┌────────────▼────────────┐
              │      3. INDEX           │
              │  Build SQLite FTS5      │
              │  Boosted fields         │
              │  Schema versioning      │
              └────────────┬────────────┘
                           │
                    docsbrain.db
                           │
              ┌────────────▼────────────┐
              │  4. SPECIAL PARSERS     │
              │  (optional per brain)   │
              │  Release notes manifest │
              │  Operator changelog     │
              └────────────┬────────────┘
                           │
              build_manifest.json
              operator_changelog.json
```

---

## Rebuilding After a New Scrape

When Derivative releases a new TouchDesigner build and you re-scrape docs.derivative.ca, follow these steps to update TDPilot's knowledge.

### Prerequisites

- A fresh offline scrape of docs.derivative.ca (use wget, httrack, or similar)
- The scrape folder should contain `.html` files mirroring the site structure

### Step-by-step rebuild

**1. Re-scrape the docs site**

Use your preferred tool to download an updated copy of docs.derivative.ca. The scrape folder should look like:

```
docs.derivative.ca/
    Composite_TOP.html
    Feedback_TOP.html
    Wave_CHOP.html
    Release_Notes/
        2025.30000.html
    Palette:camSchnappr.html
    ...
```

**2. Run the build script**

```bash
# From the TDPilot project root
python scripts/build_docs_brain.py --source /path/to/docs.derivative.ca/
```

Or set the environment variable once and skip `--source`:
```bash
export TDPILOT_DOCS_SCRAPE_PATH="/path/to/docs.derivative.ca/"
python scripts/build_docs_brain.py
```

**3. Verify the output**

The script prints progress for each stage:

```
INFO: Stage 1: Normalizing HTML files from /path/to/scrape
INFO:   → 2478 pages normalized
INFO: Stage 2: Chunking pages
INFO:   → 25887 chunks created
INFO: Stage 3: Building FTS5 index
INFO:   → 25887 chunks indexed
INFO: Stage 4: Building release note artifacts
INFO:   → 10 builds, 245 operators with changelog
INFO: Done in 194.0s
```

Generated files go to `data/normalized/derivative/`:

| File | Description |
|------|-------------|
| `pages.jsonl` | One JSON record per normalized page |
| `chunks.jsonl` | One JSON record per searchable chunk |
| `docsbrain.db` | SQLite FTS5 search database |
| `build_manifest.json` | All known builds with dates |
| `operator_changelog.json` | Per-operator change history across builds |

**4. Restart TDPilot**

Stop and restart `npx tdpilot`. On startup it will detect the brain database and load it automatically:

```
INFO: DocsBrain loaded (25887 chunks)
```

If the database is missing or corrupt, TDPilot falls back to the original 30 JSON knowledge cards.

### Quick one-liner

```bash
python scripts/build_docs_brain.py --source ~/Desktop/docs.derivative.ca/ && echo "Brain rebuilt. Restart TDPilot to load."
```

### What gets updated

- All operator documentation (parameters, summaries, inputs)
- Python API class references
- Palette component descriptions
- Glossary terms
- Release notes for all builds — TDPilot will know every fix, feature, and breaking change
- Per-operator changelog — when asking about any operator, TDPilot shows its recent history

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `No source path` error | Pass `--source` or set `TDPILOT_DOCS_SCRAPE_PATH` |
| `Source directory not found` | Check the path points to the folder containing `.html` files |
| `No #mw-content-text` warnings | Normal — some pages (redirects, stubs) lack content and are skipped |
| TDPilot still using old cards | Make sure `data/normalized/derivative/docsbrain.db` exists and restart |
| Build takes too long | Normal for first run (~3 minutes). The bottleneck is HTML parsing, not indexing |

---

## Future: Vector Search Layer

The current brain system uses SQLite FTS5 (lexical/keyword search). A future upgrade can add vector embeddings for semantic search ("how do I smooth jittery motion" finding noise-based smoothing techniques). The brain config and pipeline are designed to support this addition without changing the brain YAML format or rebuild process.
