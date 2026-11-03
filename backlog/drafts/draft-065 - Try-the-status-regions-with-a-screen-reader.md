---
id: DRAFT-065
title: Try the status regions with a screen reader
status: Draft
assignee: []
created_date: '2026-11-03T13:32:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Grid and room screens » close. B-046's one live status region per page and per sheet is proven only by MutationObserver tests; it has never been heard in a real screen reader. A one-off manual check by the human with NVDA (Windows) or VoiceOver: join a room, undo, a vote, a lost connection, a solved grid; note what is read twice or not at all. Related: DRAFT-054 (regions keep their last text), DRAFT-048 (the glossary).
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
