---
id: B-001
title: Rebaseline v1.1.0 into domain specs
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels: []
dependencies: []
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved every domain file, 2026-10-24)
- Domains: all (`specs/_map.md`)
- Branch: feat/b-001-rebaseline · PR: none yet
- Problem: the numbered specs (2 MB) mix the contract with its history, and a
  role reads about 60k tokens before it starts; the domain specs state the
  current truth.
- In scope: the tooling for domain specs; the 18 domain files still pending,
  `product.md` and `_settings.md`; the design split into `specs/_design/`; a
  review of each domain file against the tests and code of v1.1.0; moving the
  numbered specs to `specs/_archive/v1.1.0/`.
- Out of scope: any change of behaviour or code; compacting the tests (B-003).
- Screens: none (the screens sheet's captions follow the design split).
- The design split also: states the state lines as v1.1.0 draws them (a line
  standing for a page is 16 px with no role, the catalogue's and « Mes
  salons »'s load errors included; inside a card, sheet or dialog, waiting and
  done lines are `role="status"`, error lines `role="alert"`; a failed
  action's error line is `role="alert"`); takes the phone top bar's 40 px
  buttons and the clue bar's minimum width (320 px) into `_design/room.md`;
  takes the grid's name in the computer top bar out of the design.
<!-- SECTION:DESCRIPTION:END -->
