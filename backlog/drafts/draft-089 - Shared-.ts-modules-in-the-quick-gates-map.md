---
id: DRAFT-089
title: Shared .ts modules in the quick gate's map
status: Draft
assignee: []
created_date: '2026-11-06T13:46:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-103: SHARED_COMPONENT_DOMAINS and its static check cover .svelte components only, so wideWindow.ts (4 domains) does not widen the quick gate. Covering .ts modules was tried: it adds 8 at once (roomSession.ts in 17 domains, roomConnection.ts, activityFeed.ts, roomCommands.ts, gridKeys.ts, playFit.ts, wideWindow.ts), and a change to roomSession.ts would then run nearly the full gate. New tooling behaviour: the human's call.
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
