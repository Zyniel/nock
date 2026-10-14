---
id: "035"
title: Accessibility
status: approved
---

# 035 - Accessibility

Epic E10 Quality bar (US-10.1) · Release: MVP · Epic depends on: All
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The grid
elements are those of spec 006, selection and the clue bar spec 007, keys specs
008 and 009, presence and the feed spec 013, host controls spec 014, undo spec
018, the check controls spec 023, the completion banner spec 026, the pages and
i18n spec 040, the catalogue spec 004.

## Goal

As a player using a keyboard or a screen reader, I want the full game, so that I can play with my group.

These criteria apply to every story above and belong in each agent's definition of done.

## Public interface

No new Python name and no new protocol message. Client only (`web/src/`).

### Build order

This spec is built after specs 023 and 026: its keyboard walk uses their controls.

### Grid roles (replaces spec 006's bare `role="grid"`)

- The `grid` element keeps `role="grid"`, `aria-label` `t("grid.label")` and
  `tabindex="0"`, and gains `aria-describedby="grid-hint"`.
- Its children are exactly `height` elements `data-testid="grid-row"` with
  `role="row"` and `data-row` (0 to `height - 1`), in row order. Each row holds
  exactly the `width` `cell` elements of that row (spec 006), in column order.
  Rows must not change the layout of spec 006 (for example `display: contents`).
- Every `cell` element, whatever its `data-type`, has `role="gridcell"` and
  `id="cell-<row>-<column>"` (for example `cell-2-2`).
- Letter cells have `aria-selected="true"` on the selected cell and
  `aria-selected="false"` on the others. Clue and empty cells have no
  `aria-selected`.
- While a cell is selected, the `grid` element has `aria-activedescendant` equal to
  that cell's `id`; with nothing selected it has no `aria-activedescendant`.
- Clue arrows stay `aria-hidden="true"` (spec 006).

### Screen reader announcement

- A `data-testid="grid-announcement"` element with `role="status"`,
  `aria-live="polite"`, `aria-atomic="true"` and class `visually-hidden`, present
  whenever the grid is shown.
- Its text is set each time the selection changes (cell, direction or word) to
  `t("a11y.announcement", { clue, direction, length, position })`, where `clue` is
  the selected word's clue text, `direction` is `t("a11y.direction.across")` or
  `t("a11y.direction.down")`, `length` the number of cells of the word, and
  `position` the 1-based index of the selected cell in the word. A word of one
  cell uses `t("a11y.announcement_one", { clue, direction })`. With nothing
  selected the text is empty.

### Leaving the grid from the keyboard

Spec 009 handles `Tab` and `Shift+Tab` on the grid (next and previous unfinished
word). To leave the grid:

- `Escape` (no modifier) while the grid has the focus releases it: the next key
  press, if it is `Tab` or `Shift+Tab`, is left to the browser (its default is not
  prevented and the selection does not change), so the focus moves to the next or
  previous focusable element in document order.
- Any other key press, or the grid losing then regaining the focus, ends the
  release: `Tab` selects words again.
- `Escape` itself changes nothing else (selection, letters and pending edits stay).
- A `data-testid="grid-hint"` element, `id="grid-hint"`, class `visually-hidden`,
  holds `t("a11y.grid_hint")`.

### In-app keyboard (spec 009, touch screens)

(Note from the lead, 2026-10-13: added in place of "its keys are focusable and get
the visible focus", which contradicted spec 009. The human asked for the best
accessibility option. Tested by AC-10.)

Spec 009 already fixes these points, and this spec does not test them again: the 26
`key` elements are buttons with `data-key` and the letter as text; `key-delete` is a
button with `aria-label` `t("keyboard.delete")` and an icon; the `keyboard` element
has `aria-label` `t("keyboard.label")`; tapping a key never moves the focus off the
grid. Spec 009 AC-3 checks the rows and the typing, and spec 009 has no test that the
focus stays on the grid. This spec adds the following:

- Each `key` and the `key-delete` is a `<button type="button">` with
  `tabindex="-1"`, so it is never a Tab stop.
- Each key has an accessible name. For a letter key it is the letter (`A` to `Z`),
  and for `key-delete` it is `fr.json["keyboard.delete"]` (`Effacer`). Neither the
  keys nor any of their ancestors have `aria-hidden="true"`, the `inert` attribute,
  or `role="presentation"` or `role="none"`. A screen reader user on a touch screen
  reaches the keys by swipe navigation.
- After a tap on a key, `document.activeElement` is the `grid` element.
- If a key gets the focus anyway (a screen reader can move the focus there), it
  shows the visible focus of "Visible focus and non-colour signals" (AC-2's
  outline).

### Visible focus and non-colour signals

- Every element that can take the keyboard focus (links, buttons, inputs,
  selects, the `grid`) shows, while it has the focus after a keyboard move, an
  outline whose computed `outline-style` is neither `none` nor `auto` and whose
  computed `outline-width` is at least 2 px, with an `outline-color` of contrast at
  least 3:1 against the page background. (A global `:focus-visible` rule is
  enough; spec 006's `.grid:focus { outline: none; }` goes.)
- The selected letter cell (spec 007) always has a computed `outline-style` of
  `solid` and an `outline-width` of at least 2 px, whether the grid has the focus
  or not; other letter cells have `outline-style` `none`.
- A locked letter cell (spec 016) shows its letter with a computed `font-weight`
  of at least 700; an unlocked letter cell's `font-weight` is below 700.
- Each `remote-selection` element (spec 013) of a player who gets a label (see
  "Initials on a crowded cell") holds one `data-testid="remote-initials"` element
  whose text is the initials of that player, drawn inside the cell's box. The
  `remote-selection` of a player who gets no label holds no `remote-initials`.
  (Note from the lead, 2026-10-13: "each `remote-selection` holds one" became "each
  labelled player's", for the "+N" rule of AC-11.)
- Struck-through wrong letters are spec 023's (`line-through`).
- Roster states (spec 013) are not shown by dimming. The `roster-player` items, their
  descendants and their ancestors have a computed `opacity` of 1. The
  `roster-nickname` of an `idle` player has a computed `font-style` of `italic`
  and no `line-through` in its computed `text-decoration-line`. The
  `roster-nickname` of a `disconnected` player has `italic` and `line-through`. The
  `roster-nickname` of an `active` player has `normal` and no `line-through`. The
  state is also written in the row: `roster-state` holds `t("presence.<state>")`,
  as in spec 013. (Note from the lead, 2026-10-13: settled here in place of "dimmed
  rows that still reach 4.5:1". Without opacity the text keeps its full contrast,
  and the state does not depend on colour. Tested by AC-7.)

Initials (`web/src/lib/remoteSelections.ts`):

```ts
// The initials of a nickname: split on spaces, hyphens, apostrophes (' and ’)
// and underscores; with two or more parts, the first character of each of the
// first two parts; with one part, its first two characters. Upper-cased with
// toLocaleUpperCase('fr'). Characters are code points.
export function initialsOf(nickname: string): string

export interface RemoteSelection {
  // ... fields of spec 013
  initials: string
}
```

Examples: `Ana` gives `AN`, `Jean-Luc` gives `JL`, `marie ève` gives `MÈ`,
`R2` gives `R2`, `Zoé` gives `ZO`, `_Max_` gives `MA`.

### Initials on a crowded cell

(Note from the lead, 2026-10-13: added for the "+N" rule the human approved. On
FX-02 at 360 px wide a cell is about 25 px, the labels have a font of at least
7 px, and three or more cursors on one cell made the labels overlap. Tested by
AC-11.)

Terms:

- The cursors of a cell are the other players whose `remote-selection` is drawn
  on that cell (spec 013: never `you`, never a disconnected player), in roster
  order (the order of the `roster-player` items, which is the join order of spec
  013). `n` is their number.
- A label is a `remote-initials` element or the overflow label below.
- The cell side `c` is the width of the `cell` element's bounding box, in CSS
  pixels.
- A corner is one of `top-left`, `bottom-right`, `top-right`, `bottom-left`. These
  four names, in this order, are the slots of a cell.

How many slots a cell has (`S`):

| Cell side `c` | Slots `S` | Corners used |
| --- | --- | --- |
| 44 px or more | 4 | `top-left`, `bottom-right`, `top-right`, `bottom-left` |
| at least 20 px and below 44 px | 2 | `top-left`, `bottom-right` |
| below 20 px | 1 | `top-left` |

Why these values: the label font is `max(7px, 0.2 × c)`, with line height 1.1 and
1 px of padding on each side, so two bold capitals are at most about
`1.9 × font + 2` px wide and `1.1 × font` px high. Two labels side by side, as the
four-corner layout needs, fit from about 44 px. Two labels in diagonal corners,
one above the other, fit from about 18 px. Below 20 px only one label is placed.

Who gets a label:

- When `n <= S`, every cursor gets a label: cursor `i` (0-based, roster order)
  takes slot `i`.
- When `n > S`, cursors 0 to `S - 2` get labels in slots 0 to `S - 2`, and the last
  slot (slot `S - 1`) holds one overflow label for the `k = n - S + 1` cursors
  without a label. With `S = 1`, nobody gets initials and the overflow label reads
  `+n`.

| `S` | `n` | Labels |
| --- | --- | --- |
| 4 | 1 to 4 | one `remote-initials` per cursor |
| 4 | 5, 6, 7 | 3 `remote-initials`, then `+2`, `+3`, `+4` at `bottom-left` |
| 2 | 1, 2 | one `remote-initials` per cursor |
| 2 | 3 to 7 | 1 `remote-initials` at `top-left`, then `+2` to `+6` at `bottom-right` |
| 1 | 1 | one `remote-initials` at `top-left` |
| 1 | 2 to 7 | only `+2` to `+7` at `top-left` |

Markup:

- Each `remote-initials` has `data-corner` set to the name of its corner.
- The overflow label is `data-testid="remote-overflow"`, a descendant of the `cell`
  (not of any `remote-selection`). It has `data-corner`, `data-count` equal to `k`,
  `aria-hidden="true"`, and the text `t("grid.remote_overflow", { count: k })`, for
  example `+2`. It has the same font and colours as `remote-initials`.
- The same `cell` holds one `data-testid="remote-overflow-label"` element with the
  class `visually-hidden` and the text `t("a11y.remote_overflow", { count: k })`,
  for example `2 autres joueurs`. A screen reader reads it with the cell, in place
  of the `+2`. Because `k` is always 2 or more, no singular form is needed.
- A cell with `n <= S` holds no `remote-overflow` and no `remote-overflow-label`.

Layout, for every cell with `c` of at least 20 px:

- Each label's bounding box lies inside the cell's bounding box (1 px tolerance).
- The labels of one cell never overlap. For any two of them, their bounding boxes
  overlap by at most 1 px horizontally or by at most 1 px vertically.
- A label in corner X has the X corner of its bounding box within 3 px of the X
  corner of the cell's bounding box, on both axes. For example, a `top-left` label
  has its left edge at most 3 px right of the cell's left edge and its top edge at
  most 3 px below the cell's top edge.
- Every label has a computed `font-size` of at least 7 px and a computed
  `visibility` of `visible`. Its contrast is covered by AC-8.

Below 20 px, the slot and count rules still apply, but a 7 px label may not fit
inside the cell. The player can zoom in (spec 006).

### Text contrast

Every visible text on the pages listed in "Test harness" has a contrast ratio of
at least 4.5:1 with its background (WCAG 2.x formula), the same threshold for
large text. Opacity counts: text inside an element with `opacity` below 1 is
measured with that opacity applied.

### Language

The interface is in French: `<html lang="fr">` (spec 040 AC-15) and every
interface string comes from `web/src/i18n/fr.json` through `t()` (spec 040 AC-22
to AC-24). This spec adds a runtime check of the rendered pages (AC-9).

### Visually hidden

A global CSS class `visually-hidden` hides an element from sight but not from
assistive technology (1 px clipped box, `position: absolute`, `overflow: hidden`,
`white-space: nowrap`; never `display: none` or `visibility: hidden`).

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `a11y.announcement` | `{clue}, {direction}, {length} lettres, lettre {position}` |
| `a11y.announcement_one` | `{clue}, {direction}, 1 lettre` |
| `a11y.direction.across` | `horizontal` |
| `a11y.direction.down` | `vertical` |
| `a11y.grid_hint` | `Flèches pour se déplacer, Tab pour le mot suivant. Échap puis Tab pour quitter la grille.` |
| `grid.remote_overflow` | `+{count}` |
| `a11y.remote_overflow` | `{count} autres joueurs` |

(Note from the lead, 2026-10-13: the last two keys were added for the "+N" rule of
AC-11.)

### Test harness

- "Browser with live server", "browser with mocked socket" and the catalogue
  fixture as in specs 040, 004 and 023. The reference catalogue `CAT` of spec 004
  holds FX-01 entries (with spec 005's credits).
- Keyboard only: the test uses `page.keyboard` and never `click`, `tap`, `hover`
  or `mouse`.
- `tab_to(page, test_id, selector="")` moves the focus to its target: the element
  that has that `data-testid` and, when `selector` is given, also matches it (for
  example `[data-force="1"]`); exactly one element must match. Before each press,
  if the target is `document.activeElement`, it stops. Otherwise, if the grid has
  the focus, it first presses `Escape`, which releases the grid's next `Tab` or
  `Shift+Tab`. Then it presses `Shift+Tab` when the target comes before the
  focused element in document order, and `Tab` otherwise, including when no
  element has the focus (`document.activeElement` is `body`). It fails when the
  target does not have the focus after 60 presses of `Tab` or `Shift+Tab` (the
  `Escape` presses do not count). So it never relies on `Tab` wrapping past the
  end of the document. (Note from the lead, 2026-10-14: it used to press only
  `Tab`, or only `Shift+Tab`, so a target before the focused element was reached
  only by going past the grid and wrapping past the end of the document, which
  Firefox under automation does not do. The walks keep their intent.)
- Sentinel (AC-1 to AC-3): a `<button type="button" data-testid="tab-sentinel">`
  with a short text, which the test appends as the last child of `body` with
  `page.evaluate` (setup, allowed in a keyboard-only test). It is placed so that
  the page's layout does not change, for example with `position: fixed` in a
  corner. The room page has nothing focusable after the grid, so the sentinel
  becomes the first focusable element after it, and `Escape` then `Tab` moves the
  focus to it in every engine. It is never a `tab_to` target, and no contrast or
  language scan runs while it is on the page. (Note from the lead, 2026-10-14:
  added.)
- `Tab` listener (AC-3): a `keydown` listener that the test adds on `window`
  (bubble phase) with `page.evaluate` once the grid is shown. For each `Tab`
  keydown, with or without `Shift`, it records `defaultPrevented`, which tells
  whether the page cancelled it. (Note from the lead, 2026-10-14: added.)
- Contrast scan, run in the page with `page.evaluate`: for each element that has
  a direct non-empty text node (after trimming), is visible (non-zero box,
  `visibility` `visible`, not inside a `visually-hidden` element, not a disabled
  control, not an `option`), the text colour is the computed `color` with its
  alpha multiplied by the `opacity` of the element and of each ancestor; the
  background is the first non-transparent `background-color` among the element
  and its ancestors (white when none), itself composited over white when it is
  translucent; the text colour is composited over the background; the WCAG
  contrast ratio of the two must be at least 4.5. The scan fails with the list of
  offending elements, their text and ratio.
- Contrast states (all at 1280 by 720, and the room states also at 360 by 740):
  - K1: `/` with `CAT` and `nock.progress` `{"1": "started", "2": "finished"}`;
  - K2: room page, mocked socket, FX-01 snapshot `seq` 10, `you` `p1` (host),
    players `p1`, `p2` (active, selection (2, 2) `down`), `p3` (idle), `p4`
    (disconnected); (1, 0) `T` locked, (1, 1) `X` wrong, (1, 2) `M` by `p2`;
    the player taps (1, 3); the mock then sends `player_joined` (`p5`, `Eve`),
    `check_result` by `p2` on the word `0,2,0` with empty lists, and
    `settings_changed` locking the room, so the feed holds three items, then
    `error` `nothing_to_undo` (the undo message shows);
  - K3: K2, then `letter_changed` by `p2` replacing `p1`'s letter at (1, 3),
    scanned within the 1 s flash (spec 016);
  - K4: K2, then the mock closes with code 1011 (connection banner, spec 017);
  - K5: room page with the nickname form showing `join.error.characters`;
  - K6: a FX-01 snapshot with every cell right and `solved` true
    (`grid-status` `solved`), and one full and wrong (`full_wrong`);
  - K7: `/r/ZZZZZZ` on the live server (`not_found`). (Note from the lead,
    2026-10-12: `/g/99` was dropped from K7. The server answers it with a JSON
    404 of spec 004 AC-4 and serves no page, so there is nothing to scan.)
- Language scan, run on K1 to K7: each visible direct text node (trimmed) and each
  `aria-label`, `title`, `placeholder` and `alt` value must either fully match a
  `fr.json` value read as a pattern (each `{name}` matches one or more
  characters, everything else literally), or be data of the test: a nickname of
  the snapshot or its initials, a clue text of FX-01, one letter `A` to `Z`, the
  room code, the share URL, or digits only.
- Touch context (AC-10): as spec 009's "Test harness": 360 by 740,
  `has_touch=True`, `is_mobile=True` (left out under Firefox). In Firefox and
  WebKit, the same init script as spec 009 makes `(pointer: coarse)` match. Keys
  are tapped with `locator.tap()`, and Tab presses use `page.keyboard`. (Note from
  the lead, 2026-10-13.)
- Crowded cells (AC-11): the mocked socket sends snapshots where several players
  have their selection on one cell. FX-02 snapshots are built from
  `tests/fixtures/fx02.json` (spec 006). Label boxes are read with
  `locator.bounding_box()`. Two boxes are disjoint when the width or the height of
  their intersection is at most 1 px. (Note from the lead, 2026-10-13.)
- Engines: Chromium and WebKit locally, Firefox too in CI. No check of this spec
  is Chromium-only. One check is skipped under Firefox: where the focus goes after
  `Escape` then `Tab` when nothing follows the grid (AC-3). (Note from the lead,
  2026-10-14: added after the first run on all three engines, Chromium 153,
  Firefox 155 and WebKit 26.6, as CI runs them.)
  One check is skipped under WebKit: whether the focus outline of the scrolling
  list in `activity-feed` is fully visible (AC-2), at all three of its window
  sizes (360 by 740, 568 by 320 and 1280 by 720), because WebKit does not make
  that list a Tab stop. (Note from the lead, 2026-10-14: added after a review
  finding. The test already skipped this check under WebKit, but only the Firefox
  skip was listed here.)

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-10.1.1) (browser with live server, keyboard only) Every action is reachable from the keyboard. With `CAT` served: on `/`, `tab_to` `force-filter` `data-force="1"` then `Enter` makes it `aria-pressed="true"`; `tab_to` the `catalogue-play` of item 1 then `Enter` opens the room page, which reaches `data-status="joined"` (Ana, host). There: `tab_to` `grid` then `Tab` selects `0,0,0` on (1, 0); `T` then `A` fill (1, 0) and (1, 1); `ArrowDown` moves the selection; `Backspace` erases; `Control+z` sends `undo`; `Escape` then `Tab` leaves the grid: the focus moves to the sentinel of "Test harness", which the test adds once the room page is `joined`. `tab_to` `check-word` and `Enter` sends a `check`; the same for `check-letter`, `check-grid` and `undo-button`; `tab_to` `copy-link` and `share-link` focus them; `tab_to` `lock-room` then `Enter` makes it `aria-pressed="true"` and again unlocks; `tab_to` `help-mode-select`, `ArrowDown`, then `tab_to` `settings-save` and `Enter` sends `change_settings`. A second page (Bob) opens the room link and, keyboard only, `tab_to` `nickname-input`, types `Bob`, presses `Enter` and reaches `joined`; then on Ana's page `tab_to` the `remove-player` of Bob and `Enter` removes him (Bob's page reaches `data-status="removed"`). (Note from the lead, 2026-10-14: the sentinel was added so that leaving the grid shows in every engine, and each `tab_to` follows its new definition in "Test harness". The walk's steps and intent are unchanged.)
- **AC-2** (AC-10.1.1) (browser with live server, keyboard only) The focus is always visible. During the walk of AC-1, each time `tab_to` reaches an element, that element's computed outline has a style other than `none` and `auto`, a width of at least 2 px and a colour of contrast at least 3:1 against white; this includes the `grid`. While a cell is selected, the selected cell has `outline-style` `solid` and `outline-width` of at least 2 px, and any other letter cell has `outline-style` `none`, with the focus on the grid and after `Escape` then `Tab` moved it to the sentinel (AC-1). (Note from the lead, 2026-10-14: "moved it away" became "moved it to the sentinel", which every engine shows. The pointer-focus check of the host panel is described under "Edge cases and errors".)
- **AC-3** (new, from spec 009 decision 5) (browser with mocked socket, keyboard only) A keyboard player can leave the grid. Given a FX-01 snapshot (`you` host, so the host panel shows) and the focus on the grid with (1, 0) selected, the following holds. (Note from the lead, 2026-10-14: split into the cases below, with the sentinel and the `Tab` listener of "Test harness", so that every check holds in Chromium, Firefox and WebKit. The old text required "`document.activeElement` is not the grid" even when nothing follows the grid, which Firefox under automation cannot show.)
  - Word navigation: `Tab` selects `0,0,1` and the focus stays on the grid (as spec 009).
  - Forward, with the sentinel: with the sentinel of "Test harness" added, `Escape` then `Tab` moves the focus to the first focusable element after the grid in document order, which is the sentinel while the page has none of its own after the grid. The selection is unchanged.
  - Backward: from there, `Shift+Tab` puts the focus back on the grid. Then `Escape` then `Shift+Tab` focuses the last focusable element before the grid in document order (the host panel's `settings-save` or a later control). The selection is unchanged.
  - Forward, without the sentinel (a separate run on the page as it is, where nothing focusable follows the grid): after `Escape` then `Tab` the selection is unchanged, and the focus leaves the page content wherever the browser can move it: `document.activeElement` is not the grid, or `document.hasFocus()` is false. Under Firefox the test skips only this focus check, because Firefox under automation has no toolbar to move the focus to and leaves it on the grid ("Nothing focusable after the grid" in "Edge cases and errors"). There, the next check is what shows that the page released the `Tab`.
  - Not cancelled: in every engine, for each `Tab` or `Shift+Tab` pressed right after `Escape` in the cases above, the `Tab` listener of "Test harness" records `defaultPrevented` false.
  - Release ended: `Escape`, then `T`, then `Tab` types `T` and then selects the next word.
  - Hint: the grid's `aria-describedby` is `grid-hint`, whose text is `fr.json["a11y.grid_hint"]`.
- **AC-4** (AC-10.1.2) (browser with mocked socket) On selecting a cell, a screen reader announces the clue, direction, word length and position. On a FX-01 snapshot, after tapping (2, 2) twice (down word MIME selected), `grid-announcement` has `role="status"`, `aria-live="polite"`, the class `visually-hidden`, and the exact text `Artiste muet, vertical, 4 lettres, lettre 2`; after `ArrowDown` it reads `Artiste muet, vertical, 4 lettres, lettre 3`; after `ArrowUp` it reads `Artiste muet, vertical, 4 lettres, lettre 2` again; after tapping (2, 2) once more (spec 007: the selected cell switches to its across word VIDE) it reads `Sans contenu, horizontal, 4 lettres, lettre 2`; after tapping (1, 0) it reads `Passoire fine, horizontal, 5 lettres, lettre 1`.
- **AC-5** (new, from spec 006's review) (browser with mocked socket) The grid exposes grid, row and gridcell roles. On a FX-01 snapshot: `page.get_by_role("grid")` has one element; it has 5 `grid-row` children with `role="row"` and `data-row` 0 to 4; each holds 5 elements with `role="gridcell"`, `data-row` equal to its row and `data-column` 0 to 4 in order; `page.get_by_role("gridcell")` counts 25; `cell-2-2` is the `cell` at (2, 2); with nothing selected the grid has no `aria-activedescendant` and every letter cell has `aria-selected="false"`; after tapping (2, 2) the grid's `aria-activedescendant` is `cell-2-2`, that cell has `aria-selected="true"` and the 17 other letter cells `false`; spec 006's layout criteria (cell squares, positions) still pass.
- **AC-6** (AC-10.1.3) (browser with mocked socket) Colour is never the only signal: each player's cursor also carries their initials. Given a FX-01 snapshot with `p1` (`you`), `p2` `Jean-Luc` selecting (2, 2) `down`, `p3` `Ana` selecting (2, 2) `across` and `p4` `zoé` selecting (1, 0): the cell (2, 2) holds two `remote-selection` elements whose `remote-initials` read `JL` and `AN`, each inside the cell's bounding box (1 px tolerance) with computed `visibility` `visible`; (1, 0) holds one reading `ZO`; after `selection_moved` of `p2` to (3, 1), (3, 1) holds `JL` and (2, 2) only `AN`.
- **AC-7** (AC-10.1.3) (browser with mocked socket) Locked letters and roster states differ by more than colour. In state K2, (1, 0) (locked) has a computed `font-weight` of 700 or more and (1, 2) (not locked) below 700. In the same state, at 1280 by 720 and at 360 by 740, the roster items behave as follows. The `roster-player` items of `p2` (active), `p3` (idle) and `p4` (disconnected), each of their descendants and each of their ancestors have a computed `opacity` of `1`. The `roster-nickname` of `p3` has `font-style` `italic` and a `text-decoration-line` without `line-through`, and its `roster-state` reads `inactif`. The `roster-nickname` of `p4` has `font-style` `italic` and a `text-decoration-line` containing `line-through`, and its `roster-state` reads `déconnecté`. The `roster-nickname` of `p2` has `font-style` `normal` and no `line-through`, and its `roster-state` reads `actif`. (Note from the lead, 2026-10-13: the roster part was added. It settles the "Translucent styles" edge case.)
- **AC-8** (AC-10.1.3) (browser with live server and mocked socket) Text contrast is at least 4.5:1. The contrast scan of the test harness finds no offending element in each of the states K1 to K7, at both window sizes.
- **AC-9** (AC-10.1.4) (browser with live server and mocked socket; static) The interface is in French by default, with every string in a translation file. In each state K1 to K7, `document.documentElement.lang` is `fr` and the language scan of the test harness finds no text outside `fr.json` and the test's data; the scan's checker flags the samples `Loading…`, `Salon` (alone, no template is exactly `Salon`) and `Check word`, and accepts `Salon ABC123`, `Grille n° 2` and `Ana a rejoint le salon`. The seven keys of "New `fr.json` keys" exist with those values. (Note from the lead, 2026-10-13: five keys became seven, with `grid.remote_overflow` and `a11y.remote_overflow`.)
- **AC-10** (new, from the spec 009 and 035 contradiction) (browser with mocked socket, touch context, in Chromium, Firefox and WebKit) The in-app keyboard keys stay out of the Tab order but stay in the accessibility tree. Given a FX-01 snapshot in the touch context:
  - Markup: each of the 26 `key` elements and the `key-delete` is a `BUTTON` element with `type="button"` and the attribute `tabindex="-1"` (its `tabIndex` property is `-1`). For each letter `L` from `A` to `Z`, `page.get_by_role("button", name=L, exact=True)` inside `keyboard` resolves to exactly the `key` with `data-key=L`. `page.get_by_role("button", name="Effacer", exact=True)` resolves to exactly `key-delete`. No key and no ancestor of a key has `aria-hidden="true"`, the `inert` attribute, or `role` `presentation` or `none`.
  - Focus after a tap: after tapping (1, 0), then the key `T`, then `key-delete`, `document.activeElement` is the `grid` after each tap.
  - Tab order: with the focus on the grid, `Escape` then `Tab`, followed by up to 60 more `Tab` presses (stopping early if the focus comes back to the grid or reaches `document.body`), never puts the focus on a `key` or on `key-delete`. The same holds with `Escape` then `Shift+Tab` and up to 60 more `Shift+Tab` presses.
  - Focus forced onto a key: after any key press on the page, calling `focus()` on the key `A` from `page.evaluate` gives it a computed outline with a style other than `none` and `auto`, a width of at least 2 px and a colour of contrast at least 3:1 against white (AC-2).
- **AC-11** (AC-10.1.3, "+N" rule approved by the human, 2026-10-13) (browser with mocked socket) When too many cursors share a cell, the cell shows as many initials as fit, then one "+k" label, and no two labels overlap. The rules are those of "Initials on a crowded cell". In every case below, the layout rules hold for each label (inside the cell with 1 px tolerance, pairwise disjoint, corner within 3 px, `font-size` at least 7 px, `visibility` `visible`). The test first reads the side `c` of the cell. If `c` is not in the expected tier, the test fails and reports the measured size, which means the layout has changed and the example must be revisited.
  - FX-01, large cells: window 1280 by 720, desktop context. In the snapshot, `p1` is `you`, and `p2` `Jean-Luc`, `p3` `Ana`, `p4` `zoé`, `p5` `Wanda Moreau` and `p6` `Max` all select (2, 2), joined in that order. Expected tier: `c` is at least 44. (2, 2) shows `JL` at `top-left`, `AN` at `bottom-right` and `ZO` at `top-right` (3 `remote-initials`). It shows one `remote-overflow` at `bottom-left` with the text `+2` and `data-count="2"`. Its `remote-overflow-label` reads `2 autres joueurs`. The `remote-selection` elements of `p5` and `p6` hold no `remote-initials`. After `selection_moved` of `p6` to (3, 1), (2, 2) shows four `remote-initials`: `JL` `top-left`, `AN` `bottom-right`, `ZO` `top-right` and `WM` `bottom-left`. It holds no `remote-overflow` and no `remote-overflow-label`. (3, 1) shows `MA` at `top-left`.
  - FX-02, small cells: window 360 by 740, desktop context, FX-02 snapshot. The cell used is the first letter cell in row-major order, found from `tests/fixtures/fx02.json`. `p2` `Jean-Luc`, `p3` `Ana` and `p4` `Wanda Moreau` select that cell, joined in that order. Expected tier: `c` is at least 20 and below 44 (about 25 px). The cell shows `JL` at `top-left` and one `remote-overflow` reading `+2` at `bottom-right`, and its `remote-overflow-label` reads `2 autres joueurs`. After `selection_moved` of `p2` to another letter cell, the first cell shows `AN` at `top-left` and `WM` at `bottom-right`, with no `remote-overflow`. With `p2` to `p8` (7 cursors) on the first cell, it shows one `remote-initials` (`p2`'s) at `top-left` and `+6` at `bottom-right`.
  - FX-02, tiny cells: window 568 by 320, desktop context, same cell, with `p2` and `p3` on it. Expected tier: `c` is below 20. The cell holds no `remote-initials` and one `remote-overflow` with `data-corner="top-left"`, the text `+2` and `data-count="2"`. Only the slot and count rules are checked here, not the layout rules.
  - Language and contrast: in the FX-01 state with five cursors, the language scan of AC-9 accepts `+2` and `2 autres joueurs`, and the contrast scan of AC-8 finds no offending element.

## Edge cases and errors

Known issues carried from earlier specs, recorded by the lead on 2026-10-11 and
settled here:

- Keyboard trap (WCAG 2.1.2): spec 009 prevents `Tab` and `Shift+Tab` whenever the
  grid has the focus. Settled by "Leaving the grid from the keyboard" (AC-3): the
  way out is `Escape` then `Tab`, announced by the grid's description.
- Missing `row` and `gridcell` children under `role="grid"` (accessibility
  checkers' aria-required-children): settled by "Grid roles" (AC-5).

Other cases:

- Announcement with a pending letter (AC-4): the text does not include letters, so
  it does not change when a letter is typed, only when the selection moves; typing
  a letter moves the selection to the next cell, which updates `position`.
- Same selection chosen again (AC-4): the text does not change, so a polite live
  region stays silent.
- Remote selection of a disconnected player (AC-6): not drawn (spec 013), so no
  initials. It is not counted in `n` (AC-11).
- Crowded cell, labels re-flow (AC-11): labels follow the current cursors. When a
  cursor leaves a cell or a player disconnects, the remaining cursors take the slots
  again in roster order, and the overflow label disappears once `n <= S`. (Note from
  the lead, 2026-10-13.)
- Crowded cell and zoom (AC-11): `S` follows the current cell side, so zooming in
  (spec 006) can turn `+k` into initials. (Note from the lead, 2026-10-13.)
- Crowded cell, my own selection on it (AC-11): `you` has no cursor (spec 013), so
  it does not count. The selected cell's outline (AC-2) does not move the labels.
  (Note from the lead, 2026-10-13.)
- Two players with the same initials (AC-6): both are shown; colours and the roster
  tell them apart. Initials of a nickname of one character (not possible: spec 012
  needs 2) would be that character.
- `Escape` with nothing selected (AC-3): the release works the same. With the
  sentinel added, `Tab` then moves the focus to it, and nothing becomes selected.
  (Note from the lead, 2026-10-14: "leaves the grid" is now measured with the
  sentinel, as in AC-3, so that it holds in every engine.)
- `Escape` on other controls (AC-3): left to the browser.
- Nothing focusable after the grid (AC-1 to AC-3): on the room page the grid is
  the last focusable element in document order (the lead checked it with a
  script). After `Escape` then `Tab`, the page leaves the `Tab` to the browser in
  every engine (`defaultPrevented` false), and the browser decides where the focus
  goes. Under automation, Chromium and WebKit move it out of the document
  (`document.hasFocus()` false, `document.activeElement` is `body`). A real Firefox
  moves it to its toolbar, but Firefox under automation (Playwright) has none, so
  the focus stays on the grid, `document.hasFocus()` stays true and no `blur`
  fires. The released key press still ends the release, so a second `Tab` there
  selects the next word. That is why AC-1 to AC-3 add the sentinel, and why
  `tab_to` presses `Escape` before each press while the grid has the focus. For
  the same reason, AC-10's Tab order check stops at once under Firefox. It still
  does its job: the in-app keyboard comes after the grid in document order, so a
  key that is a Tab stop would take the focus there. (Note from the lead,
  2026-10-14: added from the first run under Firefox. A `keydown` listener on
  `window` saw `defaultPrevented` false in all three engines, so a real Firefox
  user reaches the toolbar.)
- In-app keyboard (spec 009, touch screens) (AC-10): the keys stay out of the Tab
  order (`tabindex="-1"`). Each key duplicates a physical key, so WCAG 2.1.1 is met
  by the physical keyboard, and about 30 more Tab stops would hurt keyboard users
  (2.4.3). The keys are still real buttons in the accessibility tree, with an
  accessible name (the letter, or `Effacer`) and no `aria-hidden`, so screen reader
  users on a touch screen reach them by swipe navigation. A tap never moves the
  focus off the grid. If a key gets the focus anyway (screen reader focus), it shows
  the visible focus of AC-2. (Note from the lead, 2026-10-13: rewritten. The old
  text said the keys are focusable, which contradicted spec 009.)
- Flash colours (AC-8, state K3): a letter on a flashing cell must still reach
  4.5:1; the implementer may change how the flash is drawn (spec 016 only fixes
  its colour and duration).
- Translucent styles (AC-7, AC-8): the idle and disconnected roster rows use no
  opacity. The nickname is italic for idle, and italic with line-through for
  disconnected, and the state text (`inactif`, `déconnecté`) is written in the
  row. The text keeps 4.5:1, and the state does not rely on colour. (Note from the
  lead, 2026-10-13: settled. It replaces "dimmed rows with `opacity` 0.7 and 0.45
  must still reach 4.5:1, or use another non-colour sign".)
- Hidden text (AC-8, AC-9): text inside `visually-hidden` elements is in the
  language scan but not in the contrast scan.
- Disabled buttons (AC-8): exempt from contrast (WCAG), still in the language scan.
- Pointer focus in the host panel (AC-2, spec 014 AC-7): a keyboard focus on a
  host-panel control hides `host-panel-more`, so that the fade never covers the
  outline of AC-2 (spec 014). On a pointer focus (a click or a tap), the page's own
  code never scrolls the panel, and the fade stays visible while panel content is
  still hidden past the panel's right edge
  (`scrollWidth - clientWidth - scrollLeft > 1`). A scroll that the browser makes
  by itself to show a focused form control is allowed: WebKit, for example,
  scrolls a partly visible `<select>` into view when it is clicked or tapped. So
  the test does not compare the panel's `scrollLeft` before and after the press;
  it spies on the page's scroll calls. This check uses a pointer, unlike the rest
  of AC-2. Setup: state K2 in a 320 by 568 window, with a mouse click in a desktop
  context and a tap in a touch context (`has_touch=True`, and `is_mobile=True`
  except under Firefox), on each of `lock-room`, `help-mode-select`,
  `reveal-letters-input` and `reveal-words-input`. The test first sets the
  panel's `scrollLeft` so that the control is partly hidden past the right edge,
  or fully shown. Then it wraps `scrollIntoView`, `scrollIntoViewIfNeeded` (where
  the engine has it), `scroll`, `scrollTo`, `scrollBy` and the `scrollLeft` setter
  of `Element.prototype`, so that each call made on `host-panel` or on an element
  inside it is recorded. It presses the centre of the control's visible part at
  raw coordinates (`page.mouse.click` or `page.touchscreen.tap`), because
  `locator.click()` would scroll the control into view first. 300 ms after the
  press, no call has been recorded, and `host-panel-more` is visible (computed
  `visibility` `visible`, `display` not `none`) if panel content is still hidden
  past the right edge. (Note from the lead, 2026-10-14: added. The check of
  2026-10-13 required an unchanged `scrollLeft` and failed in WebKit for
  `help-mode-select` because of WebKit's own scroll, while the fade stayed
  visible. The page's code scrolls only on a keyboard focus.)

## Out of scope

- Nothing stated in the backlog (epic E10).
- Performance: spec 036.
- Integrity: spec 037.
- Privacy and operations: spec 038.
- Tests with real screen readers (NVDA, VoiceOver, TalkBack); the announcement is
  tested through its live region.
- A full audit with an accessibility engine such as axe-core (adding it is a
  dependency the owner decides).
- Other languages and a language switch; right-to-left layouts.
- Announcing other players' moves or letters, the feed, or checks in the live
  region (the feed list is readable as is).
- Reduced motion settings and zoom beyond spec 006.
- Keyboard shortcuts for checks, reveals or chat.
- Swipe navigation with a real screen reader on a phone (AC-10 checks the
  accessibility tree, not TalkBack or VoiceOver). A way to list every player on a
  crowded cell (the roster gives the names; AC-11 shows `+k` only). (Note from the
  lead, 2026-10-13.)
- Moving the focus somewhere when nothing focusable follows the grid: after the
  released `Tab`, the browser decides where the focus goes (AC-3). (Note from the
  lead, 2026-10-14.)
- Cancelling or undoing a scroll that the browser makes by itself when a form
  control gets the focus, such as WebKit scrolling a clicked `<select>` into view
  (AC-2). (Note from the lead, 2026-10-14.)

## Work packages

None.

## Decisions

Decided by the lead on 2026-10-11, under the owner's delegation of technical
decisions. Each one is already part of the spec above.

1. Leaving the grid. Options: `Escape` moves the focus out at once; `Escape` then
   `Tab`; or `Tab` never captured. Pick: `Escape` releases the next `Tab` or
   `Shift+Tab`, so the player leaves in either direction, and spec 009's word
   navigation stays. The method is announced in the grid's description (WCAG 2.1.2
   asks that a non-standard exit be advised).
2. Grid roles. Options: a full ARIA grid (rows and gridcells), or `role="application"`
   with no structure. Pick: a full grid with `aria-activedescendant`, so screen
   readers can explore cells; rows use `display: contents` (or equivalent) to keep
   spec 006's CSS grid.
3. The announcement is a polite, atomic live region (testable in every engine),
   not only `aria-activedescendant` (which screen readers announce
   inconsistently). Wording: `Artiste muet, vertical, 4 lettres, lettre 2`, as the
   backlog example; `horizontal` for across.
4. Visible focus: an outline of at least 2 px, not the browser's `auto` ring, so it
   is the same in every engine; the selected cell carries its own outline, which
   is the non-colour sign of the selection.
5. Initials: first character of the first two parts of the nickname, or its first
   two characters; drawn inside the outlined cell.
6. Locked letters are bold (the non-colour sign of spec 016's grey background).
   Tints (other players' words) and flashes stay colour-only: the same
   information is also given by text (the initials, the letter that changed, the
   clue bar).
7. Contrast threshold: 4.5:1 for all text, large text included (simpler than
   WCAG's 3:1 for large text, and the backlog value). Owner's answer: keep the
   backlog defaults.
8. Language: spec 040's static checks stay; this spec adds a scan of the rendered
   pages, so strings built in TypeScript are covered too.

Added on 2026-10-13. The human allowed agents to refine approved and done specs,
and these are the lead's decisions:

9. In-app keyboard keys (AC-10). Options: make the keys Tab stops; hide them from
   assistive technology; or keep them out of the Tab order but in the accessibility
   tree. Pick: the last. Physical keys already cover WCAG 2.1.1, about 30 Tab stops
   would hurt the focus order (2.4.3), and screen reader users on touch still reach
   the keys by swipe. A key that gets the focus anyway shows the visible focus.
10. Roster states (AC-7). Options: dimmed rows tuned to reach 4.5:1, or no opacity
    with a typographic sign. Pick: no opacity. The nickname is italic for idle, and
    italic with line-through for disconnected, and the state text stays in the row.
11. Crowded cells (AC-11). The human approved a "+N" rule. Pick: 4 corner slots
    from a 44 px cell, 2 diagonal slots from 20 px, and 1 slot below that. Labels go
    to cursors in roster order, and the last slot holds `+k` when the cursors
    outnumber the slots. The thresholds come from the label font
    (`max(7px, 0.2 × cell)`) and the widest two-capital initials. The `+k` is
    hidden from assistive technology and replaced by `k autres joueurs` in a
    visually hidden element of the cell.

Added on 2026-10-14, after the first run of the full suite on Chromium 153,
Firefox 155 and WebKit 26.6, as CI runs it. The lead probed each failure. The
human allowed agents to refine approved and done specs, and these are the lead's
decisions:

12. Leaving the grid, in every engine (AC-1 to AC-3). Nothing focusable follows the
    grid on the room page. After `Escape` then `Tab`, Chromium and WebKit move the
    focus out of the document, and Firefox under automation, which has no
    toolbar, leaves it on the grid. In none of them is the `Tab` cancelled.
    Options: keep "the focus is not on the grid" and run it in Chromium and WebKit
    only; add a focusable element after the grid to the page; or check what the
    page controls in every engine. Pick: the last. In every engine the `Tab` after
    `Escape` must not be cancelled, and a test-only sentinel at the end of `body`
    gives the forward exit a place to go. The check that the focus leaves the page
    as it is stays, skipped under Firefox. `tab_to` picks `Tab` or `Shift+Tab`
    from document order and presses `Escape` before each press while the grid has
    the focus, so no step relies on `Tab` wrapping past the end of the document.
    The page's behaviour does not change.
13. Pointer focus and the browser's own scroll (AC-2, spec 014 AC-7). The check
    added on 2026-10-13 required the host panel's `scrollLeft` to stay the same
    after a click or tap. WebKit scrolls a partly visible `<select>` into view by
    itself when it is clicked or tapped, so the check failed for
    `help-mode-select`, although the page's code scrolls only on a keyboard focus
    and the fade stayed visible. Options: keep the `scrollLeft` check and make the
    page undo the browser's scroll, which fights native behaviour and could
    misplace the select's menu; or forbid only the page's own scrolling. Pick: the
    latter. A spy on the page's scroll calls still catches the bug the check
    guards against (the page's focus scroll moving a partly visible control away
    from under the pointer), and the fade rule does not change.

## Open questions

None.
