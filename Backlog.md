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

An item's number, branch and worktree come from
`uv run python scripts/claim_item.py <short-name>` when its brief starts, never
from this file: a brief reaches `main` only when its pull request merges. A
number is final, and a dropped item leaves a gap. `--list` shows the items in
flight and the spec files each one changes.

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
- Branch: feat/b-011-catalogue-brand · PR: #50 (merged)
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

- Status: done (the human approved look E′ and the spec change, 2026-10-25;
  model option A, the lead's pick; review approved in round 1)
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
    dashes of about 3 px at 18 px cells (a 320 by 568 phone), about 7 of 5 px
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

### B-013 Grid files in the ipuz ArrowWord format

- Status: done (the human picked option D and named the ipuz fields the
  grids will carry, then approved the spec change with compound words in
  ipuz's own notation, 2026-10-26; review approved in round 1, its
  suggestions checked in round 2)
- Domains: content/grid-files (new, split from content/grids, which keeps
  the model and the import checks), content/grids, content/library (pointers
  only); `specs/_map.md` (table and glossary)
- Architecture decision: yes (the grid file format; options from the Plan
  agent on Fable, two independent passes)
- Criteria: grid-files AC-1 to AC-21 (new domain; AC-1 to AC-5 take grids
  AC-13 to AC-17 and their pointers); grids AC-1, AC-4, AC-5, AC-6, AC-18,
  AC-19 (changed), AC-13 to AC-17 (deleted, moved); library rule 1 (changed,
  no criterion)
- Branch: feat/b-013-ipuz-grids · PR: none yet
- Problem: the human asked: "Replace grid custom grid definition format by the
  standard "ipuz" Arrowword standard. This format is documented at
  https://www.puzzazz.com/ipuz. Shifting to a open-source standard will help
  using of external tooling, and libraries to possbly interact with the grid
  definitions." Today a grid file is Nock's own JSON (rule 9 of
  `content/grids.md`), which no other tool reads.
- What ipuz gives: ipuz v2 (`"version": "http://ipuz.org/v2"`) has a kind
  ArrowWord, `"kind": ["http://ipuz.org/crossword/arrowword#1"]`, with
  `"clueplacement": "blocks"`, one clue list `clues.Clues` and a clue
  `location` `[col, row]`. It has no arrow names, no rule for two clues in one
  cell, and no field for Nock's own decisions (number, published, withdrawn,
  licence). Tools seldom support ArrowWord, and none is known to keep keys it
  does not know when it saves a file, so anything Nock-only written into an
  `.ipuz` file must be assumed lost after an outside edit (the Plan agent's
  reading, not checked against the tools).
- Options:
  - **D (the human's pick): pure ipuz for the grid, Nock's decisions in an
    index.** Each `.ipuz` file uses standard ipuz fields only, no extension
    key, so an outside tool can open and save it without losing anything.
    `grids/catalogue.json` holds what Nock decides about each grid. The grid
    model, the stored rooms, the protocol and the browser do not change. No
    new dependency.
  - Set aside: A, Nock's data in namespaced extension keys of the `.ipuz`
    file (an outside edit can drop `withdrawn` or the licence without a
    word); B, both formats for a time; C, ipuz as import and export only
    (both keep two formats); ipuz as the stored model too (a migration of the
    rooms' snapshots and a client move to `[col, row]`, for no gain).
- Answers (the human, 2026-10-26): option D. Most grids will come from
  external sites, so these ipuz fields will be filled: `publisher`,
  `publication`, `url`, `uniqueid`, `title`, `author`, `editor`, `date`,
  `difficulty` (the equivalent of force), `origin`, `block`, `empty`.
- What lives where (the lead's split, from that answer): what describes the
  grid as published is in the `.ipuz` file, in its standard fields, since
  tools keep those; what Nock decides is in the index.

  | Today's key | Where it lives |
  | --- | --- |
  | `number`, `published`, `withdrawn` (optional, false), `source`, `licence` | the index entry, with `file` (the `.ipuz` name); strict as rule 9 is today |
  | `force` | ipuz `difficulty`, required, 1 to 4 (a number or the same digit as text, as ipuz allows); any other text is refused |
  | `published_on` | ipuz `date`, required, exactly `MM/DD/YYYY`, a real date |
  | `author` | ipuz `author`, required, 1 to 200 characters once stripped |
  | (new) | ipuz `title`, `editor`, `publisher`, `publication`, `url`, `uniqueid`, `origin`, `copyright`: optional text, recorded as written with the entry, never shown to players and never interpreted, like the credits; written back by the writer |

- Grid mapping. Positions stay `(row, column)` in the model and in every
  error; the reader turns ipuz's `[col, row]` into `(row, column)` before any
  message (a message may quote the value as written: `location [4, 0], that
  is (0, 4)`). Coordinates count from zero, as the standard's examples do.

  | Today | ipuz |
  | --- | --- |
  | the file | `version` `http://ipuz.org/v2`, `kind` exactly `["http://ipuz.org/crossword/arrowword#1"]`, `"clueplacement": "blocks"`, clues under `clues.Clues` |
  | `width`, `height` | `dimensions` |
  | letter cell | the file's `empty` value in `puzzle` (ipuz's default `0`; `0` and `"0"` are the same) |
  | clue cell | the file's `block` value (default `"#"`) with one or two clues whose `location` is that cell, in the cell's order; a third is refused |
  | empty cell | a block with no clue (`null`, ipuz's "no cell", is refused) |
  | clue text | `clue` (plain text; HTML entities decoded, a tag refused) |
  | arrow | derived from `location` and the word's `cells` (required): first cell to the right or below, word across or down, gives the four arrows; a one-letter word gets the straight arrow (no grid today has one) |
  | answer | `answer`, as written (B-012: `ARC-EN-CIEL`) |
  | (new) | `solution` (the letters and the block) and `enumeration` (`"3-2-5"`), written by the writer, checked against the answers when present |

  `block` and `empty` must differ. Source of truth: `puzzle` and each clue's
  `location`, `cells` and `answer`. `cells` must be the word that rule 3
  resolves (this check gives AC-6's error); `solution` and `enumeration`,
  when present, must agree with the answers. Reading is strict: an unknown
  core key, or an ipuz feature Nock does not support (`saved`, `checksum`,
  `styles`, `zones`, `Across`, a cell written as an object or a clue number,
  another `clueplacement`, ...), is refused, as the standard asks of a
  reader; ipuz's remaining descriptive keys (`notes`, `intro`,
  `explanation`, `annotation`, `charset`) are accepted and ignored; keys of
  another tool's namespace (`x:y`) are ignored. In the index, an unknown key
  is refused, as today.
- Files: the index names each grid's file; grids are read in the index's
  order (rule 8 today: file-name order); an entry naming a missing file, or
  two entries naming the same file or number, stops the start; a `.ipuz` file
  the index does not name is ignored; no index is an empty catalogue.
- Converter: a writer of the same module turns a catalogue entry back into
  ipuz, for the tests and for a one-shot converter of today's `.json` files
  into `.ipuz` files and index entries, run as a module of the package
  (`uv run python -m nock....`), so no new script in `scripts/`.
- How B-012 fits: B-012 (PR #52, merged) went first; its
  model is unchanged here (the answer as written, `Clue.letters`,
  `Clue.breaks`, `Grid.hyphen_edges`). The human asked (2026-10-26) that a
  compound word use the ipuz format itself, so the file writes it with ipuz's
  own means, all three agreeing: `enumeration` (`"3-2-5"`, ipuz's notation
  for a hyphenated answer), `answer` with or without its hyphens, and the
  `dashed` bar style on the letter before each hyphen (`R` across, `B` down),
  which is the dashed edge B-012 draws. Breaks are the enumeration's hyphens
  when it has one, else the answer's; `dashed`, when a file has any, must
  name exactly the grid's hyphen edges. A space or an apostrophe in an
  enumeration is refused for now (B-012 gives breaks to hyphens only).
- In scope: rules 8 to 12 of `content/grids.md` (the index, the `.ipuz`
  files, the split above, the mapping, the arrow rule, the new checks); the
  criteria that name the file (AC-1, AC-4 as load, write, load equal, AC-5,
  AC-6, AC-13 to AC-15) reworded; new criteria for the version and kind,
  `block` and `empty`, the `puzzle` values, the clues and their locations, a
  clue cell's order and a third clue, `cells`, `solution` and `enumeration`
  disagreeing, `difficulty` and `date`, the recorded descriptive fields,
  `[col, row]` written `(row, column)`, unknown core and foreign-namespace
  keys, the index, and the converter. `tests/fixtures/fx01.ipuz` and
  `fx02.ipuz` added; `fx01.json` and `fx02.json` stay, as the model's own JSON
  (rooms store it). The README's grid-files section follows. If
  `content/grids.md` nears 15 KB, the file rules move to a new
  `content/grid-files.md`.
- Out of scope: the grid model, the stored rooms, the protocol and the browser
  (unchanged); the library (summaries unchanged: `force` and `published_on`
  keep their names there); showing any of the descriptive fields; reading
  other ipuz kinds; a grid editor; converting
  files automatically at start.
- Screens: none.
- Open questions: none left. The lead's picks, to overrule if needed: force
  read from `difficulty` and `published_on` from `date` (one truth each, in
  the file a tool keeps); `difficulty` only 1 to 4, so an importer writes
  `3`, not `Force 3`; `author` moves to the `.ipuz` file while `source` and
  `licence` stay in the index; one index rather than a side file per grid.

### B-014 Tests for the brand link on `/ops`, the recap and the account page

- Status: done (the human picked option A and one state per page, and
  approved the spec change, 2026-10-25; review approved in round 1; no
  implementation step: the tests passed as written)
- Domains: client/shell, admin/operations
- Architecture decision: no (criteria and tests only; no behaviour, code or
  look changes)
- Criteria: shell AC-10 (changed), operations AC-13 (changed)
- Branch: feat/b-014-brand-link-tests · PR: none yet
- Problem: `client/shell.md` rule 17 makes the brand the link « Accueil » to
  `/` on every top bar that shows it but the catalogue's. Criteria prove it on
  the entry frame of a room (shell AC-10), the room's computer top bar (hud
  AC-2) and the grid page (library AC-21), but not on the shared recap
  `/recap/<token>`, the account page `/account` or the operator page `/ops`.
  All use `TopBarBrand` today, so nothing is broken, but a brand drawn another
  way there would go unseen.
- In scope: the link, its name « Accueil », its target `/` and no
  `aria-current`, on those three pages, at a computer and a phone window. The
  recap and account pages share the entry frame (shell rule 9), whose page
  frame `gameplay/results.md` and `account/account.md` leave to
  `client/shell.md`; `/ops` uses the catalogue's frame, and its page belongs
  to `admin/operations.md`.
- Out of scope: any change of behaviour or look; the brand's name (the
  label-in-name follow-up); following the link (B-010 and B-011 test that it
  loads `/`).
- Screens: none.
- Options (the three files are at 20 criteria and over 15 KB, so no new
  criterion is wanted):
  - A. Extend two criteria in place: shell AC-10 names the recap and account
    pages besides `/r/ZZZZZZ`; operations AC-13 says the `/ops` bar's brand is
    the link « Accueil » to `/`. The tests behind their pointers (046 AC-1,
    048 AC-6) are edited in place.
  - B. One new criterion per page's domain (results, account, operations).
    Puts each check by its page, but takes all three files over their budget.
  - C. One new criterion in `client/shell.md`, rule 17's owner, for all
    three pages. Puts shell at 21 criteria and over 16 KB.
  - Lead's pick: A. The checks sit with the criteria that already prove each
    frame, and no file grows.
- Answers (the human, 2026-10-25): option A; one state per page: the recap
  loaded, the account page signed out, `/ops` locked.

### B-015 Word breaks: abbreviations, spaces, apostrophes; ipuz reader review

- Status: done (the human answered the brief and approved the spec change,
  2026-10-27; review approved in round 1, its suggestions checked in round 2)
- Domains: content/grids, content/grid-files; gameplay/board (one Out of
  scope line); `_design/cells.md` « Hyphen edges » and the captions of the
  cell sheet's « 4b » and the screens sheet's compound words (text only, no
  change of look). `platform/realtime.md` rule 23 and `gameplay/board.md`
  rule 20 already speak of a word's break and its marks, so they stay.
- Architecture decision: yes (the stored grid's answers and the grid file
  format; options from the Plan agent on Fable)
- Criteria: grids AC-3, AC-20, AC-21 (changed); grid-files AC-7, AC-15,
  AC-18, AC-21 (changed); board: no criterion (one Out of scope line)
- Branch: feat/b-015-abbreviations · PR: none yet
- Problem: the human asked: "Review the ipuz parser, and include abreviation
  support. Abreviations should visually behave like compound words. They will
  use "." i the "enumeration" field to separate letters. A.I will have AI as
  answer, Artificial Intelligence as clue for example." Today an enumeration
  holding `.` is refused, and so is an answer holding one.
- Review of the reader (`src/nock/ipuz.py` against ipuz v2.0.2):
  - Accepted: the v2 ArrowWord kind only, `clueplacement` `blocks`, clues
    under `clues.Clues` as objects of `clue`, `location`, `cells`, `answer`
    and an optional `enumeration`; `puzzle` values `block`, `empty`, or a
    letter cell with the `dashed` style; `solution` of letters A to Z and the
    block; `notes`, `intro`, `explanation`, `annotation`, `charset` ignored;
    namespace keys (`x:y`) ignored; clue text plain, entities decoded.
  - Refused by design (strict reader, rule 7): `saved`, `checksum`,
    `styles`, `zones`, `Across`, a clue as a text or a pair, a clue's
    `number`, `label`, `hints`, `image`, `continued`, `references`, named
    styles, `barred`, null cells.
  - Gaps found:
    1. Enumeration separators: only `-`. ipuz also writes ` ` (words), `.`
       (an abbreviation's period, after its count: `A.M.` is `1.1.`), `'`,
       `,` and `;`. **The human's three Le Parisien sample files are all
       refused today** for this: `I A` under `"1 1"` (INTELLIGENCE
       ARTIFICIELLE), `RC` `"1 1"`, `ESE` and `DCA` `"1 1 1"`, `ENAVANT`
       `"2 5"`.
    2. An answer holding `.` (`A.I`) is refused by the model (rule 4 of
       `content/grids.md` removes only spaces, hyphens and apostrophes).
    3. `showenumerations` (a core crossword key tools write) is refused.
    4. `dotted` is refused, though ipuz draws dotted with dashed as dashed.
    5. `solution` must hold Nock's normalised letters: `É` or a lower-case
       letter there is refused (ipuz's solution is case-sensitive).
    6. A key written twice in one object silently keeps its last value.
    7. A file starting with a UTF-8 byte order mark (some Windows tools
       write one) is refused as "not valid JSON".
    8. A clue's descriptive `explanation`, `tags` or `type` is refused.
  - This item fixes 1 (`.`, ` ` and `'`, each a break with the dashed
    edge), 2 and 3. Gaps 4 to 8 go to « Small follow-ups » (none hits a file
    the human has today).
- Options (Plan agent on Fable):
  - **A (picked): the separators stay in the answer as written.** Rule 4
    gains `.`: the letters drop it as they drop `-`, ` ` and `'`. The answer
    as written keeps each separator's kind (`A.I.` stays `A.I.`), so the
    model needs no new field; `Clue.breaks` and the edges keep their shape.
    Stored rooms: same shape. Protocol: unchanged, the same `hyphen_right` /
    `hyphen_down` marks, now set for every break. No client change.
  - B: breaks get a kind in the model and in the snapshot's marks, ready for
    kinds that look different one day. Adds the protocol, the room, the
    client and their criteria, for no visible difference. Set aside: the kind
    can reach the mark the day a kind looks different, since A keeps it in
    the answer.
  - C: the reader turns `.` into `-`. The writer then writes `1-1` for
    `1.1.`, so a grid no longer survives the round trip as written. Set
    aside.
- Answers (the human, 2026-10-27): "Update my spec and support
  abbreviations, apostrophes in the most ipuz fashion. Include support for
  proper "." abbreviations and simple space " ". A.I. or "A I" "A.I" on top
  of current "-"". Then: "do not do A.I. (last dot). Support answer A but
  with space, dot, hyphen". The lead reads them as option A, with every separator
  between two letters, hyphen, dot, space or apostrophe, a break drawn as the
  compound word's dashed edge (so `A I`, `A.I` and `A-I` look the same, and
  so do `EN AVANT` and `AUJOURD'HUI`), and no trailing dot.
- The model (`content/grids.md` rule 4):
  - The separators are `-`, `.`, ` ` and `'` (`’` is read as `'`). The
    letters drop them all. A break is exactly one separator between two
    letters, counted as the letters before it: `A.I`, `A I` and `A-I` give
    the letters `AI` and a break after 1; `AUJOURD'HUI` a break after 7;
    `ARC-EN CIEL` after 3 and 5.
  - A separator at the start or the end, or two in a row, is refused,
    naming the answer: `A.I.`, `.AI`, `A..I`, `A.-I`, `A  I`, `DR. NO`,
    `-ARC`, `ARC- EN`.
  - Step 8 of rule 6: two words sharing an edge agree on its break, not on
    its kind (both draw the same dashes).
  - Rooms stored since B-012 keep their answers as written, so one holding
    `AUJOURD'HUI` now draws its edge; rooms stored before hold letters only
    and draw none, as today.
- The file (`content/grid-files.md` rules 7, 9, 12, 14), as ipuz writes an
  enumeration:
  - Enumeration: counts of one or more joined by single `-`, `.`, ` ` or
    `'`: `1.1`, `1 1`, `1-1`, `7'3`, `3-2-5`, `1.1-3` load. A trailing `.`
    (ipuz's `1.1.`, `5 1.1.`), two separators in a row (`2. 2`), `,`, `;`,
    `0` (unknown length), `*`, `^`, `+` and `=` are refused.
  - Answer: written with the enumeration's separators (`A.I` under `1.1`,
    `A I` under `1 1`), or as letters only (`AI`), which takes the
    enumeration's separators: `AI` under `1.1` is the model's `A.I`.
    Separators that differ from the enumeration's, kind included, are
    refused naming the clue (`A I` or `A-I` under `1.1`). Without
    enumeration the answer's own separators rule, as today.
  - `dashed` names every break edge, whatever its separator, with today's
    check.
  - Writer: `answer` as written and the enumeration derived from it, so
    `A.I` writes `1.1`, `A I` `1 1`, `A-I` `1-1`, and each reads back
    equal.
  - `showenumerations` (a boolean) is accepted and ignored.
- In scope: rule 4 and step 8 of `content/grids.md`; rules 7, 9, 12, 14 of
  `content/grid-files.md`; one sentence in `_design/cells.md` « Hyphen
  edges » saying every break is drawn so. Criteria changed in place where
  they can: grids AC-3 (`AUJOURD'HUI` gets its break), AC-20; grid-files
  AC-7, AC-15 (`"2 3"` and `"2'3"` load), AC-18, AC-21. No new criterion in
  `content/grid-files.md`, already over its size budget.
- Out of scope: a mark of its own per separator (option B); showing the
  enumeration in the clue bar; the reader's gaps 4 to 8 (« Small
  follow-ups »); rewriting the Le Parisien files (they load once this is
  built: `I A` under `1 1` draws the dashed edge).
- Screens: none redrawn. Every break is drawn as B-012's dashed edge (look
  E′), whose drawing does not change; « Hyphen edges » and the cell sheet's
  « 4b · Compound words » caption name the other separators.
- Open questions: none left. To overrule if the lead misread: a space and an
  apostrophe draw the dashed edge too, not only the dot; the apostrophe stays
  in (asked in the first answer, not named in the second).

### B-025 Split `client/hud.md`: the room panel and the notes

- Status: done (the human approved the brief, option A and both of the
  lead's defaults, with the new file named `client/room.md`, then the spec
  change as written, 2026-10-28; built and reviewed in two rounds, 2026-10-28)
- Domains: client/hud, client/room (new); citations repointed in social/chat,
  social/catch-up, social/presence, gameplay/hints, platform/server,
  client/shell, `_settings.md` and `_map.md`
- Architecture decision: yes, it adds a domain (options from the Plan agent on
  Fable)
- Criteria: room AC-1 to AC-7 (new file, moved word for word from hud AC-4,
  AC-11 to AC-14, AC-17, AC-18 with their 043 pointers); hud AC-4, AC-11 to
  AC-14, AC-17, AC-18 (moved out, numbers never reused)
- Branch: feat/b-025-hud-split · PR: none yet
- Problem: `client/hud.md` holds 19.4 KB and 20 criteria, over the budget of
  about 15 KB and 20 (`specs/_map.md`, « What a spec holds »). B-021 (the room
  gone dialog) adds about 1.8 KB and 2 criteria to it, and waits for this item.
- In scope: the room panel (« Salon ») and the 3-second notes leave `hud.md`
  for a new `client/room.md`. Rules and criteria move word for word; each criterion
  keeps its pointer to 043 and takes a number from AC-1 in the new file; the
  numbers it leaves in `hud.md` are never reused. Rules are renumbered in both
  files and every citation in other specs follows. `_map.md` gains the file's
  row (043 split between the two rows) and a glossary line for the room panel
  and the notes. The table's Look column keeps naming the design file
  `_design/room.md`.
- Out of scope: any change of behaviour, look or tests. Every `hud.md`
  criterion is proven by its pointer to 043, so no test file changes and no
  code cites `hud.md`. B-022 (creator rooms) runs alongside: it edits `hud.md`
  rules 11 and 18 (they stay) and one word of rule 17 (it moves), and both
  items touch the glossary; whichever merges second resolves it.
- Screens: none.
- Options (the Plan agent on Fable; the lead's pick first):
  - **A (pick): the request's cut, with rule 7.** Rules 7 (the « Salon »
    button's badge and dot), 14 to 17 (the Salon) and 20 to 22 (the notes),
    with AC-4, AC-11 to AC-14, AC-17 and AC-18, go to a new file:
    `hud.md` about 13.3 KB and 13 criteria (about 15.1 KB and 15 after B-021),
    the new file about 7.8 KB and 7. It follows the seam that
    `_design/room.md`, the code (`Salon`, `PlayersPanel`, `RoomNote`) and the
    other specs already draw: chat, catch-up and hints cite the Salon and the
    notes as one pair. About ten citations move.
  - B: the Salon only (rules 7, 14 to 17; AC-4, AC-11 to AC-14). `hud.md`
    about 15.0 KB and 15 criteria, but about 16.9 KB and 17 after B-021: over
    budget again, so a second split follows.
  - C: A, and the menus and sheets (rules 9 to 12 and 18; AC-6 to AC-9 and
    AC-15) to a third file `client/menus.md`. The most room (`hud.md` about
    9.2 KB, 8 criteria), but it cuts the popover rule 13 and AC-10 across files
    and moves nine more citations for a budget problem that does not exist yet.
- Answers (the human, 2026-10-28): option A. Rule 7 moves with AC-4, which
  proves it (`hud.md` rules 8 to 13 become 7 to 12; `client/shell.md` and
  `social/chat.md` follow). « Salon » is the room, so the new file is
  `client/room.md`, not `client/salon.md`; its title says it is the room
  panel and the notes.
- Naming: once a domain is called `room`, no other may be called `room-...`
  (the gate: its test files would also name `room`). B-023 planned a
  `lobby/room-life.md`; its brief takes another name.

### B-022 Creator rooms and host return

- Status: building (the human approved the brief as written, with the
  lead's calls, then the spec change as written, `invalid_target` included,
  2026-10-28)
- Domains: lobby/host (new: the host role, moved from `lobby/rooms.md` rules
  13 to 21), lobby/rooms, lobby/joining, account/account, platform/realtime;
  `specs/_map.md` (a table row, the glossary); "guest" reworded in product,
  client/hud, admin/operations, `_reference.md`; citations of the host rules
  repointed in client/hud (rules 10 and 13), client/room, and wherever else
  `lobby/rooms.md` is cited for them
- Architecture decision: yes (a new domain file; stored data: the room's
  creator and each member's account; the room socket reads the session
  cookie). The options were weighed by the Plan agent on Fable for the first
  brief of this request; the human settled them, so no new Plan run.
- Criteria: host AC-1 to AC-8 (moved from rooms AC-13 to AC-20, pointers to
  014 kept), host AC-9 to AC-16 (new); rooms AC-13 to AC-20 (deleted, moved);
  joining AC-21 (new); account AC-13, hud AC-8, product AC-1 (wording only)
- Branch: feat/b-022-creator-rooms · PR: none yet
- Problem: the human asked: "Creator rooms and host return." Today the first
  joiner is host, a host away 60 s loses the role for good, an account may
  hold several members of one room, and "guest" means three things (an
  invited player, a player with no account, a player who is not host).
- In scope, the human's request as written:
  - Terms, in the glossary of `specs/_map.md` and used the same way in every
    domain; "guest" dropped as a spec term: account player (a member linked
    to an account); anonymous player (a member linked to no account);
    invited player (someone who enters by the room link and the nickname
    form); connection (one socket of a player; "session" stays the sign-in
    cookie); creator (the account whose session sent `POST /api/rooms`, set
    once at creation and never changed; none without a valid session or
    with accounts off); creator room and anonymous room (a room with and
    without a creator; a room created without a session stays anonymous
    even if its host signs in later); creator's player (the member of a
    creator room linked to its creator); stand-in host (a host of a creator
    room other than the creator's player); hand-over delay
    (`host_handover_seconds`, 60 s).
  - An account is at most one player in a room. A signed-in join to a room
    where the account already has a member gets that member back (seat,
    colour, letters, host role), and the older connection is closed with
    4001 as in today's takeover. The room socket learns the account from
    the session cookie.
  - The creator's player is host whenever connected: their join, resume or
    seat back gives them the role at once in one `host_changed`; while they
    are away longer than the hand-over delay, the role passes on as today.
  - A stand-in host cannot remove or mute the creator's player; a lock does
    not keep the creator's player out; a full room still does.
  - If the creator's account is erased, the room becomes an anonymous room.
  - Every duration or limit is written as its name with its default, never
    a bare number.
- Out of scope: any mark of the creator in the roster, the snapshot or the
  page; room lives (B-023); handing the role on by hand; co-hosts.
- Screens: none.
- Already decided by the human (on the first brief of this request and its
  spec change, 2026-10-28):
  - Where it lives: **A, a new file `lobby/host.md`**, "the host role: who
    holds it, how it passes, what it may do; the creator". It takes
    `rooms.md` rules 13 to 21 and AC-13 to AC-20 (pointers to 014 kept,
    renumbered from AC-1) and adds about eight criteria; `rooms.md` falls to
    12 criteria. The one-player-per-account rule changes in place in
    `joining.md` and `account.md`; `realtime.md` gets a sentence on the
    cookie and no criterion. Rejected: B, a `lobby/members.md`; C, edits in
    place in four files already at their budget.
  - Terms: **A, written in this item**, not in a wording-only item first.
  - Shape:
    - The room stores its creator's account id, set by `POST /api/rooms`
      from a valid `nock_session` (none with accounts off), in a nullable
      column of the store table `room_times`, beside `last_edit_at`, so that
      B-023's sweep reads a room's kind from one table. Stored rooms without
      it are anonymous rooms. The column makes `PRAGMA user_version` 1;
      B-023 takes 2.
    - Each member stores its account id, set at a signed-in join. The
      creator's player is the member whose account is the creator, not a
      stored member id, so a time-out and seat back keeps them.
      `PUT /api/account/rooms` stays for pages already open and links no
      member.
    - The join's member is chosen once, before the steps: signed in, the
      account's member of the room, player or past player, whatever token
      the join carries; else the member whose token it carries. A token
      that is not the join's member's is not used: its member is not
      touched and their connection stays open. Steps: removed token; the
      member a player: resume (older connection 4001), or time out and go
      on; locked (skipped for a join from the creator's session, member or
      not); full (for everyone); the member a past player: seat back;
      nickname; new player.
    - The hand-over tick also gives the role back to a connected creator's
      player who lacks it, so "whenever connected" holds after a plain
      reconnection; the tick never gives the role to a disconnected player.
    - Erasure clears the room's creator and the member's account, live and
      stored, with no event; a stand-in keeps the role. Its criterion lives
      in `host.md`.
    - Rooms where one account already holds several members get no
      backfill: the member whose token the device sends is stamped at the
      next signed-in join. A member linked to account A, joined with its
      token by a device signed in as B with no member there, is resumed and
      stays A's.
    - Accounts turned off after creation: the room keeps its creator in the
      store and plays as an anonymous room while accounts are off.
    - A signed-in page with no stored identity still shows the nickname
      form; a removed account player may come back from another device as a
      new player, as today.
- New since the first brief (the lead's calls; say if any should change):
  - B-025 split `client/hud.md`: the host rules are cited from hud rule 10
    (« Réglages de l'hôte » in the Menu) and rule 13 (the settings sheet),
    and the remove and mute buttons from `client/room.md` (the Salon's
    Joueurs tab). Those citations move to `lobby/host.md`.
  - `joining.md` gains one criterion (the account's member wins over a
    token) and goes to 21 criteria and about 17.5 KB, a little over the
    budget of about 15 KB and 20; `account.md` is already at about 19 KB.
    The lead keeps them there, since the rules belong there, and adds a
    small follow-up to trim or split both.
  - B-021 (room gone dialog) runs at the same time and may touch
    `joining.md` and `hud.md`; whichever merges second merges `origin/main`
    and resolves. B-023 waits for this item.
- Open questions: none.

### B-021 Room gone dialog

- Status: done (the human approved the brief as written, then the spec
  change as written, 2026-10-28; built and reviewed in two rounds,
  2026-10-28)
- Domains: client/hud (a new rule and two criteria; rules 3 and 7 name the
  dialog), client/shell (rule 7, one line), lobby/joining (rule 16, one line);
  `_design/overlays.md` (a new section « Room gone »), `_design/room.md`
  « Connection lost » and « Layers », `_design/foundation.md` (the dialog
  scrim and bottom sheet rows); the screens sheet, part 3
- Architecture decision: no (the client only: the server already closes every
  socket of a deleted room with 4404; no message, stored data or public name
  changes)
- Criteria: hud AC-21, AC-22 (new); shell, joining: no criterion (one line
  each)
- Branch: feat/b-021-room-gone · PR: none yet
- Request (the human, 2026-10-28, word for word): "Players inside a room that
  expires are displayed a "This room no longuer exists" popup (To translate in
  French) and routed back to the menu."
- Problem: once the room has shown, the 4404 close of a deleted room ends the
  page on `not_found`: the status band « Ce salon n'existe pas. » under the top
  bar (`client/hud.md` rule 7), the grid still drawn and typable under it, its
  letters going nowhere, and no way on but « Retour aux grilles » or the brand.
- When it happens: a room expires 30 days after its last edit and the hourly
  sweep deletes it (`lobby/joining.md` rules 15, 16). A player meets it with a
  tab left open on an idle room, or when a page back from a long sleep or an
  offline spell opens a socket to the deleted room: a 4404 after the first
  snapshot, joined or reconnecting.
- In scope: on that 4404, a modal alert dialog titled `room.gone.title`
  « Ce salon n'existe plus. », with the existing line
  `room.status.not_found_detail` (« Un salon est effacé 30 jours après sa
  dernière modification. ») and one primary link, `share.home` « Voir les
  grilles », to `/`, the catalogue (the lead reads the human's "menu" as the
  home page, not the room's « Menu »). The dialog takes the focus and is
  announced; a menu, the Salon sheet, a room sheet or the recap open at that
  moment closes; the connection band goes, pending edits are dropped, and the
  room under the scrim is inert. It goes into `client/hud.md` (about 15.1 KB
  and 15 criteria after it, within the budget).
- Out of scope (the human's answer: removed players): a player removed by the
  host keeps the status band « Vous avez été retiré de ce salon. ». Also: a
  4404 before the first snapshot (the entry card « Ce salon n'existe pas. »
  stays, that player never saw the room); the other final statuses once the
  room has shown (locked, replaced, throttled keep the band); a warning before
  expiry or extending a room; forgetting the stored identity of a deleted room.
- Screens: the room page once it has shown, in both layouts; the screens sheet
  draws « The room deleted after it showed » in part 3. Options:
  - **A (the human's pick): a dialog with one way out.** The recap's frame
    (`_design/overlays.md` « Recap »: a 440 px dialog in the column layout, a
    bottom sheet in the sheet layout, over the dialog scrim): the title, the
    30-day line in muted, « Voir les grilles » right-aligned. Escape does
    nothing, since there is no room to go back to. The page changes only on
    the player's press, as the accessibility baseline wants.
  - B (rejected): the same dialog, and `/` loads by itself after 10 seconds.
  - C (rejected): no dialog; `/` loads at once and the catalogue shows a
    3-second note.
- Order: B-022 (creator rooms) runs alongside; the two share only this file.
  B-023 later moves `lobby/joining.md` rule 16 with this item's line in it.
- Answers (the human, 2026-10-28, on an earlier brief of this request):
  "Approved, option A. Removed players stay out of scope."
- Open questions: none new. To overrule if the lead misread: "menu" is the
  catalogue `/`, and the French text is the title « Ce salon n'existe plus. »
  over the existing 30-day line.

## Small follow-ups

Taken when a change touches them.

- `lobby/joining.md` (about 18.2 KB, 21 criteria after B-022) and
  `account/account.md` (about 19.5 KB, 18 criteria) are over the size
  guideline: trim them or split each, an architecture decision.
- `client/hud.md` rule 16 closes the menus, the reaction picker, a room sheet
  and the recap before the room-gone dialog shows, but AC-21 proves only the
  Salon sheet (B-021's review); an open room sheet or the recap in AC-21's
  second case would prove the native modals give way. The Android back
  gesture's reopen is tested only through `close()`.
- `content/grid-files.md` is over the size guideline (about 18.7 KB, 21
  criteria after B-015): the converter (rule 15, AC-20) could leave for its own
  short section or file, or the sample lists of AC-9 and AC-18 shrink.
- The converter does not refuse two former files with the same `number`; the
  index it writes is then refused at server start. Refusing it there, naming
  the second file, keeps its "writes nothing" promise
  (`content/grid-files.md` rule 15 does not ask for it).
- An index `file` may hold `:` (on Windows, `C:x.ipuz` resolves outside
  `grids/`, `a:b.ipuz` opens an NTFS stream), and `A.ipuz` and `a.ipuz` are
  one file on a case-insensitive disk (`content/grid-files.md` rule 2). The
  operator writes the index and CI runs on Linux: hardening only.
- A `grids/` still holding former `.json` files and no `catalogue.json`
  starts with an empty catalogue and no error (`content/grid-files.md` rule
  1): run `uv run python -m nock.ipuz_convert` on it once.
- `gameplay/board.md` is over the size guideline (about 20 KB, 22 criteria
  after B-012): split the grid's look (rules 1 to 4 and 20, AC-4 to AC-8,
  AC-21, AC-22) into its own domain file, an architecture decision.
- `_design/cells.md` « Hyphen edges » does not say how two hyphen edges meet:
  a cell with both marks (the code draws a 1 px rule-grey corner pixel), and,
  at 3 px thickness, an across edge ending where a down edge starts (the outer
  pixel can fall in the other edge's gap); neither is drawn in the cell sheet.
- The ipuz reader's gaps left by B-015 (`src/nock/ipuz.py`): `dotted` is
  refused, though ipuz draws dotted with dashed as dashed; `solution` must
  hold Nock's normalised letters (`É` or a lower-case letter is refused); a
  key written twice in one object keeps its last value silently; a file
  starting with a UTF-8 byte order mark is refused as "not valid JSON"; a
  clue's descriptive `explanation`, `tags` or `type` is refused.
- B-015 left: `’` in an enumeration is refused while rule 4 of
  `content/grids.md` makes it the same separator as `'` (`content/grid-files.md`
  rule 9 lists `'` only; say which); no test locks in that an enumeration
  with a leading zero (`"05"`, `"02-3"`) loads, as it does.
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
- The brand's name « Accueil » does not contain its visible text « Nock »
  (WCAG 2.5.3, label in name): a voice-control user saying "Nock" misses it.
  The human chose « Accueil »; « Nock, accueil » would meet both.
- WebKit reaching the brand by Tab (`tabindex="0"`, hud AC-20) is proven only
  once CI runs WebKit after the merge.
- `client/shell.md` (about 16.4 KB, 20 criteria) and `admin/operations.md`
  (about 18 KB, 20 criteria) are past the size budget of `specs/_map.md`; the
  next criterion in either needs a split first (an architecture item). For
  shell, the B-010 spec-writer proposed `client/foundation.md` taking rules 13
  to 17 and their criteria.
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
- No test taps the reaction pill on a clue (`client/hud.md` rule 14 says a
  tap selects that clue; 043 AC-25 checks only where the pill is drawn).
- Untested account behaviour the code has: a link token arriving in the URL
  fragment while `/account` already shows signs in; another method on an
  account route answers 405 while accounts are on, and 404 while they are off
  for a method no route has; a failed purge is logged and the sweep goes on
  (`account/account.md`).
- Known flakes: 036 AC-8's join on the room of `NOCK_DATABASE` fails under
  load and passes alone; 046 AC-22's nickname error failed once on Firefox,
  never reproduced; 019 AC-4's legend after Bob leaves failed once in the
  full gate on Windows (B-015), passed alone; on Windows, `net::ERR_NO_BUFFER_SPACE` after several
  gates in a row (rerun alone).
- B-009's option B, once Docker is how Nock deploys: a domain
  `platform/deployment.md` and a CI job that builds the image and checks the
  running container (serves `/`, a room survives a restart, no `.env*` or
  `data/` inside, not root). Needs the human's approval of the CI actions.
- Rule grey `#9AA3B2` is 2.54:1 on white, under the 3:1 WCAG 1.4.11 asks of a
  control's boundary; kept by the human, `#8A93A3` (3.10:1) remains possible.

## Grid engine ideas from ipuz

What the ipuz standard can describe and the grid engine does not use yet
(listed by the lead, 2026-10-26, at the human's request). Each becomes an item
through `/new-spec` when the human picks it. To keep the engine free of ipuz,
each adds a concept to Nock's own model first (`src/nock/grid.py`), and only
`nock.ipuz` maps the ipuz field onto it: another file format could fill the
same concept, and the rooms, the protocol and the browser never see ipuz.

- A mark of its own per kind of break: B-015 draws every break (hyphen,
  dot, space, apostrophe) as the same dashed edge and keeps its kind in the
  answer as written; a kind that should look different would reach the
  snapshot's marks then (B-015's option B).
- The length pattern in the clue bar: « (3-2-5) » after the clue text, from
  the letters and breaks the model already has (ipuz's `showenumerations` is
  the file's switch). B-012 left it out of scope.
- The title on the card and the grid page: B-013 records `title` without
  showing it (`intro` and `notes` are read and ignored). Showing it changes
  the summary (`content/library.md` rule 2), an interface change.
- One grid imported twice: B-013 records `uniqueid`; refusing two index
  entries whose files share one would stop the same grid entering twice
  (`content/grid-files.md`).

Not taken from ipuz: its `checksum` (the server needs the answers for check
and reveal), `references` and `continued` (rare in arrowwords), image clues
(the product serves no third-party content). Arrows stay Nock's own: ipuz has
none.

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
