"""Regression tests for deterministic device-key mismatch recovery."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).parents[1]


def _load_tng_adapter():
    spec = importlib.util.spec_from_file_location(
        "hermes_matrix_tng_recovery_adapter", ROOT / "adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _recovery_adapter(tng, tmp_path, *, policy="repair"):
    adapter = object.__new__(tng._bundled.MatrixAdapter)
    adapter._device_id_unverified = False
    adapter._crypto_db_path = tmp_path / "store" / "crypto.db"
    adapter._device_key_mismatch = False
    adapter._device_key_recovery_status = "normal"
    adapter._device_key_mismatch_policy = policy
    adapter._device_id = "TNGTEST"
    adapter._user_id = "@tng-test:example.test"
    adapter._password = "test-password"
    return adapter


def _fake_matrix(local_key, server_state):
    class API:
        Method = SimpleNamespace(DELETE="DELETE")

        def __init__(self):
            self.calls = []

        async def request(self, method, path):
            self.calls.append((method, path))
            server_state["key"] = None

    class Client:
        mxid = "@tng-test:example.test"
        device_id = "TNGTEST"

        def __init__(self):
            self.api = API()
            self.login_calls = []

        async def query_keys(self, _request):
            key = server_state["key"]
            device_keys = {} if key is None else {
                self.mxid: {
                    self.device_id: SimpleNamespace(
                        keys={f"ed25519:{self.device_id}": key}
                    )
                }
            }
            return SimpleNamespace(device_keys=device_keys)

        async def login(self, *, identifier, password, device_id, device_name):
            self.login_calls.append((identifier, password, device_id, device_name))
            assert password == "test-password"
            self.device_id = device_id
            self.api.token = "replacement-token"
            return SimpleNamespace(device_id=device_id, access_token=self.api.token)

    class Olm:
        def __init__(self):
            self.account = SimpleNamespace(
                shared=True,
                identity_keys={"ed25519": local_key},
            )
            self.share_calls = 0

        async def share_keys(self):
            assert self.account.shared is False
            self.share_calls += 1
            server_state["key"] = local_key
            self.account.shared = True

    return Client(), Olm()


def test_mismatch_repair_rebinds_server_to_local_identity_and_records_audit(tmp_path):
    tng = _load_tng_adapter()
    local_key = "local-public-key"
    server_state = {"key": "other-public-key"}
    client, olm = _fake_matrix(local_key, server_state)
    adapter = _recovery_adapter(tng, tmp_path)

    assert asyncio.run(adapter._verify_device_keys_on_server(client, olm)) is True

    assert client.api.calls == [("DELETE", "/_matrix/client/v3/devices/TNGTEST")]
    assert olm.share_calls == 1
    assert server_state["key"] == local_key
    assert adapter._device_key_mismatch is False
    assert adapter._device_key_recovery_status == "server_device_repaired"

    evidence_path = tmp_path / "store" / "device-key-mismatches.jsonl"
    records = [json.loads(line) for line in evidence_path.read_text().splitlines()]
    assert [record["action"] for record in records] == [
        "detected",
        "server_repair_started",
        "server_reauthenticated",
        "server_repair_verified",
    ]
    assert all(record["local_key_fingerprint"] for record in records)
    assert all(record["server_key_fingerprint"] for record in records)
    assert local_key not in evidence_path.read_text()
    assert "other-public-key" not in evidence_path.read_text()


def test_quarantine_policy_leaves_server_record_untouched(tmp_path):
    tng = _load_tng_adapter()
    server_state = {"key": "other-public-key"}
    client, olm = _fake_matrix("local-public-key", server_state)
    adapter = _recovery_adapter(tng, tmp_path, policy="quarantine")

    assert asyncio.run(adapter._verify_device_keys_on_server(client, olm)) is False

    assert client.api.calls == []
    assert olm.share_calls == 0
    assert server_state["key"] == "other-public-key"
    assert adapter._device_key_mismatch is True
    assert adapter._device_key_recovery_status == "device_key_mismatch"


def test_mismatch_repair_completes_password_uia_before_deleting_device(tmp_path):
    from mautrix.errors import MatrixUnknownRequestError

    tng = _load_tng_adapter()
    server_state = {"key": "other-public-key"}
    client, olm = _fake_matrix("local-public-key", server_state)
    adapter = _recovery_adapter(tng, tmp_path)
    adapter._password = "test-password"
    calls = []

    async def requires_uia(method, path, content=None, **kwargs):
        calls.append((method, path, content, kwargs))
        if len(calls) == 1:
            raise MatrixUnknownRequestError(
                401, json.dumps({"session": "uia-session", "flows": []})
            )
        assert content["auth"] == {
            "type": "m.login.password",
            "session": "uia-session",
            "identifier": {"type": "m.id.user", "user": client.mxid},
            "password": "test-password",
        }
        assert kwargs == {"sensitive": True}
        server_state["key"] = None

    client.api.request = requires_uia

    assert asyncio.run(adapter._verify_device_keys_on_server(client, olm)) is True

    assert len(calls) == 2
    assert adapter._device_key_recovery_status == "server_device_repaired"
    actions = [
        json.loads(line)["action"]
        for line in (tmp_path / "store" / "device-key-mismatches.jsonl").read_text().splitlines()
    ]
    assert actions == [
        "detected",
        "server_repair_started",
        "server_delete_uia_completed",
        "server_reauthenticated",
        "server_repair_verified",
    ]


def test_mismatch_repair_reports_uia_requirement_without_password(tmp_path):
    from mautrix.errors import MatrixUnknownRequestError

    tng = _load_tng_adapter()
    server_state = {"key": "other-public-key"}
    client, olm = _fake_matrix("local-public-key", server_state)
    adapter = _recovery_adapter(tng, tmp_path)
    adapter._password = ""

    async def requires_uia(*_args, **_kwargs):
        raise MatrixUnknownRequestError(401, json.dumps({"session": "uia-session"}))

    client.api.request = requires_uia

    assert asyncio.run(adapter._verify_device_keys_on_server(client, olm)) is False

    assert adapter._device_key_recovery_status == "server_repair_needs_uia"
    actions = [
        json.loads(line)["action"]
        for line in (tmp_path / "store" / "device-key-mismatches.jsonl").read_text().splitlines()
    ]
    assert actions == ["detected", "server_repair_started", "server_delete_needs_uia"]
