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
