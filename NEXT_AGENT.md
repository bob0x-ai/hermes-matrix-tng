# Handoff for deployment agent

Read `AGENTS.md`, `MIGRATION.md`, `docs/STATUS.md`, and `docs/ROLLOUT.md`.

Before deployment:

- run `pytest -q tests` with the Hermes checkout on `PYTHONPATH`;
- verify the TNG plugin is selected, not the old user override;
- use a temporary Hermes home/profile discovery root when piloting a subset;
- keep the old gateway units stopped so two processes never use one Matrix
  device concurrently;
- back up complete stores before any production start;
- TNG never deletes a local crypto store. By default it repairs a conflicting
  server record for the same configured device ID, then re-queries it before
  starting. Tuwunel requires password UIA for that delete: ensure every pilot
  profile has its own `MATRIX_PASSWORD`, or expect the explicit
  `server_repair_needs_uia` status.
- Read `RECOVERY.md` and `ALERTING.md`. Provision the optional dedicated
  `@matrix-adapter` notifier and explicitly configured unencrypted alert room
  only on the target homeserver; do not copy notifier credentials into this
  repository.

For the single-process systemd deployment, check the *active profile's*
`gateway.multiplex_profiles` value (not only the root config). Install the TNG
`matrix-platform` link in each Matrix profile's `plugins/` directory and make
sure no legacy nested `platforms/matrix` link remains discoverable. Profiles
without a Matrix identity must explicitly set `platforms.matrix.enabled: false`
so inherited/plugin discovery cannot create a useless adapter.

The persistent disposable-account file is outside the repository. Do not copy
it into Git or print its contents.
