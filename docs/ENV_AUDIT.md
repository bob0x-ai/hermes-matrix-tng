# Matrix Environment Read Audit

This is the Phase 2 audit of the bundled adapter at the Phase 0 installed
revision. Values that describe one Matrix account/profile must be snapshotted
at adapter construction; values must not be read from process-global
`os.environ` during later async work.

## Already covered by TNG settings

- homeserver, access token, password, user ID, device ID;
- E2EE mode/encryption compatibility;
- recovery key during connect;
- allowed users and rooms;
- free-response rooms and mention policy;
- threading/session scope and notice processing;
- reactions, proxy, media limit, approval settings;
- message length and text-batching settings;
- public-room and room-mention policy;
- crypto-store directory/database path.

## Remaining inherited or outer-boundary reads

- `MATRIX_RECOVERY_KEY_OUTPUT_FILE`: generated-key output is a deployment
  operation and must be made profile-local before automatic bootstrap is used.
- `MATRIX_MAX_MESSAGE_LENGTH`: construction-time fallback remains in the
  bundled superclass; TNG overwrites the resolved instance value afterward.
- plugin `check_matrix_requirements` and standalone sender reads: these run
  outside the long-lived adapter and need profile-aware wrappers before relying
  on them in multiplex mode.
- any future Matrix environment variable added upstream: compatibility tests
  must fail or the variable must be classified here.

## Rule

No Phase 2 gate passes while an inherited runtime method can use another
profile's value for authentication, authorization, E2EE, device state, store
path, or room creation policy. Construction-time compatibility reads are
acceptable only when immediately overwritten from the immutable settings
snapshot and covered by tests.
