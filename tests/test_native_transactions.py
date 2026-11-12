from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[1] / "td_component/mcp_webserver_callbacks.py"


@pytest.fixture
def native(monkeypatch):
    spec = importlib.util.spec_from_file_location("native_test", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    graph = {"/test/a": {"value": 3, "expression": "1 + 2"}}
    stack = ["User edit"]
    saved = []
    calls = []

    class Undo:
        globalState = True
        undoStack = stack

        def startBlock(self, label):
            calls.append("start")
            saved.append(copy.deepcopy(graph))
            stack.insert(0, label)

        def endBlock(self):
            calls.append("end")

        def addCallback(self, callback, info):
            pass

        def undo(self):
            calls.append("undo")
            graph.clear()
            graph.update(saved.pop())
            stack.pop(0)

    def apply(item, root):
        if item.get("fail"):
            raise ValueError("deliberate failure")
        graph["/test/a"] = {"value": item["value"], "expression": ""}
        return {"success": True}

    monkeypatch.setattr(module, "ui", SimpleNamespace(undo=Undo()), raising=False)
    monkeypatch.setattr(module, "op", lambda path: None, raising=False)
    monkeypatch.setattr(module, "_atomic_watch", lambda body: {"/test/a": {}})
    monkeypatch.setattr(module, "_atomic_capture", lambda watch: copy.deepcopy(graph))
    monkeypatch.setattr(module, "_atomic_op", apply)
    body = {
        "session": module._ATOMIC_SESSION,
        "request_id": "test-id",
        "target_root": "/test",
        "operations": [{"value": 8}],
        "undo_label": "Test",
    }
    return module, graph, stack, calls, body


def test_one_callback_owned_block_and_exact_restore(native):
    module, graph, stack, calls, body = native
    before = copy.deepcopy(graph)
    result = module.handle_patch_apply(body)
    assert result["status"] == "clean"
    assert calls == ["start", "end"]
    assert graph != before
    assert module.handle_patch_rollback(body)["ok"]
    assert graph == before
    assert stack == ["User edit"]
    assert calls == ["start", "end", "undo"]


def test_failed_apply_rolls_back_inside_callback(native):
    module, graph, stack, calls, body = native
    body["operations"].append({"fail": True})
    result = module.handle_patch_apply(body)
    assert result["status"] == "broken"
    assert result["failed_op"] == 1
    assert result["rollback"]["ok"]
    assert graph["/test/a"] == {"value": 3, "expression": "1 + 2"}
    assert stack == ["User edit"]


def test_retry_same_id_never_mutates_twice(native):
    module, graph, stack, calls, body = native
    first = module.handle_patch_apply(body)
    assert module.handle_patch_apply(body) == first
    assert calls == ["start", "end"]
    assert "error" in module.handle_patch_apply({**body, "operations": [{"value": 4}]})
    assert calls == ["start", "end"]


@pytest.mark.parametrize("interference", ["history", "state", "session"])
def test_intervening_changes_never_undo_user_work(native, interference):
    module, graph, stack, calls, body = native
    module.handle_patch_apply(body)
    if interference == "history":
        stack.insert(0, "User edit after transaction")
    elif interference == "state":
        graph["/test/a"]["value"] = 99
    else:
        body["session"] = "old-session"
    result = module.handle_patch_rollback(body)
    assert result["ok"] is False
    assert "undo" not in calls


def test_exact_restore_does_not_accept_merely_different_value(native, monkeypatch):
    module, graph, stack, calls, body = native
    module.handle_patch_apply(body)
    monkeypatch.setattr(module.ui.undo, "undo", lambda: graph.update({"/test/a": {"value": 1}}))
    proof = module.handle_patch_rollback(body)
    assert not proof["ok"]
    assert proof["mismatched_paths"] == ["/test/a"]


def test_disabled_undo_rejects_before_mutation(native):
    module, graph, stack, calls, body = native
    module.ui.undo.globalState = False
    assert "error" in module.handle_patch_apply(body)
    assert not calls


def test_expired_receipt_does_not_reapply_or_undo(native):
    module, graph, stack, calls, body = native
    response = module.handle_patch_apply(body)
    del module._ATOMIC_RECEIPTS[body["request_id"]]["watch"]
    assert module.handle_patch_apply(body) == response
    assert not module.handle_patch_rollback(body)["ok"]
    assert calls == ["start", "end"]


def test_unknown_receipt_never_undo(native):
    module, graph, stack, calls, body = native
    assert not module.handle_patch_rollback(body)["ok"]
    assert not calls


def test_dat_callback_restores_both_undo_and_redo(native, monkeypatch):
    module, graph, stack, calls, body = native
    dat = SimpleNamespace(isDAT=True, text="after")
    monkeypatch.setattr(module, "op", lambda path: dat)
    info = {"path": "/test/dat", "before": "before\nλ", "after": "after\nζ"}
    module._atomic_dat_undo(True, info)
    assert dat.text == info["before"]
    module._atomic_dat_undo(False, info)
    assert dat.text == info["after"]


@pytest.mark.parametrize("bad", ["/elsewhere/x", "/test/../x", "/test//x", "relative", "/test/x/"])
def test_scope_and_traversal_rejected(native, monkeypatch, bad):
    module, *_ = native
    monkeypatch.setattr(
        module,
        "me",
        SimpleNamespace(
            parent=lambda: SimpleNamespace(parent=lambda: SimpleNamespace(path="/project1/tdpilot"))
        ),
        raising=False,
    )
    with pytest.raises(ValueError):
        module._atomic_path(bad, "/test")


def test_fanout_disconnect_refuses_extra_peer(native, monkeypatch):
    module, *_ = native
    peers = [
        SimpleNamespace(owner=SimpleNamespace(path="/test/b"), index=0),
        SimpleNamespace(owner=SimpleNamespace(path="/test/c"), index=0),
    ]
    node = SimpleNamespace(outputConnectors=[SimpleNamespace(connections=peers)])
    monkeypatch.setattr(module, "op", lambda path: node)
    with pytest.raises(ValueError, match="Expected route changed"):
        module._atomic_require_route("/test/a", "output", 0, "/test/b")


def test_repeated_rollback_after_redo_or_raw_edit_is_not_falsely_clean(native):
    module, graph, stack, calls, body = native
    module.handle_patch_apply(body)
    assert module.handle_patch_rollback(body)["ok"]
    graph["/test/a"]["value"] = 8
    assert not module.handle_patch_rollback(body)["ok"]
    assert calls.count("undo") == 1


def test_after_capture_failure_still_undoes_owned_block_in_same_callback(native, monkeypatch):
    module, graph, stack, calls, body = native
    original = module._atomic_capture
    count = 0

    def capture(watch):
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("state verification size limit")
        return original(watch)

    monkeypatch.setattr(module, "_atomic_capture", capture)
    response = module.handle_patch_apply(body)
    assert response["status"] == "broken"
    assert response["rollback"]["ok"]
    assert stack == ["User edit"]
    assert graph["/test/a"]["value"] == 3


def test_receipt_storage_does_not_register_self_cook_dependency():
    class CallbackDAT:
        storage = {}
        startup = {}

        def fetch(self, *args, **kwargs):
            raise AssertionError("fetch() creates a callback DAT self-dependency")

        def storeStartupValue(self, key, value):
            self.startup[key] = value

    dat = CallbackDAT()
    namespace = {"me": dat}
    exec(compile(PATH.read_text(), str(PATH), "exec"), namespace)
    session = namespace["_ATOMIC_SESSION"]
    exec(compile(PATH.read_text(), str(PATH), "exec"), namespace)
    assert namespace["_ATOMIC_SESSION"] == session
    assert dat.startup["_tdpilot_atomic_v1"] is None
