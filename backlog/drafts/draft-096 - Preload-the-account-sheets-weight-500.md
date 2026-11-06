---
id: DRAFT-096
title: Preload the account sheet's weight 500
status: Draft
assignee: []
created_date: '2026-11-06T18:37:00Z'
labels:
  - follow-up
  - domain:foundation
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the investigation of 2026-11-05, item F, left out of B-105 (tooling): on a phone, the account sheet's first error line jumps from two lines to one because Source Sans 3 weight 500 loads only when that line appears. Preloading it on the pages that show the sheet removes the jump, with no change of look; it changes which pages preload (client/foundation.md rule 5, AC-16).
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
