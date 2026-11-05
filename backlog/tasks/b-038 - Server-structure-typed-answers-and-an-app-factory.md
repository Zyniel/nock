---
id: B-038
title: 'Server structure: typed answers and an app factory'
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-05T02:11:00Z'
labels:
  - domain:server
  - domain:serving
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 server AC-30 (new)
- [ ] #2 serving AC-15 (new)
- [ ] #3 serving AC-4 (changed)
- [ ] #4 serving AC-5 (changed)
- [ ] #5 overrides AC-2 (changed)
- [ ] #6 overrides AC-6 (changed)
- [ ] #7 operations AC-4 (changed)
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
1. Plan agent (Fable, high) proposes the options; the lead picks.
2. Spec change: platform/server.md (and _architecture.md if the modeling rules move), spec-writer then spec-checker.
3. Tests, implementer, reviewer, full gate, pull request.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Released by the human in chat, 2026-11-05 (« /milestone m-2 »: run Upkeep). Open question 1 settled by the lead: option A, the data folders keep the repository layout (the image keeps it, B-009); no variables.

Lead's pick among the Plan agent's options (Fable, high): B. nock.server loses its module-level app; production_app() builds it (create_app with the catalogue of grids/) and main() calls it after the variable checks; routes keep their closures. Answers become pydantic models (frozen, extra forbid) in today's key order, int | float where a value can be either, so the JSON bytes stay the same: overrides' Setting becomes a model (SETTINGS and SETTING_BY_NAME keep their names), SettingRow, SettingsAnswer, DryRunAnswer; operations' DashboardAnswer adds offered_days last; LinkRequested for the link route's {}; every /api route declares its answer. Rejected: A (a lazy module app keeps a hidden singleton), C (routers and app.state: two or three tasks, out of this cut). product.md rule 27 and serving.md AC-4 name production_app() in place of nock.server.app: the entry's name only, inside the human's release of B-038.

Lead decisions on the spec: the answer-model rule lives in serving.md (rule 14, AC-15), which owns the HTTP edge; the progress route declares dict[str, Literal['started', 'finished']]; LinkRequested stays unnamed in the specs (account AC-1 already checks 202 {}); server.md at about 18 KB and 24 criteria is accepted until B-086 splits it.

Spec-checker round 1: CHANGES REQUESTED (key order claimed only where a file gives one; overrides' integers named; grids/ files; the no-app name; _map.md rows). For the implementer: README.md's uvicorn nock.server:app line changes with the code.

Spec-checker round 2: APPROVED.
<!-- SECTION:NOTES:END -->
