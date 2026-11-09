---
id: B-113
title: The cards harness, and the hyphen-edge tests split
status: To Do
assignee: []
created_date: '2026-11-05T22:33:00Z'
updated_date: '2026-11-09T04:50:00Z'
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
- [ ] #1 tests/library_harness.py is gone, every test imports what it uses from cards_harness.py or the shared harness, and role_gate.py's map names the files that exist
- [ ] #2 The hyphen-edge tests live in one file per criterion group, each under about 400 lines, with the same tests passing
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
