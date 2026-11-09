---
id: B-116
title: gameplay/co-op.md under the size guide
status: In Progress
assignee: []
created_date: '2026-11-09T18:05:00Z'
updated_date: '2026-11-09T20:55:00Z'
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
- [ ] #1 co-op.md is under about 15 KB and 20 criteria, any moved part has its criteria and pointers, _map.md updated, the gate's traceability green
- [ ] #2 pencil AC-1 (moved from co-op AC-10)
- [ ] #3 pencil AC-2 (moved from co-op AC-11)
- [ ] #4 pencil AC-3 (moved from co-op AC-12)
- [ ] #5 pencil AC-4 (moved from co-op AC-13)
- [ ] #6 pencil AC-5 (moved from co-op AC-14)
- [ ] #7 pencil AC-6 (moved from co-op AC-15)
- [ ] #8 pencil AC-7 (moved from co-op AC-16)
- [ ] #9 pencil AC-8 (moved from co-op AC-17)
- [ ] #10 pencil AC-9 (moved from co-op AC-18)
- [ ] #11 pencil AC-10 (moved from co-op AC-19)
- [ ] #12 pencil AC-11 (moved from co-op AC-20)
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
Specs: specs/gameplay/co-op.md, new specs/gameplay/pencil.md, specs/_map.md, the specs citing co-op's pencil rules; scripts/gate.py SHARED_COMPONENT_DOMAINS (lead) if the Code sections change
Tests: none expected (AC-10 to AC-20 are pointers to 020)
Gate: uv run python scripts/gate.py --specs co-op,pencil --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's pick among the Plan agent's options (Fable, high, during B-115): C1, move co-op's « Pencil mode and confirming » (rules 7-9, AC-10 to AC-20, all pointers to 020) to a new domain gameplay/pencil.md, criteria renumbered AC-1 to AC-11, text unchanged. Rejected: C2 (the page's grid rules to a pending-edits domain: mixes server and page, overlaps shell and reconnection); C3 (a narrower pencil cut that splits 020's pointers across two domains). The pitch names each split adding a domain.

Lead (tooling coherence, the gate's static check demands it): scripts/gate.py SHARED_COMPONENT_DOMAINS follows the Code sections: pencil added to LetterCell.svelte and RoomPage.svelte; RoomTopBar.svelte now hud, pencil, rules, server (co-op's Code no longer names it). AideMenu.svelte and InAppKeyboard.svelte stay under four domains: no entry.

Spec-checker APPROVED. co-op.md 9,968 bytes, 10 criteria; pencil.md 7,987 bytes, 11 criteria. Its three wording notes taken (pencil Out of scope names the co-op rules its AC-1, AC-3, AC-4, AC-6 to AC-9 give pencil cases of; co-op Purpose and Code). No test renamed: every moved criterion points at 020.
<!-- SECTION:NOTES:END -->
