---
id: B-110
title: Window sizes in layout criteria, one rule
status: To Do
assignee: []
created_date: '2026-11-05T22:21:00Z'
updated_date: '2026-11-09T04:50:00Z'
labels:
  - follow-up
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-076. Criteria name window sizes (360 by 740, 320 by 568, 1280 by 720) in about 12 files: hud 18 times, menus 9, viewport 6, cells 5, and others. _map.md « What a spec holds » keeps test mechanics out of specs, but a window size is the condition a layout criterion is about, what the player's screen is. Lead's call: _map.md names the window sizes a layout criterion may state (the phone, the small phone, the desktop) and says a criterion names them, not the test. Only _map.md changes, plus any size a criterion uses that is not on the list. Out of scope: rewording the criteria that already name a listed size.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _map.md « What a spec holds » lists the window sizes layout criteria may name, every size named in a domain spec is on the list, and the gate's traceability is green
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
