---
id: B-030
title: Grid lookups in constant time
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:grids
  - domain:server
dependencies: []
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved the brief and picked A, then approved the
  spec change, 2026-10-30; the Plan agent on Fable confirmed A, with the two
  corrections below; both review rounds approved)
- Priority: second (B-028's worst CPU path; no behaviour change)
- Domains: content/grids (the model's lookups), platform/server (a time
  budget)
- Architecture decision: yes (new public names of `Grid`, read by `room.py`,
  `catch_up.py`, `recap.py`, `grid_import.py` and `ipuz.py`): options from
  the Plan agent on Fable
- Criteria: grids AC-22 (new), grids AC-23 (new), grids AC-24 (new), server
  AC-20 (new), server AC-21 (new), server AC-22 (new)
- Branch: feat/b-030-grid-lookups · PR: none yet
- Problem: one engine thread runs every room (`nock.hub`), and the hottest
  rules find a cell's answer by linear scans: `Grid.cell_at` walks every cell,
  `word_cells` calls it for each letter, `_solution_letter` (`room.py:2405`)
  rebuilds every word of the grid for each cell, and `Clue.letters`
  normalises the answer again at each read. On the largest catalogue grid
  (12 x 15), the solving edit, and any edit of a full grid, cost up to 56 ms
  of that thread, a grid check 80 ms, and a catch-up rebuilds every word for
  each letter of the absence (`catch_up.py:181`). Every other room waits
  meanwhile (B-028 H2, M4).
- In scope: a grid computes its cell index, its words and its solution
  letters once, and the rules read them. Options:
  - A (the human's pick): private attributes filled after validation, read
    through public methods (`Grid.solution_letter`, `Grid.words` of a frozen
    `Word`); the model stays frozen and its JSON, schema and equality
    unchanged. The Plan agent's corrections: fill them at the end of the
    grid's after-validator, since `model_post_init` runs before it and would
    change AC-5's message; index only the clues that resolve, so that
    `grid_import` keeps its own messages for the others (AC-6).
  - B: a module cache keyed by the grid, outside the model (rejected: no
    cheap key, state the tests cannot see).
  - C: precompute in the catalogue only (rejected: every store load builds a
    grid, so rooms after a restart, catch-up and recaps stay slow).
  A time budget proves it, measured on FX-02 (`tests/fixtures/fx02.json`,
  13 x 17), since the catalogue files are not in the repository: for example
  the solving edit under 5 ms, a check of a grid full of wrong letters under
  10 ms, a catch-up over 100 letters under 50 ms (its test file goes in
  `SERIAL_TEST_FILES`); the spec-writer picks the measure and its home.
- Out of scope: the limits on checks and reveals (B-031); the protocol, the
  answers and the store.
- Screens: none.
- Open questions: none left. The spec-writer's two, answered by the lead:
  `Grid.solution_letter` gives none for a position outside the grid (callers
  ask only about room cells, and it stays total), and a cell held by words
  that disagree takes the first word in clue order (deterministic, so
  equality holds; the import still refuses such a grid, AC-11).
- Build note: `tests/test_server_engine_time.py` measures durations; the lead
  adds it to `SERIAL_TEST_FILES` (`scripts/gate_browsers.py`) before the
  test-writer's gate.
<!-- SECTION:DESCRIPTION:END -->
