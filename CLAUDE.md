# Nock

Nock is an online collaborative arrowword (mots fléchés) game: a Python server
and a Svelte + TypeScript client. The name is the notch at the back of an arrow.
It is built spec-first by Claude Code agents. The human owns the product. The
main session is the lead: it plans, delegates to the four roles in
`.claude/agents/` and keeps `Backlog.md`; it writes no tests and no code.

This file is for the lead. The roles carry their own instructions and do not
load it.

## Rules

- No implementation without an approved spec, and none before its tests exist:
  the tests, written from the spec by another agent, decide what gets built.
- Only the human approves a brief or a spec change. The lead sets a status line
  only on their word.
- Take technical decisions yourself and report them: tooling details, test
  setup, small spec slips, reviewer suggestions. Ask the human about product
  scope or behaviour they would notice, money and accounts, and pushing to
  `main`.
- Tooling and new dependencies (Python or npm) are the human's call: ask first.
  Tooling means `pyproject.toml`, `scripts/`, `.claude/`, `.github/` and, in
  `web/`, `package.json`, `package-lock.json` and the Vite, Svelte and
  TypeScript config files. Exception: the lead fixes an incoherence or a
  weakness of the tooling (a timeout, a flaky setup, a hook that blocks the
  wrong thing) without asking, in a pull request of its own.
- Specs and design files state what is true now, with no dated notes and no
  history. The reason for a change goes in its commit message.
- The visual documentation is always current, so the human can see the whole
  look at any time. A change that alters what a screen looks like updates the
  design file of that part of the screen in `specs/_design/` and redraws it in
  `docs/design/` in the same commit, before tests and code: the cell sheet by
  hand, the screens sheet from `docs/design/screens_sheet/`, then rebuilt. The
  reviewer blocks a change of look that is not drawn.

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
| Claim a backlog item: its number, branch and worktree | `uv run python scripts/claim_item.py <short-name>` |
| The items in flight and the spec files they change | `uv run python scripts/claim_item.py --list` |

Black is the only formatter. Ruff is a linter only: never run `ruff format`.

## Building a change

Before a spec or code, read `specs/_map.md` (the domains, how domain specs work,
the glossary), then only the files the task names. `specs/_architecture.md`
holds the stack and the modeling rules.

1. `/new-spec <description>`: the lead claims the item, writes its brief in
   `Backlog.md` and stops for the human's approval; the spec-writer changes the
   domain specs, and the human approves the change.
2. `/feature B-NNN`: test-writer, implementer, then reviewer (two rounds at
   most), with one commit per phase.

A tooling change skips `/new-spec`: the lead claims the item, writes its brief
in `Backlog.md` with "Domains: none (tooling only)", and builds it on its
branch.

## Roles

| Role | Model | Writes | Never touches |
| --- | --- | --- | --- |
| spec-writer | Opus | `specs/`, `docs/design/` | everything else |
| test-writer | Sonnet | `tests/` | `src/`, `specs/` |
| implementer | Sonnet | `src/`, `web/`, `docs/` (not `docs/design/`), `README.md` | `tests/`, `specs/`, `docs/design/`, tooling |
| reviewer | Opus | nothing (read-only) | everything |

`scripts/hooks/guard_paths.py` holds each role to its paths. The lead writes
`Backlog.md` and, on the human's word, the status lines. A role sees none of
this conversation: each message to one stands on its own.

## Models and effort

The weekly token budget is the constraint, and context size costs more than
model price.

- No agent runs above `high` effort, on any model.
- The roles' models are set in their files. Pass `model: "opus"` to the
  test-writer or the implementer only when the criteria are about layout,
  painted pixels or timing in a browser, or after a review sent the work back.
- Architecture decisions run on Fable at `high` effort, or on Opus at `high`
  when the human's Fable tokens are used up: the `Plan` agent proposes the
  brief's options, and the spec-writer writes the change. An architecture
  decision adds, splits or merges a domain; changes an interface between
  modules (protocol messages, stored data, a module's public names); changes
  `specs/_architecture.md` or the baselines of `specs/product.md`; or changes
  the design of the tooling.
- Small fixes (a flaky test, a typo, an import): Sonnet at `medium`.
- The lead runs on Opus at `high`, in a fresh session per backlog item once the
  context has grown large.

## Specs and criteria

- A domain spec, `specs/<area>/<file>.md`, says what is true now, in the format
  of `specs/_template.md`. `specs/product.md` holds the core flows, the stable
  routes and the baselines every domain keeps.
- Status is `draft`, `approved` or `done`, on a `status:` line in the front
  matter. A change makes a `done` file `draft` until the human approves it.
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
- An item's number, branch and worktree come from `scripts/claim_item.py`, and
  the number never changes. On a clash, stop and report instead of renumbering.
- One branch and one pull request per item. After the merge, delete the remote
  branch and the worktree.
- Do not push and do not open pull requests unless the human asks.

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
