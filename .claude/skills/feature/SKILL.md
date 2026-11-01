---
name: feature
description: Build a task of a milestone the human bet on, or of Upkeep, through the spec-writer, spec-checker, test-writer, implementer and reviewer agents, with a commit per phase, then open its pull request with auto-merge.
argument-hint: [task-id] [team]
arguments: [item, mode]
disable-model-invocation: true
---

# Build a backlog task

Task: `$item` (`backlog task view $item --plain`)
Mode: `$mode` (empty means subagents; `team` means an agent team)

You are the lead. You coordinate the agents and you do not write specs, tests
or implementation yourself, even for a small fix: the value of this pipeline is
that specs, tests, code and review come from separate contexts. None of the
agents sees this conversation and none runs `backlog`, so every message you
send one has to stand on its own, and it should hold only what that agent
needs, which is also what keeps a run cheap:

- the task id, its description and its criteria word for word, and the
  milestone's pitch for the spec-writer and the spec-checker;
- the domain files, and the test files for the implementer and the reviewer;
- the base commit (where the branch left `origin/main`), for the spec-checker
  and the reviewer;
- the quick gate of the task:
  `uv run python scripts/gate.py --specs <domain names> --browsers chromium`;
- earlier agents' reports, word for word, where they concern this agent.

Never ask an agent to read the whole `specs/` folder or the numbered specs.

Models (CLAUDE.md, "Models and effort"): the definitions apply, and no agent runs
above `high` effort. Pass `model: "opus"` to the test-writer or the implementer
only when the task's criteria are about layout, painted pixels or timing in a
browser, or when a review round sent that agent's work back.

You decide everything inside the milestone's scope: the open questions of the
task, the agents' questions, the options with equivalent results for players.
Record each decision in the task's notes (`--append-notes`). Only an
escalation (CLAUDE.md, "Decisions and escalations") stops the task: assign it
to `@zyniel` with a comment giving the question, the options and your
recommendation, label its pull request `needs-human` if it has one, and go on
with another task.

## 1. Check before starting

- The task is on `origin/main` (its milestone's pitch is merged, or it is in
  Upkeep), `To Do`, not assigned to `@zyniel`, and its dependencies are `Done`
  (`backlog task list --ready --plain`). If not, stop and say why.
- At most 3 tasks are `In Progress`, never two with the same `domain:` label
  (`backlog task list -s "In Progress" --plain`). If this one would break that,
  take another task or wait.
- `uv run python scripts/start_item.py $item` gives the task's worktree. Work
  only there, by its absolute path. If the script says the branch lacks commits
  of `origin/main`, merge it there first (`git merge origin/main`). Run
  `git status`: changes unrelated to the task mean stop and ask.
- In the worktree, set the task `In Progress` with a three-line plan: the spec
  files, the test files, the quick gate. `backlog task edit $item -s "In
  Progress" --plan "..."`. It travels with the task's commits.

## 2. Spec change

A tooling task has no spec and no criterion: build it yourself, run the gate,
commit (`tooling: B-NNN <title>`), and go to 5, where the task's description
stands for the spec.

1. For an architecture decision (CLAUDE.md, "Models and effort"), delegate the
   options to the `Plan` agent with `model: "fable"` and `effort: "high"` (Opus
   at `high` when Fable is not available): the task word for word, the domain
   files, and "two or three options with their trade-offs and the one you would
   pick". Pick one, unless it falls in an escalation class.
2. Delegate to `spec-writer`: the task, the pitch, your answers to the task's
   open questions and the option picked. For an architecture decision pass
   `model: "fable"` and `effort: "high"`. Answer its open questions yourself and
   send them back to the same spec-writer.
3. If it redrew screens, rebuild the sheet with
   `uv run python docs/design/screens_sheet/build.py`.
4. Delegate to `spec-checker`: the task, the pitch and the base commit.
   - `APPROVED`: set `status: approved` in each changed domain file, add the
     criteria to the task (`--ac "grids AC-20 (new)"`, one per criterion, with
     `changed` or `deleted` where it applies), and commit the spec change and
     the task: `docs: spec change for B-NNN`, the reasons of the spec-writer's
     report in the message body.
   - `CHANGES REQUESTED`: send the findings to the same spec-writer, then ask
     the spec-checker again. A second `CHANGES REQUESTED` is an escalation
     (stuck).
   - `ESCALATE`: escalate with its question, options and pick.

## 3. Tests first

Delegate to `test-writer`. When it returns:

- If it reports questions or untested criteria, answer them yourself when they
  stay inside the spec; a fix to the spec goes through `spec-writer` and the
  `spec-checker`, then back to `test-writer`. When the fix changes a look,
  rebuild the screens sheet and commit it with the spec.
- Otherwise commit only the test files: `test: tests for B-NNN`.

## 4. Implementation

Delegate to `implementer`. When it returns:

- If it reports that a test contradicts the spec, send that report to
  `test-writer`, commit the corrected tests, then return to `implementer`.
- If it asks for a new dependency, escalate.
- Otherwise commit: `feat: B-NNN <title>`.

## 5. Review

Delegate to `reviewer`. On `CHANGES REQUESTED`, send each blocking finding, and
the small and certain suggestions, to the role the reviewer named, and commit the
fix. Then ask for a second round, giving the first round's findings and the
commit the fixes start from: the second round checks only those. After two
rounds that still end in `CHANGES REQUESTED`, escalate (stuck) with the open
findings instead of looping. A suggestion you do not take becomes a draft
(`backlog draft create`, label `follow-up`) on the next board branch.

## 6. Close

- In each domain file of the task, delete the "New interface" section and set
  `status: done`.
- Run `uv run python scripts/gate.py` yourself, in the foreground, and read the
  output. Rerun a single browser failure alone before trusting it.
- In the worktree: check each criterion with its evidence (`--check-ac N`), the
  Definition of Done items that hold (`--check-dod N`), write the final summary
  (`--final-summary`: one line per criterion with its tests, the reviewer's
  verdict, the decisions you took, anything an agent flagged or assumed), and set
  the task `Done`. Commit: `docs: close B-NNN`.
- Push the branch, open the pull request with the final summary as its body
  (`gh pr create --title "<kind>: B-NNN <title>" --body-file <file>`), check the
  last Definition of Done item, commit `docs: B-NNN records its PR` and push.
  Then turn on auto-merge: `gh pr merge --auto --merge`. CI merges it once the
  `Quality gate` check passes.
- Report to the user in a few lines: the pull request, the criteria and their
  result, the decisions you took.
- After the merge: delete the worktree and the remote branch.

A held task gets no auto-merge: its pull request carries the `needs-human`
label (`gh label create needs-human` once, if it is missing) and waits for the
human's answer.

## Team mode

Only when the mode above is `team`. It needs
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` set to `1` in `.claude/settings.json`; if it
is not, say so and continue with subagents.

- Spawn three teammates from the agent types `test-writer`, `implementer` and
  `reviewer`, and name each teammate exactly like its agent type. The quality gate
  hook recognises a teammate by its name.
- Create the tasks with dependencies in the same order as above: tests, then
  implementation, then review. The steps and the commits stay the same.
- A team pays off when the work splits. If the task splits the work into parts
  that touch different files, spawn one implementer per part, named
  `implementer-1`, `implementer-2`, and give each one its criteria and its files.
  Two teammates must never edit the same file.
- Wait for teammates to finish instead of doing their work, and ask them to shut
  down when the task is closed.
