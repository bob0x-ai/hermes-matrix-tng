"""Profile-isolated Hermes Matrix adapter.

The implementation reuses Hermes' bundled Matrix adapter while scoping its
legacy process-wide paths and environment reads to each adapter instance.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import asyncio
import os
import threading

from hermes_constants import reset_hermes_home_override, set_hermes_home_override


def _resolve_import_home(
    *, env_home: str | None, env_profile: str | None, platform_home: Path, active_profile: str | None
) -> Path | None:
    """Choose the profile home used while importing legacy Hermes modules."""
    if env_home and env_home.strip():
        return Path(env_home).expanduser().resolve()
    profile = (env_profile or active_profile or "").strip()
    if profile and profile != "default":
        return (platform_home / "profiles" / profile).resolve()
    return platform_home.resolve()


def _import_bundled_adapter():
    """Import the legacy adapter under the active profile home.

    Several Hermes platform/base modules initialize path globals at import
    time. Importing them with an unset ``HERMES_HOME`` while a named profile is
    active causes a misleading fallback to the default home. This scoped import
    prevents that warning and gives the inherited module globals the primary
    profile's initial context; per-adapter lifecycle scopes handle secondary
    profiles afterward.
    """
    platform_home = Path.home() / ".hermes"
    active_file = platform_home / "active_profile"
    try:
        active_profile = active_file.read_text(encoding="utf-8").strip()
    except OSError:
        active_profile = None
    home = _resolve_import_home(
        env_home=os.environ.get("HERMES_HOME"),
        env_profile=os.environ.get("HERMES_PROFILE"),
        platform_home=platform_home,
        active_profile=active_profile,
    )
    token = set_hermes_home_override(home)
    try:
        try:
            from . import bundled_adapter as bundled
        except ImportError as exc:
            if "no known parent package" not in str(exc):
                raise
            import bundled_adapter as bundled
        return bundled
    finally:
        reset_hermes_home_override(token)


_bundled = _import_bundled_adapter()

try:
    from .profile_isolation import MatrixProfileSettings, resolve_matrix_profile_settings
except ImportError as exc:
    if "no known parent package" not in str(exc):
        raise
    from profile_isolation import MatrixProfileSettings, resolve_matrix_profile_settings

UPSTREAM_BASE_COMMIT = "bc747001eec58150aba08e586ff1e7a25fc532aa"
UPSTREAM_ORIGIN_MAIN_AT_BASELINE = "024f3e044bfd89ee226afc604fffafc1c2005f7ec"
TNG_PHASE = 5

@contextmanager
def _profile_env_scope(settings: MatrixProfileSettings):
    """Temporarily provide legacy raw-env reads with this profile's values."""
    values = {
        "MATRIX_RECOVERY_KEY": settings.recovery_key,
        "MATRIX_RECOVERY_KEY_OUTPUT_FILE": settings.recovery_key_output_file,
        "MATRIX_DEVICE_KEY_MISMATCH_POLICY": settings.device_key_mismatch_policy,
        "MATRIX_ADAPTER_ALERT_HOMESERVER": settings.adapter_alert_homeserver,
        "MATRIX_ADAPTER_ALERT_TOKEN": settings.adapter_alert_token,
        "MATRIX_ADAPTER_ALERT_ROOM": settings.adapter_alert_room_alias,
        "MATRIX_ADAPTER_ALERT_USER_ID": settings.adapter_alert_user_id,
        "MATRIX_ALLOW_PUBLIC_ROOMS": "true" if settings.allow_public_rooms else "false",
    }
    previous = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class MatrixAdapter(_bundled.MatrixAdapter):
    """Phase 2 adapter shell with profile-owned persistent state.

    The inherited Matrix behavior remains unchanged for now. Lifecycle entry
    points receive explicit store paths; the remaining profile-dependent
    behavior is applied from the immutable settings snapshot.
    """

    _store_lifecycle_lock: asyncio.Lock | None = None
    _store_path_lock = threading.RLock()

    def __init__(self, config):
        self.profile_settings = resolve_matrix_profile_settings(config)
        self._device_key_mismatch = False
        self._device_key_recovery_status = "normal"
        # Vendored runtime methods use instance-owned paths from their first
        # constructor call onward; establish them before invoking upstream.
        self._store_dir = self.profile_settings.store_dir
        self._crypto_db_path = self.profile_settings.crypto_db_path
        with type(self)._store_path_lock:
            with _profile_env_scope(self.profile_settings):
                super().__init__(config)
        self._apply_profile_settings()

    def _apply_profile_settings(self):
        s = self.profile_settings
        self._store_dir = s.store_dir
        self._crypto_db_path = s.crypto_db_path
        self._homeserver = s.homeserver
        self._access_token = s.access_token
        self._user_id = s.user_id
        self._password = s.password
        self._device_id = s.device_id
        self._e2ee_mode = s.e2ee_mode
        self._encryption = s.e2ee_mode != "off"
        self._device_key_mismatch_policy = s.device_key_mismatch_policy
        self._adapter_alert_homeserver = s.adapter_alert_homeserver or s.homeserver
        self._adapter_alert_token = s.adapter_alert_token
        self._adapter_alert_room_alias = s.adapter_alert_room_alias
        self._adapter_alert_user_id = s.adapter_alert_user_id
        self._allowed_user_ids = set(s.allowed_users)
        self._allowed_rooms = set(s.allowed_rooms)
        self._allowed_room_ids = set(s.allowed_rooms)
        self._free_rooms = set(s.free_response_rooms)
        self._require_mention = s.require_mention
        self._auto_thread = s.auto_thread
        self._dm_auto_thread = s.dm_auto_thread
        self._dm_mention_threads = s.dm_mention_threads
        self._matrix_session_scope = s.session_scope
        self._process_notices = s.process_notices
        self._reactions_enabled = s.reactions
        self._allow_room_mentions = s.allow_room_mentions
        self._allow_public_rooms = s.allow_public_rooms
        self._proxy_url = s.proxy or None
        self._max_media_bytes = s.max_media_bytes
        self.max_message_length = s.max_message_length
        self.MAX_MESSAGE_LENGTH = s.max_message_length
        self._split_threshold = max(100, s.max_message_length - 100)
        self._room_identity_ttl_seconds = s.room_identity_ttl_seconds
        self._text_batch_delay_seconds = s.text_batch_delay_seconds
        self._text_batch_split_delay_seconds = s.text_batch_split_delay_seconds
        self._approval_require_sender = s.approval_require_sender
        self._approval_timeout_seconds = s.approval_timeout_seconds

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if type(self)._store_lifecycle_lock is None:
            type(self)._store_lifecycle_lock = asyncio.Lock()
        async with type(self)._store_lifecycle_lock:
            with _profile_env_scope(self.profile_settings):
                return await super().connect(is_reconnect=is_reconnect)

    async def disconnect(self):
        if type(self)._store_lifecycle_lock is None:
            type(self)._store_lifecycle_lock = asyncio.Lock()
        async with type(self)._store_lifecycle_lock:
            with _profile_env_scope(self.profile_settings):
                return await super().disconnect()

    def get_diagnostics(self):
        with type(self)._store_path_lock:
            result = super().get_diagnostics()
        if isinstance(result, dict):
            result["recovery"] = {
                "status": self._device_key_recovery_status,
                "evidence_file": str(self._crypto_db_path.parent / "device-key-mismatches.jsonl"),
                "action": (
                    "the server device was repaired from this profile's local crypto store; review the audit record"
                    if self._device_key_recovery_status == "server_device_repaired"
                    else "configure this profile's Matrix password so the server's password confirmation can complete the repair"
                    if self._device_key_recovery_status == "server_repair_needs_uia"
                    else "restore a matching crypto-store backup or explicitly create a new device/store"
                    if self._device_key_mismatch
                    else "none"
                ),
            }
            crypto = result.get("e2ee")
            if isinstance(crypto, dict):
                crypto["crypto_store_path"] = str(self.profile_settings.crypto_db_path)
            policy = result.get("policy")
            if isinstance(policy, dict):
                policy["allow_room_mentions"] = self.profile_settings.allow_room_mentions
                policy["allow_public_rooms"] = self.profile_settings.allow_public_rooms
        return result

    async def create_room(self, *args, **kwargs):
        """Keep public-room policy bound to this adapter's profile."""
        if kwargs.get("preset", "private_chat") == "public_chat" and not self.profile_settings.allow_public_rooms:
            return None
        with _profile_env_scope(self.profile_settings):
            return await super().create_room(*args, **kwargs)


def _build_adapter(config):
    return MatrixAdapter(config)


async def _standalone_send(
    pconfig,
    chat_id,
    message,
    *,
    thread_id=None,
    media_files=None,
    force_document=False,
):
    """Profile-explicit standalone Matrix delivery.

    This path is intentionally small and token-only. Password login and E2EE
    standalone delivery remain live-adapter responsibilities; a cron job must
    not create a second crypto client for the same account.
    """
    import time
    from urllib.parse import quote

    try:
        import aiohttp
    except ImportError:
        return {"error": "aiohttp not installed. Run: pip install aiohttp"}
    extra = getattr(pconfig, "extra", {}) or {}
    homeserver = str(extra.get("homeserver", "")).rstrip("/")
    token = str(getattr(pconfig, "token", None) or "")
    if not homeserver or not token:
        return {"error": "Matrix standalone delivery requires explicit homeserver and access token"}
    url = f"{homeserver}/_matrix/client/v3/rooms/{quote(str(chat_id), safe='')}/send/m.room.message/{int(time.time() * 1000)}"
    payload = {"msgtype": "m.text", "body": str(message)}
    try:
        import markdown as markdown_lib
        payload["format"] = "org.matrix.custom.html"
        payload["formatted_body"] = markdown_lib.markdown(
            str(message), extensions=["fenced_code", "tables"]
        )
    except ImportError:
        pass
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.put(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            ) as response:
                if response.status not in {200, 201}:
                    return {"error": f"Matrix API error ({response.status}): {await response.text()}"}
                data = await response.json()
        return {"success": True, "platform": "matrix", "chat_id": chat_id, "message_id": data.get("event_id")}
    except Exception as exc:
        return {"error": f"Matrix send failed: {exc}"}


class _RegistrationContext:
    def __init__(self, context):
        self._context = context

    def __getattr__(self, name):
        return getattr(self._context, name)

    def register_platform(self, *args, **kwargs):
        kwargs["adapter_factory"] = _build_adapter
        kwargs["standalone_sender_fn"] = _standalone_send
        return self._context.register_platform(*args, **kwargs)


def register(ctx):
    """Register the bundled manifest surface with the TNG adapter factory."""
    return _bundled.register(_RegistrationContext(ctx))


check_matrix_requirements = _bundled.check_matrix_requirements

__all__ = [
    "MatrixAdapter",
    "UPSTREAM_BASE_COMMIT",
    "UPSTREAM_ORIGIN_MAIN_AT_BASELINE",
    "TNG_PHASE",
    "check_matrix_requirements",
    "register",
]
