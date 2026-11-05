---
area: client
file: hud
status: done
---

# client/hud - The room's frame: top bar, clue bar, play area

## Purpose

Every room page frames the grid with the top bar and the clue bar, on a phone
or a computer, never taking the grid's room, and gives the menus and sheets
(`client/menus.md`) their place and the Salon (`client/room.md`) its column or
its sheet.

## Depends on

- `product.md`: the supported windows and the accessibility baselines.
- `gameplay/viewport.md`: the grid and its fit; the selection and the in-app
  keyboard are `gameplay/board.md`.
- `client/room.md`: the Salon's open and closed states, which the layout and
  the play area follow.

## Rules

### Layout

1. Once the room shows (from its opening, `client/shell.md`), the page has the
   column layout when the window is landscape and either at least 900 px wide
   and more than 500 px high, or at most 500 px high while the in-app keyboard
   does not show; the sheet layout otherwise. It follows each resize, rotation
   and change of the keyboard within 300 ms. A change of layout closes the
   menus and the reaction picker; the Salon takes the new layout's state.
2. The phone top bar is used in the sheet layout and in the column layout at
   most 500 px high; the computer top bar otherwise.
3. Document order: the heading `room.heading` (« Salon <code> »), read but not
   seen; the top bar; the Aide menu and the Menu; the connection band; the
   status; the play area (vote banner, notes, grid, clue bar, reaction picker,
   end band, in-app keyboard); the Salon; the scrim; the sheets and the recap;
   the room-gone dialog (rule 16).

### Top bar

4. Phone top bar: the timer slot, « Annuler », « Aide », « Salon », a fourth
   button, « Menu ». On any touch screen the fourth is « Clavier » and the bar
   has no « Crayon »; elsewhere it is « Crayon ». There the ✎ key of the in-app
   keyboard (`gameplay/board.md`) toggles pencil mode, only while the keyboard
   shows: with the keyboard hidden by « Clavier », the player has no way to
   change the mode. Computer top bar: the brand (`client/shell.md` rule 17),
   the timer slot, « Annuler », « Crayon », « Aide », « Salon », « Clavier » on
   a touch screen only, « Menu ».
5. A button is named by its label (`room.undo`, `pencil.toggle`, `topbar.aide`,
   `topbar.salon`, `keyboard.label`, `topbar.menu`), « Salon » as
   `client/room.md` rule 1 says; the brand is the link `topbar.home`
   (« Accueil »). « Aide », « Salon » and « Menu » expose whether what they
   control is open, « Crayon » and « Clavier » whether they are pressed. Short
   of room, the phone bar's buttons shrink equally, never the timer; labels
   stay whole on one line and the page never scrolls sideways.
6. Once the room shows, the timer slot holds the timer or, while the player
   hides it, « Chrono » (`gameplay/rules.md` rule 13).
7. While reconnecting, the connection band `room.banner.offline` shows under the
   top bar and pushes the play area down. The status line is read but not seen
   while joined or reconnecting. Once the room has shown, `not_found` is the
   room-gone dialog (rule 16); any other status is a band under the top bar,
   without the connection band's dot.

### Clue bar

14. The clue bar holds ‹ `clue_bar.previous`, the clue on one line with its
    direction, « Réagir », « Je bloque », › `clue_bar.next`. › does what Tab
    does in the grid, ‹ what Shift+Tab does (`gameplay/board.md`), grid focused
    or not; a pointer press moves no focus. The reaction picker floats over
    the grid's bottom; a reaction pill lies on its clue, and a tap on it
    selects that clue.

### Play area

15. The play area takes what the top bar, bands and Salon column leave: the grid
    viewport, the clue bar, the end band (`gameplay/rules.md` rule 7) and the
    in-app keyboard while it shows. In the sheet layout a menu or the Salon
    moves none of it. Whatever is open, the grid keeps 100 px of height, the
    page never scrolls, and the top bar and the clue bar stay in the window.
    The vote banner is drawn over the Salon sheet and the scrim.

### Room gone

16. Once the room has shown, `not_found` (the 4404 of a deleted room,
    `lobby/lifetime.md` rule 6), joined or reconnecting, closes the menus, the
    Salon sheet, the reaction picker and any other room sheet
    (`client/menus.md` rule 6), takes the connection band away and drops the
    letters waiting to be sent. A modal alert dialog then covers the page,
    named by its title `room.gone.title`
    (« Ce salon n'existe plus. ») and described by
    `room.status.not_found_detail`, with one control, the link `share.home`
    (« Voir les grilles ») to `/`, which takes the focus. The room stays drawn
    under it and inert: Escape, a press outside the dialog and the keys change
    nothing, and Tab and Shift+Tab stay on the link. The page stays until the
    player follows it.

### Other final states

19. Once the room has shown, any other final state (`replaced`, `removed`,
    `locked`, `full`, `throttled`: `platform/reconnection.md` rule 4) drops
    the letters waiting to be sent and the kept undos, checks and reveals, and
    makes the grid read-only: a typed letter or an erase, from the keys or the
    in-app keyboard, changes no cell and sends nothing; « Annuler » and every
    Aide item, the confirm item included, are disabled (`client/menus.md`
    rule 2). The selection still moves.

### Status region

17. From its first paint, in every state, the room page holds one region with
    `role="status"`, read but not seen, kept for the page's life. The messages
    the domains call announced are written to it as text: the connection band
    (`platform/reconnection.md` rule 5), the grid status (`gameplay/rules.md`
    rule 5), `undo.nothing` (`client/room.md` rule 8), `room.share.copied`
    (`lobby/rooms.md` rule 11). The elements that show them have no live role:
    no `role="status"`, no `aria-live`. A message first empties the region,
    then writes its text, which replaces the one there at once, so the same
    message twice is announced twice. The region is empty until its first
    message, and again `MESSAGE_HOLD_MS` (5 s, `StatusRegion.svelte`) after
    its last message was written; each new message starts the 5 s again. The
    vote's region (`gameplay/votes.md` rule 8), the grid's (`product.md`
    rule 17) and the alerts stay as they are.
18. While a room sheet is open (`client/menus.md` rule 6) the page behind it
    is inert, so the sheet holds a region of the same kind, empty at its
    opening and emptied as rule 17 says, and every message goes to it
    instead, the recap's own
    (`gameplay/results.md` rules 9, 12) included; the page's region gets none,
    and gets the messages again once the sheet closes.

### Look

`_design/room.md`: « Which layout »; « Phone and upright tablet (sheet
layout) » and « Computer and landscape tablet (column layout) » for the play
areas, with « Phone top bar », « Clue bar », « Computer top bar » and « Low
column layout »; « Reactions »; « Connection lost »; « Layers ». The end band:
`_design/overlays.md`, « End of grid »; the room-gone dialog, « Room gone ».
Buttons, the brand link: `_design/foundation.md`, « Components »; the focus,
« Focus ».

## Acceptance criteria

- **AC-1** On a computer 900 by 600 is the column layout, 899 by 600, 800 by
  800 and 360 by 740 the sheet; 740 by 360 is the column, but the sheet on a
  touch screen with its keyboard. Resized from 1280 by 720 to 360 by 740 and
  back, the layout follows within 300 ms each way, an open Menu closes and the
  Salon takes each layout's state. (← 043 AC-1)
- **AC-2** On a computer at 360 by 740 the phone top bar reads « Annuler »,
  « Aide », « Salon », « Crayon », « Menu » after the timer; at 1280 by 720 the
  computer one starts with the brand, the link « Accueil » to `/`, which a
  click follows with no question, « Crayon » second; 740 by 360 on a computer
  has the phone one, with no brand. Each follows its design section ("Look").
  (← 043 AC-2, 043 AC-3)
- **AC-3** At 320 by 568 with the timer at `10:00:00`, at 283 by 640, 568 by
  320 and 740 by 360, every button lies in the bar, 40 px wide at least, its
  label whole on one line, the timer on one line clear of « Annuler », with no
  sideways scroll. Joined, « Salon ABC123 » and the status are read but not
  seen. (← 043 AC-4)
- **AC-5** The socket closes: within 5 s the connection band shows under the top
  bar and the grid area moves down; rejoined, both are back. After `removed`,
  « Vous avez été retiré de ce salon. » is a band under the top bar with no
  dot. Both follow « Connection lost ». (← 043 AC-7)
- **AC-16** MIME selected, the clue bar reads ‹, « Artiste muet » ↓,
  « Réagir », « Je bloque », ›; with nothing selected the middle two are
  disabled. With TAMIS full, › selects NAVAL then MIME, ‹ NAVAL; a click on ›
  while typing leaves the focus on the grid. The picker floats over the grid's
  bottom; Bob's reaction is a pill drawn on top of IDES's clue, and a tap on
  the pill selects IDES. (← 043 AC-23, 043 AC-24, 043 AC-25)
- **AC-19** With 8 players, at every window of `product.md` on a computer and a
  touch screen, all closed, the Salon open or a menu open: the grid keeps
  100 px, nothing scrolls, the top bar, clue bar and what is open lie in the
  window, each of their buttons is hit at its centre unless the scrim or the
  Salon sheet covers it, and in the sheet layout the grid viewport stays put.
  Solved, the end band under the clue bar holds « Voir le bilan », which opens
  the recap. (← 043 AC-27, 043 AC-28)
- **AC-20** At 1280 by 720 Tab walks the brand, « Annuler », « Crayon »,
  « Aide », « Salon », « Menu », the grid, the clue bar's buttons, then the
  Salon, each with its ring; at 360 by 740 in the phone bar's order. From the
  grid Escape then Tab reaches ‹, Escape then Shift+Tab « Menu ». Every state
  of the frame passes the scans of `product.md`. (← 043 AC-29, 043 AC-31)
- **AC-21** Joined at 360 by 740 with the Salon sheet open, the room is
  deleted: the sheet closes, no band shows under the top bar, and a modal alert
  dialog named « Ce salon n'existe plus. », described by « Un salon est effacé
  après un certain temps sans modification. », holds the focus on « Voir les
  grilles », a link to `/`. At 1280 by 720 while reconnecting, with `T` typed
  at (1, 0) and not yet answered, the connection band goes, (1, 0) is empty
  and the dialog shows alike. These two dialogs follow « Room gone » and pass
  the scans of `product.md`. At 1280 by 720 with « Réglages de l'hôte » open,
  the settings sheet closes and the dialog shows alike.
- **AC-22** Under the room-gone dialog, with (1, 0) selected, Escape, a press on
  the scrim, Tab and Shift+Tab leave the focus on « Voir les grilles » and the
  dialog open; a typed `A` leaves (1, 0) empty; a press on the link loads `/`.
- **AC-26** With the socket opened but not answered, the room page's first
  paint holds a region with `role="status"`, empty and read but not seen;
  once joined, and again after a socket loss, it is still that element.
  Joined, « Annuler » with nothing to undo makes it read « Rien à annuler. »;
  pressed again 4 s later, it reads « Rien à annuler. » anew, still 4 s
  after that, and is empty 5 s after it read the text anew.
- **AC-27** At 1280 by 720, Ana, host, opens « Réglages de l'hôte », whose
  status region is empty; the socket closes: within 5 s that region reads
  « Connexion perdue. Vous pouvez continuer : vos lettres seront envoyées au
  retour du réseau. » while the page's region stays empty; 5 s after that
  text came, the sheet's region is empty. Once the sheet is closed,
  « Annuler » with nothing to undo makes the page's region read « Rien à
  annuler. », and « Copier le lien » 1 s later makes it read « Lien copié ».
- **AC-28** At 1280 by 720, joined with the empty (1, 0) selected, the socket
  closes with 4001: the band under the top bar reads « Ce salon est ouvert
  dans un autre onglet. », a typed `t` leaves (1, 0) empty, and › still moves
  the selection. After `removed` a typed `t` leaves (1, 0) empty alike.
  Reconnecting with `T` typed at (1, 0) and not yet answered, a rejoin refused
  with `room_locked` leaves (1, 0) empty.
- **AC-29** After a close 4001 with MIME selected, « Annuler » and the Aide
  items « La lettre », « Le mot », « La grille » of « Vérifier » and « La
  lettre », « Le mot » of « Révéler » take the disabled look, and a press on
  any sends nothing; with Bob's pencil `T` at (1, 0) selected, the confirm
  item is disabled alike.

## Edge cases

- A square window is a sheet (AC-1).
- Removed by the host after the room showed: the status band, never the
  room-gone dialog (AC-5).
- A 4404 before the first snapshot: the entry card (`client/shell.md` rule 7),
  not the dialog (AC-21).

## Out of scope

- A question before leaving the room; a brand on the phone top bar, where
  « Retour aux grilles » is the way home.
- Room gone: leaving by itself after a delay; a dialog for a removed player or
  another final status; forgetting the deleted room's stored identity, which
  only a sign-out or deletion forgets, for a seat the account brought
  (`account/account.md` rule 17).
- The Salon, what « Salon » carries while it is closed, the 3-second notes:
  `client/room.md`. « Réagir », « Je bloque », the reactions: `social/chat.md`.
- The menus, the popover rules, the scrim and the room sheets:
  `client/menus.md`.
- What lines and rows do: the domains each rule names. The page before the
  room shows: `client/shell.md`.

## Code

- `web/src/lib/RoomPage.svelte` (layout, play area, room gone),
  `roomOverlays.ts` (what a layout change and the room's deletion close),
  `playFit.ts` (layout, the grid's box, the clue bar's width, the legend's
  place), `StatusRegion.svelte` and `announce.ts` (the status region,
  announced by `RoomPage.svelte`), `GridStatus.svelte` (the grid's completion
  line) and its parts: `RoomTopBar.svelte`, `ClueBar.svelte`,
  `RoomGoneDialog.svelte`, `RoomSheet.svelte` (the room-gone dialog's frame,
  a sheet's region); `windowForm.ts`.
- Tests: `tests/test_spec_043_*`, `tests/spec043_harness.py`,
  `tests/test_hud_*`, `tests/hud_harness.py`.
