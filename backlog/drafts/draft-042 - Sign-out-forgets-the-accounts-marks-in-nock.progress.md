---
id: DRAFT-042
title: Sign-out forgets the account's marks in nock.progress
status: Draft
assignee: []
created_date: '2026-11-01T20:21:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
B-040 makes a sign-out or deletion forget the identities, room records and history records the account brought to the device. nock.progress, the device's record of started and finished grids, keeps the marks those rooms set, so the next person on a shared device sees the account's grids marked in the catalogue. Out of B-040's scope (the task named identities, nock.room.* and nock.history only). Forgetting them needs the device to know which marks came from the account's rooms. A change players can notice: it needs a milestone.
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
