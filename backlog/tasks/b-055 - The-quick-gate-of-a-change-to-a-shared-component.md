---
id: B-055
title: The quick gate of a change to a shared component
status: In Progress
assignee: []
created_date: '2026-11-02T00:07:00Z'
updated_date: '2026-11-02T11:08:00Z'
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
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
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

Lead (2026-11-02): option A, the human's pick. The map lives in scripts/gate.py rather than gate_browsers.py (the lead's default said beside SERIAL_TEST_FILES): the role hook runs from the main checkout and loads the checked checkout's gate.py to read the map, and gate_browsers.py imports pytest and Playwright, which the hook should not load. The map is the domain specs whose Code section names the component: RoomPage.svelte 16 domains, GridViewport.svelte 8, PlayersPanel.svelte 4; the other components are named by three domains at most and stay out. The quick gate run by hand (--specs) adds them too, printing what it adds, so the lead's quick gate and the hook's agree.
<!-- SECTION:NOTES:END -->
