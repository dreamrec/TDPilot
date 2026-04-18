"""Normalizer — reads scraped HTML files and produces pages.jsonl."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

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
