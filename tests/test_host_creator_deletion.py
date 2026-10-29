"""Tests of lobby/host, AC-15: erasing an account deletes the rooms it created.

Over the room socket, with the app of `host_harness`. Lea's account is erased with
`DELETE /api/account` (the identities she recorded with `PUT /api/account/rooms`
are what the erasure reaches, as her page does):

- R, Lea's creator room, solved: Bob (signed in, her identity and his recorded) is
  the connected stand-in host.
- S, Bob's creator room: Lea is a player, Bob host.
- T, an anonymous room: Lea is the host, with Cy.

`erased_scene` plays all of it up to the answer of the deletion, and each test
reads one facet.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient

from host_harness import (
    BOB_EMAIL,
    HAND_OVER_SECONDS,
    LEA_EMAIL,
    HostApp,
    account_id_of,
    create_room_as,
    host_app,
    host_ids,
    open_member,
    sign_in_as,
    wait_for_host,
    wait_for_state,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import EditLetter, GridSolved, PlayerState, Pong, ServerMessage
from nock.room import RoomState
from nock.store import RoomStore
from spec012_harness import close_code_of_next_read
from spec014_harness import Peer, ping_and_wait, player_of, socket_url
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec028_harness import ROW_MAJOR, SOLUTION
from spec029_harness import history_body
from spec032_harness import grid_from_text
from spec033_harness import ACCOUNT_PATH, ROOMS_PATH, room_key, state_of, with_session

ROOM_NOT_FOUND = 4404
THROTTLED = 4429
WRONG_CODE_LIMIT = 10  # `lobby/rooms.md`: ten wrong codes in a minute
FORMER = "--"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


class Erased(NamedTuple):
    """The play of AC-15 once Lea's account is deleted; the app is still running."""

    app: HostApp
    bob_session: str
    bob_account: str
    r_code: str
    s_code: str
    t_code: str
    lea_in_s: str
    lea_in_t: str
    bob_in_s: str
    cy_in_t: str
    bob_r: Peer
    bob_s: Peer
    cy_t: Peer
    bob_r_before: list[ServerMessage]
    bob_s_before: list[ServerMessage]
    cy_t_before: list[ServerMessage]
    deletion_status: int


def record(app: HostApp, session: str, code: str, peer: Peer) -> None:
    """`PUT /api/account/rooms` with the peer's token, as the account's page does."""
    key = room_key(code, peer.snapshot().resume_token)
    response = app.client.put(ROOMS_PATH, json=key, headers=with_session(session))
    assert response.status_code == 204, response.text


def solve_from(peer: Peer) -> None:
    """Type the solution of the grid from a peer, then wait for the room."""
    for row, column in ROW_MAJOR:
        letter = SOLUTION[(row, column)]
        peer.send(EditLetter(row=row, column=column, letter=letter))
    ping_and_wait(peer)


def without_pongs(messages: list[ServerMessage]) -> list[ServerMessage]:
    """The messages, leaving out the pongs of the test's pings."""
    kept: list[ServerMessage] = []
    for message in messages:
        if not isinstance(message, Pong):
            kept.append(message)
    return kept


@contextlib.contextmanager
def erased_scene(
    directory: Path,
    clock: FakeClock,
    catalogue: Catalogue,
    grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Erased]:
    """Play AC-15 up to the answer of `DELETE /api/account` with Lea's session."""
    with (
        host_app(directory, clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as lea_r_stack,
    ):
        lea_session = sign_in_as(app, LEA_EMAIL)
        bob_session = sign_in_as(app, BOB_EMAIL)
        bob_account = account_id_of(app, bob_session)

        # R: Lea's creator room, solved by Bob; Lea goes away, Bob stands in.
        r_code = create_room_as(app, lea_session)
        lea_r = open_member(lea_r_stack, app.client, r_code, "Lea", None, lea_session)
        bob_r = open_member(stack, app.client, r_code, "Bob", None, bob_session)
        record(app, lea_session, r_code, lea_r)
        record(app, bob_session, r_code, bob_r)
        solve_from(bob_r)
        bob_r.wait_until(
            lambda: any(isinstance(m, GridSolved) for m in bob_r.messages()),
            "the grid_solved event",
        )
        lea_r_stack.close()
        wait_for_state(
            app.registry, r_code, lea_r.snapshot().you, PlayerState.DISCONNECTED
        )
        clock.advance(HAND_OVER_SECONDS + 1)
        wait_for_host(app.registry, r_code, bob_r.snapshot().you)

        # S: Bob's creator room, with Lea as a player.
        s_code = create_room_as(app, bob_session)
        bob_s = open_member(stack, app.client, s_code, "Bob", None, bob_session)
        lea_s = open_member(stack, app.client, s_code, "Lea", None, lea_session)
        record(app, lea_session, s_code, lea_s)

        # T: an anonymous room where Lea is host.
        t_code = app.registry.register_room(grid, grid_number=1)
        lea_t = open_member(stack, app.client, t_code, "Lea", None, lea_session)
        cy_t = open_member(stack, app.client, t_code, "Cy")
        record(app, lea_session, t_code, lea_t)

        for peer in (bob_r, bob_s, cy_t):
            ping_and_wait(peer)
        bob_r_before = without_pongs(bob_r.messages())
        bob_s_before = without_pongs(bob_s.messages())
        cy_t_before = without_pongs(cy_t.messages())

        deletion = app.client.delete(ACCOUNT_PATH, headers=with_session(lea_session))
        yield Erased(
            app=app,
            bob_session=bob_session,
            bob_account=bob_account,
            r_code=r_code,
            s_code=s_code,
            t_code=t_code,
            lea_in_s=lea_s.snapshot().you,
            lea_in_t=lea_t.snapshot().you,
            bob_in_s=bob_s.snapshot().you,
            cy_in_t=cy_t.snapshot().you,
            bob_r=bob_r,
            bob_s=bob_s,
            cy_t=cy_t,
            bob_r_before=bob_r_before,
            bob_s_before=bob_s_before,
            cy_t_before=cy_t_before,
            deletion_status=deletion.status_code,
        )


def stored_room(app: HostApp, code: str) -> RoomState | None:
    """The room as a second store on the database file loads it."""
    store = RoomStore(app.database_path)
    try:
        return store.load_room(code)
    finally:
        store.close()


def close_code_before_any_message(client: TestClient, code: str) -> int:
    """Open a socket to a room and return the code it is closed with."""
    with client.websocket_connect(socket_url(code)) as websocket:
        return close_code_of_next_read(websocket)


def test_ac15_the_erasure_closes_the_other_players_socket_with_4404_and_nothing_else(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with erased_scene(tmp_path, fake_clock, catalogue, fx01_grid, monkeypatch) as scene:
        scene.bob_r.wait_until(
            lambda: scene.bob_r.close_code is not None, "the close of Bob's R socket"
        )
        after = without_pongs(scene.bob_r.messages())

    assert scene.deletion_status == 204
    assert scene.bob_r.close_code == ROOM_NOT_FOUND
    assert after == scene.bob_r_before


def test_ac15_the_creator_room_is_gone_live_and_stored_and_its_code_is_wrong(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with erased_scene(tmp_path, fake_clock, catalogue, fx01_grid, monkeypatch) as scene:
        live = scene.app.registry.room_state(scene.r_code)
        stored = stored_room(scene.app, scene.r_code)
        has_rows = scene.app.store.has_room(scene.r_code)
        log = scene.app.store.read_log(scene.r_code)
        wrong_codes: list[int] = []
        for _ in range(WRONG_CODE_LIMIT):
            wrong_codes.append(
                close_code_before_any_message(scene.app.client, scene.r_code)
            )
        next_attempt = close_code_before_any_message(scene.app.client, scene.s_code)

    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as restarted:
        after_restart = restarted.registry.room_state(scene.r_code)
        has_rows_after = restarted.store.has_room(scene.r_code)

    assert (live, stored, has_rows, log) == (None, None, False, [])
    assert (after_restart, has_rows_after) == (None, False)
    assert wrong_codes == [ROOM_NOT_FOUND] * WRONG_CODE_LIMIT
    assert next_attempt == THROTTLED


def test_ac15_bobs_history_keeps_the_solved_record_naming_her_dashes(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with erased_scene(tmp_path, fake_clock, catalogue, fx01_grid, monkeypatch) as scene:
        records = history_body(scene.app.client, scene.bob_session)

    assert [record["code"] for record in records] == [scene.r_code]
    assert records[0]["teammates"] == [FORMER]


def test_ac15_in_a_room_she_did_not_create_her_player_is_erased_and_nothing_else(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with erased_scene(tmp_path, fake_clock, catalogue, fx01_grid, monkeypatch) as scene:
        ping_and_wait(scene.bob_s)
        live = state_of(scene.app.registry, scene.s_code)
        stored = stored_room(scene.app, scene.s_code)
        bob_s_after = without_pongs(scene.bob_s.messages())

    assert stored is not None
    for room in (live, stored):
        lea = player_of(room, scene.lea_in_s)
        assert (lea.nickname, lea.account_id) == (FORMER, None)
        assert room.creator_account_id == scene.bob_account
        assert host_ids(room) == [scene.bob_in_s]
        assert [p.player_id for p in room.players] == [scene.bob_in_s, scene.lea_in_s]
    assert bob_s_after == scene.bob_s_before


def test_ac15_an_anonymous_room_where_she_was_host_keeps_its_players_and_host(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with erased_scene(tmp_path, fake_clock, catalogue, fx01_grid, monkeypatch) as scene:
        ping_and_wait(scene.cy_t)
        live = state_of(scene.app.registry, scene.t_code)
        cy_after = without_pongs(scene.cy_t.messages())

    lea = player_of(live, scene.lea_in_t)
    assert (lea.nickname, lea.account_id) == (FORMER, None)
    assert [p.player_id for p in live.players] == [scene.lea_in_t, scene.cy_in_t]
    assert host_ids(live) == [scene.lea_in_t]
    assert cy_after == scene.cy_t_before
