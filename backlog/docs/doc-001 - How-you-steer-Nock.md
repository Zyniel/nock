---
id: doc-001
title: How you steer Nock
type: guide
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T16:44:00Z'
---
You decide **what** gets built, **why**, and in what order: features,
milestones and releases. The lead decides **how**, builds it with the agents,
and comes to you only when something touches the product, money, lasting
architecture, dependencies or something that can't be undone. Expect about 45
minutes a week.

The method is **Shape Up's shaping and betting on a Kanban flow**. From Shape
Up it keeps four things:
- the problem and its limits are settled before any work;
- your bet is the only approval;
- ideas wait as drafts instead of growing a queue;
- a circuit breaker stops runaway work.

From Kanban it keeps a limit on the work running at once. Shape Up's six-week
cycles and its time-based appetite are left out: agents are not limited by
calendar time, but by your token budget, your attention, and how much a review
can really check. Milestones are therefore budgeted in **tasks**, not in weeks.

## The words

| Word | What it is |
| --- | --- |
| **Idea** | Something worth doing some day. Stored as a Backlog.md *draft*: not on the board, nothing gets built from it. |
| **Milestone** | One feature or epic you bet on: a pitch (problem, size, scope, look direction) and its tasks. |
| **Task** (`B-NNN`) | One change: one branch, one pull request, built and reviewed by the agents. One task fits one agent context. |
| **Size** | How much a milestone is *worth* to you, in tasks: **S** (1–2), **M** (3–5), **L** (6–8). Above 8 it is split. The scope is cut to fit the size, never the other way round. |
| **Bet** | Your yes to a milestone. It is the only approval a feature needs. |
| **Circuit breaker** | When a milestone has used its task budget and is not done, work stops and you decide. The lead never adds a task past the budget on its own. |
| **Verdict** | The lead's closing report on a milestone, checked by an independent review. |
| **Release** | A version tag (`vX.Y.Z`) on `main` that ships whatever is merged, cut when you choose. |
| **Upkeep** | A standing milestone for bug fixes, tooling fixes and small follow-ups, which the lead fills without a bet, within limits (see the last section). |

## The loop

```
 idea ──► pitch ──► BET ──► build ──► verdict ──► ACCEPT ──► release ──► TAG
  you      lead      you    agents      lead        you        lead       you
```

Capitals mark your decisions. Everything between them runs without you,
unless an escalation (step 4) stops it. There are no cycles or due dates: you
bet when a pitch is ready, a verdict comes when its milestone ends, and you
release when you choose.

## 1. Bring an idea

In a Claude session at `K:\Projects\awf`, write in your own words:

- `/milestone <the idea>`: you want it shaped into a milestone now.
- `Add to the ideas: <the idea>`: keep it as a draft for later.
- `What should we bet on next?`: the lead proposes 2 or 3 pitches, taken from
  the drafts, the review findings and the open items.

Say what you know: the problem, who it is for, the size it is worth to you (S,
M or L; M if you don't say), and anything you already want or refuse. The lead
asks at most one batch of questions, and only about the product.

## 2. Read the pitch and bet

The lead opens a pull request named **`backlog: milestone <name>`**. It holds
about one screen of text:

- **The pitch** (the milestone's description):
  - the problem;
  - the size, which is the task budget;
  - what is in and out of scope;
  - the look direction: 2 or 3 options with the lead's pick, when a screen
    changes;
  - the risks;
  - the questions only you can answer.
- **The tasks**: for each one, a title, why it exists, and the criteria it must
  meet. There are never more tasks than the size allows.

Then, in 5 to 10 minutes, you do one of three things:

| You want to… | You do |
| --- | --- |
| **Bet** | Answer the questions and pick the options in a comment, if there are any, then merge the PR. |
| **Reshape** | Comment on what to change, the size included. The lead updates the PR, and you look again. |
| **Drop** | Close the PR. The idea goes back to the drafts, or is deleted if you say so. |

Merging is the bet. The work starts on the next session.

## 3. While it is built: nothing to do

For each task, in order, the lead runs:

1. The spec change, checked by the **spec-checker**, which stands in for your
   old approval of each spec change. It checks that the change stays within
   the milestone's scope and rules.
2. The look change, if any, drawn into the screens sheet at the same time.
3. The tests, then the code, then **two review rounds** and the full quality
   gate.
4. The pull request, merged automatically once CI is green.

A task that still fails review after its two rounds stops there and comes to
you (step 4), instead of burning more tokens on retries.

**Getting work to move:** open a session and say `continue`. The lead takes the
next ready task of the milestones you bet on. For parallel work, say
`work on 3 tasks in parallel`.

**The work-in-progress limit:** at most 3 tasks run at once, and never two on
the same part of the game, meaning the same domain spec. After a usage limit,
the hourly resume picks the work up again.

**Watching, if you want to:** `backlog browser` shows the board, milestones with
their progress (tasks done out of the budget), and the drafts. Use it to read,
not to edit: your decisions go through pull requests and chat. GitHub lists the
open PRs.

## 4. When the lead needs you

Only these reach you:

| Kind | Examples |
| --- | --- |
| **Product** | A change outside the milestone's scope, a new page or screen, removing something players can see, the brand's wording. |
| **Money, accounts, outside services** | Hosting, a domain, secrets, any paid service, what deleting an account does. |
| **Lasting architecture** | The format of stored data or a migration, adding or splitting a part of the game's specs, the architecture rules, the product baselines. |
| **A new dependency** | Any new Python or npm package. |
| **Something that can't be undone** | A force push, deleting a branch that is not merged, deleting grid files. |
| **Budget spent** | A milestone that used its task budget and is not done (the circuit breaker). |
| **Stuck** | A task that still fails review after its two rounds, a task blocked for more than 3 days, or work the usage limit stopped and the resume could not restart. |

**How it reaches you:** the task is assigned to you (`@zyniel`) with a comment
giving the question, the options and the lead's recommendation. If a PR exists,
it gets the `needs-human` label, so GitHub notifies you.

**Your inbox:** the board filtered on your name (`backlog task list -a
@zyniel`), plus the PRs labelled `needs-human`.

**How to answer:** in a session (`B-061: option A`), or as a PR comment. The
task then goes back into the flow.

**What never reaches you:** test setup, wording of specs, reviewer
suggestions, choosing between two equivalent technical options, tooling
fixes, branch cleanup, the order of tasks. The lead decides these and writes
them in the task's notes, and you see them all in the verdict.

## 5. Accept a milestone

When every task is merged, the lead opens a PR named **`backlog: close <name>`**
with the verdict:

- **What shipped**: one line per task.
- **The budget**: tasks used out of the size, and about what share of a week's
  tokens the milestone took.
- **The screens that changed**: their sections in the screens sheet
  (`docs/design/screens-sheet.html`).
- **Every decision the lead took**, one line each.
- **Open items and follow-ups**: recorded as ideas, nothing built.
- **The verdict** of an independent review of the whole milestone: `accepted`,
  `accepted with open items` or `not accepted`, with the evidence.

In about 10 minutes: **merge** to accept, or **comment** to send it back. If you
send it back, the lead adds fix tasks inside the same milestone. A fix task
counts toward the budget, so a big send-back may also mean raising the size.

**Circuit breaker:** if the budget is spent before the milestone is done, the
lead stops and assigns the milestone to you, saying what works, what is
missing, and its recommendation. You choose one:
- grant more tasks (`<milestone>: 2 more tasks`);
- cut the scope and close it with what works;
- send the rest back to the ideas;
- drop it.

## 6. Cut a release

Whenever you want a version, say `prepare release v1.2.0`. The lead checks the
release checklist:
- every task of the release is merged;
- `main` is green in the three browsers;
- the full gate passes;
- release notes are written from the accepted milestones, plus the Upkeep
  tasks done since the last release.

You read the notes and push the tag:

```bash
git tag v1.2.0
```

```bash
git push origin v1.2.0
```

The lead then archives the finished tasks. They stay readable in the board's
archive.

## Your week, as an example

| When | Time | What you do |
| --- | --- | --- |
| Monday | 15 min | Open the inbox and answer what is assigned to you. Bet, reshape or drop the pitches waiting. Say `continue`. |
| During the week | 0 | Nothing, unless GitHub sends a `needs-human` notification. |
| A milestone closes | 10 min | Read the verdict and look at the changed screens, then merge or send it back. |
| When you want to ship | 15 min | Cut a release and ask for the next pitches. |

## What you no longer do

- Approve each brief.
- Approve each spec change.
- Answer the agents' technical questions.
- Ask for each push or pull request.
- Merge every PR (you merge only the held ones and the milestone PRs).
- Pick between technical options that are equivalent for players.

## Cheat sheet

| You want to… | Say or do |
| --- | --- |
| Start a feature | `/milestone <idea>` (add `size S`, `M` or `L` if you know it) |
| Keep an idea for later | `Add to the ideas: <idea>` |
| Get proposals | `What should we bet on next?` |
| Bet on a milestone | Merge its `backlog: milestone …` PR |
| Change a pitch or its size | Comment on its PR |
| Drop a pitch | Close its PR |
| Get work moving | `continue`, or `work on N tasks in parallel` (up to 3) |
| See what's going on | `backlog browser` (read only), or `backlog task list -a @zyniel` for your inbox |
| Answer an escalation | `B-NNN: <your answer>` in a session, or a PR comment |
| Give a stopped milestone more room | `<milestone>: 2 more tasks` |
| Accept a milestone | Merge its `backlog: close …` PR |
| Ship a version | `prepare release vX.Y.Z`, then push the tag |
| Stop something | `stop B-NNN` or `drop milestone <name>` |

## Templates the lead fills in

**A pitch** (the milestone's description):

```md
Problem: who hits it, and when.
Size: M (up to 5 tasks).
In scope: …
Out of scope: …
Look: A (lead's pick) … / B … / none.
Risks: none, or the kind (product, money, architecture, dependency).
Questions for you: … (or none)
```

**A verdict** (the close PR):

```md
Verdict: accepted | accepted with open items | not accepted
Budget: 4 of 5 tasks, about 15 % of a week's tokens
Shipped: B-061 … / B-062 … / B-063 …
Screens changed: room panel, hint button (screens sheet, sections 4 and 7)
Decisions the lead took: B-062 kept the old error text …
Open items: … (recorded as ideas)
```

## Where it starts

The import kept every number. The done items are archived and stay readable in
`backlog/archive/tasks/`; the open ones are in three milestones. Merging the
import's pull request was your bet on the first two:

- **Connection and sync**, size M: B-040 (sign-out forgets the seats), B-041
  (reconnection keeps order and presence), B-043 (remote updates in
  proportion), B-047 (connection hardening).
- **Grid and room screens**, size L: B-042 (focus ring), B-044 (zoom follows
  the selection), B-045 (one room sheet, focus in overlays), B-046 (one live
  status region), B-049 (split the two big components), B-050 (small fixes).
- **Upkeep:** B-048 (unit tests for the client's pure modules), B-038 (server
  structure) and B-003 (compact the tests). Each comes to you before it
  starts: a second test runner is new tooling, B-038 changes the architecture
  rules, and you delayed B-003.

The small follow-ups and the grid engine ideas are drafts. Nothing is assigned
to you: you dropped the four decisions that were waiting.

## Choices you made (2026-11-01)

1. **Default size:** M, up to 5 tasks. You can set S or L in any pitch.
2. **Upkeep runs without a bet**, for fixes of 1 day or less that change no
   behaviour players would notice and hit no risk class. New tooling behaviour
   still needs you. Upkeep tasks are listed in each release's notes.
3. **You push release tags.**
4. **You bet by merging the pitch PR.** The board is for reading only.
5. **At most 3 tasks at once**, never two on the same part of the game. Say
   `one at a time this week` to spare the token budget.
6. **Both a session's chat and PR comments count as your answer** to an
   escalation. The lead confirms what it understood.
