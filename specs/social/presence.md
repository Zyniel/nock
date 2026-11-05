---
area: social
file: presence
status: done
---

# social/presence - Who is here and where

## Purpose

The players of a room see who is active, idle or away, and where each other
player works on the grid.

## Depends on

- `lobby/joining.md`: players, colours, nicknames and their display, the
  roster's rows and order, resume and seat back.
- `platform/realtime.md`: the messages and who receives each, the silence
  time-out; the resume window is `platform/reconnection.md`.
- `gameplay/board.md`: a selection's word, the « Mots des autres »
  and « Accessibilité » switches; the grid is `gameplay/viewport.md`.

## Rules

### Presence states

1. A player is active, idle or disconnected. Input is any valid message of a
   joined player, refused or not (`platform/realtime.md` rule 12), except
   `join` and `ping`; an invalid frame is only a sign of life (rule 5 there).
   Each input restarts the player's idle count; an idle player's input first
   makes them active with one `player_state_changed`, ahead of the message's
   own events.
2. The room's check each second (`platform/realtime.md` rule 16) turns idle,
   in roster order, each active player whose last input is 120 seconds old or
   more, with one `player_state_changed` `idle`. A disconnected player never
   turns idle: only a resume makes them active.
3. A resume (`lobby/joining.md` rule 6) restarts the idle count, and makes an
   idle or disconnected player active with one `player_state_changed`.
4. `player_state_changed` is a logged event: every joined socket gets it, the
   player's own included.
5. Each roster row writes its player's state, `presence.active` (« actif »),
   `presence.idle` (« inactif ») or `presence.disconnected` (« déconnecté »),
   and follows `player_state_changed` in place, the order unchanged. How a
   state shows without colour: `product.md` rule 15.
6. The Salon's stream (`social/chat.md`) gets one line per `player_joined`,
   `feed.player_joined` (« {name} a rejoint le salon »), and per
   `player_left`: reason `left`, `feed.player_left` (« {name} a quitté le
   salon »); `removed`, `feed.player_removed` (« {name} a été retiré du
   salon »); `timed_out`, `feed.player_timed_out` (« {name} est parti
   (déconnecté trop longtemps) »). `{name}` is the nickname the page knows
   then, a departed player's included, shown as `lobby/joining.md` rule 3
   says, as text; an unknown player is `feed.someone` (« Quelqu'un »).
   `player_state_changed` and `selection_moved` add no line.

### Selections

7. A `select_cell` on a letter cell sets the sender's selection (cell and
   direction) and goes to the other players only, as `selection_moved` with
   the same values, even when it repeats the current one. It is never logged
   and takes no seq. On any other position it is `not_a_letter_cell` to the
   sender alone, and their selection stays.
8. An idle player keeps their selection. A disconnection clears it: the others
   get `player_state_changed` `disconnected`, then, when there was one,
   `selection_moved` with `null`. A snapshot carries each player's state and
   selection, so a joiner sees the current selections.
9. The page keeps each other player's last selection, from the snapshot and
   from `selection_moved`, and drops it on `null`, on that player's
   `player_state_changed` `disconnected` and on their `player_left`; it
   ignores a `selection_moved` for a player it holds as disconnected. It never
   shows one for itself, even one the snapshot or an event gives it.
10. A kept selection shows as that player's cursor on its cell and a tint of
    its word. A cell shows at most four cursors (`product.md` rule 16); a cell
    in several players' words takes the tint of the first in roster order;
    the tint shows while « Mots des autres » is on. My own selection and word
    keep their own look and never get a cursor; a cell of my word keeps my
    word's look when another player's word holds it too. Each Joueurs row,
    mine included, shows the clue of that player's selected word, none
    without a selection, and follows the selection within 300 ms.

### The grid's room

11. The grid's room: with 8 players and a full stream, in either layout, touch
    or computer, the Salon open or closed, the grid viewport stays at least
    100 px high with the grid inside it at zoom 1, the page does not scroll,
    and the clue bar stays in the window, above the in-app keyboard when it
    shows. A new stream line never moves the grid viewport.

### Look

- Cursors: `_design/cells.md`, « Other players on a cell » and « Player
  icons »; tints and my selection: « Letter cell backgrounds ».
- Roster rows and state words: `_design/room.md`, « Salon ». Player colours:
  `_design/foundation.md`, « Player colours ».

## Acceptance criteria

- **AC-1** With Ana's last input at t, the check at t + 119.9 changes nothing
  and the one at t + 120 makes her idle; in a room of two, each player gets
  the other's `player_state_changed` `idle`. Her `select_cell` at t + 130
  sends `player_state_changed` `active` before the `selection_moved`; a `ping`
  or a `join` leaves her idle, while an edit, an erase, a pencil letter, its
  confirmation, an undo, a check, a reveal, a vote, even refused (a vote with
  none open), a flag, a chat line or a lock wakes her ahead of its own events.
  (← 013 AC-1)
- **AC-2** A disconnected player stays disconnected through every check. Idle
  Ana resuming on a new socket (her old one closed with 4001) or after a
  disconnection is active in her snapshot, the others get
  `player_state_changed` `active`, and her idle count starts again.
  (← 013 AC-1)
- **AC-3** A snapshot with Ana active, Bob idle and Cleo disconnected shows
  three roster rows in that order, in three different colours, reading
  « actif », « inactif » and « déconnecté »; `player_state_changed` `active`
  for Bob turns his row to « actif », and `idle` for Ana hers to « inactif »,
  the order unchanged, and no stream line. In the stream, Cy joining then
  leaving reads « Cy a rejoint le salon » then « Cy a quitté le salon », Cy
  removed « Cy a été retiré du salon », Bob timed out « Bob est parti
  (déconnecté trop longtemps) », and an unknown p9 timed out « Quelqu'un est
  parti (déconnecté trop longtemps) ». (← 013 AC-1, 013 AC-5)
- **AC-4** Over the socket, 100 `select_cell` of A on random letter cells
  reach B as `selection_moved` with the same values within 100 ms at the p95,
  and A gets none; a `select_cell` on (0, 0) gets `not_a_letter_cell` to A
  alone and A's selection stays; the same selection sent twice is relayed
  twice and takes no seq. (← 013 AC-2)
- **AC-5** A's selection on (3, 2) down is in a newcomer's snapshot; when A's
  socket closes, or A goes silent, B gets `player_state_changed`
  `disconnected` then `selection_moved` `null`, and a later snapshot shows A
  disconnected with no selection; A idle keeps hers. (← 013 AC-2)
- **AC-6** Within 300 ms of `selection_moved` for Bob (colour 3) on (2, 2)
  across, (2, 2) shows one cursor in Bob's colour, top-left, and exactly
  (2, 1) to (2, 4) are in his word, tinted unlike (1, 1); down from (4, 4) it
  is column 4. Bob idle keeps both; `null`, Bob disconnected or Bob leaving
  removes both; a selection in the snapshot shows the same. Bob's Joueurs row
  reads « Sans contenu » within 300 ms of his move across row 2, and no clue
  after `null`, nor for a player with no selection. (← 013 AC-2, 043 AC-19)
- **AC-7** Bob (across) then Cleo (down) on (1, 1): both cursors show, Bob's
  top-left and Cleo's top-right, each in its colour, and (1, 1), in both
  words, takes Bob's tint; in the reverse order Cleo is top-left, the tint
  still Bob's. When I select (1, 1) both stay; when Bob clears his, Cleo's
  stays. (← 013 AC-3)
- **AC-8** With Bob on (2, 2), my click on (3, 1) gives it my selection's
  look, unlike (2, 2) and the tinted (2, 3), and no cursor; no cursor ever
  shows for me, from the snapshot or from a `selection_moved` naming me; Bob's
  word down through (3, 2) leaves that cell in my word's look. (← 013 AC-4)
- **AC-9** With 8 players and 100 stream lines, at each window size, touch or
  computer, after a tap on (3, 1), with the Salon closed then open on
  « Discussion », rule 11 holds, and in the phone layout the grid viewport
  does not move when the Salon opens. Without a tap, the viewport keeps its
  box with 0 to 3 stream lines, and the stream list is as tall with 3 as with
  100. (← 013 AC-6)

## Edge cases

- A disconnected player has no cursor and does not count among a cell's four
  (AC-6; `product.md` AC-10).
- A selection is lost on a server restart, since it is never logged
  (`platform/server.md`).

## Out of scope

- The stream's order, caps and scroll, and its host, lock and settings
  lines: `social/chat.md`. Its lines of checks and reveals:
  `gameplay/hints.md`; of votes: `gameplay/votes.md`. The Joueurs tab's layout: `client/room.md`; the Menu:
  `client/menus.md`. Changes while away: `social/catch-up.md`. The recap's
  player marks: `gameplay/results.md`.
- A letter's author and the « Auteurs » mode: `social/authorship.md`.
- Cursor trails, typing indicators, avatars; a disconnected player's
  selection.

## Code

- `src/nock/room.py`: input and idleness (`handle_message`, `tick`),
  `select_cell`, `disconnect_player`; `RoomConfig` holds the idle delay.
- `web/src/lib/remoteSelections.ts`, `GridViewport.svelte`, `LetterCell.svelte`:
  cursors, tints; `roomSession.ts`: states and selections kept;
  `PlayersPanel.svelte`: state words, current clue; `activityFeed.ts`: stream
  lines; `RoomPage.svelte`: the grid's room.
- Tests: `tests/test_spec_013_ac01*` to `ac06*`, `tests/spec013_harness.py`.
