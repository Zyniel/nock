---
id: "008"
title: Letter entry
status: done
---

# 008 - Letter entry

Epic E2 Solo solving (US-2.3) · Release: MVP · Epic depends on: E1
The FX-01 reference grid is in `specs/_reference.md`. The grid elements are those of
spec 006, the selection and focus rules those of spec 007, the messages those of
spec 039. It needs nothing from specs 015 and 016: locks are read from the
snapshot's `locked` field (spec 006 `data-locked`), so it can be built right after
spec 007 (see decision 6).

## Goal

As a player, I want typing to flow along the word, so that I fill an answer without re-selecting cells.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

No new Python name and no new protocol message. Client only.

### Keys

The page handles `keydown` events while the `grid` element (spec 007) has the
keyboard focus and a cell is selected, using `event.key`. Events with `ctrlKey`,
`metaKey` or `altKey` set, and events with `isComposing`, are left to the browser.

- Letter: `event.key` is one character which, after Unicode NFD decomposition,
  removal of combining marks (category `Mn`) and uppercasing, is exactly one
  character `A` to `Z`. So `a` and `A` give `A`; `é`, `è`, `ê`, `ë`, `É` give `E`;
  `à`, `â` give `A`; `ç` gives `C`; `î`, `ï` give `I`; `ô` gives `O`; `ù`, `û`, `ü`
  give `U`. The default action is prevented.
- `Backspace`: see "Erasing". The default action is prevented.
- Anything else (digits, space, punctuation, `œ`, `æ`, `ß`, `Dead`, function keys)
  is ignored by this spec: nothing changes and nothing is sent. Arrow keys and Tab
  belong to spec 009.

Spec 009's in-app keyboard calls the same two actions (letter, erase).

### Typing a letter `L` on the selected cell `c`

1. If `c` is locked (`data-locked="true"`), nothing changes and nothing is sent.
2. Otherwise, if `c` does not already hold `L`, the cell shows `L` at once
   (`data-letter`), before any answer from the server, and the page sends
   `{"type": "edit_letter", "row": r, "column": k, "letter": "L", "base_seq": null}`.
   If it already holds `L`, nothing is sent.
3. The selection moves to the next cell of the selected word, in its direction,
   that is not locked. If there is none (`c` is the last cell, or every later cell
   is locked), the selection stays on `c`. The direction does not change.
4. A selection change sends `select_cell` as spec 007 AC-5 says.

### Erasing (`Backspace`) on the selected cell `c`

1. If `c` is filled and not locked: it is cleared at once (`data-letter=""`), the
   page sends `{"type": "erase", "row": r, "column": k, "base_seq": null}`, and the
   selection stays on `c`.
2. Otherwise (`c` is empty, or locked): if `c` is the first cell of the selected
   word, nothing changes. Else the selection moves to the previous cell of the word;
   if that cell is filled and not locked, it is cleared and an `erase` for it is
   sent.

### Test harness

"Browser with mocked socket" as in spec 007: a FX-01 snapshot (cells replaced with
`model_copy` for letters and locks), a tap with `locator.click()` on a cell (which
selects it and focuses the grid), ASCII keys with `page.keyboard.press(...)`,
accented keys (é, à, ç...) by dispatching a `KeyboardEvent("keydown", {key: "é",
bubbles: true, cancelable: true})` on the focused grid with `page.evaluate`
(Playwright's `keyboard.press("é")` raises "Unknown key" and `keyboard.type`
sends no keydown, in every engine), sent frames parsed with
`parse_client_message`. The mock never answers edits, so what the cells show comes
from the client alone. `select_cell` frames are ignored by these tests unless
stated. (Note from the lead, 2026-10-15: the heartbeat `ping` frames of spec 017,
which the page may send at any time once the socket is open, are ignored in the
same way: wherever this spec says that nothing is sent, that the page sends
nothing or sends no frame, `ping` frames are not counted.)

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-2.3.1) (browser with mocked socket) Typing a letter fills the cell and moves to the next cell of the word. At the last cell the cursor stays. On an empty FX-01 grid, tapping (1, 0) then pressing `t` gives (1, 0) `data-letter="T"`, the selection on (1, 1) `across`, and one sent `EditLetter(row=1, column=0, letter="T")`. Pressing `a`, `m`, `i`, `s` fills (1, 1) to (1, 4) with `A`, `M`, `I`, `S` and leaves the selection on (1, 4); pressing `x` then replaces `S` with `X` at (1, 4), sends `EditLetter(row=1, column=4, letter="X")`, and the selection stays on (1, 4).
- **AC-2** (AC-2.3.2) (browser with mocked socket) Typing é, à or ç enters E, A or C. Digits, spaces and punctuation are ignored. Tapping (1, 0) then pressing `é`, `à`, `ç` fills (1, 0), (1, 1), (1, 2) with `E`, `A`, `C` and sends three `EditLetter` with those letters; then pressing `1`, `Space`, `.`, `-`, `'` and `?` changes no cell, keeps the selection on (1, 3) and sends no frame (Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted).
- **AC-3** (AC-2.3.3) (browser with mocked socket) Backspace clears the current cell. On an empty cell it moves back one cell and clears that one. With a snapshot where (1, 0) holds `T` and (1, 1) holds `A`: tapping (1, 1) (across) and pressing `Backspace` clears (1, 1), keeps the selection there and sends `Erase(row=1, column=1)`; pressing `Backspace` again moves the selection to (1, 0), clears it and sends `Erase(row=1, column=0)`; pressing it a third time (first cell, empty) changes nothing and sends nothing (Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted).
- **AC-4** (AC-2.3.4) (browser with mocked socket) Typing over a filled cell replaces its letter, unless the cell is locked (spec 016 AC-3, backlog AC-4.2.3). With a snapshot where (1, 1) holds `A` (author `p2`) and (1, 2) holds `M` with `locked=True`: tapping (1, 1) and pressing `e` shows `E` at (1, 1) and sends `EditLetter(row=1, column=1, letter="E")`; tapping (1, 2) and pressing `x` leaves `M`, sends no `edit_letter` and keeps the selection on (1, 2).
- **AC-5** (new) (browser with mocked socket) Backspace never leaves the page. When the `grid` element has the focus and no cell is selected (for example after Tab, or after a snapshot removed the selected word), a Backspace keydown on the grid is prevented (`dispatchEvent` returns false), changes nothing and sends nothing (Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted), and the page stays on the room URL.

## Edge cases and errors

- Skipping locked cells (AC-1, AC-4): in the AC-4 snapshot, typing `e` at (1, 1)
  moves the selection over the locked (1, 2) to (1, 3).
- Same letter again (AC-1): typing `T` on a cell that holds `T` sends nothing and
  moves on.
- Upper case and modifiers (AC-2): `Shift+A` (`event.key` `A`) gives `A`;
  `Control+a`, `Meta+r` and `Alt+e` change nothing, send nothing and are not
  prevented.
- Ignored letters (AC-2): `œ`, `æ`, `ß` and `ø` change nothing (they do not fold to
  one letter A to Z).
- Backspace on a locked cell (AC-3, AC-4): acts as on an empty cell, moving back;
  a locked previous cell is reached but not cleared and nothing is sent.
- Erasing an empty cell sends nothing (AC-3).
- No selection, or the focus elsewhere (an input of a later spec, the page body):
  keys do nothing here, and typing in an input of another spec is never captured.
- Before the first snapshot or after the socket closes: no grid input before the
  snapshot; after a close, cells still change locally and nothing is sent (the
  resend queue is spec 017).
- Server refusal: if the server answers `error` with code `cell_locked` (a lock
  that crossed the edit), restoring the cell is spec 016's. A lock that arrives
  as a `cell_locked` event is applied to the cell by spec 016; from then on this
  spec's lock rules apply to it, since they read the cell's lock state.
- Server confirmation: reconciling the shown letter with `letter_changed` events
  is spec 015's (AC-2 there); this spec only shows the letter at once.

## Out of scope

- Printing and offline play (epic E2).
- Grid rendering: spec 006.
- Word selection and direction: spec 007.
- Keyboard and navigation: spec 009 (arrow keys, Tab, the in-app keyboard).
- Instant solo start: spec 010.
- Server handling of `edit_letter` and `erase`: specs 015 and 016; server-side
  rejection of locked cells: spec 016 AC-3; checks of the cell position: spec 037.
- Pencil letters (spec 020), the `Delete` key, undo (spec 018), paste.

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written.
Each one is already part of the spec above.

1. Next cell after typing. Options: the next cell even if filled, or the next empty
   cell. Pick: the next cell even if filled, skipping only locked cells.
2. Typing on a locked cell. Options: ignore and stay, or ignore and move on. Pick:
   ignore, stay, send nothing.
3. Letters that fold to two letters (`œ`, `æ`) or none. Options: ignore, or enter
   the first letter. Pick: ignore.
4. Typing the letter already in the cell. Options: send it again (it would make me
   the author, spec 019), or send nothing. Pick: send nothing, just move on.
5. Where keys are read. Pick: `keydown` while the `grid` element has the focus, so
   other inputs keep their keys; tested with `page.keyboard.press` for ASCII keys
   and a dispatched `keydown` with `event.key` for characters such as `é`, which
   Playwright cannot press (see the test harness). Not covered: dead-key
   composition and IME input on real keyboards (only the final `event.key` is
   handled).
6. Build order. The build plan puts 008 after 016 for the lock, and 009 (whose
   in-app keyboard types and erases with this spec's rules) before both. Options:
   keep the plan, so 009's implementer writes these rules early; or build 008
   right after 007, testing the lock with snapshot locks only. Pick: build 008
   right after 007, before 009 (the lead updates `docs/build-plan.md`).

Added after the review, decided by the lead on 2026-10-11 under the human's
instruction to take technical decisions:
7. Backspace is always prevented on the focused grid, even with no selection, so
   no browser can treat it as "back" and leave the room (AC-5).

## Open questions

None.
