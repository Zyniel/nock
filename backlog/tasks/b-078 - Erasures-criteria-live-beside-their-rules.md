---
id: B-078
title: Erasure's criteria live beside their rules
status: Done
assignee: []
created_date: '2026-11-04T01:17:00Z'
updated_date: '2026-11-05T03:23:00Z'
labels:
  - domain:account
  - domain:erasure
milestone: m-6
dependencies: []
documentation:
  - specs/account/account.md
  - specs/account/erasure.md
priority: low
ordinal: 66000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-055, option B (the lead's pick, delegated by the human 2026-11-04). account AC-2 (the purge of links and sessions), AC-10 (SHA-256 storage, no secrets in logs) and AC-13 (an anonymous player stored as a nickname, no cookie) prove erasure.md rules 3 and 4. Move the three criteria to erasure.md (next free numbers there; pointers move as they are; the domain tests renamed and moved), so account gets lighter (past the size budget) and each criterion sits beside its rule. No behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The three criteria are in erasure.md beside rules 3 and 4, their tests renamed and passing, and account.md no longer holds them
- [x] #2 erasure AC-15 (new, was account AC-2)
- [x] #3 erasure AC-16 (new, was account AC-10)
- [x] #4 erasure AC-17 (new, was account AC-13)
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
1. Spec: account/account.md AC-2, AC-10, AC-13 move to account/erasure.md beside rules 3 and 4.
2. Tests: the domain tests renamed and moved; pointers move as they are.
3. Quick gate: uv run python scripts/gate.py --specs account,erasure --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decisions: the moved criteria are erasure AC-15 (was account AC-2), AC-16 (AC-10), AC-17 (AC-13), right after AC-13 beside rule 3, not in number order. erasure.md at 16.4 KB and 17 criteria is accepted (account drops to 17.6 KB). No domain test existed: the three were proven by their pointers to tests/test_spec_033_* and test_spec_038_*, so no test moves.

No test phase and no implementer: the moved criteria are proven by their unchanged pointers to tests/test_spec_033_* and test_spec_038_*.

Review round 1: APPROVE. Taken: the Out of scope sentence reworded. Not taken: cutting AC-15 down to its purge sentence (the task moves the criteria whole, and every clause stays proven by its pointer); the sizes were already accepted.

Criterion #1: no domain test existed, so none was renamed; the three are proven by their unchanged pointers. Full gate, one engine at a time: chromium 8,757 + 162 passed, firefox 4,074, webkit 4,074 (plus the serial files), all green.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
account AC-2, AC-10 and AC-13 now live in erasure.md as AC-15, AC-16 and AC-17, beside rules 3 and 4, with their text and their pointers to the tests of v1.1.0 unchanged; account's three numbers are retired. _map.md's citation rows follow, and erasure's Out of scope says the rules of sign-in and the session stay in account.md. account.md is 17.6 KB, erasure.md 16.5 KB (accepted; « Spec splits 2 » cuts account next). No behaviour change, no test changed.
<!-- SECTION:FINAL_SUMMARY:END -->
