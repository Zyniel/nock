---
id: DRAFT-034
title: A mark of its own per kind of word break
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - idea
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A mark of its own per kind of break: B-015 draws every break (hyphen, dot, space, apostrophe) as the same dashed edge and keeps its kind in the answer as written; a kind that should look different would reach the snapshot's marks then (B-015's option B).

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
