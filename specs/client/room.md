---
area: client
file: room
status: done
---

# client/room - The room panel (« Salon ») and the notes

## Purpose

The Salon is the room's panel, a column beside the grid or a sheet over it:
the progress, the chat stream and the players. While it is closed, « Salon »
tells what is new, and 3-second notes over the grid tell what another player
just did.

## Depends on

- `client/hud.md`: the layouts, the top bar and its « Salon » button, the
  scrim, the play area the Salon column shares.
- `social/chat.md`: the stream's lines, messages, the unread count, the
  message box.
- `social/presence.md`: the Joueurs rows, their states and clues.

## Rules

### « Salon »

1. « Salon » carries the count of unread messages (`social/chat.md` rule 11).
   With none unread, it shows the new-events dot once an event line about
   another player was added to the stream since it last showed, a catch-up line
   (`social/catch-up.md`) included; one's own lines and a closed vote's line
   never count. Showing the stream clears both. « Salon » is named
   `topbar.salon_unread` with the count while the badge shows,
   `topbar.salon_events` (« Salon, nouvelle activité ») while the dot shows,
   else by its label.

### Salon

2. The Salon is an aside (a complementary landmark) named `topbar.salon`,
   hidden while closed; « Salon » opens and closes it and Escape inside
   focuses « Salon ». Sheet layout: a bottom sheet over the play area, moving
   nothing, closed at each load; Escape closes it. Column layout: a column
   right of the play area, which gives or takes its width; open at load unless
   `nock.salon_closed` is `"true"`, which closing it writes and opening it
   removes (storage that throws: open at each load); Escape leaves it open.
3. Opened from « Salon » or a note, it focuses the message box when
   « Discussion » is selected and the box enabled, else the selected tab; the
   column opened at load takes no focus.
4. It holds the progress `salon.progress`: words whose every cell shows a
   letter, pending edits included, over the grid's words. Then the tabs
   « Discussion » (`chat.heading`) and `salon.players_tab` (« Joueurs (n) »,
   n players): only the selected one is a Tab stop, the arrow keys switch;
   « Discussion » at load, the choice kept for the page's life. The stream
   shows while the Salon is open on « Discussion ».
5. « Discussion » holds the stream list, the message box and the chat notes
   (`social/chat.md`). « Joueurs » holds a row per player in snapshot order,
   on two lines (colour, name, tags, the host's buttons; state, then the clue
   of the player's word, `social/presence.md`), then the invitation link
   (`lobby/rooms.md`). A message starts with its author's player dot only
   while the author is a player of the room: a message of someone who left,
   or who never was a player, has none. While « Accessibilité » is on, every
   player dot, in the stream and in the rows, holds that player's icon
   (`product.md` rule 15).

### Notes

6. While the stream is not shown, a note over the grid tells of another
   player's message (`note.message`); a live line of a flag, a reveal, a
   closed vote, a player joining, leaving, removed or timed out, or another
   player's check (its text after its pictogram); one's own reaction
   (`note.own_reaction`). Nothing else: no snapshot, no catch-up line. Notes
   take no room and are hidden from screen readers.
7. A new note replaces the shown one. A note shows 3 seconds, fades (at once
   under reduced motion) and leaves; one showing when the stream opens stays
   its time. A tap on it opens the Salon on « Discussion » and removes it.
   While the vote banner shows, the newest note waits, then shows once the
   banner has gone, unless the stream shows by then or the closed vote's note
   (rule 6) replaces it.
8. `undo.nothing` (« Rien à annuler. ») has a note's look and place, replaces
   any note and shows even with the stream shown; under the vote banner while
   it shows. It has no live role; each time it shows, the status region
   announces it (`client/hud.md` rule 17).

### Look

`_design/room.md`: « Salon »; « 3-second notes »; « Layers » for the sheet
and the scrim. The badge: `_design/foundation.md`, « Components ».

## Acceptance criteria

- **AC-1** Salon closed, Bob's two messages show the badge `2` and name
  « Salon » « Salon, 2 messages non lus »; on a new page his check shows the
  dot, named « Salon, nouvelle activité », then his message the badge instead;
  showing the stream clears both. On « Joueurs » his lines count the same, on
  « Discussion » never, nor Ana's own. A return whose catch-up holds Bob's
  check shows the dot. (← 043 AC-5, 043 AC-17)
- **AC-2** At 1280 by 720 the Salon is open, unfocused. Closing it writes
  `nock.salon_closed`, keeps the cells' size and moves the grid right by half
  the column; reloaded it stays closed; reopened, the key is gone, the message
  box focused, the grid back. Escape in the box focuses « Salon » and leaves it
  open. (← 043 AC-13)
- **AC-3** At 360 by 740 the Salon is closed at load whatever
  `nock.salon_closed` holds; « Salon » opens the sheet focused on the message
  box, grid and clue bar unmoved; Escape closes it and focuses « Salon ».
  (← 043 AC-14)
- **AC-4** With TAMIS and VIDE full and 3 players the Salon reads « 2 / 8
  mots », then « 3 / 8 mots » once AMEN is typed, unanswered; « Discussion »
  is selected beside « Joueurs (3) »; ArrowRight shows « Joueurs », ArrowLeft
  « Discussion »; a join reads « Joueurs (4) ». (← 043 AC-15)
- **AC-5** « Discussion » shows messages and event lines in seq order in one
  list named « Discussion », then the message box and the chat notes. With
  host Ana on MIME, « Joueurs » shows her row with « (vous) », « hôte » and
  « Artiste muet », Bob's with « Couper » and « Retirer » inside it, then the
  link. A message of a player who left has no dot; « Accessibilité » on puts
  each player's icon in every dot. Each follows « Salon ». (← 043 AC-16,
  043 AC-18, 043 AC-19, 043 AC-20, 043 AC-30)
- **AC-6** At 360 by 740, Bob's `IDES ?` shows « Bob : IDES ? » within
  300 ms, still at 2.7 s, gone by 3.7 s; his reveal, then his flag 1 s later,
  replace it; his check makes a note; Ana's message or check, Bob's reaction, a
  snapshot or catch-up lines make none; Ana's `wow` makes « Vous avez réagi :
  😮 ». With the stream shown no message or event line makes one.
  (← 043 AC-26)
- **AC-7** A tap on a note opens « Discussion » and removes it; a note showing
  when « Salon » opens the stream stays its time; reduced motion drops the
  fade. Bob's two messages during a vote make no note; after it only the vote's
  note shows. « Rien à annuler. » shows with the stream shown, and under the
  vote banner, uncovered. (← 043 AC-26)
- **AC-8** Ana presses « Annuler » twice, 1 s apart, with nothing to undo: the
  note « Rien à annuler. » has no live role, and after each press the status
  region reads « Rien à annuler. », having been empty in between.

## Edge cases

- A message wins over the dot (AC-1); a vote never queues notes (AC-7).

## Out of scope

- Dragging the Salon sheet, scrolling to a tapped note's line, announcing
  other players' actions to screen readers.
- The layouts, the top bar, the scrim and the play area: `client/hud.md`. What
  the stream, its lines and the message box do: `social/chat.md`. The Joueurs
  rows' content: `social/presence.md`; the invitation link: `lobby/rooms.md`;
  the host's buttons: `lobby/host.md`. The catch-up lines: `social/catch-up.md`. The
  vote banner: `gameplay/hints.md`.

## Code

- `web/src/lib/RoomPage.svelte` (the Salon's state, the dot, the notes) and
  its parts `Salon`, `PlayersPanel`, `RoomNote` (`.svelte`); `chat.ts` (badge,
  dot); `roomSession.ts` (what makes a note).
- Tests: `tests/test_spec_043_*`, `tests/spec043_harness.py`;
  `tests/test_room_*` for AC-8.
