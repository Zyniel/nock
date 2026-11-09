---
id: B-114
title: account/erasure.md back under the size guide
status: Done
assignee: []
created_date: '2026-11-05T05:01:00Z'
updated_date: '2026-11-09T21:54:00Z'
labels:
  - domain:erasure
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-069. account/erasure.md is 17.5 KB with 18 criteria, over the ~15 KB guide of specs/_map.md. Tighten its prose or move one part, its criteria as they are, to a new domain spec; the Plan agent proposes the options, the lead picks. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 erasure.md is under about 15 KB and 20 criteria, any moved part has its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 records AC-1 (moved from erasure AC-1)
- [x] #3 records AC-2 (moved from erasure AC-4)
- [x] #4 records AC-3 (moved from erasure AC-5)
- [x] #5 records AC-4 (moved from erasure AC-6)
- [x] #6 records AC-5 (moved from erasure AC-11)
- [x] #7 records AC-6 (moved from erasure AC-18)
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
Specs: specs/account/erasure.md, new specs/account/records.md, specs/_map.md, the specs citing the moved rules and criteria
Tests: tests/test_erasure_progress.py, _history.py, _teammates.py renamed to test_records_* with their test_acN_ renumbered
Gate: uv run python scripts/gate.py --specs erasure,records --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's pick among the Plan agent's options (Fable, high): option 3, a new domain account/records.md for what the account keeps of a player's play (erasure rules 8-10; AC-1, AC-4, AC-5, AC-6, AC-11, AC-18 renumbered AC-1 to AC-6, text unchanged, as B-085 did), three test files renamed to test_records_*. Rejected: tightening prose only (about 1-1.5 KB, short of the 2.5 KB needed, with a risk of changing meaning); moving AC-15 to AC-17 to account.md (erasure would land at about 15.0 KB, marginal, and leave two topics). Adding the domain is covered by the bet: the pitch names each split adding one. product.md is out of the milestone: not edited.

Spec-checker APPROVED. erasure.md 12,483 bytes, 12 criteria; records.md 6,234 bytes, 6 criteria. Its note on records.md's Purpose taken (the original « which a team-mate's erasure must never undo » restored). Code names progress and account_history checked in src/nock/accounts.py. product.md's routes table (lines 70-71) still names erasure.md as owner of the history and progress routes: product.md is out of the milestone, follow-up draft. The lead updates scripts/gate_browsers.py SERIAL_TEST_FILES with the test rename (an incoherence of the tooling otherwise).

Lead (tooling incoherence): scripts/gate_browsers.py SERIAL_TEST_FILES names test_records_history.py, the renamed file.

Reviewer: APPROVE in one round. Two wording suggestions (erasure.md's records link inside the joining.md bullet; records.md's third edge case « that step 1 ») left for a follow-up draft.

Pull request: https://github.com/Zyniel/nock/pull/190
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
No behaviour change. Architecture decision: the Plan agent (Fable, high) gave three options; the lead picked option 3, a new domain account/records.md (the pitch names each split adding a domain).
- #1 erasure.md is 12,486 bytes with 12 criteria (was 17.5 KB, 18); records.md about 6.2 KB, 6 criteria. Moved word for word: erasure rules 8-10 -> records rules 1-3 (cross-references only); erasure AC-1 (← 029 AC-3, AC-6, AC-7), AC-4, AC-5, AC-6, AC-11, AC-18 -> records AC-1 to AC-6; four edge cases. Tests followed: tests/test_erasure_progress.py, _history.py, _teammates.py renamed tests/test_records_* with test_acN_ renumbered, bodies unchanged; account_harness.py docstring. _map.md: records row, shared-criteria list, glossary. Pointers fixed in history, creator, operations, cards, library, account.
- Tooling (lead): scripts/gate_browsers.py SERIAL_TEST_FILES names test_records_history.py.
- Spec-checker APPROVED (its note on records.md's Purpose taken). Reviewer: APPROVE in one round.
- Full gate: GATE PASSED (full), 8915 parallel and 147 serial tests.
- Follow-up drafts: product.md's routes table still names erasure.md as owner of GET /api/account/history and /progress (product.md out of the milestone); two wording suggestions (erasure.md's records link inside the joining.md bullet, records.md's « that step 1 »).
<!-- SECTION:FINAL_SUMMARY:END -->
