---
name: new-spec
description: Turn a feature request into a brief in Backlog.md, then into a change of the domain specs, stopping for the human's approval of each.
argument-hint: [feature or change description]
disable-model-invocation: true
---

# Brief, then spec change

The user wants this feature or change:

$ARGUMENTS

You are the lead. You write the brief, the spec-writer agent writes the spec
change, and the human approves both. Keep both short: every agent after you reads
them.

## 1. Brief

1. If you are on the default branch, create the item's branch from `origin/main`
   with `git switch -c feat/b-NNN-<short-name>` (NNN is the next free item number
   in `Backlog.md`).
2. Read `specs/_map.md` and pick the domain files the request touches. More than
   three means it is several changes: say so and propose how to split it.
3. Read the Purpose and Rules of those files, enough to write the brief.
4. Decide whether the request is an architecture decision (CLAUDE.md, "Models
   and effort"). If it is, delegate the options to the `Plan` agent with
   `model: "fable"` and `effort: "high"` (Opus at `high` when Fable is not
   available): the request word for word, the domain files, and "two or three
   options with their trade-offs and the one you would pick". Its options go in
   the brief.
5. Add the item to `Backlog.md`, in the format at its top, with status `brief`:
   the problem in one or two lines, in scope, out of scope, the domain files,
   whether it is an architecture decision, the screens it touches, and the open
   questions. When it changes what a screen looks like, or when it is an
   architecture decision, give two or three options with your pick.
6. Show the user the brief and stop. When they approve it (and pick an option),
   set the item to `approved`.

## 2. Spec change

1. Delegate to the `spec-writer` agent: the item id, its brief word for word, and
   the user's answers. It does not see this conversation. For an architecture
   decision, pass `model: "fable"` and `effort: "high"` (Opus at `high` when
   Fable is not available); otherwise its definition applies.
2. When it returns, show the user the diff of the specs (`git diff -- specs`), the
   criteria it added, changed or deleted, and its open questions. Send the user's
   answers back to the same spec-writer, then show the result again.
3. If the spec-writer redrew screens, rebuild the sheet with
   `uv run python docs/design/screens_sheet/build.py` and check that
   `uv run python docs/design/screens_sheet/build.py --check` passes.

## 3. Stop for approval

The changed domain files stay `status: draft` until the user has read the change
and says it is approved. Then:

- set `status: approved` in each changed domain file;
- fill the item's "Criteria" line (for example `grids AC-20 (new), grids AC-7
  (changed), library AC-3 (deleted)`) and set the item to `ready`;
- commit the brief and the spec change, `docs: spec change for B-NNN`, with the
  reasons of the spec-writer's report in the message body;
- tell the user the next step: `/feature B-NNN`.

Do not write tests or code from this command.
