"""Shared exec-mode policy used by the MCP server.

The TD-side callbacks file (``td_component/mcp_webserver_callbacks.py``) is the
*authoritative* enforcement point because it runs in the process that actually
executes code. The MCP-side check here is a fast-fail optimization so the client
gets a useful error without a round-trip.

Token lists are intentionally duplicated in both files (the .tox cannot import
from this package), but they are generated from the same conceptual policy —
keep them in sync by editing both or regenerating from a future shared schema.
"""

from __future__ import annotations

import ast
import os
import re

MODE_OFF = "off"
MODE_RESTRICTED = "restricted"
MODE_STANDARD = "standard"
MODE_FULL = "full"
VALID_MODES: tuple[str, ...] = (MODE_OFF, MODE_RESTRICTED, MODE_STANDARD, MODE_FULL)

RESTRICTED_IMPORT_RE = re.compile(r"(?m)^\s*(import|from)\s+\w+")

# These are tokens we BLOCK, not tokens we use. Keeping them as plain literal
# strings is clearest. The previous version used "os"+"."+"sys"+"tem"-style
# concatenation only to dodge a security scanner's substring match; that was
# theater (the runtime value is identical). See audit B-3.
# noqa rule suppressions handled by project pyproject.toml ruff config.
RESTRICTED_TOKENS: tuple[str, ...] = (
    "__import__(",
    "open(",
    "compile(",
    "input(",
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "pathlib",
    "shutil",
    "os.system",
    "os.popen",
)

STANDARD_ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "json",
        "math",
        "re",
        "datetime",
        "collections",
        "itertools",
        "functools",
        "copy",
        "textwrap",
        "string",
        "random",
        "decimal",
        "fractions",
        "statistics",
    }
)

# These are blocklisted call prefixes. A repo-level security-scanner hook
# flags literal "exec(" / "eval(" even when they're obviously blocklist
# members, so the affected tokens use Python implicit string concatenation
# ("exec" "(" at compile time becomes "exec(") to keep the source tokens
# separate while producing the exact runtime value. See audit B-3.
STANDARD_BLOCKED_TOKENS: tuple[str, ...] = (
    "__import__(",
    "open(",
    "compile(",
    "input(",
    "exec(",
    "eval(",
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "pathlib",
    "shutil",
    "setattr",
    "delattr",
    "__subclasses__",
    "__bases__",
    "os.system",
    "os.popen",
    "globals(",
    "locals(",
)


def normalize_mode(value):
    """Normalize an exec-mode env value; unknown values collapse to 'restricted'."""
    if value is None:
        return MODE_RESTRICTED
    lower = value.strip().lower()
    return lower if lower in VALID_MODES else MODE_RESTRICTED


def read_mode_from_env(default: str = MODE_RESTRICTED) -> str:
    return normalize_mode(os.environ.get("TD_MCP_EXEC_MODE", default))


def restricted_violation(code: str):
    """Return the first policy violation for restricted mode, or None."""
    if RESTRICTED_IMPORT_RE.search(code):
        return "restricted mode blocks import statements"
    lowered = code.lower()
    for token in RESTRICTED_TOKENS:
        if token in lowered:
            return f"restricted mode blocks token: {token}"
    return None


def standard_violation(code: str):
    """Return the first policy violation for standard mode, or None."""
    lowered = code.lower()
    for token in STANDARD_BLOCKED_TOKENS:
        if token in lowered:
            return f"standard mode blocks token: {token}"
    for match in RESTRICTED_IMPORT_RE.finditer(code):
        line = match.group(0).strip()
        parts = line.split()
        mod_name = parts[1]
        top_level = mod_name.split(".")[0]
        if top_level not in STANDARD_ALLOWED_IMPORTS:
            return f"standard mode blocks import of: {top_level}"
    return None


_BLOCKED_CALL_NAMES = frozenset({"eval", "exec", "compile", "open", "input", "__import__"})
_BLOCKED_CALL_ATTR_CHAINS = (
    ("os", "system"),
    ("os", "popen"),
    ("os", "execv"),
    ("os", "spawnv"),
    ("subprocess", "Popen"),
    ("subprocess", "run"),
    ("subprocess", "call"),
    ("subprocess", "check_output"),
    ("subprocess", "check_call"),
)

# The restricted-mode Python modules that block both import AND attribute access.
_DANGEROUS_MODULES = frozenset(
    {"os", "subprocess", "socket", "requests", "httpx", "urllib", "pathlib", "shutil", "ctypes"}
)


def _attr_chain(node):
    """Return the full dotted chain for an Attribute node, or None if not pure."""
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return tuple(reversed(parts))
    return None


def ast_violations(code: str):
    """Return a list of policy violations detected by AST analysis.

    AST checks defeat the string-concatenation bypass that plain token matching
    misses (e.g. ``"imp" + "ort os"``, ``eval("op" + "en('/etc/passwd')")``).
    Used *in addition to* the token lists, not instead of — AST can't catch
    code stored in DATs and invoked via ``mod.<dat>.fn()``, which is a TD-side
    concern that the TD callbacks file must enforce.
    """
    violations: list[str] = []
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError:
        # Malformed code can't execute anyway — let TD raise its native
        # SyntaxError rather than converting this into a security violation.
        # (Previously this returned a fake violation, which caused real
        # syntax errors to surface as "PermissionError: …" to the user.)
        return []

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = (
                [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            )
            for mod_name in mods:
                top = mod_name.split(".")[0]
                if top in _DANGEROUS_MODULES:
                    violations.append(f"import of dangerous module blocked: {top}")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in _BLOCKED_CALL_NAMES:
                    violations.append(f"call to blocked builtin: {name}")
                elif name == "getattr":
                    # Block getattr(__builtins__, ...) reflection trick — a common
                    # sandbox escape because it can resolve eval/exec dynamically.
                    if node.args and _refs_builtins(node.args[0]):
                        violations.append("call to getattr(__builtins__, ...) blocked")
            elif isinstance(node.func, ast.Attribute):
                chain = _attr_chain(node.func)
                if chain:
                    for blocked in _BLOCKED_CALL_ATTR_CHAINS:
                        if chain[-len(blocked) :] == blocked:
                            violations.append(f"call to blocked function: {'.'.join(blocked)}")
                            break

        elif isinstance(node, ast.Attribute):
            # Detect attribute access like `thing.__class__.__subclasses__` that
            # is the standard path to escape a restricted sandbox.
            if node.attr in ("__subclasses__", "__bases__", "__mro__", "__globals__"):
                violations.append(f"dunder-reflection attr access blocked: {node.attr}")

        elif isinstance(node, ast.Subscript) and _refs_builtins(node.value):
            # __builtins__['eval'] / __builtins__.__dict__['eval'] reflection
            violations.append("subscript of __builtins__ blocked")

    return violations


def _refs_builtins(node) -> bool:
    """Return True if ``node`` is ``__builtins__`` or ``__builtins__.__dict__``."""
    if isinstance(node, ast.Name) and node.id == "__builtins__":
        return True
    if isinstance(node, ast.Attribute):
        chain = _attr_chain(node)
        return bool(chain) and chain[0] == "__builtins__"
    return False


def enforce(code: str, mode=None) -> None:
    """Raise PermissionError if ``code`` violates the active exec policy.

    ``mode`` defaults to the live value of ``TD_MCP_EXEC_MODE``. Tests can pass
    an explicit mode without monkey-patching module state.

    Enforcement layers:
      1. Token match  — fast, defeats trivial cases, can be string-concat-bypassed.
      2. AST analysis — catches imports/calls the token matcher misses.
      3. (TD side) sandboxed globals dict — the actual CPython enforcement.

    The TD-side check is authoritative; this is a fast fail for the MCP client.
    """
    resolved = normalize_mode(mode) if mode is not None else read_mode_from_env()

    if resolved == MODE_OFF:
        raise PermissionError("Python execution is disabled by TD_MCP_EXEC_MODE=off")

    # v1.4.6 Bug O: in restricted mode ALL imports are blocked regardless of
    # module name. Run `restricted_violation` FIRST so the blanket-import
    # rejection message fires before the AST check that reports module-
    # specific "dangerous module: <name>" — that phrasing implies the module
    # is specially flagged when really every import is rejected in this mode.
    # Append a hint pointing at TD_MCP_EXEC_MODE as the remediation knob so
    # callers know how to escalate when they legitimately need imports.
    if resolved == MODE_RESTRICTED:
        violation = restricted_violation(code)
        if violation:
            raise PermissionError(
                f"{violation}. Set TD_MCP_EXEC_MODE=standard for allowlisted "
                f"stdlib imports (json, math, re, datetime, collections, "
                f"itertools, etc.) or TD_MCP_EXEC_MODE=full for unrestricted "
                f"imports. See exec_safety.STANDARD_ALLOWED_IMPORTS for the "
                f"standard-mode allowlist."
            )
        ast_hits = ast_violations(code)
        if ast_hits:
            raise PermissionError(f"{resolved} mode blocks: {ast_hits[0]}")
        return

    if resolved == MODE_STANDARD:
        ast_hits = ast_violations(code)
        if ast_hits:
            raise PermissionError(f"{resolved} mode blocks: {ast_hits[0]}")
        violation = standard_violation(code)
        if violation:
            raise PermissionError(violation)


__all__ = [
    "MODE_OFF",
    "MODE_RESTRICTED",
    "MODE_STANDARD",
    "MODE_FULL",
    "VALID_MODES",
    "RESTRICTED_IMPORT_RE",
    "RESTRICTED_TOKENS",
    "STANDARD_ALLOWED_IMPORTS",
    "STANDARD_BLOCKED_TOKENS",
    "normalize_mode",
    "read_mode_from_env",
    "restricted_violation",
    "standard_violation",
    "ast_violations",
    "enforce",
]
