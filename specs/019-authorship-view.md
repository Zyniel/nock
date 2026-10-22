---
id: "019"
title: Authorship view
status: done
---

# 019 - Authorship view

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.) (Note from the lead, 2026-10-15: done. The human's answers are decisions 6 to 8 below, and "Open questions" says "None.")

(Note from the lead, 2026-10-15: refined after the review of spec 019 with the lead's decisions 9 to 14 below. AC-1 and AC-4 changed, so the test-writer updates their tests before the implementer runs (review of spec 019).) (Note from the lead, 2026-10-15: AC-1's box run changed again, with a fourth page at 296 by 640 (296 by 568 gave 18.28 px cells, limited by the height), so the test-writer updates its test before the implementer runs (second review of spec 019).)

(Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells (`_design.md` section 6): the other players' cursors are corner triangles with no labels, so the band's "Drawing order" rule and AC-1's drawing-order check change, and the test-writer updates that check before the implementer runs. The band itself, the switch and the other criteria do not change until step 5 brings the Auteurs mode of `_design.md` section 7.)

(Note from the lead, 2026-10-22: refined by spec 043, the design's room layout (`_design.md` section 8): `authors-switch` is the first item of the room Menu (« Auteurs », with the detail « activé » or « désactivé »), still off at each page load until step 5; `clue-bar-author` stays in the navy clue bar, after the clue text, in white, with the shrinking rules of AC-4; the new layout's cells at 296 by 640 on FX-02 are about 21.5 px. "Client: the authors switch", AC-1's fourth page (283 by 640 in place of 296 by 640), AC-4's in-row checks and AC-5 change, so the test-writer updates their tests before the implementer runs. The other criteria do not change; a test that clicks the switch opens the Menu first (spec 043's "Test harness").)

(Note from the lead, 2026-10-22: refined by spec 045, the design's Auteurs mode (`_design.md` section 7): the band at the bottom of each cell is gone, with its colour, hatching, box, baseline, drawing-order and contrast rules; while the switch is on each letter is drawn in its finder's ink (`--player-ink-N`), a letter with no finder (empty, revealed, or by a player who is not in the kept snapshot) in plain ink, and a legend under the grid names each player in their ink; the clue bar's `clue-bar-author` goes; the switch is remembered per browser (`nock.authors`). "Client: the authors switch", "Client: the view, switch on", "Client: the author in words", "New `fr.json` keys", "Test harness", AC-1, AC-2, AC-3 (its browser part only), AC-4, AC-5, the edge cases and "Out of scope" change, so the test-writer updates the tests of AC-1, AC-2, AC-3's browser part, AC-4 and AC-5 before spec 045's implementer runs. AC-3's rule and WebSocket parts (the server keeps authors) do not change.)

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
  (`false` or `true`) and the text `t("authors.switch")`, the first item of spec
  043's room Menu (`room-menu`), with its detail. (Note from the lead, 2026-10-22:
  refined by spec 043; this read "last in spec 024's `room-toolbar`".) It starts
  from `localStorage["nock.authors"]` (`"true"` gives `true`, any other value or
  none `false`), and each click flips it and writes `"true"` or `"false"` there.
  (Note from the lead, 2026-10-22: refined by spec 045; this read "It is `false` at
  each page load, and each click flips it".) It is
  never disabled (the view is useful on a solved grid too) and sends nothing.
  (Note from the lead, 2026-10-15: "sends nothing" leaves aside the heartbeat
  `ping` frames of spec 017, which the page may send at any time once the socket
  is open.)

### Client: the view, switch on

(Note from the lead, 2026-10-22: refined by spec 045, the design's Auteurs mode.
This section described `author-mark`, a band in the author's colour along the
bottom of each filled cell: its colour, the hatching of a departed author's band,
its 3:1 contrast in every state of the cell, its box rules, its baseline probe, its
drawing order and its visibility. The band is gone; the section now reads as
follows, and spec 045's "The letters while the mode is on" gives the whole rule.)

On each letter `cell` (spec 006):

- `data-author-colour`: the colour index (`0` to `7`) of the cell's finder (spec
  045: the confirmed author of a letter that is not revealed, when that author is a
  player of the kept snapshot); `""` when the cell has no finder (empty, revealed,
  or written by a player who left the room, spec 017, was removed, spec 014, or was
  never known to the page);
- the cell's computed `color`, which its letter inherits, is the finder's ink
  `var(--player-ink-N)` (spec 041), and `--nock-ink` when it has no finder, on every
  background of the cell; a pencil letter keeps its italics in that ink, a locked
  letter its weight, and the strike of a wrong letter turns `--nock-ink`;
- nothing else of the cell changes (spec 042's background, marks and drawing
  order).

Every other cell (clue or empty type) has `data-author-colour=""`. No cell holds an
`author-mark`.

The inks follow the confirmed grid, within 300 ms of each event the page applies:
a `letter_changed` (spec 015) gives the cell the new author's ink, or no letter for
an erase; a `cell_locked` with `revealed` true leaves the cell with no finder (spec
016 clears the author); a `player_left` turns that player's letters to plain ink; a
`player_joined` of a new player changes no letter, since letters keep the ids of
their authors, and a player seated back (spec 032) is the finder of their letters
again. (Note from the lead, 2026-10-22: refined by spec 045; this paragraph read
"The marks follow the confirmed grid", with the mark's colour in place of the
ink.)

While the switch is on, a legend under the grid (`authors-legend`, spec 045) names
each player of the kept snapshot in their ink, in join order. (Note from the lead,
2026-10-22: added by spec 045.)

### Client: the view, switch off

No `authors-legend` exists, and every cell has `data-author-colour=""`. (Note from
the lead, 2026-10-22: refined by spec 045; this read "No `author-mark` exists".) A
letter's look does not depend on its author: two letter cells in the same state (pencil
flag of spec 020, lock, selection and word highlight, other players' word tints,
wrong mark, flash) but with different authors have the same computed `color`,
`background-color`, `font-style` and `font-weight`. Spec 016's flash, which shows
for 1 second the colour of a player who replaced my letter, is not the authors
view and is unchanged.

### Client: the author in words

(Note from the lead, 2026-10-22: refined by spec 045, the design's Auteurs mode.
This section described `clue-bar-author`, the line « Lettre de {name} » that the
clue bar showed after the clue for the selected cell's author while the switch was
on, with its rules of following the cell (decision 12) and of shrinking first on a
low window (decision 11). The design's clue bar shows only the clue (`_design.md`
section 7), so the line and its rules are gone. The section now reads as follows.)

The names in words are the legend's: while the switch is on, `authors-legend`
(spec 045) names every player of the kept snapshot, each in their ink, so a player
reads which ink is whose. The clue bar holds no `clue-bar-author`, and
`clue-bar-text` keeps its text exactly (spec 007). Nothing on the grid names the
author of one letter in words (spec 045's Open question 1).

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `authors.switch` | `Auteurs` |
| `authors.legend` | `Auteurs :` |

(Note from the lead, 2026-10-22: refined by spec 045; the key `authors.selected`
(`Lettre de {name}`) is removed and `authors.legend` added.)

### Test harness

- Rule unit tests and WebSocket tests: specs 011 and 018 (`new_room`,
  `join_room`, `handle_message`, `replay`, `RoomStore`; spec 018 AC-1's simulated
  restart).
- "Browser with mocked socket" and "browser with live server": as spec 023;
  snapshots built with `grid_view(fx01_grid)` (or FX-02) and `model_copy`.
- Colours: a letter cell's computed `color` against the colour of a probe `span`
  whose style is `color: var(--player-ink-N)`, appended to `body` (setup), as spec
  041 reads a token; plain ink is rgb(20, 24, 31). (Note from the lead, 2026-10-22:
  refined by spec 045; this item compared a mark's computed `background-color` with
  that of a `roster-colour` swatch, and a second item read a band's colours for its
  contrast run, which is gone.)
- Window sizes and contexts: as spec 024 (the eight sizes of spec 006 AC-5, desktop
  and touch contexts).
- Engines: every browser criterion runs in Chromium and WebKit locally and also
  Firefox in CI. No check of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-5.1.1) (browser with mocked socket; browser with live server) An "authors" switch draws each filled cell's letter in the ink of the last player who edited it. Mocked: given a FX-01 snapshot with players `p1` (`you`, `Ana`, colour 0) and `p2` (`Bob`, colour 3), where (1, 0) holds `T` by `p1`, (1, 1) `A` by `p2`, (1, 2) `M` by `p9` (not in the room), (1, 3) `I` locked by a check with author `p2`, and (1, 4) `S` revealed (no author): after a click on `authors-switch`, which then has `aria-pressed="true"`, (1, 0) has `data-author-colour="0"` and the computed `color` of `--player-ink-0`; (1, 1) and (1, 3) have `data-author-colour="3"` and the colour of `--player-ink-3` ((1, 3) still in `font-weight` 700); (1, 2) and (1, 4) have `data-author-colour=""` and the colour rgb(20, 24, 31); no cell holds an `author-mark`. Then, within 300 ms of each event: after `letter_changed` (seq 6) at (1, 0) letter `X` from `p2`, (1, 0) has `data-author-colour="3"` and the ink of colour 3; after `letter_changed` (seq 7) erasing (1, 1), (1, 1) has `data-author-colour=""`; after `cell_locked` (seq 8) at (1, 0) letter `T` with `revealed` true, (1, 0) has `data-author-colour=""` and plain ink; after `player_left` (seq 9) of `p2`, (1, 3) has `data-author-colour=""` and plain ink. Live: two pages join one FX-01 room as `Ana` and `Bob`; Ana types `T` at (1, 0), Bob types `A` at (1, 1); Ana clicks `authors-switch`; on Ana's page, (1, 0) has the ink of Ana's colour index and (1, 1) the ink of Bob's, each index read from that player's `roster-player` `data-colour`. (Note from the lead, 2026-10-22: refined by spec 045, the design's Auteurs mode. This criterion checked an `author-mark` band per filled cell: its colour against the author's `roster-colour`, the hatching of a departed author's band, the band's box rules on four pages (FX-01 at 1280 by 720, FX-02 at 320 by 568, 568 by 320 and 283 by 640), its drawing order under the corner triangles and its 3:1 contrast in every cell state and flash; the band and those runs are gone, and spec 045 AC-2 to AC-5 check the inks in detail.)
- **AC-2** (AC-5.1.2) (browser with mocked socket) With the switch off, all letters share one neutral colour. Given the snapshot of AC-1: `authors-switch` starts with `aria-pressed="false"`; no `author-mark` exists and every cell has `data-author-colour=""`, and there is no `authors-legend`; with nothing selected, (1, 0) (by `p1`), (1, 1) (by `p2`) and (1, 2) (by `p9`), none of them locked or wrong and none in another player's word, have the same computed `color` (rgb(20, 24, 31)), `background-color`, `font-style` and `font-weight`. After switching the view on and then off again, the same holds. After a page reload, the switch keeps the state it had (`localStorage["nock.authors"]`): off after it was turned off, on after it was turned on. (Note from the lead, 2026-10-22: refined by spec 045, the design's Auteurs mode; this read "no `author-mark` exists" and "After a page reload, the switch is off again".)
- **AC-3** (AC-5.1.3) (rule unit test; WebSocket; browser with live server) Authorship survives reconnection and is kept for the recap (spec 028, backlog US-7.2). Rule: in a FX-01 room, the entries of a play by `p1` and `p2` (letters, one letter written over another player's, an erase, an undo, a check that locks a cell, a reveal) replayed in order from `new_room` give each cell the same `author` as the live state: a cell locked by a check keeps its author, a revealed cell has `author=None`, and the letter put back by an undo has the undoer as author (spec 018); `p1`, disconnected then resumed with its token (`join_room`, spec 017), keeps its id, and its cells keep `author="p1"`; after `p1` times out and leaves (spec 017), its cells keep `author="p1"`; the room saved in a `RoomStore` and loaded again (spec 018) has the same authors. The recap itself is spec 028's, built from these authors; this spec checks only that they are kept. WebSocket: A (`Ana`) types `T` at (1, 0) and B (`Bob`) types `A` at (1, 1); A's socket closes and A joins again with its resume token: A's snapshot holds (1, 0) with `author` equal to A's id and (1, 1) with B's, and A's player view keeps colour 0; after a simulated restart (spec 018 AC-1's harness), B's new snapshot holds the same two authors. Browser: two pages join one FX-01 room as `Ana` and `Bob`; Ana types `T` at (1, 0) and Bob types `A` at (1, 1); Ana's page is reloaded (spec 017 decision 7), reaches `data-status="joined"`, and with its switch on (it stays on across the reload, spec 045), (1, 0) has the ink of Ana's colour index and (1, 1) the ink of Bob's, as before the reload. (Note from the lead, 2026-10-22: refined by spec 045; this read "once its switch is on again, (1, 0)'s mark has the colour of Ana's `roster-colour` and (1, 1)'s the colour of Bob's".)
- **AC-4** (new) (browser with mocked socket) The view names the players in words, each in their ink, and the clue bar keeps only the clue. Given the snapshot of AC-1 with the switch on: `authors-legend` shows under the grid, holding `authors-legend-label` (`fr.json["authors.legend"]`) then two `authors-legend-name` reading `Ana` and `Bob`, in that order, each with the computed `color` of its player's ink (`--player-ink-0`, `--player-ink-3`); tapping (1, 1) shows no `clue-bar-author`, and `clue-bar-text` reads `Passoire fine`; after `player_left` (seq 6) of `p2`, the legend reads `Ana` only; switching the view off removes the legend. With a FX-02 snapshot whose letter cells are all filled by `p2`, whose nickname has 20 characters, at every window size of spec 006 AC-5, in desktop and touch contexts, spec 013 AC-6's checks pass with the switch on, and at 568 by 320 and 740 by 360 `clue-bar`'s height with the switch on equals its height with the switch off (1 px). (Note from the lead, 2026-10-22: refined by spec 045, the design's Auteurs mode. This criterion checked `clue-bar-author` (« Lettre de … ») for the selected cell, its following of the cell's events and pending edits, and its shrinking rules in the clue bar's row on a low window with spec 026's `FX02_FULL_WRONG` page; the line is gone, and spec 045 AC-6 to AC-9 check the legend. The text that follows is kept for its history and is not tested.) The line followed the cell, in a separate run on the snapshot of AC-1 in the desktop context with the switch on and (1, 0) tapped (`Lettre de Ana`), each check within 300 ms of its event: after `letter_changed` (seq 6) at (1, 0) letter `X` from `p2`, `clue-bar-author` reads `Lettre de Bob`; after `letter_changed` (seq 7) erasing (1, 0) from `p2`, it is absent; after `letter_changed` (seq 8) at (1, 0) letter `T` from `p2`, it reads `Lettre de Bob`; after `cell_locked` (seq 9) at (1, 0) letter `T` with `revealed` true, it is absent. Then the test taps (1, 1) (`Lettre de Bob`), presses `z`, which the page sends as `edit_letter` and shows as a pending letter, and taps (1, 1) again (spec 009 may have moved the selection): 500 ms after that tap, with no answer from the mock, it still reads `Lettre de Bob`; after `letter_changed` (seq 10) at (1, 1) letter `Z` from `p1`, it reads `Lettre de Ana`. (Note from the lead, 2026-10-15: added, decision 12 (review of spec 019).) With a FX-02 snapshot whose letter cells are all filled by `p2`, whose nickname has 20 characters, and the first cell of the word with FX-02's longest clue selected: at every window size of spec 006 AC-5, in desktop and touch contexts, spec 013 AC-6's checks pass with the switch on; and at 568 by 320 and 740 by 360, `clue-bar`'s height with the switch on equals its height with the switch off (1 px tolerance). That FX-02 page is spec 026's `FX02_FULL_WRONG` page (its players, feed items and tap of `On la glisse dans une enveloppe`, which selects (1, 6)) with `p2`'s nickname 20 characters long, so `grid-status` shows with `data-state="full_wrong"`. (Note from the lead, 2026-10-15: added, so that the status is in the row (review of spec 019).) At 568 by 320 and 740 by 360, in the touch context (spec 043's sheet layout, where `grid-status` sits in the clue bar's row), with the switch on: `clue-bar-text`, `clue-bar-author` and `grid-status` lie inside `clue-bar`'s box, in this order from left to right (each one's left edge at or right of the right edge of the one before), with vertical ranges that overlap pairwise; `clue-bar-author` has the computed `white-space` `nowrap`, `overflow` `hidden` and `text-overflow` `ellipsis`; with M the smaller of its `scrollWidth` and 6 times its computed `font-size`, its `clientWidth` is at least M; either `clue-bar-text` shows its whole text (`scrollWidth <= clientWidth + 1`) or the `clientWidth` of `clue-bar-author` is at most M; `grid-status` shows its whole text (the same measure); and `clue-bar-text` still has the text `On la glisse dans une enveloppe`. Each comparison has 1 px of tolerance. (Note from the lead, 2026-10-15: added. The clue text has priority over the author line, which shortens first, down to M; decision 11 (review of spec 019).) (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout: the in-row checks read "in both contexts"; in the desktop context these two windows are spec 043's column layout, where `grid-status` sits under the clue bar, and there `clue-bar-text` and `clue-bar-author` lie inside `clue-bar`'s box, in this order, on one line, with the same `clue-bar-author` rules.)
- **AC-5** (new) (browser with mocked socket) The authors switch meets spec 035 and keeps the grid's room. Setup: spec 013 AC-6's (FX-01, `you` host among 8 players, 100 feed items, (3, 1) tapped), with letters by four of the players and the switch on. At every window size of spec 006 AC-5, in desktop and touch contexts, spec 013 AC-6's checks pass, `authors-switch` is the first item of `room-menu`, and, with the Menu open, spec 043 AC-28's checks hold for it (inside the window; `elementFromPoint` at its centre returns it). In a separate run at 1280 by 720, keyboard only with no tap (spec 035's harness): `tab_to` `menu-button` and `Enter` open the Menu with the focus on `authors-switch`, then `Enter` turns it on (`aria-pressed="true"`) and `Enter` again off, with spec 035 AC-2's outline. (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout; this read "`authors-switch` is in `room-toolbar` after `reveal-panel`, and spec 024 AC-8's toolbar rules hold for it (one row on small windows; with the keyboard focus, inside the toolbar's client area and an outline that is not clipped; `elementFromPoint` at its centre after `scrollIntoView`)" and "`tab_to` `authors-switch`".) With the switch on, at 1280 by 720 and 360 by 740, spec 035's contrast scan and language scan find no offending element, and `authors-legend` lies inside the window and does not overlap the `grid` or `clue-bar` at every window size above. (Note from the lead, 2026-10-22: refined by spec 045, the design's Auteurs mode: the legend's check was added; the checks now run on the inks and the legend, the band being gone.)

## Edge cases and errors

(Note from the lead, 2026-10-22: refined by spec 045, the design's Auteurs mode: in
the items below, a "mark" or "band" reads the letter's ink, the "hatched grey
mark" of a player who left reads plain ink, the corner labels and the overlap rules
no longer apply, and the clue bar names no author; spec 045's "Edge cases and
errors" holds the current rules.)

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
- Remembering the switch across devices; a filter that shows one player's letters
  only. (Note from the lead, 2026-10-22: refined by spec 045; this read "across
  reloads or devices": the switch is now remembered per browser.)
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
    568, 568 by 320 and 296 by 640. Cells can be under 20 px at 568 by 320, so
    the small-cell rule is tested too, and they measure 20 to 21 px at 296 by 640
    (the test asserts it), the range closest to the letter rule's limit. (Note
    from the lead, 2026-10-15: added (review of spec 019).) (Note from the lead,
    2026-10-15: the 296 by 640 page was added, since no other page has cells of 20
    to 21 px; 296 by 568 gave 18.28 px cells, limited by the height (second
    review of spec 019).)

## Open questions

None.
