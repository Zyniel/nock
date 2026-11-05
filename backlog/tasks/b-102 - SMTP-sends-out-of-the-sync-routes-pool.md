---
id: B-102
title: SMTP sends out of the sync routes' pool
status: To Do
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-05T01:54:00Z'
labels:
  - domain:account
milestone: m-10
dependencies: []
documentation:
  - specs/account/account.md
priority: low
ordinal: 90000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-030: a slow mail server and many addresses could fill the 40 threads of every sync route. Runs after B-038 and the account split.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A slow SMTP server leaves the other sync routes answering, with a test
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
