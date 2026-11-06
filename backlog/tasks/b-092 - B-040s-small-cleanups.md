---
id: B-092
title: B-040's small cleanups
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T19:20:00Z'
labels:
  - domain:my-account
milestone: m-10
dependencies: []
documentation:
  - specs/account/my-account.md
priority: low
ordinal: 80000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-043: one reading of a mixed nock.account_rooms array, malformed history records of other rooms kept, test_ac33's branches. Runs after the account split.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each cleanup of DRAFT-043 is done or decided, with its test
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: account/my-account.md: the reading of a mixed nock.account_rooms array and the sign-out keeping other rooms' records as stored, each with a criterion
Tests: tests/test_my_account_*.py (new criteria; AC-7's test parametrized, its stored-JSON helper reusing the harnesses')
Quick gate: uv run python scripts/gate.py --specs my-account --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
After B-084: the test test_ac33 is now my-account AC-7 (test_ac7 in tests/test_my_account_signout_forgets.py).

Lead's decisions on DRAFT-043: (1) a mixed nock.account_rooms array: the strict reading stays (the rule already says anything but an array of codes reads as empty, and Nock never writes another shape), the code follows it, with a criterion; (2) the sign-out keeps the other rooms' history records exactly as stored, malformed ones included (filter the raw items), with a criterion; (3) test_ac33, now my-account AC-7's test: parametrized over the action, its stored_json helper replaced by the harnesses' readers, a test-only change with no criterion.

Lead's answers to the spec-writer: AC-10 and AC-11 never used in this file (only 033 pointers); a malformed nock.history item whose code is listed goes with the room's records (rule 5: each item whose code is listed); any string of nock.account_rooms counts as a code (strict only about non-string items); a sign-in after a mixed array rewrites it with the new codes only, not stated (Nock never writes one); history.ts's merge dropping malformed items is gameplay/history.md's, a follow-up draft.

Spec-checker round 1: APPROVED. Its notes 1 (rule 1: « a JSON array of strings, each read as a code », « any item ») and 2 (AC-10 also checks nock.account_rooms is gone) taken by the spec-writer after the verdict, the checker's own wording, so no second check; note 3 (a nock.history that is not an array) left, outside DRAFT-043.
<!-- SECTION:NOTES:END -->
