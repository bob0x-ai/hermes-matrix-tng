# Rollout and Rollback

No production rollout is authorized merely by this document. Obtain explicit
user approval at Phase 5.

## Preflight

- focused and integration tests are green;
- exact Hermes/upstream compatibility is recorded;
- selected profiles and current gateway units are identified;
- complete Matrix store backups are verified;
- expected store paths and device IDs are recorded without secret material;
- old unit definitions and current production plugin remain available;
- monitoring queries and rollback commands are prepared.

## Pilot

Consolidate two lower-risk profiles only. Stop their old gateways cleanly,
verify TNG resolves their original stores before connecting, start the
multiplexed gateway, test new encrypted traffic both ways, restart once, and
soak for 24–48 hours.

Monitor at least:

- process and cgroup memory;
- adapter connection/reconnect state;
- sync latency;
- new-event decryption failures;
- key-MAC or device-key verification failures;
- unexpected recovery/cross-signing generation;
- SQLite lock latency and stopped-pool errors;
- wrong-profile responses or authorization behavior.

## Immediate Rollback

Stop the multiplexed pilot before starting the old per-profile gateways. Do
not allow two processes to sync the same Matrix credential simultaneously.
Restore configuration/plugin selection as documented at deployment time and
restart the old gateways against their unchanged original stores.

Never attempt to repair a failed pilot by deleting a store or rotating a
device. Preserve evidence and diagnose offline.

## Expansion

Add one profile at a time only after the pilot gate passes. Repeat identity,
message, restart, and observation checks for each profile. Keep old services
recoverable until the consolidated deployment has completed its final soak.

