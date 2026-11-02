---
id: B-064
title: Citations repointed after the spec splits
status: To Do
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T01:16:00Z'
labels:
  - domain:host
  - domain:lifetime
  - domain:results
  - domain:library
  - domain:hud
  - domain:chat
  - domain:room
milestone: m-2
dependencies:
  - B-060
  - B-061
  - B-062
priority: low
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: lobby/host, lobby/lifetime, gameplay/results, content/library, client/hud, social/chat, client/room (one-line citations only)
- Architecture decision: no
- Model: spec-writer on Sonnet (medium); no tests change.
- Problem: the splits of « Spec splits » leave one-line citations that name the old file: host (account rules 18 and 22), lifetime (account rules 20 and 26), results (account rule 18), library (account rule 24), hud's « Depends on » (the grid and its fit, now viewport), chat and room (hints for the vote's banner and its line, now votes).
- In scope: those citations point to the new files and their new numbers. Past three domain files, the lead's exception: one-line citations, no rule's text changes.
- Out of scope: any change of behaviour, rule or criterion.
- Screens: none.
- Open questions: none.
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
