# Grid cells

The cells of the playing grid, drawn in `docs/design/cell-sheet.html`. Units
(`s`, `max(…)`), tokens and the grid's type: `foundation.md`.

## Grid lines and empty cells

The grid container has a 1 px rule-grey left and top border; each cell has a
1 px rule-grey right and bottom border, inside its side `s`. No gap between cells.
Cells clip their content (`overflow: hidden`), except clue cells (« Clue cells »).
The grid container itself clips at its outer edge (`overflow: clip`): a clue text
may spill over neighbouring cells, never past the grid's box.

An empty cell (the grid's `empty` type) is filled with `--nock-rule`.

The one edge that is not a plain line is the hyphen of a compound word
(« Hyphen edges »).

## Hyphen edges

A word's break takes no cell (`content/grids.md`, rule 4): the edge between the
two letters it joins is dashed instead of the plain grid line. Every break is
drawn so, whatever its separator: a compound word's hyphen, an abbreviation's
dot, a space or an apostrophe (`A.I`, `A I` and `A-I` look the same). Across,
it is the right edge of the letter before the break (the cell's `hyphen_right`
mark, `platform/realtime.md`); down, its bottom edge (`hyphen_down`). The rule-grey
line of that edge is not drawn; in its place, dashes in `--nock-hyphen`, the same
in every state of the two cells: no one selecting the word, my word, another
player's tint, my word beside another's triangles, a crossing word selected,
locked, revealed, checked wrong, catch-up ring, flash, Auteurs mode, pencil
letters.

Geometry, along the edge of length L = s − 1 px (the cell's inner side, up to the
crossing grid line, which stays plain), with s the cell side at the current zoom:

- thickness t: 1 px while s < 36, 2 px from 36, 3 px from 72. Centred on the grid
  line's pixel: t = 1 on it; t = 2 on it and the next pixel into the following
  cell; t = 3 one pixel on each side of it;
- n dashes, n = max(3, round(L / p)) with p = 5, 8, 11 px for t = 1, 2, 3; the
  period is L / n. Dash i (from 0) runs from round((i + 0.2) · L / n) to
  round((i + 0.8) · L / n) from the edge's start: each dash is about 60 % of its
  period, with half a gap at each end, so the corners stay open and the edge
  never merges into the crossing lines;
- the edge's start and every dash end lie on whole CSS pixels, whatever the cell
  size (fractional at zoom 1, `gameplay/board.md`) or the pinch zoom: along the
  edge every pixel is `--nock-hyphen` or the cells' background, none blended.

| Cell side | t | Dashes | Each about |
| --- | --- | --- | --- |
| about 6 px (FX-02 at 568 by 320 on a touch phone, keyboard shown) | 1 px | 3 | 1 px, 1 px gaps |
| about 12 px (FX-02 at 568 by 320 on a computer) | 1 px | 3 | 2 px |
| 18 px (FX-02 on a 320 by 568 phone) | 1 px | 3 | 3 px |
| 56 px (a computer) | 2 px | 7 | 5 px |
| 90 px (a phone at zoom 5) | 3 px | 8 | 7 px |

Contrast (`foundation.md`, « Colour tokens »): 5.86:1 on white, 4.26:1 on my
selected cell, at least 4.4:1 on every word, tint and locked background; 2.93:1 on
the darkest flash, accepted for the flash's 1 s.

My selected cell beside the edge: my selection border turns dashed on that side.
The band from the border's inner edge to the grid line, 3 px (the border's 2 px
plus the line's pixel), carries the same dashes in `--nock-navy` (9.65:1 on
selected), its gaps in `--nock-selected`; the three other sides stay solid. So the
hyphen never hides under the border, which is drawn over every mark.

Layers: the dashes replace the grid line and sit where it sat, over the
backgrounds and the flash overlay, under every mark of the two cells (« Drawing
order »): the catch-up ring, the triangles and icons, the arrows keep their places,
and the revealed notch of the cell above a down hyphen sits over its dashes, its
base on the edge. No arrow ever lies on a hyphen edge: an arrow's edge faces its
clue cell. The dashed side of my selection border is on top, like the rest of the
border.

Drawn in the cell sheet, « 4b · Compound words », and in the screens sheet, part 3,
« Compound words ».

## Letter cell backgrounds

Exactly one background applies, the first that matches in this list:

| State | Background |
| --- | --- |
| Flash (`gameplay/co-op.md`), 1,000 ms | white with the replacer's `--player-colour-N` at 38 % over it |
| My selected cell | `--nock-selected` |
| Locked (checked right, or revealed) | `--nock-locked` |
| In my selected word | `--nock-word` |
| In another player's selected word, while « Mots des autres » is « teintés » | `color-mix(in srgb, var(--player-colour-N) 16%, var(--nock-white))` |
| Otherwise | `--nock-white` |

Another player's word tint: each player turns it on or off from the Menu item
« Mots des autres » (« teintés » / « sans teinte »), remembered per browser, on by
default. When a cell is in the words of two other players, the tint is that of the
one who comes first in join order.

My selection border: 2 px solid navy drawn inside the cell, over every other mark
of the cell. It is the cell's own outline (`outline: 2px solid var(--nock-navy)`,
`outline-offset: -2px`), which the visible-focus baseline of `product.md` reads.
It is the only cell border besides the grid lines and the catch-up ring. Its side
on a hyphen edge is dashed (« Hyphen edges »).

## Letter marks

| Mark | Look |
| --- | --- |
| Normal letter | ink, weight 500 |
| Locked | weight 700 on locked grey |
| Pencil | italic, `--nock-pencil`; during a flash, ink and italic (italics are the only sign) |
| Wrong after a check | `text-decoration: line-through`, thickness max(2px, 0.07em), colour `--nock-red`; ink in Auteurs mode |
| Revealed | locked (bold, locked grey) plus the notch below |

Revealed notch: an isosceles triangle in `--nock-reveal`, pointing up, centred on
the middle of the bottom edge and flush with it. Base max(7px, 0.22 s), height
max(4px, 0.11 s). Corners belong to players, and no arrow ever enters a cell from
the bottom, so nothing else uses that spot. During a flash the notch is drawn in
`--nock-ink`, so it keeps 3:1 on every player colour (the cell sheet's
`.flash.rev::after`). The notch, the bold letter on locked grey and the letter's
hidden label are the non-colour signs of a revealed letter.

## Catch-up ring

A cell that changed while I was away gets a 3 px solid `--nock-ink` ring on its
edge (`inset: 0`, inside the cell), for 5 s, `pointer-events: none`. It is drawn
over the letter and its background and under the player triangles, the notch and
the arrows (the sheet's z-index 1). The matching lines go in the stream (`room.md`,
« Salon »).

## Other players on a cell

A plain right triangle in one corner of the cell, legs along the two edges, each
leg t = max(6, round(0.3 s)) px, filled with the player's `--player-colour-N`, no
outline, no text, ever. Corners are given in the order players arrive on the cell:
top-left, top-right, bottom-right, bottom-left. When a player leaves the cell, the
others keep their corners. At most 4 are drawn; a fifth or later player is not
drawn and nothing says "+k"; a freed corner goes to the player who has waited
longest. A disconnected player is not drawn. My own selection is never a triangle.
No screen-reader text names the players on a cell.

Accessibilité mode: a switch in the Menu, « Accessibilité » (« activée » /
« désactivée »), off by default, remembered per browser like the other Menu
switches. While it is off, the triangles carry colour only, by the human's choice;
the Joueurs list of the Salon (name, state, current clue) says in words where each
player is. While it is on, each triangle is replaced by a small icon, one distinct
icon per player by join index (as the colours), drawn in that player's
`--player-colour-N`, in the same corners and the same arrival order, at most 4.
Colour is then no longer the only sign.

### Player icons

Drawn in the cell sheet (`PICONS`, `ICON_NAMES`, `picon()` and the access branch of
`corners()`). Each icon is filled with its player's `--player-colour-N`, with no
outline, in an SVG `viewBox="0 0 10 10"`:

| Index | Name | Shape |
| --- | --- | --- |
| 0 | Rond | `<circle cx="5" cy="5" r="4.4"/>` |
| 1 | Carré | `<rect x="0.9" y="0.9" width="8.2" height="8.2"/>` |
| 2 | Triangle | `<polygon points="5,0.4 9.7,9.3 0.3,9.3"/>` |
| 3 | Losange | `<polygon points="5,0.1 9.9,5 5,9.9 0.1,5"/>` |
| 4 | Étoile | `<polygon points="5,0.2 6.3,3.6 9.9,3.7 7.1,6 8.1,9.6 5,7.5 1.9,9.6 2.9,6 0.1,3.7 3.7,3.6"/>` |
| 5 | Croix | `<polygon points="3.3,0.4 6.7,0.4 6.7,3.3 9.6,3.3 9.6,6.7 6.7,6.7 6.7,9.6 3.3,9.6 3.3,6.7 0.4,6.7 0.4,3.3 3.3,3.3"/>` |
| 6 | Cœur | `<path d="M5 9.4L1.1 5.5A2.45 2.45 0 0 1 5 2.3A2.45 2.45 0 0 1 8.9 5.5Z"/>` |
| 7 | Sablier | `<polygon points="0.6,0.6 9.4,0.6 5.6,5 9.4,9.4 0.6,9.4 4.4,5"/>` |

Geometry in a letter cell: the icon's box has side max(6px, 0.24 s) and sits
inset from its corner by max(1px, 0.04 s) on both axes; same corners and arrival
order as the triangles (top-left, top-right, bottom-right, bottom-left), at most
4; same layer as the triangles (2), so under the notch, the arrows and my
selection border. The colours are the triangles', so each icon keeps at least
3:1 on my selected cell (`foundation.md`, « Player colours »). At 18 px cells four
icons fit but touch the letter; this is accepted, as players zoom.

Elsewhere: wherever a player dot appears (stream messages, the Joueurs list, the
recap's « Qui a fait quoi »), the mode shows that player's icon at 12 px instead of
the dot. The Auteurs legend names players in their ink with no dot; it does not
change.

## Clue cells

- Background `--nock-clue-bg`, text `--nock-clue-ink` (`foundation.md`,
  « Typography »), padding 2 px top and bottom, 3 px left and right. Clue cells do
  not clip (`overflow: visible`); the grid container clips at its edge.
- One clue fills the cell, centred vertically. Two clues share it in two equal
  halves, clue 0 on top, with a 1 px separator between them in clue ink at 55 %
  opacity, inset 14 % of the cell width on each side.
- At about 29 px cells (a tablet with the keyboard shown) a two-clue cell does not
  hold its text: players zoom or hide the keyboard.
- Active clue: the half (or the whole cell for a lone clue) that holds my selected
  word's clue takes `--nock-selected`, radius 2 px.
- Flag: the filled red flag icon (`foundation.md`, « Icons »), in a square of side
  max(8px, 0.22 s) at the top-left of its own clue's half (top 0 of the half, left
  −2 px, so 1 px from the cell's left edge), on a clue blue-grey backing with a
  3 px bottom-right radius, the icon at 86 % of the square, fill and stroke
  `--nock-red`, stroke width 2, layer 2. A flagged second clue has its flag at the
  top-left of the lower half. The flag never moves the text. Top-left is the one
  corner of a clue no arrow uses.
- Shown reaction: `room.md`, « Reactions ».

## Direction arrows

Drawn in the letter cell where the word starts, next to its clue, as in printed
grids; never in the clue cell. SVG `viewBox="0 0 24 24"`, box side
a = max(9px, 0.26 s), stroke ink, stroke width 2.4 (in the 24-unit box), round caps
and joins, no fill on the path, the head a filled ink polygon. A thin white halo
lets it read over any mark: `filter: drop-shadow(0 0 0.8px #FFFFFF)
drop-shadow(0 0 0.8px #FFFFFF)` (white is `--nock-white`).

| Arrow | Kind (`content/grids.md`) | Path | Head |
| --- | --- | --- | --- |
| → | right | `M2 12H15` | `14,7.5 22,12 14,16.5` |
| ↓ | down | `M12 2V15` | `7.5,14 12,22 16.5,14` |
| ↳ | down then right | `M5 2V10Q5 15 10 15H15` | `14,10.5 22,15 14,19.5` |
| ↴ | right then down | `M2 5H10Q15 5 15 10V15` | `10.5,14 15,22 19.5,14` |

Position of the box in the letter cell (as `arrowFor()` and `arrowMap()` in the
cell sheet). An arrow's target cell is the cell right of its clue cell for → and
↴, the cell below for ↓ and ↳; an arrow whose target is outside the grid or a clue
cell is not drawn.

| Arrow | Box position |
| --- | --- |
| → (default) | left −1 px; vertical centre at 0.5 s |
| ↓ | top −1 px; horizontal centre at 0.5 s |
| ↳ (default) | top −1 px; left 0.06 s |
| ↴ | left −1 px; top 0.06 s |

Collision rules, applied per target cell (drawn in the cell sheet's « Two arrows in
one cell »):

1. A → whose target cell also receives a ↴: the → takes the low slot, vertical
   centre at 0.72 s; the ↴ keeps the top.
2. Otherwise, when two → share a target cell (only possible from one two-clue
   cell), the → of clue 0 is centred at 0.25 s and the → of clue 1 at 0.72 s.
3. A ↳ whose target cell also receives a ↴: the ↳ moves right, to left 0.4 s (top
   −1 px); the ↴ keeps the top-left corner.

The −1 px puts the box's edge on the grid line; the clipped column holds no
stroke (strokes start at 2 units). On 68 px cells every arrow keeps at least
2.7 px from every letter A to Z.

## Drawing order

Top first, inside one cell (the sheet's z-index in brackets):

1. My selection border (7; the cell's outline).
2. Direction arrows (6).
3. Revealed notch (3).
4. Player triangles (2), and in clue cells the flag (2).
5. Catch-up ring (1).
6. The letter, or the clue text.
7. The dashes of a hyphen edge (« Hyphen edges »), in place of the grid line.
8. The flash overlay, then the background.

A shown reaction (8) sits over its clue cell and the cells around it (`room.md`,
« Reactions »).

## One cell with every mark

A selected, revealed letter cell at s = 64, entered by ↴, with four players:

```
+------------------------------------------+  <- 2 px navy border (my selection)
|\ P0                                  P1 /|     P0..P3: player triangles,
| \                                     / |     legs 19 px, arrival order
|  \                                   /  |     TL, TR, BR, BL
|-->+  <- ↴ box (17 px, top 0.06 s)       |
|   |                                     |
|   v          #   #                      |  <- letter N, 36 px, weight 700,
|              ##  #                      |     ink on locked grey
|              # # #                      |
|              #  ##                      |
|  /           #   #                   \  |
| /                 /\                  \ |  <- revealed notch, 14 x 7 px,
|/ P3              /__\              P2  \|     orange-red, bottom centre
+------------------------------------------+
```

Background: selected blue (selected beats locked). Paint order as above.

## Auteurs mode

Each player turns it on or off; off by default.

- A switch in the Menu (`room.md`, « Menu »): « Auteurs » with the detail
  « activé » or « désactivé », remembered per browser, as the tint switch.
- When on, each letter is drawn in its finder's ink `--player-ink-N`
  (`foundation.md`, « Player colours »), on whatever background the cell has.
- A revealed letter has no finder: it stays ink.
- A letter whose finder has left the room is drawn in plain ink (`--nock-ink`), as
  a letter with no finder.
- A pencil letter keeps its italics, in its finder's ink.
- The wrong-letter strike turns ink (a red strike would vanish on a red letter).
- A legend shows while the mode is on: « Auteurs : » then each player's name in
  their ink, weight 700, in join order, 8 px apart. It is the only key to the inks:
  no other sign of a letter's author. Background `--nock-legend-bg`, 1 px line-grey
  border, radius 14 px, padding 4 px 12 px, gap 8 px.
- The legend sits in the flow under the grid, centred, 8 px below it (the grid and
  legend form one column with an 8 px gap). The grid gives it max(38, h + 8) px of
  its height, `h` the legend's height (38 px for one line), the space under the
  grid rounded down to a quarter pixel, so nothing else moves. A long legend wraps,
  each line centred, its lines 2 px apart. It is never wider than the clue bar (nor,
  on a phone, than the grid area less its 8 px sides), a width the mode does not
  change, so its wrapping never narrows the grid. It is centred on the grid area,
  the grid's centre at zoom 1, and on the viewport when the grid is zoomed.
- Where giving the legend its room would leave the grid's viewport under 100 px
  high, on a phone or a computer, for example at 568 by 320 with the keyboard shown,
  the legend takes no room: the grid keeps its size, and the legend lies over the
  bottom of the grid's viewport, centred, its bottom 8 px above the viewport's
  bottom edge, on layer 6 (`room.md`, « Layers »), with its own background and
  border, and lets taps through to the cells under it. It covers only the grid's
  bottom, never the clue bar, the top bar, the status, the keyboard or the Salon.
  Hiding the keyboard gives the room back. Drawn in the screens sheet, part 9,
  « Auteurs » mode, the 568 by 320 frame.
- The clue bar shows only the clue, never a letter's author.
- During a flash the letters keep their inks; their contrast on the flash is not
  guaranteed.
