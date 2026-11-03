---
id: B-074
title: Three account behaviours proven
status: In Progress
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T20:18:00Z'
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
- [ ] #1 A link token in the fragment of an open /account signs in
- [ ] #2 A wrong method on an account route answers 405 with accounts on, 404 with them off
- [ ] #3 A failed purge is logged and the sweep goes on
- [ ] #4 account AC-6 (changed)
- [ ] #5 account AC-12 (changed)
- [ ] #6 erasure AC-13 (changed)
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
1. Spec: account/account.md (at its budget: widen existing criteria).
2. Tests: tests/test_account_*.py.
3. Quick gate: uv run python scripts/gate.py --specs account --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: new tests in tests/test_account_* and tests/test_erasure_* (not in the 033 tests behind the pointers); « logged » left without a level; account.md's next cut (page and sheet) is DRAFT-058's.
<!-- SECTION:NOTES:END -->
