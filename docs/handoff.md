# Handoff

Read this first in a new session, then `CLAUDE.md`, `specs/_reference.md` and
`docs/build-plan.md`. It replaces the long conversation of the session that
wrote it (2026-10-12 to 2026-10-14), so a fresh session can continue cheaply.
Update it at the end of each session.

## Where things stand

- Branch `feat/phase5-mvp-ldddid`, pushed. No pull request yet (the human has
  not asked for one).
- Phase 5 (MVP): specs 005, 023, 026 are done. 035 (accessibility) and 036
  (performance) are built but not closed: see "In flight".
- Phase 6 (V1): the 13 specs 019-022, 024, 025, 027-029, 032-034, 038 have
  public interfaces and were approved by the human on 2026-10-14 with the
  recommended answer to every open question. Not built.
- Phase 7 (030, 031): untouched, only if the human wants competitive modes.

## Update, late 2026-10-14

- Done since the first version: lane A's code is committed (de12363); spec
  036's code is on the branch (77dcd18); the spec 013, 035 and 036 tests are
  split into files per criterion group (ed17f7e, 8abc954, 6a899c4), with
  `search-path = ["src", "tests"]` for pyrefly (d15bb2b). Items 1 and 2 below
  are therefore done.
- Still open, in worktrees of the lead's session (if they are lost, redo them):
  - The spec 014 test split (same method as the other three).
  - Spec 036 AC-5 race: `test_ac5_a_client_that_never_reads_is_closed_as_
    stalled_and_disconnected` fails about 3 times in 5 under CPU load ("timed
    out after 10.0s waiting for B's 30 letter_changed"), passes idle. Root
    cause to find in `src/nock/hub.py`; reproduce with four busy-loop
    processes running alongside the test.
  - Item 3's first two bullets (015/018 burst fixtures, `live_server` with
    `server_config`), plus `pytest.register_assert_rewrite` for the
    `specNNN_harness` modules in `tests/conftest.py`.
- Then item 3's remaining bullets: full three-engine gate, reviewer, close 035
  and 036, then the pull request (the human asked the lead to open it once
  Phase 5 is green, and to follow its CI).
- Right after the pull request (human decision): split every remaining test
  file over about 800 lines by criterion group (018, 017, 039, 012, 023, 037,
  011, 026, 006, 015, 040, 007, 016, 004, 010, 005, 009, 008), and bring the
  036 and 014 harness modules under about 800 lines. Same method and checks
  as the first four splits: identical collected ids and per-test outcomes on
  the three engines, one worktree per file, cherry-picked onto the branch.

## In flight when this was written

1. **Lane A code, uncommitted when this file was first written:** `web/src/`
   (`GridViewport.svelte`, `InAppKeyboard.svelte`, `RoomPage.svelte`, new
   `scrollingLists.ts`). It implements spec 035 AC-11 (label padding `0 1px`)
   and AC-12 (keyboard-reachable scrolling lists), spec 014 AC-3 (no page error
   when `hostPanel` becomes `null`), spec 013 AC-7/AC-8 (the feed keeps the
   reader's position) and review nits. Tests are committed (262ddb9, 0517ca7).
   If it is not in the log yet, check `git status`: commit it only after the
   three-engine check below passes.
2. **Spec 036 code** is commit `852075b` on the local branch
   `worktree-agent-a2dcc8d6894ad775b` (worktree under `.claude/worktrees/`,
   ignored). Merge it into `feat/phase5-mvp-ldddid` once lane A is committed;
   it touches `RoomPage.svelte` too, away from lane A's hunks. If the branch is
   gone (new machine), re-run the implementer on spec 036: its tests are
   committed (81a4260, 58a102d).
3. **After the merge, in order:**
   - Test-writer: add `max_inbound_pending=1000` to the burst fixtures of
     `tests/test_spec_015_shared_letters.py` (line ~122) and
     `tests/test_spec_018_durable_room_state.py` (`SERVER_CONFIG`, line ~128).
     The specs already say so (03d90d8); without it those two tests are closed
     with 1008 by spec 036 AC-6, as they should be.
   - Test-writer: switch the shared `live_server` fixture in
     `tests/conftest.py` to `server_config(app, log_level="warning")`, as spec
     036 asks, in a commit after the implementation.
   - Full gate on the three engines, then one reviewer pass over lane A and
     spec 036. Then set 035 and 036 to `done` (`docs: close spec NNN`).
   - Phase 5 is then complete: `docs/build-plan.md` says to tag `v0.1.0`. Ask
     the human before pushing a tag.
4. **Phase 6 next step:** a spec-writer folds the approved answers into the 13
   specs (each spec's "Open questions" become dated decisions) and makes the
   follow-on refinements they name: 005 (allow `smtplib` in
   `src/nock/mailer.py` only), 012 and 017 (a timed-out player gets their seat
   back, from 032), 013 (word-completed lines during live play, from 034; feed
   keys no longer unique by `seq`), 018 (033's erasure as a second exception to
   "the log is never rewritten"), 023 (check buttons hidden, not disabled, in
   `none` mode, from 025; two 023 tests change), 026 (`elapsed_ms` from the
   027 timer; one 026 test changes), 036 (038's log settings and variables).
   Then build in the order of `docs/build-plan.md` Phase 6.

## How to verify (what the lead runs before any code commit)

- Full gate as CI runs it, all three engines (about 50 minutes):
  `PYTEST_ADDOPTS="--browser firefox" uv run python scripts/gate.py`.
- Targeted runs while working:
  `PYTEST_ADDOPTS="--browser firefox" uv run pytest tests/test_spec_NNN*.py -q`.
- The session-start hook (`.claude/hooks/session-start.sh`) installs the
  Python and web dependencies and Chromium, Firefox and WebKit in cloud
  sessions. The gate skips an engine that is not installed, with a warning
  (`scripts/gate_browsers.py`); CI fails instead.

## Decisions the human made (2026-10-13 and 14)

- The gate skips missing browser engines locally; CI runs all three.
- Agents may refine an approved or done spec, with a dated note; only the
  human sets `approved`.
- Accessibility choices are delegated to the lead: in-app keyboard keys stay
  out of the Tab order (`tabindex="-1"`) but named; roster states use italic
  and line-through, no opacity; a crowded cell shows "+N"; scrolling lists
  with nothing focusable are Tab stops (035 AC-12).
- Spec 014: compact "✕" remove button on narrow lists, minimum roster width.
- The 13 Phase 6 specs: approved with the recommended answers (above).
- Work in parallel with several agents; resume automatically when a usage
  limit resets; prefer a fresh session when the lead's context grows large.

## Pending questions for the human

- `scripts/hooks/role_gate.py` gives the gate 540 s, but the full gate now
  takes 30-50 minutes, so the hook always times out and never blocks an
  implementer. Proposal: run the changed spec's tests plus the static checks
  in the hook instead.
- Proposal to split the largest test files (see the session's last message;
  also below).
- Spec 036 AC-11: should a `NOCK_PORT` value with a control character appear
  raw or escaped in the error message? The tests accept both.

## Conventions that kept the branch healthy

- One commit per phase: spec, tests (red), code, then closing. Specs with new
  criteria are committed together with their tests, or the gate's
  traceability fails.
- Never commit half-written tests or unverified code; stage explicit paths
  (`git add <files>`), never `-A` (agent worktrees live in `.claude/`).
- Agents that share a file must not run at the same time; an implementer that
  must not rebuild the client under another agent's tests runs in a git
  worktree (`isolation: worktree`).
- Review findings go back through the roles: spec-writer, then test-writer,
  then implementer.

## Keeping the cost down

- Start a fresh session when the lead's context passes a few hundred thousand
  tokens; every turn re-reads it.
- Use a cheaper model (Sonnet 5.5, Haiku 5.5) for small spec notes and
  mechanical edits; keep Opus for building and reviewing.
- Cap review rounds at two, then list the remaining findings for the human.

## Proposal: split the largest test files

Five test files are over 2,600 lines (014: 4,524; 035: 4,007; 018: 3,188;
013: 3,114; 036: 2,678). Every agent that touches one reads large parts of it,
and two agents once collided in the same file. The gate already matches every
`tests/test_spec_NNN*.py`, so a spec's tests can live in several files with no
gate change:

- One file per criterion group, for example
  `tests/test_spec_035_ac02_visible_focus.py`, at most about 800 lines each.
- The spec's shared harness in a helper module that pytest does not collect,
  for example `tests/spec035_harness.py`.
- A purely mechanical move, checked by the same number of collected test ids
  before and after (`pytest --collect-only -q`) and a three-engine run.
- It needs the human's go-ahead, because `CLAUDE.md` and the test-writer's
  instructions name one test file per spec.
