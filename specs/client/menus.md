---
area: client
file: menus
status: approved
---

# client/menus - The room's menus, popovers and sheets

## Purpose

From the room's top bar, « Aide » and « Menu » open two menus over the page,
and the Menu opens the room sheets. Each opens, closes and moves the focus the
same way by pointer, touch or keyboard, on a phone or a computer.

## Depends on

- `client/hud.md`: the layouts, the top bar whose buttons open the menus, the
  room-gone dialog that closes them.
- `client/room.md`: the Salon, its sheet and its column, which the popover
  rules share.
- `product.md`: the supported windows and the accessibility baselines.

## Rules

### Menus

1. The Aide menu, a group named `topbar.aide`, holds the pencil confirm and a
   separator while it applies (`gameplay/co-op.md`); then, unless the help mode
   is `none`, « Vérifier » and « Révéler » (`gameplay/hints.md`), each a group
   named by its heading, a separator between; else, when empty, the line
   `aide.empty` (« L'aide est désactivée dans ce salon. »). « Aide » never
   leaves the bar. An item that appears while the menu is open moves no focus.
2. An enabled Aide item closes the menu, focuses « Aide », then sends its
   request once. A disabled item sends nothing and leaves the menu open, as
   does an item disabled while it is open.
3. The Menu, a group named `topbar.menu`, holds in order: the switches
   « Auteurs », « Mots des autres », « Accessibilité » (`social/presence.md`,
   `gameplay/board.md`), each with the detail of its state; « Inviter »
   (`menu.invite`, detail `menu.invite_detail`); « Réglages de l'hôte », for
   the host only (`lobby/host.md`); « Compte » (`account.open`), while
   accounts are on (`account/account.md`); a separator; `timer.hide` or
   `timer.toggle_label`; « Retour aux grilles » (`menu.back`), a link to `/`.
   Details are hidden from screen readers. Following « Retour aux grilles »
   or the brand asks nothing: the page loads `/`, and the player,
   disconnected, keeps the seat, to resume from « Mes salons »
   (`lobby/summaries.md`).
4. A switch flips in place, the Menu open and focused on it. Every other item
   closes the Menu: « Inviter » opens the Salon on « Joueurs » focused on
   « Copier le lien »; « Réglages de l'hôte » and « Compte » open their sheet;
   the timer item hides or shows the timer and focuses « Menu ».

### Popovers

5. A menu's button opens and closes it; opening focuses its first enabled item,
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

### Sheets

6. The room sheets (the host's settings, the account, the recap of
   `gameplay/results.md` rule 9, the room-gone dialog of `client/hud.md`
   rule 16) are modal dialogs named by their title, the focus inside from
   their opening; in the sheet layout the top bar stays seen and inert above.
   Tab and Shift+Tab go round a sheet's controls and never leave it: Tab on
   its last control focuses its first, Shift+Tab on its first its last. The
   host's settings and the account close on Escape, or on a press and its
   release both on the backdrop: a press that starts in the sheet and ends on
   the backdrop, or the reverse, closes nothing. Each close of either focuses
   « Menu » (Escape, the backdrop, « Fermer », « Enregistrer » once it has
   sent the settings, the loss of the host role, `lobby/host.md` rule 8),
   except when the room-gone dialog closes it (`client/hud.md` rule 16).

### Look

`_design/room.md`: « Aide menu »; « Menu », with the scrim; « Room sheets:
host settings and account »; « Layers ». Menus, switches: `_design/foundation.md`,
« Components »; the focus in menus and sheets, « Focus ».

## Acceptance criteria

- **AC-1** With 5 letters and 1 word left, the Aide menu holds « Vérifier »
  (« La lettre », « Le mot », « La grille »), a separator, « Révéler » (« La
  lettre » « 5 restantes », « Le mot » « 1 restant »); with Bob's pencil `T`
  at (1, 0) selected, « Confirmer la lettre au crayon » and a separator come
  first; in mode `none` on an empty cell, only « L'aide est désactivée dans ce
  salon. ». (← 043 AC-8)
- **AC-2** MIME selected, « Le mot » sends one check of MIME, closes the menu,
  focuses « Aide » and keeps the selection; so does each item with its request.
  A disabled « La lettre », or items a vote disables while it is open, send
  nothing and leave it open. (← 043 AC-9)
- **AC-3** The host's Menu reads « Auteurs » « désactivé », « Mots des autres »
  « teintés », « Accessibilité » « désactivée », « Inviter » « lien »,
  « Réglages de l'hôte », a separator, « Masquer le chrono », « Retour aux
  grilles » to `/`; a player who is not host has no « Réglages de l'hôte »;
  with accounts on « Compte » follows it, or « Inviter » for a player who is
  not host. It hangs where its top bar
  form's design puts it. (← 043 AC-10)
- **AC-4** « Accessibilité » turns to « activée », the Menu open and focused on
  it; by keyboard, Enter on « Menu » focuses « Auteurs » and Enter flips each
  switch. « Inviter » opens « Joueurs » focused on « Copier le lien ».
  « Masquer le chrono » puts « Chrono » at the timer's place and focuses
  « Menu ». (← 043 AC-6, 043 AC-11)
- **AC-5** « Aide » or « Menu » opens expanded, with the pressed look, focused
  on its first enabled item; Escape focuses the button; a second press closes.
  At 1280 by 720 a click on (2, 2) closes the Menu and selects (2, 2), the
  Salon column staying open. At 360 by 740 a tap on the scrim closes « Aide »,
  sending and selecting nothing; opening the Menu closes « Aide », opening the
  Salon the Menu or the picker. A closed « Aide » still holds « La grille ».
  (← 043 AC-5, 043 AC-12)
- **AC-6** « Réglages de l'hôte » is a modal sheet named by its title, centred
  at 1280 by 720, a bottom sheet at 360 by 740 that a tap above closes;
  « Enregistrer » sends, closes it and focuses « Menu ». « Compte » opens the
  account sheet alike; Escape focuses « Menu ». Both follow « Room sheets ».
  (← 043 AC-21, 043 AC-22)
- **AC-7** At 360 by 740 with MIME selected, Tab on « Le mot », the last item
  of the open Aide menu, focuses the grid, the menu and the scrim gone; at 1280
  by 720 Shift+Tab on « Auteurs » in the open Menu focuses « Menu », the Menu
  closed. With « La grille » focused in the open Aide menu, a vote that
  disables it leaves the menu open.
- **AC-8** At 360 by 740 with MIME selected and the Salon sheet open,
  Shift+Tab on « Discussion » focuses › of the clue bar, the sheet and the
  scrim gone and « Salon » not expanded. Bob at 360 by 740, the Salon sheet
  open and the focus in its message box, is muted by Ana: the sheet stays open
  with the focus on « Salon », and his next Tab closes it.
- **AC-9** At 1280 by 720 in the host's settings, a press in « Lettres à
  révéler » released on the backdrop, or a press on the backdrop released in
  the sheet, leaves it open with its values; a press and its release both on
  the backdrop close it and focus « Menu ».

## Edge cases

- Help mode `none` keeps « Aide » (AC-1).
- Tab on the Salon sheet's last control leaves the page for the browser and
  closes nothing; the Tab that brings the focus back to the page's first
  control closes nothing either, and the next Tab pressed inside the page
  closes it (rule 5).

## Out of scope

- What items, switches and sheets do: the domains each rule names. The
  Salon's content: `client/room.md`. The layouts, the top bar, the play area
  and the room-gone dialog: `client/hud.md`.

## Code

- `web/src/lib/RoomPage.svelte` (the menus' and sheets' state, the focus after
  an item or a close), `roomOverlays.ts` (the one-overlay rule, the scrim, the
  Tab out), and its parts: `RoomPopover.svelte`, `AideMenu.svelte`,
  `RoomMenu.svelte`, `RoomSheet.svelte` (the sheets' shared dialog: the Tab
  trap, Escape, the backdrop), `HostSettings.svelte` and `AccountDialog.svelte`
  (the two sheets the Menu opens).
- Tests: `tests/test_spec_043_*`, `tests/spec043_harness.py`;
  `tests/test_menus_*` for AC-7 to AC-9, `tests/menus_harness.py`.
