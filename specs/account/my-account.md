---
area: account
file: my-account
status: done
---

# account/my-account - The account sheet and page

## Purpose

A player opens « Compte » in a room or on the catalogue to ask for a sign-in
link, and manages the account on « Mon compte » (`/account`): signing in from
the link, back to the room, signing out, deleting. The device keeps the seats
the account brings and forgets them when the account leaves it.

## Depends on

- `account/account.md`: accounts on or off, the status, the link, the sign-in,
  the sign-out and the account's rooms that the sheet and the page call.
- `lobby/joining.md`: the device's identities, the seat a device takes itself.
- `gameplay/history.md`: `nock.history`, whose records a sign-out removes.

## Rules

### Status and the device's identities

1. The room and catalogue pages ask `GET /api/account` once when they load
   and show account controls only on a 200; the account page asks it at load
   unless the fragment holds a link token (rule 4). Signed in, a room page
   sends one `PUT` with its code and its first snapshot's token
   (`account/account.md` rule 11); the catalogue, before « Mes salons » asks,
   and the account page after a sign-in store each identity the account lists
   (`account/account.md` rule 12) whose code has none on the device
   (`lobby/joining.md` rule 8), never replacing one, and add its code to
   `nock.account_rooms`, a JSON array of strings, each read as a code, that
   only the account code reads; anything else, an array with any item that is
   not a string included, reads as empty.

### The account sheet and page

2. « Compte » opens the sheet: in a room from the Menu (`client/menus.md`); on
   the catalogue from the top bar, whose button's `aria-expanded` follows the
   sheet. A modal dialog named by its heading: focus goes to the address
   field, else its first control, and stays inside; Escape, « Fermer » or the
   backdrop, on a press and its release both on it, in a room or on the
   catalogue, close it and focus « Menu » or « Compte ». Signed out it shows
   `account.dialog_heading`, `account.dialog_intro` in a room or
   `account.signed_out_intro` outside, and the e-mail form; signed in
   `account.signed_in_heading`, `account.signed_in_as` and « Gérer mon
   compte » to `/account`.
3. The e-mail form (sheet and page) has the field `account.email_label` (type
   e-mail, the browser's address autocomplete) and the button `account.send`,
   disabled while waiting. It sends the typed address unchecked by the
   browser, with the page's room key in a room, else `"room": null`
   (`account/account.md` rule 6). 202: `account.sent`, a status. 422:
   `account.error.email`, the field marked invalid; 429:
   `account.error.too_many`; else `account.error.send`; each an alert that
   describes the field. A new submit clears the last answer.
4. `/account` is one card « Mon compte », in one state: `loading` (title
   only) until `GET /api/account` answers, then `signed_in`, `signed_out`
   (`account.signed_out_intro`, the form) or `error`
   (`account.error.generic`), also for a failed sign-out or deletion. A
   fragment of 43 URL-safe characters, at load or later, is dropped from the
   URL, then used (`account/account.md` rule 8): `signing_in`
   (« Connexion… »), then `signed_in` on a 200, `link_invalid` on a 404
   (`account.link_invalid` above the form), else `error`.
5. Signed in: `account.signed_in_as`; « Retourner au salon <code> » to
   `/r/<code>` after a sign-in with a `room_code`; « Se déconnecter », ending
   on `signed_out`; « Supprimer mon compte », a disclosure of
   `account.delete_warning`, « Supprimer définitivement », which alone sends
   `DELETE /api/account`, and « Garder mon compte », which closes it and
   focuses the disclosure. A 204 ends on `deleted`: `account.deleted` and
   « Voir les grilles » to `/`. Before it shows `signed_out` or `deleted`, a
   204 removes, for each code of `nock.account_rooms`, its identity,
   `nock.room.<CODE>` and each item of `nock.history` whose `code` is one of
   those codes, then the list and
   `nock.account_progress` (`content/cards.md` rule 2); a seat the device took
   itself, and `nock.progress`, stay. Every other item of `nock.history` stays
   as stored and in its order, one `gameplay/history.md` rule 2 ignores
   included. A failed sign-out or deletion removes nothing.

### Look

- The sheet: `_design/room.md` « Room sheets: host settings and account ».
- The catalogue's « Compte »: `_design/pages.md` « Catalogue ».
- The account page and its deletion: `_design/pages.md` « Plain pages:
  account, shared recap, operator ».
- Its lines: `_design/pages.md` « States: opening, loading, empty, error ».

## Acceptance criteria

- **AC-1** Device 1, as Ana in a room, signs in from « Compte »: `/account`
  loses the fragment and offers « Retourner au salon »; her room keeps her
  seat, colour and letters. Device 2 signs in from `/account` (`"room":
  null`) and enters as Ana with no form, replacing device 1
  (`lobby/joining.md` rule 11); its « Mes salons » lists the room, whose page
  sends one `PUT` after its first snapshot. A device holding Bob's identity
  there keeps it. On an `/account` already showing signed out, a link token
  set as the fragment, with no reload, leaves the URL and signs in.
  (← 033 AC-2, 033 AC-11)
- **AC-2** « Compte », in the room Menu inside every supported window or a
  catalogue top-bar button, shows the focus ring from the keyboard
  (`product.md` rule 14); Enter opens the sheet on the field, and
  Escape focuses « Menu » or « Compte ». In a room, Tab and Shift+Tab stay
  in the sheet, a 202, 422, 429, 503 and 500 show rule 3's lines, and the
  open sheet keeps `product.md` rules 19 and 20. On the catalogue,
  `lea@example.org` goes with `"room": null` and shows the 202 line, and a
  phone's bottom sheet closes on a press on the backdrop. A 404: no
  « Compte ». (← 033 AC-9, 046 AC-3)
- **AC-3** Each state of rule 4 shows its line: after a 404,
  `account.link_invalid` above the form. A refused address marks the field; a
  new submit answered 202 unmarks it and shows `account.sent` with the typed
  address; a 429 leaves it unmarked. The lines follow "Look". In the states
  signed out, signed in, stale link and deleted the page keeps `product.md`
  rules 19 and 20; signed out and signed in, it has no sideways scroll at any
  supported window. (← 048 AC-5, 033 AC-9)
- **AC-4** Signed in after a link from `K7QM2X`, the card holds « Connecté
  avec <address> », « Retourner au salon K7QM2X » and the two actions,
  collapsed; asked, the deletion's warning and buttons sit in the card, and
  « Garder mon compte » leaves the focus on « Supprimer mon compte »; the
  confirm sends one `DELETE /api/account`. Signed in, no sideways scroll at
  320 by 568, a long address included; with the deletion asked, nothing on
  the page is red. (← 048 AC-3, 048 AC-4, 033 AC-5)
- **AC-5** Ana's account lists R and T; her device holds its own seat in T,
  `nock.room.R` and history records of R and T. She signs in from `/account`
  (which stores R), her account links S from another device, and `/` loads
  (which stores S): the device holds R's and S's identities, T's unchanged.
  « Se déconnecter », answered 204, shows `signed_out`; the device then holds
  no identity, room record or history record of R or S and no
  `nock.account_rooms`, T's identity and its history record stay, and « Mes
  salons » on `/` lists T alone.
- **AC-6** On AC-5's device before the sign-out, « Supprimer définitivement »,
  answered 204, shows `deleted` and leaves the device as AC-5's sign-out
  does.
- **AC-7** On AC-5's device before the sign-out, a sign-out answered 500,
  or a deletion answered 500, shows `account.error.generic`, and every
  identity, room record, history record and `nock.account_rooms` stays as it
  was.
- **AC-8** In a room at 1280 by 720 and on the catalogue at 360 by 740, with
  `lea@exa` typed in the account sheet, a press in the field released on the
  backdrop leaves the sheet open with `lea@exa` still typed; a press and its
  release both on the backdrop close it.
- **AC-9** Ana signed in, `GET /api/account/progress` answering `{}`, the
  device holding `nock.progress` `{"1": "finished"}` and
  `nock.account_progress` `{"1": "started", "2": "finished"}`: `/` shows
  cards 1 and 2 « Terminée ». After « Se déconnecter »
  answered 204, or « Supprimer définitivement » answered 204, the device holds
  no `nock.account_progress`, `nock.progress` is unchanged, and `/` shows
  card 1 « Terminée » and card 2 no pill. After either answered 500, both
  keys are as they were.
- **AC-10** The device holds `nock.account_rooms` `["RRRRRR", 1]`, an
  identity, a room record and a history record of `RRRRRR`. « Se
  déconnecter », answered 204, shows `signed_out`; the identity, room record
  and history record of `RRRRRR` stay, and the device holds no
  `nock.account_rooms`.
- **AC-11** The device holds `nock.account_rooms` `["RRRRRR"]` and
  `nock.history` holding, in order, a record of `RRRRRR`, `{"code":
  "RRRRRR", "grid": "two"}`, a record of `TTTTTT`, `{"code": "UUUUUU",
  "grid": "two"}` and `null`. After « Se
  déconnecter » answered 204, or « Supprimer définitivement » answered 204,
  `nock.history` holds the record of `TTTTTT`, `{"code": "UUUUUU", "grid":
  "two"}` and `null`, in that order.

## Edge cases

- A seat the device took itself in a room the account also lists stays
  through a sign-out (AC-5).
- A mark set signed out stays through a sign-out, even on a grid the account
  also marked (AC-9).
- A `nock.account_rooms` with any item that is not a string names no room
  (AC-10).
- History items of other rooms that the history ignores stay through a
  sign-out (AC-11).

## Out of scope

- The routes the sheet and the page call, the session, the account's rooms:
  `account/account.md`. `DELETE /api/account` and the erasure it starts:
  `account/erasure.md`.
- The Menu and its popover rules: `client/menus.md`. « Mes salons »:
  `lobby/summaries.md`.
- Forgetting on the device a seat whose room the summaries no longer return;
  forgetting the account's seats when a session expires with no sign-out
  (they stay until the next sign-out on that device).

## Code

- `web/src/lib/account.ts`, `AccountDialog.svelte`, `AccountEmailForm.svelte`,
  `AccountPage.svelte`, `RoomMenu.svelte`, `CataloguePage.svelte`,
  `RoomPage.svelte` (its status and its `PUT`), `FocusableLink.svelte` (their
  links), `wideWindow.ts` (the catalogue page's wide-window test).
- Tests: those of the pointers (033 AC-2, AC-5, AC-9, AC-11; 046 AC-3; 048
  AC-3 to AC-5), in `tests/test_spec_NNN_*`; `tests/test_my_account_*` (AC-1
  for its open page, AC-5 to AC-11).
