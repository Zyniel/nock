---
id: DRAFT-031
title: Move the vote out of `gameplay/hints.md`
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:hints
  - domain:votes
  - domain:realtime
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`gameplay/hints.md` is over the size guideline (about 21 KB, 23 criteria after B-031): the spec-writer proposes moving the vote and its banner (rules 14 to 22, AC-13 to AC-20, with their pointers) to a new `gameplay/votes.md`, an architecture decision. `platform/realtime.md` is over too (about 19 KB, 20 criteria).
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
