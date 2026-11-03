---
id: B-070
title: A status region empties after it spoke
status: To Do
assignee: []
created_date: '2026-11-03T16:02:00Z'
labels:
  - domain:hud
milestone: m-4
dependencies: []
documentation:
  - specs/client/hud.md
priority: medium
ordinal: 58000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-054 (B-046). The room page's role=status region and each open sheet's keep their last text for good (« Connexion perdue… » after the page reconnects, « Chargement du bilan… » after the recap loads), so a screen reader walking the page reads stale news. Lead's default: a region empties a few seconds after it is written, and a new message replaces the old at once. hud.md is past the budget: change rule 17 and widen AC-26 or AC-27. Out of scope: a real screen-reader check (DRAFT-065).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A status region is empty a few seconds after its last message, and still announces each new one
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
