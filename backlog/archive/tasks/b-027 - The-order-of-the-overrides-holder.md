---
id: B-027
title: The order of the overrides holder
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels: []
dependencies: []
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved the brief and picked A, 2026-10-29;
  no spec change; built and reviewed in two rounds, 2026-10-29)
- Waits for: nothing left (B-024 is merged and on this branch).
- Domains: none (no behaviour change: `src/nock/server.py` only)
- Architecture decision: no (private names of `server.py`)
- Criteria: none new; the tests of `admin/overrides.md` prove nothing changed
- Branch: feat/b-027-overrides-holder-order · PR: #65
- Problem: in `server.py`, `_RoomsHolder.settings_set()` answers None both for
  a registry given to the app and before any registry exists, which mean
  different things. It works today only because the lifespan calls
  `holder.get()` first (B-024 review round 2, a suggestion).
- In scope: make that order impossible to break by accident. Options:
  - A (the human's pick): `settings_set()` fails loudly when no registry exists
    yet, so None means only "a registry was given".
  - B: `get()` answers the registry and the set together, and
    `settings_set()` goes.
  - C: a comment at the call site only.
- Out of scope: any change to the routes, the answers or the page.
- Screens: none.
- Open questions: none beyond the option.
<!-- SECTION:DESCRIPTION:END -->
