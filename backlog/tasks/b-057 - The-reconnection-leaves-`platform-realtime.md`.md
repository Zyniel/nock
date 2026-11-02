---
id: B-057
title: The reconnection leaves `platform/realtime.md`
status: To Do
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T01:16:00Z'
labels:
  - domain:realtime
  - domain:reconnection
  - domain:server
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
