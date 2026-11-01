---
id: DRAFT-035
title: The length pattern in the clue bar
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - idea
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The length pattern in the clue bar: « (3-2-5) » after the clue text, from the letters and breaks the model already has (ipuz's `showenumerations` is the file's switch). B-012 left it out of scope.

Keep the engine free of ipuz: add the concept to Nock's own model first (`src/nock/grid.py`); only `nock.ipuz` maps the ipuz field onto it (doc "Grid engine and ipuz").
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
