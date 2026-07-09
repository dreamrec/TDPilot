#!/usr/bin/env python3
"""Generate the tool-reference region of docs/API_REFERENCE.md from the registry.

Why this exists (audit batch E): the API reference was hand-maintained and
silently drifted — an audit found tools missing from the doc entirely. The
FastMCP registry (``server.mcp.list_tools()``) is the single source of truth
for the tool surface, so the doc's tool tables are now generated from it.

What is generated vs hand-written
---------------------------------
Only the region between the BEGIN/END markers is generated:

    <!-- BEGIN GENERATED: tool-reference (scripts/gen_api_reference.py) -->
    ...header, table of contents, per-module tool tables...
    <!-- END GENERATED: tool-reference -->

Everything outside the markers (Environment Variables, the ``_read_journal``
envelope note, exec-mode tables, etc.) is hand-written prose and preserved
verbatim on every regeneration.

Grouping
--------
Sections are derived from each tool's registry module of origin
(``src/td_mcp/registry/tools_*.py``), resolved by AST-scanning the decorator
registrations. This is the maintainable choice: adding a tool to a module
automatically lands it in the right doc section with zero doc edits, and a
brand-new module gets an auto-titled section appended (add a friendly title
to ``_SECTION_TITLES`` when that happens).

Usage
-----
    uv run python scripts/gen_api_reference.py           # regenerate in place
    uv run python scripts/gen_api_reference.py --check   # CI freshness gate
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "API_REFERENCE.md"
REGISTRY_DIR = ROOT / "src" / "td_mcp" / "registry"

BEGIN_MARKER = "<!-- BEGIN GENERATED: tool-reference (scripts/gen_api_reference.py) -->"
END_MARKER = "<!-- END GENERATED: tool-reference -->"

# module stem -> human section title, in doc order. Modules present in the
# registry but missing here still get a section (prettified stem, appended
# after the known ones) so a new module can never silently vanish from docs.
_SECTIONS: list[tuple[str, str]] = [
    ("tools_info", "Scene & Server Info"),
    ("tools_graph", "Node Graph & Parameters"),
    ("tools_content", "Content & Python Execution"),
    ("tools_data", "Data Inspection & Diagnostics"),
    ("tools_state", "Runtime State"),
    ("tools_runtime", "Timeline, Lifecycle & Python Help"),
    ("tools_events", "Events & Subscriptions"),
    ("tools_memory", "Technique Memory & Preferences"),
    ("tools_knowledge_store", "User Knowledge Store"),
    ("tools_safety", "Safety & Stability"),
    ("tools_snapshots", "Snapshots"),
    ("tools_macros", "Macros"),
    ("tools_planning", "Planning & Project Audit"),
    ("tools_patch", "Patch Pipeline"),
    ("tools_vision", "Vision & Frame Analysis"),
    ("tools_streaming", "Visual Monitoring & Streaming"),
    ("tools_optimizer", "Visual Optimization & Dynamics"),
    ("tools_knowledge", "Official & POPx Knowledge"),
    ("tools_recommendations", "Recommendations"),
    ("tools_hints", "Hints"),
    ("tools_notes", "Component Notes"),
    ("tools_system", "TD 2025 Native & System"),
    ("tools_batch", "Tool Batch"),
    ("tools_brain", "Brain Planning & Transactions"),
    ("tools_meta", "Sync, Self-Update & Activity"),
]


def scan_tool_modules() -> dict[str, str]:
    """Map tool name -> registry module stem by AST-scanning ``@mcp.tool``.

    Handles both ``@mcp.tool(name="td_x")`` and bare ``@mcp.tool()`` (where
    the function name is the tool name), including multi-line decorators
    with nested calls (``annotations=ToolAnnotations(...)``).
    """
    mapping: dict[str, str] = {}
    for path in sorted(REGISTRY_DIR.glob("tools_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "tool"
                ):
                    name = node.name
                    for kw in dec.keywords:
                        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                            name = str(kw.value.value)
                    mapping[name] = path.stem
    return mapping


def list_registry_tools() -> list[Any]:
    # Imported lazily so ``--help`` works without the package importable.
    import td_mcp.server as server

    return asyncio.run(server.mcp.list_tools())


def _escape_cell(text: str) -> str:
    """Make arbitrary text safe inside a one-line markdown table cell."""
    return " ".join(text.replace("|", "\\|").split())


def _first_paragraph(text: str) -> str:
    return text.strip().split("\n\n", 1)[0]


def _returns_summary(description: str) -> str:
    """Pull a 'Returns ...' sentence out of the docstring, else a fallback.

    Every tool returns a JSON string envelope, so the fallback is honest
    rather than invented.
    """
    for raw_line in description.splitlines():
        line = raw_line.strip()
        if line.lower().startswith("returns"):
            return line
    match = re.search(r"(?:^|\.\s+)(Returns? [^.]*\.)", description)
    if match:
        return match.group(1).strip()
    return "JSON envelope (string)."


def _deref(prop: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    ref = prop.get("$ref", "")
    if ref.startswith("#/$defs/"):
        resolved = dict(defs.get(ref.split("/")[-1], {}))
        # Local keys (description/default) win over the referenced schema.
        resolved.update({k: v for k, v in prop.items() if k != "$ref"})
        return resolved
    return prop


def _prop_type(prop: dict[str, Any], defs: dict[str, Any]) -> str:
    prop = _deref(prop, defs)
    if "enum" in prop:
        values = ", ".join(f"`{v}`" for v in prop["enum"])
        return f"enum: {values}"
    if "anyOf" in prop:
        parts = [_prop_type(member, defs) for member in prop["anyOf"]]
        parts = [p for p in parts if p and p != "null"]
        return " \\| ".join(dict.fromkeys(parts)) or "any"
    ptype = prop.get("type")
    if ptype == "array":
        items = prop.get("items") or {}
        inner = _prop_type(items, defs) if items else "any"
        return f"list[{inner}]"
    if ptype is None:
        return "any"
    return str(ptype)


def _format_param(name: str, prop: dict[str, Any], required: bool, defs: dict[str, Any]) -> str:
    resolved = _deref(prop, defs)
    bits = [_prop_type(prop, defs), "**required**" if required else "opt"]
    if not required and "default" in resolved:
        bits.append(f"default `{json.dumps(resolved['default'])}`")
    header = f"`{name}` ({', '.join(bits)})"
    description = str(resolved.get("description") or "").strip()
    if description:
        return f"{header}: {_escape_cell(description)}"
    return header


def _anchor(title: str) -> str:
    slug = re.sub(r"[^0-9a-z\s-]", "", title.lower())
    return re.sub(r"\s", "-", slug)


def build_generated_region() -> str:
    from td_mcp import __version__

    tools = list_registry_tools()
    module_of = scan_tool_modules()

    known_stems = [stem for stem, _ in _SECTIONS]
    extra_stems = sorted({module_of.get(t.name, "unknown") for t in tools} - set(known_stems))
    sections: list[tuple[str, str]] = list(_SECTIONS) + [
        (stem, stem.removeprefix("tools_").replace("_", " ").title()) for stem in extra_stems
    ]

    by_module: dict[str, list[Any]] = {}
    for tool in tools:
        by_module.setdefault(module_of.get(tool.name, "unknown"), []).append(tool)

    lines: list[str] = [BEGIN_MARKER, ""]
    lines.append(
        f"> TDPilot v{__version__} | {len(tools)} tools | This region is **generated** from the "
        "FastMCP registry by `scripts/gen_api_reference.py` — do not edit it by hand. "
        "Regenerate with `uv run python scripts/gen_api_reference.py`; CI enforces freshness "
        "with `--check`. Sections group tools by their `src/td_mcp/registry/` module of origin."
    )
    lines.append("")
    lines.append("## Table of Contents")
    lines.append("")
    index = 0
    numbered: list[tuple[int, str, str]] = []  # (number, stem, title)
    for stem, title in sections:
        if not by_module.get(stem):
            continue
        index += 1
        numbered.append((index, stem, title))
        lines.append(f"{index}. [{title}](#{_anchor(f'{index} {title}')})")
    lines.append("")
    lines.append(
        "_Hand-written sections (response envelope, environment variables, exec modes, "
        "response formats, macro types) follow the generated region below._"
    )
    lines.append("")

    for number, stem, title in numbered:
        lines.append("---")
        lines.append("")
        lines.append(f"## {number}. {title}")
        lines.append("")
        lines.append(f"_Registry module: `src/td_mcp/registry/{stem}.py`_")
        lines.append("")
        lines.append("| Tool | Description | Parameters | Returns |")
        lines.append("|------|-------------|------------|---------|")
        for tool in sorted(by_module[stem], key=lambda t: t.name):
            schema = tool.inputSchema or {}
            defs = schema.get("$defs", {})
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))
            description = tool.description or ""
            desc_cell = _escape_cell(_first_paragraph(description)) or "_(no description)_"
            if properties:
                params_cell = "<br>".join(
                    _format_param(name, prop, name in required, defs) for name, prop in properties.items()
                )
            else:
                params_cell = "_(none)_"
            returns_cell = _escape_cell(_returns_summary(description))
            lines.append(f"| `{tool.name}` | {desc_cell} | {params_cell} | {returns_cell} |")
        lines.append("")

    lines.append(END_MARKER)
    return "\n".join(lines)


def render_document(current: str) -> str:
    begin = current.find(BEGIN_MARKER)
    end = current.find(END_MARKER)
    if begin == -1 or end == -1 or end < begin:
        raise SystemExit(
            f"ERROR: {DOC_PATH} is missing the generated-region markers.\n"
            f"Expected both:\n  {BEGIN_MARKER}\n  {END_MARKER}\n"
            "Restore them (see git history) before regenerating."
        )
    tail_start = end + len(END_MARKER)
    return current[:begin] + build_generated_region() + current[tail_start:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if docs/API_REFERENCE.md is stale instead of rewriting it.",
    )
    args = parser.parse_args(argv)

    current = DOC_PATH.read_text(encoding="utf-8")
    rendered = render_document(current)

    if args.check:
        if rendered != current:
            print(
                "docs/API_REFERENCE.md is STALE relative to the tool registry.\n"
                "Regenerate it with: uv run python scripts/gen_api_reference.py",
                file=sys.stderr,
            )
            return 1
        print("docs/API_REFERENCE.md is up to date with the tool registry.")
        return 0

    if rendered == current:
        print("docs/API_REFERENCE.md already up to date.")
        return 0
    DOC_PATH.write_text(rendered, encoding="utf-8")
    print(f"Regenerated tool-reference region of {DOC_PATH.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
