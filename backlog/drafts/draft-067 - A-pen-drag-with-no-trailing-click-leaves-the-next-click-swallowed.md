---
id: DRAFT-067
title: A pen drag with no trailing click leaves the next click swallowed
status: Draft
assignee: []
created_date: '2026-11-05T05:01:00Z'
labels:
  - follow-up
  - domain:viewport
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the close of « Owner's calls »: in web/src/lib/pinchPan.ts, isPenDragged stays true when an engine fires no click after a captured pen drag, so the next keyboard or assistive-technology click inside the viewport is dropped until the next pointer press. Clear the flag on the next pointerdown, keydown or a short timeout, with a test.
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
