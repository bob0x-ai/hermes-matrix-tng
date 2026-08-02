from types import SimpleNamespace
import importlib.util
from pathlib import Path
import sys

from agent import secret_scope

_SPEC = importlib.util.spec_from_file_location(
    "hermes_matrix_tng_profile_isolation", Path(__file__).parents[1] / "profile_isolation.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
resolve_matrix_profile_settings = _MODULE.resolve_matrix_profile_settings


def test_settings_snapshot_uses_explicit_profile_home_and_config(monkeypatch, tmp_path):
    secret_scope.set_multiplex_active(False)
    monkeypatch.setenv("MATRIX_RECOVERY_KEY", "root-key-must-not-win")
    config = SimpleNamespace(
        token="profile-token",
        extra={
            "homeserver": "https://matrix.example",
            "user_id": "@writer:example",
            "device_id": "WRITERDEVICE",
            "e2ee_mode": "required",
            "allowed_users": ["@owner:example"],
            "allowed_rooms": ["!room:example"],
            "require_mention": False,
        },
    )
    settings = resolve_matrix_profile_settings(config, tmp_path / "writer")

    assert settings.profile_home == (tmp_path / "writer").resolve()
    assert settings.crypto_db_path == settings.profile_home / "platforms/matrix/store/crypto.db"
    assert settings.access_token == "profile-token"
    assert settings.user_id == "@writer:example"
    assert settings.device_id == "WRITERDEVICE"
    assert settings.allowed_users == ("@owner:example",)
    assert settings.require_mention is False


def test_scoped_secret_is_authoritative_for_each_profile(monkeypatch, tmp_path):
    secret_scope.set_multiplex_active(True)
    monkeypatch.setenv("MATRIX_RECOVERY_KEY", "default-key")
    first = secret_scope.set_secret_scope({"MATRIX_RECOVERY_KEY": "first-key"})
    try:
        first_settings = resolve_matrix_profile_settings(SimpleNamespace(extra={}), tmp_path / "first")
    finally:
        secret_scope.reset_secret_scope(first)
    second = secret_scope.set_secret_scope({"MATRIX_RECOVERY_KEY": "second-key"})
    try:
        second_settings = resolve_matrix_profile_settings(SimpleNamespace(extra={}), tmp_path / "second")
    finally:
        secret_scope.reset_secret_scope(second)
        secret_scope.set_multiplex_active(False)

    assert first_settings.recovery_key == "first-key"
    assert second_settings.recovery_key == "second-key"
    assert first_settings.crypto_db_path != second_settings.crypto_db_path
