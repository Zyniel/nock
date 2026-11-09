---
id: B-116
title: gameplay/co-op.md under the size guide
status: To Do
assignee: []
created_date: '2026-11-09T18:05:00Z'
labels:
  - domain:co-op
  - domain:pencil
milestone: m-11
dependencies:
  - B-115
priority: low
ordinal: 94000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split from B-115 (the lead's call: both cuts do not fit one agent context; the milestone's last slot). gameplay/co-op.md is 16.4 KB with 21 criteria. Move one part, its criteria as they are, to a new domain spec; the Plan agent proposed the options during B-115, the lead picked the pencil cut (« Pencil mode and confirming » to gameplay/pencil.md). Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 co-op.md is under about 15 KB and 20 criteria, any moved part has its criteria and pointers, _map.md updated, the gate's traceability green
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
