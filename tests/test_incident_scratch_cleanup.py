"""Failure injection for owned incident-replay scratch cleanup."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def replay():
    path = Path(__file__).resolve().parents[1] / "scripts" / "replay_live_debug_incident.py"
    spec = importlib.util.spec_from_file_location("incident_cleanup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScratchClient:
    def __init__(self, *, fail_build=False, keep_root=False, malformed=False):
        self.root = "/project1/nested/fixture1"
        self.existing = "/project1/nested/fixture"
        self.paths = {self.existing}
        self.fail_build = fail_build
        self.keep_root = keep_root
        self.malformed = malformed
        self.deleted = []

    async def request(self, endpoint, body):
        if endpoint == "node/create":
            if body["parent_path"] == "/project1/nested":
                self.paths.add(self.root)
                return {"node": {"path": self.root}}
            if self.fail_build:
                raise RuntimeError("injected child creation failure")
        if endpoint == "node/delete":
            self.deleted.append(body["path"])
            if not self.keep_root:
                self.paths.remove(body["path"])
            return {"success": True}
        if endpoint == "nodes":
            if self.malformed:
                return {}
            if body["path"] != "/project1/nested":
                return {"nodes": [], "has_more": False}
            # Put the undeleted owned root on page two.
            if body.get("offset", 0) == 0:
                return {"nodes": [{"path": self.existing}], "has_more": self.root in self.paths}
            return {"nodes": [{"path": self.root}], "has_more": False}
        raise AssertionError((endpoint, body))


@pytest.mark.asyncio
async def test_partial_build_is_cleaned_up_without_deleting_existing_target(replay):
    client = ScratchClient(fail_build=True)
    with pytest.raises(RuntimeError, match="injected child creation failure"):
        await replay._run_live_scratch_replay(client, client.existing)
    assert client.paths == {client.existing}
    assert client.deleted == [client.root]


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", [False, True])
async def test_cleanup_requires_complete_readback_from_actual_parent(replay, monkeypatch, malformed):
    client = ScratchClient(keep_root=True, malformed=malformed)

    async def build(*args):
        client.paths.add(client.root)
        return {"root": client.root}

    async def validate(*args):
        return {"ok": True}

    monkeypatch.setattr(replay, "_build_ten_output_library", build)
    monkeypatch.setattr(replay, "_validate_live_scratch_replay", validate)
    with pytest.raises(RuntimeError, match="cleanup"):
        await replay._run_live_scratch_replay(client, client.existing)
    assert client.existing in client.paths
