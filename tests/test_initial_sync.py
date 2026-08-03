"""Regression coverage for bounded multiplexed Matrix startup."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _load_tng_adapter():
    spec = importlib.util.spec_from_file_location(
        "hermes_matrix_tng_initial_sync_adapter", ROOT / "adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_initial_sync_dispatch_keeps_e2ee_events_but_never_replays_room_history():
    tng = _load_tng_adapter()
    original = {
        "next_batch": "batch-token",
        "to_device": {"events": [{"type": "m.room_key"}]},
        "device_lists": {"changed": ["@owner:example.test"]},
        "rooms": {
            "join": {
                "!large-history:example.test": {
                    "timeline": {"events": [{"type": "m.room.message"}]}
                }
            }
        },
    }

    bounded = tng._bundled._initial_sync_non_room_payload(original)

    assert bounded is not original
    assert bounded["next_batch"] == "batch-token"
    assert bounded["to_device"] is original["to_device"]
    assert bounded["device_lists"] is original["device_lists"]
    assert bounded["rooms"] == {}
    assert original["rooms"]["join"]
