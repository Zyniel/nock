---
id: DRAFT-108
title: Depends on sections after the m-11 splits
status: Draft
assignee: []
created_date: '2026-11-09T22:25:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the milestone review of m-11. The rules point at the new domains, but some « Depends on » lists still name only the old file, and agents load a task's files plus their Depends on: platform/reconnection.md (rule 1 cites fair-play rule 2 and pencil.md; Depends on lists realtime, joining, co-op), gameplay/rules.md (rule 6 cites pencil.md), platform/server.md (cites fair-play for the edit rate), lobby/creator.md and admin/operations.md (cite records rule 1). Spec-writer, no behaviour change.
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
