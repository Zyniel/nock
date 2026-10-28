# Nock

Nock is an online collaborative arrowword (mots fléchés) game, named after the
notch at the back of an arrow. It is a spec-first Python project where a small
team of Claude Code agents does the building: you approve a brief and a spec
change, and the agents write the tests, then the code, then review it.
`CLAUDE.md` is the short version the agents read; this file is for you.

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

The browser tests need the web client's dependencies and the test browsers; run
`npm --prefix web ci` first in every checkout (a stale `node_modules` builds a
client that never starts, and every browser test then fails the same way), and
`uv run playwright install chromium firefox webkit` once.

## 2. Adding grids

The repository holds no grid: a fresh server lists none. A grid enters the
product as a standard ipuz ArrowWord file in the `grids/` folder, named in an
index that holds what Nock decides about it (`specs/content/grid-files.md`).

**Where the server looks.** In the `grids/` folder at the root of the
repository, next to `src/` and `web/` (`GRIDS_DIR` in `src/nock/catalogue.py`,
worked out from the place of that module). No environment variable and no
option changes it. The folder is not created for you: create it. A missing
folder, or a folder without an index, gives an empty catalogue. The server reads
the folder once, when it starts, so restart the server after any change.

**To add a grid.** Drop its `.ipuz` file in `grids/`, then add an entry for it to
the index `grids/catalogue.json`. A file the index does not name is ignored.
Grids are read in the index's order, and the grid number comes from the entry,
not from the file name.

**The index.** `grids/catalogue.json` is a JSON array of entries. Each one holds
exactly these keys, and no other:

| Key | Rule |
| --- | --- |
| `number` | Whole number from 1 to 999999999, unique in the index. |
| `file` | Name of the grid file, directly inside `grids/` (no `/` or `\`), ending in `.ipuz`. Two entries may not name the same file. |
| `published` | `true` or `false`. A grid that is not published is not listed and its address answers "not found". |
| `source`, `licence` | The rights, see below. |
| `withdrawn` | Optional `true` or `false` (default `false`). A withdrawn grid is not listed and no new room can start on it; rooms already created on it keep working. |

```json
[
  {
    "number": 1,
    "file": "grid-0001.ipuz",
    "published": true,
    "source": "Commande Nock 2026",
    "licence": "Contrat d'auteur Nock n° 1"
  }
]
```

**The grid file.** A JSON object (UTF-8) of the ipuz v2 ArrowWord kind. It holds
`version` (`http://ipuz.org/v2`), `kind` (`["http://ipuz.org/crossword/arrowword#1"]`),
`clueplacement` (`"blocks"`), `dimensions`, `puzzle`, `clues`, `author`, `date`
(`MM/DD/YYYY`) and `difficulty` (the force, 1 to 4), and optionally `solution` and
the descriptive texts `title`, `editor`, `publisher`, `publication`, `url`,
`uniqueid`, `origin` and `copyright` (kept with the grid, never shown to
players). Every coordinate is `[column, row]`, counted from zero. In `puzzle`,
`0` is a letter cell and `"#"` a block; a block with one or two clues at its
`location` is a clue cell. Each clue holds `clue`, `location`, `cells` (its word,
which gives the arrow), `answer` and optionally `enumeration`. The example is
the FX-01 grid (`tests/fixtures/fx01.ipuz`), cut after its first clues:

```json
{
  "version": "http://ipuz.org/v2",
  "kind": ["http://ipuz.org/crossword/arrowword#1"],
  "clueplacement": "blocks",
  "dimensions": {"width": 5, "height": 5},
  "author": "Équipe Nock",
  "date": "10/01/2026",
  "difficulty": 2,
  "puzzle": [
    ["#", 0, "#", "#", "#"],
    [0, 0, 0, 0, 0],
    ...
  ],
  "clues": {
    "Clues": [
      {"clue": "Passoire fine", "location": [0, 0], "cells": [[0, 1], [1, 1], [2, 1], [3, 1], [4, 1]], "answer": "TAMIS", "enumeration": "5"},
      {"clue": "De la marine", "location": [0, 0], "cells": [[1, 0], [1, 1], [1, 2], [1, 3], [1, 4]], "answer": "NAVAL", "enumeration": "5"},
      ...
    ]
  }
}
```

A compound word (`ARC-EN-CIEL`) says where it breaks with its `enumeration`
(`3-2-4`), with hyphens in its `answer`, and with `dashed` edges in `puzzle`;
they must agree. The reader is strict: an unsupported key, a clue number, a
`<` or `>` in a clue text or a `solution` that disagrees with the answers
refuses the file. Any tool that reads and writes ipuz can open the file;
`nock.ipuz.write_ipuz` writes one.

A grid is refused when an arrow points outside the grid or to a cell that is not
a letter, when an answer is not as long as its word, when two clues give the same
word, when a letter belongs to no word, when a run of two or more letters has no
clue, or when two crossing words disagree on their shared letter. The answer is
normalised to the letters A to Z (accents and the ligatures Œ and Æ are folded;
spaces, hyphens and apostrophes are removed).

**Credits and licence.** `author` (in the grid file), `source` and `licence` (in
the index) are required: the creator of the grid, where it comes from, and the
licence or contract that lets you publish it. Each one is a text of 1 to 200
characters once the spaces at both ends are removed. A key that is missing, blank,
too long or not a text refuses the grid, so the server does not start with a grid
whose rights are not written down.

**Converting former grid files.** Grids written in the former format (one
`<name>.json` file per grid, with the listing data and the credits beside the
grid) become ipuz files and an index with:

```bash
uv run python -m nock.ipuz_convert SOURCE TARGET
```

It writes `TARGET/<name>.ipuz` for each file of `SOURCE` and
`TARGET/catalogue.json`. If a source file is refused, or the index or an `.ipuz`
file already exists in `TARGET`, it writes nothing, names that file and exits
with a non-zero code.

**An invalid index or file.** `load_catalogue` stops at the first problem, in the
order of the index, and raises `CatalogueError`; the server loads the folder when
`nock.server` is imported, so `uv run python -m nock` stops with that error and
its traceback instead of starting. The last line gives the file name (`catalogue.json`
for the index) and the reason, for example:

```text
nock.catalogue.CatalogueError: grid-0002.ipuz: invalid grid file: words TAMIX and SENT disagree at (1, 4): X against S
nock.catalogue.CatalogueError: catalogue.json: invalid index: duplicate grid number 1
```

Fix or remove the entry or the file and start again.

**Checking the result.** Build the web client once (`npm --prefix web ci`, then
`npm --prefix web run build`; without it, `/` answers 503 with "The web client
is not built"), start the server with `uv run python -m nock`, and open
`http://127.0.0.1:8000/`. The page lists the published grids, newest
publication date first, with their number, date, force, size and word count.
`http://127.0.0.1:8000/api/grids` gives the same list as JSON, without any
clue, and `/g/<number>` opens a grid.

## 3. Building a feature

The work queue is `Backlog.md`: one item per change, moving through `brief`,
`approved`, `ready`, `building` and `done`. The behaviour lives in the domain
specs, `specs/<area>/<file>.md`; `specs/_map.md` lists them and explains how they
work. Inside `claude`, in this folder:

1. **Write the brief.** `/new-spec` followed by the feature or change in plain
   words. The lead claims the item's number, branch and worktree
   (`scripts/claim_item.py`), writes a brief in `Backlog.md` (`B-NNN`) and waits
   for you. Approve it, or correct it.
2. **Approve the spec change.** The spec-writer changes the domain specs of the
   item (and, for a change of look, `specs/_design/` and `docs/design/`) and
   lists its open questions. Read the change, fix what is wrong, then tell Claude
   it is approved: the item becomes `ready`. Nothing gets built from a draft.
3. **Build it.** `/feature B-NNN`. The lead works on a `feat/b-NNN-...` branch,
   runs three agents in order and commits after each one:

   | Phase | Agent | Result | Blocked until |
   | --- | --- | --- | --- |
   | Tests | test-writer | `tests/test_<name>_*.py` of the domain (`co-op` gives `test_co_op_*`), failing | lint is clean and every AC has a test |
   | Code | implementer | code under `src/nock/` and `web/` | the quick gate passes |
   | Review | reviewer | `APPROVE` or `CHANGES REQUESTED` | read-only, reports to you |

4. **Publish it.** Claude stops before pushing. You run
   `git push -u origin <branch>` and `gh pr create --fill`; GitHub Actions then
   runs the same gate.

`specs/_archive/v1.1.0/` holds the numbered specs (`002-...` to `048-...`), the
build record of v1.1.0; they are never edited again, and the domain specs point
to their tests. The look is in `specs/_design/`, drawn in `docs/design/`.

## 4. Where things go

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
commands above). The four roles are in `.claude/agents/`.

### Running the server with a database

Start the server with `uv run python -m nock`. It listens on
`http://127.0.0.1:8000`; the `NOCK_HOST` and `NOCK_PORT` environment variables
change the address and the port. An empty variable counts as unset. `NOCK_HOST`
is a host name or an IP address, written with ASCII letters, the digits 0 to 9,
`.` and `-` only; `:` is allowed in an IPv6 address, which is written without
brackets (`::1`, not `[::1]`). The dots of a name cut it into labels of 1 to 63
characters, and only the last label may be empty: a name may end with a dot
(`example.org.`), but `a..b`, `.example` and a label of 64 characters are
refused. `NOCK_PORT` must be a whole number from 1 to 65535, written with the
digits 0 to 9. A refused value (in these two variables or in `NOCK_DATABASE`,
below) stops the start with a message that names the variable and shows the
value. Use this command rather than `uvicorn nock.server:app`: it also sets the
WebSocket frame limit of spec 036 (8,192 bytes), where uvicorn alone accepts
frames of 16 MiB, and it logs warnings and errors only, with no access log, so
that the logs hold no client address (spec 038).

The rooms are stored in the SQLite file named by the `NOCK_DATABASE`
environment variable. Its path may hold spaces, accents and the separators of
both systems, but not a control character (a newline, a tab), a line or
paragraph separator, or a format character other than the zero width joiner and
non-joiner (a zero width space, a byte order mark). When it is unset or empty,
rooms live in memory and are lost when the server stops. The folder of the file
must exist:

```powershell
New-Item -ItemType Directory -Force data
$env:NOCK_DATABASE = "data/nock.sqlite3"
uv run python -m nock
```

(bash: `NOCK_DATABASE=data/nock.sqlite3 uv run python -m nock`)

A room is deleted 30 days after its last edit (a letter written, erased or
locked), with its log, its snapshots and its share link (spec 032). The server
looks for such rooms when it starts and then every hour, and deletes a room at
once when someone opens it after that time. A file written by an older version
of the server is not supported: start with a new file. A deleted room leaves no
copy in the database files: SQLite overwrites its rows with zeros, and the
write-ahead log is emptied after each deletion (spec 038).

### The operator pages

The `NOCK_OPERATOR_TOKEN` environment variable turns on the operator pages of
spec 038: `/ops` shows a dashboard of the rooms created in the last 1, 7 or 30
days (rooms, players, completion, solving time, server latency, dropped
connections) and replays the edits of a room. Its value is a secret of 32 to 256
characters, each one an ASCII letter, a digit 0 to 9, `_` or `-`; spec 038
("Operator access") gives the rule. To make one:

```powershell
$env:NOCK_OPERATOR_TOKEN = uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
uv run python -m nock
```

(bash: `export NOCK_OPERATOR_TOKEN="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))')"`,
then `uv run python -m nock`)

The page asks for the token and keeps it in the browser tab only; ten wrong
tokens from one address within a minute block that address for the rest of the
minute. When the variable is unset or empty, the operator pages are off and
their paths answer as unknown ones. A refused value stops the start with a
message that names the variable and the rule broken, but never shows the value.

### Optional accounts

Accounts (spec 033) let a player get their rooms on another device. They are
off unless both `NOCK_PUBLIC_URL` (the address players open, such as
`https://nock.example`; the links of the e-mails start with it) and
`NOCK_SMTP_HOST` are set. A player signs in with a link sent by e-mail, which
works once and for 30 minutes. The other variables:

| Variable | Default |
| --- | --- |
| `NOCK_SMTP_SECURITY` | `starttls` (or `tls`, or `none`) |
| `NOCK_SMTP_PORT` | 587 with `starttls`, 465 with `tls`, 25 with `none` |
| `NOCK_SMTP_USER`, `NOCK_SMTP_PASSWORD` | no login; set both or neither, never with `none` |
| `NOCK_SMTP_FROM` | required: the sender's address |

The accounts are kept in the `NOCK_DATABASE` file, with the rooms. A refused
value stops the start with a message that names the variable; it never shows
the password.

## 5. Running in Docker

One image runs Nock in development and in production (`Dockerfile`: Node builds
the web client, a Python 3.14 image runs the server as a non-root user). The
settings are the `NOCK_*` variables of section 4, read from an env file that git
ignores: `.env.dev` and `.env.prod`, never committed.

**Development** (http on port 8000, with Mailpit for the e-mails):

```bash
cp .env.dev.example .env.dev          # then edit it
docker compose -f compose.dev.yaml up --build
```

Open `http://localhost:8000`. Mailpit catches every e-mail, the sign-in links
included, at `http://localhost:8025` (its SMTP port is 1025). The `grids/` folder
is mounted read-only, so a new grid needs a restart, not a rebuild.

**Production** (Caddy in front, https with a certificate it gets by itself):

```bash
cp .env.prod.example .env.prod        # then edit it
docker compose up --build -d
```

Caddy serves the domain in `NOCK_DOMAIN` (shell variable or `.env` file; default
`nock.zyniel.com`) on ports 80 and 443, which must reach the host, and the
domain must point to it. In `.env.prod`, `NOCK_PUBLIC_URL` must be the public
https address (`https://nock.zyniel.com`): the links of the sign-in e-mails
start with it. The grids are part of the image: after adding one, run the same
command again, which rebuilds the last layers only.

- **One replica only.** The rooms live in the memory of one process; do not
  scale `nock` above 1.
- **The proxy setting.** Behind Caddy every connection comes from the proxy's
  address. `compose.yaml` sets `FORWARDED_ALLOW_IPS` (uvicorn reads it) so that
  the server trusts Caddy's `X-Forwarded-For` header and each player keeps their
  own address, for the throttles of specs 028 and 038. Nothing else reaches the
  `nock` container: it publishes no port.
- **The database** is `/data/nock.sqlite3` in a named volume (`nock_dev_data` for
  the development stack, `nock_data` for production, prefixed by the project
  name, `nock-dev` or `nock`: see `docker volume ls`). It survives a rebuild and
  `docker compose down`; `down -v` deletes it. To back it up, copy it out while
  the server runs (the write-ahead log makes a plain file copy unsafe, so ask
  SQLite for a snapshot):

  ```bash
  docker compose exec nock /app/.venv/bin/python -c     "import sqlite3; sqlite3.connect('/data/nock.sqlite3').backup(sqlite3.connect('/data/backup.sqlite3'))"
  docker compose cp nock:/data/backup.sqlite3 ./nock-backup.sqlite3
  docker compose exec nock rm /data/backup.sqlite3
  ```

  To restore, stop the stack, put the file back as `nock.sqlite3` in the volume,
  and start it again.
- **Logs and health.** `docker compose logs nock`; the container is `healthy`
  when `/` answers 200 (it answers 503 without a web build).

## 6. The quality gate

`scripts/gate.py` is the single definition of "done". It runs:

1. `ruff check .` (PEP 8, naming, docstrings, annotations, import order)
2. `black --check .` (formatting)
3. spec traceability: every `- **AC-n**` of a domain spec has a `test_acn_...`
   test (or a pointer to the tests of v1.1.0), and no test points to a
   criterion that does not exist
4. `pyrefly check` (types), `svelte-check` and the vite build of `web/`
5. `pytest`, in parallel (pytest-xdist), then the timing-sensitive test files
   on their own

`--stage tests` stops after step 3. That is the stage the test-writer has to
pass, because at that point the code does not exist yet and the tests are
supposed to fail.

The browser tests run in Chromium by default; `--browsers all` (or
`NOCK_BROWSERS=all`) adds Firefox and WebKit. `--tests browser` or `--tests other` runs only
the tests with or without a browser, and `--skip-static` skips steps 1 to 4
except the build. CI uses them: each pull request runs Chromium on Ubuntu, and a
merge into `main` (or a run started by hand from the Actions tab) adds one job
each for Firefox and WebKit, on Ubuntu.
`--specs grids,027` keeps the browser tests of those domains and numbered specs
only (the tests without a browser all run): the quick gate an implementer passes
before it finishes.

The same script runs in three places:

- **You:** `uv run python scripts/gate.py`
- **The agents:** `scripts/hooks/role_gate.py` runs it when the test-writer or the
  implementer tries to finish, and sends the failures back until it is green.
  The test-writer passes `--stage tests`; the implementer passes the quick gate
  of the domains and numbered specs its branch changed (`--specs`, Chromium only), which fits in the
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

## 7. GitHub

```powershell
gh auth login
gh repo create nock --private --source . --push
```

CI needs no secret and no configuration. To make it binding, protect `main` in the
repository settings and require the `Quality gate` check before merging: it
passes only when every job of CI passed.

## 8. From subagents to an agent team

The default mode uses **subagents**: the three agents run one after the other
inside your session and report to the lead. It is the cheaper mode and it fits a
feature that is built in sequence.

An **agent team** runs separate Claude Code sessions that share a task list and
talk to each other. It pays off when a feature splits into parts that touch
different files. It is experimental and uses several times more of your plan's
usage.

To use it:

1. In `.claude/settings.json`, set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` to `"1"`.
2. In the item's brief in `Backlog.md`, split the work so each implementer owns
   different files.
3. Run `/feature B-NNN team`.

Known limits of teams today: they need an interactive session, resuming a session
does not bring teammates back, and split panes do not work in Windows Terminal
(teammates show in a panel under the prompt instead).

## 9. Changing the kit

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

## 10. Credits

The web client uses two font families, served by Nock itself from its own origin
(the npm packages `@fontsource/source-sans-3` and
`@fontsource/ibm-plex-sans-condensed`, built into `web/dist`):

- Source Sans 3, designed by Adobe, under the SIL Open Font License 1.1.
- IBM Plex Sans Condensed, copyright 2019 IBM Corp., under the SIL Open Font
  License 1.1.
