---
id: B-072
title: The host sheet reopens on the room's values, proven
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T20:41:00Z'
labels:
  - domain:host
milestone: m-5
dependencies: []
documentation:
  - specs/lobby/host.md
priority: medium
ordinal: 60000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-062. B-050's first review round blocked on the host settings sheet reopening on abandoned typed values; the fix (host rule 8) has no test. host.md is past the budget: widen host AC-21 rather than add. Out of scope: lower-level tests of L12, L14, L15.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Typed values closed without saving are gone when the sheet reopens: the room's values show
- [x] #2 host AC-21 (changed)
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
1. Spec: lobby/host.md, widen AC-21 (host is past the budget).
2. Tests: tests/test_host_settings_sheet.py.
3. Quick gate: uv run python scripts/gate.py --specs host --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: option A, « closed without Enregistrer » (the test-writer picks the close); the reopen covers the help mode and the count, as rule 8 names both.

Review round 1: APPROVE. Not taken: 1 (a separate test for the reopen: it saves a browser run, the name covers the lock scenario it continues); 2 (other closes than Escape: they share RoomSheet's onClosed path, as 019's AC-19 test already relies on).

PR #127.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
host AC-21 now also states rule 8's reopening: after the lock, the sheet closed without « Enregistrer » and reopened shows the room's help mode and allowance (vote, 3, 0), not the abandoned typed 7 and « libre ». No code change.

Criteria and their tests:
- host AC-21 (changed): tests/test_host_settings_sheet.py::test_ac21_a_lock_keeps_the_typed_count_and_the_chosen_help_mode (extended: Escape, reopen, vote/3/0).

Spec-checker: APPROVED. Reviewer: APPROVE in round 1 (the test fails if openHostSettings stops copying the room's values); suggestions not taken (reasons in the notes). Full gate: passed (8725 parallel, 162 serial).
Decisions: « closed without Enregistrer » without naming the close, Escape in the test; the reopen covers the help mode and the count; the tests passed on the existing code, so no implementer phase.
<!-- SECTION:FINAL_SUMMARY:END -->
