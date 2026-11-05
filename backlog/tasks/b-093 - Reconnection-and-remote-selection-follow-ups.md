---
id: B-093
title: Reconnection and remote selection follow-ups
status: To Do
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T01:54:00Z'
labels:
  - domain:reconnection
  - domain:presence
milestone: m-10
dependencies: []
documentation:
  - specs/platform/reconnection.md
  - specs/social/presence.md
priority: low
ordinal: 81000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-044 and DRAFT-046: the two lead's decisions of B-041 get criteria (a queued request kept again, the dying socket's request), and the reuse of remotesByCell gets a guard.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The two B-041 decisions and the remotesByCell reuse each have a criterion and a test that fails without them
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
