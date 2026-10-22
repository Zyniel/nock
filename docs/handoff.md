# Handoff

Read this first in a new session, then `CLAUDE.md`, `specs/_reference.md` and
`docs/build-plan.md`. It replaces the long conversations of the sessions that
wrote it (2026-10-12 to 2026-10-21), so a fresh session can continue cheaply.
Update it at the end of each session.

## Where things stand (2026-10-22)

- Phase 6 is complete (2026-10-22): its 13 specs are merged and `done`. The
  last four went in one pull request each: 038 (#22), 034 (#24), 033 (#25) and
  029 (#26). Next is the visual design (`_design.md`, from spec 041); Phase 7
  (specs 030 and 031, competitive modes) is wanted and queued after it.
- The work moved on 2026-10-21 from the cloud session to a session on the
  human's Windows computer. The cloud session's worktrees are gone.
- Local setup: section 1 of the README (`uv sync`, `npm --prefix web ci`,
  `uv run playwright install chromium firefox webkit`). The session-start hook
  and CI's fonts are for cloud sessions; the finish hook works in both.

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
  line), PR #13 (spec 028, end-of-game recap and share link), PR #14 (tooling:
  the four test files that measure durations in the serial pass), PR #15 (spec
  032, room resume, seat back and "My rooms"; its two lead decisions stand
  unless the human overrides them: a mute survives a time-out, only lookups
  check expiry), PR #16 (tooling: page loads in the tests keep Playwright's
  30 s, which ended the Firefox-Windows `Page.goto` timeouts; the finish hook
  gives the gate 1,140 s; a spec 018 AC-2 race), PR #17 (the nickname rule:
  typed and stored in capitals, compared exactly, shown with capitalised words;
  NFC before and after the capitals; the field shows capitals through CSS and
  keeps its value as typed), PR #18 (from the design session: `specs/_design.md`,
  `docs/design/cell-sheet.html` and the draft spec 041, the visual foundation),
  PR #19 (tooling, for a faster pipeline: CI drops Firefox's Windows job; the
  test-writer and implementer run at high effort with 250 turns; the finish hook
  gates the checkout the agent edited), PR #20 (spec 041, the visual
  foundation, from the design session), PR #21 (tooling: CI skips the browser
  jobs for a pull request that only changes `specs/` or `docs/`), PR #22 (spec
  038, privacy and operations, with the `utc_datetime` fix for Windows), PR #23
  (tooling: the new CI workflow, below), PR #24 (spec 034, catching up after an
  absence), PR #25 (spec 033, optional account, with its `link_identity` race
  fix), PR #26 (spec 029, game history), PR #27 (tooling: the finish hook also
  finds the agent's checkout from its Bash commands: `git -C`, `cd`,
  `--directory`, and Git Bash `/k/...` paths read as `K:/...`). Tag `v0.1.0`
  is on the remote.
- Open: the pull request that closes specs 038, 034, 033 and 029 and carries
  this handoff.
- Questions left to the human from PR #12: the reading of the rule for
  `NOCK_DATABASE` (control, separator and format characters only). Spec 033's
  open question 2 (players' addresses outside ASCII) is answered with (b), under
  the human's simplicity rule: say so in its pull request.
- Pull requests, human decision of 2026-10-16: one pull request per spec (with
  its refinements of other specs), and tooling changes in a pull request of
  their own. With one designated branch there is one open pull request at a
  time: push the next spec and open its pull request once the previous one is
  merged. CI runs only on pull requests, so a local check comes first.
- The human was asked to require the `Quality gate` check in `main`'s ruleset;
  a pull request whose CI runs should then show as "blocked", not "unstable".
- Phase 6 specs: all 13 merged and `done` (019, 020, 021, 022, 024, 025, 027,
  028, 029, 032, 033, 034, 038).

## Left open from Phase 6

- **How the last spec pull requests were opened:** `specs-chain` (a local
  branch) keeps the whole reviewed chain. Each spec was cherry-picked onto
  `main` in a worktree `pr-NNN` once the previous one was merged. Cherry-pick
  ranges and single commits in separate calls: one call with both walks the
  whole history between them. Those worktrees and `specs-chain` can go.
- **Spec 029 (game history), merged in PR #26:**
  - **Commits (their `specs-chain` hashes):** spec d1f3388; tests 4239b0b; code 27fa970 (server) and
    ce383c6 (client); the first review's fix round: spec 6402495, tests
    822bddb, code a2b65d3, spec 032 note 28768fc.
  - **Also in its pull request:** 2272dda (two spec 032 AC-4 tests compare
    summaries as models, since spec 029 adds two summary fields) and 4ba1ce5
    (`utc_datetime` in `room.py` replaces `datetime.fromtimestamp(..., UTC)`,
    which raises `OSError` on Windows for a negative time; spec 038's AC-6
    `[30-3]` test failed locally for that reason).
  - **First review's blocking finding, fixed:** deleting an account while one
    of its solved rooms had expired but was not swept left the nickname in
    another account's history and in the files. The route now runs
    `AccountStore.erase_players_from_history` after the rooms are erased.
  - **For the human (in PR #26; nothing decided yet):**
    - One race is left: a history save that read the room before the erasure
      and writes after it keeps the nickname. Very unlikely (the other thread
      must stall through `erase_player` and two commits). Closing it: the
      store keeps the erased `(code, player_id)` pairs and writes `--` for
      them on every later save.
    - The delete hook writes SQLite under the registry lock.
    - Two erased team-mates of one record show as one `--`.
    - The room page asks its summary once per page and does not retry; "My
      rooms" writes the record on the next visit.
    - `peek_room` re-reads the log of a room solved before spec 029 at each
      call (correct, slower on old rooms).
- **Local environment, 2026-10-21:** the `.venv` launchers failed with "uv
  trampoline failed to canonicalize script path" (black, playwright,
  uvicorn); `uv sync --reinstall` fixed it.
- **Waiting for another agent's gate:** use
  `pgrep -f '^[^ ]*python[0-9.]* [^ ]*scripts/gate[.]py'`. The simpler
  `pgrep -f scripts/gate.py` matches its own shell, and a wait loop on it never
  ends.
- Follow-up noted from spec 028's first review: spec 035's scan accepts any
  "X : Y" text through `{name} : {reaction}` (bind open placeholders to their
  values, a spec 035 refinement, after 032).
- A tool call can turn a typed `\uXXXX` into the character itself: the first
  draft of spec 036 held six raw invisible characters, U+202E among them. Write
  such characters as `\N{NAME}` in code and as typed escapes in specs, and scan
  the files for categories Cc, Cf, Zl and Zp after writing.
- Commit trailers: the implementer and test-writer roles run on Sonnet unless the
  lead passes `model: "opus"`. Each agent signs with its own model's trailer;
  some pushed commits of 2026-10-15 carry the Opus line by mistake, and pushed
  history is not rewritten. Since 2026-10-17 those two roles run at high effort
  (their definitions); the spec-writer and the reviewer keep the session's.
- The lead works in the main tree and reaches worktrees with `git -C` and
  absolute paths: a `cd` into a worktree makes it the session's working
  directory, and the stop hook then checks that worktree.

## First tasks for the next session

1. Phase 6's end in the build plan: tag `v1.0.0` on `main`, if the human wants
   it.
2. The visual design first (human, 2026-10-22: "I want the game now to be
   implemented based on the full design system provided"): `_design.md`
   section 14's build order. Step 1 is spec 041 (approved). Steps 2 to 5 get
   specs drafted from `_design.md`, which the human approves one by one. Lead
   decisions of 2026-10-22, for the human to override: the design's revealed
   notch (0.22 by 0.11 of the side) wins over spec 024 AC-9's minimum, and the
   spec writer's picks of section 15's "Still open" items are accepted.
3. Phase 7 (competitive modes) is wanted (human, 2026-10-22: "E8 is wanted"),
   and queued after the design ("Stop and queue 030 or any competitive
   modes"): spec 030 (race mode), then 031 (team mode), one pull request each.
   Both are 45-line stubs, approved before their public interface existed: a
   spec writer writes them in full first.
4. The small follow-up below ("Follow-up noted from spec 028's first review"),
   when a spec touches it.
- **Models:** pass `model: "opus"` to the implementer and to the test-writer of
  a whole spec (their definitions default to Sonnet, at high effort). Use
  Sonnet for small spec notes and mechanical test edits.

## How a feature is built here

1. Spec answers and refinements first (spec-writer), then tests (test-writer),
   then code (implementer), then review (reviewer). One commit per phase.
2. Each spec is built in a worktree of its own (`git worktree add -b spec-NNN
   .claude/worktrees/spec-NNN <base>`), based on the previous spec's branch.
   Agents work there with `git -C` and absolute paths. A phase that runs no
   tests (spec-writer) overlaps another spec's phases. Two test runs at once
   slow each other down, so a test-writer waits while another gate runs
   (`pgrep -f scripts/gate.py`). Implementers run one at a time per shared file
   set (they all touch `room.py` and `RoomPage.svelte`).
3. Review findings go back through the roles, two rounds at most; what is left
   goes to the human in the pull request description. Since 2026-10-17, to save
   time: a fix round takes the blocking findings and the small, certain
   suggestions; the second review reads only the fix round; agents run only
   their spec's tests while they work, and the lead runs the gate once more on
   the rebased head before the pull request.
4. Red test commits stay local until their code lands; when a red commit sits
   under a commit that must be pushed, the lead rebuilds the chain with
   `git commit-tree -S` (`-S` signs it: plain `commit-tree` ignores
   `commit.gpgsign`, and GitHub then shows the commit as Unverified; a few
   pushed commits of 2026-10-15 are unsigned for that reason) and pushes up to
   the green commit with `git push origin <sha>:refs/heads/feat/phase5-mvp-ldddid`.
   Never rewrite pushed history.
5. Turn limits: 250 for test-writers and implementers since 2026-10-17 (60 and
   80 before, which stopped them 19 times in two days). A stopped agent resumes
   with SendMessage and keeps its context.

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
  `--browsers all` runs all three engines; the default is chromium since
  2026-10-21 (`NOCK_BROWSERS` overrides it). A full Chromium gate takes about
  6 minutes on the human's machine. After several gates in a row, Windows can
  run out of local ports (`net::ERR_NO_BUFFER_SPACE`): rerun the failures.
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
  the branch changed, Chromium). It takes 2 to 4 minutes for one spec, and
  about 9 minutes for a branch built on unmerged work that changes 19 specs.
  The hook allows 1,140 s since 2026-10-16, because a gate that times out does
  not block. Since 2026-10-17 it gates the checkout of the last file the agent
  edited, read from the agent's transcript. Before, it ran in the session's
  directory, the main checkout, and checked none of a worktree agent's changes.
- CI runs on pull requests, on pushes to `main` and by hand
  (`workflow_dispatch`), and cancels a run when a new commit is pushed (on
  `main`, each merge cancels the previous merge's run). Since 2026-10-21 (PR
  #23, human decision): a pull request runs the static and non-browser tests
  (Ubuntu, Python 3.13) and Chromium (Ubuntu, 3.14), about 13 minutes; a push
  to `main` or a manual run adds Firefox and WebKit on Ubuntu. No Windows job:
  Windows is covered by the local gate. `Quality gate` passes only when the
  jobs that should run passed (the other engines' job skipped on a pull
  request). Auto-fix watches pull requests, not `main`: check `main`'s run
  (`gh run list --branch main`) before opening the next pull request. A
  pull request's re-run keeps its old workflow file; to run a new workflow,
  push to its branch (for example a merge of `main`).
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
- 2026-10-16, night: build the four remaining Phase 6 specs now ("The four extras
  now"), in the build plan's order, one pull request each: 038, then 034
  ("Then catchup"), then 033 and 029. PR #15 merged.
- 2026-10-17: the pipeline is too slow ("I'm really upset by the time
  everything now takes"). The test-writer and implementer run at high effort,
  the spec-writer and reviewer keep the session's max; CI drops Firefox's
  Windows job. PRs #17, #18 and #19 merged.
- 2026-10-17 to 21: the weekly usage limit stopped every agent until 07:00 UTC
  on 2026-10-21.
- 2026-10-21: the work moves from the cloud session to a session on the human's
  computer. The work in flight of specs 038, 034 and 033 is saved as one chain
  on `feat/phase5-mvp-ldddid`. Then: "Finish both other specs I'll move when all
  is green". Specs 034 and 033 were built through their two review rounds that
  day, and 038's two small fixes went in.

- 2026-10-21, evening: CI is too slow and WebKit flakes ("would reducing the
  Browser coverage be a better option?"). Pull requests run the static checks,
  the tests without a browser and Chromium, on Ubuntu; Firefox and WebKit run
  on Ubuntu after a merge into `main` or by hand (`workflow_dispatch`); no
  Windows job; the local gate defaults to Chromium (PR #23). A failure on
  `main` is fixed in the next pull request. Bring WebKit back to pull requests
  once the visual design settles.
- 2026-10-21 to 22: the four spec pull requests opened one at a time; #22 and
  #24 merged.

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
- Another cloud session, "Nock graphical design ideas"
  (session_011p3hVBtTSdr7LXMomuHkez, opened 2026-10-16 at the human's request),
  works on design directions with the human. Its PR #18 (merged 2026-10-17)
  added the design reference, a cell sheet and the draft spec 041.
- Visual design, for the human to take up later (2026-10-16, after seeing the
  app for the first time, from screenshots): the app works but has no visual
  design (browser-default buttons, everything stacked above the grid, a narrow
  column on a computer, the chat panel over the grid). The human thought the Le
  Parisien reverse engineering covered the visual side. It never happened: the
  backlog of 2026-10-10 could not open Le Parisien's page, so its baseline is
  assumed, and `specs/_reference.md` keeps "Le Parisien baseline" as an open
  decision, to confirm from screenshots of the listing, an open grid and its
  help menu. Those screenshots would let a spec-writer draft a visual spec.
- Closed 2026-10-22: the README now says how to add grids (section 2, "Adding
  grids": the `grids/` folder, the file format, the credits, what an invalid
  file does). The repository still ships no grid of its own.

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
  the implementer and test-writer definitions default to Sonnet, at high
  effort).
- Do not run the local full gate while agents run browsers; CI is the full
  check once a pull request is open.
