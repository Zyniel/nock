---
id: "041"
title: Visual foundation
status: approved
---

# 041 - Visual foundation

Epic E10 Quality bar · Release: MVP · No backlog story: this is build step 1 of
`specs/_design.md` (section 14). It applies `_design.md` sections 2 (colour
tokens), 3 (player colours), 4 (typography: families and faces), 5 (icons), 6 (only the shapes of the
player icons) and 11
(components: buttons, focus ring, menus, badge, 3-second note). The FX-01
reference grid is in `specs/_reference.md`; the stack in `specs/_architecture.md`.

## Goal

The human validated a visual design for the whole client (`_design.md`,
`docs/design/cell-sheet.html`). This spec puts its foundation in place so that
every later screen is built from it: the colour tokens as the only source of
colours, the eight imposed player colours, the fonts served by Nock, the icons,
and the styling primitives (buttons, focus ring, menus, badge, note). Today's
screens take the token colours, with no change of layout, of protocol or of
behaviour.

## Public interface

No new Python name, no new protocol message, no new HTTP route, no new `fr.json`
key. Client only (`web/`).

### Colour tokens (`web/src/app.css`)

One `:root` block in `web/src/app.css` (the token block) declares these custom
properties, with these values. They replace every colour written anywhere else in
the client. Jobs and contrast are in `_design.md` section 2.

| Token | Value |
| --- | --- |
| `--nock-navy` | #1B2F55 |
| `--nock-ink` | #14181F |
| `--nock-muted` | #5E6573 |
| `--nock-pencil` | #555B67 |
| `--nock-white` | #FFFFFF |
| `--nock-page` | #F6F7F9 |
| `--nock-clue-bg` | #EEF2F8 |
| `--nock-clue-ink` | #1B2230 |
| `--nock-word` | #E6EDF9 |
| `--nock-selected` | #CFDDF3 |
| `--nock-locked` | #E3E7EE |
| `--nock-rule` | #9AA3B2 |
| `--nock-line` | #DDE2EA |
| `--nock-red` | #B42318 |
| `--nock-reveal` | #C2410C |
| `--nock-green` | #1E7B45 |
| `--nock-green-bg` | #E6F2EA |
| `--nock-key` | #E9ECF1 |
| `--nock-keyboard-bg` | #D9DEE6 |
| `--nock-handle` | #C5CCD8 |
| `--nock-thumb` | #C9D2E0 |

(Note from the spec writer, 2026-10-16: second round. `--nock-page` is added for
the pages that are not the room (sheet 4.2, `_design.md` section 2).
`--nock-rule` keeps #9AA3B2, decided by the human on 2026-10-16. `--nock-departed`
is removed: in Auteurs mode a departed player's letters are plain ink, decided by
the human on 2026-10-16.)

Translucent tokens:

| Token | Value |
| --- | --- |
| `--nock-scrim` | rgb(20 24 31 / 35%) |
| `--nock-scrim-dialog` | rgb(20 24 31 / 38%) |
| `--nock-dot-ring` | rgb(20 24 31 / 55%) |
| `--nock-key-shadow` | rgb(20 24 31 / 25%) |
| `--nock-shadow-soft` | rgb(20 24 31 / 35%) |
| `--nock-shadow` | rgb(20 24 31 / 45%) |
| `--nock-shadow-strong` | rgb(20 24 31 / 50%) |
| `--nock-legend-bg` | rgb(255 255 255 / 96%) |
| `--nock-pen-fill` | rgb(255 255 255 / 35%) |

Player colours and Auteurs inks (`_design.md` section 3). The names
`--player-colour-0` to `--player-colour-7` stay (spec 012); their values change.

| N | `--player-colour-N` | `--player-ink-N` |
| --- | --- | --- |
| 0 | #604800 | #604800 |
| 1 | #608838 | #4B6A2C |
| 2 | #008878 | #006D60 |
| 3 | #6838E0 | #6838E0 |
| 4 | #B83850 | #AD354B |
| 5 | #D000A0 | #B3008A |
| 6 | #B06000 | #904F00 |
| 7 | #784030 | #784030 |

Font tokens:

| Token | Value |
| --- | --- |
| `--nock-font-ui` | "Source Sans 3", "Segoe UI", system-ui, sans-serif |
| `--nock-font-clue` | "IBM Plex Sans Condensed", "Arial Narrow", "Roboto Condensed", sans-serif |

`--focus-outline` (used today by the in-app keyboard) stays, with the value
`2px solid var(--nock-navy)`. `--author-departed-dark` and
`--author-departed-light` (spec 019) go; the hatch uses `--nock-ink` and
`--nock-white`.

### Page base

`body`: `font-family: var(--nock-font-ui)`, `color: var(--nock-ink)`,
`background: var(--nock-white)`. Its margin, font size and line height do not
change in this spec.

Form controls: one global rule in `web/src/app.css`, next to the `body` rule,
gives `button`, `input`, `select` and `textarea` `font: inherit`, so that they
take their parent's font family, size, weight, style and line height instead of
the OS control font. A component or a primitive (`nock-button`, `nock-menu-item`)
that sets its own font on a control still overrides it. (Note from the spec
writer, 2026-10-21, at the lead's request: added. Browsers draw form controls in the OS control font unless told
otherwise, and only four components set `font: inherit` today, so the controls of
the other screens were drawn in a font that differs between Windows and Ubuntu.
Checked by AC-21.)

### Fonts

The two families of `_design.md` section 4 are declared with `@font-face` under
the exact family names `Source Sans 3` (weights 400, 500, 600, 700 normal; 500
and 700 italic) and `IBM Plex Sans Condensed` (500 and 600 normal), as WOFF2 files
built into `web/dist` and served by Nock from its own origin, with
`font-display: swap`.

The files come from two npm packages, added to `web/package.json` (decided by the
human on 2026-10-16): `@fontsource/source-sans-3` and
`@fontsource/ibm-plex-sans-condensed`. `web/src/main.ts` imports exactly these
per-weight files and no other weight or style of either package:

- `@fontsource/source-sans-3/400.css`, `500.css`, `600.css`, `700.css`,
  `500-italic.css`, `700-italic.css`;
- `@fontsource/ibm-plex-sans-condensed/500.css`, `600.css`.

Vite builds the WOFF2 files into `web/dist/assets`, served by Nock from its own
origin; nothing is fetched from Google or another host. `README.md` credits both
families under the SIL Open Font License 1.1. (Note from the spec writer,
2026-10-16: added when the human decided the fonts; Open question 1 is closed.)

### Focus ring

- Every `:focus-visible` element: `outline: 2px solid var(--nock-navy)`,
  `outline-offset: 2px`. The per-element offsets already in the client (the
  `grid`'s `-3px`, the timer toggle's `-3px`) stay.
- Class `nock-on-navy`: a navy surface (`background: var(--nock-navy)`,
  `color: var(--nock-white)`). Inside it, a `:focus-visible` element has
  `outline-color: var(--nock-white)` and `outline-offset: -4px`. No element uses
  it yet (the clue bar of `_design.md` section 8 will).

### Styling primitives (global classes in `web/src/app.css`)

| Class | On | Look (`_design.md` section 11) |
| --- | --- | --- |
| `nock-button` | `button` | radius 6px, padding 10px 16px, 1px solid border, `font: 600 0.95rem/1 var(--nock-font-ui)`, `cursor: pointer` |
| `nock-button-primary` | with `nock-button` | navy background, white text, transparent border |
| `nock-button-secondary` | with `nock-button` | white background, navy text, navy border |
| `nock-button-quiet` | with `nock-button` | word-blue background, navy text, transparent border |
| `nock-button:disabled` | any variant | clue blue-grey background, muted text, line-grey border, `cursor: not-allowed` |
| `nock-menu` | container | white, radius 8px, padding 6px 0, min width 220px, `box-shadow: 0 12px 30px -10px var(--nock-shadow)`, no border |
| `nock-menu-item` | `button` in a menu | `display: flex`, `justify-content: space-between`, gap 12px, width 100%, padding 10px 16px, `font: 500 1rem/1.2 var(--nock-font-ui)`, navy, transparent background, no border, `text-align: left`; `:hover` word-blue background |
| `nock-menu-detail` | inside an item | muted, `font-style: normal`, `font-variant-numeric: tabular-nums` |
| `nock-menu-heading` | text in a menu | margin 6px 16px 2px, `font: 600 0.7rem/1.2 var(--nock-font-ui)`, uppercase, letter spacing 0.08em, muted |
| `nock-menu-separator` | `hr` in a menu | no border but a 1px solid line-grey top border, margin 4px 0 |
| `nock-badge` | `span` | red background, white text, `font: 700 0.62rem/1 var(--nock-font-ui)`, padding 2px 4px, radius 8px |
| `nock-note` | container | ink background, white text, `font: 500 0.85rem/1.2 var(--nock-font-ui)`, padding 8px 12px, radius 6px, `white-space: nowrap`, `box-shadow: 0 6px 18px -8px var(--nock-shadow-strong)`, `transition: opacity 0.25s`; with the attribute `data-off`: opacity 0 and `pointer-events: none`; under `prefers-reduced-motion: reduce`: no transition |

This spec only defines these classes. Later specs put them on controls.

### Icons (`web/src/lib/icons.ts`)

```ts
// web/src/lib/icons.ts
export type IconName =
  | 'undo' | 'aide' | 'salon' | 'clavier' | 'menu' | 'crayon' | 'swap' | 'effacer'
  | 'chrono' | 'flag' | 'chevron-left' | 'chevron-right' | 'smile'

export type IconShape =
  | { kind: 'path'; d: string }
  | { kind: 'rect'; x: number; y: number; width: number; height: number; rx: number }
  | { kind: 'circle'; cx: number; cy: number; r: number }
  | { kind: 'polygon'; points: string }

// The shapes of _design.md section 5, in its order, in a 24 by 24 box.
export const ICONS: Record<IconName, readonly IconShape[]>

// The player icons of the Accessibilité mode (_design.md section 6), by join
// index 0 to 7, in a 10 by 10 box. A rect here has rx 0.
export const PLAYER_ICONS: readonly (readonly IconShape[])[]

// The Nock mark, in a 10 by 14 box.
export const NOCK_MARK_POINTS: string // '0,0 10,0 10,14 5,10 0,14'
```

The shapes are exactly those of `_design.md` sections 5 and 6:

| Name | Shapes |
| --- | --- |
| `undo` | path `M9 14 4 9l5-5`; path `M4 9h10a6 6 0 0 1 0 12h-3` |
| `aide` | path `M9 18h6M10 22h4`; path `M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z` |
| `salon` | path `M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z` |
| `clavier` | rect x 2, y 6, width 20, height 12, rx 2; path `M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10` |
| `menu` | path `M4 7h16M4 12h16M4 17h16` |
| `crayon` | path `M4 20h4L19 9l-4-4L4 16v4z`; path `M13.5 6.5l4 4` |
| `swap` | path `M4 8h14l-3-3M20 16H6l3 3` |
| `effacer` | path `M9 5h11v14H9l-6-7 6-7z`; path `M13 9l4 6M17 9l-4 6` |
| `chrono` | circle cx 12, cy 13.5, r 7.5; path `M12 10v3.5l2.5 2M9.5 3h5M12 3v3` |
| `flag` | path `M6 21V4`; path `M6 4h12l-3 4.5 3 4.5H6z` |
| `chevron-left` | path `M15 5l-7 7 7 7` |
| `chevron-right` | path `M9 5l7 7-7 7` |
| `smile` | circle cx 12, cy 12, r 9; path `M8.5 14.5c1.8 2 5.2 2 7 0`; path `M9 9.5h.01M15 9.5h.01` |

| `PLAYER_ICONS` index | Shape |
| --- | --- |
| 0 (Rond) | circle cx 5, cy 5, r 4.4 |
| 1 (Carré) | rect x 0.9, y 0.9, width 8.2, height 8.2, rx 0 |
| 2 (Triangle) | polygon `5,0.4 9.7,9.3 0.3,9.3` |
| 3 (Losange) | polygon `5,0.1 9.9,5 5,9.9 0.1,5` |
| 4 (Étoile) | polygon `5,0.2 6.3,3.6 9.9,3.7 7.1,6 8.1,9.6 5,7.5 1.9,9.6 2.9,6 0.1,3.7 3.7,3.6` |
| 5 (Croix) | polygon `3.3,0.4 6.7,0.4 6.7,3.3 9.6,3.3 9.6,6.7 6.7,6.7 6.7,9.6 3.3,9.6 3.3,6.7 0.4,6.7 0.4,3.3 3.3,3.3` |
| 6 (Cœur) | path `M5 9.4L1.1 5.5A2.45 2.45 0 0 1 5 2.3A2.45 2.45 0 0 1 8.9 5.5Z` |
| 7 (Sablier) | polygon `0.6,0.6 9.4,0.6 5.6,5 9.4,9.4 0.6,9.4 4.4,5` |

(Note from the spec writer, 2026-10-16: second round. `chrono`, `flag`,
`chevron-left`, `chevron-right` and `smile` come from sheet 4.2, and
`PLAYER_ICONS` from sheet 4.3's Accessibilité mode, decided by the human on
2026-10-16. Only the shapes are pinned here; no screen draws them in this spec.)

How a component draws them (for example an `Icon.svelte` with the stroke
attributes of `_design.md` section 5) is the implementer's choice; no screen uses
them in this spec.

### Today's elements in the token colours

The colours written today in `web/src/app.css` and the components are replaced by
tokens, by job. Only colours (and the two changes marked below) change: no size,
border width, padding, position or element changes, except the flash overlay.

| Element today | Property | Token |
| --- | --- | --- |
| `body` text, `.letter` text, `remote-label`, `clue-reaction` text, keys, vote buttons | `color` | `--nock-ink` |
| Page, letter cells, menus and panels, `remote-label`, `clue-reaction`, vote banner, keys | `background` | `--nock-white` (keys: `--nock-key`) |
| Grid cell borders, key borders, vote button borders, clue bar top border | border colour | `--nock-rule` |
| `connection-banner` border | border colour | `--nock-line` (the band of `_design.md` section 8 has a line-grey bottom border) |
| Chat panel, reaction picker and `clue-reaction` borders | border colour | `--nock-line` |
| Selected letter cell (`data-selected="true"`) | background; outline | `--nock-selected`; `2px solid var(--nock-navy)`, `outline-offset: -2px` (was 3px, -3px) |
| Letter cell in my word (`data-in-word="true"`) | background | `--nock-word` |
| Locked letter cell | background | `--nock-locked` |
| Cell in another player's word (`data-tinted-by` not empty) | background | `color-mix(in srgb, var(--player-colour-N) 16%, var(--nock-white))` (was 28 %) |
| Pencil letter outside a flash | `color` | `--nock-pencil` |
| Wrong letter (`data-wrong="true"`) | `text-decoration-color` | `--nock-red` |
| Clue cell; its text; `clue-separator` | background; `color`; background | `--nock-clue-bg`; `--nock-clue-ink`; `--nock-clue-ink` |
| Clue of the selected word (`.clue.active`) | background | `--nock-selected` (decided by the human on 2026-10-16, `_design.md` section 6) |
| Empty cell (`data-type="empty"`) | background | `--nock-rule` (decided by the human on 2026-10-16, `_design.md` section 6) |
| `clue-arrow` | border colour | `--nock-ink` |
| `clue-flag`, `nickname-error` text | `color` | `--nock-red` |
| `chat-unread` | background; `color` | `--nock-red`; `--nock-white` |
| `roster-state`, `chat-note`, `clue-bar-author` text | `color` | `--nock-muted` |
| Disabled reveal buttons, disabled vote buttons | background; `color` | `--nock-clue-bg`; `--nock-muted` |
| `keyboard` | background | `--nock-keyboard-bg` |
| `clue-bar` | background | `--nock-clue-bg` (the navy bar comes with the room layout) |
| `vote-banner` | background; bottom border colour | `--nock-white`; `--nock-navy` |
| `connection-banner` | background; text | `--nock-clue-bg`; `--nock-ink` (the band's colours; its place and dot come with the room layout) |
| Chat panel and reaction picker shadows | shadow colour | `--nock-shadow` (offsets and blur unchanged) |
| Author band of a departed author (spec 019) | the two hatch colours | `--nock-ink` and `--nock-white` |

### Flash overlay (spec 016)

The flash of spec 016 changes basis (`_design.md` section 6): the replacer's colour
at 38 % over white, with ink letters. While a letter cell has `data-flash` other
than `""`:

- the cell's own computed `background-color` is `--nock-white`;
- the cell holds one `data-testid="cell-flash"` element, `aria-hidden="true"`,
  `position: absolute`, `inset: 0`, `z-index: -1`, `pointer-events: none`,
  `background-color: var(--player-colour-N)` (N = the `data-flash` value) and
  `opacity: 0.38`. The cell stays its own stacking context (`isolation: isolate`,
  as today), so the overlay paints over the cell's background and under its
  letter and marks;
- the letter's computed `color` is `--nock-ink`, a pencil letter's too (its
  italics stay).

With `data-flash=""` no `cell-flash` element exists. The eight
`.letter[data-flash='N']` text colours of today go.

### Test harness

- "Browser with live server" and "browser with mocked socket" as in spec 040,
  with spec 004's reference catalogue `CAT` served for `/`. Window 1280 by 720,
  desktop context, unless a criterion says otherwise.
- Probes: a criterion that checks a token or a primitive appends its own elements
  to `body` with `page.evaluate` (setup, as spec 035's sentinel), on `/` once
  `catalogue-page` shows, then reads `getComputedStyle`. A token is read through a
  probe whose style uses it (for example `color: var(--nock-navy)`), never from
  the custom property's text, which a build may rewrite.
- Colours are compared after `parseColour` of `tests/colour_contrast.js`: exact
  channels for a token, within 1 per channel for a `color-mix`, alpha within
  0.01. A shadow is read from the computed `box-shadow`: its colour (parsed as
  above), x and y offsets, blur and spread, in px.
- Keyboard focus as spec 035: `tab_to`, or a key press followed by `focus()` from
  `page.evaluate` (spec 035 AC-10's "Focus forced onto a key").
- Static criteria read files with Python only. The built files are those of
  `web/dist`, which the gate builds before pytest; when `web/dist/index.html` is
  missing the test fails with spec 040's message
  `web/dist is missing: run npm --prefix web run build`.
- Engines: Chromium and WebKit locally, Firefox too in CI. No check is
  Chromium-only.

### Colour scans (AC-19, AC-20)

A colour literal is, in a CSS value after quoted strings and `url(...)` are
removed:

- a hex colour: `#` then 3, 4, 6 or 8 hex digits, not followed by a letter, a
  digit, `_` or `-`; except `#0000` and `#00000000` (transparent black, which a
  minifier may write for `transparent`);
- a colour function: one of `rgb`, `rgba`, `hsl`, `hsla`, `hwb`, `lab`, `lch`,
  `oklab`, `oklch`, `color`, immediately followed by `(`, and not preceded by a
  letter, a digit, `_` or `-` (so `color-mix(` is not one);
- a named colour: one of the 148 named colours of CSS Color Level 4 or one of its
  system colours (`Canvas`, `CanvasText`, `LinkText`, `VisitedText`, `ActiveText`,
  `ButtonFace`, `ButtonText`, `ButtonBorder`, `Field`, `FieldText`, `Highlight`,
  `HighlightText`, `SelectedItem`, `SelectedItemText`, `Mark`, `MarkText`,
  `GrayText`, `AccentColor`, `AccentColorText`), any case, as a whole word: not
  preceded or followed by a letter, a digit, `_` or `-` (so `--nock-white` is not
  one). `transparent` and `currentColor` are allowed.

A token declaration is a declaration whose property starts with `--nock-`,
`--player-colour-` or `--player-ink-`. It may hold colour literals.

Built CSS scan (AC-19): each `.css` file under `web/dist/assets/`, comments
removed, split into declarations (`property: value`, ended by `;` or `}`). Every
declaration that is not a token declaration holds no colour literal.

Source scan (AC-20): each `web/src/**/*.svelte`, `web/src/**/*.ts` and
`web/src/**/*.css` file, with comments removed (`/* ... */`, `<!-- ... -->`, and
in `.ts` files and `<script>` blocks `//` to the end of the line):

- in CSS (`.css` files and `<style>` blocks), every declaration that is not a
  token declaration holds no colour literal;
- everywhere else (scripts, markup), the text holds no hex colour and no colour
  function;
- in markup, the attributes `style`, `fill`, `stroke`, `color`, `stop-color`,
  `flood-color` and `lighting-color` hold no named colour.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (new) (browser with live server, probes) Each colour token resolves to its value. On `/`, for each of the 21 tokens of "Colour tokens", a probe `div` with `color: var(<token>)` has the computed colour of the table, as `rgb()`: for example `--nock-navy` gives rgb(27, 47, 85), `--nock-ink` rgb(20, 24, 31), `--nock-selected` rgb(207, 221, 243), `--nock-reveal` rgb(194, 65, 12).
- **AC-2** (new) (browser with live server, probes) Each translucent token resolves to its value. On `/`, for each of the 9 translucent tokens, a probe with `color: var(<token>)` parses to the table's channels and alpha: for example `--nock-scrim` gives 20, 24, 31 with alpha 0.35, and `--nock-legend-bg` 255, 255, 255 with alpha 0.96.
- **AC-3** (new) (browser with live server, probes; browser with mocked socket) The eight imposed player colours and their inks are in place. On `/`, probes give `--player-colour-0` to `--player-colour-7` and `--player-ink-0` to `--player-ink-7` the colours of the table (for example `--player-colour-1` rgb(96, 136, 56) and `--player-ink-1` rgb(75, 106, 44)). On the room page, given a FX-01 snapshot with eight players of colours 0 to 7, the `roster-colour` swatch of the player with `data-colour` N has the computed background of `--player-colour-N`, for each N.
- **AC-4** (new) (browser with live server; browser with mocked socket) The page base uses the tokens. On `/` and on the room page with a FX-01 snapshot, `body` has the computed `background-color` rgb(255, 255, 255) and `color` rgb(20, 24, 31), and its computed `font-family`, read as a list of family names with quotes removed, is `Source Sans 3`, `Segoe UI`, `system-ui`, `sans-serif`. A probe with `font-family: var(--nock-font-clue)` reads `IBM Plex Sans Condensed`, `Arial Narrow`, `Roboto Condensed`, `sans-serif`.
- **AC-5** (new) (browser with live server) Nock serves its fonts itself. The test records every request the page makes from `page.goto("/")` on. After `document.fonts.ready`, `document.fonts.load(f)` resolves to a non-empty list of `FontFace` objects, each with `status` `loaded`, for each `f` of: `400 16px "Source Sans 3"`, `500 16px "Source Sans 3"`, `600 16px "Source Sans 3"`, `700 16px "Source Sans 3"`, `italic 500 16px "Source Sans 3"`, `italic 700 16px "Source Sans 3"`, `500 16px "IBM Plex Sans Condensed"`, `600 16px "IBM Plex Sans Condensed"`. Every recorded request of resource type `font` has a URL on the live server's origin and a response with status 200, and no recorded request goes to another host.
- **AC-6** (new) (static) The font packages are the decided ones and are credited. `web/package.json` lists `@fontsource/source-sans-3` and `@fontsource/ibm-plex-sans-condensed`; the `@fontsource/` imports in `web/src/**/*.ts` and `web/src/**/*.svelte` are exactly the eight files of "Fonts" (each once, no other `@fontsource` import); `README.md` contains `Source Sans 3`, `IBM Plex Sans Condensed` and `SIL Open Font License 1.1`. (Note from the spec writer, 2026-10-16: AC-5 and AC-6 now apply unconditionally, the human having decided the fonts; AC-6 gained the package and import checks.)
- **AC-7** (new) (browser with live server, keyboard only; browser with mocked socket) The focus ring is 2 px navy. On `/`, after `tab_to(page, "force-filter", '[data-force="1"]')`, that button's computed `outline-style` is `solid`, `outline-width` `2px`, `outline-color` rgb(27, 47, 85) and `outline-offset` `2px`. On the room page with a FX-01 snapshot, after the grid gets the keyboard focus (`tab_to(page, "grid")`), the `grid` has `outline-style` `solid`, `outline-width` `2px` and `outline-color` rgb(27, 47, 85). In the touch context of spec 035 AC-10, after a key press and `focus()` on the key `A`, the key has the same three values.
- **AC-8** (new) (browser with live server, probes) A navy surface has a white focus ring. On `/`, a probe `<div class="nock-on-navy"><button type="button" class="nock-button">Test</button></div>` has a `div` with computed `background-color` rgb(27, 47, 85) and `color` rgb(255, 255, 255). After a key press and `focus()` on the button, the button's computed `outline-style` is `solid`, `outline-width` `2px`, `outline-color` rgb(255, 255, 255) and `outline-offset` `-4px`.
- **AC-9** (new) (browser with live server, probes) Every button variant has the same shape. On `/`, four probe buttons with the classes `nock-button nock-button-primary`, `nock-button nock-button-secondary`, `nock-button nock-button-quiet` and `nock-button nock-button-primary` with `disabled` each have the computed values: border radius `6px` on each corner, padding `10px 16px` (top and bottom 10px, left and right 16px), border width `1px` and style `solid` on each side, `font-weight` 600, `font-size` `15.2px` and `line-height` `15.2px`.
- **AC-10** (new) (browser with live server, probes) Each button variant has its colours. On the probes of AC-9 (enabled ones): primary has background rgb(27, 47, 85), text rgb(255, 255, 255) and a border colour with alpha 0; secondary has background rgb(255, 255, 255), text rgb(27, 47, 85) and border rgb(27, 47, 85); quiet has background rgb(230, 237, 249), text rgb(27, 47, 85) and a border colour with alpha 0. Each enabled probe has `cursor` `pointer`.
- **AC-11** (new) (browser with live server, probes) A disabled button keeps a readable text. On `/`, a probe of each variant with the `disabled` attribute has background rgb(238, 242, 248), text rgb(94, 101, 115), border rgb(221, 226, 234) and `cursor` `not-allowed`; the contrast of its text against its background, by spec 035's formula, is at least 4.5:1 (5.22:1 expected).
- **AC-12** (new) (browser with live server, probes, desktop context) The menu primitive has the menu look. On `/`, the probe `<div class="nock-menu"><div class="nock-menu-heading">Vérifier</div><button type="button" class="nock-menu-item">La lettre<span class="nock-menu-detail">4 restantes</span></button><hr class="nock-menu-separator"><button type="button" class="nock-menu-item">Le mot</button></div>`, appended in a `div` with `position: fixed; left: 20px; top: 20px` (setup), gives: menu background rgb(255, 255, 255), radius `8px`, padding top and bottom `6px` and left and right `0px`, `min-width` `220px`, border width `0px`, and a shadow with offsets 0 and 12px, blur 30px, spread -10px and colour 20, 24, 31 at alpha 0.45. Heading: margin `6px 16px 2px`, weight 600, size `11.2px`, `text-transform` `uppercase`, letter spacing 0.896px (within 0.01 px), colour rgb(94, 101, 115). Item: `display` `flex`, `justify-content` `space-between`, padding `10px 16px`, weight 500, size `16px`, line height `19.2px`, colour rgb(27, 47, 85), border width `0px`, and its width equals the menu's `clientWidth` (1 px tolerance); its background has alpha 0, and after `page.hover` on it, rgb(230, 237, 249). Detail: colour rgb(94, 101, 115), `font-style` `normal`, `font-variant-numeric` `tabular-nums`, and its right edge within 1 px of the item's right edge less 16 px. Separator: top border `1px solid` rgb(221, 226, 234), other border widths `0px`, margin top and bottom `4px`, left and right `0px`.
- **AC-13** (new) (browser with live server, probes) The badge primitive is white on red. On `/`, a probe `<span class="nock-badge">2</span>` has background rgb(180, 35, 24), colour rgb(255, 255, 255), weight 700, size `9.92px`, line height `9.92px`, padding `2px 4px` and radius `8px`; its text contrast is at least 4.5:1 (6.57:1 expected).
- **AC-14** (new) (browser with live server, probes) The note primitive is white on ink and fades only when motion is allowed. On `/`, a probe `<div class="nock-note">Bruno : SENT</div>` has background rgb(20, 24, 31), colour rgb(255, 255, 255), weight 500, size `13.6px`, line height `16.32px`, padding `8px 12px`, radius `6px`, `white-space` `nowrap`, a shadow with offsets 0 and 6px, blur 18px, spread -8px and colour 20, 24, 31 at alpha 0.5, `transition-property` `opacity` and `transition-duration` `0.25s`. With the attribute `data-off`, its computed `opacity` is `0` and `pointer-events` `none`. In a page with `page.emulate_media(reduced_motion="reduce")`, the same probe has a `transition-duration` of `0s`.
- **AC-15** (new) (browser with mocked socket) Today's room elements take the token colours. Given a FX-01 snapshot with `you` `p1` (colour 0) and `p2` (colour 3) where (1, 0) holds `T` locked, (1, 1) holds `X` with `wrong` true, (2, 3) holds `D` as a pencil letter of `p1`, and `p2` selects (3, 1) `across`, after the player taps (2, 2) (`across`, VIDE): (2, 2) has background rgb(207, 221, 243) and outline `2px` `solid` rgb(27, 47, 85) with `outline-offset` `-2px`; (2, 1) has background rgb(230, 237, 249); (1, 0) has background rgb(227, 231, 238); (1, 1) has `text-decoration-color` rgb(180, 35, 24); (2, 3), in my word, has `color` rgb(85, 91, 103); (3, 2), in `p2`'s word, has a background within 1 per channel of rgb(231, 223, 250) (`--player-colour-3` at 16 % over white); every `cell` has a right border colour rgb(154, 163, 178); the clue cell (0, 2) has background rgb(238, 242, 248) and its `clue-text` colour rgb(27, 34, 48); its `clue-arrow` (a down arrow, `data-side="bottom"`) has the computed `border-top-color` rgb(20, 24, 31). (Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells. Once spec 042 is built, the arrow of (0, 2) is an `svg` drawn in (1, 2), and this check reads the computed `stroke` of its `path`, rgb(20, 24, 31), in place of a `border-top-color`; the test-writer updates it before spec 042's implementer runs.)
- **AC-16** (new) (browser with mocked socket) A flash is the replacer's colour at 38 % over white, under an ink letter. Given a FX-01 snapshot with `you` `p1` (colour 0) and `p2` (colour 1), where (1, 0) holds `T` by `p1` and (1, 1) holds `A` as a pencil letter of `p1`, after the player taps (1, 0): when the mock sends `letter_changed` by `p2` setting (1, 0) to `B`, then within 300 ms (1, 0) has `data-flash="1"`, its computed `background-color` is rgb(255, 255, 255), its `color` is rgb(20, 24, 31), and it holds exactly one `cell-flash` element with `aria-hidden="true"`, computed `position` `absolute`, `z-index` `-1`, `pointer-events` `none`, `opacity` `0.38`, `background-color` equal to `p2`'s `roster-colour` background (rgb(96, 136, 56)), and a bounding box within 1 px of the cell's padding box; the cell's computed `isolation` is `isolate`. When the mock then sends `letter_changed` by `p2` setting (1, 1) to the pencil letter `C`, (1, 1) shows `C` with `font-style` `italic` and `color` rgb(20, 24, 31) while `data-flash` is `1`. Once `data-flash` is `""` again (spec 016's 1,000 ms), the cell holds no `cell-flash`.
- **AC-17** (new) (browser with mocked socket) The flash keeps the letter readable for every player colour. For each N from 0 to 7, given a FX-01 snapshot with `you` `p1` and a player of colour N who replaces `p1`'s `T` at (1, 0) (as AC-16), the letter's contrast against the composite of `--player-colour-N` at 38 % over white is at least 4.5:1, and spec 035's contrast scan run during the flash finds no offending element.
- **AC-18** (new) (static) The icon module holds the design's shapes. `web/src/lib/icons.ts` exports `ICONS`, `PLAYER_ICONS` and `NOCK_MARK_POINTS`; its text contains each `d` string and each `points` string of the two tables of "Icons" exactly once inside quotes, the numbers `x: 2`, `y: 6`, `width: 20`, `height: 12`, `rx: 2` for `clavier`'s rectangle, the circles `cx: 12, cy: 13.5, r: 7.5`, `cx: 12, cy: 12, r: 9` and `cx: 5, cy: 5, r: 4.4`, the rectangle `x: 0.9, y: 0.9, width: 8.2, height: 8.2`, the thirteen names `undo`, `aide`, `salon`, `clavier`, `menu`, `crayon`, `swap`, `effacer`, `chrono`, `flag`, `chevron-left`, `chevron-right`, `smile` as keys, and the string `'0,0 10,0 10,14 5,10 0,14'`. (Note from the spec writer, 2026-10-16: second round, the five icons of sheet 4.2 and the player icons of sheet 4.3 were added.)
- **AC-19** (new) (static) The built CSS holds no colour outside the token block. With the rules of "Colour scans": the CSS under `web/dist/assets/` declares each custom property of "Colour tokens", the translucent tokens and the player table exactly once; and its built CSS scan finds no colour literal. The scan's checker flags the samples `a{color:#1b2f55}`, `a{color:#FFF}`, `a{background:rgb(0 0 0/20%)}`, `a{border-color:White}`, `a{box-shadow:0 1px 0 hsl(0 0% 0%)}`, `a{outline-color:Highlight}`, and accepts `:root{--nock-navy:#1b2f55}`, `:root{--player-ink-1:#4b6a2c}`, `a{color:var(--nock-navy)}`, `a{background:transparent}`, `a{border-color:currentColor}`, `a{background:#0000}`, `a{background:color-mix(in srgb,var(--player-colour-1) 16%,var(--nock-white))}`, `a{font-family:"White Rabbit"}`, `a{background:url(red.svg)}` and `a{grid-area:sidebar}`.
- **AC-20** (new) (static) The client sources hold no colour outside the token block. With the rules of "Colour scans", the source scan of `web/src` finds nothing. The scan's checker flags the samples `<style>a{color:#1b2f55}</style>`, `<rect fill="#1B2F55"/>`, `<rect fill="white"/>`, `<div style="color: rgb(0 0 0)">`, and in a `.ts` file `const c = '#14181f'`; and accepts `<rect fill="currentColor"/>`, `<rect fill="none"/>`, `/* #1B2F55 */`, `// #1B2F55`, `const id = '#cell-1-2'` and `<p>white</p>`.
- **AC-21** (new) (browser with live server, probes; browser with mocked socket, probes) Form controls take the page font, not the OS control font. On `/` once `catalogue-page` shows, and on the room page once the `grid` of a FX-01 snapshot shows, the test appends to `body` the probe `<div style="font-size: 20px"><button type="button">Bouton</button><input type="text" value="Texte"><select><option>Choix</option></select><textarea>Zone</textarea></div>` (setup). Each of the four controls has the computed `font-family` that, read as a list of family names with quotes removed (as AC-4), is `Source Sans 3`, `Segoe UI`, `system-ui`, `sans-serif`, and the computed `font-size` `20px`, equal to the wrapping `div`'s. On the same pages, a real control has the same `font-family`: on `/` the `force-filter` button `[data-force="1"]`, on the room page the `timer-toggle` button (spec 027). (Note from the spec writer, 2026-10-21, at the lead's request: added with the form-control rule of "Page base"; AC-4 only read `body`.)

## Edge cases and errors

Current tests whose expectations change, all still passing. The lead adds a dated
note to each spec named here when this spec is approved, and the test-writer
checks each test against it.

- Focus outline (spec 035 AC-2, AC-10, AC-12; spec 021 AC-10; spec 022 AC-16):
  3 px blue (#1A4FD6) becomes 2 px navy. Their checks ask for at least 2 px and
  3:1 against white (13.26:1), so they pass. The feed list's "Not clipped" check
  measures a smaller ring (offset plus width 4 px instead of 5 px). (AC-7)
- Selected cell (spec 035 AC-2, spec 007, spec 013 AC-3 and AC-4): the outline
  goes from 3 px ink to 2 px navy, inside the cell; its background from yellow to
  selected blue. Spec 035 needs `solid` and at least 2 px; spec 013 AC-4 needs a
  background different from a remote player's cell and a tinted cell, which
  holds (rgb(207, 221, 243), white, the 16 % tint). (AC-15)
- Player colours (spec 012, spec 013 AC-1 to AC-3, spec 016 AC-2, spec 019): the
  tests compare colours with the roster swatches, which follow the new values;
  the eight colours stay pairwise different. (AC-3)
- Flash (spec 016 AC-2, spec 020 AC-1 and AC-7, spec 024 AC-9, spec 035 AC-8 state
  K3): spec 016's test looks for the swatch colour on the cell or any element in
  it, which `cell-flash` gives. Spec 020's pencil letter takes ink during the
  flash, the same colour as a normal letter there, as its note of 2026-10-15
  requires. Spec 024's `reveal-mark` is drawn in the cell's text colour (ink)
  against the cell's computed background (white during the flash): 17.79:1.
  Spec 035's contrast scan measures the letter against the cell's background.
  Spec 016's text "uses that player's colour" still holds; its dated note says
  "at 38 % over white". (AC-16, AC-17)
- Tint (spec 013 AC-2, spec 020 AC-7): 28 % becomes 16 %. At 28 %, the pencil grey
  falls to 4.32:1 on `--player-colour-3`'s tint, below spec 020's 4.5:1; at 16 %
  every tint keeps the pencil grey above 5.2:1. Spec 013 AC-2 only needs the
  tinted cell to differ from a plain one. (AC-15)
- Text contrast (spec 035 AC-8, states K1 to K7): every new text pair is in
  `_design.md` section 2 and reaches 4.5:1; the muted labels on clue blue-grey
  (disabled reveal and vote buttons) reach 5.22:1. (AC-11, AC-15)
- Text widths (spec 013 AC-6, spec 014 AC-7 to AC-10, spec 020 AC-7, spec 021
  AC-11, spec 022 AC-15 and AC-19, spec 024 AC-8, spec 025 AC-8, spec 027 AC-8):
  once the fonts load (AC-5), every text is set in Source Sans 3 instead of the
  system font (DejaVu Sans in CI), which is narrower; the thresholds of spec 014
  are in rem and its compact-button rule follows measured widths. These tests are
  run in all three engines before this spec is done; a failure goes to the lead.
- Control sizes (spec 006 AC-7, spec 013 AC-6, spec 014 AC-7 to AC-10 and the
  compact-button rule of AC-9, spec 019 AC-5, spec 020 AC-7, spec 024 AC-8,
  spec 027 AC-8, spec 028 AC-7, spec 033 AC-9): with the form-control rule of
  "Page base", a `button`, `input`, `select` or `textarea` that sets no font of its
  own goes from the browser's default control size (about 13.33 px) to its
  parent's size (16 px on most of today's pages) and its family's widths, so it
  gets wider and taller; the toolbar, the header and the roster may need more
  room or another row. These tests measure controls' widths, heights or rows, or
  check that the room page and its toolbar still fit; they are run in all three
  engines before this spec is done; a failure goes to the lead. (AC-21) (Note from
  the spec writer, 2026-10-21, at the lead's request: added with the form-control
  rule.)
- Measuring before the fonts load: with `font-display: swap` a text is first drawn
  in the fallback font, which differs per OS (Segoe UI on Windows, DejaVu Sans in
  CI), so a measurement taken then differs per OS. Rule for every browser test, of
  this spec and of every other spec: a test that reads a size or a position that
  depends on text (a bounding box, `clientWidth`, `scrollWidth`, `offsetHeight`,
  an overflow, a wrap, a line count, or a check whether an element fits or is
  clipped, of an element that holds text or is laid out next to text) first
  waits for `document.fonts.ready`, with
  `page.evaluate("() => document.fonts.ready.then(() => true)")`, after the page
  shows the text it measures and before the first read; it waits again after a
  change that shows a face not shown before (an italic pencil letter, a clue
  cell's IBM Plex Sans Condensed, a bold text). Every shared helper in `tests/`
  that opens a page and returns once it shows its content (for example
  `open_room`, `open_fx01`, `open_mock_room` followed by `show_snapshot`,
  `make_page`, `start_from_catalogue`) does the same wait before it returns. A
  test that only reads colours, computed styles or texts needs no wait. The
  test-writer applies the rule when writing or updating a test; the reviewer
  checks it. (Note from the spec writer, 2026-10-21, at the lead's request: added
  so that measurements are taken in Nock's fonts on every OS. It stays a rule, not
  a criterion: the gate links criteria to the tests of one spec and cannot check
  how other specs' tests measure. See Decision 7.)
- Author band of a departed author (spec 019): its hatch goes from #333333 and
  white to ink and white; ink keeps at least 3:1 on every cell background.
- A font file that fails to load (offline, blocked): the browser uses the next
  family of the stack; nothing else changes. (AC-5)
- `color-mix()` is supported by the current Chromium, Firefox and WebKit. (AC-15)
- A minifier may rewrite a token's value (`#1B2F55` as `#1b2f55`, a translucent
  value as an 8-digit hex) or `transparent` as `#0000`; the probes read computed
  colours, and the scans allow `#0000`. (AC-1, AC-2, AC-19)
- `web/public/favicon.svg` keeps its colours: it is not CSS and not under
  `web/src`. (AC-19, AC-20)
- Reactions and chat text may hold coloured emoji: user content, not a colour of
  the client. (AC-20)

## Out of scope

- Any change of layout, size, position or element other than `cell-flash`: the top
  bar, the Salon sheet and column, the clue bar in navy, the keyboard keys ✎ and
  ⇄, the end band and the recap (later specs, `_design.md` section 14).
- The grid cell design of `_design.md` section 6: corner triangles, the revealed
  notch, arrows in letter cells, the letter and clue sizes, the flag's new size.
  Dashed borders, initials, the author band and the top-right reveal mark stay
  until their specs are refined.
- Putting the primitives on today's controls (they change sizes); later specs do
  it control by control.
- Auteurs mode and its inks on screen (the ink tokens exist; nothing uses them).
- The Menu switches decided by the human on 2026-10-16: « Mots des autres » (the
  tint stays on, as today), « Auteurs » and « Accessibilité » with its player
  icons (the shapes exist in `icons.ts`; nothing draws them). (Note from the spec
  writer, 2026-10-16: second round, added.)
- Font Awesome: no icon is missing yet.
- Line heights and the type scale of `_design.md` section 4 beyond the primitives.
- A dark mode, forced-colours (high contrast) styles, print styles.
- Screenshot comparison with the sheet (`_design.md` section 13, a human
  decision).

## Work packages

None.

## Decisions

Decided with the human on 2026-10-16 (the design session):

1. The palette, the eight player colours and their inks, the two font families,
   the icon style and Font Awesome Free as the fallback icon set are those of
   `_design.md`, which the human validated.
1b. The fonts come in as the npm packages `@fontsource/source-sans-3` and
   `@fontsource/ibm-plex-sans-condensed`, imported per weight used, self-hosted by
   the build (decided by the human on 2026-10-16).

Proposed by the spec writer, each already part of the spec above:

2. Epic: E10 (Quality bar), with no new epic. The design is a quality rule that
   holds on every screen, as accessibility does.
3. Primitives are global classes tested on probe elements, so this spec changes no
   layout and no existing control, and later specs apply them one by one.
4. Today's colours map to tokens by job, so the scans can pass before the screens
   are redrawn. Two non-colour values change with them because the new colours
   need them: the selected cell's outline (2 px navy inset, the design's border,
   still meeting spec 035) and the tint (16 %, for the pencil contrast).
5. The flash is an overlay at 38 % opacity rather than a mixed background: it
   gives the design's look and keeps spec 016's swatch check as written. A full
   player colour behind the letter, as today, cannot work with the new palette:
   on `--player-colour-1` neither ink (4.30:1) nor white (4.14:1) reaches 4.5:1.
6. Both the built CSS and the sources are scanned: the build catches every rule
   that reaches the browser, the sources catch inline styles and SVG attributes.
7. Form controls inherit the page font through one global rule rather than one
   rule per component, and browser tests that measure text wait for
   `document.fonts.ready` (rule in "Edge cases and errors"), so that text is set
   and measured in Nock's own fonts on Windows and Ubuntu alike. The wait is a
   test rule, not a criterion, because no criterion of this spec can observe how
   another spec's tests measure. (Note from the spec writer, 2026-10-21, at the
   lead's request: added.)

## Open questions

1. Closed. Font files: the npm packages `@fontsource/source-sans-3` and
   `@fontsource/ibm-plex-sans-condensed`, imported per weight used (decided by the
   human on 2026-10-16; see "Fonts").
2. Closed. Departed grey: no such colour; a departed player's letters are plain
   ink in Auteurs mode, and `--nock-departed` is removed (decided by the human on
   2026-10-16).

No question is left open.

(Note from the spec writer, 2026-10-16: second round. Three questions of the
first round are settled and left this list. Rule grey: #9AA3B2 is kept, decided by
the human on 2026-10-16. Empty cells (rule grey) and the selected word's clue
(selected blue): decided by the human on 2026-10-16 and drawn in sheet 4.2. The
connection banner: drawn in sheet 4.2 as a clue blue-grey band with ink text and a
line-grey border, which the mapping table now follows.)
