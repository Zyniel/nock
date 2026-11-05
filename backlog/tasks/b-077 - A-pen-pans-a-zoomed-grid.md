---
id: B-077
title: A pen pans a zoomed grid
status: Done
assignee: []
created_date: '2026-11-04T01:17:00Z'
updated_date: '2026-11-05T04:35:00Z'
labels:
  - domain:viewport
milestone: m-6
dependencies: []
documentation:
  - specs/gameplay/viewport.md
priority: medium
ordinal: 65000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-063, the human's option B (2026-11-04). Since B-050 (L15), web/src/lib/pinchPan.ts ignores every pointer but touch, so a pen no longer pans a zoomed grid. A pen drags like a finger: one pen on a zoomed grid pans it; a pen tap still selects the cell (a drag starts only past the threshold the finger uses). A mouse still never pans. Out of scope: pinch with a pen (one pointer), mouse panning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 On a zoomed grid, a pen drag pans the grid as a finger drag does
- [x] #2 A pen tap still selects the cell it touched, and a mouse drag still pans nothing
- [x] #3 viewport AC-2 (changed)
- [x] #4 viewport AC-20 (new)
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
1. Spec: gameplay/viewport.md rule 3 (which pointers pan) and its criterion.
2. Tests: tests/test_viewport_*.py (a pen drag pans, a pen tap selects, a mouse drag pans nothing).
3. Quick gate: uv run python scripts/gate.py --specs viewport --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decisions: no drag-threshold number in the spec (no spec or code has one; AC-20 sets a still tap against a 100 px drag). The code drops a click that an engine fires after a pen drag, with a small movement limit for the pen only; the finger keeps the browser's behaviour. Pinch counts touch pointers only. Whether AC-20 needs a Chromium-only note is the test-writer's call.

Review round 1: CHANGES REQUESTED. Fixed: a pen lifted beside the viewport, or hovering with its tip up, is forgotten and never pans; the pen-beside-a-pinch test now fails if a pen joins or clears the fingers (checked on two mutations); the hover sends no button; the pen-alone zoom test that could not fail is gone; the pen keeps its start as a Finger.

Review round 2: APPROVE. Not taken: listening for the pen's lift in the capture phase (the tip-up check already forgets a pen whose lift never arrives).

Pull request #138.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
A pen on a zoomed grid now pans it as a finger does; a pen tap still selects its cell, and a mouse drag pans nothing. pinchPan.ts tracks a pen apart from the fingers (pinch counts touch only), drops the click an engine fires after a pen drag, and forgets a pen lifted outside the viewport or hovering tip-up. Spec: viewport AC-2 widened, AC-20 added. Full gate green in Chromium, Firefox and WebKit.
<!-- SECTION:FINAL_SUMMARY:END -->
