"""Regression for installed operators absent from the current graph."""

import ast
import sys
from pathlib import Path
from types import SimpleNamespace


def test_family_inventory_uses_registered_classes_without_creating_nodes(monkeypatch):
    class TOP:
        pass

    class noiseTOP(TOP):
        pass

    class fakeTOP:
        pass

    monkeypatch.setitem(sys.modules, "td", SimpleNamespace(TOP=TOP, noiseTOP=noiseTOP, fakeTOP=fakeTOP))
    source = Path("td_component/mcp_webserver_callbacks.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    handler = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "handle_list_families"
    )
    scope = {"op": lambda path: SimpleNamespace(family="COMP", type="base", isCOMP=True, children=[])}
    exec(compile(ast.Module(body=[handler], type_ignores=[]), "<handler>", "exec"), scope)
    result = scope["handle_list_families"]({})
    assert "noiseTOP" in result["families"]["TOP"]
    assert "fakeTOP" not in result["families"]["TOP"]
    assert "base" in result["families"]["COMP"]
