# Visual design

Not a spec: the quality gate ignores files starting with "_". Every spec that puts
something on screen follows this note, as every "Public interface" follows
`specs/_architecture.md`. Decided with the human on 2026-10-16, from the design
session whose result is the page `docs/design/cell-sheet.html` (version 4.6
on `feat/design-system`; 4.5 was commit 32fad92; 4.2 was commit d3382db; first published as
https://claude.ai/artifact/VCuP9WSmsdXA7JJEvb9ixV).

(Note from the spec writer, 2026-10-16: second round. The human's decisions of
2026-10-16 and sheet version 4.2 are folded in: the remaining screens of the
sheet's section 12, the arrow collision rules, the drawn pictograms, empty cells,
the active clue, the catch-up ring, the connection band and the full-but-wrong
band. Each decision carries the note "decided by the human on 2026-10-16". The
Accessibilité mode and its player icons come from sheet 4.3.)

Values are CSS values. `s` is the side of a grid cell in CSS px, its right and
bottom grid line included (the cell is `box-sizing: border-box`). "max(7px, 0.22 s)"
means the larger of 7 px and 22 % of `s`. `rem` is the root font size (16 px by
default). Items marked OPEN or DEFERRED are in section 15.

## 1. Purpose and authority

This file and the two sheets in `docs/design/` are the visual reference of the
web client: `cell-sheet.html` draws the grid cells, `screens-sheet.html` every
screen and state at phone width (360 px) and computer width (1280 px). Where they
differ, this file wins, and the difference is listed in section 15 or fixed in the
sheet. (Note from the lead, 2026-10-22: the screens sheet joins the reference, its
proposals P1 to P16 and D1 to D3 decided by the human on 2026-10-22, section 15; this
paragraph named the cell sheet only.)

Rules:

1. Every spec that puts something on screen cites the sections of this file it
   applies, in its "Public interface", and has acceptance criteria that check the
   values that matter: computed colours, sizes and positions at a known cell size or
   window size, paint order, and which elements are present or absent.
2. No spec and no code introduces a colour, a font, a font size, a radius, a
   shadow or an icon that is not listed here. Colours are used only through the
   tokens of sections 2 and 3.
3. A change of look starts here. Any change that alters what a screen looks
   like (a decision of the human, a new or refined spec, a review finding) updates
   this file, with a dated note next to the change, and redraws what it changes in
   the sheets, in the same commit, before any test or code changes. The screens
   sheet is generated: edit `docs/design/screens_sheet/` and run
   `uv run python docs/design/screens_sheet/build.py`; its HTML is never edited by
   hand. A screen whose look changed without its drawing is a review finding
   (section 13). (Note from the lead, 2026-10-22: the human's rule of 2026-10-22,
   "always update this visual documentation to include changes"; the rule read "The
   spec writer updates this file (and the sheet when the change is visible in it)".)
4. Where an existing `approved` or `done` spec contradicts this file, this file
   describes the target and the spec is refined to match (section 12 lists them).
   Until a spec is refined, it wins for its own tests, and the code keeps passing
   them.
5. Grid letters are the 26 capitals `A` to `Z`, never accented, in examples too.
6. Strings are the app's own: `fr.json` and the key tables of the specs. Where the
   sheet's sample text differs from a spec's string (for example « a rejoint la
   partie » against spec 013's « a rejoint le salon »), the spec's string wins.
7. The sheets draw the decided design. Something not yet decided (a spec's pick
   pending its approval, a proposal) carries a dashed label in the screens sheet
   and an item in section 15 until the human decides it. (Note from the lead,
   2026-10-22: new rule, with the screens sheet.)

## 2. Colour tokens

Each colour is a CSS custom property declared once, in the `:root` block of
`web/src/app.css` (the token block). Code uses `var(--nock-...)`, never the value.
Ratios are WCAG 2.x contrast against white (#FFFFFF).

| Token | Value | Its one job | Never for | On white |
| --- | --- | --- | --- | --- |
| `--nock-navy` | #1B2F55 | The app's colour: top bar, top-bar icons and labels, clue bar, primary buttons, my selection border, focus ring, links, headings, segmented control and switch when on, slider fill and knob (section 11; P15, 2026-10-22) | Player marks | 13.26:1 |
| `--nock-ink` | #14181F | All text and grid letters, direction arrows, the catch-up ring, 3-second notes (background), the revealed notch during a flash, scrim and shadow base | Backgrounds of cells | 17.79:1 |
| `--nock-muted` | #5E6573 | Secondary text: captions, event lines in the stream, disabled labels, menu details, inactive tabs, the room code above an entry card | Grid letters | 5.86:1 |
| `--nock-pencil` | #555B67 | Pencil letters (italic), letter keys in pencil mode | Any other text | 6.82:1 |
| `--nock-white` | #FFFFFF | Room page, letter cells, menus, sheets, dialogs, cards; text and icons on navy, ink and red | - | 1:1 |
| `--nock-page` | #F6F7F9 | Background of the pages that are not the room (nickname, entry statuses, not found) behind their white card | Room page, cells | 1.07:1 |
| `--nock-clue-bg` | #EEF2F8 | Clue cells, disabled buttons, the "not yet" status band, the connection band, the « hôte » tag | Selection | 1.12:1 |
| `--nock-clue-ink` | #1B2230 | Clue text in clue cells, the separator between two clues | Any other text | 15.97:1 |
| `--nock-word` | #E6EDF9 | My selected word, hovered menu item, pressed top-bar button, quiet buttons, pressed filter chips, progress bar and slider track, hovered reaction | Player tints | 1.18:1 |
| `--nock-selected` | #CFDDF3 | My selected cell, and the half of the clue cell that holds my selected word's clue (decided by the human on 2026-10-16, drawn in sheet 4.2) | Anything else | 1.37:1 |
| `--nock-locked` | #E3E7EE | Locked letter cells (with bold letters) | Disabled states | 1.24:1 |
| `--nock-rule` | #9AA3B2 | Grid lines, empty cells, input borders, border of the catalogue's grid drawing, switch track when off | Text | 2.54:1 (DEFERRED, low) |
| `--nock-line` | #DDE2EA | Dividers in menus, panels and cards; card and list-row borders; filter chip borders; disabled button border; reaction pill and picker borders; inner lines of the catalogue's generic grid drawing (2026-10-17) | Grid lines of the playing grid | 1.30:1 |
| `--nock-red` | #B42318 | "Look here": wrong-letter strike, flag, unread badge, new-events dot, the connection band's dot, error text and the border of a field in error | Decoration | 6.57:1 |
| `--nock-reveal` | #C2410C | "Revealed", and nothing else: the revealed notch, the reveal line in the stream | Anything else | 5.18:1 |
| `--nock-green` | #1E7B45 | "Done": finished-grid band text, passed-check line in the stream, "Terminée" pill text, confirmation lines (« Lien copié », « Lien envoyé … ») | Player marks | 5.28:1 |
| `--nock-green-bg` | #E6F2EA | Background of the finished-grid band and of the "Terminée" pill | Anything else | 1.15:1 |
| `--nock-key` | #E9ECF1 | In-app keyboard keys | - | 1.18:1 |
| `--nock-keyboard-bg` | #D9DEE6 | In-app keyboard background | - | 1.35:1 |
| `--nock-handle` | #C5CCD8 | Grab handle of a bottom sheet | - | 1.62:1 |
| `--nock-thumb` | #C9D2E0 | Clue cells of the catalogue's generic grid drawing, force notches above the grid's force | - | 1.52:1 |

Translucent tokens, all built on ink or white (the sheet's remaining
`rgba(0, 0, 0, ...)` shadows become ink, see section 15):

| Token | Value | Job |
| --- | --- | --- |
| `--nock-scrim` | rgb(20 24 31 / 35%) | Scrim under a menu, a popover, the Salon sheet and the other room sheets |
| `--nock-scrim-dialog` | rgb(20 24 31 / 38%) | Scrim under the recap |
| `--nock-dot-ring` | rgb(20 24 31 / 55%) | 1 px ring around a player dot |
| `--nock-key-shadow` | rgb(20 24 31 / 25%) | 1 px shadow under a key |
| `--nock-shadow-soft` | rgb(20 24 31 / 35%) | Shadow colour of a shown reaction |
| `--nock-shadow` | rgb(20 24 31 / 45%) | Shadow colour of menus, popovers, sheets, the vote banner and the reaction picker |
| `--nock-shadow-strong` | rgb(20 24 31 / 50%) | Shadow colour of dialogs and 3-second notes |
| `--nock-legend-bg` | rgb(255 255 255 / 96%) | Background of the Auteurs legend |
| `--nock-pen-fill` | rgb(255 255 255 / 35%) | Fill of the ✎ icon on the pressed pencil key |

Rules:

- Navy is the app's own colour. Red means "look here". Orange-red means
  "revealed" and nothing else. Green means "done". A player colour (section 3)
  only ever means a player: triangles, word tints, flashes, dots, Auteurs ink;
  never a button, a state or a decoration.
- Text and icons reach 4.5:1 against their background, disabled buttons included.
  Marks, borders that carry meaning and the focus ring reach 3:1 (except the
  DEFERRED rule grey, section 15).
- No pure black (#000000) and no neutral grey: the neutrals lean toward the navy.
- No dark mode for now. Every colour is a named token, so one can be added later
  by redefining the tokens.
- Two colours may be mixed only with `color-mix(in srgb, ...)` over tokens, or by
  `opacity`, at the percentages this file gives: 16 % (word tint), 38 % (flash),
  55 % (clue separator), 80 % (direction glyph in the clue bar).
- `transparent` and `currentColor` are allowed everywhere.

Measured pairs (WCAG 2.x):

| Pair | Ratio | Needs |
| --- | --- | --- |
| Ink on selected | 12.95:1 | 4.5 |
| Ink on locked | 14.34:1 | 4.5 |
| Ink on clue blue-grey (connection band) | 15.84:1 | 4.5 |
| Pencil on word / on selected | 5.80:1 / 4.97:1 | 4.5 |
| Pencil on key | 5.76:1 | 4.5 |
| Clue ink on clue blue-grey / on selected (active clue) | 14.18:1 / 11.6:1 | 4.5 |
| Red flag on clue blue-grey | 5.85:1 | 3 (icon), 4.5 met |
| White on navy | 13.26:1 | 4.5 |
| White on red (badge) | 6.57:1 | 4.5 |
| Muted on clue blue-grey (disabled button) | 5.22:1 | 4.5 |
| Muted on word blue (menu detail on hover) | 4.98:1 | 4.5 |
| Muted on page grey (room code line) | 5.47:1 | 4.5 |
| Navy on clue blue-grey (« hôte » tag) | 11.8:1 | 4.5 |
| Green on green background | 4.59:1 | 4.5 |
| Navy on word blue (pressed top-bar button) | 11.27:1 | 4.5 |
| Revealed notch on white / selected / locked / word | 5.18 / 3.77 / 4.17 / 4.40:1 | 3 |
| Navy selection border on selected | 9.65:1 | 3 |

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
third-party URLs); never from Google Fonts or another host. The files come from
the npm packages `@fontsource/source-sans-3` and
`@fontsource/ibm-plex-sans-condensed`, imported per weight and style used and no
other, and built into `web/dist` (decided by the human on 2026-10-16). The sheet's third family,
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
  and two-clue cells (section 15 on the sheet's caption).

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
| Key letter | 500 | 1.3rem / 1 | ink |
| Wide key | 500 | 1.1rem / 1 | ink |
| Button | 600 | 0.95rem / 1 | |
| Small button (« Retirer ») | 600 | 0.8rem / 1 | padding 6 px 10 px |
| Menu item | 500 | 1rem / 1.2 | navy; the pencil confirm item 600 |
| Menu group heading | 600 | 0.7rem / 1.2 | muted, uppercase, letter spacing 0.08em |
| Badge | 700 | 0.62rem / 1 | white on red |
| 3-second note | 500 | 0.85rem / 1.2 | white on ink |
| Auteurs legend | 500 (names 700) | 0.8rem / 1.2 | muted (names in inks) |
| Connection band | 500 | 0.85rem / 1.3 | ink |
| Progress label | 600 | 0.85rem / 1 | navy, tabular |
| Salon tab | 600 | 0.95rem / 1 | muted, navy when selected |
| Stream message | 400 (name 700) | 0.92rem | ink |
| Stream event | 400 | 0.82rem (13.1 px) | muted, or orange-red / green (section 8) |
| Message box | 400 | 0.9rem | placeholder muted |
| Send pill | 600 | 0.85rem | navy on word blue |
| Player row | 400 (own name 700) | 0.95rem | state 0.85rem muted |
| « hôte » tag | 600 | 0.72rem / 1.3 | navy on clue blue-grey |
| Vote question | 600 | 0.95rem / 1.3 | ink |
| Vote seconds | 500 | 0.85rem / 1 | muted, tabular |
| Status band | 600 | 0.95rem / 1.2 | |
| Dialog and sheet title | 700 | 1.2rem / 1.2 | navy |
| Dialog section heading | 600 | 0.78rem / 1.2 | muted, uppercase, letter spacing 0.07em |
| Card title | 700 | 1.25rem / 1.2 | navy |
| Card text | 400 | 0.95rem | ink; secondary 0.85rem muted |
| Room code above a card | 600 | 0.85rem / 1 | muted |
| Field label | 600 | 0.85rem / 1.2 | ink |
| Field input | 400 | 1rem / 1.2 | ink |
| Error and confirmation lines | 500 | 0.85rem / 1.3 | red / green |
| Switch row label | 500 | 0.95rem / 1.2 | ink |
| Segmented control | 600 | 0.85rem / 1 | navy, white when chosen |
| Text link | 600 | inherited | navy |
| Recap time | 700 | 2.1rem / 1 | navy, tabular |
| Recap lines and rows | 400 (names 600) | 0.95rem | values 0.85rem muted, tabular |
| Share URL box | 400 | 0.85rem | one line, ellipsis |
| Catalogue heading | 700 | 1.7rem / 1.1 | navy |
| Catalogue section heading (« Mes salons », « Grilles terminées ») | 700 | 1.15rem / 1.2 | navy |
| Filter label | 600 | 0.85rem / 1 | muted |
| Filter chip | 600 | 0.9rem / 1 | navy |
| Card number, list row title | 700 | 1.05rem / 1.2 (row title: inherited size) | ink |
| Card meta, list row lines | 400 | 0.85rem | muted |
| Status pill | 600 | 0.75rem / 1.2 | |
| Reaction pill | - | emoji 16 px / 1.2 | |
| Reaction picker | - | emoji 22 px | |

## 5. Icons

Thin outline icons drawn for Nock: SVG `viewBox="0 0 24 24"`, `fill="none"`,
`stroke="currentColor"`, round caps and joins, `aria-hidden="true"` (the button
carries the name).

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
| chrono | « Chrono » (timer hidden), the sheet's STOPWATCH | `<circle cx="12" cy="13.5" r="7.5"/>` `<path d="M12 10v3.5l2.5 2M9.5 3h5M12 3v3"/>` |
| flag | Je bloque, the flag on a clue, stream and note lines (the sheet's FLAG and FLAG_ICO) | `<path d="M6 21V4"/>` `<path d="M6 4h12l-3 4.5 3 4.5H6z"/>` |
| chevron-left | ‹ previous clue (CHEV_L) | `<path d="M15 5l-7 7 7 7"/>` |
| chevron-right | › next clue (CHEV_R) | `<path d="M9 5l7 7-7 7"/>` |
| smile | Réagir (SMILE) | `<circle cx="12" cy="12" r="9"/>` `<path d="M8.5 14.5c1.8 2 5.2 2 7 0"/>` `<path d="M9 9.5h.01M15 9.5h.01"/>` |

Sizes and strokes:

| Where | Size | Stroke width |
| --- | --- | --- |
| Phone top bar, keys | 22 px | 1.8 |
| Computer top bar | 20 px | 1.8 |
| Clue bar (chevrons, Réagir, Je bloque) | 20 px | 2 |
| Inline in text (stream, notes): class of the sheet `.ico` | 1em, `vertical-align: -0.15em` | 2 |

Filled variants: the flag is filled (`fill: currentColor`) when it marks a state:
on a flagged clue (red), on the pressed Je bloque button (navy), and inline in
stream and note lines (the sheet's FLAG_ICO: the pole path stays unfilled). On the
not-pressed Je bloque button it is an outline.

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

Text glyphs used as pictograms, in the current font: ✓ (done, check line), → (joined
line), ← (left line; not in the sheet, the spec writer's pick, decided by the
lead's decision of 2026-10-22 on the human's instruction, note from the spec writer
of that day, section 15 item 11), ▲ (reveal line, in
orange-red), ✎ (detail of the pencil confirm item), ▾ (Aide menu on a computer).
The flag and the clue bar's ‹ › are drawn icons, never text glyphs (the fonts have
no ⚑). No emoji in the interface; reactions and chat text are user content.

## 6. Grid cells

### Grid lines and empty cells

The grid container has a 1 px rule-grey left and top border; each cell has a
1 px rule-grey right and bottom border, inside its side `s`. No gap between cells.
Cells clip their content (`overflow: hidden`), except clue cells (see "Clue
cells").

An empty cell (spec 002's `empty` type) is filled with `--nock-rule` (decided by
the human on 2026-10-16, drawn in sheet 4.2).

### Letter cell backgrounds

Exactly one background applies, the first that matches in this list:

| State | Background |
| --- | --- |
| Flash (spec 016), 1,000 ms | white with the replacer's `--player-colour-N` at 38 % over it |
| My selected cell | `--nock-selected` |
| Locked (checked right, or revealed) | `--nock-locked` |
| In my selected word | `--nock-word` |
| In another player's selected word, while « Mots des autres » is « teintés » | `color-mix(in srgb, var(--player-colour-N) 16%, var(--nock-white))` |
| Otherwise | `--nock-white` |

Another player's word tint: kept, and each player can turn it on or off from the
Menu item « Mots des autres » (« teintés » / « sans teinte »), remembered per
browser, on by default (decided by the human on 2026-10-16). When a cell is in the
words of two other players, the tint is that of the one who comes first in join
order (the sheet does not say; the spec writer's pick).

My selection border: 2 px solid navy drawn inside the cell, over every other mark
of the cell. It is the cell's own outline (`outline: 2px solid var(--nock-navy)`,
`outline-offset: -2px`), which spec 035 AC-2 reads. It is the only cell border
besides the grid lines and the catch-up ring.

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
the bottom, so nothing else uses that spot. During a flash the notch is drawn in
`--nock-ink`, so it keeps 3:1 on every player colour (sheet 4.2,
`.flash.rev::after`). (Note from the spec writer, 2026-10-22: the ink during a
flash and the size above are decided, by the lead's decision of 2026-10-22 on the
human's instruction; they read "OPEN: ... pending approval" and "Its size is
DEFERRED". The size wins over spec 024 AC-9's former minimum, which spec 042
refines; section 15.)

### Catch-up ring (spec 034)

A cell that changed while I was away gets a 3 px solid `--nock-ink` ring on its
edge (`inset: 0`, inside the cell), for 5 s, `pointer-events: none`. It is drawn
over the letter and its background and under the player triangles, the notch and
the arrows (the sheet's z-index 1). The matching lines go in the stream (section
8).

### Other players on a cell

A plain right triangle in one corner of the cell, legs along the two edges, each
leg t = max(6, round(0.3 s)) px, filled with the player's `--player-colour-N`, no
outline, no text, ever. Corners are given in the order players arrive on the cell:
top-left, top-right, bottom-right, bottom-left (decided by the human on
2026-10-16). When a player leaves the cell, the others keep their corners. At most
4 are drawn; a fifth or later player is not drawn and nothing says "+k". A
disconnected player is not drawn (spec 013). My own selection is never a
triangle. This replaces the dashed borders of spec 013 and the initials and "+k"
labels of spec 035 (section 12).

Accessibilité mode (decided by the human on 2026-10-16): a switch in the Menu,
« Accessibilité » (« activée » / « désactivée »), off by default, remembered per browser like the other Menu
switches. While it is off, the triangles carry colour only, by the human's choice;
the Joueurs list of the Salon (name, state, current clue) says in words where each
player is. While it is on, each triangle is replaced by a small icon, one distinct
icon per player by join index (as the colours), drawn in that player's
`--player-colour-N`, in the same corners and the same arrival order, at most 4.
Colour is then no longer the only sign. Spec 035 AC-6 and AC-11 are refined
accordingly (section 12).

#### Player icons

Drawn in sheet 4.3 (`PICONS`, `ICON_NAMES`, `picon()` and the access branch of
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
3:1 on my selected cell (section 3). At 18 px cells four icons fit but touch the
letter; this is accepted, as players zoom (spec 006).

Elsewhere: wherever a player dot appears (stream messages, the Joueurs list, the
recap's « Qui a fait quoi », the roster swatch until it moves into the Salon), the
mode shows that player's icon at 12 px instead of the dot. The Auteurs legend
names players in their ink with no dot; it does not change.

### Clue cells

- Background `--nock-clue-bg`, text `--nock-clue-ink` (section 4), padding 2 px
  top and bottom, 3 px left and right.
- One clue fills the cell, centred vertically. Two clues share it in two equal
  halves, clue 0 on top, with a 1 px separator between them in clue ink at 55 %
  opacity, inset 14 % of the cell width on each side.
- Active clue: the half (or the whole cell for a lone clue) that holds my selected
  word's clue takes `--nock-selected`, radius 2 px (decided by the human on
  2026-10-16, drawn in sheet 4.2; spec 007 AC-1).
- Flag (spec 021): the filled red flag icon (section 5), in a square of side
  max(8px, 0.22 s) at the top-left of its own clue's half (top 0 of the half, left
  −2 px, so 1 px from the cell's left edge), on a clue blue-grey backing with a
  3 px bottom-right radius, the icon at 86 % of the square, fill and stroke
  `--nock-red`, stroke width 2, layer 2. A flagged second clue has its flag at the
  top-left of the lower half. The flag never moves the text. Top-left is the one
  corner of a clue no arrow uses.
- Shown reaction (spec 022): see "Reactions" in section 8.

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

Position of the box in the letter cell (as `arrowFor()` and `arrowMap()` in the
sheet). An arrow's target cell is the cell right of its clue cell for → and ↴,
the cell below for ↓ and ↳; an arrow whose target is outside the grid or a clue
cell is not drawn.

| Arrow | Box position |
| --- | --- |
| → (default) | left −1 px; vertical centre at 0.5 s |
| ↓ | top −1 px; horizontal centre at 0.5 s |
| ↳ (default) | top −1 px; left 0.06 s |
| ↴ | left −1 px; top 0.06 s |

Collision rules, applied per target cell (drawn in the sheet's « Two arrows in one
cell »):

1. A → whose target cell also receives a ↴: the → takes the low slot, vertical
   centre at 0.72 s; the ↴ keeps the top.
2. Otherwise, when two → share a target cell (only possible from one two-clue
   cell), the → of clue 0 is centred at 0.25 s and the → of clue 1 at 0.72 s.
3. A ↳ whose target cell also receives a ↴: the ↳ moves right, to left 0.4 s (top
   −1 px); the ↴ keeps the top-left corner.

The −1 px puts the box's edge on the grid line; the clipped column holds no
stroke (strokes start at 2 units). Measured during the design session on 68 px
cells: every arrow keeps at least 2.7 px from every letter A to Z.

### Drawing order

Top first, inside one cell (the sheet's z-index in brackets):

1. My selection border (7; the cell's outline).
2. Direction arrows (6).
3. Revealed notch (3).
4. Player triangles (2), and in clue cells the flag (2).
5. Catch-up ring (1).
6. The letter, or the clue text.
7. The flash overlay, then the background.

A shown reaction (8) sits over its clue cell and the cells around it (section 8).

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

Replaces the author band of spec 019, which is removed. Kept, toggled on and off
by each player, off by default (decided by the human on 2026-10-16).

- A switch in the Menu (section 8): « Auteurs » with the detail « activé » or
  « désactivé », remembered per browser, as the tint switch. (Note from the spec
  writer, 2026-10-22: decided by the lead's decision of 2026-10-22 on the human's
  instruction; it read "Whether it is remembered across reloads is OPEN (section
  15)".)
- When on, each letter is drawn in its finder's ink `--player-ink-N` (section 3),
  on whatever background the cell has.
- A revealed letter has no finder: it stays ink.
- A letter whose finder has left the room is drawn in plain ink (`--nock-ink`), as
  a letter with no finder; there is no departed grey (decided by the human on
  2026-10-16; the earlier `--nock-departed` token, #6B7079 then #5C616A, is gone).
- A pencil letter keeps its italics, in its finder's ink.
- The wrong-letter strike turns ink (a red strike would vanish on a red letter).
- A legend shows while the mode is on: « Auteurs : » then each player's name in
  their ink, weight 700, in join order, one space apart. It sits in the flow under
  the grid, centred, 8 px below it (the grid and legend form one column with an
  8 px gap); the grid shrinks by 38 px of height while the mode is on, so nothing
  else moves. Background `--nock-legend-bg`, 1 px line-grey border, radius 14 px,
  padding 4 px 12 px, gap 8 px, one line.
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

How the two rules combine: column when the window is landscape and either at
least 900 px wide and more than 500 px high, or at most 500 px high with the
in-app keyboard hidden; otherwise sheet. (Note from the spec writer, 2026-10-22:
decided by the lead's decision of 2026-10-22 on the human's instruction; it read
"How the two rules combine for phones narrower than 900 px held sideways is OPEN
(section 15)".)

### Phone and upright tablet (sheet layout)

Top to bottom, filling the window, nothing scrolls:

1. Top bar, 54 px high, white, 1 px line-grey bottom border, padding 0 4 px 0
   10 px. The timer on the left (button, no border, padding 0 4 px), then
   `margin-right: auto`, then five buttons 56 px wide and the bar's full height:
   Annuler, Aide, Salon, Clavier, Menu. Each holds its 22 px icon over its label
   (gap 2 px), navy, radius 6 px. Pressed (Aide, Salon, Menu while open; Clavier
   while the keyboard shows): word-blue background. (Note from the spec writer,
   2026-10-22: spec 044 proposes, pending the human's approval, that « Clavier »
   takes this slot on touch screens only; on a narrow window that is not a touch
   screen, which has no in-app keyboard, the slot holds « Crayon » (section 15).)
   - Unread badge on Salon (messages): top 5 px, right 8 px (section 11).
   - New events and no unread message: an 8 px red dot on Salon, top 8 px, right
     15 px.
   - Timer hidden (« Masquer le chrono », spec 027): the left slot holds a
     top-bar button « Chrono » with the chrono icon, `aria-label` « Afficher le
     chrono », which shows the timer again.
2. Connection band (spec 017), only while the connection is lost: see "Connection
   lost" below.
3. The grid area: all the height left, white, the grid centred, cells as large as
   fit with 8 px around (the sheet keeps 16 px in total on each axis), and the
   Auteurs legend under the grid while that mode is on.
4. Clue bar, 34 px high, navy, white text, in this order: ‹ button (36 px wide,
   chevron-left icon), the clue text centred with its direction glyph (→ or ↓, 80 %
   opacity, 6 px left margin), on one line with an ellipsis when too long; then
   « Réagir » (40 px wide, smile icon, `aria-label` spec 022's
   `reaction.button_label`); then « Je bloque » (40 px wide, flag icon); then ›
   (36 px wide, chevron-right icon). The two 40 px buttons have radius 6 px. Je
   bloque not pressed: white outline flag; pressed (`aria-pressed="true"`): white
   button background, navy filled flag. Text only: no author name, no pencil tag.
   Focus inside the bar: white ring, offset −4 px (section 11).
5. End-of-grid band (section 9), when the grid is full.
6. In-app keyboard (touch screens, spec 009): background `--nock-keyboard-bg`,
   padding 6 px 3 px 8 px, rows 6 px apart, keys 4 px apart and centred.
   - Rows: `A Z E R T Y U I O P`; `Q S D F G H J K L M`; `✎ W X C V B N ⇄ ⌫`.
   - Keys: 44 px high, flexible width up to 33 px, radius 5 px, `--nock-key`, ink,
     shadow `0 1px 0 var(--nock-key-shadow)`, no border. ✎ and ⌫ are wide: up to
     48 px, flex basis 48 px, grow 1.5. Icons 22 px.
   - ✎ pressed: navy key, white icon with `--nock-pen-fill` fill; every letter key
     then shows its letter italic in `--nock-pencil`.
   - ⇄ switches the selected cell between its across and down word (as a second
     tap on the cell, spec 007). ⌫ erases one letter (spec 008). No long press on
     ⌫ (decided by the human on 2026-10-16).
   - « Clavier » hides and shows the keyboard; the choice is remembered per
     browser. The grid takes the space back.
   - (Note from the spec writer, 2026-10-22: spec 044 proposes, pending the
     human's approval, keys 28 px high on a window at most 500 px high, so that a
     phone held sideways keeps 100 px of grid with the keyboard shown (section
     15). Once the grid is solved the keyboard goes away (section 9) and
     « Clavier » is disabled.)

### Computer and landscape tablet (column layout)

1. (Note from the lead, 2026-10-22: on a window at most 500 px high the column
   layout has the phone top bar of the section above instead; spec 044 Decision 8,
   section 15.) Top bar, 56 px high, white, 1 px line-grey bottom border, padding 0 16 px, gap
   4 px, items centred vertically, in this order: the Nock mark and « Nock »
   (gap 8 px); the grid name « Grille n° N · Force F » (14 px left margin, then
   `margin-right: auto`); the timer (10 px right margin), or « Chrono » while the
   timer is hidden; then buttons 38 px high, padding 0 12 px, radius 6 px, gap
   6 px, icon 20 px beside its label: Annuler, Crayon, « Aide ▾ », Salon, Clavier
   (touch screens only), Menu. Pressed: word-blue background. Unread badge on
   Salon: top 2 px, left 24 px; the new-events dot, with no unread message, at the
   same place. `room-heading` (spec 040) is visually hidden in the room, on a
   computer and on a phone. (Note from the spec writer, 2026-10-22: the dot's place
   and `room-heading` are decided by the lead's decision of 2026-10-22 on the
   human's instruction; section 15, items 9 and 10.)
2. Connection band under the top bar while the connection is lost.
3. Body: the main area and, on its right, the side column.
   - Main area: padding 12 px, the grid centred and as large as fits in all the
     space left; under it the clue bar, as wide as the grid (grid width + 1 px);
     then the end-of-grid band at the same width; on touch tablets the in-app
     keyboard under them, full width of the main area (margins −12 px, top 10 px).
   - Side column: 340 px wide, white, 1 px line-grey left border; the Salon
     (below). It is open by default in this layout, with « Salon » pressed.
     « Salon » closes and opens it; the grid refits each time. A column the player
     closed stays closed next time, per browser (decided by the human on
     2026-10-16).
4. Nothing else is permanently on screen. Chat, players, progress, invitation,
   host settings and the account open on demand.

### Aide menu (« Aide »)

A popover (section 11) under the button, min width 220 px:

- when the selected cell holds a pencil letter (spec 020), first the item
  « Confirmer la lettre au crayon » (weight 600, detail ✎), then a separator;
- heading « Vérifier »; items « La lettre », « Le mot », « La grille » (spec 023);
- separator;
- heading « Révéler »; items « La lettre » with the detail « n restantes », « Le
  mot » with « n restant » or « n restants » (spec 024's budget).
- An item whose budget is spent stays in place, disabled: its text and detail
  muted, the detail « Plus de lettre » or « Plus de mot » (`reveal.letter_none`,
  `reveal.word_none`), no hover; the menu keeps its shape (decided by the human on 2026-10-22, screens sheet P7; spec 043 AC-8
  draws it so).

The pencil toggle itself is the ✎ key on touch screens and the « Crayon » top-bar
button on a computer.

### Menu (« Menu »)

A popover anchored to the right (6 px from the right edge on a phone), in this
order: « Auteurs » (detail « activé » / « désactivé »); « Mots des autres »
(detail « teintés » / « sans teinte »); « Accessibilité » (detail « activée » /
« désactivée », off by default, per browser, section 6; its place in the list is
the spec writer's pick); « Inviter » (detail « lien »); « Réglages
de l'hôte » (host only); « Compte » (spec 033; not drawn in the sheet's Menu, the
spec writer's place for it, decided by the lead's decision of 2026-10-22 on the
human's instruction, note from the spec writer of that day, section 15 item 7);
separator; « Masquer le chrono » (« Afficher le
chrono » while hidden); « Retour aux grilles ».

On a phone, a scrim (`--nock-scrim`) covers everything below the top bar (top
54 px) while a menu or a sheet is open; a tap on it closes them. Menus sit 58 px
from the top.

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
3. Discussion: one stream, oldest first, padding 10 px 16 px, items 8 px apart,
   then the message box.
   - A message: a player dot (section 11) and the name in weight 700 ink, gap
     6 px, then the text.
   - An event: one line, 0.82rem, 16 px left padding, one line per event of spec
     013 (no grouping):

     | `data-kind` (spec 013) | Pictogram | Colour |
     | --- | --- | --- |
     | `player_joined` | → | muted |
     | `player_left`, `player_removed`, `player_timed_out` | ← | muted |
     | `check` | ✓ | muted; green when the check found no wrong letter |
     | `reveal` | ▲ | orange-red |
     | `flag` | inline filled flag icon | muted |
     | `room_locked`, `room_unlocked`, `settings_changed`, `host_changed` | none | muted |

     Catch-up lines (spec 034) take the same look. There is no line for typed
     letters or filled words (the sheet's « a rempli » line is dropped).
   - Message box: padding 8 px 12 px 12 px, 1 px line-grey top border, gap 8 px;
     the input with a 1 px rule-grey border, radius 18 px, padding 7 px 12 px; the
     « Envoyer » pill (section 11). Spec 022's chat notes (« Patientez avant
     d'envoyer. », « L'hôte a coupé votre discussion. ») show as one muted line
     under the input (500 0.85rem/1.3, 12 px left padding), one at a time; while I
     am muted, the input and « Envoyer » are disabled (section 11) (decided by the human on 2026-10-22, screens sheet P5).
4. Joueurs (specs 011, 013, 014): padding 10 px 16 px, rows 8 px apart, 0.95rem.
   Each row: player dot; name, « (vous) » after my own (my name weight 700); the
   « hôte » tag after the host's name (section 11); then on the right the state
   word « actif », « inactif » or « déconnecté » with spec 035 AC-7's styling
   (italic name for inactive, italic and struck through for disconnected), « · »
   and the player's current clue; for the host, a small secondary « Retirer »
   button on each other player's row. Under the rows, « Lien d'invitation » (dialog
   section heading), the URL box (1 px rule-grey border, radius 6 px, padding
   8 px 10 px, one line, full width), the primary « Copier le lien », and after a
   copy the green confirmation line « Lien copié ». « Inviter » in the Menu opens
   the Salon on this tab. (Note from the spec writer, 2026-10-22: spec 043 draws
   each row on two lines, the state and the current clue under the name, and puts
   the host's « Couper » (spec 022's mute) beside « Retirer »; pending the human's
   approval of spec 043, section 15.) (Note from the lead, 2026-10-22: the host's
   « Couper » / « Rétablir » beside « Retirer », as small secondary buttons, is
   decided by the human on 2026-10-22, screens sheet P5; spec 022's separate
   « Sourdine » block goes. The row's two lines are spec 043's, decided by the
   human's approval of spec 043 on 2026-10-22, section 15 « Where the screens sheet
   met spec 043 ».)

### 3-second notes

- One line, ink background, white text (section 4), padding 8 px 12 px, radius
  6 px, shadow `0 6px 18px -8px var(--nock-shadow-strong)`, centred over the top
  edge of the grid area, 8 px down, layer 6 of the grid area. No layout shift.
- A line may start with its pictogram (the inline flag icon for a flag, ▲, →).
- One at a time; a new note replaces the current one. It shows for 3 s, then fades
  out in 0.25 s (opacity only, no slide). With `prefers-reduced-motion: reduce` it
  appears and goes without transition.
- A tap opens the Salon on that line.
- Not shown while the stream is visible (Salon open on Discussion), and held back
  while the vote banner shows; they come after it goes.
- Which events: others' messages (« Bruno : … »), « Je bloque », reveals, others'
  checks, joins and departures, and my own reaction. Never typed letters. Also two
  short answers of the room: « Rien à annuler. » after « Annuler » with nothing to
  undo (P9), and a vote's result, « Vote accepté. », « Vote refusé. » or « Temps
  écoulé, vote annulé. », once its banner has gone (P6) (decided by the human on 2026-10-22, screens sheet).

### Reactions (spec 022)

- « Réagir » in the clue bar (above) opens the picker; a second press closes it.
- Picker: `role="group"`, `aria-label` spec 022's `reaction.picker_label`
  (« Réactions » in the sheet), the five reactions 👍 👏 😂 😮 🤔 with spec 022's
  names. Over the bottom of the grid area, centred, 8 px above its bottom edge
  (so above the clue bar), layer 9: white, 1 px line-grey border, radius 24 px,
  padding 5 px, gap 2 px, shadow `0 10px 24px -10px var(--nock-shadow)`. Each
  reaction a 40 by 40 px round button (radius 20 px), no background (word blue on
  hover), emoji 22 px.
- A shown reaction: a white pill centred over its clue cell, 1 px line-grey
  border, radius 12 px, padding 2 px 6 px, emoji 16 px, line height 1.2, shadow
  `0 4px 10px -4px var(--nock-shadow-soft)`, layer 8, for 3 s (spec 022). On a
  two-clue cell it is centred on its own clue's half, as spec 022 does. (Note from
  the spec writer, 2026-10-22: decided by the lead's decision of 2026-10-22 on the
  human's instruction; it read "For a two-clue cell the sheet draws none (section
  15)".)

### Connection lost (spec 017)

A band under the top bar, full width, while the room is reconnecting: background
`--nock-clue-bg`, 1 px line-grey bottom border, padding 8 px 12 px, gap 10 px,
items aligned to the top; an 8 px red dot (`--nock-red`, 5 px from the top), then
the ink text (500 0.85rem/1.3) « Connexion perdue. Vous pouvez continuer : vos
lettres seront envoyées au retour du réseau. ». The grid stays usable. The band
goes when the room is back. The band pushes the grid area down; nothing covers the
grid. `room-status` (« Reconnexion… », spec 040) may then be visually hidden
(class `visually-hidden`), read by screen readers only.

### Room sheets: host settings and account

On a phone these open as a bottom sheet from under the top bar (scrim from 54 px),
white, radius 16 px on the top corners, padding 14 px 18 px 18 px, gap 14 px; on a
computer as the recap's dialog (440 px, section 9).

- Host settings (spec 014), from Menu « Réglages de l'hôte »: title « Réglages de
  l'hôte »; a switch row « Verrouiller le salon » (switch, section 11); the field
  « Aide » with a three-way segmented control « libre » | « par vote » |
  « désactivée » (section 11); two number fields side by side, 16 px apart,
  « Lettres à révéler » and « Mots à révéler » (inputs 64 px wide, text centred);
  primary « Enregistrer », right-aligned.
- Account (spec 033), from Menu « Compte » or the catalogue's « Compte ». Signed
  out: title `account.dialog_heading`, text `account.dialog_intro` (muted 0.9rem),
  field « Adresse e-mail », primary « Recevoir le lien », after sending the green
  line (« Lien envoyé à … Il est valable 30 minutes. »), secondary « Fermer »
  right-aligned. Signed in: title « Votre compte », « Connecté avec {email} », the
  text link « Gérer mon compte », secondary « Fermer » right-aligned. Outside a
  room (the catalogue's « Compte »), the intro is `account.signed_out_intro`, since
  `account.dialog_intro` speaks of « ce salon » (decided by the human on 2026-10-22, screens sheet P13).

### Entry and not-found pages (specs 012, 040)

Pages shown instead of the room: a top bar 54 px with the Nock mark and « Nock »
only (padding 0 14 px), then the page on `--nock-page`, padding 20 px 16 px, gap
14 px, holding:

- the room code line « Salon {code} » (muted, 600 0.85rem), above the card, on
  room pages;
- one card (section 11).

Cards:

- Nickname (spec 012): title « Choisissez un pseudo »; field « Pseudo »; when
  refused, the input's border turns red and the error text shows in red under the
  field; primary « Entrer dans le salon ».
- Entry statuses (specs 011, 012, 040: full, locked, not found, removed, replaced,
  throttled): the status text as the card title, a muted line when the spec gives
  one, secondary « Voir les grilles ».
- Not found (spec 040): title « Page introuvable », primary « Voir les grilles »
  (an addition to spec 040), no room code line.
- A room that is not found or has expired (spec 032 deletes an expired room, so
  both read « Ce salon n'existe pas. »): the status card with the muted line « Un
  salon est effacé 30 jours après sa dernière modification. » (a new `fr.json`
  key) and « Voir les grilles » primary, the only way on (decided by the human on 2026-10-22, screens sheet P3).

On a computer (and any window wider than a phone), these pages, and the plain
pages below, use the 56 px top bar of the catalogue (section 10) and the phone's
column, centred, at most 420 px wide, 48 px under the top bar, on `--nock-page`
(decided by the human on 2026-10-22, screens sheet P1).

### Plain pages: account, shared recap, operator (specs 028, 033, 038)

Decided by the human on 2026-10-22 (screens sheet P11, P12, P14); drawn in the
screens sheet, parts 5 to 7.

- Shared recap `/recap/<token>` (spec 028): an entry page with no room code line
  and one card: title « Grille terminée » (`share.heading`), « Grille n° N »
  (card secondary text), « Temps : m:ss » in the recap time style (section 4),
  « Équipe : … » (card text), primary « Voir les grilles ». The unavailable recap
  is the same card with the title « Ce bilan n'est pas disponible. » and the
  button.
- Account page `/account` (spec 033): an entry page with one card titled « Mon
  compte ». Signed in: « Connecté avec {email} », the text link « Retourner au
  salon {code} » when there is one, then « Se déconnecter » and « Supprimer mon
  compte », both secondary, side by side (gap 8 px, wrapping). « Supprimer mon
  compte » asks once more in the same card, under a line-grey divider: the warning
  (`account.delete_warning`) in ink, then « Supprimer définitivement » (primary)
  and « Garder mon compte » (secondary); while asked, « Supprimer mon compte » shows
  pressed (quiet). No red button: red keeps its one job (section 2; D1). The other
  states are one line in the card (« States » below): « Connexion… » muted, the
  invalid link as an error line above the e-mail field and « Recevoir le lien »,
  « Votre compte a été supprimé. » as a confirmation line with « Voir les grilles »
  primary, the generic error as an error line.
- Operator page `/ops` (spec 038): the catalogue's frame (top bar with the brand
  only, the 920 px column on `--nock-page`), heading « Exploitation » in the
  catalogue heading style. The token form is one card: the field « Jeton
  d'opérateur » (a password input), the error line « Jeton refusé. » or « Trop
  d'essais… » under it, primary « Ouvrir ». Then a card « Tableau de bord » (card
  title): the field « Période » with the three periods as the catalogue's filter
  chips, then one tile per figure (white, 1 px line-grey border, radius 8 px,
  padding 12 px 14 px, in a grid of `repeat(auto-fill, minmax(min(100%, 270px),
  1fr))`, gap 10 px) holding the `fr.json` line as it is. Then a card « Relecture
  d'un salon »: the field « Code du salon » with « Relire » (primary) beside it;
  the edits, one line each (0.85rem, tabular), the current step on word blue and
  weight 600, later steps muted; the grid at the chosen step, drawn with the cells
  of section 6 at 44 px (36 px on a phone) with no clue text, no arrows and no
  players; under it the field « Étape » with the slider (section 11) and « Étape n
  sur m » (card secondary text). On a computer the edits sit left of the grid, gap
  20 px; on a phone the grid, the slider, then the edits.

### States: opening, loading, empty, error

Decided by the human on 2026-10-22 (screens sheet P2, P4, P10). One rule for every
page: a state is one line of text where its content will be; muted (`--nock-muted`,
the page's text size) while waiting or when empty, an error line (section 11) when
something failed, a confirmation line when done. No spinner, no skeleton.

- Opening the room (P2): before the first snapshot, the room's top bar is in place
  (no timer yet, no grid name), and the grid area holds one muted line,
  « Connexion… » or « Entrée dans le salon… » (spec 040's `room-status`); no clue
  bar, no keyboard. A refusal before the join then shows its card (above); a final
  status after a snapshot shows spec 043's status band.
- Catalogue (P4): « Chargement… », « Aucune grille pour le moment. » (the chips are
  not shown) and « Aucune grille de cette force. » (the chips stay) as muted lines
  under the heading, « Impossible de charger les grilles. » as an error line there;
  a failed « Jouer » puts « Impossible de lancer la partie. Réessayez. » as an error
  line inside its card, under its text. « Mes salons » shows nothing while it loads
  and has no section when there is no room; « Impossible de charger vos salons. »
  is an error line under its heading.
- Recap (P10): inside its sheet or dialog, the title, then « Chargement du bilan… »
  muted or « Le bilan n'est pas disponible. » as an error line, and « Fermer ».

### Focus and keyboard

The sheets, the column, each menu and the picker are labelled regions. Opening
one moves the focus into it; Échap closes it and puts the focus back on the button
that opened it.

### Layers of the room page

| Layer | z-index |
| --- | --- |
| 3-second note | 6 |
| Phone scrim | 7 |
| Menus, popovers, sheets, vote banner, shown reaction | 8 |
| Reaction picker | 9 |
| Recap overlay (dialog or sheet with its scrim) | 20 |

## 9. Overlays

### Vote (spec 025)

A banner over the top of the grid area: 8 px from its top, left and right edges,
white, 2 px navy border, radius 10 px, padding 10 px 12 px, gap 8 px, shadow
`0 10px 24px -12px var(--nock-shadow)`, layer 8. Content: the question
(`vote.question.*`); a row with « Oui » (primary) and « Non » (secondary), both with
padding 7 px 16 px, and on the right the seconds left (« 18 s »); then a progress
bar 4 px high, radius 2 px, word-blue track, navy fill for the time left. No
layout shift. Notes wait while it shows.

Once I have voted, « Oui » and « Non » give way to the muted line « Vote
enregistré. En attente des autres joueurs… » (500 0.85rem/1.3) in their row, the
seconds kept on the right; the player who asked sees « En attente des autres
joueurs… » there from the start. The result is a 3-second note when the banner
goes (section 8) and a line in the stream (decided by the human on 2026-10-22, screens sheet P6).

### End of grid (spec 026)

A band under the clue bar, padding 8 px 12 px, gap 10 px, text 600 0.95rem/1.2:

- Finished: background `--nock-green-bg`, green text « ✓ Grille terminée, bravo ! »
  and, pushed right, the primary button « Voir le bilan » (padding 7 px 12 px,
  0.85rem). The recap-open control moves here (spec 028 AC-7 change). The in-app
  keyboard goes away once the grid is solved.
- Full but wrong: background `--nock-clue-bg`, navy text « Grille complète, mais
  pas encore juste. ». No red, no cell changes look. It sits between the clue bar
  and the keyboard, which stays.

### Recap (spec 028)

Opens only when asked.

- Phone: a bottom sheet over a `--nock-scrim-dialog` scrim covering the whole
  window, radius 16 px on the top corners, padding 14 px 18 px 18 px, no grab
  handle.
- Computer: a dialog 440 px wide, centred, over a `--nock-scrim-dialog` scrim
  covering the whole window, white, radius 12 px, padding 20 px 22 px, gap 14 px,
  shadow `0 20px 40px -16px var(--nock-shadow-strong)`.

Content in order (spec 028's strings): title « Bilan de la partie »; « Temps :
m:ss » (recap time style); the lines « Vérifications : n », « Révélations : … »,
« Lettres révélées : n » (gap 4 px); heading « Qui a fait quoi »; one row per player
(dot, name, « (vous) » in muted after mine, and on the right « n lettres · n mots
complétés »), rows 8 px apart (on the phone the value wraps under the name, 18 px
in); heading « Lien à partager »; the URL box and « Copier le lien » (secondary,
padding 8 px 12 px); « Fermer » (primary), right-aligned. Échap closes it.
After a copy, « Copier le lien » keeps its label and the confirmation line « Lien
copié » shows under the URL box, as in the Joueurs tab (section 8); spec 028
changes the button's text today and is refined (decided by the human on 2026-10-22, screens sheet P16). Loading and
unavailable: section 8 « States ».

## 10. Catalogue (spec 004, with 029, 032, 033)

- Top bar 56 px as the computer room's, with the Nock mark and « Nock », and on the
  right « Compte » (spec 033): a computer top-bar button with no icon, pressed
  while its sheet is open (34 px high on a phone).
- Main column: max width 920 px, centred, padding 24 px (16 px on a phone), gap
  16 px, in this order:
  1. heading « Grilles » (section 4);
  2. « Mes salons » (spec 032), when the player has open rooms on this device or
     account: section heading, then list rows (section 11), 10 px apart. Each row:
     title « Grille n° N · W × H » (and the « Terminée » pill when solved), « Joueurs
     : … », « Dernière activité : {date} à {time} », and « Reprendre » (primary;
     secondary when the room is solved);
  3. the filter row: label « Force », then chips « Toutes », « Force 1 » to
     « Force 4 »: radius 16 px, padding 7 px 14 px, 1 px line-grey border, white,
     navy text. Pressed: word-blue background, navy border;
  4. the grid cards;
  5. « Grilles terminées » (spec 029), when the history holds finished grids:
     section heading, then list rows: title « Grille n° N · W × H », « Terminée le
     {date} · en {time} · Avec {names} » or « … · En solo », and secondary
     « Rejouer ».
- Cards in a grid: `repeat(auto-fill, minmax(min(100%, 400px), 1fr))`, gap 12 px,
  so one per row on a phone. A card: 1 px line-grey border, radius 8 px, padding
  12 px 14 px, gap 14 px, white:
  - a generic grid drawing, built from the grid's width W and height H only
    (spec 004's `GridSummary` is unchanged): it shows the proportions, not the
    real layout. An SVG 51 px high and round(51 × W / H) px wide (39 by 51 for 13
    by 17), viewBox W × 10 by H × 10 (10 units per cell): white cells; clue cells
    in `--nock-thumb` in row 0 at the even columns (0, 2, 4, …) and in column 0 at
    the even rows from 2 (2, 4, …); inner grid lines in `--nock-line`, 1 unit
    wide; a 1 px rule-grey border. Shown only while the cards sit more than one
    per row (wide windows); with one card per row (phones) the card has no
    drawing and keeps its text only. (Decided by the human on 2026-10-17, sheet
    4.6 `genericThumb()`; it replaces the real-shape thumbnail, which needed clue
    positions from the API.);
  - « Grille n° N » and, after it, the status pill: « Commencée » (word blue,
    navy) or « Terminée » (green background, green text), radius 12 px, padding
    3 px 9 px;
  - « Publiée le … »;
  - four Nock marks (8 by 11 px, gap 2 px), navy up to the grid's force and
    `--nock-thumb` after, then « Force F · W × H · N mots ». Force is written, so
    it never relies on the drawing alone;
  - the primary button « Jouer » on the right (padding 9 px 16 px).
- Loading, empty and error states: section 8 « States » (decided by the human on 2026-10-22, screens sheet P4).
- Grid credits (spec 005) are not on the screens while no spec sends them to
  players; when one does, they take one muted card line (« Auteur : … ») (decided by the human on 2026-10-22, screens sheet
  D2).

## 11. Components

| Component | Look |
| --- | --- |
| Button, all | radius 6 px, padding 10 px 16 px, weight 600, 0.95rem, line height 1, 1 px border |
| Primary | navy background, white text, transparent border |
| Secondary | white background, navy text, navy border |
| Quiet | word-blue background, navy text, transparent border |
| Small button | any variant, padding 6 px 10 px, 0.8rem |
| Disabled (any) | clue blue-grey background, muted text, line-grey border, `cursor: not-allowed`; text still 4.5:1 |
| Focus ring | `outline: 2px solid var(--nock-navy)`, `outline-offset: 2px`, on `:focus-visible`. On a navy surface (the clue bar): white, offset −4 px |
| Menu / popover | white, radius 8 px, padding 6 px 0, min width 220 px, shadow `0 12px 30px -10px var(--nock-shadow)`, no border |
| Menu item | full-width button, padding 10 px 16 px, 500 1rem/1.2, navy, left-aligned; detail on the right (gap 12 px), muted, not italic, tabular; hover: word-blue background |
| Menu heading | margin 6 px 16 px 2 px, 600 0.7rem, uppercase, letter spacing 0.08em, muted |
| Menu separator | 1 px line-grey top border, margin 4 px 0 |
| Top-bar button | navy icon and label, transparent background; pressed: word blue |
| Badge | red background, white 700 0.62rem/1 text, padding 2 px 4 px, radius 8 px |
| New-events dot | 8 px red circle |
| 3-second note | section 8 |
| Bottom sheet | white, radius 14 px top with grab handle (Salon) or 16 px top without (other room sheets, recap), section 8 |
| Scrim | `--nock-scrim` (menus, sheets) or `--nock-scrim-dialog` (recap) |
| Card | white, 1 px line-grey border, radius 10 px, padding 18 px 16 px, gap 12 px |
| List row | white, 1 px line-grey border, radius 8 px, padding 12 px 14 px, gap 12 px, items centred; text column gap 3 px (title 700, lines 0.85rem muted); its button on the right |
| Field | label above its input, gap 6 px, label 600 0.85rem/1.2 ink |
| Text input | 1 px rule-grey border, radius 6 px, padding 10 px 12 px, 400 1rem/1.2, ink on white; in error: red border. Message box: radius 18 px, padding 7 px 12 px. URL box: padding 8 px 10 px, 0.85rem, one line with ellipsis |
| Number input | a text input 64 px wide, text centred |
| Error line | red, 500 0.85rem/1.3, under its field |
| Confirmation line | green, 500 0.85rem/1.3 |
| Switch | track 42 by 24 px, radius 12 px, rule grey when off, navy when on; knob 18 px white circle, 3 px from the top, left 3 px (off) or 21 px (on). In a switch row: label left (500 0.95rem/1.2), switch right, gap 10 px |
| Segmented control | inline row with a 1 px navy border, radius 6 px, clipped; options padding 8 px 10 px, 600 0.85rem/1, navy, 1 px navy dividers; the chosen one navy background, white text |
| Tag (« hôte ») | clue blue-grey background, navy 600 0.72rem/1.3, radius 10 px, padding 2 px 8 px |
| Pill button (« Envoyer ») | word blue, navy, 600 0.85rem, radius 14 px, padding 6 px 12 px, no border |
| Text link | navy, weight 600 |
| Player dot | 10 px circle, player colour, ring `0 0 0 1px var(--nock-dot-ring)` |
| Reaction picker, shown reaction | section 8 |
| Slider | a native range input styled: track 6 px high, radius 3 px, `--nock-word`; the part before the knob `--nock-navy`; knob 18 px navy circle; the focus ring of this table on the knob. Full width of its field (decided by the human on 2026-10-22, screens sheet P15) |
| Destructive action | no variant of its own: a primary or secondary button after a confirmation step in place, never red (red means "look here", section 2) (decided by the human on 2026-10-22, screens sheet D1) |
| State line | section 8 « States » |

## 12. Spec impact

Refinements to make, each with dated notes, before the matching build step
(section 14).

| Spec | Status | What contradicts or is missing | Change |
| --- | --- | --- | --- |
| 004 | done | Catalogue look (AC-1, AC-3 show the fields and progress, no look) | Section 10 criteria, with the generic grid drawing from width and height; no HTTP or `GridSummary` change (decided by the human on 2026-10-17) |
| 005 | done | Credits on the catalogue and grid page are not drawn | Gap: the spec writer proposes a card line here first |
| 006 | done | AC-2: arrows drawn in the clue cell on its side; AC-3: separator look; letter 0.55 s and clue 0.11 s / 0.09 s today; empty cells grey #C9CDD8; AC-5 and AC-7 fit a page without top bar or clue bar of this design | Arrows into the letter cell with the collision rules (section 6); separator 55 %, 14 % insets; letter 0.56 s; clue max(6px, 0.145 s); empty cells rule grey; fit rules with the new layout |
| 007 | done | AC-1: the selected word's clue is highlighted (yellow today); selected cell yellow with a 3 px ink outline; AC-4: clue bar look | Selected blue and 2 px navy outline; active clue half in selected blue; clue bar of section 8 |
| 009 | done | AC-3: third row `WXCVBN` plus `key-delete` only; key size and colours; no Clavier control | ✎ and ⇄ keys, key geometry (section 8), « Clavier » hides the keyboard |
| 010, 011 | done | The share link and copy button sit on the room page | Into the Joueurs tab's « Lien d'invitation » (Menu « Inviter » opens it); also changes spec 035 AC-12's Tab walk, which starts at `share-link` |
| 012 | done | Palette values; nickname form and entry statuses look; roster on the page | Section 3 values (spec 041); nickname card and status cards (section 8); roster into the Joueurs tab |
| 013 | done | AC-2, AC-3: dashed border in the player's colour on the cell; tint 28 % today, always on; AC-5, AC-7, AC-8 and "Client: feed height": the feed is stacked above the grid and "never beside the grid"; AC-6: roster and feed on the page | Corner triangles (section 6); tint 16 % with the « Mots des autres » toggle; feed lines become stream events (section 8 table), in the sheet or the column; roster becomes the Joueurs tab |
| 014 | done | Host panel and roster remove buttons on the page; AC-7 to AC-10 measure their small-window layouts | Host settings sheet from Menu « Réglages de l'hôte » (switch, segmented control, number fields); « Retirer » in the Joueurs rows; AC-7 to AC-10 rewritten for the new places |
| 016 | done | Flash basis: the cell takes the replacer's full colour, with a text colour per player | Replacer's colour at 38 % over white, ink letters (spec 041 draws it as an overlay so AC-2's swatch check still holds) |
| 017 | done | Connection banner look and place | Connection band under the top bar (section 8); `room-status` may be visually hidden |
| 018 | done | Undo button look and place | « Annuler » in the top bar (section 8) |
| 019 | done | The whole author band (AC-1, AC-2, AC-5); AC-4 « Lettre de … » in the clue bar; switch in the toolbar | Auteurs mode of section 7; switch in the Menu; legend under the grid instead of the clue bar line |
| 020 | done | `pencil-toggle` and `confirm-pencil` in the toolbar; AC-7 layout | ✎ key on touch screens, « Crayon » in the computer top bar; confirm as the first Aide item while a pencil letter is selected |
| 021 | done | `flag-button` in the toolbar; marker position and size (AC-9), the second clue's flag under the separator today | Je bloque in the clue bar with its pressed state; flag icon of section 6 at the top-left of its own half |
| 022 | done | Chat panel drawn over the page (decision 6, AC-17); `chat-toggle` and `react-button` in the toolbar (AC-5); chat notes (AC-19); reaction look (AC-4) | Discussion tab of the Salon; « Salon » with the red unread badge and the new-events dot; « Réagir » in the clue bar between the clue text and Je bloque; picker over the bottom of the grid area; reaction pill over the clue cell; 3-second notes |
| 023 | done | `check-panel` in the toolbar (AC-9); strike look | Aide menu « Vérifier »; strike of section 6; check lines in the stream |
| 024 | done | `reveal-panel` in the toolbar (AC-7, AC-8); `reveal-mark` in the top-right corner, at least 6 px and a quarter of the side (AC-9), 3:1 during a flash | Aide menu « Révéler »; bottom-centre notch of section 6, ink during a flash, the design's size (both decided on 2026-10-22; AC-9 refined by spec 042) |
| 025 | done | Vote banner look; AC-4 hides `check-panel` and `reveal-panel` in none mode | Section 9 banner; in none mode « Aide » is hidden (to confirm in the refinement) |
| 026 | done | `grid-status` look; AC-10 puts the status in the clue bar's row on windows at most 500 px high | Band under the clue bar (section 9): finished replaces the keyboard, full-but-wrong sits above the keyboard; AC-10 rewritten |
| 027 | done | `timer`, `timer-toggle`, `chat-toggle` are the first three toolbar elements (AC-8); « ⏱ » toggle | Timer in the top bar; « Masquer le chrono » in the Menu; « Chrono » in the timer's slot while hidden |
| 028 | approved | AC-7: `recap-open` in the toolbar right after `chat-toggle`; AC-10 dialog sizes | « Voir le bilan » in the end band; sheet on a phone, 440 px dialog on a computer (section 9) |
| 029 | approved | History list not drawn before | « Grilles terminées » section of the catalogue (section 10) |
| 032 | approved | « My rooms » list not drawn before | « Mes salons » section of the catalogue (section 10) |
| 033 | approved | `account-open` is the last control of `room-toolbar` | « Compte » in the room Menu and in the catalogue's top bar; account sheet or dialog (section 8) |
| 034 | approved | AC-2: changed cells highlighted for 5 s, no look | Catch-up ring (section 6); lines in the stream |
| 035 | done | AC-2: focus outline 3 px blue today, and "3:1 against the page background" fails for a white ring on navy; AC-6 initials; AC-11 slots and "+k"; AC-7 roster states; AC-12 lists named `roster` and `activity-feed`; "Reduced motion" out of scope | 2 px navy ring (spec 041); measure against the surface behind the ring; AC-6 and AC-11 refined: the non-colour sign of a player's cursor is the Accessibilité mode's icons (section 6) plus the Joueurs list, and triangles stay colour-only while the mode is off (decided by the human on 2026-10-16); AC-7 and AC-12 follow the Salon lists; notes respect reduced motion |
| 040 | done | `room-heading` (« Salon {code} ») and `room-status` shown on the page; not-found page has no way back; styles were "not binding" | « Salon {code} » above the entry cards; `room-status` visually hidden while the connection band shows; « Voir les grilles » on the not-found card (an addition); styles now follow this file |

(Note from the lead, 2026-10-22: the screens sheet's decisions (section 15) add
these refinements: 022, the chat notes under the message box and the mute in the
Joueurs rows (P5, as spec 043 does); 024, spent reveal items disabled in place (P7,
as spec 043 AC-8 does); 025, the line after a vote and the result notes (P6); 018,
« Rien à annuler. » as a note (P9, as spec 043 AC-26 does); 028, the recap's states
(P10), the « Lien copié » line (P16) and the shared recap page (P11); 032 and 040,
the expired room's line and its new `fr.json` key (P3); 033, the account page and
deletion (P12) and the sheet's intro outside a room (P13); 038, the operator page
(P14, P15); 004, 029 and 032, the catalogue's states (P4); 012 and 040, the plain
pages on a computer (P1) and the opening room (P2).)

New specs, numbers proposed in build order (section 14): 041 visual foundation
(written); 042 grid cells (written); 043 room layout (written); then keyboard,
Auteurs mode, catalogue, overlays, remaining screens. (Note from the spec writer,
2026-10-22: 042 written; its "Refined specs" table lists the criteria of 006, 013,
019, 021, 024, 034, 035 and 041 that it changes.) (Note from the spec writer,
2026-10-22: 043 written; its "Refined specs" table lists the criteria of 011, 013,
014, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028, 033, 035 and 042 that it
changes, and notes 007, 010, 012, 017, 018, 034 and 040. It also takes, from step 5, the
end band's look and « Voir le bilan » in it, since the toolbar that held that
button goes.) (Note from the spec writer, 2026-10-22: 044 keyboard written; its
"Refined specs" table lists the criteria of 020, 026 and 043 that it changes, and
notes 009 and 035. It also takes, from step 5, hiding the in-app keyboard once the
grid is solved.)

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
   - the cell geometry, the arrow collision rules and the drawing order of
     section 6;
   - contrast of section 2 holds in every state the spec covers, flashes
     included;
   - the layout rules of section 8, and that nothing extra is permanently on
     screen;
   - focus ring and Échap behaviour of sections 8 and 11;
   - the spec cites the sections it applies;
   - every change of look is drawn in the sheets in the same change (section 1
     rule 3), and the screens sheet's HTML is what its generator builds.
6. The sheets stay in `docs/design/` as the visual reference, updated with this
   file in the same change: `cell-sheet.html` by hand, `screens-sheet.html` from
   `docs/design/screens_sheet/` (`uv run python docs/design/screens_sheet/build.py`).
   (Note from the lead, 2026-10-22: the screens sheet and its generator added; the
   item read "The sheet stays in `docs/design/` as the visual reference, updated
   with this file.")

## 14. Build order

Each step leaves the app working and every test passing.

1. Foundation: tokens, player colours, fonts, icons, buttons, focus ring, menus,
   badges, notes (spec 041). Today's screens take the token colours with no layout
   change.
2. Grid cells: section 6 (with specs 006, 007, 013, 016, 021, 023, 024, 034, 035
   refined), with the Accessibilité mode's icons (spec 042). The notch item it
   needed is settled (decided on 2026-10-22, section 15).
3. Room layout: top bar, sheet and column, Salon, 3-second notes, Aide and Menu,
   connection band, reactions, room sheets (specs 010, 011, 013, 014, 017, 018,
   020, 022, 023, 024, 027, 033, 035, 040 refined). The notch item it needed is
   settled (decided on 2026-10-22, section 15).
4. Keyboard: ✎, ⇄, « Clavier » (specs 009, 020 refined).
5. Auteurs mode, catalogue and its sections, entry pages, overlays (specs 019,
   004, 012, 025, 026, 028, 029, 032, 040 refined), and the screens sheet's plain
   pages and states: the account page, the shared recap page, the operator page,
   the opening room and the states of section 8 (specs 028, 033, 038 refined).
   (Note from the lead, 2026-10-22: the plain pages and states added, decided by the
   human on 2026-10-22.)

(Note from the spec writer, 2026-10-22: steps 2 and 3 read "Needs the DEFERRED,
high notch item settled first"; the lead decided it on 2026-10-22 on the human's
instruction. The human's instruction of 2026-10-22: the game is now built on the
full design system; competitive modes (epic E8) wait.)

## 15. Open decisions

### Decided by the human on 2026-10-16

- Another player's word: tinted at 16 %, and each player can turn it off from the
  Menu (« Mots des autres » : « teintés » / « sans teinte »), per browser, on by
  default (section 6).
- Auteurs mode: kept, toggled from the Menu, off by default (section 7).
- A closed side column stays closed next time, per browser (section 8).
- No long press on ⌫ to erase the word (section 8).
- Auteurs mode: the letters of a player who has left are drawn in plain ink, like
  letters with no finder. No departed grey and no `--nock-departed` token
  (section 7). The sheet (version 4.5) draws them in ink too.
- Catalogue cards show a generic grid drawing built from width and height only,
  on wide windows, and no drawing with one card per row; no API change, spec
  004's `GridSummary` stays as it is (section 10; decided by the human on
  2026-10-17, sheet 4.6).
- Fonts come in as npm dependencies: `@fontsource/source-sans-3` and
  `@fontsource/ibm-plex-sans-condensed`, imported per weight and style used (no
  other), self-hosted by the build, never from Google (section 4).
- A player's corner is given by the order of arrival on the cell (section 6).
- An « Accessibilité » mode in the Menu, off by default, per browser: while on,
  each corner triangle becomes that player's own icon in their colour, same
  corners, same order, at most 4, and replaces the player dot elsewhere (section
  6, icons drawn in sheet 4.3). This settles
  the former deferred item "corner triangles carry colour only": with the mode
  off, triangles stay colour-only by the human's choice, and spec 035 AC-6 is
  refined so that its non-colour sign is the mode plus the Joueurs list.
- Grid lines and input borders keep the sheet's rule grey #9AA3B2 ("use the one
  from the style"); its contrast is tracked below as low importance.

### Decided by the lead on 2026-10-22, on the human's instruction

(Note from the spec writer, 2026-10-22: this list is new. The human's instruction
of 2026-10-22: "the game is now to be implemented on the full design system
provided; competitive modes wait". On it, the lead settled the deferred high item
and accepted the spec writer's pick of every "Still open" item, for the human to
override at the approval of spec 042. Each item below left "Deferred, high
importance" or "Still open"; the sections it touches carry a note of the same
day.)

- The revealed notch keeps the design's size, 0.22 s by 0.11 s (min 7 by 4 px),
  which wins over spec 024 AC-9's former minimum (at least 6 px and a quarter of
  the side, wide and high; at a 29 px cell, 7 by 4 px against 8 by 8 px). The
  notch, the bold letter on locked grey and spec 024's hidden label remain the
  non-colour signs of a revealed letter. Spec 042 refines spec 024 AC-9 (section
  6). Formerly "Deferred, high importance", item 1, skipped by the human on
  2026-10-16.
- The revealed notch is drawn in ink during a flash (orange-red falls to 2.1:1 to
  2.8:1 on the Orange, Cramoisi and Magenta flashes, below spec 024's 3:1), as
  sheet 4.2's `.flash.rev::after` (section 6). Formerly "Still open", item 2.
- A phone held sideways and the 900 px rule: column when the window is landscape
  and either at least 900 px wide and more than 500 px high, or at most 500 px
  high with the in-app keyboard hidden; otherwise sheet (section 8). Formerly
  item 5.
- Auteurs mode is remembered per browser, as the tint switch (section 7).
  Formerly item 6.
- « Compte » in the room Menu: after « Réglages de l'hôte », before the separator
  (section 8). Formerly item 7.
- A shown reaction on a two-clue cell is centred on its own clue's half, as spec
  022 does today (section 8). Formerly item 8.
- The new-events dot on the computer top bar sits at the unread badge's place
  (top 2 px, left 24 px) (section 8). Formerly item 9.
- `room-heading` inside the room is visually hidden (section 8). Formerly item
  10.
- The « ← » pictogram for departures (section 5). Formerly item 11.

### Proposed by spec 043, pending the human's approval

(Note from the spec writer, 2026-10-22: this list is new. Each item is the pick of
an open question of spec 043, the room layout; the human confirms or changes it
when approving that spec.)

- Joueurs rows on two lines, the state and the current clue under the name, and
  the host's « Couper » beside « Retirer » (section 8, "Salon"; spec 043 Open
  questions 2 and 3).
- A disabled icon button on the navy clue bar draws its icon in `--nock-rule`
  (5.22:1 on navy), a new job for the rule grey (section 2; spec 043 Open question
  10).
- The timer in the top bar is text, not a button (spec 043 Open question 7).
- « Aide » stays in help mode `none`, holding the pencil confirm or a muted line
  (section 12's "to confirm"; spec 043 Open question 4).
- Until step 4, « Crayon » takes the phone top bar's fourth slot, where
  « Clavier » goes (spec 043 Open question 5). (Note from the spec writer,
  2026-10-22: spec 044 is step 4; see the list below.)
- The computer top bar shows no grid name until the client knows the grid's number
  and force (spec 043 Open question 6).
- The clue bar in the column layout is never narrower than the smaller of 320 px
  and the play area (spec 043 Decision 12).

### Proposed by spec 044, pending the human's approval

(Note from the spec writer, 2026-10-22: this list is new. Each item is the pick of
an open question of spec 044, the keyboard.)

- Keys 28 px high instead of 44 px on a window at most 500 px high (section 8; spec
  044 Open question 1): with 44 px keys a phone held sideways keeps about 58 px of
  grid at 568 by 320, below spec 013 AC-6's 100 px.
- « Clavier » on touch screens only; on a narrow window without touch the phone top
  bar's fourth slot holds « Crayon » (section 8; spec 044 Open question 2).
- A phone held sideways goes to the column layout when the grid is solved, since
  the keyboard goes away (section 8, "Which layout"; spec 044 Open question 3).
- « Clavier » is disabled once the grid is solved (spec 044 Open question 4).
- The ⇄ key is named « Changer de sens » (spec 044 Open question 5).

(Note from the lead, 2026-10-22: decided by the lead, spec 043 being a draft: in
the column layout on a window at most 500 px high the top bar is the phone top bar
(54 px, icons over labels, the phone's slots and order), since the computer top bar
is wider than those windows (568 to 740 px). Spec 044 Decision 8; spec 043 is
refined. Section 8's "Computer and landscape tablet" top bar applies only to a
column layout more than 500 px high.)

### Decided by the human on 2026-10-22, from the screens sheet

(Note from the lead, 2026-10-22: this list is new. The human accepted every
recommended answer of `docs/design/screens-sheet.html` (version 1.0, its part 12);
each item names the section that now carries it.)

- P1. Entry and plain pages on a computer: the phone's column, centred, at most
  420 px, 48 px under the 56 px top bar, on the page grey (section 8).
- P2. The opening room: top bar in place, one muted line in the grid area, no clue
  bar or keyboard, no spinner (section 8 « States »).
- P3. An expired room: the not-found card with one muted line on expiry (a new
  `fr.json` key) and « Voir les grilles » primary (section 8).
- P4. Catalogue and « Mes salons » states as one line in place of the content
  (section 8 « States », section 10).
- P5. The host's « Couper » / « Rétablir » beside « Retirer » in the Joueurs rows;
  the chat notes as a muted line under the message box; a muted player's input
  disabled (section 8). The row's lines: spec 043's, see the next list.
- P6. After a vote: a muted waiting line instead of « Oui » / « Non »; the result
  as a note and a stream line (sections 8, 9).
- P7. A spent reveal item stays, disabled, with « Plus de lettre » / « Plus de mot »
  (section 8). Help mode `none`: spec 043's, see the next list.
- P8. The clue bar with nothing selected shows « Touchez une case ou une
  définition. »; its buttons: spec 043's, see the next list.
- P9. « Rien à annuler. » is a 3-second note (section 8).
- P10. The recap's loading and unavailable states inside its sheet or dialog
  (section 8 « States »).
- P11. The shared recap page (section 8 « Plain pages »).
- P12. The account page and deletion, with no red button (section 8 « Plain
  pages »).
- P13. Outside a room, the account sheet's intro is `account.signed_out_intro`
  (section 8).
- P14. The operator page (section 8 « Plain pages »).
- P15. A slider component (section 11).
- P16. « Lien copié » as a line under the recap's URL box (section 9).
- D1. No red « danger » button (section 11).
- D2. Grid credits stay off the screens until a spec sends them (section 10).
- D3. The screens sheet loads the app's own font files, else a local copy, else
  the fallback stack; never Google.

### Where the screens sheet met spec 043

(Note from the lead, 2026-10-22: the screens sheet was drawn from `main`, before
spec 043 was drafted, and on three points the answer the human accepted from the
sheet differed from spec 043's pick. The human approved spec 043 on 2026-10-22
("Approve specs 042 and 043."), so spec 043's version is decided on all three, by
that approval; the sheet's answers P5 (the row's lines), P7 (help mode `none`) and
P8 (the clue bar's buttons) are set aside on these points. This list read "both
wait for the human, who settles them when approving spec 043".)

1. The Joueurs row: line 1 the dot, the name, « (vous) », the « hôte » tag and, for
   the host, « Couper » / « Rétablir » and « Retirer » on the right; line 2, under
   the name, the state and the player's current clue (spec 043 Decision 5), so the
   current clue never ends in an ellipsis at 340 px. Not P5's buttons on a second
   line.
2. Help mode `none`: « Aide » stays in the top bar; its menu holds the pencil
   confirm when it applies, otherwise the muted line « L'aide est désactivée dans ce
   salon. » (spec 043 Decision 7), since the pencil confirm lives in the Aide menu on
   a computer. Not P7's hidden button.
3. Réagir and Je bloque while nothing is selected: drawn disabled, their icon in
   `--nock-rule` (5.22:1 on navy; spec 043 Open question 10), so the clue bar keeps
   its shape. Not P8's hidden buttons.

### Deferred, high importance

None left. (Note from the spec writer, 2026-10-22: its one item, the size of the
revealed notch, was decided by the lead on 2026-10-22 on the human's instruction;
see the list above. The other item first deferred here, "corner triangles carry
colour only", was settled on 2026-10-16 by the Accessibilité mode.)

### Deferred, low importance

- Rule grey #9AA3B2 is 2.54:1 on white. WCAG 1.4.11 asks 3:1 for the boundary of an
  input and for the parts of a control, such as the switch track when off. Kept by
  the human's decision above; a darker value (#8A93A3, 3.10:1) remains possible
  later.

### Still open

None left. (Note from the spec writer, 2026-10-22: items 2 and 5 to 11 moved to
"Decided by the lead on 2026-10-22, on the human's instruction" above, each with
the spec writer's pick; items 1, 3 and 4 had been settled by the human on
2026-10-16 and 2026-10-17. The numbers are kept there as "Formerly item N".)

### The sheet, version 4.2

Settled in 4.2 (no longer open): the leftovers of earlier versions are removed
(`fitName`, `LABEL_AT`, `.tri b`, `.band`, `.pentag`, the triangle-edge contrast
row); ⚑ ‹ › are drawn icons; the legend sits under the grid in the flow; 👁 is
replaced by ▲; the wording says orange-red and ink; the hidden timer's slot holds
« Chrono »; the new-events dot is drawn; a flagged second clue has its own flag;
Je bloque has a drawn pressed state; the full-but-wrong band sits between the clue
bar and the keyboard; the arrow collisions have rules; the « a rempli » line is
gone; empty cells and the active clue are drawn.

Still in 4.2, settled here unless the human says otherwise:

- `--clue-ink` (#1B2230) is kept as `--nock-clue-ink`.
- The menu, popover, sheet, dialog, vote and note shadows still use
  `rgba(0, 0, 0, ...)`, against "no pure black"; the demo menu has a 0.35 shadow
  and a border, the phone popover 0.45 and no border: ink-based shadows, the
  popover's values (the reaction pill and picker already use ink).
- Recap sheet and room sheets: radius 16 px, no handle; Salon sheet 14 px with a
  handle: kept as drawn.
- The caption "smaller type in two-clue cells" disagrees with the CSS, which has
  one clue size: one size.
- The palette table's jobs are not updated (selected blue "my selected cell only",
  rule grey without empty cells): section 2 of this file is the reference.
- The sheet's "Still open" recap block still lists the tint, the corner, the
  column and the long press, which the human decided: this file is the reference.
- Two captions still say "red notch" (section 6b's lead, the phone's note): the
  notch is orange-red.
- Clue cells have `overflow: visible`, so a long clue could spill over its
  neighbours; spec 006 AC-1 still requires no cut at full zoom. At about 29 px
  (tablet with the keyboard) two-clue cells do not hold their text: players zoom
  or hide the keyboard.
- The players-and-invite drawing shows only the state word, while the Salon's
  Joueurs tab shows « state · current clue »: both kept (the current clue is the
  list's job as the sign of where each player is).
- Sample texts differ from spec strings (« a rejoint la partie »; « 31 / 48 mots »
  on a FX-01-sized grid): rule 6 of section 1.
- The legend's 38 px reservation is more than its drawn height (about 25 px plus
  the 8 px gap): 38 px kept, as drawn.
