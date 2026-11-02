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
  - domain:co-op
  - domain:catch-up
  - domain:rooms
  - domain:shell
  - domain:joining
  - domain:product
milestone: m-2
dependencies:
  - B-058
  - B-059
  - B-060
  - B-061
  - B-062
priority: low
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: lobby/host, lobby/lifetime, gameplay/results, content/library, client/hud, social/chat, client/room, gameplay/co-op, social/catch-up, lobby/rooms, client/shell, lobby/joining, product (one-line citations only)
- Architecture decision: no
- Model: spec-writer on Sonnet (medium); no tests change.
- Problem: the splits of « Spec splits » leave one-line citations that name the old file: host (account rules 18 and 22), lifetime (account rules 20 and 26), results (account rule 18), library (account rule 24), hud's « Depends on » (the grid and its fit, now viewport), chat and room (hints for the vote's banner and its line, now votes). B-057 leaves citations by name of `platform/realtime.md` for what is now `platform/reconnection.md`: co-op (the stale rule and the pending edits), catch-up, rooms (resume and time-out), shell (losses, final closes, the band, wherever B-058 leaves those lines), joining (the resume window, after B-059), and `product.md` baseline 25 « Bounded clients » (« the page reconnects »).
- In scope: those citations point to the new files and their new numbers. Past three domain files, the lead's exception: one-line citations, no rule's text changes. `product.md` baseline 25 changes its pointer only, no value or other text, as the human's answer A on B-059's routes cell.
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
