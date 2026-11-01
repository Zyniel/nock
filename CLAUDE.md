# Nock

Nock is an online collaborative arrowword (mots fléchés) game: a Python server
and a Svelte + TypeScript client. The name is the notch at the back of an arrow.
It is built spec-first by Claude Code agents. The human owns the product and
decides milestones, releases and escalations. The main session is the lead: it
plans, delegates to the roles in `.claude/agents/` and keeps the backlog
(`backlog/`); it writes no specs, tests or product code.

This file is for the lead. The roles carry their own instructions and do not
load it.

## Rules

- No implementation without an approved spec, and none before its tests exist:
  the tests, written from the spec by another agent, decide what gets built.
- Nothing is built outside a milestone the human bet on, or Upkeep. Inside
  one, the lead decides: the tasks' open questions, the agents' questions,
  options with equivalent results for players, tooling details, test setup,
  small spec slips, reviewer suggestions. It records each decision in the
  task's notes; the human reads them in the milestone's verdict.
- A spec change is approved by the `spec-checker`'s APPROVED; the lead then sets
  the status line. Only an escalation (below) waits for the human.
- New tooling behaviour and new dependencies (Python or npm) are the human's
  call: escalate first. Tooling means `pyproject.toml`, `scripts/`, `.claude/`,
  `.github/` and, in `web/`, `package.json`, `package-lock.json` and the Vite,
  Svelte and TypeScript config files. Exception: the lead fixes an incoherence
  or a weakness of the tooling (a timeout, a flaky setup, a hook that blocks
  the wrong thing) without asking, as an Upkeep task.
- Specs and design files state what is true now, with no dated notes and no
  history. The reason for a change goes in its commit message.
- The visual documentation is always current, so the human can see the whole
  look at any time. A change that alters what a screen looks like updates the
  design file of that part of the screen in `specs/_design/` and redraws it in
  `docs/design/` in the same commit, before tests and code: the cell sheet by
  hand, the screens sheet from `docs/design/screens_sheet/`, then rebuilt. The
  reviewer blocks a change of look that is not drawn.

## Decisions and escalations

The human decides with pull requests and chat: a bet is the merge of a
`backlog: milestone <name>` pull request, an acceptance the merge of a
`backlog: close <name>` one, a release the push of a tag. Everything else
merges on its own once CI is green.

Escalate only these, with the task assigned to `@zyniel` and a comment giving
the question, the options and your recommendation (`backlog task edit B-NNN -a
@zyniel --comment "..."`), plus the `needs-human` label on its pull request if
it has one:

- Product: a change outside the milestone's scope, a new page, screen or route,
  removing something players can see, the brand's wording.
- Money, accounts, outside services: hosting, a domain, secrets, a paid
  service, what deleting an account does.
- Lasting architecture: the format of stored data or a migration, a protocol
  message, adding, splitting or merging a domain, `specs/_architecture.md`,
  the baselines of `specs/product.md`.
- A new dependency, or new tooling behaviour.
- Something that cannot be undone: a force push, deleting a branch that is not
  merged, deleting grid files.
- Budget spent: a milestone used its task budget and is not done (the circuit
  breaker of `/milestone`).
- Stuck: a task still `CHANGES REQUESTED` after two review rounds, or after two
  spec-checker rounds; a task blocked for more than 3 days; work the usage limit
  stopped and the resume could not restart.

A session's chat and a pull request comment both count as the human's answer.
Say what you understood, record it in the task's notes, unassign the task
(`-a ""`) and go on.

## Backlog

`backlog/` is kept with the Backlog.md CLI, `backlog` 1.55.3 (pinned; `npm i -g
backlog.md@1.55.3`). The roles never run it: the lead records for them. Its own
guides (`backlog instructions`) are not read; this section overrides them.

- A milestone is one bet: its pitch is its description, its size the task
  budget (S 1 or 2 tasks, M 3 to 5, L 6 to 8). Upkeep is a standing milestone
  with no bet and no budget: fixes of one day or less that change nothing a
  player would notice and fall in no escalation class.
- A task, `B-NNN`, is one change: one branch, one pull request. Statuses are
  `To Do`, `In Progress` and `Done`; a held task is one assigned to `@zyniel`.
  Its `domain:<name>` labels name the domain specs it changes.
- A draft is an idea or a follow-up: nothing is built from it until a milestone
  takes it. The lead creates drafts freely; follow-ups never wait for the human.
- Scope growth inside a milestone the human bet on is the lead's call, within
  the budget; outside it, it becomes a draft.
- At most 3 tasks `In Progress` at once, never two with the same `domain:`
  label.
- A task's own state (status, plan, notes, criteria, final summary) is edited in
  its worktree, so it travels with its pull request. Drafts, milestones, added
  tasks and assignments go on a short-lived board branch
  (`start_item.py --board <topic>`), merged by its own pull request: draft
  numbers clash across worktrees.
- `backlog doctor` is clean before every commit that touches `backlog/`.

| What | Command |
| --- | --- |
| The board, one task | `backlog task list --plain`, `backlog task view B-NNN --plain` |
| The tasks ready to start, a milestone's tasks | `backlog task list --ready --plain`, `backlog task list -m "<name>" --plain` |
| The human's inbox | `backlog task list -a @zyniel --plain` |
| Start, plan, note, close | `backlog task edit B-NNN -s "In Progress" --plan "..."`, `--append-notes "..."`, `--check-ac N`, `--check-dod N`, `--final-summary "..."`, `-s Done` |
| Ideas | `backlog draft create "<title>" -d "..." -l follow-up`, `backlog draft list --plain` |
| Milestones, docs | `backlog milestone list`, `backlog doc list` (the human's guide, the release checklist) |

## Commands

Everything runs through uv: never `pip` or a bare `python`.

| What | Command |
| --- | --- |
| Install or update the environment | `uv sync` |
| Full quality gate (what CI runs) | `uv run python scripts/gate.py` |
| Gate before the code exists | `uv run python scripts/gate.py --stage tests` |
| Quick gate: static checks, tests without a browser, browser tests of the domain `grids` and of spec 027 | `uv run python scripts/gate.py --specs grids,027 --browsers chromium` |
| Gate without browser tests | `uv run python scripts/gate.py --tests other` |
| Gate in the three engines | `uv run python scripts/gate.py --browsers all` |
| One engine's browser tests only (a CI job) | `uv run python scripts/gate.py --skip-static --tests browser --browsers firefox` |
| All tests, or one file (browser tests in Chromium) | `uv run pytest`, `uv run pytest <file>` |
| Format, lint, type check | `uv run black .`, `uv run ruff check --fix .`, `uv run pyrefly check` |
| Web client: install, type check, build | `npm --prefix web ci`, `npm --prefix web run check`, `npm --prefix web run build` |
| Browsers for the browser tests | `uv run playwright install chromium firefox webkit` |
| Rebuild the screens sheet (after any change of look) | `uv run python docs/design/screens_sheet/build.py` |
| A task's branch and worktree, from `origin/main` | `uv run python scripts/start_item.py B-NNN` |
| A board branch and worktree for backlog edits | `uv run python scripts/start_item.py --board <topic>` |

Black is the only formatter. Ruff is a linter only: never run `ruff format`.

## Building a change

Before a spec or code, read `specs/_map.md` (the domains, how domain specs work,
the glossary), then only the files the task names. `specs/_architecture.md`
holds the stack and the modeling rules.

1. `/milestone <idea>`: the pitch and its tasks in a `backlog: milestone
   <name>` pull request; the human bets by merging it.
2. `/feature B-NNN`, task by task: spec-writer and spec-checker, test-writer,
   implementer, then reviewer (two rounds at most), with one commit per phase;
   then the pull request, with auto-merge.
3. `/milestone close <name>`: the verdict, checked by an independent review, in
   a `backlog: close <name>` pull request; the human accepts by merging it.

`/task <milestone> <change>` adds one task inside a milestone's budget, or to
Upkeep. A tooling task has the label `tooling` and no spec: the lead builds it
on its branch. `prepare release vX.Y.Z` follows the release checklist
(`backlog doc list`).

## Roles

| Role | Model | Writes | Never touches |
| --- | --- | --- | --- |
| spec-writer | Opus | `specs/`, `docs/design/` | everything else |
| test-writer | Sonnet | `tests/` | `src/`, `specs/` |
| implementer | Sonnet | `src/`, `web/`, `docs/` (not `docs/design/`), `README.md` | `tests/`, `specs/`, `docs/design/`, tooling |
| reviewer | Opus | nothing (read-only) | everything |
| spec-checker | Opus | nothing (read-only) | everything |

`scripts/hooks/guard_paths.py` holds each role to its paths. The lead writes
`backlog/` and the specs' status lines (`approved` on the spec-checker's
APPROVED, `done` at a task's close). A role sees none of this conversation: each
message to one stands on its own.

## Models and effort

The weekly token budget is the constraint, and context size costs more than
model price.

- No agent runs above `high` effort, on any model.
- The roles' models are set in their files. Pass `model: "opus"` to the
  test-writer or the implementer only when the criteria are about layout,
  painted pixels or timing in a browser, or after a review sent the work back.
- Architecture decisions run on Fable at `high` effort, or on Opus at `high`
  when the human's Fable tokens are used up: the `Plan` agent proposes the
  options of the pitch or the task, and the spec-writer writes the change. An
  architecture decision adds, splits or merges a domain; changes an interface
  between modules (protocol messages, stored data, a module's public names);
  changes `specs/_architecture.md` or the baselines of `specs/product.md`; or
  changes the design of the tooling. The lead picks among the options, unless
  the pick falls in an escalation class.
- Small fixes (a flaky test, a typo, an import): Sonnet at `medium`.
- The lead runs on Opus at `high`, in a fresh session per task once the
  context has grown large.

## Specs and criteria

- A domain spec, `specs/<area>/<file>.md`, says what is true now, in the format
  of `specs/_template.md`. `specs/product.md` holds the core flows, the stable
  routes and the baselines every domain keeps.
- Status is `draft`, `approved` or `done`, on a `status:` line in the front
  matter. A change makes a `done` file `draft` until the spec-checker approves
  it.
- A criterion is a bullet starting with a bold id: `- **AC-1** ...`. Numbers are
  per file and never reused.
- A criterion is proven by a test `def test_acN_...` in `tests/test_<name>_*.py`
  (the domain `co-op` gives `test_co_op_*`), or by its pointer `(← NNN AC-n)` to
  the tests of v1.1.0 in `tests/test_spec_NNN_*.py`. The gate checks every link
  both ways; `specs/_map.md`, "Criteria and their tests", has the rules.
- `specs/_archive/v1.1.0/` is the build record of v1.1.0: never edited.
- `docs/design/cell-sheet.html` is drawn by hand. `docs/design/screens-sheet.html`
  is generated by `build.py`: never edit it. The gate fails when it is not what
  its sources build (`build.py --check`).

## Quality gate

- `scripts/gate.py` runs the static checks, then the tests in parallel
  (pytest-xdist, at a low priority), then on their own the timing-sensitive
  files listed in `SERIAL_TEST_FILES` (`scripts/gate_browsers.py`). A test file
  that measures a duration or a pace goes in that list.
- Engines come from `--browsers` or `NOCK_BROWSERS` (default `chromium`); an
  engine that is not installed is left out with a warning. Workers come from
  `--workers` or `NOCK_WORKERS`, which `.claude/settings.json` sets.
- One gate at a time runs its tests: another waits up to 10 minutes for the
  lock in `.git/`, then fails naming the gate that holds it.
- When a role finishes, `scripts/hooks/role_gate.py` runs the gate: `--stage
  tests` for the test-writer, and for the implementer the quick gate of the
  domains and numbered specs the branch changed since `main`. A role held by a
  failure outside its files (a stale test, for the implementer) says so in its
  report and finishes again without changing anything; the hook then lets it
  stop.
- CI runs on Ubuntu: Chromium on each pull request, plus Firefox and WebKit after
  a merge into `main` or when started by hand. It runs only the gate jobs the
  changed files can affect. There is no Windows job.

## Git

- Work on a `feat/b-NNN-short-name` branch in a worktree of its own under
  `.claude/worktrees/`, never on `main`. Never run `git switch` or `git
  checkout` in the main checkout: several sessions share it.
- A task's number comes from `backlog task create` and never changes; its
  branch `feat/b-NNN-<short-name>` and worktree from `scripts/start_item.py`.
  On a clash, stop and report instead of renumbering.
- One branch and one pull request per task. The lead pushes it, opens the pull
  request and turns on auto-merge (`gh pr merge --auto --merge`), except for a
  held task and for the `backlog: milestone` and `backlog: close` pull requests,
  which the human merges. Never merge one yourself. After the merge, delete the
  remote branch and the worktree.

## Code standards

The `python-standards` skill holds them: PEP 8, 88-character lines, full type
annotations, Google-style docstrings, `from __future__ import annotations` in
every module, and readable code (plain loops and named variables rather than
clever one-liners). No `# noqa`, no `# type: ignore`. Write invisible characters
as `\N{NAME}` escapes, never raw, and keep LF line endings.

## Environment

- The human works on Windows 11. CI and cloud sessions run Linux.
- In a cloud session, `.claude/hooks/session-start.sh` installs the Python and
  web dependencies and the three test browsers before the first prompt, and
  the browsers draw text in CI's font, DejaVu Sans
  (`.claude/hooks/ci-fonts.conf`).
