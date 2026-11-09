---
id: DRAFT-107
title: Specs still over the size guide after m-11
status: Draft
assignee: []
created_date: '2026-11-09T22:22:00Z'
updated_date: '2026-11-09T22:25:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-079 (m-11 took realtime, co-op and erasure). Over the ~15 KB / 20-criteria guide of specs/_map.md on 2026-11-09: gameplay/rules.md 15.6 KB, 20 criteria; lobby/joining.md 15.5 KB; client/shell.md 21 criteria; gameplay/viewport.md 21 criteria; social/catch-up.md 21 criteria; the _design files cells.md 18 KB, room.md 20 KB, foundation.md 27 KB. client/hud.md is DRAFT-084. Each needs a cut or a tightening, proposed by the Plan agent (a split adds a domain: an architecture decision).
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
m-11's review: platform/realtime.md is 15,338 bytes at its close (B-116 added the pencil.md line to rule 7), at the edge of the guide: its next addition takes it over.
<!-- SECTION:NOTES:END -->
