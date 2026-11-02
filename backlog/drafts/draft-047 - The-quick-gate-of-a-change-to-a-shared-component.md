---
id: DRAFT-047
title: The quick gate of a change to a shared component
status: Draft
assignee: []
created_date: '2026-11-02T00:07:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The quick gate picks its browser tests from the domains and numbered specs a branch changes, but `RoomPage.svelte` and `GridViewport.svelte` serve nearly every domain: three regressions of one round passed the quick gate and showed only in the full gate (B-041: product 035 AC-5 and board 007 AC-1; B-045: chat 022 AC-18, a mute closing the Salon sheet). Options: (A) `scripts/hooks/role_gate.py` and the lead widen the quick gate with the domains a shared component serves (a map of the components to their domains); (B) a change to either file runs the full gate in the role hook; (C) keep it as it is, the lead running the full gate at close. New tooling behaviour: the human decides (A or B).
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
