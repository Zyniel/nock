---
area: social
file: presence
status: done
---

# social/presence - Who is here, where, and who wrote what

## Purpose

The players of a room see who is active, idle or away, where each other
player works on the grid, and, when they ask for it, who wrote each letter.

## Depends on

- `lobby/joining.md`: players, colours, nicknames and their display, the
  roster's rows and order, resume and seat back.
- `platform/realtime.md`: the messages and who receives each, the silence
  time-out, the resume window.
- `gameplay/board.md`: the grid, a selection's word, the « Mots des autres »
  and « Accessibilité » switches.

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

### Authorship

12. A letter cell's author is the player of its last `letter_changed` that put
    a letter there: the last writer, the undoer of a letter an undo puts back,
    the confirmer of a pencil letter (`gameplay/co-op.md`). An erase and a
    reveal leave no author; a lock by a check keeps it. The server keeps
    authors by player id through a resume, a time-out and a restart, from the
    log or from a stored snapshot.
13. A cell's finder, on the page, is its confirmed author while the cell shows
    a letter that is not revealed and that author is a player of the room,
    connected or not. A letter by a player who left, timed out, was removed or
    was never known has no finder, so a newcomer in their colour takes none of
    their letters; a player seated back finds their letters again. A letter
    typed and not yet confirmed keeps the cell's confirmed finder, or none.

### Auteurs mode

14. « Auteurs » (`authors.switch`) is the first item of the Menu
    (`client/hud.md`), with the detail `authors.on` (« activé ») or
    `authors.off` (« désactivé »). It is a toggle, never disabled, a solved
    grid included; activating it sends nothing and leaves the Menu open. It
    starts on only when `localStorage["nock.authors"]` is `"true"`; each
    activation writes `"true"` or `"false"` there. When storage throws, it
    starts off and its state lasts the page's life.
15. While on, each letter is drawn in its finder's ink, a letter with no
    finder in plain ink, on any background: a pencil letter keeps its italics,
    a locked letter its weight, a revealed one its weight and notch, and the
    strike of a wrong letter turns plain ink. Nothing else of any cell
    changes; during a flash the letter keeps its finder's ink, whose contrast
    is then not guaranteed (`product.md` rule 19 holds outside a flash). The
    inks follow each `letter_changed`, `cell_locked`, `player_left`,
    `player_joined` and snapshot within 300 ms. While off, a letter's look
    ignores its author.
16. While on, a legend after the grid reads `authors.legend` (« Auteurs : »)
    then each player of the room, the page's own included, connected or not,
    in join order, each nickname in its player's ink, shown as
    `lobby/joining.md` rule 3 says, as text, with no dot or icon, Accessibilité
    on or off. It is hidden from assistive technology and follows
    `player_joined` and `player_left` within 300 ms. While off there is none.
17. The grid gives the legend its room and nothing else moves: the top bar,
    status, keyboard and Salon keep their boxes, the clue bar its width, and
    its box too in the phone layout (in the computer layout the centred block
    of grid, legend, clue bar and status may shift by less than a cell row). A
    legend too long for one line wraps, never wider than the clue bar, and
    gets each further line's room. Where that room would leave the grid
    viewport under rule 11's floor, the grid keeps its size and the legend
    lies over the viewport's bottom, letting taps through to the cells, over
    none of the bars, the status, the keyboard or the Salon. This is decided
    again on each change of the window, keyboard, Salon, status or legend
    height: hiding the keyboard gives the room back.
18. The clue bar shows only the clue, mode on or off: nothing names one
    letter's author in words.

### Look

- Cursors: `_design/cells.md`, « Other players on a cell » and « Player
  icons »; tints and my selection: « Letter cell backgrounds ».
- Inks, the legend, its room and its place over the grid: `_design/cells.md`,
  « Auteurs mode »; its layer: `_design/room.md`, « Layers ».
- Roster rows and state words: `_design/room.md`, « Salon ». Player colours and
  inks: `_design/foundation.md`, « Player colours ».

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
- **AC-10** On FX-01, a play by p1 and p2 rebuilt from its log gives each cell
  its live author: a letter written over is the last writer's, an erased or
  revealed cell has none, a checked lock keeps it, an undone letter is the
  undoer's; p1 resumed or timed out keeps its cells; a store reload, from the
  log or a snapshot, gives the same. Over the socket, Ana resumed gets (1, 0)
  as hers and (1, 1) as Bob's, colour 0 kept, and Bob the same after a
  restart; in the browser, Ana's reload keeps the mode on with both inks.
  (← 019 AC-3)
- **AC-11** With empty storage « Auteurs » is off, « désactivé »; a click
  turns it on, « activé », stores `"true"`, keeps the Menu open and sends no
  frame; a reload keeps it on, with the legend; another click turns it off and
  stores `"false"`, and a reload keeps it off; a stored `"yes"` starts it off;
  storage that throws starts it off and it still flips; on a solved grid it
  works. (← 019 AC-2, 045 AC-1)
- **AC-12** With eight players each writing one letter and the mode on, each
  letter is in its writer's ink and the empty cells have no finder; off, all
  are plain ink. Off, Ana's `T` and Bob's `A` look the same, also after on
  then off. On the live server, Ana's page shows her `T` and Bob's `A` in the
  inks of the colours its roster gives them. (← 019 AC-1, 019 AC-2, 045 AC-2)
- **AC-13** Mode on, (1, 2) by p9, never in the room, and the revealed (1, 4)
  are plain ink; within 300 ms of each event, Bob writing over (1, 0) gives it
  his ink, an erase leaves no letter, a reveal plain ink, Bob leaving or
  removed turns his letters plain ink and a newcomer in his colour gets none
  of them, and a past player seated back with colour 2 gets her letter back in
  that ink. A letter I type keeps the cell's confirmed ink, or plain ink,
  until the server confirms it in mine. (← 019 AC-1, 045 AC-3)
- **AC-14** Mode on, a letter locked by a check is bold, a pencil letter
  italic, each in its finder's ink; a revealed letter is bold plain ink with
  its notch; a wrong letter keeps its finder's ink under a plain-ink strike
  whose line and thickness rule do not change. Off, that pencil letter is
  pencil grey and the strike red. (← 045 AC-4)
- **AC-15** With Bob's word tinted and (1, 0) selected, turning the mode on
  changes no cell's background, outline, cursors, reveal notch, catch-up ring
  or arrows; mode on, when another player writes over my letter, the flashing
  cell's letter is in that player's ink. (← 019 AC-1, 045 AC-5)
- **AC-16** Mode on, with eight players, `p2` named `JEAN-LUC` and Cy
  disconnected, the legend comes right after the grid viewport, hidden from
  assistive technology, and reads « Auteurs : » then `Ana`, `Jean-Luc`, `Cy`
  and the five others in join order, each bold in its ink, Accessibilité on
  or off; within 300 ms a player who leaves is dropped and Zoé, joining, is
  last, in her ink; turned off, the legend goes. (← 019 AC-4, 045 AC-6)
- **AC-17** With four short nicknames, on a phone and a computer, the legend
  follows « Auteurs mode » on one line under the grid, and rule 17 holds (the
  clue bar within 5 px vertically on a computer); eight 20-character
  nicknames on a phone wrap it. At 568 by 320 with the keyboard nothing
  moves, the legend lies over the viewport's bottom on the notes' layer, and
  a tap there reaches the cell under it. (← 045 AC-7, 045 AC-8)
- **AC-18** In AC-9's room with letters by four players and the mode on, at
  each window size, touch or computer, rules 11 and 17 hold, the legend in the
  window and centred on the grid area. On FX-02 with eight 20-character
  nicknames, the clue bar keeps its width and, on low windows, its height.
  (← 019 AC-4, 019 AC-5, 045 AC-10)
- **AC-19** Mode on or off, a tap on (1, 1) or on (1, 2) leaves only
  « Passoire fine » in the clue bar, no author named. (← 019 AC-4, 045 AC-9)
- **AC-20** Keyboard only, Tab to « Menu » and Enter open it with the focus on
  « Auteurs », first in the Menu and in the window at each size; Enter turns
  it on then off, with `product.md` rule 14's ring. Mode on, the contrast and
  language scans (`product.md` rules 19, 20) find nothing, every ink reaching
  4.5:1 on each cell background outside a flash. `fr.json` holds
  `authors.switch`, `authors.legend`, `authors.on` and `authors.off`, and no
  `authors.selected`. (← 019 AC-5, 045 AC-11)

## Edge cases

- A disconnected player has no cursor and does not count among a cell's four
  (AC-6; `product.md` AC-10).
- A selection is lost on a server restart, since it is never logged
  (`platform/server.md`).

## Out of scope

- The stream's order, caps and scroll, and its host, lock and settings
  lines: `social/chat.md`. Its lines of checks, reveals and votes:
  `gameplay/hints.md`. The Joueurs tab's layout: `client/room.md`; the Menu:
  `client/hud.md`. Changes while away: `social/catch-up.md`. The recap's
  player marks: `gameplay/results.md`.
- Cursor trails, typing indicators, avatars; a disconnected player's
  selection; a letter's author in words or for a screen reader; a filter on
  one player's letters; « Auteurs » kept on an account or across devices.

## Code

- `src/nock/room.py`: input and idleness (`handle_message`, `tick`),
  `select_cell`, `disconnect_player`, authors, `replay`; `RoomConfig` holds
  the idle delay. `src/nock/store.py`: authors across a restart.
- `web/src/lib/remoteSelections.ts`, `GridViewport.svelte`: cursors, tints,
  inks; `roomSession.ts`: states and selections kept; `PlayersPanel.svelte`:
  state words, current clue; `activityFeed.ts`: stream lines;
  `authorsView.ts`, `AuthorsLegend.svelte`, `RoomPage.svelte`,
  `RoomMenu.svelte`: the switch, legend and room.
- Tests: `tests/test_spec_013_ac01*` to `ac06*`, `tests/test_spec_019_*`,
  `tests/test_spec_045_*`, their harnesses.
