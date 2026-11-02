---
id: B-057
title: The reconnection leaves `platform/realtime.md`
status: In Progress
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T08:09:00Z'
labels:
  - domain:realtime
  - domain:reconnection
  - domain:server
  - domain:hud
milestone: m-3
dependencies: []
documentation:
  - specs/platform/realtime.md
  - specs/platform/server.md
priority: medium
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: platform/realtime → platform/reconnection (new); platform/server (cites rules 20 and 22, near its line 110)
- Architecture decision: yes (a new domain), approved by the merge of the « Spec splits » pitch; the spec-writer runs on Fable at high effort.
- Model: spec-writer on Fable (high); test-writer on Sonnet; no implementer (no code changes).
- Problem: `platform/realtime.md` is 22.5 KB with 24 criteria, past the budget of `specs/_map.md`.
- In scope: rules 15 and 17 to 22 (stale edits, the resume window, the page's connection, retries, resends) and AC-16 to AC-19 and AC-24 move to `platform/reconnection.md`, about 7 KB and 5 criteria; rule 16 (the room's silence check and the join deadline, a server rule) stays with AC-15 and AC-21, so `social/presence.md` is untouched. Their tests move to `tests/test_reconnection_*.py`; the pointers of 017 move with their criteria. A moved criterion takes the next free number of the new file and its tests are renamed and moved to the new domain's test files; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps allowed). `specs/_map.md`: the new row, the split « From the v1.1.0 specs » cell, a glossary line next to its related term.
- Out of scope: any change of behaviour or code; the citations of rules 19, 20 and 22 in shell, joining and hints, which their own tasks repoint.
- Order: before B-058, B-059 and B-060.
- Screens: none.
- Open questions: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 reconnection AC-1 (moved from realtime AC-16)
- [ ] #2 reconnection AC-2 (moved from realtime AC-17)
- [ ] #3 reconnection AC-3 (moved from realtime AC-18)
- [ ] #4 reconnection AC-4 (moved from realtime AC-19)
- [ ] #5 reconnection AC-5 (moved from realtime AC-24)
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
Spec files: specs/platform/realtime.md, specs/platform/reconnection.md (new), specs/platform/server.md, specs/_map.md.
Test files: the tests of realtime AC-16 to AC-19 and AC-24 move from tests/test_realtime_*.py to tests/test_reconnection_*.py.
Quick gate: uv run python scripts/gate.py --specs realtime,reconnection,server --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): B-057 runs before B-047, which also carries domain:realtime: it unblocks B-058, B-059 and B-060, and B-047 then writes its connection rules into the new reconnection file. Run in the dispatcher session: the app refused to start a separate session from a Remote Control message.

Lead: client/hud.md rule 17 cites realtime rule 20 (the connection band) by number, outside the task's out-of-scope list (shell, joining, hints). Repointed here to reconnection rule 5 rather than left dangling until B-064; the task takes domain:hud. realtime.md ends at 17.5 KB with 19 criteria, above the 15 KB budget but the cut the pitch picked; no further split.

Lead: the spec-checker APPROVED in round one; its three minor findings were taken before the commit (two lines rewrapped in realtime.md, rule 16's pointer sentence reworded, the locked-cell edge case cites realtime AC-12 again). server.md's citations by name of the moved behaviour (Depends on, rule 6, an edge case) were repointed here, server being in the task. The by-name citations left in co-op (21, 38, 247), catch-up (22, 218), rooms (18, 223), shell (20, 348), joining (19) and product.md baseline 25 (line 167, a pointer only) go to B-064's scope, which did not list them.
<!-- SECTION:NOTES:END -->
