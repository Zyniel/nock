---
id: "017"
title: Disconnection and reconnection
status: approved
---

# 017 - Disconnection and reconnection

Epic E4 Real-time sync (US-4.3) · Release: MVP · Epic depends on: E3
The rooms engine, `RoomConfig` and the fake-clock harness are defined in spec 011;
joining, resume tokens, the stored identity and the roster in spec 012; edits and
the page's pending queue in spec 015; the log in spec 018. The messages are those
of spec 039.

## Goal

As a player on a train, I want to keep my place when my connection drops, so that I rejoin without starting over.

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests.

## Public interface

### Protocol change (see open question 1)

Two messages without `seq` are added to spec 039, and one error code:

```python
# src/nock/protocol.py (additions)
class Ping(ProtocolModel):            # client to server, member of ClientMessage
    type: Literal["ping"] = "ping"


class Pong(ProtocolModel):            # server to client, member of ServerMessage, no seq
    type: Literal["pong"] = "pong"


class ErrorCode(StrEnum):
    ...
    STALE_EDIT = "stale_edit"         # an offline edit on a cell changed since
```

Wire examples: `{"type": "ping"}`, `{"type": "pong"}`.

### Server

Hub (`nock.hub`):

- A `ping` is answered with one `pong` at any time after the socket is accepted,
  before or after the join. Before the join it is not `not_joined`.
- New constant `SILENCE_CLOSE_CODE: int = 4408`, re-exported by `nock.server`.

Rules (`nock.room`):

- `handle_message(state, p, Ping(), now)`: `reply = (Pong(),)`,
  `p.last_seen_at = now`, no entry. A ping is not input (spec 013's idle rule).
- Every message of a joined player sets `p.last_seen_at = now`.
- Offline edits, check 4 of spec 015: an `edit_letter` or `erase` (and, with spec
  020, `pencil_edit` and `confirm_pencil`) with `base_seq = b` not None is refused
  with `ErrorMessage(code=STALE_EDIT)` when the cell's `changed_seq > b` and its
  `changed_by != p`. Otherwise it is applied as a live edit. A live edit
  (`base_seq` None) is never stale.
- `tick(state, now, config)` is built here (signature in spec 011; specs 013 and
  014 add steps after these two). For each player, in `players` order:
  1. Silence: a player not `disconnected` with
     `now - last_seen_at >= config.silence_timeout_seconds` becomes
     `disconnected` exactly as in `disconnect_player` (entry
     `PlayerStateChanged(disconnected)`), and the outcome holds
     `Disconnect(player_id, close_code=4408)` so the hub closes the silent socket.
  2. Time-out: a `disconnected` player with
     `now - disconnected_at > config.resume_window_seconds` leaves: entry
     `PlayerLeft(player_id, reason=timed_out)`, removed from `players` (their seat,
     colour and nickname are free again; their letters keep their author id). If
     they were host, spec 014's hand-over rule picks the next host at once
     (`host_changed` after the `player_left`); if nobody is left, the room has no
     host until the next joiner (spec 012).
- `join_room`, resume step (spec 012 step 2), gains the window: a token whose
  player is `disconnected` with `now - disconnected_at > resume_window_seconds`
  does not resume: that player times out in this same step (entry
  `PlayerLeft(timed_out)`, as in the tick) and the join goes on as a new player with
  the join's nickname.

### Client

Heartbeat and loss detection:

| Constant | Value |
| --- | --- |
| `PING_INTERVAL_MS` | 2,000: while the socket is open the page sends `{"type": "ping"}` this often |
| `SILENCE_LIMIT_MS` | 4,000: when no frame of any kind has arrived for this long while the socket is open, the page closes it itself and treats it as lost |
| `RECONNECT_DELAYS_MS` | 1,000, 2,000, 4,000, 8,000, then 8,000 for every later try |

A connection is lost when the socket closes or errors with any code other than a
final one, or by the silence rule. Final: close 4404 (`not_found`), 4429
(`throttled`), 4001 (`replaced`), and a close that follows an `error` with code
`room_full`, `room_locked` or `removed`. Close 4408 (silence) is not final.

When the connection is lost after the page had joined at least once:

1. `data-status="reconnecting"`, and `data-testid="connection-banner"`
   (`role="status"`) is shown with `t("room.banner.offline")`. It is shown at the
   latest 5 seconds after the loss (in practice at once).
2. The grid stays usable: typing and erasing (specs 008, 009) change the shown
   letters and add pending edits as usual; nothing is sent while no socket is open.
   Each pending edit records `base_seq`: the page's `seq` when it was made.
3. The page opens a new socket after the next delay of `RECONNECT_DELAYS_MS`, and
   at once when the browser fires `online`. On open it sends the join of spec 012
   with the stored identity (no form).
4. On the new snapshot: it replaces the kept snapshot (spec 040 rules), status
   `joined`, the banner is hidden, the delays start again from the first; then
   every pending edit is sent again, oldest first, each with its recorded
   `base_seq` (not `null`), and stays pending until its answer (spec 015).
5. A final close or error ends the attempts with its status (spec 012, 011, 014).

When the connection is lost before the first snapshot ever arrived, the page also
retries with the same delays, with `data-status="connecting"` and no banner.

The status `closed` of spec 040 is no longer produced (see open question 4).

New `fr.json` keys:

| Key | Value |
| --- | --- |
| `room.status.reconnecting` | `Reconnexion…` |
| `room.banner.offline` | `Connexion perdue. Vous pouvez continuer : vos lettres seront envoyées au retour du réseau.` |

### Test harness

As spec 011. Server timing criteria use `RoomRegistry(clock=fake_clock,
config=RoomConfig(tick_seconds=0.05))`, so the 6-second, 5-minute and 10-second
values keep their defaults and pass in milliseconds. Browser criteria use spec
040's mocked socket: the handler is called again for each new socket the page
opens, so a test can count connections, answer pings (or not), close a socket
(`ws.close(code=...)`) and send snapshots; it seeds the stored identity of spec 012
with `context.add_init_script` when needed. Times in the browser are measured with
Playwright's waiting assertions and their `timeout`.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-4.3.1) (browser with mocked socket) A banner shows within 5 seconds of a lost connection, and I can keep typing. Given the page joined (FX-01 snapshot, `seq` 5) with a mock that answers each `ping` with `pong`: (a) when the mock closes the socket with code 1011, `connection-banner` is visible with `fr.json["room.banner.offline"]` and `data-status="reconnecting"` within 5,000 ms; tapping (1, 0) and pressing `t` then shows `T` at (1, 0) and no frame is sent while no socket is open. (b) In a second run, when the mock stops answering pings and sends nothing more, the banner is visible within 5,000 ms of the last frame the mock sent. (c) In both runs, when the mock accepts the next socket and answers its join with a snapshot, the banner is hidden and `data-status="joined"`.
- **AC-2** (AC-4.3.2) (Python; WebSocket; browser with mocked socket) On reconnection, my offline letters are sent. Where the server's cell changed in the meantime, the server's letter is kept. Python: in a FX-01 room at seq 10 where `p2` wrote `B` at (1, 0) with seq 8, `handle_message` from `p1` with `EditLetter(row=1, column=0, letter="T", base_seq=7)` is refused with `stale_edit` and the cell keeps `B`; with `base_seq=8` it is applied; `EditLetter(row=1, column=1, letter="A", base_seq=7)` on a cell unchanged since seq 7 is applied; an edit with `base_seq=7` on a cell last changed by `p1` itself at seq 9 is applied. WebSocket: clients A and B join (seq 2); A closes its socket; B writes `B` at (1, 0); A reconnects with its token, then sends `edit_letter` (1, 0) `T` with `base_seq` 2 and (1, 1) `A` with `base_seq` 2: the first gets `error` `stale_edit` and nobody receives a `letter_changed` for it, the second is applied and both clients receive it. Browser: given the page joined with `you` = `p1`, its stored identity, a snapshot at `seq` 5, and the mock closing the socket, typing `T` at (1, 0) and `A` at (1, 1) while offline, then the mock accepting the new socket: the page's first message is `Join` with the stored nickname and `resume_token`; after the mock sends a snapshot at `seq` 9 whose (1, 0) holds `B` from `p2`, the page sends `EditLetter(row=1, column=0, letter="T", base_seq=5)` then `EditLetter(row=1, column=1, letter="A", base_seq=5)`; when the mock answers the first with `error` `stale_edit`, (1, 0) shows `B`, and when it answers the second with `letter_changed` seq 10 from `p1`, (1, 1) shows `A` with `data-unconfirmed="false"`.
- **AC-3** (AC-4.3.3) (Python; WebSocket with a fake clock; browser with live server) Reconnecting within 5 minutes restores my nickname, colour and authorship with nothing to re-enter. Python: `p1` (`Ana`, colour 0, author of `T` at (1, 0)) disconnected at `t`; `join_room` with `p1`'s token at `t + 300` resumes `p1` (same id, nickname, colour; (1, 0) still authored by `p1`); at `t + 300.5` the same join gives `PlayerLeft(p1, reason="timed_out")` then `PlayerJoined` of a new id; `tick` at `t + 300` leaves `p1` in the room and at `t + 300.5` removes them with `PlayerLeft(timed_out)`. WebSocket: A (`Ana`) and B join; A's socket closes; after `advance(299)` and one tick, B has received no `player_left`; A's token joins again and gets `you` equal to its old id with `Ana` and colour 0. In a second run, after `advance(301)`, B receives `PlayerLeft(<A>, reason="timed_out")` within one second of real time, and A's token then joins as a new player id. Browser: on the live server, page 1 joins as `Ana` and page 2 (another context) as `Bob`; page 1 is reloaded (open question 7); it reaches `data-status="joined"` again with the same `data-you`, its roster entry `Ana` keeps the same `data-colour`, `nickname-form` is never shown, and page 2's roster still holds exactly 2 players, with `Ana` back to `data-state="active"`.
- **AC-4** (AC-4.3.4) (Python; WebSocket with a fake clock; browser with mocked socket) Other players see my state change in the roster within 10 seconds. Python: `tick` at `last_seen_at + 5.9` leaves an active player active; at `last_seen_at + 6.0` it gives `PlayerStateChanged(disconnected)` and a `Disconnect` with close code 4408. WebSocket: A and B join; A stops sending anything; after `advance(6)`, B receives `PlayerStateChanged(<A>, state="disconnected")` within one second of real time and A's socket is closed with 4408; when A's socket is closed by the client instead, B receives it without any clock change. Browser: given the page joined with players `p1` (`you`) and `p2`, when the mock sends `player_state_changed` for `p2` `disconnected`, `p2`'s `roster-player` gets `data-state="disconnected"` within 300 ms, and `active` again on the next such event.

## Edge cases and errors

- Detection budget (AC-4): server side, a closed socket is seen at once; a silent
  one after 6 seconds plus at most one tick (1 second): 7 seconds, under 10. Client
  side, a silent socket is seen after 4 seconds, under the 5 of AC-1.
- Background tabs (AC-4): browsers slow timers in hidden tabs, so a tab hidden for
  a long time may stop pinging and be shown `disconnected`; it reconnects when
  shown again. Accepted.
- Pings are not input (AC-4): a page left open with no typing still turns `idle`
  after 2 minutes (spec 013).
- Stale rule (AC-2): `base_seq` equal to the cell's `changed_seq` is not stale;
  only later changes by someone else are. My own later changes never make my
  edit stale, so resending several offline edits to one cell keeps the last one.
- Locked cell (AC-2): an offline edit on a cell locked since gets `cell_locked`
  (checked before staleness, spec 015 order).
- Offline erase (AC-2): an `erase` follows the same rule as `edit_letter`.
- Edits that reached the server before the loss (AC-2): their answers may be lost
  with the socket; they are resent with their `base_seq`, and since the last change
  of the cell is mine they are applied again with no visible change.
- A `base_seq` greater than the room's `seq` (AC-2): not stale (no later change can
  exist); applied.
- Resume window edge (AC-3): exactly 300 seconds after the disconnection still
  resumes; time-out needs more than 300.
- After a time-out (AC-3): the page's stored token no longer resumes; the page's
  join (stored nickname, no form) makes a new player; spec 012 stores the new
  identity. The old letters keep the old author id. A locked room (spec 014)
  refuses that join with `room_locked`.
- Full room (AC-3): a disconnected player keeps the seat for the whole window, so a
  ninth player is refused meanwhile; after the time-out the seat is free.
- Host (AC-3): spec 014 hands the host role over after 60 seconds of
  disconnection; when the host times out, the hand-over also happens then.
- Reconnection while replaced (AC-1): a 4001 close is final, so two tabs never take
  the room from each other in a loop.
- Before the first snapshot (AC-1): a lost socket retries with status
  `connecting`, no banner; the nickname form, if it was shown, stays.
- Pending edits across a reload (AC-1): kept in memory only; a reload loses them.
- Order of resent edits (AC-2): oldest first, after the snapshot, before any new
  edit typed after the reconnection.
- Snapshot during reconnection (AC-2): buffered events and the `seq` follow spec
  040; pending edits are kept and shown over the new snapshot.

## Out of scope

- Peer-to-peer sync (epic E4).
- Shared letters: spec 015.
- Same-cell conflicts: spec 016.
- Durable room state across a server restart: spec 018.
- Keeping pending edits across a page reload or a closed tab (localStorage queue).
- Showing other players' presence states as text and idle detection: spec 013.
- Catch-up summary after a long absence: spec 034.
- A "leave the room" button.

## Work packages

None.

## Open questions

Each pick below is already written into the spec. The lead confirms or changes it.

1. Protocol change: heartbeat. A browser cannot see WebSocket ping frames, and a
   dead mobile connection may not close for minutes, so neither side can meet the 5
   and 10 seconds without an application heartbeat. Options: add `ping` / `pong`
   to spec 039, or rely on uvicorn's protocol pings (server side only). Pick: add
   `Ping` (client) and `Pong` (server, no `seq`) to spec 039; the lead reopens spec
   039 to add them, their wire examples and their parse criteria before this spec
   is built.
2. Protocol change: `stale_edit`. The server needs to answer an offline edit it
   refuses (spec 015 matches one answer per edit). Pick: add `STALE_EDIT` to
   `ErrorCode` (allowed by spec 039 decision 14). If spec 039's AC-9 test checks the
   exact count of codes, the lead updates it.
3. Stale rule. Options: refuse when the cell changed after `base_seq` at all, or
   only when someone else changed it. Pick: only someone else, so a player's own
   offline edits to one cell, resent in order, all apply.
4. Spec 040 amendment. Spec 040 AC-21 expects `data-status="closed"` after a close
   with code 1011; this spec reconnects instead. Pick: the lead reopens spec 040 in
   this spec's branch so AC-21 expects `reconnecting` and the banner; `closed` and
   its `fr.json` key stay but are no longer produced.
5. Timing values (AC-1, AC-4). Picks: the page pings every 2 seconds and declares
   the connection lost after 4 seconds of silence; the server declares a player
   disconnected after 6 seconds without a frame and checks every second. Not
   covered: a real mobile network dropping packets; browser criteria wait real
   seconds (up to 5) with a mocked socket, server criteria use the fake clock.
6. Reconnection delays. Pick: 1, 2, 4, 8 seconds then every 8 seconds, without end
   while the page is open, plus an immediate try on the browser's `online` event.
7. AC-3 in the browser. A real network cut cannot be made on the live server
   socket from the test. Pick: a page reload stands for the reconnection (same
   stored identity, same server rule); the automatic reconnection itself is covered
   by AC-1 and AC-2 with a mocked socket.
