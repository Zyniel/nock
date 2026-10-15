# Handoff

Read this first in a new session, then `CLAUDE.md`, `specs/_reference.md` and
`docs/build-plan.md`. It replaces the long conversations of the sessions that
wrote it (2026-10-12 to 2026-10-16), so a fresh session can continue cheaply.
Update it at the end of each session.

## Where things stand (2026-10-16, around midnight)

- Branch `feat/phase5-mvp-ldddid` (the designated branch; it is restarted from
  `main` after each merge, keeping unmerged commits).
- Merged: PR #6 (Phase 5, MVP), PR #7 (Phase 6: specs 024, 025, first version of
  019, the spec 026 AC-10 fix). Tag `v0.1.0` exists locally on #6's merge commit
  but could not be pushed from the cloud session (tag pushes are refused): the
  human pushes it from a clone.
- Open: PR #8 (019 refinements, 020, 021, 022 and its first review round, the
  CI speed-up). Green on 958442b, all seven jobs and `Quality gate`. Its
  description is up to date. The human was asked to require the `Quality gate`
  check in `main`'s ruleset.
- Phase 6 specs: 019, 020, 021, 022, 024, 025 are `done`. Still to build, in
  this order: 027, 028, 032 (with the 012/017 seat-back refinement), 038
  (refines 036), 034 (refines 013), 033 (refines 005 and 018), 029.

## Work in flight (not pushed)

- Spec 022, second review round: the spec is committed locally (a97f860,
  decisions 20 to 22, new AC-19 and AC-20); its tests are being written in the
  main tree; then the implementer: `chat.wait` becomes "Patientez avant
  d'envoyer.", the focus goes back to `chat-input` after a send, a shared Escape
  helper for `ChatPanel.svelte` and `ReactionPicker.svelte`, `isConnected`
  renamed `isJoined`, `after_restart`'s rebound loop variable. Push the spec,
  tests and code together: a spec pushed before its tests fails the gate's
  traceability (it happened on 595597d).
- Spec 027 (shared timer): tests 854ee70 in worktree `agent-abc0fc6...`, with a
  fix commit coming for two test defects (Playwright for Python reads a numeric
  `page.clock` time in seconds, not milliseconds; AC-4's second page needs
  another room code) and a load-proof AC-5 refresh test. Implementation 0329ee5
  in worktree `agent-ac73bc7...` (on c0c0ebb, a cherry-pick of 854ee70): new
  `RoomTimer.svelte` and `timer.ts`. When it lands: add
  `test_spec_027_ac02_ac03_live_pages.py` to `SERIAL_TEST_FILES`, then review.
- Spec 028 (recap): tests e563c92 in worktree `agent-a0de19b...`, on 11059de (a
  cherry-pick of 854ee70; drop it when integrating). Build after 027 is reviewed.
- Commit trailers: the implementer and test-writer roles run on Sonnet
  (`model: sonnet` in `.claude/agents/`), but until 2026-10-15 the lead's prompts
  gave them the Opus trailer. Pushed history keeps it (the PR description says
  so); fix the trailer of their unpushed commits when integrating them, and tell
  agents to use the trailer of their own environment.

## First tasks for the next session

1. PR #8: subscribe to it and keep it green. If it merged, restart the branch
   from `main` (keeping the unmerged commits) and open the next pull request
   once the next batch is green.
2. Finish the work in flight above, in that order, through the roles.
3. Then 028, and the rest of Phase 6 in the order above. Pass `model: "opus"`
   to the implementer and to the test-writer of a whole spec (their definitions
   default to Sonnet); Sonnet for small spec notes and mechanical test edits.
- Phase 7 (030, 031): untouched.

## How a feature is built here

1. Spec answers and refinements first (spec-writer), then tests (test-writer),
   then code (implementer), then review (reviewer). One commit per phase.
2. Test-writers can run ahead in worktrees (`isolation: worktree`, first
   `git merge --ff-only feat/phase5-mvp-ldddid`); the lead cherry-picks their
   commits when the feature's turn comes. Implementers run one at a time per
   shared file set (they all touch `room.py` and `RoomPage.svelte`), in the main
   tree or a worktree.
3. Review findings go back through the roles, two rounds at most; what is left
   goes to the human in the pull request description.
4. Red test commits stay local until their code lands; when a red commit sits
   under a commit that must be pushed, the lead rebuilds the chain with
   `git commit-tree -S` (`-S` signs it: plain `commit-tree` ignores
   `commit.gpgsign`, and GitHub then shows the commit as Unverified; a few
   pushed commits of 2026-10-15 are unsigned for that reason) and pushes up to
   the green commit with `git push origin <sha>:refs/heads/feat/phase5-mvp-ldddid`.
   Never rewrite pushed history.
5. Agents hit their turn limits (60 for test-writers, 80 for implementers):
   resume them with SendMessage, they keep their context.

## Test layout

Every test file over about 800 lines is split by criterion group:
`tests/test_spec_NNN_acNN[_acMM]_<topic>.py`, with shared setup in
`tests/specNNN_harness.py`. `tests/conftest.py` registers every
`spec*_harness.py` for assert rewriting. Fixtures are thin per-file wrappers.
Mocked room sockets answer `ping` with `pong`; "sends nothing" checks leave
pings aside. The toolbar order (spec 024 AC-8) is relative.

## How to verify (what the lead runs before any code commit)

- The gate runs the tests in parallel (pytest-xdist, one worker per CPU), then
  the files of `SERIAL_TEST_FILES` (`scripts/gate_browsers.py`) on their own. It
  warms each browser up once before its first test.
- Static checks and the tests without a browser (1 minute):
  `uv run python scripts/gate.py --tests other`.
- One engine's browser tests, as a CI job runs them (7 to 15 minutes here):
  `uv run python scripts/gate.py --skip-static --tests browser --browsers firefox`.
  `--browsers all` runs all three engines; the default is chromium,webkit
  (`NOCK_BROWSERS` overrides it).
- Targeted runs, in parallel:
  `PYTHONPATH=scripts uv run pytest -p gate_browsers -n auto --browser chromium --browser webkit --browser firefox tests/test_spec_NNN*.py -q`.
  A bare `uv run pytest` runs the browser tests in Chromium only.
- The gate builds `web/dist` at its start: do not rebuild the client while it
  runs, and expect load flakes when agents run browsers at the same time
  (rerun a single failure before trusting it).
- Fonts: CI's Ubuntu runner uses DejaVu Sans, this machine Inter. Layout files
  run a second time with `FONTCONFIG_FILE=<scratchpad>/fonts/fonts.conf` (a
  session scratchpad file: recreate it in a new session's scratchpad;
  `fc-match sans-serif` must then say DejaVu Sans). Its content:

  ```xml
  <?xml version="1.0"?>
  <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
  <fontconfig>
    <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
    <selectfont>
      <rejectfont>
        <glob>*/Inter*</glob>
        <pattern><patelt name="family"><string>Inter</string></patelt></pattern>
        <pattern><patelt name="family"><string>Inter Display</string></patelt></pattern>
      </rejectfont>
    </selectfont>
  </fontconfig>
  ```
- CI runs only on pull requests and pushes to `main`, and cancels a run when a
  new commit is pushed. Seven jobs (static and non-browser tests on Ubuntu
  3.13; each engine on Ubuntu and Windows, Python 3.14), then `Quality gate`,
  which passes only when all seven passed. About 17 to 19 minutes; Firefox on
  Windows is the slowest job. The Windows jobs widen the ephemeral port range
  (the parallel tests once exhausted the default one) and print the TIME_WAIT
  count when they fail.

## Decisions the human made

- 2026-10-13 to 15 (Phase 5): the gate skips missing engines locally; agents
  may refine approved or done specs with dated notes; accessibility and layout
  choices are delegated to the lead; split test files past about 800 lines;
  work in parallel; open pull requests when green and follow their CI.
- 2026-10-14: the 13 Phase 6 specs approved with the recommended answers.
- 2026-10-15: tag `v0.1.0`; open the Phase 6 pull requests when green; on PR #8,
  "I agree with all comments. Open points assumptions are fine": pencil letters
  keep only their italics during a flash (spec 020 decision 12); a focused
  button that becomes disabled may drop the focus (specs 023 to 025); the spec
  019 small-cell trade-offs and the optional spec 020 test tightenings stand.
- 2026-10-15: the CI speed-up ("Go with the first 2"): pytest-xdist, engines
  chosen by the gate, one CI job per engine. The human then agreed to one
  summary check (`Quality gate`) for the branch rule. The browser warm-up and
  the Windows port range are the lead's follow-up fixes to that change.

## Lead decisions of 2026-10-15 worth knowing

- Spec 024: the room keeps `reveals_used`, so allowance changes never give
  spent reveals back. Spec 025: a restart resets an open vote's ballots to the
  requester's yes; vote buttons are disabled offline; focus rules after a
  ballot. Spec 026 AC-10: on windows at most 500 px high the completion status
  sits in the clue bar's row. Spec 013: the feed list has a fixed height.
  Spec 032 AC-7: a timed-out player gets their seat back (nickname taken
  meanwhile gives "Ana 2"). Specs 020-025: a refused message still wakes an
  idle sender. Spec 039: a chat text strips as `str.strip()` does.
- Spec 022, review rounds: the vote banner wins over an open chat panel; a
  restart clears every player's chat and reaction windows; a mute closes the
  picker (focus to the grid) and moves the focus from the chat form to
  `chat-toggle`; the chat notes sit in one always-present one-line slot and the
  mute note wins over the wait note; after a send the focus is on `chat-input`.

## Pending questions for the human

- `scripts/hooks/role_gate.py` gives the gate 540 s, but the gate takes over an
  hour, so the hook always times out. Proposal: run the changed spec's tests
  and the static checks in the hook.
- Proposal: make local browser tests use CI's fonts by default (the
  session-start hook could write the fontconfig file and export
  `FONTCONFIG_FILE`). A tooling change.
- Spec 036 AC-11: should a `NOCK_PORT` value with a control character appear
  raw or escaped in the error message? The tests accept both.
- A separate cloud session ("Nock hosting plan (document only)") drafts
  `docs/hosting.md` on branch `docs/hosting-plan`.

## Keeping the cost down

- Start a fresh session when the lead's context grows large.
- Cheaper models (Sonnet) for small spec notes and mechanical test edits; Opus
  for building, test-writing of whole specs and reviews (pass `model: "opus"`:
  the implementer and test-writer definitions default to Sonnet).
- Do not run the local full gate while agents run browsers; CI is the full
  check once a pull request is open.
