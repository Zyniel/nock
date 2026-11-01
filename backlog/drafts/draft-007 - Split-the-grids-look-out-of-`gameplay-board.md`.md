---
id: DRAFT-007
title: Split the grid's look out of `gameplay/board.md`
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:board
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`gameplay/board.md` is over the size guideline (about 20 KB, 22 criteria after B-012): split the grid's look (rules 1 to 4 and 20, AC-4 to AC-8, AC-21, AC-22) into its own domain file, an architecture decision.
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
