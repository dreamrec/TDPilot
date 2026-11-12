import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load_dispatch():
    path = Path(__file__).resolve().parents[1] / "td_component/http_dispatch.py"
    spec = importlib.util.spec_from_file_location("http_dispatch_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dispatch_preserves_request_and_response_for_authenticated_router():
    module = load_dispatch()
    request, response = {"uri": "/api/patch/apply"}, {}
    calls = []

    def route(server, actual_request, actual_response):
        calls.append((server, actual_request, actual_response))
        actual_response["statusCode"] = 401
        return actual_response

    runtime = SimpleNamespace(module=SimpleNamespace(onHTTPRequest=route))
    parent = SimpleNamespace(op=lambda name: runtime if name == "callbacks" else None)
    server = SimpleNamespace(parent=lambda: parent)
    assert module.onHTTPRequest(server, request, response) is response
    assert response["statusCode"] == 401
    assert calls == [(server, request, response)]


def test_missing_runtime_fails_closed():
    module = load_dispatch()
    server = SimpleNamespace(parent=lambda: SimpleNamespace(op=lambda name: None))
    response = module.onHTTPRequest(server, {"uri": "/api/patch/apply"}, {})
    assert response["statusCode"] == 503
    assert b"missing" in response["data"]
