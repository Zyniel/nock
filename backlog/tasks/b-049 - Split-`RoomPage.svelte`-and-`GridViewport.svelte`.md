---
id: B-049
title: Split `RoomPage.svelte` and `GridViewport.svelte`
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-03T03:31:00Z'
labels: []
milestone: m-1
dependencies:
  - B-041
  - B-045
  - B-048
priority: low
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: last of B-039's items (maintainability; no player sees it)
- Waits for: B-041 and B-045 (their tests pin the behaviour the split
  keeps), and B-048 if the human takes it; best after B-042 to B-047, which
  change the same files
- Domains: none (no behaviour change: `web/src/lib/` only)
- Architecture decision: yes (new modules of the client and their public
  names): the Plan agent checks the report's split on Fable
- Criteria: none new; every existing test proves nothing changed
- Problem: `RoomPage.svelte` holds 2,720 lines and five concerns: the
  transport, the game commands, the view state, the layout arithmetic and
  the device storage. `session` has two writers, and the connection code,
  where M1, M2, M3, L1, L2, L6 and L11 come from, is reachable only by a
  browser test (B-039 M11). `GridViewport.svelte` mixes gestures, key
  mapping, legend arithmetic, announcements and cell drawing in 1,321 lines.
  The one-overlay rule is applied by hand in eight places, the expiry timers
  are three copies, and the play state machine and the WebKit link
  workaround are repeated (L24); some leftovers and comments are wrong
  (L25).
- In scope: the nine steps of the report's « Structure », one commit each,
  every `data-testid`, id and the document order of `client/hud.md` rule 3
  kept, no wrapper element added: `roomConnection.ts` (an injected socket
  factory and clock, the only writer of `session.status`),
  `expiry.svelte.ts`, `VoteBanner`, `GridStatus`, `EntryPage`, `NoteSlot`,
  `roomOverlays.svelte.ts`, `playFit.svelte.ts` (last, on Opus: pixels),
  optionally `roomCommands.ts`; for the grid `LetterCell`, `ClueCell`, a
  `use:pinchPan` action, `gridKeys.ts` and `legendLayout.ts`; the duplicates
  of L24 and the leftovers of L25.
- Out of scope: any change a player or a test can see.
- Screens: none.
- Open questions:
  1. The props drilled through `Salon` (22) and `RoomTopBar` (26): A (lead's
     default) grouped into a few objects here; B left as they are.
<!-- SECTION:DESCRIPTION:END -->

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
1. No spec change (no behaviour change); the Plan agent (Fable, high) checks the report's split (claude_docs/frontend-review.md « Structure ») against today's code.
2. Tests: node:test unit tests (tests/web/) pinning the pure modules the split extracts (roomConnection with an injected socket factory and clock, expiry, gridKeys, legendLayout), by the test-writer, before the moves; the browser tests prove nothing changed.
3. Implementation in the report's steps, one commit each; gate: uv run python scripts/gate.py (full, RoomPage and GridViewport serve 17 and 9 domains).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): started after B-047 (#109) merged: B-042 to B-047 changed the same files. B-048 (node:test) and B-055 (the quick gate of a shared component) are merged, as the human's order asked. Open question 1, the props drilled through Salon and RoomTopBar: A, grouped into a few objects (the lead's default). RoomPage.svelte is 3,073 lines and GridViewport.svelte 1,490 today (the report said 2,720 and 1,321). Base: origin/main b9871e7.

Lead: the Plan agent (Fable, high) checked the report's split against today's code; plan taken as written: 14 steps, one commit each, risk rising (1 L25 leftovers; 2 roomCommands.ts; 3 gridKeys.ts, legendLayout.ts, pinch math; 4 expiry.ts; 5 roomConnection.ts with injected deps read at call time — openSocket, now, random, isHidden — the only writer of session.status but the parser; 6 roomOverlays.ts reducer; 7 GridStatus; 8 EntryPage; 9 VoteBanner, always mounted with its live region; 10 NoteSlot; 11 LetterCell, ClueCell, use:pinchPan; 12 the props of Salon and RoomTopBar grouped as $derived objects (question 1, A); 13 playFit.ts on Opus; 14 the specs' Code sections and B-055's map, last). Decisions: pure .ts modules with the $state kept in RoomPage rather than .svelte.ts rune modules (Node-testable, no change of effect ordering); roomCommands.ts mandatory and before roomConnection.ts; the connection exposes onOnline()/onVisible() rather than owning DOM listeners. Step 14 changes the Code sections of about 20 domain specs: it waits until B-063 and B-064 (in progress, many of those domains) merge. Node unit tests (tests/web/) pin roomConnection, roomCommands, expiry, roomOverlays, gridKeys, legendLayout, playFit and reconnectDelay before the moves; the components are covered by the browser tests. Full gate after steps 5, 11 and 13; three engines at the end.

Lead: tests 239 in tests/web/ (one per module plus roomConnectionHarness.ts), checked by the test-writer against a scratch copy of today's logic (all pass) and against deliberate breakages (each fails). Interface decisions: the connection takes a joinPlan() hook (identity, nickname) instead of heldIdentity/defaultNickname, so it needs no room code; gridKeyAction returns { kind: 'modifier' } for a modifier key alone (keeps the Escape release), distinct from 'none' (clears it); announcementOf lives in gridKeys.ts; onEnded only when the room is gone (4404); join(nickname) sets joining and sends, the status guard and nicknameRefused reset stay in RoomPage; resent edits keep the base_seq stored when typed; a join plan with both an identity and a nickname uses the identity (as planAutomaticJoin).

Lead: steps 1 to 4 done by the implementer (Sonnet) in one run and committed in two (the room page's L25 leftovers ride with steps 2 to 4, being in the same file); its chromium gate passed 8361 + 162, all Node tests of the built modules pass; the tests of roomConnection, roomOverlays and playFit wait for steps 5, 6 and 13.

Lead: review round 1 CHANGES REQUESTED (L24's play state machine, WebKit link workaround and window-width tracking still copied; L25's layer comment still wrong; hud's Code section named GridStatus for the status region; suggestions), fixed in ee47d3a, 27be639, f381525, ba772d2 (implementer, Opus), f8cabf4 (spec-writer), bc9ca01 (test-writer: scrollAfterZoom); round 2 APPROVE, its suggestions in DRAFT-059 (board PR #112). Commit 4ff2ad5 (step 1) does not build alone (ClueBar imports a constant step 2 adds); the branch was pushed, so it stays: only bisecting is affected. Gates: Chromium full gate green (8704 parallel, 162 serial); the three-engine gate was cut twice by container restarts, so the engines ran one by one: Firefox 4054 passed, 1 failed (test_server_offline_undo.py ac29 [firefox-50 ms], the load flake of DRAFT-053, passed 3/3 alone); WebKit GATE PASSED (4055 + 72).

Pull request: https://github.com/Zyniel/nock/pull/113
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
RoomPage.svelte (3,073 → 2,195 lines) and GridViewport.svelte (1,490 → 730) split along the B-039 review's « Structure », checked by the Plan agent (Fable). No behaviour change: every browser test unchanged and passing; no new criterion.
New pure modules, unit-tested in Node (tests/web/, 242 tests): roomCommands.ts (messages), roomConnection.ts (socket, join, heartbeat and silence by the clock, connect limit, jittered retries, resend, final closes; injected socket, clock, random and visibility; the only writer of session.status besides the parser), expiry.ts (one tracker for the three timer copies), roomOverlays.ts (the one-overlay rule, once), playFit.ts (layout arithmetic), gridKeys.ts, legendLayout.ts, gridLayout's scrollAfterZoom.
New components, root element unchanged, no wrapper: GridStatus, EntryPage, VoteBanner (always mounted with its live region), NoteSlot, LetterCell, ClueCell, use:pinchPan; PlayButton, FocusableLink, wideWindow.ts (L24's duplicates); Salon and RoomTopBar props grouped. L25 leftovers fixed.
Specs: the Code sections name the new files (step 14; spec-checker APPROVED round 2); B-055's map gains LetterCell and ClueCell.
Criteria: none (no behaviour change). Reviewer: CHANGES REQUESTED round 1 (L24 partly done, a comment, a Code attribution), APPROVE round 2.
Decisions: pure .ts modules with the state kept in RoomPage (not rune modules); roomCommands before roomConnection; a joinPlan() hook; gridKeyAction's 'modifier'; props grouped (question 1, A); steps 1–4 in two commits, the rest one each.
Gates: Chromium full green (8704 + 162); Firefox 4054 passed + 1 known load flake that passes alone; WebKit green (4055 + 72).
<!-- SECTION:FINAL_SUMMARY:END -->
