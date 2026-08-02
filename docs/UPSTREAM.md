# Upstream Tracking

Phase 1 records the upstream compatibility point without copying or installing
the adapter:

- Installed Hermes checkout at Phase 0: `bc747001eec58150aba08e586ff1e7a25fc532aa`.
- Available `origin/main` at Phase 0: `024f3e044bfd89ee226afc604fffafc1c2005f7ec`.
- TNG Phase 1 bridge marker: `UPSTREAM_BASE_COMMIT` in `adapter.py`.

The bridge delegates to the installed bundled adapter so this phase has no
runtime behavior change. Before Phase 2, choose one exact upstream adapter
revision and record it here and in `adapter.py`. Do not use a moving branch or
copy an adapter whose base cannot be identified.

## Rebase Procedure

1. Fetch/read the intended upstream revision without changing production.
2. Diff the bundled Matrix adapter and the current production override against
   that revision.
3. Classify each local change as required for TNG, upstream-worthy, obsolete,
   or intentionally local.
4. Port only the required changes into the TNG implementation.
5. Run the Phase 1 compatibility tests and the Phase 2/3 isolation tests.
6. Update this document and `docs/STATUS.md` with the new base revision.

Do not enable or install the plugin as part of this procedure.

