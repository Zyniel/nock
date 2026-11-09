---
area: gameplay
file: co-op
status: approved
---

# gameplay/co-op - Shared letters and same-cell conflicts

## Purpose

The players of a room fill one grid together. A letter shows at once on the
typer's page and reaches the others within a fraction of a second. When two
players write in one cell, the last edit the server receives wins, and the player
whose letter was replaced sees the cell flash. A pencil letter is an edit here;
pencil mode and confirming are `gameplay/pencil.md`.

## Depends on

- `gameplay/board.md`: letter cells, selection, typing and erasing, the in-app
  keyboard.
- `platform/realtime.md`: the edit messages and errors; the edit rate is
  `platform/fair-play.md`; the stale rule, reconnection and the resend of
  pending edits are `platform/reconnection.md`.
- `gameplay/rules.md`: `grid_full_wrong`, `grid_solved` and the solved grid's
  input lock.

## Rules

### The shared grid

1. The server holds the only true grid. An edit is an `edit_letter`, `erase`,
   `pencil_edit` or `confirm_pencil`. The room applies edits one at a time in
   arrival order, and an accepted edit overwrites its cell: the last edit
   received wins.
2. An edit's checks run in this order; the first that fails refuses it:
   1. the edit rate (`platform/fair-play.md`): `rate_limited`;
   2. not a letter cell: `not_a_letter_cell`;
   3. a locked cell: `cell_locked`;
   4. the stale rule (`platform/reconnection.md` rule 1): `stale_edit`;
   5. a solved grid: `grid_solved`;
   6. for `confirm_pencil` only, a cell that holds no pencil letter: `stale_edit`.

   A refusal answers its sender alone with one error. It changes no cell, writes
   no event of its own and is not counted in the edit rate; an idle sender is
   still woken first (`social/presence.md`).
3. An accepted edit from player p takes the next seq (after the wake of an idle
   sender) and sends one
   `letter_changed` (seq, cell, letter, pencil flag, p) to every player, p
   included. The cell then holds the edit's letter (none for `erase`, its own
   letter for `confirm_pencil`), the pencil flag for `pencil_edit` only, p as
   author (none when empty), and no wrong strike. The edit counts in p's edit
   rate and becomes p's undo (`platform/server.md`).
4. An edit that changes nothing (the same letter again, erasing an empty cell) is
   accepted too, so every edit gets exactly one answer, in the order sent: its
   `letter_changed` or one error.
5. A pencil letter fills its cell and is compared with the solution like any
   letter, so a `pencil_edit` may be followed by `grid_full_wrong` or
   `grid_solved`, after its `letter_changed` and any flag it clears
   (`gameplay/rules.md`); a `confirm_pencil` never is. These events answer no
   edit.
6. A cell locked by a check or a reveal (`gameplay/hints.md`) stays locked for the
   rest of the game. A check leaves pencil letters out; a reveal replaces a
   pencil letter with a normal one. An undo restores a cell's pencil flag with
   its letter, and the log and store keep it (`platform/server.md`).

### The page's grid

10. The confirmed grid is the snapshot's, updated by each `letter_changed`
    (letter, pencil flag, the event's player as author when there is a letter,
    strike cleared) and each `cell_locked` (its letter, locked, not pencil,
    strike cleared, author cleared when revealed).
11. The pending edits are the page's edits sent and not yet answered, oldest
    first, each with its cell, letter (none for an erase), kind (letter, pencil
    or confirm) and the page's seq when it was made. A cell that is not locked
    shows its newest pending edit, unconfirmed, a pencil letter for kind pencil
    only; otherwise it shows its confirmed letter. Selection jumps (Tab, a clue
    tap) treat the shown letter as the cell's letter.
12. An own `letter_changed` with the oldest pending edit's cell, letter and
    pencil flag answers and removes it; any other `letter_changed` (another
    player's, an undo's) only updates the confirmed grid. An error
    `rate_limited`, `not_a_letter_cell`, `cell_locked`, `stale_edit` or
    `grid_solved` removes the oldest pending edit, whatever its kind; other
    errors leave the pending edits. A snapshot keeps the pending edits; after
    a reconnection each is sent again as the message of its kind, oldest
    first, with its recorded seq as `base_seq`. The server sends
    `rate_limited`, `cell_locked` and `stale_edit` only in answer to an edit;
    `not_a_letter_cell` also answers a `select_cell`, a check or a reveal
    naming a cell that is not a letter cell, and `grid_solved` an undo, a
    check or a reveal on a solved grid; no other message gets any of these
    five codes.
13. When the page applies another player's `letter_changed` on a cell whose
    confirmed letter I wrote, the cell flashes for 1 second in that player's
    colour (colour 0 for a player no longer in the room); a new flash on the cell
    restarts the second. Erases, the same letter, pencil letters and
    confirmations count. My own edits and a `cell_locked` never flash a cell.

### Look

The flash, `_design/cells.md` « Letter cell backgrounds »; locked and revealed
letters, `_design/cells.md` « Letter marks ».

## Acceptance criteria

- **AC-1** Ana types `TAMIS` from (1, 0) and each letter shows on Bob's page
  within 300 ms of her key press; on one machine, the server relays 200
  successive edits from Ana's socket to Bob's within 100 ms at the 95th
  percentile. (← 015 AC-1)
- **AC-2** In an FX-01 room with p1 and p2 at seq 2, p1's `edit_letter` `T` at
  (1, 0) sends both `letter_changed` seq 3, `T`, not pencil, p1, and the cell
  holds `T` by p1; over p2's struck pencil `B` it leaves a normal, unstruck `T`;
  `A`, `A` and three erases each get their own `letter_changed`, in order.
  (← 015 AC-3)
- **AC-3** Four players each send 250 random edits with no pause: once all are
  answered, each player's grid equals the server's cell by cell, each got every
  seq after its snapshot once and in order, and the room's seq is 4 + 1,000 +
  the completion events. (← 015 AC-3)
- **AC-4** Two players write all 18 FX-01 cells at once, `A` in row order and `B`
  in reverse: no error, each player's edits apply in its order, and every cell
  holds its later seq's letter on both and on the server. On the page a pending
  `T` at (1, 0) stays unconfirmed when another player's `A` lands at (1, 1).
  (← 015 AC-4)
- **AC-5** With the page at seq 5, `t` at (1, 0) shows `T` unconfirmed at once and
  sends one `edit_letter`; p2's `B` there at seq 6 leaves my `T` shown,
  unconfirmed, with author p2; my `T` at seq 7 confirms it, by me. With `T`, `A`,
  `M` pending, a `rate_limited` after the `T` answer empties (1, 1), `M` still
  pending, while `not_host` removes nothing. (← 015 AC-2)
- **AC-6** p1 and p2 send `A` and `B` to (1, 0) at once, 50 rounds: both receive
  each round's two events in one seq order, and the server and both hold the
  higher seq's letter. On the page with my `A` pending, my `A` at seq 6 then p2's
  `B` at seq 7 shows `B`; p2's `B` then my `A` shows `A`. (← 016 AC-1)
- **AC-7** With my `T` at (1, 0), me colour 0 and p2 colour 3, p2's `A`
  flashes the cell in colour 3 for about a second; an erase or the same `T` by
  p2 flashes, and a gone player flashes in colour 0; none flashes when p3
  replaces p2's letter, on an empty cell, on my own letter or my still pending
  one, or on a `cell_locked`. (← 016 AC-1, 016 AC-2)
- **AC-8** With (1, 2) holding a locked `M`, `X`, `M` and an erase there from
  either player each get `cell_locked`, ahead of a stale or solved check; the
  seq and cell stay as they were, nobody receives a `letter_changed`, and (1, 1)
  still takes edits. (← 016 AC-3)
- **AC-9** On the page, a `cell_locked` `M` at (1, 2) over my pending `X`
  shows `M` locked; `e`, Backspace and Delete there send nothing; the
  `cell_locked` error answering `X` leaves `M`, confirmed. A revealed lock
  clears the author, a checked one keeps it. (← 016 AC-3)
- **AC-21** On FX-01, a `select_cell`, a check and a reveal of the clue cell
  (0, 0) each get `not_a_letter_cell`; once Ana's `S` has solved the grid, her
  undo, a check of the grid and a reveal of (1, 0) each get `grid_solved`. On
  that solved grid, Ana's `chat`, `react`, `flag`, `vote`, `mute_player`,
  `lock_room`, `change_settings`, `remove_player` of Bob, second `join` and
  `ping` get none of `rate_limited`, `not_a_letter_cell`, `cell_locked`,
  `stale_edit` and `grid_solved`.

## Edge cases

- The same letter from two players: two events, the second sender its author
  (AC-6, AC-7).
- My pending letter outrun by another player's does not flash; once mine is
  confirmed, a later replacement does (AC-7).

## Out of scope

- Merging or voting on conflicting letters, a cell lock while someone types,
  unlocking.
- Pencil mode, the pencil controls and confirming a pencil letter:
  `gameplay/pencil.md`. Typing, selection and the in-app keyboard:
  `gameplay/board.md`. Messages: `platform/realtime.md`; the edit rate:
  `platform/fair-play.md`; the stale rule, reconnection:
  `platform/reconnection.md`. Undo, the log and the store:
  `platform/server.md`. Locks by checks and reveals: `gameplay/hints.md`.
  Completion: `gameplay/rules.md`. Authors and their colours:
  `social/authorship.md`. The relay under a 4G profile: `product.md`.

## Code

- `src/nock/room.py`: `handle_message`'s edit checks and accepted edits,
  `_is_filled`.
- `src/nock/hub.py`: the room task, arrival order, delivery to every connection.
- `web/src/lib/roomSession.ts`: confirmed grid, pending edits, `shownCell`,
  answers, flashes (`FLASH_MS`).
- `web/src/lib/RoomPage.svelte`: typing; `roomCommands.ts`: the edit
  messages; `expiry.ts`: flash timers; `LetterCell.svelte`: cell marks and the
  flash.
- Tests: `tests/test_spec_015_*`, `tests/test_spec_016_*`; `tests/test_co_op_*`
  for AC-21.
