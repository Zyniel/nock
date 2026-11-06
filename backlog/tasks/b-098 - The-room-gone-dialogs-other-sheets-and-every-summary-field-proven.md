---
id: B-098
title: The room-gone dialog's other sheets and every summary field, proven
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T10:41:00Z'
labels:
  - domain:hud
  - domain:library
milestone: m-9
dependencies: []
documentation:
  - specs/client/hud.md
  - specs/content/library.md
priority: low
ordinal: 86000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-070 and DRAFT-072: hud AC-21 widens to the recap and the account sheet; a parametrised unit test covers every isGridSummary field check.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Deleting any sheet's close line in leaveDeletedRoom, or any field check of isGridSummary, fails a test
- [x] #2 hud AC-32 (new)
- [x] #3 library AC-26 (new)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: specs/client/hud.md (AC-21), specs/content/library.md (isGridSummary)
Tests: tests/test_hud_*.py, tests/test_library_*.py or tests/web/
Quick gate: uv run python scripts/gate.py --specs hud,library --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decision: the description's « unit test » became browser-observable criteria (hud AC-32, library AC-26), since only pytest tests prove a criterion. Spec-checker: APPROVED; noted hud.md is now 15.7 KB, so a further hud criterion should come with a split.

Test-writer: every guarded line (two sheet closes in leaveDeletedRoom, six field checks in isGridSummary) fails its test when removed. No implementer phase: the behaviour exists and the tests pass on the current code.

Reviewer round 1: APPROVE (it re-ran the removal check itself). Taken: one route handler for AC-25/AC-26's list edits, the hud_harness and test_hud_room_gone docstrings (test-writer). Not taken, to a follow-up draft: hud.md is 15.7 KB, so its next criterion should come with a split.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Milestone m-9 « Tidy tests and tooling ». No product code changes: the behaviour existed and was not fully proven.

- **hud AC-32 (new)**: `tests/test_hud_room_gone.py::test_ac32_with_the_recap_open_the_deletion_closes_it_and_shows_the_dialog` and `::test_ac32_with_the_account_sheet_open_the_deletion_closes_it_and_shows_it` (helpers in `tests/hud_harness.py`). Removing `isRecapOpen = false` or `accountDialog?.close()` in leaveDeletedRoom fails its test.
- **library AC-26 (new)**: `tests/test_library_date_check.py::test_ac26_a_list_with_a_field_of_the_wrong_type_is_an_error`, one case per field (number, force, width, height, word_count, published_on). Removing any field check of isGridSummary fails its case.
- **Task #1**: the tests above; the reviewer re-ran the removal check itself.
- **Reviewer**: APPROVE, round 1. Taken: one route handler for AC-25/AC-26's list edits, docstrings. Follow-up: hud.md is 15.7 KB, so its next criterion should come with a split.
- **Decisions**: the description's « unit test » became browser-observable criteria, since only pytest tests prove a criterion; no implementer phase.
- **Gate**: full gate in Chromium passed.
<!-- SECTION:FINAL_SUMMARY:END -->
