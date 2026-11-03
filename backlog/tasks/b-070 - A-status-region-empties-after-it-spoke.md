---
id: B-070
title: A status region empties after it spoke
status: In Progress
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T16:18:00Z'
labels:
  - domain:hud
milestone: m-4
dependencies: []
documentation:
  - specs/client/hud.md
priority: medium
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-054 (B-046). The room page's role=status region and each open sheet's keep their last text for good (« Connexion perdue… » after the page reconnects, « Chargement du bilan… » after the recap loads), so a screen reader walking the page reads stale news. Lead's default: a region empties a few seconds after it is written, and a new message replaces the old at once. hud.md is past the budget: change rule 17 and widen AC-26 or AC-27. Out of scope: a real screen-reader check (DRAFT-065).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A status region is empty a few seconds after its last message, and still announces each new one
- [ ] #2 hud AC-26 (changed)
- [ ] #3 hud AC-27 (changed)
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
1. Spec: client/hud.md rule 17, widen AC-26 or AC-27 (hud is past the budget).
2. Tests: tests/test_hud_status_region.py.
3. Quick gate: uv run python scripts/gate.py --specs hud --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: 5 s after the last write (MESSAGE_HOLD_MS), counted from the write after the existing 50 ms clear; a new message replaces at once and restarts the 5 s; a repeated text is still announced.

Lead: « 5 s after » counts from when the region reads the message (rule 17), not from the press; « at once » means within 500 ms of page time. AC-26's wording aligned with rule 17 by the spec-writer.
<!-- SECTION:NOTES:END -->
