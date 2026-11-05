---
id: B-105
title: The fonts' preload through a ?url import
status: To Do
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-05T22:21:00Z'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), item F: on a phone, the account sheet's first error line jumps from two lines to one, because Source Sans 3 weight 500 loads only when that line appears. Preloading weight 500 with the other faces removes the jump, with no change of look.
<!-- SECTION:NOTES:END -->
