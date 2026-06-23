#!/usr/bin/env python3
"""Audit direct live parameter writes for shared preflight coverage."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PARAM_SET_ENDPOINT = "node/params/set"
DIRECT_PARAM_PREFLIGHT_CONTRACT = "shared_direct_param_preflight_v1"
CENTRAL_GUARD = "_preflight_direct_param_write"
SHARED_CONTRACT_LABEL = "shared-contract:_preflight_direct_param_write"
EXECUTOR_CONTRACT_LABEL = "executor-contract:_preflight_set_param_ops->_preflight_direct_param_write"
WRAPPER_CONTRACT_LABEL = "wrapper-contract:shared_direct_param_preflight_v1"
NONCENTRAL_GUARD_TOKENS = (
    "param_preflight",
    "_preflight_params",
    "_preflight_set_param_ops",
)
LOW_LEVEL_EXECUTOR_CONTRACTS = {("src/td_mcp/patch/applier.py", "_apply_op")}
WRAPPER_CONTRACTS: tuple[dict[str, Any], ...] = (
    {
        "call": "apply_plan",
        "skip_paths": {"src/td_mcp/patch/applier.py"},
        "required_keywords": {"param_preflight", "param_semantics_policy"},
    },
    {
        "call": "apply_transaction",
        "skip_paths": {"src/td_mcp/brain/transaction.py"},
        "required_keywords": {"param_preflight"},
    },
    {
        "call": "_apply_optimizer_plan",
        "skip_paths": set(),
        "required_keywords": {"param_semantics_policy"},
    },
    {
        "call": "MacroEngine",
        "skip_paths": {"src/td_mcp/macros/engine.py"},
        "required_keywords": {"param_preflight"},
    },
    {
        "call": "create_macro",
        "skip_paths": {"src/td_mcp/macros/engine.py"},
        "required_keywords": {"param_semantics_policy"},
    },
)


class _WriteSite:
    def __init__(self, *, path: Path, relpath: str, line: int, function: str) -> None:
        self.path = path
        self.relpath = relpath
        self.line = line
        self.function = function


def audit_direct_param_preflight(root: str | Path = ROOT) -> dict[str, Any]:
    """Return a JSON-serializable report for direct ``node/params/set`` sites."""
    repo_root = Path(root)
    src_root = repo_root / "src" / "td_mcp"
    write_sites: list[_WriteSite] = []
    wrapper_sites: list[dict[str, Any]] = []
    guarded: list[dict[str, Any]] = []
    noncentral_guarded: list[dict[str, Any]] = []
    unguarded: list[dict[str, Any]] = []
    wrapper_guarded: list[dict[str, Any]] = []
    wrapper_unguarded: list[dict[str, Any]] = []

    for path in sorted(src_root.rglob("*.py")) if src_root.exists() else []:
        write_sites.extend(_param_set_write_sites(path, repo_root))
        wrapper_sites.extend(_wrapper_contract_sites(path, repo_root))

    for site in write_sites:
        guarded_by, noncentral_guarded_by = _guard_for_site(site, repo_root)
        payload = {
            "path": site.relpath,
            "line": site.line,
            "function": site.function,
        }
        if guarded_by:
            guarded.append({**payload, "guarded_by": guarded_by})
        elif noncentral_guarded_by:
            noncentral_guarded.append({**payload, "guarded_by": noncentral_guarded_by})
        else:
            unguarded.append(payload)

    for site in wrapper_sites:
        missing = list(site.pop("missing_keywords", []))
        if missing:
            wrapper_unguarded.append({**site, "missing_keywords": sorted(missing)})
        else:
            wrapper_guarded.append({**site, "guarded_by": WRAPPER_CONTRACT_LABEL})

    centralized_contract_ok = not unguarded and not noncentral_guarded and not wrapper_unguarded
    return {
        "schema_version": 1,
        "contract": DIRECT_PARAM_PREFLIGHT_CONTRACT,
        "ok": centralized_contract_ok,
        "centralized_contract_ok": centralized_contract_ok,
        "endpoint": PARAM_SET_ENDPOINT,
        "write_count": len(write_sites),
        "guarded_count": len(guarded),
        "unguarded_count": len(unguarded),
        "noncentral_guarded_count": len(noncentral_guarded),
        "wrapper_call_count": len(wrapper_sites),
        "wrapper_guarded_count": len(wrapper_guarded),
        "wrapper_unguarded_count": len(wrapper_unguarded),
        "guarded_writes": guarded,
        "unguarded_writes": unguarded,
        "noncentral_guarded_writes": noncentral_guarded,
        "wrapper_guarded_calls": wrapper_guarded,
        "wrapper_unguarded_calls": wrapper_unguarded,
    }


def _param_set_write_sites(path: Path, repo_root: Path) -> list[_WriteSite]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    function_by_node: dict[ast.AST, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                function_by_node[child] = node.name

    sites: list[_WriteSite] = []
    relpath = path.relative_to(repo_root).as_posix()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_uses_param_set_endpoint(node):
            sites.append(
                _WriteSite(
                    path=path,
                    relpath=relpath,
                    line=int(getattr(node, "lineno", 0) or 0),
                    function=function_by_node.get(node, "<module>"),
                )
            )
    return sites


def _call_uses_param_set_endpoint(node: ast.Call) -> bool:
    return any(_node_contains_endpoint(arg) for arg in [*node.args, *[kw.value for kw in node.keywords]])


def _wrapper_contract_sites(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    function_by_node: dict[ast.AST, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                function_by_node[child] = node.name

    relpath = path.relative_to(repo_root).as_posix()
    sites: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node.func)
        if not call_name:
            continue
        for contract in WRAPPER_CONTRACTS:
            wanted = str(contract["call"])
            if call_name != wanted and not call_name.endswith(f".{wanted}"):
                continue
            if relpath in contract["skip_paths"]:
                continue
            required = set(contract["required_keywords"])
            provided = {kw.arg for kw in node.keywords if kw.arg}
            missing = sorted(required - provided)
            sites.append(
                {
                    "path": relpath,
                    "line": int(getattr(node, "lineno", 0) or 0),
                    "function": function_by_node.get(node, "<module>"),
                    "call": call_name,
                    "required_keywords": sorted(required),
                    "missing_keywords": missing,
                }
            )
            break
    return sites


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _node_contains_endpoint(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and child.value == PARAM_SET_ENDPOINT:
            return True
    return False


def _guard_for_site(site: _WriteSite, repo_root: Path) -> tuple[str | None, str | None]:
    source = site.path.read_text(encoding="utf-8")
    function_source = _function_source_for_line(source, site.line)
    prefix = "\n".join(function_source.splitlines()[: _line_offset(function_source, source, site.line)])
    if (site.relpath, site.function) in LOW_LEVEL_EXECUTOR_CONTRACTS:
        if _patch_executor_contract_is_shared(source):
            return EXECUTOR_CONTRACT_LABEL, None
    if _macro_engine_contract_is_shared(site, source, prefix):
        return SHARED_CONTRACT_LABEL, None
    if CENTRAL_GUARD in prefix:
        return SHARED_CONTRACT_LABEL, None
    for token in NONCENTRAL_GUARD_TOKENS:
        if token in prefix:
            return None, f"noncentral:{token}"
    return None, None


def _patch_executor_contract_is_shared(source: str) -> bool:
    return all(
        token in source
        for token in (
            "_preflight_set_param_ops",
            "_predicted_annotate_path",
            'op.kind == "annotate"',
            "param_preflight(",
        )
    )


def _macro_engine_contract_is_shared(site: _WriteSite, source: str, prefix: str) -> bool:
    return (
        site.relpath == "src/td_mcp/macros/engine.py"
        and "_preflight_params" in prefix
        and DIRECT_PARAM_PREFLIGHT_CONTRACT in source
        and "self._param_preflight(" in source
    )


def _function_source_for_line(source: str, line: int) -> str:
    tree = ast.parse(source)
    best: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = int(getattr(node, "lineno", 0) or 0)
        end = int(getattr(node, "end_lineno", 0) or 0)
        if start <= line <= end and (best is None or start >= int(best.lineno)):
            best = node
    if best is None:
        return source
    lines = source.splitlines()
    return "\n".join(lines[best.lineno - 1 : best.end_lineno])


def _line_offset(function_source: str, full_source: str, line: int) -> int:
    function_start = 1
    first = function_source.splitlines()[0] if function_source.splitlines() else ""
    for index, candidate in enumerate(full_source.splitlines(), start=1):
        if candidate == first:
            function_start = index
            break
    return max(0, line - function_start)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_direct_param_preflight(args.root)
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
