# Handoff

Read this first in a new session, then `CLAUDE.md`, `specs/_reference.md` and
`docs/build-plan.md`. It replaces the long conversation of the session that
wrote it (2026-10-12 to 2026-10-15), so a fresh session can continue cheaply.
Update it at the end of each session.

## Where things stand (2026-10-15)

- Branch `feat/phase5-mvp-ldddid`, pushed, with pull request #6 to `main`
  ("Phase 5 (MVP): check, completion, licensed content, accessibility,
  performance"). The lead is subscribed to its CI and reviews.
- Phase 5 (MVP) is complete: every MVP spec is `done`, including 005, 023, 026,
  035 and 036. The final reviewer approved with no blocking findings; its
  suggestions are applied (spec notes 7094c0b, tests 394f9a7, fix 18740a3).
- Phase 6 (V1): the 13 specs 019-022, 024, 025, 027-029, 032-034, 038 have
  public interfaces and were approved by the human on 2026-10-14 with the
  recommended answer to every open question. Not built.
- Phase 7 (030, 031): untouched, only if the human wants competitive modes.

## Test layout

Every test file over about 800 lines is split by criterion group:
`tests/test_spec_NNN_acNN[_acMM]_<topic>.py`, with the setup shared by several
files in `tests/specNNN_harness.py` (spec 014 also has `spec014_windows_harness.py`;
spec 036 has `spec036_hub_harness.py`, `spec036_browser_harness.py` and
`spec036_frames_harness.py`). `tests/conftest.py`
registers every `spec*_harness.py` for assert rewriting by glob. Fixtures are
thin per-file wrappers around harness functions, so no imported fixture trips
ruff F401. Each split was checked by identical collected ids (file path
stripped) and identical per-test outcomes on the three engines, and by an AST
comparison of the top-level definitions; the whole suite's 5,451 ids were
identical before and after.

## Next steps

1. Follow PR #6 to green (Ubuntu 3.13 and 3.14, Windows 3.14, three engines).
   Spec 036 AC-2 (p95 33 ms locally against 50 ms) passed on the runners. The
   first CI runs found three problems, all fixed on the branch (2026-10-15):
   - Ubuntu: the room header wrapped to three rows with DejaVu Sans, leaving
     the grid under 100 px at 568x320 touch (specs 013 AC-6, 014 AC-1/AC-7).
     Fixed in `RoomPage.svelte`, checked with Inter, DejaVu Sans and a third
     font.
   - Windows WebKit: a click moves the focus off a button (spec 014 AC-7 now
     says so); spec 035's mocked socket did not answer pings, so a slow setup
     looked like a lost connection (it answers now).
   - Windows Chromium: a heartbeat `ping` (every 2 s from the socket's opening)
     broke "sends nothing" checks; the specs now leave pings aside (ec6634c)
     and so do the tests.
   - Follow-up: most specs' mocked sockets (012 and others) still never answer
     a `ping`, so a browser test that runs more than 4 s on a slow engine sees
     the page go to `reconnecting` (spec 017 AC-4). Make every mock answer pings
     with a `pong` as specs 014, 035 and 036 do, except where spec 017 tests the
     silence itself.
2. After the merge, `docs/build-plan.md` says to tag `v0.1.0`. Ask the human
   before pushing a tag.
3. Phase 6: a spec-writer folds the approved answers into the 13 specs (each
   spec's "Open questions" become dated decisions) and makes the follow-on
   refinements they name: 005 (allow `smtplib` in `src/nock/mailer.py` only),
   012 and 017 (a timed-out player gets their seat back, from 032), 013
   (word-completed lines during live play, from 034; feed keys no longer unique
   by `seq`), 018 (033's erasure as a second exception to "the log is never
   rewritten"), 023 (check buttons hidden, not disabled, in `none` mode, from
   025; two 023 tests change), 026 (`elapsed_ms` from the 027 timer; one 026
   test changes), 036 (038's log settings and variables). Then build in the
   order of `docs/build-plan.md` Phase 6.

## How to verify (what the lead runs before any code commit)

- Full gate as CI runs it, all three engines (about 55 minutes):
  `PYTEST_ADDOPTS="--browser firefox" uv run python scripts/gate.py`.
- Targeted runs while working:
  `PYTEST_ADDOPTS="--browser firefox" uv run pytest tests/test_spec_NNN*.py -q`.
- The session-start hook (`.claude/hooks/session-start.sh`) installs the
  Python and web dependencies and Chromium, Firefox and WebKit in cloud
  sessions. The gate skips an engine that is not installed, with a warning
  (`scripts/gate_browsers.py`); CI fails instead.
- CI cancels a run when a new commit is pushed to the pull request, so batch
  pushes while a run is in progress.
- Fonts differ: cloud sessions resolve `system-ui, sans-serif` to Inter, CI's
  Ubuntu runner to DejaVu Sans (wider). Layout tests can pass here and fail on
  CI. To run as CI does, hide Inter with a fontconfig file:
  `FONTCONFIG_FILE=<file> uv run pytest ...`, where the file includes
  `/etc/fonts/fonts.conf` and rejects the Inter families (`<selectfont>
  <rejectfont>`); `fc-match sans-serif` must then say DejaVu Sans.

## Decisions the human made (2026-10-13 to 15)

- The gate skips missing browser engines locally; CI runs all three.
- Agents may refine an approved or done spec, with a dated note; only the
  human sets `approved`.
- Accessibility choices are delegated to the lead: in-app keyboard keys stay
  out of the Tab order (`tabindex="-1"`) but named; roster states use italic
  and line-through, no opacity; a crowded cell shows "+N"; scrolling lists
  with nothing focusable are Tab stops (035 AC-12).
- Spec 014: compact "✕" remove button on narrow lists, minimum roster width.
- The 13 Phase 6 specs: approved with the recommended answers (above).
- Test files past about 800 lines are split by criterion group (approved
  2026-10-14; all files split 2026-10-15, after the pull request was opened).
- Open the pull request once Phase 5 is green, and follow its CI.
- Work in parallel with several agents; resume automatically when a usage
  limit resets; prefer a fresh session when the lead's context grows large.

## Pending questions for the human

- `scripts/hooks/role_gate.py` gives the gate 540 s, but the full gate takes
  about 55 minutes, so the hook always times out and never blocks an
  implementer (and an implementer may sit waiting on a full gate run).
  Proposal: run the changed spec's tests plus the static checks in the hook.
- Proposal: make local browser tests use CI's fonts by default (for example,
  the session-start hook writes the fontconfig file above and exports
  `FONTCONFIG_FILE`), so a layout that depends on Inter fails here first. This
  is a tooling change.
- Spec 036 AC-11: should a `NOCK_PORT` value with a control character appear
  raw or escaped in the error message? The tests accept both.
- Please confirm the tooling changes made for the test split: `CLAUDE.md`
  ("Layout"), `.claude/agents/test-writer.md`, and pyrefly's
  `search-path = ["src", "tests"]` in `pyproject.toml`.
- The reviewer noted `RoomConnection.mark_input_applied` (`src/nock/hub.py`) is
  public but not in spec 036's interface. The lead kept it: only the room task
  calls it, and a private name called from another class reads worse.

## Conventions that kept the branch healthy

- One commit per phase: spec, tests (red), code, then closing. Specs with new
  criteria are committed together with their tests, or the gate's
  traceability fails.
- Never commit half-written tests or unverified code; stage explicit paths
  (`git add <files>`), never `-A` (agent worktrees live in `.claude/`).
- Agents that share a file must not run at the same time; work that would
  collide runs in a git worktree (`isolation: worktree`). Worktrees start on an
  old `main`, so the agent first runs
  `git merge --ff-only feat/phase5-mvp-ldddid`; the lead cherry-picks the
  result. Tell each agent the exact commit trailer to use.
- Review findings go back through the roles: spec-writer, then test-writer,
  then implementer.

## Keeping the cost down

- Start a fresh session when the lead's context passes a few hundred thousand
  tokens; every turn re-reads it.
- Use a cheaper model (Sonnet 5.5, Haiku 5.5) for small spec notes and
  mechanical edits; keep Opus for building and reviewing.
- Cap review rounds at two, then list the remaining findings for the human.
