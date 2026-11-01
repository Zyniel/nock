---
id: B-052
title: CLAUDE.md and the role files follow Claude Code's guidance
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - tooling
dependencies: []
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human asked for it, 2026-10-30: « review the CLAUDE.md
  and AGENTS.md. Rewrite them if needed against best practices »; tooling,
  built by the lead; the human read the diff and asked for the PR)
- Domains: none (tooling only: `CLAUDE.md`, `.claude/agents/*.md`,
  `.claude/skills/python-standards/SKILL.md`)
- Architecture decision: no (the same rules in new words; one change of
  behaviour: the roles stop loading `CLAUDE.md`)
- Branch: feat/b-052-instructions-review · PR: #80
- Problem: `CLAUDE.md` (183 lines, 10.7 KB) loads in the lead and in every role
  run. It describes a layout Claude can read itself, carries gate internals and
  dated notes, and mixes the lead's rules with rules the roles already hold in
  their own files. There is no `AGENTS.md`: Claude Code reads one only when no
  `CLAUDE.md` exists, and the project uses Claude Code only.
- In scope: `CLAUDE.md` rewritten for the lead, grouped by intent (rules,
  commands, building a change, roles, models, specs, gate, git, standards,
  environment), with no dated notes, and with the human's standing preferences
  that only the lead's memory held (decide technical details and report them;
  tooling items skip `/new-spec`; delete the branch and worktree after a
  merge); `omitClaudeMd: true` in the four role files, which already hold what
  they need, plus the serial-test rule for the test-writer; stale lines fixed
  (the numbered specs' folder, the test file names in `python-standards`).
- Out of scope: the change of process (epics, the Backlog.md tool), which waits
  for the human; `.claude/agents/code-reviewer.md` (the human's, not
  committed); hooks, gate, settings, skills other than `python-standards`.
- Screens: none.
<!-- SECTION:DESCRIPTION:END -->
