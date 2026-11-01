---
name: task
description: Add one task to a milestone the human bet on, within its budget, or to Upkeep, through a board pull request with auto-merge; an idea outside them becomes a draft.
argument-hint: [milestone] [change]
disable-model-invocation: true
---

# Add a task

$ARGUMENTS

You are the lead. A task is one change: one branch, one pull request, built by
`/feature`. It starts from `origin/main`, so it reaches `main` first, through a
small board pull request that merges on its own.

1. Find the milestone: `backlog milestone list`. It must be on `origin/main`
   (the human merged its pitch), or be Upkeep.
2. Decide where the change belongs:
   - Inside the milestone's scope, with budget left (the tasks of
     `backlog task list -m "<name>" --plain` against the size in its pitch): a
     task of that milestone.
   - Inside the scope with no budget left: the circuit breaker
     (`.claude/skills/milestone/SKILL.md`).
   - Outside the scope: a draft (`backlog draft create "<title>" -d "..." -l
     follow-up`), never a task.
   - Upkeep: a fix of one day or less, changing nothing a player would notice,
     in no escalation class (CLAUDE.md, "Decisions and escalations"). New
     tooling behaviour goes to the human first.
3. Start a board branch: `uv run python scripts/start_item.py --board
   task-<short-name>`, and work only in its worktree.
4. `backlog task create "<title>" -m "<name>" -l domain:<name>,... --doc
   specs/<area>/<file>.md -d "<why it exists; Out of scope: ...>" --ac
   "<criterion>" --plain`. A tooling task takes the label `tooling` and no
   criterion. `backlog doctor` must be clean.
5. Commit `backlog: task B-NNN <title>`, push, open the pull request with that
   title, and turn on auto-merge (`gh pr merge --auto --merge`). CI runs no gate
   job for `backlog/` alone, so it merges in a minute or two.
6. Once it is merged, build it: `/feature B-NNN`.
