---
id: B-096
title: Three archived specs' checks tightened
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T10:15:00Z'
labels:
  - tooling
milestone: m-9
dependencies: []
priority: low
ordinal: 84000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-011, 013 and 014: spec 025's vote banner test leaves SERIAL_TEST_FILES; 048 AC-13 checks document.getAnimations(); spec 035's scan binds placeholders to their values.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The three checks are tightened and fail on the regression each draft names
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
Tooling, no spec: three v1.1.0 tests tightened (025 AC-7, 048 AC-13, 035 language scan)
Tests: tests/test_spec_025_ac07_vote_banner.py, tests/test_spec_048_*ac13*, tests/test_spec_035_*; SERIAL_TEST_FILES in scripts/gate_browsers.py (lead)
Gate: the full gate in Chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Test-writer: 025 AC-7 measures no duration (BANNER_GONE_MS is a bounded wait), 5/5 green with 4 workers, so it leaves SERIAL_TEST_FILES (lead). 048 AC-13 gains a document.getAnimations() check (CSSTransition allowed, as AC-13 allows transition) on the recap, account and ops replay states; an injected element.animate fails the 11 new tests while the 17 text-scan tests pass. 035 AC-9's scan binds {name} to the nicknames and {reaction} to fr.json's reactions (spec035_harness.unknown_texts gains an optional bound_values, default unchanged for its other users); an injected « Error : connection lost » fails the 16 page cases. {text} of note.message stays open, being free chat text.
<!-- SECTION:NOTES:END -->
