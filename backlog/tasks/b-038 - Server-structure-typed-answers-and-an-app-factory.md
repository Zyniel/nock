---
id: B-038
title: 'Server structure: typed answers and an app factory'
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:server
  - domain:overrides
  - domain:operations
milestone: m-2
dependencies: []
documentation:
  - specs/platform/server.md
  - specs/admin/overrides.md
  - specs/admin/operations.md
priority: low
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: last (maintainability; no player sees it)
- Waits for: nothing (B-027, which changed `server.py`, is merged)
- Domains: platform/server, admin/overrides, admin/operations (the answers
  keep their JSON)
- Architecture decision: yes (`nock.server`'s public names, how the app is
  built, and the modeling rules of `_architecture.md`): options from the Plan
  agent on Fable
- Problem: several answers are built as `dict[str, object]`
  (`RoomLifeOverrides.answer`, the dashboard's `offered_days`, the dry run's
  `{"rooms": n}`, the link route's `{}`), `Setting` and `SETTINGS` are a
  public `NamedTuple`, against the modeling rules, and no route declares a
  `response_model`, so no answer is checked on its way out (B-028 L8).
  `nock.server` reads the catalogue and builds the app when it is imported
  (`server.py:1475`), so one bad grid file fails every import, tests
  included, and the data folders resolve only from the repository layout
  (L9).
- In scope: a model per answer and `response_model` on each route, with the
  same JSON; `Setting` private, or a model; an app factory that `__main__`
  calls.
- Out of scope: any change of what an answer holds.
- Screens: none.
- Open questions:
  1. The data folders (`web/dist`, `grids/`, `fr.json`) from variables: A
     (lead's default) no, the image keeps the layout (B-009); B yes.
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
