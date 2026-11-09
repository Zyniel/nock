---
area: platform
file: server
status: approved
---

# platform/server - Durable rooms, undo, building the app

## Purpose

The server holds the only true room state and keeps it on disk, so a restart
loses nothing a player saw and every player gets their seat back. A player can
take back their last edit.

## Depends on

- `platform/realtime.md`: the messages, delivery by seq, refusals and close
  codes; the resume window and the resends are `platform/reconnection.md`.
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
   else, loads such a room and makes it live (`platform/live-rooms.md`
   rule 2), after one restart step run before anything else and logged like
   any step: each player not disconnected becomes disconnected at that time,
   with one `player_state_changed` each in roster order, selection and recent
   edits cleared. Their resume window runs from then
   (`platform/reconnection.md` rule 2). What the restart step does to chat
   windows, reaction windows, the vote and the timer: `social/chat.md` rule 7,
   `social/reactions.md` rule 7, `gameplay/votes.md`, `gameplay/rules.md`.
   Every other read (summaries, catch-up, the recaps, the account's rooms and
   history, the operator's edits) replays the room from the store without
   making it live, with no restart step and no log entry. A lookup that meets
   an expired room deletes it instead (`lobby/lifetime.md`).

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
   the edit rate (`platform/fair-play.md`).
9. The page: « Annuler » (`room.undo`), shown once joined, sends `undo`; so do
   Control+z and Meta+z while the grid has the focus, their default prevented;
   all until the grid is solved, when they send nothing and the button is
   disabled (`gameplay/rules.md` rule 6).
   An undo is sent after the edits pending when it was made and before any
   later edit, across a reconnection too (`platform/reconnection.md` rules 5
   and 7). An error `nothing_to_undo` shows `undo.nothing` (« Rien à annuler. »)
   for 3 seconds; no other error does. The undo's `letter_changed` only
   updates the confirmed grid (`gameplay/co-op.md` rule 12).

### Building the app

23. Importing `nock.server` builds no app and reads no file under `grids/`;
    the module has no `app` name. Each call of
    `create_app` builds one; `production_app()` builds the one `python -m
    nock` runs (`platform/serving.md` rule 6): `create_app` with the catalogue
    read from `grids/` of the repository, the other arguments left to their
    defaults.

### Look

« Annuler » and « Rien à annuler. »: `client/hud.md` rule 4 and
`client/room.md` rule 8, `_design/room.md`, « 3-second notes » and the two
top bars (« Phone top bar », « Computer top bar »).

## New interface

- `nock.server.production_app() -> FastAPI` (rule 23).

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
- **AC-27** As Ana types 250 letters in a FX-01 room, after the saves at seq
  100 and 200 the store holds two snapshots of the room, at seq 0 and 200;
  once her socket closes, at 0 and the room's seq only, the log whole, and the
  room loads with every letter; with her socket still open, the server's
  shutdown leaves 0 and the room's seq alike.
- **AC-28** In that room, Ana's catch-up from seq 150 to 250 answers the same
  cells, lines and names after the save that deleted the snapshot at 200 as
  before it, and the room's state at seq 150 reads the same; the state at or
  before the first snapshot's seq is still the first snapshot's.
- **AC-29** Offline, Ana types `T`, `A`, `M` from (1, 0); her Control+z,
  pressed offline after `M` or 50 ms after her reconnection snapshot, reaches
  the server after the three edits: every page ends with `T` at (1, 0), `A`
  at (1, 1) and (1, 2) empty. Pressed offline between `A` and `M`, it reaches
  the server between them: every page ends with (1, 1) empty and `M` at
  (1, 2).
- **AC-30** With every read of a file under `grids/` failing, `import
  nock.server` succeeds, reads no file under `grids/` and leaves the module
  with no `app`;
  `production_app()` then fails with that read's error.

## Edge cases

- A crash loses no event a player saw; an edit being applied when the process
  died is lost, and its page sends it again (`platform/reconnection.md` rule 7)
  (AC-3).
- A room that crashed without a snapshot still loads whole from its log (AC-1).
- An undo of an erase brings the letter back, authored by the undoer; an undo
  after one's own second edit of the same cell goes back one step only (AC-10).
- An undo restores the pencil flag of what it puts back (AC-10).
- An undo works after a restart: replay rebuilds each player's undo (AC-1).
- Loading an unknown code gives nothing and a lookup stays unknown (AC-7).
- A room whose first and newest snapshots are one row keeps that one; a save at
  the newest's seq replaces it (AC-27).
- A deleted snapshot's pages leave the WAL at the next checkpoint
  (`admin/operations.md` rule 2) (AC-27).

## Out of scope

- Several processes on one database, replication, backups, a real kill or
  power cut in tests, repairing a damaged database, multi-level undo, redo.
- Expiry, deletion and the sweep: `lobby/lifetime.md`. Logs and retention:
  `admin/operations.md`; the operator's replay of the log: `admin/ops-page.md`. What changed while away:
  `social/catch-up.md`. Client routing and its pages: `client/shell.md`.
- Serving the client, the HTTP edge and the environment variables, `main()`
  included: `platform/serving.md`. The run configuration, frame size and
  connection bounds: `product.md`.
- Engine time, the rooms held in memory and the socket's lookup:
  `platform/live-rooms.md`.

## Code

- `src/nock/store.py`: `RoomStore`. `src/nock/room.py`: `replay`,
  `after_restart`, undo in `handle_message`; `RoomConfig.snapshot_every`.
- `src/nock/hub.py`: commit before delivery, snapshots, loading, `close()`.
- `src/nock/server.py`: `create_app`, `production_app`, the store's path.
- `web/src/lib/RoomTopBar.svelte`, `gridKeys.ts`, `GridViewport.svelte`,
  `RoomPage.svelte`, `roomSession.ts`, `RoomNote.svelte`: the undo button,
  shortcut and message.
- Tests: `tests/test_spec_018_*`; `tests/test_server_*` for AC-27 to AC-30.
