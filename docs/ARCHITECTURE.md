# Architecture

## Decision

Use Hermes's existing gateway profile multiplexer. The gateway creates one
ordinary Matrix adapter per profile and owns routing, registries, reconnects,
and shutdown. TNG makes the adapter instance-safe; it does not introduce a
multi-account adapter manager.

## Ownership Model

Each `MatrixAdapter` owns immutable resolved settings and its own runtime
resources:

- profile identity and home;
- homeserver and authentication;
- Matrix user and device identity;
- E2EE mode and recovery configuration;
- crypto-store directory/database path;
- Mautrix client, Olm machine, SQLite connection, and sync tasks;
- access policy, room policy, mention/thread behavior, and other Matrix
  behavior.

No adapter may discover these from mutable process-global state after
construction.

## Boundaries

Pure resolution code should accept an explicit profile home, platform config,
and scoped-secret reader. It returns a resolved settings value. The Hermes
plugin factory is the composition root: it invokes resolution while the
gateway's profile scope is active, then constructs the adapter.

Mautrix and SQLite are infrastructure details consumed by the adapter. Tests
should exercise resolution and ownership without a homeserver, while separate
integration tests exercise the real infrastructure boundary.

## Compatibility Strategy

The project is a full `matrix-platform` override, matching the current local
deployment mechanism. Record the exact upstream source commit in the plugin.
Keep local changes reviewable as focused commits or clearly marked sections so
upstream adapter updates can be rebased rather than recopied blindly.

## Known Hazards to Remove

- crypto-store paths resolved at module import time;
- raw `os.getenv` reads that bypass the active profile secret/config scope;
- module globals that imply one Matrix account per process;
- cleanup paths capable of closing another adapter's resources;
- ephemeral send paths that create and tear down crypto clients independently
  of the live gateway;
- silent compatibility drift from Hermes or Mautrix.

