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
- Each `remote-selection` element (spec 013) holds one
  `data-testid="remote-initials"` element whose text is the initials of that
  player, drawn inside the cell's box.
- Struck-through wrong letters are spec 023's (`line-through`).

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

### Test harness

- "Browser with live server", "browser with mocked socket" and the catalogue
  fixture as in specs 040, 004 and 023. The reference catalogue `CAT` of spec 004
  holds FX-01 entries (with spec 005's credits).
- Keyboard only: the test uses `page.keyboard` and never `click`, `tap`, `hover`
  or `mouse`. `tab_to(page, test_id, shift=False)` presses `Tab` (or `Shift+Tab`)
  up to 60 times until `document.activeElement` has that `data-testid`, and fails
  otherwise.
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
  - K7: `/r/ZZZZZZ` on the live server (`not_found`) and `/g/99` (not found page).
- Language scan, run on K1 to K7: each visible direct text node (trimmed) and each
  `aria-label`, `title`, `placeholder` and `alt` value must either fully match a
  `fr.json` value read as a pattern (each `{name}` matches one or more
  characters, everything else literally), or be data of the test: a nickname of
  the snapshot or its initials, a clue text of FX-01, one letter `A` to `Z`, the
  room code, the share URL, or digits only.
- Engines: Chromium and WebKit locally, Firefox too in CI. No check of this spec
  is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-10.1.1) (browser with live server, keyboard only) Every action is reachable from the keyboard. With `CAT` served: on `/`, `tab_to` `force-filter` `data-force="1"` then `Enter` makes it `aria-pressed="true"`; `tab_to` the `catalogue-play` of item 1 then `Enter` opens the room page, which reaches `data-status="joined"` (Ana, host). There: `tab_to` `grid` then `Tab` selects `0,0,0` on (1, 0); `T` then `A` fill (1, 0) and (1, 1); `ArrowDown` moves the selection; `Backspace` erases; `Control+z` sends `undo`; `Escape` then `Tab` leaves the grid. `tab_to` `check-word` and `Enter` sends a `check`; the same for `check-letter`, `check-grid` and `undo-button`; `tab_to` `copy-link` and `share-link` focus them; `tab_to` `lock-room` then `Enter` makes it `aria-pressed="true"` and again unlocks; `tab_to` `help-mode-select`, `ArrowDown`, then `tab_to` `settings-save` and `Enter` sends `change_settings`. A second page (Bob) opens the room link and, keyboard only, `tab_to` `nickname-input`, types `Bob`, presses `Enter` and reaches `joined`; then on Ana's page `tab_to` the `remove-player` of Bob and `Enter` removes him (Bob's page reaches `data-status="removed"`).
- **AC-2** (AC-10.1.1) (browser with live server, keyboard only) The focus is always visible. During the walk of AC-1, each time `tab_to` reaches an element, that element's computed outline has a style other than `none` and `auto`, a width of at least 2 px and a colour of contrast at least 3:1 against white; this includes the `grid`. While a cell is selected, the selected cell has `outline-style` `solid` and `outline-width` of at least 2 px, and any other letter cell has `outline-style` `none`, with the focus on the grid and after `Escape` then `Tab` moved it away.
- **AC-3** (new, from spec 009 decision 5) (browser with mocked socket, keyboard only) A keyboard player can leave the grid. Given a FX-01 snapshot (`you` host, so the host panel shows) and the focus on the grid with (1, 0) selected: `Tab` selects `0,0,1` and the focus stays on the grid (as spec 009); `Escape` then `Tab` moves the focus to the first focusable element after the grid in document order, or out of the page content when there is none (`document.activeElement` is not the grid in either case), and the selection is unchanged; back on the grid with `Shift+Tab`, `Escape` then `Shift+Tab` focuses the last focusable element before the grid in document order (the host panel's `settings-save` or a later control). `Escape`, then `T`, then `Tab` types `T` and then selects the next word (the release ended). The grid's `aria-describedby` is `grid-hint`, whose text is `fr.json["a11y.grid_hint"]`.
- **AC-4** (AC-10.1.2) (browser with mocked socket) On selecting a cell, a screen reader announces the clue, direction, word length and position. On a FX-01 snapshot, after tapping (2, 2) twice (down word MIME selected), `grid-announcement` has `role="status"`, `aria-live="polite"`, the class `visually-hidden`, and the exact text `Artiste muet, vertical, 4 lettres, lettre 2`; after `ArrowDown` it reads `Artiste muet, vertical, 4 lettres, lettre 3`; after `ArrowUp` it reads `Artiste muet, vertical, 4 lettres, lettre 2` again; after tapping (2, 2) once more (spec 007: the selected cell switches to its across word VIDE) it reads `Sans contenu, horizontal, 4 lettres, lettre 2`; after tapping (1, 0) it reads `Passoire fine, horizontal, 5 lettres, lettre 1`.
- **AC-5** (new, from spec 006's review) (browser with mocked socket) The grid exposes grid, row and gridcell roles. On a FX-01 snapshot: `page.get_by_role("grid")` has one element; it has 5 `grid-row` children with `role="row"` and `data-row` 0 to 4; each holds 5 elements with `role="gridcell"`, `data-row` equal to its row and `data-column` 0 to 4 in order; `page.get_by_role("gridcell")` counts 25; `cell-2-2` is the `cell` at (2, 2); with nothing selected the grid has no `aria-activedescendant` and every letter cell has `aria-selected="false"`; after tapping (2, 2) the grid's `aria-activedescendant` is `cell-2-2`, that cell has `aria-selected="true"` and the 17 other letter cells `false`; spec 006's layout criteria (cell squares, positions) still pass.
- **AC-6** (AC-10.1.3) (browser with mocked socket) Colour is never the only signal: each player's cursor also carries their initials. Given a FX-01 snapshot with `p1` (`you`), `p2` `Jean-Luc` selecting (2, 2) `down`, `p3` `Ana` selecting (2, 2) `across` and `p4` `zoé` selecting (1, 0): the cell (2, 2) holds two `remote-selection` elements whose `remote-initials` read `JL` and `AN`, each inside the cell's bounding box (1 px tolerance) with computed `visibility` `visible`; (1, 0) holds one reading `ZO`; after `selection_moved` of `p2` to (3, 1), (3, 1) holds `JL` and (2, 2) only `AN`.
- **AC-7** (AC-10.1.3) (browser with mocked socket) Locked letters differ by more than colour. In state K2, (1, 0) (locked) has a computed `font-weight` of 700 or more and (1, 2) (not locked) below 700.
- **AC-8** (AC-10.1.3) (browser with live server and mocked socket) Text contrast is at least 4.5:1. The contrast scan of the test harness finds no offending element in each of the states K1 to K7, at both window sizes.
- **AC-9** (AC-10.1.4) (browser with live server and mocked socket; static) The interface is in French by default, with every string in a translation file. In each state K1 to K7, `document.documentElement.lang` is `fr` and the language scan of the test harness finds no text outside `fr.json` and the test's data; the scan's checker flags the samples `Loading…`, `Salon` (alone, no template is exactly `Salon`) and `Check word`, and accepts `Salon ABC123`, `Grille n° 2` and `Ana a rejoint le salon`. The five keys of "New `fr.json` keys" exist with those values.

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
  initials.
- Two players with the same initials (AC-6): both are shown; colours and the roster
  tell them apart. Initials of a nickname of one character (not possible: spec 012
  needs 2) would be that character.
- `Escape` with nothing selected (AC-3): the release works the same; `Tab` then
  leaves the grid.
- `Escape` on other controls (AC-3): left to the browser.
- In-app keyboard (spec 009, touch screens): its keys are buttons, so they are
  focusable and get the visible focus of AC-2; they keep the grid focused after a
  tap.
- Flash colours (AC-8, state K3): a letter on a flashing cell must still reach
  4.5:1; the implementer may change how the flash is drawn (spec 016 only fixes
  its colour and duration).
- Translucent styles (AC-8): spec 013's dimmed roster rows (`opacity` 0.7 and 0.45)
  must still reach 4.5:1 once composited, or use another non-colour sign.
- Hidden text (AC-8, AC-9): text inside `visually-hidden` elements is in the
  language scan but not in the contrast scan.
- Disabled buttons (AC-8): exempt from contrast (WCAG), still in the language scan.

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

## Open questions

None.
