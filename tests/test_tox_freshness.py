from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_check_tox_freshness_module():
    path = ROOT / "scripts" / "check_tox_freshness.py"
    spec = importlib.util.spec_from_file_location("check_tox_freshness", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_minimal_tox_tree(module, root: Path, *, include_artifact_metadata: bool = True) -> None:
    for rel in module.SOURCE_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {rel}\nVALUE = {rel!r}\n", encoding="utf-8")
    tox_file = root / module.TOX_REL
    tox_file.parent.mkdir(parents=True, exist_ok=True)
    tox_file.write_bytes(b"tdpilot-tox-binary")
    manifest = {
        "tox_source_hash": module.compute_current_hash(root),
        "built_at": "2026-06-23T00:00:00+00:00",
        "source_files": list(module.SOURCE_FILES),
    }
    if include_artifact_metadata:
        manifest.update(module.compute_tox_artifact_metadata(root))
    (root / module.HASH_REL).write_text(json.dumps(manifest), encoding="utf-8")


def test_check_tox_freshness_accepts_matching_source_and_artifact_metadata(tmp_path):
    module = _load_check_tox_freshness_module()
    _write_minimal_tox_tree(module, tmp_path)

    ok, messages = module.check_freshness(tmp_path)

    assert ok is True
    assert "artifact hash" in "\n".join(messages)


def test_check_tox_freshness_rejects_old_sidecar_without_artifact_metadata(tmp_path):
    module = _load_check_tox_freshness_module()
    _write_minimal_tox_tree(module, tmp_path, include_artifact_metadata=False)

    ok, messages = module.check_freshness(tmp_path)

    assert ok is False
    assert "artifact metadata is missing" in "\n".join(messages)


def test_check_tox_freshness_rejects_binary_drift_with_matching_source_hash(tmp_path):
    module = _load_check_tox_freshness_module()
    _write_minimal_tox_tree(module, tmp_path)
    (tmp_path / module.TOX_REL).write_bytes(b"tdpilot-tox-binary-replaced")

    ok, messages = module.check_freshness(tmp_path)

    assert ok is False
    assert "binary changed" in "\n".join(messages)


def test_tox_freshness_hashes_structural_builder_sources():
    module = _load_check_tox_freshness_module()

    assert "td_component/build_export_mcp_tox.py" in module.SOURCE_FILES
    assert "td_component/build_tdpilot_tox.py" in module.SOURCE_FILES
