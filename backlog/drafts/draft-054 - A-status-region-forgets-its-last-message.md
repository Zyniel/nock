---
id: DRAFT-054
title: A status region forgets its last message
status: Draft
assignee: []
created_date: '2026-11-02T08:21:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-046 (#94). The room page's role=status region and each open sheet's keep their last text for good: « Connexion perdue… » after the page reconnects, « Chargement du bilan… » after the recap loads (or written after it when the fetch answers within 50 ms). A screen reader that walks the page reads stale news. Option: empty a region a few seconds after it is written. Domain: client/hud rule 17.
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
