# Nock

Nock is an online collaborative arrowword (mots fléchés) game. The name is the
notch at the back of an arrow. It is a Python project built spec-first by a small
team of Claude Code agents. A human writes or approves a spec; agents write the
tests, then the code, then review it.

Before writing a spec or code, read `specs/_reference.md` (reference grid, spec
index) and `specs/_architecture.md` (stack and modeling rules).

## Commands

Everything runs through uv. Do not use `pip` or a bare `python`.

| What | Command |
| --- | --- |
| Install or update the environment | `uv sync` |
| Full quality gate (same as CI) | `uv run python scripts/gate.py` |
| Gate while the code does not exist yet | `uv run python scripts/gate.py --stage tests` |
| Gate with the browser tests in all three engines | `uv run python scripts/gate.py --browsers all` |
| Gate, one engine's browser tests only (a CI job) | `uv run python scripts/gate.py --skip-static --tests browser --browsers firefox` |
| Gate, static checks and tests without a browser | `uv run python scripts/gate.py --tests other` |
| Quick gate: static checks, tests without a browser, browser tests of specs 027 and 028 | `uv run python scripts/gate.py --specs 027,028 --browsers chromium` |
| Tests only (browser tests in Chromium) | `uv run pytest` |
| Fix formatting | `uv run black .` |
| Fix lint findings | `uv run ruff check --fix .` |
| Type check | `uv run pyrefly check` |
| Install the web client dependencies | `npm --prefix web ci` |
| Web client type check | `npm --prefix web run check` |
| Build the web client | `npm --prefix web run build` |
| Install the browsers for browser tests | `uv run playwright install chromium firefox webkit` |

Black is the only formatter. Ruff is a linter here; do not run `ruff format`.

## Layout

- `specs/NNN-short-name.md`: one spec per feature, copied from `specs/_template.md`.
- `tests/test_spec_NNN_*.py`: the tests of spec NNN, in one file
  (`test_spec_NNN_short_name.py`) or, past about 800 lines, one file per
  criterion group with the shared setup in `tests/specNNN_harness.py`.
- `src/nock/`: the package.
- `web/`: the Svelte + TypeScript client, built by Vite into `web/dist`.
- `scripts/gate.py`: the quality gate.
- `.claude/agents/`: the four roles. `.claude/skills/`: standards and workflows.
  `scripts/hooks/`: the scripts that enforce the rules below.
- `.claude/hooks/session-start.sh`: in a Claude Code cloud session, installs the
  Python and web dependencies and the three test browsers before the first prompt.

## How a feature gets built

1. `/new-spec <description>` has the spec-writer draft `specs/NNN-....md`.
2. The human reads it and approves it. Only a human sets `status: approved`.
3. `/feature specs/NNN-....md` runs test-writer, then implementer, then reviewer,
   with one commit per phase.

Never write implementation for behaviour that has no approved spec, and never
write the implementation before its tests exist.

## Rules the tooling relies on

- An acceptance criterion is a bullet starting with a bold id: `- **AC-1** ...`.
- A test is linked to its criterion by name: `def test_ac1_...` in the test file
  of that spec. The gate fails when a criterion has no test, or when a test points
  to a criterion that does not exist.
- Spec status is one of `draft`, `approved`, `done`, on a line `status: ...` in the
  front matter.
- An agent may refine an `approved` or `done` spec (a review finding, a
  contradiction, a missing rule). It keeps the status and adds a dated note next
  to each change; the tests follow before the code. Only a human sets `approved`.
- The gate leaves out the tests of a browser engine that is not installed, with a
  warning (`scripts/gate_browsers.py`). CI runs, on Ubuntu, Chromium for each
  pull request, and Firefox and WebKit too after a merge into `main` or when
  started by hand (human decision, 2026-10-21; no Windows job).
- The gate runs the tests in parallel (pytest-xdist), then the timing-sensitive
  files listed in `SERIAL_TEST_FILES` (`scripts/gate_browsers.py`) on their own.
  A test file that measures a duration or a pace (a latency percentile, a time
  budget, a time window) goes in that list; a check that only waits up to a
  bound for a change stays in the parallel pass unless it flakes there.
- The gate's engines come from `--browsers` or the `NOCK_BROWSERS` environment
  variable (default `chromium`).
- When a role finishes, `scripts/hooks/role_gate.py` runs the gate: the
  test-writer's `--stage tests`, the implementer's quick gate (the specs whose
  spec, test or harness files the branch changed since `main`, with `--specs`
  and Chromium). CI runs everything. A role held by a failure outside its
  files (a stale test, for the implementer) says so in its report and finishes
  again without changing anything; the hook then lets it stop.
- In a cloud session, the browsers draw text in CI's font, DejaVu Sans
  (`.claude/hooks/ci-fonts.conf`, installed by the session-start hook).

## Who may write what

| Role | Writes | Never touches |
| --- | --- | --- |
| spec-writer | `specs/` | everything else |
| test-writer | `tests/` | `src/`, `specs/` |
| implementer | `src/`, `web/`, `docs/`, `README.md` | `tests/`, `specs/`, tooling |
| reviewer | nothing (read-only) | everything |

Tooling means `pyproject.toml`, `scripts/`, `.claude/`, `.github/` and, in `web/`,
`package.json`, `package-lock.json` and the Vite, Svelte and TypeScript config
files. Changing it, or adding a dependency (Python or npm), is a decision for the
human: ask first. Exception (human decision, 2026-10-16): the lead fixes an
incoherence or a weakness of the tooling (a timeout, a flaky setup, a hook that
blocks the wrong thing) without asking, in a pull request of its own; new
tooling behaviour and new dependencies still need the human.

## Code standards

The `python-standards` skill has the full list. In short: PEP 8, 88-character
lines, full type annotations, Google-style docstrings, `from __future__ import
annotations` in every module, and readable code (plain loops and named variables
rather than clever one-liners). No `# noqa`, no `# type: ignore`.

## Git

Work on a `feat/...` branch, never directly on `main`. Do not push and do not open
pull requests unless the human asks.
