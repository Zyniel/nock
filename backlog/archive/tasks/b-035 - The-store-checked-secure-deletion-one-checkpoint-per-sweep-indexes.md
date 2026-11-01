---
id: B-035
title: 'The store: checked secure deletion, one checkpoint per sweep, indexes'
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:operations
  - domain:lifetime
  - domain:account
dependencies: []
ordinal: 45000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done
- Priority: seventh (privacy promise and sweep cost)
- Domains: admin/operations (no copy of a deleted room stays), lobby/lifetime
  (the sweep), account/account (the purge)
- Architecture decision: no (indexes in migration 3 and the order of the
  statements; no row changes)
- Criteria: operations AC-22 to AC-25 (new), lifetime AC-16, AC-17 (new),
  lifetime AC-13 (changed), account AC-22, AC-23 (new), host AC-9 (changed)
- Branch: feat/b-035-store-deletion · PR: #76
- Problem: each room deletion runs `PRAGMA wal_checkpoint(TRUNCATE)`
  (`store.py:347`) inside the store lock that the engine thread takes for
  each step, so a sweep of thousands of expired rooms stalls every room. The
  checkpoint's result is never read: one that gave up (busy, while the
  account store's connection to the same file is active) leaves the old pages
  in the log, although `admin/operations.md` says no byte of the room stays.
  The same holds for `erase_player`, `delete_account`,
  `erase_players_from_history` and `purge` (B-028 M7). Several queries scan
  their whole table: rooms by creation time and by creator, identities by
  room code, team-mates by code and player, links by address, sessions by
  account (L5).
- In scope: a sweep deletes its expired rooms, then checkpoints once; each
  checkpoint reads its `busy` column; the indexes, in migration 3.
- Out of scope: the size of snapshots (B-037).
- Screens: none.
- Open questions:
  1. A checkpoint that stays busy: A (lead's default) one retry, then a
     WARNING, and the next sweep empties the log; B the request fails.
- Decisions: the human, 2026-10-31: 1A, one retry, then a WARNING, and the
  next sweep empties the log. The spec change approved, with the lead's
  picks: a checkpoint try never waits on the busy handler; the account
  store makes its own indexes when it opens; two checkpoints per sweep
  with accounts on; `nock.store.checkpoint_wal` as the one checkpoint.
<!-- SECTION:DESCRIPTION:END -->
