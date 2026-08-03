#!/usr/bin/env python3
"""Exercise automatic same-device key repair against the local Tuwunel test account.

The script intentionally uses a fresh temporary local store with the reusable
``TEST1_*`` account. That differs from the server's existing key for its
configured device ID. With ``TEST1_PASSWORD`` supplied, the first connection
must execute the full UIA-backed repair and the second must restart cleanly.
Without it, the test proves that TNG reports the UIA requirement clearly and
does not make an unverified mutation. It never prints credentials.

Example (run only against the disposable local account):

  set -a; . /home/ubuntu/.config/hermes-matrix-tng/accounts.env; set +a
  python scripts/live_device_key_recovery_test.py --run
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]


def load_adapter():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("tng_live_recovery_adapter", ROOT / "adapter.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="confirm the intentional, disposable-account server-device repair",
    )
    return parser.parse_args()


async def exercise(adapter_type, config, store_dir: Path) -> tuple[bool, str, list[str]]:
    adapter = adapter_type(config)
    connected = await adapter.connect()
    try:
        diagnostics = adapter.get_diagnostics()
        status = diagnostics["recovery"]["status"]
        evidence = store_dir / "device-key-mismatches.jsonl"
        actions = []
        if evidence.exists():
            actions = [json.loads(line)["action"] for line in evidence.read_text().splitlines()]
        return connected, status, actions
    finally:
        await adapter.disconnect()


async def main() -> None:
    args = parse_args()
    if not args.run:
        raise SystemExit("Refusing to mutate a Matrix device without --run")

    required = ("TEST1_ACCESS_TOKEN", "TEST1_USER_ID", "TEST1_DEVICE_ID")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit("Missing disposable-account environment: " + ", ".join(missing))

    old_home = os.environ.get("HERMES_HOME")
    with tempfile.TemporaryDirectory(prefix="hermes-matrix-tng-device-recovery-") as temp:
        profile_home = Path(temp) / "profile"
        os.environ["HERMES_HOME"] = str(profile_home)
        tng = load_adapter()
        config = SimpleNamespace(
            token=os.environ["TEST1_ACCESS_TOKEN"],
            api_key=None,
            extra={
                "homeserver": os.environ.get("TEST_MATRIX_HOMESERVER", "http://127.0.0.1:6167"),
                "user_id": os.environ["TEST1_USER_ID"],
                "device_id": os.environ["TEST1_DEVICE_ID"],
                "password": os.environ.get("TEST1_PASSWORD", ""),
                "e2ee_mode": "required",
            },
        )
        store_dir = profile_home / "platforms" / "matrix" / "store"
        first_ok, first_status, actions = await exercise(tng.MatrixAdapter, config, store_dir)
        if os.environ.get("TEST1_PASSWORD"):
            second_ok, second_status, second_actions = await exercise(tng.MatrixAdapter, config, store_dir)

    if old_home is None:
        os.environ.pop("HERMES_HOME", None)
    else:
        os.environ["HERMES_HOME"] = old_home

    if not os.environ.get("TEST1_PASSWORD"):
        assert not first_ok and first_status == "server_repair_needs_uia", (first_ok, first_status)
        assert actions == ["detected", "server_repair_started", "server_delete_needs_uia"], actions
        print("PASS: live server correctly required UIA; TNG surfaced it without mutation")
        return

    assert first_ok and first_status == "server_device_repaired", (first_ok, first_status)
    assert actions == [
        "detected",
        "server_repair_started",
        "server_delete_uia_completed",
        "server_repair_verified",
    ], actions
    assert second_ok and second_status == "normal", (second_ok, second_status)
    assert second_actions == actions, second_actions
    print("PASS: live disposable device repair, verification, and clean restart")


if __name__ == "__main__":
    asyncio.run(main())
