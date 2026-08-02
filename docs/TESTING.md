# Testing Strategy

## Testing Pyramid

### 1. Pure and mocked tests

These should cover most cases quickly and without production state:

- per-profile settings and path resolution;
- fail-closed secret behavior;
- differing policies for two profiles in one process;
- plugin registration and Hermes interface compatibility;
- routing and adapter selection;
- lifecycle ownership, failure, reconnect, and shutdown;
- recovery-key scope;
- local-plugin regressions.

### 2. Real local infrastructure tests

Use temporary profile homes and real SQLite/Mautrix store objects. Verify
independent connections, paths, cleanup, restart/reopen behavior, and absence
of cross-adapter database ownership. Do not use production databases.

### 3. Disposable Matrix E2EE tests

Use disposable accounts and rooms to prove real sync, Olm/Megolm operation,
cross-signing/recovery behavior, concurrent adapters, and cold restart.

### 4. Narrow production pilot

Mocks and disposable accounts cannot prove compatibility with existing device
identities and crypto stores. Pilot two lower-risk profiles after explicit
approval and verified backups, then soak before expanding.

## Required Negative Tests

- secondary recovery key missing while default has one;
- secondary allowed-user policy missing while default has one;
- two profiles with different device IDs and store paths;
- duplicate credential/account claim;
- one adapter failing or disconnecting while another remains healthy;
- wrong or absent store path detected before network connection;
- incompatible Hermes adapter API;
- SQLite lock or stopped-pool errors are surfaced, not endlessly retried.

## Test Hygiene

Tests must scrub the host Matrix environment or explicitly replace the secret
scope. A test expecting an unset Matrix variable must not inherit the VPS's
live `.env`. Never log secret values in assertion failures.

