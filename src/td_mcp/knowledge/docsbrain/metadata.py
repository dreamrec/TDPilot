"""Page classification and metadata extraction for the docs brain."""

from __future__ import annotations

import re

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


def classify_page(filename: str) -> str | None:
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


def extract_operator_family(filename: str) -> str | None:
    """Extract operator family (TOP, CHOP, etc.) from filename."""
    for family in _OP_FAMILIES:
        if filename.endswith(f"_{family}.html") or filename.endswith(f"_{family}"):
            return family
    return None


def extract_operator_name(title: str) -> str | None:
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
