---
id: doc-002
title: Release checklist
type: guide
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T16:44:00Z'
---
When the human says `prepare release vX.Y.Z`, the lead checks, in order:

1. Every task of the release is `Done` and its pull request merged; none is
   `In Progress` (`backlog task list -s "In Progress" --plain`, `gh pr list`).
2. `main`'s last CI run is green in the three engines
   (`gh run list --branch main`).
3. The full gate passes locally in the three engines
   (`uv run python scripts/gate.py --browsers all`), each single failure rerun
   alone.
4. Release notes: one line per milestone accepted since the last tag (from its
   `backlog: close` pull request), then one line per Upkeep task done since
   then. The human reads them.
5. The human tags `vX.Y.Z` on `main` and pushes the tag.
6. On a board branch, the lead archives the release's `Done` tasks
   (`backlog task archive B-NNN`) and its accepted milestones
   (`backlog milestone archive <name>`). They stay readable in
   `backlog/archive/`.
