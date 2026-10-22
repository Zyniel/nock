---
id: "042"
title: Grid cells
status: draft
---

# 042 - Grid cells

Epic E10 Quality bar · Release: MVP · No backlog story: this is build step 2 of
`specs/_design.md` (section 14). It applies `_design.md` section 6 (grid cells),
with the parts of sections 2 (colour tokens and their jobs), 3 (player colours),
4 (grid letters and clue text) and 5 (the flag icon) that a cell uses, and the
Accessibilité mode's player icons (section 6, "Player icons"). It builds on spec
041 (tokens, player colours, fonts, `web/src/lib/icons.ts`, the flash overlay
`cell-flash`) and redefines none of them. The FX-01 reference grid is in
`specs/_reference.md`; the stack in `specs/_architecture.md`.

## Goal

The human validated the look of every grid cell (`_design.md` section 6,
`docs/design/cell-sheet.html`) and asked on 2026-10-22 that the game be built on
that design. This spec draws the cells that way: grid lines, backgrounds,
letters, the strike, the revealed notch, the catch-up ring, the other players'
corner triangles and their Accessibilité icons, clue cells with their separator,
active clue and flag, and the direction arrows inside the letter cells, in the
design's drawing order. The room layout around the grid (top bar, Salon, Menu,
clue bar) does not change here; steps 3 to 5 do it.

## Public interface

No new Python name, no new protocol message, no new HTTP route. Client only
(`web/`, chiefly `web/src/lib/GridViewport.svelte`, `remoteSelections.ts`,
`gridLayout.ts` and `RoomPage.svelte`). Every colour is a token of spec 041, used
for its job in `_design.md` section 2; every icon shape comes from
`web/src/lib/icons.ts` (`ICONS.flag`, `PLAYER_ICONS`).

Terms used below:

- `s`: the side of a cell, the width of its `cell` element's bounding box in CSS
  px, its right and bottom grid lines included (the cell is
  `box-sizing: border-box`).
- The inner box of a cell: its bounding box less its 1 px right and bottom grid
  lines (its padding box): left and top as the bounding box, width and height
  `s - 1`. "The top-left corner of the inner box" and so on are its corners.
- `max(7px, 0.22 s)` means the larger of 7 px and 0.22 times `s`.

### Grid lines and empty cells (`_design.md` section 6)

- The `grid` element (spec 006) has a 1 px solid `--nock-rule` left and top
  border, and no right or bottom border.
- Every `cell` has a 1 px solid `--nock-rule` right and bottom border and no left
  or top border. There is no gap between cells: a cell's left edge is its left
  neighbour's right edge.
- Letter cells and empty cells clip their content (`overflow: hidden`); clue
  cells do not (`overflow: visible`).
- An empty cell (`data-type="empty"`) has the background `--nock-rule` and holds
  no element.
- The grid's box is `W x s + 1` wide and `H x s + 1` high (`W`, `H` its width and
  height in cells): spec 006's fit at zoom 1 counts the extra line.

### Letter cell backgrounds

Exactly one background applies, the first that matches:

| State | The cell's computed `background-color` |
| --- | --- |
| Flash (`data-flash` not `""`, spec 016) | `--nock-white`, under spec 041's `cell-flash` overlay (the replacer's colour at 38 %) |
| My selected cell (`data-selected="true"`) | `--nock-selected` |
| Locked (`data-locked="true"`: checked right, or revealed) | `--nock-locked` |
| In my selected word (`data-in-word="true"`) | `--nock-word` |
| In another player's selected word (`data-tinted-by` not `""`) while the tint is on | `color-mix(in srgb, var(--player-colour-N) 16%, var(--nock-white))`, N the colour of the first player of `data-tinted-by` (roster order, spec 013) |
| Otherwise | `--nock-white` |

Locked now beats "in my word" (today a locked cell of my word takes the word blue).

The tint switch, « Mots des autres » (`_design.md` section 6):

- `data-testid="others-tint-switch"`, a `<button type="button">` with
  `aria-pressed` and the text `t("others_tint.switch")`, in `room-toolbar` (see
  "Room toolbar"). `true` means the other players' words are tinted.
- It starts from `localStorage["nock.others_tint"]`: `"false"` gives `false`; any
  other value, or none, gives `true` (on by default). Each click flips it and
  writes `"true"` or `"false"` there. It is never disabled and sends nothing.
- While it is `false`, no letter cell takes the tint row of the table; every
  `data-tinted-by` keeps its value (spec 013).

### Letters (`_design.md` sections 4 and 6)

- A letter cell whose `data-letter` is not `""` holds one
  `data-testid="cell-letter"` element whose text is that letter; a cell with
  `data-letter=""` holds none. The cell's text still holds the letter, followed
  by the hidden labels of other specs (`reveal-label`).
- The cell sets the letter's font, inherited by `cell-letter`: family
  `var(--nock-font-ui)`, size `0.56 s`, line height 1, weight 500, and 700 when
  the cell is locked (spec 035 AC-7); colour `--nock-ink` (pencil letters:
  spec 020 and spec 041, `--nock-pencil` and italic, ink during a flash).
- `cell-letter` has `text-box: trim-both cap alphabetic`, so the capital is
  centred on its cap height and baseline; an engine without `text-box` (Firefox
  today) centres the line box, about 0.5 px off, which is accepted. The cell
  centres `cell-letter` on both axes.
- Wrong after a check (`data-wrong="true"`, spec 023): the cell has
  `text-decoration-line: line-through`, `text-decoration-thickness:
  max(2px, 0.07em)` and `text-decoration-color: var(--nock-red)`; the line is
  drawn through the letter.

### Revealed notch (spec 024, refined)

A cell with `data-revealed="true"` holds one `data-testid="reveal-mark"`, the
notch, and spec 024's `reveal-label`:

- `aria-hidden="true"`, no text, `pointer-events: none`, `position: absolute`,
  `z-index: 3`;
- an isosceles triangle pointing up: `clip-path: polygon(50% 0%, 100% 100%, 0%
  100%)` on a box `max(7px, 0.22 s)` wide and `max(4px, 0.11 s)` high, centred
  on the inner box horizontally, its bottom on the inner box's bottom;
- `background-color: var(--nock-reveal)`, and `var(--nock-ink)` while the cell
  has `data-flash` other than `""` (lead's decision 2).

Orange-red keeps 3:1 on the locked grey (4.17:1) and on my selected cell
(3.77:1); ink keeps it on the white-and-colour composite of every flash.

### Catch-up ring (spec 034)

`catch-up-mark` (spec 034) is `position: absolute` with `inset: 0` (the inner
box), `box-sizing: border-box`, a 3 px solid `--nock-ink` border on each side,
`z-index: 1` and `pointer-events: none`.

### Other players on a cell (spec 013, refined)

The cursors of a cell are the other players whose selection is on it (never
`you`, never a disconnected player, spec 013).

Corners, in this order: `top-left`, `top-right`, `bottom-right`, `bottom-left`.

- A player arrives on a cell when their selection moves onto it from another
  cell or from none (a `selection_moved`, or a snapshot that puts them there).
  A `selection_moved` that keeps the cell (a new direction, or the same
  selection again) is not an arrival.
- An arriving player takes the first corner, in the order above, that no cursor
  of the cell holds. When all four are held, the player gets no corner and waits.
- A player leaves the cell when their selection moves to another cell or to
  `null`, when their state becomes `disconnected`, or when they leave the room.
  The others keep their corners. The corner it frees goes at once to the player
  who has waited longest on that cell, if any.
- A snapshot: a player whose selected cell is the one they had before keeps their
  corner; the other players with a selection arrive in roster order (the order of
  the snapshot's `players`). So on the first snapshot every cursor arrives in
  roster order.

For each cursor that holds a corner the cell holds one
`data-testid="remote-selection"` element (spec 013's id), with `data-player-id`,
`data-colour`, `data-corner` (its corner) and `data-shape`. A cursor with no
corner has no element and nothing says "+k". The element has `aria-hidden="true"`,
no text, `pointer-events: none`, `position: absolute` and `z-index: 2`:

- Accessibilité off: `data-shape="triangle"`, a box `t` by `t` with
  `t = max(6, round(0.3 s))` px, in its corner of the inner box. It holds one
  `svg` (`viewBox="0 0 10 10"`, `preserveAspectRatio="none"`, filling the box)
  with one `polygon` whose `points` is, by corner: `top-left` `0,0 10,0 0,10`;
  `top-right` `0,0 10,0 10,10`; `bottom-right` `10,0 10,10 0,10`; `bottom-left`
  `0,0 10,10 0,10`. The polygon's `fill` is `var(--player-colour-N)` (N its
  `data-colour`), with no stroke.
- Accessibilité on: `data-shape="icon"`, a box of side `max(6px, 0.24 s)`, inset
  from its corner of the inner box by `max(1px, 0.04 s)` on both axes. It holds
  one `svg` with `data-testid="player-icon"`, `data-icon` N (the player's colour
  index), `viewBox="0 0 10 10"`, filling the box, whose shapes are exactly
  `PLAYER_ICONS[N]` of spec 041 (same elements, same attribute values), each with
  `fill` `var(--player-colour-N)` and no stroke.

The dashed outlines of spec 013 and the initials and `+k` labels of spec 035
(`remote-initials`, `remote-overflow`, `remote-overflow-label`) are gone, with
`initialsOf` and the `initials` field of `RemoteSelection`.

The Accessibilité switch, « Accessibilité » (`_design.md` section 6):

- `data-testid="access-switch"`, a `<button type="button">` with `aria-pressed`
  and the text `t("access.switch")`, in `room-toolbar`. `true` means the mode is
  on.
- It starts from `localStorage["nock.accessibility"]`: `"true"` gives `true`;
  any other value, or none, gives `false` (off by default). Each click flips it
  and writes `"true"` or `"false"` there. It is never disabled and sends nothing.
- While it is `true`, each `roster-colour` swatch (spec 012) has a transparent
  background and holds one `player-icon` `svg` of 12 by 12 px for that player's
  colour index (as above), in place of the coloured dot. It is the legend of the
  icons until the Joueurs list of step 3.

### Clue cells (`_design.md` sections 4 and 6)

- Background `--nock-clue-bg`; padding 2 px top and bottom, 3 px left and right;
  the cell's `clue` elements fill its content box: one clue fills it, two clues
  share it in two halves of equal height, clue 0 on top, with the separator
  between them. Each `clue` centres its `clue-text` vertically.
- `clue-text`: family `var(--nock-font-clue)`, weight 600, size
  `max(6px, 0.145 s)`, line height 1.12, letter spacing 0.01em,
  `text-transform: uppercase`, `text-align: center`, `overflow-wrap: break-word`,
  `hyphens: manual`, colour `--nock-clue-ink`. One size for one-clue and two-clue
  cells. The text node keeps the clue as written (the capitals are the CSS's).
- `clue-separator`: 1 px high, background `--nock-clue-ink` at `opacity: 0.55`,
  `margin: 0 14%` (14 % of the cell's content width on each side).
- Active clue (`data-active="true"`, spec 007): background `--nock-selected`,
  `border-radius: 2px`, on that clue element only (one half of a two-clue cell).
- Flag (spec 021, refined): `clue-flag` is a square of side `max(8px, 0.22 s)`,
  `position: absolute`, `z-index: 2`, at the top-left of its own `clue` element:
  its top on that element's top, its left 1 px right of the cell's left edge.
  Background `--nock-clue-bg`, `border-radius: 0 0 3px 0`. It holds no text and
  one `svg` (`aria-hidden="true"`, `viewBox="0 0 24 24"`, 86 % of the square's
  side, centred in it) with the two paths of `ICONS.flag` (`M6 21V4` and
  `M6 4h12l-3 4.5 3 4.5H6z`), `fill` and `stroke` `var(--nock-red)`,
  `stroke-width` 2, round caps and joins. Spec 021's `clue-flag-label` stays. The
  flag is drawn over the clue text and never moves it (spec 021).
- Shown reaction (spec 022): unchanged in this spec; its look comes with step 3.

### Direction arrows (spec 006, refined)

Each clue's arrow is drawn in its target cell: the cell right of its clue cell
for `right` and `right_then_down`, the cell below for `down` and
`down_then_right`. A target outside the grid or that is not a letter cell gets no
arrow (spec 003 makes this impossible in a valid grid). No clue cell holds an
arrow.

- `data-testid="clue-arrow"` is an `svg` child of the target letter cell, with
  spec 006's `data-arrow` and `data-side`, plus `data-clue-row`,
  `data-clue-column` and `data-clue-index` naming its clue; `aria-hidden="true"`,
  no text, `pointer-events: none`, `position: absolute`, `z-index: 6`,
  `viewBox="0 0 24 24"`, width and height `a = max(9px, 0.26 s)`.
- It holds one `path` (no fill, stroke `--nock-ink`, `stroke-width` 2.4, round
  caps and joins) and one `polygon` (fill `--nock-ink`), by arrow:

  | `data-arrow` | Glyph | `path` `d` | `polygon` `points` |
  | --- | --- | --- | --- |
  | `right` | → | `M2 12H15` | `14,7.5 22,12 14,16.5` |
  | `down` | ↓ | `M12 2V15` | `7.5,14 12,22 16.5,14` |
  | `down_then_right` | ↳ | `M5 2V10Q5 15 10 15H15` | `14,10.5 22,15 14,19.5` |
  | `right_then_down` | ↴ | `M2 5H10Q15 5 15 10V15` | `10.5,14 15,22 19.5,14` |

- Halo: `filter: drop-shadow(0 0 0.8px var(--nock-white)) drop-shadow(0 0 0.8px
  var(--nock-white))`.
- Position in the target cell, relative to its bounding box (left `L`, top `T`):

  | Arrow | Box |
  | --- | --- |
  | → | left `L - 1`; vertical centre `T + 0.5 s` |
  | ↓ | top `T - 1`; horizontal centre `L + 0.5 s` |
  | ↳ | top `T - 1`; left `L + 0.06 s` |
  | ↴ | left `L - 1`; top `T + 0.06 s` |

- Collision rules, per target cell (`_design.md` section 6):
  1. A → whose target also receives a ↴: the → has its vertical centre at
     `T + 0.72 s`; the ↴ keeps its place.
  2. Otherwise, two → in one target (only from one two-clue cell): the → of clue
     0 has its centre at `T + 0.25 s`, the → of clue 1 at `T + 0.72 s`.
  3. A ↳ whose target also receives a ↴: the ↳ has its left at `L + 0.4 s` (top
     `T - 1`); the ↴ keeps its place.

The box's edge at `-1` lies on the grid line, where the cell clips it; no stroke
is there (strokes start 2 units in).

### Drawing order (`_design.md` section 6)

Top first, inside one cell: my selection border (the cell's `outline`, 2 px
solid `--nock-navy`, `outline-offset: -2px`, spec 041); the arrows (6); the
notch (3); the triangles or icons (2), and in clue cells the flag (2); the
catch-up ring (1); the letter or the clue text; the flash overlay (spec 041),
then the background. Each letter cell stays a stacking context of its own
(`isolation: isolate`, spec 041), so these z-indexes order the cell's marks only.
Spec 019's `author-mark` (until step 5 replaces it) sits above the ring and under
the triangles.

### Room toolbar

`others-tint-switch` and `access-switch` sit in spec 024's `room-toolbar`, in
this order, right after `authors-switch` and before `account-open` (spec 033)
when it shows. Spec 024's toolbar rules apply to them. Step 3 moves them into the
Menu (`_design.md` section 8), keeping their test ids and storage keys.

(Note from the lead, 2026-10-22: refined by spec 043, the design's room layout.
Once spec 043 is built, the two switches are the second and third items of the
room Menu (`room-menu`), after `authors-switch`, each with its label and a detail
(« teintés » / « sans teinte », « activée » / « désactivée »), the toolbar being
gone; activating one leaves the Menu open. Their ids, `aria-pressed`, texts of
`fr.json`, storage keys and behaviour do not change. AC-19 changes, so the
test-writer updates its test before spec 043's implementer runs; the clicks of
AC-3, AC-11, AC-18 and AC-20 are made with the Menu open (spec 043's "Test
harness"). The roster swatch of "The Accessibilité switch" is the Joueurs row's
player dot, and spec 043 gives the stream's dots the same icon.)

### `fr.json` keys

New:

| Key | Value |
| --- | --- |
| `others_tint.switch` | `Mots des autres` |
| `access.switch` | `Accessibilité` |

Removed, since nothing shows them any more: `grid.remote_overflow` and
`a11y.remote_overflow` (spec 035), `flag.marker` (spec 021).

### Refined specs

Each refined spec carries a dated note. The test-writer updates the tests of the
criteria named here before the implementer runs.

| Spec | Criteria that change | What changes in their tests |
| --- | --- | --- |
| 006 | AC-2; the edge case "Two clues pointing right" | `clue-arrow` is found in the word's first letter cell by `data-clue-row`, `data-clue-column` and `data-clue-index`, no longer inside its `clue`; its box test is unchanged. Of a → and a ↴ from one cell, the ↴ is in the top half and the → in the bottom half, whatever their indexes |
| 013 | AC-2, AC-3 | `remote-selection` is a corner triangle: its polygon's `fill`, not a dashed `border-color`, equals the roster swatch; AC-3's two cursors are at `top-left` then `top-right` |
| 019 | AC-1 (drawing-order check) | Over the band, the triangles replace the corner labels: points inside a triangle return it, points outside every triangle return `author-mark` |
| 021 | AC-1, AC-9, AC-10 | `clue-flag` holds the flag icon and no text (no `fr.json["flag.marker"]`); AC-9 checks the square's side instead of a font size and drops the NAVAL overlap check; AC-10's scan no longer meets `⚑` |
| 024 | AC-9 | `reveal-mark` is the bottom-centre notch of "Revealed notch"; during a flash it is ink, and the flash run reads the colour from `cell-flash` |
| 034 | AC-2 | The hit test is on `p2`'s triangle, not on its initials |
| 035 | AC-6, AC-9, AC-11 | AC-6: the non-colour sign of a cursor is the Accessibilité icon; AC-9: five keys, not seven; AC-11: at most four triangles, no `+k` |
| 041 | AC-15 (the `clue-arrow` check) | The arrow of (0, 2) is in (1, 2), and its path's `stroke` is ink, in place of a `border-top-color` |

Specs 007, 012, 016, 020 and 023 get a note and no criterion change: their
checks (three different highlight colours, the roster swatch's colour while the
mode is off, the flash colour on `cell-flash`, the pencil italics and grey, the
`line-through`) still hold.

### Test harness

- "Browser with mocked socket" as in spec 040, with FX-01 snapshots built from
  `grid_view(fx01_grid)` and `model_copy`, `seq` 5, `you` `p1` (`ANA`, colour 0,
  host) unless a criterion says otherwise; other players `p2` to `p8` with the
  colours a criterion gives. "Browser with mocked socket and mocked catch-up" as
  in spec 034. FX-02 snapshots from `tests/fixtures/fx02.json` (spec 006).
  Hand-built views are `GridView` values of spec 039, as in spec 007.
- Window 1280 by 720, desktop context, unless a criterion says otherwise.
  `localStorage` starts empty, except where a criterion seeds it with
  `context.add_init_script`.
- `s` is read from the cell's bounding box; positions are bounding boxes
  (`getBoundingClientRect`). Tolerances: 1 px for a position, 0.5 px for a size,
  0.1 px for a font size or line height, unless a criterion says otherwise.
- Colours as spec 041: `parseColour` of `tests/colour_contrast.js`, exact
  channels for a token, within 1 per channel for a `color-mix` or a composite.
  The composite of a flash is `--player-colour-N` at alpha 0.38 over white.
  Contrast by spec 035's formula. An SVG shape's colour is its computed `fill`
  or `stroke`.
- Hit tests: after `scrollIntoView` of the cell, a test style sets
  `pointer-events: auto !important` on every descendant of every `cell` (spec
  019 AC-1's method), then `document.elementFromPoint` at the named point. The
  test first checks that the point lies where the criterion says (inside the
  triangle, inside the ring's band) and fails otherwise.
- "Inside a triangle": for a point at distances `dx` and `dy` from the two edges
  of the triangle's corner of the inner box, `dx + dy < t - 1.5`.
- Fonts: spec 041's rule (wait for `document.fonts.ready` before reading a size
  or a position that depends on text).
- Engines: Chromium and WebKit locally, Firefox too in CI. No check is
  Chromium-only. The `text-box` check of AC-4 runs where
  `CSS.supports("text-box", "trim-both cap alphabetic")` is true.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (new) (browser with mocked socket) Grid lines are single 1 px rule-grey lines and empty cells are rule grey. On a FX-01 snapshot: the `grid` has a computed `border-left` and `border-top` of `1px` `solid` rgb(154, 163, 178) and a `border-right-width` and `border-bottom-width` of `0px`; every `cell` has `border-right` and `border-bottom` `1px` `solid` rgb(154, 163, 178) and `border-left-width` and `border-top-width` `0px`; the left edge of (2, 2) is within 0.5 px of the right edge of (2, 1), and the top edge of (2, 2) within 0.5 px of the bottom edge of (1, 2); the grid's box is `5 s + 1` wide and high (1 px tolerance); every letter cell has computed `overflow` `hidden` and every clue cell `visible`. On spec 007's hand-built view (width 3, height 1, (0, 2) an `EmptyCellView`), (0, 2) has `background-color` rgb(154, 163, 178), `overflow` `hidden` and no child element.
- **AC-2** (new) (browser with mocked socket) One background per letter cell, by the design's precedence. Given a FX-01 snapshot with `p2` (colour 3) selecting (2, 2) `down` (MIME), (1, 0) holding `T` locked and (1, 2) holding `M` locked: before any tap, (3, 2) has a `background-color` within 1 per channel of rgb(231, 223, 250) and (2, 1) rgb(255, 255, 255). After a tap on (1, 1) (`across`, TAMIS): (1, 1) has rgb(207, 221, 243); (1, 0), locked and in my word, rgb(227, 231, 238); (1, 2), locked, in my word and in `p2`'s word, rgb(227, 231, 238); (1, 3), in my word, rgb(230, 237, 249); (3, 2) still the tint. After a tap on (1, 0): (1, 0), selected and locked, has rgb(207, 221, 243) and (1, 1) rgb(230, 237, 249). After a tap on (3, 2): (3, 2), selected and tinted, has rgb(207, 221, 243).
- **AC-3** (new) (browser with mocked socket) Each player can turn the other players' word tint off, and the choice is kept in the browser. With the snapshot of AC-2 and empty `localStorage`: `others-tint-switch` has `aria-pressed="true"` and (3, 2) has the tint of AC-2. After a click, `aria-pressed` is `false`, (3, 2) and (4, 2) have `background-color` rgb(255, 255, 255) while their `data-tinted-by` is still `p2`, `localStorage["nock.others_tint"]` is `"false"`, and the page sent no frame within 300 ms (spec 017's `ping` frames are not counted). After a reload with the same mock, the switch has `aria-pressed="false"` and (3, 2) is white. A second click gives `aria-pressed="true"`, the tint again, and `"true"` in storage.
- **AC-4** (new) (browser with mocked socket) Grid letters are Source Sans 3 at 0.56 of the cell, bold when locked. Given a FX-01 snapshot where (1, 0) holds `T` locked and (1, 1) holds `A`: each of the two cells holds one `cell-letter` with the text of its `data-letter`, whose computed `font-family`, read as spec 041 AC-4 reads it, is `Source Sans 3`, `Segoe UI`, `system-ui`, `sans-serif`, whose `font-size` is `0.56 s` and `line-height` equal to its `font-size`, and whose `color` is rgb(20, 24, 31); its `font-weight` is 700 in (1, 0) and 500 in (1, 1). (1, 2), empty, holds no `cell-letter`. Where the engine supports `text-box` (see "Test harness"), `cell-letter` has the computed `text-box-trim` `trim-both` and `text-box-edge` `cap alphabetic`. The centre of the `cell-letter` box is within 1 px of the centre of the cell's inner box on the horizontal axis.
- **AC-5** (new) (browser with mocked socket) A wrong letter is struck in red with a line of at least 2 px. Given a FX-01 snapshot where (1, 1) holds `X` with `wrong` true: (1, 1) has `data-wrong="true"`, a computed `text-decoration-line` containing `line-through`, a `text-decoration-color` of rgb(180, 35, 24) and a `text-decoration-thickness` within 0.1 px of the larger of 2 px and 0.07 times its computed `font-size`.
- **AC-6** (new; refines spec 024 AC-9) (browser with mocked socket) A revealed letter has an orange-red notch at the middle of its bottom edge. Given a FX-01 snapshot where (1, 0) holds `T` revealed (`locked`, `revealed`, no author): its `reveal-mark` has computed `position` `absolute`, `z-index` `3`, `pointer-events` `none`, `background-color` rgb(194, 65, 12) and `clip-path` `polygon(50% 0%, 100% 100%, 0% 100%)`; its box is `max(7, 0.22 s)` wide and `max(4, 0.11 s)` high, its horizontal centre within 1 px of the inner box's, and its bottom within 1 px of the inner box's bottom. Its colour has a contrast of at least 3:1 against the cell's `background-color` (locked grey) and, after a tap on (1, 0), against the selected blue. (1, 1), not revealed, holds no `reveal-mark`.
- **AC-7** (new; lead's decision 2) (browser with mocked socket) During a flash the notch turns ink. Given a FX-01 snapshot (`seq` 10) with `p1` (colour 0) and `p5`, `p6`, `p7` of colours 4, 5 and 6, where (1, 0), (1, 1) and (1, 2) hold `X` by `p1`: for c = 4, 5, 6, on the cell at position c - 3 of that list (solutions `T`, `A`, `M`), the mock sends back to back a `letter_changed` with `Y` by the player of colour c, a `reveal_result` (scope letter, that cell) and a `cell_locked` (that cell, its solution, `revealed` true), with consecutive seqs. Right after the cell's `data-revealed` becomes `true`, one `page.evaluate` reads `data-flash` (still `c`), the `reveal-mark`'s `background-color`, which is rgb(20, 24, 31), and its contrast against the composite of `--player-colour-c` at 38 % over white, which is at least 3:1. Once `data-flash` is `""` (within 2,000 ms), the notch is rgb(194, 65, 12) again.
- **AC-8** (new) (browser with mocked socket and mocked catch-up) The catch-up ring is a 3 px ink ring on the cell's inner edge. With `seen_seq` 5 stored, a snapshot at `seq` 9 and the catch-up `CatchUp(after_seq=5, until_seq=9, cells=(CellRef(row=1, column=0), CellRef(row=2, column=2)), lines=(), names=())`, after a tap on (2, 2): each `catch-up-mark` has computed `position` `absolute`, `top`, `right`, `bottom` and `left` `0px`, `box-sizing` `border-box`, a `3px` `solid` border of rgb(20, 24, 31) on each side, `z-index` `1` and `pointer-events` `none`, and its box is the cell's inner box (left and top of the cell, `s - 1` wide and high). Its contrast against the cell's background is at least 3:1 on (1, 0) (white) and on (2, 2) (selected blue).
- **AC-9** (new; refines spec 013 AC-2 and AC-3) (browser with mocked socket) Another player on a cell is a plain triangle in their colour, in a corner. Given a FX-01 snapshot with `p2` (colour 1) and `p3` (colour 2) and no selection, when the mock sends `selection_moved` for `p2` on (2, 2) `across`, then for `p3` on (2, 2) `down`: within 300 ms (2, 2) holds exactly two `remote-selection` elements, `p2`'s with `data-corner="top-left"` and `p3`'s with `data-corner="top-right"`, each with `data-shape="triangle"`, `aria-hidden="true"`, no text, computed `pointer-events` `none` and `z-index` `2`; each box is `t` by `t` with `t = max(6, round(0.3 s))`, `p2`'s at the inner box's top-left corner and `p3`'s at its top-right corner; each holds one `svg` with `viewBox="0 0 10 10"` and `preserveAspectRatio="none"`, holding one `polygon` with `points` `0,0 10,0 0,10` (`p2`) or `0,0 10,0 10,10` (`p3`), whose computed `fill` equals the `background-color` of that player's `roster-colour` and whose computed `stroke` is `none`. After `p1` taps (2, 2), no cell holds a `remote-selection` with `data-player-id="p1"`, and the two triangles stay.
- **AC-10** (new) (browser with mocked socket) Corners go by order of arrival, at most four, and a player who leaves frees a corner without moving the others. Given a FX-01 snapshot with `p2` to `p6` (colours 1 to 5) and no selection, the mock sends `selection_moved` on (2, 2) `across` for `p2`, `p3`, `p4`, `p5` and `p6`, in that order: (2, 2) holds four `remote-selection` elements, `p2` `top-left`, `p3` `top-right`, `p4` `bottom-right`, `p5` `bottom-left`, and none for `p6`. Then, each within 300 ms: `p3` moves to (3, 1) `across`: (2, 2) has `p2` `top-left`, `p6` `top-right`, `p4` `bottom-right`, `p5` `bottom-left`, and (3, 1) has `p3` `top-left`; `p2` moves to (2, 2) `down`: `p2` keeps `top-left`; `p3` moves back to (2, 2) `across`: (3, 1) has no `remote-selection` and (2, 2) the same four as before; `player_state_changed` makes `p4` `disconnected`: (2, 2) has `p3` at `bottom-right` and the other three unchanged. In a second run, a snapshot whose players `p2`, `p3` and `p4` already select (2, 2) gives `p2` `top-left`, `p3` `top-right` and `p4` `bottom-right` (roster order).
- **AC-11** (new; refines spec 035 AC-6) (browser with mocked socket) The Accessibilité mode gives each player their own icon, on the grid and in the roster, and the choice is kept in the browser. Given a FX-01 snapshot with `p2` (colour 1) and `p3` (colour 2) selecting (2, 2) and `p4` (colour 6) selecting (1, 0), and empty `localStorage`: `access-switch` has `aria-pressed="false"` and the cursors are triangles. After a click it is `true`, `localStorage["nock.accessibility"]` is `"true"`, the page sent no frame within 300 ms (pings not counted), and each `remote-selection` has `data-shape="icon"`, the same `data-corner` as before (`p2` `top-left`, `p3` `top-right`, `p4` `top-left`), a box of side `max(6, 0.24 s)` whose near edges are `max(1, 0.04 s)` from its corner's two edges of the inner box, and one `player-icon` with `data-icon` equal to its `data-colour` and `viewBox="0 0 10 10"`, holding exactly the shapes of `PLAYER_ICONS[N]`: for `p2` one `rect` with `x` 0.9, `y` 0.9, `width` 8.2, `height` 8.2; for `p3` one `polygon` with `points` `5,0.4 9.7,9.3 0.3,9.3`; for `p4` one `path` with `d` `M5 9.4L1.1 5.5A2.45 2.45 0 0 1 5 2.3A2.45 2.45 0 0 1 8.9 5.5Z`; each shape's computed `fill` is the player's `roster-colour` colour read before the click. Each `roster-colour` then has a background with alpha 0 and holds one `player-icon`, 12 by 12 px, with `data-icon` equal to its item's `data-colour`. After a reload, the switch is `true` and the icons show. A second click gives `false`, `"false"` in storage, triangles again, and swatches with their colour and no `player-icon`.
- **AC-12** (new) (browser with mocked socket) Clue text is IBM Plex Sans Condensed in capitals, one size in every clue cell. On a FX-01 snapshot, for the clue cells (0, 0) and (0, 2): computed `background-color` rgb(238, 242, 248), `padding-top` and `padding-bottom` `2px`, `padding-left` and `padding-right` `3px`; each `clue-text` has `font-family` `IBM Plex Sans Condensed`, `Arial Narrow`, `Roboto Condensed`, `sans-serif` (read as spec 041 AC-4), `font-weight` 600, `font-size` `max(6, 0.145 s)` px, the same in both cells, `line-height` 1.12 times its size, `letter-spacing` 0.01 times its size (0.05 px tolerance), `text-transform` `uppercase`, `text-align` `center`, `overflow-wrap` `break-word`, `hyphens` `manual` and `color` rgb(27, 34, 48), and its text content is the clue as written (`Passoire fine`). The `clue` of (0, 2) fills the content box (left `L + 3`, top `T + 2`, width `s - 7`, height `s - 5`); the two `clue` elements of (0, 0) have the same height and the width `s - 7`, clue 0 above the separator and clue 1 below it; each `clue-text` has its vertical centre within 1 px of its `clue`'s.
- **AC-13** (new) (browser with mocked socket) The separator is a 55 % clue-ink line inset 14 %, and the active clue is its own half in selected blue. On a FX-01 snapshot, the `clue-separator` of (0, 0) is 1 px high, with computed `background-color` rgb(27, 34, 48), `opacity` `0.55`, and `margin-left` and `margin-right` of 0.14 times `s - 7` (0.5 px tolerance). After a tap on (1, 0) (TAMIS), clue 0 of (0, 0) has `background-color` rgb(207, 221, 243) and `border-radius` `2px` on each corner, and clue 1 a background with alpha 0; after a tap on (2, 1) (VIDE), the `clue` of (2, 0), as large as its content box, has rgb(207, 221, 243) and clue 0 of (0, 0) alpha 0.
- **AC-14** (new; refines spec 021 AC-9) (browser with mocked socket) A flagged clue shows the red flag icon at the top-left of its own half, over the text. Given a FX-01 snapshot whose `flags` hold `p2` on IDES (0, 3, 0) and `p3` on NAVAL (0, 0, 1): each `clue-flag` has computed `position` `absolute`, `z-index` `2`, `background-color` rgb(238, 242, 248), `border-bottom-right-radius` `3px` and the three other radii `0px`, no text, and a box of side `f = max(8, 0.22 s)` whose left edge is 1 px right of its cell's left edge and whose top is its `clue` element's top (for NAVAL, the bottom of the `clue-separator`, 1 px tolerance). It holds one `svg` with `aria-hidden="true"` and `viewBox="0 0 24 24"`, of side `0.86 f`, centred in the flag's box, with two `path` elements whose `d` are `M6 21V4` and `M6 4h12l-3 4.5 3 4.5H6z`, each with computed `fill` and `stroke` rgb(180, 35, 24) and `stroke-width` `2px`; the red's contrast against the flag's background is at least 3:1. With the hit-test style, `document.elementFromPoint` at the centre of each flag returns the `clue-flag` or a descendant. The `clue-text` of IDES has the same box as on a snapshot without the flag (1 px).
- **AC-15** (new; refines spec 006 AC-2) (browser with mocked socket) Each arrow is drawn in its word's first letter cell. On a FX-01 snapshot: no clue cell holds a `clue-arrow`; for each of the 8 clues, exactly one `clue-arrow` has its `data-clue-row`, `data-clue-column` and `data-clue-index`, with the clue's `data-arrow`, and it is an `svg` child of the cell where the word starts ((1, 0) for `0,0,0`, (0, 1) for `0,0,1`, (1, 2), (1, 3), (1, 4), (2, 1), (3, 1), (4, 1)), with `aria-hidden="true"`, `viewBox="0 0 24 24"`, computed `pointer-events` `none`, `z-index` `6`, a box of side `a = max(9, 0.26 s)`, one `path` and one `polygon` with the `d` and `points` of the table for its arrow, the path's computed `stroke` rgb(20, 24, 31), `stroke-width` `2.4px`, `stroke-linecap` and `stroke-linejoin` `round` and `fill` `none`, the polygon's `fill` rgb(20, 24, 31), and a computed `filter` of two `drop-shadow` functions, each of rgb(255, 255, 255) with offsets 0 and blur `0.8px`. Positions in the target cell: the ↳ in (1, 0) has its top at `T - 1` and its left at `L + 0.06 s`; the ↴ in (0, 1) its left at `L - 1` and its top at `T + 0.06 s`; each ↓ its top at `T - 1` and its horizontal centre at `L + 0.5 s`; each → its left at `L - 1` and its vertical centre at `T + 0.5 s`.
- **AC-16** (new) (browser with mocked socket) Two arrows in one cell never meet. Three hand-built views, each at 1280 by 720: view A, width 2 and height 3, (0, 0) a clue cell with clue 0 `{"text": "Un", "arrow": "right"}` and clue 1 `{"text": "Deux", "arrow": "right_then_down"}`, (1, 0) and (2, 0) empty, (0, 1), (1, 1), (2, 1) letters: in (0, 1), the → has its vertical centre at `T + 0.72 s` and the ↴ its top at `T + 0.06 s` and its left at `L - 1`. View B, width 2 and height 1, (0, 0) a clue cell with two clues `right` (`Un`, `Deux`), (0, 1) a letter: in (0, 1), the → of clue 0 has its centre at `T + 0.25 s` and that of clue 1 at `T + 0.72 s`. View C, width 3 and height 3, (0, 1) a clue cell with one clue `{"text": "Est", "arrow": "down_then_right"}`, (1, 0) one with `{"text": "Sud", "arrow": "right_then_down"}`, (1, 1), (1, 2), (2, 1) letters, the other cells empty: in (1, 1), the ↳ has its left at `L + 0.4 s` and its top at `T - 1`, and the ↴ its left at `L - 1` and its top at `T + 0.06 s`. In each view the two arrow boxes of the cell overlap by at most 1 px on one axis.
- **AC-17** (new) (browser with mocked socket and mocked catch-up) The marks of one cell are drawn in the design's order. With `seen_seq` 5 stored, a FX-01 snapshot at `seq` 9 with `p2` to `p5` (colours 1 to 4) selecting (0, 1) `down` and (0, 1) holding `N` revealed, and the catch-up `CatchUp(after_seq=5, until_seq=9, cells=(CellRef(row=0, column=1),), lines=(), names=())`, after a tap on (0, 1): (0, 1) has `background-color` rgb(207, 221, 243) and `outline` `2px` `solid` rgb(27, 47, 85) with `outline-offset` `-2px`; it holds the triangles of `p2` `top-left`, `p3` `top-right`, `p4` `bottom-right`, `p5` `bottom-left`, its `reveal-mark`, its `catch-up-mark` and the ↴ `clue-arrow`. With the hit-test style: at the point of the ↴'s path `6/24 a` right of and `5/24 a` below the arrow box's top-left corner, inside `p2`'s triangle, `elementFromPoint` returns the `clue-arrow` or a descendant; at the point 1.5 px inside both edges of each of the corners `top-right`, `bottom-right` and `bottom-left` of the inner box (inside the ring's band and the triangle), it returns that corner's `remote-selection` or a descendant, never the `catch-up-mark`; at the notch's horizontal centre, 1.5 px above the inner box's bottom, it returns the `reveal-mark`.
- **AC-18** (new) (browser with mocked socket) On small cells every mark keeps its minimum size. At 568 by 320 in the desktop context, on a FX-02 snapshot where L, the first letter cell in row-major order, holds `A` revealed and is selected by `p2` (colour 1, in L's across word if it has one, else down), and `p2` flags clue 0 of C, the first clue cell in row-major order: the test first reads `s` and fails, reporting it, unless `s` is below 20. Then L's `reveal-mark` is 7 by 4 px, `p2`'s triangle is `max(6, round(0.3 s))` px, every `clue-arrow` is 9 by 9 px, C's `clue-flag` is 8 by 8 px, and every `clue-text` has a `font-size` of `6px`. After a click on `access-switch`, `p2`'s icon box is 6 by 6 px, 1 px from its corner's edges.
- **AC-19** (new) (browser with mocked socket) The two switches are controls that every player can reach and that keep the grid's room. On a FX-01 snapshot: `room-menu` (spec 043) holds `authors-switch`, `others-tint-switch` and `access-switch` in this order, as its first three items, each a `BUTTON` with `type="button"`, an `aria-pressed` attribute, never disabled, whose label (the item's text without its `aria-hidden` detail) is `fr.json["others_tint.switch"]` and `fr.json["access.switch"]` for the two of this spec; with accounts on (spec 033), both come before `account-open`. Keyboard only (spec 035's harness, no tap): with the Menu opened from the keyboard (`tab_to` `menu-button`, `Enter`), `Tab` gives each switch the focus with spec 035 AC-2's outline, and `Enter` flips its `aria-pressed` and leaves the Menu open. Layout: in spec 024 AC-8's setup, at every window size of spec 006 AC-5, in desktop and touch contexts, with the Menu open, spec 013 AC-6's checks pass, both switches lie inside the window, and `elementFromPoint` at the centre of each, after `scrollIntoView({block: "nearest"})`, returns the switch. (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout; this read "toolbar controls", "`room-toolbar` holds `authors-switch`, `others-tint-switch` and `access-switch` in this relative order", "with the texts", "`tab_to` each switch" and "both switches meet spec 024 AC-8's toolbar rules (one row with the other buttons on the four small windows; with the keyboard focus, inside the toolbar's client area with an outline that passes "Not clipped"; `elementFromPoint` at the centre after `scrollIntoView` returns the switch)".)
- **AC-20** (new) (browser with mocked socket; static) The new cells keep the text contrast and the language of spec 035. In the state of AC-17 without the catch-up (no `seen_seq`), plus `p2`'s flag on IDES and (1, 1) holding `X` wrong, at 1280 by 720 and at 360 by 740, once with `access-switch` off and once on, spec 035's contrast scan (AC-8) and language scan (AC-9) find no offending element. Static: `web/src/i18n/fr.json` holds `others_tint.switch` and `access.switch` with the values of "`fr.json` keys", and none of `grid.remote_overflow`, `a11y.remote_overflow` and `flag.marker`.

## Edge cases and errors

- Flash on my selected cell (AC-2): the flash row comes first, so the cell's own
  background is white under `cell-flash` (spec 041 AC-16 already taps the cell
  before the flash).
- Two other players' words on one cell (AC-2): the tint is that of the first in
  roster order, as spec 013 says; with the tint off neither shows.
- Tint off and my word (AC-3): my own word and cell keep their look; only the
  others' tint goes. The `data-tinted-by` attribute stays, so spec 013's data does
  not depend on a display choice.
- A player selects a cell where four others already are (AC-10): they get no
  corner and are not drawn; nothing on the cell says so. Where each player is
  stays in words in the Joueurs list of step 3.
- A player's direction change on the same cell (AC-10): not an arrival; they keep
  their corner.
- A reconnection snapshot (AC-10): players still on the same cell keep their
  corners, so a reconnection does not reshuffle a crowded cell.
- A player who leaves the room and a new player who joins with the same colour
  (AC-9, AC-11): the corner follows the player id, the colour and the icon follow
  `data-colour`.
- Triangles and icons on tiny cells (AC-18): the minimums can make four icons
  touch the letter on cells of about 18 px; accepted, as players zoom (spec 006,
  `_design.md` section 6).
- Triangles and the notch (AC-17): the notch is bottom-centre and the bottom
  triangles end `t` from their corners, so they do not overlap from 20 px cells;
  below, they may touch, the notch being drawn over.
- Arrows and the selection border (AC-17): the arrow box starts on the grid line,
  so its tail passes under the 2 px border; the border is drawn over it (see
  Decision 10).
- Arrow targets (AC-15): spec 003 refuses an arrow whose word starts outside the
  grid or on a clue cell, so every clue of a valid grid has its arrow; a
  hand-built view with such a clue simply draws no arrow for it.
- Taps on an arrow (AC-15): the arrow is in the letter cell and has
  `pointer-events: none`, so a tap there selects the letter cell (spec 007), where
  it used to land in the clue cell.
- Long clue text (AC-12): one size in every clue cell, larger than today's
  two-clue size (0.145 s against 0.09 s); spec 006 AC-1 still requires no cut at
  full zoom, so the implementer may raise `data-zoom-max` (spec 006 decision 3).
  At zoom 1 a two-clue cell of about 29 px may not hold its text; clue cells do
  not clip, and players zoom (`_design.md` section 15, sheet notes).
- Capitals by CSS (AC-12): the text node keeps the clue as written, so spec
  035's language scan and the tests that read `textContent` see `Passoire fine`;
  `innerText` may show the capitals in some engines.
- The flag over the clue text (AC-14): it may cover the first letters of a long
  first line; it never moves the text. Top-left is the one corner no arrow uses.
- Pencil letters (spec 020): unchanged, italic in `--nock-pencil`, ink during a
  flash (spec 041); `cell-letter` inherits them.
- Auteurs mode (step 5): spec 019's band stays until then, above the ring and
  under the triangles, whose bottom corners may cover its ends.
- Letter centring and spec 019's baseline rule: `text-box` moves the capital up
  by about half its descent, so the baseline rises and the band's rule gets
  easier; in Firefox nothing changes.
- A `localStorage` that throws (private mode): the switches start at their
  defaults and still flip for the page's life.

## Out of scope

- The room layout: top bar, Menu (where the two switches move), Salon and its
  Joueurs list with the current clue, clue bar in navy, 3-second notes, the
  reaction pill's look and the picker (step 3, `_design.md` sections 8 and 11).
- The in-app keyboard's ✎ and ⇄ keys (step 4).
- Auteurs mode and its inks, the end band, the recap's dots, the catalogue's grid
  drawing (step 5). In this spec the Accessibilité icons replace the dot in the
  roster swatch only.
- A hidden text naming the players on a crowded cell (decided against, Open
  question 3).
- Screenshot comparison with the sheet (`_design.md` section 13, a human
  decision).
- A dark mode, forced-colours styles, print styles.

## Work packages

None.

## Decisions

Decided by the lead on 2026-10-22, on the human's instruction of 2026-10-22 ("the
game is now to be implemented on the full design system provided; competitive
modes wait"), for the human to override at approval:

1. The revealed notch (`_design.md` section 15, the deferred high item): the
   design's size, `max(7px, 0.22 s)` by `max(4px, 0.11 s)`, wins over spec 024
   AC-9's minimum (at least 6 px and a quarter of the side). Spec 024 AC-9 is
   refined to it. The notch and the bold letter on locked grey remain the
   non-colour signs of a revealed letter, with spec 024's hidden label.
2. The spec writer's picks of `_design.md` section 15 "Still open" are accepted:
   item 2, the revealed notch in ink during a flash (orange-red falls to 2.1:1 to
   2.8:1 on the Orange, Cramoisi and Magenta flashes); item 8, a reaction on a
   two-clue cell centred on its own clue's half, as spec 022 does today (nothing
   changes in this spec); and items 5, 6, 7, 9, 10 and 11, which concern later
   steps.

Proposed by the spec writer, each already part of the spec above:

3. Arrows move into the target letter cell's DOM (`clue-arrow` with
   `data-clue-row`, `data-clue-column`, `data-clue-index`). Drawn from the clue
   cell, an arrow would sit in another stacking context than the letter cell's
   marks and my selection border, and the design's order (arrows over triangles,
   under the border) could not hold. Spec 006 AC-2's geometry holds unchanged.
4. Corners by arrival: a newcomer takes the first free corner in the design's
   order; a freed corner goes to the player who has waited longest; a snapshot
   brings players in roster order and keeps the corners of players who stayed. This
   is the human's arrival rule with the fewest cases: no corner ever moves while
   its player stays (Open question 1).
5. The icon of a player is `PLAYER_ICONS[colour index]`, as the design says "by
   join index (as the colours)": the icon follows the colour, so a player's
   triangle, icon and swatch always agree.
6. In Accessibilité mode the roster swatch shows the icon (`_design.md` section
   6, "Elsewhere"), so the icons have a legend from this step on.
7. The initials, the `+k` label and its hidden text go, with their keys
   (`_design.md` section 6: "no text, ever"). Spec 035 AC-6 and AC-11 are refined
   as the human decided on 2026-10-16: the non-colour sign is the Accessibilité
   mode plus the Joueurs list.
8. The flag is the drawn icon (`ICONS.flag`), never the `⚑` glyph, which the
   fonts do not have (`_design.md` section 5); `flag.marker` goes.
9. The letter is a `cell-letter` element for `text-box`, but the cell keeps the
   letter's font, colour and strike, which `cell-letter` inherits or which
   decorates its text. So the checks of specs 019, 020, 023 and 035 that read the
   cell's computed `color`, `font-weight`, `font-style` and `text-decoration-line`
   keep reading the same values.
10. My selection border stays the cell's `outline`, which spec 035 AC-2 reads.
    The reviewer checks in the three engines that it shows over the arrows; if an
    engine paints an outline under its element's positioned children, the
    implementer may draw the same 2 px navy border a second time as an
    `aria-hidden` element at `z-index: 7` with `pointer-events: none`, the outline
    staying.
11. The two switches go in today's room toolbar, after `authors-switch`, until
    step 3 moves them into the Menu (Open question 2). The Accessibilité mode
    must ship with this step: it is the non-colour sign that replaces the
    initials.
12. Locked beats "in my word", as the design's table says; today the word blue
    covers a locked cell of my word, and its bold letter is then the only sign.

## Open questions

The pick of each is already in the spec above; the human may change it at
approval.

1. A fifth player on a crowded cell. Options: never drawn until they move again;
   or take the first corner that frees, the longest-waiting first. Pick: take the
   freed corner (Decision 4), so the cell always shows four cursors while four or
   more are on it.
2. Where the « Mots des autres » and « Accessibilité » switches live before the
   Menu exists (step 3). Options: in today's room toolbar; or only from step 3,
   with no way to turn them on until then. Pick: the toolbar (Decision 11), as
   spec 019's `authors-switch`; without it the step would remove the initials
   with no non-colour sign to replace them.
3. A text for screen readers naming the players on a cell. Options: keep a
   visually hidden list per cell; or none, the Joueurs list saying where each
   player is. Pick: none, as the design's "no text, ever" and spec 035's
   "Out of scope" (no announcement of other players' moves).
