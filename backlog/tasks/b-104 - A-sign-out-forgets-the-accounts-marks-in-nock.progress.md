---
id: B-104
title: A sign-out forgets the account's marks in nock.progress
status: To Do
assignee: []
created_date: '2026-11-05T01:54:00Z'
labels:
  - domain:account
milestone: m-10
dependencies: []
documentation:
  - specs/account/account.md
priority: medium
ordinal: 92000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-042. B-040 makes a sign-out or deletion forget the identities, room records and history records the account brought to the device; nock.progress keeps the marks those rooms set, so the next person on a shared device sees the account's grids marked in the catalogue. The device must know which marks came from the account's rooms. Runs after the account split (B-084). Out of scope: marks set while signed out.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 After a sign-out or a deletion, the catalogue shows none of the account's grids as started or finished, and the marks set while signed out stay
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
