---
id: B-082
title: gameplay/results.md splits in two
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T16:27:00Z'
labels:
  - domain:results
milestone: m-7
dependencies: []
documentation:
  - specs/gameplay/results.md
priority: medium
ordinal: 70000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. results is 19.4 KB with 23 criteria. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 results.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
- [ ] #2 results AC-17 to AC-20 move to gameplay/history.md as history AC-1 to AC-4
<!-- AC:END -->

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
The new gameplay/history.md (domain history) takes « Finished grids »: results rules 14-19 as history rules 1-6, and results AC-17..20 as history AC-1..4, pointers unchanged. Rule 20 splits: results keeps the band, the dialog and the page; history rule 7 keeps the section's baselines. All four Edge cases move, and results gets one line of its own. Repoint _map.md (new row, glossary), _settings.md:23, account.md:22, erasure.md:110 and :263, library.md:74 and :280, summaries.md:22, :35 and :99, joining.md:252, host.md:137. results' Depends on swaps lobby/summaries.md for lobby/joining.md. gate.py: RoomPage.svelte gains history. No test moves.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut 1 (history) over Cut 2 (recap). It splits by topic, not by layer, matches the glossary's terms results and history, moves no test and changes no code. results ends near 14.6 KB with 19 criteria, at the line: the next results criterion should come from elsewhere. B-091 and B-095 now concern history as well as results.
<!-- SECTION:NOTES:END -->
