---
id: B-049
title: Split `RoomPage.svelte` and `GridViewport.svelte`
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T16:55:00Z'
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
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
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
<!-- SECTION:NOTES:END -->
