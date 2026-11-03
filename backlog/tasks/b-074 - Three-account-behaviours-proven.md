---
id: B-074
title: Three account behaviours proven
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T21:39:00Z'
labels:
  - domain:account
milestone: m-5
dependencies:
  - B-066
documentation:
  - specs/account/account.md
priority: low
ordinal: 62000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-023. Untested behaviour the code has: a link token arriving in the URL fragment while /account already shows signs in; another method on an account route answers 405 while accounts are on, and 404 while they are off; a failed purge is logged and the sweep goes on. account.md is at its budget (20 criteria): widen existing criteria rather than add.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A link token in the fragment of an open /account signs in
- [x] #2 A wrong method on an account route answers 405 with accounts on, 404 with them off
- [x] #3 A failed purge is logged and the sweep goes on
- [x] #4 account AC-6 (changed)
- [x] #5 account AC-12 (changed)
- [x] #6 erasure AC-13 (changed)
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
1. Spec: account/account.md (at its budget: widen existing criteria).
2. Tests: tests/test_account_*.py.
3. Quick gate: uv run python scripts/gate.py --specs account --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: new tests in tests/test_account_* and tests/test_erasure_* (not in the 033 tests behind the pointers); « logged » left without a level; account.md's next cut (page and sheet) is DRAFT-058's.

Review round 1: APPROVE (mutations of the sweep, the log and the hashchange listener each failed the tests). Not taken: 1 (rule 1's long line: cosmetic, another spec round not worth it); 2 (merge the no-store test into the 405 one: one behaviour per test); 3 (a third copy of accounts_off_client: a harness move for a later tidy).

PR #131.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Three account behaviours the code had are now criteria with tests; no code change.

Criteria and their tests:
- account AC-6 (changed, keeps ← 033 AC-8, AC-1): tests/test_account_wrong_methods.py (GET /api/account/link and POST /account: 404 Not Found with accounts off, 405 Method Not Allowed with them on; no-store on the GET to link). account rule 1 names the 405 body.
- account AC-12 (changed, keeps ← 033 AC-2, AC-11): tests/test_account_fragment_link.py (a link token set as the fragment of a signed-out /account, no reload, signs in and leaves the URL).
- erasure AC-13 (changed): tests/test_erasure_purge_failure.py (a purge at 157,680,001 s that raises is logged; a later sweep deletes the erasure).

Spec-checker: APPROVED. Reviewer: APPROVE in round 1 (mutations of the sweep, the log and the hashchange listener each failed the tests); suggestions not taken (reasons in the notes). Full gate: passed (8743 parallel, 162 serial).
Decisions: new tests in domain files beside the kept 033 pointers; « logged » without a level; account.md's next cut is DRAFT-058's; the tests passed on the existing code, so no implementer phase.
<!-- SECTION:FINAL_SUMMARY:END -->
