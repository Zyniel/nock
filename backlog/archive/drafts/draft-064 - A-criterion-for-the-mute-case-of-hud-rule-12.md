---
id: DRAFT-064
title: A criterion for the mute case of hud rule 12
status: Draft
assignee: []
created_date: '2026-11-03T13:32:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Grid and room screens » close. specs/client/hud.md rule 12 (about lines 105-107): when the page itself moves the focus out of the Salon sheet (the mute case), the sheet stays open; this has no criterion of its own, and a full gate once caught a regression there through 022 AC-18 only. Add a hud criterion and its browser test. The rule's other limit (a Tab from the browser's own controls closes the sheet only on the next Tab inside the page) was the lead's decision in B-045.
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
