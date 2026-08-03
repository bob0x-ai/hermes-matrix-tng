# Handoff for deployment agent

Read `AGENTS.md`, `MIGRATION.md`, `docs/STATUS.md`, and `docs/ROLLOUT.md`.

Before deployment:

- run `pytest -q tests` with the Hermes checkout on `PYTHONPATH`;
- verify the TNG plugin is selected, not the old user override;
- use a temporary Hermes home/profile discovery root when piloting a subset;
- keep the old gateway units stopped so two processes never use one Matrix
  device concurrently;
- back up complete stores before any production start;
- fail closed on device-key mismatch; never delete a store as an automatic fix.

The persistent disposable-account file is outside the repository. Do not copy
it into Git or print its contents.
