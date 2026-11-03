---
id: B-066
title: 'Two server slips: MAX_PLAYERS and one QUIT'
status: To Do
assignee: []
created_date: '2026-11-03T16:02:00Z'
labels:
  - domain:rooms
  - domain:account
milestone: m-4
dependencies: []
documentation:
  - specs/lobby/rooms.md
  - specs/account/account.md
priority: medium
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-027 and DRAFT-028 (B-028's review). RoomState.players and Snapshot.players hold max_length=8 where MAX_PLAYERS is meant (src/nock/room.py:290, src/nock/protocol.py:739). SmtpMailer._send calls quit() inside 'with connection:', whose exit sends QUIT again (src/nock/mailer.py:99); smtplib swallows the error. Out of scope: the mailer's thread pool (DRAFT-030).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The player limit of a room's state and of a snapshot is MAX_PLAYERS, one constant
- [ ] #2 A mail send sends QUIT once
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
