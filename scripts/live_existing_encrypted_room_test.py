#!/usr/bin/env python3
"""Validate encrypted sends to an existing room immediately after TNG restart.

This uses two persistent disposable accounts and profile homes outside the
repository. ``--bootstrap`` creates those accounts once on the local Tuwunel
server; later executions reuse the same device IDs, tokens, stores, and room.
It never reads or changes production Matrix profiles or crypto stores.

Run:

  python scripts/live_existing_encrypted_room_test.py --bootstrap --run
  python scripts/live_existing_encrypted_room_test.py --run
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from types import SimpleNamespace

ROOT = Path(__file__).parents[1]
STATE_DIR = Path.home() / ".local" / "state" / "hermes-matrix-tng" / "disposable-e2e"
ACCOUNTS_FILE = STATE_DIR / "accounts.json"
DEFAULT_HOMESERVER = "http://127.0.0.1:6167"

# This dedicated subprocess has no production profile. Set its import context
# before Hermes modules read the host's active-profile marker.
os.environ.setdefault("HERMES_HOME", str(STATE_DIR / "profiles" / "import"))

from agent import secret_scope
from hermes_constants import reset_hermes_home_override, set_hermes_home_override
from mautrix.types import EventType, RoomID, UserID


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="perform the live disposable check")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="create the two persistent disposable accounts if they do not exist",
    )
    parser.add_argument(
        "--tuwunel-config",
        type=Path,
        default=Path("/etc/tuwunel/tuwunel.toml"),
        help="root-readable local Tuwunel configuration used only to read its registration token",
    )
    return parser.parse_args()


def _load_adapter():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "tng_existing_encrypted_room_adapter", ROOT / "adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(STATE_DIR / "profiles" / "import")
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous_home
    return module


def _read_registration_token(config_path: Path) -> str:
    """Read the local registration token without exposing it in output."""
    program = r'/^[[:space:]]*registration_token[[:space:]]+/ { print $2; exit }'
    try:
        token = subprocess.check_output(
            ["sudo", "awk", program, str(config_path)], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("could not read the local Tuwunel registration token") from exc
    if len(token) < 2 or token[0] != '"' or token[-1] != '"':
        raise RuntimeError("the local Tuwunel registration token is not configured")
    return token[1:-1]


def _request_json(url: str, body: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            response_body = json.loads(exc.read().decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            response_body = {"errcode": "HTTP_ERROR"}
        return exc.code, response_body


def _register_account(homeserver: str, registration_token: str, label: str) -> dict[str, str]:
    status, challenge = _request_json(f"{homeserver}/_matrix/client/v3/register", {})
    session = challenge.get("session")
    if status != 401 or not session:
        raise RuntimeError("Matrix registration did not return an authentication session")
    username = f"tng-e2e-{label}-{secrets.token_hex(4)}"
    password = secrets.token_urlsafe(32)
    status, response = _request_json(
        f"{homeserver}/_matrix/client/v3/register",
        {
            "auth": {
                "type": "m.login.registration_token",
                "token": registration_token,
                "session": session,
            },
            "username": username,
            "password": password,
            "initial_device_display_name": "Hermes Matrix TNG disposable E2EE",
        },
    )
    if status != 200:
        raise RuntimeError(f"Matrix registration failed: {response.get('errcode', status)}")
    required = ("user_id", "access_token", "device_id")
    if any(not response.get(name) for name in required):
        raise RuntimeError("Matrix registration returned incomplete disposable credentials")
    return {
        "user_id": str(response["user_id"]),
        "access_token": str(response["access_token"]),
        "device_id": str(response["device_id"]),
        "password": password,
    }


def _write_accounts(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=STATE_DIR, delete=False, encoding="utf-8") as handle:
            json.dump(data, handle)
            handle.write("\n")
            temporary_path = Path(handle.name)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, ACCOUNTS_FILE)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _load_or_bootstrap(args: argparse.Namespace) -> dict:
    if ACCOUNTS_FILE.exists():
        try:
            data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("disposable account state cannot be read") from exc
        if all(data.get(key) for key in ("homeserver", "first", "second")):
            return data
        raise RuntimeError("disposable account state is incomplete; do not overwrite it automatically")
    if not args.bootstrap:
        raise RuntimeError("no persistent disposable accounts exist; rerun once with --bootstrap")

    homeserver = os.getenv("TEST_MATRIX_HOMESERVER", DEFAULT_HOMESERVER).rstrip("/")
    registration_token = _read_registration_token(args.tuwunel_config)
    data = {
        "homeserver": homeserver,
        "first": _register_account(homeserver, registration_token, "one"),
        "second": _register_account(homeserver, registration_token, "two"),
    }
    _write_accounts(data)
    return data


def _build_adapter(tng, homeserver: str, name: str, account: dict[str, str], peer_user_id: str):
    home = STATE_DIR / "profiles" / name
    home_token = set_hermes_home_override(home)
    secret_token = secret_scope.set_secret_scope({})
    try:
        return tng.MatrixAdapter(
            SimpleNamespace(
                token=account["access_token"],
                api_key=None,
                extra={
                    "homeserver": homeserver,
                    "user_id": account["user_id"],
                    "password": account["password"],
                    "device_id": account["device_id"],
                    "e2ee_mode": "required",
                    "allowed_users": [peer_user_id],
                    "require_mention": False,
                },
            )
        )
    finally:
        secret_scope.reset_secret_scope(secret_token)
        reset_hermes_home_override(home_token)


async def _connect_pair(tng, accounts: dict):
    first = _build_adapter(
        tng, accounts["homeserver"], "first", accounts["first"], accounts["second"]["user_id"]
    )
    second = _build_adapter(
        tng, accounts["homeserver"], "second", accounts["second"], accounts["first"]["user_id"]
    )
    connected = await asyncio.gather(first.connect(), second.connect())
    if not all(connected):
        await asyncio.gather(first.disconnect(), second.disconnect(), return_exceptions=True)
        raise RuntimeError("one or both disposable Matrix adapters did not connect")
    return first, second


async def _ensure_encrypted_room(first, second, accounts: dict) -> str:
    room_id = accounts.get("room_id")
    if room_id:
        return str(room_id)
    room_id = str(
        await first._client.create_room(
            invitees=[UserID(accounts["second"]["user_id"])],
            initial_state=[
                {
                    "type": "m.room.encryption",
                    "state_key": "",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                }
            ],
        )
    )
    await second._client.join_room(RoomID(room_id))
    accounts["room_id"] = room_id
    _write_accounts(accounts)
    return room_id


async def _send_and_receive(sender, receiver, room_id: str, body: str) -> None:
    received: asyncio.Queue[str] = asyncio.Queue()

    async def capture(event) -> None:
        content = getattr(event, "content", None)
        if str(getattr(event, "room_id", "")) == room_id and getattr(content, "body", None) == body:
            received.put_nowait(body)

    receiver._client.add_event_handler(EventType.ROOM_MESSAGE, capture, wait_sync=True)
    result = await sender.send(room_id, body)
    if not result.success:
        raise RuntimeError("TNG could not send an encrypted disposable test message")
    try:
        await asyncio.wait_for(received.get(), timeout=45)
    except asyncio.TimeoutError as exc:
        raise RuntimeError("the receiving TNG adapter did not decrypt the encrypted test message") from exc


async def exercise(accounts: dict) -> None:
    tng = _load_adapter()
    secret_scope.set_multiplex_active(True)
    first = second = None
    try:
        first, second = await _connect_pair(tng, accounts)
        room_id = await _ensure_encrypted_room(first, second, accounts)
        await _send_and_receive(first, second, room_id, "TNG disposable pre-restart encrypted message")
        await asyncio.gather(first.disconnect(), second.disconnect())
        first = second = None

        # This is the review target: the room already exists, and the first
        # post-restart operation is an encrypted send with no historic room
        # dispatch or manual state backfill in between.
        first, second = await _connect_pair(tng, accounts)
        await _send_and_receive(first, second, room_id, "TNG disposable immediate post-restart encrypted message")
    finally:
        secret_scope.set_multiplex_active(False)
        if first is not None and second is not None:
            await asyncio.gather(first.disconnect(), second.disconnect(), return_exceptions=True)


async def main() -> None:
    args = parse_args()
    if not args.run:
        raise SystemExit("Refusing to contact Matrix without --run")
    accounts = _load_or_bootstrap(args)
    await exercise(accounts)
    print("PASS: two persistent disposable TNG adapters exchanged encrypted messages before and immediately after restart")


if __name__ == "__main__":
    asyncio.run(main())
