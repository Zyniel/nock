---
id: "019"
title: Authorship view
status: approved
---

# 019 - Authorship view

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

Epic E5 Collaboration aids (US-5.1) · Release: V1 · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The grid
elements are those of spec 006, the selection and the clue bar spec 007, the
in-app keyboard spec 009, players, colours and the roster spec 012, word tints,
remote selections, known names and the layout guarantees of spec 013 AC-6 spec
013, edits and `data-author` spec 015, locks and the flash spec 016, resume and
time-out spec 017, the log, `replay` and undo spec 018, checks spec 023, reveals
and the room toolbar spec 024, the recap spec 028, accessibility spec 035, the
messages spec 039 (`LetterChanged.player_id`, `LetterCellView.author`). Built after
specs 024 and 025.

## Goal

As a player, I want to see who wrote each letter, so that I know whom to ask about a doubtful answer.

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking.

## Public interface

No new Python name, no new protocol message and no server change. The room
already keeps the author of every letter (`CellState.author`, spec 011) and sends
it (`LetterChanged.player_id`, `LetterCellView.author`, spec 039); a resumed
player keeps their id (spec 017); `replay` restores authors (spec 018). This spec
pins that behaviour with tests (AC-3) and adds the authors view to the room page.

### Who is the author of a letter

The author of a letter cell is the player of its last `letter_changed` (spec 015),
so an undo makes the undoer the author (spec 018 decision 5) and a confirmation of
a pencil letter makes the confirmer the author (spec 020). An empty cell and a
revealed cell have no author (spec 024); a cell locked by a check keeps its author
(spec 023). The page uses the confirmed author, `data-author` of spec 015, never a
pending edit.

### Client: the authors switch

- `data-testid="authors-switch"`: a `<button type="button">` with `aria-pressed`
  (`false` or `true`) and the text `t("authors.switch")`, last in spec 024's
  `room-toolbar`. It is `false` at each page load, and each click flips it. It is
  never disabled (the view is useful on a solved grid too) and sends nothing.

### Client: the view, switch on

On each letter `cell` (spec 006) whose confirmed cell has a letter and an author:

- `data-author-colour`: the author's colour index (`0` to `7`) when the author is a
  player of the kept snapshot; `""` when they are not (they left the room, spec
  017, or were removed, spec 014);
- one child `data-testid="author-mark"`, with `data-colour` (the same value),
  `aria-hidden="true"` and no text: a band in the author's colour along the bottom
  of the cell.
  - Its computed `background-color` equals the computed `background-color` of the
    author's `roster-colour` swatch (spec 012). With `data-colour=""` it is a
    neutral grey that is none of the eight player colours.
  - On a cell whose side is 20 px or more: its box lies inside the cell's box
    shrunk by 3 px on every side, so the selected cell's outline (spec 035 AC-2)
    never covers it; its bottom edge is between 3 and 6 px above the cell's bottom
    edge; it is at least half the cell side wide, and at least 3 px and at least a
    tenth of the cell side high. On a smaller cell (a large grid on a small window)
    it only has to lie inside the cell's box; the player can zoom in (spec 006), as
    spec 035 says of its labels.
  - Its computed `visibility` is `visible`.

Every other cell (empty, revealed, clue or empty type) holds no `author-mark` and
has `data-author-colour=""`.

The marks follow the confirmed grid, within 300 ms of each event the page applies:
a `letter_changed` (spec 015) gives the mark the new author's colour, or removes
it for an erase; a `cell_locked` with `revealed` true removes it (spec 016 clears
the author); a `player_left` turns that player's marks to `data-colour=""`; a
`player_joined` of a new player changes no mark, since letters keep the ids of
their authors.

### Client: the view, switch off

No `author-mark` exists, and every cell has `data-author-colour=""`. A letter's
look does not depend on its author: two letter cells in the same state (pencil
flag of spec 020, lock, selection and word highlight, other players' word tints,
wrong mark, flash) but with different authors have the same computed `color`,
`background-color`, `font-style` and `font-weight`. Spec 016's flash, which shows
for 1 second the colour of a player who replaced my letter, is not the authors
view and is unchanged.

### Client: the author in words

While the switch is on and the selected cell's confirmed letter has an author,
`clue-bar` (spec 007) holds `data-testid="clue-bar-author"` after `clue-bar-text`,
with the text `t("authors.selected", { name })`, where `name` is the author's
nickname from spec 013's known names (so a player who left is still named), or
`t("feed.someone")` when unknown, inserted as text (spec 037 AC-4). It is absent
while the switch is off, while nothing is selected, and while the selected cell is
empty or revealed. `clue-bar-text` keeps its text exactly (spec 007).

It sits on the line of the clue text when there is room, and may end with an
ellipsis. At 568 by 320 and 740 by 360, where the height is tight, the clue bar is
no taller with it than without it (1 px tolerance); at every size, spec 013 AC-6's
guarantees and spec 009 AC-4 keep holding.

This text is the way to tell authors apart that does not rely on colour (spec 035
AC-6): a player who cannot tell two colours apart selects a cell and reads who
wrote it.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `authors.switch` | `Auteurs` |
| `authors.selected` | `Lettre de {name}` |

### Test harness

- Rule unit tests and WebSocket tests: specs 011 and 018 (`new_room`,
  `join_room`, `handle_message`, `replay`, `RoomStore`; spec 018 AC-1's simulated
  restart).
- "Browser with mocked socket" and "browser with live server": as spec 023;
  snapshots built with `grid_view(fx01_grid)` (or FX-02) and `model_copy`.
- Colours are compared as spec 016 AC-2 does for the flash: the computed
  `background-color` of a mark against the computed `background-color` of a
  `roster-colour` swatch; the eight player colours are read from the page's
  `--player-colour-0` to `--player-colour-7`.
- Window sizes and contexts: as spec 024 (the eight sizes of spec 006 AC-5, desktop
  and touch contexts).
- Engines: every browser criterion runs in Chromium and WebKit locally and also
  Firefox in CI. No check of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-5.1.1) (browser with mocked socket; browser with live server) An "authors" switch tints each filled cell with the colour of the last player who edited it. Mocked: given a FX-01 snapshot with players `p1` (`you`, `Ana`, colour 0) and `p2` (`Bob`, colour 3), where (1, 0) holds `T` by `p1`, (1, 1) `A` by `p2`, (1, 2) `M` by `p9` (not in the room), (1, 3) `I` locked by a check with author `p2`, and (1, 4) `S` revealed (no author): after a click on `authors-switch`, which then has `aria-pressed="true"`, (1, 0) holds one `author-mark` with `data-colour="0"` whose background colour equals the background colour of `p1`'s `roster-colour`; (1, 1) and (1, 3) each hold one with `data-colour="3"` equal to `p2`'s swatch; (1, 2) holds one with `data-colour=""` whose background colour is none of the eight player colours; (1, 4) and every empty letter cell hold none; each mark meets the box rules of "The view, switch on". Then, within 300 ms of each event: after `letter_changed` (seq 6) at (1, 0) letter `X` from `p2`, (1, 0)'s mark has `data-colour="3"`; after `letter_changed` (seq 7) erasing (1, 1), (1, 1) holds no mark; after `cell_locked` (seq 8) at (1, 0) letter `T` with `revealed` true, (1, 0) holds no mark; after `player_left` (seq 9) of `p2`, (1, 3)'s mark has `data-colour=""`. Live: two pages join one FX-01 room as `Ana` and `Bob`; Ana types `T` at (1, 0), Bob types `A` at (1, 1); Ana clicks `authors-switch`; on Ana's page, (1, 0)'s mark has the background colour of Ana's `roster-colour` and (1, 1)'s that of Bob's.
- **AC-2** (AC-5.1.2) (browser with mocked socket) With the switch off, all letters share one neutral colour. Given the snapshot of AC-1: `authors-switch` starts with `aria-pressed="false"`; no `author-mark` exists and every cell has `data-author-colour=""`; with nothing selected, (1, 0) (by `p1`), (1, 1) (by `p2`) and (1, 2) (by `p9`), none of them locked or wrong and none in another player's word, have the same computed `color`, `background-color`, `font-style` and `font-weight`. After switching the view on and then off again, the same holds. After a page reload, the switch is off again.
- **AC-3** (AC-5.1.3) (rule unit test; WebSocket; browser with live server) Authorship survives reconnection and is kept for the recap (spec 028, backlog US-7.2). Rule: in a FX-01 room, the entries of a play by `p1` and `p2` (letters, one letter written over another player's, an erase, an undo, a check that locks a cell, a reveal) replayed in order from `new_room` give each cell the same `author` as the live state: a cell locked by a check keeps its author, a revealed cell has `author=None`, and the letter put back by an undo has the undoer as author (spec 018); `p1`, disconnected then resumed with its token (`join_room`, spec 017), keeps its id, and its cells keep `author="p1"`; after `p1` times out and leaves (spec 017), its cells keep `author="p1"`; the room saved in a `RoomStore` and loaded again (spec 018) has the same authors. The recap itself is spec 028's, built from these authors; this spec checks only that they are kept. WebSocket: A (`Ana`) types `T` at (1, 0) and B (`Bob`) types `A` at (1, 1); A's socket closes and A joins again with its resume token: A's snapshot holds (1, 0) with `author` equal to A's id and (1, 1) with B's, and A's player view keeps colour 0; after a simulated restart (spec 018 AC-1's harness), B's new snapshot holds the same two authors. Browser: two pages join one FX-01 room as `Ana` and `Bob`; Ana types `T` at (1, 0) and Bob types `A` at (1, 1); Ana's page is reloaded (spec 017 decision 7), reaches `data-status="joined"`, and once its switch is on again, (1, 0)'s mark has the colour of Ana's `roster-colour` and (1, 1)'s the colour of Bob's, as before the reload.
- **AC-4** (new) (browser with mocked socket) The view names the author of the selected letter in words, so colour is not the only signal (spec 035 AC-6). Given the snapshot of AC-1 with the switch on: tapping (1, 1) shows `clue-bar-author` with the text `Lettre de Bob` (built from `fr.json["authors.selected"]`) while `clue-bar-text` still reads `Passoire fine`; after `player_left` (seq 6) of `p2`, tapping (1, 3) still shows `Lettre de Bob`; tapping (1, 4) (revealed) or (2, 1) (empty) shows no `clue-bar-author`; switching the view off removes it. With a FX-02 snapshot whose letter cells are all filled by `p2`, whose nickname has 20 characters, and the first cell of the word with FX-02's longest clue selected: at every window size of spec 006 AC-5, in desktop and touch contexts, spec 013 AC-6's checks pass with the switch on; and at 568 by 320 and 740 by 360, `clue-bar`'s height with the switch on equals its height with the switch off (1 px tolerance).
- **AC-5** (new) (browser with mocked socket) The authors switch meets spec 035 and keeps the grid's room. Setup: spec 013 AC-6's (FX-01, `you` host among 8 players, 100 feed items, (3, 1) tapped), with letters by four of the players and the switch on. At every window size of spec 006 AC-5, in desktop and touch contexts, spec 013 AC-6's checks pass, `authors-switch` is in `room-toolbar` after `reveal-panel`, and spec 024 AC-8's toolbar rules hold for it (one row on small windows; with the keyboard focus, inside the toolbar's client area and an outline that is not clipped; `elementFromPoint` at its centre after `scrollIntoView`). In a separate run at 1280 by 720, keyboard only with no tap (spec 035's harness): `tab_to` `authors-switch`, then `Enter` turns it on (`aria-pressed="true"`) and `Enter` again off, with spec 035 AC-2's outline. With the switch on, at 1280 by 720 and 360 by 740, spec 035's contrast scan and language scan find no offending element.

## Edge cases and errors

- AC-3 depends on behaviour owned by spec 028; test only this spec's side of it here.
- A player who left (AC-1, AC-4): their letters keep their id as author (spec 017),
  get the neutral mark, and are still named in the clue bar. A new player may take
  their colour index (spec 012), so the departed player's letters never show in a
  newcomer's colour (decision 2).
- A removed player (AC-1): the same as a player who left.
- A resumed player (AC-3): same id, same colour, so their letters keep their mark.
- Pending edits (AC-1): a letter I typed shows its mark in my colour once the server
  confirms it (spec 015), not before.
- Undo (AC-3): the restored letter is authored by the undoer (spec 018 decision 5),
  so its mark takes the undoer's colour.
- Checks (AC-1): a cell locked by a check keeps its author and its mark, and its
  bold letter (spec 035 AC-7).
- Reveals (AC-1): no author and no mark; the reveal's corner mark (spec 024) is at
  the top right and the band at the bottom, so they never meet.
- Pencil letters (spec 020): a pencil letter has an author and a mark like any
  letter; a confirmation gives it the confirmer's colour.
- Backgrounds (AC-1, AC-2): the band is drawn over the cell's background, whatever
  it shows (my selection and word, spec 007; other players' word tints, spec 013;
  the flash, spec 016; the locked grey, spec 016); it replaces none of them.
- Crowded cells (AC-5): the corner labels of spec 035 AC-11 may cover the ends of
  the band; its middle stays visible.
- `data-author` (spec 015) keeps its meaning, switch on or off.
- The switch is per page: other players' views do not change, and a reload turns it
  off (AC-2).
- Solved grid (AC-1): the switch keeps working, so the group can look at who wrote
  what once the grid is solved.

## Out of scope

- Voice and video (epic E5).
- Pencil letters: spec 020.
- Clue flag: spec 021.
- Chat and reactions: spec 022.
- The recap and its credits: spec 028.
- Remembering the switch across reloads or devices; a filter that shows one
  player's letters only.
- Initials or patterns on every cell for the authors (the clue bar names the
  selected cell's author).
- Showing the author of a letter before the server confirms it.

## Work packages

None.

## Decisions

Proposed in the Phase 6 refine of 2026-10-14, for the human's re-approval. Each one
is already part of the spec above; items 1 to 3 are also open questions.

1. The tint is a band along the bottom of the cell, not the cell's whole
   background. The background already shows my selection and word (spec 007),
   other players' word tints in their colours (spec 013), the flash in a player's
   colour (spec 016) and the locked grey (spec 016); a background tint would look
   like spec 013's word tint, and would hide or be hidden by the others.
2. Letters of a player who is no longer in the room get a neutral band: their
   colour index may now belong to someone else.
3. The selected cell's author is named in the clue bar, the way to tell authors
   apart that does not rely on colour; spec 035 decision 6 relies on text in the
   same way for word tints.
4. No server change: authorship is already kept, sent, resumed and replayed; AC-3
   pins it with tests.
5. The switch starts off at each page load and acts on this page only.

## Open questions

1. "Tints each filled cell": options (a) a band in the author's colour along the
   bottom of the cell (the spec as written); (b) the whole background of the cell
   in the author's colour, which while the switch is on would replace spec 013's
   word tints and the own-word highlight of spec 007 on filled cells. Pick: (a).
2. Letters of a player who left the room. Options: (a) a neutral band (the spec as
   written); (b) the colour they had, which a new player may now have. Pick: (a).
3. The non-colour signal. Options: (a) the selected cell's author named in the
   clue bar (the spec as written); (b) the author's initials on every cell, which
   collide with the corner labels of spec 035 AC-11 on small cells; (c) the name
   next to the switch in the toolbar, which may be scrolled out of view on small
   windows. Pick: (a).
