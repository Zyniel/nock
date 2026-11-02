---
id: B-060
title: The vote leaves `gameplay/hints.md`
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T01:16:00Z'
labels:
  - domain:hints
  - domain:votes
  - domain:realtime
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
