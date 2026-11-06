---
id: DRAFT-094
title: « Mes salons » after a sign-out keeps rooms created signed in
status: Draft
assignee: []
created_date: '2026-11-06T16:20:00Z'
labels:
  - follow-up
  - domain:my-account
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-104's spec check: a room created on the device with « Jouer » while signed in is a seat the device took itself (B-040), not in nock.account_rooms, so after a sign-out its identity, its nock.history record and its « Mes salons » row stay, and « Grilles terminées » still lists it. Part of the same shared-device problem; a change players notice, so a milestone's.
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
