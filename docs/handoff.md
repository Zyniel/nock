# Handoff

Read this first in a new session, then `CLAUDE.md`, `specs/_reference.md` and
`docs/build-plan.md`. It replaces the long conversations of the sessions that
wrote it (2026-10-12 to 2026-10-16), so a fresh session can continue cheaply.
Update it at the end of each session.

## Where things stand (2026-10-16, early afternoon)

- Branch `feat/phase5-mvp-ldddid` (the designated branch). It is restarted from
  `main` after each merge (`git fetch origin main && git checkout -B
  feat/phase5-mvp-ldddid origin/main`), keeping unmerged commits.
- Merged: PR #6 (Phase 5, MVP), PR #7 (Phase 6: specs 024, 025, first version of
  019, the spec 026 AC-10 fix), PR #8 (019 refinements, 020, 021, 022 with both
  of its review rounds, the CI speed-up), PR #9 (tooling: the implementer's quick
  gate, CI's fonts in cloud sessions, a write guard that judges an edit against
  the checkout holding it), PR #10 (spec 027, the shared timer, and spec 035's
  stricter language scan), PR #11 (tooling: the finish hook lets an agent stop
  once it has reported a failure it cannot fix), PR #12 (spec 036's refinement:
  technical variables refuse special characters; spec 033's variables brought in
  line), PR #13 (spec 028, end-of-game recap and share link). Tag `v0.1.0`
  exists locally on #6's merge commit but could not be pushed from the cloud
  session (tag pushes are refused): the human pushes it from a clone.
- Open: a tooling pull request, the four test files that measure durations in
  the serial pass.
- Questions left to the human from PR #12: the reading of the rule for
  `NOCK_DATABASE` (control, separator and format characters only); spec 033's
  open question 2 (players' addresses outside ASCII; (b) recommended).
- Pull requests, human decision of 2026-10-16: one pull request per spec (with
  its refinements of other specs), and tooling changes in a pull request of
  their own. With one designated branch there is one open pull request at a
  time: push the next spec and open its pull request once the previous one is
  merged. CI runs only on pull requests, so a local check comes first.
- The human was asked to require the `Quality gate` check in `main`'s ruleset;
  a pull request whose CI runs should then show as "blocked", not "unstable".
- Phase 6 specs: 019, 020, 021, 022, 024, 025, 027, 028 are `done`. Still to
  build: 032 (built and simplified, its pull request next), then the nickname
  rule below. The human was asked on 2026-10-16 whether to park 029, 033, 034
  and 038 ("the core is the game engine not all the rest") and what engine work
  comes first; the lead proposed simplifying the room engine.

## Work in flight (not pushed)

- Spec 032 (room resume): worktree `.claude/worktrees/spec-032`, branch
  `spec-032`, still on spec 028's commits from before their rebase (3059df6):
  rebase with `git rebase --onto origin/main 3059df6 spec-032`. Two reviews,
  then a last fix round the lead verified (the throttle checks and records in
  one locked step; the reviewer's burst script gives exactly 10 wrong codes
  through for 40 and 300 sockets) and a simplification under the human's rule
  (no store upgrade: Nock was never deployed; 126 lines fewer). Lead decisions
  for the human in its pull request: 13 (a mute survives a time-out and seat
  back), 14 (only lookups check expiry).
- Nickname rule (human, 2026-10-16): typed in capitals, stored in capitals
  (`str.upper()` before the checks), compared exactly (no casefold left), shown
  with capitalised words (one display function). Worktree
  `.claude/worktrees/caps-names`, branch `caps-names` on spec 032's head
  (c8e004a); the spec-writer is at work. Its own pull request after 032's.
- Follow-up noted from spec 028's first review: spec 035's scan accepts any
  "X : Y" text through `{name} : {reaction}` (bind open placeholders to their
  values, a spec 035 refinement, after 032).
- For spec 033's turn: a seated-back player whose nickname spec 033 erased to
  `--` keeps it, exempt from spec 012's suffix rule (from spec 032's pass).
- A tool call can turn a typed `\uXXXX` into the character itself: the first
  draft of spec 036 held six raw invisible characters, U+202E among them. Write
  such characters as `\N{NAME}` in code and as typed escapes in specs, and scan
  the files for categories Cc, Cf, Zl and Zp after writing.
- Commit trailers: the implementer and test-writer roles run on Sonnet unless the
  lead passes `model: "opus"`. Each agent signs with its own model's trailer;
  some pushed commits of 2026-10-15 carry the Opus line by mistake, and pushed
  history is not rewritten.
- The lead works in the main tree and reaches worktrees with `git -C` and
  absolute paths: a `cd` into a worktree makes it the session's working
  directory, and the stop hook then checks that worktree.

## First tasks for the next session

1. Keep the open pull request green until the human merges it; answer its
   review comments.
2. Then spec 032, then the nickname rule (above), each in its own pull request.
3. Then the rest of Phase 6 in the order above, one pull request each. Pass
   `model: "opus"` to the implementer and to the test-writer of a whole spec
   (their definitions default to Sonnet); Sonnet for small spec notes and
   mechanical test edits.
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
- Fonts: CI's Ubuntu runner draws the app's text in DejaVu Sans; this image
  prefers Inter. Since 2026-10-16 the session-start hook installs
  `.claude/hooks/ci-fonts.conf` in `~/.config/fontconfig/conf.d/`, so the
  browsers of a cloud session use DejaVu Sans as CI does (`fc-match sans-serif`
  says DejaVu Sans). Layout files no longer need a second run with another
  font.
- The implementer's finish hook runs the quick gate (`--specs` of the specs
  the branch changed, Chromium); about 2 to 4 minutes.
- CI runs only on pull requests and pushes to `main`, and cancels a run when a
  new commit is pushed. Seven jobs (static and non-browser tests on Ubuntu
  3.13; each engine on Ubuntu and Windows, Python 3.14), then `Quality gate`,
  which passes only when all seven passed. About 20 minutes; Firefox on
  Windows is the slowest job. The Windows jobs run 3 workers on their 4 CPUs
  (with 4 the runner once stalled for over 5 s), use ephemeral ports 16384 to
  65535 (the default range ran out once; the range starts above 10080, the
  highest port browsers refuse), and print the TIME_WAIT count when they fail.
- `SERIAL_TEST_FILES` holds the files that measure a duration or a pace: spec
  013 AC-7/AC-8 and spec 022 AC-11/AC-12 (list scroll, 300 ms), spec 022 AC-10
  (pacing), spec 036 AC-1 (time budgets), spec 027's live pages, and since
  2026-10-16 spec 013 AC-2 and spec 015 AC-1 (relay percentiles), spec 025 AC-7
  (the banner's time window) and spec 026 AC-1/AC-3 (the solve budget). A file
  that only waits up to a bound for a change stays parallel unless it flakes.

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
  summary check (`Quality gate`) for the branch rule. The browser warm-up, the
  Windows port range, the Windows worker count and the scroll files' serial
  pass are the lead's follow-up fixes to that change, each from a CI failure.
- 2026-10-16: PR #8 merged; from now on one pull request per spec, tooling
  changes in their own. Spec 032: a returning player whose nickname was taken
  comes back as "Ana 2" (fold it into the spec's decisions when 032 starts).
  The finish hook runs a quick gate, and cloud sessions use CI's fonts.
  Technical variables should not contain special characters: `NOCK_PORT`,
  `NOCK_HOST` and `NOCK_DATABASE` refuse control characters, the error showing
  the value escaped (a spec 036 refinement, in its own pull request).
- 2026-10-16: the lead fixes tooling incoherences and weaknesses (a timeout, a
  flaky setup, a hook blocking the wrong thing) without asking, in a pull
  request of their own; new tooling behaviour and new dependencies still need
  the human (written in `CLAUDE.md`).
- 2026-10-16: no screenshots in pull requests. No work on the app's visuals
  until the human takes it up ("don't bother yet about visuals").
- 2026-10-16: "Force player names to be input as caps, stored as caps, and
  rendered as Camel case. Make things simple from a backend perspective, don't
  generate edge cases by making things complicated. We are here to work on a
  core Arrow Crossword game. The core is the game engine not all the rest."
  "Camel case" read as capitalised words ("Ana"). Applied at once to spec 032
  (no store upgrade). Prefer the simplest rule that removes edge cases; do not
  escalate obscure edge cases of peripheral features.

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

- A separate cloud session ("Nock hosting plan (document only)") drafts
  `docs/hosting.md` on branch `docs/hosting-plan`.
- Another cloud session, "Nock graphical design ideas (no code)"
  (session_011p3hVBtTSdr7LXMomuHkez, opened 2026-10-16 at the human's request),
  brews design directions with the human: ideas only, no file, no code.
- Visual design, for the human to take up later (2026-10-16, after seeing the
  app for the first time, from screenshots): the app works but has no visual
  design (browser-default buttons, everything stacked above the grid, a narrow
  column on a computer, the chat panel over the grid). The human thought the Le
  Parisien reverse engineering covered the visual side. It never happened: the
  backlog of 2026-10-10 could not open Le Parisien's page, so its baseline is
  assumed, and `specs/_reference.md` keeps "Le Parisien baseline" as an open
  decision, to confirm from screenshots of the listing, an open grid and its
  help menu. Those screenshots would let a spec-writer draft a visual spec.
- The README does not say how to add grids: the repository has no `grids/`
  folder, so a fresh server lists none. For the implementer's next README
  change (the folder, the file format of `nock.catalogue`).

## Showing the app

The repository has no grids, so a demo serves
`create_app(catalogue=Catalogue(entries=...))` with FX-02 and FX-01 from
`tests/fixtures/` (credits from `credits.json`) and drives it with Playwright.
A room's creator joins at once under `localStorage["nock.nickname"]` (else
"Invité"); a player who opens the link gets the nickname form; another player
can be a raw WebSocket opened from a page of the same origin (`join`, then
`edit_letter`, `flag`, `react`, `chat`, `select_cell`).

## Keeping the cost down

- Start a fresh session when the lead's context grows large.
- Cheaper models (Sonnet) for small spec notes and mechanical test edits; Opus
  for building, test-writing of whole specs and reviews (pass `model: "opus"`:
  the implementer and test-writer definitions default to Sonnet).
- Do not run the local full gate while agents run browsers; CI is the full
  check once a pull request is open.
