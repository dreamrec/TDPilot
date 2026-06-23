from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_audit_module():
    path = ROOT / "scripts" / "audit_direct_param_preflight.py"
    spec = importlib.util.spec_from_file_location("audit_direct_param_preflight", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_direct_param_preflight_audit_reports_raw_unguarded_write(tmp_path):
    module = _load_audit_module()
    source = tmp_path / "src" / "td_mcp" / "registry" / "unsafe_tool.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "\n".join(
            [
                "async def unsafe(client):",
                "    await client.request('node/params/set', {'path': '/p/x', 'params': {'reset': 1}})",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = module.audit_direct_param_preflight(tmp_path)

    assert report["ok"] is False
    assert report["unguarded_count"] == 1
    assert report["unguarded_writes"][0]["path"].endswith("unsafe_tool.py")


def test_direct_param_preflight_audit_rejects_noncentral_local_guard(tmp_path):
    module = _load_audit_module()
    source = tmp_path / "src" / "td_mcp" / "registry" / "unsafe_tool.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "\n".join(
            [
                "async def unsafe(client):",
                "    _preflight_params(path='/p/x')",
                "    await client.request('node/params/set', {'path': '/p/x', 'params': {'reset': 1}})",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = module.audit_direct_param_preflight(tmp_path)

    assert report["ok"] is False
    assert report["centralized_contract_ok"] is False
    assert report["unguarded_writes"] == []
    assert report["noncentral_guarded_count"] == 1
    assert report["noncentral_guarded_writes"][0]["guarded_by"] == "noncentral:_preflight_params"


def test_direct_param_preflight_audit_reports_wrapper_without_shared_preflight(tmp_path):
    module = _load_audit_module()
    source = tmp_path / "src" / "td_mcp" / "registry" / "unsafe_wrapper.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "\n".join(
            [
                "async def unsafe(client, plan, sentinel):",
                "    await apply_transaction(client, plan, sentinel=sentinel)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = module.audit_direct_param_preflight(tmp_path)

    assert report["ok"] is False
    assert report["wrapper_unguarded_count"] == 1
    assert report["wrapper_unguarded_calls"][0]["call"] == "apply_transaction"
    assert report["wrapper_unguarded_calls"][0]["missing_keywords"] == ["param_preflight"]


def test_direct_param_preflight_audit_accepts_current_repo():
    module = _load_audit_module()

    report = module.audit_direct_param_preflight(ROOT)

    assert report["ok"] is True
    assert report["contract"] == "shared_direct_param_preflight_v1"
    assert report["centralized_contract_ok"] is True
    assert report["unguarded_writes"] == []
    assert report["noncentral_guarded_writes"] == []
    assert report["wrapper_unguarded_calls"] == []
    assert report["wrapper_call_count"] >= 1
    assert {item["guarded_by"] for item in report["guarded_writes"]} <= {
        "shared-contract:_preflight_direct_param_write",
        "executor-contract:_preflight_set_param_ops->_preflight_direct_param_write",
    }
