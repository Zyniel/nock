---
id: "018"
title: Durable room state
status: done
---

# 018 - Durable room state

Epic E4 Real-time sync (US-4.4) · Release: MVP · Epic depends on: E3
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine
(`RoomState`, `LogEntry`, `Outcome`, the runtime and its delivery order) is defined
in spec 011, joins in spec 012, edits in specs 015 and 016. The messages are those
of spec 039.

## Goal

As a player, I want the room to survive a server incident, so that an hour of solving is never lost.

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests.

## Public interface

### `nock.store`: SQLite log and snapshots

```python
# src/nock/store.py
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from nock.room import LogEntry, RoomState


class RoomStore:
    """Rooms on disk: an append-only event log per room plus state snapshots.

    A plain class (a service, not data). Safe to call from several threads.
    """

    def __init__(self, path: str | Path) -> None:
        """Open or create the SQLite database at `path` (":memory:" for an
        in-memory one) and create its tables when missing. A file database
        uses journal_mode WAL and synchronous FULL."""

    def create_room(self, state: RoomState) -> None:
        """Record a new room and `state` as its first snapshot.

        Raises:
            ValueError: a room with `state.code` already exists.
        """

    def has_room(self, code: str) -> bool:
        """Tell whether room `code` exists in the store."""

    def append(self, code: str, entries: Sequence[LogEntry]) -> None:
        """Append `entries` to the log of room `code`, in one transaction that is
        committed before this method returns.

        Raises:
            ValueError: unknown room, or the entries' seqs are not exactly
                last_seq + 1, last_seq + 2, ... (last_seq: the room's highest
                logged seq, or its first snapshot's seq when the log is empty).
                Nothing is written then.
        """

    def read_log(self, code: str, after_seq: int = 0) -> list[LogEntry]:
        """The logged entries of room `code` with seq > after_seq, in seq order.
        An unknown room gives []."""

    def save_snapshot(self, state: RoomState) -> None:
        """Store `state` as a snapshot of room `state.code` at `state.seq`
        (replacing one at the same seq). Raises ValueError for an unknown room."""

    def load_room(self, code: str) -> RoomState | None:
        """The room's state: its snapshot with the highest seq, then
        `replay` of every logged entry after it, in order. None when unknown."""

    def close(self) -> None:
        """Close the database. Idempotent."""
```

Table layout and JSON columns are the implementer's choice; `LogEntry` and
`RoomState` are written with `model_dump_json()` and read with
`model_validate_json()`. The log is never rewritten or truncated (deletion at
expiry is spec 032's).

### `nock.room` functions built by this spec

```python
# src/nock/room.py (signatures fixed in spec 011)
def replay(state: RoomState, entry: LogEntry) -> RoomState:
    """Return the state after the logged `entry`, as the live step that made it
    left it, for every field the log carries. See "Replay"."""


def after_restart(state: RoomState, now: float) -> Outcome:
    """A room loaded in a new process: every player not disconnected becomes
    disconnected (disconnected_at = now, selection None, recent_edits ()), one
    PlayerStateChanged(disconnected) entry each, in players order."""
```

Replay rules, by `entry.event.type` (each sets `state.seq = event.seq`):

| Event | Effect on the state |
| --- | --- |
| `player_joined` | a `PlayerRecord` built from the view, `resume_token = entry.resume_token`, `joined_seq = seq`, `last_input_at = last_seen_at = entry.at`, appended |
| `player_state_changed` | the player's `state`; `disconnected_at = entry.at` when `disconnected`, else `None` |
| `player_left` | the player is removed; with reason `removed`, their token is added to `removed_tokens` |
| `letter_changed` | the cell's `letter`, `pencil`, `author` (the player, or `None` for an empty letter), `wrong = False`, `changed_seq`, `changed_by`; when `entry.undo` is False, the player's `last_edit` = the cell as it was before; when True, their `last_edit = None` |
| `cell_locked` | the cell's `letter`, `locked = True`, `revealed`, `author = None` if revealed, `changed_seq`, `changed_by = None` |
| `settings_changed` | `settings`, `reveal_budget` |
| `host_changed` | `is_host` True on that player, False on every other |
| `player_muted` | the player's `muted` |
| other types | owned by later specs (023 to 027), which extend this table; until then only `seq` |

Fields the log does not carry are not restored by replay: `selection`,
`recent_edits`, and `last_input_at` / `last_seen_at` after the join. A loaded room
goes through `after_restart`, which resets them anyway.

### `nock.hub`: registry with a store

```python
# src/nock/hub.py (changes)
class RoomRegistry:
    def __init__(
        self,
        *,
        config: RoomConfig | None = None,
        clock: Clock | None = None,
        store: RoomStore | None = None,     # new; None: RoomStore(":memory:")
    ) -> None: ...
```

- `register_room` and `add_room` also call `store.create_room(state)`; a code that
  exists in the store counts as taken.
- Delivery step 1 of spec 011 becomes real: a step's entries are appended with
  `store.append` (committed) before any of them is sent.
- After every `config.snapshot_every` logged events of a room, and when the room
  task stops, the hub saves a snapshot of that room.
- `find_room`, `room_state` and a socket for a code that is not live but is in the
  store load it with `store.load_room`, make it live, and run one step with
  `after_restart(state, clock())` (logged like any step) before anything else.
- `close()` saves a snapshot of each live room, then closes the store if the
  registry created it.

### `nock.server`

- `create_app(rooms=None)` builds `RoomRegistry(store=RoomStore(path))` with
  `path` from the environment variable `NOCK_DATABASE`; when it is unset or empty,
  the store is `":memory:"` (nothing is written to disk, so tests never create
  files). The store is opened when the app starts (lifespan), not at import, and
  the registry is closed when the app stops. A registry passed as `rooms` is never
  closed by the app. (Note from the lead, 2026-10-16: "or empty" added: an empty
  `NOCK_DATABASE` counts as unset, like the other technical variables (spec 036
  decision 15). The app used to hand `""` to `RoomStore`, which SQLite opens as a
  private temporary file. Spec 036 AC-12 tests it: it replaces
  `nock.server.RoomStore`, the class the app calls when it starts, with a
  subclass that records the path. `python -m nock` also refuses, before the app
  starts, a `NOCK_DATABASE` that holds a control character, a line or paragraph
  separator, or a format character other than the zero width joiner and
  non-joiner (Unicode categories Cc, Zl, Zp and Cf; spec 036 AC-11).) (Note from
  the lead, 2026-10-16: "a control character or another invisible character"
  became "a control character, a line or paragraph separator, or a format
  character other than the zero width joiner and non-joiner", since spec 036
  allows those two, which are invisible too, and refuses every other format
  character, visible or not (review of spec 036's refinement).)
- The production run command sets it, for example
  `NOCK_DATABASE=data/nock.sqlite3 uv run python -m nock` (the
  implementer documents it in `README.md`). (Note from the lead, 2026-10-15: the
  command used to be `NOCK_DATABASE=data/nock.sqlite3 uv run uvicorn nock.server:app`.
  That command skips spec 036's 8,192-byte frame limit, which only
  `python -m nock` sets, through `server_config`; the README already says
  `uv run python -m nock`.)

### Undo (`nock.room.handle_message` for `Undo`)

A player's `last_edit` is set by each of their accepted edits (spec 015) to the
cell as it was before, with the edit's seq. `Undo` from player `p`:

1. `p.last_edit` is None: refused, `ErrorMessage(code=NOTHING_TO_UNDO)`.
2. The cell of `p.last_edit` has `changed_seq != last_edit.seq` (someone, `p`
   included, changed it since: an edit, an undo, a lock), or is locked: refused,
   `NOTHING_TO_UNDO`, and `p.last_edit` becomes None.
3. (spec 026) the grid is solved: refused, `GRID_SOLVED`.
4. Otherwise, with `seq = state.seq + 1`: the cell gets back the `letter` and
   `pencil` of `last_edit`, `author = p` when that letter is not None (else
   `None`), `wrong = False`, `changed_seq = seq`, `changed_by = p`;
   `p.last_edit = None`; one entry
   `LogEntry(at=now, event=LetterChanged(seq, row, column, letter, pencil, player_id=p), undo=True)`.

Undo is one level: after an undo, a second undo answers `nothing_to_undo` until
`p` edits again. An undo is not an edit for spec 037's rate limit.

### Client: undo

- `data-testid="undo-button"`, shown once joined, text `t("room.undo")`; clicking it
  sends `{"type": "undo"}`.
- `Control+z` and `Meta+z` while the `grid` element has the focus send the same
  message and prevent the default (an exception to spec 008's "modifiers are left
  to the browser").
- An `error` with code `nothing_to_undo` shows `data-testid="undo-message"` with
  `t("undo.nothing")` for 3 seconds.
- The undo's result arrives as a normal `letter_changed` (spec 015), from `you`;
  since no edit is pending for it, it does not touch the pending queue (only an
  own `letter_changed` matching the oldest pending edit's cell and letter removes
  it, see "Pending queue matching").

Pending queue matching (refines spec 015): an own `letter_changed` removes the
oldest pending edit only when it is for the same cell and letter as that edit;
otherwise (an undo's result) it updates the confirmed grid and leaves the queue.

New `fr.json` keys:

| Key | Value |
| --- | --- |
| `room.undo` | `Annuler` |
| `undo.nothing` | `Rien à annuler.` |

### Test harness

- Store criteria use `RoomStore(tmp_path / "nock.sqlite3")`.
- Simulated restart (AC-1): process one is `RoomRegistry(store=RoomStore(path))`
  with its app and TestClient; when the test stops it, it neither closes the
  registry nor the store (as a crash would not), and drops them; process two is a
  new `RoomStore(path)`, a new registry and a new app. Both run in the test process.
- Mid-game join (AC-2): two writer threads keep sending edits
  (`RoomConfig(max_edits_per_second=1000, max_inbound_pending=1000)`, so that
  spec 036's inbound cap does not close the test's sockets) while a third client
  joins. (Note from the lead, 2026-10-14: `max_inbound_pending=1000` added.
  Spec 036 AC-6 closes with 1008 (`FLOOD_CLOSE_CODE`) a connection with more
  than `max_inbound_pending` unapplied inputs, 100 by default, and the writers
  send their 200 edits each faster than the room applies them. 1000 is above
  any connection's burst here (200 edits). The default stays at 100: real
  players never queue that many inputs.)

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-4.4.1) (Python; WebSocket with a simulated restart) Given a server restart during a game, when players reconnect, then at most the last second of edits is missing. Python: a FX-01 room is created with `create_room`, then driven by 250 steps of `join_room` and `handle_message` (3 joins, edits, erases, undos), each step's entries appended; `load_room` returns a state whose `grid_state` and `player_views` equal those of the live state, with the same `seq` and the same resume tokens; the same holds when a snapshot of the live state was saved at seq 100; a hand-made entry `PlayerLeft(seq=<next>, player_id=<p2>, reason="removed")` appended then loaded removes `p2` and puts `p2`'s token in `removed_tokens`; `append` with a gap in seqs raises `ValueError` and writes nothing. WebSocket: in process one, `Ana` and `Bob` join a FX-01 room and type 30 letters; each time Bob's client receives a `letter_changed` with seq `n`, a separate `RoomStore(path).read_log(code)` already holds seq `n`; then process one stops and process two starts on the same file; Ana reconnects with her resume token and gets a `Snapshot` whose `you` is Ana's id, whose players keep their nicknames and colours, and whose `grid` letters and authors equal the grid Bob's client held before the restart; Bob's reconnection gets the same grid.
- **AC-2** (AC-4.4.2) (WebSocket) A player joining mid-game receives the full state in one message, then every later edit with none skipped. While `Ana` and `Bob` each send 200 edits on random letter cells, `Cy` joins after the room's `seq` passed 50; Cy's first message is a `Snapshot` with `seq = s`; every later message Cy receives with a `seq` has seq `s + 1`, `s + 2`, ... with no gap and no repeat up to the room's final `seq`; and Cy's grid (snapshot plus events applied in order) equals `grid_state(room_state(code))` once the edits stop. The same holds for a room loaded from the store after a simulated restart (AC-1).
- **AC-3** (AC-4.4.3) (Python; WebSocket; browser with mocked socket) Undo reverts my own last edit, and only when nobody has changed that cell since. Python, on FX-01 with players `p1`, `p2`: `p1` writes `T` at (1, 0) then undoes: one `letter_changed` entry with `letter=None`, `player_id="p1"`, `undo=True`, and the cell is empty again; `p1` writes `A` over `p2`'s `B` at (1, 1) then undoes: the cell holds `B` again with `author="p1"`; `p1` writes `T` at (1, 0), `p2` writes `X` there, `p1` undoes: refused with `nothing_to_undo`, the cell keeps `X`; a second undo right after a successful undo is refused with `nothing_to_undo`; `p1` writes `M` at (1, 2), the cell is then locked, `p1` undoes: `nothing_to_undo`. WebSocket: the first and third Python cases over two clients, where the other client receives the undo's `letter_changed` and nothing for the refused undo. Browser: on the joined page, clicking `undo-button` sends `Undo()`, and with the grid focused `Control+z` sends `Undo()`; when the mock answers `error` with code `nothing_to_undo`, `undo-message` shows `fr.json["undo.nothing"]`.
- **AC-4** (new) (Python; WebSocket via TestClient with a `RoomStore` subclass passed as `store=`) Saving comes first, and a failed save changes nothing. (a) With a store whose `append` blocks until the test releases it, no client receives an event before the `append` that holds it has returned. (b) With a store whose `append` raises, an edit's step is dropped: no client receives any event or reply for it, `room_state` is unchanged, and the room goes on processing later inputs once `append` works again. (c) When the commit of a join fails, the joining socket is closed with code 1011 and no player is added. (d) `RoomRegistry.close()` saves a snapshot of each live room, observable through `load_room` after closing, even when the room task did not stop on its own first.

## Edge cases and errors

Note from the lead (2026-10-11, after the spec 015 review): spec 015's
accepted edit does not set `PlayerRecord.last_edit` yet. This spec owns it:
its implementation must set `last_edit` on every accepted edit and erase, and
its undo tests cover that.

- Commit before broadcast (AC-1): every event any client received was committed
  first, so a crash loses no event a player saw; an edit that was being applied
  when the process died is lost and its sender's page resends it (spec 017). This
  is stricter than the "last second" of the criterion.
- Crash without close (AC-1): no snapshot was saved at the end; `load_room` replays
  the log after the last snapshot, so the state is complete.
- After a restart (AC-1): every player is `disconnected` until they reconnect, with
  the five-minute window of spec 017 starting at the restart time; the
  `after_restart` events are logged and numbered like any other, so the
  reconnecting players' snapshots include them.
- Removed players after a restart (AC-1): still refused (`removed_tokens` is
  replayed from `player_left` with reason `removed`).
- Gaps (AC-1): `append` refuses entries that do not follow the last seq, and an
  empty `entries` writes nothing and raises nothing.
- Corrupt database (AC-1): a log row that fails `model_validate_json` makes
  `load_room` raise `pydantic.ValidationError`; repairing is out of scope.
- Unknown codes (AC-1): `load_room` and `has_room` of an unknown code give `None`
  and `False`; `read_log` gives `[]`.
- Mid-game snapshot (AC-2): the joiner's own `player_joined` is not sent to it;
  its snapshot already includes it (spec 012).
- Undo of an erase (AC-3): restores the erased letter, authored by the undoer.
- Undo of my edit after my own later edit elsewhere (AC-3): `last_edit` points to
  my latest edit only; earlier edits cannot be undone.
- Undo of my edit after I edited the same cell again (AC-3): undoes the latest one
  only, back to my previous letter.
- Undo on an untouched cell (AC-3): impossible; `last_edit` is None before any edit.
- Undo and pending edits (AC-3): pressing undo while my last edit is still pending
  sends the undo after it; the server applies both in order.
- Snapshots (AC-1): with `snapshot_every=100`, a room with 250 events has snapshots
  at seq 0 (creation), 100 and 200 at least.

## Out of scope

- Peer-to-peer sync (epic E4).
- Shared letters: spec 015.
- Same-cell conflicts: spec 016.
- Disconnection, reconnection and the resend queue: spec 017.
- Multi-level undo and redo.
- Several server processes sharing one database, replication, backups.
- A real process kill or power cut in CI (see decision 2).
- Expiry and deletion of rooms (spec 032), the operator replay tool (spec 038 AC-4,
  which reads `read_log`), catch-up after an absence (spec 034).

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written.
Each one is already part of the spec above.

1. Undo stays in this spec (answered by the human).
2. Testing a restart (AC-1). Options: an in-process simulated restart (a second
   store and registry on the same file, the first dropped without closing), or a
   real `uvicorn` subprocess killed with `kill()`. Pick: in-process simulated
   restart, plus the check that each received event is already in the database
   when it arrives. Not covered: an operating-system crash or power cut, where
   `synchronous=FULL` is relied on, and a real process kill.
3. "At most the last second". Options: commit each step before sending it (nothing
   seen is ever lost), or batch commits every second (faster, may lose up to a
   second). Pick: commit each step, which meets the criterion with margin; a
   SQLite commit on WAL is well under the 100 ms budget of spec 015.
4. What the log holds. Options: the clients' inputs (replayed through the rules), or
   the server events. Pick: the server events exactly as sent (`LogEntry.event`),
   plus two private fields the events cannot carry: the new player's
   `resume_token` and the `undo` flag. The operator replay (spec 038) and catch-up
   (spec 034) read the same log.
5. Undo depth and author. Options: one level or a stack; after undoing over another
   player's letter, the restored letter is authored by its old author or by me.
   Pick: one level ("my own last edit"), and authored by me, because
   `letter_changed` carries a single `player_id` that the page takes as the author
   (spec 015); keeping the old author would need a new protocol field.
6. Undo refused when the cell changed. Pick: `nothing_to_undo`, and the entry is
   dropped, since that edit can never be undone afterwards.
7. Database location. Pick: `NOCK_DATABASE` environment variable, in-memory when
   unset or empty, so imports and tests never write files; the README documents
   the production setting. (Note from the lead, 2026-10-16: "or empty" added; see
   "`nock.server`" and spec 036 decision 15.)
8. Pending queue and undo. An undo's `letter_changed` comes from `you` but answers
   no pending edit, which spec 015's plain FIFO would mismatch. Pick: an own
   `letter_changed` removes the oldest pending edit only when cell and letter match
   it.

Added after the review, decided by the lead on 2026-10-11 under the human's
instruction to take technical decisions:
- Commit before delivery gets a test that can fail, and a failed commit drops
  the step; a joiner whose join cannot be saved is closed with 1011 rather than
  left waiting; `close()` saves a snapshot of every live room (AC-4).

## Open questions

None.
