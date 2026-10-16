"""Tests of spec 028 over HTTP: AC-1, AC-4, AC-5, AC-6 and AC-8.

Rooms are made with `registry.register_room(grid, grid_number=1)` (so with a share
token) and played by simulated clients over the room socket, on spec 011's
`TestClient` and `create_app(rooms=registry, dist_dir=...)`. The throttle cases use
spec 011's `FakeClock`.

Reading of the throttle table: "the request is not counted as a failure" is tested
by sliding window arithmetic. The failures of the first batch are at t0; a refused
request at t0 + 30 s must not move the end of the window, so the request at
t0 + 60 s answers 200. A burst of 40 recap requests for a wrong code, sent at once
from 40 threads, is counted one request after another, as spec 011 says.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.recap import PublicRecap, Recap
from nock.room import RoomState
from nock.server import create_app
from spec011_harness import (
    BURST_SIZE,
    JOIN_TEXT,
    FakeClock,
    SlowLookupRegistry,
    at_once,
    receive_text_or_fail,
)
from spec024_harness import INDEX_HTML, make_dist_dir
from spec028_harness import (
    FAKE_CLOCK_CONFIG,
    SHARE_TOKEN,
    UNKNOWN_TOKEN,
    make_http_registry,
    play_r,
    solve_after_a_removal,
    solve_with_a_check,
    solve_with_a_reveal,
    traffic_problems,
)

NOT_FOUND = {"detail": "Not Found"}
TOO_MANY = {"detail": "Too Many Requests"}
UNKNOWN_CODE = "ZZZZZZ"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    rooms = make_http_registry()
    yield rooms
    rooms.close()


@pytest.fixture
def client(registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def clock_registry(fake_clock: FakeClock) -> Iterator[RoomRegistry]:
    rooms = RoomRegistry(clock=fake_clock, config=FAKE_CLOCK_CONFIG)
    yield rooms
    rooms.close()


@pytest.fixture
def clock_client(clock_registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    app = create_app(rooms=clock_registry, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


def recap_url(code: str) -> str:
    return f"/api/rooms/{code}/recap"


def token_of(registry: RoomRegistry, code: str) -> str:
    state = registry.room_state(code)
    assert state is not None
    assert state.share_token is not None
    return state.share_token


def solved_removal_room(
    registry: RoomRegistry, client: TestClient, grid: Grid
) -> tuple[str, str]:
    """A room where Cy was removed and Ana and Bob solved the grid: code, token."""
    code = registry.register_room(grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        solve_after_a_removal(stack, client, code)
    return code, token_of(registry, code)


def close_code_on_join(client: TestClient, code: str) -> int:
    """Connect to a room, send a join and return the close code received."""
    try:
        with client.websocket_connect(f"/api/rooms/{code}/ws") as websocket:
            websocket.send_text(JOIN_TEXT)
            receive_text_or_fail(websocket)
    except WebSocketDisconnect as closed:
        return closed.code
    pytest.fail("the server sent a message instead of closing the socket")


# ---- AC-1 ----


def test_ac1_the_recap_route_answers_the_totals_of_a_game_with_one_check(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    code = registry.register_room(fx01_grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        _, elapsed = solve_with_a_check(stack, client, code)

    response = client.get(recap_url(code))

    assert response.status_code == 200
    recap = Recap.model_validate(response.json())
    assert recap.checks == 1
    assert recap.letter_reveals == 0
    assert recap.word_reveals == 0
    assert recap.elapsed_ms == elapsed
    assert recap.grid_number == 1


def test_ac1_the_body_is_the_recap_as_json(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    code = registry.register_room(fx01_grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        solve_with_a_check(stack, client, code)

    recap = registry.room_recap(code)

    assert recap is not None
    assert client.get(recap_url(code)).json() == recap.model_dump(mode="json")


# ---- AC-4 ----


def test_ac4_a_revealed_letter_is_credited_to_nobody_in_a_socket_game(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    code = registry.register_room(fx01_grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        solve_with_a_reveal(stack, client, code)

    recap = Recap.model_validate(client.get(recap_url(code)).json())

    assert sum(player.letters for player in recap.players) == 17
    assert recap.revealed_letters == 1
    assert recap.letter_reveals == 1
    assert recap.letter_cells == 18


# ---- AC-5 ----


def test_ac5_the_share_path_and_the_public_recap_after_a_removal(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    code, token = solved_removal_room(registry, client, fx01_grid)

    recap = Recap.model_validate(client.get(recap_url(code)).json())
    shared = client.get(f"/api/recaps/{token}")

    assert recap.share_path == f"/recap/{token}"
    assert shared.status_code == 200
    assert PublicRecap.model_validate(shared.json()) == PublicRecap(
        grid_number=1, elapsed_ms=recap.elapsed_ms, team=("Ana", "Bob")
    )


def test_ac5_the_removed_player_keeps_a_row_with_nothing_in_it(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    code, _ = solved_removal_room(registry, client, fx01_grid)

    recap = Recap.model_validate(client.get(recap_url(code)).json())

    names = [player.nickname for player in recap.players]
    assert names == ["Ana", "Bob", "Cy"]
    cy = recap.players[2]
    assert (cy.removed, cy.letters, cy.words) == (True, 0, 0)
    assert recap.players[0].removed is False
    assert recap.players[1].removed is False


def test_ac5_the_share_page_answers_index_html(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    _, token = solved_removal_room(registry, client, fx01_grid)

    response = client.get(f"/recap/{token}")

    assert response.status_code == 200
    assert response.text == INDEX_HTML


def test_ac5_the_share_page_answers_503_when_the_client_is_not_built(
    registry: RoomRegistry, tmp_path: Path, fx01_grid: Grid
) -> None:
    empty_dist = tmp_path / "empty"
    empty_dist.mkdir()
    app = create_app(rooms=registry, dist_dir=empty_dist)
    with TestClient(app) as test_client:
        _, token = solved_removal_room(registry, test_client, fx01_grid)

        response = test_client.get(f"/recap/{token}")
        api_response = test_client.get(f"/api/recaps/{token}")

    assert response.status_code == 503
    assert api_response.status_code == 200


def test_ac5_the_share_routes_follow_spec_040_no_redirect_and_no_trailing_slash(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    _, token = solved_removal_room(registry, client, fx01_grid)

    page = client.get(f"/recap/{token}/", follow_redirects=False)
    api = client.get(f"/api/recaps/{token}/", follow_redirects=False)

    assert page.status_code == 404
    assert api.status_code == 404


# ---- AC-6 ----


def test_ac6_the_public_recap_has_exactly_three_keys(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    _, token = solved_removal_room(registry, client, fx01_grid)

    body = client.get(f"/api/recaps/{token}").json()

    assert sorted(body) == ["elapsed_ms", "grid_number", "team"]


def test_ac6_both_recap_bodies_pass_the_three_rules_of_spec_037(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    code, token = solved_removal_room(registry, client, fx01_grid)

    room_body = client.get(recap_url(code)).text
    share_body = client.get(f"/api/recaps/{token}").text

    assert traffic_problems(room_body) == []
    assert traffic_problems(share_body) == []
    assert json.loads(room_body)["players"][0]["nickname"] == "Ana"


# ---- AC-8 ----


def test_ac8_a_room_that_is_not_solved_answers_404(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    code = registry.register_room(fx01_grid, grid_number=1)

    response = client.get(recap_url(code))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_ac8_an_unsolved_room_records_no_failure(
    clock_registry: RoomRegistry, clock_client: TestClient, fx01_grid: Grid
) -> None:
    unsolved = clock_registry.register_room(fx01_grid, grid_number=1)
    solved = clock_registry.register_room(fx01_grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        solve_with_a_check(stack, clock_client, solved)

    for _ in range(12):
        assert clock_client.get(recap_url(unsolved)).status_code == 404

    assert clock_client.get(recap_url(solved)).status_code == 200


def test_ac8_wrong_codes_count_against_the_throttle_and_it_lifts_after_a_minute(
    clock_registry: RoomRegistry,
    clock_client: TestClient,
    fake_clock: FakeClock,
    fx01_grid: Grid,
) -> None:
    code = clock_registry.register_room(fx01_grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        solve_with_a_check(stack, clock_client, code)

    for _ in range(10):
        response = clock_client.get(recap_url(UNKNOWN_CODE))
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
    throttled = clock_client.get(recap_url(code))

    assert throttled.status_code == 429
    assert throttled.json() == TOO_MANY
    assert close_code_on_join(clock_client, code) == 4429
    fake_clock.advance(60)
    assert clock_client.get(recap_url(code)).status_code == 200


def test_ac8_a_refused_request_does_not_extend_the_window(
    clock_registry: RoomRegistry,
    clock_client: TestClient,
    fake_clock: FakeClock,
    fx01_grid: Grid,
) -> None:
    code = clock_registry.register_room(fx01_grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        solve_with_a_check(stack, clock_client, code)
    for _ in range(10):
        clock_client.get(recap_url(UNKNOWN_CODE))

    fake_clock.advance(30)
    assert clock_client.get(recap_url(code)).status_code == 429
    fake_clock.advance(30)

    assert clock_client.get(recap_url(code)).status_code == 200


def test_ac8_nine_wrong_codes_do_not_throttle(
    clock_registry: RoomRegistry, clock_client: TestClient, fx01_grid: Grid
) -> None:
    code = clock_registry.register_room(fx01_grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        solve_with_a_check(stack, clock_client, code)

    for _ in range(9):
        clock_client.get(recap_url(UNKNOWN_CODE))

    assert clock_client.get(recap_url(code)).status_code == 200


def recap_answer(client: TestClient, code: str) -> tuple[int, object]:
    """The status and the JSON body of `GET /api/rooms/<code>/recap`."""
    response = client.get(recap_url(code))
    return response.status_code, response.json()


def test_ac8_forty_recap_requests_at_once_get_ten_404_and_thirty_429(
    fake_clock: FakeClock, dist_dir: Path
) -> None:
    # The clock does not move. Each lookup answers a little later
    # (`SlowLookupRegistry`), so that the 40 requests are in flight together.
    registry = SlowLookupRegistry(clock=fake_clock)
    try:
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client:
            answers = at_once(BURST_SIZE, lambda: recap_answer(client, UNKNOWN_CODE))
    finally:
        registry.close()

    not_found = 0
    throttled = 0
    others: list[object] = []
    for answer in answers:
        if answer == (404, NOT_FOUND):
            not_found += 1
        elif answer == (429, TOO_MANY):
            throttled += 1
        else:
            others.append(answer)
    assert (not_found, throttled, others) == (10, 30, [])


def test_ac8_the_share_routes_answer_404_for_a_token_that_is_not_a_solved_room(
    clock_registry: RoomRegistry, clock_client: TestClient, fx01_grid: Grid
) -> None:
    unsolved = clock_registry.register_room(fx01_grid, grid_number=1)
    unsolved_token = token_of(clock_registry, unsolved)

    for token in [unsolved_token, UNKNOWN_TOKEN, "a b"]:
        api = clock_client.get(f"/api/recaps/{token}")
        page = clock_client.get(f"/recap/{token}")
        assert api.status_code == 404, token
        assert api.json() == NOT_FOUND, token
        assert page.status_code == 404, token
        assert page.json() == NOT_FOUND, token


def test_ac8_the_share_routes_are_not_counted_by_the_throttle(
    clock_registry: RoomRegistry, clock_client: TestClient, fx01_grid: Grid
) -> None:
    unsolved = clock_registry.register_room(fx01_grid, grid_number=1)
    unsolved_token = token_of(clock_registry, unsolved)
    solved = clock_registry.register_room(fx01_grid, grid_number=1)
    with contextlib.ExitStack() as stack:
        solve_with_a_check(stack, clock_client, solved)

    for _ in range(3):
        for token in [unsolved_token, UNKNOWN_TOKEN, "a b"]:
            clock_client.get(f"/api/recaps/{token}")
            clock_client.get(f"/recap/{token}")

    assert clock_client.get(recap_url(solved)).status_code == 200


def test_ac8_a_room_added_without_its_history_has_no_recap(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    state: RoomState = play_r(fx01_grid).state
    registry.add_room(state)

    assert registry.room_recap(state.code) is None
    assert registry.shared_recap(SHARE_TOKEN) is None
    response = client.get(recap_url(state.code))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert client.get(f"/api/recaps/{SHARE_TOKEN}").status_code == 404
