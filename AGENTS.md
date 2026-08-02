# Hermes Matrix TNG — Agent Operating Guide

This repository is the planned successor to the local Hermes Matrix override.
Its purpose is to make multiple Matrix accounts/profiles run safely inside one
Hermes multiplexed gateway process, reducing duplicated gateway RAM without
mixing credentials, policy, sessions, devices, or E2EE state.

## Mission

Deliver an update-tolerant user plugin named `matrix-platform` that replaces
the bundled Hermes Matrix platform adapter through the supported plugin
registry. Do not patch Hermes core unless the plugin boundary is proven
insufficient and the user explicitly approves a core change.

The desired runtime shape is:

- one Hermes gateway process;
- one `MatrixAdapter` instance per served Hermes profile;
- one Matrix client and Olm machine per adapter;
- each adapter retaining its profile's existing Matrix account, device ID,
  recovery key, configuration, and crypto database;
- generic Hermes multiplex routing selecting the correct adapter/profile.

Do **not** build one monolithic `MultiMatrixAdapter`. Hermes already owns
multi-profile adapter creation, routing, reconnects, and shutdown. TNG should
make a normal Matrix adapter safe to instantiate multiple times.

## Required Local Context

Before working, inspect these sources in this order:

1. This file and the documents under `docs/`.
2. `/home/ubuntu/.hermes/hermes-agent/AGENTS.md`.
3. `/home/ubuntu/projects/hermes-matrix-user-plugin/AGENTS.md` for the current
   production override and operational history.
4. The currently installed upstream Matrix adapter:
   `/home/ubuntu/.hermes/hermes-agent/plugins/platforms/matrix/adapter.py`.
5. The generic multiplex implementation in
   `/home/ubuntu/.hermes/hermes-agent/gateway/run.py`, especially
   `_profile_runtime_scope`, `_start_secondary_profile_adapters`,
   `_start_one_profile_adapters`, and secondary reconnect handling.

Search OpenViking before work where previous Matrix/device/gateway history may
matter. Never store or print access tokens, passwords, recovery keys, private
keys, Olm pickle material, or raw crypto database content.

## Non-Negotiable Safety Rules

- Treat Matrix device IDs and their local crypto stores as inseparable.
- Never point an existing device ID at an empty or different crypto store.
- Never delete, move, merge, recreate, or migrate a production crypto store
  without explicit user approval and a verified backup.
- Never rotate access tokens, device IDs, cross-signing keys, or recovery keys
  as part of an ordinary multiplex test.
- Do not let a secondary profile fall back to another profile's process
  environment, credentials, policy, or store path.
- Preserve existing profile directories and production services.
- Do not restart gateways during implementation or unit testing. Restarts are
  allowed only in the rollout phase with explicit user approval.
- Do not modify `/home/ubuntu/projects/hermes-matrix-user-plugin` casually. It
  is the current production plugin and has user-owned uncommitted changes.
- Keep rollback possible at every production step.

## Architectural Boundary

The plugin is an interface adapter around Hermes and Mautrix. Profile
resolution should be completed at adapter construction time, while Hermes has
installed the profile's runtime and secret scopes. Long-lived async work must
use immutable, instance-owned resolved settings; it must not re-read global
`os.environ` or module-global `HERMES_HOME` paths later.

Preferred dependency direction:

1. Pure configuration/path resolution functions accept explicit inputs.
2. `MatrixAdapter` owns a resolved per-profile settings object.
3. Mautrix clients and SQLite stores consume those instance settings.
4. Hermes plugin registration constructs the adapter.

Keep Hermes/Mautrix imports at the outer adapter boundary where practical so
the resolution and safety rules can be tested without a homeserver.

## Phased Delivery Plan

Only one phase should be active at a time. Record phase completion and evidence
in `docs/STATUS.md`. Do not skip a gate because later testing appears easier.

### Phase 0 — Baseline and Inventory

Goal: establish exactly what is running and what must remain compatible.

Steps:

1. Record the installed Hermes commit and upstream `origin/main` commit.
2. Inventory Matrix-related configuration **keys only**, never secret values,
   for every served profile.
3. Record each profile's expected crypto-store path, existence, permissions,
   size, and a checksum taken while its gateway is stopped or after a safe
   SQLite backup. Do not hash an inconsistent live WAL database and call it a
   backup.
4. Map the current user plugin's differences from the matching upstream
   adapter, including its room-create-state and cross-signing fixes.
5. Identify all module globals and raw environment reads in the upstream
   adapter.
6. Capture current gateway RSS/cgroup memory as a comparison baseline.

Gate: `docs/STATUS.md` contains a non-secret inventory, upstream base commit,
current-plugin delta list, and baseline memory numbers.

### Phase 1 — Plugin Skeleton and Upstream Tracking

Goal: create an installable override without changing behavior.

Steps:

1. Add `plugin.yaml`, `__init__.py`, and the adapter implementation.
2. Register as `matrix-platform` so the user plugin cleanly overrides the
   bundled plugin key.
3. Start from a recorded upstream Matrix adapter revision; do not copy an
   unidentified moving version.
4. Port only still-required fixes from the current production plugin.
5. Add an upstream-base marker and a documented diff/rebase procedure.
6. Add a compatibility smoke test that loads the plugin against the installed
   Hermes checkout and verifies registration/factory contracts.

Gate: plugin imports, registers, and constructs under tests with no production
configuration or service changes.

### Phase 2 — Profile Isolation Implementation

Goal: make multiple adapter instances safe within one Python process.

Steps:

1. Replace module-import-time `_STORE_DIR` and `_CRYPTO_DB_PATH` ownership with
   instance-owned paths resolved during adapter construction under the active
   profile runtime scope.
2. Ensure every store operation, legacy-file check, diagnostic, connect,
   reconnect, and disconnect uses the instance path.
3. Resolve all profile-dependent Matrix settings into an immutable settings
   object or `PlatformConfig.extra` at construction time.
4. Remove profile-dependent runtime reads from raw `os.getenv`. Use Hermes's
   scoped secret resolver for secrets and explicit resolved configuration for
   behavior.
5. Include, at minimum: homeserver, token/password, user/device IDs, E2EE mode,
   recovery key, recovery output target, allowed users/rooms, mention rules,
   session/thread rules, ignored-user patterns, proxy, reactions, approval
   policy, media limits, and home-channel routing.
6. Fail closed when a scoped secondary profile lacks a value; never borrow a
   default profile's value.
7. Preserve single-profile behavior and existing store locations.

Gate: two adapters built in one process retain different paths, credentials,
policies, and recovery keys after their construction scopes have exited.

### Phase 3 — Deterministic Test Suite

Goal: minimize production discovery by proving failure-prone behavior locally.

Required test groups:

- pure settings/path resolution tests;
- two-profile secret and behavioral isolation tests;
- missing-secondary-secret fail-closed tests;
- plugin override/registration compatibility tests;
- duplicate Matrix credential/account rejection through the generic gateway;
- inbound profile stamping and outbound adapter selection;
- independent connect, reconnect, fatal-error, and shutdown ownership;
- one adapter disconnecting must not close another adapter's database/client;
- temporary-directory tests using real SQLite/Mautrix crypto-store plumbing;
- preservation tests proving existing store paths are selected without moving
  or recreating them;
- recovery-key scoping tests equivalent to upstream fix `153442dd5` or its
  eventual successor;
- regression tests for every local fix ported from the current plugin.

Mocks may replace network calls and homeserver responses. Prefer real path
resolution, filesystem operations, SQLite connections, and plugin imports.

Gate: all focused tests pass repeatedly, including shuffled or repeated runs,
with no access to production Matrix credentials or stores.

### Phase 4 — Disposable Matrix Integration Environment

Goal: exercise real Matrix/E2EE behavior without production accounts.

Steps:

1. Use disposable Matrix accounts, device IDs, tokens, recovery keys, rooms,
   profile homes, and crypto stores.
2. Start one multiplexed gateway with at least two Matrix profiles.
3. Verify initial E2EE bootstrap, encrypted inbound/outbound messages,
   concurrent sync, reconnect, process restart, and independent shutdown.
4. Verify each profile reopens its own crypto database and retains its device
   identity across restart.
5. Inspect for SQLite locks, pool-stopped errors, key-MAC failures, undecrypted
   events, cross-profile routing, and leaked configuration.

Gate: repeatable end-to-end success after a cold restart, with saved logs and a
short result summary that contains no secrets.

### Phase 5 — Controlled Production Pilot

Goal: validate the remaining homeserver/device interaction with minimal blast
radius.

This phase requires explicit user approval.

Steps:

1. Select two lower-risk profiles; do not begin with the most important Matrix
   identity.
2. Stop only their current gateway units cleanly.
3. Create verified, timestamped backups of their complete Matrix store
   directories plus non-secret configuration metadata.
4. Confirm the multiplexed plugin resolves the exact original store path and
   configured device ID for each profile before connecting.
5. Start the pilot gateway and test newly sent encrypted messages in both
   directions for both accounts.
6. Exercise one clean gateway restart; verify device/store identity again.
7. Soak for 24–48 hours while monitoring memory, sync health, SQLite latency or
   locking, decryption failures, recovery-key failures, reconnect behavior,
   routing, and unexpected cross-signing activity.
8. Compare pilot memory against Phase 0.

Immediate rollback conditions include wrong store path/device ID, key-MAC
failure, unexplained cross-signing generation, persistent undecrypted new
events, account cross-routing, database lock storms, or repeated adapter death.

Gate: stable soak, correct E2EE behavior, documented memory improvement, and
user approval to expand.

### Phase 6 — Gradual Consolidation

Goal: replace the remaining per-profile gateway units safely.

Steps:

1. Add one profile at a time.
2. Repeat backup, preflight identity check, encrypted-message test, restart
   test, and observation window for every addition.
3. Keep old unit definitions available but stopped until the full deployment
   has soaked successfully.
4. Record final memory savings and operational topology.
5. Only remove obsolete units or backups with explicit user approval.

Gate: all intended profiles are served by one stable gateway and rollback
documentation has been verified.

### Phase 7 — Upstream and Maintenance

Goal: avoid a permanent unmaintainable fork.

Steps:

1. Separate generic fixes suitable for upstream from local policy/bootstrap
   behavior.
2. Submit focused upstream changes where appropriate.
3. Track upstream Matrix adapter changes and periodically rebase the plugin.
4. Run compatibility and isolation tests before every Hermes update rollout.
5. Retire TNG only after upstream provides equivalent proven behavior and the
   production stores survive a controlled migration back to bundled code.

## Verification Standard

Mocks are necessary but not sufficient. They should eliminate configuration,
path, ownership, routing, and lifecycle surprises. A disposable real Matrix
test must cover protocol/E2EE mechanics, and a narrow production pilot must
cover the existing homeserver/device/store relationship.

Do not describe a test as proving E2EE if it only mocks Mautrix crypto calls.
Do not describe a database backup as verified until it can be opened or
restored safely.

## Update-Survival Contract

This plugin should survive normal Hermes updates because it lives outside the
Hermes checkout and overrides the platform through registration. It is not
immune to upstream API changes. Any change to `BasePlatformAdapter`,
`PlatformConfig`, platform registration, gateway handler wiring, or Mautrix
dependencies may require a rebase.

The plugin must fail clearly on incompatible interfaces rather than starting a
partially functional Matrix adapter.

## Documentation Duties

- Update `docs/STATUS.md` as phases advance.
- Record architecture decisions in `docs/ARCHITECTURE.md`.
- Keep test strategy and production evidence in `docs/TESTING.md`.
- Keep deployment, rollback, and monitoring steps in `docs/ROLLOUT.md`.
- Never put secrets, recovery keys, tokens, raw logs, or private crypto data in
  Git or documentation.

