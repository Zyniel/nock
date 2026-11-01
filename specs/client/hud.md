---
area: client
file: hud
status: approved
---

# client/hud - The room's frame: top bar, menus, sheets, clue bar

## Purpose

Every room page frames the grid with the top bar, two menus, the room sheets
and the clue bar, on a phone or a computer, never taking the grid's room, and
gives the Salon (`client/room.md`) its column or its sheet.

## Depends on

- `product.md`: the supported windows and the accessibility baselines.
- `gameplay/board.md`: the grid, its fit, the selection, the in-app keyboard.
- `client/room.md`: the Salon's open and closed states, which the layout, the
  scrim and the play area follow.

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

### Menus

8. The Aide menu, a group named `topbar.aide`, holds the pencil confirm and a
   separator while it applies (`gameplay/co-op.md`); then, unless the help mode
   is `none`, « Vérifier » and « Révéler » (`gameplay/hints.md`), each a group
   named by its heading, a separator between; else, when empty, the line
   `aide.empty` (« L'aide est désactivée dans ce salon. »). « Aide » never
   leaves the bar. An item that appears while the menu is open moves no focus.
9. An enabled Aide item closes the menu, focuses « Aide », then sends its
   request once. A disabled item sends nothing and leaves the menu open, as
   does an item disabled while it is open.
10. The Menu, a group named `topbar.menu`, holds in order: the switches
    « Auteurs », « Mots des autres », « Accessibilité » (`social/presence.md`,
    `gameplay/board.md`), each with the detail of its state; « Inviter »
    (`menu.invite`, detail `menu.invite_detail`); « Réglages de l'hôte », for
    the host only (`lobby/host.md`); « Compte » (`account.open`), while
    accounts are on (`account/account.md`); a separator; `timer.hide` or
    `timer.toggle_label`; « Retour aux grilles » (`menu.back`), a link to `/`.
    Details are hidden from screen readers. Following « Retour aux grilles »
    or the brand asks nothing: the page loads `/`, and the player,
    disconnected, keeps the seat, to resume from « Mes salons »
    (`lobby/joining.md`).
11. A switch flips in place, the Menu open and focused on it. Every other item
    closes the Menu: « Inviter » opens the Salon on « Joueurs » focused on
    « Copier le lien »; « Réglages de l'hôte » and « Compte » open their sheet;
    the timer item hides or shows the timer and focuses « Menu ».

### Popovers

12. A menu's button opens and closes it; opening focuses its first enabled item,
    else the menu; Escape inside closes it and focuses the button. Column
    layout: a pointer press outside closes it. Sheet layout: while a menu or
    the Salon is open a scrim covers the page under the top bar; a tap on it
    closes them, moving no focus and selecting nothing. A Tab or Shift+Tab
    pressed inside the page that puts the focus on an element outside an open
    menu or the Salon sheet closes it, the focus staying on that element,
    wherever the focus was before: inside it, lost to no element (an item
    disabled under it), or on an element outside it where the page had moved
    it. Losing the focus to no element closes nothing, nor does a focus the
    page moves: after a mute (`social/chat.md` rule 15) the Salon sheet stays
    open with the focus on « Salon », and the next Tab closes it. A focus that
    enters the page from another window or the browser's own controls closes
    nothing by itself. A press follows the rules above, not the focus: a press
    on its own button (« Aide », « Menu », « Salon ») closes it, once. At most
    one of the menus, the Salon sheet and the reaction picker is open; the
    Salon column is apart. A closed menu stays in the page, hidden, with its
    items' states. A menu's place follows the top bar's form; its content
    scrolls inside it, so it stays in the window.

### Sheets, clue bar

13. The room sheets (the host's settings, the account, the recap of
    `gameplay/results.md` rule 9, the room-gone dialog of rule 16) are modal
    dialogs named by their title, the focus inside from their opening; in the
    sheet layout the top bar stays seen and inert above. Tab and Shift+Tab go
    round a sheet's controls and never leave it: Tab on its last control
    focuses its first, Shift+Tab on its first its last. The host's settings and
    the account close on Escape, or on a press and its release both on the
    backdrop: a press that starts in the sheet and ends on the backdrop, or the
    reverse, closes nothing. Each close of either focuses « Menu » (Escape, the
    backdrop, « Fermer », « Enregistrer » once it has sent the settings, the
    loss of the host role, `lobby/host.md` rule 8), except when the room-gone
    dialog closes it (rule 16).
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
    Salon sheet, the reaction picker and any other room sheet (rule 13), takes
    the connection band away and drops the letters waiting to be sent. A modal
    alert dialog then covers the page, named by its title `room.gone.title`
    (« Ce salon n'existe plus. ») and described by
    `room.status.not_found_detail`, with one control, the link `share.home`
    (« Voir les grilles ») to `/`, which takes the focus. The room stays drawn
    under it and inert: Escape, a press outside the dialog and the keys change
    nothing, and Tab and Shift+Tab stay on the link. The page stays until the
    player follows it.

### Look

`_design/room.md`: « Which layout »; « Phone and upright tablet (sheet
layout) » and « Computer and landscape tablet (column layout) » for the play
areas, with « Phone top bar », « Clue bar », « Computer top bar » and « Low
column layout »; « Aide menu »; « Menu »; « Reactions »; « Connection lost »;
« Room sheets: host settings and account »; « Layers ». The end band:
`_design/overlays.md`, « End of grid »; the room-gone dialog, « Room gone ».
Menus, buttons, switches, the brand link: `_design/foundation.md`,
« Components »; the focus in menus and sheets, « Focus ».

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
- **AC-6** With 5 letters and 1 word left, the Aide menu holds « Vérifier »
  (« La lettre », « Le mot », « La grille »), a separator, « Révéler » (« La
  lettre » « 5 restantes », « Le mot » « 1 restant »); with Bob's pencil `T`
  at (1, 0) selected, « Confirmer la lettre au crayon » and a separator come
  first; in mode `none` on an empty cell, only « L'aide est désactivée dans ce
  salon. ». (← 043 AC-8)
- **AC-7** MIME selected, « Le mot » sends one check of MIME, closes the menu,
  focuses « Aide » and keeps the selection; so does each item with its request.
  A disabled « La lettre », or items a vote disables while it is open, send
  nothing and leave it open. (← 043 AC-9)
- **AC-8** The host's Menu reads « Auteurs » « désactivé », « Mots des autres »
  « teintés », « Accessibilité » « désactivée », « Inviter » « lien »,
  « Réglages de l'hôte », a separator, « Masquer le chrono », « Retour aux
  grilles » to `/`; a player who is not host has no « Réglages de l'hôte »;
  with accounts on « Compte » follows it, or « Inviter » for a player who is
  not host. It hangs where its top bar
  form's design puts it. (← 043 AC-10)
- **AC-9** « Accessibilité » turns to « activée », the Menu open and focused on
  it; by keyboard, Enter on « Menu » focuses « Auteurs » and Enter flips each
  switch. « Inviter » opens « Joueurs » focused on « Copier le lien ».
  « Masquer le chrono » puts « Chrono » at the timer's place and focuses
  « Menu ». (← 043 AC-6, 043 AC-11)
- **AC-10** « Aide » or « Menu » opens expanded, with the pressed look, focused
  on its first enabled item; Escape focuses the button; a second press closes.
  At 1280 by 720 a click on (2, 2) closes the Menu and selects (2, 2), the
  Salon column staying open. At 360 by 740 a tap on the scrim closes « Aide »,
  sending and selecting nothing; opening the Menu closes « Aide », opening the
  Salon the Menu or the picker. A closed « Aide » still holds « La grille ».
  (← 043 AC-5, 043 AC-12)
- **AC-15** « Réglages de l'hôte » is a modal sheet named by its title, centred
  at 1280 by 720, a bottom sheet at 360 by 740 that a tap above closes;
  « Enregistrer » sends, closes it and focuses « Menu ». « Compte » opens the
  account sheet alike; Escape focuses « Menu ». Both follow « Room sheets ».
  (← 043 AC-21, 043 AC-22)
- **AC-16** MIME selected, the clue bar reads ‹, « Artiste muet » ↓,
  « Réagir », « Je bloque », ›; with nothing selected the middle two are
  disabled. With TAMIS full, › selects NAVAL then MIME, ‹ NAVAL; a click on ›
  while typing leaves the focus on the grid. The picker floats over the grid's
  bottom; Bob's reaction is a pill drawn on top of IDES's clue.
  (← 043 AC-23, 043 AC-24, 043 AC-25)
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
  and the dialog shows alike. Both follow « Room gone » and pass the scans of
  `product.md`.
- **AC-22** Under the room-gone dialog, with (1, 0) selected, Escape, a press on
  the scrim, Tab and Shift+Tab leave the focus on « Voir les grilles » and the
  dialog open; a typed `A` leaves (1, 0) empty; a press on the link loads `/`.
- **AC-23** At 360 by 740 with MIME selected, Tab on « Le mot », the last item
  of the open Aide menu, focuses the grid, the menu and the scrim gone; at 1280
  by 720 Shift+Tab on « Auteurs » in the open Menu focuses « Menu », the Menu
  closed. With « La grille » focused in the open Aide menu, a vote that
  disables it leaves the menu open.
- **AC-24** At 360 by 740 with MIME selected and the Salon sheet open,
  Shift+Tab on « Discussion » focuses › of the clue bar, the sheet and the
  scrim gone and « Salon » not expanded.
- **AC-25** At 1280 by 720 in the host's settings, a press in « Lettres à
  révéler » released on the backdrop, or a press on the backdrop released in
  the sheet, leaves it open with its values; a press and its release both on
  the backdrop close it and focus « Menu ».

## Edge cases

- A square window is a sheet (AC-1); help mode `none` keeps « Aide » (AC-6).
- Removed by the host after the room showed: the status band, never the
  room-gone dialog (AC-5).
- A 4404 before the first snapshot: the entry card (`client/shell.md` rule 7),
  not the dialog (AC-21).
- Tab on the Salon sheet's last control leaves the page for the browser and
  closes nothing; the Tab that brings the focus back to the page's first
  control closes nothing either, and the next Tab pressed inside the page
  closes it (rule 12).

## Out of scope

- A question before leaving the room; a brand on the phone top bar, where
  « Retour aux grilles » is the way home.
- Room gone: leaving by itself after a delay; a dialog for a removed player or
  another final status; forgetting the deleted room's stored identity, which
  only a sign-out or deletion forgets, for a seat the account brought
  (`account/account.md` rule 17).
- The Salon, what « Salon » carries while it is closed, the 3-second notes:
  `client/room.md`. « Réagir », « Je bloque », the reactions: `social/chat.md`.
- What items, sheets, lines and rows do: the domains each rule names. The page
  before the room shows: `client/shell.md`.

## Code

- `web/src/lib/RoomPage.svelte` (layout, overlays, play area) and its parts:
  `RoomTopBar`, `RoomPopover`, `AideMenu`, `RoomMenu`, `ClueBar`,
  `RoomGoneDialog`, `RoomSheet` (the room sheets' shared dialog) (`.svelte`);
  `windowForm.ts`.
- Tests: `tests/test_spec_043_*`, `tests/spec043_harness.py`,
  `tests/test_hud_*`, `tests/hud_harness.py`.
