---
id: DRAFT-023
title: Tests for three account behaviours the code has
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:account
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Untested account behaviour the code has: a link token arriving in the URL fragment while `/account` already shows signs in; another method on an account route answers 405 while accounts are on, and 404 while they are off for a method no route has; a failed purge is logged and the sweep goes on (`account/account.md`).
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
