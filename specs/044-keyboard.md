---
id: "044"
title: Keyboard
status: approved
---

# 044 - Keyboard

Epic E10 Quality bar · Release: MVP · No backlog story: this is build step 4 of
`specs/_design.md` (section 14). It applies `_design.md` section 8 (the phone top
bar's « Clavier », the computer top bar's « Clavier (touch screens only) », the
in-app keyboard with its ✎, ⇄ and ⌫ keys, "Which layout" for a phone held
sideways), section 9 only where it says that the in-app keyboard goes away once the
grid is solved, and the parts of sections 2 (`--nock-key`, `--nock-keyboard-bg`,
`--nock-key-shadow`, `--nock-pen-fill`, `--nock-pencil`), 4 (key letter) and 5
(icons `clavier`, `crayon`, `swap`, `effacer`) that the keyboard uses. It builds on
spec 041 (tokens, fonts, `ICONS` of `web/src/lib/icons.ts`), spec 042 (grid cells)
and spec 043 (top bar, sheet and column layouts, clue bar, completion status) and
redefines none of them; where it changes one of their rules, "Refined specs" says
so. The FX-01 reference grid is in `specs/_reference.md`; the stack in
`specs/_architecture.md`.

(Note from the lead, 2026-10-22: refined by spec 046, the design's catalogue and
entry pages: while the room opens, before its first snapshot, `room-topbar` shows
with its buttons and the `inert` attribute, so `keyboard-toggle` is on the page then
too (on a touch screen, with `aria-pressed="false"`, since the keyboard does not
show before a snapshot); "on the page only on a touch screen once the page has a
snapshot" reads "on the page only on a touch screen, from the opening on". No
criterion of this spec changes.)

## Goal

A player on a touch screen types with the in-app keyboard of the design: AZERTY
letters, a ✎ key that turns pencil mode on and off, a ⇄ key that switches between
the across and the down word, and ⌫. A « Clavier » button in the top bar hides the
keyboard and gives its room to the grid, a choice the browser remembers; once the
grid is solved the keyboard goes away by itself. The rule of the human holds: the
simplest design that removes edge cases. One definition of "the keyboard shows"
drives the layout, the place of the completion status and the top bar, so the
cases that spec 043 left open for this step close.

## Public interface

No new Python name, no new protocol message, no new HTTP route. Client only
(`web/`: chiefly `web/src/lib/InAppKeyboard.svelte`, the top bar and
`web/src/lib/RoomPage.svelte`). Every colour is a token of spec 041 used for its
job in `_design.md` section 2, every icon comes from `ICONS`, every string from
`web/src/i18n/fr.json`.

### Terms

- Touch screen: `window.matchMedia("(pointer: coarse)").matches`, read once when
  the room page loads (spec 009 decision 6).
- Low window: `window.innerHeight <= 500` (the height part of spec 024's small
  window, as in specs 026 and 043).
- The keyboard choice: `localStorage["nock.keyboard_hidden"]`. The value `"true"`
  means that the player hid the keyboard; any other value, or no key, means shown.
- The in-app keyboard shows when all of these hold: the page has a snapshot, it is
  on a touch screen, the keyboard choice is not `"true"`, and the grid is not solved
  (`room-page` has `data-solved="false"`, spec 026). Otherwise it is hidden, and no
  `keyboard` element is on the page. This replaces spec 043's term "The in-app
  keyboard is shown on a touch screen and nowhere else": every rule of spec 043
  that reads "the in-app keyboard is hidden" or "on a touch screen" for the
  keyboard reads this definition (see "Refined specs").

### Which layout (refines spec 043's "Which layout")

Spec 043's rule is unchanged and now reads the definition above: `room-page` has
`data-layout="column"` when the window is landscape and either at least 900 px wide
and more than 500 px high, or a low window on which the in-app keyboard does not
show; `"sheet"` otherwise. So a phone held sideways is in the sheet layout while its
keyboard shows, and in the column layout once the player hides it or the grid is
solved. A change of layout follows spec 043's rules (within 300 ms; popovers and
the reaction picker close; the Salon takes the state of the new layout).

### « Clavier » in the top bar (`_design.md` section 8)

`data-testid="keyboard-toggle"`: a top-bar button of spec 043 (`<button
type="button">`, transparent background, no border, navy icon and label, the
accessible name its label), on the page only on a touch screen once the page has a
snapshot:

- Icon `clavier`, label `t("keyboard.label")` (« Clavier », spec 009's key).
- `aria-pressed` is `"true"` while the in-app keyboard shows, `"false"` otherwise.
  Pressed look: `--nock-word` background (spec 043's pressed look).
- Place: right after `chat-toggle`, right before `menu-button`, in both forms of the
  top bar (spec 043's "Terms"). In the phone top bar it is the fourth slot, with
  that bar's button size, icon and label; in the computer top bar it has that bar's
  button look. (Note from the lead, 2026-10-22: this read "In the sheet layout ...
  in the column layout"; the phone top bar is also the column layout's on a window
  at most 500 px high, Decision 8.)
- A click while the keyboard shows writes `"true"` to the keyboard choice; a click
  while it is hidden removes the key. It sends nothing. The keyboard, the layout
  and the grid's fit follow within 300 ms (the grid refits as on a resize, spec
  006). After an activation from the keyboard (`Enter` or `Space`), the focus is on
  `keyboard-toggle`, also when the layout changed.
- Once the grid is solved it is `disabled`, with `aria-pressed="false"` and spec
  043's disabled top-bar look (icon and label in `--nock-muted`, `cursor:
  not-allowed`); the keyboard choice is not changed.
- When `localStorage` throws, the choice holds for the page's life only.

### The pencil toggle (refines spec 043's top bar and spec 020's controls)

Pencil mode is one state of the page (spec 020: off at each load, never sent, never
stored). Two controls show and flip it, each with `aria-pressed` equal to it:

- `key-pencil`, the ✎ key of the in-app keyboard (below), whenever the keyboard
  shows;
- `pencil-toggle` (« Crayon », spec 043), in the computer top bar always (after
  `undo-button`), and in the phone top bar only when the page is not on a touch
  screen (its fourth slot, as spec 043 has it). On a touch screen the phone top
  bar's fourth slot is `keyboard-toggle` and there is no `pencil-toggle`. (Note from
  the lead, 2026-10-22: this read "column layout's top bar" and "sheet layout's top
  bar"; the top bar's form, not the layout, decides, Decision 8.)

So, in the phone top bar (the sheet layout, and the column layout on a window at
most 500 px high):

| Page | Top bar after `timer` |
| --- | --- |
| Not a touch screen | `undo-button`, `aide-button`, `chat-toggle`, `pencil-toggle`, `menu-button` (spec 043) |
| Touch screen | `undo-button`, `aide-button`, `chat-toggle`, `keyboard-toggle`, `menu-button` |

and in the computer top bar (the column layout on a window more than 500 px high):
`topbar-brand`, `timer`, then `undo-button`, `pencil-toggle`, `aide-button`,
`chat-toggle`, `keyboard-toggle` (touch screens only), `menu-button`.

### In-app keyboard (refines spec 009's "In-app keyboard"; `_design.md` section 8)

`data-testid="keyboard"` keeps spec 009's `role="group"` and `aria-label`
`t("keyboard.label")`, and its place: in the sheet layout under `clue-bar` (and
under `grid-status` when the band is under the bar), full window width, its bottom
on the window's bottom; in the column layout spec 043's place (full width of the
play area at its bottom, margins −12 px, 10 px under the block above it).

Look:

- `keyboard`: background `--nock-keyboard-bg`, padding 6 px 3 px 8 px; three
  `data-testid="keyboard-row"` rows, 6 px apart; in each row the keys are 4 px
  apart and the row is centred.
- Rows: row 1 `A Z E R T Y U I O P`; row 2 `Q S D F G H J K L M`; row 3
  `key-pencil`, `W X C V B N`, `key-swap`, `key-delete`.
- Every key: a `<button type="button">` with `tabindex="-1"`, 44 px high (28 px on
  a low window, Decision 3), radius 5 px, background `--nock-key`, no border,
  `box-shadow: 0 1px 0 var(--nock-key-shadow)`, padding 0, its content centred.
- Letter keys (`data-testid="key"`, `data-key` and the letter as text, spec 009) and
  `key-swap`: `flex: 1 1 0`, at most 33 px wide; the letter in `--nock-font-ui`,
  500 1.3rem/1, `--nock-ink`.
- Wide keys `key-pencil` and `key-delete`: `flex: 1.5 1 48px`, at most 48 px wide.
- Icons: `key-pencil` `crayon`, `key-swap` `swap`, `key-delete` `effacer` (in place
  of today's drawn cross), each an `svg` with `aria-hidden="true"`, 22 by 22 px,
  `fill="none"`, `stroke="currentColor"` in `--nock-ink`, stroke width 1.8, round
  caps and joins.

Keys and their actions (every key keeps the focus on the grid and never opens the
system keyboard, spec 009; a key is never a Tab stop and keeps an accessible name,
spec 035):

- A letter key does what typing its letter does (spec 008, with spec 020's pencil
  mode).
- `data-testid="key-pencil"`, `aria-label` `t("pencil.toggle")` (« Crayon »),
  `aria-pressed` equal to pencil mode: a tap flips pencil mode and sends nothing.
  While pencil mode is on, `key-pencil` has a `--nock-navy` background and its icon
  a `--nock-white` stroke and a `--nock-pen-fill` fill, and each of the 26 letter
  keys shows its letter in italics in `--nock-pencil`; `key-swap` and `key-delete`
  do not change.
- `data-testid="key-swap"`, `aria-label` `t("keyboard.swap")`: a tap does what a tap
  on the selected cell does (spec 007): when the selected cell has words in both
  directions the direction switches and `select_cell` is sent (spec 007 AC-5);
  otherwise, and with nothing selected, nothing changes and nothing is sent.
- `key-delete` (spec 009: `aria-label` `t("keyboard.delete")`): a tap does what
  `Backspace` does (spec 008). A long press does nothing more: one press erases as
  one tap does (decided by the human on 2026-10-16).

### Completion status (refines spec 026's "Where `grid-status` sits" and spec 043's "Completion status")

- `grid-status` sits in `clue-bar`'s row (spec 026's rules for that place) while
  the in-app keyboard shows on a low window; everywhere else it is the end band
  under the clue bar (spec 043). Since the keyboard never shows on a solved page, a
  solved `grid-status` is always the band, and `recap-open` is always the primary
  button inside it; spec 043's secondary `recap-open` in the clue bar's row goes.
- In the sheet layout the band sits between `clue-bar` and `keyboard` while both
  show (`_design.md` section 9, full but wrong).

### `fr.json` keys

New:

| Key | Value |
| --- | --- |
| `keyboard.swap` | `Changer de sens` |

Kept and used here: `keyboard.label` (`Clavier`), `keyboard.delete` (`Effacer`),
`pencil.toggle` (`Crayon`).

### Refined specs

Each refined spec carries a dated note "(Note from the lead, 2026-10-22: refined by
spec 044, the design's keyboard ...)" and keeps its status. The test-writer updates
the tests of the criteria named here before the implementer runs.

| Spec | Criteria that change | What changes in their tests |
| --- | --- | --- |
| 020 | AC-1 (edge case "The in-app keyboard") | The test runs in a touch context and taps `key-pencil`, since the touch sheet layout has no `pencil-toggle`. (Note from the lead, 2026-10-22: row added.) |
| 028 | AC-10 | The layout checks on the solved touch page run without spec 013 AC-6's keyboard check; the test asserts there is no `keyboard` (AC-9). (Note from the lead, 2026-10-22: row added.) |
| 020 | AC-7 | In the touch context's sheet layout the pencil toggle is `key-pencil`, not `pencil-toggle`; spec 043 AC-28's and spec 013 AC-6's checks hold with it |
| 026 | AC-10 | The in-row checks run with `FX02_FULL_WRONG` only; with `FX02_SOLVED` at 568 by 320 and 740 by 360 in the touch context the page has no `keyboard` and `data-layout="column"`, and `grid-status` is under the clue bar, as at 1280 by 720. (Note from the lead, 2026-10-22: spec 043's build leaves this `FX02_SOLVED` case out, since it needs this spec's keyboard; this spec's test-writer adds it to the test of spec 026 AC-10.) |
| 043 | AC-27 | At 568 by 320 in the touch context the solved page has no `keyboard` and the column layout: `grid-status` is under the bar with a primary `recap-open`; the in-row check runs on the full-and-wrong snapshot there, which has no `recap-open`. (Note from the lead, 2026-10-22: spec 043's build checks, at 568 by 320 in the touch context, the solved `grid-status` in `clue-bar`'s row (keyboard shown, sheet layout, white text) with a secondary `recap-open` (spec 043 AC-27 and its "Completion status"); this spec's test-writer replaces that check in the test of spec 043 AC-27 by the one of this row, and this spec's implementer removes the solved in-row case and the secondary `recap-open`. This spec's AC-9 checks the new case too. This note read before: "spec 043's build leaves the solved touch case at 568 by 320 out, since it needs this spec's keyboard (spec 043 AC-27's build-order sentence); this spec's test-writer adds it to the test of spec 043 AC-27, and this spec's AC-9 checks it too.") |
| 043 | AC-2, AC-3, AC-4, AC-28 | The lead's Decision 8: the column layout on a window at most 500 px high has the phone top bar. AC-2's phone checks also run at 740 by 360 and 568 by 320 (desktop); AC-3 checks that no `topbar-brand` shows there; AC-4's fit checks also run there, in the desktop context and in the touch context with the keyboard hidden; AC-28 checks the phone top bar there in both contexts. (Note from the lead, 2026-10-22: row added.) |

Specs 009, 035 and 043 (its other criteria) get a note and no other criterion
change:

- Spec 009 AC-3 and AC-4 hold as written: row 3 also holds `key-pencil` first and
  `key-swap` before `key-delete`, neither a `key` nor with a `data-key`, so the rows'
  `data-key` values still read `AZERTYUIOP`, `QSDFGHJKLM`, `WXCVBN`; with empty
  `localStorage` the keyboard shows in the touch context; AC-4's room holds with the
  28 px keys of a low window.
- Spec 035 AC-10 holds as written for the 26 letter keys and `key-delete`; this
  spec's AC-8 checks the same rules for `key-pencil` and `key-swap`.
- Spec 043 AC-1, AC-5 and AC-29 run in the desktop context, where nothing changes
  (AC-2, AC-3 and AC-4 change only for the low windows, row above); AC-28's touch runs keep their checks, with `keyboard-toggle`
  among the top-bar buttons that its `elementFromPoint` check reads.

### Test harness

- "Browser with mocked socket" as in spec 043 (FX-01 snapshots from
  `grid_view(fx01_grid)` and `model_copy`, `seq` 5, `you` `p1`), with its helpers
  (`open_menu`, `show_tab`, `tab_to`).
- Contexts as spec 043's "Test harness". Touch context: `has_touch=True`,
  `device_scale_factor=2`, `is_mobile=True` except under Firefox, and spec 009's
  `(pointer: coarse)` init script under Firefox and WebKit. Taps with
  `locator.tap()` in the touch context. Default for this spec: the touch context at
  360 by 740, empty `localStorage` unless a criterion seeds it with
  `context.add_init_script`.
- `SOLVED`: a FX-01 snapshot whose 18 letter cells hold their solution, `solved`
  true. `FULL_WRONG`: the same with `X` at (4, 4) (its solution is `T`), `solved`
  false, so `grid-status` has `data-state="full_wrong"`.
- Positions are bounding boxes; tolerances 1 px for a position, 0.5 px for a size,
  0.1 px for a font size, unless a criterion says otherwise. Colours as spec 041
  (`parseColour`, exact channels for a token, alpha within 0.01). Fonts: spec 041's
  wait for `document.fonts.ready` before reading a size or a position.
- "No frame" means no frame within 300 ms, pings (spec 017) and `select_cell`
  frames where a criterion says so not counted.
- Engines: Chromium and WebKit locally, Firefox too in CI. No check is
  Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (new) (browser with mocked socket) « Clavier » is in the top bar on touch screens only, in its place. On a FX-01 snapshot in the touch context at 360 by 740: the children of `room-topbar` that show are, in document order, `timer`, `undo-button`, `aide-button`, `chat-toggle`, `keyboard-toggle`, `menu-button`, and there is no `pencil-toggle`; `keyboard-toggle` is a `BUTTON` with `type="button"`, 56 px wide (0.5 px) and 53 px high (1 px), holding one `svg` with `aria-hidden="true"`, 22 by 22 px, `stroke-width` 1.8, whose shapes are those of `ICONS.clavier`, above its label, which reads `fr.json["keyboard.label"]` in `font-size` 10.88 px, weight 500, colour rgb(27, 47, 85); it has `aria-pressed="true"` and a `background-color` rgb(230, 237, 249). In the touch context at 1024 by 768 (column layout), the buttons are, left to right, `undo-button`, `pencil-toggle`, `aide-button`, `chat-toggle`, `keyboard-toggle`, `menu-button`, and `keyboard-toggle` is 38 px high (0.5 px) with its 20 by 20 px icon left of its label. In the desktop context at 360 by 740 and at 1280 by 720 there is no `keyboard-toggle`, and `pencil-toggle` is in spec 043's place.
- **AC-2** (new) (browser with mocked socket) « Clavier » hides and shows the keyboard, the browser remembers it, and the grid takes the room. On a FX-01 snapshot in the touch context at 360 by 740, the test notes the height `k` of `keyboard` and the height `v` of `grid-viewport`. A tap on `keyboard-toggle`: within 300 ms no `keyboard` is on the page, `keyboard-toggle` has `aria-pressed="false"` and a background with alpha 0, `localStorage["nock.keyboard_hidden"]` is `"true"`, no frame was sent, `clue-bar`'s bottom is on the window's bottom, and `grid-viewport` is `v + k` high (1 px). After a reload, no `keyboard` is on the page and `keyboard-toggle` has `aria-pressed="false"`. A tap shows `keyboard` again, removes the key, gives `keyboard-toggle` `aria-pressed="true"`, and `grid-viewport` is `v` high again (1 px). Keyboard only (spec 035's harness): `tab_to` `keyboard-toggle` gives it a `2px` `solid` rgb(27, 47, 85) outline; `Enter` hides the keyboard and leaves the focus on `keyboard-toggle`; `Enter` again shows it, the focus still on `keyboard-toggle`. With `nock.keyboard_hidden` seeded `"true"`, in the desktop context, nothing differs from an empty `localStorage` (no `keyboard`, no `keyboard-toggle`).
- **AC-3** (new; settles spec 043's phone held sideways) (browser with mocked socket) A phone held sideways has the column layout while its keyboard is hidden, and the sheet layout while it shows. On a FX-01 snapshot in the touch context at 740 by 360, `room-page` has `data-layout="sheet"` and `keyboard` shows; the test notes the cell side `s` of (1, 1). After a tap on `keyboard-toggle`: within 300 ms `data-layout` is `"column"`, no `keyboard` is on the page, `salon` is the open side column (empty `localStorage`), `room-topbar` is still the phone top bar (54 px high, no `topbar-brand` shown) with `keyboard-toggle` in its fourth slot, between `chat-toggle` and `menu-button`, with `aria-pressed="false"`, there is no `pencil-toggle`, and the side of (1, 1) is larger than `s`. (Note from the lead, 2026-10-22: this read "`keyboard-toggle` is in the column top bar ... `pencil-toggle` is in the top bar after `undo-button`"; Decision 8.) A tap on `keyboard-toggle` then gives `data-layout="sheet"` and shows `keyboard` within 300 ms. The same holds at 568 by 320. In the touch context at 1024 by 768, hiding the keyboard keeps `data-layout="column"` and makes the side of (1, 1) larger.
- **AC-4** (new; refines spec 009's in-app keyboard) (browser with mocked socket) The keyboard has the design's rows, keys and colours. On a FX-01 snapshot in the touch context at 360 by 740: `keyboard` is 360 px wide, its bottom on the window's bottom and its top on `clue-bar`'s bottom (1 px), with `background-color` rgb(217, 222, 230) and padding `6px 3px 8px`; it holds three `keyboard-row` elements, the first's top 6 px below `keyboard`'s top, each next row's top 6 px below the previous row's bottom, the last's bottom 8 px above `keyboard`'s bottom; rows 1 and 2 hold the `key` elements whose `data-key` values read `AZERTYUIOP` and `QSDFGHJKLM`; row 3 holds in document order and left to right `key-pencil`, the `key` elements `W`, `X`, `C`, `V`, `B`, `N`, `key-swap`, `key-delete`. In each row, each key's left edge is 4 px right of the previous key's right edge. Every key is a `BUTTON` with `type="button"`, 44 px high, `border-radius` `5px`, border width `0px`, `background-color` rgb(233, 236, 241), and a `box-shadow` with offsets 0 and 1 px, blur 0 and colour 20, 24, 31 at alpha 0.25. Widths: each key of rows 1 and 2 is 31.8 px, `key-pencil` and `key-delete` 48 px, the six letter keys of row 3 and `key-swap` 32.3 px each. Each letter key shows its letter with `color` rgb(20, 24, 31), `font-size` 20.8 px, `font-weight` 500, `font-style` `normal` and a `font-family` whose first family is `Source Sans 3`. `key-pencil`, `key-swap` and `key-delete` each hold one `svg` with `aria-hidden="true"`, 22 by 22 px, `stroke-width` 1.8, a `stroke` rgb(20, 24, 31), whose shapes are those of `ICONS.crayon`, `ICONS.swap` and `ICONS.effacer`. In the touch context at 1024 by 768 (column layout, Salon open), `keyboard`'s left edge is the play area's left edge and its right edge the Salon's left edge (1 px), its top 10 px below `clue-bar`'s bottom (1 px), every letter key is 33 px wide, and the centre of each row is within 1 px of `keyboard`'s centre.
- **AC-5** (new) (browser with mocked socket) On a low window the keys are lower, so the grid keeps its room. On a FX-01 snapshot in the touch context at 740 by 360 and at 568 by 320, after a tap on (3, 1): every key is 28 px high (0.5 px) and `keyboard` is 110 px high (1 px); `grid-viewport` is at least 100 px high, `clue-bar`'s bottom is at or above `keyboard`'s top, `keyboard`'s bottom is on the window's bottom, and the page has no vertical or horizontal scroll. At 360 by 740 every key is 44 px high and `keyboard` is 158 px high (1 px).
- **AC-6** (new; refines spec 020's pencil controls) (browser with mocked socket) ✎ turns pencil mode on and off, and the letter keys show it. On a FX-01 snapshot in the touch context at 360 by 740: `key-pencil` has the `aria-label` `fr.json["pencil.toggle"]` and `aria-pressed="false"`. After a tap on (1, 0) and a tap on `key-pencil`: `key-pencil` has `aria-pressed="true"`, `background-color` rgb(27, 47, 85), and its icon's shapes have the `stroke` rgb(255, 255, 255) and a `fill` with channels 255, 255, 255 and alpha 0.35; each of the 26 `key` elements has `font-style` `italic` and `color` rgb(85, 91, 103); `key-swap` and `key-delete` keep the background rgb(233, 236, 241); `document.activeElement` is the `grid`; no frame was sent. A tap on the key `T` then sends one edit frame that parses to `PencilEdit(row=1, column=0, letter="T")`, and (1, 0) has `data-pencil="true"`. A second tap on `key-pencil` gives `aria-pressed="false"`, the background rgb(233, 236, 241), the letter keys `font-style` `normal` and `color` rgb(20, 24, 31), and the key `A` on (1, 1) then sends `EditLetter(row=1, column=1, letter="A")`. After a reload, `key-pencil` has `aria-pressed="false"`. In the touch context at 1024 by 768, a click on `pencil-toggle` gives both `pencil-toggle` and `key-pencil` `aria-pressed="true"`, and a tap on `key-pencil` gives both `"false"`.
- **AC-7** (new) (browser with mocked socket) ⇄ switches the selected cell between its across and down word, as a second tap on the cell does. On a FX-01 snapshot in the touch context at 360 by 740: `key-swap` has the `aria-label` `fr.json["keyboard.swap"]`. With nothing selected, a tap on `key-swap` selects nothing and sends no frame. After a tap on (1, 1) (`across`, `data-word="0,0,0"`), a tap on `key-swap` keeps (1, 1) selected with `down` and `clue-bar` `data-word="0,0,1"`, and sends one frame that parses to `SelectCell(row=1, column=1, direction=down)`; a second tap gives `across` and `data-word="0,0,0"` again; `document.activeElement` is the `grid` after each tap. After a tap on (1, 0) (one word, `across`, `0,0,0`), a tap on `key-swap` changes nothing and sends no frame.
- **AC-8** (new; extends spec 035 AC-10 to the new keys) (browser with mocked socket, touch context) The ✎ and ⇄ keys stay out of the Tab order but in the accessibility tree, and ⌫ erases one letter per press. On a FX-01 snapshot in the touch context at 360 by 740: `key-pencil` and `key-swap` have `tabindex="-1"` (their `tabIndex` is `-1`); inside `keyboard`, `page.get_by_role("button", name=fr.json["pencil.toggle"], exact=True)` resolves to exactly `key-pencil` and `page.get_by_role("button", name=fr.json["keyboard.swap"], exact=True)` to exactly `key-swap`; neither they nor an ancestor has `aria-hidden="true"`, `inert`, or `role` `presentation` or `none`. With the focus on the grid, `Escape` then `Tab` and up to 60 more `Tab` presses (stopping when the focus comes back to the grid or reaches `body`) never focus a key of `keyboard`; the same with `Shift+Tab`. After any key press, `focus()` on `key-swap` from `page.evaluate` gives it a computed outline of style `solid`, width `2px` and colour rgb(27, 47, 85). With (1, 0) and (1, 1) holding `T` and `A` and (1, 1) selected, a press on `key-delete` held for 1,000 ms (`page.mouse.down` at its centre, a 1,000 ms wait, `page.mouse.up`) sends exactly one frame that parses to `Erase(row=1, column=1)`, and (1, 0) still shows `T`.
- **AC-9** (new; settles spec 043's keyboard on a solved page) (browser with mocked socket) The keyboard goes away once the grid is solved. On `FULL_WRONG` in the touch context at 360 by 740, `keyboard` shows; when the mock sends `letter_changed` (seq 6) at (4, 4) with `T` from `p2` and `grid_solved` (seq 7): within 300 ms no `keyboard` is on the page, `keyboard-toggle` is `disabled` with `aria-pressed="false"` and its label colour rgb(94, 101, 115), `localStorage` holds no `nock.keyboard_hidden`, and `grid-status` (`data-state="solved"`) has its top on `clue-bar`'s bottom (1 px) and holds `recap-open` with the primary button's colours (spec 041 AC-10). A page whose first snapshot is `SOLVED` never shows a `keyboard`. On `SOLVED` in the touch context at 740 by 360 and at 568 by 320, `room-page` has `data-layout="column"`, no `keyboard` is on the page, and `grid-status` is under the clue bar with a primary `recap-open`. (Note from the lead, 2026-10-22: "no `keyboard` is on the page" was added to this sentence, so that it holds the whole of spec 043 AC-27's solved touch case at 568 by 320, which spec 043's build leaves to this spec's build.)
- **AC-10** (new; refines spec 026's and spec 043's in-row status) (browser with mocked socket) The status shares the clue bar's row only while the keyboard shows on a low window. On `FULL_WRONG` in the touch context at 740 by 360 and at 568 by 320, after a tap on (1, 1): `data-layout` is `"sheet"`, `keyboard` shows, and `grid-status` (`data-state="full_wrong"`) lies inside `clue-bar`'s box, right of `clue-bar-text` and left of `react-button`, with no `recap-open`. With `nock.keyboard_hidden` seeded `"true"`, on the same snapshot and windows, `data-layout` is `"column"` and `grid-status` has its top on `clue-bar`'s bottom (1 px). At 360 by 740 in the touch context, `grid-status` has its top on `clue-bar`'s bottom and `keyboard` its top on `grid-status`'s bottom (1 px).
- **AC-11** (new) (browser with mocked socket; static) The keyboard passes spec 035's scans, and `fr.json` holds its key. On a FX-01 snapshot in the touch context, in these states: at 360 by 740 the keyboard shown with pencil mode off, then on; at 360 by 740 the keyboard hidden; at 740 by 360 the keyboard hidden (column layout); and at 360 by 740 on `FULL_WRONG` with the keyboard shown; spec 035's contrast scan (its AC-8) and language scan (its AC-9, with the clue texts as test data) find no offending element. Static: `web/src/i18n/fr.json` holds `keyboard.swap` with the value `Changer de sens`, and still `keyboard.label` `Clavier` and `keyboard.delete` `Effacer`.

## Edge cases and errors

- Desktop window with a seeded choice (AC-2): `nock.keyboard_hidden` has no effect
  off a touch screen; there is no keyboard and no « Clavier ».
- A touch laptop whose primary pointer is fine (spec 009): no keyboard, no
  « Clavier », and « Crayon » in the top bar in both layouts.
- Pointer type changes after load (a mouse plugged into a tablet): the page keeps
  what it read at load (Terms); a reload reads it again.
- Toggling on a phone held sideways (AC-3): the layout changes with each toggle,
  so spec 043's rules close an open popover or reaction picker; the Salon column
  opens or not by `nock.salon_closed`. A keyboard activation keeps the focus on
  `keyboard-toggle`.
- A touch screen with the phone top bar and the keyboard hidden (the sheet layout,
  or a phone held sideways in the column layout): no pencil control shows (no ✎, no
  « Crayon »); pencil mode keeps its state, and the player who shows
  the keyboard again finds ✎ as it was. A player who types on a paired hardware
  keyboard there types in the mode last set.
- Pencil mode set with ✎ on a tablet (AC-6): « Crayon » in the computer top bar
  shows the same state; the mode is one state of the page.
- ⇄ on a locked or filled cell (AC-7): selection only, so it works as on any cell;
  on a solved page there is no keyboard (selection still works by taps, spec 026).
- ⌫ held down (AC-8): one erase per press, as each key (spec 009); no erase of the
  word (decided by the human on 2026-10-16).
- A popover or the Salon sheet open in the sheet layout: the scrim (spec 043) and
  the sheet cover the keyboard, so a tap there closes them and types nothing.
- Solving (AC-9): the keyboard leaves within 300 ms of the `grid_solved`; on a phone
  held sideways the page goes to the column layout; `keyboard-toggle` stays in the
  top bar, disabled, so the top bar does not move. The stored choice stays, so the
  next room opens as the player left it.
- Full but wrong on a low window (AC-10): the keyboard still shows, so the status
  takes the clue bar's row and no height from the grid (spec 026 decision 8).
- A portrait low window without the keyboard (for example a desktop window 480 by
  480): the status is the band under the clue bar, since no keyboard takes height.
- Key widths on narrow windows (AC-4): keys shrink with the window; at 320 px wide
  the letter keys of rows 1 and 2 are about 27.8 px wide, still above the 24 px of
  WCAG 2.5.8.
- `localStorage` that throws (AC-2): the keyboard shows at each load and hiding it
  holds for the page's life.

## Out of scope

- Long press on ⌫ to erase a word (decided against by the human on 2026-10-16), key
  repeat, key previews, sounds or vibration.
- A physical-keyboard shortcut for ⇄ or ✎ (spec 009 and spec 020 leave shortcuts
  out); on a computer the second click on the cell and « Crayon » do it.
- Hiding the keyboard automatically when a hardware keyboard is used.
- A QWERTY layout, accented keys, digits (spec 009).
- Remembering pencil mode (spec 020).
- The Auteurs legend's 38 px and the other screens of step 5.

## Work packages

None: one pull request.

## Decisions

Proposed by the spec writer, each already part of the spec above.

1. One definition of "the in-app keyboard shows" (touch screen, not hidden by the
   player, not solved) drives the layout, the keyboard's presence and the place of
   the status, so no rule asks why the keyboard is hidden.
2. A hidden keyboard is absent from the page, as off a touch screen (spec 009), so
   no test or screen reader meets a hidden keyboard.
3. On a low window the keys are 28 px high instead of 44 px (Open question 1). With
   44 px keys the keyboard is 158 px high, which leaves `grid-viewport` about 58 px
   at 568 by 320 and 98 px at 740 by 360 in the sheet layout, below spec 013 AC-6's
   100 px; with 28 px keys it is 110 px high and leaves about 106 px and 146 px.
   Today's keyboard has a low-window size too (1.8rem).
4. On a touch screen, ✎ is the pencil toggle of the phone top bar and « Clavier »
   takes the fourth slot; off a touch screen, where there is no keyboard to hide,
   « Crayon » keeps that slot (Open question 2). The computer top bar keeps
   « Crayon » always, as the design draws it, so both controls show one state on a
   tablet.
5. Once solved, the keyboard goes away and « Clavier » is disabled, not removed, so
   the top bar keeps its five or six buttons (Open question 4).
6. The status sits in the clue bar's row only while the keyboard shows on a low
   window. A solved page has no keyboard, so « Voir le bilan » is always the band's
   primary button, and spec 043's secondary variant in the row goes.
7. ⇄ reuses spec 007's second-tap rule, so it adds no selection rule of its own.

Decided by the lead on 2026-10-22, spec 043 being still a draft. It is already part
of this spec and of spec 043.

8. The top bar on a low window. Spec 043 gave the column layout the computer top
   bar (brand, timer, five buttons with labels beside their icons, about 650 px of
   content, about 750 px with « Clavier » on a touch screen), wider than the 568 to
   740 px of a low column-layout window (a phone held sideways with its keyboard
   hidden, spec 043's desktop windows 568 by 320 and 740 by 360). Decision: in the
   column layout on a window at most 500 px high the top bar is the phone top bar
   (54 px, icons over labels, the phone's slots and order, « Clavier » in the fourth
   slot on a touch screen), so spec 043 AC-28 holds there in both contexts. Spec 043
   is refined accordingly (its "Terms", "Top bar", popover places, AC-2, AC-3, AC-4
   and AC-28). (Note from the lead, 2026-10-22: this was Open question 1, the
   options being the phone top bar, the computer top bar without labels, or the
   brand and timer giving way.)

Decided by the human on 2026-10-22, with the spec's approval (these were the Open
questions, answered with their recommended answer; the text above already follows
them). The number in brackets is the question's number, which the text above cites:

9. (Open question 1.) Key height on a low window. Options: 44 px everywhere, as the
   design draws it, and spec 013 AC-6's 100 px floor relaxed for a phone held
   sideways with the keyboard; or 28 px keys on a low window. Answer: 28 px
   (Decision 3); `_design.md` section 8 carries a note on it.
10. (Open question 2.) The phone top bar's fourth slot off a touch screen (a narrow
    desktop window). Options: « Crayon », since there is no keyboard to hide;
    « Clavier » disabled, as drawn. Answer: « Crayon » (Decision 4).
11. (Open question 3.) A phone held sideways when the grid is solved. Options: the
    column layout, by the one definition of Decision 1; or the sheet layout kept,
    the layout reading only the player's choice. Answer: the column layout, which
    shows the Salon for the end of the game.
12. (Open question 4.) « Clavier » on a solved page. Options: disabled; removed.
    Answer: disabled (Decision 5).
13. (Open question 5.) The name of ⇄. Options: « Changer de sens »; « Changer de
    direction »; « Inverser le sens ». Answer: « Changer de sens »
    (`keyboard.swap`).

## Open questions

None left (all answered with the approval of 2026-10-22).
