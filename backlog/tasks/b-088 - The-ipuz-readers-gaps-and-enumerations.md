---
id: B-088
title: The ipuz reader's gaps and enumerations
status: To Do
assignee: []
created_date: '2026-11-05T01:53:00Z'
labels:
  - domain:grid-files
  - domain:grids
milestone: m-8
dependencies: []
documentation:
  - specs/content/grid-files.md
  - specs/content/grids.md
priority: low
ordinal: 76000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-009 and DRAFT-010: dotted (drawn as dashed), solution letters, a key written twice, a UTF-8 byte order mark, a clue's explanation, tags or type; ’ as an enumeration separator, and a test that a leading zero loads. Decide each in the spec, then build. Out of scope: other ipuz features.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the reader's gaps and the ’ separator is decided in the specs with a criterion, tested and built
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
