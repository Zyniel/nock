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
- Architecture decision: no (or yes: options from the Plan agent on Fable)
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
- Branch: feat/b-001-rebaseline · PR: none yet
- Problem: the numbered specs (2 MB) mix the contract with its history, and a
  role reads about 60k tokens before it starts; the domain specs state the
  current truth.
- In scope: the tooling for domain specs; the 18 domain files still pending,
  `product.md` and `_settings.md`; the design split into `specs/_design/`; a
  review of each domain file against the tests and code of v1.1.0; moving the
  numbered specs to `specs/_archive/v1.1.0/`.
- Out of scope: any change of behaviour or code; compacting the tests (B-003).
- Screens: none (the screens sheet's captions follow the design split).
- The design split also: aligns `_design.md` §8 « States »'s note on state
  lines with v1.1.0 (16 px; no role on a waiting line, nor on the catalogue's
  and « Mes salons »'s load-error lines; `role="alert"` only on the error line
  of a failed action); takes the clue bar's minimum width (320 px) into
  `_design/room.md`; takes the grid's name in the computer top bar out of the
  current design (B-006).

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

### B-004 Live "word completed" lines in the Salon's stream

- Status: approved (the human's pick (b) of spec 034's decision 7: add the live
  line as a later refinement of spec 013; never built)
- Domains: social/chat, social/catch-up
- Waits for: B-001
- Problem: a player who comes back reads « … a complété … » lines in the
  catch-up, but a player who stayed never sees them: live play adds no such line.
- In scope: the same word-completed line, added live when a letter completes a
  word.
- Out of scope: other new kinds of line.
- Screens: the stream's line, as the catch-up already draws it.

### B-005 Grid progress on the account

- Status: approved (spec 004's decision 8, approved by the human on
  2026-10-10: progress shows "on my device or account", the account part
  waiting for spec 033; never built)
- Domains: content/library, account/account
- Waits for: B-001
- Problem: a grid's « Commencée » or « Terminée » comes only from this
  device's storage; a signed-in player on another device sees none.
- In scope: progress read from the account for a signed-in player.
- Out of scope: progress of guests across devices.
- Screens: the catalogue's progress pills, as drawn today.

### B-006 The grid's name in the computer top bar

- Status: brief (drawn in the design reference of 2026-10-16, « Grille n° N ·
  Force F » in the computer top bar; spec 043 left it as an open question and
  never built it)
- Domains: client/hud
- Waits for: B-001
- Problem: on a computer, the room page does not say which grid is played.
- In scope: the grid's number and force in the computer top bar.
- Out of scope: the phone top bar.
- Screens: the computer top bar; the design split takes the drawing out of
  the current design until the human decides.
- Open questions: build it, or drop it from the design for good?

### B-007 Pencil mode on a touch phone with the keyboard hidden

- Status: brief (found by the rebaseline's review of `client/hud.md`)
- Domains: gameplay/co-op, client/hud, gameplay/board
- Waits for: B-001
- Problem: the phone top bar has no « Crayon », and the ✎ key lives in the
  in-app keyboard; once « Clavier » hides the keyboard, a touch phone has no
  way to turn pencil mode on or off.
- In scope: a way to change pencil mode with the keyboard hidden.
- Out of scope: the computer top bar.
- Screens: the phone top bar or the Aide menu; options to draw.
- Open questions: is it worth fixing, or is hiding the keyboard rare enough?

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
- Rules stated but untested (the code does them; a test would catch a
  regression): the catalogue asks once and refuses items that are not
  summaries; the force filter makes no new request; the grid page's loading
  line and its non-summary answer; after a chip, only that chip pressed
  (`content/library.md` rules 8, 10, 16 and AC-6).
- The room page's `closed` status can no longer be reached (a socket lost is
  `reconnecting` or `connecting`, `platform/realtime.md`), yet
  `room.status.closed` (« Connexion perdue. ») is still a required key of 040
  AC-22's test: drop the key and that test entry (`client/shell.md`).
- No test taps the reaction pill on a clue (`client/hud.md` rule 19 says a
  tap selects that clue; 043 AC-25 checks only where the pill is drawn).
- Untested account behaviour the code has: a link token arriving in the URL
  fragment while `/account` already shows signs in; another method on an
  account route answers 405 while accounts are on (`account/account.md`).
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
