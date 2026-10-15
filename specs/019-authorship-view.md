---
id: "019"
title: Authorship view
status: approved
---

# 019 - Authorship view

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.) (Note from the lead, 2026-10-15: done. The human's answers are decisions 6 to 8 below, and "Open questions" says "None.")

(Note from the lead, 2026-10-15: refined after the review of spec 019 with the lead's decisions 9 to 14 below. AC-1 and AC-4 changed, so the test-writer updates their tests before the implementer runs (review of spec 019).)

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
  (Note from the lead, 2026-10-15: "sends nothing" leaves aside the heartbeat
  `ping` frames of spec 017, which the page may send at any time once the socket
  is open.)

### Client: the view, switch on

On each letter `cell` (spec 006) whose confirmed cell has a letter and an author:

- `data-author-colour`: the author's colour index (`0` to `7`) when the author is a
  player of the kept snapshot; `""` when they are not (they left the room, spec
  017, or were removed, spec 014);
- one child `data-testid="author-mark"`, with `data-colour` (the same value),
  `aria-hidden="true"` and no text: a band in the author's colour along the bottom
  of the cell.
  - Its computed `background-color` equals the computed `background-color` of the
    author's `roster-colour` swatch (spec 012), in every state of the cell. (Note
    from the lead, 2026-10-15: "in every state of the cell" was added. The band's
    main colour never changes; its contrast comes from its other colours, decision
    9 (review of spec 019).)
  - With `data-colour=""` it is hatched, never a plain colour: its computed
    `background-image` is a `repeating-linear-gradient` whose line is diagonal (an
    angle that is not a whole multiple of 90 degrees, or a corner keyword such as
    `to top right`) and whose colour stops hold at least two different colours.
    Each of its colours (as "Contrast" below lists them) is a grey: its red, green
    and blue channels are within 8 of each other, so none is a player colour. No
    player's band has a pattern: with `data-colour` `0` to `7`, the computed
    `background-image` of `author-mark` and of each of its layers is `none`. So a
    departed author's band differs from every player's band by its pattern, not by
    its colour. (Note from the lead, 2026-10-15: this item replaces the sentence
    "With `data-colour=""` it is a neutral grey that is none of the eight player
    colours". That grey, `#737885`, has almost the lightness of red, olive and
    teal, so many colour-blind players saw it as the teal band; decision 10 (review
    of spec 019).)
  - Contrast: the band keeps a contrast of at least 3:1 against the cell's
    computed `background-color` in every state of the cell: not selected;
    selected; in my selected word (spec 007); in another player's word, tinted in
    their colour (spec 013); locked by a check (spec 016's locked grey); struck
    through by a check (spec 023); and flashing in any of the eight player colours
    (spec 016), whatever the band's own colour. A revealed cell has no author, so
    it has no band to check. (Note from the lead, 2026-10-15: added. With spec
    012's palette, the bands of colours 1 and 3 had under 3:1 on every cell
    background, the grey band under 3:1 on some word tints, and on a flashing cell
    the band vanished, since the flash is in the new author's colour; decision 9
    (review of spec 019).)
  - The band's contrast is measured over its colours, as spec 024 measures its
    corner mark. Its colours are the computed `background-color` of `author-mark`
    and the colour stops of its computed `background-image`, and the same for each
    layer inside it (element descendants, or its `::before` and `::after`
    pseudo-elements whose computed `content` is not `none`) that is at least half
    the cell side wide and at least 1 px high (bounding box for an element,
    computed `width` and `height` for a pseudo-element). A colour with alpha 0 does
    not count; every other colour of the band is opaque. The band's contrast is the
    highest contrast of its colours against the cell's computed
    `background-color`. A colour counts only where it shows: an edge shows at least
    1 px of its colour along the whole length of the band, above it and below it,
    and each stripe of a hatched band is at least 1 px wide (the reviewer checks
    this; the tests read the colours). (Note from the lead, 2026-10-15: added,
    decision 9 (review of spec 019).)
  - How the band keeps 3:1 is the implementer's choice, for example an edge in a
    colour that contrasts with every background, or one that changes with the
    cell's state. The ink colour alone has under 3:1 on the flash colours 2 and 4
    (spec 024 decision 14), and white alone on the light backgrounds. The band's
    main colour stays the author's swatch colour (first item), and the flash keeps
    its colour and its 1,000 ms (spec 016). (Note from the lead, 2026-10-15: added,
    decision 9 (review of spec 019).)
  - On a cell whose side is 20 px or more: its box lies inside the cell's box
    shrunk by 3 px on every side, so the selected cell's outline (spec 035 AC-2)
    never covers it; its bottom edge is between 3 and 6 px above the cell's bottom
    edge; it is at least half the cell side wide, and at least 3 px and at least a
    tenth of the cell side high. On a smaller cell (a large grid on a small window)
    it only has to lie inside the cell's box and below the letter's baseline (next
    item); the player can zoom in (spec 006), as spec 035 says of its labels.
    (Note from the lead, 2026-10-15: "and below the letter's baseline (next item)"
    was added, decision 13 (review of spec 019).)
  - At every cell size, the band never overlaps the letter: its top is at or below
    the letter's baseline (1 px tolerance). The letters are capitals, with no ink
    below the baseline. Measure: right after the text node holding the cell's
    shown letter (the letter of `data-letter`), the test inserts a probe, an empty
    `span` with `display: inline-block`, `width` and `height` 0 and
    `vertical-align: baseline`; the probe's top is the baseline. The probe must
    share the letter's line: when the text node's parent is a flex or grid
    container (the cell is a flex container today), an element beside the text
    would be an item of its own, so the test first wraps the text node in a `span`
    and puts the probe in that `span`. The probe changes nothing the test
    measures: the bounding box of a DOM `Range` over the text node moves by at
    most 0.5 px when the probe is inserted. The current layout is expected to meet
    this rule, to be confirmed by the tests; an estimate with common font metrics
    puts cells of 20 to about 23 px closest to the limit. (Note from the lead,
    2026-10-15: added, decision 13. The rule first measured the bottom of the
    letter's `Range` box, which includes the font's descent, and now measures the
    baseline, so that small cells need no smaller letters (review of spec 019).)
  - Drawing order: the band is drawn above the `remote-selection` outlines of
    other players (spec 013), whatever their inset, so no outline crosses it. Only
    the corner labels of spec 035 AC-11 (`remote-initials`, `remote-overflow`) are
    drawn over it, where they meet it, from its ends inward; nothing else covers
    it. (Note from the lead, 2026-10-15: added. The band was drawn under the
    outlines, and their bottom sides crossed it; decision 13 (review of spec 019).)
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

The line follows the selected cell's confirmed author within 300 ms of each event
the page applies, as the bands do: after a `letter_changed` on that cell it names
the event's player, and after an erase of that cell or a `cell_locked` on it with
`revealed` true it is absent. The page's own pending edit on the selected cell
(spec 015) does not change it; the line changes when the server's
`letter_changed` confirms the edit, as AC-1's bands follow confirmed letters only.
(Note from the lead, 2026-10-15: added, decision 12 (review of spec 019).)

It sits on the line of the clue text when there is room, and may end with an
ellipsis. At 568 by 320 and 740 by 360, where the height is tight, the clue bar is
no taller with it than without it (1 px tolerance); at every size, spec 013 AC-6's
guarantees and spec 009 AC-4 keep holding.

On a window at most 500 px high (`window.innerHeight <= 500`, as in spec 026's
"Where `grid-status` sits"), `clue-bar-author` sits in `clue-bar`'s row, after
`clue-bar-text` and before `grid-status` when the status is there, on one line
(computed `white-space` `nowrap`, `overflow` `hidden` and `text-overflow`
`ellipsis`); `clue-bar-text` is then one line too, cut at its end with an
ellipsis, as spec 026 says for the status. The clue text has priority over the
author: `clue-bar-author` shortens first, and `clue-bar-text` shortens only once
`clue-bar-author` is down to its minimum width. That minimum is the smaller of the
width of its whole text (its `scrollWidth`) and 6 times its computed `font-size`,
about the width of `Lettre de `, one character and the ellipsis;
`clue-bar-author` is never narrower. `grid-status` keeps its whole text (spec
026), and the bar is never higher with the author than without it (spec 026
AC-10's rule). (Note from the lead, 2026-10-15: added. On low windows the clue
text and the author shrank together, so the clue text lost about half its room to
the author; decision 11 (review of spec 019).)

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
- Contrast (AC-1): WCAG 2.x ratios, computed as spec 035's contrast scan does; a
  band's colours are read as "The view, switch on" says, with the colour stops
  parsed from the computed `background-image`. (Note from the lead, 2026-10-15:
  added (review of spec 019).)
- Window sizes and contexts: as spec 024 (the eight sizes of spec 006 AC-5, desktop
  and touch contexts).
- Engines: every browser criterion runs in Chromium and WebKit locally and also
  Firefox in CI. No check of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-5.1.1) (browser with mocked socket; browser with live server) An "authors" switch tints each filled cell with the colour of the last player who edited it. Mocked: given a FX-01 snapshot with players `p1` (`you`, `Ana`, colour 0) and `p2` (`Bob`, colour 3), where (1, 0) holds `T` by `p1`, (1, 1) `A` by `p2`, (1, 2) `M` by `p9` (not in the room), (1, 3) `I` locked by a check with author `p2`, and (1, 4) `S` revealed (no author): after a click on `authors-switch`, which then has `aria-pressed="true"`, (1, 0) holds one `author-mark` with `data-colour="0"` whose background colour equals the background colour of `p1`'s `roster-colour`; (1, 1) and (1, 3) each hold one with `data-colour="3"` equal to `p2`'s swatch; (1, 2) holds one with `data-colour=""`, hatched as "The view, switch on" says (its computed `background-image` a diagonal `repeating-linear-gradient` whose colours, like all the band's colours, are greys), while the computed `background-image` of the marks of (1, 0), (1, 1) and (1, 3) and of their layers is `none` (Note from the lead, 2026-10-15: this said "whose background colour is none of the eight player colours"; the departed band is now hatched, decision 10 (review of spec 019)); (1, 4) and every empty letter cell hold none; each mark meets the box rules of "The view, switch on". Then, within 300 ms of each event: after `letter_changed` (seq 6) at (1, 0) letter `X` from `p2`, (1, 0)'s mark has `data-colour="3"`; after `letter_changed` (seq 7) erasing (1, 1), (1, 1) holds no mark; after `cell_locked` (seq 8) at (1, 0) letter `T` with `revealed` true, (1, 0) holds no mark; after `player_left` (seq 9) of `p2`, (1, 3)'s mark has `data-colour=""` and is hatched. (Note from the lead, 2026-10-15: "and is hatched" was added, decision 10 (review of spec 019).) Live: two pages join one FX-01 room as `Ana` and `Bob`; Ana types `T` at (1, 0), Bob types `A` at (1, 1); Ana clicks `authors-switch`; on Ana's page, (1, 0)'s mark has the background colour of Ana's `roster-colour` and (1, 1)'s that of Bob's. Box run, in the desktop context, on three mocked pages: the snapshot above with `p3` to `p6` added (colours 1, 2, 4 and 5) and `p2` to `p6` selecting (1, 0) `across`, at the default window (1280 by 720); and, at 320 by 568 and at 568 by 320, a FX-02 snapshot built as spec 026's `FX02_FULL_WRONG` (players `p1` to `p8`, every letter cell `E` by `p2`), without its feed items or tap, whose letter cells of row 1 are by `p9` instead and where `p2` to `p6` select (1, 6) `down`; the selections are given in the snapshot (spec 013). On each page, with the switch on, every `author-mark` meets the box rules of "The view, switch on" (inside the cell, distance from the cell's bottom edge, width, height, and top at or below the letter's baseline, measured with the probe that rule describes), each held to the rule of its own cell's side as measured on the page; FX-02's cells are under 20 px at 568 by 320 (spec 035 AC-11), so the small-cell rule is tested there. (Note from the lead, 2026-10-15: added; the box rules were checked at the default window only, decisions 13 and 14. The letter check measures the baseline, not the bottom of the letter's `Range` box (review of spec 019).) On each of these pages the drawing order also holds on the cell with the five outlines (spec 035 AC-11 gives it its labels): after `scrollIntoView` of that cell, a test style sets `pointer-events: auto !important` on every descendant of every `cell`, since hit testing follows the drawing order but skips elements with `pointer-events: none`; then `document.elementFromPoint`, at points of the band's middle line (half its height below its top), every 2 px from 1 px inside its left end to 1 px inside its right end, returns, at a point more than 1 px inside the box of a `remote-initials` or `remote-overflow` element, that label or one of its descendants, and at a point more than 1 px outside every such box, `author-mark` or one of its descendants, never a `remote-selection` or any other element. (Note from the lead, 2026-10-15: added, decision 13 (review of spec 019).) Contrast run, at 1280 by 720 in the desktop context, with the switch on, on FX-01 snapshots (`seq` 10) where `you` is `p1` (colour 0) and `p2` to `p8` have colours 1 to 7. There are nine bands: those of colours 0 to 7, by `p1` and by `p2` to `p8`, and the departed band, by `p9`. In each state below, the test reads in one `page.evaluate` the cell's computed `background-color` and the band's colours, and the band's contrast, measured over its colours as "The view, switch on" says, is at least 3:1. Static states, on one page per band whose letter cells all hold letters by the band's author, with (4, 4) locked by a check (`locked` true, `revealed` false) and (3, 3) struck through (`wrong` true), nothing selected: (0, 1) not selected, (4, 4) locked and (3, 3) struck through; after a tap on (1, 0), (1, 0) selected and (1, 1) in my word; then, for each colour k from 1 to 7 in turn, (2, 2) after a `selection_moved` of the player with colour k to (2, 2) `across` (tinted in colour k), followed by a `selection_moved` of that player to `null`. Flash states, on one page per flash colour f from 0 to 7, whose cells (1, 0) to (1, 4) and (2, 1) to (2, 4) hold `X` by `p1`, nothing selected, one cell per band: on each cell the mock sends, back to back with consecutive seqs from 11, a `letter_changed` with letter `Y` from the player other than `p1` whose colour is f (for f = 0, `p9`, whom spec 016 flashes in colour 0), which starts the flash, then, unless that player is the band's author, a `letter_changed` with letter `Z` from the band's author, which keeps the flash, since the letter it replaces is not mine (spec 016). Once each of the nine cells has its band's author in `data-author`, the test reads in one `page.evaluate`, for each cell, `data-flash`, which is still f; the computed `background-color`, which equals the computed background colour of the `roster-colour` of the player with colour f (`p1`'s for f = 0), as in spec 016 AC-2; and the band's colours. (Note from the lead, 2026-10-15: added, decision 9 (review of spec 019).)
- **AC-2** (AC-5.1.2) (browser with mocked socket) With the switch off, all letters share one neutral colour. Given the snapshot of AC-1: `authors-switch` starts with `aria-pressed="false"`; no `author-mark` exists and every cell has `data-author-colour=""`; with nothing selected, (1, 0) (by `p1`), (1, 1) (by `p2`) and (1, 2) (by `p9`), none of them locked or wrong and none in another player's word, have the same computed `color`, `background-color`, `font-style` and `font-weight`. After switching the view on and then off again, the same holds. After a page reload, the switch is off again.
- **AC-3** (AC-5.1.3) (rule unit test; WebSocket; browser with live server) Authorship survives reconnection and is kept for the recap (spec 028, backlog US-7.2). Rule: in a FX-01 room, the entries of a play by `p1` and `p2` (letters, one letter written over another player's, an erase, an undo, a check that locks a cell, a reveal) replayed in order from `new_room` give each cell the same `author` as the live state: a cell locked by a check keeps its author, a revealed cell has `author=None`, and the letter put back by an undo has the undoer as author (spec 018); `p1`, disconnected then resumed with its token (`join_room`, spec 017), keeps its id, and its cells keep `author="p1"`; after `p1` times out and leaves (spec 017), its cells keep `author="p1"`; the room saved in a `RoomStore` and loaded again (spec 018) has the same authors. The recap itself is spec 028's, built from these authors; this spec checks only that they are kept. WebSocket: A (`Ana`) types `T` at (1, 0) and B (`Bob`) types `A` at (1, 1); A's socket closes and A joins again with its resume token: A's snapshot holds (1, 0) with `author` equal to A's id and (1, 1) with B's, and A's player view keeps colour 0; after a simulated restart (spec 018 AC-1's harness), B's new snapshot holds the same two authors. Browser: two pages join one FX-01 room as `Ana` and `Bob`; Ana types `T` at (1, 0) and Bob types `A` at (1, 1); Ana's page is reloaded (spec 017 decision 7), reaches `data-status="joined"`, and once its switch is on again, (1, 0)'s mark has the colour of Ana's `roster-colour` and (1, 1)'s the colour of Bob's, as before the reload.
- **AC-4** (new) (browser with mocked socket) The view names the author of the selected letter in words, so colour is not the only signal (spec 035 AC-6). Given the snapshot of AC-1 with the switch on: tapping (1, 1) shows `clue-bar-author` with the text `Lettre de Bob` (built from `fr.json["authors.selected"]`) while `clue-bar-text` still reads `Passoire fine`; after `player_left` (seq 6) of `p2`, tapping (1, 3) still shows `Lettre de Bob`; tapping (1, 4) (revealed) or (2, 1) (empty) shows no `clue-bar-author`; switching the view off removes it. The line follows the cell, in a separate run on the snapshot of AC-1 in the desktop context with the switch on and (1, 0) tapped (`Lettre de Ana`), each check within 300 ms of its event: after `letter_changed` (seq 6) at (1, 0) letter `X` from `p2`, `clue-bar-author` reads `Lettre de Bob`; after `letter_changed` (seq 7) erasing (1, 0) from `p2`, it is absent; after `letter_changed` (seq 8) at (1, 0) letter `T` from `p2`, it reads `Lettre de Bob`; after `cell_locked` (seq 9) at (1, 0) letter `T` with `revealed` true, it is absent. Then the test taps (1, 1) (`Lettre de Bob`), presses `z`, which the page sends as `edit_letter` and shows as a pending letter, and taps (1, 1) again (spec 009 may have moved the selection): 500 ms after that tap, with no answer from the mock, it still reads `Lettre de Bob`; after `letter_changed` (seq 10) at (1, 1) letter `Z` from `p1`, it reads `Lettre de Ana`. (Note from the lead, 2026-10-15: added, decision 12 (review of spec 019).) With a FX-02 snapshot whose letter cells are all filled by `p2`, whose nickname has 20 characters, and the first cell of the word with FX-02's longest clue selected: at every window size of spec 006 AC-5, in desktop and touch contexts, spec 013 AC-6's checks pass with the switch on; and at 568 by 320 and 740 by 360, `clue-bar`'s height with the switch on equals its height with the switch off (1 px tolerance). That FX-02 page is spec 026's `FX02_FULL_WRONG` page (its players, feed items and tap of `On la glisse dans une enveloppe`, which selects (1, 6)) with `p2`'s nickname 20 characters long, so `grid-status` shows with `data-state="full_wrong"`. (Note from the lead, 2026-10-15: added, so that the status is in the row (review of spec 019).) At 568 by 320 and 740 by 360, in both contexts, with the switch on: `clue-bar-text`, `clue-bar-author` and `grid-status` lie inside `clue-bar`'s box, in this order from left to right (each one's left edge at or right of the right edge of the one before), with vertical ranges that overlap pairwise; `clue-bar-author` has the computed `white-space` `nowrap`, `overflow` `hidden` and `text-overflow` `ellipsis`; with M the smaller of its `scrollWidth` and 6 times its computed `font-size`, its `clientWidth` is at least M; either `clue-bar-text` shows its whole text (`scrollWidth <= clientWidth + 1`) or the `clientWidth` of `clue-bar-author` is at most M; `grid-status` shows its whole text (the same measure); and `clue-bar-text` still has the text `On la glisse dans une enveloppe`. Each comparison has 1 px of tolerance. (Note from the lead, 2026-10-15: added. The clue text has priority over the author line, which shortens first, down to M; decision 11 (review of spec 019).)
- **AC-5** (new) (browser with mocked socket) The authors switch meets spec 035 and keeps the grid's room. Setup: spec 013 AC-6's (FX-01, `you` host among 8 players, 100 feed items, (3, 1) tapped), with letters by four of the players and the switch on. At every window size of spec 006 AC-5, in desktop and touch contexts, spec 013 AC-6's checks pass, `authors-switch` is in `room-toolbar` after `reveal-panel`, and spec 024 AC-8's toolbar rules hold for it (one row on small windows; with the keyboard focus, inside the toolbar's client area and an outline that is not clipped; `elementFromPoint` at its centre after `scrollIntoView`). In a separate run at 1280 by 720, keyboard only with no tap (spec 035's harness): `tab_to` `authors-switch`, then `Enter` turns it on (`aria-pressed="true"`) and `Enter` again off, with spec 035 AC-2's outline. With the switch on, at 1280 by 720 and 360 by 740, spec 035's contrast scan and language scan find no offending element.

## Edge cases and errors

- AC-3 depends on behaviour owned by spec 028; test only this spec's side of it here.
- A player who left (AC-1, AC-4): their letters keep their id as author (spec 017),
  get the hatched grey mark, and are still named in the clue bar. (Note from the
  lead, 2026-10-15: "the neutral mark" became "the hatched grey mark", decision 10
  (review of spec 019).) A new player may take
  their colour index (spec 012), so the departed player's letters never show in a
  newcomer's colour (decision 2).
- A removed player (AC-1): the same as a player who left.
- A resumed player (AC-3): same id, same colour, so their letters keep their mark.
- Pending edits (AC-1, AC-4): a letter I typed shows its mark in my colour once the
  server confirms it (spec 015), not before, and the clue bar names me as its
  author only then. (Note from the lead, 2026-10-15: AC-4 and the clue bar were
  added, decision 12 (review of spec 019).)
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
  the flash, spec 016; the locked grey, spec 016); it replaces none of them. On
  each of them it keeps 3:1 (AC-1's contrast run). (Note from the lead,
  2026-10-15: added, decision 9 (review of spec 019).)
- Crowded cells (AC-1, AC-5): the corner labels of spec 035 AC-11 are drawn over
  the band where they meet it, from its ends inward; on a cell under 44 px the
  bottom-right label can reach past the band's middle. Other players' outlines
  never cross it. (Note from the lead, 2026-10-15: this item said "may cover the
  ends of the band; its middle stays visible". From 20 to 35 px a label keeps
  its 7 px font and is about 15 px wide, so it can pass the middle; the
  outlines rule is decision 13 (review of spec 019).)
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
  selected cell's author). The hatching of a departed author's band is one
  pattern shared by every player who left, not a pattern per author. (Note from
  the lead, 2026-10-15: added with decision 10 (review of spec 019).)
- Showing the author of a letter before the server confirms it.

## Work packages

None.

## Decisions

Proposed in the Phase 6 refine of 2026-10-14 and approved by the human with the
spec. Each one is already part of the spec above. Items 1 to 3 were also open
questions: the human's answers to them are items 6 to 8 below.

1. The tint is a band along the bottom of the cell, not the cell's whole
   background. The background already shows my selection and word (spec 007),
   other players' word tints in their colours (spec 013), the flash in a player's
   colour (spec 016) and the locked grey (spec 016); a background tint would look
   like spec 013's word tint, and would hide or be hidden by the others.
2. Letters of a player who is no longer in the room get a neutral band: their
   colour index may now belong to someone else. That band is now hatched in greys
   (decision 10). (Note from the lead, 2026-10-15: the last sentence was added
   (review of spec 019).)
3. The selected cell's author is named in the clue bar, the way to tell authors
   apart that does not rely on colour; spec 035 decision 6 relies on text in the
   same way for word tints.
4. No server change: authorship is already kept, sent, resumed and replayed; AC-3
   pins it with tests.
5. The switch starts off at each page load and acts on this page only.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question. Each one is already part of the spec above.

6. How the author is shown ("tints each filled cell", former open question 1).
   Options: a band in the author's colour along the bottom of the cell; or the
   whole background of the cell in the author's colour, which while the switch is
   on would replace spec 013's word tints and the own-word highlight of spec 007 on
   filled cells. Pick: the band (decision 1).
7. Letters of a player who left the room (former open question 2). Options: a
   neutral band; or the colour they had, which a new player may now have. Pick: the
   neutral band (decision 2).
8. The non-colour signal (former open question 3). Options: the selected cell's
   author named in the clue bar; the author's initials on every cell, which collide
   with the corner labels of spec 035 AC-11 on small cells; or the name next to the
   switch in the toolbar, which may be scrolled out of view on small windows. Pick:
   the clue bar (decision 3).

Decided by the lead on 2026-10-15 after the review, under the owner's delegation
of accessibility choices. Each one is already part of the spec above. (Note from
the lead, 2026-10-15: this group was added (review of spec 019).)

9. Band contrast. With spec 012's palette, the bands of colours 1 (green) and 3
   (orange) had under 3:1 on every cell background (about 2.7:1 and 2.6:1 on
   white), the neutral band had under 3:1 on some word tints, and on a cell that
   flashes because another player wrote over my letter (spec 016) the band
   vanished, since the flash is in the new author's colour, which is the band's.
   Pick: the band keeps at least 3:1 against the cell's background in every state
   of the cell (not selected, selected, in my word, in another player's word,
   locked, struck through by a check, flashing in each of the eight colours; a
   revealed cell has no band), measured over its colours as spec 024's corner mark
   is (layers and an edge count, and the best colour counts). A contrasting edge
   thus passes while the band's main colour stays exactly the author's swatch
   colour. (Note from the lead, 2026-10-15: added (review of spec 019).)
10. Departed authors. The neutral grey `#737885` has almost the lightness of red,
    olive and teal, so for many colour-blind players it looked like the teal band.
    Pick: a departed author's band is hatched (diagonal stripes of two greys, or of
    a grey and white), never a plain colour, and no player's band has a pattern, so
    it differs from every player's band by its pattern, not by its colour. Its
    colours are greys, each with its three channels within 8 of each other. (Note
    from the lead, 2026-10-15: added (review of spec 019).)
11. Low windows. On windows at most 500 px high the author line shares the clue
    bar's row with the clue text and `grid-status`, and the clue text and the
    author shrank together, so the clue text lost about half its room. Pick: the
    clue text has priority. `clue-bar-author` shortens first, down to a minimum of
    6 times its font size (or its whole text when narrower), about `Lettre de `,
    one character and the ellipsis; only then does the clue text shorten. The bar
    is still never higher (spec 026 AC-10). (Note from the lead, 2026-10-15: added
    (review of spec 019).)
12. The author line follows the cell. It follows the selected cell's confirmed
    author within 300 ms, as the bands do: a letter written over it by another
    player names that player, an erase or a reveal removes the line, and the
    page's own pending edit changes it only once the server confirms it. (Note
    from the lead, 2026-10-15: added (review of spec 019).)
13. Drawing order and the letter. The band is drawn above other players' outlines
    (spec 013), whose bottom sides crossed it, and below the corner labels of spec
    035 AC-11, which alone may cover it, from its ends inward. At every cell size,
    cells under 20 px included, the band's top is at or below the letter's
    baseline (1 px tolerance), measured with a zero-size `inline-block` probe
    aligned on the baseline right after the letter's text node. The letters are
    capitals, with no ink below the baseline, so the font's descent does not
    count, and small cells need no smaller letters. (Note from the lead,
    2026-10-15: added; the baseline replaced the bottom of the letter's `Range` box
    after the coordinator's review (review of spec 019).)
14. Box rules at several sizes. AC-1 checks the band's box rules, the letter rule
    and the drawing order on FX-01 at the default window and on FX-02 at 320 by
    568 and 568 by 320, where cells can be under 20 px, so the small-cell rule is
    tested too. (Note from the lead, 2026-10-15: added (review of spec 019).)

## Open questions

None.
