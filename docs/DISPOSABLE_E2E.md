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

## Gate

Phase 4 is pending. It requires either:

1. a maintenance-safe user-level Docker permission fix; or
2. another disposable Matrix runtime that does not use production Tuwunel.

Do not substitute the live homeserver for this gate. Once available, run the
disposable test with fresh accounts, fresh device IDs, fresh recovery keys, and
temporary profile homes, then record cold-start, encrypted send/receive,
reconnect, and restart evidence without storing secrets.

