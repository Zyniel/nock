"""Tests of spec 005, AC-6 and AC-7: withdrawing a grid.

No new room can be created on a withdrawn grid, and no route shows it (AC-6); the
rooms already open on it can still be finished and reloaded (AC-7). The shared
setup is in `spec005_harness`.
"""

from __future__ import annotations

import contextlib
import queue
import re
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    ErrorMessage,
    Join,
    LetterCellView,
    LetterChanged,
    Snapshot,
    parse_server_message,
)
from nock.room import RoomConfig
from nock.server import create_app
from nock.store import RoomStore
from spec005_harness import grid_from_text, make_entry

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
NOT_FOUND_BODY = {"detail": "Not Found"}
RECEIVE_TIMEOUT_SECONDS = 5.0
SERVER_CONFIG = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)

# The solution of FX-01 (specs/_reference.md): position -> letter.
SOLUTION: dict[tuple[int, int], str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        SOLUTION[(_row, _offset + 1)] = _letter
assert len(SOLUTION) == 18


# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


@pytest.fixture
def mixed_catalogue(fx01_grid: Grid) -> Catalogue:
    """Entry 1 published, entry 2 published and withdrawn."""
    entries = (
        make_entry(fx01_grid, 1),
        make_entry(fx01_grid, 2, withdrawn=True),
    )
    return Catalogue(entries=entries)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry(config=SERVER_CONFIG)
    yield room_registry
    room_registry.close()


@pytest.fixture
def client(
    registry: RoomRegistry, mixed_catalogue: Catalogue, dist_dir: Path
) -> Iterator[TestClient]:
    app = create_app(rooms=registry, catalogue=mixed_catalogue, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


# ---- AC-6: no new room on a withdrawn grid ----------------------------------


def test_ac6_published_summaries_skip_the_withdrawn_entry(
    mixed_catalogue: Catalogue,
) -> None:
    summaries = mixed_catalogue.published_summaries()

    numbers = []
    for summary in summaries:
        numbers.append(summary.number)
    assert numbers == [1]


def test_ac6_published_summaries_with_a_force_skip_the_withdrawn_entry(
    mixed_catalogue: Catalogue,
) -> None:
    summaries = mixed_catalogue.published_summaries(force=2)

    numbers = []
    for summary in summaries:
        numbers.append(summary.number)
    assert numbers == [1]


def test_ac6_find_published_returns_none_for_the_withdrawn_entry(
    mixed_catalogue: Catalogue,
) -> None:
    assert mixed_catalogue.find_published(2) is None


def test_ac6_find_published_still_finds_the_other_entry(
    mixed_catalogue: Catalogue,
) -> None:
    found = mixed_catalogue.find_published(1)

    assert found is not None
    assert found.number == 1


def test_ac6_withdrawn_wins_over_published_true(fx01_grid: Grid) -> None:
    catalogue = Catalogue(entries=(make_entry(fx01_grid, 3, withdrawn=True),))

    assert catalogue.find_published(3) is None
    assert catalogue.published_summaries() == []


def test_ac6_an_unpublished_withdrawn_entry_is_hidden(fx01_grid: Grid) -> None:
    entry = make_entry(fx01_grid, 3, published=False, withdrawn=True)
    catalogue = Catalogue(entries=(entry,))

    assert catalogue.find_published(3) is None
    assert catalogue.published_summaries() == []


def test_ac6_the_list_route_shows_only_the_entry_that_is_not_withdrawn(
    client: TestClient,
) -> None:
    response = client.get("/api/grids")

    assert response.status_code == 200
    numbers = []
    for item in response.json():
        numbers.append(item["number"])
    assert numbers == [1]


def test_ac6_the_list_route_keeps_the_shape_of_spec_004(client: TestClient) -> None:
    response = client.get("/api/grids")

    assert response.json() == [
        {
            "number": 1,
            "published_on": "2026-10-01",
            "force": 2,
            "width": 5,
            "height": 5,
            "word_count": 8,
        }
    ]


def test_ac6_the_detail_route_answers_200_for_the_entry_that_is_not_withdrawn(
    client: TestClient,
) -> None:
    response = client.get("/api/grids/1")

    assert response.status_code == 200
    assert response.json()["number"] == 1


def test_ac6_the_detail_route_answers_404_for_the_withdrawn_entry(
    client: TestClient,
) -> None:
    response = client.get("/api/grids/2")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac6_the_grid_page_answers_200_for_the_entry_that_is_not_withdrawn(
    client: TestClient,
) -> None:
    response = client.get("/g/1")

    assert response.status_code == 200


def test_ac6_the_grid_page_answers_404_for_the_withdrawn_entry(
    client: TestClient,
) -> None:
    response = client.get("/g/2")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac6_a_room_is_created_on_the_entry_that_is_not_withdrawn(
    client: TestClient,
) -> None:
    response = client.post("/api/rooms", json={"grid_number": 1})

    assert response.status_code == 201
    assert re.fullmatch(r"[A-Z0-9]{6}", response.json()["code"]) is not None


def test_ac6_no_room_is_created_on_the_withdrawn_entry(client: TestClient) -> None:
    response = client.post("/api/rooms", json={"grid_number": 2})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac6_a_withdrawn_unpublished_entry_answers_404_everywhere(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    entry = make_entry(fx01_grid, 5, published=False, withdrawn=True)
    app_registry = RoomRegistry(config=SERVER_CONFIG)
    try:
        app = create_app(
            rooms=app_registry, catalogue=Catalogue(entries=(entry,)), dist_dir=dist_dir
        )
        with TestClient(app) as test_client:
            assert test_client.get("/api/grids").json() == []
            assert test_client.get("/api/grids/5").status_code == 404
            assert test_client.get("/g/5").status_code == 404
            posted = test_client.post("/api/rooms", json={"grid_number": 5})
            assert posted.status_code == 404
    finally:
        app_registry.close()


# ---- AC-7: open rooms on a withdrawn grid can finish ------------------------


def receive_text_or_fail(websocket: WebSocketTestSession) -> str:
    """Return the next text of the socket, failing instead of waiting forever."""
    received: queue.Queue[str | BaseException] = queue.Queue()

    def read() -> None:
        try:
            received.put(websocket.receive_text())
        except BaseException as error:  # handed to the test thread, re-raised there
            received.put(error)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        outcome = received.get(timeout=RECEIVE_TIMEOUT_SECONDS)
    except queue.Empty:
        pytest.fail(f"nothing received from the socket in {RECEIVE_TIMEOUT_SECONDS}s")
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome


def join_room(
    stack: contextlib.ExitStack, http_client: TestClient, code: str, nickname: str
) -> WebSocketTestSession:
    """Open a socket on the room, join and check the answer is a snapshot."""
    websocket = stack.enter_context(
        http_client.websocket_connect(f"/api/rooms/{code}/ws")
    )
    websocket.send_text(Join(nickname=nickname).model_dump_json())
    message = parse_server_message(receive_text_or_fail(websocket))
    assert isinstance(message, Snapshot)
    return websocket


def type_and_wait(
    websocket: WebSocketTestSession, row: int, column: int, letter: str
) -> None:
    """Send one letter and read until its letter_changed (other events skipped)."""
    edit = EditLetter(row=row, column=column, letter=letter)
    websocket.send_text(edit.model_dump_json())
    while True:
        message = parse_server_message(receive_text_or_fail(websocket))
        assert not isinstance(message, ErrorMessage), message
        if isinstance(message, LetterChanged) and (message.row, message.column) == (
            row,
            column,
        ):
            assert message.letter == letter
            return


def count_letters(snapshot: Snapshot) -> dict[tuple[int, int], str]:
    """Return the letters written in the cells of a snapshot."""
    letters: dict[tuple[int, int], str] = {}
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and cell.letter is not None:
            letters[(cell.row, cell.column)] = cell.letter
    return letters


def test_ac7_a_room_open_before_the_withdrawal_can_be_finished_and_reloaded(
    tmp_path: Path, fx01_grid: Grid, dist_dir: Path
) -> None:
    store_path = tmp_path / "nock.sqlite3"
    store = RoomStore(store_path)
    shared = RoomRegistry(config=SERVER_CONFIG, store=store)
    before = Catalogue(entries=(make_entry(fx01_grid, 1),))
    after = Catalogue(entries=(make_entry(fx01_grid, 1, withdrawn=True),))
    app_a = create_app(rooms=shared, catalogue=before, dist_dir=dist_dir)
    app_b = create_app(rooms=shared, catalogue=after, dist_dir=dist_dir)
    second_store: RoomStore | None = None
    second_registry: RoomRegistry | None = None
    try:
        created = TestClient(app_a).post("/api/rooms", json={"grid_number": 1})
        assert created.status_code == 201
        code = created.json()["code"]

        with contextlib.ExitStack() as stack:
            client_b = stack.enter_context(TestClient(app_b))
            ana = join_room(stack, client_b, code, "Ana")
            bob = join_room(stack, client_b, code, "Bob")
            sockets = [ana, bob]
            for index, position in enumerate(sorted(SOLUTION)):
                row, column = position
                type_and_wait(sockets[index % 2], row, column, SOLUTION[position])

            refused = client_b.post("/api/rooms", json={"grid_number": 1})
            assert refused.status_code == 404
            assert refused.json() == NOT_FOUND_BODY

        shared.close()
        store.close()

        second_store = RoomStore(store_path)
        second_registry = RoomRegistry(config=SERVER_CONFIG, store=second_store)
        app_again = create_app(
            rooms=second_registry, catalogue=after, dist_dir=dist_dir
        )
        with contextlib.ExitStack() as stack:
            client_again = stack.enter_context(TestClient(app_again))
            websocket = stack.enter_context(
                client_again.websocket_connect(f"/api/rooms/{code}/ws")
            )
            websocket.send_text(Join(nickname="Cleo").model_dump_json())
            message = parse_server_message(receive_text_or_fail(websocket))

        assert isinstance(message, Snapshot)
        assert count_letters(message) == SOLUTION
    finally:
        if second_registry is not None:
            second_registry.close()
        if second_store is not None:
            second_store.close()
        shared.close()
        store.close()


def test_ac7_a_room_page_is_still_served_whatever_the_catalogue_holds(
    client: TestClient,
) -> None:
    response = client.get("/r/ABC123")

    assert response.status_code == 200
