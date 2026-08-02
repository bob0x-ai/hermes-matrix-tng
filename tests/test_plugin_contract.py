"""Phase 1 compatibility checks; no user plugin is installed by these tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).parents[1]


def _load_tng_adapter():
    spec = importlib.util.spec_from_file_location(
        "hermes_matrix_tng_adapter", ROOT / "adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_declares_the_bundled_override_key():
    manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text())
    assert manifest["name"] == "matrix-platform"
    assert manifest["kind"] == "platform"
    assert manifest["version"] == "0.1.0-tng"


def test_phase_two_adapter_preserves_bundled_registration_surface():
    tng = _load_tng_adapter()
    from plugins.platforms.matrix import adapter as bundled

    assert tng.TNG_PHASE == 2
    assert tng.UPSTREAM_BASE_COMMIT
    assert callable(tng.register)
    assert tng.MatrixAdapter is not bundled.MatrixAdapter
    assert tng.check_matrix_requirements is bundled.check_matrix_requirements


def test_registration_replaces_only_the_adapter_factory():
    tng = _load_tng_adapter()
    from plugins.platforms.matrix import adapter as bundled

    calls = {}

    class Context:
        def register_platform(self, **kwargs):
            calls.update(kwargs)

    tng.register(Context())
    assert calls["name"] == "matrix"
    assert calls["adapter_factory"] is not bundled._build_adapter
    assert calls["adapter_factory"] is not None


def test_adapter_constructor_snapshots_profile_store_path(monkeypatch, tmp_path):
    from types import SimpleNamespace

    tng = _load_tng_adapter()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profile"))
    config = SimpleNamespace(
        token="test-token",
        api_key=None,
        extra={
            "homeserver": "https://example.invalid",
            "user_id": "@tng:example.invalid",
            "device_id": "TNGTEST",
            "e2ee_mode": "off",
        },
    )
    adapter = tng.MatrixAdapter(config)
    assert adapter.profile_settings.crypto_db_path == (
        tmp_path / "profile/platforms/matrix/store/crypto.db"
    )
    assert adapter._encryption is False
    assert adapter._device_id == "TNGTEST"
    diagnostics = adapter.get_diagnostics()
    assert diagnostics["e2ee"]["crypto_store_path"].endswith(
        "profile/platforms/matrix/store/crypto.db"
    )
