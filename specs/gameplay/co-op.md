---
area: gameplay
file: co-op
status: done
---

# gameplay/co-op - Shared letters, same-cell conflicts and pencil letters

## Purpose

The players of a room fill one grid together. A letter shows at once on the
typer's page and reaches the others within a fraction of a second. When two
players write in one cell, the last edit the server receives wins, and the player
whose letter was replaced sees the cell flash. A pencil letter marks a guess as
uncertain until any player confirms it.

## Depends on

- `gameplay/board.md`: letter cells, selection, typing and erasing, the in-app
  keyboard.
- `platform/realtime.md`: the edit messages and errors, the stale rule, the edit
  rate, reconnection and the resend of pending edits.
- `gameplay/rules.md`: `grid_full_wrong`, `grid_solved` and the solved grid's
  input lock.

## Rules

### The shared grid

1. The server holds the only true grid. An edit is an `edit_letter`, `erase`,
   `pencil_edit` or `confirm_pencil`. The room applies edits one at a time in
   arrival order, and an accepted edit overwrites its cell: the last edit
   received wins.
2. An edit's checks run in this order; the first that fails refuses it:
   1. the edit rate (`platform/realtime.md`): `rate_limited`;
   2. not a letter cell: `not_a_letter_cell`;
   3. a locked cell: `cell_locked`;
   4. the stale rule (`platform/realtime.md`): `stale_edit`;
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

### Pencil mode and confirming

7. Pencil mode is off at each page load. « Crayon » (`pencil.toggle`) in the
   top bar, absent from the phone top bar on any touch screen
   (`client/hud.md` rule 4), and the ✎ key of the in-app keyboard wherever
   the keyboard shows (`gameplay/board.md`) flip the one mode and show it
   pressed; on a touch phone with the keyboard hidden, nothing changes the
   mode. « Crayon » is disabled once the grid is solved.
8. Typing L on a cell that is not locked: if the cell already shows L with the
   mode's pencil flag, nothing is sent; else the cell shows L with that flag at
   once and the page sends `pencil_edit` (mode on) or `edit_letter` (mode off).
   The selection then moves as `gameplay/board.md` says. Erasing is the same in
   both modes. A typed letter or erase is sent without `base_seq`, so it is never
   stale.
9. The confirm item « Confirmer la lettre au crayon » (`pencil.confirm`), named
   by its text alone, is the Aide menu's first item, there only while the
   selected cell shows a pencil letter, confirmed or pending, is not locked and
   the grid is not solved. It
   sends `confirm_pencil` for that cell with the page's seq as `base_seq`, and
   the cell shows the letter as a normal one at once; the selection stays. Any
   player may confirm any pencil letter and becomes its author.

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
    errors leave them. A snapshot keeps them; after a reconnection each is sent
    again as the message of its kind, oldest first, with its recorded seq as
    `base_seq`.
13. When the page applies another player's `letter_changed` on a cell whose
    confirmed letter I wrote, the cell flashes for 1 second in that player's
    colour (colour 0 for a player no longer in the room); a new flash on the cell
    restarts the second. Erases, the same letter, pencil letters and
    confirmations count. My own edits and a `cell_locked` never flash a cell.

### Look

The flash, `_design/cells.md` « Letter cell backgrounds »; pencil, locked and
revealed letters, `_design/cells.md` « Letter marks »; the confirm item,
`_design/room.md` « Aide menu »; the pencil toggle and the ✎ key,
`_design/room.md` « Phone top bar », « Computer top bar » and « In-app
keyboard ».

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
- **AC-10** p1's `pencil_edit` `T` at (1, 0) sends both `letter_changed` seq 3
  with pencil and the cell holds a pencil `T` by p1, as a later joiner's snapshot
  shows; over p2's normal `T` it makes a pencil `T` by p1, and p1's `edit_letter`
  over p2's pencil `T` a normal `T` by p1. A check leaves a pencil letter out; a
  reveal makes it a normal locked letter without author. (← 020 AC-1)
- **AC-11** In pencil mode, `t` at (1, 0) shows a pending pencil `T`, sends one
  `pencil_edit` and moves to (1, 1), and its answer leaves a confirmed pencil
  `T`; with the mode off, `t` sends `edit_letter`. Another player's and a
  snapshot's pencil letters show as pencil letters; live, Ana's pencil `T` shows
  so on Bob's page within 300 ms. A reload turns the mode off. (← 020 AC-1)
- **AC-12** In pencil mode, `t` on a pencil `T` sends nothing and moves on, and on
  a normal `T` sends `pencil_edit`; with the mode off, `t` on a pencil `T` sends
  `edit_letter`; on a locked cell nothing is sent. On a touch screen in the sheet
  layout, the ✎ key turns the mode on. Another player's pencil letter over mine
  flashes. (← 020 AC-1)
- **AC-13** After p1's pencil `T` at (1, 0) (seq 3), p2's `confirm_pencil` gives
  `letter_changed` seq 4, `T`, not pencil, p2, and a normal `T` by p2; p1 may
  confirm its own; on an empty cell or a normal letter it is `stale_edit`. After
  pencil `T` (seq 3) then `A` (seq 4), a confirmation with `base_seq` 3 is
  `stale_edit` and with 4 confirms `A`. Of two confirmations at once, the second
  is `stale_edit`. (← 020 AC-2)
- **AC-14** With p2's pencil `T` at (1, 0) and the page at seq 5, the confirm item
  is absent until (1, 0) is selected; it then sends `confirm_pencil` (1, 0),
  `base_seq` 5, and shows a normal pending `T` with the selection kept; my answer
  confirms it by me, a `stale_edit` brings p2's pencil `T` back. Once the grid is
  solved the item is gone, the toggle disabled, and pencil typing sends nothing.
  Live, Bob confirms Ana's pencil `T` and both pages show a normal `T`.
  (← 020 AC-2, 020 AC-7)
- **AC-15** A `pencil_edit` or `confirm_pencil` at (0, 0) gets
  `not_a_letter_cell`, on a locked cell `cell_locked`, older than another
  player's change `stale_edit` (never for one's own change), on a solved grid
  `grid_solved`; from a sender who is not idle, each leaves the room and the
  edit rate as they were. The rate comes before the lock, a clue cell before
  the solved grid, the lock before the stale rule, the stale rule before the
  solved grid, the solved grid before the missing pencil letter. Both kinds
  share one edit rate with `edit_letter`; a refused one is answered to its
  sender only. (← 020 AC-4)
- **AC-16** With 17 right letters, p2's pencil `T` at (4, 4) gives its
  `letter_changed` then `grid_solved`; a pencil `X` gives `grid_full_wrong`, and
  confirming it only its `letter_changed`; 18 right pencil letters give one
  `grid_solved`, after the last; on the solved grid both kinds get `grid_solved`.
  (← 020 AC-3)
- **AC-17** p1's pencil `T` undone empties the cell; a pencil `B` over p1's normal
  `A`, undone, gives the normal `A` back; p2's confirmation of a pencil `T`,
  undone by p2, gives a pencil `T` by p2. Replaying the log from a new room, and
  saving and loading the room, give the same cells. (← 020 AC-5)
- **AC-18** A pending pencil `T` at (1, 0) is not answered by my `T` without
  pencil, and is by my pencil `T`; a pending confirmation is answered by my
  normal `T` only. A pencil `A` typed offline at (1, 1) and a confirmation of
  (1, 0) are sent again after the reconnection in that order, as `pencil_edit`
  and `confirm_pencil`, `base_seq` 7. (← 020 AC-6)
- **AC-19** At every supported window, on a computer and a touch screen, the
  pencil toggle shown there and the open Aide menu's confirm item are fully on
  screen and can be pressed, and the grid keeps its room with no page scroll.
  Keyboard only, Tab and Enter turn pencil mode on, `t` on (1, 0) sends
  `pencil_edit`, Enter on « Aide » focuses the confirm item and Enter confirms;
  each control shows the focus outline of `specs/product.md`.
  (← 020 AC-7)
- **AC-20** With pencil letters plain, selected, in my word, tinted by a player
  of each colour and flashed by a player of each colour, pencil letters follow
  `_design/cells.md` « Letter marks » in every state, the flash included, and
  the page keeps the contrast baseline of `specs/product.md`;
  the two controls' texts pass its language check. (← 020 AC-7)

## Edge cases

- The same letter from two players: two events, the second sender its author
  (AC-6, AC-7).
- My pending letter outrun by another player's does not flash; once mine is
  confirmed, a later replacement does (AC-7).
- The loser of two confirmations sees the first confirmer's normal letter
  (AC-13, AC-14).
- A refused edit from an idle player still wakes them, `social/presence.md`
  (AC-15).

## Out of scope

- Merging or voting on conflicting letters, a cell lock while someone types,
  unlocking.
- Several candidates in a cell, confirming a word or every pencil letter,
  shortcuts for pencil mode or confirming, remembering pencil mode across
  reloads.
- Typing, selection and the in-app keyboard: `gameplay/board.md`. The top bar and
  the Aide menu: `client/hud.md`. Messages, the stale rule, the edit rate,
  reconnection: `platform/realtime.md`. Undo, the log and the store:
  `platform/server.md`. Locks by checks and reveals: `gameplay/hints.md`.
  Completion: `gameplay/rules.md`. Authors and their colours:
  `social/presence.md`. The relay under a 4G profile: `product.md`.

## Code

- `src/nock/room.py`: `handle_message`'s edit checks, accepted edits and
  confirmations, `_is_filled`.
- `src/nock/hub.py`: the room task, arrival order, delivery to every connection.
- `web/src/lib/roomSession.ts`: confirmed grid, pending edits, `shownCell`,
  answers, flashes (`FLASH_MS`).
- `web/src/lib/RoomPage.svelte`: pencil mode, typing, confirming, flash timers;
  `GridViewport.svelte`: cell marks and the flash; `RoomTopBar.svelte`,
  `AideMenu.svelte`, `InAppKeyboard.svelte`: the pencil controls.
- Tests: `tests/test_spec_015_*`, `tests/test_spec_016_*`,
  `tests/test_spec_020_*`.
