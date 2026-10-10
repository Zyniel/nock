---
id: "015"
title: Shared letters
status: approved
---

# 015 - Shared letters

Epic E4 Real-time sync (US-4.1) · Release: MVP · Epic depends on: E3
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine (`nock.room`, `nock.hub`, runtime, delivery order, test harness) is defined
in spec 011, joining in spec 012; the messages are those of spec 039; the grid
elements those of spec 006; typing and erasing on the page those of spec 008.

## Goal

As a player, I want my friends' letters to appear as they type, so that the grid feels like one sheet of paper.

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests.

## Public interface

### `nock.room.handle_message`: built by this spec for `edit_letter` and `erase`

```python
# src/nock/room.py (signature fixed in spec 011)
def handle_message(
    state: RoomState,
    player_id: str,
    message: ClientMessage,
    now: float,
    config: RoomConfig = RoomConfig(),
) -> Outcome:
    """Apply one message from the joined player `player_id`."""
```

For `EditLetter(row, column, letter, base_seq)` and `Erase(row, column, base_seq)`
from player `p`, the checks run in this order; the first that fails refuses the
edit (unchanged state, no entry, one `ErrorMessage` in `reply`):

1. (spec 037) rate limit: `rate_limited`.
2. (spec 037) `(row, column)` is not a letter cell of `state.grid` (a clue cell, an
   empty cell, or outside the grid): `not_a_letter_cell`.
3. (spec 016) the cell is locked: `cell_locked`.
4. (spec 017) `base_seq` is not None and the cell changed since then by someone
   else: `stale_edit`.
5. (spec 026) the grid is solved: `grid_solved`.

Until the spec named on a check is built, that check never refuses. This spec
builds check 2 as well, since it needs a letter cell to write in; spec 037 AC-2
tests it.

An accepted edit, with `seq = state.seq + 1`:

- the cell becomes: `letter` = the edit's letter (`None` for `erase`),
  `pencil = False`, `author = p` (`None` for `erase`), `wrong = False`,
  `changed_seq = seq`, `changed_by = p`; `locked` and `revealed` stay `False`;
- (spec 018) `p`'s `last_edit` records the cell as it was before;
- (spec 037) `now` is added to `p`'s `recent_edits`;
- `state.seq = seq`;
- one entry `LogEntry(at=now, event=LetterChanged(seq, row, column, letter, pencil=False, player_id=p))`.

An edit is accepted even when it does not change the cell (the same letter again,
or erasing an empty cell): it still gets its `letter_changed`. Every edit a client
sends therefore gets exactly one answer, either its own `letter_changed` or one
error, in the order sent.

Any message other than an edit changes nothing in this spec (spec 011 rule).

### Server timing

No other code path is added: the room task (spec 011) applies edits in arrival
order and sends each `letter_changed` to every joined connection, the author's
included, through each connection's own queue.

### Client: what the page does with edits

The page already shows a typed letter at once and sends `edit_letter` / `erase`
(spec 008). This spec adds the queue of unconfirmed edits and the application of
`letter_changed`.

- Confirmed grid: the kept snapshot's grid, updated by each applied
  `letter_changed`: the cell's `letter`, `pencil`, `author = player_id` when
  `letter` is not null (else `null`), and `wrong = false`.
- Pending edits: a FIFO list of the edits this page sent (or will send, spec 017)
  and that have no answer yet. Each holds `row`, `column`, `letter` (`null` for an
  erase) and `base_seq` (the page's `seq` when the edit was made; spec 017).
- Shown letter of a cell: the letter of the newest pending edit for that cell if
  there is one, else the confirmed letter. A locked cell (spec 016) always shows
  its confirmed letter.
- Answers, matched in order: an applied `letter_changed` whose `player_id` is the
  page's own `you` removes the oldest pending edit; an `error` whose `code` is one
  of `rate_limited`, `not_a_letter_cell`, `cell_locked`, `stale_edit`,
  `grid_solved` also removes the oldest pending edit (the cell then shows its
  confirmed letter again). Other errors do not touch the queue.
- A `letter_changed` from another player updates the confirmed grid only; a pending
  edit of mine on that cell stays shown until its own answer.

Cell attributes (on the `cell` elements of spec 006):

| Attribute | Value |
| --- | --- |
| `data-letter` | the shown letter, `""` when none (spec 006) |
| `data-unconfirmed` | `true` when the shown letter comes from a pending edit, else `false` |
| `data-author` | the confirmed author's player id, `""` when none |

The room page root's `data-pending` (spec 040) keeps counting buffered events,
not pending edits.

### Test harness

As spec 011. Simulated clients (AC-3, AC-4) are Python threads, each with one
TestClient socket of the same `with TestClient(app) as client` block, each keeping
its own copy of the grid: the snapshot's `grid`, then every `letter_changed`
applied in `seq` order (setting `letter`, `pencil` and `author`). Random choices
use `random.Random(15)`. The registries of AC-1 and AC-3 use
`RoomConfig(max_edits_per_second=1000)` so that spec 037's throttle (built later)
does not refuse the test's edits (spec 011 harness).

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-4.1.1) (WebSocket; browser with live server) A letter typed by one player appears for the others within 300 ms at the 95th percentile on a 4G connection. WebSocket (server relay): clients A and B join a FX-01 room; A sends 200 `edit_letter` messages one after the other on random letter cells, each sent only after A received the `letter_changed` of the previous one; for each, the time from A sending it to B receiving the matching `letter_changed` (same seq order, same cell and letter, `player_id` A) is measured with `time.monotonic()`; the 95th percentile is at most 100 ms and every edit reached B. Browser: two pages on the live server join one FX-01 room as `Ana` and `Bob`; Ana taps (1, 0) and types `TAMIS`; for each letter, Bob's matching cell reaches that `data-letter` within 300 ms of the key press (`expect(...).to_have_attribute(..., timeout=300)`).
- **AC-2** (AC-4.1.2) (browser with mocked socket) My own letter appears at once, before the server confirms it. Given the page joined with a FX-01 snapshot (`you` = `p1`, `seq` 5) and a mock that never answers edits, tapping (1, 0) and pressing `t` gives (1, 0) `data-letter="T"` and `data-unconfirmed="true"` at once and one `EditLetter(row=1, column=0, letter="T")` sent; when the mock then sends `letter_changed` seq 6 for (1, 0) letter `B` from `p2`, the cell still shows `T` with `data-unconfirmed="true"` and `data-author="p2"`; when it sends `letter_changed` seq 7 for (1, 0) letter `T` from `p1`, the cell shows `T` with `data-unconfirmed="false"` and `data-author="p1"`. In a second run, after the page sends `T`, the mock answers `error` with code `cell_locked`: the cell shows its confirmed letter (`""`) with `data-unconfirmed="false"`.
- **AC-3** (AC-4.1.3) (WebSocket, simulated clients) Given 4 simulated clients sending 1,000 random edits on FX-01, when the edits stop, then all clients and the server hold the same grid. Four clients join one FX-01 room; each, in its own thread, sends 250 edits on random letter cells (90 % `edit_letter` with a random letter A to Z, 10 % `erase`) with no pause, while reading its socket. Once every client has received its 250 answers and the server's `room_state(code).seq` has stopped moving, then: each client's grid equals `grid_state(registry.room_state(code))` cell by cell (`letter`, `pencil`, `author`); every client received every seq from its snapshot's `seq + 1` to the final `seq` exactly once, in order; and the room's `seq` equals 4 (joins) plus 1,000.
- **AC-4** (AC-4.1.4) (WebSocket; browser with mocked socket) Edits to different cells never delay or cancel each other. WebSocket: clients A and B each send, at the same time from two threads, 18 edits, one per FX-01 letter cell, A with letter `A` in row-major order and B with letter `B` in reverse order, each on a different cell from the other's at the same index; after both received 36 `letter_changed` events, every cell holds the letter of whichever edit to it came last in seq order, both clients agree with `grid_state`, and no edit got an error. Browser: given the page joined with a FX-01 snapshot (`you` = `p1`) and a pending `T` typed at (1, 0), when the mock sends `letter_changed` for (1, 1) letter `A` from `p2`, then (1, 1) shows `A` with `data-unconfirmed="false"` and (1, 0) still shows `T` with `data-unconfirmed="true"`.

## Edge cases and errors

- Same letter again (AC-2, AC-3): the server answers it with a `letter_changed`
  (the page of spec 008 does not send it, but a simulated client may).
- Erasing an empty cell (AC-3): answered with `letter_changed` with
  `letter: null`; nothing else changes.
- Author of an erased cell (AC-2, AC-3): `None` on the server and `""` on the page.
- Edit on a non-letter cell (AC-3): `not_a_letter_cell`, nothing changes (tested by
  spec 037 AC-2). The simulated clients only pick letter cells.
- Edit before join (AC-3): `not_joined` (spec 040), nothing changes.
- Events received before the snapshot (AC-3): dropped by the client (spec 040);
  every client's first event is its snapshot's `seq + 1`.
- Snapshot after a reconnection (AC-2): pending edits stay pending (spec 017 resends
  them); this spec does not reconnect.
- Errors not about edits (AC-2): `not_host`, `nothing_to_undo`, `invalid_message`
  and the others leave the pending queue unchanged.
- Order of answers (AC-2): an answer always matches the oldest pending edit,
  because the server answers each connection's edits in the order it sent them
  (spec 011 delivery order, one queue per connection).
- 95th percentile (AC-1): the 190th smallest of the 200 relay times.
- Seq count (AC-3): every accepted edit adds exactly one seq; the room's final
  `seq` proves that no edit was dropped or merged.

## Out of scope

- Peer-to-peer sync (epic E4).
- Same-cell conflicts, flashes and locked cells: spec 016.
- Disconnection, reconnection and resending pending edits: spec 017.
- Durable room state and the log on disk: spec 018.
- Pencil letters (`pencil_edit`, `confirm_pencil`): spec 020.
- Showing authors' colours on letters: spec 019.
- Performance under a throttled 4G profile on a phone: spec 036.

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written.
Each one is already part of the spec above. (The `stale_edit` error code named in
check 4 and in the page's answer matching is part of spec 039 since its
reopening, decision 20 there.)

1. "300 ms at the 95th percentile on a 4G connection" (AC-1). A real 4G network
   cannot run in CI. Options: emulate 4G in the browser, or split the budget.
   Pick: split it. The server relay on localhost must stay within 100 ms at the
   95th percentile, leaving 200 ms for the network (two one-way trips of about
   85 ms each under the 170 ms round-trip profile of spec 036); the browser check
   on localhost uses the full 300 ms. Not covered here: a measurement under the 4G
   profile, which spec 036 (which refers to this spec) owns.
2. 1,000 edits (AC-3). Options: Python simulated clients over the real WebSocket,
   or 4 browser pages. Pick: Python clients, which test the server and the event
   order fast and deterministically; the page's own reconciliation is covered by
   AC-2 and AC-4 with a mocked socket. Not covered: four real browser pages under
   that load.
3. Matching answers to edits. The protocol has no message ids (spec 039 out of
   scope). Pick: every edit gets exactly one answer, its own `letter_changed` or one
   of five edit errors, in order, so the page matches them first in, first out.
   This is why an edit that changes nothing still gets a `letter_changed`.
4. Typing ownership. Spec 008 (built before this spec) shows the letter at once and
   sends the edit. Pick: this spec adds only the pending queue, the confirmed grid
   and the answers; spec 008's rules are unchanged.
5. Letter cell check. Spec 037 AC-2 owns it, but an edit must land on a letter cell
   to be applied at all. Pick: built here, tested there.
6. Clearing `wrong`. Spec 023 strikes wrong letters; a new letter in the cell is no
   longer the checked one. Pick: any accepted edit clears `wrong`, on the server and
   on the page.

## Open questions

None.
