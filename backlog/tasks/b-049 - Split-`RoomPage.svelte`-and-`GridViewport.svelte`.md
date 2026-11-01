---
id: B-049
title: Split `RoomPage.svelte` and `GridViewport.svelte`
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
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
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
