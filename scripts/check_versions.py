#!/usr/bin/env python3
"""Fail if versioned files disagree with src/td_mcp/__init__.__version__.

Run locally or in CI after bumping pyproject.toml. Prevents the v1.3.2/v1.3.4
drift problem that accumulated across plugin_README, docs, skills, and npm.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical_version() -> str:
    text = (ROOT / "src" / "td_mcp" / "__init__.py").read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("Could not find __version__ in src/td_mcp/__init__.py")
    return match.group(1)


def pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("Could not find version in pyproject.toml")
    return match.group(1)


def canonical_tool_count() -> str:
    text = (ROOT / "src" / "td_mcp" / "release_gates.py").read_text()
    match = re.search(r"EXPECTED_MIN_TOOL_COUNT\s*:\s*int\s*=\s*(\d+)", text)
    if not match:
        raise SystemExit("Could not find EXPECTED_MIN_TOOL_COUNT in src/td_mcp/release_gates.py")
    return match.group(1)


def check_line(path: Path, pattern: str, expected: str, label: str, *, flags: int = 0) -> str | None:
    if not path.exists():
        return f"{label}: missing file {path}"
    text = path.read_text()
    match = re.search(pattern, text, flags)
    if not match:
        return f"{label}: pattern not found in {path.relative_to(ROOT).as_posix()}"
    actual = match.group(1)
    if actual != expected:
        return f"{label}: {path.relative_to(ROOT).as_posix()} says {actual}, expected {expected}"
    return None


def check_json_version(path: Path, expected: str, label: str) -> str | None:
    if not path.exists():
        return f"{label}: missing file {path}"
    data = json.loads(path.read_text())
    actual = data.get("version")
    if actual != expected:
        return f"{label}: {path.relative_to(ROOT).as_posix()} says {actual}, expected {expected}"
    return None


def _json_path_value(data: object, key_path: str) -> object:
    current = data
    for key in key_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def check_json_value(path: Path, key_path: str, expected: object, label: str) -> str | None:
    if not path.exists():
        return f"{label}: missing file {path}"
    data = json.loads(path.read_text())
    actual = _json_path_value(data, key_path)
    if actual != expected:
        return f"{label}: {path.relative_to(ROOT).as_posix()} says {actual}, expected {expected}"
    return None


def main() -> int:
    expected = canonical_version()
    expected_tool_count = canonical_tool_count()
    errors: list[str] = []

    py_version = pyproject_version()
    if py_version != expected:
        errors.append(f"pyproject.toml says {py_version}, expected {expected}")

    errors += [
        check_json_version(ROOT / "npm" / "package.json", expected, "npm/package.json"),
        check_json_version(ROOT / "mcp" / "manifest.json", expected, "mcp/manifest.json"),
        check_json_value(
            ROOT / "mcp" / "manifest.json",
            "surface.tool_count",
            int(expected_tool_count),
            "mcp/manifest.json tool_count",
        ),
        check_json_version(ROOT / ".claude-plugin" / "plugin.json", expected, ".claude-plugin/plugin.json"),
        check_json_version(
            ROOT / "plugins" / "tdpilot" / ".codex-plugin" / "plugin.json",
            expected,
            "plugins/tdpilot/.codex-plugin/plugin.json",
        ),
        check_line(
            ROOT / ".claude-plugin" / "marketplace.json",
            r'"version"\s*:\s*"([^"]+)"',
            expected,
            ".claude-plugin/marketplace.json tdpilot plugin",
        ),
        # v1.6.5: API_VERSION is now lockstep with __version__.
        # Pre-v1.6.5 history: this constant was deliberately decoupled from the
        # package version, on the theory that the TD-side HTTP protocol version
        # only needs bumping when route shapes change. In practice the
        # decoupling caused two user-visible drift bugs (v1.6.3 panel showing
        # "TDPilot 1.5.3" because nobody had bumped API_VERSION across the v1.6
        # line; v1.6.4 silently shipped with API_VERSION still at "1.6.3"
        # because no CI gate caught a missing Edit). The panel renderer reads
        # API_VERSION directly, so users expect it to match the package version.
        # We choose the simpler invariant: API_VERSION == __version__ on every
        # release. If you legitimately need a TD-side protocol version distinct
        # from the package version, introduce a separate TD_PROTOCOL_VERSION
        # constant rather than re-decoupling this one.
        check_line(
            ROOT / "README.md",
            r"# TDPilot Runtime v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "README.md title",
        ),
        check_line(
            ROOT / "README.md",
            # v2.1.0 README restructure: inline "What's New In X" sections
            # moved to CHANGELOG.md; the "## Latest Release" pointer carries
            # the current version instead.
            r"\*\*v([0-9]+\.[0-9]+\.[0-9]+)\*\* —",
            expected,
            "README.md Latest Release",
        ),
        check_line(
            ROOT / "README.md",
            r"MCP%20tools-(\d+)-blueviolet",
            expected_tool_count,
            "README.md MCP tools badge",
        ),
        check_line(
            ROOT / "README.md",
            r"## Tool Map \((\d+) Tools\)",
            expected_tool_count,
            "README.md Tool Map",
        ),
        # The former "**N MCP tools**" install line and "- N-tool runtime
        # surface" bullet were deliberately made count-free in the v2.1.0
        # README restructure (counts live in the badge and Tool Map heading,
        # both checked above) — do not re-add prose count checks.
        check_line(
            ROOT / "td_component" / "mcp_webserver_callbacks.py",
            r'API_VERSION\s*=\s*"([^"]+)"',
            expected,
            "td_component/mcp_webserver_callbacks.py API_VERSION",
        ),
        check_line(
            ROOT / "plugin_README.md",
            r"TDPilot v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "plugin_README.md header",
        ),
        check_line(
            ROOT / "plugin_README.md",
            r"provides (\d+) MCP tools",
            expected_tool_count,
            "plugin_README.md tool count",
        ),
        check_line(
            ROOT / "plugin_README.md",
            r"(\d+)-tool reference",
            expected_tool_count,
            "plugin_README.md core skill tool count",
        ),
        check_line(
            ROOT / "docs" / "API_REFERENCE.md",
            # Header dropped the false "Auto-generated" claim in v2.1.0.
            r"> TDPilot v([0-9]+\.[0-9]+\.[0-9]+) \| \d+ tools",
            expected,
            "docs/API_REFERENCE.md header",
        ),
        check_line(
            ROOT / "docs" / "API_REFERENCE.md",
            r"> TDPilot v[0-9]+\.[0-9]+\.[0-9]+ \| (\d+) tools",
            expected_tool_count,
            "docs/API_REFERENCE.md header tool count",
        ),
        check_line(
            ROOT / "docs" / "MANUAL.md",
            r"# TDPilot v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "docs/MANUAL.md title",
        ),
        check_line(
            ROOT / "npm" / "README.md",
            r"# TDPilot v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "npm/README.md title",
        ),
        check_line(
            ROOT / "npm" / "README.md",
            r"MCP%20tools-(\d+)-blueviolet",
            expected_tool_count,
            "npm/README.md MCP tools badge",
        ),
        check_line(
            ROOT / "npm" / "README.md",
            r"— (\d+) tools for full live control",
            expected_tool_count,
            "npm/README.md prose tool count",
        ),
        check_line(
            ROOT / "docs" / "TDPILOT_EFFECTIVENESS_ROADMAP.md",
            r"- (\d+) local MCP tools",
            expected_tool_count,
            "docs/TDPILOT_EFFECTIVENESS_ROADMAP.md tool count",
        ),
        check_line(
            ROOT / "skills" / "tdpilot-core" / "SKILL.md",
            r"TDPilot Core v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "skills/tdpilot-core/SKILL.md",
        ),
        check_line(
            ROOT / "skills" / "tdpilot-production" / "SKILL.md",
            r"TDPilot Production v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "skills/tdpilot-production/SKILL.md",
        ),
        check_line(
            ROOT / "skills" / "tdpilot-core" / "SKILL.md",
            r"description:\s*>\s*.*?TDPilot v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "skills/tdpilot-core/SKILL.md frontmatter",
            flags=re.DOTALL,
        ),
        check_line(
            ROOT / "skills" / "tdpilot-production" / "SKILL.md",
            r"description:\s*>\s*.*?TDPilot v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "skills/tdpilot-production/SKILL.md frontmatter",
            flags=re.DOTALL,
        ),
        check_line(
            ROOT / "plugins" / "tdpilot" / "skills" / "tdpilot-core" / "SKILL.md",
            r"description:\s*>\s*.*?TDPilot v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "plugins/tdpilot/skills/tdpilot-core/SKILL.md frontmatter",
            flags=re.DOTALL,
        ),
        check_line(
            ROOT / "plugins" / "tdpilot" / "skills" / "tdpilot-production" / "SKILL.md",
            r"description:\s*>\s*.*?TDPilot v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "plugins/tdpilot/skills/tdpilot-production/SKILL.md frontmatter",
            flags=re.DOTALL,
        ),
    ]

    errors = [e for e in errors if e]

    if errors:
        print(f"Canonical version (src/td_mcp/__init__.py): {expected}")
        print("Version drift detected:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"All versioned files are in sync at v{expected}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
