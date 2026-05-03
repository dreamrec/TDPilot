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


def check_line(path: Path, pattern: str, expected: str, label: str) -> str | None:
    if not path.exists():
        return f"{label}: missing file {path}"
    text = path.read_text()
    match = re.search(pattern, text)
    if not match:
        return f"{label}: pattern not found in {path.relative_to(ROOT)}"
    actual = match.group(1)
    if actual != expected:
        return f"{label}: {path.relative_to(ROOT)} says {actual}, expected {expected}"
    return None


def check_json_version(path: Path, expected: str, label: str) -> str | None:
    if not path.exists():
        return f"{label}: missing file {path}"
    data = json.loads(path.read_text())
    actual = data.get("version")
    if actual != expected:
        return f"{label}: {path.relative_to(ROOT)} says {actual}, expected {expected}"
    return None


def main() -> int:
    expected = canonical_version()
    errors: list[str] = []

    py_version = pyproject_version()
    if py_version != expected:
        errors.append(f"pyproject.toml says {py_version}, expected {expected}")

    errors += [
        check_json_version(ROOT / "npm" / "package.json", expected, "npm/package.json"),
        check_json_version(ROOT / ".claude-plugin" / "plugin.json", expected, ".claude-plugin/plugin.json"),
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
            ROOT / "docs" / "API_REFERENCE.md",
            r"Auto-generated from TDPilot v([0-9]+\.[0-9]+\.[0-9]+)",
            expected,
            "docs/API_REFERENCE.md header",
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
