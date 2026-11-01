---
id: B-026
title: The gate's load on the machine
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - tooling
dependencies: []
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human asked for it, 2026-10-29: « Apply suggestions. Set
  NOCK_WORKERS au 10 »; tooling, built by the lead)
- Priority: first (the human, 2026-10-29): every item's gates and review
  rounds run on it.
- Domains: none (tooling only: `scripts/gate.py`, `scripts/hooks/role_gate.py`,
  `.claude/settings.json`, `CLAUDE.md`)
- Architecture decision: no (the human chose the fixes)
- Branch: feat/b-026-gate-load · PR: #62
- Problem: review rounds froze the human's desktop. `--workers auto` started
  one pytest worker per logical CPU (16), each with its own Chromium: 64
  Chromium processes, about 10 GB and 94 % CPU on 2026-10-29, while the
  implementer's finish hook ran a second gate. At its timeout, `role_gate.py`
  stopped only `uv`, and the gate's tree ran on.
- In scope: `NOCK_WORKERS`, the default of `--workers`, set to 10 in
  `.claude/settings.json`; never more workers than logical CPUs; the parallel
  pass at a low priority (the serial pass keeps the normal one for its
  timings); one gate's tests at a time per clone (a lock in `.git/`; another
  gate waits up to 10 minutes, then fails naming the holder); `role_gate.py`
  stops the gate's whole process tree at its timeout.
- Out of scope: CI (no `NOCK_WORKERS` there: `auto` as before); a bare
  `uv run pytest`; tests, specs and code.
- Screens: none.
- A worktree gets it once its branch takes `main` after the merge: the hook
  runs the `gate.py` of the checkout it checks.
<!-- SECTION:DESCRIPTION:END -->
