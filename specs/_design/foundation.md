# Visual foundation

Not a spec: the quality gate ignores files under `specs/_design/`. With
`cells.md`, `room.md`, `overlays.md` and `pages.md` it is the look of the web
client, which every domain spec cites and never repeats.

Values are CSS values. `s` is the side of a grid cell in CSS px, its right and
bottom grid line included (the cell is `box-sizing: border-box`). "max(7px, 0.22 s)"
means the larger of 7 px and 22 % of `s`. `rem` is the root font size (16 px by
default).

## Authority

The design files and the two sheets in `docs/design/` are the visual reference of
the web client: `cell-sheet.html` draws the grid cells, `screens-sheet.html` every
screen and state at phone width (360 px) and computer width (1280 px). Where a
sheet and these files differ, the files win, and the difference is listed below or
fixed in the sheet.

Rules:

1. Every domain spec that puts something on screen cites, under « Look », the
   design file and section it applies, and has acceptance criteria that check the
   values that matter: computed colours, sizes and positions at a known cell size or
   window size, paint order, and which elements are present or absent.
2. No spec and no code introduces a colour, a font, a font size, a radius, a
   shadow or an icon that is not listed in these files. Colours are used only
   through the tokens of « Colour tokens » and « Player colours ».
3. A change of look starts here. Any change that alters what a screen looks like
   (a decision of the human, a new or changed spec, a review finding) updates the
   design file of that part of the screen and redraws what it changes in the
   sheets, in the same commit, before any test or code changes. The files state
   what is true now, with no dated notes; the commit message holds the reason. The
   screens sheet is generated: edit `docs/design/screens_sheet/` and run
   `uv run python docs/design/screens_sheet/build.py`; its HTML is never edited by
   hand. A screen whose look changed without its drawing is a review finding
   (« How conformance is checked »).
4. Where a domain spec contradicts these files, the files describe the target and
   the spec is changed to match. Until it is, the spec wins for its own tests, and
   the code keeps passing them.
5. Grid letters are the 26 capitals `A` to `Z`, never accented, in examples too.
6. Strings are the app's own: `fr.json` and the key tables of the specs. Where a
   sheet's sample text differs from a string (« a rejoint la partie » against
   « a rejoint le salon »; « 31 / 48 mots » on a FX-01-sized grid), the string
   wins.
7. The sheets draw the decided design. Something not yet decided carries a dashed
   label in the screens sheet and an item in `Backlog.md` until the human decides
   it.

Where the cell sheet differs, these files win: its `--clue-ink` is
`--nock-clue-ink`; its menu, popover, sheet, dialog, vote and note shadows in
`rgba(0, 0, 0, ...)` are the ink-based shadow tokens below (the popover's values,
no border); its palette table's jobs, its « Still open » block, and its captions
« smaller type in two-clue cells » (there is one clue size) and « red notch » (the
notch is orange-red) are out of date; its players-and-invite drawing shows the
state word only, where the Joueurs rows of `room.md` are the reference.

## Colour tokens

Each colour is a CSS custom property declared once, in the `:root` block of
`web/src/app.css` (the token block). Code uses `var(--nock-...)`, never the value.
Ratios are WCAG 2.x contrast against white (#FFFFFF).

| Token | Value | Its one job | Never for | On white |
| --- | --- | --- | --- | --- |
| `--nock-navy` | #1B2F55 | The app's colour: top bar, top-bar icons and labels, clue bar, primary buttons, my selection border, focus ring, links, headings, segmented control and switch when on, slider fill and knob (« Components ») | Player marks | 13.26:1 |
| `--nock-ink` | #14181F | All text and grid letters, direction arrows, the catch-up ring, 3-second notes (background), the revealed notch during a flash, scrim and shadow base | Backgrounds of cells | 17.79:1 |
| `--nock-muted` | #5E6573 | Secondary text: captions, event lines in the stream, disabled labels, menu details, inactive tabs, the room code above an entry card | Grid letters | 5.86:1 |
| `--nock-pencil` | #555B67 | Pencil letters (italic), letter keys in pencil mode | Any other text | 6.82:1 |
| `--nock-white` | #FFFFFF | Room page, letter cells, menus, sheets, dialogs, cards; text and icons on navy, ink and red | - | 1:1 |
| `--nock-page` | #F6F7F9 | Background of the pages that are not the room (nickname, entry statuses, not found) behind their white card | Room page, cells | 1.07:1 |
| `--nock-clue-bg` | #EEF2F8 | Clue cells, disabled buttons, the "not yet" status band, the connection band, the « hôte » tag | Selection | 1.12:1 |
| `--nock-clue-ink` | #1B2230 | Clue text in clue cells, the separator between two clues | Any other text | 15.97:1 |
| `--nock-word` | #E6EDF9 | My selected word, hovered menu item, pressed top-bar button, quiet buttons, pressed filter chips, progress bar and slider track, hovered reaction | Player tints | 1.18:1 |
| `--nock-selected` | #CFDDF3 | My selected cell, and the half of the clue cell that holds my selected word's clue | Anything else | 1.37:1 |
| `--nock-locked` | #E3E7EE | Locked letter cells (with bold letters) | Disabled states | 1.24:1 |
| `--nock-rule` | #9AA3B2 | Grid lines, empty cells, input borders, border of the catalogue's grid drawing, switch track when off, the icon of a disabled button on the navy clue bar | Text | 2.54:1 (below 3:1, accepted) |
| `--nock-line` | #DDE2EA | Dividers in menus, panels and cards; card and list-row borders; filter chip borders; disabled button border; reaction pill and picker borders; inner lines of the catalogue's generic grid drawing | Grid lines of the playing grid | 1.30:1 |
| `--nock-red` | #B42318 | "Look here": wrong-letter strike, flag, unread badge, new-events dot, the connection band's dot, error text and the border of a field in error | Decoration | 6.57:1 |
| `--nock-reveal` | #C2410C | "Revealed", and nothing else: the revealed notch, the reveal line in the stream | Anything else | 5.18:1 |
| `--nock-green` | #1E7B45 | "Done": finished-grid band text, passed-check line in the stream, "Terminée" pill text, confirmation lines (« Lien copié », « Lien envoyé … ») | Player marks | 5.28:1 |
| `--nock-green-bg` | #E6F2EA | Background of the finished-grid band and of the "Terminée" pill | Anything else | 1.15:1 |
| `--nock-key` | #E9ECF1 | In-app keyboard keys | - | 1.18:1 |
| `--nock-keyboard-bg` | #D9DEE6 | In-app keyboard background | - | 1.35:1 |
| `--nock-handle` | #C5CCD8 | Grab handle of a bottom sheet | - | 1.62:1 |
| `--nock-thumb` | #C9D2E0 | Clue cells of the catalogue's generic grid drawing, force notches above the grid's force | - | 1.52:1 |

Translucent tokens, all built on ink or white:

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
  "revealed" and nothing else. Green means "done". A player colour (« Player
  colours ») only ever means a player: triangles, word tints, flashes, dots,
  Auteurs ink; never a button, a state or a decoration.
- Text and icons reach 4.5:1 against their background, disabled buttons included.
  Marks, borders that carry meaning and the focus ring reach 3:1, except the rule
  grey of grid lines, input borders and the switch track when off (2.54:1,
  accepted).
- No pure black (#000000) and no neutral grey: the neutrals lean toward the navy.
- No dark mode for now. Every colour is a named token, so one can be added later
  by redefining the tokens.
- Two colours may be mixed only with `color-mix(in srgb, ...)` over tokens, or by
  `opacity`, at the percentages these files give: 16 % (word tint), 38 % (flash),
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
| Rule grey on navy (disabled icon in the clue bar) | 5.22:1 | 4.5 |
| Muted on word blue (menu detail on hover) | 4.98:1 | 4.5 |
| Muted on page grey (room code line) | 5.47:1 | 4.5 |
| Navy on clue blue-grey (« hôte » tag) | 11.8:1 | 4.5 |
| Green on green background | 4.59:1 | 4.5 |
| Navy on word blue (pressed top-bar button) | 11.27:1 | 4.5 |
| Revealed notch on white / selected / locked / word | 5.18 / 3.77 / 4.17 / 4.40:1 | 3 |
| Navy selection border on selected | 9.65:1 | 3 |

## Player colours

Imposed by the human, in join order: the room's first player gets index 0. They
are `--player-colour-0` to `--player-colour-7` in `web/src/app.css`. Each has an
Auteurs ink, token `--player-ink-0` to `--player-ink-7`. The triangle colour is
used for corner triangles, word tints, flashes, player dots and roster swatches;
the ink only for letters in Auteurs mode and for names in the Auteurs legend.

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

The rules they meet (found by a search, not by eye):

- each triangle reaches 3:1 on my selected cell (#CFDDF3), the darkest background a
  triangle can have outside a flash, with no outline;
- each ink reaches 4.5:1 on my selected cell; the ink is the triangle colour
  darkened toward black only as far as needed;
- no blue, so no player looks like my own selection;
- the worst pairwise colour difference (CIEDE2000), over normal vision and the
  protan, deutan and tritan simulations of Machado 2009 at severity 1, inks
  included with a weight, is at least 10.9 among players 0 to 3 and at least 7.1
  among all 8. The weakest pairs are Violet/Magenta (protan) and Orange/Vert
  (deutan).

The order puts the most distinct colours first, because most rooms have two to
four players. With five players or more, the player list in the Salon is the
reference.

## Typography

Families:

| Token | Stack | Used for |
| --- | --- | --- |
| `--nock-font-ui` | "Source Sans 3", "Segoe UI", system-ui, sans-serif | Interface text and grid letters |
| `--nock-font-clue` | "IBM Plex Sans Condensed", "Arial Narrow", "Roboto Condensed", sans-serif | Clue text in clue cells |

Faces served: Source Sans 3 at weights 400, 500, 600, 700 upright and 500, 700
italic; IBM Plex Sans Condensed at 500 and 600 upright. Nock serves the font files
itself from its own origin (privacy: no third-party URL); never from Google Fonts or
another host. The files come from the npm packages `@fontsource/source-sans-3` and
`@fontsource/ibm-plex-sans-condensed`, imported per weight and style used and no
other, and built into `web/dist`. The cell sheet's third family, Source Serif 4,
styles the sheet's own headings only and is not part of the app.

Grid:

- Letters: `--nock-font-ui`, size 0.56 s, line height 1, weight 500; locked
  letters weight 700. The capital is centred on its own cap height and baseline,
  not on the line box: `text-box: trim-both cap alphabetic` on the letter. An
  engine without `text-box` (Firefox today) centres the line box; the letter then
  sits about 0.5 px off, which is accepted.
- Clue text: `--nock-font-clue`, size max(6px, 0.145 s), weight 600, line height
  1.12, letter spacing 0.01em, uppercase (`text-transform`), centred. It wraps at
  word breaks (`overflow-wrap: break-word`, `hyphens: manual`) and is never cut and
  never ends with an ellipsis at full zoom. One size for one-clue and two-clue
  cells.

Interface sizes (all `--nock-font-ui`; `tabular` means
`font-variant-numeric: tabular-nums`):

| Element | Weight | Size / line height | Other |
| --- | --- | --- | --- |
| Page text | 400 | 16 px / 1.5 | ink |
| Top-bar label, phone | 500 | 0.68rem / 1 | navy, under the icon |
| Top-bar label, computer | 500 | 0.92rem / 1 | navy, beside the icon |
| Timer | 600 | 1.15rem / 1 | navy, tabular |
| Brand "Nock" | 700 | 1.3rem / 1 | navy, letter spacing 0.01em |
| Clue bar text | 500 | 0.95rem (15.2 px) / 1.2 | white; at least 14 px |
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
| Stream event | 400 | 0.82rem (13.1 px) | muted, or orange-red / green (`room.md`, « Salon ») |
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

## Icons

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

When an icon is missing: Font Awesome Free, in its outline "regular" style first.
Only the icons used are bundled, served by Nock itself; never the Font Awesome CDN
or kit. Each use carries a comment with the CC BY 4.0 attribution, and the README
has one line crediting Font Awesome Free. When Font Awesome Free has no outline
version of an icon, Nock draws one in the style above rather than mix filled and
outline icons. Font Awesome is a dependency the human approved; the spec that first
needs it names the exact package.

Nock's own marks, never Font Awesome:

- The grid arrows (`cells.md`, « Direction arrows »).
- The Nock mark (the notch at the back of an arrow): `<svg viewBox="0 0 10 14">`
  with `<polygon points="0,0 10,0 10,14 5,10 0,14"/>`, filled. Brand: 12 by 18 px,
  navy. Force notch in the catalogue: 8 by 11 px.

Text glyphs used as pictograms, in the current font: ✓ (done, check line), →
(joined line), ← (left line), ▲ (reveal line, in orange-red), ✎ (detail of the
pencil confirm item), ▾ (Aide menu on a computer). The flag and the clue bar's ‹ ›
are drawn icons, never text glyphs (the fonts have no ⚑). No emoji in the
interface; reactions and chat text are user content.

## Components

| Component | Look |
| --- | --- |
| Button, all | radius 6 px, padding 10 px 16 px, weight 600, 0.95rem, line height 1, 1 px border |
| Primary | navy background, white text, transparent border |
| Secondary | white background, navy text, navy border |
| Quiet | word-blue background, navy text, transparent border |
| Small button | any variant, padding 6 px 10 px, 0.8rem |
| Disabled (any) | clue blue-grey background, muted text, line-grey border, `cursor: not-allowed`; text still 4.5:1 |
| Focus ring | `outline: 2px solid var(--nock-navy)`, `outline-offset: 2px`, on `:focus-visible`. On a navy surface (the clue bar): white, offset −4 px. Inside a container that scrolls or clips (a popover's items and the popover itself, the Salon's tabs, the stream list): navy, drawn inside at offset −2 px, so the container never cuts it. On a segmented control's option: offset −4 px, navy on an option not chosen, white on the chosen (navy) one. |
| Menu / popover | white, radius 8 px, padding 6 px 0, min width 220 px, shadow `0 12px 30px -10px var(--nock-shadow)`, no border |
| Menu item | full-width button, padding 10 px 16 px, 500 1rem/1.2, navy, left-aligned; detail on the right (gap 12 px), muted, not italic, tabular; hover: word-blue background |
| Menu heading | margin 6 px 16 px 2 px, 600 0.7rem, uppercase, letter spacing 0.08em, muted |
| Menu separator | 1 px line-grey top border, margin 4 px 0 |
| Top-bar button | navy icon and label, transparent background; pressed: word blue |
| Brand link | the Nock mark (« Icons ») and « Nock » (« Typography »), gap 8 px, no underline: at rest it looks as plain text. Padding 8 px 10 px inside a margin of −8 px −10 px, so its box is larger than its content and nothing moves; radius 6 px. Hover: word-blue background. Focus: the ring of this table. The same on the catalogue, where it is the current page |
| Badge | red background, white 700 0.62rem/1 text, padding 2 px 4 px, radius 8 px |
| New-events dot | 8 px red circle |
| 3-second note | `room.md`, « 3-second notes » |
| Bottom sheet | white, radius 14 px top with grab handle (Salon) or 16 px top without (other room sheets, recap): `room.md`, « Salon » and « Room sheets: host settings and account »; `overlays.md`, « Recap » |
| Scrim | `--nock-scrim` (menus, sheets) or `--nock-scrim-dialog` (recap) |
| Card | white, 1 px line-grey border, radius 10 px, padding 18 px 16 px, gap 12 px |
| List row | white, 1 px line-grey border, radius 8 px, padding 12 px 14 px, gap 12 px, items centred; text column gap 3 px (title 700, lines 0.85rem muted); its button on the right |
| Field | label above its input, gap 6 px, label 600 0.85rem/1.2 ink |
| Text input | 1 px rule-grey border, radius 6 px, padding 10 px 12 px, 400 1rem/1.2, ink on white; in error: red border. Message box: radius 18 px, padding 7 px 12 px. URL box: padding 8 px 10 px, 0.85rem, one line with ellipsis |
| Number input | a text input 64 px wide, text centred |
| Error line | red, 500 0.85rem/1.3, under its field |
| Confirmation line | green, 500 0.85rem/1.3 |
| Switch | track 42 by 24 px, radius 12 px, rule grey when off, navy when on; knob 18 px white circle, 3 px from the top, left 3 px (off) or 21 px (on). In a switch row: label left (500 0.95rem/1.2), switch right, gap 10 px |
| Segmented control | inline row with a 1 px navy border, radius 6 px, clipped; options padding 8 px 10 px, 600 0.85rem/1, navy, 1 px navy dividers; the chosen one navy background, white text. When the row is wider than its place (a large root font size, a very narrow window), its options wrap onto a second line inside the same border rather than leave the sheet |
| Tag (« hôte ») | clue blue-grey background, navy 600 0.72rem/1.3, radius 10 px, padding 2 px 8 px |
| Pill button (« Envoyer ») | word blue, navy, 600 0.85rem, radius 14 px, padding 6 px 12 px, no border |
| Text link | navy, weight 600 |
| Player dot | 10 px circle, player colour, ring `0 0 0 1px var(--nock-dot-ring)` |
| Reaction picker, shown reaction | `room.md`, « Reactions » |
| Slider | a native range input, 18 px high and transparent, over three drawn parts, so the look is the same in the three engines: the track, 6 px high, radius 3 px, `--nock-word`; the fill, the part before the knob, `--nock-navy`; the knob, an 18 px navy circle. The input stays the control, with its role, name and keys; the focus ring of this table is on the knob. Full width of its field |
| Destructive action | no variant of its own: a primary or secondary button after a confirmation step in place, never red (red means "look here", « Colour tokens ») |
| State line | `pages.md`, « States: opening, loading, empty, error » |

## Focus

The focus ring is the one of « Components ». The room's sheets, the Salon column,
each menu and the reaction picker are labelled regions. Opening one moves the focus
into it; Échap closes it and puts the focus back on the button that opened it.

## How conformance is checked

1. Tests pin the foundation: the tokens, the player colours and inks, the fonts,
   the focus ring, the button, menu, badge and note primitives, and the colour
   scan below.
2. Each domain spec that puts something on screen has criteria that read what the
   eye sees: computed colours as `rgb()`, sizes and positions in px at a known
   window or cell size, paint order with `document.elementFromPoint` at chosen
   points, bounding boxes for positions and clearances, and data attributes for
   states.
3. The tokens in `web/src/app.css` are the only source of colours. A test scans
   the built CSS in `web/dist` and the client sources for colour literals outside
   the token block.
4. Screenshot comparison against reference images rendered from
   `docs/design/cell-sheet.html` is not done: it would be new tooling, a decision
   for the human.
5. The reviewer checks each change against these files:
   - every colour comes from a token, and the token is used for its job;
   - no new font, size, radius, shadow or icon outside these files;
   - the cell geometry, the arrow collision rules and the drawing order of
     `cells.md`;
   - the contrast of « Colour tokens » holds in every state the spec covers,
     flashes included;
   - the layout rules of `room.md`, and that nothing extra is permanently on
     screen;
   - the focus ring and Échap behaviour of « Components » and « Focus »;
   - the domain spec cites the sections it applies;
   - every change of look is drawn in the sheets in the same change (« Authority »,
     rule 3), and the screens sheet's HTML is what its generator builds.
6. The sheets stay in `docs/design/` as the visual reference, updated with these
   files in the same change: `cell-sheet.html` by hand, `screens-sheet.html` from
   `docs/design/screens_sheet/` (`uv run python docs/design/screens_sheet/build.py`).
