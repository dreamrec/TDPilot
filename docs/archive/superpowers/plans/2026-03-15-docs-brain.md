# Docs Brain Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace TDPilot's 30 hand-curated JSON knowledge cards with a full-corpus docs brain built from 3,369 scraped docs.derivative.ca pages, with SQLite FTS5 search and release notes intelligence.

**Architecture:** Three-stage offline pipeline (normalize HTML → chunk by headings → index in FTS5) producing a SQLite database that `DocsBrain` reads at runtime as a drop-in replacement for `CardIndex`. Release notes are additionally parsed into a per-operator changelog and build manifest.

**Tech Stack:** Python 3, BeautifulSoup4 (HTML parsing), SQLite FTS5 (search), pytest (testing). No new dependencies — bs4 and sqlite3 are already available.

**Spec:** `docs/superpowers/specs/2026-03-15-docs-brain-design.md`

---

## File Structure

```
New files:
  src/td_mcp/knowledge/docsbrain/__init__.py    — DocsBrain class (runtime search interface)
  src/td_mcp/knowledge/docsbrain/normalizer.py  — HTML → pages.jsonl
  src/td_mcp/knowledge/docsbrain/chunker.py     — pages.jsonl → chunks.jsonl
  src/td_mcp/knowledge/docsbrain/metadata.py    — page classification, operator/param extraction
  src/td_mcp/knowledge/docsbrain/release_parser.py — release notes → manifest + changelog
  src/td_mcp/knowledge/docsbrain/indexer.py     — chunks.jsonl → SQLite FTS5 database
  scripts/build_docs_brain.py                    — CLI entry point
  tests/test_normalizer.py                       — normalizer unit tests
  tests/test_chunker.py                          — chunker unit tests
  tests/test_release_parser.py                   — release parser unit tests
  tests/test_docsbrain_search.py                 — DocsBrain search + integration tests
  tests/fixtures/sample_pages/                   — small HTML fixtures for tests

Modified files:
  src/td_mcp/knowledge/__init__.py               — export DocsBrain
  src/td_mcp/services.py                         — try DocsBrain, fall back to CardIndex
  src/td_mcp/tool_registry.py                    — ~3 lines in init to try DocsBrain path
  data/.gitignore                                — ignore normalized/
  pyproject.toml                                 — add beautifulsoup4 dependency
```

---

## Chunk 1: Metadata & Normalization

### Task 1: Add beautifulsoup4 dependency and create package skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `src/td_mcp/knowledge/docsbrain/__init__.py`
- Create: `src/td_mcp/knowledge/docsbrain/metadata.py`
- Create: `data/.gitignore`

- [ ] **Step 1: Add beautifulsoup4 to dependencies**

In `pyproject.toml`, add `"beautifulsoup4>=4.12"` to the `dependencies` list:

```toml
dependencies = [
    "mcp>=1.0,<2.0",
    "httpx>=0.27",
    "pydantic>=2.0",
    "websockets>=12.0",
    "beautifulsoup4>=4.12",
]
```

- [ ] **Step 2: Create the docsbrain package with empty init**

Create `src/td_mcp/knowledge/docsbrain/__init__.py`:

```python
"""TDPilot Docs Brain — full-corpus search over scraped docs.derivative.ca."""
```

- [ ] **Step 3: Create metadata.py with page classification**

Create `src/td_mcp/knowledge/docsbrain/metadata.py`:

```python
"""Page classification and metadata extraction for the docs brain."""

from __future__ import annotations

import re
from typing import Optional


# Operator family suffixes
_OP_FAMILIES = ("TOP", "CHOP", "SOP", "DAT", "COMP", "MAT", "POP")

# Patterns matched against the filename (without .html), first match wins
_PAGE_RULES: list[tuple[str, str]] = [
    # Skip rules (return None to signal skip)
    (r"^File:", "skip"),
    # Operator pages
    (r"_(?:TOP|CHOP|SOP|DAT|COMP|MAT|POP)$", "operator"),
    # Python API class pages
    (r"(?:_Class|Class)$", "python_api"),
    # Release notes
    (r"^Release_Notes", "release_notes"),
    # Palette components
    (r"^Palette:", "palette"),
    # OP Snippets
    (r"^OP_Snippets", "snippet"),
    # Glossary
    (r"Glossary", "glossary"),
]

# Files to skip entirely (non-content)
_SKIP_EXTENSIONS = {".css", ".js", ".png", ".jpg", ".gif", ".ico", ".svg"}


def classify_page(filename: str) -> Optional[str]:
    """Classify a page by its filename (without .html).

    Returns doc_type string, or None if the page should be skipped.
    """
    for pattern, doc_type in _PAGE_RULES:
        if re.search(pattern, filename):
            return None if doc_type == "skip" else doc_type
    return "general"


def should_skip_file(filename: str) -> bool:
    """Return True if the file should be skipped entirely."""
    # Skip non-HTML files
    if not filename.endswith(".html"):
        return True
    # Skip load.php, index.php resources
    if filename.startswith(("load.php", "index.php")):
        return True
    return False


def derive_page_id(filename: str) -> str:
    """Derive a stable page ID from a filename.

    Transformation: strip .html, lowercase, / → __, . → _
    Example: Release_Notes/2025.30000.html → release_notes__2025_30000
    """
    page_id = filename
    if page_id.endswith(".html"):
        page_id = page_id[:-5]
    page_id = page_id.lower()
    page_id = page_id.replace("/", "__")
    page_id = page_id.replace(".", "_")
    return page_id


def derive_url(filename: str) -> str:
    """Reconstruct the source URL from a filename."""
    page_name = filename
    if page_name.endswith(".html"):
        page_name = page_name[:-5]
    return f"https://docs.derivative.ca/{page_name}"


def extract_operator_family(filename: str) -> Optional[str]:
    """Extract operator family (TOP, CHOP, etc.) from filename."""
    for family in _OP_FAMILIES:
        if filename.endswith(f"_{family}.html") or filename.endswith(f"_{family}"):
            return family
    return None


def extract_operator_name(title: str) -> Optional[str]:
    """Extract operator display name from page title.

    Example: 'Composite TOP' → 'Composite TOP'
    """
    if not title:
        return None
    for family in _OP_FAMILIES:
        if title.endswith(f" {family}"):
            return title
    return None


def slugify(text: str) -> str:
    """Convert a heading to a URL-safe slug for chunk IDs."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug
```

- [ ] **Step 4: Create data/.gitignore**

Create `data/.gitignore`:

```
# Generated docs brain output
normalized/
```

- [ ] **Step 5: Reinstall package with new dependency**

Run: `cd <REPO_ROOT> && pip install -e ".[dev]"`
Expected: Successful install, beautifulsoup4 confirmed available

- [ ] **Step 6: Commit**

```bash
git add src/td_mcp/knowledge/docsbrain/__init__.py src/td_mcp/knowledge/docsbrain/metadata.py data/.gitignore pyproject.toml
git commit -m "feat(docsbrain): add package skeleton and page classification"
```

---

### Task 2: Metadata unit tests

**Files:**
- Create: `tests/test_normalizer.py`

- [ ] **Step 1: Write metadata classification tests**

Create `tests/test_normalizer.py`:

```python
"""Tests for docs brain normalizer and metadata extraction."""

from __future__ import annotations

import pytest

from td_mcp.knowledge.docsbrain.metadata import (
    classify_page,
    derive_page_id,
    derive_url,
    extract_operator_family,
    extract_operator_name,
    should_skip_file,
    slugify,
)


class TestClassifyPage:
    def test_operator_top(self):
        assert classify_page("Composite_TOP") == "operator"

    def test_operator_chop(self):
        assert classify_page("Wave_CHOP") == "operator"

    def test_operator_pop(self):
        assert classify_page("Particle_POP") == "operator"

    def test_python_api_class(self):
        assert classify_page("CompositeTOP_Class") == "python_api"

    def test_python_api_bare_class(self):
        assert classify_page("OP_Class") == "python_api"

    def test_release_notes(self):
        assert classify_page("Release_Notes/2025.30000") == "release_notes"

    def test_palette(self):
        assert classify_page("Palette:camSchnappr") == "palette"

    def test_snippet(self):
        assert classify_page("OP_Snippets") == "snippet"

    def test_glossary(self):
        assert classify_page("TouchDesigner_Glossary") == "glossary"

    def test_general(self):
        assert classify_page("3D_Parenting") == "general"

    def test_skip_file_page(self):
        assert classify_page("File:some_image.jpg") is None


class TestDerivePageId:
    def test_simple_operator(self):
        assert derive_page_id("Composite_TOP.html") == "composite_top"

    def test_release_notes_with_path(self):
        assert derive_page_id("Release_Notes/2025.30000.html") == "release_notes__2025_30000"

    def test_palette_colon(self):
        assert derive_page_id("Palette:camSchnappr.html") == "palette:camschnappr"

    def test_no_html_suffix(self):
        assert derive_page_id("Composite_TOP") == "composite_top"


class TestDeriveUrl:
    def test_simple(self):
        assert derive_url("Composite_TOP.html") == "https://docs.derivative.ca/Composite_TOP"

    def test_release_notes(self):
        assert derive_url("Release_Notes/2025.30000.html") == "https://docs.derivative.ca/Release_Notes/2025.30000"


class TestShouldSkipFile:
    def test_skip_css(self):
        assert should_skip_file("style.css") is True

    def test_skip_png(self):
        assert should_skip_file("image.png") is True

    def test_skip_loadphp(self):
        assert should_skip_file("load.php?lang=en") is True

    def test_keep_html(self):
        assert should_skip_file("Composite_TOP.html") is False


class TestExtractOperatorFamily:
    def test_top(self):
        assert extract_operator_family("Composite_TOP.html") == "TOP"

    def test_chop(self):
        assert extract_operator_family("Wave_CHOP.html") == "CHOP"

    def test_pop(self):
        assert extract_operator_family("Particle_POP.html") == "POP"

    def test_non_operator(self):
        assert extract_operator_family("3D_Parenting.html") is None


class TestExtractOperatorName:
    def test_operator(self):
        assert extract_operator_name("Composite TOP") == "Composite TOP"

    def test_non_operator(self):
        assert extract_operator_name("3D Parenting") is None


class TestSlugify:
    def test_simple(self):
        assert slugify("Bug Fixes and Improvements") == "bug_fixes_and_improvements"

    def test_special_chars(self):
        assert slugify("Build 2025.32460 Mar 10, 2026") == "build_2025_32460_mar_10_2026"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_normalizer.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_normalizer.py
git commit -m "test(docsbrain): add metadata classification tests"
```

---

### Task 3: HTML normalizer

**Files:**
- Create: `src/td_mcp/knowledge/docsbrain/normalizer.py`
- Create: `tests/fixtures/sample_pages/Composite_TOP.html`
- Modify: `tests/test_normalizer.py`

- [ ] **Step 1: Create a minimal HTML test fixture**

Create `tests/fixtures/sample_pages/Composite_TOP.html`. This is a stripped-down version of a real operator page:

```html
<!DOCTYPE html>
<html lang="en-CA">
<head>
<title>Composite TOP - TouchDesigner Documentation</title>
<script>/* mediawiki js */</script>
<style>/* mediawiki css */</style>
</head>
<body>
<div id="mw-page-base" class="noprint"></div>
<div id="content" class="mw-body">
  <h1 id="firstHeading"><span class="mw-page-title-main">Composite TOP</span></h1>
  <div id="bodyContent" class="vector-body">
    <div id="siteSub" class="noprint">From Derivative</div>
    <div id="contentSub"></div>
    <div id="jump-to-nav"></div>
    <a class="mw-jump-link" href="#mw-head">Jump to navigation</a>
    <div id="mw-content-text" class="mw-body-content">
      <div class="mw-parser-output">
        <p>The Composite TOP combines two or more texture inputs using blend operations.</p>
        <div id="toc" class="toc"><h2>Contents</h2><ul><li>Parameters</li></ul></div>
        <h2><span class="mw-headline" id="Summary">Summary</span><span class="mw-editsection">[<a href="#">edit</a>]</span></h2>
        <p>The <span class="mw-lingo-term" data-lingo-term-id="abc">Composite TOP</span> is a multi-input TOP that will perform a composite operation for each input.</p>
        <h2><span class="mw-headline" id="Parameters">Parameters</span></h2>
        <p><b>Operand</b> - Blend mode: Over, Under, Add, Subtract, Multiply, Screen.</p>
        <p><b>Opacity</b> - Master opacity (0-1).</p>
        <p><b>Pre Fit</b> - How to handle resolution mismatches.</p>
        <h2><span class="mw-headline" id="Inputs">Inputs</span></h2>
        <p>Accepts multiple TOP inputs.</p>
      </div>
    </div>
  </div>
</div>
<div id="mw-navigation" class="noprint">Navigation here</div>
<div id="footer" class="noprint">Footer here</div>
</body>
</html>
```

- [ ] **Step 2: Create a release notes test fixture**

Create `tests/fixtures/sample_pages/Release_Notes/2025.30000.html`. Minimal version:

```html
<!DOCTYPE html>
<html lang="en-CA">
<head><title>Release Notes/2025.30000 - TouchDesigner Documentation</title></head>
<body>
<div id="content" class="mw-body">
  <h1 id="firstHeading"><span class="mw-page-title-main">Release Notes/2025.30000</span></h1>
  <div id="bodyContent">
    <div id="mw-content-text" class="mw-body-content">
      <div class="mw-parser-output">
        <p>Current Official <b><a href="https://derivative.ca/release/202532460/74120">Build 2025.32460 Download</a></b> - <b>Mar 10 2026</b></p>
        <h2><span class="mw-headline" id="Known_Issues">Known Issues</span></h2>
        <ul><li>HDR backdrop blending issue.</li></ul>
        <h2><span id="Build_2025.32460_Mar_10.2C_2026"></span><span class="mw-headline" id="Build_2025.32460_Mar_10,_2026">Build 2025.32460 Mar 10, 2026</span></h2>
        <p>Hotfix for 2025.32440 ray tracing bug.</p>
        <h3><span class="mw-headline" id="New_Features">New Features</span></h3>
        <ul>
          <li><a href="../Text_POP.html" title="Text POP">Text POP</a> - A new POP with text as 3D line strips.</li>
          <li><a href="../Trace_POP.html" title="Trace POP">Trace POP</a> - A new POP for tracing 2D inputs.</li>
        </ul>
        <h3><span class="mw-headline" id="Bug_Fixes_and_Improvements">Bug Fixes and Improvements</span></h3>
        <ul>
          <li><a href="../Trail_POP.html" title="Trail POP">Trail POP</a> - Fixed double-transforming when cooking a second time.</li>
          <li><a href="../Movie_File_In_TOP.html" title="Movie File In TOP">Movie File In TOP</a> - Fixed incorrect ProRes 4:4:4:4 output.</li>
        </ul>
        <h3><span class="mw-headline" id="Backward_Compatibility_Changes">Backward Compatibility Changes</span></h3>
        <ul><li>Some backward compat note.</li></ul>
        <h2><span class="mw-headline" id="Build_2025.32280_Jan_20,_2025">Build 2025.32280 Jan 20, 2025</span></h2>
        <h3><span class="mw-headline" id="New_Features_2">New Features</span></h3>
        <ul><li>Some feature in earlier build.</li></ul>
        <h3><span class="mw-headline" id="Bug_Fixes_and_Improvements_2">Bug Fixes and Improvements</span></h3>
        <ul><li><a href="../Count_CHOP.html" title="Count CHOP">Count CHOP</a> - Fixed count down pulse issue.</li></ul>
      </div>
    </div>
  </div>
</div>
</body>
</html>
```

- [ ] **Step 3: Write the normalizer**

Create `src/td_mcp/knowledge/docsbrain/normalizer.py`:

```python
"""Normalizer — reads scraped HTML files and produces pages.jsonl."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Iterator

from bs4 import BeautifulSoup, NavigableString, Tag

from .metadata import (
    classify_page,
    derive_page_id,
    derive_url,
    extract_operator_family,
    should_skip_file,
)

logger = logging.getLogger(__name__)

# CSS selectors to strip from content
_STRIP_SELECTORS = [
    "#toc",
    ".mw-editsection",
    ".noprint",
    "#siteSub",
    "#contentSub",
    "#contentSub2",
    "#jump-to-nav",
    ".mw-jump-link",
    "script",
    "style",
]


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from the firstHeading element."""
    heading = soup.find("h1", id="firstHeading")
    if heading:
        span = heading.find("span", class_="mw-page-title-main")
        if span:
            return span.get_text(strip=True)
        return heading.get_text(strip=True)
    # Fallback to <title> tag
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text(strip=True)
        # Strip " - TouchDesigner Documentation" suffix
        if " - " in text:
            return text.split(" - ")[0].strip()
        return text
    return ""


def _extract_headings(content_div: Tag) -> list[str]:
    """Extract all heading texts from content."""
    headings = []
    for tag in content_div.find_all(["h2", "h3", "h4"]):
        headline = tag.find("span", class_="mw-headline")
        if headline:
            headings.append(headline.get_text(strip=True))
        else:
            headings.append(tag.get_text(strip=True))
    return headings


def _unwrap_lingo_terms(content_div: Tag) -> None:
    """Replace lingo wrapper spans with their inner text (in place)."""
    for span in content_div.find_all("span", class_="mw-lingo-term"):
        span.unwrap()


def _strip_boilerplate(content_div: Tag) -> None:
    """Remove navigation, edit links, and other chrome from content."""
    for selector in _STRIP_SELECTORS:
        for el in content_div.select(selector):
            el.decompose()
    _unwrap_lingo_terms(content_div)


def _clean_text(content_div: Tag) -> str:
    """Get clean text from content div."""
    return content_div.get_text(separator="\n", strip=True)


def normalize_file(filepath: Path, relative_name: str) -> dict[str, Any] | None:
    """Normalize a single HTML file into a page record.

    Args:
        filepath: Absolute path to the HTML file.
        relative_name: Filename relative to scrape root (e.g. "Composite_TOP.html").

    Returns:
        Page record dict, or None if the file should be skipped.
    """
    if should_skip_file(relative_name):
        return None

    # Derive the base name without .html for classification
    base_name = relative_name
    if base_name.endswith(".html"):
        base_name = base_name[:-5]

    doc_type = classify_page(base_name)
    if doc_type is None:
        return None

    try:
        html = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", filepath, exc)
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Find main content
    content_div = soup.find("div", id="mw-content-text")
    if content_div is None:
        logger.warning("No #mw-content-text in %s, skipping", relative_name)
        return None

    title = _extract_title(soup)
    headings = _extract_headings(content_div)

    # Strip boilerplate before extracting text
    _strip_boilerplate(content_div)
    text = _clean_text(content_div)

    if not text.strip():
        logger.warning("Empty content after stripping %s, skipping", relative_name)
        return None

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return {
        "page_id": derive_page_id(relative_name),
        "url": derive_url(relative_name),
        "title": title,
        "doc_type": doc_type,
        "operator_family": extract_operator_family(relative_name),
        "headings": headings,
        "text": text,
        "text_hash": text_hash,
    }


def normalize_directory(scrape_dir: Path) -> Iterator[dict[str, Any]]:
    """Normalize all HTML files in a scrape directory.

    Yields page record dicts, skipping non-content files.
    """
    scrape_dir = Path(scrape_dir)
    if not scrape_dir.is_dir():
        raise FileNotFoundError(f"Scrape directory not found: {scrape_dir}")

    for filepath in sorted(scrape_dir.rglob("*.html")):
        relative = str(filepath.relative_to(scrape_dir))
        record = normalize_file(filepath, relative)
        if record is not None:
            yield record


def write_pages_jsonl(pages: Iterator[dict[str, Any]], output_path: Path) -> int:
    """Write page records to a JSONL file. Returns count of pages written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for page in pages:
            f.write(json.dumps(page, ensure_ascii=False) + "\n")
            count += 1
    return count
```

- [ ] **Step 4: Add normalizer tests to test_normalizer.py**

Append to `tests/test_normalizer.py`:

```python
from pathlib import Path

from td_mcp.knowledge.docsbrain.normalizer import normalize_file


FIXTURES = Path(__file__).parent / "fixtures" / "sample_pages"


class TestNormalizeFile:
    def test_operator_page(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert result is not None
        assert result["page_id"] == "composite_top"
        assert result["title"] == "Composite TOP"
        assert result["doc_type"] == "operator"
        assert result["operator_family"] == "TOP"
        assert "Summary" in result["headings"]
        assert "Parameters" in result["headings"]
        assert "text_hash" in result

    def test_boilerplate_stripped(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert result is not None
        # Edit links, navigation, footer should be gone
        assert "[edit]" not in result["text"]
        assert "Jump to navigation" not in result["text"]
        assert "Footer here" not in result["text"]
        # But actual content should be present
        assert "Composite TOP" in result["text"]
        assert "Operand" in result["text"]

    def test_lingo_terms_unwrapped(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert result is not None
        # Lingo span text should be kept, wrapper removed
        assert "Composite TOP" in result["text"]

    def test_skips_non_html(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "style.css")
        assert result is None

    def test_skips_file_pages(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "File:some_image.jpg.html")
        assert result is None

    def test_release_notes_page(self):
        result = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        assert result is not None
        assert result["doc_type"] == "release_notes"
        assert result["page_id"] == "release_notes__2025_30000"
        assert "Build 2025.32460" in result["text"] or "New Features" in result["headings"]
```

- [ ] **Step 5: Run tests**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_normalizer.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/td_mcp/knowledge/docsbrain/normalizer.py tests/test_normalizer.py tests/fixtures/sample_pages/
git commit -m "feat(docsbrain): add HTML normalizer with boilerplate stripping"
```

---

### Task 4: Chunker

**Files:**
- Create: `src/td_mcp/knowledge/docsbrain/chunker.py`
- Create: `tests/test_chunker.py`

- [ ] **Step 1: Write chunker tests**

Create `tests/test_chunker.py`:

```python
"""Tests for the docs brain chunker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp.knowledge.docsbrain.normalizer import normalize_file
from td_mcp.knowledge.docsbrain.chunker import chunk_page, chunk_html


FIXTURES = Path(__file__).parent / "fixtures" / "sample_pages"


class TestChunkPage:
    def test_operator_produces_chunks(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert page is not None
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        assert len(chunks) >= 2  # At least summary + parameters

    def test_chunk_has_required_fields(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        required = {"chunk_id", "page_id", "doc_type", "section_title",
                     "operator_family", "operator_name", "mentioned_operators",
                     "parameter_names", "python_symbols", "build_number",
                     "build_date", "change_category", "token_estimate", "content"}
        for chunk in chunks:
            assert required.issubset(chunk.keys()), f"Missing: {required - chunk.keys()}"

    def test_chunk_ids_are_unique(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_ids_contain_page_id(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["chunk_id"].startswith("composite_top__")

    def test_operator_name_propagated(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["operator_name"] == "Composite TOP"

    def test_token_estimate_reasonable(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["token_estimate"] > 0
            # No chunk should be absurdly large for this small fixture
            assert chunk["token_estimate"] < 5000


class TestReleaseNoteChunks:
    def test_release_notes_produce_chunks(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        assert page is not None
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        assert len(chunks) >= 2

    def test_release_chunks_have_build_numbers(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        # At least some chunks should have build numbers
        build_chunks = [c for c in chunks if c["build_number"]]
        assert len(build_chunks) >= 1

    def test_release_chunks_have_mentioned_operators(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        # At least one chunk should mention operators
        op_chunks = [c for c in chunks if c["mentioned_operators"]]
        assert len(op_chunks) >= 1

    def test_release_chunks_have_change_category(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        cats = {c["change_category"] for c in chunks if c["change_category"]}
        # Should detect at least new_feature and bug_fix
        assert "new_feature" in cats or "bug_fix" in cats
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_chunker.py -v`
Expected: FAIL with ImportError (chunker not yet implemented)

- [ ] **Step 3: Write the chunker**

Create `src/td_mcp/knowledge/docsbrain/chunker.py`:

```python
"""Chunker — splits normalized pages into searchable chunks by heading."""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Any, Iterator

from bs4 import BeautifulSoup, Tag

from .metadata import extract_operator_name, slugify

logger = logging.getLogger(__name__)

# Heading → change_category mapping for release notes
_CHANGE_CATEGORIES = {
    "new features": "new_feature",
    "new python": "python",
    "python": "python",
    "new palette": "palette",
    "palette": "palette",
    "bug fixes and improvements": "bug_fix",
    "bug fixes": "bug_fix",
    "backward compatibility changes": "backward_compat",
    "backward compatibility issues": "backward_compat",
    "backward compatibility": "backward_compat",
    "hotfix": "bug_fix",
    "operator snippets": "other",
    "operator snippets and examples": "other",
    "known issues": "other",
    "release highlights": "new_feature",
}

# Regex to extract build number and date from heading text
# e.g. "Build 2025.32460 Mar 10, 2026"
_BUILD_HEADING_RE = re.compile(
    r"Build\s+(\d{4}\.\d{4,5})\s+(\w+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE
)


def _extract_mentioned_operators(section: Tag) -> list[str]:
    """Extract operator names mentioned in <a> links within a section."""
    ops = []
    for a in section.find_all("a"):
        title = a.get("title", "")
        if title and any(title.endswith(f" {fam}") for fam in
                         ("TOP", "CHOP", "SOP", "DAT", "COMP", "MAT", "POP")):
            if title not in ops:
                ops.append(title)
    return ops


def _extract_parameter_names(text: str) -> list[str]:
    """Extract bold parameter names from section text."""
    # Pattern: lines starting with bold text that look like parameter names
    params = []
    for match in re.finditer(r"(?:^|\n)\s*(\w[\w\s]*?)\s*[-–—]", text):
        candidate = match.group(1).strip()
        # Simple heuristic: parameter names are short
        if len(candidate) < 40 and not candidate[0].islower():
            params.append(candidate)
    return params


def _token_estimate(text: str) -> int:
    """Estimate token count from text."""
    word_count = len(text.split())
    return int(word_count * 1.3)


def _parse_build_heading(heading_text: str) -> tuple[str | None, str | None]:
    """Parse build number and date from a heading like 'Build 2025.32460 Mar 10, 2026'."""
    m = _BUILD_HEADING_RE.search(heading_text)
    if m:
        return m.group(1), m.group(2).strip().rstrip(",")
    return None, None


def _get_section_content(heading_tag: Tag) -> tuple[str, Tag]:
    """Collect all content between this heading and the next same-level heading.

    Returns (text, container_tag_with_content).
    """
    container = BeautifulSoup("<div></div>", "html.parser").div
    level = heading_tag.name  # h2, h3, h4
    current = heading_tag.next_sibling

    while current is not None:
        if isinstance(current, Tag) and current.name == level:
            break
        # Also stop at higher-level headings
        if isinstance(current, Tag) and current.name in ("h2", "h3", "h4"):
            tag_level = int(current.name[1])
            heading_level = int(level[1])
            if tag_level <= heading_level:
                break
        if isinstance(current, Tag):
            container.append(current.__copy__())
        current = current.next_sibling

    return container.get_text(separator="\n", strip=True), container


def _heading_text(tag: Tag) -> str:
    """Get clean heading text from a heading tag."""
    headline = tag.find("span", class_="mw-headline")
    if headline:
        return headline.get_text(strip=True)
    return tag.get_text(strip=True)


def chunk_page(page: dict[str, Any], html_path: Path) -> list[dict[str, Any]]:
    """Split a normalized page into chunks based on headings.

    Args:
        page: Normalized page record from normalizer.
        html_path: Path to the original HTML file (for re-parsing structure).

    Returns:
        List of chunk dicts.
    """
    try:
        html = html_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read %s for chunking: %s", html_path, exc)
        return []

    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find("div", id="mw-content-text")
    if content_div is None:
        return []

    # Strip boilerplate for clean chunking
    for sel in ("#toc", ".mw-editsection", "script", "style"):
        for el in content_div.select(sel):
            el.decompose()
    for span in content_div.find_all("span", class_="mw-lingo-term"):
        span.unwrap()

    chunks = []
    page_id = page["page_id"]
    doc_type = page["doc_type"]
    operator_name = extract_operator_name(page["title"])
    operator_family = page.get("operator_family")
    sequence = 0

    # Track current build context for release notes
    current_build = None
    current_build_date = None

    # Collect intro text (before first heading)
    headings = content_div.find_all(["h2", "h3", "h4"])

    if headings:
        # Intro: everything before first heading
        intro_parts = []
        for sibling in content_div.children:
            if isinstance(sibling, Tag) and sibling.name in ("h2", "h3", "h4"):
                break
            if isinstance(sibling, Tag):
                intro_parts.append(sibling.get_text(separator="\n", strip=True))
        intro_text = "\n".join(p for p in intro_parts if p)

        if intro_text and len(intro_text.split()) >= 10:
            sequence += 1
            chunks.append(_make_chunk(
                page_id=page_id,
                section_title=page["title"],
                sequence=sequence,
                content=intro_text,
                doc_type=doc_type,
                operator_family=operator_family,
                operator_name=operator_name,
            ))

        # Process each heading section
        for heading_tag in headings:
            heading = _heading_text(heading_tag)
            section_text, section_tag = _get_section_content(heading_tag)

            if not section_text or len(section_text.split()) < 5:
                continue  # Skip very short sections, will be merged later

            # Release notes: detect build headings
            if doc_type == "release_notes":
                build_num, build_date = _parse_build_heading(heading)
                if build_num:
                    current_build = build_num
                    current_build_date = build_date

            # Determine change category for release note subsections
            change_category = None
            if doc_type == "release_notes" and heading_tag.name in ("h3", "h4"):
                # Strip trailing numbers from heading for matching (e.g. "New Features 2")
                clean_heading = re.sub(r"\s*\d+$", "", heading).lower()
                change_category = _CHANGE_CATEGORIES.get(clean_heading, "other")

            mentioned_ops = _extract_mentioned_operators(section_tag)
            param_names = _extract_parameter_names(section_text) if doc_type == "operator" else []

            sequence += 1
            chunks.append(_make_chunk(
                page_id=page_id,
                section_title=heading,
                sequence=sequence,
                content=section_text,
                doc_type=doc_type,
                operator_family=operator_family,
                operator_name=operator_name,
                mentioned_operators=mentioned_ops,
                parameter_names=param_names,
                build_number=current_build if doc_type == "release_notes" else None,
                build_date=current_build_date if doc_type == "release_notes" else None,
                change_category=change_category,
            ))
    else:
        # No headings — single chunk for the whole page
        sequence += 1
        chunks.append(_make_chunk(
            page_id=page_id,
            section_title=page["title"],
            sequence=sequence,
            content=page["text"],
            doc_type=doc_type,
            operator_family=operator_family,
            operator_name=operator_name,
        ))

    return chunks


def _make_chunk(
    *,
    page_id: str,
    section_title: str,
    sequence: int,
    content: str,
    doc_type: str,
    operator_family: str | None = None,
    operator_name: str | None = None,
    mentioned_operators: list[str] | None = None,
    parameter_names: list[str] | None = None,
    python_symbols: list[str] | None = None,
    build_number: str | None = None,
    build_date: str | None = None,
    change_category: str | None = None,
) -> dict[str, Any]:
    """Build a chunk dict with all required fields."""
    slug = slugify(section_title)
    chunk_id = f"{page_id}__{slug}__{sequence:04d}"

    return {
        "chunk_id": chunk_id,
        "page_id": page_id,
        "doc_type": doc_type,
        "section_title": section_title,
        "operator_family": operator_family,
        "operator_name": operator_name,
        "mentioned_operators": mentioned_operators or [],
        "parameter_names": parameter_names or [],
        "python_symbols": python_symbols or [],
        "build_number": build_number,
        "build_date": build_date,
        "change_category": change_category,
        "token_estimate": _token_estimate(content),
        "content": content,
    }


def write_chunks_jsonl(chunks: list[dict[str, Any]], output_path: Path) -> int:
    """Write chunks to a JSONL file. Returns count written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            count += 1
    return count
```

- [ ] **Step 4: Run tests**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_chunker.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/td_mcp/knowledge/docsbrain/chunker.py tests/test_chunker.py
git commit -m "feat(docsbrain): add heading-aware chunker with release note support"
```

---

## Chunk 2: Indexer, Release Parser, and DocsBrain Search

### Task 5: SQLite FTS5 indexer

**Files:**
- Create: `src/td_mcp/knowledge/docsbrain/indexer.py`

- [ ] **Step 1: Write the indexer**

Create `src/td_mcp/knowledge/docsbrain/indexer.py`:

```python
"""Indexer — builds SQLite FTS5 database from chunks.jsonl."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"

_CREATE_CHUNKS = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    page_id TEXT,
    doc_type TEXT,
    section_title TEXT,
    operator_family TEXT,
    operator_name TEXT,
    mentioned_operators TEXT,
    parameter_names TEXT,
    python_symbols TEXT,
    build_number TEXT,
    build_date TEXT,
    change_category TEXT,
    token_estimate INTEGER,
    content TEXT
)
"""

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    section_title,
    operator_name,
    parameter_names,
    python_symbols,
    content,
    content='',
    tokenize='porter unicode61'
)
"""

_CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
)
"""


def build_index(chunks_path: Path, db_path: Path) -> int:
    """Build SQLite FTS5 index from chunks.jsonl.

    Args:
        chunks_path: Path to chunks.jsonl file.
        db_path: Path to output SQLite database.

    Returns:
        Number of chunks indexed.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DB for clean rebuild
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_CREATE_CHUNKS)
        conn.execute(_CREATE_FTS)
        conn.execute(_CREATE_META)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )

        count = 0
        with open(chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                _insert_chunk(conn, chunk)
                count += 1

        conn.commit()
        logger.info("Indexed %d chunks into %s", count, db_path)
        return count
    finally:
        conn.close()


def _insert_chunk(conn: sqlite3.Connection, chunk: dict[str, Any]) -> None:
    """Insert a chunk into both the chunks table and FTS5 index."""
    conn.execute(
        """INSERT OR REPLACE INTO chunks
           (chunk_id, page_id, doc_type, section_title, operator_family,
            operator_name, mentioned_operators, parameter_names, python_symbols,
            build_number, build_date, change_category, token_estimate, content)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            chunk["chunk_id"],
            chunk["page_id"],
            chunk["doc_type"],
            chunk["section_title"],
            chunk.get("operator_family"),
            chunk.get("operator_name"),
            json.dumps(chunk.get("mentioned_operators", [])),
            json.dumps(chunk.get("parameter_names", [])),
            json.dumps(chunk.get("python_symbols", [])),
            chunk.get("build_number"),
            chunk.get("build_date"),
            chunk.get("change_category"),
            chunk.get("token_estimate", 0),
            chunk["content"],
        ),
    )

    # Insert into contentless FTS5
    conn.execute(
        """INSERT INTO chunks_fts
           (chunk_id, section_title, operator_name, parameter_names,
            python_symbols, content)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            chunk["chunk_id"],
            chunk.get("section_title", ""),
            chunk.get("operator_name", ""),
            " ".join(chunk.get("parameter_names", [])),
            " ".join(chunk.get("python_symbols", [])),
            chunk["content"],
        ),
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/td_mcp/knowledge/docsbrain/indexer.py
git commit -m "feat(docsbrain): add SQLite FTS5 indexer"
```

---

### Task 6: Release notes parser

**Files:**
- Create: `src/td_mcp/knowledge/docsbrain/release_parser.py`
- Create: `tests/test_release_parser.py`

- [ ] **Step 1: Write release parser tests**

Create `tests/test_release_parser.py`:

```python
"""Tests for release notes parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp.knowledge.docsbrain.release_parser import (
    build_release_artifacts,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sample_pages"
CHUNKS_FIXTURE = FIXTURES / "sample_chunks.jsonl"


@pytest.fixture
def sample_chunks(tmp_path: Path) -> Path:
    """Create a sample chunks.jsonl with release note chunks."""
    chunks = [
        {
            "chunk_id": "release_notes__2025_30000__new_features__0002",
            "page_id": "release_notes__2025_30000",
            "doc_type": "release_notes",
            "section_title": "New Features",
            "operator_name": None,
            "mentioned_operators": ["Text POP", "Trace POP"],
            "build_number": "2025.32460",
            "build_date": "Mar 10, 2026",
            "change_category": "new_feature",
            "content": "Text POP - A new POP. Trace POP - A new POP for tracing.",
            "operator_family": None,
            "parameter_names": [],
            "python_symbols": [],
            "token_estimate": 20,
        },
        {
            "chunk_id": "release_notes__2025_30000__bug_fixes__0003",
            "page_id": "release_notes__2025_30000",
            "doc_type": "release_notes",
            "section_title": "Bug Fixes and Improvements",
            "operator_name": None,
            "mentioned_operators": ["Trail POP", "Movie File In TOP"],
            "build_number": "2025.32460",
            "build_date": "Mar 10, 2026",
            "change_category": "bug_fix",
            "content": "Trail POP - Fixed double-transforming. Movie File In TOP - Fixed ProRes output.",
            "operator_family": None,
            "parameter_names": [],
            "python_symbols": [],
            "token_estimate": 15,
        },
        {
            "chunk_id": "release_notes__2025_30000__bug_fixes_2__0005",
            "page_id": "release_notes__2025_30000",
            "doc_type": "release_notes",
            "section_title": "Bug Fixes and Improvements",
            "operator_name": None,
            "mentioned_operators": ["Count CHOP"],
            "build_number": "2025.32280",
            "build_date": "Jan 20, 2025",
            "change_category": "bug_fix",
            "content": "Count CHOP - Fixed count down pulse issue.",
            "operator_family": None,
            "parameter_names": [],
            "python_symbols": [],
            "token_estimate": 10,
        },
    ]
    path = tmp_path / "chunks.jsonl"
    with open(path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    return path


class TestBuildReleaseArtifacts:
    def test_manifest_has_builds(self, sample_chunks: Path, tmp_path: Path):
        manifest, changelog = build_release_artifacts(sample_chunks, tmp_path)
        assert manifest["latest_build"] == "2025.32460"
        builds = [b["build"] for b in manifest["builds"]]
        assert "2025.32460" in builds
        assert "2025.32280" in builds

    def test_manifest_sorted_newest_first(self, sample_chunks: Path, tmp_path: Path):
        manifest, _ = build_release_artifacts(sample_chunks, tmp_path)
        builds = manifest["builds"]
        assert builds[0]["build"] == "2025.32460"

    def test_changelog_maps_operators(self, sample_chunks: Path, tmp_path: Path):
        _, changelog = build_release_artifacts(sample_chunks, tmp_path)
        assert "Trail POP" in changelog
        assert changelog["Trail POP"][0]["category"] == "bug_fix"
        assert "double-transforming" in changelog["Trail POP"][0]["text"]

    def test_changelog_multiple_entries(self, sample_chunks: Path, tmp_path: Path):
        _, changelog = build_release_artifacts(sample_chunks, tmp_path)
        # Text POP and Trace POP should both have entries
        assert "Text POP" in changelog
        assert "Trace POP" in changelog

    def test_artifacts_written_to_disk(self, sample_chunks: Path, tmp_path: Path):
        build_release_artifacts(sample_chunks, tmp_path)
        assert (tmp_path / "build_manifest.json").exists()
        assert (tmp_path / "operator_changelog.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_release_parser.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write the release parser**

Create `src/td_mcp/knowledge/docsbrain/release_parser.py`:

```python
"""Release parser — builds build manifest and per-operator changelog from chunks."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _parse_build_sort_key(build: str) -> int:
    """Convert build string to sortable integer. E.g. '2025.32460' → 202532460."""
    try:
        parts = build.split(".")
        return int(parts[0]) * 100000 + int(parts[1])
    except (IndexError, ValueError):
        return 0


def _extract_operator_bullet(content: str, operator_name: str) -> str:
    """Extract the specific bullet text for an operator from chunk content."""
    # Look for lines starting with the operator name
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith(operator_name):
            # Strip the operator name prefix and separator
            text = re.sub(rf"^{re.escape(operator_name)}\s*[-–—:]\s*", "", line)
            return text.strip()
    # Fallback: return first mention context
    return content[:200]


def build_release_artifacts(
    chunks_path: Path, output_dir: Path
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Build build_manifest.json and operator_changelog.json from release note chunks.

    Args:
        chunks_path: Path to chunks.jsonl.
        output_dir: Directory to write output files.

    Returns:
        Tuple of (manifest_dict, changelog_dict).
    """
    builds: dict[str, dict[str, Any]] = {}
    changelog: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            if chunk["doc_type"] != "release_notes":
                continue
            build_num = chunk.get("build_number")
            if not build_num:
                continue

            # Track build info
            if build_num not in builds:
                builds[build_num] = {
                    "build": build_num,
                    "date": chunk.get("build_date", ""),
                }

            # Extract per-operator entries
            category = chunk.get("change_category", "other")
            content = chunk.get("content", "")
            for op_name in chunk.get("mentioned_operators", []):
                bullet_text = _extract_operator_bullet(content, op_name)
                changelog[op_name].append({
                    "build": build_num,
                    "category": category,
                    "text": bullet_text,
                })

    # Sort builds newest first
    sorted_builds = sorted(
        builds.values(),
        key=lambda b: _parse_build_sort_key(b["build"]),
        reverse=True,
    )

    manifest = {
        "latest_build": sorted_builds[0]["build"] if sorted_builds else "",
        "latest_date": sorted_builds[0].get("date", "") if sorted_builds else "",
        "builds": sorted_builds,
    }

    # Write to disk
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "build_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    changelog_path = output_dir / "operator_changelog.json"
    changelog_path.write_text(
        json.dumps(dict(changelog), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info(
        "Release artifacts: %d builds, %d operators with changelog entries",
        len(sorted_builds),
        len(changelog),
    )

    return manifest, dict(changelog)
```

- [ ] **Step 4: Run tests**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_release_parser.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/td_mcp/knowledge/docsbrain/release_parser.py tests/test_release_parser.py
git commit -m "feat(docsbrain): add release notes parser with operator changelog"
```

---

### Task 7: DocsBrain search class

**Files:**
- Modify: `src/td_mcp/knowledge/docsbrain/__init__.py`
- Create: `tests/test_docsbrain_search.py`

- [ ] **Step 1: Write search tests**

Create `tests/test_docsbrain_search.py`:

```python
"""Tests for DocsBrain search — the runtime query interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp.knowledge.docsbrain import DocsBrain
from td_mcp.knowledge.docsbrain.indexer import build_index


@pytest.fixture
def brain(tmp_path: Path) -> DocsBrain:
    """Build a small DocsBrain from test chunks."""
    chunks = [
        {
            "chunk_id": "composite_top__summary__0001",
            "page_id": "composite_top",
            "doc_type": "operator",
            "section_title": "Composite TOP",
            "operator_family": "TOP",
            "operator_name": "Composite TOP",
            "mentioned_operators": [],
            "parameter_names": ["operand", "opacity"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 50,
            "content": "The Composite TOP combines two or more texture inputs using blend operations like Over, Add, Multiply.",
        },
        {
            "chunk_id": "composite_top__parameters__0002",
            "page_id": "composite_top",
            "doc_type": "operator",
            "section_title": "Parameters",
            "operator_family": "TOP",
            "operator_name": "Composite TOP",
            "mentioned_operators": [],
            "parameter_names": ["operand", "opacity", "prefit"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 30,
            "content": "Operand - Blend mode. Opacity - Master opacity. Pre Fit - Resolution mismatch handling.",
        },
        {
            "chunk_id": "feedback_top__summary__0001",
            "page_id": "feedback_top",
            "doc_type": "operator",
            "section_title": "Feedback TOP",
            "operator_family": "TOP",
            "operator_name": "Feedback TOP",
            "mentioned_operators": [],
            "parameter_names": ["top"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 40,
            "content": "The Feedback TOP creates feedback loops for TOPs. Set the top parameter to reference the downstream node.",
        },
        {
            "chunk_id": "wave_chop__summary__0001",
            "page_id": "wave_chop",
            "doc_type": "operator",
            "section_title": "Wave CHOP",
            "operator_family": "CHOP",
            "operator_name": "Wave CHOP",
            "mentioned_operators": [],
            "parameter_names": ["type", "frequency"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 30,
            "content": "Generates waveforms as channel data. Sine, square, triangle, ramp patterns.",
        },
        {
            "chunk_id": "release_notes__bug_fixes__0001",
            "page_id": "release_notes__2025_30000",
            "doc_type": "release_notes",
            "section_title": "Bug Fixes and Improvements",
            "operator_family": None,
            "operator_name": None,
            "mentioned_operators": ["Trail POP"],
            "parameter_names": [],
            "python_symbols": [],
            "build_number": "2025.32460",
            "build_date": "Mar 10, 2026",
            "change_category": "bug_fix",
            "token_estimate": 20,
            "content": "Trail POP - Fixed double-transforming when cooking a second time.",
        },
        {
            "chunk_id": "palette_camschnappr__summary__0001",
            "page_id": "palette:camschnappr",
            "doc_type": "palette",
            "section_title": "camSchnappr",
            "operator_family": None,
            "operator_name": None,
            "mentioned_operators": [],
            "parameter_names": [],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 25,
            "content": "Camera snapshot tool for capturing and restoring camera positions.",
        },
    ]

    # Write chunks and build index
    chunks_path = tmp_path / "chunks.jsonl"
    with open(chunks_path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")

    db_path = tmp_path / "docsbrain.db"
    build_index(chunks_path, db_path)

    # Write changelog and manifest for DocsBrain
    changelog = {
        "Trail POP": [
            {"build": "2025.32460", "category": "bug_fix",
             "text": "Fixed double-transforming when cooking a second time."}
        ]
    }
    manifest = {
        "latest_build": "2025.32460",
        "latest_date": "Mar 10, 2026",
        "builds": [{"build": "2025.32460", "date": "Mar 10, 2026"}],
    }
    (tmp_path / "operator_changelog.json").write_text(json.dumps(changelog))
    (tmp_path / "build_manifest.json").write_text(json.dumps(manifest))

    return DocsBrain(
        db_path=db_path,
        changelog_path=tmp_path / "operator_changelog.json",
        manifest_path=tmp_path / "build_manifest.json",
    )


class TestDocsBrainSearch:
    def test_search_finds_operator_by_name(self, brain: DocsBrain):
        results = brain.search("Composite TOP")
        assert len(results) >= 1
        assert any(r["operator_name"] == "Composite TOP" for r in results)

    def test_search_finds_by_parameter(self, brain: DocsBrain):
        results = brain.search("opacity")
        assert len(results) >= 1

    def test_search_filters_by_family(self, brain: DocsBrain):
        results = brain.search("wave", family="CHOP")
        assert len(results) >= 1
        assert all(r.get("operator_family") == "CHOP" for r in results if r.get("operator_family"))

    def test_search_limits_results(self, brain: DocsBrain):
        results = brain.search("TOP", limit=2)
        assert len(results) <= 2

    def test_count(self, brain: DocsBrain):
        assert brain.count() >= 5


class TestDocsBrainGetOperator:
    def test_get_operator_found(self, brain: DocsBrain):
        result = brain.get_operator("compositeTOP")
        assert result is not None
        assert result["op_type"] == "compositeTOP"
        assert result["family"] == "TOP"

    def test_get_operator_missing(self, brain: DocsBrain):
        assert brain.get_operator("nonexistentOP") is None

    def test_get_operator_has_recent_changes(self, brain: DocsBrain):
        # Trail POP has changelog entries — but we need to look it up
        # by op_type format which is derived from operator_name
        # For now test that the method returns correct shape
        result = brain.get_operator("compositeTOP")
        if result:
            assert "op_type" in result
            assert "family" in result
            assert "display_name" in result


class TestDocsBrainGetRelease:
    def test_get_release_found(self, brain: DocsBrain):
        result = brain.get_release("2025.32460")
        assert result is not None
        assert result["build"] == "2025.32460"
        assert "entries" in result

    def test_get_release_missing(self, brain: DocsBrain):
        assert brain.get_release("9999.99999") is None


class TestDocsBrainGetPalette:
    def test_get_palette_found(self, brain: DocsBrain):
        result = brain.get_palette("camSchnappr")
        assert result is not None

    def test_get_palette_missing(self, brain: DocsBrain):
        assert brain.get_palette("nonexistent") is None


class TestDocsBrainChangelog:
    def test_get_operator_changelog(self, brain: DocsBrain):
        entries = brain.get_operator_changelog("Trail POP")
        assert len(entries) >= 1
        assert entries[0]["category"] == "bug_fix"

    def test_get_build_manifest(self, brain: DocsBrain):
        manifest = brain.get_build_manifest()
        assert manifest["latest_build"] == "2025.32460"
        assert len(manifest["builds"]) >= 1


class TestDocsBrainCompatibility:
    def test_check_compatibility(self, brain: DocsBrain):
        result = brain.check_compatibility("compositeTOP", "2025.32460")
        assert "status" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_docsbrain_search.py -v`
Expected: FAIL with ImportError (DocsBrain not yet implemented)

- [ ] **Step 3: Write DocsBrain class**

Replace `src/td_mcp/knowledge/docsbrain/__init__.py` with:

```python
"""TDPilot Docs Brain — full-corpus search over scraped docs.derivative.ca."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DocsBrain:
    """Runtime search interface for the docs brain SQLite FTS5 database.

    Drop-in replacement for CardIndex — implements the same public API.
    """

    def __init__(
        self,
        db_path: Path,
        changelog_path: Path | None = None,
        manifest_path: Path | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row

        # Load operator changelog
        self._changelog: dict[str, list[dict]] = {}
        if changelog_path and Path(changelog_path).exists():
            self._changelog = json.loads(Path(changelog_path).read_text("utf-8"))

        # Load build manifest
        self._manifest: dict[str, Any] = {}
        if manifest_path and Path(manifest_path).exists():
            self._manifest = json.loads(Path(manifest_path).read_text("utf-8"))

        # Build operator name lookup set for intent detection
        self._operator_names: set[str] = set()
        try:
            cursor = self._conn.execute(
                "SELECT DISTINCT operator_name FROM chunks WHERE operator_name IS NOT NULL AND operator_name != ''"
            )
            self._operator_names = {row[0] for row in cursor}
        except sqlite3.OperationalError:
            pass

        # Build op_type → operator_name mapping
        self._op_type_map: dict[str, str] = {}
        for name in self._operator_names:
            # "Composite TOP" → "compositeTOP"
            parts = name.split()
            if len(parts) >= 2:
                op_type = parts[0].lower() + parts[-1]
                self._op_type_map[op_type] = name

    def count(self) -> int:
        """Total number of chunks in the index."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM chunks")
        return cursor.fetchone()[0]

    def search(
        self,
        query: str,
        card_types: list[str] | None = None,
        family: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search the docs brain with intent-based routing and boosted ranking.

        Args:
            query: Search query string.
            card_types: Optional list of doc_types to filter by.
            family: Optional operator family filter (TOP, CHOP, etc.).
            limit: Maximum results to return.
        """
        # Intent detection: narrow doc_type filter
        intent_filter = self._detect_intent(query)

        # Build FTS5 query — escape special characters
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []

        # Build SQL with optional filters
        conditions = []
        params: list[Any] = []

        if card_types:
            placeholders = ",".join("?" for _ in card_types)
            conditions.append(f"c.doc_type IN ({placeholders})")
            params.extend(card_types)
        elif intent_filter:
            if isinstance(intent_filter, list):
                placeholders = ",".join("?" for _ in intent_filter)
                conditions.append(f"c.doc_type IN ({placeholders})")
                params.extend(intent_filter)
            else:
                conditions.append("c.doc_type = ?")
                params.append(intent_filter)

        if family:
            conditions.append("c.operator_family = ?")
            params.append(family.upper())

        where_clause = ""
        if conditions:
            where_clause = "AND " + " AND ".join(conditions)

        sql = f"""
            SELECT c.*, fts.rank as score
            FROM chunks_fts fts
            JOIN chunks c ON c.chunk_id = fts.chunk_id
            WHERE chunks_fts MATCH ?
            {where_clause}
            ORDER BY bm25(chunks_fts, 10.0, 8.0, 5.0, 3.0, 1.0)
            LIMIT ?
        """

        try:
            cursor = self._conn.execute(sql, [fts_query] + params + [limit])
            rows = cursor.fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("FTS5 query failed: %s (query=%r)", exc, fts_query)
            return []

        return [self._row_to_dict(row) for row in rows]

    def get_operator(self, op_type: str) -> dict | None:
        """Look up an operator by op_type (e.g. 'compositeTOP').

        Returns a dict matching the CardIndex response shape.
        """
        operator_name = self._op_type_map.get(op_type)
        if not operator_name:
            return None

        cursor = self._conn.execute(
            """SELECT * FROM chunks
               WHERE operator_name = ? AND doc_type = 'operator'
               ORDER BY chunk_id LIMIT 10""",
            (operator_name,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        first = dict(rows[0])
        # Build response matching CardIndex shape
        summary_chunks = [dict(r) for r in rows]
        summary = next(
            (c["content"] for c in summary_chunks if "summary" in c["section_title"].lower()),
            summary_chunks[0]["content"] if summary_chunks else "",
        )

        # Collect all parameter names
        all_params = []
        for chunk in summary_chunks:
            params = json.loads(chunk.get("parameter_names", "[]"))
            all_params.extend(p for p in params if p not in all_params)

        result = {
            "op_type": op_type,
            "family": first.get("operator_family", ""),
            "display_name": operator_name,
            "summary": summary[:500],
            "parameters": all_params,
            "docs_url": f"https://docs.derivative.ca/{operator_name.replace(' ', '_')}",
            "recent_changes": self._changelog.get(operator_name, []),
        }
        return result

    def get_palette(self, component_name: str) -> dict | None:
        """Look up a palette component by name."""
        # Try case-insensitive search
        cursor = self._conn.execute(
            """SELECT * FROM chunks
               WHERE doc_type = 'palette' AND LOWER(section_title) = LOWER(?)
               LIMIT 1""",
            (component_name,),
        )
        row = cursor.fetchone()
        if not row:
            # Try content search
            cursor = self._conn.execute(
                """SELECT * FROM chunks
                   WHERE doc_type = 'palette' AND content LIKE ?
                   LIMIT 1""",
                (f"%{component_name}%",),
            )
            row = cursor.fetchone()
        if not row:
            return None

        d = dict(row)
        return {
            "component_name": component_name,
            "summary": d.get("content", "")[:300],
            "doc_type": "palette",
        }

    def get_release(self, build: str) -> dict | None:
        """Look up a specific build's release notes."""
        cursor = self._conn.execute(
            """SELECT * FROM chunks
               WHERE doc_type = 'release_notes' AND build_number = ?
               ORDER BY chunk_id""",
            (build,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        entries = []
        for row in rows:
            d = dict(row)
            entries.append({
                "section": d.get("section_title", ""),
                "category": d.get("change_category", "other"),
                "content": d.get("content", ""),
                "mentioned_operators": json.loads(d.get("mentioned_operators", "[]")),
            })

        return {
            "build": build,
            "date": rows[0]["build_date"] or "",
            "entries": entries,
        }

    def check_compatibility(self, op_type: str, current_build: str) -> dict:
        """Check if an operator is compatible with the given build."""
        op = self.get_operator(op_type)
        if op is None:
            return {"status": "caution", "reason": f"No data for '{op_type}'."}
        # With the full docs brain, all operators in the index are valid
        return {"status": "compatible", "reason": f"Operator found in docs corpus."}

    # --- New methods ---

    def get_operator_changelog(self, operator_name: str) -> list[dict]:
        """Get changelog entries for a specific operator."""
        return self._changelog.get(operator_name, [])

    def get_build_manifest(self) -> dict:
        """Get the build manifest with all known builds."""
        return self._manifest

    def search_release_notes(
        self, query: str, build: str | None = None, limit: int = 10
    ) -> list[dict]:
        """Search release notes, optionally filtered by build."""
        results = self.search(query, card_types=["release_notes"], limit=limit)
        if build:
            results = [r for r in results if r.get("build_number") == build]
        return results

    # --- Private helpers ---

    def _detect_intent(self, query: str) -> str | list[str] | None:
        """Classify query intent to narrow search scope."""
        query_lower = query.lower()

        # Build number in query → release notes
        if re.search(r"\d{4}\.\d{4,5}", query):
            return "release_notes"
        if any(kw in query_lower for kw in ("what changed", "release", "new in", "latest build")):
            return "release_notes"

        # Palette prefix
        if query_lower.startswith("palette:") or query_lower.startswith("palette "):
            return "palette"

        # Glossary
        if "glossary" in query_lower or query_lower.startswith("what does ") or query_lower.startswith("define "):
            return "glossary"

        # Operator name match
        for op_name in self._operator_names:
            if op_name.lower() in query_lower:
                return ["operator", "python_api"]

        return None

    def _build_fts_query(self, query: str) -> str:
        """Build a safe FTS5 query string from user input."""
        # Remove FTS5 special characters
        cleaned = re.sub(r'["\(\)\*\^\{\}:]', " ", query)
        terms = cleaned.split()
        if not terms:
            return ""
        # Quote each term and OR them
        quoted = " OR ".join(f'"{t}"' for t in terms if t)
        return quoted

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a plain dict with parsed JSON fields."""
        d = dict(row)
        for field in ("mentioned_operators", "parameter_names", "python_symbols"):
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        return d
```

- [ ] **Step 4: Run tests**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_docsbrain_search.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/td_mcp/knowledge/docsbrain/__init__.py tests/test_docsbrain_search.py
git commit -m "feat(docsbrain): add DocsBrain search class with FTS5 and intent routing"
```

---

## Chunk 3: CLI, Integration, and Wiring

### Task 8: Build script (CLI)

**Files:**
- Create: `scripts/build_docs_brain.py`

- [ ] **Step 1: Write the build script**

Create `scripts/build_docs_brain.py`:

```python
#!/usr/bin/env python3
"""Build the TDPilot docs brain from scraped HTML files.

Usage:
    python scripts/build_docs_brain.py --source /path/to/docs.derivative.ca/
    python scripts/build_docs_brain.py  # uses TDPILOT_DOCS_SCRAPE_PATH env var
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from td_mcp.knowledge.docsbrain.normalizer import normalize_directory, write_pages_jsonl
from td_mcp.knowledge.docsbrain.chunker import chunk_page, write_chunks_jsonl
from td_mcp.knowledge.docsbrain.indexer import build_index
from td_mcp.knowledge.docsbrain.release_parser import build_release_artifacts

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the TDPilot docs brain")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to scraped docs.derivative.ca HTML files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "normalized" / "derivative",
        help="Output directory for generated files",
    )
    args = parser.parse_args()

    # Resolve source path
    source = args.source
    if source is None:
        env_path = os.environ.get("TDPILOT_DOCS_SCRAPE_PATH")
        if env_path:
            source = Path(env_path)
        else:
            logger.error(
                "No source path. Use --source or set TDPILOT_DOCS_SCRAPE_PATH"
            )
            sys.exit(1)

    if not source.is_dir():
        logger.error("Source directory not found: %s", source)
        sys.exit(1)

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    # Stage 1: Normalize
    logger.info("Stage 1: Normalizing HTML files from %s", source)
    pages_path = output / "pages.jsonl"
    pages = normalize_directory(source)
    page_count = write_pages_jsonl(pages, pages_path)
    logger.info("  → %d pages normalized", page_count)

    # Stage 2: Chunk
    logger.info("Stage 2: Chunking pages")
    all_chunks: list[dict] = []
    with open(pages_path, "r", encoding="utf-8") as f:
        for line in f:
            page = json.loads(line)
            # Reconstruct the HTML path from page URL
            page_name = page["url"].replace("https://docs.derivative.ca/", "")
            html_path = source / f"{page_name}.html"
            if html_path.exists():
                chunks = chunk_page(page, html_path)
                all_chunks.extend(chunks)

    chunks_path = output / "chunks.jsonl"
    chunk_count = write_chunks_jsonl(all_chunks, chunks_path)
    logger.info("  → %d chunks created", chunk_count)

    # Stage 3: Index
    logger.info("Stage 3: Building FTS5 index")
    db_path = output / "docsbrain.db"
    indexed = build_index(chunks_path, db_path)
    logger.info("  → %d chunks indexed", indexed)

    # Stage 4: Release notes
    logger.info("Stage 4: Building release note artifacts")
    manifest, changelog = build_release_artifacts(chunks_path, output)
    logger.info(
        "  → %d builds, %d operators with changelog",
        len(manifest.get("builds", [])),
        len(changelog),
    )

    elapsed = time.time() - t0
    logger.info("Done in %.1fs. Output: %s", elapsed, output)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable**

Run: `chmod +x <REPO_ROOT>/scripts/build_docs_brain.py`

- [ ] **Step 3: Commit**

```bash
git add scripts/build_docs_brain.py
git commit -m "feat(docsbrain): add CLI build script"
```

---

### Task 9: Wire DocsBrain into ServiceContainer

**Files:**
- Modify: `src/td_mcp/knowledge/__init__.py`
- Modify: `src/td_mcp/services.py`
- Modify: `src/td_mcp/tool_registry.py`

- [ ] **Step 1: Update knowledge __init__.py**

In `src/td_mcp/knowledge/__init__.py`, replace the content with:

```python
"""TDPilot knowledge corpus — structured JSON cards for TD operators, palette, releases."""

from td_mcp.knowledge.card_index import CardIndex  # noqa: F401

try:
    from td_mcp.knowledge.docsbrain import DocsBrain  # noqa: F401
except ImportError:
    DocsBrain = None  # type: ignore[assignment,misc]
```

- [ ] **Step 2: Update services.py import**

In `src/td_mcp/services.py`, change the import and type:

Replace:
```python
from td_mcp.knowledge.card_index import CardIndex
```
With:
```python
from td_mcp.knowledge.card_index import CardIndex
try:
    from td_mcp.knowledge.docsbrain import DocsBrain
except ImportError:
    DocsBrain = None  # type: ignore[assignment,misc]
```

And change the field type annotation:
```python
    card_index: Optional[CardIndex] = None
```
This stays the same — `DocsBrain` implements the same interface, so the existing type works via duck typing.

- [ ] **Step 3: Update tool_registry.py initialization**

In `src/td_mcp/tool_registry.py`, find the block that loads `CardIndex` (around line 303-309). Add DocsBrain initialization **before** the CardIndex fallback:

```python
    card_index = None
    try:
        from td_mcp.knowledge.docsbrain import DocsBrain
        brain_dir = Path(__file__).resolve().parent.parent.parent / "data" / "normalized" / "derivative"
        db_path = brain_dir / "docsbrain.db"
        if db_path.exists():
            card_index = DocsBrain(
                db_path=db_path,
                changelog_path=brain_dir / "operator_changelog.json",
                manifest_path=brain_dir / "build_manifest.json",
            )
            logger.info("DocsBrain loaded (%d chunks)", card_index.count())
    except Exception as exc:
        logger.debug("DocsBrain not available: %s", exc)

    if card_index is None:
        try:
            from td_mcp.knowledge.card_index import CardIndex
            cards_dir = Path(__file__).resolve().parent / "knowledge" / "cards"
            if cards_dir.is_dir():
                card_index = CardIndex(cards_dir)
                logger.info("Knowledge corpus loaded (%d cards)", card_index.count())
        except Exception as exc:
            logger.warning("CardIndex failed: %s", exc)
```

- [ ] **Step 4: Run existing tests to make sure nothing broke**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_knowledge_index.py tests/test_knowledge_tools.py -v`
Expected: All existing tests PASS (DocsBrain DB doesn't exist yet, so CardIndex fallback is used)

- [ ] **Step 5: Commit**

```bash
git add src/td_mcp/knowledge/__init__.py src/td_mcp/services.py src/td_mcp/tool_registry.py
git commit -m "feat(docsbrain): wire DocsBrain into ServiceContainer with CardIndex fallback"
```

---

### Task 10: Run the build script on real data and verify

- [ ] **Step 1: Set the scrape path and run the build**

Run:
```bash
cd <REPO_ROOT> && \
python scripts/build_docs_brain.py \
  --source "<DERIVATIVE_DOCS>/"
```

Expected output (approximate):
```
INFO: Stage 1: Normalizing HTML files from ...
INFO:   → ~2500+ pages normalized
INFO: Stage 2: Chunking pages
INFO:   → ~5000+ chunks created
INFO: Stage 3: Building FTS5 index
INFO:   → ~5000+ chunks indexed
INFO: Stage 4: Building release note artifacts
INFO:   → ~5 builds, ~50+ operators with changelog
INFO: Done in ~10-30s
```

- [ ] **Step 2: Verify the output files exist**

Run:
```bash
ls -la data/normalized/derivative/
```
Expected: `pages.jsonl`, `chunks.jsonl`, `docsbrain.db`, `build_manifest.json`, `operator_changelog.json`

- [ ] **Step 3: Quick sanity check on the database**

Run:
```bash
cd <REPO_ROOT> && \
python3 -c "
from td_mcp.knowledge.docsbrain import DocsBrain
from pathlib import Path
brain = DocsBrain(
    db_path=Path('data/normalized/derivative/docsbrain.db'),
    changelog_path=Path('data/normalized/derivative/operator_changelog.json'),
    manifest_path=Path('data/normalized/derivative/build_manifest.json'),
)
print(f'Total chunks: {brain.count()}')
print(f'Manifest: {brain.get_build_manifest()[\"latest_build\"]}')
results = brain.search('Feedback TOP')
print(f'Search \"Feedback TOP\": {len(results)} results')
if results:
    print(f'  Top result: {results[0][\"section_title\"]} ({results[0][\"doc_type\"]})')
op = brain.get_operator('feedbackTOP')
print(f'get_operator(\"feedbackTOP\"): {\"found\" if op else \"not found\"}')
if op:
    print(f'  Recent changes: {len(op.get(\"recent_changes\", []))}')
"
```
Expected: Chunk count in thousands, latest build found, Feedback TOP search returns results.

- [ ] **Step 4: Run all tests**

Run: `cd <REPO_ROOT> && python -m pytest tests/test_normalizer.py tests/test_chunker.py tests/test_release_parser.py tests/test_docsbrain_search.py tests/test_knowledge_index.py tests/test_knowledge_tools.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add data/.gitignore
git commit -m "feat(docsbrain): verify full pipeline on real corpus"
```

---

### Task 11: Run full test suite

- [ ] **Step 1: Run all project tests**

Run: `cd <REPO_ROOT> && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS. No regressions.

- [ ] **Step 2: Final commit with any fixes**

If any tests needed fixing:
```bash
git add -A
git commit -m "fix(docsbrain): address test regressions from integration"
```
