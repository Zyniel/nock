---
id: B-053
title: The gate runs 6 workers
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - tooling
dependencies: []
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human asked for it, 2026-10-31: « Lower to 6 »; tooling,
  built by the lead)
- Domains: none (tooling only: `.claude/settings.json`, `CLAUDE.md`)
- Architecture decision: no
- Branch: feat/b-053-gate-six-workers · PR: #78 (merged)
- Problem: the PC restarted on 2026-10-31 at 22:58, 8 minutes into B-037's
  closing full gate, which had started at 22:50 with 10 workers (B-026's
  number, on a machine with 16 logical CPUs). The same gate, run again with
  4 workers, passed and the PC held; its parallel pass took 11 minutes,
  against about 5 with 10. The crash's cause is not confirmed: the Windows
  event log was not read.
- In scope: `NOCK_WORKERS` goes from 10 to 6 in `.claude/settings.json`, and
  `CLAUDE.md` says so.
- Out of scope: the gate's own default (`auto`, one per logical CPU), CI's
  workers, and the role gate's timeout.
- Open questions: none. Two things to watch: a quick gate that changes many
  specs runs longer with 6 workers, and `scripts/hooks/role_gate.py` gives
  the gate 1,140 s, the lock wait included (a gate out of time does not
  block, so it would let a role finish unchecked); and B-052 rewrites
  `CLAUDE.md` without its line about the workers, so whichever merges second
  keeps B-052's text.
<!-- SECTION:DESCRIPTION:END -->
