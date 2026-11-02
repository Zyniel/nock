---
area: client
file: foundation
status: approved
---

# client/foundation - State lines, motion, tokens, fonts, icons, components, redraws

## Purpose

What every screen is built from: the colour tokens, the two font families, the
icon shapes, the shared components and the focus ring, the one-line states and
the motion allowed; and what a frame may redraw in the grid, so the room stays
smooth on a phone.

## Depends on

- `product.md`: accessibility and performance baselines, the reference phone, the
  typing pace and the local echo.
- `client/shell.md`: the room page, its snapshots and frames, the opening before
  the room shows.
- `social/catch-up.md`: the catch-up ring a frame redraws.

## Rules

### States and motion

1. A page's state (waiting, empty, failed, done) is one line of text where its
   content will be: muted while waiting or empty, an error line when failed, a
   confirmation line when done. No spinner, no skeleton: no `<progress>`, no
   `role="progressbar"`, no CSS animation (`@keyframes` or an `animation`
   property, vendor prefixes included) in the sources or the built CSS.
2. The note's fade is a transition; under reduced motion it has none.

### Visual foundation

3. Colours come only from the tokens declared once in the token block of
   `web/src/app.css` (`--nock-*`, `--player-colour-N`, `--player-ink-N`).
   Outside a token declaration no CSS declaration, in `web/src` or in the
   built CSS, holds a colour literal: a hex colour, a colour function (not
   `color-mix()`), or a named or system colour; `transparent` and
   `currentColor` are allowed, and so is `#0000` (transparent). Scripts and
   markup hold no hex colour or colour function, and colour attributes of
   markup (`style`, `fill`, `stroke`, …) no named colour. Comments,
   `web/public/favicon.svg` and user content (emoji) are not colours of the
   client.
4. Nock serves its two font families itself, from the packages
   `@fontsource/source-sans-3` and `@fontsource/ibm-plex-sans-condensed`,
   importing only the eight faces the design uses; no request goes to
   another host. `README.md` credits both under the SIL Open Font License 1.1.
   A face that fails to load falls back to the next family. Form controls
   take their parent's font, never the system's.
5. The faces are served in their `latin` and `latin-ext` subsets only. The
   room page preloads the `latin` files of the grid's letter and clue faces
   (`_design/foundation.md`, « Typography »).
6. `web/src/lib/icons.ts` holds the design's icon shapes, the eight player
   icons and the Nock mark as data.
7. The shared components (buttons in their variants and disabled, menus and
   their items, details, headings and separators, the badge, the note) and the
   focus ring, including its form on a navy surface, are global styles, their
   colours those of « Components »; a hidden note lets pointers through.
   Nothing of the Vite template's demo is left. The grid's ring, its own
   outline, is drawn again by an overlay over the whole grid, painted after
   the cells, hidden from assistive technology and letting pointers through,
   so the ring shows along every edge cell.

### What a frame redraws

8. Once the room shows, each of the following mutates (adds, removes or
   changes a node, an attribute or a text) no node of the grid outside the
   cells whose drawing it changes and the nodes inside them:
   - a frame other than a snapshot: one that changes no cell's drawing (a
     `pong`, a `chat_message`, a `selection_moved` that leaves its cursor
     where it was) mutates no node of the grid; a letter change only its
     cell; a cursor's move only the cells it leaves and enters, and those its
     player's word tint leaves or enters;
   - a flash's start and end, and a catch-up ring's (`social/catch-up.md` rule
     14), only their cell;
   - a pinch no cell, and the cells still follow `_design/cells.md` at the new
     side.

   A snapshot, a reconnection's included, may redraw the whole grid.

   On the reference phone (`product.md` rule 21) and a 13 by 17 grid, a frame
   that changes no cell costs at most 2 ms of main-thread time on average over
   a burst of such frames.
   With the 7 other players each typing at `product.md` rule 24's pace,
   the local echo of `product.md` rule 23 holds.

### Look

- Tokens, player colours and inks: `_design/foundation.md`, « Colour tokens »,
  « Player colours ». Fonts: « Typography ». Icons: « Icons ». Components and
  focus ring: « Components », « Focus ». The scans: « How conformance is
  checked ».
- Grid cells in token colours and the flash: `_design/cells.md`, « Letter cell
  backgrounds », « Letter marks », « Clue cells », « Direction arrows ».
- The state lines: `_design/pages.md`, « States: opening, loading, empty,
  error ».

## Acceptance criteria

- **AC-1** The client's sources and built CSS hold no `@keyframes`, no
  `animation` property (prefixed or not), no `<progress` and no
  `role="progressbar"`: `a{-webkit-animation:spin 1s}` is refused and
  `a{transition:opacity .25s}` passes. (← 048 AC-13)
- **AC-2** Each colour token, translucent token, player colour and ink
  resolves to its value in « Colour tokens » and « Player colours », the
  roster swatch of colour N shows player colour N, the page base takes the
  tokens' white and ink, the page and every form control use the UI font
  stack of « Typography », a control at its parent's size, and the clue font
  token gives the clue stack of « Typography ».
  (← 041 AC-1, 041 AC-2, 041 AC-3, 041 AC-4, 041 AC-21)
- **AC-3** The eight faces load from Nock's origin with status 200 and no
  request leaves it; `web/package.json` lists the two font packages, the
  client imports exactly the eight faces, and `README.md` credits both
  families under the SIL Open Font License 1.1. (← 041 AC-5, 041 AC-6)
- **AC-4** The focus ring on a force chip, the grid and an in-app key, the
  ring on a navy surface, the four button looks (disabled text at 4.5:1 at
  least), the menu, its item (hovered too), detail, heading and separator, the
  badge and the note (hidden, and with reduced motion) each follow
  « Components ». (← 041 AC-7, 041 AC-8, 041 AC-9, 041 AC-10, 041 AC-11,
  041 AC-12, 041 AC-13, 041 AC-14)
- **AC-5** On FX-01 with a locked `T`, a wrong `X`, a pencil `D`, Bob's word
  and VIDE selected, every cell's colours, borders and arrows follow the cells
  design. When Bob replaces a letter, the cell flashes as that design draws
  it, until the flash ends, its letter in ink, a pencil one too, and for every
  player colour the letter keeps 4.5:1 at least. (← 041 AC-15, 041 AC-16,
  041 AC-17)
- **AC-6** The colour scan refuses `<rect fill="white"/>`, passes
  `:root{--nock-navy:#1b2f55}`, and finds nothing in `web/src` or the built
  CSS, which declares each token once; `icons.ts` holds every shape of the
  design once; no demo file or text is left. (← 041 AC-18, 041 AC-19, 041 AC-20,
  040 AC-26)
- **AC-7** On a fresh FX-01 room with (1,0) across selected and the grid
  focused from the keyboard, the ring shows in painted pixels over the letter
  cells of the grid's right and bottom edges: at the middle of the outer side
  of each of (1,4) to (4,4) and (4,1) to (4,4), the 3 px inside the grid's edge
  hold a pixel of the ring's navy (`--nock-navy`, #1B2F55).
- **AC-8** On FX-01 with Bob's cursor on (1, 1) across, a `pong`, a
  `chat_message` from Bob and a `selection_moved` putting Bob on (1, 1) across
  again mutate no node of the grid.
- **AC-9** On FX-01, Bob's `M` in the empty (1, 2) mutates no node of the
  grid outside (1, 2); nor does Bob's `X` over my `M` there, from its flash's
  start to its end.
- **AC-10** On FX-01, Bob's cursor going from (1, 1) to (1, 2) across mutates
  only those two cells; Bob then turning to down on (1, 2) mutates only the
  cells of TAMIS and MIME.
- **AC-11** On a touch phone with FX-01 and Bob on (1, 1), a pinch from zoom 1
  to 1.5 mutates no cell, and Bob's triangle then has the leg « Other players
  on a cell » gives the new cell side.
- **AC-12** On the reference phone, on FX-02 with 7 other players each typing
  2 letters a second in their own words, their cursors following, 40 letters
  typed 250 ms apart show in their cell within 50 ms at the p95.
- **AC-13** On the reference phone, on FX-02 with the 7 other players' cursors
  in the grid, Bob sending 100 `select_cell` in a row for the cell and
  direction he already holds costs the page at most 2 ms of main-thread time
  per `selection_moved`, on average over the 100.
- **AC-14** On FX-01, after a reconnection whose snapshot is at 9 with
  `seen_seq` 5 stored, a catch-up answer naming only (1, 2) mutates no node of
  the grid outside (1, 2), from the start of its ring to the ring's end 5
  seconds later.
- **AC-15** The built client declares its font faces for the `latin` and
  `latin-ext` subsets only, and ships no font file of another subset.
- **AC-16** `/r/ABC123` preloads, from Nock's origin, the `latin` files of
  Source Sans 3 at 500 and of IBM Plex Sans Condensed at 600.

## Edge cases

- A minifier writing `transparent` as `#0000` passes the scan (AC-6).

## Out of scope

- A dark mode, forced colours, print styles; screenshot comparison with the
  sheets.
- The pages, their frames and texts, the opening, the brand: `client/shell.md`.
  What each cell's state draws: `gameplay/board.md`, `gameplay/co-op.md`,
  `social/presence.md`; the catch-up ring itself: `social/catch-up.md`. The
  connection band: `platform/reconnection.md`.

## Code

- `web/src/app.css` (tokens, page base, focus ring, components, the note's
  fade), `web/src/lib/GridViewport.svelte` (the grid's ring and its overlay,
  what a frame redraws), `web/src/main.ts` (fonts, subsets, preload),
  `web/src/lib/icons.ts`.
- Tests: `tests/test_foundation_*`, `tests/test_spec_041_*` and the
  `tests/test_spec_040_*` and `test_spec_048_*` files of the cited criteria.
