#!/usr/bin/env python3
"""Atomically bump version and/or tool-count across all canonical and user-facing files.

Usage:
    release_bump.py [--version X.Y.Z] [--tool-count N] [--api-version X.Y.Z]
                    [--dry-run] [--changelog-stub]

  --version          New X.Y.Z. If omitted, version files are not touched.
  --tool-count       New tool count integer. If omitted, count files not touched.
  --api-version      Override API_VERSION in mcp_webserver_callbacks.py if you
                     want it to differ from --version (rare). Default: same as
                     --version.
  --dry-run          Print unified diffs of every change, write nothing.
  --changelog-stub   Insert a "## vX.Y.Z (YYYY-MM-DD) — TBD" header at the top
                     of CHANGELOG.md (after the # Changelog line).
"""

from __future__ import annotations

import argparse
import collections
import difflib
import json
import os
import re
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Transformation registry
# Maps path → ordered list of (transform_fn, description) pairs.
# Each transform_fn takes a string (current text) and returns the new text.
# All transforms for a file are applied in sequence on the accumulated text.
# ---------------------------------------------------------------------------

TransformFn = Callable[[str], str]
TransformEntry = tuple[TransformFn, str]  # (fn, human-readable description)

_transforms: dict[Path, list[TransformEntry]] = collections.defaultdict(list)
_parse_errors: list[str] = []


def _register(rel: str, fn: TransformFn, desc: str, required_file: bool = True) -> None:
    """Register a transformation for the given relative path.

    If ``required_file`` is False, missing files are silently skipped instead of
    failing the run. Use for surfaced-post-design files that may not exist in
    every checkout (e.g. partial test fixtures, slimmed-down distributions).
    """
    path = ROOT / rel
    if not path.exists():
        if required_file:
            _parse_errors.append(f"File not found: {rel}")
        return
    _transforms[path].append((fn, desc))


def _regex_transform(
    pattern: str,
    replacement: str,
    flags: int = 0,
    count: int = 0,
    required: bool = True,
) -> TransformFn:
    """Return a function that applies a regex substitution to text."""
    compiled = re.compile(pattern, flags)

    def transform(text: str) -> str:
        new_text, n = compiled.subn(replacement, text, count=count)
        if n == 0 and required:
            raise ValueError(f"Pattern {pattern!r} matched nothing")
        return new_text

    return transform


# ---------------------------------------------------------------------------
# Current-value readers (for no-op detection)
# ---------------------------------------------------------------------------


def _current_version() -> str | None:
    path = ROOT / "src" / "td_mcp" / "__init__.py"
    if not path.exists():
        return None
    m = re.search(r'__version__\s*=\s*"([^"]+)"', path.read_text())
    return m.group(1) if m else None


def _current_tool_count() -> int | None:
    path = ROOT / "src" / "td_mcp" / "release_gates.py"
    if not path.exists():
        return None
    m = re.search(r"EXPECTED_MIN_TOOL_COUNT\s*:\s*int\s*=\s*(\d+)", path.read_text())
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Version transforms
# ---------------------------------------------------------------------------


def _register_version_transforms(new_ver: str, api_ver: str) -> None:
    V = new_ver

    def r(rel: str, pattern: str, repl: str, flags: int = 0, required: bool = True) -> None:
        _register(
            rel, _regex_transform(pattern, repl, flags=flags, required=required), f"version: {pattern!r}"
        )

    # 1. pyproject.toml
    r("pyproject.toml", r'^(version\s*=\s*")[^"]+(")', rf"\g<1>{V}\g<2>", re.MULTILINE)

    # 2. src/td_mcp/__init__.py
    r("src/td_mcp/__init__.py", r'(__version__\s*=\s*")[^"]+(")', rf"\g<1>{V}\g<2>")

    # 3–6. JSON files — regex preserves formatting
    for rel in (
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        "npm/package.json",
        "mcp/manifest.json",
    ):
        r(rel, r'("version"\s*:\s*")[^"]+(")', rf"\g<1>{V}\g<2>")

    # 7. td_component/mcp_webserver_callbacks.py  (API_VERSION)
    r("td_component/mcp_webserver_callbacks.py", r'(API_VERSION\s*=\s*")[^"]+(")', rf"\g<1>{api_ver}\g<2>")

    # --- check_versions.py gated files: ---

    # plugin_README.md  — "TDPilot vX.Y.Z provides"
    r("plugin_README.md", r"(TDPilot v)\d+\.\d+\.\d+", rf"\g<1>{V}")

    # docs/API_REFERENCE.md  — "Auto-generated from TDPilot vX.Y.Z"
    r("docs/API_REFERENCE.md", r"(Auto-generated from TDPilot v)\d+\.\d+\.\d+", rf"\g<1>{V}")

    # docs/MANUAL.md  — "# TDPilot vX.Y.Z"
    r("docs/MANUAL.md", r"(# TDPilot v)\d+\.\d+\.\d+", rf"\g<1>{V}")

    # npm/README.md  — "# TDPilot vX.Y.Z"
    r("npm/README.md", r"(# TDPilot v)\d+\.\d+\.\d+", rf"\g<1>{V}")

    # skills/tdpilot-core/SKILL.md  — "TDPilot Core vX.Y.Z" and "for TDPilot vX.Y.Z"
    r("skills/tdpilot-core/SKILL.md", r"(TDPilot (?:Core )?v)\d+\.\d+\.\d+", rf"\g<1>{V}")

    # skills/tdpilot-production/SKILL.md
    r("skills/tdpilot-production/SKILL.md", r"(TDPilot (?:Production )?v)\d+\.\d+\.\d+", rf"\g<1>{V}")

    # README.md  — title "# TDPilot Runtime vX.Y.Z"
    r("README.md", r"(# TDPilot Runtime v)\d+\.\d+\.\d+", rf"\g<1>{V}")

    # README.md  — "## What's New In X.Y.Z" — FIRST occurrence only (most recent entry)
    def _readme_whats_new(text: str) -> str:
        return re.sub(
            r"(## What[''']s New In )\d+\.\d+\.\d+",
            rf"\g<1>{V}",
            text,
            count=1,
        )

    _register("README.md", _readme_whats_new, f"README What's New In → {V}")


# ---------------------------------------------------------------------------
# Tool-count transforms
# ---------------------------------------------------------------------------


def _register_tool_count_transforms(new_count: int) -> None:
    nc = str(new_count)

    def r(
        rel: str,
        pattern: str,
        repl: str,
        flags: int = 0,
        required: bool = True,
        required_file: bool = True,
    ) -> None:
        _register(
            rel,
            _regex_transform(pattern, repl, flags=flags, required=required),
            f"tool-count: {pattern!r}",
            required_file=required_file,
        )

    # Canonical source
    r("src/td_mcp/release_gates.py", r"(EXPECTED_MIN_TOOL_COUNT\s*:\s*int\s*=\s*)\d+", rf"\g<1>{nc}")

    # mcp/manifest.json — integer field
    r("mcp/manifest.json", r'("tool_count"\s*:\s*)\d+', rf"\g<1>{nc}")

    # JSON description fields — "N tools" or "N MCP tools" in description strings
    for rel in (
        ".claude-plugin/marketplace.json",
        ".claude-plugin/plugin.json",
        "npm/package.json",
    ):
        r(rel, r"(\d+)(\s+(?:MCP\s+)?tools)", rf"{nc}\2")

    # README.md — badge
    r("README.md", r"(MCP%20tools-)\d+(-blueviolet)", rf"\g<1>{nc}\g<2>")
    # README.md — prose "101 MCP tools" and "101-tool runtime"
    r("README.md", r"\b\d+(\s+MCP\s+tools|\s*-tool\s+runtime)", rf"{nc}\1")
    # README.md — "Tool Map (101 Tools)" heading
    r("README.md", r"(## Tool Map \()\d+( Tools\))", rf"\g<1>{nc}\g<2>")

    # README.md — "Tool count: 97 → 101" in the What's New section (first occurrence only)
    def _readme_tool_count_arrow(text: str) -> str:
        m = re.search(r"Tool count:.*?→\s*\d+", text)
        if m:
            return (
                text[: m.start()]
                + re.sub(r"(Tool count:.*?→\s*)\d+", rf"\g<1>{nc}", m.group(0))
                + text[m.end() :]
            )
        return text

    _register("README.md", _readme_tool_count_arrow, f"README Tool count arrow → {nc}")

    # npm/README.md
    r("npm/README.md", r"(MCP%20tools-)\d+(-blueviolet)", rf"\g<1>{nc}\g<2>")
    r("npm/README.md", r"\b\d+(\s+tools\b)", rf"{nc}\1")

    # plugin_README.md — "provides N MCP tools" and "N-tool reference"
    r("plugin_README.md", r"\b\d+(\s+MCP\s+tools|\s*-tool\s+reference)", rf"{nc}\1")

    # docs/API_REFERENCE.md — "| N tools |" header
    r("docs/API_REFERENCE.md", r"\b\d+(\s+tools\b)", rf"{nc}\1")

    # docs/USER_GUIDE.md
    r("docs/USER_GUIDE.md", r"\b\d+(\s+tools\b)", rf"{nc}\1")

    # docs/GETTING_STARTED.md
    r("docs/GETTING_STARTED.md", r"\b\d+(\s+tools\b)", rf"{nc}\1")

    # skills/tdpilot-core/SKILL.md
    r("skills/tdpilot-core/SKILL.md", r"\b\d+(\s*-tool\s+reference|\s+MCP\s+tools|\s+tools\b)", rf"{nc}\1")
    # Complete Tool Surface heading e.g. "(101 tools, 6 resource templates)"
    r("skills/tdpilot-core/SKILL.md", r"(Complete Tool Surface.*?\()\d+(\s+tools)", rf"\g<1>{nc}\g<2>")

    # skills/tdpilot-production/SKILL.md
    r(
        "skills/tdpilot-production/SKILL.md",
        r"\b\d+(\s*-tool\s+reference|\s+MCP\s+tools|\s+tools\b)",
        rf"{nc}\1",
    )

    # CHANGELOG.md — only the FIRST entry's "Tool count: N → M" line
    def _changelog_tool_count(text: str) -> str:
        # Find the first ## section (skip the title line)
        first_section_match = re.search(r"\n##\s+", text[1:])
        search_limit = (first_section_match.start() + 1) if first_section_match else len(text)
        m = re.search(r"(Tool count:.*?→\s*)\d+", text[:search_limit])
        if m:
            return text[: m.start()] + m.group(1) + nc + text[m.end() :]
        return text

    _register("CHANGELOG.md", _changelog_tool_count, f"CHANGELOG Tool count → {nc}")

    # docs/MANUAL.md — optional: may not have bare numeric count
    r("docs/MANUAL.md", r"\b\d+(\s+tools\b)", rf"{nc}\1", required=False)

    # --- Files surfaced post-design that also reference the count ---

    # docs/INSTALL_CLAUDE_PLUGIN.md — "You get N MCP tools" prose line
    r(
        "docs/INSTALL_CLAUDE_PLUGIN.md",
        r"\b\d+(\s+MCP\s+tools\b)",
        rf"{nc}\1",
        required=False,
        required_file=False,
    )

    # scripts/build_mcpb.py — hardcoded description strings (.mcpb metadata
    # ships to Claude Desktop's plugin panel, so this IS user-facing)
    # Two occurrences: "N MCP tools" and "exposes N tools"
    r(
        "scripts/build_mcpb.py",
        r"\b\d+(\s+(?:MCP\s+)?tools\b)",
        rf"{nc}\1",
        required=False,
        required_file=False,
    )

    # src/td_mcp/registry/tools_info.py — module docstring "all N tools"
    r(
        "src/td_mcp/registry/tools_info.py",
        r"\b\d+(\s+tools\b)",
        rf"{nc}\1",
        required=False,
        required_file=False,
    )

    # tests/test_cli.py — comment "match at N tools" referencing canonical count.
    # NOTE: long-term this test should import EXPECTED_MIN_TOOL_COUNT instead of
    # hardcoding; tracked as a follow-up. For now, keep the comment in sync.
    r(
        "tests/test_cli.py",
        r"(match at )\d+(\s+tools\b)",
        rf"\g<1>{nc}\g<2>",
        required=False,
        required_file=False,
    )


# ---------------------------------------------------------------------------
# Changelog stub
# ---------------------------------------------------------------------------


def _register_changelog_stub(new_ver: str) -> None:
    today = date.today().strftime("%Y-%m-%d")
    stub = f"\n## {new_ver} - {today} — TBD\n"

    def _transform(text: str) -> str:
        return re.sub(
            r"(^# Changelog\s*\n)",
            rf"\1{stub}",
            text,
            count=1,
            flags=re.MULTILINE,
        )

    _register("CHANGELOG.md", _transform, f"changelog stub for {new_ver}")


# ---------------------------------------------------------------------------
# Apply transforms and compute diffs
# ---------------------------------------------------------------------------


def _compute_changes() -> tuple[dict[Path, tuple[str, str]], list[str]]:
    """
    Apply all registered transforms in order.

    Returns:
        (changed_files, errors)
        changed_files: {path: (original_text, final_text)} for files that differ
        errors: list of error messages from transforms that failed
    """
    changed: dict[Path, tuple[str, str]] = {}
    errors: list[str] = []

    if _parse_errors:
        errors.extend(_parse_errors)
        return changed, errors

    for path, transform_list in _transforms.items():
        try:
            original = path.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(f"Could not read {path.relative_to(ROOT)}: {e}")
            continue

        current = original
        for fn, desc in transform_list:
            try:
                current = fn(current)
            except ValueError as e:
                errors.append(f"{path.relative_to(ROOT)}: {e}")
                break

        if current != original:
            changed[path] = (original, current)

    return changed, errors


def _unified_diff(path: Path, old: str, new: str) -> str:
    rel = str(path.relative_to(ROOT))
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    global _transforms, _parse_errors
    # Reset globals for re-entrant use (important for tests)
    _transforms = collections.defaultdict(list)
    _parse_errors = []

    parser = argparse.ArgumentParser(
        description="Bump version and/or tool-count across all canonical and user-facing files."
    )
    parser.add_argument("--version", metavar="X.Y.Z", help="New version string")
    parser.add_argument("--tool-count", metavar="N", type=int, help="New tool count")
    parser.add_argument(
        "--api-version",
        metavar="X.Y.Z",
        help="API_VERSION override (default: same as --version)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print unified diffs only; write nothing",
    )
    parser.add_argument(
        "--changelog-stub",
        action="store_true",
        help="Insert a stub section header in CHANGELOG.md",
    )
    args = parser.parse_args(argv)

    if not args.version and not args.tool_count:
        parser.error("At least one of --version or --tool-count is required.")

    # No-op detection
    cur_ver = _current_version()
    cur_count = _current_tool_count()
    already_version = args.version and cur_ver == args.version
    already_count = args.tool_count and cur_count == args.tool_count

    if args.version and args.tool_count:
        if already_version and already_count:
            print(f"Nothing to do; already at version {args.version}, tool-count {args.tool_count}")
            return 0
    elif args.version and already_version:
        print(f"Nothing to do; already at version {args.version}")
        return 0
    elif args.tool_count and already_count:
        print(f"Nothing to do; already at tool-count {args.tool_count}")
        return 0

    # --- Register all transforms ---
    if args.version:
        api_ver = args.api_version or args.version
        _register_version_transforms(args.version, api_ver)

    if args.tool_count:
        _register_tool_count_transforms(args.tool_count)

    if args.changelog_stub and args.version:
        _register_changelog_stub(args.version)

    # --- Compute changes (parse errors are accumulated, not raised) ---
    changed, errors = _compute_changes()

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        print("No files written (parse/match failure).", file=sys.stderr)
        return 1

    if not changed:
        print("Nothing to do; all requested values already present.")
        return 0

    # --- Design map header ---
    if args.dry_run:
        print("=" * 72)
        print("DESIGN MAP — files that would be patched:")
        for path, (old, new) in changed.items():
            rel = path.relative_to(ROOT)
            n_lines = sum(
                1
                for line in difflib.unified_diff(old.splitlines(), new.splitlines())
                if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
            )
            print(f"  {rel}  ({n_lines} changed lines)")
        print("=" * 72)
        print()

    # --- Dry run: print diffs ---
    if args.dry_run:
        for path, (old, new) in changed.items():
            diff = _unified_diff(path, old, new)
            if diff:
                print(diff)
        print("\n(dry-run: no files written)")
        return 0

    # --- Real run: write all or nothing ---
    for path, (_, new) in changed.items():
        path.write_text(new, encoding="utf-8")
        print(f"  wrote: {path.relative_to(ROOT)}")

    print(f"\nDone. {len(changed)} file(s) updated.")
    if args.version:
        print(f"  version → {args.version}")
    if args.tool_count:
        print(f"  tool-count → {args.tool_count}")
    if args.api_version and args.version and args.api_version != args.version:
        print(f"  API_VERSION → {args.api_version}")

    print("\nNext steps:")
    print("  1. Run: python scripts/check_versions.py")
    print("  2. Rebuild td_component/tdpilot.tox inside TouchDesigner")
    print("  3. Run: uv run python scripts/build_plugin_zip.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
