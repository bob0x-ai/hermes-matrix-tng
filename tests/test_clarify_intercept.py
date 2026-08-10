"""Regression coverage for the multiplex clarify-reply intercept.

Reproduces the 2026-08-10 stuck-session bug: under multiplex_profiles the
runner registers pending clarify entries under agent:<profile>:... while the
core busy-guard looks them up under agent:main:..., so clarify answers get
queued behind the turn that waits for them and the session hangs.

The TNG adapter resolves clarify replies at Matrix ingress using the
adapter's own profile-namespaced key. These tests pin that behavior.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[1]
ROOM = "!clarifytest:example.test"


def _load_tng_adapter():
    spec = importlib.util.spec_from_file_location(
        "hermes_matrix_tng_clarify_adapter", ROOT / "adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_adapter(tng):
    config = SimpleNamespace(token="", extra={})
    adapter = tng.MatrixAdapter(config)
    adapter._message_handler = object()  # truthy sentinel; never invoked
    return adapter


def _make_event(tng, text: str, message_type=None):
    from gateway.platforms.base import MessageEvent, MessageType
    from gateway.config import Platform
    from gateway.session import SessionSource

    source = SessionSource(
        platform=Platform.MATRIX,
        user_id="@dhaneor:example.test",
        user_name="dhaneor",
        chat_id=ROOM,
        chat_type="dm",
        thread_id=None,
    )
    return MessageEvent(
        text=text,
        message_type=message_type or MessageType.TEXT,
        source=source,
        raw_message={},
        message_id="$evt",
    )


@pytest.fixture()
def kernel_scope(monkeypatch):
    """Make adapters constructed under this fixture report the 'kernel' profile.

    Mirrors the runner's multiplex startup: _start_one_profile_adapters builds
    each secondary adapter inside that profile's runtime scope, so the
    adapter's construction-time profile resolution reports its own profile.
    """
    import hermes_cli.profiles as profiles_mod

    monkeypatch.setattr(profiles_mod, "get_active_profile_name", lambda: "kernel")
    yield "kernel"


@pytest.fixture()
def clarify_state():
    """Isolate module-level clarify state per test."""
    from tools import clarify_gateway as cg

    yield cg
    # Cleanup: cancel anything left pending.
    for key in list(cg._session_index.keys()):
        cg.clear_session(key)


def test_adapter_key_matches_runner_profile_namespace(tng_module, kernel_scope):
    adapter = _make_adapter(tng_module)
    event = _make_event(tng_module, "hello")
    assert adapter._adapter_profile_name() == "kernel"
    key = adapter._session_key_for_event(event)
    assert key == f"agent:kernel:matrix:dm:{ROOM}"


def test_clarify_reply_resolves_under_multiplex_key(tng_module, kernel_scope, clarify_state):
    cg = clarify_state
    adapter = _make_adapter(tng_module)
    session_key = adapter._session_key_for_event(_make_event(tng_module, ""))

    # Agent thread (runner) blocks on a clarify registered under agent:kernel:...
    cg.register(
        clarify_id="regtest01",
        session_key=session_key,
        question="Proceed?",
        choices=["Yes", "No"],
    )

    # The core busy-guard's profile-less lookup would miss:
    assert cg.get_pending_for_session(
        f"agent:main:matrix:dm:{ROOM}", include_choice_prompts=True
    ) is None

    # The adapter-side intercept hits and resolves:
    event = _make_event(tng_module, "1")
    assert adapter._try_resolve_pending_clarify(event) is True

    # Blocked thread wakes with the mapped choice and cleans the entry:
    assert cg.wait_for_response("regtest01", timeout=1.0) == "Yes"
    assert cg.get_pending_for_session(session_key, include_choice_prompts=True) is None


def test_slash_commands_are_never_swallowed(tng_module, kernel_scope, clarify_state):
    cg = clarify_state
    adapter = _make_adapter(tng_module)
    session_key = adapter._session_key_for_event(_make_event(tng_module, ""))

    # Open-ended clarify accepts ANY text — /stop must still get through.
    cg.register(clarify_id="regtest02", session_key=session_key,
                question="What next?", choices=None)
    event = _make_event(tng_module, "/stop")
    assert adapter._try_resolve_pending_clarify(event) is False
    # Entry still pending, untouched:
    assert cg.get_pending_for_session(session_key, include_choice_prompts=True) is not None


def test_no_pending_clarify_passes_through(tng_module, kernel_scope, clarify_state):
    adapter = _make_adapter(tng_module)
    event = _make_event(tng_module, "just a normal message")
    assert adapter._try_resolve_pending_clarify(event) is False


def test_rejected_prose_falls_through_to_core_dispatch(tng_module, kernel_scope, clarify_state):
    """Multi-choice clarify + arbitrary prose: rejected, normal dispatch continues."""
    cg = clarify_state
    adapter = _make_adapter(tng_module)
    session_key = adapter._session_key_for_event(_make_event(tng_module, ""))

    # Native button UI: awaiting_text=False → arbitrary prose is rejected.
    cg.register(clarify_id="regtest03", session_key=session_key,
                question="Pick one", choices=["A", "B"])
    event = _make_event(tng_module, "some unrelated prose")
    assert adapter._try_resolve_pending_clarify(event) is False
    # Entry still pending (core dispatch will queue it as a follow-up):
    assert cg.get_pending_for_session(session_key, include_choice_prompts=True) is not None


def test_handle_message_delegates_to_core_when_not_a_clarify_reply(tng_module, kernel_scope, monkeypatch):
    adapter = _make_adapter(tng_module)
    calls = []

    async def fake_core_handle(self, event):
        calls.append(event.text)

    from gateway.platforms.base import BasePlatformAdapter

    monkeypatch.setattr(BasePlatformAdapter, "handle_message", fake_core_handle)
    asyncio.run(adapter.handle_message(_make_event(tng_module, "hi there")))
    assert calls == ["hi there"]


def test_handle_message_short_circuits_on_resolved_clarify(tng_module, kernel_scope, clarify_state, monkeypatch):
    cg = clarify_state
    adapter = _make_adapter(tng_module)
    session_key = adapter._session_key_for_event(_make_event(tng_module, ""))
    cg.register(clarify_id="regtest04", session_key=session_key,
                question="Go?", choices=["Yes", "No"])

    calls = []

    async def fake_core_handle(self, event):
        calls.append(event.text)

    from gateway.platforms.base import BasePlatformAdapter

    monkeypatch.setattr(BasePlatformAdapter, "handle_message", fake_core_handle)
    asyncio.run(adapter.handle_message(_make_event(tng_module, "2")))

    assert calls == []  # core dispatch never saw the reply
    assert cg.wait_for_response("regtest04", timeout=1.0) == "No"


@pytest.fixture()
def tng_module():
    return _load_tng_adapter()
