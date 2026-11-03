---
id: B-070
title: A status region empties after it spoke
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T17:52:00Z'
labels:
  - domain:hud
milestone: m-4
dependencies: []
documentation:
  - specs/client/hud.md
priority: medium
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-054 (B-046). The room page's role=status region and each open sheet's keep their last text for good (« Connexion perdue… » after the page reconnects, « Chargement du bilan… » after the recap loads), so a screen reader walking the page reads stale news. Lead's default: a region empties a few seconds after it is written, and a new message replaces the old at once. hud.md is past the budget: change rule 17 and widen AC-26 or AC-27. Out of scope: a real screen-reader check (DRAFT-065).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A status region is empty a few seconds after its last message, and still announces each new one
- [x] #2 hud AC-26 (changed)
- [x] #3 hud AC-27 (changed)
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
1. Spec: client/hud.md rule 17, widen AC-26 or AC-27 (hud is past the budget).
2. Tests: tests/test_hud_status_region.py.
3. Quick gate: uv run python scripts/gate.py --specs hud --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: 5 s after the last write (MESSAGE_HOLD_MS), counted from the write after the existing 50 ms clear; a new message replaces at once and restarts the 5 s; a repeated text is still announced.

Lead: « 5 s after » counts from when the region reads the message (rule 17), not from the press; « at once » means within 500 ms of page time. AC-26's wording aligned with rule 17 by the spec-writer.

Review round 1: APPROVE (full gate green in Chromium, widened by the shared component). Suggestion 1 taken (pin MESSAGE_HOLD_MS with one more reading). Not taken: 2 (rule 17 naming MESSAGE_HOLD_MS and its file: product.md names constants the same way, the spec-checker accepted it); 3 (AC-27 setup copied instead of open_host_sheet: cost only); 4 (a page message written within 50 ms before a sheet opens lands in the inert page's region: no reader, no change).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
One persistent status region per room page and per open sheet now empties MESSAGE_HOLD_MS (5 s) after its last message (web/src/lib/StatusRegion.svelte): a new message replaces the text at once and restarts the 5 s; a repeated text is still announced; the page's region gets nothing while a sheet is open.

Criteria and their tests (tests/test_hud_status_region.py, on Playwright's page clock):
- hud AC-26 (changed): test_ac26_the_region_is_there_at_the_first_paint_and_stays_the_same_element, test_ac26_a_second_message_is_announced_again_and_starts_the_5_s_again (pins the 5 s: text 10 ms before, empty at it).
- hud AC-27 (changed): test_ac27_a_sheet_takes_the_messages_and_the_page_gets_them_once_it_closes.
- tests/test_spec_026_ac10_status_layout.py no longer reads the page's region seconds after the status, which neither of its criteria asks.

Spec-checker: APPROVED (and again for AC-26's count from the write, a slip the test-writer found). Reviewer: APPROVE in round 1; suggestion 1 (pin the 5 s) taken, 2 to 4 not (reasons in the notes). Full gate: passed (8705 parallel, 162 serial).
Decisions: 5 s counted from the write, after the existing 50 ms clear; « at once » within 500 ms of page time; a page message written within 50 ms before a sheet opens may land in the inert page's region (no reader).
<!-- SECTION:FINAL_SUMMARY:END -->
