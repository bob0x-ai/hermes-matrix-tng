# Lens Matrix E2EE instability — 2026-08-05

## Impact

Messages from `@lens:neurosovereign.quest` were intermittently readable and then appeared as “Unable to decrypt.” After repair attempts, Lens temporarily could not decrypt newly received messages in any encrypted room.

## Confirmed evidence

- The multiplex gateway used independent SQLite crypto stores for each Matrix profile.
- Mautrix encrypted to-device handling crashed after restart because `mau.crypto` was a standard Python logger without Mautrix's non-standard `trace()` method.
- Lens later received room events but logged missing Megolm sessions.
- The decisive account-wide failure was `olm event doesn't contain ciphertext for this device`: inbound Olm ciphertext had been produced for a Curve25519 identity other than Lens's current local identity.
- Lens's local and current server Ed25519 and Curve25519 keys ultimately matched, and its complete server device record had a valid self-signature. Earlier `Invalid signature from ...` warnings came from Mautrix's cross-signing-key validation path, not the device self-signature check.
- Deleting Lens's server device invalidated its access token. The adapter then retried `M_UNKNOWN_TOKEN` indefinitely instead of initiating profile-local reauthentication.

## Root causes and contributing defects

1. The adapter passed a logger lacking `trace()` into Mautrix, aborting encrypted to-device event processing.
2. Device health checks compared only Ed25519 signing keys. They did not validate Curve25519 encryption-key equality or the complete device record's self-signature.
3. A remote sender retained a stale cached Lens Curve25519 key. Restarting Lens alone could not invalidate that cache.
4. The sync loop treated `M_UNKNOWN_TOKEN` as a generic retryable error.
5. Multiplex gateway shutdown could be delayed for several minutes by an active Lens research job.

## Repair

- Added a Mautrix-compatible logger providing `trace()` and `silly()`.
- Added complete device self-signature verification.
- Added local/server Ed25519 and Curve25519 binding checks.
- Added regression coverage for matching Ed25519 with mismatched Curve25519.
- Republished Lens's same server device identity while preserving its local crypto store.
- Reauthenticated the same configured device ID and atomically persisted the replacement token.
- Verified the republished server record, self-signature, and Curve25519 equality.
- Confirmed a newly encrypted message worked after the device-list update.

## Commits

- `0febaef` — stabilize multiplexed Matrix delivery and crypto logging
- `daee4cc` — verify Matrix device self-signatures
- `48f7d1b` — bind Matrix device encryption keys to local stores

## Lessons

- Treat `user ID + device ID + token + store + Ed25519 + Curve25519 + signed record` as one invariant.
- Trace warnings to their precise call sites before inferring what signature failed.
- “Readable, then undecryptable” commonly means an old Megolm session was cached and a newly created session exposed a key-distribution defect.
- “Service active” and “crypto DB open” are not recovery proof. Require fresh inbound and outbound encrypted-message tests.
- Commit and test adapter changes before production mutation, preserve the local crypto store, and keep rollback artifacts.
- State uncertainty explicitly; do not present intermediate hypotheses as confirmed root causes.

## Remaining work

- Make `M_UNKNOWN_TOKEN` trigger controlled profile-local reauthentication/reconnect rather than infinite retry.
- Add contextual logging that distinguishes device self-signatures from cross-signing signatures.
- Add a repeatable production smoke test for fresh inbound/outbound Megolm sessions after reconnect.
- Prevent active agent turns from holding multiplex gateway shutdown until the systemd timeout.
