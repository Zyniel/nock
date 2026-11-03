---
id: B-068
title: 'Grid files: one number once, safe file names, a former grids folder named'
status: In Progress
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T17:29:00Z'
labels:
  - domain:grid-files
milestone: m-4
dependencies: []
documentation:
  - specs/content/grid-files.md
priority: low
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-004, 005, 006. The converter does not refuse two former files with one number, and the index it writes is then refused at server start: refuse there, naming the second file, writing nothing. An index file name may hold ':' (on Windows outside grids/ or an NTFS stream), and A.ipuz and a.ipuz are one file on a case-insensitive disk: refuse both at load. A grids/ with former .json files and no catalogue.json starts with an empty catalogue and no word: log what to run (uv run python -m nock.ipuz_convert). Out of scope: the ipuz reader's gaps (DRAFT-009, DRAFT-010).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The converter refuses two former files with one number, names the second and writes nothing
- [ ] #2 The index refuses a file name with ':' and two names equal but for case
- [ ] #3 A grids/ with former files and no index logs the command that converts it
- [ ] #4 grid-files AC-22 (new)
- [ ] #5 grid-files AC-23 (new)
- [ ] #6 grid-files AC-24 (new)
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: content/grid-files.md (the converter's refusal, the index's file names, a former grids folder's log line).
2. Tests: tests/test_grid_files_*.py.
3. Quick gate: uv run python scripts/gate.py --specs grid-files --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: the warning fires for a file the converter would read (a .json name not starting with '.'); case-folded equal names reuse the existing same-file refusal; the converter's own lower-case and ':' checks on source names left out (a draft at the milestone's close).
<!-- SECTION:NOTES:END -->
