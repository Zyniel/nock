---
id: DRAFT-092
title: A test of the ping worker's error fallback
status: Draft
assignee: []
created_date: '2026-11-06T16:20:00Z'
labels:
  - follow-up
  - domain:reconnection
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-101's review and m-9's close: platform/reconnection.md rule 3 and its edge case say a page whose worker cannot be created or reports an error keeps the 2 s with its own timer, but only the no-Worker branch is tested (the frozen-clock harnesses). Test a worker asset answered 404 (onerror) and a throwing constructor: pings go on every 2 s, no 4408. The reviewer's probes showed both work today.
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
