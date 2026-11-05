---
id: DRAFT-071
title: Fresh worktrees and the gate lock's own exit code
status: Draft
assignee: []
created_date: '2026-11-05T22:21:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), items I-3 to I-5 (tooling weaknesses, Upkeep). (1) scripts/start_item.py runs npm --prefix web ci and npm --prefix web run build after making a task worktree, so the implementer's role gate does not fail on missing node_modules and bare pytest runs find web/dist. (2) gate.py exits with its own code (for example 3) when the lock wait gives up after 600 s. role_gate.py maps that code to 'could not run' and quotes the holder line, instead of reading it as a failing test and blocking the agent. Size XS and S.
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
