---
id: B-071
title: 'hud: the room-gone dialog, the reaction pill and the mute case proven'
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T19:42:00Z'
labels:
  - domain:hud
milestone: m-5
dependencies:
  - B-070
documentation:
  - specs/client/hud.md
priority: medium
ordinal: 59000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-002, 022, 064. hud rule 16: AC-21 proves only the Salon sheet giving way to the room-gone dialog; an open room sheet or the recap would prove the native modals give way. Rule 14: no test taps the reaction pill on a clue (a tap selects that clue). Rule 12: when the page moves the focus out of the Salon sheet (mute), the sheet stays open, with no criterion of its own. hud.md is past the budget: widen AC-21 and the existing criteria of rules 12 and 14 rather than add. Out of scope: the Android back gesture.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An open room sheet or the recap gives way to the room-gone dialog
- [x] #2 A tap on a clue's reaction pill selects that clue
- [x] #3 Muting from the Salon sheet keeps it open
- [x] #4 hud AC-16 (changed)
- [x] #5 hud AC-21 (changed)
- [x] #6 hud AC-24 (changed)
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
1. Spec: client/hud.md, widen AC-21 and the criteria of rules 12 and 14 (hud is past the budget).
2. Tests: tests/test_hud_*.py.
3. Quick gate: uv run python scripts/gate.py --specs hud --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: AC-24's mute case from the muted player's side (rule 12: chat rule 15 moves his focus to « Salon »); AC-21 names one room sheet (the host's settings), the recap left out (one sheet shows room sheets give way); the pill tap widens AC-16, the clue cell's pill (ClueCell.svelte).

Lead: the new tests pass on the existing code, so no implementer phase; the scrim and scan checks stay on the two dialogs AC-21 names for them.

Review round 1: APPROVE. Not taken: 1 (assert where the focus lands after the closing Tab: the test already fails on the regression it guards); 2 (AC-16 mixing a pointer and a named test: allowed by _map.md, explained in the docstring).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Criteria and tests for hud behaviour the code already had; no code change.

Criteria and their tests:
- hud AC-16 (changed, keeps ← 043 AC-23..25): tests/test_hud_clue_bar.py::test_ac16_a_tap_on_bobs_pill_selects_ides (a tap at 360x740 and a click at 1280x720 on Bob's pill on IDES's clue select IDES).
- hud AC-21 (changed): tests/test_hud_room_gone.py::test_ac21_with_the_host_settings_open_the_deletion_closes_them_and_shows_it (tests/hud_harness.py: delete_while_host_settings_open).
- hud AC-24 (changed): tests/test_hud_overlay_focus.py::test_ac24_muted_with_the_focus_in_the_message_box_the_sheet_stays_open.

Spec-checker: APPROVED in round 2 (« These two dialogs » for the look and scans). Reviewer: APPROVE in round 1; suggestions not taken (reasons in the notes). Full gate: passed (8716 parallel, 162 serial).
Decisions: AC-21 names the host's settings sheet only, the recap left out; the mute case from the muted player's side; the pill tap widens AC-16; the tests passed on the existing code, so no implementer phase.
<!-- SECTION:FINAL_SUMMARY:END -->
