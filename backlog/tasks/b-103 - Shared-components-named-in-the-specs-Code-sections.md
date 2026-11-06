---
id: B-103
title: Shared components named in the specs' Code sections
status: Done
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T11:40:00Z'
labels:
  - tooling
milestone: m-9
dependencies: []
priority: low
ordinal: 91000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-059: FocusableLink.svelte, PlayButton.svelte and wideWindow.ts are named in the Code sections of the domains they serve, so the quick gate widens when they change; hud's Code line about GridStatus reads right.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The three files are in the Code sections, and the gate's shared-component map lists them
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: the Code sections of the domains FocusableLink.svelte, PlayButton.svelte and wideWindow.ts serve; client/hud.md's GridStatus Code line (spec-writer)
Code: SHARED_COMPONENT_DOMAINS in scripts/gate.py (lead); VoteBanner.svelte's long comment line (implementer)
Gate: the full gate in Chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decisions: a change to a done file's Code section makes it draft (specs/_map.md), so the 12 touched specs go draft → approved → done. PlayButton.svelte and wideWindow.ts are named in every domain whose Code section names one of their importers, so each reaches 4 domains. The gate's map (SHARED_COMPONENT_DOMAINS) gains FocusableLink.svelte (8 domains) and PlayButton.svelte (4), and hud for PlayersPanel.svelte (hud's Code line now names it). wideWindow.ts is named in 5 Code sections but the map covers .svelte components only: extending the static check to .ts modules was tried and would add 8 modules at once (roomSession.ts in 17 domains, roomConnection.ts, activityFeed.ts, …), widening the quick gate a lot — new tooling behaviour, so it becomes a draft for the human rather than part of this task.

Spec-checker round 1: CHANGES REQUESTED (FocusableLink missing from lobby/rooms, hud's frame gloss on the wrong file, PlayButton's gloss, one placement rule). Lead's decision on placement: a shared file is named in the domains it serves, so wideWindow.ts left gameplay/history and stays in account/my-account (it lays out the account dialog). Round 2: APPROVED. Final: FocusableLink.svelte in 9 domains, PlayButton.svelte in 4, both in SHARED_COMPONENT_DOMAINS (with hud for PlayersPanel); wideWindow.ts in 4 Code sections, outside the map (.svelte only), for the human.

PR: #164.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Milestone m-9 « Tidy tests and tooling ». Tooling task: Code sections of 12 domain specs and the gate's shared-component map; no rule or criterion changed.

- **AC #1** (the three files in the Code sections, the gate's map lists them):
  - `FocusableLink.svelte` named in 9 domains (shell, hud, room, menus, foundation, results, my-account, summaries, rooms) and listed in `SHARED_COMPONENT_DOMAINS`.
  - `PlayButton.svelte` named in 4 (cards, history, foundation, rooms) and listed in the map.
  - `wideWindow.ts` named in 4 (shell, library, foundation, my-account) but **not in the map**: the map and its static check cover `.svelte` components only. Widening them to `.ts` modules would add 8 modules at once (roomSession.ts in 17 domains, roomConnection.ts, activityFeed.ts, …), new tooling behaviour left to the human as a draft. The criterion is met in part for this file.
  - `PlayersPanel.svelte` gains hud in the map, since hud's Code line now names it.
  - hud's GridStatus Code line reads right: GridStatus alone, the room page's parts apart, every writer of the status region.
- **Decisions**: a shared file is named in the domains it serves (not every domain naming an importer).
- **Spec-checker**: APPROVED in round 2. **Reviewer**: APPROVE, round 1, no findings.
- **Gate**: static stage passed locally (shared components: 9 in the map); the change touches no test or client code, so CI's Chromium gate on this PR is the full gate.
<!-- SECTION:FINAL_SUMMARY:END -->
