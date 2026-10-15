---
id: "024"
title: Reveal a letter or a word
status: approved
---

# 024 - Reveal a letter or a word

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.) (Note from the lead, 2026-10-15: done. The human's answers are decisions 11 and 12 below, and "Open questions" says "None.")

Epic E6 Help and validation (US-6.2) · Release: V1 · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine (`nock.room`, `nock.hub`, delivery order, test harness) is defined in spec
011, edits and their check order in spec 015, locked cells in spec 016, the log,
`replay` and undo in spec 018, the activity feed and the layout guarantees of
spec 013 AC-6 in spec 013, the reveal allowance and the host panel in spec 014,
checks in spec 023, completion in spec 026, accessibility in spec 035, the traffic
rules in spec 037, the messages in spec 039 (`Reveal`, `RevealTarget`,
`RevealResult`, `RevealBudget`, `CellLocked`, `ErrorCode.BUDGET_EXHAUSTED`). Group
decisions on help (votes) are spec 025, built after this one.

## Goal

As a blocked team, we want to reveal a letter or a word, so that the game keeps moving.

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone.

## Public interface

No new protocol message, no new `ErrorCode` and no new public Python name. This
spec gives `Reveal` its meaning in `nock.room.handle_message`, extends
`nock.room.replay`, extends spec 037's traffic rule to revealed letters, and adds
to the room page the reveal controls, the look of a revealed cell and the room
toolbar.

(Note from the lead, 2026-10-15: this spec touches three `done` specs, and none of
the human's answers, decisions 11 and 12, adds another. No criterion or test of them
changes. Spec 018: its `undo-button` moves into `room-toolbar`, and its criteria do
not say where that button sits; the `cell_locked` row of its `replay` table gains
`pencil = False`, which changes nothing before spec 020 since no pencil letter
exists. Spec 023: `check-panel` moves into `room-toolbar`, which stays "in the room
header beside the undo control", as its "Client: check controls" says. Spec 037: its
traffic rule is extended in this spec's own copy of the checker ("Test harness"),
not in spec 037's tests.)

### Server rule: `Reveal` in `nock.room.handle_message`

```python
# src/nock/room.py (signatures unchanged, spec 011)
def handle_message(state, player_id, message, now, config=DEFAULT_CONFIG) -> Outcome: ...
def replay(state: RoomState, entry: LogEntry) -> RoomState: ...
```

`Reveal(target)` from joined player `p` is input (spec 013: it sets
`last_input_at` and wakes an idle player). It is not an edit: spec 037's rate
limit does not count it, and the budget is what limits reveals. Its checks run in
this order; the first that fails refuses the reveal (unchanged state, no entry,
one `ErrorMessage` in `reply`):

1. (spec 026) the grid is solved: `grid_solved`.
2. `state.settings.help_mode` is `none`: `help_disabled`.
3. The target names nothing, as for a check (spec 023):
   - `CellTarget(row, column)` that is not a letter cell of `state.grid` (a clue
     cell, an empty cell, or outside the grid): `not_a_letter_cell`;
   - `WordTarget(row, column, clue_index)` where `(row, column)` is outside the
     grid or not a clue cell, or `clue_index` is not an index of its clues:
     `invalid_target`.
4. Nothing is left to reveal: a `CellTarget` whose cell is locked, or a
   `WordTarget` whose cells are all locked: `invalid_target` (decision 2).
5. The budget is spent: a `CellTarget` while `state.reveal_budget.letters` is 0,
   or a `WordTarget` while `state.reveal_budget.words` is 0: `budget_exhausted`.

Help mode `vote` behaves like `free` until spec 025 is built; spec 025 then turns
a reveal into a vote.

The cells revealed, in this order:

- letter: the one cell;
- word: `state.grid.word_cells(row, column, clue_index)`, in reading order,
  leaving out the cells that are locked.

Each revealed cell gets its solution letter (the letter of the normalised `answer`
of any clue whose word holds the cell, as in spec 023), whatever it held before:
nothing, a wrong letter, the right letter, or a pencil letter (spec 020).

An accepted reveal, with `s = state.seq`, produces in one step:

- one entry `RevealResult(seq=s + 1, player_id=p, target=<the target as received>, reveal_budget=<what is left after it>)`, where what is left is `state.reveal_budget` with `letters` 1 lower for a letter target, or with `words` 1 lower for a word target. A word costs one word, whatever its length, and no letter;
- then, for the k-th revealed cell (k from 1), one entry
  `CellLocked(seq=s + 1 + k, row, column, letter=<its solution letter>, revealed=True)`;
- then the completion entry of spec 026 when it applies: `grid_solved`, or
  `grid_full_wrong` when the reveal fills the grid and a letter elsewhere is wrong.

State after the step: `reveal_budget` is what is left, and `settings.reveal_budget`
(the allowance the host set) does not change; each revealed cell has its solution
letter, `pencil = False`, `author = None`, `locked = True`, `revealed = True`,
`wrong = False`, `changed_seq` = the seq of its `cell_locked` and
`changed_by = None` (as `replay` of `cell_locked` does); `state.seq` is the last
seq of the step.

Every entry is broadcast to every joined connection, the revealer's included
(spec 011 delivery). A revealed letter is sent only in its `cell_locked` frame
and, after it, in snapshots (spec 039 decision 10); `reveal_result` and every
refusal carry no letter.

### `replay` additions (spec 018 table)

| Event | Effect on the state |
| --- | --- |
| `reveal_result` | `reveal_budget = event.reveal_budget` |
| `cell_locked` | as specs 018 and 023, and also `pencil = False` |

Replaying the entries of a reveal gives the same state as the live step.

### What a browser may receive (spec 037, extended)

Spec 037's third rule forbids a letter at a cell other than one earned there
before the payload was sent. This spec adds how a revealed letter is earned:

- A letter revealed at a cell is earned there by the `cell_locked` frame
  (`revealed` true) that carries it. With `s` the `seq` of that frame, a payload
  may show that letter at that cell when it is that frame, a snapshot whose `seq`
  is `s` or more, or a frame that a client received after it had already received
  that frame or such a snapshot.
- Any other payload that shows it is a leak: an HTTP body, a frame that a client
  received before its own revealing frame (or such a snapshot), or a snapshot
  whose `seq` is below `s`.
- The rule keys on the revealing frame and its `seq`, not on the order of the log
  across clients. A letter typed at a cell stays earned there as spec 037 says.

### Client: revealed cells

`web/src/lib/roomSession.ts`:

- An applied `reveal_result` sets the kept snapshot's `reveal_budget`
  (`RevealBudgetView`) to the event's `reveal_budget`.
- An applied `cell_locked` already sets `revealed` and clears the author (spec
  016); nothing changes there.

On the `cell` element of each letter cell (spec 006):

- New attribute `data-revealed`: `true` when the confirmed cell's `revealed` is
  true, else `false`.
- A cell with `data-revealed="true"` holds one `data-testid="reveal-mark"` and one
  `data-testid="reveal-label"`; any other cell holds neither.
  - `reveal-mark` is the corner marker: `aria-hidden="true"`, no text, a box drawn
    with its `background-color` (a `clip-path` may cut it to a triangle) in the
    cell's top-right corner. Its bounding box lies inside the cell's box (1 px
    tolerance), with its right edge within 4 px of the cell's right edge and its
    top edge within 4 px of the cell's top edge. It is at least 6 px and at least
    a quarter of the cell side wide and high. Its colour has a contrast of at
    least 3:1 against the cell's computed `background-color`. Its computed
    `visibility` is `visible`.
  - `reveal-label` has the class `visually-hidden` (spec 035) and the text
    `t("a11y.revealed")`, so a screen reader reads the cell as revealed.
- A revealed cell is locked: spec 016's rules apply (typing and erasing do
  nothing, the confirmed letter shows over a pending edit), its letter is bold
  (spec 035 AC-7), and its `data-author` is `""`.

### Client: reveal controls

Shown on the room page once it has a snapshot, in the room toolbar right after
`check-panel`, while the kept settings' `help_mode` is not `none`. With `none` the
panel is absent from the page (spec 025 AC-4 asks the same of the check panel).

- `data-testid="reveal-panel"`, a `role="group"` with `aria-label`
  `t("reveal.label")`, holding two buttons in this order. In the table, `letters`
  and `words` are the kept snapshot's `reveal_budget` (what is left):

  | `data-testid` | Text | `aria-label` | Sends |
  | --- | --- | --- | --- |
  | `reveal-letter` | `t("reveal.letter", { count: letters })`, or `t("reveal.letter_none")` while `letters` is 0 | `t("reveal.letter_label", { count: letters })`, or `t("reveal.letter_none_label")` while `letters` is 0 | `{"type": "reveal", "target": {"scope": "letter", "row": r, "column": c}}` for the selected cell |
  | `reveal-word` | `t("reveal.word", { count: words })`, or `t("reveal.word_none")` while `words` is 0 | `t("reveal.word_label", { count: words })`, or `t("reveal.word_none_label")` while `words` is 0 | `{"type": "reveal", "target": {"scope": "word", "row": cr, "column": cc, "clue_index": i}}` for the selected word's clue |

- `reveal-letter` is `disabled` while nothing is selected, while the selected cell
  is locked (confirmed `locked`), while `letters` is 0, and while the grid is
  solved (spec 026). `reveal-word` is `disabled` while nothing is selected, while
  every cell of the selected word is locked, while `words` is 0, and while the
  grid is solved. (Spec 025 adds: while a vote is open.)
- A button disabled because its budget is 0 says why with its own text
  (`Plus de lettre`, `Plus de mot`). That text keeps a contrast of at least 4.5:1
  against the button's background, although spec 035's contrast scan leaves
  disabled controls out.
- Pressing an enabled button sends its message once and does not move the
  selection; the page waits for the server's events (no local guess of the
  letter).
- An `error` answering a reveal changes nothing on the page. Of the codes a reveal
  can get, only `not_a_letter_cell` and `grid_solved` are also edit answers (spec
  015) that remove a pending edit. The page never sends a letter reveal on a
  non-letter cell and disables the buttons once the grid is solved, so in normal
  use these refusals cannot remove an unrelated pending edit (as spec 023 says of
  checks).

### Client: room toolbar

(The lead noted on 2026-10-14 that the room header has no spare height at 568 by
320: `grid-viewport` is 103 px high there, against the 100 px floor of spec 013
AC-6. This section is the plan for the controls of this spec and of specs 019, 020
and 025.)

- `data-testid="room-toolbar"`, inside the room header after `share-panel`, holds
  the tools of specs 018, 020, 023, 024 and 019 in this relative order, each
  before the next: the undo control (`undo-button` and `undo-message`, spec 018),
  the pencil controls (spec 020, once built), `check-panel` (spec 023),
  `reveal-panel` (this spec), the authors switch (spec 019, once built). This is
  not the toolbar's exact content: specs 021, 022 and 027 add theirs, and other
  controls may sit before, between or after these. (Note from the lead,
  2026-10-15: the order is relative, so that the controls of specs 019-022 and 027
  can join the toolbar without changing this criterion.) Moving the undo control
  and `check-panel` into it changes none of their test ids, texts, labels or
  behaviour.
- A small window is one with `window.innerHeight <= 500` or
  `window.innerWidth <= 480` (the room page's existing breakpoint). On a small
  window:
  - the toolbar is one row: it never wraps, and the vertical ranges of any two of
    its visible buttons overlap;
  - when its content is wider than its box, it scrolls sideways (computed
    `overflow-x` `auto` or `scroll`);
  - `data-testid="room-toolbar-more"`, inside the toolbar, with
    `aria-hidden="true"` and no text, is the edge fade of spec 014 AC-7 applied
    to the toolbar. It is visible (computed `visibility` `visible` and `display`
    not `none`) at the toolbar's right edge while toolbar content is hidden past
    that edge (`scrollWidth - clientWidth - scrollLeft > 1`). It is not visible
    while a toolbar control has the focus from the keyboard (`Tab` or
    `Shift+Tab`); a pointer focus keeps it;
  - a control that gets the focus from the keyboard is scrolled whole into the
    toolbar's visible part, and its focus outline (spec 035 AC-2) is drawn whole
    inside the toolbar; a pointer focus never makes the page scroll the toolbar
    (as spec 035's "Pointer focus in the host panel").
- On a larger window the toolbar may wrap, and `room-toolbar-more` is not visible.
- At every window size of spec 006 AC-5, in desktop and touch contexts, spec 013
  AC-6's guarantees keep holding with the toolbar and every control of this spec
  shown: `grid-viewport` at least 100 px high, no vertical or horizontal page
  scroll, the grid inside the viewport at zoom 1, and the clue bar inside the
  window above the in-app keyboard.
- A browser that makes the scrolling toolbar a Tab stop by its own rule (Firefox
  can, as with `host-panel`) is left as it is (spec 035, "Out of scope").

### Activity feed

Spec 013 already turns each applied `reveal_result` into one feed item,
`data-kind="reveal"`, with the text
`t("feed.reveal.letter" | "feed.reveal.word", { name })` (the revealer's nickname
and the scope). This spec keeps those keys and texts.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `reveal.label` | `Révéler` |
| `reveal.letter` | `Lettre ({count})` |
| `reveal.word` | `Mot ({count})` |
| `reveal.letter_label` | `Révéler la lettre (reste {count})` |
| `reveal.word_label` | `Révéler le mot (reste {count})` |
| `reveal.letter_none` | `Plus de lettre` |
| `reveal.word_none` | `Plus de mot` |
| `reveal.letter_none_label` | `Révéler la lettre : plus de lettre à révéler` |
| `reveal.word_none_label` | `Révéler le mot : plus de mot à révéler` |
| `a11y.revealed` | `lettre révélée` |

Each `aria-label` holds the words of the visible text (WCAG 2.5.3), as in spec 023
decision 7.

### Test harness

- Rule unit tests: `new_room("ABC123", fx01_grid, NOW)`, players added with
  `join_room`, letters written with `handle_message(..., EditLetter(...))`, then
  `handle_message(state, "p1", Reveal(target=...), NOW)`.
- `R1` is a FX-01 room with players `p1` (host) and `p2` (seq 2 after the joins)
  where `p1` wrote `T` at (1, 0) and `X` at (1, 1), and `p2` wrote `I` at (2, 2):
  seq 5, budget 5 letters and 1 word. Solutions: (1, 0) T, (1, 1) A, (1, 2) M,
  (1, 3) I, (1, 4) S, (2, 2) I, (3, 2) M, (4, 2) E.
- `FULL17` is spec 026's: the 17 FX-01 letters other than (4, 4) written right by
  `p1` in row-major order, in a room with `p1` and `p2` created at `NOW`: seq 19.
- WebSocket tests: as spec 011 (`TestClient`, FX-01 room,
  `RoomConfig(max_edits_per_second=1000)`).
- Traffic checker: spec 037's (`TrafficLog` in `tests/spec037_harness.py`; `leaks_in`
  and `replay_problems` in `tests/test_spec_037_ac01_full_game_traffic.py`) (Note
  from the lead, 2026-10-15: the old path was `tests/test_spec_037_integrity.py`,
  before the spec 037 tests were split into one file per criterion group) with the
  reveal rule of "What a browser may
  receive" added; this spec's test file holds its own copy, as spec 023's does.
- Full game with reveals (AC-5, WebSocket): spec 037's full-game setup (every text
  frame of each client and every HTTP body recorded; the room created by
  `POST /api/rooms` on FX-01, catalogue entry 1), with these steps. Ana and Bob
  join. Bob types `V`, `I`, `D`, `E` at (2, 1) to (2, 4). Cy joins, so his snapshot
  comes before any reveal. Ana reveals `CellTarget(row=4, column=4)` (`T`, a cell
  nobody typed). Ana reveals `WordTarget(row=0, column=2, clue_index=0)` (MIME:
  (1, 2), (2, 2), (3, 2), (4, 2)). Dee joins, so her snapshot comes after both
  reveals. Ana and Bob type the ten cells still empty with their solution letters,
  (0, 1) `N`, (1, 0) `T`, (1, 1) `A`, (1, 3) `I`, (1, 4) `S`, (3, 1) `A`, (3, 3)
  `E`, (3, 4) `N`, (4, 1) `L`, (4, 3) `S`; the last one solves the grid.
- Browser game with reveals (AC-5, browser with live server): spec 037's browser
  recording (every `framereceived` of every WebSocket of every page, every text
  response body) on a room registered on FX-01, with three browser contexts. Ana
  joins and types `VIDE` from (2, 1). Cy joins. Ana taps (4, 4) and clicks
  `reveal-letter`, then taps (2, 2) twice (MIME, `down`) and clicks `reveal-word`.
  Dee joins. Ana types the ten remaining letters (spec 008 skips the locked cells),
  60 ms or more between keys.
- "Browser with mocked socket" and "browser with live server": as spec 023.
- Window sizes and contexts: the eight sizes of spec 006 AC-5. Desktop context:
  that viewport, no touch. Touch context: as spec 014's "Test harness" (that
  viewport, `has_touch=True`, `device_scale_factor=2`, `is_mobile=True` except
  under Firefox, and spec 009's `(pointer: coarse)` init script under Firefox and
  WebKit), which shows spec 009's in-app keyboard.
- The tests of this spec use help mode `free`, or `none` where a criterion says
  so. None of them sets `vote`, whose behaviour spec 025 changes.
- Engines: every browser criterion runs in Chromium and WebKit locally and also
  Firefox in CI (`specs/_architecture.md`). No check of this spec is
  Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-6.2.1) (rule unit test; WebSocket; browser with live server) A revealed cell shows the right letter, is locked and has no author, for every player. Rule: given `R1`, when `p1` reveals `CellTarget(row=1, column=1)` (which holds `X`), then the outcome's entries are `RevealResult(seq=6, player_id="p1", target=CellTarget(row=1, column=1), reveal_budget=RevealBudget(letters=4, words=1))` then `CellLocked(seq=7, row=1, column=1, letter="A", revealed=True)`; the new state has seq 7, `reveal_budget` 4 letters and 1 word, `settings.reveal_budget` still 5 letters and 1 word, and (1, 1) with `letter="A"`, `pencil=False`, `author=None`, `locked=True`, `revealed=True`, `wrong=False`, `changed_seq=7`, `changed_by=None`, which `grid_state` shows too. When `p2` then reveals `WordTarget(row=0, column=2, clue_index=0)`, the entries are `RevealResult(seq=8, player_id="p2", target=WordTarget(row=0, column=2, clue_index=0), reveal_budget=RevealBudget(letters=4, words=0))` then `CellLocked` seq 9 at (1, 2) `M`, seq 10 at (2, 2) `I`, seq 11 at (3, 2) `M`, seq 12 at (4, 2) `E`, each with `revealed=True`, and (2, 2), which `p2` had typed, now has `author=None`. In a second run from `R1`, `p1` checks `CellTarget(row=1, column=0)` (seq 6 and 7, spec 023) then reveals `WordTarget(row=0, column=0, clue_index=0)`: the `reveal_result` (seq 8, budget 5 letters and 0 words) is followed by `cell_locked` for (1, 1), (1, 2), (1, 3), (1, 4) only (seq 9 to 12), and (1, 0) keeps `revealed=False` and its author `p1`. WebSocket: A (`Ana`) and B (`Bob`) join a FX-01 room, B types `X` at (1, 1), then A sends `{"type": "reveal", "target": {"scope": "letter", "row": 1, "column": 1}}`: A and B each receive, in seq order, one `reveal_result` then one `cell_locked` for (1, 1) with letter `A` and `revealed` true; a client C joining afterwards gets a snapshot whose (1, 1) has `letter="A"`, `locked=True`, `revealed=True` and `author=None`. Browser: two pages join one FX-01 room as `Ana` and `Bob`; Bob taps (1, 1) and types `X`; Ana taps (1, 1) and clicks `reveal-letter`; then on both pages (1, 1) has `data-letter="A"`, `data-locked="true"`, `data-revealed="true"`, `data-author=""` and one `reveal-mark` that meets the rules of "Client: revealed cells"; Bob then tapping (1, 1) and pressing `B` changes nothing and sends no `edit_letter`.
- **AC-2** (AC-6.2.2) (rule unit test; WebSocket; browser with mocked socket) Reveals draw on a room budget set by the host; the default is 5 letters and 1 word. Rule: `new_room(...)` has `reveal_budget` and `settings.reveal_budget` both equal to `RevealBudget(letters=5, words=1)`. In a FX-01 room with `p1` (host) and `p2`, five letter reveals by `p1` and `p2` on five different cells leave `RevealBudget(letters=0, words=1)`, and a sixth is answered `budget_exhausted`; one word reveal then leaves `RevealBudget(letters=0, words=0)`, and a second word reveal is answered `budget_exhausted`. From a fresh room, one word reveal leaves 5 letters: a word costs no letter. After 2 letter reveals and 1 word reveal, the host's `ChangeSettings(help_mode="free", reveal_budget=RevealBudget(letters=7, words=2))` leaves `RevealBudget(letters=5, words=1)` (spec 014: new allowance minus what was used), and the next letter reveal's `reveal_result` carries `RevealBudget(letters=4, words=1)`. WebSocket: in a FX-01 room where the host A sent `change_settings` with the budget 1 letter and 1 word, A reveals (1, 0): A and B receive a `reveal_result` whose `reveal_budget` is 0 letters and 1 word; B's reveal of (1, 1) is answered `error` `budget_exhausted` to B only; a client C joining afterwards gets a snapshot whose `reveal_budget` is 0 letters and 1 word and whose `settings.reveal_budget` is 1 letter and 1 word. Browser: given a FX-01 snapshot with `reveal_budget` 5 letters and 1 word and (2, 2) tapped, `reveal-letter` reads `Lettre (5)` and `reveal-word` reads `Mot (1)` (texts built from `fr.json`); after the mock sends a `reveal_result` (seq 6, scope letter) whose `reveal_budget` is 4 letters and 1 word, `reveal-letter` reads `Lettre (4)` and has the `aria-label` built from `fr.json["reveal.letter_label"]` with 4; after a `settings_changed` (seq 7) whose `reveal_budget` is 3 letters and 1 word, it reads `Lettre (3)`.
- **AC-3** (AC-6.2.3) (browser with mocked socket) At zero budget, the reveal controls are disabled and say why. Given a FX-01 snapshot whose `reveal_budget` is 0 letters and 1 word, and (2, 2) tapped: `reveal-letter` is disabled, with the text `fr.json["reveal.letter_none"]` and the `aria-label` `fr.json["reveal.letter_none_label"]`, and `reveal-word` is enabled with the text `Mot (1)`; clicking `reveal-letter` sends nothing (no frame within 300 ms; Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted). When the mock then sends a `reveal_result` (seq 6, scope word) whose `reveal_budget` is 0 letters and 0 words, `reveal-word` becomes disabled, with the text `fr.json["reveal.word_none"]` and the `aria-label` `fr.json["reveal.word_none_label"]`. In both states, the text of each disabled reveal button has a contrast of at least 4.5:1 against its background, computed as spec 035's contrast scan does, on that element although it is disabled. A first snapshot whose allowance (`settings.reveal_budget`) and `reveal_budget` are both 0 letters and 0 words shows the same two disabled buttons.
- **AC-4** (new) (rule unit test; WebSocket) A reveal that cannot apply is refused and changes nothing. Given `R1`: with `help_mode` `none` (set by a `ChangeSettings` from the host `p1`, seq 6), any reveal is answered `help_disabled`, also one whose target names nothing. With `help_mode` `free`: `CellTarget(row=0, column=0)` (a clue cell) and `CellTarget(row=5, column=0)` are answered `not_a_letter_cell`; `WordTarget(row=1, column=0, clue_index=0)` (a letter cell), `WordTarget(row=0, column=2, clue_index=1)` (one clue only) and `WordTarget(row=9, column=9, clue_index=0)` are answered `invalid_target`; after `p1` revealed (1, 1) (seq 7), `CellTarget(row=1, column=1)` is answered `invalid_target`; after the host raised the allowance to 5 letters and 2 words and `p1` revealed MIME, a second reveal of MIME is answered `invalid_target`. With the allowance set to 0 letters and 1 word, `CellTarget(row=1, column=1)` is answered `budget_exhausted`, while `CellTarget(row=0, column=0)` is still answered `not_a_letter_cell` and, once `p1` checked (1, 0) (which locks it, spec 023), `CellTarget(row=1, column=0)` is answered `invalid_target`: the target is checked before the budget. On the solved grid of `FULL17` plus `T` at (4, 4) by `p2`, any reveal is answered `grid_solved`, also after the host set `none`. Each refusal returns the state it was given apart from the player's `last_seen_at` and `last_input_at`, with the same `seq` and `reveal_budget`, no entry and exactly one `ErrorMessage` in `reply`. WebSocket: a refused reveal reaches its sender only; the other client receives nothing.
- **AC-5** (new, from the lead's note of 2026-10-11 on spec 037) (WebSocket; browser with live server) No payload sent to a browser shows a revealed letter before the room revealed it. WebSocket: in the full game with reveals of "Test harness", every recorded frame and HTTP body passes spec 037's three rules with the reveal rule of "What a browser may receive"; Cy's snapshot holds no letter at (4, 4), (1, 2), (3, 2) or (4, 2); Dee's snapshot holds `T` at (4, 4) and `M`, `I`, `M`, `E` from (1, 2) down to (4, 2), each with `revealed=True` and `author=None`; Ana, Bob and Cy each received the five `cell_locked` frames with `revealed` true; the game ends with `grid_solved`. The extended checker reports a snapshot whose `seq` is below the revealing frame's and that shows the revealed letter, a frame received before the revealing frame that shows it, and an HTTP body that shows it, and accepts the same snapshot with a `seq` equal to the revealing frame's. Browser: in the browser game with reveals, every WebSocket frame of the three pages and every response body passes the same rules, and Ana's page received at least one `snapshot`, two `reveal_result` and five `cell_locked` frames with `revealed` true.
- **AC-6** (new, from the lead's note of 2026-10-12 on spec 026) (rule unit test; WebSocket) A reveal that fills the grid completes it. Rule: given `FULL17`, when `p2` reveals `CellTarget(row=4, column=4)` at `NOW + 754.0`, the entries are `RevealResult(seq=20, player_id="p2", target=CellTarget(row=4, column=4), reveal_budget=RevealBudget(letters=4, words=1))`, `CellLocked(seq=21, row=4, column=4, letter="T", revealed=True)` and `GridSolved(seq=22, elapsed_ms=754000)`, and the new state has `solved=True`. With `FULL17` where `p1` wrote `X` at (1, 1) instead of `A`, the same reveal gives the result, the lock and then `GridFullWrong(seq=22)`, and `solved` stays False. In a FX-01 room where every letter cell except the four of MIME holds its right letter, a reveal of `WordTarget(row=0, column=2, clue_index=0)` gives the result, four `cell_locked` and then one `grid_solved`. On the solved grid of the first case, any reveal is answered `grid_solved` (spec 026 AC-4). WebSocket: in a room where Ana, Bob and Cy joined and Ana and Bob typed the 17 letters other than (4, 4), Bob's reveal of (4, 4) makes each of the three clients receive `reveal_result`, `cell_locked` (4, 4) `T` and then `grid_solved`, with consecutive seqs.
- **AC-7** (new) (browser with mocked socket) The reveal controls send the right message and are disabled when they cannot apply. Given a FX-01 snapshot (`help_mode` `free`, budget 5 letters and 1 word): `reveal-panel` is inside `room-toolbar` right after `check-panel`, has `role="group"` and the `aria-label` `fr.json["reveal.label"]`, and holds `reveal-letter` then `reveal-word`; with nothing selected both are disabled. After tapping (2, 2) twice (`down`, word `0,2,0`), clicking `reveal-letter` sends one frame that parses to `Reveal(target=CellTarget(row=2, column=2))` and clicking `reveal-word` one that parses to `Reveal(target=WordTarget(row=0, column=2, clue_index=0))`; the selection is still (2, 2) `down`, and no cell changes until the mock answers. With a snapshot where (2, 2) is locked, after selecting it `reveal-letter` is disabled and `reveal-word` enabled; with every cell of MIME locked, `reveal-word` is disabled too. After the mock sends `grid_solved`, both are disabled. A snapshot with `help_mode` `none` shows no `reveal-panel`; a `settings_changed` to `free` shows it, and one back to `none` removes it.
- **AC-8** (new) (browser with mocked socket) The room toolbar keeps the grid's room on small windows, and every control in it can be reached. Setup: spec 013 AC-6's (FX-01 snapshot, `you` host among 8 players, 100 feed items, (3, 1) tapped), with help mode `free` and the budget 5 letters and 1 word. At every window size of spec 006 AC-5, in desktop and touch contexts:
  - Layout: spec 013 AC-6's checks pass with the toolbar and the reveal panel shown.
  - Order: `room-toolbar` is inside the room header and holds `undo-button`, `check-letter`, `check-word`, `check-grid`, `reveal-letter`, `reveal-word` in this relative document order, each before the next, with other controls allowed before, between or after them when other specs add them, and with no other button whose `data-testid` starts with `reveal-`; the test checks the relative order of these six elements, not the toolbar's exact children. (Note from the lead, 2026-10-15: the order is relative, so that the controls of specs 019-022 and 027 can join the toolbar without changing this criterion.)
  - One row, at 320 by 568, 568 by 320, 360 by 740 and 740 by 360: the vertical ranges of any two of these six buttons overlap. When the toolbar's `scrollWidth` is more than its `clientWidth` plus 1, its computed `overflow-x` is `auto` or `scroll` and, with `scrollLeft` 0, `room-toolbar-more` is visible. At the four other sizes `room-toolbar-more` is not visible.
  - Keyboard, desktop context: after the test calls `focus()` on `share-link` from `page.evaluate`, it presses `Tab` until each of the six buttons has had the focus (at most 60 presses). While each one has the focus: its box lies inside the toolbar's client area (1 px tolerance); its computed outline has a style other than `none` and `auto`, a width of at least 2 px and a colour of contrast at least 3:1 against white (spec 035 AC-2); the outline passes the "Not clipped" measure of spec 035's "Focus outline of the feed's scrolling list", with the toolbar among the clipping ancestors; and `room-toolbar-more` is not visible.
  - Pointer: for each of the six buttons, after `scrollIntoView({block: "nearest", inline: "nearest"})`, `document.elementFromPoint` at the centre of its box returns the button or one of its descendants.
- **AC-9** (new) (browser with mocked socket) A revealed cell is marked by more than its colour, and the reveal controls meet spec 035. Given a FX-01 snapshot (`seq` 10, `you` `p1` and host, players `p1` and `p2`) where (1, 0) holds `T` revealed (`locked`, `revealed`, no author) and (1, 1) holds `A` locked by a check (`revealed` false, author `p2`): (1, 0) has `data-revealed="true"`, one `reveal-mark` and one `reveal-label` whose text is `fr.json["a11y.revealed"]`; (1, 1) has `data-revealed="false"` and neither; the mark's `background-color` has a contrast of at least 3:1 against the `background-color` of (1, 0), both while (1, 0) is not selected and while it is selected. In this state with (2, 2) tapped, at 1280 by 720 and at 360 by 740, spec 035's contrast scan (AC-8) and language scan (AC-9) find no offending element. In a separate run on the same snapshot at 1280 by 720, keyboard only with no tap (spec 035's harness): `tab_to` `grid`, then `Tab` selects the first unfinished word (spec 009), then `tab_to` `reveal-letter` and `tab_to` `reveal-word` each reach an enabled button that shows spec 035 AC-2's outline.
- **AC-10** (new) (rule unit test) Reveals and the budget survive a reload. Given the entries of `R1`'s play followed by the two reveals of AC-1 (seq 1 to 12), when they are replayed in order with `replay` from `new_room` on the same grid, the result equals the live state for `seq`, `reveal_budget`, `settings` and `cells`; and the same room saved in a `RoomStore` and loaded again (spec 018) has `reveal_budget` 4 letters and 0 words, keeps (1, 1) and the four cells of MIME revealed with no author, and answers a word reveal with `budget_exhausted`.

## Edge cases and errors

Note from the lead (2026-10-11, from the spec 037 review): spec 037 AC-1's
traffic check counts a letter as earned only when a player typed it. This
spec must extend that check: a `cell_locked` frame with `revealed: true` earns
its letter at that cell; any payload sent before the revealing frame that shows
the letter is a leak; the full game must reveal a cell nobody typed and a word,
with one late joiner's snapshot before the reveal (must not show the letter) and
one after; the same for the browser game. The earn rule keys on the revealing
frame, not on log order across clients. (Addressed by "What a browser may
receive", the two games of "Test harness" and AC-5.)

Note from the lead (2026-10-12, from the spec 026 review): spec 026's
completion rule also triggers on `cell_locked` (`_with_completion` in
`src/nock/room.py`), and only a reveal can fill a cell through a lock. This
spec's tests must cover completion by a reveal: `grid_solved` after the last
revealed letter, or `grid_full_wrong` when the grid is then full but wrong.
Revealing on a solved grid is refused with `grid_solved` (spec 026 AC-4).
(Addressed by AC-6.)

- A right letter already in the cell (AC-1): revealed all the same. It loses its
  author, so the recap credits it to nobody (spec 028 AC-3), and the budget is
  spent. Skipping it would tell the group that the letter was right, which is a
  free check (decisions 4 and 11). (Note from the lead, 2026-10-15: "decision 4,
  open question 1" became "decisions 4 and 11", the human's answer.)
- A wrong letter (AC-1): replaced by the solution letter; its strike goes, on the
  server (`wrong = False`) and on the page (`cell_locked` clears `wrong`, spec 023).
- Locked cells in a word (AC-1, AC-4): left out of the reveal; a word whose cells
  are all locked is refused `invalid_target` and costs nothing.
- Two reveals of one cell at once (AC-4): the second is answered `invalid_target`
  and costs nothing. Two reveals of the last letter of the budget at once (AC-2):
  the second is answered `budget_exhausted`.
- A pending edit on a cell being revealed (AC-1): the page shows the revealed
  letter at once (spec 016: a locked cell shows its confirmed letter); the server
  answers the pending edit `cell_locked`, which removes it from the queue (spec 015).
- Allowance changed after reveals (AC-2): spec 014's rule, new allowance minus what
  was used, never below 0. The allowance itself is shown only in the host's form;
  the buttons show what is left.
- Undo after a reveal (AC-1): an undo of an edit whose cell was revealed since is
  refused `nothing_to_undo` (spec 018 step 2: the cell is locked).
- Checks after a reveal (AC-1): a revealed cell is locked, so checks leave it out
  (spec 023).
- Pencil letters (AC-1): a revealed cell holds no pencil letter. No pencil letter
  exists until spec 020 is built, so no criterion of this spec tests it.
- Help mode `vote` (all): acts as `free` until spec 025 is built; the tests of this
  spec never set it.
- Rate (AC-2): reveals are not throttled; the budget limits them, and each
  accepted reveal is logged.
- Feed (AC-1): one line per accepted reveal (spec 013); a refusal adds none.
- Reading a cell's letter (AC-1, AC-9): a revealed cell's text also holds the
  hidden `reveal-label`, as a crowded cell holds spec 035's hidden overflow label;
  tests read the letter from `data-letter`.
- Crowded revealed cell (AC-9): a label of spec 035 AC-11 in the top-right slot
  (three or more cursors on a cell of 44 px or more) may cover the corner mark;
  the label is drawn over it.
- Tab order (AC-8): the toolbar comes before the roster, the feed, the host panel
  and the grid in document order, so spec 035's walks keep their landmarks
  (`share-link` first among the room's controls, the grid last). Its controls add
  Tab stops before the roster list, which spec 035 AC-12's walk passes.
- Scrollbar height (AC-8): a visible horizontal scrollbar takes height in desktop
  engines; the toolbar may hide it, since `room-toolbar-more` already shows that
  more content exists (spec 014 AC-7).

## Out of scope

- Generated hints and dictionary lookups (epic E6).
- Check a letter, a word or the grid: spec 023.
- Group decision on help: spec 025.
- Completion detection: spec 026.
- Undoing a reveal, or giving budget back.
- Revealing the whole grid.
- A confirmation step before a reveal.
- Keyboard shortcuts for reveals (spec 035 leaves them out too).
- Showing on the cell who revealed it (the feed says it).
- A collapsible help menu in place of the toolbar (decision 12). (Note from the
  lead, 2026-10-15: "open question 2" became "decision 12", the human's answer.)

## Work packages

None.

## Decisions

Proposed in the Phase 6 refine of 2026-10-14 and approved by the human with the
spec. Each one is already part of the spec above. Items 4 and 8 were also open
questions: the human's answers to them are items 11 and 12 below.

1. No protocol change. `Reveal`, `RevealResult`, `CellLocked(revealed=True)` and
   `budget_exhausted` already exist (spec 039).
2. Nothing to reveal is answered `invalid_target`, not `cell_locked`. The page
   treats `cell_locked` as the answer to an edit (spec 015) and removes a pending
   edit for it, so a reveal refused with it in a race would drop an unrelated
   pending letter. `invalid_target` already means "the target names nothing" for
   checks (spec 023 decision 1).
3. Order of refusals: solved, help mode `none`, target, then the reveal's own
   (nothing to reveal, budget). The first three are spec 023's order.
4. A reveal reveals every unlocked cell of its target, right letters included.
5. A word costs one word, whatever its length, and no letter.
6. `reveal_result` first, then one `cell_locked` per revealed cell in reading order
   (spec 023 decision 5, spec 039 decision 10).
7. The budget shows in the button texts (`Lettre (4)`); a spent budget replaces
   the text with its reason (`Plus de lettre`), so the disabled control says why
   by itself, and that text keeps 4.5:1.
8. Small windows: one toolbar row that scrolls sideways, like the host panel (spec
   014 AC-7), shared by the tools of specs 018, 020, 023, 024 and 019, so new
   controls cost no height.
9. The corner mark (a shape) and a hidden text are the signs of a revealed cell
   that do not rely on colour (spec 035), and they tell it apart from a cell locked
   by a check.
10. The reveal panel is hidden in `none` mode from this spec on (spec 025 AC-4),
    rather than disabled first and hidden later.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question. Each one is already part of the spec above.

11. A cell that already holds the right letter, inside a reveal's target (former
    open question 1). Options: reveal it all the same, spending the budget, so its
    author loses the credit in the recap; skip it, which tells the group the letter
    was right (a free check); or refuse a letter reveal of such a cell, which tells
    the same. Pick: reveal it all the same (decision 4).
12. Room toolbar on small windows (former open question 2). Options: one row that
    scrolls sideways, with an edge fade; or, on small windows, one `Aide` button
    that opens the check and reveal controls over the page, which hides them behind
    one more tap. Pick: the row that scrolls sideways, the pattern the host panel
    already uses (decision 8). The other specs that add controls to the toolbar
    (019, 020, 021, 022, 027) follow it.

## Open questions

None.
