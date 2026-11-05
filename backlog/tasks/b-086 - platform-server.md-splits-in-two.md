---
id: B-086
title: platform/server.md splits in two
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T18:48:00Z'
labels:
  - domain:server
milestone: m-7
dependencies: []
documentation:
  - specs/platform/server.md
priority: medium
ordinal: 74000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. server is 17.3 KB with 23 criteria. Out of scope: any behaviour change. Runs after B-038 (Upkeep), which changes server.py's answers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 server.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
- [ ] #2 server AC-20 to AC-26 move to platform/live-rooms.md as live-rooms AC-1 to AC-7, their tests renamed to tests/test_live_rooms_*.py
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
The new platform/live-rooms.md (domain live-rooms) takes the rooms held in memory, the socket's one lookup and engine time: server rules 20-22 as live-rooms rules 1-3, and server AC-20..26 as live-rooms AC-1..7. Server keeps rules 1-9 and 23, and AC-1..13 and 27..30. Four test files move to tests/test_live_rooms_*.py; tests/server_harness.py keeps its name and gets a new docstring. Repoint lobby/rooms.md, platform/realtime.md, serving.md and grids.md, and the code comments in hub.py, server.py and spec011_harness.py. scripts/gate_browsers.py: two SERIAL_TEST_FILES entries and one comment.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut A (live-rooms) over Cut B (gameplay/undo). It is the coherent runtime topic, leaves server.md near 13.5 KB with 17 criteria, and needs no shared-components change. Cut B would leave server at 14.5 KB with 19 criteria and touch three shared-component entries.

Spec-checker APPROVED in one round. Two wrapping slips it noted were fixed before the commit.
<!-- SECTION:NOTES:END -->
