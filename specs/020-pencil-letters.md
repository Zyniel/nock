---
id: "020"
title: Pencil letters
status: done
---

# 020 - Pencil letters

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.) (Note from the lead, 2026-10-15: done. The human's answers are decisions 8 to 11 below, "Open questions" says "None.", and the refinements of `done` specs are listed in the note under "Public interface".)

(Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells (`_design.md` section 6): a letter is drawn in a `cell-letter` element at 0.56 of the cell side, and a pencil letter keeps its italics in `--nock-pencil` (spec 041), in ink and italic during a flash. The cell keeps the letter's colour and style, which `cell-letter` inherits, so no criterion of this spec changes. The pencil controls move in step 3 (Aide menu, « Crayon ») and step 4 (✎ key).)

(Note from the lead, 2026-10-22: refined by spec 043, the design's room layout (`_design.md` section 8): `pencil-toggle` is the top bar's « Crayon » button (after `undo-button` on a computer, in the phone top bar's fourth slot until step 4 puts the ✎ key on the keyboard), with `aria-pressed` and a word-blue background while pressed; `confirm-pencil` is the first item of the Aide menu, with the text « Confirmer la lettre au crayon » (`pencil.confirm`) and no `aria-label` (`pencil.confirm_label` is removed), present only while the selected cell shows a pencil letter, is not locked and the grid is not solved, instead of being disabled otherwise. "Client: pencil mode and the confirm control", AC-2's mocked part and AC-7 change, so the test-writer updates their tests before the implementer runs. The other criteria do not change; a test that clicks `confirm-pencil` opens the Aide menu first (spec 043's "Test harness").)

(Note from the lead, 2026-10-22: refined by spec 044, the design's keyboard (`_design.md` section 8): the in-app keyboard gets the ✎ key `key-pencil` (`aria-label` `t("pencil.toggle")`, `aria-pressed` equal to pencil mode; navy while on, and the letter keys then show their letters in italics in `--nock-pencil`). On a touch screen in spec 043's sheet layout, the top bar's fourth slot is « Clavier » and there is no `pencil-toggle`: ✎ is the pencil toggle there. `pencil-toggle` stays in the column layout's top bar and in the sheet layout off a touch screen. Both controls show and flip the one pencil mode. AC-7 changes, so the test-writer updates its test before the implementer runs; the other criteria do not change (AC-1 and AC-2 click `pencil-toggle` in the desktop context).)

Epic E5 Collaboration aids (US-5.2) · Release: V1 · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The grid
elements are those of spec 006, typing and erasing spec 008, the arrow keys and the
in-app keyboard spec 009, the rooms engine and its test harness spec 011, word
tints spec 013, edits, their check order and the pending queue spec 015, locks and
the flash spec 016, the stale rule and the resend queue spec 017, undo and `replay`
spec 018, the authors view spec 019, checks spec 023, reveals and the room toolbar
spec 024, completion spec 026, accessibility spec 035, the rate limit spec 037,
the messages spec 039 (`PencilEdit`, `ConfirmPencil`, `LetterChanged.pencil`,
`LetterCellView.pencil`). Built after specs 024, 025 and 019.

## Goal

As a player, I want to mark a guess as uncertain, so that others don't build on it blindly.

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking.

## Public interface

No new protocol message, no new `ErrorCode` and no new public Python name. This
spec gives `pencil_edit` and `confirm_pencil` their meaning in
`nock.room.handle_message` (today they only go through the rate limit), changes the
private `_is_filled` of `nock.room` so that a pencil letter fills its cell (spec
026), and adds pencil mode, the look of pencil letters and the confirm control to
the room page.

(Note from the lead, 2026-10-15: this spec refines four `done` specs, and none of
the human's answers, decisions 8 to 11, adds another: decision 11 keeps spec 016 as
it is. Each refinement is described where it applies below. None changes a
criterion or a test of the spec it refines, because their tests show no pencil
letter, so every pencil flag they compare is `false`. Spec 008, tested by its AC-1
and AC-4: step 2 of "Typing a letter" also compares the pencil flag. Spec 018,
tested by its AC-3: "Pending queue matching" also compares the pencil flag. Spec
017, tested by its AC-2: the resend after a reconnection sends each pending edit as
the message of its kind. Spec 026: `_is_filled`, whose text was already amended on
2026-10-12. The new cases are tested by AC-1 to AC-7 here.)

### Server rule: `PencilEdit` and `ConfirmPencil` in `nock.room.handle_message`

Both are edits (spec 037 decision 2). From player `p`, their checks run in this
order; the first that fails refuses the edit (state unchanged apart from `p`'s
`last_seen_at`, `last_input_at` and, if `p` was idle, their state, to which spec
013's wake entry adds one to the seq; `p.recent_edits` unchanged; no entry of its
own, an idle sender being first woken by spec 013's entry, which a refusal does not
undo; one `ErrorMessage` in `reply`) (Note from the lead, 2026-10-15: an idle
sender is woken even when its message is refused, as spec 013's input rule and the
code do.):

1. (spec 037) rate limit: `rate_limited`.
2. (spec 037) `(row, column)` is not a letter cell of `state.grid`:
   `not_a_letter_cell`.
3. (spec 016) the cell is locked: `cell_locked`.
4. (spec 017) `base_seq` is not None, and the cell changed since then by someone
   else (`changed_seq > base_seq` and `changed_by != p`): `stale_edit`.
5. (spec 026) the grid is solved: `grid_solved`.
6. For a `ConfirmPencil` only: the cell holds no pencil letter (it is empty, or
   holds a normal letter): `stale_edit` (decision 2). This check comes after check
   5, so a confirmation on a solved grid gets `grid_solved`, as spec 026 AC-4
   requires.

Checks 1 to 5 are spec 015's order, so this spec's refusals come before
`grid_solved` as spec 026 sets, and the one refusal of its own comes after.

An accepted `PencilEdit(row, column, letter, base_seq)` is spec 015's accepted
`EditLetter` with `pencil = True`. With `seq = state.seq + 1`: the cell becomes
`letter`, `pencil = True`, `author = p`, `wrong = False`, `changed_seq = seq`,
`changed_by = p`; `p.last_edit` records the cell as it was before (spec 018);
`now` is added to `p.recent_edits` (spec 037); one entry
`LetterChanged(seq, row, column, letter, pencil=True, player_id=p)`; then spec
026's completion entry when it applies. A pencil edit that does not change the
cell still gets its `letter_changed` (spec 015).

An accepted `ConfirmPencil(row, column, base_seq)`, on a cell holding the pencil
letter `L`: with `seq = state.seq + 1`, the cell keeps `L` with `pencil = False`,
`author = p` (the confirmer, decision 1), `wrong = False`, `changed_seq = seq`,
`changed_by = p`; `p.last_edit` records the cell as it was before, the pencil
letter and its author, so an undo puts the pencil letter back (authored by the
undoer, spec 018); `now` is added to `p.recent_edits`; one entry
`LetterChanged(seq, row, column, letter=L, pencil=False, player_id=p)`. A
confirmation changes neither whether the grid is full nor whether it is right, so
spec 026's rule never adds an entry after it.

Completion (spec 026's definitions, amended on 2026-10-12): `_is_filled(cell)`
becomes `cell.letter is not None`, so a pencil letter fills its cell and is
compared with the solution like any letter. A pencil edit that fills the grid is
followed by `grid_full_wrong` or `grid_solved` like any letter change.

Unchanged: checks leave pencil letters out (spec 023); a reveal replaces a pencil
letter and clears `pencil` (spec 024); `replay` of `letter_changed` already sets
`pencil` (spec 018); an undo restores `pencil` from `last_edit` (spec 018).

### Client: pencil letters on the page

`web/src/lib/roomSession.ts`:

```ts
export interface LetterCellView {
  // ... fields of specs 015 to 024
  // True while the letter in place is a pencil letter (spec 020).
  pencil: boolean
}

export interface PendingEdit {
  // ... fields of specs 015 and 017
  // The message that made it: 'edit' (edit_letter or erase), 'pencil'
  // (pencil_edit) or 'confirm' (confirm_pencil).
  kind: 'edit' | 'pencil' | 'confirm'
}

// What a cell shows: the newest pending edit of the cell, else the confirmed
// letter; a locked cell always shows its confirmed letter (specs 015, 016).
export function shownCell(
  cell: LetterCellView,
  pendingEdits: PendingEdit[],
): { letter: string | null; pencil: boolean; unconfirmed: boolean }
```

- A snapshot's letter cell gets `pencil = (cell.pencil === true)`. An applied
  `letter_changed` sets `pencil` to the event's `pencil`; an applied `cell_locked`
  sets `pencil = false`.
- The shown pencil flag of a cell is that of its newest pending edit (`true` for
  kind `pencil` only) when it has one and is not locked, else the confirmed
  `pencil`.
- Answers (refines spec 018's "Pending queue matching"): an own `letter_changed`
  removes the oldest pending edit only when it is for the same cell, the same
  letter and the same pencil flag (`true` for kind `pencil`, `false` for the other
  kinds); otherwise it only updates the confirmed grid. The five edit error codes
  of spec 015 remove the oldest pending edit, whatever its kind.
- After a reconnection (spec 017), each pending edit is sent again as the message
  of its kind (`edit_letter` or `erase`, `pencil_edit`, `confirm_pencil`), oldest
  first, paced as spec 017 AC-5 says, each with its recorded `base_seq`.

On the `cell` element of each letter cell, new attribute `data-pencil`: `true` when
the shown letter is a pencil letter, else `false`. A cell with `data-pencil="true"`
shows its letter in italics (computed `font-style` `italic`) in every state, the
flash of spec 016 included. (Note from the lead, 2026-10-15: the italics hold in
every state including the flash, since they are then the only sign left (review of
spec 020).) Outside a flash (`data-flash` is `""`), it also shows it in grey: its
computed `color` differs from the `color` of a normal letter in a cell in the same
state, and has a contrast of at least 4.5:1 against the cell's background in every
state of AC-7 other than the flash (spec 035 AC-8). (Note from the lead,
2026-10-15: the colour rule holds in every state except the flash. It replaces "in
every state of AC-7", because on flash colours 0, 5 and 7 every colour that keeps
4.5:1 is almost indistinguishable from the normal letter's text colour (review of
spec 020).) While the cell flashes (`data-flash` is not `""`), its pencil letter
takes the flash's text colour, the same `color` as a normal letter in that state,
and the italics alone mark it as a pencil letter; its contrast against the flash
colour is at least 4.5:1 (spec 035 AC-8, state K3). (Note from the lead,
2026-10-15: added, decision 12 (review of spec 020).) (Note from the lead,
2026-10-22: since spec 041 AC-16, the flash is the replacer's colour at 38 % over
white, drawn by a `cell-flash` overlay under a white cell background: the pencil
letter has `font-style` `italic` and the ink `color` rgb(20, 24, 31), as a normal
letter does, and its contrast is measured against the cell's background with the
overlay composited over it, not against a full player colour. Outside a flash,
the tint of another player's word is 16 % instead of 28 %, which keeps the pencil
grey at 4.5:1 or more on all eight tints.) The italics are the sign that
does not rely on colour (spec 035 AC-6 and AC-7). A cell with `data-pencil="false"`
has the `font-style` `normal`.

### Client: pencil mode and the confirm control

In spec 024's `room-toolbar`, right after the undo control:

- `data-testid="pencil-toggle"`: a `<button type="button">` with `aria-pressed`
  and the text `t("pencil.toggle")`. It is `false` at each page load, each click
  flips it, and it is `disabled` once the grid is solved (spec 026). (Note from the
  lead, 2026-10-22: refined by spec 044, the design's keyboard: the ✎ key
  `key-pencil` of the in-app keyboard flips the same mode and shows it with
  `aria-pressed`; on a touch screen in the sheet layout it is the only pencil
  toggle. The keyboard is absent once the grid is solved.)
- `data-testid="confirm-pencil"`: a `<button type="button">` with the text
  `t("pencil.confirm")`. It is on the page only while the selected cell shows a
  pencil letter (confirmed or pending), is not locked, and the grid is not solved.
  (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout:
  it is the first item of the Aide menu. This read "and the `aria-label`
  `t("pencil.confirm_label")`. It is `disabled` unless the selected cell shows a
  pencil letter (confirmed or pending), is not locked, and the grid is not
  solved.")

Typing (spec 008's "Typing a letter", which spec 009's in-app keys also use). Step
2 of spec 008 becomes: if the cell is not locked and does not already show `L`
with the pencil flag of the mode (`true` while pencil mode is on, `false` while it
is off), the cell shows `L` at once with that flag, a pending edit is added (kind
`pencil` with the mode on, `edit` with it off), and the page sends
`{"type": "pencil_edit", "row": r, "column": k, "letter": "L", "base_seq": null}`
with the mode on, or spec 008's `edit_letter` with it off. Otherwise nothing is
sent. The selection then moves as spec 008 says. So, in pencil mode, typing `L`
over a normal `L` turns it into a pencil letter; with pencil mode off, typing `L`
over a pencil `L` turns it into a normal letter by an edit, and the typer becomes
its author. `Backspace` and `key-delete` erase as spec 008 says, whatever the
mode.

Confirming, in one action: a click on `confirm-pencil` sends
`{"type": "confirm_pencil", "row": r, "column": k, "base_seq": <the page's seq>}`
for the selected cell, adds a pending edit of kind `confirm` holding the shown
letter, and the cell shows that letter as a normal letter at once
(`data-pencil="false"`, `data-unconfirmed="true"`). The selection does not move.
The page's `seq` goes in `base_seq` so that a confirmation of a letter that
another player changed meanwhile is refused `stale_edit` (spec 017's rule), rather
than confirming a letter the player never saw (decision 3).

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `pencil.toggle` | `Crayon` |
| `pencil.confirm` | `Confirmer` |
| `pencil.confirm_label` | `Confirmer la lettre au crayon` |

### Test harness

- Rule unit tests: spec 026's harness (`new_room("ABC123", fx01_grid, NOW)` with
  `p1` and `p2`, seq 2; `FULL17`), pencil letters written with
  `handle_message(..., PencilEdit(...))` and confirmed with
  `handle_message(..., ConfirmPencil(...))`.
- WebSocket tests: as spec 011, with `RoomConfig(max_edits_per_second=1000)`.
- "Browser with mocked socket" and "browser with live server": as spec 023; keys
  as spec 008's harness; the reconnection mock as spec 017's harness.
- Contrast states (AC-7), each in a FX-01 snapshot with pencil letters: a pencil
  letter on a plain cell, on the selected cell and on another cell of my selected
  word; for each colour index k from 0 to 7, a pencil letter in a cell tinted by
  another player of colour k (spec 013), with `you` given a colour other than k;
  and for each k, a `letter_changed` with `pencil` true from a player of colour k
  replacing a letter of mine, scanned within its 1-second flash (spec 016). (Note
  from the lead, 2026-10-15: these eight flash states are the "flash states" of
  AC-7. In them the pencil letter has the flash's text colour, so only its italics
  and its 4.5:1 contrast are checked, not a colour difference (review of spec
  020).)
- Window sizes and contexts: as spec 024 (the eight sizes of spec 006 AC-5,
  desktop and touch contexts).
- Engines: every browser criterion runs in Chromium and WebKit locally and also
  Firefox in CI. No check of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-5.2.1) (rule unit test; WebSocket; browser with mocked socket; browser with live server) A letter typed in pencil mode shows in italics, and in grey outside a flash, for every player. (Note from the lead, 2026-10-15: "in grey italics" became "in italics, and in grey outside a flash", decision 12 (review of spec 020).) Rule: in a FX-01 room with `p1` and `p2` (seq 2), `PencilEdit(row=1, column=0, letter="T")` from `p1` gives one entry `LetterChanged(seq=3, row=1, column=0, letter="T", pencil=True, player_id="p1")`, and the cell has `letter="T"`, `pencil=True`, `author="p1"`, which `grid_state` shows too. WebSocket: A and B join a FX-01 room; A sends `{"type": "pencil_edit", "row": 1, "column": 0, "letter": "T", "base_seq": null}`; A and B receive that `letter_changed` with `pencil` true; a client C joining afterwards gets a snapshot whose (1, 0) has `letter="T"` and `pencil=True`. Mocked: given a FX-01 snapshot (`you` = `p1`, `seq` 5) where (1, 2) holds `M` (normal, by `p2`), a click on `pencil-toggle` (which then has `aria-pressed="true"`), a tap on (1, 0) and the key `t` show `T` at (1, 0) at once with `data-pencil="true"`, `data-unconfirmed="true"`, the computed `font-style` `italic` and a computed `color` different from the `color` of (1, 2), which has `data-pencil="false"` and `font-style` `normal`; one edit frame is sent (spec 008's harness leaves `select_cell` frames aside), which parses to `PencilEdit(row=1, column=0, letter="T")`, and the selection moves to (1, 1); when the mock answers `letter_changed` (seq 6) at (1, 0) `T` with `pencil` true from `p1`, the cell keeps its pencil `T` with `data-unconfirmed="false"`; a `letter_changed` (seq 7) at (2, 2) `I` with `pencil` true from `p2` shows a pencil `I` there; a snapshot whose (3, 1) holds a pencil `A` shows it in pencil. With pencil mode off, typing sends `EditLetter` and the letter is not in italics. Live: two pages join one FX-01 room as `Ana` and `Bob`; Ana clicks `pencil-toggle`, taps (1, 0) and types `T`; within 300 ms of the key press (spec 015 AC-1), Bob's (1, 0) shows `T` with `data-pencil="true"` and the computed `font-style` `italic`.
- **AC-2** (AC-5.2.2) (rule unit test; browser with mocked socket; browser with live server) Any player can confirm a pencil letter with one action; it then shows as a normal letter. Rule: in the room of AC-1 after `p1`'s pencil `T` at (1, 0) (seq 3), `ConfirmPencil(row=1, column=0)` from `p2` gives one entry `LetterChanged(seq=4, row=1, column=0, letter="T", pencil=False, player_id="p2")`, and the cell has `pencil=False` and `author="p2"`; `p1` can confirm its own pencil letter the same way; a `ConfirmPencil` on an empty cell, or on a normal letter, is refused `stale_edit`. In another run, `p1` writes a pencil `T` (seq 3) then a pencil `A` (seq 4) at (1, 0): `p2`'s `ConfirmPencil(row=1, column=0, base_seq=3)` is refused `stale_edit`, and with `base_seq=4` it is accepted and confirms `A`. Mocked: given a FX-01 snapshot (`you` = `p1`, `seq` 5) where (1, 0) holds a pencil `T` by `p2`: with nothing selected, and with (1, 1) (empty) selected, there is no `confirm-pencil`; after a tap on (1, 0) it is the first item of `aide-menu`, enabled, and (with the Aide menu opened) a click sends (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout; this read "`confirm-pencil` is disabled; after a tap on (1, 0) it is enabled, and a click sends") one frame that parses to `ConfirmPencil(row=1, column=0, base_seq=5)`, shows `T` at once with `data-pencil="false"` and `data-unconfirmed="true"`, and leaves the selection on (1, 0); when the mock answers `letter_changed` (seq 6) at (1, 0) `T` with `pencil` false from `p1`, the cell shows a normal `T` with `data-unconfirmed="false"` and `data-author="p1"`. In a second run the mock answers `error` `stale_edit`, and the cell shows its confirmed pencil `T` again. Live: Ana writes a pencil `T` at (1, 0); Bob taps (1, 0) and clicks `confirm-pencil`; on both pages, (1, 0) then shows `T` with `data-pencil="false"` and the computed `font-style` `normal`.
- **AC-3** (AC-5.2.3) (rule unit test) Completion (spec 026, backlog US-6.4) evaluates pencil and normal letters the same way. Given `FULL17`: `PencilEdit(row=4, column=4, letter="T")` from `p2` at `NOW + 754.0` gives `LetterChanged(seq=20, row=4, column=4, letter="T", pencil=True, player_id="p2")` then `GridSolved(seq=21, elapsed_ms=754000)`; in a second run, a `PencilEdit` with `X` gives the `letter_changed` then `GridFullWrong(seq=21)`, and confirming that `X` (`ConfirmPencil`) then gives only its `letter_changed`; in a fresh FX-01 room where `p1` writes the 18 solution letters with `PencilEdit` in row-major order, exactly one `GridSolved` comes, after the 18th. On the solved grid of the first run, `PencilEdit` and `ConfirmPencil` at (4, 4) are refused `grid_solved`.
- **AC-4** (new, from the lead's note of 2026-10-11 on spec 037) (rule unit test; WebSocket) `pencil_edit` and `confirm_pencil` go through the edit checks of spec 015 in their order, and a refused one is not counted. Rule, in a FX-01 room with `p1` and `p2`: a `PencilEdit` and a `ConfirmPencil` at (0, 0) and at (5, 0) are refused `not_a_letter_cell`; on a locked cell, `cell_locked`; with a `base_seq` older than another player's change of the cell, `stale_edit`; on a solved grid, `grid_solved`. Each refusal leaves the state, its `seq` and `p1.recent_edits` as they were (apart from `last_seen_at`, `last_input_at` and, for a sender who was idle, their state and the seq raised by spec 013's wake entry, which a refusal does not undo) and sends one error. (Note from the lead, 2026-10-15: an idle sender is woken even when its message is refused, as spec 013's input rule and the code do.) Order: with `max_edits_per_second=1` and an edit in the last second, a pencil edit on a locked cell is refused `rate_limited`; a pencil edit on a clue cell of a solved grid is refused `not_a_letter_cell`; a confirmation on a locked cell with an old `base_seq` is refused `cell_locked`; a confirmation with an old `base_seq` on a solved grid is refused `stale_edit`; a confirmation of a normal letter on a solved grid is refused `grid_solved`. Twenty-one pencil edits at one `now` give 20 `letter_changed` and one `rate_limited`, and pencil edits share the window with `edit_letter` (spec 037 AC-3). WebSocket: a `pencil_edit` at (0, 0) is answered `not_a_letter_cell` to its sender only, and the other client receives nothing.
- **AC-5** (new) (rule unit test) Pencil letters survive an undo and a reload. Rule, in one play on a FX-01 room with `p1` and `p2`: `p1`'s pencil `T` at (1, 0) then `Undo()` gives one `letter_changed` with `letter=None` and `pencil=False`, logged with `undo=True`; `p1`'s normal `A` at (1, 1), then pencil `B` there, then `Undo()` gives back `A` with `pencil=False`; `p1` then writes a pencil `T` at (1, 0) again, `p2` confirms it, and `p2`'s `Undo()` gives back `T` with `pencil=True` and `author="p2"` (spec 018: the undoer is the author). Replaying all the entries of this play in order from `new_room` gives the same cells (`letter`, `pencil`, `author`) as the live state, and so does the room saved in a `RoomStore` and loaded again (spec 018).
- **AC-6** (new) (browser with mocked socket) Pending pencil edits and confirmations are matched and resent by their kind. Given a FX-01 snapshot (`you` = `p1`, `seq` 5): with pencil mode on, the player types `T` at (1, 0); the mock sends `letter_changed` (seq 6) at (1, 0) `T` with `pencil` false from `p1`, which does not answer the pending pencil edit (an undo's result has that shape): the cell still shows the pending pencil `T` with `data-unconfirmed="true"`; the mock then sends `letter_changed` (seq 7) at (1, 0) `T` with `pencil` true from `p1`, which answers it: `data-unconfirmed="false"`. Then the mock closes the socket with code 1011; offline, the player types a pencil `A` at (1, 1), taps (1, 0) and clicks `confirm-pencil`; the mock accepts the next socket and answers its join with a snapshot (`seq` 9) whose (1, 0) still holds the pencil `T`: the edit messages the page then sends are, in this order, `PencilEdit(row=1, column=1, letter="A", base_seq=7)` and `ConfirmPencil(row=1, column=0, base_seq=7)` (spec 017 AC-2; pings and selections aside).
- **AC-7** (new) (browser with mocked socket) The pencil controls and pencil letters meet spec 035 and keep the grid's room. At every window size of spec 006 AC-5, in desktop and touch contexts, with spec 013 AC-6's setup (FX-01, `you` host among 8 players, 100 feed items, (3, 1) tapped): spec 013 AC-6's checks pass with `pencil-toggle` shown in `room-topbar` (after `undo-button` in the column layout, after `chat-toggle` in the sheet layout of the desktop context) and, in the touch context's sheet layout, with `key-pencil` shown in `keyboard` and no `pencil-toggle` (Note from the lead, 2026-10-22: refined by spec 044, the design's keyboard; the touch context's sheet layout had `pencil-toggle` after `chat-toggle`), and, with (1, 0) holding a pencil letter and selected, with `confirm-pencil` the first item of the open `aide-menu`; spec 043 AC-28's checks hold for both, and for `key-pencil` where it shows in place of `pencil-toggle` (inside the window; `elementFromPoint` at their centre returns them). In a separate run on a FX-01 snapshot with nothing selected, at 1280 by 720, keyboard only (spec 035's harness): `tab_to` `pencil-toggle` and `Enter` sets `aria-pressed="true"`; `tab_to` `grid`, `Tab` selects `0,0,0` on (1, 0) (spec 009), and `t` sends `PencilEdit(row=1, column=0, letter="T")` and moves the selection to (1, 1); `ArrowLeft` brings it back to (1, 0); `Escape`, then `tab_to` `aide-button`, `Enter` (the focus goes to `confirm-pencil`, the menu's first item) and `Enter` send `ConfirmPencil(row=1, column=0, base_seq=...)`; (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout; this read "both are in `room-toolbar` right after `undo-button`, and spec 024 AC-8's toolbar rules hold for them (one row on small windows; with the keyboard focus, inside the toolbar's client area and an outline that is not clipped; `elementFromPoint` at their centre after `scrollIntoView`)" and "`tab_to` `confirm-pencil` and `Enter`".) each of the two buttons shows spec 035 AC-2's outline when reached. In every contrast state of "Test harness", spec 035's contrast scan finds no offending element, and its language scan accepts the texts of the two buttons. Flash states: for each colour index k from 0 to 7, in the flash state of "Test harness" (a pencil `letter_changed` from a player of colour k replacing a letter of mine, checked within the 1-second flash), the flashing cell has `data-flash` equal to `k` and `data-pencil="true"`, its computed `font-style` is `italic`, and the computed `color` of its text has a contrast of at least 4.5:1 against the flash colour (the cell's computed `background-color`, or that of its overlay, spec 016) (Note from the lead, 2026-10-22: since spec 041 AC-16, the flash colour is the overlay's colour at its 0.38 opacity over the white cell; the 4.5:1 is measured against that composite, and the test also checks one `cell-flash` at 0.38 on a white cell.); no colour difference with a normal letter is expected there. (Note from the lead, 2026-10-15: added, decision 12. It narrows the colour rule of "Client: pencil letters on the page" to the states other than the flash, and checks the italics and the 4.5:1 contrast in the flash (review of spec 020).)

## Edge cases and errors

Note from the lead (2026-10-11, from the spec 037 review): `pencil_edit` and
`confirm_pencil` are counted by the rate limit (spec 037) but do not yet go
through checks 2 to 5 of spec 015's order. This spec must route them through
the same edit checks, so a refused pencil edit (for example on a clue cell)
is answered with its error and not counted. (Addressed by "Server rule" and AC-4.)

Note from the lead (2026-10-12, from the spec 026 review): completion counts
pencil letters like normal letters (AC-3, backlog AC-5.2.3; spec 026's
definitions and decision 6 were amended on 2026-10-12 to match). On the
server, `_is_filled` in `src/nock/room.py` still returns False for a pencil
letter (`cell.letter is not None and not cell.pencil`); this spec must change
it so a pencil letter fills its cell, and a pencil edit that fills or
completes the grid must trigger spec 026's completion rule like any letter
change. On the client, `isGridFull` in `web/src/lib/RoomPage.svelte` (around
line 229) checks only `cell.letter !== null`, so it already counts pencil
letters towards the `full_wrong` banner, which is now right; it needs no
change. `pencil_edit` and `confirm_pencil` are refused with `grid_solved` once the
grid is solved; until this spec defines its own checks, only the rate limit
comes before that refusal. This spec must place its own refusals before
`grid_solved`, in the order spec 026 sets. (Addressed by AC-3 and AC-4: checks 2
to 4 of spec 015 come before `grid_solved`; the one new refusal, "no pencil letter
to confirm", comes after it, because spec 026 AC-4 expects `grid_solved` for a
confirmation on a solved grid's normal letter.)

- AC-3 depends on behaviour owned by spec 026; test only this spec's side of it here.
- Typing the same letter (AC-1): in pencil mode, typing `L` on a cell that shows a
  pencil `L` sends nothing and moves on (spec 008 decision 4); on a normal `L` it
  sends a `pencil_edit` (decision 10). (Note from the lead, 2026-10-15:
  "sends nothing" leaves aside the heartbeat `ping` frames of spec 017, which the
  page may send at any time once the socket is open.) (Note from the lead,
  2026-10-15: "open question 3" became "decision 10", the human's answer.)
- A locked cell (AC-1, AC-4): typing in pencil mode does nothing and sends nothing
  (spec 008); the server refuses a pencil edit there with `cell_locked`. (Note
  from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted.)
- Two confirmations at once (AC-2): the second is refused `stale_edit`, since the
  cell then holds a normal letter, and its page shows the first confirmer's letter.
- The flash (spec 016): a confirmation of my pencil letter by another player makes
  my cell flash in their colour, as any `letter_changed` from another player on my
  letter does, the same letter included (spec 016's edge case "Same letter from
  both"); a pencil edit by another player over my letter flashes too (decision
  11). (Note from the lead, 2026-10-15: "open question 4" became "decision 11", the
  human's answer.) While my cell flashes with a pencil letter in it, the letter
  keeps its italics and takes the flash's text colour (decision 12, AC-7). (Note
  from the lead, 2026-10-15: added (review of spec 020).)
- Authors (spec 019): a pencil letter has an author and a band like any letter; a
  confirmation makes the confirmer its author, so the band takes their colour
  (decision 1).
- Checks (spec 023): pencil letters are left out of checks; a cell struck wrong
  loses its strike when a pencil letter is written in it (any edit clears `wrong`).
- Reveals (spec 024): a reveal replaces a pencil letter with the solution letter
  and clears its pencil flag, on the server and on the page.
- Undo (AC-5): one level, as spec 018; an undo of a pencil edit or of a
  confirmation puts the cell back as it was, authored by the undoer.
- Offline (AC-6): pencil edits and confirmations made offline are resent with
  their kinds; a confirmation whose pencil letter another player changed
  meanwhile is refused `stale_edit`, and the page then shows the server's letter.
- A cell locked while a pencil edit of mine is pending (AC-1): as spec 016, the
  cell shows its confirmed letter and the server's `cell_locked` error removes the
  pending edit.
- The in-app keyboard (AC-1): its keys follow pencil mode; it gets no pencil key,
  since the toolbar's toggle serves touch screens too. (Note from the lead,
  2026-10-22: refined by spec 044, the design's keyboard: it gets the ✎ key
  `key-pencil`, which is the pencil toggle of a touch screen in the sheet layout.)
- Solved grid (AC-3, AC-7): `pencil-toggle` and `confirm-pencil` are disabled, and
  spec 026's input lock sends nothing. (Note from the lead, 2026-10-15: spec 017's
  heartbeat `ping` frames are not counted.)
- Rate (AC-4): pencil edits and confirmations count with letter edits (spec 037),
  and the resend pacing of spec 017 AC-5 applies to them.
- Integrity (spec 037 AC-1): a pencil letter is typed, so it is earned at its cell
  like any typed letter; a confirmation shows a letter already earned there.

## Out of scope

- Voice and video (epic E5).
- Authorship view: spec 019.
- Clue flag: spec 021.
- Chat and reactions: spec 022.
- Keyboard shortcuts for pencil mode and for confirming (spec 035 leaves out the
  shortcuts of checks and reveals too); both buttons are reached with `Tab`.
- Confirming a whole word, or every pencil letter at once.
- Several candidate letters in one cell.
- Remembering pencil mode across reloads.
- A pencil key on the in-app keyboard. (Note from the lead, 2026-10-22: refined by
  spec 044, the design's keyboard, which adds the ✎ key; this item no longer
  applies.)

## Work packages

None.

## Decisions

Proposed in the Phase 6 refine of 2026-10-14 and approved by the human with the
spec. Each one is already part of the spec above. Items 1, 2 and 4 were also open
questions: the human's answers to them are items 8 to 10 below, and item 11 answers
a fourth question.

1. The confirmer becomes the author of the confirmed letter. `letter_changed`
   carries one `player_id`, which the page takes as the author (spec 015), as spec
   018 decision 5 found for undo; keeping the pencil author would need a new
   protocol field. Confirming also vouches for the letter, so the confirmer is a
   good person to ask about it.
2. Confirming a cell that holds no pencil letter is refused `stale_edit`: the cell
   is not what the confirmation expected, and the page already treats `stale_edit`
   as the answer to one edit (spec 015), so no protocol change is needed. The check
   comes after `grid_solved` (spec 026 AC-4).
3. A confirmation carries the page's `seq` as `base_seq`, so spec 017's stale rule
   refuses the confirmation of a letter that another player changed meanwhile.
4. Typing the same letter in the other mode changes its pencil flag.
5. Pencil letters fill their cells and count for completion (spec 026 decision 6,
   backlog AC-5.2.3).
6. Grey italics: the italics are the sign that does not rely on colour, and they
   hold in every state, the flash included; outside a flash, the grey differs from
   the colour of a normal letter and keeps 4.5:1 on every background a cell can
   have. During a flash, see decision 12. (Note from the lead, 2026-10-15: "the grey
   keeps 4.5:1 on every background a cell can have" and the colour difference held
   in every state, which no colour can do on the flash backgrounds (review of spec
   020).)
7. The two controls go right after the undo control in spec 024's toolbar, since
   they are used while typing.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question. Each one is already part of the spec above.

8. Who is the author of a confirmed pencil letter (former open question 1).
   Options: the confirmer, with no protocol change; or the player who wrote it in
   pencil, which needs a new field in `letter_changed` (a change to spec 039).
   Pick: the confirmer (decision 1).
9. Confirming a cell that holds no pencil letter, by a race or a forged message
   (former open question 2). Options: `stale_edit`, with no protocol change; or a
   new `ErrorCode` such as `not_pencil` (a change to spec 039, and the page must
   treat it as an edit answer). Pick: `stale_edit` (decision 2).
10. Typing the letter a cell already shows, in the other mode (former open question
    3). Options: it changes the pencil flag; or it sends nothing, as spec 008 does
    for the same letter. Pick: it changes the pencil flag, so pencil mode can mark
    a doubt on a letter without retyping it, and normal typing can firm it up
    (decision 4).
11. The flash when another player confirms my pencil letter (former open question
    4). Options: it flashes, which is spec 016 as written (another player changed
    my letter); or no flash when the letter stays the same, which would amend spec
    016 AC-2. Pick: it flashes, so spec 016 does not change.

Decided by the lead on 2026-10-15 after the review, under the owner's delegation of
accessibility choices. It is already part of the spec above.

12. The colour of a pencil letter during the flash (review of spec 020). During the
    flash of spec 016 (1,000 ms, the cell's background is the colour of the player
    who changed it, its text takes the flash's own text colour), the reviewer
    computed that on flash colours 0, 5 and 7 every colour that keeps 4.5:1 is almost
    indistinguishable from the normal letter's text colour, so a colour difference
    cannot hold in every flash state. Options: a grey that differs from the normal
    letter in every flash state, which breaks 4.5:1 on some of them; or a pencil
    letter that takes the flash's text colour while the cell flashes, with its
    italics alone marking it. Pick: the second. While the cell flashes, a pencil
    letter has the same `color` as a normal letter in that state; outside a flash,
    the colour rule and the 4.5:1 grey are unchanged. The italics hold in every
    state, the flash included (AC-7).

## Open questions

None.
