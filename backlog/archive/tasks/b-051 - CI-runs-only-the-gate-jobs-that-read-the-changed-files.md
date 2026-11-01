---
id: B-051
title: CI runs only the gate jobs that read the changed files
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - tooling
dependencies: []
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human asked for it, 2026-10-30: « PR B-039 is triggering
  Quality Gates when only updating backlog and claude_docs review. This should
  not happen. », then « Review my requirements and include coherent files in
  potential QG skips »; tooling, built by the lead)
- Domains: none (tooling only: `.github/workflows/ci.yml`)
- Architecture decision: no
- Criteria: none (tooling)
- Branch: feat/b-051-ci-skip-notes-only · PR: #71 (the notes-only rule);
  feat/b-051-ci-skip-by-file · PR: #72 (every file)
- Problem: CI skipped the browser jobs only for a pull request that changed
  nothing outside `specs/`, `docs/` and `grids/`. B-039 (#70) changed
  `Backlog.md` and `claude_docs/frontend-review.md` only, files no check and
  no test reads, and still ran the static job and the Chromium job.
- In scope: each changed file of a pull request says which gate jobs it
  needs. None, for a file no check and no test reads: `Backlog.md`,
  `CLAUDE.md`, `claude_docs/`, `.claude/`, `docs/` outside `docs/design/`,
  `Dockerfile`, `.dockerignore`, `compose*.yaml`, `Caddyfile`,
  `.env.*.example`. The static job only, for a file only it reads: `specs/`
  (traceability), `docs/design/` (the screens sheet), `grids/` (the shipped
  grids), `README.md` (the font credits, spec 041 AC-6, a test without a
  browser). Every job for any other file and for a Python file anywhere
  (ruff and black read the whole repository). The `Quality gate` check
  accepts a skipped static job only when the files allow it.
- Out of scope: a push to `main` and a run started by hand (every job, as
  before). Files that change what a check sees stay in every job:
  `.gitignore` (ruff and black skip what it lists), `.gitattributes` (line
  endings at checkout), `.python-version`, `pyproject.toml`, `uv.lock`,
  `.github/`.
- Screens: none.
- Built: checked by running the workflow's shell step under `bash -e` on 31
  sample file lists, one or more per kind above, with look-alike paths
  (`Backlog.mdx`, `claude_docsx/`, `compose.yml`, `.env`), a quoted
  non-ASCII path, a path with a space and an empty list (every job); a push
  runs every job.
<!-- SECTION:DESCRIPTION:END -->
