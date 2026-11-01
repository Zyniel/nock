---
id: B-005
title: Grid progress on the account
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels:
  - domain:account
  - domain:library
dependencies: []
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (spec 004's decision 8, 2026-10-10: progress shows "on my
  device or account"; the human approved this brief with option A,
  2026-10-29, the spec change and AC-24's rewording, 2026-10-30; review
  approved in rounds 1 and 2)
- Domains: account/account (the route), content/library (rule 7, the merge)
- Architecture decision: yes (a new account route): options from the Plan
  agent on Fable; the human picked A
- Criteria: account AC-19, AC-20, AC-21 (new); library AC-22, AC-23, AC-24
  (new)
- Branch: feat/b-005-account-progress · PR: #66
- Problem: a grid's « Commencée » or « Terminée » comes only from this
  device's `nock.progress`; a signed-in player on another device sees none.
- In scope: a signed-in player's progress read from the account and merged
  with the device's on `/` and `/g/<n>`, per grid `finished` over `started`
  over none. Signed out, accounts off, or a failed request: the device's
  progress alone, the page ready either way. Options:
  - A (lead's pick): derived, nothing stored. `GET /api/account/progress`
    answers `{"<n>": "started" | "finished"}` like `nock.progress`:
    `finished` for each history record, and for each solved room still
    existing of the account's identities; `started` for the others and for
    its creator rooms still existing. 401 without session, 404 accounts off.
    Erasure and privacy unchanged. Lost: « Commencée » once an unsolved room
    expires (it can no longer be resumed); « Terminée » lasts as « Grilles
    terminées » does. About 3 criteria; no clash with B-036 or B-038.
  - B: a table `account_progress (account, grid, progress)` written by the
    client beside `nock.progress` (`PUT /api/account/progress`), read by the
    same `GET`. Keeps « Commencée » forever; erasure must delete it (clashes
    with B-036 on rule 18), and `account.md` would pass the size guidance, so
    a new domain file `account/progress.md` (a map change).
  - C: B's table written by the server (room creation, signed-in join,
    `grid_solved`). Counts rooms joined by link too, but changes the room
    engine and three more domains.
- Out of scope: guests' progress across devices; pushing a device's progress
  up to the account at sign-in; progress from a room joined by link before
  the account's identity was stored; splitting `account/account.md` (19.8 KB,
  a later item after B-036).
- Screens: none change: the catalogue's and `/g/<n>`'s pills as drawn today,
  shown from the device at once, then with the account's when it answers.
- Open questions: none (the human picked A).
<!-- SECTION:DESCRIPTION:END -->
