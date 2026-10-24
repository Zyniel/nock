---
id: "016"
title: Same-cell conflicts
status: done
---

# 016 - Same-cell conflicts

Epic E4 Real-time sync (US-4.2) · Release: MVP · Epic depends on: E3
The rooms engine is defined in spec 011, edits and the page's pending queue in
spec 015, the grid elements in spec 006, typing in spec 008, player colours in
spec 012. The messages are those of spec 039.

(Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells
(`_design.md` section 6): the flash comes first among a letter cell's
backgrounds, over my selection and the locked grey, drawn as spec 041's
`cell-flash` overlay (the replacer's colour at 38 % over white) under an ink
letter, and a revealed notch turns ink while the cell flashes. No criterion of this
spec changes: AC-2 finds the replacer's colour on `cell-flash`, as spec 041 says.)

## Goal

As a player, I want a clear rule when two of us type in one cell, so that nobody is surprised by a vanishing letter.

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests.

## Public interface

### Server: `nock.room.handle_message`

This spec builds check 3 of spec 015 ("the cell is locked"): an `edit_letter` or
`erase` on a cell whose `CellState.locked` is True is refused with
`ErrorMessage(code=CELL_LOCKED)`; the state is unchanged and there is no entry.
The same refusal applies, when spec 020 is built, to `pencil_edit` and
`confirm_pencil`. An `undo` whose cell is locked is refused by spec 018 with
`nothing_to_undo`.

"Last edit received wins" needs no new code: the room task applies edits one at a
time in arrival order (spec 011), and each accepted edit overwrites the cell
(spec 015).

Who locks a cell: a correct check (spec 023) and a reveal (spec 024), each by a
`cell_locked` event. This spec adds no way to lock a cell; tests seed locked cells
with `registry.add_room(state)`.

### Client

Applying `cell_locked` (spec 039 `CellLocked`) to the kept snapshot: the cell's
`letter` becomes the event's letter, `locked = true`, `revealed` the event's
`revealed`, `wrong = false`, and `author = null` when `revealed` is true (else
unchanged). A locked cell shows its confirmed letter even if a pending edit of mine
targets it; that edit is still answered by the server (`cell_locked` error) and
then leaves the queue (spec 015).

Typing or erasing on a locked cell does nothing and sends nothing (spec 008).
(Note from the lead, 2026-10-15: "sends nothing" leaves aside the heartbeat
`ping` frames of spec 017, which the page may send at any time once the socket
is open.)

Flash: when the page applies a `letter_changed` whose `player_id` is not `you`, on
a cell whose confirmed letter before it was not null and whose confirmed author
was `you`, the cell flashes in the colour of the event's player:

| Attribute on the `cell` | Value |
| --- | --- |
| `data-flash` | the colour index (`0` to `7`) of the player who replaced my letter, for 1,000 ms after the event is applied; `""` otherwise |

During the flash the cell's computed `background-color` (or a full-size overlay
inside it) uses that player's colour from spec 012's palette. (Note from the lead, 2026-10-22: since spec 041 AC-16, the cell's computed `background-color` is white and the colour is a full-size `cell-flash` overlay inside it, at 38 % opacity, so the flash is that colour at 38 % over white, under an ink letter.) A new flash on the
same cell restarts the 1,000 ms. A player not in the roster (gone) flashes in
colour index `0`.

Constant: `FLASH_MS = 1000` in the client.

### Test harness

As specs 011 and 015. WebSocket races (AC-1) use two threads and a
`threading.Barrier(2)` so both clients send at once; the test does not assume which
arrives first, it reads the order from the seqs; its registry uses
`RoomConfig(max_edits_per_second=1000)` (spec 011 harness). Mocked-socket tests build
snapshots with `grid_view(fx01_grid)` and `model_copy`.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-4.2.1) (WebSocket; browser with mocked socket) When two players type in the same cell at once, the edit the server receives last wins and every client shows it. WebSocket: clients A and B in a FX-01 room each send, at the same time, `edit_letter` on (1, 0), A with `A` and B with `B`, 50 times in a row; for each round both clients receive the two `letter_changed` events in the same seq order, and after each round the cell in `room_state` holds the letter of the higher seq, as does each client's grid. Browser: with the page joined (`you` = `p1`, `seq` 5) and a pending `A` typed at (1, 0), when the mock sends `letter_changed` seq 6 (1, 0) `A` from `p1` then seq 7 (1, 0) `B` from `p2`, the cell shows `B`; in a second run with seq 6 `B` from `p2` then seq 7 `A` from `p1`, the cell shows `A`.
- **AC-2** (AC-4.2.2) (browser with mocked socket) The player whose letter was replaced sees the cell flash in the other player's colour. Given the page joined with a FX-01 snapshot whose players are `p1` (`you`, colour 0) and `p2` (colour 3), and whose cell (1, 0) holds `T` with author `p1`, when the mock sends `letter_changed` for (1, 0) letter `A` from `p2`, then (1, 0) gets `data-flash="3"` and its computed background colour equals the computed background colour of `p2`'s `roster-colour` (Note from the lead, 2026-10-22: since spec 041 AC-16, it is the cell's single `cell-flash` element whose computed background colour equals that of `p2`'s `roster-colour`, at `opacity` 0.38 over the cell, whose own background is white; before, the cell's own computed background colour equalled it) (Note from the lead, 2026-10-22, second review of spec 041: the test finds that colour on the cell's `cell-flash` element; spec 041 AC-16 checks that there is one, at 0.38, on a white cell); between 800 ms and 2,000 ms later `data-flash` is `""`. No flash happens (`data-flash` stays `""`) when the replaced letter's author was `p2` and the new letter comes from `p3`, when the cell was empty, or when the new letter comes from `p1`.
- **AC-3** (AC-4.2.3) (Python; WebSocket; browser with mocked socket) A cell confirmed correct by a check or a reveal is locked and rejects edits from everyone. Python: on a FX-01 room whose cell (1, 2) has `letter="M"`, `locked=True`, `handle_message` with `EditLetter(row=1, column=2, letter="X")` or `Erase(row=1, column=2)` from any player returns the same state, no entry and `reply` holding one `ErrorMessage` with code `cell_locked`. WebSocket: in a room added with that cell locked, two players each send `edit_letter` and `erase` on (1, 2): each gets `error` `cell_locked`, nobody receives a `letter_changed`, and `room_state` still holds `M` locked with the same `seq`. Browser: given a snapshot where (1, 2) is unlocked and empty and a pending `X` typed there, when the mock sends `cell_locked` for (1, 2) letter `M`, `revealed` false, the cell shows `M` with `data-locked="true"`; typing `e` on it then sends nothing (Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted); when the mock answers the earlier `X` with `error` `cell_locked`, the cell still shows `M` and `data-unconfirmed="false"`.

## Edge cases and errors

- Same letter from both (AC-1): two `letter_changed` events, the second wins with
  the same letter; the author is the second sender; a flash is shown to the first
  author only if the second sender is another player (spec 019 makes authorship
  visible).
- Erase as a conflict (AC-1, AC-2): an `erase` is an edit; erasing my letter makes
  me see the flash in the eraser's colour.
- Pending edit vs a remote edit (AC-1): if the other player's edit has the higher
  seq, my letter shows until my answer arrives, then the other's letter shows, and
  I see a flash (my confirmed letter, authored by me, was replaced).
- My own letters (AC-2): my edits never flash my cells.
- Locked cells (AC-3): a locked cell keeps `locked` for the rest of the game; the
  MVP has no unlock. A `cell_locked` on a cell that was mine does not flash.
- Revealed cells (AC-3): `cell_locked` with `revealed` true clears the author on the
  page and on the server.
- Undo on a locked cell (AC-3): refused (spec 018 tests it with its own error code
  `nothing_to_undo`, since the undo cannot happen).
- Order of checks (AC-3): spec 015's order applies, so a locked cell is refused
  with `cell_locked` before any `base_seq` (`stale_edit`) or solved check, and an
  edit throttled by spec 037 gets `rate_limited` first.

## Out of scope

- Peer-to-peer sync (epic E4).
- Shared letters: spec 015.
- Disconnection and reconnection: spec 017.
- Durable room state: spec 018.
- Locking by checks and reveals (specs 023, 024): this spec only enforces and shows
  locks.
- Merging or voting on conflicting letters; a per-cell edit lock while someone
  types.
- Showing who last wrote each letter (spec 019).

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written.
Each one is already part of the spec above.

1. "Typing at once" (AC-1). The server cannot know which keystroke was first.
   Pick: arrival order at the room task is the truth (architecture: last edit
   received wins), and the test checks agreement with the seq order rather than a
   given winner.
2. When to flash (AC-2). Options: whenever another player changes a cell I see,
   only when they replace my letter, or also when they replace my pending letter.
   Pick: when another player's `letter_changed` replaces a confirmed letter whose
   author is me, erases included; 1,000 ms, restarted by a new flash.
3. Flash colour check (AC-2). Pick: compare the cell's computed colour with the
   roster swatch of the same player (spec 012), so the palette itself stays the
   implementer's choice.
4. Lock seeding (AC-3). Checks and reveals are built later (specs 023, 024). Pick:
   tests seed locked cells through `add_room` and the mocked `cell_locked` event.

## Open questions

None.
