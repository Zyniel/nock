---
area: lobby
file: rooms
status: draft
---

# lobby/rooms - Solo start, room creation, invitation and host controls

## Purpose

A player starts a grid alone in one tap and invites friends with the room's link.
The room's first player is its host, who can remove players, lock the room and set
its help; the role passes on when the host stays away.

## Depends on

- `lobby/joining.md`: joins, identities, the roster, past players.
- `platform/realtime.md`: messages, codes, delivery, resume and time-out.
- `content/library.md`: the catalogue, published grids, `nock.progress`.

## Rules

### Solo start

1. A solo game is a room created from the catalogue with one player; inviting is
   sending its link, and nothing converts when others come.
2. Each catalogue item, on the catalogue page and on `/g/<number>`, has « Jouer »
   (`catalogue.play`). A tap marks the grid `started` in `nock.progress` unless it
   is `finished`, then asks for a room (rule 6). On success it writes the room
   record `{"grid": <number>, "selection": null}` and loads `/r/<code>`. On a
   network error, any other status or an answer without a code, it stays, shows
   `catalogue.play_failed` in that item and enables the button again. The button is
   disabled while the request runs. Each tap makes a new room.
3. The room record `nock.room.<CODE>` is a JSON object with `grid` (the catalogue
   number or null) and `selection`; anything else reads as no record, and a
   rewrite keeps unknown fields. The room page writes the selection at each change,
   creating the record with `grid: null` when there is none.
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
   `POST /api/rooms/` is 404 with no redirect. Only a 201 creates a room.
7. A new room has seq 0, no player, empty cells, help mode `free`, a budget of 5
   letters and 1 word, no lock, and its catalogue number.
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
    seconds; the button keeps its text. Without a usable clipboard nothing changes.
    Before any snapshot (`not_found`, `throttled`, a refused join) no link shows.

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

### Host rules

13. Host actions are remove, lock, change settings and mute. Another player gets
    `not_host`. Removing or muting oneself, or anyone not a player of the room,
    gets `invalid_target`. An action that would change nothing gives no event and
    no reply.
14. Removing t: `player_left` with reason `removed`; t's seat, colour and nickname
    are freed, their letters keep their author, their token is banned (its join is
    `removed`, `lobby/joining.md` rule 4); a connected t gets `error` `removed`,
    then a close 1000. No confirmation. Another token, or none, is a new player.
15. Locking or unlocking announces `settings_changed` with the settings and the
    remaining budget. While locked, every join that is neither a resume nor a
    removed token's (`removed` comes first), a seat back included, is
    `room_locked`.
16. Changing settings sets the help mode and the reveal allowance (any count from
    0), never the lock; locking never changes them. The remaining budget is, for
    letters and words apart, `max(0, new allowance - reveals of that kind used)`.
    One `settings_changed` carries both. Their effect: `gameplay/hints.md`.
17. Muting sets the player's `muted` with one `player_muted`, kept across a
    restart. Its effect: `social/chat.md`.
18. When the host has been disconnected more than 60 seconds, a tick gives the role
    to the player not disconnected (idle counts) with the smallest join seq, in one
    `host_changed`; with none, the host stays and the next tick tries again. A host
    who times out hands the role at once, after the `player_left`, to the remaining
    player with the smallest join seq, connected first; with nobody left the next
    joiner is host. A resume keeps one's join seq. A host back after a hand-over is
    an ordinary player.
19. The room refuses with `not_joined`, changing nothing, any message from an id
    that is not one of its players (removed, timed out, unknown). On a socket,
    before its join, every message but `join` and `ping` gets `not_joined`
    (`platform/realtime.md` rule 4). Frames from a socket the room closed (a
    removal, a silence) reach nothing, from that step on; a new socket of that
    player is heard again.

### Host controls on the page

20. The host's row shows `roster.host`. Only the host sees « Retirer » in each
    other player's Joueurs row, named `host.remove_label`, which sends
    `remove_player` at once; and « Réglages de l'hôte » in the Menu, opening the
    host sheet (`settings.heading`): the switch `host.lock`; the help mode
    (`settings.help_mode_label`) as three choices (`settings.help_mode.*`); the
    counts `settings.reveal_letters_label` and `settings.reveal_words_label`
    (whole, 0 to 99); « Enregistrer », which sends `change_settings`, never with a
    count out of those bounds. The sheet shows the room's help mode and allowance,
    not the remaining budget, and follows `settings_changed`; the switch sends the
    opposite of the room's lock and shows the room's, not the click's. A
    `host_changed` gives or takes these controls at once.
21. `removed` or `room_locked`, on a join, during the game or a reconnection, ends
    the page on `removed` or `locked` with `room.status.removed` or
    `room.status.locked`, with no form, no reconnection band and no reconnection;
    `throttled` is final too. Before any snapshot it shows on the entry card of
    `lobby/joining.md` rule 11, after it on the status band. After `removed` the
    identity stays, so a reload is refused again.

### Look

« Jouer » and its error: `_design/pages.md`, « Catalogue » (today
`specs/_design.md` §10). Joueurs rows, host buttons and link: `_design/room.md`,
« Salon » (today §8 « Salon »); the Menu entry, « Menu » (today §8 « Menu
(« Menu ») »); the host sheet, « Room sheets » (today §8 « Room sheets: host
settings and account »); a final status once the room has shown, the status band
of « Connection lost » (today §8 « Connection lost (spec 017) »); before, the entry
card of `lobby/joining.md` rule 11, `_design/pages.md` (today §8 « Entry and
not-found pages »).

## Acceptance criteria

- **AC-1** On `/` or `/g/1`, one tap on item 1's « Jouer » (FX-01) and nothing
  else reaches `/r/<code>` joined on a 5 × 5 grid with one player and no nickname
  form; tapping (1, 0) and typing `t` then shows `T`. (← 010 AC-1)
- **AC-2** With the creation answered 500, 409 or not at all, the tap stays on
  `/`, shows « Impossible de lancer la partie. Réessayez. », enables « Jouer »
  again and keeps grid 1 `started`; the next tap, once the server answers, enters a
  room. (← 010 AC-1)
- **AC-3** Ana starts FX-01 and types `T`, `A` from (1, 0) across; Bob opens her
  room's link in another browser, phone or computer: his grid shows `T` at (1, 0)
  and `A` at (1, 1), and Ana's page keeps its code and letters, not reloaded.
  (← 010 AC-2, 011 AC-2)
- **AC-4** After Ana types `T`, `A` and taps (2, 2) twice, a reload first sends a
  join with her stored token and is the same player, alone in the roster, with `T`,
  `A` and (2, 2) selected down. (← 010 AC-3)
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
  `<origin>/r/<code>` with that text; « Copier le lien » puts it in the clipboard and shows « Lien copié » for 2
  seconds while the button still reads « Copier le lien »; an unknown room shows no
  link. (← 011 AC-1)
- **AC-10** 1,000 codes from one registry are distinct and in the alphabet, use at
  least 20 characters at each position, and none is the previous one plus 1 in base
  32; two registered rooms find their grid, `abc123` finds nothing. (← 011 AC-3,
  040 AC-7)
- **AC-11** From one address, ten sockets to `ZZZZZZ` close with 4404; the
  eleventh, to an existing room, closes with 4429 before any message, and its page
  ends on « Trop de codes erronés. Réessayez dans une minute. »; 60 seconds later it
  joins. Forty sockets at once to `ZZZZZZ` get ten 4404 and thirty 4429.
  (← 011 AC-3)
- **AC-12** With rules that answer Ana's `select_cell` with two `letter_changed`,
  a `pong` reply and a relayed `selection_moved`: Ana gets the two events in seq
  order then her `pong`, Bob and Cy the two events then the `selection_moved`; ticks
  run while a socket is attached and stop after the last leaves, and a new socket
  gets one tick before its first input; a raising `handle_message`, `tick` or
  `disconnect_player` is logged, leaves the state, and ticks and inputs go on; two
  sockets of one player both get each event, and closing either keeps the other;
  after `close()` the engine thread stops and no input runs a rule. (← 011 AC-4)
- **AC-13** Host Ana removes Bob: Ana and Cy get `player_left` (Bob, `removed`),
  Bob gets `error` `removed` then a close 1000, and his page shows « Vous avez été
  retiré de ce salon. », after a reload too, with no form; Bob's removal of Cy gets
  `not_host`, Ana's of herself or `zz` `invalid_target`. (← 014 AC-1)
- **AC-14** Ana locks: she and Bob get `settings_changed` locked; a new socket gets
  `room_locked` and its page « Ce salon est verrouillé. », the room keeps 2 players
  and Bob's token resumes; locking again gives nothing, Bob's unlock `not_host`;
  once Ana unlocks, a newcomer joins. (← 014 AC-2)
- **AC-15** Host p1 disconnected at t, p2 active, p3 idle: a tick at t + 60 changes
  nothing, at t + 60.5 p2 is host; with p2 away too p3, with both away p1 stays; p1
  back is no host and gets `not_host`; the new host's page gains « Retirer » and
  « Réglages de l'hôte », the old host's loses them. (← 014 AC-3)
- **AC-16** Ana sets vote, 3 letters, 0 words: both get `settings_changed` with
  these and remaining 3 and 0, and both feeds read « Ana a modifié les réglages :
  aide par vote, 3 lettres et 0 mots à révéler »; the same again gives nothing; with
  3 letters and 1 word used, 1 and 1 leave 0 and 0, then 10 and 5 leave 7 and 4.
  (← 014 AC-4)
- **AC-17** Just after Ana removes Bob, 40 `edit_letter` from Bob's socket are
  neither applied nor sent and no cell has Bob as author; a message from a
  timed-out or unknown id, or an `edit_letter` before any join, gets `not_joined`.
  (← 014 AC-5)
- **AC-18** Ana mutes Bob: one `player_muted` reaches everyone and his snapshot
  shows him muted, after a restart too; muting again gives nothing; Bob's mute gets
  `not_host`, Ana's of herself, `zz` or a removed player `invalid_target`.
  (← 014 AC-6)
- **AC-19** With the host among 8 players, in the windows of `product.md` rule 11
  and from 300 px wide with root fonts of 12 to 24 px, each « Retirer » and
  « Couper » is at least 24 px square and hit on every pixel once scrolled into the
  Joueurs tab, which never scrolls sideways, while the grid keeps its room; each
  « Retirer » reads so, shows whole with its focus ring from the keyboard, and
  keeps the baselines of `product.md`. (← 014 AC-7, 014 AC-8, 014 AC-9)
- **AC-20** In the same windows and fonts, the host sheet lies inside the window
  with no sideways scroll, and the switch, the three choices, both counts and
  « Enregistrer » are each at least 24 px high, inside it and hit at their centre,
  the counts as wide as « Room sheets » says; opened from the Menu by keyboard,
  Tab reaches them in that order, each with the focus ring of `product.md` inside
  the sheet. (← 014 AC-7, 014 AC-10)

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
- A disconnected player can be removed, with no socket to close; removed again,
  `invalid_target` (AC-13).
- A player away within the resume window resumes in a locked room; one timed out
  is refused, and seats back once it is unlocked (AC-14).

## Out of scope

- Handing the host role on by hand, co-hosts, banning by address or browser,
  un-banning; throttling creation or any HTTP route, `X-Forwarded-For` (behind a
  proxy all players share one address); Web Share, QR codes, offline play.
- Reconnection and fair play: `platform/realtime.md`. Durable state:
  `platform/server.md`. Feed lines: `social/presence.md`. « Couper » and muting's
  effect: `social/chat.md`. The Menu, sheets and top bar: `client/hud.md`.

## Code

- `src/nock/room.py`: `new_room`, host actions, the hand-over in `tick`;
  `RoomConfig` holds its delay. `src/nock/hub.py`: `RoomRegistry`, codes, room
  tasks. `src/nock/server.py`: `POST /api/rooms`, the throttle.
- `web/src/lib/playGrid.ts`, `CatalogueItem.svelte`: « Jouer »; `roomRecord.ts`:
  the record; `PlayersPanel.svelte`, `HostSettings.svelte`: host controls and
  link; `RoomPage.svelte`, `roomSession.ts`: final statuses.
- Tests: `tests/test_spec_010_*`, `test_spec_011_*`, `test_spec_014_*`, and AC-7 of
  `tests/test_spec_040_*`.
