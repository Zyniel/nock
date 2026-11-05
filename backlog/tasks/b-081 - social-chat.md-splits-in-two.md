---
id: B-081
title: social/chat.md splits in two
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T16:12:00Z'
labels:
  - domain:chat
milestone: m-7
dependencies: []
documentation:
  - specs/social/chat.md
priority: medium
ordinal: 69000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. chat is 21.5 KB with 23 criteria; the spec-writer proposed social/stream (rules 18 to 20). Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 chat.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 reactions AC-1 to AC-10 (moved from chat AC-1 to AC-7, AC-10, AC-11, AC-22)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Plan agent (Fable, high) proposes the cut; the lead picks.
2. spec-writer moves the part to the new domain spec, _map.md follows; spec-checker.
3. Tests: rename or move the domain tests of moved criteria (after B-003 merges, which edits many test files).
4. No code change; reviewer; full gate; pull request.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision (Plan agent on Fable, three cuts): Cut C, social/reactions.md takes the clue flag (rules 1-6, AC-1 to AC-7, 021 whole) and the reactions (rules 12-14, AC-10, AC-11, AC-22; 022 AC-3 to AC-5), renumbered rules 1-9 and AC-1 to AC-10. chat goes to about 13.8 KB and 13 criteria, reactions about 9.4 KB and 10. Not taken: social/stream (rules 18-20) leaves chat 2.3 KB over and at 20 criteria; the flag alone leaves it 1.7 KB over. Cost: test_chat_connection.py's two test_ac22_* move to tests/test_reactions_connection.py as test_ac10_*.

Spec-checker: CHANGES REQUESTED in round 1 (escapes of chat AC-9 turned into real characters; the restart sentence moved with the reactions), APPROVED in round 2. Lead decision: the restart sentence split, chat rule 7 keeps the chat window, reactions rule 7 the reaction window. chat 13.8 KB and 13 criteria, reactions 9.2 KB and 10.

Review round 1: APPROVE. Taken: the helpers both test files share move to spec022_harness.py (no test imports a test module). Not taken: re-wrapping a few lines after the inserted links (cosmetic).

Full gate here: Chromium static checks and 8,774 parallel tests green. The same two timing tests failed as on B-080 (foundation remote pace AC-13, spec 036 AC-1): this container is too slow for them, and B-080's CI passed them. The moved tests pass in Firefox and WebKit (8 passed). After main took B-080, the merge conflicted only in hud.md's Related list: the resolution keeps both the reactions pointer and the menus line. The traceability gate and the moved tests passed again after the merge.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
social/chat.md splits in two: the new social/reactions.md takes the reactions (chat rules 1-6 and 12-14 as reactions rules 1-9; chat AC-1..7, AC-10, AC-11, AC-22 as reactions AC-1..10). The restart sentence splits between chat rule 7 (chat window) and reactions rule 7 (reaction window), and server rule 6 cites both. chat.md is 13.8 KB with 13 criteria, reactions.md 9.2 KB with 10. The AC-22 tests move to tests/test_reactions_connection.py as test_ac10_*, their helpers to tests/spec022_harness.py; _map.md, citations, gate.py's shared components and one code comment follow.
<!-- SECTION:FINAL_SUMMARY:END -->
