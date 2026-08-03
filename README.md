# Hermes Matrix TNG

An update-tolerant Hermes user plugin project for safely running multiple
profile-owned Matrix adapters in one multiplexed gateway process.

Phase 1 now contains a non-deployed compatibility bridge. It delegates to the
installed bundled adapter and intentionally makes no runtime changes. The
profile-isolated implementation begins in Phase 2.

Start with [AGENTS.md](AGENTS.md). Supporting documents:

- [Architecture](docs/ARCHITECTURE.md)
- [Testing strategy](docs/TESTING.md)
- [Rollout and rollback](docs/ROLLOUT.md)
- [Current status](docs/STATUS.md)
- [Upstream tracking](docs/UPSTREAM.md)

The current production override remains in
`/home/ubuntu/projects/hermes-matrix-user-plugin` and must not be replaced until
the TNG test and pilot gates have passed.

## Optional Matrix operator alerts

TNG can send redacted Matrix recovery incidents through a dedicated notifier
account. Provision that account, its access token, and an **unencrypted** alert
room outside the plugin. Then configure the shared/default Hermes
`config.yaml`:

```yaml
platforms:
  matrix:
    alerts: true
    alerts_homeserver: https://matrix.example.org
    alerts_user_id: "@matrix-adapter:example.org"
    alerts_room: "#operator-alerts:example.org"
```

Provide the matching token only through the gateway's protected environment:
`HERMES_MATRIX_ADAPTER_ALERT_TOKEN`. With `alerts: false` (the default), TNG
only writes the incident to Hermes logs. See [ALERTING.md](ALERTING.md) for the
complete provisioning and delivery contract.
