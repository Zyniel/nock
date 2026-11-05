---
id: B-082
title: gameplay/results.md splits in two
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T17:06:00Z'
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
- [x] #1 results.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 results AC-17 to AC-20 move to gameplay/history.md as history AC-1 to AC-4
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
The new gameplay/history.md (domain history) takes « Finished grids »: results rules 14-19 as history rules 1-6, and results AC-17..20 as history AC-1..4, pointers unchanged. Rule 20 splits: results keeps the band, the dialog and the page; history rule 7 keeps the section's baselines. All four Edge cases move, and results gets one line of its own. Repoint _map.md (new row, glossary), _settings.md:23, account.md:22, erasure.md:110 and :263, library.md:74 and :280, summaries.md:22, :35 and :99, joining.md:252, host.md:137. results' Depends on swaps lobby/summaries.md for lobby/joining.md. gate.py: RoomPage.svelte gains history. No test moves.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut 1 (history) over Cut 2 (recap). It splits by topic, not by layer, matches the glossary's terms results and history, moves no test and changes no code. results ends near 14.6 KB with 19 criteria, at the line: the next results criterion should come from elsewhere. B-091 and B-095 now concern history as well as results.

Reviewer round 1: APPROVE. Taken: specs back to done. Not taken here: B-091 and B-095 gaining domain:history and specs/gameplay/history.md, which goes on a board branch since those are other tasks. Not taken: adding rules.md, account.md and rooms.md to history's Depends on, because the template's limit is three files and they are cited inline, as they were in results.

Full gate here (Chromium): static checks and 8,774 parallel tests green. Only foundation remote pace AC-13 failed (main-thread time per selection), as on B-080 and B-081: this container is too slow for it, and CI passed it for both. No test or code changed, so Firefox and WebKit are left to CI after the merge. After merging main (B-081), the shared-components check and the traceability gate passed again.

Pull request #143, auto-merge on.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
gameplay/results.md splits in two: the new gameplay/history.md (domain history) takes the finished grids, « Grilles terminées » and « Rejouer » (results rules 14-19 as history rules 1-6; results AC-17..20 as history AC-1..4, still proven by their 029 and 046 AC-13 pointers). Rule 20 splits, with history rule 7 keeping the section's baselines. results.md is 14.5 KB with 19 criteria, history.md 5.6 KB with 4. _map.md (new row, glossary, shared criteria), twelve citations in seven specs and gate.py's RoomPage.svelte entry follow. No test or code changed.
<!-- SECTION:FINAL_SUMMARY:END -->
