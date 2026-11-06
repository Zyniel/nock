---
id: DRAFT-083
title: shell AC-36 and AC-7 share the typeless frame
status: Draft
assignee: []
created_date: '2026-11-06T13:46:00Z'
labels:
  - follow-up
  - domain:shell
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-097's review: AC-7 lists {"seq": 6} among the frames that change nothing and AC-36 proves it apart from event 6. Keep the typeless frame in one criterion, or strengthen 040 AC-19's test to check seq 5 before event 6. Also: AC-36's binary case tells a decoded frame only by a check after SETTLE_MS (300 ms).
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
