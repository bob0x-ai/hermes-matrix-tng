"""Regression tests for policy and diagnostic profile isolation."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import sys

from agent import secret_scope
from hermes_constants import reset_hermes_home_override, set_hermes_home_override


ROOT = Path(__file__).parents[1]


def _load_tng_adapter():
    spec = importlib.util.spec_from_file_location(
        "hermes_matrix_tng_policy_adapter", ROOT / "adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_adapter(tng, profile_home, scoped_secrets):
    secret_token = secret_scope.set_secret_scope(scoped_secrets)
    home_token = set_hermes_home_override(profile_home)
    try:
        return tng.MatrixAdapter(SimpleNamespace(token="", extra={}))
    finally:
        reset_hermes_home_override(home_token)
        secret_scope.reset_secret_scope(secret_token)


def test_conflicting_profile_policies_are_applied_after_inherited_initialization(
    monkeypatch, tmp_path
):
    """The immutable snapshot wins over the inherited raw-environment reads."""
    tng = _load_tng_adapter()
    monkeypatch.setenv("MATRIX_IGNORE_USER_PATTERNS", "^@root:example$")
    monkeypatch.setenv("MATRIX_THREAD_REQUIRE_MENTION", "false")

    def inherited_init(adapter, _config):
        adapter._ignored_user_patterns = [
            tng._bundled.re.compile(pattern)
            for pattern in os.getenv("MATRIX_IGNORE_USER_PATTERNS", "").split(",")
            if pattern
        ]
        adapter._thread_require_mention = (
            os.getenv("MATRIX_THREAD_REQUIRE_MENTION", "false").lower() == "true"
        )

    monkeypatch.setattr(tng._bundled.MatrixAdapter, "__init__", inherited_init)
    secret_scope.set_multiplex_active(True)
    try:
        first = _build_adapter(
            tng,
            tmp_path / "first",
            {
                "MATRIX_IGNORE_USER_PATTERNS": "^@bridge:example$,^@system:example$",
                "MATRIX_THREAD_REQUIRE_MENTION": "true",
            },
        )
        second = _build_adapter(
            tng,
            tmp_path / "second",
            {
                "MATRIX_IGNORE_USER_PATTERNS": "^@bot:example$",
                "MATRIX_THREAD_REQUIRE_MENTION": "false",
            },
        )
    finally:
        secret_scope.set_multiplex_active(False)

    assert [pattern.pattern for pattern in first._ignored_user_patterns] == [
        "^@bridge:example$",
        "^@system:example$",
    ]
    assert first._thread_require_mention is True
    assert [pattern.pattern for pattern in second._ignored_user_patterns] == ["^@bot:example$"]
    assert second._thread_require_mention is False


def test_diagnostics_read_recovery_status_from_own_profile_snapshot(monkeypatch, tmp_path):
    """Inherited diagnostics must not inspect the root profile's raw key."""
    tng = _load_tng_adapter()
    monkeypatch.setenv("MATRIX_RECOVERY_KEY", "root-recovery-key")

    def inherited_init(adapter, _config):
        adapter._ignored_user_patterns = []

    def inherited_diagnostics(_adapter):
        return {
            "e2ee": {
                "recovery_key_configured": bool(
                    os.getenv("MATRIX_RECOVERY_KEY", "").strip()
                )
            }
        }

    monkeypatch.setattr(tng._bundled.MatrixAdapter, "__init__", inherited_init)
    monkeypatch.setattr(tng._bundled.MatrixAdapter, "get_diagnostics", inherited_diagnostics)
    secret_scope.set_multiplex_active(True)
    try:
        with_key = _build_adapter(
            tng, tmp_path / "with-key", {"MATRIX_RECOVERY_KEY": "profile-key"}
        )
        without_key = _build_adapter(tng, tmp_path / "without-key", {})
    finally:
        secret_scope.set_multiplex_active(False)

    assert with_key.get_diagnostics()["e2ee"]["recovery_key_configured"] is True
    assert without_key.get_diagnostics()["e2ee"]["recovery_key_configured"] is False
