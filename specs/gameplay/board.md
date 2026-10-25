---
area: gameplay
file: board
status: approved
---

# gameplay/board - The grid, selection, typing and the in-app keyboard

## Purpose

A player sees the grid fit their screen, picks a word with one tap, types along
it and moves between words from the keyboard. On a touch screen an in-app
AZERTY keyboard replaces the system one, and the player may hide it.

## Depends on

- `gameplay/co-op.md`: what a letter or erase sends and shows, pencil mode.
- `gameplay/rules.md`: the solved page's input lock and the status's place.
- `platform/realtime.md`: the snapshot and `select_cell`.

## Rules

### The grid

1. The page draws its latest snapshot's grid: `height` rows of `width` square
   cells, (0, 0) top left, named `grid.label` (« Grille »); letter cells show
   what `gameplay/co-op.md` rule 11 gives them, empty cells nothing. No grid
   shows before the first snapshot; after a close the last one stays. A
   snapshot whose grid repeats a position, has a cell outside it or other than
   `width` x `height` cells is ignored whole, no error shown.
2. A clue cell shows its clues as written, clue 0 over clue 1, a separator
   between. A clue's arrow is in its word's first letter cell, against the clue
   cell's right side for `right`, `right_then_down`, its bottom for `down`,
   `down_then_right`, hidden from assistive technology, taking no tap; a clue
   whose word starts on no letter cell draws none.
3. At zoom 1 the grid fits its viewport and the room page the window, with no
   scrolling; the grid refits when its room changes. Two fingers multiply the
   zoom by the ratio of their distances, between 1 and a maximum at which no
   FX-02 clue text is cut off on a 360 px wide phone; one finger pans. There is
   no other zoom control.
4. Cursors follow `product.md` rule 16, one's own never drawn. A selection
   arriving from another cell or none takes the first free corner of top-left,
   top-right, bottom-right, bottom-left; a change of direction keeps it;
   moving off, disconnecting or leaving frees it. A snapshot keeps the corners
   of players still on their cell and brings the others in roster order.

### Words and selection

5. A word is named by its clue, `row,column,clue_index`, and runs from the cell
   its arrow points to up to the next cell that is not a letter cell or the
   edge: across for `right` and `down_then_right`, else down. A cell's word in
   a direction is the one holding it, of several the longest. A cell is filled
   when it shows a letter, pending, pencil or locked.
6. The selection is a letter cell, a direction in which it has a word, and that
   word; none when the page opens. A tap:
   1. on a letter cell not selected selects it in the current direction if it
      has a word there, else the other; with nothing selected, across if it
      can; the word is the longest;
   2. on the selected cell switches direction if it has words both ways;
   3. on a clue (its half of a two-clue cell) selects that clue's word, even
      inside a longer run, on its first cell not filled, else its first cell;
   4. on an empty cell, a separator or outside the grid changes nothing.

   A tap on a cell or clue gives the focus to the grid, one Tab stop.
7. A snapshot keeps the selection while its word still holds its cell in its
   direction, else clears it, sending nothing. Each other change of selected
   cell or direction sends one `select_cell` with them while the socket is
   open; a change of word alone, or nothing changed, sends nothing.
8. The selected cell, its word and its clue show as such. The clue bar, from
   the first snapshot, is outside the grid's scroll, inside the window, above
   the in-app keyboard when it shows: a region named `clue_bar.label`
   (« Définition en cours ») with the selected word's clue or `clue_bar.empty`
   (« Touchez une case ou une définition. »), its text never under 14 px.

### Typing and moving

9. Keys act while the grid has the focus; with Ctrl, Meta or Alt held, or while
   composing, they are left to the browser, except undo
   (`platform/server.md`). A letter is one character that, decomposed (NFD),
   without combining marks and in capitals, is one of `A` to `Z` (`é` gives
   `E`); others (`œ`, digits, space, punctuation) are ignored, not prevented.
   Letters and Backspace act on a selected cell, not once the grid is solved
   (`gameplay/rules.md` rule 6). A key handled here is prevented, Backspace
   even with nothing selected, so it never leaves the room.
10. A letter L on the selected cell: on a locked cell, nothing. Else the cell
    shows L at once and the edit is sent (`gameplay/co-op.md` rule 8), unless
    it already shows L with the mode's pencil flag; sent or not, the selection
    then moves to the word's next unlocked cell, filled or not, or stays at
    the end.
11. Backspace: a filled, unlocked selected cell is cleared and its `erase`
    sent. Else, off the word's first cell, the selection moves back one cell,
    which is cleared and erased if filled and unlocked.
12. An arrow key steps from the selected cell past clue and empty cells to the
    next letter cell and selects it, across for ← →, down for ↑ ↓ if it has a
    word that way, else the other way; with none before the edge, or nothing
    selected, nothing changes.
13. Tab and Shift+Tab on the grid select the next or previous unfinished word
    (a cell not filled) in clue order (clue cells row by row, clue 0 first),
    wrapping, the selected word last, on its first cell not filled; with
    nothing selected they start before the first or after the last word; with
    none unfinished nothing changes and the focus stays. Escape lets the next
    Tab leave (`product.md` rule 13).

### The in-app keyboard

14. It shows when the page has a snapshot, is on a touch screen (a coarse
    primary pointer, read when the room page loads), the player has not hidden
    it and the grid is not solved; otherwise it is not on the page. Named
    `keyboard.label` (« Clavier »), its rows are `A Z E R T Y U I O P`;
    `Q S D F G H J K L M`; ✎ `W X C V B N` ⇄ ⌫, keys as `product.md` rule 12
    says. While it shows, the grid area, clue bar and keyboard hold no editable
    field, so no system keyboard opens.
15. A letter key types (rule 10); ⌫ (`keyboard.delete`, « Effacer ») is
    Backspace, once per press however long. ⇄ (`keyboard.swap`, « Changer de
    sens ») taps the selected cell (rule 6.2). With nothing selected these do
    nothing. ✎ (`pencil.toggle`, « Crayon ») flips pencil mode
    (`gameplay/co-op.md` rule 7), pressed while on; hiding the keyboard keeps
    the mode.
16. « Clavier » is a top-bar button on a touch screen only. There the phone top
    bar (sheet layout, or any window at most 500 px high, `client/hud.md`) has
    it instead of « Crayon », so a phone held sideways with its keyboard hidden
    has no pencil control; the computer top bar has both. It is pressed while
    the keyboard shows; a press hides it and stores `nock.keyboard_hidden` =
    `true`, or shows it and removes the key, sending nothing; keyboard, layout
    and grid follow within 300 ms, the focus staying on it. Solved, it is
    disabled and unpressed, the stored choice kept.
17. A landscape window at most 500 px high has the sheet layout while the
    keyboard shows, else the column one (`_design/room.md`, « Which layout »);
    its keys take the room design's low size, so the grid keeps 100 px. The
    status sits as `gameplay/rules.md` rule 7 says; on a window more than
    500 px high in the sheet layout, between clue bar and keyboard, while the
    keyboard shows.

### Display switches

18. « Mots des autres » (`others_tint.switch`), on unless `nock.others_tint` is
    `"false"`, tints the other players' words (`social/presence.md`); off, no
    cell is tinted, one's own word unchanged. « Accessibilité »
    (`access.switch`), off unless `nock.accessibility` is `"true"`, makes each
    cursor its player's icon (one per colour index) in the same corner, shown
    in the Joueurs list too (`product.md` rule 15).
19. Both are Menu items after « Auteurs », buttons with `aria-pressed`; a press
    flips one, stores `"true"` or `"false"`, sends nothing, keeps the Menu
    open. A `localStorage` that throws leaves them and the keyboard choice at
    their default, flipping for the page's life.

### Hyphen edges

20. A letter cell's `hyphen_right` or `hyphen_down` mark (`platform/realtime.md`
    rule 23; absent reads false) draws that edge, its right or its bottom, as
    the dashed hyphen edge of `_design/cells.md` « Hyphen edges » in place of
    the grid line, whatever the state of the two cells and at every zoom; no
    other edge is dashed. Words, selection, typing, navigation, check and
    reveal read no mark: `VI-DE` is the four cells of VIDE.

### Look

- `_design/cells.md`: « Grid lines and empty cells »; « Hyphen edges »; « Letter
  cell backgrounds » (the first state that applies wins); « Letter marks » (bold
  locked letter, strike, notch, ink during a flash); « Catch-up ring »; « Other
  players on a cell », « Player icons »; « Clue cells » (text, separator, active
  clue, flag); « Direction arrows »; « Drawing order »; each mark's least size.
- `_design/room.md`: « Clue bar »; « In-app keyboard » (✎'s pencil look, low
  keys, « Clavier »); « Phone top bar », « Computer top bar », « Low column
  layout »; « Menu ».
- Fonts, focus ring: `_design/foundation.md`, « Typography », « Components »,
  « Focus ».

## Acceptance criteria

- **AC-1** A fresh FX-01 room shows a 5 by 5 grid named « Grille »: 7 clue
  cells and 18 empty, unlocked letter cells; FX-02 shows 221 cells. A snapshot
  with `T` at (1, 0) and a locked `M` at (1, 2) shows them; one with (1, 0)
  empty empties it; a malformed one changes nothing, the next valid one shows.
  No grid before the first snapshot or for a room not found; after a close it
  stays. (← 006 AC-4, 006 AC-6, 006 AC-8)
- **AC-2** On a 360 by 740 touch phone FX-02 opens at zoom 1 inside its
  viewport; fingers going from 100 to 150 px apart give 1.5; pinching on stops
  at the maximum, where a pan scrolls both ways and no clue text is cut off;
  pinching in never goes below 1; one finger never zooms; these gesture checks
  run in Chromium only. At 1280 by 800 FX-02 needs no pan. (← 006 AC-1)
- **AC-3** At the supported windows (`product.md` rule 11), for example 320 by
  568 and 568 by 320, the catalogue and the room page never scroll sideways;
  the room page does not scroll down, its grid viewport is inside the window
  and at least 100 by 100 px, and every FX-01 cell is inside the window.
  (← 006 AC-5, 006 AC-7)
- **AC-4** With p2 selecting MIME and `T`, `M` locked at (1, 0), (1, 2), (3, 2)
  has p2's tint; after a tap on (1, 1) it is the selected cell, (1, 0) and
  (1, 2) keep the locked background inside my word, (1, 3) has the word's; a
  tap on (1, 0) makes it the selected cell, as « Letter cell backgrounds »
  orders them. Lines and empty cells follow « Grid lines and empty cells »; at
  1280 by 800 nothing of FX-02 paints outside the grid. (← 042 AC-1, 042 AC-2)
- **AC-5** Letters, a bold locked letter, a struck wrong letter and a revealed
  notch, ink during a flash, follow « Letter marks », the catch-up ring
  « Catch-up ring », with their contrast, selected too. A selected cell with a
  notch, a ring, four cursors and an arrow stacks them in « Drawing order »,
  its border on top. FX-02's small cells at 568 by 320 keep each mark's least
  size of `_design/cells.md`.
  (← 042 AC-4, 042 AC-5, 042 AC-6, 042 AC-7, 042 AC-8, 042 AC-17, 042 AC-18)
- **AC-6** FX-01's (0, 0) shows « Passoire fine » over « De la marine » with a
  separator between; (0, 2) and (2, 0) one clue and no separator; each two-clue
  cell of FX-02 a separator. Clue texts, one size in all clue cells, the
  active clue's half and a flag, over the text without moving it, follow
  « Clue cells ».
  (← 006 AC-3, 042 AC-12, 042 AC-13, 042 AC-14)
- **AC-7** On FX-01 each of the 8 clues has one arrow, in its word's first
  cell ((1, 0) for TAMIS, below (0, 0); (0, 1) for NAVAL, right of it),
  none in a clue cell; a tap on one selects its cell. Two arrows in one cell
  never meet: a → beside a ↴, two →, and a ↳ beside a ↴ take the places of
  « Direction arrows ». (← 006 AC-2, 042 AC-15, 042 AC-16)
- **AC-8** p2 then p3 selecting (2, 2) draw p2 top-left and p3 top-right,
  triangles in their colours; mine draws none. With p2 to p6 arriving there,
  p6 waits; p3 moving off gives p6 top-right; p2 turning down keeps top-left;
  p3 back waits until p4 disconnects, then takes bottom-right. A snapshot with
  p2, p3, p4 on (2, 2) gives them corners in that order.
  (← 042 AC-9, 042 AC-10)
- **AC-9** A press on « Mots des autres » removes AC-4's (3, 2) tint, stores
  `"false"`, sends nothing, and a reload keeps it. A press on « Accessibilité »
  turns p2, p3, p4 (colours 1, 2, 6) into a square, a triangle and a heart in
  their corners and in the Joueurs list, and a reload keeps it. Each is reached
  by Tab in the open Menu with the focus ring, Enter flipping it, and lies in
  the window and takes a tap at every supported window.
  (← 042 AC-3, 042 AC-11, 042 AC-19)
- **AC-10** On FX-01 a tap on (2, 2) selects VIDE (`2,0,0`) across, its four
  cells, « Sans contenu » the only active clue, the focus on the grid. Taps on
  (1, 1), (1, 1), (0, 1), (0, 1) give TAMIS, NAVAL, (0, 1) down, nothing, and
  send exactly `select_cell` (1, 1, across), (1, 1, down), (0, 1, down). Down
  selected, (2, 2) keeps down, (1, 0) turns across. Socket closed, taps select
  and send nothing. (← 007 AC-1, 007 AC-2, 007 AC-5)
- **AC-11** With `M` at (1, 2), « Artiste muet » selects (2, 2) down,
  « Passoire fine » (1, 0) across, « De la marine » (0, 1) down; with IDES full
  « Fatales à César » selects (1, 3). Where « Court » starts inside « Long »,
  « Court » selects its cells only, sending nothing if only the word changed;
  a tap on another cell of the run selects « Long ». (← 007 AC-3, 007 AC-6)
- **AC-12** The clue bar reads « Touchez une case ou une définition. », then
  « Fin de prière » after a tap on (3, 1), at 14 px or more, named « Définition
  en cours », in the window after any scroll. On a touch phone upright or
  sideways it sits above the keyboard, the grid keeping 100 px, no scroll.
  (← 007 AC-4, 007 AC-6, 009 AC-4, 044 AC-5)
- **AC-13** After a tap on (1, 0), `t` shows `T`, sends one `edit_letter` and
  selects (1, 1); `a`, `m`, `i`, `s` fill TAMIS and stay on (1, 4), where `x`
  replaces `S`. `é`, `à`, `ç` type `E`, `A`, `C`; `1`, Space and `?` do
  nothing. Over `A` at (1, 1), `e` sends `E` and skips the locked (1, 2); on
  the locked (1, 2) itself, `x` changes nothing, sends nothing and stays.
  (← 008 AC-1, 008 AC-2, 008 AC-4)
- **AC-14** With `T` and `A` at (1, 0) and (1, 1), Backspace on (1, 1) clears
  it and sends its `erase`, again clears (1, 0), a third time does nothing.
  With nothing selected, Backspace on the grid is prevented and the page stays
  in the room. (← 008 AC-3, 008 AC-5)
- **AC-15** On FX-01 from (1, 1), ArrowDown selects (2, 1) down, ArrowRight
  (2, 2) across, ArrowUp (1, 2) down; ArrowLeft from (1, 0) does nothing; on
  FX-02 arrows jump a clue cell. With MIME full, from NAVAL, Tab selects IDES
  on (1, 3), Shift+Tab NAVAL, TAMIS on (1, 0), then LEST on (4, 1); every word
  full, Tab does nothing, the focus kept. (← 009 AC-1, 009 AC-2)
- **AC-16** On a touch phone the keyboard shows rule 14's rows, it and its
  keys as the room design draws them; keys `T`, `A` after a tap on (1, 0) fill
  and send two letters and ⌫ clears (1, 1); no field is editable or focused;
  ⌫ held 1 s erases once; Tab never reaches a key; ✎ and ⇄ are buttons named
  « Crayon », « Changer de sens ». A computer, a narrow fine-pointer window or
  a page with no snapshot has no keyboard.
  (← 009 AC-3, 044 AC-4, 044 AC-8)
- **AC-17** A tap on ✎ presses it, gives the letter keys the pencil look, sends
  nothing and keeps the focus on the grid; key `T` then sends a `pencil_edit`;
  a tap or a reload turns it off; on a touch tablet « Crayon » shows the same
  state. ⇄ on (1, 1) across selects NAVAL and sends `select_cell`, again TAMIS;
  on (1, 0), or with nothing selected, it does nothing. (← 044 AC-6, 044 AC-7)
- **AC-18** On a touch phone « Clavier » is pressed in the top bar, with no
  « Crayon »; a touch tablet has both, a computer no « Clavier ». A tap hides
  the keyboard within 300 ms, stores the choice, sends nothing, and the grid
  viewport grows by its height; a reload keeps it hidden; a tap, or Enter with
  the focus kept, shows it and removes the key. Hidden at 740 by 360 the layout
  turns column, the top bar stays the phone bar, with no « Crayon », and the
  grid refits larger (`_design/room.md`); at 1024 by 768 it stays column and
  the grid refits larger. (← 044 AC-1, 044 AC-2, 044 AC-3)
- **AC-19** With a full, wrong FX-01 on a touch phone the status band sits
  between clue bar and keyboard; at 740 by 360 it is in the clue bar's row,
  and the band once the keyboard is hidden. A `grid_solved` removes the
  keyboard within 300 ms and disables « Clavier », the choice kept; a page
  opened solved never shows one, and sideways is in the column layout.
  (← 044 AC-9, 044 AC-10)
- **AC-20** `product.md`'s contrast and language scans find nothing on cells
  with a flag, a wrong letter and four cursors, « Accessibilité » off and on,
  or on the keyboard shown, in pencil mode, hidden, or on a full, wrong grid.
  `fr.json` holds `keyboard.label`, `keyboard.delete`, `keyboard.swap`,
  `others_tint.switch` and `access.switch` with the texts of the rules, and
  none of `grid.remote_overflow`, `a11y.remote_overflow`, `flag.marker`.
  (← 042 AC-20, 044 AC-11)
- **AC-21** On FX-01 with `VI-DE` and `NA-VAL`, the right edge of (2, 2) and
  the bottom edge of (1, 1) are the dashed edges of « Hyphen edges », in
  `--nock-hyphen`, with the dash count, thickness and open corners the section
  gives at about 56 px cells and, on a 13 by 17 grid with one hyphen at 568 by
  320, at 18 px; every dash end on a whole pixel at a fractional cell size, and
  every other edge the plain line; the dashes read the same with no one on
  VIDE, with p2's tint on it, with (2, 2) locked, wrong, flashing, or in
  Auteurs mode; a revealed (1, 1) puts its notch over the down hyphen's dashes.
- **AC-22** With (2, 2) my selected cell, its border is dashed on its right
  side in navy, as « Hyphen edges » says, and solid on its three others; a tap
  on (2, 2) selects VIDE's four cells and `v`, `i`, `d`, `e` fill them as on
  FX-01 as published.

## Edge cases

- Locked cells are selectable and count as filled (AC-11, AC-15).
- A stored keyboard choice changes nothing off a touch screen (AC-18).
- A snapshot of a room stored before answers kept their hyphens has no mark:
  no edge is dashed (AC-21).

## Out of scope

- Zoom buttons, Ctrl+wheel; Home, End, Page, Delete keys; shortcuts for ⇄ or ✎;
  QWERTY, accent or digit keys; erasing a word with ⌫, key repeat.
- The hyphen in the clue bar, the announcement or a length pattern; marks for
  spaces and apostrophes; the dashed edge in the operator's replay
  (`admin/operations.md`) and the catalogue's generic grid drawing.
- The selection after a reload: `lobby/rooms.md`. Others' selections:
  `social/presence.md`. Edits, pencil letters: `gameplay/co-op.md`. Top bar,
  Menu, clue bar buttons: `client/hud.md`. Grid roles: `product.md`.

## Code

- `web/src/lib/`: `GridViewport.svelte` (cells, taps, keys, pinch),
  `gridLayout.ts`, `wordSelection.ts`, `navigation.ts`, `letterEntry.ts`,
  `remoteSelections.ts`, `cellDisplaySwitches.ts`, `RoomPage.svelte` (typing,
  keyboard, layout), `roomSession.ts`, `ClueBar.svelte`, `InAppKeyboard.svelte`.
- Tests: `tests/test_board_*`, `tests/test_spec_006_*` to `009_*`, `042_*`,
  `044_*`.
