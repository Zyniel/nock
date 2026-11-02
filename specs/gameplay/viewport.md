---
area: gameplay
file: viewport
status: done
---

# gameplay/viewport - The grid's drawing, cursors, fit, zoom and hyphen edges

## Purpose

A player sees the grid drawn from the latest snapshot, fitted to their screen,
with the other players' cursors on it. On a touch screen two fingers zoom and
one pans, and the viewport follows the selection as the player types or moves
along the grid. A hyphenated answer shows its hyphen as a dashed edge.

## Depends on

- `gameplay/board.md`: the selection and its word; the taps, keys and in-app
  keyboard that move it.
- `gameplay/co-op.md`: what a letter cell shows (rule 11).
- `platform/realtime.md`: the snapshot and its grid, the hyphen marks,
  `selection_moved`.

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
   no other zoom control. While the zoom is above 1, each change of selected
   cell (`gameplay/board.md`), except one made by a tap on a letter cell,
   scrolls the grid's viewport at once the least that shows the whole cell
   with one cell of margin on each side the grid's edge allows; on an axis
   where the viewport holds less than three cells, the cell is centred on it
   instead. A tap on a letter cell, a change of direction alone, a pan, a
   pinch, a resize, a refit, or the keyboard shown or hidden never scrolls
   toward the selected cell; the room page itself never scrolls.
4. Cursors follow `product.md` rule 16, one's own never drawn. A selection
   arriving from another cell or none takes the first free corner of top-left,
   top-right, bottom-right, bottom-left; a change of direction keeps it;
   moving off, disconnecting or leaving frees it. A snapshot keeps the corners
   of players still on their cell and brings the others in roster order.

### Hyphen edges

5. A letter cell's `hyphen_right` or `hyphen_down` mark (`platform/realtime.md`
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
  pinching in never goes below 1; one finger never zooms. At 1280 by 800 FX-02
  needs no pan. (← 006 AC-1)
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
- **AC-9** On FX-01 with `VI-DE` and `NA-VAL`, the right edge of (2, 2) and
  the bottom edge of (1, 1) are the dashed edges of « Hyphen edges », in
  `--nock-hyphen`, with the dash count, thickness and open corners the section
  gives at about 56 px cells and, on a 13 by 17 grid with one hyphen at 568 by
  320 on a computer, at about 12 px; every dash end on a whole pixel at a
  fractional cell size, and every other edge the plain line; the dashes read
  the same with no one on VIDE, with p2's tint on it, with (2, 2) locked,
  wrong, flashing, or in Auteurs mode; a revealed (1, 1) puts its notch over
  the down hyphen's dashes.
- **AC-10** With (2, 2) my selected cell, its border is dashed on its right
  side in navy, as « Hyphen edges » says, and solid on its three others; a tap
  on (2, 2) selects VIDE's four cells, and `v`, `i`, `d`, `e` give the same
  cells and letters as on FX-01 as published.
- **AC-11** On a touch phone held upright, FX-02 zoomed to 2, the viewport at
  the grid's top-left corner: after a tap on « Elle entend les sons », the
  in-app keys `O R E I L L E` fill OREILLE, (1, 2) to (1, 8). Each letter that
  selects a cell with no whole cell right of it in view scrolls across only,
  the viewport's right edge ending at the right edge of the cell after the
  selected one; the scroll down stays 0, the page unscrolled. Typed on the
  grid with a physical keyboard, the letters scroll the same.
- **AC-12** In AC-11's start, after a tap on « Elle va du genou au pied »,
  ArrowDown steps from (2, 0) down column 0 to MONT's (12, 0); each step onto
  a cell with no whole cell below it in view scrolls down only, the viewport's
  bottom edge ending one cell below the selected cell's bottom. From AC-11's
  start again, Shift+Tab with nothing selected selects ECHEC on (16, 6) and
  scrolls down until the viewport's bottom edge is the grid's, and across no
  further than needed to show (16, 7) whole.
- **AC-13** In AC-11's start, after a tap on (1, 2), `O` selects (1, 3), in
  view with a cell of margin around it, and leaves the scroll unchanged; a
  tap on the cell of row 1 that the viewport's right edge cuts selects it,
  the scroll unchanged too.
- **AC-14** On FX-02 at zoom 1, after a tap on « Elle entend les sons »,
  typing OREILLE, then Shift+Tab to JAMBE on (2, 0) and ArrowDown to
  (12, 0) leave the grid's viewport and the page unscrolled.
- **AC-15** On a touch phone held upright, the keyboard hidden, FX-01 zoomed
  to 2 holds two and a half cells across: after a tap on (2, 1), ArrowRight
  selects (2, 2) and centres it left to right, to within 1 px.
- **AC-16** In AC-11's start with (1, 2) selected and a pan to the grid's
  bottom-right corner, (1, 2) stays out of view after ⇄ (COU down), after a
  pinch from 2 to 3 away from it, and after « Clavier » hides the keyboard:
  none of them scrolls toward it.
- **AC-17** In AC-11's start with OREIL in (1, 2) to (1, 6), a tap on « Elle
  entend les sons » selects (1, 7) and scrolls across only, the viewport's
  right edge ending at (1, 8)'s right edge.
- **AC-18** `product.md`'s contrast and language scans find nothing on cells
  with a flag, a wrong letter and four cursors, « Accessibilité » off and on.
  `fr.json` holds `others_tint.switch` and `access.switch` with the texts of
  `gameplay/board.md` rule 18, and none of `grid.remote_overflow`,
  `a11y.remote_overflow`, `flag.marker`. (← 042 AC-20)

## Edge cases

- A selected cell on the grid's first or last row or column keeps no margin
  beyond the grid's edge (AC-12).
- A snapshot of a room stored before answers kept their hyphens has no mark:
  no edge is dashed (AC-9).

## Out of scope

- Zoom buttons, Ctrl+wheel; an animated scroll to the selection; a look of its
  own per separator; the dashed edge in the operator's replay
  (`admin/operations.md`) and the catalogue's generic grid drawing.
- The selection, taps, typing, navigation, the clue bar, the in-app keyboard,
  « Mots des autres » and « Accessibilité »: `gameplay/board.md`. Others'
  selections and their tint: `social/presence.md`. Edits, pencil letters:
  `gameplay/co-op.md`. Grid roles: `product.md`. What a frame may redraw:
  `client/foundation.md`.

## Code

- `web/src/lib/GridViewport.svelte` (cells, arrows, cursors, pinch, following
  the selection), `web/src/lib/gridLayout.ts` (fit, zoom, arrow places, hyphen
  dashes), `web/src/lib/HyphenEdge.svelte`, `web/src/lib/remoteSelections.ts`
  (the corners), `web/src/lib/roomSession.ts` (the snapshot's grid check),
  `web/src/lib/RoomPage.svelte` (the grid's box in the room page).
- Tests: `tests/test_viewport_*`, `tests/test_spec_006_*` and the
  `tests/test_spec_042_*` files of the cited criteria; the pinch gestures of
  AC-2 and AC-16 are checked in Chromium only (`product.md` rule 10).
