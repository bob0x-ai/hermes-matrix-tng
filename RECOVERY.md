# Device/store mismatch recovery

TNG never deletes a Matrix device or crypto store automatically.

When `get_diagnostics()` reports `recovery.status: device_key_mismatch`:

1. Stop only the affected gateway/profile if necessary.
2. Preserve the complete store directory and the adjacent
   `device-key-mismatches.jsonl` evidence file.
3. Compare the evidence fingerprints with timestamped backups.
4. Restore a matching complete backup when one exists.
5. If no matching backup exists, explicitly approve a new Matrix device and
   new crypto store. Archive the old store; do not overwrite it.
6. Record the new device ID and store path, then verify encrypted traffic.

Recovery is profile-local. Other profiles should remain eligible to run.
