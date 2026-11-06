---
id: B-099
title: Lower-level tests of three B-050 fixes
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T11:55:00Z'
labels:
  - domain:hud
  - domain:menus
milestone: m-9
dependencies: []
documentation:
  - specs/client/hud.md
  - specs/client/menus.md
priority: low
ordinal: 87000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-071: L12 (RoomPopover placed again after tick()), L14 (one watcher per list), L15 (a lost pointerup).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each of L12, L14 and L15 has a test that fails without its fix
- [x] #2 menus AC-10 (new)
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
Spec: specs/client/menus.md and/or hud.md, criteria for L12 (and L14, L15 if a pure unit test cannot reach them)
Tests: tests/test_menus_*.py / tests/test_hud_*.py, tests/web/*.test.ts
Quick gate: uv run python scripts/gate.py --specs hud,menus --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
After B-080: L12 (RoomPopover.svelte) is now client/menus.md.

Lead's decisions: L12 becomes menus AC-10 (browser criterion; menus.md owns RoomPopover.svelte, hud.md is over 15 KB); L14 and L15 get tests/web/ unit tests (scrollingLists.test.ts, pinchPan.test.ts), which prove no criterion, so no criterion for them. Rule 5 sharpened to name an open menu following a change of the bar's form; the spec-checker found it states current behaviour (hud rules 1 and 2), not a product change. Spec-checker: APPROVED; its wording note (« turned to » means resized, not rotated) is passed to the test-writer instead of a spec round.

Test-writer: a plain viewport resize does not show L12's bug (Svelte redraws the bar in the microtasks between RoomPage's and the popover's resize listeners), so the AC-10 test delivers each resize as one script event whose listeners run back to back (an init script), the case the fix exists for; without placeAgain() it fails in three engines. Lead's decision: accepted, since the size, layout, bar and expected place are the criterion's and only the event's timing is forced. L14: tests/web/scrollingLists.test.ts (3 of 4 fail on the pre-fix code); L15: tests/web/pinchPan.test.ts (ghost finger fails without the isPrimary guard, capture without setPointerCapture). No implementer phase: the fixes exist.

Reviewer round 1: APPROVE (it re-ran each removal itself in three engines). Taken (test-writer): tests of stopping a shared watcher, the IN_ONE_GO_SCRIPT comment for all engines. Not taken, to a follow-up draft: the dom lib reference in two tests/web files types every unit test with the DOM (a separate DOM-typed group would be tooling). Noted: a real resize does not produce L12's event timing, so L12 is defensive; AC-10 guards it.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Milestone m-9 « Tidy tests and tooling ». No product code changes: the three B-050 fixes existed with no test.

- **menus AC-10 (new)**, L12 (RoomPopover placed again after tick()): `tests/test_menus_popover_place.py::test_ac10_the_open_menu_follows_the_phone_bar_when_the_window_gets_lower`. A plain resize does not show the bug (Svelte redraws the bar in the microtasks between RoomPage's and the popover's resize listeners), so the test delivers each resize as one script event whose listeners run back to back; without `placeAgain()` it fails in Chromium, Firefox and WebKit. Rule 5 names the case.
- **L14** (one watcher per list): `tests/web/scrollingLists.test.ts`, 7 unit tests (sharing, new and removed lines, stopping a shared watcher); each fails on its broken variant.
- **L15** (a lost pointerup): `tests/web/pinchPan.test.ts`, ghost finger (fails without the isPrimary guard) and capture (fails without setPointerCapture).
- **Task #1**: the three above.
- **Spec-checker**: APPROVED. **Reviewer**: APPROVE, round 1 (it re-ran each removal itself). Taken: tests of stopping a shared watcher, the init-script comment. Follow-up: the dom lib reference now types every tests/web unit test with the DOM.
- **Decisions**: L12 as a menus criterion (menus owns RoomPopover; hud.md is over 15 KB); L14 and L15 as unit tests, which prove no criterion; the forced event timing accepted, since a real resize does not produce it and L12 is defensive.
- **Gate**: full gate in Chromium passed (8841 parallel).
<!-- SECTION:FINAL_SUMMARY:END -->
