---
id: DRAFT-027
title: '`MAX_PLAYERS` in place of `max_length=8`'
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
B-028: `RoomState.players` and `Snapshot.players` hold `max_length=8` where `MAX_PLAYERS` is meant (`room.py:277`, `protocol.py:739`).
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
