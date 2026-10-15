"""Tests of spec 018, AC-1: `RoomStore` on its own.

The created room, the log (`append`, gaps, `read_log`), the snapshots, `close`, and
the file database (the WAL journal, a second store on the same file, several
threads). The shared setup is in `spec018_harness`.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from nock.grid import Grid
from nock.protocol import (
    EditLetter,
    PlayerJoined,
    PlayerState,
    PlayerView,
    RevealBudget,
)
from nock.room import LogEntry, handle_message, new_room
from nock.store import RoomStore
from spec018_harness import (
    NOW,
    OTHER_CODE,
    OVERALL_SECONDS,
    ROOM_CODE,
    START_TIME,
    assert_same_room,
    grid_from_text,
    letter_changed,
    token_of,
    two_player_room,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def file_store(tmp_path: Path) -> Iterator[RoomStore]:
    store = RoomStore(tmp_path / "nock.sqlite3")
    yield store
    store.close()


@pytest.fixture
def memory_store() -> Iterator[RoomStore]:
    store = RoomStore(":memory:")
    yield store
    store.close()


# ---- Helpers on room states ----


def log_entry(
    seq: int,
    row: int = 1,
    column: int = 0,
    letter: str | None = "A",
    player_id: str = "p1",
) -> LogEntry:
    return LogEntry(at=NOW, event=letter_changed(seq, row, column, letter, player_id))


# ---- AC-1: RoomStore ----


def test_ac1_store_a_created_room_is_known_and_loads_as_created(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    state = two_player_room(fx01_grid)

    memory_store.create_room(state)

    assert memory_store.has_room(ROOM_CODE) is True
    assert memory_store.load_room(ROOM_CODE) == state
    assert memory_store.read_log(ROOM_CODE) == []


def test_ac1_store_an_unknown_code_gives_false_none_and_an_empty_log(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))

    assert memory_store.has_room(OTHER_CODE) is False
    assert memory_store.load_room(OTHER_CODE) is None
    assert memory_store.read_log(OTHER_CODE) == []
    assert memory_store.read_log(OTHER_CODE, after_seq=3) == []


def test_ac1_store_creating_a_room_twice_raises_and_keeps_the_first(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    first = two_player_room(fx01_grid)
    memory_store.create_room(first)

    with pytest.raises(ValueError, match=r".+"):
        memory_store.create_room(new_room(ROOM_CODE, fx01_grid, START_TIME))

    assert memory_store.load_room(ROOM_CODE) == first


def test_ac1_store_appended_entries_read_back_equal_and_in_order(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    joined = LogEntry(
        at=NOW,
        event=PlayerJoined(
            seq=3,
            player=PlayerView(
                player_id="p3",
                nickname="Cleo",
                colour=2,
                state=PlayerState.ACTIVE,
                is_host=False,
                muted=False,
                selection=None,
            ),
        ),
        resume_token=token_of(3),
    )
    undone = LogEntry(
        at=NOW + 2.5, event=letter_changed(5, 1, 0, None, "p1"), undo=True
    )
    typed = log_entry(4)

    memory_store.append(ROOM_CODE, [joined])
    memory_store.append(ROOM_CODE, [typed, undone])

    assert memory_store.read_log(ROOM_CODE) == [joined, typed, undone]
    assert memory_store.read_log(ROOM_CODE)[0].resume_token == token_of(3)
    assert memory_store.read_log(ROOM_CODE)[2].undo is True


def test_ac1_store_read_log_after_seq_returns_only_the_later_entries(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    entries = [log_entry(seq) for seq in range(3, 9)]
    memory_store.append(ROOM_CODE, entries)

    assert memory_store.read_log(ROOM_CODE, after_seq=5) == entries[3:]
    assert memory_store.read_log(ROOM_CODE, after_seq=8) == []
    assert memory_store.read_log(ROOM_CODE, after_seq=0) == entries


@pytest.mark.parametrize("first_seq", [1, 2, 4, 5])
def test_ac1_store_the_first_entry_must_follow_the_snapshot_seq(
    memory_store: RoomStore, fx01_grid: Grid, first_seq: int
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))  # snapshot at seq 2

    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(ROOM_CODE, [log_entry(first_seq)])

    assert memory_store.read_log(ROOM_CODE) == []


def test_ac1_store_a_gap_in_the_seqs_raises_and_writes_nothing(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    memory_store.append(ROOM_CODE, [log_entry(3)])

    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(ROOM_CODE, [log_entry(5)])

    assert memory_store.read_log(ROOM_CODE) == [log_entry(3)]


def test_ac1_store_a_gap_inside_the_batch_writes_none_of_it(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))

    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(ROOM_CODE, [log_entry(3), log_entry(4), log_entry(6)])

    assert memory_store.read_log(ROOM_CODE) == []
    memory_store.append(ROOM_CODE, [log_entry(3)])
    assert memory_store.read_log(ROOM_CODE) == [log_entry(3)]


def test_ac1_store_a_repeated_seq_raises_and_writes_nothing(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    memory_store.append(ROOM_CODE, [log_entry(3), log_entry(4)])

    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(ROOM_CODE, [log_entry(4)])

    assert [entry.event.seq for entry in memory_store.read_log(ROOM_CODE)] == [3, 4]


def test_ac1_store_entries_for_an_unknown_room_raise(
    memory_store: RoomStore,
) -> None:
    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(OTHER_CODE, [log_entry(1)])

    assert memory_store.read_log(OTHER_CODE) == []


def test_ac1_store_an_empty_append_writes_nothing_and_raises_nothing(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))

    memory_store.append(ROOM_CODE, [])
    memory_store.append(ROOM_CODE, ())

    assert memory_store.read_log(ROOM_CODE) == []
    memory_store.append(ROOM_CODE, [log_entry(3)])
    assert memory_store.read_log(ROOM_CODE) == [log_entry(3)]


def test_ac1_store_a_snapshot_of_an_unknown_room_raises(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    with pytest.raises(ValueError, match=r".+"):
        memory_store.save_snapshot(two_player_room(fx01_grid))

    assert memory_store.has_room(ROOM_CODE) is False


def test_ac1_store_the_snapshot_with_the_highest_seq_is_the_one_loaded(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(new_room(ROOM_CODE, fx01_grid, START_TIME))
    two_players = two_player_room(fx01_grid)

    memory_store.save_snapshot(two_players)

    assert memory_store.load_room(ROOM_CODE) == two_players


def test_ac1_store_a_snapshot_at_the_same_seq_replaces_the_old_one(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    original = two_player_room(fx01_grid)
    memory_store.create_room(original)
    replaced = original.model_copy(
        update={"reveal_budget": RevealBudget(letters=1, words=0)}
    )

    memory_store.save_snapshot(replaced)

    assert memory_store.load_room(ROOM_CODE) == replaced


def test_ac1_store_load_room_replays_only_the_entries_after_the_snapshot(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    base = two_player_room(fx01_grid)
    memory_store.create_room(base)
    first = handle_message(base, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    memory_store.append(ROOM_CODE, first.entries)
    memory_store.save_snapshot(first.state)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )
    memory_store.append(ROOM_CODE, second.entries)

    loaded = memory_store.load_room(ROOM_CODE)

    assert_same_room(loaded, second.state)
    assert loaded is not None
    assert len(loaded.players) == 2


def test_ac1_store_the_log_is_not_truncated_by_snapshots(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    entries = [log_entry(seq) for seq in range(3, 13)]
    memory_store.append(ROOM_CODE, entries)
    state = two_player_room(fx01_grid).model_copy(update={"seq": 12})

    memory_store.save_snapshot(state)

    assert memory_store.read_log(ROOM_CODE) == entries


def test_ac1_store_close_can_be_called_twice(fx01_grid: Grid, tmp_path: Path) -> None:
    store = RoomStore(tmp_path / "nock.sqlite3")
    store.create_room(two_player_room(fx01_grid))

    store.close()
    store.close()


def test_ac1_store_a_missing_file_is_created_and_the_room_survives_a_reopen(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    assert not path.exists()
    first = RoomStore(path)
    try:
        assert path.exists()
        assert first.has_room(ROOM_CODE) is False
        first.create_room(two_player_room(fx01_grid))
        first.append(ROOM_CODE, [log_entry(3)])
    finally:
        first.close()

    second = RoomStore(path)
    try:
        assert second.has_room(ROOM_CODE) is True
        assert second.read_log(ROOM_CODE) == [log_entry(3)]
    finally:
        second.close()


def test_ac1_store_a_file_database_uses_the_wal_journal(
    file_store: RoomStore, tmp_path: Path, fx01_grid: Grid
) -> None:
    file_store.create_room(two_player_room(fx01_grid))
    file_store.append(ROOM_CODE, [log_entry(3)])

    connection = sqlite3.connect(tmp_path / "nock.sqlite3")
    try:
        row = connection.execute("PRAGMA journal_mode").fetchone()
    finally:
        connection.close()

    assert row is not None
    assert str(row[0]).lower() == "wal"


def test_ac1_store_a_second_store_sees_what_the_first_committed_without_closing(
    file_store: RoomStore, tmp_path: Path, fx01_grid: Grid
) -> None:
    file_store.create_room(two_player_room(fx01_grid))
    file_store.append(ROOM_CODE, [log_entry(3), log_entry(4)])

    reader = RoomStore(tmp_path / "nock.sqlite3")
    try:
        assert reader.has_room(ROOM_CODE) is True
        assert reader.read_log(ROOM_CODE) == [log_entry(3), log_entry(4)]
    finally:
        reader.close()


def test_ac1_store_several_threads_can_append_to_their_own_rooms(
    file_store: RoomStore, fx01_grid: Grid
) -> None:
    codes = ["AAAAA1", "AAAAA2", "AAAAA3", "AAAAA4"]
    for code in codes:
        file_store.create_room(two_player_room(fx01_grid, code))
    problems: list[str] = []

    def append_forty(code: str) -> None:
        try:
            for seq in range(3, 43):
                file_store.append(code, [log_entry(seq)])
        except Exception as error:  # reported by the test thread
            problems.append(repr(error))

    threads: list[threading.Thread] = []
    for code in codes:
        thread = threading.Thread(target=append_forty, args=(code,), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join(timeout=OVERALL_SECONDS)
        assert not thread.is_alive(), "an appending thread did not finish"

    assert problems == []
    for code in codes:
        seqs = [entry.event.seq for entry in file_store.read_log(code)]
        assert seqs == list(range(3, 43))
