---
id: DRAFT-045
title: B-044 small follow-ups
status: Draft
assignee: []
created_date: '2026-11-02T00:07:00Z'
labels:
  - follow-up
  - domain:board
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reviewer suggestions of B-044 not taken in the task:
- The scroll backwards is never tested: every zoomed test of board AC-23 to AC-29 scrolls right or down from the top-left corner, so a defect of the `marginStart < scroll` branch of `scrollShowingCell` (`web/src/lib/gridLayout.ts`) would pass every check. A criterion, for example ArrowLeft back along a word after a pan, and its test would guard it (a spec change: needs the spec-writer and the spec-checker).
- "(Chromium only, as AC-2)" in board AC-2 and AC-28 is test mechanics in the spec; best removed with the split of DRAFT-007.
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
