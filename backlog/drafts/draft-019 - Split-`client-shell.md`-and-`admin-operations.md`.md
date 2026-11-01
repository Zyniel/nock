---
id: DRAFT-019
title: Split `client/shell.md` and `admin/operations.md`
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T20:21:00Z'
labels:
  - follow-up
  - domain:shell
  - domain:operations
  - domain:foundation
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`client/shell.md` (about 17 KB, 21 criteria after B-042) and `admin/operations.md` (about 19.6 KB, 21 criteria after B-034, whose one criterion the human approved without a split) are past the size budget of `specs/_map.md`; the next criterion in either needs a split first (an architecture item). For shell, the B-010 and B-042 spec-writers propose `client/foundation.md` taking the visual foundation (rules 13 to 16 or 17; AC-13, AC-16 to AC-21).
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
