---
area: platform
file: live-rooms
status: approved
---

# platform/live-rooms - The rooms held in memory, the socket's lookup, engine time

## Purpose

Every room's rules run on one thread, so each step stays short whatever the
grid. A room is held in memory only while it is played, and a socket finds its
room in one lookup that never holds up the server.

## Depends on

- `platform/server.md`: the store, snapshots, loading and the restart step
  (rules 2, 4 and 6).
- `lobby/rooms.md`: the engine thread (rule 12) and the wrong-code throttle
  (rule 9).
- `lobby/lifetime.md`: the expired room a lookup deletes (rule 6).

## Rules

### Engine time

1. Every live room's step runs on the one engine thread (`lobby/rooms.md` rule
   12), so a step is bounded in time whatever the grid: the rules read the
   grid's lookups (`content/grids.md` rule 12) and never resolve a clue again.
   Measured on the rules alone, with no socket and no store, on FX-02, as the
   median of 5 runs after one warm-up: the edit that solves the grid takes
   under 5 ms; a check of the whole grid, every letter wrong, under 10 ms; the
   catch-up of an absence of 100 letters (`social/catch-up.md`) under 50 ms.
   No player sees a difference: the events, replies and answers are as before.

### Rooms in memory

2. A room is live, held in memory with its task, only while it is played:
   from when a socket opens to it until its task ends with no socket open to
   it, joined or not. Creating a room writes it to the store
   (`platform/server.md` rule 2) and holds nothing. When its task ends with no
   socket open, its snapshot is saved (`platform/server.md` rule 4) and it
   leaves memory; a room whose snapshot fails stays live until its task next
   ends or the server stops. The next socket loads it back by
   `platform/server.md` rule 6; its players are all disconnected already, so
   the restart step logs nothing. The number of live rooms has no cap.
3. A socket's lookup of its room is one registry call, `RoomRegistry.connect`,
   run in a worker thread, never on the server's event loop. In one step under
   the registry lock it deletes an expired room (`lobby/lifetime.md` rule 6),
   loads and replays a room not in memory (`platform/server.md` rule 6) and
   counts the socket (rule 2), then gives back the connection, or nothing for
   an unknown or expired code, which the wrong-code throttle then records
   (`lobby/rooms.md` rule 9). No other lookup is made for the socket, so a
   room is loaded once per socket. A handler cancelled while the call runs
   leaves the connection it gets back, so the room's count of open sockets
   stays right.

## Acceptance criteria

- **AC-1** In a FX-02 room with every letter cell right but one, the edit that
  fills the last cell is applied, `grid_solved` among its events, in under 5 ms
  by rule 1's measure.
- **AC-2** In a FX-02 room with a wrong letter in every letter cell, a check of
  the whole grid is applied, its `check_result` naming every cell wrong and no
  cell correct, in under 10 ms by rule 1's measure.
- **AC-3** The catch-up of an absence of 100 letters typed into an empty FX-02
  room is built, with its changed cells and completed words, in under 50 ms by
  rule 1's measure.
- **AC-4** A room created through `POST /api/rooms` is not live; a socket
  opened to it makes it live, and once that socket closes without joining the
  room is not live again.
- **AC-5** Ana and Bob are in a room; Ana types `T` at (1, 0) and closes her
  socket: the room stays live. Once Bob's closes, it is not live and the
  store's latest snapshot is at the room's seq. Ana's next socket finds `T`
  and her seat, and the log holds no entry between that seq and her join's.
- **AC-6** With a registry whose `connect` takes 1 second, a socket opening to
  Ana's room delays nobody: `GET /api/grids` and a second socket to another
  room, sent meanwhile, are answered within 200 ms; the first socket's join
  then gets its snapshot.
- **AC-7** A socket to a room not in memory makes the store load it once (one
  `load_room` read for that socket), with its restart step; a socket to
  `ZZZZZZ` loads nothing and closes with 4404; a second socket to the room
  while the first is open loads nothing.

## Edge cases

- A room's grid built from the store's JSON (`platform/server.md` rule 5) and
  one taken from the catalogue keep the same budgets: each builds its lookups
  once, when it is built (AC-1).
- A room whose snapshot fails as its last socket closes stays live, and is
  saved at the server's shutdown (AC-5).
- The shutdown saves no snapshot of a room that already left memory (AC-5).

## Out of scope

- The store, snapshots, loading, the restart step and undo:
  `platform/server.md`. Expiry and deletion: `lobby/lifetime.md`.
- The budgets measured in a browser or across sockets: `product.md` rules 21
  to 25.
- What the grid's lookups hold: `content/grids.md`. How many checks a room
  may run: `gameplay/hints.md`.

## Code

- `src/nock/room.py` (`handle_message`), `src/nock/catch_up.py`
  (`build_catch_up`), `src/nock/recap.py`: the rules of rule 1, reading
  `Grid.words` and `Grid.solution_letter`.
- `src/nock/hub.py`: `RoomRegistry.connect`, `live_codes`, rooms leaving
  memory.
- `src/nock/server.py`: the socket route's one call to `connect` in a worker
  thread.
- Tests: `tests/test_live_rooms_engine_time.py` for AC-1 to AC-3,
  `tests/test_live_rooms_in_memory.py` for AC-4 and AC-5,
  `tests/test_live_rooms_socket_responsiveness.py` for AC-6,
  `tests/test_live_rooms_socket_loads.py` for AC-7; the first and the third
  measure durations and so run on their own (`SERIAL_TEST_FILES`). Shared
  helpers: `tests/server_harness.py`, which the tests of other domains import
  too.
