"""Phase 1 compatibility checks; no user plugin is installed by these tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def _load_tng_adapter():
    spec = importlib.util.spec_from_file_location(
        "hermes_matrix_tng_adapter", ROOT / "adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_declares_the_bundled_override_key():
    manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text())
    assert manifest["name"] == "matrix-platform"
    assert manifest["kind"] == "platform"
    assert manifest["version"] == "0.1.0-tng"


def test_phase_one_bridge_matches_bundled_registration_surface():
    tng = _load_tng_adapter()
    from plugins.platforms.matrix import adapter as bundled

    assert tng.TNG_PHASE == 1
    assert tng.UPSTREAM_BASE_COMMIT
    assert tng.register is bundled.register
    assert tng.MatrixAdapter is bundled.MatrixAdapter
    assert tng.check_matrix_requirements is bundled.check_matrix_requirements

