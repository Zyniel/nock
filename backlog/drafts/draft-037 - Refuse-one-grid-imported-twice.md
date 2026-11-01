---
id: DRAFT-037
title: Refuse one grid imported twice
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - idea
  - domain:grid-files
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
One grid imported twice: B-013 records `uniqueid`; refusing two index entries whose files share one would stop the same grid entering twice (`content/grid-files.md`).

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
