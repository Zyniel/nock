---
id: DRAFT-004
title: The converter refuses two former files with one number
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:grid-files
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The converter does not refuse two former files with the same `number`; the index it writes is then refused at server start. Refusing it there, naming the second file, keeps its "writes nothing" promise (`content/grid-files.md` rule 15 does not ask for it).
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
