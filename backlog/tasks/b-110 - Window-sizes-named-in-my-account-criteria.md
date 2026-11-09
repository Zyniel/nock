---
id: B-110
title: Window sizes in layout criteria, one rule
status: Done
assignee: []
created_date: '2026-11-05T22:21:00Z'
updated_date: '2026-11-09T20:43:00Z'
labels:
  - follow-up
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-076. Criteria name window sizes (360 by 740, 320 by 568, 1280 by 720) in about 12 files: hud 18 times, menus 9, viewport 6, cells 5, and others. _map.md « What a spec holds » keeps test mechanics out of specs, but a window size is the condition a layout criterion is about, what the player's screen is. Lead's call: _map.md names the window sizes a layout criterion may state (the phone, the small phone, the desktop) and says a criterion names them, not the test. Only _map.md changes, plus any size a criterion uses that is not on the list. Out of scope: rewording the criteria that already name a listed size.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 _map.md « What a spec holds » lists the window sizes layout criteria may name, every size named in a domain spec is on the list, and the gate's traceability is green
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
Specs: specs/_map.md « What a spec holds » (the window sizes), plus any domain spec naming a size not on the list
Tests: none expected (no criterion reworded)
Gate: uv run python scripts/gate.py --stage tests (traceability)
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: the specs (archive left out) name 78 sizes in 13 files; every window size is on the new list, so no criterion changes. The sentence defining « The supported windows » as the eight sizes the tests share is dropped: that set is product.md rule 11, a baseline (escalation class, out of the milestone); follow-up draft. 283 by 640 stays listed (hud AC-3's test runs at it).

Spec-checker: CHANGES REQUESTED in round 1 (1920 by 1080 both listed and excluded as a bound of product.md rule 11; 283 by 640 named like a phone class), APPROVED in round 2. No test and no code change: no criterion changed.

Reviewer: APPROVE in one round; its wording suggestion taken (a window on a threshold or a pixel on either side), spec-checker APPROVED. Left: _map.md is 20 KB (not a domain file; already over before).

Pull request: https://github.com/Zyniel/nock/pull/187
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Only specs/_map.md changed; no criterion, test or code.
- #1 « What a spec holds »: a window is not a test mechanic; a layout criterion names the window it is about, from a list: phone 360 by 740 / 740 by 360, small phone 320 by 568 / 568 by 320, 283 by 640 (under product.md rule 11's floor), tablet 768 by 1024 / 1024 by 768, desktop 1280 by 720, laptop 1280 by 800, large desktop 1920 by 1080, low desktop 1280 by 480; a criterion on a _design/ threshold may name a window on it or a pixel on either side (900 and 899 by 600, 800 by 800); sizes that are not windows (grid viewport, a cell, an image, rule 11's floor 300 by 480) are not on the list. Every size named in a domain spec is covered (spec-checker's scan across line wraps); traceability green.
- Decisions: no sentence defines « the supported windows » (product.md rule 11's set is a baseline, an escalation class, out of the milestone): follow-up draft. 283 by 640 listed (hud AC-3's test runs at it).
- Spec-checker: CHANGES REQUESTED once (1920 by 1080 both listed and excluded), then APPROVED. Reviewer: APPROVE in one round; its threshold-wording suggestion taken.
- Full gate: GATE PASSED (full), 8915 parallel and 147 serial tests.
<!-- SECTION:FINAL_SUMMARY:END -->
