# Hermes Matrix TNG migration notes

## Current state

- TNG is implemented on branch `phase-5-controlled-pilot`.
- The adapter vendors Hermes Matrix adapter commit
  `bc747001eec58150aba08e586ff1e7a25fc532aa`.
- Runtime crypto-store paths are instance-owned; the inherited module-global
  path collision has been removed.
- Automatic server-device deletion on key mismatch is disabled. TNG records a
  non-secret `device-key-mismatches.jsonl` evidence file beside the store and
  requires explicit operator recovery.
- Local suite: 10 tests passing.
- Disposable Tuwunel test: two concurrent encrypted DM profiles connected,
  exchanged messages in both directions, and reconnected from the same stores.

## Deployment rules

1. Back up each complete Matrix store directory, including WAL/SHM files.
2. Never reuse a Matrix device ID with a different crypto store.
3. Deploy TNG alongside the existing plugin and start with a small profile set.
4. Verify device/store fingerprints before enabling sync.
5. Monitor SQLite locks, undecryptable events, device-key mismatches, and
   reconnect behavior before expanding the profile set.

## Known production issue

The existing `writer` and `yan-cgo` stores do not match the server-side device
keys. Do not delete or rotate those stores automatically. Treat recovery as a
separate explicit device/store migration.

## Test accounts

Persistent disposable Tuwunel test-account credentials are stored outside this
repository in `/home/ubuntu/.config/hermes-matrix-tng/accounts.env` with mode
600. Reuse them; do not create accounts for every test.
