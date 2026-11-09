---
area: platform
file: fair-play
status: done
---

# platform/fair-play - Fair play

## Purpose

No browser receives an answer letter before the room earns it, no player floods
the room with edits, and nothing a player types runs as HTML.

## Depends on

- `platform/realtime.md`: the socket, the messages, the snapshot and its grid
  view, the error codes.
- `gameplay/co-op.md`: the edits and their check order.
- `gameplay/hints.md`: the reveal, which earns a letter at its cell.

## Rules

### Answer-free payloads

1. The server never adds an answer to a payload, HTTP or WebSocket: no key
   `answer` or `solution`, and no letter at a cell before it is earned there,
   by a player's accepted edit at that cell or by a reveal (`gameplay/hints.md`).
   An answer's letters reach a browser only where players put them (accepted
   letters, chat texts, nicknames) or a reveal put them, or by chance in
   random ids, tokens and codes. The snapshot's grid holds clue texts and
   arrows, never answers.

### The edit rate

2. Edits (`edit_letter`, `erase`, `pencil_edit`, `confirm_pencil`) are limited
   to 20 per player in any sliding second; one more is `rate_limited`, and a
   refused edit does not count. The client stays connected. `undo` and
   `select_cell` are not counted.

### Text, never HTML

3. A page inserts every nickname, chat text and clue text as text, never as
   HTML: no `{@html` block in a `.svelte` file under `web/src` (whitespace or a
   line break after `{` included), and none of `innerHTML`, `outerHTML`,
   `insertAdjacentHTML`, `document.write`, `parseFromString`,
   `createContextualFragment`, `setHTMLUnsafe` or `srcdoc` in its `.ts` and
   `.svelte` files.

## Acceptance criteria

- **AC-1** The view of FX-01 has 25 cells in grid order, its 18 letter cells
  empty, its clue at (0, 0) « Passoire fine » then « De la marine »; its JSON
  holds neither `answer` nor `TAMIS`, no snapshot field is named `answer` or
  `solution`, and a clue sent with an `answer` is refused. (← 039 AC-14,
  039 AC-15, 039 AC-16, 039 AC-17)
- **AC-2** 25 edits sent at one instant give 20 `letter_changed`, which the
  other client receives too, and 5 `rate_limited`; the next edit 1 second later
  is accepted, and a second player is never held by the first one's count.
  (← 037 AC-3)
- **AC-3** In a full FX-01 game, with three wrong letters corrected, an erase
  and a late joiner, no frame or HTTP body breaks rule 1, and the late joiner's
  snapshot holds exactly the 9 letters typed before it. (← 037 AC-1,
  040 AC-9)
- **AC-4** Players named `<b>Eve</b>` and `<img src=x>` show in the roster as
  the texts `<b>eve</b>` and `<img Src=x>`, with no `b` or `img` element and no
  dialog; the static scan finds no banned construct. (← 037 AC-4)

## Edge cases

- A typed letter replaced later stays earned at that cell, never at another
  (AC-3); a revealed letter is earned when its `cell_locked` is sent, not
  before (`gameplay/hints.md`).

## Out of scope

- The socket, the messages, the snapshot's hyphen marks, close codes and
  delivery: `platform/realtime.md`. The edit's other checks and their order:
  `gameplay/co-op.md`. Stalled, flooding and oversized sockets: `product.md`.
- Throttling other messages: chat, `social/chat.md`; reactions,
  `social/reactions.md`; checks and reveals, `gameplay/hints.md`; wrong codes,
  `lobby/rooms.md`; `undo`, `select_cell`, ballots and the rest are not limited.
- A Content Security Policy.

## Code

- `src/nock/protocol.py`: `grid_view` and the view's models, without answers.
- `src/nock/room.py`: the rate limit; `RoomConfig.max_edits_per_second`.
- `web/src`: every `.svelte` and `.ts` file, scanned by the tests.
- Tests: `tests/test_spec_037_ac01_*`, `tests/test_spec_037_ac03_*`,
  `tests/test_spec_037_ac04_*`, `tests/test_spec_039_ac14_ac17_*`,
  `tests/test_spec_040_ac07_ac13_*` (its AC-9).
