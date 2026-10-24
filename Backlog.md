# Backlog

The work queue of Nock: one item per change, from its brief to done. The lead
keeps this file; only the human approves a brief or a spec change. Keep it short:
every role reads the item it works on. A done item leaves the file at the next
release (git keeps it).

## How an item moves

`brief` → `approved` → `ready` → `building` → `done`, or `blocked` at any point,
with the reason.

- `brief`: the lead wrote it (`/new-spec`); it waits for the human.
- `approved`: the human approved the brief; the spec-writer changes the domain
  specs.
- `ready`: the human approved the spec change; `/feature B-NNN` can build it.
- `building`: on its branch, through tests, code and review.
- `done`: closed by `/feature`; it ships when its pull request is merged.

An item looks like this:

```md
### B-NNN Short title

- Status: brief
- Domains: content/grids, content/library
- Criteria: grids AC-20 (new), grids AC-7 (changed), library AC-3 (deleted)
- Branch: feat/b-NNN-short-name · PR: none yet
- Problem: one or two lines.
- In scope: ...
- Out of scope: ...
- Screens: the screens it touches, or none. When the look changes, two or three
  options with the lead's pick.
- Open questions: ...
```

"Criteria" is filled when the human approves the spec change. "Waits for" names
an item that must be done first.

## Items

### B-001 Rebaseline v1.1.0 into domain specs

- Status: building
- Domains: all (`specs/_map.md`)
- Branch: feat/rebaseline-content-grids · PR: none yet
- Problem: the numbered specs (2 MB) mix the contract with its history, and a
  role reads about 60k tokens before it starts; the domain specs state the
  current truth.
- In scope: the tooling for domain specs; the 18 domain files still pending,
  `product.md` and `_settings.md`; the design split into `specs/_design/`; a
  review of each domain file against the tests and code of v1.1.0; moving the
  numbered specs to `specs/_archive/v1.1.0/`.
- Out of scope: any change of behaviour or code; compacting the tests (B-003).
- Screens: none (the screens sheet's captions follow the design split).

### B-002 Phase 8: race and team modes

- Status: approved (the human, 2026-10-22: E8 is wanted, once the visual design
  is built)
- Domains: gameplay/modes
- Waits for: B-001
- Problem: specs 030 and 031 are 1.5 KB stubs approved before their interface
  existed.
- In scope: race on one grid; two teams racing. Answers already given: teams
  differ in size by at most one player and no team is empty; the host cannot
  start with fewer than 2 players.
- Out of scope: other competitive modes.
- Screens: to draw in the screens sheet with the spec change.

### B-003 Compact the tests

- Status: brief
- Domains: none (tests only)
- Waits for: B-001
- Problem: 4.9 MB of tests for 875 KB of code; helpers are copied from file to
  file (`dist_dir` in 72 files, `catalogue` in 82) and near-copies of one test
  stand where a parameter would do.
- In scope: shared fixtures and harnesses; parametrized tests in place of
  copies; the same criteria proven, no weaker check.
- Out of scope: the code; what the tests prove.
- Screens: none.

## Small follow-ups

Taken when a change touches them.

- Spec 025's vote banner test (`test_spec_025_ac07_vote_banner.py`) no longer
  measures a window (spec 047) and can leave `SERIAL_TEST_FILES`.
- Spec 045: no zoom test with the legend shown; the column layout with the legend
  over the grid is not drawn in the screens sheet.
- Spec 048 AC-13's no-animation rule is a text scan and cannot see an animation
  started at run time; a `document.getAnimations()` check, as spec 046 AC-9 does,
  would.
- Spec 035's language scan accepts any "X : Y" text through
  `{name} : {reaction}`; binding open placeholders to their values would close it.
- Spec 029, left for the human in PR #26: a history save that read the room
  before an account's erasure and writes after it keeps the nickname (very
  unlikely); the delete hook writes SQLite under the registry lock; two erased
  team-mates of one record show as one `--`; the room page asks its summary once
  and does not retry; `peek_room` re-reads the log of a room solved before spec
  029 at each call.
- Rule grey `#9AA3B2` is 2.54:1 on white, under the 3:1 WCAG 1.4.11 asks of a
  control's boundary; kept by the human, `#8A93A3` (3.10:1) remains possible.

## Decisions waiting for the human

- Grid source for real content (commission, licence, or generate and review):
  before launch.
- Le Parisien baseline: confirm it from screenshots, if the comparison is still
  wanted.
- Hosting (Fly.io, Render or a VPS) and a domain, before the first public test.
  A cloud session drafts `docs/hosting.md` on the branch `docs/hosting-plan`.
- GitHub: protect `main` (require the "Quality gate" check, no force push).
  Repository settings are the human's.

## Release checklist

Before the human tags a release on `main`:

1. Every item of the release is `done` and merged; none is `building`.
2. `main`'s last CI run is green in the three engines
   (`gh run list --branch main`).
3. The full gate passes locally in the three engines (`--browsers all`), each
   single failure rerun alone.
4. Release notes, one line per item, written from this file and approved by the
   human.
5. The human tags `vX.Y.Z` and pushes the tag; the done items then leave this
   file.
