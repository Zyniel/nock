"""Tests of admin/operations, AC-22, AC-23 and AC-25's busy timeout: the checkpoint.

`nock.store.checkpoint_wal` is rule 20's one checkpoint. These tests count its
calls and read its answers without timing anything:

- AC-22 and the busy timeout of AC-25 run it on a `sqlite3.Connection` subclass
  (`FakeCheckpointConnection`) whose `execute` answers `PRAGMA wal_checkpoint`
  with a row of its own, `(busy, 0, 0)`, the way SQLite does. The function is
  assumed to run the checkpoint with `connection.execute(...)` and to read the
  first column of its row as `busy`. The subclass also tells which busy timeout
  the connection had at each try.
- AC-23 replaces `checkpoint_wal` by a recorder that returns the answer a test
  chooses, and runs the six operations of the criterion on a file and in memory.
  The recorder is set on `nock.store` and on `nock.accounts`, whichever module the
  account store looks the function up in (`raising=False` on the second). The
  erasure done with no address (`finish_erasure`) is read on a file with the real
  checkpoint, in a test of its own. With the same recorder, the three other writes
  of an erasure (`begin_attempt`, `mark_player_erased`, `count_deleted_room`) run
  none on a file, and still count the attempt, mark the player and count the room.
  A `save_snapshot` that deletes an older snapshot of its room (`platform/server.md`
  rule 4) runs none either, on a file, and still leaves the room's first and newest
  snapshots.

The time bounds of AC-24 and AC-25 are in `test_operations_checkpoint_busy.py`.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest

import nock.store
from account_harness import erasure_rows
from lifetime_harness import select_rows
from nock.accounts import AccountStore, ErasedPlayer, RoomIdentity
from nock.grid import Grid
from nock.room import FORMER_PLAYER_NICKNAME, new_room
from nock.store import RoomStore
from operations_harness import LOGGER_PREFIX, write_room
from spec029_harness import Player, play_fx01
from spec032_harness import ANA, BOB, NO_TICK_CONFIG, T0, TA, TB, Run, grid_from_text
from spec033_harness import ANA_EMAIL, database_bytes, strings_in

if TYPE_CHECKING:
    from _typeshed import SupportsLenAndGetItem

CODE = "QJ7WXK"
BUSY_TIMEOUT_SECONDS = 5.0
BUSY_TIMEOUT_MS = 5000
LINK_LIFE_SECONDS = 1_800.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-22 and AC-25: checkpoint_wal on a connection that fakes its answers --------


class FakeCheckpointConnection(sqlite3.Connection):
    """A file connection whose `PRAGMA wal_checkpoint` reports what the test says.

    `busy_answers` holds the `busy` column of each checkpoint in turn; the last one
    repeats when there are more checkpoints than answers. `checkpoints_run` counts
    the checkpoints and `busy_timeouts_seen` holds the connection's busy timeout in
    milliseconds at each of them. Every other statement runs on the real database.
    """

    busy_answers: list[int]
    checkpoints_run: int
    busy_timeouts_seen: list[int]

    def execute(
        self,
        sql: str,
        parameters: SupportsLenAndGetItem[object] | Mapping[str, object] = (),
        /,
    ) -> sqlite3.Cursor:
        """Run the statement; answer a checkpoint with the next fake row."""
        if not sql.upper().startswith("PRAGMA WAL_CHECKPOINT"):
            return super().execute(sql, parameters)
        timeout_row = super().execute("PRAGMA busy_timeout").fetchone()
        self.busy_timeouts_seen.append(int(timeout_row[0]))
        answer_index = min(self.checkpoints_run, len(self.busy_answers) - 1)
        self.checkpoints_run += 1
        return super().execute("SELECT ?, 0, 0", (self.busy_answers[answer_index],))


def open_fake_connection(
    database_path: Path, busy_answers: list[int]
) -> FakeCheckpointConnection:
    """A WAL connection with a busy timeout of 5 s that answers `busy_answers`."""
    connection = sqlite3.connect(
        database_path,
        timeout=BUSY_TIMEOUT_SECONDS,
        isolation_level=None,
        factory=FakeCheckpointConnection,
    )
    connection.execute("PRAGMA journal_mode = WAL")
    connection.busy_answers = busy_answers
    connection.checkpoints_run = 0
    connection.busy_timeouts_seen = []
    return connection


class Case(NamedTuple):
    """The answers a connection gives to successive checkpoints, and what follows."""

    busy_answers: list[int]
    checkpoints_run: int
    emptied: bool
    record_levels: list[int]


CASES = [
    pytest.param(Case([0], 1, True, []), id="free at the first try"),
    pytest.param(Case([1, 0], 2, True, []), id="busy then free"),
    pytest.param(Case([1, 1], 2, False, [logging.WARNING]), id="busy twice"),
]


def nock_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """The records of the `nock.*` loggers captured so far."""
    records: list[logging.LogRecord] = []
    for record in caplog.records:
        if record.name.startswith(LOGGER_PREFIX):
            records.append(record)
    return records


@pytest.mark.parametrize("case", CASES)
def test_ac22_a_busy_checkpoint_is_tried_once_more_then_logged_and_given_up(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, case: Case
) -> None:
    connection = open_fake_connection(tmp_path / "fake.sqlite3", case.busy_answers)
    caplog.set_level(logging.DEBUG, logger=LOGGER_PREFIX)

    try:
        emptied = nock.store.checkpoint_wal(connection)
    finally:
        connection.close()

    levels = [record.levelno for record in nock_records(caplog)]
    assert (emptied, connection.checkpoints_run, levels) == (
        case.emptied,
        case.checkpoints_run,
        case.record_levels,
    )


@pytest.mark.parametrize("case", CASES)
def test_ac25_each_try_has_a_busy_timeout_of_0_and_the_timeout_comes_back(
    tmp_path: Path, case: Case
) -> None:
    connection = open_fake_connection(tmp_path / "fake.sqlite3", case.busy_answers)

    try:
        nock.store.checkpoint_wal(connection)
        timeout_row = connection.execute("PRAGMA busy_timeout").fetchone()
    finally:
        connection.close()

    assert connection.busy_timeouts_seen == [0] * case.checkpoints_run
    assert timeout_row[0] == BUSY_TIMEOUT_MS


# ---- AC-23: six operations, one checkpoint each -----------------------------------


class CheckpointRecorder:
    """Stands in for `checkpoint_wal`: counts its calls, answers `result`."""

    def __init__(self, result: bool) -> None:
        self.result = result
        self.calls = 0

    def __call__(self, connection: sqlite3.Connection) -> bool:
        self.calls += 1
        return self.result


class Operation(NamedTuple):
    """One operation of the criterion, ready to run, with what it must do.

    `act` runs it and returns what it returned; `effect` reads what it changed,
    after it ran. Both are compared with the value expected for them.
    """

    act: Callable[[], object]
    returns: object
    effect: Callable[[], object]
    effect_after: object


def delete_a_room(database: str, grid: Grid, stack: contextlib.ExitStack) -> Operation:
    """`RoomStore.delete_room`: the room is gone and the call returns True."""
    store = RoomStore(database)
    stack.callback(store.close)
    store.create_room(new_room(CODE, grid, T0))
    return Operation(
        act=lambda: store.delete_room(CODE),
        returns=True,
        effect=lambda: store.has_room(CODE),
        effect_after=False,
    )


def erase_a_player(database: str, grid: Grid, stack: contextlib.ExitStack) -> Operation:
    """`RoomStore.erase_player`: the stored nickname becomes `--`."""
    store = RoomStore(database)
    stack.callback(store.close)
    room = Run(grid, code=CODE, grid_number=None, config=NO_TICK_CONFIG)
    room.join_new("Ana", ANA, TA, T0)
    write_room(store, room)

    def stored_nicknames() -> list[str]:
        state = store.load_room(CODE)
        assert state is not None
        return [player.nickname for player in state.players]

    return Operation(
        act=lambda: store.erase_player(CODE, ANA),
        returns=True,
        effect=stored_nicknames,
        effect_after=[FORMER_PLAYER_NICKNAME],
    )


def delete_an_account(
    database: str, grid: Grid, stack: contextlib.ExitStack
) -> Operation:
    """`AccountStore.delete_account`: the session no longer finds an account.

    It returns the pending erasure: the account, its address, the time of the call,
    no attempt yet and no player (the account holds no identity).
    """
    accounts = AccountStore(database)
    stack.callback(accounts.close)
    started = accounts.sign_in(ANA_EMAIL, T0)

    def delete() -> object:
        pending = accounts.delete_account(started.account_id, T0)
        assert pending is not None
        return (
            pending.account_id,
            pending.email,
            pending.requested_at,
            pending.attempts,
            pending.players,
        )

    return Operation(
        act=delete,
        returns=(started.account_id, ANA_EMAIL, T0, 0, ()),
        effect=lambda: accounts.account_of_session(started.session, T0),
        effect_after=None,
    )


def finish_an_erasure(
    database: str, grid: Grid, stack: contextlib.ExitStack
) -> Operation:
    """`AccountStore.finish_erasure`: no pending erasure is left."""
    accounts = AccountStore(database)
    stack.callback(accounts.close)
    started = accounts.sign_in(ANA_EMAIL, T0)
    pending = accounts.delete_account(started.account_id, T0)
    assert pending is not None
    assert accounts.pending_erasures() == [pending]
    return Operation(
        act=lambda: accounts.finish_erasure(pending.erasure_id, T0 + 1, None),
        returns=None,
        effect=accounts.pending_erasures,
        effect_after=[],
    )


def erase_a_player_from_history(
    database: str, grid: Grid, stack: contextlib.ExitStack
) -> Operation:
    """`erase_players_from_history`: Ana's team-mate Bob becomes `--` in her record."""
    accounts = AccountStore(database)
    stack.callback(accounts.close)
    play = play_fx01(
        grid, CODE, [Player("Ana", ANA, TA), Player("Bob", BOB, TB)], start=T0
    )
    started = accounts.sign_in(ANA_EMAIL, T0)
    ana = RoomIdentity(code=CODE, player_id=ANA, resume_token=TA, nickname="ANA")
    bob = ErasedPlayer(code=CODE, player_id=BOB, is_erased=False)
    assert accounts.link_identity(started.account_id, ana, T0)
    accounts.save_history(started.account_id, play.state)
    assert accounts.history(started.account_id)[0].teammates == ("BOB",)

    def teammates() -> tuple[str, ...]:
        return accounts.history(started.account_id)[0].teammates

    return Operation(
        act=lambda: accounts.erase_players_from_history([bob]),
        returns=None,
        effect=teammates,
        effect_after=(FORMER_PLAYER_NICKNAME,),
    )


def purge_an_old_link(
    database: str, grid: Grid, stack: contextlib.ExitStack
) -> Operation:
    """`AccountStore.purge`: a link older than 30 minutes can no longer be used."""
    accounts = AccountStore(database)
    stack.callback(accounts.close)
    token = accounts.add_link(ANA_EMAIL, None, T0)
    return Operation(
        act=lambda: accounts.purge(T0 + LINK_LIFE_SECONDS + 1),
        returns=None,
        effect=lambda: accounts.use_link(token, T0),
        effect_after=None,
    )


OPERATIONS = {
    "delete_room": delete_a_room,
    "erase_player": erase_a_player,
    "delete_account": delete_an_account,
    "finish_erasure": finish_an_erasure,
    "erase_players_from_history": erase_a_player_from_history,
    "purge": purge_an_old_link,
}


def record_checkpoints(
    monkeypatch: pytest.MonkeyPatch, result: bool
) -> CheckpointRecorder:
    """Replace `checkpoint_wal`, where either store looks it up, by a recorder."""
    recorder = CheckpointRecorder(result)
    monkeypatch.setattr("nock.store.checkpoint_wal", recorder)
    monkeypatch.setattr("nock.accounts.checkpoint_wal", recorder, raising=False)
    return recorder


@pytest.mark.parametrize("checkpoint_result", [True, False])
@pytest.mark.parametrize("operation_name", list(OPERATIONS))
def test_ac23_on_a_file_each_operation_runs_one_checkpoint_and_still_does_its_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    operation_name: str,
    checkpoint_result: bool,
) -> None:
    recorder = record_checkpoints(monkeypatch, checkpoint_result)
    database = str(tmp_path / "nock.sqlite3")

    with contextlib.ExitStack() as stack:
        operation = OPERATIONS[operation_name](database, fx01_grid, stack)
        recorder.calls = 0
        returned = operation.act()
        checkpoints = recorder.calls
        effect = operation.effect()

    assert checkpoints == 1
    assert returned == operation.returns
    assert effect == operation.effect_after


@pytest.mark.parametrize("operation_name", list(OPERATIONS))
def test_ac23_in_memory_no_operation_runs_a_checkpoint(
    monkeypatch: pytest.MonkeyPatch, fx01_grid: Grid, operation_name: str
) -> None:
    recorder = record_checkpoints(monkeypatch, True)

    with contextlib.ExitStack() as stack:
        operation = OPERATIONS[operation_name](":memory:", fx01_grid, stack)
        returned = operation.act()
        effect = operation.effect()

    assert recorder.calls == 0
    assert returned == operation.returns
    assert effect == operation.effect_after


# ---- AC-23: the other writes of an erasure run no checkpoint ----------------------


class ErasureWrite(NamedTuple):
    """A write of an erasure that removes no address, nickname or player id.

    `act` runs it; `effect` reads what it changed, compared with `effect_after`.
    """

    act: Callable[[], object]
    effect: Callable[[], object]
    effect_after: object


def ana_pending_erasure(
    database: str, stack: contextlib.ExitStack
) -> tuple[AccountStore, int]:
    """Ana, linked to her player in CODE, deletes her account.

    Returns:
        The account store and the id of her pending erasure, which holds that
        player, not marked erased.
    """
    accounts = AccountStore(database)
    stack.callback(accounts.close)
    started = accounts.sign_in(ANA_EMAIL, T0)
    ana = RoomIdentity(code=CODE, player_id=ANA, resume_token=TA, nickname="ANA")
    assert accounts.link_identity(started.account_id, ana, T0)
    pending = accounts.delete_account(started.account_id, T0)
    assert pending is not None
    return accounts, pending.erasure_id


def begin_an_attempt(database: str, stack: contextlib.ExitStack) -> ErasureWrite:
    """`begin_attempt`: the pending erasure counts one attempt."""
    accounts, erasure_id = ana_pending_erasure(database, stack)
    return ErasureWrite(
        act=lambda: accounts.begin_attempt(erasure_id),
        effect=lambda: accounts.pending_erasures()[0].attempts,
        effect_after=1,
    )


def mark_a_player_erased(database: str, stack: contextlib.ExitStack) -> ErasureWrite:
    """`mark_player_erased`: the erasure still holds Ana's player, marked erased."""
    accounts, erasure_id = ana_pending_erasure(database, stack)
    return ErasureWrite(
        act=lambda: accounts.mark_player_erased(erasure_id, CODE, ANA),
        effect=lambda: accounts.pending_erasures()[0].players,
        effect_after=(ErasedPlayer(code=CODE, player_id=ANA, is_erased=True),),
    )


def count_a_deleted_room(database: str, stack: contextlib.ExitStack) -> ErasureWrite:
    """`count_deleted_room`: the erasure's row counts one deleted room."""
    accounts, erasure_id = ana_pending_erasure(database, stack)
    return ErasureWrite(
        act=lambda: accounts.count_deleted_room(erasure_id),
        effect=lambda: erasure_rows(Path(database))[0].rooms_deleted,
        effect_after=1,
    )


ERASURE_WRITES = {
    "begin_attempt": begin_an_attempt,
    "mark_player_erased": mark_a_player_erased,
    "count_deleted_room": count_a_deleted_room,
}


@pytest.mark.parametrize("write_name", list(ERASURE_WRITES))
def test_ac23_on_a_file_the_counts_and_marks_of_an_erasure_run_no_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_name: str
) -> None:
    recorder = record_checkpoints(monkeypatch, True)
    database = str(tmp_path / "nock.sqlite3")

    with contextlib.ExitStack() as stack:
        write = ERASURE_WRITES[write_name](database, stack)
        recorder.calls = 0
        write.act()
        checkpoints = recorder.calls
        effect = write.effect()

    assert checkpoints == 0
    assert effect == write.effect_after


def test_ac23_on_a_file_a_snapshot_that_deletes_an_older_one_runs_no_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fx01_grid: Grid
) -> None:
    recorder = record_checkpoints(monkeypatch, True)
    database = tmp_path / "nock.sqlite3"
    first = new_room(CODE, fx01_grid, T0)
    saved_seqs = [100, 200, 300]

    with contextlib.closing(RoomStore(database)) as store:
        store.create_room(first)
        recorder.calls = 0
        for seq in saved_seqs:
            store.save_snapshot(first.model_copy(update={"seq": seq}))
        checkpoints = recorder.calls
        stored = select_rows(database, "SELECT seq FROM snapshots ORDER BY seq")

    assert checkpoints == 0
    assert stored == [(0,), (300,)]


def test_ac23_finish_erasure_leaves_the_erasure_done_with_no_address(
    tmp_path: Path,
) -> None:
    database = tmp_path / "nock.sqlite3"
    accounts = AccountStore(database)
    try:
        started = accounts.sign_in(ANA_EMAIL, T0)
        pending = accounts.delete_account(started.account_id, T0)
        assert pending is not None
        assert strings_in(database_bytes(database), [ANA_EMAIL]) == [ANA_EMAIL]

        accounts.finish_erasure(pending.erasure_id, T0 + 1, T0 + 1)
        with contextlib.closing(sqlite3.connect(database)) as connection:
            rows = connection.execute(
                "SELECT account_id, email, done_at, notified_at FROM account_erasures"
            ).fetchall()
        files = strings_in(database_bytes(database), [ANA_EMAIL])
    finally:
        accounts.close()

    assert rows == [(None, None, T0 + 1, T0 + 1)]
    assert files == []
