---
id: DRAFT-009
title: The ipuz reader's gaps left by B-015
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The ipuz reader's gaps left by B-015 (`src/nock/ipuz.py`): `dotted` is refused, though ipuz draws dotted with dashed as dashed; `solution` must hold Nock's normalised letters (`É` or a lower-case letter is refused); a key written twice in one object keeps its last value silently; a file starting with a UTF-8 byte order mark is refused as "not valid JSON"; a clue's descriptive `explanation`, `tags` or `type` is refused.
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
