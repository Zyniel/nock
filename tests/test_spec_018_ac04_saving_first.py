"""Tests of spec 018, AC-4: saving comes first, and a failed save changes nothing.

The real WebSocket through `TestClient`, with a `RoomStore` subclass passed as
`store=`: an `append` held back, an `append` that raises, a join whose commit
fails, and `RoomRegistry.close()` saving a snapshot of a room still running. The
shared setup is in `spec018_harness`.
"""

from __future__ import annotations

import contextlib
import string
import threading
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, Join, Snapshot, parse_server_message
from nock.room import LogEntry
from nock.server import create_app
from nock.store import RoomStore
from spec018_harness import (
    SERVER_CONFIG,
    SHORT_PAUSE_SECONDS,
    WAIT_SECONDS,
    assert_same_room,
    corrupt_log_entry,
    grid_from_text,
    join_peers,
    letter_cells,
    load_from_file,
    make_dist_dir,
    open_peer,
    server_grid,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


# ---- AC-4: saving first, and a failed save changes nothing ----


class ControlledStore(RoomStore):
    """A file store whose `append` the test can hold back or make fail."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.path = path
        self.hold_next_append = threading.Event()
        self.append_is_held = threading.Event()
        self.release_append = threading.Event()
        self.fail_appends = False
        self.append_failed = threading.Event()

    def append(self, code: str, entries: Sequence[LogEntry]) -> None:
        if self.fail_appends:
            self.append_failed.set()
            raise OSError("the disk is full")
        if self.hold_next_append.is_set():
            self.hold_next_append.clear()
            self.append_is_held.set()
            self.release_append.wait(WAIT_SECONDS)
        super().append(code, entries)


@pytest.fixture
def controlled_store(tmp_path: Path) -> Iterator[ControlledStore]:
    store = ControlledStore(tmp_path / "nock.sqlite3")
    yield store
    store.release_append.set()
    store.close()


@pytest.fixture
def controlled_registry(
    controlled_store: ControlledStore,
) -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry(config=SERVER_CONFIG, store=controlled_store)
    yield room_registry
    room_registry.close()


@pytest.fixture
def controlled_client(
    controlled_registry: RoomRegistry, dist_dir: Path
) -> Iterator[TestClient]:
    app = create_app(rooms=controlled_registry, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


class SocketEnd:
    """What a socket gave until it closed, read by a thread: the wait is bounded."""

    def __init__(self, websocket: WebSocketTestSession) -> None:
        self.texts: list[str] = []
        self.disconnect: WebSocketDisconnect | None = None
        self._websocket = websocket
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        while True:
            try:
                self.texts.append(self._websocket.receive_text())
            except WebSocketDisconnect as error:
                self.disconnect = error
                return
            except Exception:  # the socket was torn down at the end of the test
                return

    def wait_for_close(self) -> WebSocketDisconnect:
        self._thread.join(timeout=WAIT_SECONDS)
        if self.disconnect is None:
            pytest.fail(f"the socket was not closed within {WAIT_SECONDS}s")
        return self.disconnect


def test_ac4_websocket_no_client_gets_an_event_while_its_append_is_held(
    controlled_store: ControlledStore,
    controlled_registry: RoomRegistry,
    controlled_client: TestClient,
    fx01_grid: Grid,
) -> None:
    code = controlled_registry.register_room(fx01_grid)
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, controlled_client, code, ["Ana", "Bob"])
        messages_before = (len(ana.messages()), len(bob.messages()))

        controlled_store.hold_next_append.set()
        ana.send(EditLetter(row=1, column=0, letter="T"))
        assert controlled_store.append_is_held.wait(WAIT_SECONDS)
        time.sleep(SHORT_PAUSE_SECONDS)

        assert (len(ana.messages()), len(bob.messages())) == messages_before
        assert controlled_store.read_log(code, after_seq=2) == []

        controlled_store.release_append.set()
        ana.wait_for_seq(3, "the letter once its append returned")
        bob.wait_for_seq(3, "the letter once its append returned")
        for peer in (ana, bob):
            events = peer.letter_events()
            assert [(e.seq, e.row, e.column, e.letter) for e in events] == [
                (3, 1, 0, "T")
            ]
        logged = controlled_store.read_log(code, after_seq=2)
        assert [entry.event.seq for entry in logged] == [3]


def test_ac4_websocket_a_failed_append_drops_the_step_and_later_steps_go_on(
    controlled_store: ControlledStore,
    controlled_registry: RoomRegistry,
    controlled_client: TestClient,
    fx01_grid: Grid,
) -> None:
    code = controlled_registry.register_room(fx01_grid)
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, controlled_client, code, ["Ana", "Bob"])
        before = controlled_registry.room_state(code)
        assert before is not None
        messages_before = (len(ana.messages()), len(bob.messages()))

        controlled_store.fail_appends = True
        ana.send(EditLetter(row=1, column=0, letter="T"))
        assert controlled_store.append_failed.wait(WAIT_SECONDS)
        time.sleep(SHORT_PAUSE_SECONDS)

        assert (len(ana.messages()), len(bob.messages())) == messages_before
        assert controlled_registry.room_state(code) == before
        assert controlled_store.read_log(code, after_seq=2) == []

        controlled_store.fail_appends = False
        ana.send(EditLetter(row=1, column=1, letter="E"))
        ana.wait_for_seq(3, "the edit sent after the failure")
        bob.wait_for_seq(3, "the edit sent after the failure")
        for peer in (ana, bob):
            events = peer.letter_events()
            assert [(e.seq, e.row, e.column, e.letter) for e in events] == [
                (3, 1, 1, "E")
            ]
            assert peer.errors() == []
        after = controlled_registry.room_state(code)
        assert after is not None
        assert after.seq == 3
        grid = server_grid(controlled_registry, code)
        assert grid[(1, 0)] == (None, False, None)
        assert grid[(1, 1)] == ("E", False, ana.you())


def test_ac4_websocket_a_join_whose_append_fails_is_closed_with_1011(
    controlled_store: ControlledStore,
    controlled_registry: RoomRegistry,
    controlled_client: TestClient,
    fx01_grid: Grid,
) -> None:
    code = controlled_registry.register_room(fx01_grid)
    before = controlled_registry.room_state(code)
    assert before is not None
    controlled_store.fail_appends = True
    with contextlib.ExitStack() as stack:
        websocket = stack.enter_context(
            controlled_client.websocket_connect(f"/api/rooms/{code}/ws")
        )
        socket_end = SocketEnd(websocket)
        websocket.send_text(Join(nickname="Ana", resume_token=None).model_dump_json())

        disconnect = socket_end.wait_for_close()

        assert disconnect.code == 1011
        for text in socket_end.texts:
            assert not isinstance(parse_server_message(text), Snapshot)
        assert controlled_store.append_failed.is_set()
        state = controlled_registry.room_state(code)
        assert state is not None
        assert state.players == ()
        assert state == before
        assert controlled_store.read_log(code) == []


def test_ac4_websocket_close_saves_a_snapshot_of_a_room_still_running(
    controlled_store: ControlledStore,
    controlled_registry: RoomRegistry,
    controlled_client: TestClient,
    fx01_grid: Grid,
) -> None:
    code = controlled_registry.register_room(fx01_grid)
    cells = letter_cells(fx01_grid)
    path = controlled_store.path
    with contextlib.ExitStack() as stack:
        ana = open_peer(stack, controlled_client, code, "Ana")
        for index in range(10):
            row, column = cells[index]
            letter = string.ascii_uppercase[index % 26]
            ana.send(EditLetter(row=row, column=column, letter=letter))
        ana.wait_for_seq(11, "the 10 letters")
        # Damage a log row: only a snapshot at the end can still be loaded.
        corrupt_log_entry(path, 5)
        with pytest.raises(ValidationError):
            load_from_file(path, code)
        live = controlled_registry.room_state(code)
        assert live is not None
        assert live.seq == 11

        # Ana is still connected: the room task did not stop on its own.
        controlled_registry.close()

        assert_same_room(load_from_file(path, code), live)
