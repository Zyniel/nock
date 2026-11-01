---
id: B-042
title: The grid's focus ring above the cells
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T19:35:00Z'
labels:
  - domain:shell
milestone: m-1
dependencies: []
documentation:
  - specs/client/shell.md
priority: high
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: third of B-039's items (a baseline the product breaks today:
  `product.md` rule 14)
- Domains: client/shell (AC-18 reads the ring's computed style only; a
  pixel check along the grid's edges), `_design/foundation.md` « Focus »
  with option B only
- Architecture decision: no
- Model: Opus for the test-writer and the implementer (painted pixels,
  `CLAUDE.md`)
- Problem: `.grid:focus-visible` draws its ring inside, at offset -3 px
  (`GridViewport.svelte:1195`), over the edge cells, and the letter cells are
  positioned and opaque (`:896`): Chromium and WebKit paint them after the
  grid's outline. On screenshots of a 14 by 9 grid focused from the keyboard,
  the ring shows only where a clue cell touches the edge and is hidden along
  every letter cell (B-039 M4). The test of the ring
  (`tests/test_spec_041_ac07_ac08_focus_ring.py`) reads the computed style,
  so the gate cannot see it.
- In scope: a ring that shows along the whole edge, and a pixel check along
  the right and bottom edges in Chromium and WebKit. Options:
  - A (lead's pick): the same ring drawn by an `aria-hidden` overlay painted
    after the cells (`inset: 0`, `pointer-events: none`), outlined while the
    grid has `:focus-visible`; the look as designed.
  - B: the ring outside the grid, at the foundation's offset of 2 px; the
    look changes and the viewport must not clip it.
- Out of scope: the focus of the cells themselves (`aria-activedescendant`).
- Screens: the grid focused from the keyboard; none changes with option A
  (the ring is drawn as designed), the screens sheet redrawn with option B.
- Open questions: none beyond the option.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 shell AC-21 (new)
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
Specs: specs/client/shell.md
Tests: tests/test_shell_*.py (pixel check along the right and bottom edges, Chromium and WebKit)
Gate: uv run python scripts/gate.py --specs shell --browsers chromium (then --browsers all for the pixel check)
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decisions: option A (the ring drawn by an aria-hidden overlay painted after the cells, as designed; no change of look, nothing to redraw), as the milestone's pitch says. Test-writer and implementer on Opus (painted pixels).

Lead's decisions: the ring keeps its built offset of -3 px (no change of look); AC-21 samples FX-01 rather than the review's 14 by 9 grid. Follow-up drafts: split shell.md (the visual foundation into its own file).
<!-- SECTION:NOTES:END -->
