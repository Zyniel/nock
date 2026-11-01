---
id: DRAFT-044
title: B-041 small follow-ups
status: Draft
assignee: []
created_date: '2026-11-01T21:00:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reviewer suggestions of B-041 not taken in the task:
- Two lead's decisions have no test: a request still queued behind a resend when a new loss interrupts it is kept again for the next snapshot (stopSendQueue in RoomPage.svelte), and a request already sent on a socket that then drops is not resent. The re-keep path is the most delicate code of the change; a criterion in platform/realtime.md and its test would guard it.
- AC-23 checks that « Entrer dans le salon » is disabled, not that Enter does nothing during the retry delay (HTML blocks implicit submission by a disabled default button; not verified in a browser).
- TAMIS_KEY = "0,0,0" is defined in three test files that already share tests/realtime_harness.py.
- docs/design/screens_sheet/build.py breaks the mini card's inline style string in the middle of words (two blocks, lines about 479 and 501); a small named helper would serve both.
Upkeep-sized except the first, which adds a criterion.
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
