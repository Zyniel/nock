---
id: B-101
title: Hidden tabs measured in three engines
status: To Do
assignee: []
created_date: '2026-11-05T01:54:00Z'
labels:
  - domain:reconnection
milestone: m-9
dependencies: []
documentation:
  - specs/platform/reconnection.md
priority: low
ordinal: 89000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-060: measure whether a real hidden tab's throttled pings let the server's 6 s silence close it, in Chromium, Firefox and WebKit, and apply what the measure calls for.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The measure is recorded in the task, and a hidden tab stays connected in the three engines, or the spec says what happens
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
