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
| Tests only | `uv run pytest` |
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
- `tests/test_spec_NNN_short_name.py`: the tests of spec NNN.
- `src/nock/`: the package.
- `web/`: the Svelte + TypeScript client, built by Vite into `web/dist`.
- `scripts/gate.py`: the quality gate.
- `.claude/agents/`: the four roles. `.claude/skills/`: standards and workflows.
  `scripts/hooks/`: the scripts that enforce the rules below.

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
  warning (`scripts/gate_browsers.py`); CI still runs all three engines.

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
human: ask first.

## Code standards

The `python-standards` skill has the full list. In short: PEP 8, 88-character
lines, full type annotations, Google-style docstrings, `from __future__ import
annotations` in every module, and readable code (plain loops and named variables
rather than clever one-liners). No `# noqa`, no `# type: ignore`.

## Git

Work on a `feat/...` branch, never directly on `main`. Do not push and do not open
pull requests unless the human asks.
