---
id: "007"
title: Word selection and direction
status: done
---

# 007 - Word selection and direction

Epic E2 Solo solving (US-2.2) · Release: MVP · Epic depends on: E1
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The room
page and grid elements are those of specs 040 and 006; the messages are those of
spec 039.

## Goal

As a player, I want to pick a word with one tap, so that I always know which clue I am answering.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

No new Python name and no new protocol message. Client only.

### Words, as the client computes them

- A word is named by its clue, `row,column,clue_index` of the clue cell (spec 039
  `ClueRef`). Its cells are resolved from the snapshot's `GridView` with the rule of
  spec 002 (`Grid.word_cells`): the start cell and direction come from the arrow,
  and the word runs to the next non-letter cell or the grid edge.
- A word's direction is `across` (arrows `right`, `down_then_right`) or `down`
  (arrows `down`, `right_then_down`).
- A letter cell's word in a direction is the word of that direction that holds the
  cell. If several do, the one whose first cell comes first in the direction (the
  longest).
- A cell is filled when its `letter` is not null (locked cells are filled).
- On FX-01: (1, 1) is in W1 `0,0,0` across and W2 `0,0,1` down; (0, 1) (N) only in
  W2; (1, 0) (T) only in W1.

### Selection

The selection is one letter cell and a direction such that the cell has a word in
that direction; the selected word is that word. At start nothing is selected.

- Tap (click) on a letter cell that is not selected: it becomes the selected cell.
  Direction: the current direction if the cell has a word in it, otherwise the
  cell's other direction. With no current direction (first tap), `across` if the
  cell has an across word, otherwise `down`.
- Tap on the selected cell: if it has words in both directions, the direction
  switches; otherwise nothing changes.
- Tap on a `clue` element (one half of a two-clue cell, or the whole of a one-clue
  cell): its word becomes the selected word, with the word's direction, on the
  word's first cell that is not filled, or its first cell when all are filled.
- Tap on an empty cell, on a `clue-separator` or outside the grid: nothing changes.
- Selecting a cell gives keyboard focus to the `grid` element (`tabindex="0"`), for
  specs 008 and 009.

### Observable attributes

On `data-testid="grid"` (spec 006):

| Attribute | Value |
| --- | --- |
| `data-selected-row`, `data-selected-column` | decimal, `""` when nothing is selected |
| `data-direction` | `across`, `down`, or `""` |
| `data-word` | the selected word as `row,column,clue_index` (for example `0,0,1`), or `""` |

On each letter `cell`: `data-selected` (`true` only on the selected cell) and
`data-in-word` (`true` on every cell of the selected word, the selected cell
included), otherwise `false`. On each `clue` element: `data-active` (`true` only on
the selected word's clue).

Highlights are visible: the computed `background-color` of the selected cell, of
the other cells of the selected word, and of the letter cells outside it are three
different colours; an active `clue` has a `background-color` different from an
inactive one.

### Clue bar

`data-testid="clue-bar"`, outside the scrolling `grid-viewport`, always within the
window (fixed or sticky at the bottom of the room page), shown once the grid is
shown. It has `data-word` (same value as on the grid) and holds
`data-testid="clue-bar-text"`, whose text is the selected word's clue text, or
`t("clue_bar.empty")` when nothing is selected. The computed `font-size` of
`clue-bar-text` is 14 px or more. Its `aria-label` is `t("clue_bar.label")`.

Spec 009 places the in-app keyboard below the bar (spec 009 AC-4).

### Messages sent

Each time the selection changes (cell or direction), the page sends one
`{"type": "select_cell", "row": r, "column": c, "direction": "across"|"down"}`
(spec 039 `SelectCell`), if the socket is open. A tap that changes nothing sends
nothing.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `clue_bar.label` | `Définition en cours` |
| `clue_bar.empty` | `Touchez une case ou une définition.` |

### Test harness

- "Browser with mocked socket": spec 040's mock on `/r/ABC123`, sending a FX-01
  snapshot (`grid_view(fx01_grid)`, cells replaced with `model_copy` where letters
  are needed). A tap is `locator.click()` on the cell or `clue` element; one test of
  AC-1 uses `locator.tap()` in a context with `has_touch=True`.
- The mock records every frame the page sends; tests parse them with
  `parse_client_message`.
- Phone window for AC-4: 360 by 640, `has_touch=True`, `is_mobile=True`; under
  Firefox, where Playwright does not support `is_mobile`, the context leaves it
  out (as spec 006).
- Engines: every criterion runs in Chromium, Firefox and WebKit
  (`specs/_architecture.md`). No check of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-2.2.1) (browser with mocked socket) Tapping a letter cell selects it and highlights its whole word and that word's clue. On an empty FX-01 grid, tapping (2, 2) gives the grid `data-selected-row="2"`, `data-selected-column="2"`, `data-direction="across"`, `data-word="2,0,0"` (VIDE); (2, 2) has `data-selected="true"`; exactly (2, 1), (2, 2), (2, 3), (2, 4) have `data-in-word="true"`; the clue `Sans contenu` has `data-active="true"` and no other clue does; the three highlight colours differ as stated above.
- **AC-2** (AC-2.2.2) (browser with mocked socket) Tapping the selected cell again switches between its across and down word. On a cell with one word (N or T in FX-01), nothing changes. Tapping (1, 1) gives `across`, `data-word="0,0,0"`; tapping it again gives `down`, `data-word="0,0,1"`; a third tap gives `across` again. Tapping (0, 1) gives `down`, `data-word="0,0,1"`, and tapping it again leaves `down` and `0,0,1`; tapping (1, 0) gives `across`, `0,0,0`, and again leaves them.
- **AC-3** (AC-2.2.3) (browser with mocked socket) Tapping a clue selects the first empty cell of its word. In a two-clue cell, each half selects its own word. With a snapshot where (1, 2) holds `M`, tapping the clue `Artiste muet` gives (2, 2), `down`, `data-word="0,2,0"`. Tapping the clue `Passoire fine` gives (1, 0), `across`, `0,0,0`; tapping `De la marine` gives (0, 1), `down`, `0,0,1`. With a snapshot where (1, 3), (2, 3), (3, 3), (4, 3) hold `I`, `D`, `E`, `S`, tapping `Fatales à César` gives (1, 3), `down`, `0,3,0`.
- **AC-4** (AC-2.2.4) (browser with mocked socket, phone window) The selected word's clue is repeated at 14 px or more in a bar that stays visible above the keyboard. After tapping (3, 1), `clue-bar-text` reads `Fin de prière`, `clue-bar` has `data-word="3,0,0"`, its computed `font-size` is 14 px or more, and its box lies inside the window (top at least 0, bottom at most `window.innerHeight`). It stays inside the window after `window.scrollTo(0, 10000)` and after scrolling `grid-viewport` to its end. Before any tap it reads `fr.json["clue_bar.empty"]`. The in-app keyboard part is spec 009 AC-4.
- **AC-5** (new) (browser with mocked socket) Each selection change sends one `select_cell`. Tapping (1, 1), then (1, 1) again, then (0, 1) twice makes the page send, after its `join`, exactly `SelectCell(row=1, column=1, direction="across")`, `SelectCell(row=1, column=1, direction="down")`, `SelectCell(row=0, column=1, direction="down")`, in that order, and nothing for the last tap.
- **AC-6** (new) (browser with mocked socket) The selected word is the word that was chosen, even when it starts inside a longer run. With a hand-built view where a clue's word starts in the middle of a longer word of the same direction (so a cell belongs to two words of one direction), tapping that clue selects its own word: `data-word` names the clue's word and only its cells have `data-in-word`; the clue bar shows that clue. Tapping a cell afterwards applies AC-1 and Decision 6 again (the longest word of the direction), unless the tapped cell is the selected cell. With no clue involved, a cell shared by two words of one direction selects the longest one (Decision 6), and this is tested with a hand-built view. The `clue-bar` has `role="region"` so its `aria-label` is announced.

## Edge cases and errors

- Direction kept across taps (AC-1): with `down` selected at (1, 1), tapping (2, 2)
  keeps `down` (W3 MIME, `0,2,0`); tapping (2, 1) then keeps `down` (W2).
- Direction forced (AC-1): with `down` selected, tapping (1, 0) (T, across only)
  gives `across`.
- Empty cells and separators (AC-1, AC-3): tapping them changes nothing and sends
  nothing. FX-01 has no empty cell, so the test uses the hand-built view described
  after this list; the separator is tested on FX-01 (0, 0) with
  `locator.dispatch_event("click")`, since it is only 1 px high.
- Word with every cell filled (AC-3): the first cell is selected.
- Locked cells (AC-1, AC-3): they are selectable and count as filled.
- A tap on the active clue again (AC-3): selects the first unfilled cell again,
  which may move the selected cell back; it sends `select_cell` only if the
  selection changed.
- Second snapshot (AC-1): the selection is kept when its cell and direction still
  have a word; otherwise it is cleared (`data-word=""`), and nothing is sent.
- Socket closed (AC-5): selecting still works locally and sends nothing.
- Before the first snapshot: no grid, no clue bar.
- Server replies: the shell server ignores `select_cell`; spec 013 gives it meaning.

The hand-built view for the empty-cell case is a `GridView` (spec 039) of width 3
and height 1: (0, 0) a `ClueCellView` with one clue `{"text": "Note", "arrow": "right"}`,
(0, 1) an empty `LetterCellView`, (0, 2) an `EmptyCellView`. Tapping (0, 2) changes
nothing; tapping (0, 1) selects it `across`, `data-word="0,0,0"`; tapping it again
changes nothing.

## Out of scope

- Printing and offline play (epic E2).
- Grid rendering: spec 006.
- Letter entry: spec 008.
- Keyboard and navigation: spec 009.
- Instant solo start: spec 010 (it restores the selection after a reload).
- Showing other players' selections (spec 013).
- Selecting by long press, double tap or swipe.

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written
(item 3 reworded for the three browser engines the human chose). Each one is
already part of the spec above.

1. Direction on a first tap of a two-word cell. Options: always across, keep the
   current direction, or the direction of the longer word. Pick: keep the current
   direction when the cell has a word in it, `across` when nothing was selected.
2. Clue tap on a full word. Pick: select its first cell.
3. Bar "above the keyboard". The system keyboard cannot be shown in any headless
   engine (Chromium, Firefox, WebKit), and spec 009 replaces it on touch screens
   with an in-app keyboard.
   Pick: here, the bar stays inside the window at 14 px or more (phone emulation,
   all three engines);
   spec 009 AC-4 checks it sits above the in-app keyboard. Not covered: the
   system keyboard of a real phone (on desktop there is none on screen).
4. Nothing selected at start. Options: select the first word on load, or nothing.
   Pick: nothing; the bar shows `clue_bar.empty`. Spec 010 restores a saved
   selection after a reload.
5. Sending `select_cell`. Not asked by the backlog, but the message exists (spec
   039) and spec 013 needs it. Pick: send it on every change (AC-5); no throttling.
6. A cell in two words of the same direction (possible when a word starts in the
   middle of a run, spec 003 edge cases). Pick: the longest one.

Added after the review, decided by the lead on 2026-10-10 under the human's
instruction to take technical decisions:
7. A clue tap selects that clue's word even inside a longer run; the selection
   remembers its word. A cell tap still picks the longest word (AC-6).
8. The clue bar is a labelled region (`role="region"`) (AC-6).

## Open questions

None.
