---
id: DRAFT-069
title: MAX_PLAYERS named where it lives
status: Draft
assignee: []
created_date: '2026-11-03T20:47:00Z'
labels:
  - follow-up
  - domain:rooms
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Robustness fixes » close. specs/lobby/rooms.md's Code section (about line 234) names MAX_PLAYERS under src/nock/room.py, but since B-066 it is defined in src/nock/protocol.py and room.py only imports it; the comment beside it still cites the archived « spec 012 AC-4 » rather than rooms rule 7. Name protocol.py for the constant and point the comment at lobby/rooms.md rule 7. A few lines, spec-writer and implementer.
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
