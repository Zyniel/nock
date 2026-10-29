---
area: lobby
file: rooms
status: done
---

# lobby/rooms - Solo start, room creation and invitation

## Purpose

A player starts a grid alone in one tap and invites friends with the room's link.
Each room runs as one task that applies its inputs in order; wrong codes are
throttled per address.

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
   Each tap makes a new room.
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
   422 for any other body. `GET` is 404 JSON, `PUT`, `PATCH` and `DELETE` are 405,
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
    the link to the clipboard and shows `room.share.copied` as a status for 2
    seconds; the button keeps its text. Without a usable clipboard nothing
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
    closed, its thread stops and no input runs a rule.

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
  clipboard and shows « Lien copié » for 2 seconds while the button still
  reads « Copier le lien »; an unknown room shows no link. (← 011 AC-1)
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

## Out of scope

- The host role, its controls and the creator: `lobby/host.md`. Throttling
  creation or any other HTTP route than the ops API and the recap route,
  `X-Forwarded-For` (behind a proxy all players share one address); Web Share,
  QR codes, offline play.
- Reconnection and fair play: `platform/realtime.md`. Durable state:
  `platform/server.md`. Feed lines of joins and departures:
  `social/presence.md`. The Menu, sheets and top bar: `client/hud.md`.

## Code

- `src/nock/room.py`: `new_room`. `src/nock/hub.py`: `RoomRegistry`, codes,
  room tasks. `src/nock/server.py`: `POST /api/rooms`, the throttle.
- `web/src/lib/playGrid.ts`, `CatalogueItem.svelte`: « Jouer »; `roomRecord.ts`:
  the record; `PlayersPanel.svelte`: the link; `RoomPage.svelte`,
  `roomSession.ts`: the throttled status.
- Tests: `tests/test_spec_010_*`, `test_spec_011_*`, and AC-7 of
  `tests/test_spec_040_*`.
