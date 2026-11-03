---
id: DRAFT-063
title: Pen panning on a zoomed grid
status: Draft
assignee: []
created_date: '2026-11-03T13:32:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Grid and room screens » close, for the human's look. Since B-050 (L15), web/src/lib/pinchPan.ts:32 ignores every pointer but touch, so a pen no longer pans a zoomed grid (before, only a mouse was ignored). Either state « touch only » in specs/client/viewport.md rule 3, or restore pen panning; a criterion and its test either way. What players with a pen see: a product call.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
