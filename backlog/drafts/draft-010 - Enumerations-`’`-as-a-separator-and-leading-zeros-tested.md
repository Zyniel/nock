---
id: DRAFT-010
title: 'Enumerations: `’` as a separator, and leading zeros tested'
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:grids
  - domain:grid-files
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
B-015 left: `’` in an enumeration is refused while rule 4 of `content/grids.md` makes it the same separator as `'` (`content/grid-files.md` rule 9 lists `'` only; say which); no test locks in that an enumeration with a leading zero (`"05"`, `"02-3"`) loads, as it does.
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
