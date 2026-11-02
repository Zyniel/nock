---
id: DRAFT-007
title: Split the grid's look out of `gameplay/board.md`
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T00:07:00Z'
labels:
  - follow-up
  - domain:board
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`gameplay/board.md` is over the size guideline (about 23 KB, 29 criteria after B-044): split it, an architecture decision. Two proposals: the grid's look (rules 1 to 4 and 20, AC-4 to AC-8, AC-21, AC-22) into its own domain file (B-012), or the in-app keyboard (rules 14 to 17, AC-16 to AC-19 and the keyboard part of AC-20) into `gameplay/keyboard.md` (B-044). With the split, AC-2's and AC-28's "(Chromium only, as AC-2)" leaves the spec: it is test mechanics (B-044's reviewer).
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
