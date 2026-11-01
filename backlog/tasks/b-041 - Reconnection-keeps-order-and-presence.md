---
id: B-041
title: Reconnection keeps order and presence
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T21:41:00Z'
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
- [x] #1 realtime AC-24 (new)
- [x] #2 server AC-29 (new)
- [x] #3 hints AC-24 (new)
- [x] #4 joining AC-22 (new)
- [x] #5 joining AC-23 (new)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
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

Tests: the kept select_cell counts as the first paced send after the snapshot (sent at once, the edits and kept requests then at the 100 ms pace); no test depends on it.

Implementation: requests queued behind a resend that a new loss interrupts are kept again for the next snapshot (the spec does not cover it; the other option dropped them). Requests already sent on a socket that then drops are not resent. The select_cell is sent only after a loss; the first snapshot restores the saved selection as before.

Pull request: https://github.com/Zyniel/nock/pull/86
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
After a reconnection the page keeps the order of the player's work and its presence: undo, check and reveal wait in their place among the resent edits, the selection goes again, a browser without storage rejoins, and the kept form's button is disabled while it cannot join.

- realtime AC-24: tests/test_realtime_reconnection_selection.py::test_ac24_bob_hears_anas_selection_before_her_offline_letter
- server AC-29: tests/test_server_offline_undo.py::test_ac29_an_offline_undo_reaches_the_server_in_its_place (offline after M, offline between A and M, 50 ms after the snapshot)
- hints AC-24: tests/test_hints_offline_requests.py::test_ac24_offline_edits_a_check_and_a_reveal_reach_the_server_in_order
- joining AC-22: tests/test_joining_reconnection.py::test_ac22_a_browser_that_refuses_storage_rejoins_as_ana_after_a_drop, ::test_ac22_an_identity_another_tab_stored_meanwhile_does_not_replace_anas
- joining AC-23: tests/test_joining_reconnection.py::test_ac23_a_kept_form_disables_its_submit_until_the_next_socket_opens
- Look: the kept join form with « Entrer dans le salon » disabled, drawn under the nickname screen of the screens sheet (specs/_design/pages.md).

Code: web/src/lib/RoomPage.svelte (one paced send queue; sendRequest for undo, check and reveal; the identity held in memory; the submit disabled unless nickname), web/src/lib/joinRules.ts (planAutomaticJoin takes the held identity first). tests/realtime_harness.py gains a proxy that drops and restores a page's socket. No protocol or server change.

Spec-checker: APPROVED in round 2 (round 1 asked for a criterion behind the other-tab case and found the selection's word check unobservable). Reviewer: APPROVE in round 1; the lead's full gate then found spec 007 AC-1 broken (a second snapshot on the same socket sent the selection again), fixed and APPROVE in round 2. Full gate: passed (8538 parallel, 160 serial).

Lead's decisions: open question 1, A (a check or reveal pressed before the snapshot after a loss is kept and sent after the resent edits); a request made between offline edits goes in the order made; the kept selection is sent again with no check against the snapshot's words (a room's grid never changes) and is the first paced send; the identity held in memory goes first even when another tab stored another; requests queued behind a resend that a new loss interrupts are kept again; the button is « Entrer dans le salon » (join.submit).

Flagged: the four specs are over the size guideline (splits in follow-up drafts); the re-keep path after a second loss has no test (follow-up draft); the quick gate of the task did not cover the board domain, where the full gate caught the regression.
<!-- SECTION:FINAL_SUMMARY:END -->
