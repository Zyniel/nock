---
id: B-116
title: gameplay/co-op.md under the size guide
status: Done
assignee: []
created_date: '2026-11-09T18:05:00Z'
updated_date: '2026-11-09T21:31:00Z'
labels:
  - domain:co-op
  - domain:pencil
milestone: m-11
dependencies:
  - B-115
priority: low
ordinal: 94000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split from B-115 (the lead's call: both cuts do not fit one agent context; the milestone's last slot). gameplay/co-op.md is 16.4 KB with 21 criteria. Move one part, its criteria as they are, to a new domain spec; the Plan agent proposed the options during B-115, the lead picked the pencil cut (« Pencil mode and confirming » to gameplay/pencil.md). Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 co-op.md is under about 15 KB and 20 criteria, any moved part has its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 pencil AC-1 (moved from co-op AC-10)
- [x] #3 pencil AC-2 (moved from co-op AC-11)
- [x] #4 pencil AC-3 (moved from co-op AC-12)
- [x] #5 pencil AC-4 (moved from co-op AC-13)
- [x] #6 pencil AC-5 (moved from co-op AC-14)
- [x] #7 pencil AC-6 (moved from co-op AC-15)
- [x] #8 pencil AC-7 (moved from co-op AC-16)
- [x] #9 pencil AC-8 (moved from co-op AC-17)
- [x] #10 pencil AC-9 (moved from co-op AC-18)
- [x] #11 pencil AC-10 (moved from co-op AC-19)
- [x] #12 pencil AC-11 (moved from co-op AC-20)
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
Specs: specs/gameplay/co-op.md, new specs/gameplay/pencil.md, specs/_map.md, the specs citing co-op's pencil rules; scripts/gate.py SHARED_COMPONENT_DOMAINS (lead) if the Code sections change
Tests: none expected (AC-10 to AC-20 are pointers to 020)
Gate: uv run python scripts/gate.py --specs co-op,pencil --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's pick among the Plan agent's options (Fable, high, during B-115): C1, move co-op's « Pencil mode and confirming » (rules 7-9, AC-10 to AC-20, all pointers to 020) to a new domain gameplay/pencil.md, criteria renumbered AC-1 to AC-11, text unchanged. Rejected: C2 (the page's grid rules to a pending-edits domain: mixes server and page, overlaps shell and reconnection); C3 (a narrower pencil cut that splits 020's pointers across two domains). The pitch names each split adding a domain.

Lead (tooling coherence, the gate's static check demands it): scripts/gate.py SHARED_COMPONENT_DOMAINS follows the Code sections: pencil added to LetterCell.svelte and RoomPage.svelte; RoomTopBar.svelte now hud, pencil, rules, server (co-op's Code no longer names it). AideMenu.svelte and InAppKeyboard.svelte stay under four domains: no entry.

Spec-checker APPROVED. co-op.md 9,968 bytes, 10 criteria; pencil.md 7,987 bytes, 11 criteria. Its three wording notes taken (pencil Out of scope names the co-op rules its AC-1, AC-3, AC-4, AC-6 to AC-9 give pencil cases of; co-op Purpose and Code). No test renamed: every moved criterion points at 020.

Reviewer: APPROVE in one round. Sizes on disk at HEAD: co-op.md 9,938 bytes, pencil.md 8,032 bytes (the earlier figures were before the wording notes). Cosmetic reflows (hud.md:48, board.md:223, viewport.md:209, _map.md:136) and an « erase » word in board.md's Depends on left for a follow-up draft.

Pull request: https://github.com/Zyniel/nock/pull/189
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
No behaviour change. Architecture decision: the Plan agent (Fable, high, during B-115) gave three options for co-op.md; the lead picked C1, a new domain gameplay/pencil.md (the pitch names each split adding a domain). Split from B-115 in the milestone's last slot.
- #1 co-op.md is 9,938 bytes with 10 criteria (was 16.4 KB, 21); pencil.md 8,032 bytes, 11 criteria. Moved word for word: co-op rules 7-9 -> pencil rules 1-3; co-op AC-10 to AC-20 -> pencil AC-1 to AC-11, each with its pointer to 020 (proven by tests/test_spec_020_*, no test moved); the pencil Look lines, two edge cases, an Out of scope sentence and Code lines. co-op keeps rules 1-6, 10-13 and AC-1 to AC-9, AC-21. _map.md: co-op row rewritten, pencil row, glossary row. Pointers fixed in board, rules, viewport, hud, menus, authorship, realtime, reconnection.
- Tooling (lead, the static check demands it): scripts/gate.py SHARED_COMPONENT_DOMAINS follows the Code sections (pencil in LetterCell.svelte and RoomPage.svelte; RoomTopBar.svelte now hud, pencil, rules, server).
- Spec-checker APPROVED; its three wording notes taken. Reviewer: APPROVE in one round.
- Full gate: GATE PASSED (full), 8915 parallel and 147 serial tests.
- Follow-up draft: cosmetic reflows (hud.md:48, board.md:223, viewport.md:209, _map.md:136) and « erase » in board.md's Depends on.
<!-- SECTION:FINAL_SUMMARY:END -->
