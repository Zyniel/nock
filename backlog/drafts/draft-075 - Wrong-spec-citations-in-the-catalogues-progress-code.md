---
id: DRAFT-075
title: Wrong spec citations in the catalogue's progress code
status: Draft
assignee: []
created_date: '2026-11-05T22:21:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-087's spec-checker and reviewer. web/src/lib/CataloguePage.svelte:44 and web/src/lib/catalogue.ts:67 say '(spec 004 rule 7)' about the account's progress, but spec 004's rule 7 is the force query. Both should cite content/cards.md rule 1. Comment-only, for m-8.
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
