---
id: B-029
title: The gate type-checks `scripts/`
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - tooling
dependencies: []
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human, 2026-10-29: « Start with B-029 »; tooling, built
  by the lead)
- Waits for: nothing (B-028 is merged, with B-030).
- Priority: first (every item's gate runs on it; the smallest fix of B-028)
- Domains: none (tooling only: `scripts/gate.py`)
- Architecture decision: no
- Criteria: none (tooling)
- Branch: feat/b-029-gate-pyrefly-scripts · PR: #68
- Problem: the gate puts `scripts/` on `PYTHONPATH` (`scripts/gate.py:241`)
  for every step. Pyrefly then reads `scripts/` as a site-packages folder and
  leaves it out of the project ("Skipping include pattern ...scripts because
  it is matched by `project-excludes`"), so neither the local gate nor CI
  type-checks `scripts/`, though `pyproject.toml` includes it. A plain
  `uv run pyrefly check` does check it, with 0 errors today.
- In scope: run pyrefly without `scripts/` on its `PYTHONPATH`, the other
  steps unchanged; a test of the gate that pyrefly's environment holds no
  `scripts/` entry, if it stays cheap.
- Out of scope: the other steps of the gate; `src/` and `tests/`.
- Screens: none.
- Open questions: none.
- Built: `run_tool` puts `scripts/` on `PYTHONPATH` for pytest only, the one
  step that loads a module from it (the `gate_browsers` plugin); no other step
  imports from `scripts/`, so ruff, black, the screens sheet, svelte-check and
  the grids step lose an entry they never read. Checked with a file of
  `scripts/` holding a type error, run through the gate's own `run_tool`:
  before the fix pyrefly answered 0 errors, after it reports the error and
  the step fails. The full gate without browser tests passes (4,300 parallel
  and 64 serial tests, which load the plugin). No test of the gate: `tests/`
  holds the domains' tests only, and the probe above is the check.
<!-- SECTION:DESCRIPTION:END -->
