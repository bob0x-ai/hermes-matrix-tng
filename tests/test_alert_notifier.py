"""Tests for the independent, unencrypted Matrix operator notifier."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).parents[1]


def _load_tng_adapter():
    spec = importlib.util.spec_from_file_location(
        "hermes_matrix_tng_alert_adapter", ROOT / "adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, status, body=None):
        self.status = status
        self._body = body or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self):
        return self._body


class _Session:
    def __init__(self, responses, calls, **_kwargs):
        self._responses = iter(responses)
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def get(self, url):
        self._calls.append(("GET", url, None))
        return next(self._responses)

    def put(self, url, *, json):
        self._calls.append(("PUT", url, json))
        return next(self._responses)


def _adapter(tng, tmp_path):
    adapter = object.__new__(tng._bundled.MatrixAdapter)
    adapter._crypto_db_path = tmp_path / "profile" / "store" / "crypto.db"
    adapter._adapter_alerts_enabled = True
    adapter._adapter_alert_homeserver = "https://matrix.example.test"
    adapter._adapter_alert_token = "adapter-alert-token"
    adapter._adapter_alert_room_alias = "#operator-alerts:example.test"
    adapter._adapter_alert_user_id = "@matrix-adapter:example.test"
    return adapter


def test_notifier_resolves_alerts_alias_verifies_plain_room_and_sends_redacted_message(monkeypatch, tmp_path):
    tng = _load_tng_adapter()
    calls = []
    responses = [_Response(200, {"room_id": "!alerts:example.test"}), _Response(404), _Response(200)]
    fake_aiohttp = SimpleNamespace(
        ClientTimeout=lambda **kwargs: kwargs,
        ClientSession=lambda **kwargs: _Session(responses, calls, **kwargs),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)
    adapter = _adapter(tng, tmp_path)
    client = SimpleNamespace(mxid="@affected:example.test", device_id="AFFECTED")

    asyncio.run(
        adapter._emit_device_key_alert(
            client=client,
            status="server_device_repaired",
            local_ed25519="local-public-key",
            server_ed25519="server-public-key",
            detail="repair verified",
        )
    )

    assert [call[0] for call in calls] == ["GET", "GET", "PUT"]
    assert "%23operator-alerts%3Aexample.test" in calls[0][1]
    assert calls[1][1].endswith("/state/m.room.encryption")
    body = calls[2][2]["body"]
    assert "server_device_repaired" in body
    assert "local-public-key" not in body
    assert "server-public-key" not in body
    assert "Local key fingerprint:" in body


def test_notifier_refuses_to_send_into_encrypted_alerts_room(monkeypatch, tmp_path):
    tng = _load_tng_adapter()
    calls = []
    responses = [_Response(200, {"room_id": "!alerts:example.test"}), _Response(200, {"algorithm": "m.megolm.v1.aes-sha2"})]
    fake_aiohttp = SimpleNamespace(
        ClientTimeout=lambda **kwargs: kwargs,
        ClientSession=lambda **kwargs: _Session(responses, calls, **kwargs),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)
    adapter = _adapter(tng, tmp_path)
    client = SimpleNamespace(mxid="@affected:example.test", device_id="AFFECTED")

    asyncio.run(
        adapter._emit_device_key_alert(
            client=client,
            status="server_repair_failed",
            local_ed25519="local-public-key",
            server_ed25519="server-public-key",
        )
    )

    assert [call[0] for call in calls] == ["GET", "GET"]


def test_notifier_does_nothing_when_alerts_are_disabled(monkeypatch, tmp_path):
    tng = _load_tng_adapter()
    calls = []
    fake_aiohttp = SimpleNamespace(
        ClientTimeout=lambda **kwargs: kwargs,
        ClientSession=lambda **kwargs: _Session([], calls, **kwargs),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)
    adapter = _adapter(tng, tmp_path)
    adapter._adapter_alerts_enabled = False
    client = SimpleNamespace(mxid="@affected:example.test", device_id="AFFECTED")

    asyncio.run(
        adapter._emit_device_key_alert(
            client=client,
            status="server_repair_failed",
            local_ed25519="local-public-key",
            server_ed25519="server-public-key",
        )
    )

    assert calls == []


def test_notifier_requires_an_explicit_room_even_when_enabled(monkeypatch, tmp_path):
    tng = _load_tng_adapter()
    calls = []
    fake_aiohttp = SimpleNamespace(
        ClientTimeout=lambda **kwargs: kwargs,
        ClientSession=lambda **kwargs: _Session([], calls, **kwargs),
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)
    adapter = _adapter(tng, tmp_path)
    adapter._adapter_alert_room_alias = ""
    client = SimpleNamespace(mxid="@affected:example.test", device_id="AFFECTED")

    asyncio.run(
        adapter._emit_device_key_alert(
            client=client,
            status="server_repair_failed",
            local_ed25519="local-public-key",
            server_ed25519="server-public-key",
        )
    )

    assert calls == []
