---
name: feature
description: Build an approved spec through the test-writer, implementer and reviewer agents, with a commit per phase.
argument-hint: [spec-file] [team]
arguments: [spec, mode]
disable-model-invocation: true
---

# Build a feature from an approved spec

Spec file: `$spec`
Mode: `$mode` (empty means subagents; `team` means an agent team)

You are the lead. You coordinate three agents and you do not write tests or
implementation yourself, even for a small fix: the value of this pipeline is that
tests, code and review come from separate contexts. None of the agents sees this
conversation, so every message you send one has to stand on its own: name the spec
file, say what you expect back, and pass on reports word for word instead of
summarising them.

## 1. Check before starting

- Read the spec. If its status is not `approved`, stop and tell the user. A draft
  is not a contract yet.
- Run `git status`. If there are uncommitted changes unrelated to this spec, stop
  and ask. If you are on the default branch, create `feat/<spec-file-name>` with
  `git switch -c`. If the folder is not a git repository, skip every git step and
  say so at the end.

## 2. Tests first

Delegate to `test-writer` with the spec path. When it returns:

- If it reports questions or untested criteria, stop and take them to the user.
  A fix to the spec goes through `spec-writer`, then back to `test-writer`. When
  the fix changes a look, the spec-writer redraws it in `docs/design/`; rebuild
  the screens sheet (`uv run python docs/design/screens_sheet/build.py`) and
  commit it with the spec.
- Otherwise commit only the test files: `test: add tests for spec NNN`.

## 3. Implementation

Delegate to `implementer` with the spec path and the test file names. When it
returns:

- If it reports that a test contradicts the spec, send that report to
  `test-writer`, commit the corrected tests, then return to `implementer`.
- If it asks for a new dependency, ask the user before anything is added.
- Otherwise commit: `feat: implement spec NNN`.

## 4. Review

Delegate to `reviewer` with the spec path. On `CHANGES REQUESTED`, send each
blocking finding to the role the reviewer named, commit the fix, and ask for a new
review. After two rounds that still end in `CHANGES REQUESTED`, stop and show the
user the open findings instead of looping.

## 5. Close

- Run `uv run python scripts/gate.py` yourself and read the output.
- Change the spec status to `status: done` and commit: `docs: close spec NNN`.
- Report to the user: one row per acceptance criterion (id, tests, result), the
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
- A team pays off when the work splits. If the spec has a "Work packages" section
  whose packages touch different files, spawn one implementer per package, named
  `implementer-1`, `implementer-2`, and give each one its list of files. Two
  teammates must never edit the same file.
- Wait for teammates to finish instead of doing their work, and ask them to shut
  down when the feature is closed.
