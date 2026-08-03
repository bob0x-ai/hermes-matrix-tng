# Matrix adapter incident alerts

TNG can report device-key recovery incidents from one dedicated Matrix identity
such as `@matrix-adapter:neurosovereign.quest`. This avoids relying on the
affected profile to be connected before an operator can learn about its state.

## One-time setup

1. Create the dedicated `@matrix-adapter` account and a long-lived access token
   for it. It is an operations notifier, not an Hermes agent profile.
2. Create (or retain) the unencrypted room alias
   `#operator-alerts:<server-domain>`, and invite that account. TNG will not join or
   create rooms automatically.
3. Configure the notifier in the process/default Hermes `config.yaml`. This is
   deliberately one shared setting, not a setting copied into every Matrix
   profile. `alerts` defaults to `false`; all fields below are required when it
   is true.

   ```yaml
   platforms:
     matrix:
       alerts: true
       alerts_homeserver: https://matrix.example.org
       alerts_user_id: "@matrix-adapter:example.org"
       alerts_room: "#operator-alerts:example.org"
   ```

   The same keys may be placed under `platforms.matrix.extra` if that is how an
   operator manages plugin-specific options.
4. Add the notifier token to a mode-600 `EnvironmentFile` used by the single
   multiplexed gateway service. Do not put the token in this repository or a
   `config.yaml`.

   ```text
   HERMES_MATRIX_ADAPTER_ALERT_TOKEN=<redacted dedicated-account token>
   ```

TNG reads the non-secret options from the process/default config and snapshots
them for every Matrix adapter. The token is the only process-level secret. A
secondary profile cannot override or borrow another profile's Matrix identity.

## Delivery rules

- TNG resolves the explicitly configured alias and verifies the room has no
  `m.room.encryption` state before sending a plain `m.room.message`.
- It never joins, creates, or encrypts a room on its own.
- An unavailable alias, missing membership/token, an encrypted room, or a
  request failure falls back to a clear Hermes log line; it never blocks or
  changes profile recovery.
- The message contains the account/device, recovery status, redacted public-key
  fingerprints, result detail, and evidence-file location. It contains no
  access token, password, recovery key, raw crypto key, or database content.
