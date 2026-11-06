---
id: B-100
title: Flakes under load
status: To Do
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T03:26:00Z'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the close of « Owner's calls »: WebKit test_server_offline_undo AC-29 fails with 'Clock.pause_at: Cannot fast-forward to the past' (CI after 06c360b, and B-079's local gate); its cause is in scope here.

From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), items D, E, B and F:
- D (WebKit/Firefox 'Cannot fast-forward to the past', test_server_offline_undo AC-29). pause_page_clock pauses only 1 ms ahead of the page's Date.now(), but the round trip to WebKit or Firefox takes several ms. Reproduced 6/12 in WebKit and 4/10 in Firefox under load. Fix: a margin of about 250 ms, or install the clock paused and drive it with run_for. Size XS.
- E (Firefox 033 AC-9, seq 5 instead of 105). Most likely the mocked socket fell silent for 4 s under load and the page reconnected. MockRoomSocket.send always writes to routes[0] (spec024_harness.py:841), the dead socket. Fix: the mock follows the newest route and answers its join with the latest snapshot. Size S. Not reproduced (216/216).
- B (timing tests foundation remote pace AC-13 and 036 AC-1). Other agents' browser runs load the CPUs while the gate's serial pass runs. Fixes: AC-13 subtracts an idle window's TaskDuration; the gate-side options are the human's call (see the gate draft). Size S. The budgets stay as they are, since they are product.md baselines.
- F (048 AC-5 'account-error ends under the submit button's top', CI on #147). Weight 500 loads only when the error line appears, and the three boxes are read across the font swap. Fix: wait_for_fonts once the error shows, and read the boxes in one evaluate. Size XS.

From m-8's close review: B-094's full gate failed test_spec_035_ac08_ac09_contrast_and_french.py::test_ac8_text_contrast_holds_on_a_cell_flashing_in_every_colour[chromium-phone-7] once. The cell's data-flash was already empty when read, a timing race under load; it passed 48/48 on rerun.
<!-- SECTION:NOTES:END -->
