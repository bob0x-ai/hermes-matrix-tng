# Matrix adapter incident alerts

TNG can report device-key recovery incidents from one dedicated Matrix identity
such as `@matrix-adapter:neurosovereign.quest`. This avoids relying on the
affected profile to be connected before an operator can learn about its state.

## One-time setup

1. Create the dedicated `@matrix-adapter` account and a long-lived access token
   for it. It is an operations notifier, not an Hermes agent profile.
2. Create (or retain) the unencrypted room alias
   `#alerts:<server-domain>`, and invite that account. TNG will not join or
   create rooms automatically.
3. Add the following to a mode-600 `EnvironmentFile` used by the single
   multiplexed gateway service. Do not put the token in this repository or a
   profile `config.yaml`.

   ```text
   HERMES_MATRIX_ADAPTER_ALERT_HOMESERVER=https://matrix.example.org
   HERMES_MATRIX_ADAPTER_ALERT_TOKEN=<redacted dedicated-account token>
   HERMES_MATRIX_ADAPTER_ALERT_USER_ID=@matrix-adapter:example.org
   ```

   `HERMES_MATRIX_ADAPTER_ALERT_ROOM=#alerts:example.org` is optional; without
   it TNG derives the alias from the notifier identity.

The `HERMES_MATRIX_ADAPTER_ALERT_*` values are deliberately process-global:
they describe one notifier shared by all profiles. TNG snapshots them while it
constructs each adapter, so long-lived async work never reads another
profile's environment.

## Delivery rules

- TNG resolves the `#alerts` alias and verifies the room has no
  `m.room.encryption` state before sending a plain `m.room.message`.
- It never joins, creates, or encrypts a room on its own.
- An unavailable alias, missing membership/token, an encrypted room, or a
  request failure falls back to a clear Hermes log line; it never blocks or
  changes profile recovery.
- The message contains the account/device, recovery status, redacted public-key
  fingerprints, result detail, and evidence-file location. It contains no
  access token, password, recovery key, raw crypto key, or database content.
