---
id: "045"
title: Auteurs mode
status: done
---

# 045 - Auteurs mode

Epic E10 Quality bar · Release: MVP · No backlog story: this is the first spec of
build step 5 of `specs/_design.md` (section 14). It applies `_design.md` section 7
(Auteurs mode), with the parts of sections 2 (`--nock-ink`, `--nock-muted`,
`--nock-legend-bg`, `--nock-line`), 3 (the Auteurs inks `--player-ink-0` to
`--player-ink-7`), 4 (the Auteurs legend's type) and 6 (letter marks: the strike in
Auteurs mode) that the mode uses. It replaces the author band of spec 019, which is
removed. It builds on spec 041 (tokens, inks, fonts, `PLAYER_ICONS`), spec 042
(grid cells, `cell-letter`, the strike, `player-icon`, the « Accessibilité »
switch), spec 043 (the room Menu and its `authors-switch` item, the play area, the
clue bar) and spec 044 (the in-app keyboard), and redefines none of them; where it
changes one of their rules, "Refined specs" says so. The FX-01 reference grid is in
`specs/_reference.md`; the stack in `specs/_architecture.md`.

## Goal

A player who wonders who wrote a doubtful letter turns « Auteurs » on in the Menu:
each letter is then drawn in the ink of the player who wrote it, and a legend under
the grid names each player in their ink. The mode is off by default and the browser
remembers it. This replaces spec 019's coloured band at the bottom of each cell,
whose box, contrast, hatching and drawing-order rules go with it, and the
« Lettre de … » line of the clue bar, which leaves the clue bar to the clue. The
rule of the human holds: the simplest design
that removes edge cases; the core is the game.

## Public interface

No new Python name, no new protocol message, no new HTTP route. Client only
(`web/`: chiefly `web/src/lib/GridViewport.svelte`, `web/src/lib/authorsView.ts`
and `web/src/lib/RoomPage.svelte`). Every colour is
a token of spec 041 used for its job in `_design.md` section 2; every string comes
from `web/src/i18n/fr.json`.

### Terms

- The mode: the Auteurs mode, on while `authors-switch` (spec 019, an item of spec
  043's `room-menu`) has `aria-pressed="true"`.
- The finder of a letter cell: its author as spec 019 defines it ("Who is the author
  of a letter": the player of its last `letter_changed`, the confirmed author
  `data-author` of spec 015, never a pending edit), when the cell shows a letter,
  is not revealed, and that player is a player of the kept snapshot (present or
  disconnected). A cell has no finder when it is empty, revealed, or written by a
  player who is not in the kept snapshot (who left, was removed, or was never
  known to the page).
- The ink of a player: `--player-ink-N`, N their colour index (spec 041).

### The switch (refines spec 019's "Client: the authors switch")

`authors-switch` keeps its place (the first item of `room-menu`), its label
`t("authors.switch")`, its detail `t("authors.on")` / `t("authors.off")` (spec 043),
its `aria-pressed`, and its rules: never disabled, sends nothing (spec 017's `ping`
frames aside), activating it leaves the Menu open (spec 043).

- It starts from `localStorage["nock.authors"]`: `"true"` gives `true`; any other
  value, or none, gives `false` (off by default). Each activation flips it and
  writes `"true"` or `"false"` there (`_design.md` section 7, decided by the lead on
  2026-10-22 on the human's instruction; spec 042's two switches work the same
  way).
- When `localStorage` throws, it starts off and its state holds for the page's life.

### The letters while the mode is on (`_design.md` section 7)

On each letter `cell` (spec 006):

- `data-author-colour` (spec 019's attribute, kept): the finder's colour index
  (`0` to `7`) when the cell has a finder, `""` otherwise. While the mode is off,
  `""` on every cell.
- The cell's computed `color`, which `cell-letter` inherits (spec 042), is the
  finder's ink `var(--player-ink-N)`; with no finder it stays `--nock-ink`. This
  holds on every background of the cell (spec 042's table, the flash overlay of
  spec 041 included) and replaces, while the mode is on, the pencil grey of spec
  020 and the ink of spec 041 during a flash:
  - a pencil letter keeps its italics (spec 020) and takes its finder's ink;
  - a locked letter (checked right) keeps weight 700 (spec 035 AC-7) and its
    finder's ink; a revealed letter has no finder and stays ink, bold, with its
    notch (spec 042);
  - during a flash (spec 016) the letter keeps its finder's ink, the replacer being
    the new finder once the server confirms the letter.
- Wrong after a check (spec 042's strike): `text-decoration-color` is `--nock-ink`
  while the mode is on, `--nock-red` while it is off. Its line and style are the
  same in both modes, and its thickness follows spec 042's rule `max(2px, 0.07em)`
  in both (the px value can differ, as AC-8 shrinks the grid and its font at 1280
  by 720). (Note from the lead, 2026-10-23: this read "Its line and thickness do
  not change.")
- Nothing else of the cell changes with the mode: its background, its outline, the
  triangles or icons, the notch, the catch-up ring and the arrows are spec 042's.
- The colours follow the confirmed grid within 300 ms of each event the page
  applies: a `letter_changed` (a new finder, or no letter for an erase), a
  `cell_locked` with `revealed` true (no finder), a `player_left` (that player's
  letters lose their finder), a `player_joined` (a player seated back by spec 032
  is a finder again for the letters that still carry their id), a snapshot.

With the mode off, a letter's colour does not depend on its author (spec 019 AC-2).

### The legend (`_design.md` sections 4 and 7)

While the mode is on, `grid-area` (spec 043) holds `data-testid="authors-legend"`,
right after `grid-viewport`, `aria-hidden="true"` (it is a key to colours, which a
screen reader does not show). While the mode is off there is no `authors-legend`.

- Content, in this order: `data-testid="authors-legend-label"`, the text
  `t("authors.legend")` (« Auteurs : »); then one `data-testid="authors-legend-name"`
  per player of the kept snapshot, in the snapshot's `players` order with joiners
  appended (join order, as the Joueurs list), with `data-player-id` and
  `data-colour`, whose text is the player's nickname through spec 040's
  `displayNickname`, inserted as text (spec 037). `you` is listed too. The names
  follow `player_joined` and `player_left` within 300 ms.
- Look: background `--nock-legend-bg`, a 1 px solid `--nock-line` border, radius
  14 px, padding 4 px 12 px; a flex row, gap 8 px between its items, centred; the
  label in 500 0.8rem/1.2 `--nock-font-ui`, `--nock-muted`; each name in weight 700,
  the same size, in its player's ink `var(--player-ink-N)`. It wraps onto more
  lines, each centred, when its items do not fit on one line, its items 8 px apart
  on a line and its lines 2 px apart (`row-gap`, the screens sheet's `.legend`).
  It is never wider than `clue-bar`'s width, nor, in the sheet layout, than
  `grid-area`'s content box (`grid-viewport`'s width); neither width changes with
  the mode, so the legend's lines, and its height `h`, do not depend on the grid's
  size. (Note from the lead, 2026-10-23: the implementation found that in the
  column layout, where `grid-area` is the grid's box (spec 043), a wrapping legend
  made the grid narrower, which made the legend wrap more, until the grid
  collapsed (FX-02, 8 players with 20-character nicknames, at 568 by 320 and 740
  by 360 on a desktop); this read "It wraps onto more lines, each centred, when its
  items do not fit on one line; it is never wider than `grid-area`'s content
  box.", and the 2 px and 8 px are the implementer's values, recorded.)
- Place, when the grid gives it its room (see "The grid's room"): in the flow
  after `grid-viewport`, 8 px under the grid's shown bottom (in the sheet layout,
  where the grid is centred in a `grid-viewport` taller than itself, that can lie
  inside `grid-viewport`'s box; the Note below), horizontally centred on
  `grid-area`'s content box, which is the `grid`'s centre at zoom 1; when the
  grid is zoomed it stays centred
  on `grid-viewport`, wherever the grid is panned. Its top is 8 px below the bottom
  of the part of the `grid`'s box that shows in `grid-viewport` (the grid's bottom
  at zoom 1, `grid-viewport`'s bottom when the zoomed grid fills it). The space
  between the grid's bottom and `grid-viewport`'s bottom is rounded down to a
  quarter pixel when the legend is placed, so the gap is at least 8 px and less
  than 8.25 px. (Note from the lead, 2026-10-23: "right under `grid-viewport`"
  became "after `grid-viewport`, 8 px under the grid's shown bottom", which in the
  sheet layout can lie inside the viewport's box. The implementer's decisions,
  recorded; this read "Place: horizontally centred on the `grid`'s box; its top
  8 px below the bottom of the part of the `grid`'s box that shows in
  `grid-viewport` (the grid's bottom at zoom 1, `grid-viewport`'s bottom when the
  zoomed grid fills it).")
- Place, when the grid gives it no room (see "The grid's room"): over the bottom
  of `grid-viewport`, horizontally centred on `grid-area`'s content box as above,
  its bottom 8 px above `grid-viewport`'s bottom edge, on layer 6 (as the 3-second
  notes, `_design.md` section 8, "Layers of the room page"), with its own
  background and border (the look above), and `pointer-events: none`, so a tap or
  a click on it reaches the cell under it. It then covers only the bottom of
  `grid-viewport` (and, in the column layout when it is wider than the grid, the
  empty play area beside it), never `clue-bar`, `room-topbar`, `grid-status`,
  `keyboard` or `salon`. (Note from the lead, 2026-10-23: new; see "The grid's
  room".)

### The grid's room (`_design.md` section 7)

While the mode is on, unless the rule at the end of this section applies, the
height that spec 043's play area gives `grid-viewport` is
`R` px less, `R = max(38, h + 8)`, where `h` is the legend's height (38 px when the
legend is one line, as drawn); the room it frees holds the 8 px gap and the legend.
`grid-viewport` keeps its width and its top; the grid fits the smaller viewport as on
a resize (spec 006). Nothing else moves: in the sheet layout `room-topbar`,
`clue-bar`, `grid-status` and `keyboard` keep their boxes; in the column layout they
and the Salon keep theirs, except that the block of `grid-viewport`, the legend,
`clue-bar` and `grid-status`, centred in the play area (spec 043), may move by less
than the height of one row of cells when the grid's rounding changes. Spec 013
AC-6's guarantees keep holding with the mode on (`grid-viewport` at least 100 px
high). (Note from the lead, 2026-10-23: "unless the rule at the end of this
section applies" is added; the paragraph read "While the mode is on, the height
that spec 043's play area gives `grid-viewport` is `R` px less".)

`clue-bar` keeps its box in the column layout too: its width is the one spec 043
(Decision 12) gives it from the grid's box with no legend under it, the mode off
or on. (Note from the lead, 2026-10-23: the implementer's decision, recorded; spec
043 Decision 12 alone would make the clue bar narrower with the mode on, as the
grid gives the legend its room, against "nothing else moves" above.)

When giving the legend its room `R` would leave `grid-viewport` under 100 px high,
the grid gives it no room: `grid-viewport` keeps the box it has with the mode off,
and the legend lies over its bottom ("The legend", second "Place"). The height
compared with 100 px is the one `grid-viewport` would have with the room given: in
the sheet layout its height with the mode off less `R`; in the column layout the
height of the grid's box fitted to the height left less `R`. The rule holds in
both layouts and is read again whenever the window, the keyboard, the Salon, the
status or the legend's height `h` changes; since `h` does not depend on the grid's
size ("The legend", its width), the two placements do not alternate. For example,
at 568 by 320 in the touch context (sheet layout, keyboard shown), `grid-viewport`
is 106 px high with the mode off, and `R` = 38 would leave 68 px: the legend lies
over the grid's bottom. The player gets the room back by hiding the keyboard (spec
044). (Note from the lead, 2026-10-23: new. The implementation found that at 568
by 320 in the touch context the room left 68 px, against spec 013 AC-6's 100 px
floor, and nothing else may move to make room.)

### The clue bar (refines spec 019's "Client: the author in words")

The clue bar shows only the clue (`_design.md` section 7): `clue-bar-author` is
removed, in every mode and on every window, with its rules of shrinking on a low
window (spec 019 decision 11) and of following the selected cell (spec 019 decision
12). `clue-bar-text`, `clue-bar-direction` and the buttons are spec 043's.

### The recap's player marks

The recap's rows are spec 047's (its "recap-colour": the player dot, the 12 px
icon in Accessibilité mode, and an empty 10 px slot for a player who left, in place
of spec 028's hatching, which spec 028 borrowed from spec 019). This spec does not
change the recap: until spec 047 is built, `recap-colour` keeps spec 028's
hatching, and the custom property it reads (`--author-departed-hatching` in
`web/src/app.css`) stays; spec 047 removes it.

### Removed

`author-mark` and every rule of spec 019 about it (its colour, its hatching, its box
rules, its baseline probe, its drawing order, its 3:1 contrast in every cell state),
and `clue-bar-author`.

### `fr.json` keys

New:

| Key | Value |
| --- | --- |
| `authors.legend` | `Auteurs :` |

Removed, since nothing shows it any more: `authors.selected`.

Kept: `authors.switch` (`Auteurs`), and spec 043's `authors.on` (`activé`) and
`authors.off` (`désactivé`).

### Refined specs

Each refined spec carries a dated note "(Note from the lead, 2026-10-22: refined by
spec 045, the design's Auteurs mode ...)" and keeps its status. The test-writer
updates the tests of the criteria named here before the implementer runs.

| Spec | Criteria that change | What changes in their tests |
| --- | --- | --- |
| 019 | AC-1, AC-2, AC-3 (browser part), AC-4, AC-5 | AC-3: after the reload the switch is still on and the two letters have Ana's and Bob's inks. AC-1: each filled letter is drawn in its finder's ink (`data-author-colour` and the computed `color` against `--player-ink-N`), a letter with no finder in ink; the band's box runs, drawing-order run and contrast run go. AC-2: with the mode off the letters share one colour; a reload keeps the mode (`nock.authors`). AC-4: the legend names each player in their ink, and the clue bar holds no `clue-bar-author`; the low-window checks of the author line go. AC-5: spec 013 AC-6's checks hold with the legend; the scans run with the mode on |
| 012 | AC-8 (the authors item) | With `authors-switch` on, the five `authors-legend-name` read `Jean-Luc`, `D'Artagnan`, `Ana 2`, `O’Neil` and `Νίκος`, in roster order, in place of the five `clue-bar-author` lines |
| 032 | AC-7 (the browser run) | (1, 0) has `data-author-colour=""` and the computed `color` of `--nock-ink` before the seat back, and `data-author-colour="0"` and `--player-ink-0` after it; the legend lists `Bob`, `Cy`, then `Ana` once she is seated back; the two checks of `clue-bar-author` go |
Specs 034, 041 and 042 get a note and no criterion change: spec 034's ring is drawn
under the marks that remain (spec 042's), and spec 041's hatch row and spec 042's
drawing-order line name a band that is gone. Specs 035 and 043 need no criterion
change either (spec 035's AC-6 never read the author line; spec 043's Menu item
keeps its id, label and detail, with the storage it now has); they carry the notes
of specs 047 and 048, and the lead adds this spec's line to them. Spec 043's
Decision 12 also gets a note, with no criterion change: with the mode on, the
clue bar's width in the column layout is this spec's ("The grid's room"). (Note
from the lead, 2026-10-23: the sentence on spec 043's Decision 12 is new.)

### Test harness

- "Browser with mocked socket" as in spec 043 (FX-01 snapshots from
  `grid_view(fx01_grid)` and `model_copy`, `seq` 5, `you` `p1` (`ANA`, colour 0,
  host) unless a criterion says otherwise; other players `p2` (`BOB`, colour 1),
  `p3` (`CY`, colour 2) and on to `p8` (colour 7) as a criterion gives them), with
  its helpers (`open_menu`, `show_tab`, `tab_to`). FX-02 snapshots from
  `tests/fixtures/fx02.json` (spec 006).
- `EIGHT`: a FX-01 snapshot with players `p1` to `p8` (colours 0 to 7) whose cells
  (1, 0), (1, 1), (1, 2), (1, 3), (1, 4), (2, 1), (2, 2) and (2, 3) hold `T`, `A`,
  `M`, `I`, `S`, `V`, `I`, `D` by `p1` to `p8` in that order, none locked, none
  pencil, and every other letter cell empty.
- Mode on: after `open_menu` and a click on `authors-switch`, or with
  `nock.authors` seeded `"true"` with `context.add_init_script`. Default window
  1280 by 720, desktop context; `localStorage` empty unless a criterion seeds it.
- Colours as spec 041 (`parseColour` of `tests/colour_contrast.js`, exact channels
  for a token, alpha within 0.01). The inks as `rgb()`: 0 rgb(96, 72, 0), 1 rgb(75,
  106, 44), 2 rgb(0, 109, 96), 3 rgb(104, 56, 224), 4 rgb(173, 53, 75), 5 rgb(179,
  0, 138), 6 rgb(144, 79, 0), 7 rgb(120, 64, 48); ink rgb(20, 24, 31). Contrast by
  spec 035's formula.
- Positions are bounding boxes; tolerances 1 px for a position, 0.5 px for a size,
  0.1 px for a font size, unless a criterion says otherwise. Fonts: spec 041's rule
  (wait for `document.fonts.ready` before reading a size or a position that depends
  on text).
- "No frame" means no frame within 300 ms, spec 017's pings not counted.
- Engines: Chromium and WebKit locally, Firefox too in CI. No check is
  Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (new; refines spec 019's switch) (browser with mocked socket) « Auteurs » is off by default, and the browser remembers it. On a FX-01 snapshot with empty `localStorage`, at 360 by 740: after `open_menu`, `authors-switch` has `aria-pressed="false"` and its detail reads `fr.json["authors.off"]`. A click gives `aria-pressed="true"`, the detail `fr.json["authors.on"]`, `localStorage["nock.authors"]` `"true"`, `room-menu` still open, and no frame. After a reload with the same mock, `authors-switch` has `aria-pressed="true"` and `authors-legend` shows. A second click gives `aria-pressed="false"`, `"false"` in storage and no `authors-legend`. With `nock.authors` seeded `"yes"`, the page loads with the mode off.
- **AC-2** (new; refines spec 019 AC-1) (browser with mocked socket) Each letter is drawn in its finder's ink. On `EIGHT` with the mode on: for each N from 0 to 7, the cell written by the player of colour N has `data-author-colour` equal to `N`, and its `cell` and its `cell-letter` have the computed `color` of `--player-ink-N` (the table of "Test harness"), and the colour of a probe `span` with `color: var(--player-ink-N)` appended to `body` (setup); every empty letter cell has `data-author-colour=""`. With the mode off, each of these cells has `data-author-colour=""` and `color` rgb(20, 24, 31).
- **AC-3** (new; refines spec 019 AC-1) (browser with mocked socket) A letter with no finder is ink, and the inks follow the grid. On a FX-01 snapshot (`seq` 7) with players `p1` (colour 0) and `p2` (colour 1), where (1, 0) holds `T` by `p1`, (1, 1) `A` by `p2`, (1, 2) `M` by `p9` (not in the room) and (1, 4) `S` revealed (`locked`, `revealed`, no author), with the mode on: (1, 0) has the ink of colour 0, (1, 1) of colour 1, and (1, 2) and (1, 4) `data-author-colour=""` and `color` rgb(20, 24, 31). Then, each within 300 ms of its event: `letter_changed` (seq 8) at (1, 0) with `X` by `p2` gives (1, 0) the ink of colour 1; `letter_changed` (seq 9) erasing (1, 1) leaves it with no `cell-letter`; `cell_locked` (seq 10) at (1, 0) with `T` and `revealed` true gives it `data-author-colour=""` and ink; `player_left` (seq 11) of `p2` turns every letter by `p2` to `data-author-colour=""` and ink. In a second run whose snapshot holds (1, 0) `T` by `p9`, which is a past player of the room, a `player_joined` (seq 8) of `p9` with colour 2 gives (1, 0) `data-author-colour="2"` and the ink of colour 2 within 300 ms.
- **AC-4** (new) (browser with mocked socket) A pencil letter keeps its italics in its finder's ink, a locked letter its weight, and the strike turns ink. On a FX-01 snapshot with players `p1` (colour 0) and `p2` (colour 3), where (1, 0) holds `T` by `p2` locked by a check (`locked` true, `revealed` false), (2, 3) holds `D` as a pencil letter by `p2`, and (1, 1) holds `X` by `p1` with `wrong` true, with the mode on: (1, 0) has `font-weight` 700 and the ink of colour 3; (2, 3) has `font-style` `italic` and the ink of colour 3, not rgb(85, 91, 103); (1, 1) has `text-decoration-line` containing `line-through`, `text-decoration-color` rgb(20, 24, 31) and the ink of colour 0. With the mode off, (2, 3) has `color` rgb(85, 91, 103) and (1, 1) `text-decoration-color` rgb(180, 35, 24).
- **AC-5** (new) (browser with mocked socket) The mode changes the letters only, and a flash keeps the inks. On `EIGHT`, with `p2` selecting (3, 2) `down` and after a tap on (1, 0) (`across`, TAMIS): for every cell, the computed `background-color`, `outline-style`, and the number of its `remote-selection`, `reveal-mark`, `catch-up-mark` and `clue-arrow` children are the same with the mode on as with it off. With the mode on, when the mock sends `letter_changed` (seq 6) at (1, 0) with `Y` by `p4` (colour 3, replacing `p1`'s letter, so spec 016 flashes the cell): within 300 ms (1, 0) has `data-flash="3"`, a `cell-flash` overlay (spec 041), the background rgb(255, 255, 255) and the ink of colour 3.
- **AC-6** (new; refines spec 019 AC-4) (browser with mocked socket) The legend names each player in their ink, in join order. On `EIGHT` with `p2` named `JEAN-LUC` and `p3` disconnected, with the mode on: `authors-legend` is inside `grid-area`, right after `grid-viewport`, has `aria-hidden="true"`, and holds `authors-legend-label` reading `fr.json["authors.legend"]`, then eight `authors-legend-name` with `data-player-id` `p1` to `p8` in that order, reading `Ana`, `Jean-Luc`, `Cy` and the other nicknames through `displayNickname`, each with `data-colour` its player's index, `font-weight` 700 and the computed `color` of that player's ink. Within 300 ms of a `player_left` (seq 6) of `p4`, there are seven names, without `p4`; within 300 ms of a `player_joined` (seq 7) of `p9` (`ZOÉ`, colour 3), `Zoé` is the last name, with the ink of colour 3. With the mode off there is no `authors-legend`.
- **AC-7** (new) (browser with mocked socket) The legend has the design's look and sits 8 px under the grid. On a FX-01 snapshot with players `p1` to `p4` (short nicknames), with the mode on, at 360 by 740 and at 1280 by 720: `authors-legend` has the computed `background-color` with channels 255, 255, 255 and alpha 0.96, a `1px` `solid` rgb(221, 226, 234) border, `border-radius` `14px` on each corner, padding `4px 12px`, `display` `flex`, `column-gap` `8px`; `authors-legend-label` has `font-size` 12.8 px, `font-weight` 500, `line-height` 15.36 px and `color` rgb(94, 101, 115); each name has `font-size` 12.8 px; the legend is one line (its height is at most 26 px); its horizontal centre is within 1 px of the `grid`'s; its top is 8 px below the `grid`'s bottom (1 px); and it lies inside `grid-area`.
- **AC-8** (new) (browser with mocked socket) The grid gives the legend its room, and nothing else moves. On the snapshot of AC-7, at 360 by 740 in the touch context (sheet layout, keyboard shown) and at 1280 by 720 in the desktop context (column layout, Salon open): the test notes the boxes of `room-topbar`, `clue-bar`, `keyboard` (touch) and `salon` (desktop), and the height of `grid-viewport` and of the `grid`, with the mode off; with the mode on, `room-topbar`, `keyboard` and `salon` have the same boxes, `clue-bar` the same box at 360 by 740 and the same box within 5 px vertically at 1280 by 720; at 360 by 740 `grid-viewport` is 38 px less high (1 px); at 1280 by 720 (where the height limits the grid) the `grid` is between 35 and 40 px less high (38 px, rounded to whole cells). With 8 players whose nicknames have 20 characters each, at 360 by 740 in the touch context, the legend wraps onto more than one line, and `grid-viewport` is `h + 8` px less high than with the mode off (1 px), `h` the legend's height; the legend lies inside `grid-area`, above `clue-bar`'s top, and does not overlap the `grid`'s box. At 568 by 320 in the touch context (sheet layout, keyboard shown), where the room would leave `grid-viewport` 68 px high, the grid gives the legend no room: with the mode on, `grid-viewport`, `room-topbar`, `clue-bar` and `keyboard` have the boxes they have with the mode off (1 px); the legend's bottom is 8 px above `grid-viewport`'s bottom (1 px), its horizontal centre is within 1 px of `grid-viewport`'s, and its box lies inside `grid-viewport`'s; it has the computed `z-index` `6`, `pointer-events` `none`, and AC-7's background, border and radius; `document.elementFromPoint` at the centre of its box returns an element inside the `grid`; and its box overlaps none of `room-topbar`, `clue-bar` and `keyboard`. (Note from the lead, 2026-10-23: the 568 by 320 run is added for the rule of "The grid's room" on a grid that would fall under 100 px; the criterion ended at "and does not overlap the `grid`'s box.")
- **AC-9** (new; refines spec 019 AC-4) (browser with mocked socket; static) The clue bar shows only the clue. On the snapshot of AC-3 with the mode on, at 1280 by 720 and at 568 by 320 in the touch context: after a tap on (1, 1), `clue-bar` holds no `clue-bar-author` and `clue-bar-text` has the text content `Passoire fine`; the same after a tap on (1, 2) and with the mode off. Static: no file under `web/src` contains `clue-bar-author` or `author-mark`.
- **AC-10** (new; refines spec 019 AC-5) (browser with mocked socket) The mode keeps the room page's guarantees at every window size. With spec 043's `H8` (spec 013 AC-6's setup: FX-01, `you` host among 8 players, 100 line events, (3, 1) tapped) with letters by four of the players and the mode on, at each window size of spec 006 AC-5, in desktop and touch contexts: spec 013 AC-6's checks pass (`grid-viewport` at least 100 px high, no page scroll, the grid inside the viewport at zoom 1, `clue-bar` inside the window and, in the touch context, at or above the top of `keyboard`); `authors-legend` lies inside the window, is at most as wide as `clue-bar` (0.5 px), has its horizontal centre within 1 px of the centre of `grid-area`'s content box, and its box overlaps none of `room-topbar`, `clue-bar`, `grid-status` (when shown), `keyboard` (touch) and `salon` (when open). The test notes, with the mode off, `grid-viewport`'s box and its height `V`, and with the mode on the legend's height `h`. When `grid-viewport` is less high than with the mode off (the grid gave the legend its room; in the sheet layout by `R = max(38, h + 8)` (1 px), in the column layout by 35 px or more, as AC-8 allows, the box being the grid's rounded to whole cells), the legend's top is 8 px below the `grid`'s bottom (1 px) and its box does not overlap the `grid`'s; when `grid-viewport` keeps its box of the mode off (1 px) (the legend lies over the grid), the legend's bottom is 8 px above `grid-viewport`'s bottom (1 px). (Note from the lead, 2026-10-23: the first case read "less high ... by `R = max(38, h + 8)` (1 px)" in every layout, which cannot hold in the column layout, where `grid-viewport` is the grid's box rounded to whole cells.) (Note from the lead, 2026-10-23: the two cases are told apart by `grid-viewport`'s height, not by the legend's position; this read "When the legend's top is at or below `grid-viewport`'s bottom (the grid gave it its room), ... otherwise (it lies over the grid), `grid-viewport` has its box of the mode off". In the sheet layout on portrait windows (360 by 740, 320 by 568, 768 by 1024) the grid is centred in a `grid-viewport` taller than itself, so with the room given the legend, 8 px under the grid, lies inside the viewport's box, and the old test called it "over the grid".) In the sheet layout, the legend lies over the grid exactly when `V - max(38, h + 8)` is under 100; at 568 by 320 in the touch context it does. On a FX-02 snapshot at 568 by 320 in the desktop context with the mode on, the same checks hold. On a FX-02 snapshot with 8 players whose nicknames have 20 characters each, at 568 by 320 and at 740 by 360 in the desktop context (column layout, Salon open), with the mode on, the same checks hold (`grid-viewport` at least 100 px high among them), and `clue-bar` has the width it has with the mode off (0.5 px). (Note from the lead, 2026-10-23: refined for the rule of "The grid's room" on a grid that would fall under 100 px and for the legend's width; this read "`authors-legend` lies inside the window and inside `grid-area`, its top 8 px below the `grid`'s bottom (1 px), and its box overlaps neither the `grid`'s nor `clue-bar`'s. On a FX-02 snapshot at 568 by 320 in the desktop context with the mode on, the same checks hold.")
- **AC-11** (new) (browser with mocked socket; static) The mode passes spec 035's scans, and `fr.json` holds its keys. With the mode on, at 1280 by 720 and at 360 by 740, on `EIGHT` with `p2` selecting (3, 2) `down`, (1, 3) locked by a check, (2, 3) a pencil letter, (4, 4) holding `X` by `p1` with `wrong` true, and after a tap on (1, 0): spec 035's contrast scan (its AC-8) finds no offending element (every ink reaches 4.5:1 on white, word blue, selected blue, locked grey and every other player's tint), and its language scan (its AC-9, with the nicknames and the clue texts as test data) finds no offending element. Static: `web/src/i18n/fr.json` holds `authors.legend` with the value `Auteurs :`, still holds `authors.switch`, `authors.on` and `authors.off`, and has no key `authors.selected`.

## Edge cases and errors

- Pending letter (AC-3): a letter I type shows at once (spec 015) in the ink of the
  cell's confirmed author, or in ink on an empty cell, and takes my ink when the
  server's `letter_changed` confirms it, as spec 019's band did.
- Undo (AC-3): the letter put back by an undo is the undoer's (spec 018 decision
  5), so it takes the undoer's ink.
- A player who left and a newcomer with the same colour index (AC-3): the letters
  of the player who left are ink, so they never show in the newcomer's ink; a
  player seated back (spec 032) keeps their id, so their letters are theirs again,
  in the ink of the colour they come back with.
- A removed player (AC-3): as a player who left.
- Flash (AC-5): the letter keeps its finder's ink over the flash overlay; its
  contrast on the white-and-colour composite is not guaranteed (`_design.md`
  section 7 and section 15), for the flash's 1,000 ms. The scans of AC-11 are run
  outside a flash for that reason.
- Two finders with close inks (AC-6): the legend is the key; with five players or
  more the Joueurs list of the Salon is the reference for who plays (`_design.md`
  section 3). Nothing on the grid names a letter's author in words (Open question
  1).
- A long legend (AC-8, AC-10): it wraps, never wider than the clue bar, and the
  grid gives it the room of each further line, so it never covers the grid or the
  clue bar, unless that room would leave `grid-viewport` under 100 px high.
- A low window (AC-8, AC-10): where the room would leave `grid-viewport` under
  100 px high (568 by 320 with the keyboard shown, or a long legend on a low
  desktop window), the legend lies over the grid's bottom, which the player can
  still tap through it; hiding the keyboard (spec 044) gives the room back. (Note
  from the lead, 2026-10-23: this item is new, and the item above read "A long
  legend (AC-8): it wraps, and the grid gives it the room of each further line, so
  it never covers the grid or the clue bar.")
- A solved grid (AC-1): the mode keeps working, so the group can look at who wrote
  what at the end (spec 019).
- The Accessibilité mode (AC-6): it changes the player marks (spec 042), not the
  inks; the legend names players in their ink with no dot and no icon, in both
  modes (`_design.md` section 6, "Elsewhere").
- `localStorage` that throws (AC-1): the mode starts off at each load and flips for
  the page's life.
- The mode is per browser: other players' views do not change.

## Out of scope

- A filter that shows one player's letters only; initials or patterns on cells.
- Naming the author of a letter in words on the grid, in the clue bar or for a
  screen reader (Open question 1).
- Remembering the mode on an account or across devices.
- Contrast of the inks on a flash (`_design.md` section 15).
- The recap dialog: its look, its player marks (dot, icon, the slot of a player
  who left), its states and its « Lien copié » line (spec 047); the shared recap
  page (spec 048).
- Any server change: authorship is spec 019's (AC-3 there).

## Work packages

None: one pull request.

## Decisions

Decided by the human on 2026-10-16 (`_design.md` section 7), and by the lead on
2026-10-22 on the human's instruction (`_design.md` section 15): the Auteurs mode
replaces the band; each letter in its finder's ink; a revealed letter and a letter
whose finder left in plain ink, with no departed grey; the strike in ink; pencil
italics kept; the legend under the grid with its 38 px; the clue bar without
« Lettre de … »; the mode off by default and remembered per browser.

Proposed by the spec writer, each already part of the spec above:

1. `data-author-colour` stays, with spec 019's meaning, as the test hook of the
   inks, so the tests that read it follow with the least change; `author-mark` goes.
2. The finder is spec 019's confirmed author restricted to the players of the kept
   snapshot, so a letter's ink never belongs to a newcomer who took a departed
   player's colour index.
3. The legend lists every player of the kept snapshot (present or disconnected) in
   join order, as the Joueurs list does, and is `aria-hidden`: it maps colours to
   names, which only the eye uses.
4. The legend's room is `max(38, h + 8)` px: 38 px as drawn for one line, and the
   room of every further line when eight long names wrap (Open question 2), so the
   legend never covers the grid or the clue bar. (Note from the lead, 2026-10-23:
   except where that room would leave `grid-viewport` under 100 px high; see
   decision 8.)
5. The recap's player marks, which spec 042's report left to step 5, are spec
   047's, with the recap's look; this spec leaves the recap as it is, so spec 028's
   hatching (and the custom property it reads) stays until spec 047 replaces it.

Decided by the human on 2026-10-22, with the spec's approval (these were the Open
questions, answered with their recommended answer; the text above already follows
them). The number in brackets is the question's number, which the text above cites:

6. (Open question 1.) A sign of authorship that does not rely on colour. Spec 019's
   « Lettre de … » in the clue bar was that sign (spec 035's rule that colour is
   never the only signal); `_design.md` section 7 removes it. Options: (a) follow
   the design, the legend being the only key, and the Accessibilité mode changing
   nothing for the inks; (b) keep « Lettre de … » in the clue bar while both
   « Auteurs » and « Accessibilité » are on; (c) put the author's name in the
   grid's screen-reader announcement (spec 035) in every mode. Answer: (a), the
   design the human decided on 2026-10-16; (b) brings back spec 019's low-window
   rules, and (c) is a new feature for players who do not see the inks.
7. (Open question 2.) A legend that does not fit on one line (eight long nicknames
   on a phone). Options: (a) it wraps and the grid gives it each further line; (b)
   one line, clipped, the names past the edge not shown; (c) one line that scrolls
   sideways. Answer: (a); (b) hides players silently and (c) adds a scrolling
   region with its keyboard rules (spec 035 AC-12). The screens sheet draws one
   line only.

Decided by the lead on 2026-10-23, after the implementation found two layout
conflicts (the text above follows them, each change with its dated note):

8. Where giving the legend its room would leave `grid-viewport` under 100 px high
   (spec 013 AC-6's floor), in either layout, the legend takes no room and lies
   over the bottom of `grid-viewport`, on layer 6, with its own background and
   `pointer-events: none`; nothing else moves. At 568 by 320 with the keyboard
   shown the room left 68 px, and the top bar, the clue bar, the status and the
   keyboard may not give any; the player gets the room back by hiding the keyboard.
9. The legend is never wider than `clue-bar`'s width (nor, in the sheet layout,
   than `grid-area`'s content box), a width that does not change with the mode. It
   was "never wider than `grid-area`'s content box", which in the column layout is
   the grid's box: a wrapping legend narrowed the grid, which made it wrap more,
   until the grid collapsed (FX-02, 8 players with 20-character nicknames, at 568
   by 320 and 740 by 360 on a desktop).
10. The implementer's decisions, recorded: in the column layout the clue bar's
    width comes from the grid's box without the legend's room (spec 043 Decision
    12 would make it narrower with the mode on); wrapped legend lines are 2 px
    apart and items 8 px apart on a line; the space under the grid is rounded down
    to a quarter pixel when the legend is placed (at most 0.25 px); the legend is
    centred on `grid-area`'s content box, the grid's centre at zoom 1, and stays
    centred on the viewport when the grid is zoomed.

## Open questions

None left (all answered with the approval of 2026-10-22).
</content>
</invoke>
