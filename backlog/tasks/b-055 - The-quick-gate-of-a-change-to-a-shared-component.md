---
id: B-055
title: The quick gate of a change to a shared component
status: Done
assignee: []
created_date: '2026-11-02T00:07:00Z'
updated_date: '2026-11-02T11:35:00Z'
labels:
  - tooling
milestone: m-2
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Who decides: the human took option A (2026-11-02, in chat); tooling, built by the lead.
- Domains: none (tooling: `scripts/hooks/role_gate.py` and the quick gate of `scripts/gate.py`)
- Architecture decision: no (a list the gate reads)
- Criteria: none (tooling)
- Problem: the quick gate picks its browser tests from the domains and numbered specs a branch changes, but `RoomPage.svelte` and `GridViewport.svelte` serve nearly every domain. Three regressions of one round passed the quick gate and showed only in the full gate (B-041: product 035 AC-5 and board 007 AC-1; B-045: chat 022 AC-18, a mute closing the Salon sheet).
- In scope (option A): a map of the client components shared by several domains to the domains whose tests they serve; when a branch changes such a component, the role hook and the quick gate add those domains to the specs they run.
- Out of scope: option B (the full gate in the role hook for those files); option C (no change).
- Open questions:
  1. Where the map lives: A (lead's default) a constant of the gate's scripts, beside `SERIAL_TEST_FILES`; B a table in `specs/_map.md` that the gate reads.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. No spec (tooling): SHARED_COMPONENT_DOMAINS in scripts/gate.py; gate.py --specs and scripts/hooks/role_gate.py add the domains of the shared components the branch changed.
2. No tests (tooling; the repository has no tests of its scripts): probed by hand.
3. Gate: uv run python scripts/gate.py (full).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Human (2026-11-02, chat, answering the lead's wrap-up after B-043 to B-045): DRAFT-047 option A. Promoted to Upkeep as a tooling task.

Lead (2026-11-02): option A, the human's pick. The map lives in scripts/gate.py rather than gate_browsers.py (the lead's default said beside SERIAL_TEST_FILES): the role hook runs from the main checkout and loads the checked checkout's gate.py to read the map, and gate_browsers.py imports pytest and Playwright, which the hook should not load. The map is the domain specs whose Code section names the component: RoomPage.svelte 17 domains, GridViewport.svelte 9 (product included), PlayersPanel.svelte 5, RoomMenu.svelte 4, RoomTopBar.svelte 4; the other components are named by three domains at most and stay out. The quick gate run by hand (--specs) adds them too, printing what it adds, so the lead's quick gate and the hook's agree.

Lead: review round 1 CHANGES REQUESTED: product was missing from the map (specs/product.md is a domain spec whose Code section names RoomPage and GridViewport; only product points to 035, B-041's regression). Fixed, and a static check 'shared components' (stage tests) now keeps the map equal to the Code sections, so a spec change that makes a fourth domain name a component fails the gate until the lead updates the map. Suggestions taken: CLAUDE.md bullet moved and rewrapped, the two copies of the changed-paths logic name each other, the broad except says why.

Lead: review round 2 CHANGES REQUESTED: the check read only names written Name.svelte, while room.md and hud.md list parts with the suffix once (`Salon`, `PlayersPanel` (`.svelte`)), so PlayersPanel lacked room and RoomMenu and RoomTopBar (4 domains each) were missing. Fixed in the next commit: the check now takes any capitalised word of a Code section that names a .svelte file of web/src/, the map has 5 components, a domain listed twice fails, and the check is split in two functions. A second CHANGES REQUESTED is an escalation (stuck): the task is held for the human, its PR labelled needs-human, no auto-merge.

Human (2026-11-02, chat): option A, merge B-055 once CI is green. The lead records it, unassigns the task, removes needs-human and turns on auto-merge.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-02T11:16:00Z

---

Stuck (two review rounds ended in CHANGES REQUESTED). Question: accept B-055 as fixed after round 2, or send it for a third round? Round 1: product missing from the map (fixed, plus a static check that keeps the map equal to the specs' Code sections). Round 2: that check missed names written with the suffix once (room.md, hud.md); fixed in 4a2c131, the map now has RoomPage 17 domains, GridViewport 9, PlayersPanel 5, RoomMenu 4, RoomTopBar 4. Options: A merge the PR once CI is green; B a third review round first; C drop the static check and keep the map by hand. Recommendation: A (the remaining findings were all fixed and the gate's tests stage passes).

---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
SHARED_COMPONENT_DOMAINS in scripts/gate.py maps the client components that four domains or more name in their spec's Code section to those domains (the human's option A): RoomPage.svelte 17, GridViewport.svelte 9, PlayersPanel.svelte 5, RoomMenu.svelte 4, RoomTopBar.svelte 4. When the branch changed one, gate.py --specs (printing what it adds) and the implementer's role hook add those domains, so B-041's (product 035 AC-5, board 007 AC-1) and B-045's (chat 022 AC-18) regressions now run in the quick gate. A static check 'shared components' (stage tests) keeps the map equal to the Code sections, reading names written Name.svelte or with the suffix once. The hook loads the checked checkout's own gate.py to read the map. CLAUDE.md: one Quality gate bullet.
Criteria: none (tooling). Reviewer: CHANGES REQUESTED round 1 (product missing) and round 2 (the check missed short-form names), both fixed; stuck by the two-round rule, escalated; the human chose A (merge once CI is green). Gate: stage tests green, pyrefly 0 errors; the full gate is CI's on PR #101 (not run locally while B-062's gate held the lock).
Pull request: https://github.com/Zyniel/nock/pull/101
<!-- SECTION:FINAL_SUMMARY:END -->
