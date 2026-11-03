---
id: DRAFT-006
title: A `grids/` of former `.json` files starts empty with no error
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
A `grids/` still holding former `.json` files and no `catalogue.json` starts with an empty catalogue and no error (`content/grid-files.md` rule 1): run `uv run python -m nock.ipuz_convert` on it once.
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
