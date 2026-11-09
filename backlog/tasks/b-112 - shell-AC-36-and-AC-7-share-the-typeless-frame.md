---
id: B-112
title: shell's typeless frame in one criterion
status: To Do
assignee: []
created_date: '2026-11-06T13:46:00Z'
updated_date: '2026-11-09T04:50:00Z'
labels:
  - domain:shell
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-083 (B-097's review). client/shell.md AC-7 lists {"seq": 6} among the frames that change nothing and AC-36 proves it apart from event 6. Keep the typeless frame in one criterion. Also: AC-36's binary case tells a decoded frame only by a check after SETTLE_MS (300 ms); make its test tell it by an effect. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The typeless frame is in one criterion of shell.md, its test proves it, and the other criterion no longer lists it
- [ ] #2 AC-36's binary case is proven without waiting a fixed delay
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
