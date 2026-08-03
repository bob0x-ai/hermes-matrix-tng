# Disposable Matrix E2EE Integration

Phase 4 uses the existing Hermes disposable Continuwuity harness at
`/home/ubuntu/.hermes/hermes-agent/tests/e2e/matrix_xsign_bootstrap/` as the
starting point. It binds a dedicated local port (`26167`) and does not use the
production Tuwunel service or production crypto stores.

## Attempted on 2026-08-03

The compose command was attempted from the Phase 4 branch:

```text
docker compose ... up -d
```

It could not contact the Docker daemon because the current user lacks access to
`/var/run/docker.sock`:

```text
permission denied while trying to connect to the Docker daemon socket
```

No container was started, no production service was touched, and no privilege
escalation was attempted.

## Gate Result

The Docker permission issue was resolved with the user's explicit permission to
use passwordless `sudo` for protected Docker access. The disposable harness was
started on 2026-08-03 and then removed with `down -v`.

The TNG integration evidence was:

- two fresh Matrix accounts connected concurrently through two TNG adapters;
- each adapter used a distinct temporary profile home and crypto database;
- both adapters connected successfully and disconnected cleanly;
- fresh adapter instances reconnected successfully from the same stores;
- device IDs remained stable across the restart simulation;
- no production service, Tuwunel instance, profile home, or crypto store was
  accessed.

The homeserver emitted expected warnings because no recovery-key output file
was configured for the disposable accounts; this did not prevent connection or
store persistence. The test also emitted Hermes's profile-home fallback warning
in some inherited initialization paths. The explicit TNG store paths remained
correct, but that warning is retained as a Phase 5 hardening item.

Phase 4 passes for the disposable two-profile connect/reconnect gate. It does
not authorize a production pilot.

## Previously Blocked Gate

Before the user granted Docker access, the gate required either:

1. a maintenance-safe user-level Docker permission fix; or
2. another disposable Matrix runtime that does not use production Tuwunel.

Do not substitute the live homeserver for production rollout. The disposable
test used fresh accounts, fresh device IDs, fresh recovery state, and temporary
profile homes; no secrets were stored in the repository.
