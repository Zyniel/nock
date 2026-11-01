---
id: B-041
title: Reconnection keeps order and presence
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T19:39:00Z'
labels:
  - domain:hints
  - domain:joining
  - domain:realtime
  - domain:server
milestone: m-0
dependencies: []
documentation:
  - specs/gameplay/hints.md
  - specs/lobby/joining.md
  - specs/platform/realtime.md
  - specs/platform/server.md
priority: high
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: second of B-039's items (before the first public test: after a
  network drop an undo erases another letter for everyone, B-039 M1)
- Waits for: B-031's merge (done on its branch; it changes
  `gameplay/hints.md` and `platform/realtime.md` too)
- Domains: gameplay/hints (check and reveal wait for the resent edits),
  lobby/joining (rule 8: a page that has joined rejoins with the identity it
  holds; rule 9: the kept form's button), platform/realtime (rule 22: the kept
  selection sent again), platform/server (rule 9 already orders the undo; its
  reconnection case has no test)
- Architecture decision: no (the order of the page's sends; no message
  changes)
- Problem: after a reconnection only edits wait for the resend
  (`sendEdit`, `RoomPage.svelte:1718`; `resendPendingEdits`, `:1839`, one
  every 100 ms). Undo, check and reveal (`:868`, `:876`, `:934`) go at once,
  or are dropped while the socket is closed (`:552`): offline, the player
  types A, B, C; a Ctrl+Z 50 ms into the resend reaches the server before B
  and undoes A for everyone, against `platform/server.md` rule 9 (M1). A
  browser that refuses storage cannot rejoin after its first drop: the join
  plan reads the identity from `localStorage` only (`joinRules.ts:96`), so
  the band asks for a nickname and no form shows (M2). After a reconnection
  the others no longer see the player's cursor: the server cleared it at the
  disconnection (`room.py:1146`) and the page sends no unchanged selection
  (M3). « Rejoindre » on the kept form does nothing during the retry delay
  (`:633`, `:2011`; L11).
- In scope: one way to send a command after the pending edits (kept while
  not joined, queued behind a running resend, else sent), used by undo,
  check and reveal; the identity of the last snapshot kept in memory and
  used first by the join on open; the kept selection, checked against the
  new snapshot's words, sent before the resend; « Rejoindre » disabled
  unless the status is `nickname`.
- Out of scope: reactions and flags sent offline (B-047); moving the
  connection out of `RoomPage.svelte` (B-049).
- Screens: the kept join form while the page reconnects, « Rejoindre »
  disabled (a look that exists; drawn if the screens sheet draws that form).
- Open questions:
  1. A check or reveal pressed before the snapshot after a loss: A (lead's
     default) kept and sent after the resent edits, as the undo is; B
     refused, the buttons disabled until joined.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 realtime AC-24 (new)
- [ ] #2 server AC-29 (new)
- [ ] #3 hints AC-24 (new)
- [ ] #4 joining AC-22 (new)
- [ ] #5 joining AC-23 (new)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Specs: specs/gameplay/hints.md, specs/lobby/joining.md, specs/platform/realtime.md, specs/platform/server.md
Tests: tests/test_hints_*.py, tests/test_joining_*.py, tests/test_realtime_*.py, tests/test_server_*.py
Gate: uv run python scripts/gate.py --specs hints,joining,realtime,server --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decisions: B-031 is merged (PR #69), so nothing waits. Open question 1 takes A (a check or reveal pressed before the snapshot after a loss is kept and sent after the resent edits, as the undo is).

Lead's decisions in the spec change: an undo, check or reveal made between edits typed offline goes out in the order made (after the edits pending when it was made, before any later edit; server AC-29's second example). The kept selection is sent again with no check against the snapshot's words: a room's grid never changes, so the check is unobservable. The identity held in memory goes first even when another tab stored a different one (joining AC-22's second example). The button is « Entrer dans le salon » (join.submit), the task's « Rejoindre ». The kept join form with its button disabled is drawn as a specimen in the screens sheet. Follow-up drafts: split realtime.md (reconnection) and hints.md (votes).
<!-- SECTION:NOTES:END -->
