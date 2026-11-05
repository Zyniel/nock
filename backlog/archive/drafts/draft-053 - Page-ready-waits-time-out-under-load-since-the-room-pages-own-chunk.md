---
id: DRAFT-053
title: Page-ready waits time out under load since the room page's own chunk
status: Draft
assignee: []
created_date: '2026-11-02T08:22:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-050 (#95). The room page's code now loads as its own chunk, one round trip after the entry script (rule 22 on the room route: 1246 ms → about 1570 ms, limit 2500 ms). Under heavy parallel load, waits for the room page's first state timed out six times (014 AC-7, 013 AC-7, 044 AC-2, host AC-10, 041 AC-3, 035 AC-6), each green alone. Options: a longer page-ready wait in the harness, a preload of the room chunk, fewer workers. See DRAFT-024.
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
