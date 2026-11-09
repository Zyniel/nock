---
id: B-115
title: platform/realtime.md and gameplay/co-op.md under the size guide
status: To Do
assignee: []
created_date: '2026-11-05T22:33:00Z'
updated_date: '2026-11-09T04:50:00Z'
labels:
  - domain:realtime
  - domain:co-op
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-079. platform/realtime.md is 17.7 KB with 19 criteria and gameplay/co-op.md 16.4 KB with 21 criteria. Tighten or move one part of each, its criteria as they are, to a new domain spec; the Plan agent proposes the options, the lead picks. If both do not fit one agent context, the lead splits the task within the milestone's budget. The other files over the guide (hud, catch-up, rules, joining, viewport, the _design files) stay in a draft. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 realtime.md and co-op.md are each under about 15 KB and 20 criteria, any moved part has its criteria and pointers, _map.md updated, the gate's traceability green
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
