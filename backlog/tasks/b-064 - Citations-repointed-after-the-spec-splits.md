---
id: B-064
title: Citations repointed after the spec splits
status: In Progress
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T17:58:00Z'
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
  - domain:account
  - domain:rules
  - domain:server
  - domain:presence
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: one-line citations in the files of the task's labels repointed to the split files (erasure, foundation, summaries, votes, viewport, reconnection) and their new numbers; no rule text changes.
2. Tests: none change.
3. Quick gate: uv run python scripts/gate.py --stage tests (no test or code changes), then the full gate.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02, after B-058, B-059, B-060, B-062): citations by name the closed splits listed for this task, beyond the description's list (file:line as of each split's branch; recheck after the merges):
- B-062 (erasure): host.md:99/129/136/138, lifetime.md:85, results.md:153, library.md:53 (by number, in the description); joining.md:42 and product.md's routes were repointed by B-062 itself.
- B-058 (foundation): results.md:300 « The page frame and state lines: client/shell.md » (state lines are foundation rule 1).
- B-059 (summaries): results.md:20 (Depends on: summaries in joining), lifetime.md:222-223, library.md:264, hud.md:85-86 (« Mes salons » in joining), account.md:18/107/294 (« Mes salons », summaries).
- B-060 (votes): chat.md:101/:139, room.md:144 (in the description); rules.md:43, server.md:81, presence.md:278, product.md:36 (the vote, still hints).
The task takes domain:account, rules, server and presence for these one-line citations.

Lead (2026-11-02, after B-061): add specs/social/presence.md:20 (Depends on: « gameplay/board.md: the grid, … » — the grid is now gameplay/viewport.md).

Lead (2026-11-02): started after B-058 to B-062 and B-047 merged; B-063 (in progress) keeps operations' own citations. Spec-writer on Sonnet at medium, as the task says. Base: origin/main b9871e7.

Lead: spec-checker CHANGES REQUESTED in round 1 (three « Depends on » entries, in host, library and hud, had replaced a dependency the rules still lean on; fixed by keeping both in one entry; its optional note taken: host.md:99, :138 and results.md:153 cite erasure rules 1, 5), APPROVED in round 2. The spec-writer's grep added presence.md:18-19 and :277-278, rules.md:43, server.md:81 and account.md:18. Left: shell.md and joining.md already cite reconnection (B-047); account.md:107 and :294 name « Mes salons » in running text with no file. B-063 (in progress) reverted five one-line repoints in server.md, product.md, results.md and shell.md, whose domains this task holds; this task takes them after B-063 merges.

Lead: after B-063 merged (#110), the five repoints it left here were applied (server.md:269-270, product.md:44-45 and :60, results.md:136, shell.md:225), text exactly as B-063's spec-checker approved them in its round 1 before they were reverted there; no second spec check. shell.md (was done) is now approved with the rest.
<!-- SECTION:NOTES:END -->
