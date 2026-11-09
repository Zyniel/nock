---
id: B-113
title: The cards harness, and the hyphen-edge tests split
status: Done
assignee: []
created_date: '2026-11-05T22:33:00Z'
updated_date: '2026-11-09T19:05:00Z'
labels:
  - tooling
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-078. tests/cards_harness.py exists but tests/library_harness.py is still there; library's filter test takes only QUIET_MS from it. Move QUIET_MS to a shared harness and remove library_harness.py; the conftest registration and role_gate.py's harness-to-domain map follow. Split tests/test_viewport_hyphen_edges.py (831 lines) by criterion group (AC-9, AC-10, AC-21). Tests and tooling only: the test-writer moves the tests, the lead fixes role_gate.py's map as an incoherence of the tooling. Out of scope: any spec or product code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 tests/library_harness.py is gone, every test imports what it uses from cards_harness.py or the shared harness, and role_gate.py's map names the files that exist
- [x] #2 The hyphen-edge tests live in one file per criterion group, each under about 400 lines, with the same tests passing
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
Specs: none (tooling task)
Tests: tests/library_harness.py, tests/cards_harness.py, tests/conftest.py, tests/test_viewport_hyphen_edges*.py; scripts/hooks/role_gate.py
Gate: uv run python scripts/gate.py --specs cards,library,viewport --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: library_harness.py's content moved into cards_harness.py (the cards domain's harness), and test_library_filter.py imports QUIET_MS from it. role_gate.py's harness-to-domain map is the prefix rule of names_domain (test_<domain>_*, <domain>_harness*): with library_harness.py gone it names only files that exist (cards_harness.py -> cards), so it needs no edit. Its one gap, that a change to cards_harness.py does not add library to the quick gate though test_library_filter.py imports it, is not new and CI runs every test: a follow-up draft, since closing it is new tooling behaviour. The hyphen-edge file split in four (AC-9 is two files, at about 430 lines alone). The Tests lines of content/cards.md and content/library.md that named library_harness.py go through the spec-writer and the spec-checker.

Pull request: https://github.com/Zyniel/nock/pull/183
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Tooling task: tests and the specs' Tests lines only, no behaviour change.
- #1 tests/library_harness.py is gone: its content (content/cards AC-7 to AC-9 setup) is in tests/cards_harness.py, which every cards test, test_my_account_progress_signout.py and test_library_filter.py (QUIET_MS) import. role_gate.py's map is the prefix rule of names_domain, which names only files that exist: no edit needed. conftest registers harnesses by glob.
- #2 tests/test_viewport_hyphen_edges.py (831 lines) is four files: _ac9_edges (279), _ac9_states (252), _ac10 (232), _ac21 (147), shared setup in tests/viewport_harness.py; the same 68 test ids are collected before and after.
- content/cards.md and content/library.md: their Tests lines name the files that exist (spec-checker APPROVED).
- Reviewer: APPROVE in one round; its two small harness suggestions taken (stored_progress removed, constants together).
- Full gate: GATE PASSED (full), 8915 parallel and 147 serial tests.
- Follow-up draft: a change to cards_harness.py does not add library or my-account to the quick gate, though their tests import it (new role_gate behaviour, the human's call).
<!-- SECTION:FINAL_SUMMARY:END -->
