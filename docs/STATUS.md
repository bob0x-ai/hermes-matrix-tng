# Project Status

## Current Phase

Phase 2 — Profile Isolation Implementation: in progress.

Phase 0 baseline/inventory is complete for non-destructive capture; checksum
capture remains explicitly deferred until a safe backup window.

## Completed

- Project documentation scaffold created.
- Phased implementation, testing, pilot, rollout, and maintenance gates
  documented.
- Architectural direction fixed: one ordinary Matrix adapter per Hermes
  profile under the existing gateway multiplexer.
- Installed Hermes revision: `bc747001eec58150aba08e586ff1e7a25fc532aa`
  (`2026-07-29`, lazy-load heavy SDKs commit).
- Upstream `origin/main`: `024f3e044bfd89ee226afc604fffafc1c2005f7ec`
  (`2026-08-02`, approval-cache documentation commit). The checkout is behind
  upstream; no update was pulled.
- Current production override: `/home/ubuntu/projects/hermes-matrix-user-plugin`,
  commit `8b2f41c9f3a359b40c91e96a09de19e6594c812f`.
- The current production override has user-owned uncommitted changes in
  `AGENTS.md` and `adapter.py`; it was not modified.
- Six gateway units were active during capture: default, hikari, lens, scout,
  writer, and yan-cgo.
- Cgroup memory baseline: `2,185,441,280` bytes (`2.035 GiB`) summed across
  those six units. Main gateway process RSS baseline: `1,442,524 KiB` (`1,408.7
  MiB`) summed across their main processes.
- Matrix store paths and metadata were recorded below. Existing per-profile
  stores must not be merged or recreated.
- The upstream Matrix adapter has two import-time store globals and 23 direct
  Matrix/Hermes environment reads requiring review for multiplex isolation.

## Non-Secret Inventory

### Profile configuration

| Profile | Matrix YAML state | Matrix `.env` key families present |
|---|---|---|
| default | `enabled: false` | access, policy, E2EE, device, homeserver, user/password, recovery, session/thread, home-room |
| hikari | no explicit Matrix block; environment enables configuration | same families as default |
| lens | `enabled: true`, `home_channel` | access, E2EE, device, homeserver, user/password, recovery, session, home-room |
| scout | no Matrix keys | none |
| tool | no Matrix keys | none |
| writer | `enabled: true` | access, policy, E2EE, device, homeserver, user/password, recovery, session/thread |
| yan-cgo | no explicit Matrix block; environment enables configuration | access, policy, E2EE, device, homeserver, user/password, recovery, session/thread, home-room |

The YAML/environment distinction matters: the effective platform set is not
determined by YAML `enabled` alone.

### Matrix store paths

| Profile/home | Main DB | Main DB mode | Live WAL/SHM | Checksum |
|---|---:|---:|---|---|
| default (`~/.hermes`) | 3,878,912 bytes | 0644 | not present at capture | deferred |
| hikari | 3,907,584 bytes | 0644 | WAL 1,491,472; SHM 32,768 | deferred |
| lens | 491,520 bytes | 0600 | WAL 894,072; SHM 32,768 | deferred |
| writer | 151,552 bytes | 0644 | WAL 65,952; SHM 32,768 | deferred |
| yan-cgo | 339,968 bytes | 0644 | WAL 177,192; SHM 32,768 | deferred |

Existing timestamped backups were observed under the default and hikari store
directories, including pre-pickle, pre-session-migration, and stale-device-key
backups. Their contents were not read.

Checksums are deferred because several live stores had WAL/SHM files. A future
safe backup window must copy the complete store directory before hashes are
recorded.

## Current Override Delta (high level)

The current user plugin is a full adapter override, not a small patch. Its
local changes relative to its older upstream base include:

- missing `m.room.create` state backfill after initial sync and room joins;
- profile-local recovery-key read and atomic persistence to the active `.env`;
- password-UIA cross-signing bootstrap for the local Tuwunel deployment;
- sync-handler draining before crypto database shutdown;
- standalone sender event-loop/wait-for lifecycle fixes;
- local message-length, voice, and choice-picker behavior differences;
- current user-owned edits not yet committed.

The plugin `adapter.py` hash is
`89331dfbea5b2c67e9d72831d3d24f19ad47b8fd581898fee7417407b53fc7a6`; the
installed bundled adapter hash is
`95413482441f083449440e4c73c35482c8229f91819e49671720d6de3609957d`.
The exact upstream base for TNG must be selected before copying code.

## Phase 1 Progress

- Added `plugin.yaml`, `__init__.py`, and a compatibility `adapter.py` bridge.
- Added `tests/test_plugin_contract.py`; it imports the bridge without installing
  or enabling the plugin and verifies the registration/factory surface matches
  the bundled adapter.
- Added `docs/UPSTREAM.md` with the revision and rebase procedure.
- No Hermes core files, production plugin files, services, configuration, or
  Matrix stores were changed.

## Phase 0 Gate

Passed for non-destructive inventory and baseline capture. Deferred items are
explicitly tracked rather than treated as complete:

- safe, complete crypto-store backup and checksums;
- exact upstream commit/base for the TNG skeleton;
- line-level classification of all upstream environment reads;
- clean separation of production override changes from user-owned edits.

## Phase 1 Gate

Passed for the non-deployed skeleton. The compatibility test ran in the Hermes
virtual environment with `2 passed`; the bridge's registration, adapter, and
requirements-check surface matches the bundled adapter. The bridge remains
deliberately uninstalled and disabled in production.

The exact Phase 2 implementation base still needs a deliberate selection. The
Phase 1 bridge records the installed checkout revision only as its compatibility
point; it does not claim that the final TNG adapter has been rebased.

## Phase 2 Progress

- Added `profile_isolation.py` with an immutable per-profile settings snapshot.
- Replaced the pure delegation bridge with a `MatrixAdapter` subclass that
  snapshots profile-owned store and crypto paths at construction.
- Added profile-scoped settings for credentials, E2EE, policy, threading,
  proxy, media, approvals, and batching.
- Added lifecycle serialization around legacy bundled methods that still read
  module-level store globals; paths are restored after each operation.
- Added diagnostics path correction and profile-local public-room handling.
- Focused tests currently pass: `6 passed`.

This is not yet the Phase 2 gate: raw environment reads in inherited runtime
methods and concurrent lifecycle behavior still need explicit coverage and
further reduction before merging this phase.

## Next Actions

1. Choose and record the exact upstream adapter base for the Phase 2
   implementation.
2. Perform the safe store backup/checksum step during an approved maintenance
   window.
3. Classify upstream environment reads into scoped secrets versus behavior
   settings.
4. Complete the inherited-method environment audit and concurrency tests for
   Phase 2.

## Deployment State

TNG is not implemented, installed, enabled, or deployed. The current production
Matrix override remains `/home/ubuntu/projects/hermes-matrix-user-plugin`.
