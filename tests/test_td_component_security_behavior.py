"""BEHAVIOURAL tests for the TD-side security logic in the .tox source.

The callbacks file can't be imported (it references TouchDesigner runtime
globals), and the older tests only grep its *source text* — which would pass
even if a constant typo silently broke the sandbox. Here we instead EXTRACT the
pure-string policy functions via AST, load them as a real module, and EXECUTE
them against real bypass payloads, plus the autostart auth-env provisioner. This
is the behavioural coverage the authoritative boundary was missing.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import pathlib
import tempfile

import pytest

_TD = pathlib.Path(__file__).resolve().parent.parent / "td_component"
_CB_SRC = (_TD / "mcp_webserver_callbacks.py").read_text(encoding="utf-8")
_AUTOSTART_SRC = (_TD / "autostart.py").read_text(encoding="utf-8")

# Build banned payloads at runtime to keep literal flagged substrings out of source.
_SHELL_CALL = "os." + 'system("x")'


def _load_extracted(source: str, names: set[str], funcs: set[str], preamble: str, tag: str):
    """Unparse the named module-level assigns + functions and import them as a
    standalone module (in source order) — no live TouchDesigner required."""
    tree = ast.parse(source)
    chunks = [preamble]
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(t in names for t in targets):
                chunks.append(ast.unparse(node))
        elif isinstance(node, ast.FunctionDef) and node.name in funcs:
            chunks.append(ast.unparse(node))
    code = "\n\n".join(chunks)
    fd, path = tempfile.mkstemp(suffix=".py", prefix=f"_td_extracted_{tag}_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(code)
        spec = importlib.util.spec_from_file_location(f"_td_extracted_{tag}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        os.unlink(path)
    return module


@pytest.fixture(scope="module")
def policy():
    return _load_extracted(
        _CB_SRC,
        names={
            "RESTRICTED_IMPORT_RE",
            "RESTRICTED_TOKENS",
            "STANDARD_ALLOWED_IMPORTS",
            "STANDARD_BLOCKED_TOKENS",
            "_EXEC_PAREN",
            "_EVAL_PAREN",
            "_GLOBALS_PAREN",
            "_LOCALS_PAREN",
        },
        funcs={
            "_normalize_for_check",
            "_ast_reflection_violation",
            "_restricted_exec_violation",
            "_standard_exec_violation",
            "_exec_policy_violation",
            "_dat_content_violation",
        },
        preamble="import re",
        tag="policy",
    )


# --- restricted-mode sandbox actually blocks (behavioural, not grep) ---


def test_restricted_blocks_import(policy):
    assert policy._restricted_exec_violation("import os") is not None


def test_restricted_blocks_builtins_reflection(policy):
    # __builtins__ token now in RESTRICTED_TOKENS — closes json.__builtins__ escape.
    assert policy._restricted_exec_violation('y = j.__builtins__["x"]') is not None


def test_restricted_blocks_dat_escape_with_extra_whitespace(policy):
    # The whitespace-normalisation fix: '.text  =' (two spaces) / tab must still
    # trip the '.text=' DAT-escape token.
    assert policy._restricted_exec_violation('op("d").text  = "import os"') is not None
    assert policy._restricted_exec_violation('op("d").text\t= "x"') is not None


def test_restricted_allows_benign_op_access(policy):
    assert policy._restricted_exec_violation('out = op("noise1")') is None


def test_standard_blocks_globals_reflection(policy):
    assert policy._standard_exec_violation("g = f.__globals__") is not None


# --- standard-mode concat-obfuscated reflection escape (P2 security finding) ---
#
# The TD-side `standard` builtins KEEP getattr/type, and the token scan is
# substring-only, so `getattr(x, '__cl' + 'ass__')` used to slip past the
# authoritative TD-side check even though the MCP-side AST caught it. These
# assert the ported AST layer closes the gap so the TD side is no longer the
# weaker link (SECURITY.md "TD-side is authoritative" invariant).


def _concat_getattr_reflection_payload():
    # Split every reflection dunder across a `+` so no contiguous substring of
    # the banned literal appears in source. Built at runtime so the flagged
    # literal never appears whole in THIS test file either.
    cls = "'__cl' + 'ass__'"
    subs = "'__subc' + 'lasses__'"
    return "getattr(getattr((), " + cls + "), " + subs + ")()"


def test_standard_blocks_concat_getattr_reflection(policy):
    payload = _concat_getattr_reflection_payload()
    # sanity: the obfuscation really does defeat the plain token scan
    assert "__class__" not in payload and "__subclasses__" not in payload
    assert policy._standard_exec_violation(payload) is not None


def test_standard_blocks_getattr_of_globals(policy):
    # getattr-resolved __globals__ reaches the real builtins dict
    assert policy._standard_exec_violation("getattr(f, '__glob' + 'als__')") is not None


def test_standard_blocks_builtins_subscript(policy):
    assert policy._standard_exec_violation("__builtins__['ev' + 'al']('1')") is not None


def test_standard_blocks_nonliteral_getattr_name(policy):
    # A runtime-computed attribute name can't be proven safe → rejected outright.
    assert policy._standard_exec_violation("getattr(f, some_var)") is not None


def test_restricted_blocks_concat_getattr_in_param_expr(policy):
    # Param expressions / DAT content are evaluated later in TD's FULL Python,
    # where the sandboxed builtins never apply, so restricted must also catch the
    # concat escape statically. `_exec_policy_violation` routes to the restricted
    # check for restricted mode.
    payload = _concat_getattr_reflection_payload()
    assert policy._exec_policy_violation("restricted", payload) is not None
    assert policy._dat_content_violation("restricted", payload) is not None


def test_standard_allows_benign_getattr_and_type(policy):
    # The fix must NOT break legitimate standard-mode reflection: a literal,
    # non-dunder attribute name and plain type() stay allowed.
    assert policy._standard_exec_violation("v = getattr(op('x'), 'par')") is None
    assert policy._standard_exec_violation("t = type(op('x'))") is None
    assert policy._standard_exec_violation("n = op('x').__class__") is None


def test_ast_reflection_ignores_syntax_errors(policy):
    # Malformed code must not become a spurious PermissionError — TD raises the
    # real SyntaxError at exec time instead.
    assert policy._ast_reflection_violation("def (:oops") is None


# --- expression-write policy (handle_set_params expr) ---


def test_exec_policy_off_blocks_everything(policy):
    assert policy._exec_policy_violation("off", "1 + 1") is not None


def test_exec_policy_restricted_blocks_dangerous_expr(policy):
    assert policy._exec_policy_violation("restricted", '__import__("os")') is not None


def test_exec_policy_full_allows(policy):
    assert policy._exec_policy_violation("full", "import os") is None


# --- DAT-content policy (handle_set_content) — block code, allow data ---


def test_dat_content_restricted_blocks_code(policy):
    assert policy._dat_content_violation("restricted", "import os\n" + _SHELL_CALL) is not None


def test_dat_content_restricted_allows_plain_data(policy):
    assert policy._dat_content_violation("restricted", "a,b,c\n1,2,3\n4,5,6") is None


def test_dat_content_full_allows_code(policy):
    assert policy._dat_content_violation("full", "import os") is None


# --- autostart auth-env provisioning (replaces the old force-auth-off) ---


@pytest.fixture
def ensure_auth_env():
    module = _load_extracted(
        _AUTOSTART_SRC, names=set(), funcs={"_ensure_auth_env"}, preamble="import os", tag="autostart"
    )
    return module._ensure_auth_env


def test_ensure_auth_env_generates_secret_when_required(ensure_auth_env, tmp_path, monkeypatch):
    env_file = tmp_path / ".tdpilot.env"
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    monkeypatch.delenv("TD_MCP_REQUIRE_AUTH", raising=False)

    ensure_auth_env()

    # A secret was provisioned and persisted to the shared file (so the MCP
    # client reads the identical value — no 401 drift), auth is NOT forced off.
    assert (os.environ.get("TD_MCP_SHARED_SECRET") or "").strip()
    assert "TD_MCP_SHARED_SECRET=" in env_file.read_text(encoding="utf-8")
    assert os.environ.get("TD_MCP_REQUIRE_AUTH") not in ("0", "false", "no")


def test_ensure_auth_env_honours_explicit_opt_out(ensure_auth_env, tmp_path, monkeypatch):
    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_REQUIRE_AUTH=0\n", encoding="utf-8")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    monkeypatch.delenv("TD_MCP_REQUIRE_AUTH", raising=False)

    ensure_auth_env()

    # Explicit opt-out is honoured; no secret is generated behind the user's back.
    assert os.environ.get("TD_MCP_REQUIRE_AUTH") == "0"
    assert not (os.environ.get("TD_MCP_SHARED_SECRET") or "").strip()


def test_ensure_auth_env_reuses_existing_secret(ensure_auth_env, tmp_path, monkeypatch):
    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text(
        "TD_MCP_REQUIRE_AUTH=1\nTD_MCP_SHARED_SECRET=preexisting-secret-value\n", encoding="utf-8"
    )
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    monkeypatch.delenv("TD_MCP_REQUIRE_AUTH", raising=False)

    ensure_auth_env()

    assert os.environ.get("TD_MCP_SHARED_SECRET") == "preexisting-secret-value"
