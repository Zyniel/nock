---
id: "009"
title: Keyboard and navigation
status: approved
---

# 009 - Keyboard and navigation

Epic E2 Solo solving (US-2.4) · Release: MVP · Epic depends on: E1
The FX-01 reference grid is in `specs/_reference.md`, FX-02 in spec 006. The grid
elements are those of spec 006, the selection, focus and clue bar those of spec
007, the typing and erasing rules those of spec 008 (built before this one: see
"Build order").

## Goal

As a player, I want to move around the grid from the keyboard, so that I never need the mouse on desktop.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

No new Python name and no new protocol message. Client only. Keys are read like
spec 008's: `keydown` while the `grid` element has the focus, `ctrlKey`, `metaKey`
and `altKey` events left to the browser, default action prevented for every key
handled here.

### Arrow keys

`ArrowRight`, `ArrowLeft`, `ArrowDown`, `ArrowUp`, with a cell selected:

1. From the selected cell, step one cell at a time in the key's direction, skipping
   clue cells and empty cells, until a letter cell is found or the grid edge is
   passed.
2. If a letter cell is found, it becomes the selected cell. Direction: `across` for
   left and right, `down` for up and down, if the new cell has a word in that
   direction; otherwise its other direction.
3. If none is found, nothing changes (cell and direction stay).
4. With nothing selected, arrow keys do nothing.

A change sends `select_cell` (spec 007 AC-5).

### Tab and Shift+Tab

- The word order is the clue order: clue cells in row-major order, then clue index
  0 before 1 (the order of spec 003). On FX-01: `0,0,0` (TAMIS), `0,0,1` (NAVAL),
  `0,2,0` (MIME), `0,3,0` (IDES), `0,4,0` (SENT), `2,0,0` (VIDE), `3,0,0` (AMEN),
  `4,0,0` (LEST).
- A word is unfinished when at least one of its cells is not filled.
- `Tab`: from the selected word, look at the next words in order, wrapping from the
  last to the first and ending with the selected word itself; the first unfinished
  one becomes the selected word, on its first unfilled cell, in its direction.
  `Shift+Tab` does the same backwards. With nothing selected, `Tab` starts before
  the first word and `Shift+Tab` after the last.
- With no unfinished word, `Tab` and `Shift+Tab` change nothing.
- Both keys are handled (and their default prevented) only while the `grid` element
  has the focus; elsewhere they move the focus as usual.

### In-app keyboard (touch screens)

Shown when `window.matchMedia("(pointer: coarse)").matches` and the grid is shown;
otherwise absent from the page.

- `data-testid="keyboard"`, `aria-label` `t("keyboard.label")`, placed below the
  clue bar (spec 007) at the bottom of the window.
- Three `data-testid="keyboard-row"` elements, in order, holding
  `data-testid="key"` buttons with `data-key` and the letter as text:
  row 1 `A Z E R T Y U I O P`, row 2 `Q S D F G H J K L M`, row 3 `W X C V B N`
  followed by `data-testid="key-delete"`, a button with `aria-label`
  `t("keyboard.delete")` and an icon (no text).
- Tapping a letter key does what typing that letter does (spec 008); tapping
  `key-delete` does what `Backspace` does (spec 008). Tapping a key never moves the
  focus away from the grid and never opens the system keyboard.
- While it is shown, no element inside the room page's grid area, clue bar or
  keyboard is an `input`, `textarea`, `select` or `[contenteditable]`, so the system
  keyboard has nothing to open for.

New `fr.json` keys:

| Key | Value |
| --- | --- |
| `keyboard.label` | `Clavier` |
| `keyboard.delete` | `Effacer` |

### Build order

The in-app keyboard reuses spec 008's letter and erase actions ("Typing a letter",
"Erasing"), so spec 008 is built before this one (spec 008 decision 6). If
the lead keeps the old order instead, this spec's implementer writes those two
actions to spec 008's rules, and spec 008 later adds the physical keys.

### Test harness

- "Browser with mocked socket" as in spec 007 (FX-01 snapshots, `model_copy` for
  letters). Desktop context: default viewport 1280 by 720, no touch.
- Touch context: `viewport={"width": 360, "height": 740}`, `has_touch=True`,
  `is_mobile=True`; taps with `locator.tap()`. Landscape touch context: 740 by 360,
  same flags. Under Firefox, where Playwright does not support `is_mobile`, the
  context leaves it out (as spec 006).
- Engines: every criterion runs in Chromium, Firefox and WebKit
  (`specs/_architecture.md`). Touch detection: in Chromium the touch contexts rely
  on Playwright's touch emulation alone, which makes
  `window.matchMedia("(pointer: coarse)").matches` true, so Chromium checks the
  real detection. Firefox's and WebKit's emulation is not relied on for that media
  feature, so in those two engines the touch contexts also run, through
  `context.add_init_script`, a script that makes `window.matchMedia` report
  `matches: true` for the query `(pointer: coarse)` (other queries unchanged);
  every other check of AC-3 and AC-4 then runs there as in Chromium. The desktop
  context never runs that script, in any engine. No test of this spec is marked
  `only_browser("chromium")`.
- Arrow skips on FX-02 (live server, a room on FX-02): the test finds, from
  `fx02_text` in Python, a row with a letter cell, a clue cell, then a letter cell,
  and a column with the same pattern downwards (spec 006 guarantees both).

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-2.4.1) (browser with mocked socket on FX-01; browser with live server on FX-02) Arrow keys move to the next letter cell in that direction and skip clue cells. FX-01, after tapping (1, 1) (`across`): `ArrowDown` selects (2, 1) `down`; `ArrowRight` selects (2, 2) `across`; `ArrowUp` selects (1, 2) `down`; `ArrowLeft` from (1, 0) changes nothing (only clue cells to the left); `ArrowUp` from (0, 1) changes nothing. FX-02: from the letter cell left of a clue cell in a row, `ArrowRight` selects the letter cell right of that clue cell; from the letter cell above a clue cell in a column, `ArrowDown` selects the letter cell below it.
- **AC-2** (AC-2.4.2) (browser with mocked socket) Tab and Shift+Tab move to the next and previous unfinished word. On a FX-01 snapshot where (1, 2), (2, 2), (3, 2), (4, 2) hold `M`, `I`, `M`, `E` (MIME finished): after tapping (0, 1) (`0,0,1`), `Tab` selects `0,3,0` on (1, 3) `down` (MIME skipped); `Shift+Tab` then selects `0,0,1` on (0, 1); `Shift+Tab` again selects `0,0,0` on (1, 0) `across`; `Shift+Tab` again wraps to `4,0,0` on (4, 1) `across`. With focus on the grid and nothing selected, `Tab` selects `0,0,0` on (1, 0).
- **AC-3** (AC-2.4.3) (browser with mocked socket, touch and desktop contexts, in Chromium, Firefox and WebKit; touch detection as in "Test harness") On touch screens, an in-app AZERTY keyboard with 26 letters and a delete key replaces the system keyboard. In the touch context, `keyboard` is visible with three rows whose `data-key` values read `AZERTYUIOP`, `QSDFGHJKLM`, `WXCVBN`, 26 `key` elements in all and one `key-delete`; after tapping (1, 0) then the keys `T` and `A`, (1, 0) and (1, 1) show `T` and `A` and two `EditLetter` frames are sent; tapping `key-delete` then clears (1, 1) (spec 008 erase rule: the selection was on the empty (1, 2)); `document.activeElement` is never an `input`, `textarea`, `select` or contenteditable element, and the page holds none of these in the grid area, clue bar or keyboard. In the desktop context no `keyboard` element exists.
- **AC-4** (new) (browser with mocked socket, touch contexts, in Chromium, Firefox and WebKit) The clue bar stays visible above the in-app keyboard (spec 007 AC-4). In the 360 by 740 and 740 by 360 touch contexts, after tapping (3, 1): the bottom of `clue-bar` is at or above the top of `keyboard`, the bottom of `keyboard` is at most `window.innerHeight`, the top of `clue-bar` is at least 0, the computed `font-size` of `clue-bar-text` is 14 px or more, and `grid-viewport` is at least 100 px high.

## Edge cases and errors

- Only clue cells ahead (AC-1): `ArrowDown` from (1, 0) changes nothing, since
  (2, 0) to (4, 0) are clue cells; `ArrowRight` from (1, 0) selects (1, 1)
  `across`.
- Arrow onto a cell with one word (AC-1): `ArrowUp` from (1, 1) selects (0, 1)
  `down`; `ArrowLeft` from (1, 1) while `down` selects (1, 0) `across`.
- Arrow with the opposite axis (AC-1): `ArrowDown` while `across` moves and
  switches to `down` when the new cell has a down word.
- Only the selected word unfinished (AC-2): `Tab` re-selects that word's first
  unfilled cell.
- Every word finished (AC-2): `Tab` and `Shift+Tab` change nothing and send nothing;
  the focus stays on the grid.
- Locked cells (AC-2): they are filled; a word whose remaining cells are all locked
  or filled is finished.
- Tab outside the grid (AC-2): with the focus on another control, `Tab` moves the
  focus as the browser does.
- Modifiers (AC-1, AC-2): `Control+ArrowRight`, `Alt+Tab` are left to the browser.
- Touch detection (AC-3): a desktop window with a fine pointer never shows the
  keyboard, whatever its width; a touch laptop whose primary pointer is fine does
  not either, and its physical keys still work.
- Repeated taps on keys (AC-3): each tap is one letter; holding a key does not
  repeat.
- Before the first snapshot (AC-3): no keyboard.

## Out of scope

- Printing and offline play (epic E2).
- Grid rendering: spec 006.
- Word selection and direction: spec 007.
- Letter entry: spec 008 (physical keys).
- Instant solo start: spec 010.
- Home, End, Page keys, Escape and Space shortcuts; a QWERTY or numeric layout;
  accented keys on the in-app keyboard; key sounds or vibration.
- Screen reader announcements while moving (spec 035).

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written
(items 6 and 7 reworded for the three browser engines the human chose). Each one
is already part of the spec above.

1. Direction after an arrow key. Options: keep the direction, or follow the key's
   axis. Pick: follow the key's axis when the new cell has a word in it.
2. Arrow key at the edge. Pick: nothing changes; no wrap to the next row.
3. Empty cells are skipped like clue cells. Pick: yes.
4. Tab order and wrap. Pick: clue order of spec 003, wrapping, the current word
   last; Tab lands on the first unfilled cell.
5. Keyboard trap. Capturing Tab inside the grid could trap keyboard users (spec 035
   decides how to leave the grid, for example Escape). Pick: Tab is captured only
   while the grid has the focus; leaving it is left to spec 035.
6. "Touch screen". Options: `(pointer: coarse)`, `navigator.maxTouchPoints > 0`, or
   the window width. Pick: `(pointer: coarse)`, which Chromium reports with
   `has_touch=True`. Browser tests run in Chromium, Firefox and WebKit (human
   decision): the real detection is checked in Chromium; in Firefox and WebKit the
   touch contexts force the media query with an init script (see "Test harness"),
   so the keyboard's layout and behaviour are still checked in all three engines.
   Not covered: real phones and tablets (an iPhone's Safari, an Android phone),
   with or without a Bluetooth keyboard (the in-app keyboard still shows, and
   physical keys still work).
7. "Replaces the system keyboard" is tested by the absence of editable elements and
   of focus on them; whether a real phone opens its system keyboard cannot be
   observed in any headless engine, and is not covered.
8. Build order. The in-app keyboard needs spec 008's typing and erasing. Options:
   build 008 first, or build 009 first with its implementer writing those actions.
   Pick: build 008 right after 007, then 009 (same item as spec 008 decision 6).

## Open questions

None.
