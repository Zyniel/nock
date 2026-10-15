# Handoff

Read this first in a new session, then `CLAUDE.md`, `specs/_reference.md` and
`docs/build-plan.md`. It replaces the long conversation of the session that
wrote it (2026-10-12 to 2026-10-15), so a fresh session can continue cheaply.
Update it at the end of each session.

## Where things stand (2026-10-15, evening)

- Branch `feat/phase5-mvp-ldddid` (the designated branch; it is restarted from
  `main` after each merge, keeping unmerged commits).
- Merged: PR #6 (Phase 5, MVP), PR #7 (Phase 6: specs 024, 025, first version of
  019, the spec 026 AC-10 fix). Tag `v0.1.0` exists locally on #6's merge commit
  but could not be pushed from the cloud session (tag pushes are refused): the
  human pushes it from a clone.
- Open: PR #8 (specs 019 refinements, 020, 021, 025 closed). CI ran green on
  Ubuntu; one Windows Firefox failure was a test bug, fixed in bcab487. The
  human commented on #8 that all open points and assumptions are fine.
- Phase 6 specs: 019, 020, 021, 024, 025 are `done`. 022 (chat and reactions)
  is being built: its red tests are committed locally after df10019 (5a1b304,
  cd1f3ef) and are not pushed, so PR #8's head stays green; push them with
  022's code. Still to build, in this order: 027, 028, 032 (with the 012/017
  seat-back refinement), 038 (refines 036), 034 (refines 013), 033 (refines
  005 and 018), 029.
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
   `git commit-tree` (never rewriting pushed history) and pushes up to the green
   commit with `git push origin <sha>:refs/heads/feat/phase5-mvp-ldddid`.
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

- Full gate as CI runs it, three engines (about 70 to 90 minutes now):
  `PYTEST_ADDOPTS="--browser firefox" uv run python scripts/gate.py`. It
  collects the tests at its start and builds `web/dist`: do not rebuild the
  client or commit red tests while it runs, and expect load flakes when agents
  run browsers at the same time (rerun a single failure before trusting it).
- Targeted runs: `PYTEST_ADDOPTS="--browser firefox" uv run pytest tests/test_spec_NNN*.py -q`.
- Fonts: CI's Ubuntu runner uses DejaVu Sans, this machine Inter. Layout files
  run a second time with
  `FONTCONFIG_FILE=/tmp/claude-0/-home-user-nock/189ffddd-b0b7-58e2-88b6-f8006dfcb8c1/scratchpad/fonts/fonts.conf`
  (a session scratchpad file: recreate it in a new session; it includes
  `/etc/fonts/fonts.conf` and rejects the Inter families).
- CI runs only on pull requests and pushes to `main`; it cancels a run when a
  new commit is pushed to the pull request. The Windows job is the slowest
  (about 80 minutes) and the most timing-sensitive.

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

## Lead decisions of 2026-10-15 worth knowing

- Spec 024: the room keeps `reveals_used`, so allowance changes never give
  spent reveals back. Spec 025: a restart resets an open vote's ballots to the
  requester's yes; vote buttons are disabled offline; focus rules after a
  ballot. Spec 026 AC-10: on windows at most 500 px high the completion status
  sits in the clue bar's row. Spec 013: the feed list has a fixed height.
  Spec 032 AC-7: a timed-out player gets their seat back (nickname taken
  meanwhile gives "Ana 2"). Specs 020-025: a refused message still wakes an
  idle sender. Spec 039: a chat text strips as `str.strip()` does.

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
  for building, test-writing of whole specs and reviews.
- Do not run the local full gate while agents run browsers; CI is the full
  check once a pull request is open.
