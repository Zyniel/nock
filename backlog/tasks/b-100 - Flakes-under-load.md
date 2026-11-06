---
id: B-100
title: Flakes under load
status: In Progress
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T10:39:00Z'
labels:
  - tooling
milestone: m-9
dependencies: []
priority: low
ordinal: 88000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-024, 032, 053 and 018, and B-079's gate (webkit test_server_offline_undo AC-29, firefox test_spec_033_ac09 at 320x568): find each cause; a wait for the right state, SERIAL_TEST_FILES, or a page-ready wait in the harness; check hud AC-20 in WebKit on CI's run after a merge.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each listed flake has a found cause and a fix, or is recorded with why it stays, and the full gate passes twice in a row in three engines
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
Tooling, no spec: the causes D, E, B, F of the 2026-11-05 investigation and the 035 contrast race
Tests: tests/test_server_offline_undo.py, spec024_harness.py, the foundation pace AC-13 test, 048 AC-5, 035 AC-8 (test-writer); SERIAL_TEST_FILES if needed (lead)
Gate: the full gate, twice, chromium locally; Firefox and WebKit on CI after the merge
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the close of « Owner's calls »: WebKit test_server_offline_undo AC-29 fails with 'Clock.pause_at: Cannot fast-forward to the past' (CI after 06c360b, and B-079's local gate); its cause is in scope here.

From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), items D, E, B and F:
- D (WebKit/Firefox 'Cannot fast-forward to the past', test_server_offline_undo AC-29). pause_page_clock pauses only 1 ms ahead of the page's Date.now(), but the round trip to WebKit or Firefox takes several ms. Reproduced 6/12 in WebKit and 4/10 in Firefox under load. Fix: a margin of about 250 ms, or install the clock paused and drive it with run_for. Size XS.
- E (Firefox 033 AC-9, seq 5 instead of 105). Most likely the mocked socket fell silent for 4 s under load and the page reconnected. MockRoomSocket.send always writes to routes[0] (spec024_harness.py:841), the dead socket. Fix: the mock follows the newest route and answers its join with the latest snapshot. Size S. Not reproduced (216/216).
- B (timing tests foundation remote pace AC-13 and 036 AC-1). Other agents' browser runs load the CPUs while the gate's serial pass runs. Fixes: AC-13 subtracts an idle window's TaskDuration; the gate-side options are the human's call (see the gate draft). Size S. The budgets stay as they are, since they are product.md baselines.
- F (048 AC-5 'account-error ends under the submit button's top', CI on #147). Weight 500 loads only when the error line appears, and the three boxes are read across the font swap. Fix: wait_for_fonts once the error shows, and read the boxes in one evaluate. Size XS.

From m-8's close review: B-094's full gate failed test_spec_035_ac08_ac09_contrast_and_french.py::test_ac8_text_contrast_holds_on_a_cell_flashing_in_every_colour[chromium-phone-7] once. The cell's data-flash was already empty when read, a timing race under load; it passed 48/48 on rerun.

DRAFT-018 (hud AC-20 in WebKit on CI after a merge): CI run 419 on main (merge of #157, 2026-11-06), every engine including WebKit, concluded success, so hud AC-20 passed in WebKit there. Closed. Lead's decision: the test-side fixes go to the test-writer (tests/ is its path); SERIAL_TEST_FILES changes, if any, are the lead's.

Test-writer's findings and fixes (2026-11-06):
- D fixed: test_server_offline_undo.py's pause_page_clock (1 ms ahead) replaced by spec027_harness.freeze_clock (50 ms ahead, doubling to 800 ms). Original failed 3/6 in WebKit under load (load ~20 on 4 CPUs); fix 10/10 WebKit and Firefox under load.
- E fixed: spec024_harness.MockRoomSocket sends on the newest route and answers a rejoin with the last snapshot at the highest seq sent. Not reproduced; new path checked with a throwaway test in Chromium and Firefox; 033 AC-9 72/72 in Firefox under load x3.
- B fixed for foundation remote pace AC-13: the cost per selection_moved subtracts an idle window's TaskDuration of the same length; budget unchanged. Did not reproduce before or after. 036 AC-1 stays (the gate-side options are B-107's); a test-side « machine is quiet » calibration wait is a follow-up idea.
- F fixed: 048 AC-5 reads the boxes in one evaluate after the fonts; fonts_ready.wait_for_fonts forces a layout before document.fonts.ready (a face is requested only at layout). Passes in three engines under load; 578 paused-clock tests sharing wait_for_fonts pass.
- 035 AC-8 flash race fixed: the page clock is installed and frozen before the letter that starts the flash, so the flash stays on while read. Three engines under load.
- DRAFT-053 fixed: tests/page_ready.wait_for_room_page (10 s, as conftest's enter_room) after goto in the spec013, 014, 024 and 035 harness openers; 044 AC-2 and host AC-10 already waited 10 s.
- DRAFT-024: 036 AC-8's in-page join wait goes from a hard 5 s to SERVER_START_SECONDS (10 s), likely cause. Stay, cause not visible in the test code: 046 AC-22 nickname error (already hardened), 046 AC-22 fit, 024 AC-3 disabled reveal contrast, 019 AC-4 legend (Windows only); 046 AC-14 « client not built » is another gate rebuilding web/dist (environment).
- DRAFT-032 stays: goto waits for load, which waits for index.css where .nock-card is defined; no late stylesheet is possible. If it fails again, SERIAL_TEST_FILES.
- No SERIAL_TEST_FILES change needed. Follow-up: 14 other mocks still send only on routes[0] (spec006-016, 023, 026, 035 harnesses, 018 AC-3, 037 AC-4, 040 AC-14 tests).
<!-- SECTION:NOTES:END -->
