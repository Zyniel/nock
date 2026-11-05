---
id: B-003
title: Compact the tests
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
updated_date: '2026-11-05T18:00:00Z'
labels: []
milestone: m-2
dependencies: []
priority: low
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Who decides: the human delayed the decision.
- Domains: none (tests only)
- Waits for: B-001
- Problem: 4.9 MB of tests for 875 KB of code; helpers are copied from file to
  file (`dist_dir` in 72 files, `catalogue` in 82) and near-copies of one test
  stand where a parameter would do.
- In scope: shared fixtures and harnesses; parametrized tests in place of
  copies; the same criteria proven, no weaker check.
- Out of scope: the code; what the tests prove.
- Screens: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The local copies of dist_dir (74 files) and catalogue (114 files) give way to shared fixtures in tests/conftest.py where they are the same; near-copies in one file become parametrised tests; every criterion keeps its test names and checks, and the full gate passes
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
1. Wait for B-038 and B-077 to merge (both edit tests/conftest.py or viewport test files), then merge main here.
2. test-writer (tests only, no spec): move identical dist_dir and catalogue copies to conftest fixtures; parametrise near-copies inside one file; never rename a test_acN_ function nor weaken a check.
3. reviewer checks no check got weaker (collected test count per criterion, the gate's traceability), then the full gate in three engines and the pull request.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Released by the human in chat, 2026-11-05 (« /milestone m-2 »: run Upkeep). The lead cuts it to fit one task: the most copied helpers (dist_dir, catalogue and the like) move into shared fixtures, and near-copies become parametrised tests where a file holds them; every criterion keeps its test names and checks, none weaker. What is left goes back to a draft.

Test-writer: 381 files, +212 -3381; dist_dir in conftest.py (3 spec 040 copies kept, they write assets); catalogue built from CATALOGUE_KIND by tests/catalogue_builders.py (5 spec 011 and 018 copies kept, they build their own entries); fx01_grid also shared. Collected ids identical (8,936). Lead decision: no parametrisation, since every near-copy is a test_acN_ function and the criterion keeps every test name; 27 groups of near-copies stay as they are.

Review round 1: CHANGES REQUESTED (19 harness docstrings named the removed copies; spec 038 docstrings). Fixed; the lead also named fx01_grid and CATALOGUE_KIND in .claude/agents/test-writer.md (a tooling coherence fix). Not taken: failing on a misspelled CATALOGUE_KIND name (its tests fail on the missing grids anyway). Review round 2: APPROVE. The full gate waits for B-080 and B-081 to merge, since they move test files this task edits.

After B-080 and B-081 merged, main came in. The conflicts in test_account_sheet_backdrop.py and test_chat_connection.py were resolved: the moved helpers are imported from menus_harness and spec022_harness, with no local copies. The new test_reactions_connection.py lost its local fx01_grid copy. Full gate here (Chromium): static checks, 8,774 parallel and 162 serial tests, all green. Firefox and WebKit are left to CI after the merge: the change is to test setup only. Then main took B-082 and the board change (specs and backlog only), and the traceability gate passed again.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shared test fixtures replace the local copies: dist_dir, fx01_grid and catalogue in tests/conftest.py, built by tests/catalogue_builders.py. A module picks its catalogue with CATALOGUE_KIND (published, published_force_1, reference); without it the catalogue is empty. About 380 test files lost their copies (+212/-3381 lines). The collected test ids are unchanged, as are every test name and check. The near-copies stay separate test_acN_ functions, since parametrising them would merge criteria's tests. .claude/agents/test-writer.md now tells the test-writer to reuse these fixtures.
<!-- SECTION:FINAL_SUMMARY:END -->
