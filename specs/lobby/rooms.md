---
area: lobby
file: rooms
status: approved
---

# lobby/rooms - Solo start, room creation and invitation

## Purpose

A player starts a grid alone in one tap and invites friends with the room's link.
Each room runs as one task that applies its inputs in order; creations and wrong
codes are limited per address.

## Depends on

- `lobby/joining.md`: joins, identities, the roster, past players.
- `platform/realtime.md`: messages, codes, delivery, resume and time-out.
- `content/library.md`: the catalogue, published grids, `nock.progress`.

## Rules

### Solo start

1. A solo game is a room created from the catalogue with one player; inviting is
   sending its link, and nothing converts when others come.
2. Each catalogue item, on the catalogue page and on `/g/<number>`, has
   « Jouer » (`catalogue.play`). A tap marks the grid `started` in
   `nock.progress` unless it is `finished`, then asks for a room (rule 6). On
   success it writes the room record `{"grid": <number>, "selection": null}`
   and loads `/r/<code>`. On a network error, any other status or an answer
   without a code, it stays, shows `catalogue.play_failed` in that item and
   enables the button again. The button is disabled while the request runs.
   Each tap makes a new room. The button is named « Jouer » and described by
   its card's title (`catalogue.item.number`, `content/library.md` rule 12).
3. The room record `nock.room.<CODE>` is a JSON object with `grid` (the
   catalogue number or null) and `selection`; anything else reads as no
   record, and a rewrite keeps unknown fields. The room page writes the
   selection at each change, creating the record with `grid: null` when there
   is none.
4. After a page load's first snapshot, a saved selection on a letter cell with a
   word in its direction is restored as a tap (it sends `select_cell`); else
   nothing is selected or sent.
5. A `grid_solved`, or a snapshot with `solved: true`, in a room whose record's
   `grid` is a number marks that grid `finished`.

### Creation and codes

6. `POST /api/rooms` with `{"grid_number": N}`, N a whole number from 1, answers
   201 with only `code` and `share_url` (`<base URL>/r/<code>`) when N is
   published, 404 `{"detail": "Not Found"}` when it is unknown or unpublished, and
   422 for any other body (one over the limit: 413 first, `platform/serving.md`
   rule 11). `GET` is 404 JSON, `PUT`, `PATCH` and `DELETE` are 405,
   `POST /api/rooms/` is 404 with no redirect. Only a 201 creates a room. A valid
   session on the request makes its account the room's creator (`lobby/host.md`
   rule 11).
7. A new room has seq 0, no player, empty cells, help mode `free`, a budget of 5
   letters and 1 word, no lock, its catalogue number and its creator, if any.
8. A code is 6 characters drawn with `secrets` from the 32 of
   `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, drawn again while a room has it.

### Wrong-code throttle

9. A socket to a code with no room closes with 4404 and records a failure for its
   peer address. While an address has 10 failures less than 60 seconds old, every
   socket from it closes with 4429 before any message, whatever the code, and
   records nothing. Page loads never count; sockets that arrive at once count one
   after another. Each app keeps its failures in memory and, at each record,
   forgets the addresses with none left in the window. The recap route
   (`gameplay/results.md`) shares them.
10. On 4429 the room page ends on `throttled` with `room.status.throttled`.

### Invitation

11. Once joined, the Salon's Joueurs tab holds, under `room.share.label`, the link
    `<origin>/r/<code>` and « Copier le lien » (`room.share.copy`). A copy writes
    the link to the clipboard and shows `room.share.copied` for 2 seconds,
    with no live role, announced by the status region (`client/hud.md` rule
    17); the button keeps its text. Without a usable clipboard nothing
    changes. Before any snapshot (`not_found`, `throttled`, a refused join) no
    link shows.

### Room engine

12. Each live room is one task applying its inputs one at a time, in arrival
    order, and sending each outcome as `platform/realtime.md` rule 11 says: its
    events, then the reply, then the relayed messages, then the closes; a slow
    socket delays nobody. The task ticks every second while a socket is attached,
    stops with the last one, and when it starts again ticks once before any input.
    A rule (`handle_message`, `tick`, `disconnect_player`) that raises is logged,
    leaves the state as it was, and the room goes on. Each socket is delivered to
    and detached on its own; a player disconnects with their last socket (a resume
    takes over the older one, `lobby/joining.md` rule 6). Once the registry is
    closed, its thread stops and no input runs a rule. A room leaves memory
    when its task ends with no socket open (`platform/server.md` rule 21).

### Creation limit

13. `POST /api/rooms` is limited per client address, signed in or not: the
    address the server sees, as for the sign-in links (`account/account.md`
    rule 6); behind Caddy `compose.yaml` makes it the player's own. After the
    body (422) and grid (404) checks, an address that has created as many
    rooms with a time `t > now - 3600` as the limit (rule 14) gets 429
    `{"detail": "Too Many Requests"}` and no room. Only a 201 counts; requests
    at once count one after another. Each app keeps its counts in memory, from
    zero, and at each count forgets the addresses with none left in the hour.
    The catalogue shows a 429 as any failure (rule 2).
14. The limit is `NOCK_ROOMS_PER_ADDRESS_PER_HOUR`, a whole number of rooms
    from 1 to 10000, default 30: unset or empty, the default; set, ASCII
    digits only, any number of leading zeros, within the bounds. `main()`
    checks it after the five variables of `lobby/lifetime.md` and before the
    account variables, and stops on a refused value (`platform/serving.md`
    rules 6, 10). An app reads it each time it starts and fails its start with
    `SettingsError` on a refused value. `/ops` cannot change it.

### Look

« Jouer » and its error: `_design/pages.md`, « Catalogue ». Joueurs rows and
link: `_design/room.md`, « Salon »; a final status once the room has shown, the
status band of « Connection lost »; before, the entry card of
`lobby/joining.md` rule 11, `_design/pages.md`, « Entry and not-found pages ».

## Acceptance criteria

- **AC-1** On `/` or `/g/1`, one tap on item 1's « Jouer » (FX-01) and nothing
  else reaches `/r/<code>` joined on a 5 × 5 grid with one player and no nickname
  form; tapping (1, 0) and typing `t` then shows `T`. (← 010 AC-1)
- **AC-2** With the creation answered 500, 409 or not at all, the tap stays on
  `/`, shows « Impossible de lancer la partie. Réessayez. », enables « Jouer »
  again and keeps grid 1 `started`; the next tap, once the server answers,
  enters a room. (← 010 AC-1)
- **AC-3** Ana starts FX-01 and types `T`, `A` from (1, 0) across; Bob opens
  her room's link in another browser, phone or computer: his grid shows `T` at
  (1, 0) and `A` at (1, 1), and Ana's page keeps its code and letters, not
  reloaded. (← 010 AC-2, 011 AC-2)
- **AC-4** After Ana types `T`, `A` and taps (2, 2) twice, a reload first sends
  a join with her stored token and is the same player, alone in the roster,
  with `T`, `A` and (2, 2) selected down. (← 010 AC-3)
- **AC-5** After « Jouer » on grid 1, `nock.progress` holds `{"1": "started"}`
  (other grids and a `finished` kept), the record has `grid` 1 and the catalogue
  shows item 1 started; a `grid_solved` or solved snapshot then gives
  `{"1": "finished"}`, and with `grid` null nothing. (← 010 AC-4, 010 AC-5)
- **AC-6** With `Zoé` remembered, the first frame after « Jouer » is a join as
  `Zoé` without token, the own row reads `Zoé` and the stored identity holds that
  player's id and `ZOÉ`; with nothing remembered the join is as « Invité » and
  nothing is remembered after; `A` or `<b>` also give « Invité ». (← 010 AC-6)
- **AC-7** With FX-01 as published entry 2, `{"grid_number": 2}` answers 201 with
  a 6-character `code` of the alphabet and `share_url` `<base URL>/r/<code>`, and
  that room plays FX-01 as grid 2; a second request makes another room.
  (← 011 AC-1)
- **AC-8** `{"grid_number": "2"}`, `0`, `{}`, `not json` and an extra key answer
  422, unpublished 4 and unknown 99 answer 404 `{"detail": "Not Found"}`, as does
  `POST /api/rooms/`, and none creates a room. (← 011 AC-1)
- **AC-9** Once joined, the Joueurs tab shows « Lien d'invitation » and links to
  `<origin>/r/<code>` with that text; « Copier le lien » puts it in the
  clipboard and shows « Lien copié » for 2 seconds, with no live role and
  read by the status region, while the button still reads « Copier le
  lien »; an unknown room shows no link. (← 011 AC-1)
- **AC-10** 1,000 codes from one registry are distinct and in the alphabet,
  use at least 20 characters at each position, and none is the previous one
  plus 1 in base 32; two registered rooms find their grid, `abc123` finds
  nothing. (← 011 AC-3, 040 AC-7)
- **AC-11** From one address, ten sockets to `ZZZZZZ` close with 4404; the
  eleventh, to an existing room, closes with 4429 before any message, and its
  page ends on « Trop de codes erronés. Réessayez dans une minute. »; 60
  seconds later it joins. Forty sockets at once to `ZZZZZZ` get ten 4404 and
  thirty 4429.
  (← 011 AC-3)
- **AC-12** With rules that answer Ana's `select_cell` with two `letter_changed`,
  a `pong` reply and a relayed `selection_moved`: Ana gets the two events in seq
  order then her `pong`, Bob and Cy the two events then the `selection_moved`;
  ticks run while a socket is attached and stop after the last leaves, and a
  new socket gets one tick before its first input; a raising `handle_message`,
  `tick` or `disconnect_player` is logged, leaves the state, and ticks and
  inputs go on; two
  sockets of one player both get each event, and closing either keeps the other;
  after `close()` the engine thread stops and no input runs a rule. (← 011 AC-4)
- **AC-13** With the variable unset, thirty `{"grid_number": 1}` from one
  address answer 201; the thirty-first answers 429 `{"detail": "Too Many
  Requests"}` and creates no room, while another address gets 201. That
  address is still refused 3,599.9 s after its first creation and gets 201 at
  3,600 s.
- **AC-14** Forty creations at once from one address give thirty 201 and ten
  429, and thirty rooms exist.
- **AC-15** Twenty requests answered 422 and twenty answered 404 from one
  address count nothing: thirty creations then answer 201. Once the address
  is refused, a new app on the same store gives it 201.
- **AC-16** With `NOCK_ROOMS_PER_ADDRESS_PER_HOUR` `"3"` or `"0003"`, the
  fourth creation of an address answers 429; with `"1"`, the second; `"10000"`
  is taken.
- **AC-17** `NOCK_ROOMS_PER_ADDRESS_PER_HOUR` `"0"`, `"10001"`, `" 30"`,
  `"3.0"`, `"-1"` or `"٣"` stops `main()` with a one-line message holding
  the name and `repr()` of the value, and no server runs; `python -m nock`
  exits with 1; an app starting with it fails with `SettingsError`.
- **AC-18** On `/` with grids 3, 2 and 1, card 2's button is named « Jouer »
  and described « Grille n° 2 », card 3's described « Grille n° 3 »; on `/g/1`
  it is described « Grille n° 1 ».

## Edge cases

- Two quick taps on « Jouer » send one request (AC-1).
- Storage that refuses writes still creates and loads the room; with no record,
  the page shows the nickname form (AC-1).
- A saved selection on a clue cell, outside the grid, or in a direction with no
  word is ignored, and nothing is sent (AC-4).
- A corrupt record (`not json`, `[]`) is none; a room joined by link, or after
  one, gets a record with `grid: null` and marks no progress; a room gone at the
  reload keeps its record (AC-4).
- Failures at T refuse at T + 59.9, not at T + 60.0; codes with 0, O, 1, I, small
  letters or another length count; another address or app is not held (AC-11).
- A signed-in creator counts with the anonymous creations of its address
  (AC-13).
- The 429s refused within the hour do not delay the next 201 (AC-13).

## Out of scope

- The host role, its controls and the creator: `lobby/host.md`. Limits on any
  other HTTP route than creation, the recap route, the ops API and the
  sign-in link; the cap on the open sockets of an address:
  `platform/realtime.md` rules 2 and 26; the app
  parsing `X-Forwarded-For` itself; changing the creation limit from `/ops`.
  Web Share, QR codes, offline play.
- Reconnection and fair play: `platform/realtime.md`. Durable state:
  `platform/server.md`. Feed lines of joins and departures:
  `social/presence.md`. The Menu, sheets and top bar: `client/hud.md`.

## Code

- `src/nock/room.py`: `new_room`. `src/nock/hub.py`: `RoomRegistry`, codes,
  room tasks. `src/nock/server.py`: `POST /api/rooms`, the throttle, the
  creation limit. `src/nock/settings.py`, `src/nock/__main__.py`: the
  variable.
- `web/src/lib/playGrid.ts`, `CatalogueItem.svelte`: « Jouer »; `roomRecord.ts`:
  the record; `PlayersPanel.svelte`: the link; `RoomPage.svelte`,
  `roomSession.ts`: the throttled status.
- Tests: `tests/test_spec_010_*`, `test_spec_011_*`, AC-7 of
  `tests/test_spec_040_*`, and `tests/test_rooms_*` for AC-13 to AC-18.
