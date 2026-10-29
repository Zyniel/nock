---
area: platform
file: realtime
status: done
---

# platform/realtime - Room events, reconnection and fair play

## Purpose

The browser and the server talk over one WebSocket per room, in one validated
contract. A player whose connection drops keeps typing and gets their seat back
with nothing to re-enter. No browser receives an answer letter before the room
earns it.

## Depends on

- `lobby/joining.md`: the join's steps, resume, seat back and past players.
- `platform/server.md`: the log every event is written to before it is sent.
- `gameplay/co-op.md`: edits, their check order and the page's pending edits.

## Rules

### The socket

1. A room's socket is `/api/rooms/<code>/ws`; the URL chooses the room, so no
   message carries a code and no message reaches another room. With accounts on,
   the `nock_session` cookie of the opening request (`account/account.md` rule
   9) names the account of the socket's joins (`lobby/joining.md` rule 4);
   nothing else of the handshake is read. A frame, text or binary, is one JSON
   message.
2. An address held by the wrong-code throttle is closed with 4429
   (`lobby/rooms.md`). An unknown, malformed or expired code is closed with 4404
   and no message, and counts as a wrong code.
3. A frame of 4,097 to 8,192 bytes (UTF-8 for text) is answered
   `invalid_message` unparsed; a larger one is closed with 1009 (`product.md`).
   A frame that does not parse is answered `invalid_message`. After an
   `invalid_message` the socket stays open.
4. Before its join, a socket's `join` runs the join of `lobby/joining.md`, a
   `ping` gets a `pong`, and any other valid message gets `not_joined`; the
   socket stays open.
5. Every frame of a joined player, a ping, an invalid frame or a repeated join
   included, counts as a sign of life for rule 16. A ping is not input
   (`social/presence.md`).

### Messages

6. The models live in `src/nock/protocol.py`. Integers and booleans are strict
   (`"1"`, `1.0` and `true` are not integers), unknown fields are refused, enums
   take only their listed values, positions are `row` and `column` from 0, and a
   parsed message cannot be changed. The models check no grid bounds and no
   cross-field rule: the server does.
7. The 18 client and 21 server messages, by the domain that gives them their
   meaning:
   - this file: `join` (enter the room, with an optional resume token),
     `snapshot` (the whole room for the joiner), `ping` and `pong` (heartbeat),
     `error` (a refusal, rule 10);
   - `gameplay/co-op.md`: `edit_letter`, `erase`, `pencil_edit`,
     `confirm_pencil` (change a cell), answered by `letter_changed` (a cell's
     letter set or erased) and `cell_locked` (a cell fixed, checked right or
     revealed);
   - `gameplay/hints.md`: `check`, `reveal`, `vote`, answered by
     `check_result`, `reveal_result`, `vote_opened`, `vote_closed`;
   - `gameplay/rules.md`: `grid_solved`, `grid_full_wrong` (the grid finished
     right, or full with a mistake somewhere);
   - `social/presence.md`: `select_cell`, answered by `selection_moved` (where a
     player is), and `player_joined`, `player_left`, `player_state_changed`
     (who is here, and how);
   - `social/chat.md`: `chat`, `react`, `flag`, `mute_player`, answered by
     `chat_message`, `reaction`, `flag_changed`, `player_muted`;
   - `lobby/host.md`: `remove_player`, `lock_room`, `change_settings` (host
     controls; the help settings are `gameplay/hints.md`), answered by
     `settings_changed` and `host_changed` (the host role passed on);
   - `platform/server.md`: `undo` (take back one's last edit).
8. No client message carries an event seq; the four cell edits carry an
   optional `base_seq` (rule 15). The 16 server messages that change the room
   require `seq` >= 1; `selection_moved`, `reaction`, `pong` and `error` refuse
   one; `snapshot.seq` is >= 0.
9. A letter is one character `A` to `Z`. A join's nickname is 2 to 20 code points
   once stripped, case untouched (`lobby/joining.md` adds its rules). A chat text
   is 1 to 280 code points once stripped as Python's `str.strip()` does. A
   snapshot lists at most 8 players. A reveal targets a letter or a word, a check
   also the grid.
10. Error codes (19), each with the domain that gives it its meaning:
    `invalid_message`, `not_joined`, `rate_limited`, `stale_edit`,
    `not_a_letter_cell` (this file); `room_full`, `invalid_nickname`
    (`lobby/joining.md`); `room_locked`, `removed`, `not_host`, `invalid_target`
    (`lobby/host.md`); `cell_locked` (`gameplay/co-op.md`); `nothing_to_undo`
    (`platform/server.md`); `grid_solved` (`gameplay/rules.md`);
    `help_disabled`, `budget_exhausted`, `vote_in_progress`, `no_open_vote`
    (`gameplay/hints.md`); `muted` (`social/chat.md`). An error's text is
    English, for logs; pages use the code.

### Order and delivery

11. Each room-changing event takes the room's next seq, from 1. A snapshot's seq
    is that of the last event it includes, 0 when nothing has happened. An event
    is logged before it is sent, then reaches every joined socket of the room,
    the sender's included; a reply goes to the sender only. `selection_moved`
    goes to the other players only; a `reaction` goes to every player, the
    sender included (`social/chat.md`). A joiner gets its snapshot before any
    later event and misses none. The page applies events by seq
    (`client/shell.md`).
12. A refusal is one `error` to the sender only and changes neither the room nor
    its seq, except that it wakes an idle sender first (`social/presence.md`).
    Chat and reactions over their limit, a muted player's reaction and an
    invalid reaction are dropped with no answer (`social/chat.md`). The
    `room_full` or `room_locked` of a join, and the `removed` of a removed
    token's join or of the host's removal (sent to the removed player), are
    followed by a close with 1000.
13. Close codes: 4404 unknown or deleted room; 4429 throttled; 4001 replaced by
    the same player's newer socket (`lobby/joining.md`); 4408 silent; 1000 after
    rule 12's refusals; 1011 a join the store could not save
    (`platform/server.md`); 4507 and 1008, a socket that does not read or sends
    too fast, and 1009, a frame over 8,192 bytes (`product.md`).
14. `player_id` is public. `resume_token` is secret: drawn at random for each new
    player, sent only in that player's snapshots, given back in `join`.

### Disconnection, offline edits and the resume window

15. A cell edit sent again after a reconnection carries `base_seq`, the last seq
    the page had applied when the edit was made; an edit without one is never
    stale. A live `confirm_pencil` also carries the page's seq
    (`gameplay/co-op.md`). With `base_seq` b, the edit is `stale_edit` when the
    cell last changed after b by another player; else it applies as a live
    edit. The rate limit comes before the letter-cell check, which comes before
    `cell_locked`, then staleness (the full order: `gameplay/co-op.md`).
16. A closed socket disconnects its player at once. A connected player with no
    frame for 6 seconds is disconnected and their socket closed with 4408; the
    room checks every second, each player in roster order.
17. The resume window is 300 seconds. A player disconnected for exactly 300 still
    resumes; past that they time out, at the next check or inside a join with
    their token: `player_left` with `timed_out`, then they are a past player whom
    the join seats back (`lobby/joining.md`). A host who times out hands over at
    once (`lobby/host.md`). Time-outs due while a room was not running apply
    first when it runs again.

### The page's connection

18. While its socket is open the page sends `ping` every 2 seconds; when no frame
    of any kind has come for 4 seconds, the connection is lost at once: the socket
    is dropped, and its late frames and close event change nothing.
19. Any close or socket error is a loss, 4408 included, except a final one: 4404,
    4429, 4001, or a close after an `error` `room_full`, `room_locked` or
    `removed`. A final close ends the tries with its state (`client/shell.md`).
20. After a loss, once the page has joined: state `reconnecting`, the room
    status reads `room.status.reconnecting`, and the connection band, announced
    as a status, shows `room.banner.offline` within 5 seconds. The grid stays
    usable: typed and erased letters show and wait as pending edits, and nothing
    is sent without an open socket. Before the first snapshot: state
    `connecting`, no band, and a shown nickname form stays.
21. A new socket opens after 1, 2, 4, 8 seconds, then every 8 seconds, without
    end; the browser's `online` event tries at once, replacing a socket still
    connecting. On open, the page joins as `lobby/joining.md` rule 8 says.
22. On a snapshot: state `joined`, band hidden, delays back to 1 second; then the
    pending edits are sent again, oldest first, each with its `base_seq`, the
    first at once and one every 100 ms; an edit typed meanwhile queues behind
    them. No edit is sent between the socket opening and its snapshot. Pending
    edits live in memory only: a reload loses them.

### Fair play

23. The server never adds an answer to a payload, HTTP or WebSocket: no key
    `answer` or `solution`, and no letter at a cell before it is earned there,
    by a player's accepted edit at that cell or by a reveal (`gameplay/hints.md`).
    An answer's letters reach a browser only where players put them (accepted
    letters, chat texts, nicknames) or a reveal put them, or by chance in
    random ids, tokens and codes. The snapshot's grid holds clue texts and
    arrows, never answers. Its letter cells carry two hyphen marks,
    `hyphen_right` and `hyphen_down`, false unless a word of the grid has a
    break (`content/grids.md` rule 4) right after that cell, across or down;
    a mark names an edge between two letters and never a letter.
24. Edits (`edit_letter`, `erase`, `pencil_edit`, `confirm_pencil`) are limited
    to 20 per player in any sliding second; one more is `rate_limited`, and a
    refused edit does not count. The client stays connected. `undo` and
    `select_cell` are not counted.
25. A page inserts every nickname, chat text and clue text as text, never as
    HTML: no `{@html` block in a `.svelte` file under `web/src` (whitespace or a
    line break after `{` included), and none of `innerHTML`, `outerHTML`,
    `insertAdjacentHTML`, `document.write`, `parseFromString`,
    `createContextualFragment`, `setHTMLUnsafe` or `srcdoc` in its `.ts` and
    `.svelte` files.

### Look

The connection band follows `_design/room.md`, « Connection lost ».

## Acceptance criteria

- **AC-1** Each of the 18 client and 21 server messages, written as JSON, parses
  to its class and back unchanged: `{"type": "edit_letter", "row": 1, "column":
  0, "letter": "T", "base_seq": null}` gives that edit with `base_seq` None, and
  setting its `row` afterwards is refused. (← 039 AC-1, 039 AC-2, 039 AC-3,
  039 AC-19)
- **AC-2** A message whose `type` is `teleport`, missing, or of the other
  direction is refused: a `snapshot` sent as a client message, `{"type":
  "pong"}` from a client, and `{"type": "ping", "seq": 1}` all fail.
  (← 039 AC-4, 039 AC-20)
- **AC-3** Strict fields: an edit with `"row": "1"`, `1.0`, `true` or `-1`, an
  `undo` with an extra field, a vote with `"yes": 1`, `"help_mode": "FREE"`, a
  `reveal` of the grid, a colour 8, a snapshot with 9 players and an error code
  outside the 19 are refused, while a `check` of the grid parses. (← 039 AC-5,
  039 AC-9, 039 AC-10, 039 AC-18, 039 AC-21)
- **AC-4** `"A"` and `"Z"` are letters but `"a"`, `"É"`, `"AB"` and `"1"` are
  not; a join as `"  Ana  "` parses as `Ana` but `"  A  "` and 21 `x` are
  refused; the chat `"\u001fsalut\u001c"` reads `salut` and 281 `a` are
  refused. (← 039 AC-6, 039 AC-7, 039 AC-8)
- **AC-5** A `letter_changed` with seq 0, -1 or none is refused and one with seq
  1 parses; a `pong` with seq 5 is refused; a snapshot parses with seq 0 or 42.
  (← 039 AC-11, 039 AC-12, 039 AC-13)
- **AC-6** The view of FX-01 has 25 cells in grid order, its 18 letter cells
  empty, its clue at (0, 0) « Passoire fine » then « De la marine »; its JSON
  holds neither `answer` nor `TAMIS`, no snapshot field is named `answer` or
  `solution`, and a clue sent with an `answer` is refused. (← 039 AC-14,
  039 AC-15, 039 AC-16, 039 AC-17)
- **AC-7** On a fresh FX-01 room, a join as `Ana`, text or binary, gets a
  snapshot with seq 1, the empty grid view, Ana alone as host, help `free`, a
  budget of 5 letters and 1 word, no chat and the timer at 0, stopped; a second
  client gets another id and token, and an unknown token gets a new one.
  (← 040 AC-8, 040 AC-10)
- **AC-8** A socket to `ZZZZZZ` or `abc` closes with 4404 before any message.
  (← 040 AC-11)
- **AC-9** `not json`, a join as `A` and a frame of 4,097 bytes each get
  `invalid_message` and the socket stays open; a frame of 4,096 bytes is parsed,
  and a join after a refused frame gets a snapshot. (← 040 AC-12, 037 AC-2)
- **AC-10** Before a join, an `undo` gets `not_joined` and a `ping` gets `pong`;
  a join then gets a snapshot. (← 040 AC-13, 017 AC-4)
- **AC-11** A joined client's `edit_letter` with `"a"` gets `invalid_message`,
  one at (0, 0) (a clue cell) or (9, 9) (off the grid) gets
  `not_a_letter_cell`, and an unjoined socket's edit gets `not_joined`; the seq
  stays and the other client receives nothing, while `T` at (1, 0) from the
  joined client reaches both. (← 037 AC-2)
- **AC-12** 25 edits sent at one instant give 20 `letter_changed`, which the
  other client receives too, and 5 `rate_limited`; the next edit 1 second later
  is accepted, and a second player is never held by the first one's count.
  (← 037 AC-3)
- **AC-13** In a full FX-01 game, with three wrong letters corrected, an erase
  and a late joiner, no frame or HTTP body breaks rule 23, and the late joiner's
  snapshot holds exactly the 9 letters typed before it. (← 037 AC-1,
  040 AC-9)
- **AC-14** Players named `<b>Eve</b>` and `<img src=x>` show in the roster as
  the texts `<b>eve</b>` and `<img Src=x>`, with no `b` or `img` element and no
  dialog; the static scan finds no banned construct. (← 037 AC-4)
- **AC-15** A player silent for 5.9 seconds stays active; at 6 the other client
  gets `player_state_changed` `disconnected` and the silent socket closes with
  4408; a socket the client closes is seen with no wait, and the other page's
  roster shows the state within 300 ms. (← 017 AC-4)
- **AC-16** Bob (colour 1, not host), disconnected at t, resumes with his token
  at t + 300 (same id, nickname, colour and letters); at t + 300.5 the join
  gives `player_left` `timed_out` then his own `player_joined` (were he host,
  `host_changed` between them); a reload of a page resumes its player without
  the form. (← 017 AC-3)
- **AC-17** In a room at seq 10 where Bob wrote `B` at (1, 0) at seq 8, Ana's
  `T` there with `base_seq` 7 gets `stale_edit` and the cell keeps `B`; with
  `base_seq` 8 it applies, as it does with 7 when the change at seq 9 was hers.
  (← 017 AC-2)
- **AC-18** When the socket closes with 1011, or goes silent, within 5 seconds
  the band, announced as a status, shows « Connexion perdue. Vous pouvez
  continuer : vos lettres seront envoyées au retour du réseau. », the room
  status reads « Reconnexion… », and a typed `t` shows `T`; a close with 4404,
  4429 or 4001 ends the tries; the next snapshot hides the band. (← 017 AC-1)
- **AC-19** With 30 letters typed offline, the reconnect snapshot is followed by
  the 30 edits in order over about 3 seconds, never more than 10 in a second, and
  none before it; an `online` event opens a socket at once. (← 017 AC-5)
- **AC-20** On FX-01 with `VI-DE` and `NA-VAL`, the view's (2, 2) has
  `hyphen_right` true and (1, 1) `hyphen_down` true, every other mark false;
  on FX-01 as published every mark is false; a letter cell written without the
  marks parses with both false, and one with `"hyphen_right": "yes"` is
  refused.

## Edge cases

- The server reads a binary frame like a text one (AC-9); the page ignores the
  binary frames it receives (`client/shell.md`).
- A frame of 4,097 bytes with few characters is still refused (AC-9).
- An erase and a pencil letter follow the stale rule; a `base_seq` above the
  room's seq is never stale; edits that reached the server before the loss are
  resent and apply again with no visible change (AC-17).
- A cell locked since the edit gets `cell_locked`, not `stale_edit`; with the
  limit reached, `rate_limited` comes before both (AC-12, AC-17).
- A player who only pings, or only sends invalid frames, is never silent (AC-15).
- Two tabs never take the room from each other in a loop: 4001 is final (AC-18).
- A typed letter replaced later stays earned at that cell, never at another
  (AC-13); a revealed letter is earned when its `cell_locked` is sent, not
  before (`gameplay/hints.md`).
- A room stored while answers held letters only (`VIDE`) snapshots with every
  mark false (AC-20).

## Out of scope

- What each event does to the room: the gameplay and social domains. The join's
  steps, takeover with 4001 and past players: `lobby/joining.md`. Host hand-over
  and the creator: `lobby/host.md`. The wrong-code throttle: `lobby/rooms.md`.
- The page's seq buffer and its other connection states: `client/shell.md`.
  Presence states in the roster: `social/presence.md`.
- Durable state across a restart, the log and undo: `platform/server.md`.
  Stalled, flooding and oversized sockets: `product.md`. What changed while
  away: `social/catch-up.md`.
- Throttling other messages: chat and reactions, `social/chat.md`; wrong codes,
  `lobby/rooms.md`; `undo`, `select_cell` and the rest are not limited.
- Peer-to-peer sync, pending edits kept across a reload, a leave message,
  message acknowledgements, a Content Security Policy.

## Code

- `src/nock/protocol.py`: every message, `grid_view`, `parse_client_message`,
  `parse_server_message`.
- `src/nock/hub.py`: frames before and after the join, delivery, close codes,
  `MAX_FRAME_BYTES`. `src/nock/server.py`: the socket route.
- `src/nock/room.py`: `tick`, `disconnect_player`, the edit checks, the stale
  rule, the rate limit; `RoomConfig` holds the silence, resume and rate values.
- `web/src/lib/roomSession.ts`, `RoomPage.svelte`: heartbeat, losses, retries,
  resent edits.
- Tests: `tests/test_spec_039_*`, `tests/test_spec_017_*`,
  `tests/test_spec_037_*`, `tests/test_spec_040_ac07_ac13_*`.
