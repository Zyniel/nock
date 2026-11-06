---
id: B-095
title: Spec 029's leftovers
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T18:01:00Z'
labels:
  - domain:erasure
  - domain:history
  - domain:summaries
milestone: m-10
dependencies: []
documentation:
  - specs/account/erasure.md
  - specs/gameplay/history.md
priority: low
ordinal: 83000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-015: a history save across an erasure, the delete hook's SQLite write under the registry lock, two erased team-mates shown as one, the summary asked once, peek_room re-reading old logs. Decide each, fix what is cheap.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each leftover of DRAFT-015 is fixed with a test or stated in the spec as it is
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: account/erasure.md, gameplay/history.md, lobby/summaries.md: each of the five leftovers fixed with a criterion or stated as it is
Tests: tests/test_erasure_*.py, tests/test_history_*.py, tests/test_summaries_*.py
Quick gate: uv run python scripts/gate.py --specs erasure,history,summaries --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decisions: (1) the history save across a done erasure is stated (rule 9 now « writes while it is pending », an edge case); the fix (the route's read and save under the registry lock) costs a SQLite write under that lock per signed-in catalogue load for a very unlikely race; (2) the delete hook's write under the registry lock is stated with its observable effects (it is what keeps the hook safe from an erasure); (3) fixed: one -- per erased member, in team_nicknames too (so « Mes salons » and the device's records match the account's), erasure AC-18 and summaries AC-5; (4) the summary asked once is stated (the catalogue writes the record from « Mes salons » at its next load); (5) peek_room's re-read of old logs is stated (unobservable, the rooms age out). erasure.md reaching ~16 KB: a split of « History records » into its own domain is an architecture change for the human, filed as a follow-up draft rather than done here.

Spec-checker APPROVED (round 1). Corrections to the note above: the size follow-up is the existing DRAFT-069 (erasure.md back under the size budget), updated with the new size (17,464 bytes) rather than a new draft; summaries.md is touched (rule 1 lists the members), so the task takes domain:summaries. Lead's calls on the checker's notes: « fails the hook » wording and the two long lines fixed by the spec-writer before the commit; the cheaper fix of leftover 1 (lock only when no record exists) is not taken, the task allows stating it; the dropped -- team-mates on an erased player's own device (history rule 3, older) go to a follow-up draft.
<!-- SECTION:NOTES:END -->
