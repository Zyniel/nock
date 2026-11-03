---
id: B-075
title: Library rules proven
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T22:06:00Z'
labels:
  - domain:library
milestone: m-5
dependencies: []
documentation:
  - specs/content/library.md
priority: low
ordinal: 63000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-016. library rules 8, 10, 16 and AC-6 are kept by the code but untested: the catalogue asks once and refuses items that are not summaries; the force filter makes no new request; the grid page's loading line and its non-summary answer; after a chip, only that chip pressed. library.md is past the budget (25 criteria): widen existing criteria rather than add.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each of the four behaviours has a test that fails if the code stops keeping it
- [x] #2 library AC-6 (changed)
- [x] #3 library AC-18 (changed)
- [x] #4 library AC-25 (changed)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: content/library.md, widen the criteria of rules 8, 10, 16 and AC-6 (library is past the budget).
2. Tests: tests/test_library_*.py.
3. Quick gate: uv run python scripts/gate.py --specs library --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Review round 1: APPROVE (eleven mutations of the built client each failed a new test). Suggestion 2 taken (the AC-18 test waits for the held request). Not taken: 1 (split the AC-6 test: one page load proves both sentences of the widened criterion); 3 (two handler helpers: not weaker); 4 (progress request: outside the widened criteria).

PR #132.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Four library behaviours the code had (rules 8, 10, 16) are now criteria with tests; no code change.

Criteria and their tests:
- library AC-6 (changed, keeps ← 004 AC-2, 046 AC-4): tests/test_library_filter.py (only the chip just pressed is pressed; one request to /api/grids, none with a query, from load through the presses).
- library AC-18 (changed, keeps ← 004 AC-6, 046 AC-14): tests/test_library_grid_page.py (the muted « Chargement… » line while GET /api/grids/2 has not answered).
- library AC-25 (changed): tests/test_library_date_check.py (an item without word_count, on / and /g/2, and [] on /g/2, show the error line).

Spec-checker: APPROVED in round 2 (no type rule for force; every request counted). Reviewer: APPROVE in round 1 (eleven mutations of the built client each failed a test); the AC-18 test now waits for the held request; other suggestions not taken (reasons in the notes). Full gate: passed (8749 parallel, 162 serial).
Decisions: the closest criterion widened per behaviour; new domain tests beside kept pointers; the tests passed on the existing code, so no implementer phase.
<!-- SECTION:FINAL_SUMMARY:END -->
