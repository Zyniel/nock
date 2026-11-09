---
id: B-111
title: A calendar example for « Mes salons » and /ops dates
status: Done
assignee: []
created_date: '2026-11-06T03:26:00Z'
updated_date: '2026-11-09T21:07:00Z'
labels:
  - domain:summaries
  - domain:operations
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-080. isDateTime (web/src/lib/dateTime.ts) refuses a date-time the calendar lacks in every engine, which changes « Mes salons » (lobby/summaries.md rule 2) and the /ops replay reading; no criterion of those domains shows it. Out of scope: any change to isDateTime.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 lobby/summaries.md AC-4 includes an impossible date such as 2026-02-30, with a test that fails if the check is removed
- [x] #2 admin/operations.md's date criterion, if one exists, includes the same case with a test; otherwise the task's notes say so
- [x] #3 summaries AC-4 (changed)
- [x] #4 ops-page AC-16 (changed)
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
Specs: specs/lobby/summaries.md (rule 2, AC-4), specs/admin/ops-page.md (rule 6, AC-16)
Tests: tests/test_summaries_iso_dates.py (AC-4), tests/test_ops_page_states.py (AC-16)
Gate: uv run python scripts/gate.py --specs summaries,ops-page --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: the /ops replay page is specified in admin/ops-page.md, not operations.md; its date criterion is AC-16 (rule 6), so criterion #2 applies to ops-page AC-16.

Criterion #2: admin/operations.md has no criterion that reads a date (the server writes its dates and parses none sent to it); the /ops date criterion is ops-page AC-16. Spec-checker APPROVED; its optional note (ops-page rule 6 could mirror summaries rule 2 word for word) is not taken: one function decides both and AC-16 checks refusals only.

No implementation phase: isDateTime already refuses a date the calendar lacks; the new cases pass on the current code and fail with its day-in-month check dropped.

Reviewer: APPROVE in one round. Suggestions left for follow-up drafts: an impossible time (T25:00:00Z) and an accepted leap day (2028-02-29) are not shown by any criterion.

Pull request: https://github.com/Zyniel/nock/pull/188
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
No behaviour change: isDateTime is unchanged; specs and tests only.
- #1 (summaries AC-4 changed, rule 2 says a date is on a day and at a time the calendar has): 2026-02-30T08:30:00Z shows « Impossible de charger vos salons. » and no row; tests/test_summaries_iso_dates.py, both test_ac4_ tests (last_activity_at and finished_at).
- #2 (ops-page AC-16 changed, rule 6 alike): an edit time 2026-02-30T10:00:00Z shows only « Impossible de charger les données. »; tests/test_ops_page_states.py test_ac16_..._error_line[time-feb-30]. admin/operations.md has no criterion that reads a date (the server writes its dates and parses none sent to it): the /ops page's date criterion is ops-page AC-16 (the lead's reading).
- Proof: with isDateTime's day-in-month check dropped (day <= 31), exactly the three new cases fail; restored, they pass (test-writer and reviewer each).
- Spec-checker APPROVED. Reviewer: APPROVE in one round.
- Full gate: GATE PASSED (full), 8918 parallel and 147 serial tests.
- Follow-up draft: no criterion shows an impossible time (T25:00:00Z) nor an accepted leap day (2028-02-29).
<!-- SECTION:FINAL_SUMMARY:END -->
