---
area: platform
file: server
status: done
---

# platform/server - Durable rooms, undo, engine time, rooms in memory

## Purpose

The server holds the only true room state and keeps it on disk, so a restart
loses nothing a player saw and every player gets their seat back. A player can
take back their last edit. Every room's rules run on one thread, so each step
stays short whatever the grid, and a room is held in memory only while it is
played.

## Depends on

- `platform/realtime.md`: the messages, delivery by seq, refusals, close codes
  and the resume window.
- `lobby/joining.md`: resume and seat back; room expiry and deletion are
  `lobby/lifetime.md`.
- `gameplay/co-op.md`: the edits that undo reverses and the page's pending
  edits.

## Rules

### The store

1. Rooms live in a SQLite store (`src/nock/store.py`): the file
   `NOCK_DATABASE` (journal WAL, synchronous FULL; its check:
   `platform/serving.md` rule 9) or, when it is unset or empty, an in-memory
   database that writes no file. The app opens the store
   when it starts, never at import, and closes it when it stops. A registry
   handed to `create_app`, and a store handed to a registry, are never closed
   by them. The store is safe to use from several threads.
2. A room is written to the store when it is created, with its state as the
   first snapshot (seq 0). Its log then holds every event, exactly as sent and
   with its time, plus private fields (the joiner's resume token on a join, the
   undo flag, the relay time of `admin/operations.md`). Seqs follow one another
   with no gap: entries that skip or repeat a seq are refused and none is
   written. The log is only appended to, except when the room is deleted
   (`lobby/lifetime.md`) or a deleted account's nickname is erased
   (`account/account.md`).
3. A step's entries are committed before any of them reaches a socket. A step
   the store cannot commit is dropped: no event and no reply go out, the room
   is as before, and later inputs apply as usual. A join that cannot be
   committed adds nobody and closes its socket with 1011.
4. A snapshot of a live room is saved after the step that brings the events
   it logged since its last snapshot to `RoomConfig.snapshot_every` (100) or
   more; when the room stops running, its last socket gone; and for every live
   room when the server shuts down. The count starts at 0 when the room
   becomes live in this process, and the restart step's entries are not
   counted. A failed snapshot is logged; the log alone rebuilds the room. A
   room keeps two snapshots, its first (the lowest seq) and its newest (the
   highest): each save, in its own transaction, deletes every other snapshot
   of the room, and runs no checkpoint (`admin/operations.md` rule 2).

### Loading and restart

5. A stored room is its latest snapshot, then a replay of each later log entry
   in order. Replay rebuilds every field the log carries: cells, players and
   their order, tokens, removed tokens (the newest 100, `lobby/host.md` rule
   2), past players, each player's undo, and the fields of the other domains
   (settings, budget, flags, chat (the newest 200, `social/chat.md` rule 8), an
   open vote with its requester's yes, completion, the timer). Selections,
   recent edits, input times, the other ballots and the chat and reaction
   windows are not logged. A damaged row makes the load fail; nothing repairs
   it. The room's state at an earlier seq, which a catch-up asks for
   (`social/catch-up.md`), is the newest snapshot at or before that seq, so the
   first one for any seq below the newest's, then a replay of the log up to
   that seq: the same cells and players whatever snapshots a save deleted
   since.
6. A code held only in the store is taken. A socket to the room, and nothing
   else, loads such a room and makes it live (rule 21), after one restart
   step run before anything else and logged like any step: each
   player not disconnected becomes disconnected at that time, with one
   `player_state_changed` each in roster order, selection and recent edits
   cleared. Their resume window runs from then (`platform/realtime.md`). What
   the restart step does to chat windows, the vote and the timer:
   `social/chat.md`, `gameplay/hints.md`, `gameplay/rules.md`. Every other
   read (summaries, catch-up, the recaps, the account's rooms and history, the
   operator's edits) replays the room from the store without making it live,
   with no restart step and no log entry. A lookup that meets an expired room deletes
   it instead (`lobby/lifetime.md`).

### Undo

7. A player's undo is their latest accepted edit (`gameplay/co-op.md`) with the
   cell as it was before it; each player holds their own. A refused edit
   leaves it as it was.
8. `undo` is input, so it first wakes an idle sender (`social/presence.md`),
   refused or not. Then, the first that applies:
   1. no undo held: `nothing_to_undo`;
   2. the cell changed since (an edit or undo by anyone, the sender included) or
      is locked: `nothing_to_undo`, and that edit can never be undone;
   3. a solved grid: `grid_solved` (`gameplay/rules.md`);
   4. else the cell gets back its letter and pencil flag, authored by the
      sender (none when empty), with no wrong strike, in one `letter_changed`
      from the sender to every player, logged as an undo. The sender's undo is
      then empty.

   A refusal goes to the sender alone. Undo is one level and is not counted in
   the edit rate.
9. The page: « Annuler » (`room.undo`), shown once joined, sends `undo`; so do
   Control+z and Meta+z while the grid has the focus, their default prevented;
   all until the grid is solved, when they send nothing and the button is
   disabled (`gameplay/rules.md` rule 6).
   An undo made while edits are pending is sent after them. An error
   `nothing_to_undo` shows `undo.nothing` (« Rien à annuler. ») for 3 seconds;
   no other error does. The undo's `letter_changed` only updates the confirmed
   grid (`gameplay/co-op.md` rule 12).

### Engine time

20. Every live room's step runs on the one engine thread (`lobby/rooms.md` rule
    12), so a step is bounded in time whatever the grid: the rules read the
    grid's lookups (`content/grids.md` rule 12) and never resolve a clue again.
    Measured on the rules alone, with no socket and no store, on FX-02, as the
    median of 5 runs after one warm-up: the edit that solves the grid takes
    under 5 ms; a check of the whole grid, every letter wrong, under 10 ms; the
    catch-up of an absence of 100 letters (`social/catch-up.md`) under 50 ms.
    No player sees a difference: the events, replies and answers are as before.

### Rooms in memory

21. A room is live, held in memory with its task, only while it is played:
    from when a socket opens to it until its task ends with no socket open to
    it, joined or not. Creating a room writes it to the store (rule 2) and
    holds nothing. When its task ends with no socket open, its snapshot is
    saved (rule 4) and it leaves memory; a room whose snapshot fails stays
    live until its task next ends or the server stops. The next socket loads
    it back by rule 6; its players are all disconnected already, so the
    restart step logs nothing. The number of live rooms has no cap.
22. A socket's lookup of its room is one registry call, `RoomRegistry.connect`,
    run in a worker thread, never on the server's event loop. In one step under
    the registry lock it deletes an expired room (`lobby/lifetime.md` rule 6),
    loads and replays a room not in memory (rule 6) and counts the socket (rule
    21), then gives back the connection, or nothing for an unknown or expired
    code, which the wrong-code throttle then records (`lobby/rooms.md` rule 9).
    No other lookup is made for the socket, so a room is loaded once per
    socket. A handler cancelled while the call runs leaves the connection it
    gets back, so the room's count of open sockets stays right.

### Look

« Annuler » and « Rien à annuler. »: `client/hud.md` rule 4 and
`client/room.md` rule 8, `_design/room.md`, « 3-second notes » and the two
top bars (« Phone top bar », « Computer top bar »).

## Acceptance criteria

- **AC-1** A FX-01 room driven through 250 steps (3 joins, edits, erases,
  undos) loads from the store with the live room's grid, players, seq and
  resume tokens, from its first snapshot or from one at seq 100; after a
  logged removal of p2, p2 is gone and p2's token is banned. (← 018 AC-1)
- **AC-2** Appending entries that skip a seq, repeat one or start after the
  wrong seq is refused and writes none of them; an empty append writes nothing.
  (← 018 AC-1)
- **AC-3** Each time Bob's client receives `letter_changed` seq n, another
  reader of the database already finds seq n; with the store's write held, no
  client receives the event until it returns. (← 018 AC-1, 018 AC-4)
- **AC-4** With the store failing, Ana's `T` at (1, 0) reaches nobody, gets no
  answer and leaves the room as it was; once it works, her `E` at (1, 1) takes
  seq 3 and reaches both players. A join it cannot save is closed with 1011,
  with no snapshot and no player added. (← 018 AC-4)
- **AC-5** A snapshot is saved at seq 100 and at seq 200 as Ana types; at seq
  12 once her socket closes, Ana disconnected; and, with Ana still connected,
  at seq 11 when the server shuts down: each time the room loads again
  although a log row before it is damaged. (← 018 AC-1, 018 AC-4)
- **AC-6** Ana and Bob type 30 letters; the process stops without closing and
  a new one starts on the same file; Ana's token gets a snapshot with her id,
  both players' nicknames and colours, and the grid Bob held, and Bob's token
  gets the same grid. (← 018 AC-1)
- **AC-7** A 250-event room found only in the store, once looked up, is at
  seq 253: its three players disconnected at that time by three logged
  `player_state_changed` in roster order, selections cleared; Dan then joins
  at seq 254 beside `ANA`, `BOB`, `CLEO`, disconnected. (← 018 AC-1)
- **AC-8** While Ana and Bob send 200 edits each, Cy joins past seq 50: Cy's
  first message is a snapshot at seq s, then every event from s + 1 to the
  last with no gap or repeat and not Cy's own `player_joined`; Cy's grid ends
  as the server's. The same holds in a room loaded after a restart.
  (← 018 AC-2)
- **AC-9** With `NOCK_DATABASE` naming a file, the file appears when the app
  starts, not before, and holds a room created through it; unset or `""`, no
  file is written and the store is opened as `:memory:`. (← 018 AC-1,
  036 AC-12)
- **AC-10** p1 writes `T` at (1, 0) then undoes: one `letter_changed` with no
  letter from p1, logged as an undo, reaches both clients and the cell is
  empty; p1's `A` over p2's `B` at (1, 1), undone, gives `B` authored by p1.
  (← 018 AC-3)
- **AC-11** p1's undo is `nothing_to_undo` before any edit, after p2 wrote `X`
  over p1's `T` (the cell keeps `X`), right after a successful undo, and after
  the cell was locked; the other client receives nothing. (← 018 AC-3)
- **AC-12** Once joined, « Annuler » shows; a click sends one `undo`, and
  Control+z or Meta+z with the grid focused sends one with its default
  prevented, while Control+z with the focus elsewhere sends nothing; after a
  typed `T` still pending, a click sends `edit_letter` then `undo`.
  (← 018 AC-3)
- **AC-13** An error `nothing_to_undo` shows « Rien à annuler. » for about 3
  seconds; an error `not_host` does not. (← 018 AC-3)
- **AC-20** In a FX-02 room with every letter cell right but one, the edit that
  fills the last cell is applied, `grid_solved` among its events, in under 5 ms
  by rule 20's measure.
- **AC-21** In a FX-02 room with a wrong letter in every letter cell, a check of
  the whole grid is applied, its `check_result` naming every cell wrong and no
  cell correct, in under 10 ms by rule 20's measure.
- **AC-22** The catch-up of an absence of 100 letters typed into an empty FX-02
  room is built, with its changed cells and completed words, in under 50 ms by
  rule 20's measure.
- **AC-23** A room created through `POST /api/rooms` is not live; a socket
  opened to it makes it live, and once that socket closes without joining the
  room is not live again.
- **AC-24** Ana and Bob are in a room; Ana types `T` at (1, 0) and closes her
  socket: the room stays live. Once Bob's closes, it is not live and the
  store's latest snapshot is at the room's seq. Ana's next socket finds `T`
  and her seat, and the log holds no entry between that seq and her join's.
- **AC-25** With a registry whose `connect` takes 1 second, a socket opening to
  Ana's room delays nobody: `GET /api/grids` and a second socket to another
  room, sent meanwhile, are answered within 200 ms; the first socket's join
  then gets its snapshot.
- **AC-26** A socket to a room not in memory makes the store load it once (one
  `load_room` read for that socket), with its restart step; a socket to
  `ZZZZZZ` loads nothing and closes with 4404; a second socket to the room
  while the first is open loads nothing.
- **AC-27** As Ana types 250 letters in a FX-01 room, after the saves at seq
  100 and 200 the store holds two snapshots of the room, at seq 0 and 200;
  once her socket closes, at 0 and the room's seq only, the log whole, and the
  room loads with every letter; with her socket still open, the server's
  shutdown leaves 0 and the room's seq alike.
- **AC-28** In that room, Ana's catch-up from seq 150 to 250 answers the same
  cells, lines and names after the save that deleted the snapshot at 200 as
  before it, and the room's state at seq 150 reads the same; the state at or
  before the first snapshot's seq is still the first snapshot's.

## Edge cases

- A crash loses no event a player saw; an edit being applied when the process
  died is lost, and its page sends it again (`platform/realtime.md`) (AC-3).
- A room that crashed without a snapshot still loads whole from its log (AC-1).
- An undo of an erase brings the letter back, authored by the undoer; an undo
  after one's own second edit of the same cell goes back one step only (AC-10).
- An undo restores the pencil flag of what it puts back (AC-10).
- An undo works after a restart: replay rebuilds each player's undo (AC-1).
- Loading an unknown code gives nothing and a lookup stays unknown (AC-7).
- A room's grid built from the store's JSON (rule 5) and one taken from the
  catalogue keep the same budgets: each builds its lookups once, when it is
  built (AC-20).
- A room whose snapshot fails as its last socket closes stays live, and is
  saved at the server's shutdown (AC-24).
- The shutdown saves no snapshot of a room that already left memory (AC-24).
- A room whose first and newest snapshots are one row keeps that one; a save at
  the newest's seq replaces it (AC-27).
- A deleted snapshot's pages leave the WAL at the next checkpoint
  (`admin/operations.md` rule 2) (AC-27).

## Out of scope

- Several processes on one database, replication, backups, a real kill or
  power cut in tests, repairing a damaged database, multi-level undo, redo.
- Expiry, deletion and the sweep: `lobby/lifetime.md`. Logs, retention and the
  operator's replay of the log: `admin/operations.md`. What changed while away:
  `social/catch-up.md`. Client routing and its pages: `client/shell.md`.
- Serving the client, the HTTP edge and the environment variables, `main()`
  included: `platform/serving.md`. The run configuration, frame size and
  connection bounds: `product.md`; the budgets measured in a browser or across
  sockets: `product.md` rules 21 to 25.
- What the grid's lookups hold: `content/grids.md`. How many checks a room
  may run: `gameplay/hints.md`.

## Code

- `src/nock/store.py`: `RoomStore`. `src/nock/room.py`: `replay`,
  `after_restart`, undo in `handle_message`; `RoomConfig.snapshot_every`.
- `src/nock/hub.py`: commit before delivery, snapshots, loading, rooms
  leaving memory, `close()`.
- `src/nock/room.py` (`handle_message`), `src/nock/catch_up.py`
  (`build_catch_up`), `src/nock/recap.py`: the rules of rule 20, reading
  `Grid.words` and `Grid.solution_letter`.
- `src/nock/server.py`: `create_app`, the store's path, the socket route's one
  call to `connect` in a worker thread.
- `web/src/lib/RoomTopBar.svelte`, `GridViewport.svelte`, `RoomPage.svelte`,
  `roomSession.ts`, `RoomNote.svelte`: the undo button, shortcut and message.
- Tests: `tests/test_spec_018_*`; `tests/test_server_engine_time.py` for rule
  20, which measures durations and so runs on its own (`SERIAL_TEST_FILES`), as
  does the file of AC-25; `tests/test_server_*` for AC-23 to AC-28.
