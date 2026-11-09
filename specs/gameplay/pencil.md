---
area: gameplay
file: pencil
status: approved
---

# gameplay/pencil - Pencil mode and confirming

## Purpose

A pencil letter marks a guess as uncertain until any player confirms it. A
player turns pencil mode on to type pencil letters, and confirms one from the
Aide menu.

## Depends on

- `gameplay/co-op.md`: the edits `pencil_edit` and `confirm_pencil`, their
  checks, what they do to the cell (rules 1 to 6), the page's confirmed grid,
  pending edits and flashes (rules 10 to 13).
- `gameplay/board.md`: typing, erasing, where the selection moves, the in-app
  keyboard and its ✎ key.
- `client/menus.md`: the Aide menu that holds the confirm item.

## Rules

### Pencil mode and confirming

1. Pencil mode is off at each page load. « Crayon » (`pencil.toggle`) in the
   top bar, absent from the phone top bar on any touch screen
   (`client/hud.md` rule 4), and the ✎ key of the in-app keyboard wherever
   the keyboard shows (`gameplay/board.md`) flip the one mode and show it
   pressed; on a touch phone with the keyboard hidden, nothing changes the
   mode. « Crayon » is disabled once the grid is solved.
2. Typing L on a cell that is not locked: if the cell already shows L with the
   mode's pencil flag, nothing is sent; else the cell shows L with that flag at
   once and the page sends `pencil_edit` (mode on) or `edit_letter` (mode off).
   The selection then moves as `gameplay/board.md` says. Erasing is the same in
   both modes. A typed letter or erase is sent without `base_seq`, so it is never
   stale.
3. The confirm item « Confirmer la lettre au crayon » (`pencil.confirm`), named
   by its text alone, is the Aide menu's first item, there only while the
   selected cell shows a pencil letter, confirmed or pending, is not locked and
   the grid is not solved. It
   sends `confirm_pencil` for that cell with the page's seq as `base_seq`, and
   the cell shows the letter as a normal one at once; the selection stays. Any
   player may confirm any pencil letter and becomes its author.

### Look

Pencil letters, `_design/cells.md` « Letter marks »; the confirm item,
`_design/room.md` « Aide menu »; the pencil toggle and the ✎ key,
`_design/room.md` « Phone top bar », « Computer top bar » and « In-app
keyboard ».

## Acceptance criteria

- **AC-1** p1's `pencil_edit` `T` at (1, 0) sends both `letter_changed` seq 3
  with pencil and the cell holds a pencil `T` by p1, as a later joiner's snapshot
  shows; over p2's normal `T` it makes a pencil `T` by p1, and p1's `edit_letter`
  over p2's pencil `T` a normal `T` by p1. A check leaves a pencil letter out; a
  reveal makes it a normal locked letter without author. (← 020 AC-1)
- **AC-2** In pencil mode, `t` at (1, 0) shows a pending pencil `T`, sends one
  `pencil_edit` and moves to (1, 1), and its answer leaves a confirmed pencil
  `T`; with the mode off, `t` sends `edit_letter`. Another player's and a
  snapshot's pencil letters show as pencil letters; live, Ana's pencil `T` shows
  so on Bob's page within 300 ms. A reload turns the mode off. (← 020 AC-1)
- **AC-3** In pencil mode, `t` on a pencil `T` sends nothing and moves on, and on
  a normal `T` sends `pencil_edit`; with the mode off, `t` on a pencil `T` sends
  `edit_letter`; on a locked cell nothing is sent. On a touch screen in the sheet
  layout, the ✎ key turns the mode on. Another player's pencil letter over mine
  flashes. (← 020 AC-1)
- **AC-4** After p1's pencil `T` at (1, 0) (seq 3), p2's `confirm_pencil` gives
  `letter_changed` seq 4, `T`, not pencil, p2, and a normal `T` by p2; p1 may
  confirm its own; on an empty cell or a normal letter it is `stale_edit`. After
  pencil `T` (seq 3) then `A` (seq 4), a confirmation with `base_seq` 3 is
  `stale_edit` and with 4 confirms `A`. Of two confirmations at once, the second
  is `stale_edit`. (← 020 AC-2)
- **AC-5** With p2's pencil `T` at (1, 0) and the page at seq 5, the confirm item
  is absent until (1, 0) is selected; it then sends `confirm_pencil` (1, 0),
  `base_seq` 5, and shows a normal pending `T` with the selection kept; my answer
  confirms it by me, a `stale_edit` brings p2's pencil `T` back. Once the grid is
  solved the item is gone, the toggle disabled, and pencil typing sends nothing.
  Live, Bob confirms Ana's pencil `T` and both pages show a normal `T`.
  (← 020 AC-2, 020 AC-7)
- **AC-6** A `pencil_edit` or `confirm_pencil` at (0, 0) gets
  `not_a_letter_cell`, on a locked cell `cell_locked`, older than another
  player's change `stale_edit` (never for one's own change), on a solved grid
  `grid_solved`; from a sender who is not idle, each leaves the room and the
  edit rate as they were. The rate comes before the lock, a clue cell before
  the solved grid, the lock before the stale rule, the stale rule before the
  solved grid, the solved grid before the missing pencil letter. Both kinds
  share one edit rate with `edit_letter`; a refused one is answered to its
  sender only. (← 020 AC-4)
- **AC-7** With 17 right letters, p2's pencil `T` at (4, 4) gives its
  `letter_changed` then `grid_solved`; a pencil `X` gives `grid_full_wrong`, and
  confirming it only its `letter_changed`; 18 right pencil letters give one
  `grid_solved`, after the last; on the solved grid both kinds get `grid_solved`.
  (← 020 AC-3)
- **AC-8** p1's pencil `T` undone empties the cell; a pencil `B` over p1's normal
  `A`, undone, gives the normal `A` back; p2's confirmation of a pencil `T`,
  undone by p2, gives a pencil `T` by p2. Replaying the log from a new room, and
  saving and loading the room, give the same cells. (← 020 AC-5)
- **AC-9** A pending pencil `T` at (1, 0) is not answered by my `T` without
  pencil, and is by my pencil `T`; a pending confirmation is answered by my
  normal `T` only. A pencil `A` typed offline at (1, 1) and a confirmation of
  (1, 0) are sent again after the reconnection in that order, as `pencil_edit`
  and `confirm_pencil`, `base_seq` 7. (← 020 AC-6)
- **AC-10** At every supported window, on a computer and a touch screen, the
  pencil toggle shown there and the open Aide menu's confirm item are fully on
  screen and can be pressed, and the grid keeps its room with no page scroll.
  Keyboard only, Tab and Enter turn pencil mode on, `t` on (1, 0) sends
  `pencil_edit`, Enter on « Aide » focuses the confirm item and Enter confirms;
  each control shows the focus outline of `specs/product.md`.
  (← 020 AC-7)
- **AC-11** With pencil letters plain, selected, in my word, tinted by a player
  of each colour and flashed by a player of each colour, pencil letters follow
  `_design/cells.md` « Letter marks » in every state, the flash included, and
  the page keeps the contrast baseline of `specs/product.md`;
  the two controls' texts pass its language check. (← 020 AC-7)

## Edge cases

- The loser of two confirmations sees the first confirmer's normal letter
  (AC-4, AC-5).
- A refused edit from an idle player still wakes them, `social/presence.md`
  (AC-6).

## Out of scope

- Several candidates in a cell, confirming a word or every pencil letter,
  shortcuts for pencil mode or confirming, remembering pencil mode across
  reloads.
- The rules of the two edits on the server and the page's grid are
  `gameplay/co-op.md` rules 1 to 6 and 10 to 13; AC-1, AC-4 and AC-6 to AC-9
  give their pencil cases, AC-3 the flash's. Typing, selection and the in-app
  keyboard: `gameplay/board.md`. The top bar:
  `client/hud.md`; the Aide menu: `client/menus.md`. Messages:
  `platform/realtime.md`; the stale rule, reconnection:
  `platform/reconnection.md`. Authors and their colours:
  `social/authorship.md`.

## Code

- `src/nock/room.py`: `handle_message`'s `pencil_edit` and `_confirm_pencil`.
- `web/src/lib/RoomPage.svelte`: pencil mode, typing, confirming;
  `roomCommands.ts`: the pencil and confirm messages; `LetterCell.svelte`: the
  pencil mark; `RoomTopBar.svelte`, `AideMenu.svelte`, `InAppKeyboard.svelte`:
  the pencil controls.
- Tests: `tests/test_spec_020_*`.
