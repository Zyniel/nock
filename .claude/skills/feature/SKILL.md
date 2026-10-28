---
name: feature
description: Build a ready item of Backlog.md through the test-writer, implementer and reviewer agents, with a commit per phase.
argument-hint: [backlog-item] [team]
arguments: [item, mode]
disable-model-invocation: true
---

# Build a backlog item

Item: `$item`, in `Backlog.md`
Mode: `$mode` (empty means subagents; `team` means an agent team)

You are the lead. You coordinate three agents and you do not write tests or
implementation yourself, even for a small fix: the value of this pipeline is that
tests, code and review come from separate contexts. None of the agents sees this
conversation, so every message you send one has to stand on its own, and it
should hold only what that agent needs, which is also what keeps a run cheap:

- the item id, its domain files, and its criteria (the item's "Criteria" line),
  which the agent reads first;
- the test files, for the implementer and the reviewer;
- the base commit (where the branch left `origin/main`), for the reviewer;
- the quick gate of the item:
  `uv run python scripts/gate.py --specs <domain names> --browsers chromium`;
- earlier agents' reports, word for word, where they concern this agent.

Never ask an agent to read the whole `specs/` folder or the numbered specs.

Models (CLAUDE.md, "Models and effort"): the definitions apply, and no agent runs
above `high` effort. Pass `model: "opus"` to the test-writer or the implementer
only when the item's criteria are about layout, painted pixels or timing in a
browser, or when a review round sent that agent's work back.

## 1. Check before starting

- The item must be `ready` and each of its domain files `approved`. If not, stop
  and tell the user: a spec that is not approved is not a contract yet.
- Run `git status`. If there are uncommitted changes unrelated to the item, stop
  and ask. Work in the item's worktree: `git worktree list` shows the folder of
  the branch on the item's "Branch" line. An item without a branch gets one in
  the main checkout with `git worktree add .claude/worktrees/b-NNN-<short-name>
  -b feat/b-NNN-<short-name> origin/main`; never run `git switch` there, other
  sessions share it. If the folder is not a git repository, skip every git step
  and say so at the end.
- Set the item to `building` and note its branch.

## 2. Tests first

Delegate to `test-writer`. When it returns:

- If it reports questions or untested criteria, stop and take them to the user.
  A fix to the spec goes through `spec-writer` and the user's approval, then back
  to `test-writer`. When the fix changes a look, rebuild the screens sheet
  (`uv run python docs/design/screens_sheet/build.py`) and commit it with the
  spec.
- Otherwise commit only the test files: `test: tests for B-NNN`.

## 3. Implementation

Delegate to `implementer`. When it returns:

- If it reports that a test contradicts the spec, send that report to
  `test-writer`, commit the corrected tests, then return to `implementer`.
- If it asks for a new dependency, ask the user before anything is added.
- Otherwise commit: `feat: B-NNN <title>`.

## 4. Review

Delegate to `reviewer`. On `CHANGES REQUESTED`, send each blocking finding, and
the small and certain suggestions, to the role the reviewer named, and commit the
fix. Then ask for a second round, giving the first round's findings and the
commit the fixes start from: the second round checks only those. After two
rounds that still end in `CHANGES REQUESTED`, stop and show the user the open
findings instead of looping.

## 5. Close

- In each domain file of the item, delete the "New interface" section and set
  `status: done`. Set the item to `done` in `Backlog.md`.
- Run `uv run python scripts/gate.py` yourself, in the foreground, and read the
  output. Rerun a single browser failure alone before trusting it.
- Commit: `docs: close B-NNN`.
- Report to the user: one row per criterion of the item (id, tests, result), the
  reviewer's verdict, and anything an agent flagged or assumed.
- Do not push and do not open a pull request. Give the user the commands:
  `git push -u origin <branch>` then `gh pr create --fill`.

## Team mode

Only when the mode above is `team`. It needs
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` set to `1` in `.claude/settings.json`; if it
is not, say so and continue with subagents.

- Spawn three teammates from the agent types `test-writer`, `implementer` and
  `reviewer`, and name each teammate exactly like its agent type. The quality gate
  hook recognises a teammate by its name.
- Create the tasks with dependencies in the same order as above: tests, then
  implementation, then review. The steps and the commits stay the same.
- A team pays off when the work splits. If the item's brief splits the work into
  parts that touch different files, spawn one implementer per part, named
  `implementer-1`, `implementer-2`, and give each one its criteria and its files.
  Two teammates must never edit the same file.
- Wait for teammates to finish instead of doing their work, and ask them to shut
  down when the item is closed.
