---
id: B-105
title: The fonts' preload through a ?url import
status: In Progress
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T18:29:00Z'
labels:
  - tooling
milestone: m-10
dependencies: []
priority: low
ordinal: 93000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-050 (B-050, #95). The fonts' preload names a node_modules path; a Vite ?url import of the @fontsource file follows the package's own path. No change players see.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The preload's href comes from a ?url import of the @fontsource file, and the fonts' tests pass
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
Tooling (no spec): web/src/lib/fontPreload.ts takes the two faces' addresses from ?url imports of each @fontsource package's files/ export instead of new URL over a node_modules path. Check: svelte-check, build (the preloads name the same hashed files as the CSS), tests/test_foundation_fonts.py, full gate.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), item F: on a phone, the account sheet's first error line jumps from two lines to one, because Source Sans 3 weight 500 loads only when that line appears. Preloading weight 500 with the other faces removes the jump, with no change of look.

Built by the lead (tooling). The build's RoomPage chunk names source-sans-3-latin-500-normal-<hash> and ibm-plex-sans-condensed-latin-600-normal-<hash>, the files the faces' CSS names; tests/test_foundation_fonts.py 8 passed. Not in this task: the investigation's item F (preload Source Sans 3 weight 500 on the pages with the account sheet, against the error line's jump) changes which pages preload (foundation rule 5, AC-16), a spec change: a follow-up draft.
<!-- SECTION:NOTES:END -->
