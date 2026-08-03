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
- Local suite: 17 tests passing.
- Disposable Tuwunel test: two concurrent encrypted DM profiles connected,
  exchanged messages in both directions, and reconnected from the same stores.
- Optional operator notifications are documented in `ALERTING.md`. They use a
  dedicated token-only `@matrix-adapter` identity and an unencrypted `#alerts`
  room; no production notifier account has been created by this project.

## Deployment rules

1. Back up each complete Matrix store directory, including WAL/SHM files.
2. Never reuse a Matrix device ID with a different crypto store.
3. Deploy TNG alongside the existing plugin and start with a small profile set.
4. Verify device/store fingerprints before enabling sync.
5. Monitor SQLite locks, undecryptable events, device-key mismatches, and
   reconnect behavior before expanding the profile set.

## Known production issue

The existing `writer` and `yan-cgo` stores previously did not match the
server-side device keys. With a verified backup, they are suitable candidates
for a controlled test of automatic server-record repair; TNG does not delete
or rotate their local stores.

## Test accounts

Persistent disposable Tuwunel test-account credentials are stored outside this
repository in `/home/ubuntu/.config/hermes-matrix-tng/accounts.env` with mode
600. Reuse them; do not create accounts for every test.
