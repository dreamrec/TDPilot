"""Chunker — splits normalized pages into searchable chunks by heading."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

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
_BUILD_HEADING_RE = re.compile(r"Build\s+(\d{4}\.\d{4,5})\s+(\w+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE)


def _extract_mentioned_operators(section: Tag) -> list[str]:
    """Extract operator names mentioned in <a> links within a section."""
    ops = []
    for a in section.find_all("a"):
        title = a.get("title", "")
        if title and any(
            title.endswith(f" {fam}") for fam in ("TOP", "CHOP", "SOP", "DAT", "COMP", "MAT", "POP")
        ):
            if title not in ops:
                ops.append(title)
    return ops


def _extract_parameter_names(section: Tag | str) -> list[str]:
    """Extract operator parameter rows while ignoring menu-choice bullets."""
    if isinstance(section, Tag):
        params = _extract_parameter_names_from_html(section)
        if params:
            return params
        text = section.get_text(separator="\n", strip=True)
    else:
        text = section
    return _extract_parameter_names_from_text(text)


def _extract_parameter_names_from_html(section: Tag) -> list[str]:
    params: list[str] = []
    seen: set[str] = set()
    for element in section.find_all(["p", "div"], recursive=True):
        if element.find_parent("li"):
            continue
        if _has_class(element, "mw-collapsible") or element.find_parent(class_="mw-collapsible"):
            continue
        text = element.get_text(separator="\n", strip=True)
        if not text or not re.search(r"[-\u2013\u2014]", text):
            continue

        code = element.find("code", recursive=False)
        if code is not None:
            raw_name = code.get_text(strip=True)
            if _looks_like_internal_param_name(raw_name):
                label = _label_before_child(element, code)
                param = _format_param_candidate(label, raw_name)
                if param and param not in seen:
                    params.append(param)
                    seen.add(param)
                    continue

        bold = element.find(["b", "strong"], recursive=False)
        if bold is not None:
            param = _format_param_candidate(bold.get_text(" ", strip=True), None)
            if param and param not in seen:
                params.append(param)
                seen.add(param)
                continue

        if not element.find(["p", "div", "ul", "ol"], recursive=False):
            for param in _extract_parameter_names_from_text(text):
                if param not in seen:
                    params.append(param)
                    seen.add(param)

    return params


def _has_class(element: Tag, class_name: str) -> bool:
    classes = element.get("class") or []
    return class_name in classes


def _label_before_child(element: Tag, stop_child: Tag) -> str:
    parts: list[str] = []
    for child in element.children:
        if child is stop_child:
            break
        if isinstance(child, Tag):
            parts.append(child.get_text(" ", strip=True))
        else:
            parts.append(str(child))
    return " ".join(part.strip() for part in parts if part.strip())


def _format_param_candidate(label: str, raw_name: str | None) -> str | None:
    label = re.sub(r"\s+", " ", label).strip(" -\u2013\u2014\t\n")
    if not label or len(label) >= 80 or label[0].islower():
        return None
    if raw_name:
        return f"{label}\n{raw_name}"
    if len(label) < 40:
        return label
    return None


def _looks_like_internal_param_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name))


def _extract_parameter_names_from_text(text: str) -> list[str]:
    """Extract parameter-like rows from normalized section text."""
    params = []
    for match in re.finditer(r"(?:^|\n)\s*(\w[\w\s]*?)\s*[-\u2013\u2014]", text):
        candidate = match.group(1).strip()
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
            chunks.append(
                _make_chunk(
                    page_id=page_id,
                    section_title=page["title"],
                    sequence=sequence,
                    content=intro_text,
                    doc_type=doc_type,
                    operator_family=operator_family,
                    operator_name=operator_name,
                )
            )

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
            param_names = _extract_parameter_names(section_tag) if doc_type == "operator" else []

            sequence += 1
            chunks.append(
                _make_chunk(
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
                )
            )
    else:
        # No headings — single chunk for the whole page
        sequence += 1
        chunks.append(
            _make_chunk(
                page_id=page_id,
                section_title=page["title"],
                sequence=sequence,
                content=page["text"],
                doc_type=doc_type,
                operator_family=operator_family,
                operator_name=operator_name,
            )
        )

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
