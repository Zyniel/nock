---
name: milestone
description: Shape an idea into a milestone (its pitch and its tasks) in a `backlog: milestone <name>` pull request, which the human merges to bet on it; or close a milestone with its verdict in a `backlog: close <name>` pull request.
argument-hint: [idea] | close [milestone]
disable-model-invocation: true
---

# Pitch a milestone, or close one

$ARGUMENTS

You are the lead. A milestone is one feature or epic the human bets on: a pitch
and its tasks, budgeted in tasks. Merging its pull request is the bet, the only
approval the feature needs. Keep the pitch to about one screen: the human reads
it in 5 to 10 minutes.

If the arguments start with `close`, go to "Close a milestone".

## Pitch a milestone

1. Start a board branch: `uv run python scripts/start_item.py --board
   milestone-<short-name>`. Work only in its worktree, by its absolute path.
2. Read `specs/_map.md` and pick the domain files the idea touches. Look at the
   drafts (`backlog draft list --plain`) and the open tasks for what belongs
   with it.
3. The size is the task budget: S (1 or 2 tasks), M (3 to 5, when the human
   gave none) or L (6 to 8). Cut the scope to fit the size, never the other way
   round. Above 8 tasks, propose two milestones.
4. If the idea leaves a product question open (who it is for, what players see,
   what is in or out), ask the human once, in one batch, and only about the
   product.
5. An architecture decision (CLAUDE.md, "Models and effort"): delegate its
   options to the `Plan` agent with `model: "fable"` and `effort: "high"`.
   One that falls in an escalation class goes in the pitch's questions.
6. Write the pitch as the milestone's description:
   `backlog milestone add "<name>" -d "<pitch>"`.

   ```md
   - Problem: who hits it, and when.
   - Size: M (up to 5 tasks): B-NNN, B-NNN, ...
   - In scope: ...
   - Out of scope: ...
   - Look: A (lead's pick) ... / B ... / none.
   - Risks: none, or the kind (product, money, architecture, dependency).
   - Questions for you: ... (or none)
   ```

7. One task per change, never more than the size:
   `backlog task create "<title>" -m "<name>" -l domain:<name>,... --doc
   specs/<area>/<file>.md -d "<why it exists; Out of scope: ...>" --ac
   "<criterion>" --dep B-NNN --priority <high|medium|low> --plain`. A task fits
   one agent context and touches at most three domain files. A draft it takes
   is promoted (`backlog draft promote DRAFT-NNN`) and then given the milestone.
8. `backlog doctor` must be clean. Commit `backlog: milestone <name>` with the
   pitch's reasons, push, and open the pull request with that title, the pitch
   and the task list as its body. No auto-merge: the human merges it.
9. Tell the user the pull request and the questions in it, if any.

The human bets by merging, reshapes by commenting (update the same pull request
and say what changed), or drops by closing it (the idea goes back to a draft, or
is deleted if they say so). Work starts on the next session after the merge,
with `/feature B-NNN` in the order of the tasks' ordinals and dependencies.

## Close a milestone

1. Every task of the milestone is `Done` and its pull request merged
   (`backlog task list -m "<name>" --plain`, `gh pr list --state merged`).
2. Delegate an independent review to the `reviewer` agent: the pitch, the task
   list with their final summaries, and the range of `main` from before the
   first task's merge to now. Ask for a verdict on the milestone as a whole:
   `accepted`, `accepted with open items` or `not accepted`, with the evidence,
   and the open items.
3. Start a board branch (`--board close-<short-name>`). Each open item becomes a
   draft labelled `follow-up`.
4. Commit `backlog: close <name>`, push, and open the pull request with that
   title and the verdict as its body. No auto-merge: merging it is the human's
   acceptance.

   ```md
   Verdict: accepted | accepted with open items | not accepted
   Budget: 4 of 5 tasks, about 15 % of a week's tokens
   Shipped: B-061 ... / B-062 ... / B-063 ...
   Screens changed: room panel, hint button (screens sheet, sections 4 and 7)
   Decisions the lead took: B-062 kept the old error text ...
   Open items: ... (recorded as drafts)
   ```

5. A send-back adds fix tasks inside the same milestone, within its budget.

## Circuit breaker

When a milestone has used its whole budget and is not done, never add a task.
Stop, and create a task `Budget spent: <name>` without a milestone, assigned to
`@zyniel`, whose comment says what works, what is missing, and your
recommendation among: more tasks, cut the scope and close, back to the drafts,
drop.
