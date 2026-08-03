# Hermes Matrix TNG migration notes

## Current state

- TNG is implemented on branch `phase-5-controlled-pilot`.
- The adapter vendors Hermes Matrix adapter commit
  `bc747001eec58150aba08e586ff1e7a25fc532aa`.
- Runtime crypto-store paths are instance-owned; the inherited module-global
  path collision has been removed.
- A server/local device-key mismatch is repaired automatically from the
  profile's intact local crypto store: TNG deletes the conflicting server
  record for the same device ID, re-uploads local keys, and verifies the
  result. It records every step and non-reversible key fingerprints in
  `device-key-mismatches.jsonl` beside the store. Per-profile quarantine mode
  remains available when manual handling is preferred.
- Local suite: 18 tests passing.
- Disposable Tuwunel test: two concurrent encrypted DM profiles connected,
  exchanged messages in both directions, and reconnected from the same stores.
- Optional operator notifications are documented in `ALERTING.md`. They use a
  dedicated token-only `@matrix-adapter` identity and an explicitly configured
  unencrypted room; no production notifier account has been created by this
  project.

## Deployment rules

1. Back up each complete Matrix store directory, including WAL/SHM files.
2. Never reuse a Matrix device ID with a different crypto store.
3. Deploy TNG alongside the existing plugin and start with a small profile set.
4. Verify device/store fingerprints before enabling sync.
5. Monitor SQLite locks, undecryptable events, device-key mismatches, and
   reconnect behavior before expanding the profile set.

## Validated live deployment (old VPS, 2026-08-04)

- One `hermes-gateway.service` process served `hikari`, `lens`, `writer`, and
  `yan-cgo` concurrently through TNG. Each opened only its own SQLite store.
- The active profile is `hikari`, so its own
  `gateway.multiplex_profiles: true` setting is authoritative. Changing only
  the root profile configuration does not enable this systemd process.
- Plugin discovery is profile-local: link
  `<profile>/plugins/matrix-platform` to this project for every Matrix
  profile, and remove/disable duplicate legacy `platforms/matrix` links so
  they cannot override TNG's `matrix` registration.
- `lens`, `writer` (the active `@hikari-writer2` account), and `yan-cgo`
  each had a server/local key mismatch. TNG completed password-UIA repair,
  persisted the replacement token in that profile's `.env`, and verified the
  repaired server key. A subsequent restart connected all four profiles with
  no reauthentication or repair action.
- `scout` and `tool` have no Matrix identity and are explicitly disabled for
  Matrix (and tokenless Telegram) to avoid false adapter attempts.
- Initial full-state sync now dispatches only non-room events before returning
  from `connect()`. This retains queued E2EE to-device events while preventing
  historical room backlog from serially blocking secondary-profile startup.

## Known production issue

The existing `writer` and `yan-cgo` stores previously did not match the
server-side device keys. With a verified backup, they are suitable candidates
for a controlled test of automatic server-record repair; TNG does not delete
or rotate their local stores.

## Test accounts

Persistent disposable Tuwunel test-account credentials are stored outside this
repository in `/home/ubuntu/.config/hermes-matrix-tng/accounts.env` with mode
600. Reuse them; do not create accounts for every test.
