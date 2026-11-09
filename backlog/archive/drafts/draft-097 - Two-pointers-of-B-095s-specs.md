---
id: DRAFT-097
title: Two pointers of B-095's specs
status: Draft
assignee: []
created_date: '2026-11-06T18:37:00Z'
labels:
  - follow-up
  - domain:summaries
  - domain:history
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-095's review: lobby/summaries.md's Tests line « tests/test_spec_032_ac03_ac05_* (AC-5) » now reads as the domain's own AC-5 and should say « (032 AC-5) »; gameplay/history.md's edge case « Two erased team-mates read « Ancien joueur » twice » points at summaries AC-5 and erasure AC-18, which check the server's answer only: say « -- twice » or point at displayNickname's tests.
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
