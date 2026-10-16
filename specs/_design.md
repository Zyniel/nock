# Visual design

Not a spec: the quality gate ignores files starting with "_". Every spec that puts
something on screen follows this note, as every "Public interface" follows
`specs/_architecture.md`. Decided with the human on 2026-10-16, from the design
session whose result is the page `docs/design/cell-sheet.html` (version 4.1,
published as https://claude.ai/artifact/VCuP9WSmsdXA7JJEvb9ixV).

Values are CSS values. `s` is the side of a grid cell in CSS px, its right and
bottom grid line included (the cell is `box-sizing: border-box`). "max(7px, 0.22 s)"
means the larger of 7 px and 22 % of `s`. `rem` is the root font size (16 px by
default). Items marked OPEN wait for the human (section 15).

## 1. Purpose and authority

This file and `docs/design/cell-sheet.html` are the visual reference of the web
client. Where they differ, this file wins, and the difference is listed in
section 15 or fixed in the sheet.

Rules:

1. Every spec that puts something on screen cites the sections of this file it
   applies, in its "Public interface", and has acceptance criteria that check the
   values that matter: computed colours, sizes and positions at a known cell size or
   window size, paint order, and which elements are present or absent.
2. No spec and no code introduces a colour, a font, a font size, a radius, a
   shadow or an icon that is not listed here. Colours are used only through the
   tokens of sections 2 and 3.
3. A change of look starts here. The spec writer updates this file (and the sheet
   when the change is visible in it), with a dated note next to the change, before
   any spec, test or code changes.
4. Where an existing `approved` or `done` spec contradicts this file, this file
   describes the target and the spec is refined to match (section 12 lists them).
   Until a spec is refined, it wins for its own tests, and the code keeps passing
   them.
5. Grid letters are the 26 capitals `A` to `Z`, never accented, in examples too.

## 2. Colour tokens

Each colour is a CSS custom property declared once, in the `:root` block of
`web/src/app.css` (the token block). Code uses `var(--nock-...)`, never the value.
Ratios are WCAG 2.x contrast against white (#FFFFFF).

| Token | Value | Its one job | Never for | On white |
| --- | --- | --- | --- | --- |
| `--nock-navy` | #1B2F55 | The app's colour: top bar, top-bar icons and labels, clue bar, primary buttons, my selection border, focus ring, links, headings | Player marks | 13.26:1 |
| `--nock-ink` | #14181F | All text and grid letters, direction arrows, 3-second notes (background), scrim and shadow base | Backgrounds of cells | 17.79:1 |
| `--nock-muted` | #5E6573 | Secondary text: captions, event lines in the stream, disabled labels, menu details, inactive tabs | Grid letters | 5.86:1 |
| `--nock-pencil` | #555B67 | Pencil letters (italic), letter keys in pencil mode | Any other text | 6.82:1 |
| `--nock-white` | #FFFFFF | Page, letter cells, menus, sheets, dialogs; text and icons on navy, ink and red | - | 1:1 |
| `--nock-clue-bg` | #EEF2F8 | Clue cells, disabled buttons, the "not yet" status band | Selection | 1.12:1 |
| `--nock-clue-ink` | #1B2230 | Clue text in clue cells, the separator between two clues | Any other text | 15.97:1 |
| `--nock-word` | #E6EDF9 | My selected word, hovered menu item, pressed top-bar button, quiet buttons, pressed filter chips, progress bar track | Player tints | 1.18:1 |
| `--nock-selected` | #CFDDF3 | My selected cell, and nothing else | Anything else | 1.37:1 |
| `--nock-locked` | #E3E7EE | Locked letter cells (with bold letters) | Disabled states | 1.24:1 |
| `--nock-rule` | #9AA3B2 | Grid lines, input borders, catalogue thumbnail border | Text | 2.54:1 (OPEN: 3:1) |
| `--nock-line` | #DDE2EA | Dividers in menus, panels and cards; card borders; filter chip borders; disabled button border | Grid lines | 1.30:1 |
| `--nock-red` | #B42318 | "Look here": wrong-letter strike, ⚑ flag, unread badges, error text | Decoration | 6.57:1 |
| `--nock-reveal` | #C2410C | "Revealed", and nothing else: the revealed notch, the reveal line in the stream | Anything else | 5.18:1 |
| `--nock-green` | #1E7B45 | "Done": finished-grid band text, passed-check line in the stream, "Terminée" pill text | Player marks | 5.28:1 |
| `--nock-green-bg` | #E6F2EA | Background of the finished-grid band and of the "Terminée" pill | Anything else | 1.15:1 |
| `--nock-key` | #E9ECF1 | In-app keyboard keys | - | 1.18:1 |
| `--nock-keyboard-bg` | #D9DEE6 | In-app keyboard background | - | 1.35:1 |
| `--nock-departed` | #6B7079 | Auteurs mode: letters of a player who has left (OPEN: fails 4.5:1 on blue) | Anything else | 4.98:1 |
| `--nock-handle` | #C5CCD8 | Grab handle of a bottom sheet | - | 1.62:1 |
| `--nock-thumb` | #C9D2E0 | Clue cells of a catalogue thumbnail, force notches above the grid's force | - | 1.52:1 |

Translucent tokens, all built on ink or white (the sheet's `rgba(0, 0, 0, ...)`
shadows become ink, see section 15):

| Token | Value | Job |
| --- | --- | --- |
| `--nock-scrim` | rgb(20 24 31 / 35%) | Scrim under a menu, a popover or the Salon sheet |
| `--nock-scrim-dialog` | rgb(20 24 31 / 38%) | Scrim under the recap |
| `--nock-dot-ring` | rgb(20 24 31 / 55%) | 1 px ring around a player dot |
| `--nock-key-shadow` | rgb(20 24 31 / 25%) | 1 px shadow under a key |
| `--nock-shadow` | rgb(20 24 31 / 45%) | Shadow colour of menus, popovers, sheets and the vote banner |
| `--nock-shadow-strong` | rgb(20 24 31 / 50%) | Shadow colour of dialogs and 3-second notes |
| `--nock-legend-bg` | rgb(255 255 255 / 96%) | Background of the Auteurs legend |
| `--nock-pen-fill` | rgb(255 255 255 / 35%) | Fill of the ✎ icon on the pressed pencil key |

Rules:

- Navy is the app's own colour. Red means "look here". Orange-red means
  "revealed" and nothing else. Green means "done". A player colour (section 3)
  only ever means a player: triangles, word tints, flashes, dots, Auteurs ink;
  never a button, a state or a decoration.
- Text and icons reach 4.5:1 against their background, disabled buttons included.
  Marks, borders that carry meaning and the focus ring reach 3:1.
- No pure black (#000000) and no neutral grey: the neutrals lean toward the navy.
- No dark mode for now. Every colour is a named token, so one can be added later
  by redefining the tokens.
- Two colours may be mixed only with `color-mix(in srgb, ...)` over tokens, or by
  `opacity`, at the percentages this file gives: 16 % (word tint), 38 % (flash),
  55 % (clue separator), 80 % (direction glyph in the clue bar), 70 % (Je bloque
  not pressed, OPEN).
- `transparent` and `currentColor` are allowed everywhere.

Measured pairs (WCAG 2.x):

| Pair | Ratio | Needs |
| --- | --- | --- |
| Ink on selected | 12.95:1 | 4.5 |
| Ink on locked | 14.34:1 | 4.5 |
| Pencil on word / on selected | 5.80:1 / 4.97:1 | 4.5 |
| Pencil on key | 5.76:1 | 4.5 |
| Clue ink on clue blue-grey | 14.18:1 | 4.5 |
| Red ⚑ on clue blue-grey | 5.85:1 | 4.5 |
| White on navy | 13.26:1 | 4.5 |
| White on red (badge) | 6.57:1 | 4.5 |
| Muted on clue blue-grey (disabled button) | 5.22:1 | 4.5 |
| Muted on word blue (menu detail on hover) | 4.98:1 | 4.5 |
| Green on green background | 4.59:1 | 4.5 |
| Navy on word blue (pressed top-bar button) | 11.27:1 | 4.5 |
| Revealed notch on white / selected / locked / word | 5.18 / 3.77 / 4.17 / 4.40:1 | 3 |
| Navy selection border on selected | 9.65:1 | 3 |
| Departed grey on white / word / selected | 4.98 / 4.23 / 3.62:1 | 4.5 (OPEN) |

## 3. Player colours

Imposed by the human (2026-10-16), in join order: the room's first player gets
index 0. They replace today's values of `--player-colour-0` to `--player-colour-7`
in `web/src/app.css`. Each has an Auteurs ink, token `--player-ink-0` to
`--player-ink-7`. The triangle colour is used for corner triangles, word tints,
flashes, player dots and roster swatches; the ink only for letters in Auteurs mode
and for names in the Auteurs legend.

| Index | Name | Triangle `--player-colour-N` | On white | On selected | Ink `--player-ink-N` | Ink on selected |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Bronze | #604800 | 8.66:1 | 6.31:1 | #604800 | 6.31:1 |
| 1 | Vert | #608838 | 4.14:1 | 3.01:1 | #4B6A2C | 4.50:1 |
| 2 | Sarcelle | #008878 | 4.38:1 | 3.19:1 | #006D60 | 4.56:1 |
| 3 | Violet | #6838E0 | 6.50:1 | 4.73:1 | #6838E0 | 4.73:1 |
| 4 | Cramoisi | #B83850 | 5.65:1 | 4.11:1 | #AD354B | 4.51:1 |
| 5 | Magenta | #D000A0 | 5.01:1 | 3.65:1 | #B3008A | 4.66:1 |
| 6 | Orange | #B06000 | 4.65:1 | 3.38:1 | #904F00 | 4.63:1 |
| 7 | Brun | #784030 | 8.16:1 | 5.94:1 | #784030 | 5.94:1 |

How they were chosen (a search, not by eye), under these rules:

- each triangle reaches 3:1 on my selected cell (#CFDDF3), the darkest background a
  triangle can have outside a flash, with no outline;
- each ink reaches 4.5:1 on my selected cell; the ink is the triangle colour
  darkened toward black only as far as needed;
- no blue, so no player looks like my own selection;
- the worst pairwise colour difference (CIEDE2000), over normal vision and the
  protan, deutan and tritan simulations of Machado 2009 at severity 1, inks
  included with a weight, is at least 10.9 among players 0 to 3 and at least 7.1
  among all 8. The weakest pairs are Violet/Magenta (protan) and Orange/Vert
  (deutan). The old palette fell to 0.9.

The order puts the most distinct colours first, because most rooms have two to
four players. With five players or more, the player list in the Salon is the
reference. This supersedes the palette discussion of spec 019 (decisions 9 and 10
there): the human imposed these colours.

## 4. Typography

Families:

| Token | Stack | Used for |
| --- | --- | --- |
| `--nock-font-ui` | "Source Sans 3", "Segoe UI", system-ui, sans-serif | Interface text and grid letters |
| `--nock-font-clue` | "IBM Plex Sans Condensed", "Arial Narrow", "Roboto Condensed", sans-serif | Clue text in clue cells |

Faces served: Source Sans 3 at weights 400, 500, 600, 700 upright and 500, 700
italic; IBM Plex Sans Condensed at 500 and 600 upright. Nock serves the font files
itself from its own origin (privacy, spec 038; spec 005's rule against
third-party URLs); never from Google Fonts or another host. Adding the font files
is a dependency, so the human decides how (OPEN). The sheet's third family,
Source Serif 4, styles the sheet's own headings only and is not part of the app.

Grid:

- Letters: `--nock-font-ui`, size 0.56 s, line height 1, weight 500; locked
  letters weight 700 (spec 035 AC-7's bold rule). The capital is centred on its own
  cap height and baseline, not on the line box: `text-box: trim-both cap
  alphabetic` on the letter. An engine without `text-box` (Firefox today) centres
  the line box; the letter then sits about 0.5 px off, which is accepted.
- Clue text: `--nock-font-clue`, size max(6px, 0.145 s), weight 600, line height
  1.12, letter spacing 0.01em, uppercase (`text-transform`), centred. It wraps at
  word breaks (`overflow-wrap: break-word`, `hyphens: manual`) and is never cut and
  never ends with an ellipsis at full zoom (spec 006 AC-1). One size for one-clue
  and two-clue cells (see section 15 on the sheet's caption).

Interface sizes (all `--nock-font-ui`; `tabular` means
`font-variant-numeric: tabular-nums`):

| Element | Weight | Size / line height | Other |
| --- | --- | --- | --- |
| Page text | 400 | 16 px / 1.5 | ink |
| Top-bar label, phone | 500 | 0.68rem / 1 | navy, under the icon |
| Top-bar label, computer | 500 | 0.92rem / 1 | navy, beside the icon |
| Timer | 600 | 1.15rem / 1 | navy, tabular |
| Brand "Nock" | 700 | 1.3rem / 1 | navy, letter spacing 0.01em |
| Grid name (computer top bar) | 500 | 0.95rem / 1 | muted |
| Clue bar text | 500 | 0.95rem (15.2 px) / 1.2 | white; at least 14 px (specs 007 AC-4, 026) |
| Clue bar ‹ › | 400 | 1.2rem / 1 | white |
| Clue bar ⚑ | as text | 1rem | white |
| Key letter | 500 | 1.3rem / 1 | ink |
| Wide key | 500 | 1.1rem / 1 | ink |
| Button | 600 | 0.95rem / 1 | |
| Menu item | 500 | 1rem / 1.2 | navy |
| Menu group heading | 600 | 0.7rem / 1.2 | muted, uppercase, letter spacing 0.08em |
| Badge | 700 | 0.62rem / 1 | white on red |
| 3-second note | 500 | 0.85rem / 1.2 | white on ink |
| Auteurs legend | 500 (names 700) | 0.8rem / 1.2 | muted (names in inks) |
| Progress label | 600 | 0.85rem / 1 | navy, tabular |
| Salon tab | 600 | 0.95rem / 1 | muted, navy when selected |
| Stream message | 400 (name 700) | 0.92rem | ink |
| Stream event | 400 | 0.82rem (13.1 px) | muted, or orange-red / green (section 8) |
| Message box | 400 | 0.9rem | placeholder muted |
| Send pill | 600 | 0.85rem | navy on word blue |
| Player row | 400 (own name 700) | 0.95rem | state 0.85rem muted |
| Vote question | 600 | 0.95rem / 1.3 | ink |
| Vote seconds | 500 | 0.85rem / 1 | muted, tabular |
| Status band | 600 | 0.95rem / 1.2 | |
| Dialog title | 700 | 1.2rem / 1.2 | navy |
| Dialog section heading | 600 | 0.78rem / 1.2 | muted, uppercase, letter spacing 0.07em |
| Recap time | 700 | 2.1rem / 1 | navy, tabular |
| Recap lines and rows | 400 (names 600) | 0.95rem | values 0.85rem muted, tabular |
| Share URL box | 400 | 0.85rem | one line, ellipsis |
| Catalogue heading | 700 | 1.7rem / 1.1 | navy |
| Filter label | 600 | 0.85rem / 1 | muted |
| Filter chip | 600 | 0.9rem / 1 | navy |
| Card number | 700 | 1.05rem / 1.2 | ink |
| Card meta | 400 | 0.85rem | muted |
| Status pill | 600 | 0.75rem / 1.2 | |

## 5. Icons

Thin outline icons drawn for Nock: SVG `viewBox="0 0 24 24"`, `fill="none"`,
`stroke="currentColor"`, `stroke-width="1.8"`, `stroke-linecap="round"`,
`stroke-linejoin="round"`, `aria-hidden="true"` (the button carries the name).
Shown at 22 px in the phone top bar and on keys, 20 px in the computer top bar.

| Name | Used for | Shapes |
| --- | --- | --- |
| undo | Annuler | `<path d="M9 14 4 9l5-5"/>` `<path d="M4 9h10a6 6 0 0 1 0 12h-3"/>` |
| aide | Aide (bulb) | `<path d="M9 18h6M10 22h4"/>` `<path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/>` |
| salon | Salon (speech bubble) | `<path d="M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z"/>` |
| clavier | Clavier | `<rect x="2" y="6" width="20" height="12" rx="2"/>` `<path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>` |
| menu | Menu (3 bars) | `<path d="M4 7h16M4 12h16M4 17h16"/>` |
| crayon | Crayon, ✎ key | `<path d="M4 20h4L19 9l-4-4L4 16v4z"/>` `<path d="M13.5 6.5l4 4"/>` |
| swap | ⇄ key (change direction) | `<path d="M4 8h14l-3-3M20 16H6l3 3"/>` |
| effacer | ⌫ key (erase) | `<path d="M9 5h11v14H9l-6-7 6-7z"/>` `<path d="M13 9l4 6M17 9l-4 6"/>` |

When an icon is missing: Font Awesome Free (approved by the human on 2026-10-16),
in its outline "regular" style first. Only the icons used are bundled, served by
Nock itself; never the Font Awesome CDN or kit. Each use carries a comment with the
CC BY 4.0 attribution, and the README has one line crediting Font Awesome Free.
When Font Awesome Free has no outline version of an icon, Nock draws one in the
style above rather than mix filled and outline icons. Adding Font Awesome is a
dependency the human approved; the spec that first needs it names the exact
package.

Nock's own marks, never Font Awesome:

- The grid arrows (section 6).
- The Nock mark (the notch at the back of an arrow): `<svg viewBox="0 0 10 14">`
  with `<polygon points="0,0 10,0 10,14 5,10 0,14"/>`, filled. Brand: 12 by 18 px,
  navy. Force notch in the catalogue: 8 by 11 px.

Text glyphs used as pictograms, in the current font: ‹ › (clue bar), ⚑ (flag),
✓ (done, passed check), → (join), ▲ (reveal line), ✎ (pencil line), ▾ (Aide
menu on a computer). No emoji in the interface (reactions and chat text are user
content).

## 6. Grid cells

### Grid lines

The grid container has a 1 px rule-grey left and top border; each cell has a
1 px rule-grey right and bottom border, inside its side `s`. No gap between cells.
Cells clip their content (`overflow: hidden`), except clue cells (see "Clue
cells").

### Letter cell backgrounds

Exactly one background applies, the first that matches in this list:

| State | Background |
| --- | --- |
| Flash (spec 016), 1,000 ms | white with the replacer's `--player-colour-N` at 38 % over it |
| My selected cell | `--nock-selected` |
| Locked (checked right, or revealed) | `--nock-locked` |
| In my selected word | `--nock-word` |
| In another player's selected word (OPEN: keep or drop) | `color-mix(in srgb, var(--player-colour-N) 16%, var(--nock-white))` |
| Otherwise | `--nock-white` |

When a cell is in the words of two other players, the tint is that of the one who
comes first in join order (the sheet does not say; section 15).

My selection border: 2 px solid navy drawn inside the cell, over every other mark
of the cell. It is the cell's own outline (`outline: 2px solid var(--nock-navy)`,
`outline-offset: -2px`), which spec 035 AC-2 reads. It is the only cell border
besides the grid lines.

### Letter marks

| Mark | Look |
| --- | --- |
| Normal letter | ink, weight 500 |
| Locked | weight 700 on locked grey |
| Pencil (spec 020) | italic, `--nock-pencil`; during a flash, ink and italic (italics are the only sign) |
| Wrong after a check (spec 023) | `text-decoration: line-through`, thickness max(2px, 0.07em), colour `--nock-red`; ink in Auteurs mode |
| Revealed (spec 024) | locked (bold, locked grey) plus the notch below |

Revealed notch: an isosceles triangle in `--nock-reveal`, pointing up, centred on
the middle of the bottom edge and flush with it. Base max(7px, 0.22 s), height
max(4px, 0.11 s). Corners belong to players, and no arrow ever enters a cell from
the bottom, so nothing else uses that spot. During a flash its contrast can drop
below 3:1 (section 15).

### Other players on a cell

A plain right triangle in one corner of the cell, legs along the two edges, each
leg t = max(6, round(0.3 s)) px, filled with the player's `--player-colour-N`, no
outline, no text, ever. Corners are given in the order players arrive on the cell:
top-left, top-right, bottom-right, bottom-left. When a player leaves the cell, the
others keep their corners (OPEN: arrival order versus a fixed corner per player).
At most 4 are drawn; a fifth or later player is not drawn and nothing says "+k".
A disconnected player is not drawn (spec 013). My own selection is never a
triangle. This replaces the dashed borders of spec 013 and the initials and "+k"
labels of spec 035 (section 12).

### Clue cells

- Background `--nock-clue-bg`, text `--nock-clue-ink` (section 4), padding 2 px
  top and bottom, 3 px left and right.
- One clue fills the cell, centred vertically. Two clues share it in two equal
  halves, clue 0 on top, with a 1 px separator between them in clue ink at 55 %
  opacity, inset 14 % of the cell width on each side.
- Flag ⚑ (spec 021): in the clue cell's top-left corner, 1 px from the top and
  left edges, `--nock-red`, weight 700, size max(7px, 0.22 s), line height 1, on a
  clue blue-grey backing (padding 0 2 px 1 px 1 px, bottom-right radius 3 px). The
  flag never moves the text. Top-left is the one corner of a clue cell no arrow
  uses.
- The selected word's clue: the sheet gives it no look (OPEN, section 15).

### Direction arrows

Drawn in the letter cell where the word starts, next to its clue, as in printed
grids; never in the clue cell. SVG `viewBox="0 0 24 24"`, box side
a = max(9px, 0.26 s), stroke ink, stroke width 2.4 (in the 24-unit box), round caps
and joins, no fill on the path, the head a filled ink polygon. A thin white halo
lets it read over any mark: `filter: drop-shadow(0 0 0.8px #FFFFFF)
drop-shadow(0 0 0.8px #FFFFFF)` (white is `--nock-white`).

| Arrow | Kind (spec 002) | Path | Head |
| --- | --- | --- | --- |
| → | right | `M2 12H15` | `14,7.5 22,12 14,16.5` |
| ↓ | down | `M12 2V15` | `7.5,14 12,22 16.5,14` |
| ↳ | down then right | `M5 2V10Q5 15 10 15H15` | `14,10.5 22,15 14,19.5` |
| ↴ | right then down | `M2 5H10Q15 5 15 10V15` | `10.5,14 15,22 19.5,14` |

Position of the box in the letter cell (as `arrowFor()` in the sheet):

| Arrow | Enters from | Box position |
| --- | --- | --- |
| → | the clue on the left | left −1 px; vertical centre at 0.5 s |
| → of clue 0 of a two-clue cell | the clue on the left | left −1 px; vertical centre at 0.25 s |
| → of clue 1 of a two-clue cell | the clue on the left | left −1 px; vertical centre at 0.72 s |
| ↓ | the clue above | top −1 px; horizontal centre at 0.5 s |
| ↳ | the clue above | top −1 px; left 0.06 s |
| ↴ | the clue on the left | left −1 px; top 0.06 s |

The −1 px puts the box's edge on the grid line; the clipped column holds no
stroke (strokes start at 2 units). Measured during the design session on 68 px
cells: every arrow keeps at least 2.7 px from every letter A to Z. Two arrows in
one letter cell can collide in two cases the sheet never draws (section 15).

### Drawing order

Top first, inside one cell (the sheet's z-index in brackets):

1. My selection border (7; the cell's outline).
2. Direction arrows (6).
3. Revealed notch (3).
4. Player triangles (2), and in clue cells the flag (2).
5. The letter, or the clue text.
6. The flash overlay, then the background.

### One cell with every mark

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

## 7. Auteurs mode

Replaces the author band of spec 019, which is removed.

- A switch, off by default, in the Menu (section 8): « Auteurs » with the detail
  « activé » or « désactivé ». It is each player's own view; spec 019 does not
  remember it across reloads, and the sheet does not say otherwise.
- When on, each letter is drawn in its finder's ink `--player-ink-N` (section 3),
  on whatever background the cell has.
- A revealed letter has no finder: it stays ink.
- A letter whose finder has left the room is drawn in `--nock-departed`.
- A pencil letter keeps its italics, in its finder's ink.
- The wrong-letter strike turns ink (a red strike would vanish on a red letter).
- A legend shows while the mode is on: « Auteurs : » then each player's name in
  their ink, weight 700, in join order, one space apart. It sits centred at the
  bottom of the grid area, 8 px above its bottom edge, over the grid (no layout
  shift): background `--nock-legend-bg`, 1 px line-grey border, radius 14 px,
  padding 4 px 12 px, gap 8 px, one line. (The brief said "under the grid"; the
  sheet draws it over the bottom of the grid area. Section 15.)
- The clue bar shows only the clue; the « Lettre de … » of spec 019 AC-4 goes.
- During a flash the letter colours keep their inks; their contrast on the flash
  is not guaranteed (section 15).

## 8. Screens and layout

### Which layout

Two layouts: "sheet" (panels open as a bottom sheet) and "column" (a side column
on the right).

- Column when the window is landscape (`innerWidth > innerHeight`) and at least
  900 px wide.
- A phone held sideways (landscape, at most 500 px high) has the column only while
  its in-app keyboard is hidden.
- Otherwise, sheet.

The sheet states the phone rule without saying how it combines with the 900 px
rule for phones narrower than 900 px held sideways (section 15).

### Phone and upright tablet (sheet layout)

Top to bottom, filling the window, nothing scrolls:

1. Top bar, 54 px high, white, 1 px line-grey bottom border, padding 0 4 px 0
   10 px. The timer on the left (button, no border, padding 0 4 px), then
   `margin-right: auto`, then five buttons 56 px wide and the bar's full height:
   Annuler, Aide, Salon, Clavier, Menu. Each holds its 22 px icon over its label
   (gap 2 px), navy, radius 6 px. Pressed (Aide, Salon, Menu while open; Clavier
   while the keyboard shows): word-blue background. Unread badge on Salon: top
   5 px, right 8 px (section 11).
2. The grid area: all the height left, white, the grid centred, cells as large as
   fit with 8 px around (the sheet uses 16 px of margin in total on each axis).
3. Clue bar, 34 px high, navy, white text: ‹ button 36 px wide, then the clue text
   centred with its direction glyph (→ or ↓, 80 % opacity, 6 px left margin), on
   one line with an ellipsis when too long, then ⚑ « Je bloque » 40 px wide, then
   › 36 px wide. Text only: no author name, no pencil tag.
4. In-app keyboard (touch screens, spec 009): background `--nock-keyboard-bg`,
   padding 6 px 3 px 8 px, rows 6 px apart, keys 4 px apart and centred.
   - Rows: `A Z E R T Y U I O P`; `Q S D F G H J K L M`; `✎ W X C V B N ⇄ ⌫`.
   - Keys: 44 px high, flexible width up to 33 px, radius 5 px, `--nock-key`, ink,
     shadow `0 1px 0 var(--nock-key-shadow)`, no border. ✎ and ⌫ are wide: up to
     48 px, flex basis 48 px, grow 1.5. Icons 22 px.
   - ✎ pressed: navy key, white icon with `--nock-pen-fill` fill; every letter key
     then shows its letter italic in `--nock-pencil`.
   - ⇄ switches the selected cell between its across and down word (as a second
     tap on the cell, spec 007). ⌫ erases (spec 008).
   - « Clavier » hides and shows the keyboard; the choice is remembered per
     browser. The grid takes the space back.

### Computer and landscape tablet (column layout)

1. Top bar, 56 px high, white, 1 px line-grey bottom border, padding 0 16 px, gap
   4 px, items centred vertically, in this order: the Nock mark and « Nock »
   (gap 8 px); the grid name « Grille n° N · Force F » (14 px left margin, then
   `margin-right: auto`); the timer (10 px right margin); then buttons 38 px high,
   padding 0 12 px, radius 6 px, gap 6 px, icon 20 px beside its label: Annuler,
   Crayon, « Aide ▾ », Salon, Clavier (touch screens only), Menu. Pressed:
   word-blue background. Unread badge on Salon: top 2 px, left 24 px.
2. Body: the main area and, on its right, the side column.
   - Main area: padding 12 px, the grid centred and as large as fits in all the
     space left; under it the clue bar, as wide as the grid (grid width + 1 px);
     on touch tablets the in-app keyboard under the clue bar, full width of the
     main area (margins −12 px, top 10 px).
   - Side column: 340 px wide, white, 1 px line-grey left border; the Salon
     (below). It is open by default in this layout, with « Salon » pressed.
     « Salon » closes and opens it; the grid refits each time.
3. Nothing else is permanently on screen. Chat, players, progress, invitation and
   host settings open on demand.

### Aide menu (« Aide »)

A popover (section 11) under the button, min width 220 px:

- heading « Vérifier »; items « La lettre », « Le mot », « La grille » (spec 023);
- separator;
- heading « Révéler »; items « La lettre » with the detail « n restantes », « Le
  mot » with « n restant » or « n restants » (spec 024's budget).

### Menu (« Menu »)

A popover anchored to the right (6 px from the right edge on a phone): « Auteurs »
(detail « activé » / « désactivé »), « Inviter » (detail « lien »), « Réglages de
l'hôte » (host only), separator, « Masquer le chrono », « Retour aux grilles ».

On a phone, a scrim covers everything below the top bar (top 54 px) while a menu or
the Salon sheet is open; a tap on it closes them. Menus sit 58 px from the top.

### Salon

- Phone: a bottom sheet, 62 % of the window height, white, radius 14 px on the
  top corners, shadow `0 -10px 30px -12px var(--nock-shadow)`, with a grab handle
  (40 by 4 px, radius 2 px, `--nock-handle`, margin 8 px auto 4 px).
- Wide windows: the side column.

Content, top to bottom:

1. Progress: « 31 / 54 mots » (words fully filled / words) then a bar: 6 px high,
   radius 3 px, word-blue track, navy fill; padding 4 px 16 px 8 px (14 px top in
   the column), gap 10 px.
2. Tabs « Discussion » | « Joueurs (n) »: two equal tabs, padding 10 px, 2 px
   bottom border (transparent, navy when selected), muted text (navy when
   selected); a 1 px line-grey border under the row.
3. Discussion: one stream, oldest first, padding 10 px 16 px, items 8 px apart.
   - A message: a 10 px player dot (`--player-colour-N`, ring
     `0 0 0 1px var(--nock-dot-ring)`) and the name in weight 700 ink, gap 6 px,
     then the text.
   - An event: one line, muted, 0.82rem, 16 px left padding, starting with its
     pictogram: → joined, ← left (not in the sheet), ⚑ flag, ▲ reveal, ✓ check.
     Consecutive events of one player are grouped on one line, joined by « · »
     (« ✎ Bruno a rempli MIME · LEST » in the sheet; section 15). A reveal line is
     orange-red. A check line where everything was right is green.
   - Then the message box: padding 8 px 12 px 12 px, 1 px line-grey top border,
     gap 8 px; the input with a 1 px rule-grey border, radius 18 px, padding
     7 px 12 px; the « Envoyer » pill (word blue, navy, radius 14 px, padding
     6 px 12 px).
4. Joueurs: padding 10 px 16 px, rows 10 px apart, each row: dot, name (« (vous) »
   after my own), and on the right the state word « actif », « inactif » or
   « déconnecté » with spec 035 AC-7's styling (italic name for inactive, italic
   and struck through for disconnected), « · » and the player's current clue; then
   an « Inviter » pill.

Badges on « Salon »: the red badge counts unread messages; a dot (not drawn in
the sheet; section 15) means new events.

### 3-second notes

- One line, ink background, white text (section 4), padding 8 px 12 px, radius
  6 px, shadow `0 6px 18px -8px var(--nock-shadow-strong)`, centred over the top
  edge of the grid area, 8 px down, layer 6 of the grid area. No layout shift.
- One at a time; a new note replaces the current one. It shows for 3 s, then fades
  out in 0.25 s (opacity only, no slide). With `prefers-reduced-motion: reduce` it
  appears and goes without transition.
- A tap opens the Salon on that line.
- Not shown while the stream is visible (Salon open on Discussion).
- Which events: others' messages (« Bruno : … »), « Je bloque » (« ⚑ Dédé bloque
  sur « Flaire » »), reveals, others' checks, joins and departures. Never typed
  letters.

### Focus and keyboard

The sheet, the column and each menu are labelled regions. Opening one moves the
focus into it; Échap closes it and puts the focus back on the button that opened
it.

### Layers of the room page

| Layer | z-index |
| --- | --- |
| Auteurs legend | 5 |
| 3-second note | 6 |
| Phone scrim | 7 |
| Menus, popovers, Salon sheet, vote banner | 8 |
| Recap overlay (dialog or sheet with its scrim) | 20 |

## 9. Overlays

### Vote (spec 025)

A banner over the top of the grid area: 8 px from its top, left and right edges,
white, 2 px navy border, radius 10 px, padding 10 px 12 px, gap 8 px, shadow
`0 10px 24px -12px var(--nock-shadow)`, layer 8. Content: the question
(`vote.question.*`); a row with « Oui » (primary) and « Non » (secondary), both with
padding 7 px 16 px, and on the right the seconds left (« 18 s »); then a progress
bar 4 px high, radius 2 px, word-blue track, navy fill for the time left. No
layout shift.

### End of grid (spec 026)

A band under the clue bar, padding 8 px 12 px, gap 10 px, text 600 0.95rem:

- Finished: background `--nock-green-bg`, green text « ✓ Grille terminée, bravo ! »
  and, pushed right, the primary button « Voir le bilan » (padding 7 px 12 px,
  0.85rem). The recap-open control moves here (spec 028 AC-7 change). The in-app
  keyboard goes away once the grid is solved.
- Full but wrong: background `--nock-clue-bg`, navy text « Grille complète, mais
  pas encore juste. ». No red. Its place relative to the keyboard is not drawn
  (section 15).

### Recap (spec 028)

Opens only when asked.

- Phone: a bottom sheet over a `--nock-scrim-dialog` scrim covering the whole
  window, radius 16 px on the top corners (section 15), padding 14 px 18 px
  18 px, no grab handle.
- Computer: a dialog 440 px wide, centred, over a `--nock-scrim-dialog` scrim
  covering the whole window, white, radius 12 px, padding 20 px 22 px, gap 14 px,
  shadow `0 20px 40px -16px var(--nock-shadow-strong)`.

Content in order (spec 028's strings): title « Bilan de la partie »; « Temps :
m:ss » (recap time style); the lines « Vérifications : n », « Révélations : … »,
« Lettres révélées : n » (gap 4 px); heading « Qui a fait quoi »; one row per player
(dot, name, « (vous) » in muted after mine, and on the right « n lettres · n mots
complétés »), rows 8 px apart (on the phone the value wraps under the name, 18 px
in); heading « Lien à partager »; the URL in a box (1 px rule-grey border, radius
6 px, padding 8 px 10 px) and « Copier le lien » (secondary, padding 8 px 12 px);
« Fermer » (primary), right-aligned. Échap closes it.

## 10. Catalogue (spec 004)

- Top bar 56 px as the computer room's, with the Nock mark and « Nock » only.
- Main column: max width 920 px, centred, padding 24 px (16 px on a phone), gap
  16 px. Heading « Grilles » (section 4).
- Filter row, gap 8 px: label « Force », then chips « Toutes », « Force 1 » to
  « Force 4 »: radius 16 px, padding 7 px 14 px, 1 px line-grey border, white,
  navy text. Pressed: word-blue background, navy border.
- Cards in a grid: `repeat(auto-fill, minmax(min(100%, 400px), 1fr))`, gap 12 px,
  so one per row on a phone. A card: 1 px line-grey border, radius 8 px, padding
  12 px 14 px, gap 14 px, white:
  - a thumbnail of the grid's shape: white with its clue cells in `--nock-thumb`,
    1 px rule-grey border, 51 px high (44 px on a phone), width in proportion to
    the grid (39 by 51 for 13 by 17);
  - « Grille n° N » and, after it, the status pill: « Commencée » (word blue,
    navy) or « Terminée » (green background, green text), radius 12 px, padding
    3 px 9 px;
  - « Publiée le … »;
  - four Nock marks (8 by 11 px, gap 2 px), navy up to the grid's force and
    `--nock-thumb` after, then « Force F · W × H · N mots ». Force is written, so
    it never relies on the drawing alone;
  - the primary button « Jouer » on the right (padding 9 px 16 px).

The thumbnail needs the clue cells of each grid, which the catalogue summary of
spec 004 does not carry today (section 12).

## 11. Components

| Component | Look |
| --- | --- |
| Button, all | radius 6 px, padding 10 px 16 px, weight 600, 0.95rem, line height 1, 1 px border |
| Primary | navy background, white text, transparent border |
| Secondary | white background, navy text, navy border |
| Quiet | word-blue background, navy text, transparent border |
| Disabled (any) | clue blue-grey background, muted text, line-grey border, `cursor: not-allowed`; text still 4.5:1 |
| Focus ring | `outline: 2px solid var(--nock-navy)`, `outline-offset: 2px`, on `:focus-visible`. On a navy surface (the clue bar): white, offset −4 px |
| Menu / popover | white, radius 8 px, padding 6 px 0, min width 220 px, shadow `0 12px 30px -10px var(--nock-shadow)`, no border |
| Menu item | full-width button, padding 10 px 16 px, 500 1rem/1.2, navy, left-aligned; detail on the right (gap 12 px), muted, not italic, tabular; hover: word-blue background |
| Menu heading | margin 6 px 16 px 2 px, 600 0.7rem, uppercase, letter spacing 0.08em, muted |
| Menu separator | 1 px line-grey top border, margin 4 px 0 |
| Top-bar button | navy icon and label, transparent background; pressed: word blue |
| Badge | red background, white 700 0.62rem/1 text, padding 2 px 4 px, radius 8 px |
| 3-second note | section 8 |
| Status band | sections 9 (in the room) |
| Status pill | section 10 |
| Bottom sheet | white, radius 14 px top, grab handle, section 8 |
| Scrim | `--nock-scrim` (menus, sheet) or `--nock-scrim-dialog` (recap) |
| Text input | 1 px rule-grey border; radius 18 px (message box) or 6 px (URL box) |
| Pill button | word blue, navy, 600 0.85rem, radius 14 px, padding 6 px 12 px, no border |
| Player dot | 10 px circle, player colour, ring `0 0 0 1px var(--nock-dot-ring)` |

## 12. Spec impact

Refinements to make, each with dated notes, before the matching build step
(section 14). "Gap" means the sheet draws nothing for it yet; the spec writer
proposes a look here first (rule 3).

| Spec | Status | What contradicts or is missing | Change |
| --- | --- | --- | --- |
| 004 | done | Catalogue look (AC-1, AC-3 show the fields and progress, no look); the summary has no cell layout for a thumbnail | Section 10 criteria; add the clue-cell positions to `GridSummary` and `GET /api/grids`, or drop the thumbnail (OPEN) |
| 005 | done | Credits on the catalogue and grid page are not drawn | Gap |
| 006 | done | AC-2: arrows drawn in the clue cell on its side; AC-3: separator look; letter 0.55 s and clue 0.11 s / 0.09 s today; empty cells have no look; AC-5 and AC-7 fit a page without top bar or clue bar of this design | Arrows into the letter cell (section 6); separator 55 %, 14 % insets; letter 0.56 s; clue max(6px, 0.145 s); empty cells (OPEN); fit rules with the new layout |
| 007 | done | AC-1: the selected word's clue is highlighted (yellow today); selected cell yellow with a 3 px ink outline; AC-4: clue bar look | Selected blue and 2 px navy outline; clue highlight (OPEN); clue bar of section 8 |
| 009 | done | AC-3: third row `WXCVBN` plus `key-delete` only; key size and colours; no Clavier control | ✎ and ⇄ keys, key geometry (section 8), « Clavier » hides the keyboard |
| 010, 011 | done | The share link and copy button sit on the room page | Move into Menu « Inviter » and the Salon's « Inviter » (also changes spec 035 AC-12's Tab walk, which starts at `share-link`) |
| 012 | done | Palette values; nickname form and roster look | Section 3 values (done by spec 041); roster moves into the Salon; nickname form is a gap |
| 013 | done | AC-2, AC-3: dashed border in the player's colour on the cell; tint at 28 % today; AC-5, AC-7, AC-8 and "Client: feed height": the feed is stacked above the grid and "never beside the grid"; AC-6: roster and feed on the page | Corner triangles (section 6); tint 16 % (OPEN keep or drop); feed becomes events in the Salon stream, in the sheet or the column; the roster becomes the Salon's Joueurs list |
| 014 | done | Host panel and roster remove buttons on the page; AC-7 to AC-10 measure their small-window layouts | Host settings open from Menu « Réglages de l'hôte »; remove buttons in the Joueurs list; AC-7 to AC-10 rewritten for the new places |
| 016 | done | Flash basis: the cell takes the replacer's full colour, with a text colour per player | Replacer's colour at 38 % over white, ink letters (spec 041 draws it as an overlay so AC-2's swatch check still holds) |
| 017 | done | Connection banner look | Gap |
| 018 | done | Undo button look and place | « Annuler » in the top bar (section 8) |
| 019 | done | The whole author band (AC-1, AC-2, AC-5); AC-4 « Lettre de … » in the clue bar; switch in the toolbar | Auteurs mode of section 7; switch in the Menu; legend instead of the clue bar line |
| 020 | done | `pencil-toggle` in the toolbar; the confirm control; AC-7 layout | ✎ key on touch screens, « Crayon » in the computer top bar; confirm control is a gap |
| 021 | done | `flag-button` in the toolbar; marker position and size (AC-9), the second clue's flag sits under the separator | ⚑ « Je bloque » in the clue bar; flag of section 6; second-clue position (OPEN) |
| 022 | done | Chat panel drawn over the page (decision 6, AC-17); `chat-toggle` and `react-button` in the toolbar (AC-5); chat notes (AC-19); reactions shown on clue cells | Discussion tab of the Salon; « Salon » button with the red unread badge; 3-second notes; reactions are a gap (OPEN) |
| 023 | done | `check-panel` in the toolbar (AC-9); strike look | Aide menu « Vérifier »; strike of section 6; passed check line green |
| 024 | done | `reveal-panel` in the toolbar (AC-7, AC-8); `reveal-mark` in the top-right corner, at least 6 px and a quarter of the side (AC-9), 3:1 during a flash | Aide menu « Révéler »; bottom-centre notch of section 6, which is smaller than the quarter (OPEN) and below 3:1 on some flashes (OPEN) |
| 025 | done | Vote banner look; AC-4 hides `check-panel` and `reveal-panel` in none mode | Section 9 banner; in none mode « Aide » is hidden (to confirm in the refinement) |
| 026 | done | `grid-status` look; AC-10 puts the status in the clue bar's row on windows at most 500 px high | Band under the clue bar (section 9); AC-10 rewritten; keyboard goes away once solved |
| 027 | done | `timer`, `timer-toggle`, `chat-toggle` are the first three toolbar elements (AC-8); « ⏱ » toggle | Timer in the top bar; « Masquer le chrono » in the Menu |
| 028 | approved | AC-7: `recap-open` in the toolbar right after `chat-toggle`; AC-10 dialog sizes | « Voir le bilan » in the end band; sheet on a phone, 440 px dialog on a computer (section 9) |
| 029, 032, 033 | approved | History, « My rooms » and account screens are not drawn | Gaps; use section 10's cards and section 11's components |
| 034 | approved | AC-2: changed cells highlighted for 5 s; no look | Gap |
| 035 | done | AC-2: focus outline 3 px blue today, and "3:1 against the page background" fails for a white ring on navy; AC-6 initials; AC-11 slots and "+k"; AC-7 roster states; AC-12 lists named `roster` and `activity-feed`; "Reduced motion" out of scope | 2 px navy ring (spec 041); measure against the surface behind the ring; triangles are colour only, with the Joueurs list as the non-colour sign (OPEN); AC-11 replaced by section 6's corners; AC-7 and AC-12 follow the Salon lists; notes respect reduced motion |
| 040 | done | `room-heading` (« Salon {code} ») and `room-status` shown on the page; styles were "not binding" | Their place in the top bar is a gap; styles now follow this file |

New specs, numbers proposed in build order (section 14): 041 visual foundation
(written); then grid cells, room layout, keyboard, Auteurs mode, catalogue,
overlays.

## 13. How conformance is secured

1. Spec 041 pins the foundation with tests: the tokens, the player colours and
   inks, the fonts, the focus ring, the button, menu, badge and note primitives,
   and the colour scan below.
2. Each refined or new spec gets criteria that read what the eye sees: computed
   colours as `rgb()`, sizes and positions in px at a known window or cell size,
   paint order with `document.elementFromPoint` at chosen points, bounding boxes
   for positions and clearances, and data attributes for states.
3. The tokens in `web/src/app.css` are the only source of colours. A test scans
   the built CSS in `web/dist` and the client sources for colour literals outside
   the token block (spec 041).
4. Optional, a human decision because it is new tooling: screenshot comparison
   against reference images rendered from `docs/design/cell-sheet.html`.
5. The reviewer checks each change against this file:
   - every colour comes from a token, and the token is used for its job;
   - no new font, size, radius, shadow or icon outside this file;
   - the cell geometry and drawing order of section 6;
   - contrast of section 2 holds in every state the spec covers, flashes
     included;
   - the layout rules of section 8, and that nothing extra is permanently on
     screen;
   - focus ring and Échap behaviour of sections 8 and 11;
   - the spec cites the sections it applies.
6. The sheet stays in `docs/design/` as the visual reference, updated with this
   file.

## 14. Build order

Each step leaves the app working and every test passing.

1. Foundation: tokens, player colours, fonts, icons, buttons, focus ring, menus,
   badges, notes (spec 041). Today's screens take the token colours with no layout
   change.
2. Grid cells: section 6 (with specs 006, 007, 013, 016, 021, 023, 024, 035
   refined).
3. Room layout: top bar, sheet and column, Salon, 3-second notes, Aide and Menu
   (specs 010, 011, 013, 014, 018, 022, 023, 024, 027, 035, 040 refined).
4. Keyboard: ✎, ⇄, « Clavier » (specs 009, 020 refined).
5. Auteurs mode, catalogue, overlays (specs 019, 004, 025, 026, 028 refined).

## 15. Open decisions

For the human. The spec writer's pick comes last in each item.

1. Another player's word: keep the 16 % tint, or drop it. Pick: keep, it shows
   where a team-mate works; the sheet has a switch for both.
2. Corner triangles carry colour only, which spec 035 AC-6 forbids today. The
   Joueurs list in the Salon says where each player is. Accept the list as the
   non-colour sign? Pick: yes, and refine spec 035.
3. The revealed notch is smaller than spec 024's minimum (at least 6 px and a
   quarter of the side, in both directions): 0.22 s by 0.11 s. Accept? Pick:
   yes, refine spec 024.
4. The notch drops below 3:1 on some flashes (orange-red on Magenta 38 %: 2.6:1,
   Cramoisi 2.8:1, Orange 2.1:1), which spec 024 forbids. Options: draw the notch
   in ink during the 1 s flash; give it a white edge; accept. Pick: ink during the
   flash.
5. Font files are a dependency. Options: the npm packages
   `@fontsource/source-sans-3` and `@fontsource/ibm-plex-sans-condensed`, imported
   per weight; or the WOFF2 files committed under `web/public/fonts/` with their
   SIL OFL 1.1 licence. Pick: the npm packages.
6. Grid lines and input borders: rule grey #9AA3B2 is 2.54:1 on white; WCAG 1.4.11
   asks 3:1 for an input's border. Options: keep; darken to #8A93A3 (3.10:1).
   Pick: #8A93A3.
7. Departed grey #6B7079 is below 4.5:1 on word blue (4.23:1) and selected blue
   (3.62:1). Options: #5C616A (4.53:1 on selected); accept. Pick: #5C616A.
8. Does a closed side column stay closed next time (per browser)? Pick: yes.
9. A long press on ⌫ erases the word? Pick: not now.
10. Which corner a player gets: arrival order on the cell (the sheet), or a fixed
    corner per player. Pick: arrival order.
11. The selected word's clue in the grid: the sheet gives it no look, and spec 007
    AC-1 highlights it. Options: no highlight (the clue bar names it); the clue's
    half in selected blue. Pick: the clue's half in selected blue, which widens
    that token's job to "my selected cell and my selected clue".
12. Empty cells (spec 002's `empty` type) have no look. Options: rule grey; ink.
    Pick: rule grey.
13. Reactions (spec 022) are not drawn: no react button in the top bar, no badge
    on clue cells. Options: keep them (where?); drop them. Pick: keep the badge
    over the clue as today, react from the Aide menu; needs a drawing first.
14. Pencil confirm (spec 020) is not drawn. Pick: an item in the Aide menu.
15. Two arrows can collide in one letter cell: a → of clue 0 (centre 0.25 s) with a
    ↴ (top 0.06 s) from the same two-clue cell, and a ↴ from the left with a ↳
    from above (both near the top-left corner). Pick: → always at 0.72 s when the
    cell also has a ↴; for ↴ with ↳, a drawing first.
16. Phone held sideways and the 900 px rule (section 8). Pick: column when
    landscape and either at least 900 px wide and more than 500 px high, or at
    most 500 px high with the keyboard hidden.
17. The stream line « ✎ Bruno a rempli MIME · LEST » needs an event the protocol
    does not have (a word filled). Options: add it (protocol change); drop the
    line. Pick: drop it for now.
18. Where a 3-second note goes while the vote banner shows (both sit 8 px from the
    top of the grid area). Pick: notes wait until the banner goes.
19. The « Je bloque » button shows pressed only by opacity (100 % against 70 %).
    Pick: pressed is a white button with a navy ⚑, as the sheet's own switch
    buttons.
20. The new-events dot on « Salon » is not drawn. Pick: an 8 px red dot at the
    badge's place.

Inconsistencies of the sheet, settled here unless the human says otherwise:

- `--clue-ink` (#1B2230) is a token in the sheet but missing from the brief's
  list: kept as `--nock-clue-ink`.
- Shadows use `rgba(0, 0, 0, ...)`, against "no pure black"; the demo menu has a
  0.35 shadow and a border, the phone popover 0.45 and no border: ink-based
  shadows, the popover's values.
- Recap sheet radius 16 px with no handle, Salon sheet 14 px with a handle: kept
  as drawn.
- The reveal line's pictogram is 👁 (an emoji) on the phone and ▲ on the computer:
  ▲.
- Texts say "red notch" and "revealed letters stay black": the notch is orange-red
  and the letters ink.
- The caption "smaller type in two-clue cells" disagrees with the CSS, which has
  one clue size: one size.
- Clue cells have `overflow: visible`, so a long clue could spill over its
  neighbours; spec 006 AC-1 still requires no cut at full zoom. At about 29 px
  (tablet with the keyboard) two-clue cells do not hold their text, as the sheet
  notes: players zoom or hide the keyboard.
- The flag of a flagged second clue has no place of its own.
- The ⚑, ‹, › glyphs come from the text font; Source Sans 3 has no ⚑, so it is
  drawn by a fallback font and looks different per system.
- The legend is drawn over the bottom of the grid area, not under the grid; it can
  cover the last row.
- The sheet shows « 31 / 48 mots » on the phone and « 31 / 54 mots » on the
  computer for sample grids: sample data only.
- Leftovers of earlier versions, not part of the design: `fitName`, `LABEL_AT`,
  `.tri b`, `.band`, `.pentag`, and the contrast row "Triangle edge on selected
  fill".
- When the timer is hidden, the sheet does not say what holds the top bar's left
  slot.
- A flash replaces my selected cell's blue for 1 s (the sheet's inline style
  wins); the navy border stays.
