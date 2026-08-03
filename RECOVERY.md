# Device/store mismatch recovery

By default, TNG repairs a server/local key mismatch automatically. The local
crypto store is authoritative for its explicitly configured device ID. TNG
deletes the conflicting **server record for that same device ID**, uploads the
local device keys, then queries the server again. It starts only when that
post-repair check succeeds.

This is not silent. Every detection, repair step, and failure is appended to
`device-key-mismatches.jsonl` beside the affected profile's crypto store. It
contains timestamps and non-reversible key fingerprints, never raw keys.
Successful repairs report `recovery.status: server_device_repaired`.

Some homeservers, including Tuwunel, require password UIA before a device can
be removed. For a token-only profile, TNG reports
`server_repair_needs_uia` and leaves both stores untouched. Add that profile's
own Matrix password (`password` or `MATRIX_PASSWORD`) and retry; the adapter
will complete the challenge without exposing the password in logs or evidence.

Set `device_key_mismatch_policy: quarantine` (or
`MATRIX_DEVICE_KEY_MISMATCH_POLICY=quarantine`) to retain the old fail-closed,
manual-recovery behaviour for a profile.

If an automatic repair fails, preserve the store directory and its evidence
file. Restore a matching complete store backup where available; otherwise
explicitly create a new Matrix device and a new store. Recovery stays
profile-local, so unrelated profiles can continue to run.
