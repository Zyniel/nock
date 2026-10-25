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

- Status: done (the human approved every domain file, 2026-10-24)
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
- The design split also: states the state lines as v1.1.0 draws them (a line
  standing for a page is 16 px with no role, the catalogue's and « Mes
  salons »'s load errors included; inside a card, sheet or dialog, waiting and
  done lines are `role="status"`, error lines `role="alert"`; a failed
  action's error line is `role="alert"`); takes the phone top bar's 40 px
  buttons and the clue bar's minimum width (320 px) into `_design/room.md`;
  takes the grid's name in the computer top bar out of the design.

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

- Status: brief (the human delays the decision)
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

### B-008 Docs and comments follow the domain specs

- Status: done (the human asked for it, 2026-10-25)
- Domains: none (docs and comments only)
- Branch: feat/b-008-workflow-docs
- Problem: after B-001, `README.md`, `docs/build-plan.md` and `docs/handoff.md`
  describe the numbered-spec workflow, and comments in `web/src` and four test
  harnesses cite `specs/_design.md` by section.
- In scope: README's workflow on `Backlog.md`, `/new-spec` and `/feature B-NNN`;
  the two old docs removed, anything still current kept in README or the
  backlog; every `_design.md` citation in a comment names its
  `specs/_design/<file>.md` heading.
- Out of scope: any change of behaviour, test or look.
- Screens: none.

### B-009 Run Nock in a Docker container, dev and prod

- Status: done (the human approved option A, 2026-10-25)
- Domains: none (deployment files and README; no behaviour of the app)
- Architecture decision: yes (options from the Plan agent on Fable; the human
  picked A: files and docs, checked once by hand; a CI check is a later item)
- Branch: feat/b-009-docker
- Problem: a maintainer cannot run Nock in a container. The two local attempts
  put `.env*`, `data/` and `.git` into the image (no `.dockerignore`), run as
  root on Python 3.13 (the project pins 3.14) with Node and dev dependencies
  left in, and behind Caddy every player shares the proxy's address, so one
  player's wrong tokens throttle everyone (uvicorn trusts only 127.0.0.1).
- In scope: a two-stage image (Node builds `web/dist`; a 3.14-slim runtime with
  the venv, `src`, `web/dist`, `web/src/i18n` and `grids` at the repo layout
  the server reads), non-root, a `/data` volume, a healthcheck on `/`, `CMD`
  the venv's `python -m nock`; `.dockerignore`; one replica; dev = the same
  image over http on port 8000 with Mailpit for mail; prod = the image behind
  Caddy, the domain from `NOCK_DOMAIN` (default `nock.zyniel.com`), TLS
  automatic, `FORWARDED_ALLOW_IPS` so players keep their address; secrets from
  an env file git ignores (`.env.dev`, `.env.prod`, `data/` in `.gitignore`);
  README's "Running in Docker" with the two `docker compose` commands, in place
  of the PowerShell scripts. Checked once by hand: both setups build, `/`
  serves, a room join works, a room survives a restart.
- Out of scope: a spec and a CI check (option B, later); the hosting choice;
  live reload in a container; Docker secrets files; more than one replica.
- Dependencies (approved with A): base images `python:3.14-slim`,
  `node:lts-slim`, `ghcr.io/astral-sh/uv`, `axllent/mailpit`, `caddy:2-alpine`.
- Screens: none.

### B-010 The brand in the top bar leads home

- Status: done (the human approved option A and the spec change,
  2026-10-25; review approved in round 1)
- Domains: client/shell, client/hud, content/library
- Architecture decision: no (one new `fr.json` key; no protocol, data or
  module interface)
- Criteria: shell AC-10, AC-11 (changed); hud AC-2, AC-20 (changed); library
  AC-12 (changed), AC-19, AC-20 (new)
- Branch: feat/b-010-brand-home-link · PR: #49 (merged)
- Problem: the human asked: "On all displays extended displays, in the top
  bar, the Polygon + "Nock" should he a link back to the home page, grid
  selection." Today the brand (the Nock mark and « Nock », `TopBarBrand`) is
  plain text on every top bar that has it.
- In scope: the brand becomes a link to `/` (the catalogue, « Grilles ») on
  every top bar that shows it: the catalogue (there too, with
  `aria-current="page"`; activating it loads the catalogue again) and the grid
  page, the entry frame (nickname card, status cards, page not found), the
  shared recap, account and operator pages, and the room's computer top bar.
  Its name is a new key `topbar.home`, « Accueil ». From a room it does what
  the Menu's « Retour aux grilles » does: no question, the page loads `/`, the
  player is disconnected and keeps the seat, to resume from « Mes salons »
  within the resume window (`lobby/joining.md`). While the room opens its top
  bar is inert (`client/shell.md` rule 7), the brand with it. The room's Tab
  order on the computer top bar starts with the brand.
- Out of scope: the room's phone top bar, and so the low column layout, stay
  without the brand: there the Menu's « Retour aux grilles » is the way home.
  A question before leaving a room; any change to the Menu; client-side
  routing.
- Screens: every top bar that shows the brand (`_design/room.md` « Computer
  top bar »; `_design/pages.md` « Catalogue », « Entry and not-found pages »,
  « Plain pages »; a « Brand link » row in `_design/foundation.md`
  « Components »), redrawn in the screens sheet with the hover and focus
  states. Option A, picked by the human: the brand keeps its place and look at
  rest; on hover it takes a word-blue background, radius 6 px, as a top-bar
  button does (padding drawn inside a negative margin, so nothing moves);
  focused, the ring of « Components ». Set aside: B, the Nock mark alone on
  the phone top bar (more buttons there, and the Menu already leads home); C,
  the mark at every phone width under the 40 px floor (breaks too much).
- Open questions: none left.

### B-011 The catalogue's brand is plain text

- Status: done (the human approved the brief, its answers and the spec
  change, 2026-10-25; library keeps 21 criteria; review approved in round 1)
- Domains: client/shell, content/library
- Architecture decision: no
- Criteria: library AC-19, AC-20 (changed), AC-21 (new); shell rule 17
  (changed, no criterion)
- Branch: feat/b-011-catalogue-brand · PR: none yet
- Problem: B-010 made the brand a link to `/` on every top bar that shows it,
  the catalogue included (with `aria-current="page"`). The human decided: the
  Nock mark and « Nock » bring back to the catalogue on any page other than
  the catalogue, the grid page `/g/<n>` and the room included; on the
  catalogue itself they are "simply a plain text + logo".
- In scope: on `/` the brand is the mark and « Nock » as plain text: not a
  link, not a Tab stop, no `aria-current`, no name of its own (it reads
  « Nock »), no hover look. Everywhere else it stays the link « Accueil » to
  `/` (B-010). A criterion that the grid page's brand is that link, which
  B-010 left untested.
- Out of scope: any other page's brand; the name « Accueil ».
- Screens: the catalogue's top bar. The look at rest does not change; only
  the hover and focus states go away there. One option, the human's: the
  brand on `/` as it was before B-010 (`_design/foundation.md` « Brand link »
  no longer applies on the catalogue; `_design/pages.md` « Catalogue »).
- Answers (the human, 2026-10-25): library AC-20 checks the hover look on
  the grid page `/g/<n>`; `/ops` keeps the link, as any page other than `/`.

### B-012 Compound words: a dashed line where the hyphen falls

- Status: building (the human approved look E′ and the spec change, 2026-10-25;
  model option A, the lead's pick)
- Domains: content/grids, platform/realtime, gameplay/board
- Architecture decision: yes (grid file, stored grid and the snapshot's grid;
  options from the Plan agent on Fable)
- Criteria: grids AC-3 (changed), AC-20, AC-21 (new); realtime AC-20 (new);
  board AC-21, AC-22 (new)
- Branch: feat/b-012-compound-words · PR: none yet
- Problem: the human asked: "Grid should support "compound word". A compound
  word is represented on the grid with a special representation. Instead of
  standard cell design, the compound word "-" will be represented by a dotted
  line in between the cells instead of a plain line. Propose design options for
  all selection scenarios (selected, no players selecting)". Today rule 4 of
  `content/grids.md` drops the hyphen (`ARC-EN-CIEL` gives `ARCENCIEL`) and
  nothing of it reaches the grid.
- In scope: a hyphen takes no cell, as in printed grids: the edge between the
  two letters it joins is drawn dashed instead of the plain grid line (across:
  the right edge of the letter before it; down: its bottom edge). Typing,
  navigation, word length, check and reveal do not change (they work on
  cells). The model, the new import checks, the snapshot's hyphen marks, and
  the look of the dashed edge in every state.
- Out of scope: marks for spaces and apostrophes (`AUJOURD'HUI` stays as
  today; the model leaves room to add them later); showing the hyphen in the
  clue bar or a word's length pattern; the catalogue's generic grid drawing;
  any change to typing, navigation, check or reveal.
- Model, option A (picked): the hyphen stays in the answer. The file keeps
  writing `"answer": "ARC-EN-CIEL"`: no new key, rule 9 and existing files
  unchanged. The model keeps the answer as written and derives its letters
  (`ARCENCIEL`, today's normalised answer, which the import checks and the
  room's solution read) and its breaks (after letters 3 and 5). New checks
  when the file parses: a hyphen sits between two letters (`-ARC`, `ARC-`,
  `ARC--EN`, `ARC- EN` refused, naming the answer); new last step of rule 6:
  two words sharing an edge (a short word inside a longer run) agree on its
  hyphen, naming both answers and the edge. The snapshot's letter cells get
  two booleans, `hyphen_right` and `hyphen_down` (false by default); realtime
  rule 23 says the grid holds hyphen marks, which name an edge and never a
  letter. Rooms stored before the change hold normalised answers: they load
  and draw no dashed edge. FX-01 and FX-02 stay; criteria use FX-01 variants
  (`VI-DE`, `NA-VAL`). Set aside: B, explicit `"breaks"` per clue (authors
  count letters, a hyphen left in the answer is silently dropped); C, edge
  flags on letter cells in the file (nothing ties a flag to its word).
- Screens: grid cells (`_design/cells.md` « Grid lines and empty cells »,
  « Drawing order », each mark's least size; `cell-sheet.html` by hand; a new
  token in `_design/foundation.md`), then the room in the screens sheet,
  phone and computer. Look E′ (picked by the human, drawn on the throwaway
  comparison page): the plain line of that edge goes; in its place dashes in
  a grey of their own, a new token `--nock-hyphen` (#5E6573, darker than the
  grid lines), the same in every state (no one selecting the word, mine,
  another player's tint, mine and another's, a crossing word selected,
  locked, revealed, checked wrong, catch-up ring, flash, Auteurs mode, pencil
  letters):
  - a whole number of dashes per edge, at least 3, a period of about 5 px per
    pixel of thickness, 60 % dash, half a gap at each end so the corners stay
    open and the edge never merges into the crossing lines; dash ends on
    whole pixels, so fractional cell sizes and pinch zoom never blur them;
  - thickness 1 px under 36 px cells, 2 px from 36 px, 3 px from 72 px: 3
    dashes of about 3 px at FX-02's 18 px cells (568 by 320), about 7 of 5 px
    at a computer's 56 px, 8 of about 7 px at zoom 5 (90 px);
  - contrast 4.26:1 on my selected cell to 5.86:1 on white, 3:1 or more on
    every word, tint and locked background; 2.93:1 on the darkest flash,
    accepted for its 1 s;
  - my selected cell beside the edge: its navy border turns dashed on that
    side, with the same dashes (navy on selected 9.65:1), so the hyphen never
    hides under the border;
  - the triangles, icons, catch-up ring, notch and arrows stay as they are;
    no arrow ever sits on a hyphen edge (an arrow's edge faces its clue
    cell); the revealed notch lies over the dashes of a down hyphen.

  Set aside: ink dots (A, A′), a dotted rule-grey line (B), dots that follow
  the word's state (C), short ink dashes (D), the first E in rule grey (1.27
  to 2.54:1, hidden under my selection border, blurred at fractional sizes).
- Open questions: none left.

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
- The brand as the link « Accueil » on `/ops`, the shared recap and the
  account page (`client/shell.md` rule 17) has no criterion: only the
  catalogue, the entry frame and the room's computer top bar are tested. All
  use `TopBarBrand`, so a brand drawn elsewhere would go unseen. (The grid
  page: B-011.)
- The brand's name « Accueil » does not contain its visible text « Nock »
  (WCAG 2.5.3, label in name): a voice-control user saying "Nock" misses it.
  The human chose « Accueil »; « Nock, accueil » would meet both.
- WebKit reaching the brand by Tab (`tabindex="0"`, hud AC-20) is proven only
  once CI runs WebKit after the merge.
- The room page's `closed` status can no longer be reached (a socket lost is
  `reconnecting` or `connecting`, `platform/realtime.md`), yet
  `room.status.closed` (« Connexion perdue. ») is still a required key of 040
  AC-22's test: drop the key and that test entry (`client/shell.md`). Likewise
  046 AC-23's test still checks that `my_rooms.loading`, `my_rooms.empty` and
  `account-link` are absent, and 043 AC-31's that 043's removed keys are:
  history no spec states; drop those entries once the numbered specs are
  archived.
- Untested client details: binary frames ignored by the room page; `t()`
  placeholders; a `{"seq": 6}` frame without type cannot be told from event 6
  in 040 AC-19's test (`client/shell.md` rules 2, 3 and 5).
- No test taps the reaction pill on a clue (`client/hud.md` rule 19 says a
  tap selects that clue; 043 AC-25 checks only where the pill is drawn).
- Untested account behaviour the code has: a link token arriving in the URL
  fragment while `/account` already shows signs in; another method on an
  account route answers 405 while accounts are on, and 404 while they are off
  for a method no route has; a failed purge is logged and the sweep goes on
  (`account/account.md`).
- Known flakes: 036 AC-8's join on the room of `NOCK_DATABASE` fails under
  load and passes alone; 046 AC-22's nickname error failed once on Firefox,
  never reproduced; on Windows, `net::ERR_NO_BUFFER_SPACE` after several
  gates in a row (rerun alone).
- B-009's option B, once Docker is how Nock deploys: a domain
  `platform/deployment.md` and a CI job that builds the image and checks the
  running container (serves `/`, a room survives a restart, no `.env*` or
  `data/` inside, not root). Needs the human's approval of the CI actions.
- Rule grey `#9AA3B2` is 2.54:1 on white, under the 3:1 WCAG 1.4.11 asks of a
  control's boundary; kept by the human, `#8A93A3` (3.10:1) remains possible.

## Decisions waiting for the human

- Le Parisien baseline: confirm it from screenshots, if the comparison is still
  wanted.
- Hosting (Fly.io, Render or a VPS) and a domain, before the first public test.
  A cloud session drafts `docs/hosting.md` on the branch `docs/hosting-plan`.
- Tag `v1.1.0` on `main` (never tagged).

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
