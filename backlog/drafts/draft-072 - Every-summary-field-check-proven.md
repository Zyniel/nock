---
id: DRAFT-072
title: Every summary field check proven
status: Draft
assignee: []
created_date: '2026-11-03T22:36:00Z'
labels:
  - follow-up
  - domain:library
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Test gaps » close. isGridSummary (web/src/lib/catalogue.ts) checks the types of number, force, width and height too, but only published_on and word_count are tested, so dropping any of the other four checks passes. Library rule 8 (« anything but a list of summaries ») is only sampled. A parametrised unit test in tests/web/ would cover them cheaply.
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
