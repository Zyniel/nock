---
id: B-055
title: The quick gate of a change to a shared component
status: To Do
assignee: []
created_date: '2026-11-02T00:07:00Z'
updated_date: '2026-11-02T01:00:00Z'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Human (2026-11-02, chat, answering the lead's wrap-up after B-043 to B-045): DRAFT-047 option A. Promoted to Upkeep as a tooling task.
<!-- SECTION:NOTES:END -->
