---
id: DRAFT-093
title: The deletion e-mail out of the sync routes' pool
status: Draft
assignee: []
created_date: '2026-11-06T16:20:00Z'
labels:
  - follow-up
  - domain:erasure
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-102: DELETE /api/account still sends the deletion e-mail from its sync route (the first erasure attempt), holding one of the 40 threads every sync route shares, as the sign-in link did before B-102. account/erasure.md would say the deletion e-mail runs on a thread of its own, with a criterion like account AC-24/AC-25.
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
