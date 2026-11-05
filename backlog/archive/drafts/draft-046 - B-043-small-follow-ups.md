---
id: DRAFT-046
title: B-043 small follow-ups
status: Draft
assignee: []
created_date: '2026-11-02T00:07:00Z'
labels:
  - follow-up
  - domain:shell
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reviewer suggestions of B-043 not taken in the task:
- No test guards the reuse of previous values in `remotesByCell` (`web/src/lib/remoteSelections.ts`): AC-27 sends selections in place, which never reach it, and the mutation counts of AC-22 to AC-24 pass either way since Svelte skips writes that change nothing. Deleting the reuse would make every cell re-run its template on every real cursor move with every test green. A criterion, for example a pace for frames that change a cell (Bob moving between two cells of his word, on the reference phone), would guard it.
- Every letter cell still builds a new `shown` object when any pending edit changes (`shownCellWith` in `GridViewport.svelte`), and `hyphenDrawingsOn` builds new edge arrays when my selection moves; Svelte stops them before the DOM and AC-26 passes, so it costs little. For B-049, when the cells become components.
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
