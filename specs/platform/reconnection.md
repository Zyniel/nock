---
area: platform
file: reconnection
status: done
---

# platform/reconnection - Stale edits, the resume window, the page's connection

## Purpose

A player whose connection drops keeps typing and gets their seat back with
nothing to re-enter. This domain says when an edit made offline is too old to
apply, how long a disconnected player keeps their seat, and how the page notices
a loss, retries and sends what it held.

## Depends on

- `platform/realtime.md`: the socket, the messages and their delivery, the close
  codes, the silence check that disconnects a player.
- `lobby/joining.md`: the join on a new socket, resume with the token, the seat
  back of a past player.
- `gameplay/co-op.md`: the edits, their check order and the page's pending edits.

## Rules

### Stale edits

1. A cell edit sent again after a reconnection carries `base_seq`, the last seq
   the page had applied when the edit was made; an edit without one is never
   stale. A live `confirm_pencil` also carries the page's seq
   (`gameplay/co-op.md`). With `base_seq` b, the edit is `stale_edit` when the
   cell last changed after b by another player; else it applies as a live
   edit. The rate limit (`platform/realtime.md` rule 24) comes before the
   letter-cell check, which comes before `cell_locked`, then staleness (the
   full order: `gameplay/co-op.md`).

### The resume window

2. The resume window is 300 seconds. A player disconnected for exactly 300 still
   resumes; past that they time out, at the room's next check
   (`platform/realtime.md` rule 16) or inside a join with their token:
   `player_left` with `timed_out`, then they are a past player whom the join
   seats back (`lobby/joining.md`). A host who times out hands over at once
   (`lobby/host.md`). Time-outs due while a room was not running apply first
   when it runs again.

### The page's connection

3. While its socket is open the page sends `ping` every 2 seconds. The silence
   is the time since the socket's last frame of any kind, read from the clock,
   not counted in timer ticks; at 4 seconds of silence the connection is lost
   at once: the socket is dropped, and its late frames and close event change
   nothing. A hidden page loses no socket to the silence, as its timers may run
   late: when it becomes visible again it sends `ping` at once and counts the
   silence from that moment.
4. Any close or socket error is a loss, 4408 and 4503 included
   (`platform/realtime.md` rule 13), except a final one: 4404, 4429, 4001, or a
   close after an `error` `room_full`, `room_locked` or `removed`. A final
   close ends the tries with its state (`client/shell.md`); once the room has
   shown, the grid is then read-only (`client/hud.md` rule 19).
5. After a loss, once the page has joined: state `reconnecting`, the room
   status reads `room.status.reconnecting`, and the connection band shows
   `room.banner.offline` within 5 seconds, with no live role, announced by
   the status region (`client/hud.md` rule 17). The grid stays
   usable: typed and erased letters show and wait as pending edits; an undo, a
   check or a reveal made meanwhile is kept in its place among them; nothing
   is sent without an open socket. Before the first snapshot: state
   `connecting`, no band, and a shown nickname form stays.
6. After each loss a new socket opens after the next delay of 1, 2, 4, 8
   seconds, then 8 seconds each time, without end; each delay is drawn at
   random, uniformly within 20 % of its value either way (0.8 to 1.2 seconds
   for the first). The browser's `online` event tries at once, replacing a
   socket still connecting; the page becoming visible again tries at once
   when a try waits on its delay. A socket still connecting 6 seconds after
   it was created (the server's silence limit, `platform/realtime.md` rule 16,
   not the page's 4 seconds of rule 3) is dropped, and its late events change
   nothing: a loss. The 6 seconds are read from the clock, not counted in
   timer ticks: on a hidden page whose timers run late, the socket is dropped
   at the page's first timer after them. On open, the page joins as
   `lobby/joining.md` rule 8 says.
7. On a snapshot: state `joined`, band hidden, the next delay the first again.
   After a loss, the page then sends the selection it holds, if any, as one
   `select_cell` (the server cleared it at the disconnection,
   `social/presence.md` rule 8). Then the pending edits, each with its
   `base_seq`, and the kept undos, checks and reveals go out in the order
   they were made, each request after the edits that were pending when it
   was made and before any later one: the first at once and one every 100 ms.
   An edit, undo, check or reveal made while these go out queues behind them;
   otherwise it is sent at once. No edit, undo, check or reveal is sent
   between the socket opening and its snapshot. Pending edits and kept
   requests live in memory only: a reload loses them.

### Look

The connection band follows `_design/room.md`, « Connection lost ».

## Acceptance criteria

- **AC-1** Bob (colour 1, not host), disconnected at t, resumes with his token
  at t + 300 (same id, nickname, colour and letters); at t + 300.5 the join
  gives `player_left` `timed_out` then his own `player_joined` (were he host,
  `host_changed` between them); a reload of a page resumes its player without
  the form. (← 017 AC-3)
- **AC-2** In a room at seq 10 where Bob wrote `B` at (1, 0) at seq 8, Ana's
  `T` there with `base_seq` 7 gets `stale_edit` and the cell keeps `B`; with
  `base_seq` 8 it applies, as it does with 7 when the change at seq 9 was hers.
  (← 017 AC-2)
- **AC-3** When the socket closes with 1011, or goes silent, within 5 seconds
  the band, with no live role, shows « Connexion perdue. Vous pouvez
  continuer : vos lettres seront envoyées au retour du réseau. », which the
  status region reads, the room status reads « Reconnexion… », and a typed
  `t` shows `T`; a close with 4404, 4429 or 4001 ends the tries; the next
  snapshot hides the band. (← 017 AC-1)
- **AC-4** With 30 letters typed offline, the reconnect snapshot is followed by
  the 30 edits in order over about 3 seconds, never more than 10 in a second, and
  none before it; an `online` event opens a socket at once. (← 017 AC-5)
- **AC-5** Offline, Ana types `T` at (1, 0), her selection moving to (1, 1)
  across: after her reconnection snapshot, Bob receives `selection_moved` for
  Ana on (1, 1) across, then the `letter_changed` of her `T`.
- **AC-6** Ana's joined page is hidden and its timers run late, so for 5
  seconds it sends no ping and gets no frame while the server keeps the socket
  open: made visible again, it sends `ping` at once and keeps the same socket,
  with no band. Made visible on a socket that then gets no frame, it shows the
  band within 5 seconds of the return. Made visible while a try waits on an
  8-second delay, it opens a socket at once.
- **AC-7** After a loss, a socket whose opening the network never answers is
  dropped 6 seconds after it was created, and the next socket opens after the
  second delay, 1.6 to 2.4 seconds later; a socket that opens 5 seconds
  after it was created is kept and joins.
- **AC-8** With every random draw at its lowest, the tries after successive
  losses come 0.8, 1.6, 3.2, 6.4 and 6.4 seconds after each loss; at its
  highest, 1.2, 2.4, 4.8, 9.6 and 9.6 seconds; after a snapshot, the next loss
  is followed by a try 0.8 to 1.2 seconds later.

## Edge cases

- An erase and a pencil letter follow the stale rule; a `base_seq` above the
  room's seq is never stale; edits that reached the server before the loss are
  resent and apply again with no visible change (AC-2).
- A cell locked since the edit gets `cell_locked`, not `stale_edit`; with the
  limit reached, `rate_limited` comes before both (AC-2; `platform/realtime.md`
  AC-12).
- Two tabs never take the room from each other in a loop: 4001 is final (AC-3).
- A page hidden on a dead network keeps its socket until it is visible again,
  unless a close event comes first (AC-6).
- An `online` event replaces a socket stuck connecting before its 6 seconds
  (rule 6).

## Out of scope

- The socket, its messages and close codes, the silence check, the join
  deadline and the edit rate: `platform/realtime.md`.
- The join's steps, takeover with 4001, past players and the seat back:
  `lobby/joining.md`. Host hand-over on a time-out: `lobby/host.md`.
- The page's seq buffer and its other connection states: `client/shell.md`.
  The band's place on the screen: `client/hud.md`. Presence states in the
  roster and the cleared selection: `social/presence.md`.
- The restart step that starts the resume window again, the log and undo:
  `platform/server.md`. What changed while away: `social/catch-up.md`.
- Peer-to-peer sync, pending edits or kept requests across a reload, a leave
  message, message acknowledgements, pings from the server.

## Code

- `src/nock/room.py`: the stale rule among the edit checks, the time-outs in
  `tick` and in the join; `RoomConfig.resume_window_seconds`.
- `web/src/lib/roomSession.ts`, `RoomPage.svelte`: heartbeat, losses, retries,
  the selection sent again, resent edits, kept requests.
- Tests: `tests/test_spec_017_ac01_*`, `tests/test_spec_017_ac02_*`,
  `tests/test_spec_017_ac03_*`, `tests/test_spec_017_ac05_*`;
  `tests/test_reconnection_*` for AC-5 to AC-8.
