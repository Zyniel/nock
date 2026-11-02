---
id: B-060
title: The vote leaves `gameplay/hints.md`
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T11:42:00Z'
labels:
  - domain:hints
  - domain:votes
  - domain:realtime
  - domain:hud
milestone: m-3
dependencies:
  - B-057
documentation:
  - specs/gameplay/hints.md
  - specs/platform/realtime.md
priority: medium
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: gameplay/hints → gameplay/votes (new); platform/realtime (rules 7 and 10 name hints for `vote`, `vote_opened`, `vote_closed`, `vote_in_progress`, `no_open_vote`)
- Architecture decision: yes (a new domain), approved by the merge of the « Spec splits » pitch; the spec-writer runs on Fable at high effort.
- Model: spec-writer on Fable (high); test-writer on Sonnet; no implementer (no code changes).
- Problem: `gameplay/hints.md` is 20.3 KB with 25 criteria, past the budget of `specs/_map.md`.
- In scope: rules 14 to 22 (the vote, its banner) and AC-13 to AC-20 and AC-25 move to `gameplay/votes.md`, about 8.7 KB and 9 criteria, with five of the six edge cases; hints rule 1's « (rule 14) » becomes a file citation; `tests/test_hints_vote_focus.py` is renamed; the pointers of 025 and 047 move; `_map.md`'s note on 047 AC-13 and AC-14 names votes. Hints's citations of realtime rules 20 and 22 point to `platform/reconnection.md`. A moved criterion takes the next free number of the new file and its tests are renamed and moved to the new domain's test files; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps allowed). `specs/_map.md`: the new row, the split « From the v1.1.0 specs » cell, a glossary line next to its related term.
- Out of scope: any change of behaviour or code; the citations by name in chat and room (B-064).
- Screens: none.
- Open questions: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 votes AC-1 (new, was hints AC-13)
- [ ] #2 hints AC-13 (deleted, moved to votes AC-1)
- [ ] #3 votes AC-2 (new, was hints AC-14)
- [ ] #4 hints AC-14 (deleted, moved to votes AC-2)
- [ ] #5 votes AC-3 (new, was hints AC-15)
- [ ] #6 hints AC-15 (deleted, moved to votes AC-3)
- [ ] #7 votes AC-4 (new, was hints AC-16)
- [ ] #8 hints AC-16 (deleted, moved to votes AC-4)
- [ ] #9 votes AC-5 (new, was hints AC-17)
- [ ] #10 hints AC-17 (deleted, moved to votes AC-5)
- [ ] #11 votes AC-6 (new, was hints AC-18)
- [ ] #12 hints AC-18 (deleted, moved to votes AC-6)
- [ ] #13 votes AC-7 (new, was hints AC-19)
- [ ] #14 hints AC-19 (deleted, moved to votes AC-7)
- [ ] #15 votes AC-8 (new, was hints AC-20)
- [ ] #16 hints AC-20 (deleted, moved to votes AC-8)
- [ ] #17 votes AC-9 (new, was hints AC-25)
- [ ] #18 hints AC-25 (deleted, moved to votes AC-9)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: gameplay/hints.md → gameplay/votes.md (new), platform/realtime.md rules 7 and 10, specs/_map.md; hints's realtime 20/22 citations → reconnection rules 5/7.
2. Tests: tests/test_hints_vote_focus.py renamed to tests/test_votes_*.py, renamed to the new numbers.
3. Quick gate: uv run python scripts/gate.py --specs hints,votes,realtime --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): started alongside B-058 (no shared domain). Spec-writer on Fable at high (new domain). hints.md's citations of realtime rules 20 and 22 go to reconnection rules 5 and 7 (B-057's map). Base: origin/main f6a5666.

Lead: hud.md:168 cited hints rule 21 by number: repointed to votes rule 8 here; the task takes domain:hud. Spec-checker APPROVED in round 1; its optional notes left (hints' Depends on, at three files, does not list votes; realtime rule 7 gained '(a ballot)', the glossary term). By-name citations of the vote left: chat.md:101/:139, room.md:144 (B-064's list); rules.md:43, server.md:81, presence.md:278, product.md:36 (not on B-064's list: the lead adds them there on the next board branch). votes' Code section names RoomPage.svelte: B-055's map must follow when both are on main.
<!-- SECTION:NOTES:END -->
