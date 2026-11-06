---
id: DRAFT-099
title: nock.history kept as stored by the history merge
status: Draft
assignee: []
created_date: '2026-11-06T20:55:00Z'
labels:
  - follow-up
  - domain:history
  - domain:my-account
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-092's review: web/src/lib/history.ts (around line 150) rewrites nock.history through readHistory when it merges new records, dropping the malformed items that a sign-out now keeps (my-account AC-11); gameplay/history.md should say which. Also: my-account AC-11's stored items are already in the kept order, so a filter that re-sorts would pass; store the UUUUUU item before the TTTTTT record to check « in its order ».
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
