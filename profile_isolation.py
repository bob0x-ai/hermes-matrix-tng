"""Pure-ish profile resolution primitives for the TNG Matrix adapter.

The gateway installs a profile runtime/secret scope before constructing an
adapter. This module snapshots the values needed by the adapter so later
async work does not consult mutable process-global state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from agent.secret_scope import UnscopedSecretError, get_secret
from hermes_constants import get_hermes_home


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_csv(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(item.strip() for item in str(value).split(",") if item.strip())


def _secret(name: str, default: str = "") -> str:
    """Read a scoped value, preserving fail-closed multiplex semantics."""
    try:
        return str(get_secret(name, default) or "")
    except UnscopedSecretError:
        # The default-profile construction path may be unscoped while the
        # gateway is multiplexing. In that path os.environ is the default
        # profile's own source and is safe for compatibility with Hermes.
        return os.getenv(name, default) or ""


@dataclass(frozen=True)
class MatrixProfileSettings:
    profile_home: Path
    store_dir: Path
    crypto_db_path: Path
    homeserver: str
    access_token: str
    user_id: str
    password: str
    device_id: str
    e2ee_mode: str
    device_key_mismatch_policy: str
    recovery_key: str
    recovery_key_output_file: str
    adapter_alert_homeserver: str
    adapter_alert_token: str
    adapter_alert_room_alias: str
    adapter_alert_user_id: str
    allowed_users: tuple[str, ...]
    allowed_rooms: tuple[str, ...]
    free_response_rooms: tuple[str, ...]
    require_mention: bool
    auto_thread: bool
    dm_auto_thread: bool
    dm_mention_threads: bool
    session_scope: str
    process_notices: bool
    reactions: bool
    allow_room_mentions: bool
    allow_public_rooms: bool
    proxy: str
    max_media_bytes: int
    max_message_length: int
    room_identity_ttl_seconds: float
    text_batch_delay_seconds: float
    text_batch_split_delay_seconds: float
    approval_require_sender: bool
    approval_timeout_seconds: int


def resolve_matrix_profile_settings(config: Any, profile_home: str | Path | None = None) -> MatrixProfileSettings:
    """Snapshot Matrix settings for the currently active Hermes profile.

    ``config.extra`` is authoritative for values already normalized by Hermes;
    scoped secrets are used for credentials and environment-backed settings.
    The returned paths are explicit and remain valid after the runtime scope
    exits.
    """
    extra: Mapping[str, Any] = getattr(config, "extra", {}) or {}
    home = Path(profile_home or get_hermes_home()).resolve()

    def value(extra_key: str, env_name: str, default: Any = "") -> Any:
        if extra_key in extra and extra[extra_key] is not None:
            return extra[extra_key]
        return _secret(env_name, str(default) if default != "" else "")

    def adapter_alert_value(extra_key: str, profile_env: str, global_env: str) -> str:
        """Resolve the intentional process-global adapter notifier identity.

        It is one operator account shared by all Matrix profiles, not a
        profile credential. Snapshot it now so later async recovery work does
        not consult the mutable process environment.
        """
        if extra_key in extra and extra[extra_key] is not None:
            return str(extra[extra_key])
        profile_value = _secret(profile_env, "")
        return str(profile_value or os.getenv(global_env, ""))

    homeserver = str(value("homeserver", "MATRIX_HOMESERVER", "")).rstrip("/")
    token = str(getattr(config, "token", None) or value("access_token", "MATRIX_ACCESS_TOKEN", ""))
    user_id = str(value("user_id", "MATRIX_USER_ID", ""))
    password = str(value("password", "MATRIX_PASSWORD", ""))
    device_id = str(value("device_id", "MATRIX_DEVICE_ID", ""))
    e2ee_mode = str(value("e2ee_mode", "MATRIX_E2EE_MODE", "")).strip().lower()
    if not e2ee_mode:
        e2ee_mode = "required" if _as_bool(value("encryption", "MATRIX_ENCRYPTION", False), False) else "off"

    device_key_mismatch_policy = str(
        value("device_key_mismatch_policy", "MATRIX_DEVICE_KEY_MISMATCH_POLICY", "repair")
    ).strip().lower()
    if device_key_mismatch_policy not in {"repair", "quarantine"}:
        device_key_mismatch_policy = "repair"

    def integer(extra_key: str, env_name: str, default: int) -> int:
        try:
            return int(value(extra_key, env_name, default))
        except (TypeError, ValueError):
            return default

    def decimal(extra_key: str, env_name: str, default: float) -> float:
        try:
            return float(value(extra_key, env_name, default))
        except (TypeError, ValueError):
            return default

    session_scope = str(value("session_scope", "MATRIX_SESSION_SCOPE", "auto")).strip().lower()
    if session_scope not in {"auto", "room", "thread"}:
        session_scope = "auto"

    return MatrixProfileSettings(
        profile_home=home,
        store_dir=home / "platforms" / "matrix" / "store",
        crypto_db_path=home / "platforms" / "matrix" / "store" / "crypto.db",
        homeserver=homeserver,
        access_token=token,
        user_id=user_id,
        password=password,
        device_id=device_id,
        e2ee_mode=e2ee_mode,
        device_key_mismatch_policy=device_key_mismatch_policy,
        recovery_key=_secret("MATRIX_RECOVERY_KEY", ""),
        recovery_key_output_file=_secret("MATRIX_RECOVERY_KEY_OUTPUT_FILE", ""),
        adapter_alert_homeserver=adapter_alert_value(
            "adapter_alert_homeserver", "MATRIX_ADAPTER_ALERT_HOMESERVER", "HERMES_MATRIX_ADAPTER_ALERT_HOMESERVER"
        ).rstrip("/"),
        adapter_alert_token=adapter_alert_value(
            "adapter_alert_token", "MATRIX_ADAPTER_ALERT_TOKEN", "HERMES_MATRIX_ADAPTER_ALERT_TOKEN"
        ),
        adapter_alert_room_alias=adapter_alert_value(
            "adapter_alert_room_alias", "MATRIX_ADAPTER_ALERT_ROOM", "HERMES_MATRIX_ADAPTER_ALERT_ROOM"
        ),
        adapter_alert_user_id=adapter_alert_value(
            "adapter_alert_user_id", "MATRIX_ADAPTER_ALERT_USER_ID", "HERMES_MATRIX_ADAPTER_ALERT_USER_ID"
        ),
        allowed_users=_as_csv(value("allowed_users", "MATRIX_ALLOWED_USERS", "")),
        allowed_rooms=_as_csv(value("allowed_rooms", "MATRIX_ALLOWED_ROOMS", "")),
        free_response_rooms=_as_csv(value("free_response_rooms", "MATRIX_FREE_RESPONSE_ROOMS", "")),
        require_mention=_as_bool(value("require_mention", "MATRIX_REQUIRE_MENTION", True), True),
        auto_thread=_as_bool(value("auto_thread", "MATRIX_AUTO_THREAD", True), True),
        dm_auto_thread=_as_bool(value("dm_auto_thread", "MATRIX_DM_AUTO_THREAD", False), False),
        dm_mention_threads=_as_bool(value("dm_mention_threads", "MATRIX_DM_MENTION_THREADS", False), False),
        session_scope=session_scope,
        process_notices=_as_bool(value("process_notices", "MATRIX_PROCESS_NOTICES", False), False),
        reactions=not str(value("reactions", "MATRIX_REACTIONS", "true")).strip().lower() in {"0", "false", "no"},
        allow_room_mentions=_as_bool(value("allow_room_mentions", "MATRIX_ALLOW_ROOM_MENTIONS", False), False),
        allow_public_rooms=_as_bool(value("allow_public_rooms", "MATRIX_ALLOW_PUBLIC_ROOMS", False), False),
        proxy=str(value("proxy", "MATRIX_PROXY", "")),
        max_media_bytes=integer("max_media_bytes", "MATRIX_MAX_MEDIA_BYTES", 100 * 1024 * 1024),
        max_message_length=integer("max_message_length", "MATRIX_MAX_MESSAGE_LENGTH", 16000),
        room_identity_ttl_seconds=decimal("room_identity_ttl_seconds", "MATRIX_ROOM_IDENTITY_TTL_SECONDS", 60),
        text_batch_delay_seconds=decimal("text_batch_delay_seconds", "HERMES_MATRIX_TEXT_BATCH_DELAY_SECONDS", 0.6),
        text_batch_split_delay_seconds=decimal("text_batch_split_delay_seconds", "HERMES_MATRIX_TEXT_BATCH_SPLIT_DELAY_SECONDS", 2.0),
        approval_require_sender=_as_bool(value("approval_require_sender", "MATRIX_APPROVAL_REQUIRE_SENDER", True), True),
        approval_timeout_seconds=integer("approval_timeout_seconds", "MATRIX_APPROVAL_TIMEOUT_SECONDS", 300),
    )
