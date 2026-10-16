# Nock

Nock is an online collaborative arrowword (mots fléchés) game, named after the
notch at the back of an arrow. It is a spec-first Python project where a small
team of Claude Code agents does the building: you write or approve a spec, and
the agents write the tests, then the code, then review it. `CLAUDE.md` is the short version the agents read; this file
is for you.

## 1. One-time setup (Windows, PowerShell)

Install the tools once:

```powershell
winget install --id Git.Git -e                     # git (also gives Claude Code a Bash shell)
winget install --id astral-sh.uv -e                # uv
irm https://claude.ai/install.ps1 | iex            # Claude Code
winget install --id GitHub.cli -e                  # gh, optional, for pull requests
```

Open a new terminal, then in this folder:

```powershell
cd K:\Projects\nock
uv sync                              # creates .venv with Python 3.14, ruff, black, pyrefly, pytest
uv run python scripts/gate.py        # must end with "GATE PASSED (full)."
git init -b main
git add .
git commit -m "chore: agent team starter kit"
claude                               # log in with your Claude account, accept the trust prompt
```

Accepting the trust prompt matters: the hooks in `.claude/settings.json` only run
in a folder you have trusted.

## 2. Building a feature

Inside `claude`, in this folder:

1. **Write the spec.** `/new-spec` followed by the feature and your acceptance
   criteria in plain words. The spec-writer creates `specs/NNN-name.md` and lists
   its open questions. You can also copy `specs/_template.md` and write it yourself.
2. **Approve it.** Read the spec. Fix what is wrong, then tell Claude it is
   approved (or set `status: approved` yourself). Nothing gets built from a draft.
3. **Build it.** `/feature specs/NNN-name.md`. The lead runs three agents in
   order and commits after each one:

   | Phase | Agent | Result | Blocked until |
   | --- | --- | --- | --- |
   | Tests | test-writer | `tests/test_spec_NNN_*.py`, failing | lint is clean and every AC has a test |
   | Code | implementer | code under `src/nock/` | the full gate passes |
   | Review | reviewer | `APPROVE` or `CHANGES REQUESTED` | read-only, reports to you |

4. **Publish it.** Claude stops before pushing. You run
   `git push -u origin <branch>` and `gh pr create --fill`; GitHub Actions then
   runs the same gate.

Spec `002-grid-schema` shows the three files a feature produces: the spec, its
tests (`tests/test_spec_002_grid_schema.py`) and its code (`src/nock/grid.py`).
`specs/_archive/` keeps what is no longer used: the starter example
`001-slugify` and the original backlog, `complete.md`, that specs 002 to 038 were
split from. The gate, pytest and pyrefly ignore it.

## 3. Where things go

| You want to change | Put it in | Loaded |
| --- | --- | --- |
| Facts and rules every agent needs all the time | `CLAUDE.md` | Always, by the lead and every agent. Keep it short. |
| A procedure or a body of knowledge (your skills) | `.claude/skills/<name>/SKILL.md` | On demand, or when you type `/<name>` |
| A role: what one agent does, its tools and model | `.claude/agents/<name>.md` | When that agent is started |
| A rule that must hold every time, whatever the agent thinks | `scripts/hooks/` + `.claude/settings.json` | Automatically, on the event |
| Lint, format, type and test settings | `pyproject.toml` | By the tools |

### Adding your own skills

A skill is a folder with a `SKILL.md` inside. Three places work:

- **This project:** `K:\Projects\nock\.claude\skills\<name>\SKILL.md`. Committed
  with the repo, so the agents get it on any machine and in CI-like setups. Put
  anything specific to this project here.
- **All your projects on this PC:** `%USERPROFILE%\.claude\skills\<name>\SKILL.md`.
- **Your Claude account:** skills you enabled in the Claude app are downloaded
  automatically into Claude Code when you are logged in with the same account.
  You do not copy anything.

Then decide who uses it:

- Every agent can call any of those skills when its description matches the task.
  A clear `description:` line is what makes that happen.
- To make sure a given agent always has a skill loaded, add its name to the
  `skills:` list at the top of that agent's file (see
  `.claude/agents/implementer.md`).

The kit ships three skills: `python-standards` (the coding rules, preloaded into
the test-writer, implementer and reviewer), `new-spec` and `feature` (the two
commands above).

### Running the server with a database

Start the server with `uv run python -m nock`. It listens on
`http://127.0.0.1:8000`; the `NOCK_HOST` and `NOCK_PORT` environment variables
change the address and the port. An empty variable counts as unset. `NOCK_PORT`
must be a whole number from 1 to 65535, written with the digits 0 to 9; any
other value stops the start with a message. Use this command rather than
`uvicorn nock.server:app`: it also sets the WebSocket frame limit of spec 036
(8,192 bytes), where uvicorn alone accepts frames of 16 MiB.

The rooms are stored in the SQLite file named by the `NOCK_DATABASE`
environment variable. When it is unset, rooms live in memory and are lost when
the server stops. The folder of the file must exist:

```powershell
New-Item -ItemType Directory -Force data
$env:NOCK_DATABASE = "data/nock.sqlite3"
uv run python -m nock
```

(bash: `NOCK_DATABASE=data/nock.sqlite3 uv run python -m nock`)

## 4. The quality gate

`scripts/gate.py` is the single definition of "done". It runs:

1. `ruff check .` (PEP 8, naming, docstrings, annotations, import order)
2. `black --check .` (formatting)
3. spec traceability: every `- **AC-n**` in a spec has a `test_acn_...` test, and
   no test points to a criterion that does not exist
4. `pyrefly check` (types), `svelte-check` and the vite build of `web/`
5. `pytest`, in parallel (pytest-xdist), then the timing-sensitive test files
   on their own

`--stage tests` stops after step 3. That is the stage the test-writer has to
pass, because at that point the code does not exist yet and the tests are
supposed to fail.

The browser tests run in Chromium and WebKit by default; `--browsers all` (or
`NOCK_BROWSERS=all`) adds Firefox. `--tests browser` or `--tests other` runs only
the tests with or without a browser, and `--skip-static` skips steps 1 to 4
except the build. CI uses them to run one job per engine and system.
`--specs 027,028` keeps the browser tests of those specs only (the tests without
a browser all run): the quick gate an implementer passes before it finishes.

The same script runs in three places:

- **You:** `uv run python scripts/gate.py`
- **The agents:** `scripts/hooks/role_gate.py` runs it when the test-writer or the
  implementer tries to finish, and sends the failures back until it is green.
  The test-writer passes `--stage tests`; the implementer passes the quick gate
  of the specs its branch changed (`--specs`, Chromium only), which fits in the
  hook's time. CI runs everything. An agent held by a failure it may not fix
  (a test only the test-writer changes) reports it and finishes again without
  changing anything; the hook then lets it stop.
- **GitHub:** `.github/workflows/ci.yml` on every pull request and push to `main`.

A second hook, `scripts/hooks/guard_paths.py`, blocks an agent that tries to edit
a file outside its folders (for example the implementer editing a test).

### Trying the hooks without Claude

Each hook reads a small JSON message and answers with an exit code, so you can
play both sides from PowerShell:

```powershell
# The implementer tries to edit a test: expect "Blocked: ..." and exit code 2
'{"agent_type":"implementer","cwd":".","tool_input":{"file_path":"tests/test_x.py"}}' |
  uv run --no-project python scripts/hooks/guard_paths.py; $LASTEXITCODE

# The implementer tries to finish: runs the quick gate, expect exit code 0
'{"agent_type":"implementer","cwd":"."}' |
  uv run --no-project python scripts/hooks/role_gate.py; $LASTEXITCODE
```

## 5. GitHub

```powershell
gh auth login
gh repo create nock --private --source . --push
```

CI needs no secret and no configuration. To make it binding, protect `main` in the
repository settings and require the `Quality gate` check before merging: it
passes only when every job of CI passed.

## 6. From subagents to an agent team

The default mode uses **subagents**: the three agents run one after the other
inside your session and report to the lead. It is the cheaper mode and it fits a
feature that is built in sequence.

An **agent team** runs separate Claude Code sessions that share a task list and
talk to each other. It pays off when a feature splits into parts that touch
different files. It is experimental and uses several times more of your plan's
usage.

To use it:

1. In `.claude/settings.json`, set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` to `"1"`.
2. In a large spec, fill the "Work packages" section so each implementer owns
   different files.
3. Run `/feature specs/NNN-name.md team`.

Known limits of teams today: they need an interactive session, resuming a session
does not bring teammates back, and split panes do not work in Windows Terminal
(teammates show in a panel under the prompt instead).

## 7. Changing the kit

- **Package name:** the package is `nock` in `src/nock/`. To rename it, ask Claude:
  "rename the package nock to X everywhere, then run the gate".
- **Models:** each agent file has a `model:` line. The test-writer and implementer
  use `sonnet`; the spec-writer and reviewer use `inherit` (the model of your
  session).
- **Stricter or looser rules:** edit `[tool.ruff.lint]` in `pyproject.toml`.
- **Line length:** 88 in `[tool.black]` and `[tool.ruff]`. Change both together.
- **Another role** (security review, documentation): copy an agent file, give it
  a new `name` and `description`, and add a step to
  `.claude/skills/feature/SKILL.md`.
