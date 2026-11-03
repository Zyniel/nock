---
id: B-074
title: Three account behaviours proven
status: To Do
assignee: []
created_date: '2026-11-03T16:02:00Z'
labels:
  - domain:account
milestone: m-5
dependencies:
  - B-066
documentation:
  - specs/account/account.md
priority: low
ordinal: 62000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-023. Untested behaviour the code has: a link token arriving in the URL fragment while /account already shows signs in; another method on an account route answers 405 while accounts are on, and 404 while they are off; a failed purge is logged and the sweep goes on. account.md is at its budget (20 criteria): widen existing criteria rather than add.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A link token in the fragment of an open /account signs in
- [ ] #2 A wrong method on an account route answers 405 with accounts on, 404 with them off
- [ ] #3 A failed purge is logged and the sweep goes on
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
