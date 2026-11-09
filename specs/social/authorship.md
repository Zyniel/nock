---
area: social
file: authorship
status: approved
---

# social/authorship - A letter's author and the « Auteurs » mode

## Purpose

The players of a room see, when they ask for it, who found each letter: in
« Auteurs » mode each letter is drawn in its finder's ink, with a legend of the
players under the grid.

## Depends on

- `social/presence.md`: the grid's room (rule 11) the legend shares, the
  others' cursors and tints it leaves alone.
- `lobby/joining.md`: players, colours, nicknames and their display, join
  order, resume and seat back.
- `gameplay/co-op.md`: edits, pencil letters, flashes; confirming a pencil
  letter is `gameplay/pencil.md`.

## Rules

### Authorship

1. A letter cell's author is the player of its last `letter_changed` that put
   a letter there: the last writer, the undoer of a letter an undo puts back,
   the confirmer of a pencil letter (`gameplay/pencil.md`). An erase and a
   reveal leave no author; a lock by a check keeps it. The server keeps
   authors by player id through a resume, a time-out and a restart, from the
   log or from a stored snapshot.
2. A cell's finder, on the page, is its confirmed author while the cell shows
   a letter that is not revealed and that author is a player of the room,
   connected or not. A letter by a player who left, timed out, was removed or
   was never known has no finder, so a newcomer in their colour takes none of
   their letters; a player seated back finds their letters again. A letter
   typed and not yet confirmed keeps the cell's confirmed finder, or none.

### Auteurs mode

3. « Auteurs » (`authors.switch`) is the first item of the Menu
   (`client/menus.md`), with the detail `authors.on` (« activé ») or
   `authors.off` (« désactivé »). It is a toggle, never disabled, a solved
   grid included; activating it sends nothing and leaves the Menu open. It
   starts on only when `localStorage["nock.authors"]` is `"true"`; each
   activation writes `"true"` or `"false"` there. When storage throws, it
   starts off and its state lasts the page's life.
4. While on, each letter is drawn in its finder's ink, a letter with no
   finder in plain ink, on any background: a pencil letter keeps its italics,
   a locked letter its weight, a revealed one its weight and notch, and the
   strike of a wrong letter turns plain ink. Nothing else of any cell
   changes; during a flash the letter keeps its finder's ink, whose contrast
   is then not guaranteed (`product.md` rule 19 holds outside a flash). The
   inks follow each `letter_changed`, `cell_locked`, `player_left`,
   `player_joined` and snapshot within 300 ms. While off, a letter's look
   ignores its author.
5. While on, a legend after the grid reads `authors.legend` (« Auteurs : »)
   then each player of the room, the page's own included, connected or not,
   in join order, each nickname in its player's ink, shown as
   `lobby/joining.md` rule 3 says, as text, with no dot or icon, Accessibilité
   on or off. It is hidden from assistive technology and follows
   `player_joined` and `player_left` within 300 ms. While off there is none.
6. The grid gives the legend its room and nothing else moves: the top bar,
   status, keyboard and Salon keep their boxes, the clue bar its width, and
   its box too in the phone layout (in the computer layout the centred block
   of grid, legend, clue bar and status may shift by less than a cell row). A
   legend too long for one line wraps, never wider than the clue bar, and
   gets each further line's room. Where that room would leave the grid
   viewport under `social/presence.md` rule 11's floor, the grid keeps its
   size and the legend lies over the viewport's bottom, letting taps through
   to the cells, over none of the bars, the status, the keyboard or the
   Salon. This is decided again on each change of the window, keyboard,
   Salon, status or legend height: hiding the keyboard gives the room back.
7. The clue bar shows only the clue, mode on or off: nothing names one
   letter's author in words.

### Look

- Inks, the legend, its room and its place over the grid: `_design/cells.md`,
  « Auteurs mode »; its layer: `_design/room.md`, « Layers ». Inks:
  `_design/foundation.md`, « Player colours ».

## Acceptance criteria

- **AC-1** On FX-01, a play by p1 and p2 rebuilt from its log gives each cell
  its live author: a letter written over is the last writer's, an erased or
  revealed cell has none, a checked lock keeps it, an undone letter is the
  undoer's; p1 resumed or timed out keeps its cells; a store reload, from the
  log or a snapshot, gives the same. Over the socket, Ana resumed gets (1, 0)
  as hers and (1, 1) as Bob's, colour 0 kept, and Bob the same after a
  restart; in the browser, Ana's reload keeps the mode on with both inks.
  (← 019 AC-3)
- **AC-2** With empty storage « Auteurs » is off, « désactivé »; a click
  turns it on, « activé », stores `"true"`, keeps the Menu open and sends no
  frame; a reload keeps it on, with the legend; another click turns it off and
  stores `"false"`, and a reload keeps it off; a stored `"yes"` starts it off;
  storage that throws starts it off and it still flips; on a solved grid it
  works. (← 019 AC-2, 045 AC-1)
- **AC-3** With eight players each writing one letter and the mode on, each
  letter is in its writer's ink and the empty cells have no finder; off, all
  are plain ink. Off, Ana's `T` and Bob's `A` look the same, also after on
  then off. On the live server, Ana's page shows her `T` and Bob's `A` in the
  inks of the colours its roster gives them. (← 019 AC-1, 019 AC-2, 045 AC-2)
- **AC-4** Mode on, (1, 2) by p9, never in the room, and the revealed (1, 4)
  are plain ink; within 300 ms of each event, Bob writing over (1, 0) gives it
  his ink, an erase leaves no letter, a reveal plain ink, Bob leaving or
  removed turns his letters plain ink and a newcomer in his colour gets none
  of them, and a past player seated back with colour 2 gets her letter back in
  that ink. A letter I type keeps the cell's confirmed ink, or plain ink,
  until the server confirms it in mine. (← 019 AC-1, 045 AC-3)
- **AC-5** Mode on, a letter locked by a check is bold, a pencil letter
  italic, each in its finder's ink; a revealed letter is bold plain ink with
  its notch; a wrong letter keeps its finder's ink under a plain-ink strike
  whose line and thickness rule do not change. Off, that pencil letter is
  pencil grey and the strike red. (← 045 AC-4)
- **AC-6** With Bob's word tinted and (1, 0) selected, turning the mode on
  changes no cell's background, outline, cursors, reveal notch, catch-up ring
  or arrows; mode on, when another player writes over my letter, the flashing
  cell's letter is in that player's ink. (← 019 AC-1, 045 AC-5)
- **AC-7** Mode on, with eight players, `p2` named `JEAN-LUC` and Cy
  disconnected, the legend comes right after the grid viewport, hidden from
  assistive technology, and reads « Auteurs : » then `Ana`, `Jean-Luc`, `Cy`
  and the five others in join order, each bold in its ink, Accessibilité on
  or off; within 300 ms a player who leaves is dropped and Zoé, joining, is
  last, in her ink; turned off, the legend goes. (← 019 AC-4, 045 AC-6)
- **AC-8** With four short nicknames, on a phone and a computer, the legend
  follows « Auteurs mode » on one line under the grid, and rule 6 holds (the
  clue bar within 5 px vertically on a computer); eight 20-character
  nicknames on a phone wrap it. At 568 by 320 with the keyboard nothing
  moves, the legend lies over the viewport's bottom on the notes' layer, and
  a tap there reaches the cell under it. (← 045 AC-7, 045 AC-8)
- **AC-9** In `social/presence.md` AC-9's room with letters by four players
  and the mode on, at each window size, touch or computer,
  `social/presence.md` rule 11 and rule 6 hold, the legend in the window and
  centred on the grid area. On FX-02 with eight 20-character nicknames, the
  clue bar keeps its width and, on low windows, its height.
  (← 019 AC-4, 019 AC-5, 045 AC-10)
- **AC-10** Mode on or off, a tap on (1, 1) or on (1, 2) leaves only
  « Passoire fine » in the clue bar, no author named. (← 019 AC-4, 045 AC-9)
- **AC-11** Keyboard only, Tab to « Menu » and Enter open it with the focus on
  « Auteurs », first in the Menu and in the window at each size; Enter turns
  it on then off, with `product.md` rule 14's ring. Mode on, the contrast and
  language scans (`product.md` rules 19, 20) find nothing, every ink reaching
  4.5:1 on each cell background outside a flash. `fr.json` holds
  `authors.switch`, `authors.legend`, `authors.on` and `authors.off`, and no
  `authors.selected`. (← 019 AC-5, 045 AC-11)

## Out of scope

- A letter's author in words or for a screen reader; a filter on one player's
  letters; « Auteurs » kept on an account or across devices.
- The Menu: `client/menus.md`. The letters each player is credited with in
  the recap: `gameplay/results.md`.

## Code

- `src/nock/room.py`: each cell's `author`, set by edits, undo, confirmations
  and reveals, rebuilt by `replay`. `src/nock/store.py`: `load_room`, authors
  across a restart, from a snapshot and the log.
- `web/src/lib/roomSession.ts`: each cell's author; `authorsView.ts`: the
  switch's storage, finders, legend names and room; `legendLayout.ts`,
  `playFit.ts` (`legendPlacement`): the legend's room and place;
  `AuthorsLegend.svelte`, `GridViewport.svelte`: the legend;
  `LetterCell.svelte`: inks; `RoomMenu.svelte`: the switch;
  `RoomPage.svelte`: the mode and the legend's room.
- Tests: `tests/test_spec_019_*`, `tests/test_spec_045_*`, their harnesses
  `tests/spec019_harness.py`, `tests/spec045_harness.py`.
