"""Tests of spec 038 (privacy and operations), AC-6: the ops API is the operator's.

The ops API runs on `TestClient(create_app(rooms=registry, dist_dir=tmp_path,
operator_token=OPS_TOKEN))`, with a registry on conftest's fake clock whose store
holds rooms with chosen creation times (`new_room(code, grid, <creation time>)`,
then `add_room`, then `store.append` of hand-made entries), as the spec's "Test
harness" says. "Off" is `create_app(rooms=registry, dist_dir=tmp_path)` with
NOCK_OPERATOR_TOKEN deleted. The shared setup is in `spec038_harness`; spec 011's
`at_once` sends a burst of requests at once.

Edge cases checked as well, from "Operator access" and "Edge cases and errors": a
token that differs by one character, a token in a cookie, nine refusals, a 429
that is not counted, the token in the query counted as a refusal, a burst of wrong
tokens counted one after another while each token check is slow, two apps with
their own failures, the room sockets' separate wrong-code count, the replay route
under the same rules, the token checked before the query, the code and the room,
an empty NOCK_OPERATOR_TOKEN, `/api/ops`, `/api/ops/` and `/api/ops/xyz` with any
method while the pages are off, the other requests under `/api/ops/` while they
are on (no token check, nothing counted), `/ops` with no built client (503, as
`/`), and a room that is only in the store, which the dashboard reads without
making it live. What a throttle keeps in memory is checked in Python, in
`test_spec_038_ac06_throttle_memory.py`.

The names this spec adds are used inside the tests, so that each test fails on
the one it needs (see `spec038_harness`).
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, Join, PlayerState, Snapshot, parse_server_message
from nock.room import handle_message, join_room, new_room
from nock.server import create_app
from nock.store import RoomStore
from spec011_harness import BURST_SIZE, at_once
from spec012_harness import close_code_of_next_read, receive_text_or_fail, socket_url
from spec017_harness import FakeClock
from spec038_harness import (
    DASHBOARD_PATH,
    DAY,
    NOT_AUTHORIZED,
    NOT_FOUND,
    OPERATOR_TOKEN_VARIABLE,
    OPS_PAGE_PATH,
    OPS_TOKEN,
    TOO_MANY_REQUESTS,
    UNKNOWN_API_PATH,
    UNKNOWN_PATH,
    WRONG_CODE_LIMIT,
    WRONG_CODE_WINDOW_SECONDS,
    Log,
    answer_of,
    bearer,
    edits_path,
    seed_room,
)

if TYPE_CHECKING:
    from nock.operations import DashboardFigures

# ---- Values of the spec --------------------------------------------------------------

NO_STORE = "no-store"
BEARER_CHALLENGE = "Bearer"
METHOD_NOT_ALLOWED = {"detail": "Method Not Allowed"}  # FastAPI's 405

# Rooms created 8 days, 7 days and 1 day before `now`.
OLD_CODE = "OLD8DY"
EDGE_CODE = "EDGE7D"
NEW_CODE = "NEW1DY"

# ---- Values of the test harness ------------------------------------------------------

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
UNKNOWN_ROOM = "ZZZZZZ"
THROTTLED_CLOSE_CODE = 4429  # spec 011
ROOM_NOT_FOUND_CLOSE_CODE = 4404
TOKEN_CHECK_DELAY_SECONDS = 0.05
# A wrong token as long as OPS_TOKEN: its check is the whole comparison of rule 3.
SAME_LENGTH_WRONG_TOKEN = "Ops-" + "y" * 40


class SlowTokenCheck:
    """Rule 3's comparison, `secrets.compare_digest`, made slower and counted.

    A token check can take a while on a busy server. In a burst the delay keeps
    the wrong tokens in flight at the same time, between the throttle's check of
    rule 2 and the record of their refusal, whatever the order in which their
    threads run, so a check and a record that are not one step show on every
    run, as spec 011's `SlowLookupRegistry` does with room lookups.
    """

    def __init__(self) -> None:
        self.original = secrets.compare_digest
        self.calls = 0
        self.lock = threading.Lock()

    # `Text` is str or bytes, the same for both values, as compare_digest takes.
    def compare[Text: (str, bytes)](self, first: Text, second: Text) -> bool:
        """Wait TOKEN_CHECK_DELAY_SECONDS, count the call, then compare as usual."""
        time.sleep(TOKEN_CHECK_DELAY_SECONDS)
        with self.lock:
            self.calls += 1
        return self.original(first, second)


# ---- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    """`tmp_path` with an `index.html`, the `dist_dir` of the "Test harness"."""
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def registry(fake_clock: FakeClock) -> Iterator[RoomRegistry]:
    """A registry on conftest's fake clock, with its own in-memory store."""
    room_registry = RoomRegistry(clock=fake_clock)
    yield room_registry
    room_registry.close()


@pytest.fixture
def ops_client(registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    """The app with the operator pages on: `operator_token=OPS_TOKEN`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def off_client(
    registry: RoomRegistry, dist_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """The app with the operator pages off: no token, the variable deleted."""
    monkeypatch.delenv(OPERATOR_TOKEN_VARIABLE, raising=False)
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def slow_token_check(monkeypatch: pytest.MonkeyPatch) -> SlowTokenCheck:
    """Replace `secrets.compare_digest` by a `SlowTokenCheck` during the test."""
    slow_check = SlowTokenCheck()
    monkeypatch.setattr(secrets, "compare_digest", slow_check.compare)
    return slow_check


@pytest.fixture
def seeded(registry: RoomRegistry, fx01_grid: Grid) -> RoomRegistry:
    """The registry with three rooms, created 8 days, 7 days and 1 day ago."""
    now = registry.clock()

    old_log = Log(now - 8 * DAY + 10)
    old_log.join("p1", "ANA", 0, "token-of-ana-0001")
    old_log.join("p2", "BOB", 1, "token-of-bob-0002")
    old_log.letter("p1", 1, 0, "T", relay_ms=70)
    old_log.solved(400_000)
    seed_room(registry, new_room(OLD_CODE, fx01_grid, now - 8 * DAY), old_log.entries)

    edge_log = Log(now - 7 * DAY + 10)
    edge_log.join("p1", "ANA", 0, "token-of-ana-0003")
    edge_log.join("p2", "BOB", 1, "token-of-bob-0004")
    edge_log.letter("p1", 1, 0, "T", relay_ms=40)
    edge_log.letter("p2", 1, 1, "A", relay_ms=10)
    edge_log.presence("p2", PlayerState.DISCONNECTED)
    edge_log.presence("p2", PlayerState.ACTIVE)
    edge_log.solved(300_000)
    seed_room(registry, new_room(EDGE_CODE, fx01_grid, now - 7 * DAY), edge_log.entries)

    new_log = Log(now - DAY + 10)
    new_log.join("p1", "ANA", 0, "token-of-ana-0005")
    new_log.letter("p1", 1, 0, "T", relay_ms=25)
    seed_room(registry, new_room(NEW_CODE, fx01_grid, now - DAY), new_log.entries)
    return registry


# ---- Reading the answers -------------------------------------------------------------


def figures_of(response: Response) -> DashboardFigures:
    """The figures of a dashboard answer, read as `DashboardFigures`.

    The answer also holds `offered_days` (`admin/operations.md` rule 12), which is
    not a figure: it is checked in `test_spec_038_ac06_offered_periods.py`.
    """
    from nock.operations import DashboardFigures

    body = response.json()
    assert isinstance(body, dict), body
    body.pop("offered_days", None)
    return DashboardFigures.model_validate(body)


def figures_from_the_store(registry: RoomRegistry, days: int) -> DashboardFigures:
    """`dashboard_figures` over the rooms the store gives for the period.

    One `RoomLog` per pair of `rooms.store.codes_created_since(now - days * DAY)`,
    with that room's whole log, as "Ops API" says.
    """
    from nock.operations import RoomLog, dashboard_figures

    now = registry.clock()
    rooms: list[RoomLog] = []
    for code, created_at in registry.store.codes_created_since(now - days * DAY):
        entries = tuple(registry.store.read_log(code))
        rooms.append(RoomLog(code=code, created_at=created_at, entries=entries))
    return dashboard_figures(rooms, days, now)


def status_and_body(response: Response) -> tuple[int, object]:
    return response.status_code, response.json()


def refuse(client: TestClient, count: int) -> None:
    """Send `count` dashboard requests without a token; each must answer 401."""
    for _ in range(count):
        response = client.get(DASHBOARD_PATH)
        assert response.status_code == 401, response.text


def assert_refused_as_not_authorized(response: Response) -> None:
    """Rule 3's answer: 401, `Not authorized`, the Bearer challenge, no-store."""
    assert response.status_code == 401, response.text
    assert response.json() == NOT_AUTHORIZED
    assert response.headers.get("www-authenticate") == BEARER_CHALLENGE
    assert response.headers.get("cache-control") == NO_STORE


def assert_throttled(response: Response) -> None:
    """Rule 2's answer: 429, `Too Many Requests`, no-store."""
    assert response.status_code == 429, response.text
    assert response.json() == TOO_MANY_REQUESTS
    assert response.headers.get("cache-control") == NO_STORE


# ---- AC-6: the dashboard answers the operator --------------------------------------


def test_ac6_the_dashboard_with_the_token_answers_200_with_the_7_day_figures(
    seeded: RoomRegistry, ops_client: TestClient
) -> None:
    response = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text
    result = figures_of(response)
    assert result.days == 7
    assert result == figures_from_the_store(seeded, 7)


def test_ac6_the_7_day_figures_hold_the_rooms_of_7_days_and_1_day_ago(
    seeded: RoomRegistry, ops_client: TestClient
) -> None:
    response = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    result = figures_of(response)
    # EDGE (created exactly 7 days ago) and NEW; OLD is older than the period.
    assert result.rooms_created == 2
    assert result.players_per_room == 1.5
    assert result.completion_rate == 0.5
    assert result.median_solving_ms == 300_000.0
    assert result.latency_median_ms == 25.0
    assert result.latency_p95_ms == 40
    assert result.disconnection_rate == 1 / 3


@pytest.mark.parametrize(("days", "rooms_created"), [(1, 1), (7, 2), (30, 3)])
def test_ac6_days_1_7_and_30_give_the_figures_of_that_period(
    seeded: RoomRegistry, ops_client: TestClient, days: int, rooms_created: int
) -> None:
    response = ops_client.get(
        f"{DASHBOARD_PATH}?days={days}", headers=bearer(OPS_TOKEN)
    )

    assert response.status_code == 200, response.text
    result = figures_of(response)
    assert result.days == days
    assert result.rooms_created == rooms_created
    assert result == figures_from_the_store(seeded, days)


@pytest.mark.parametrize("days", ["2", "0", "31", "-7", "abc", "7.5"])
def test_ac6_any_other_days_answers_422_with_fastapis_validation_body(
    ops_client: TestClient, days: str
) -> None:
    response = ops_client.get(
        f"{DASHBOARD_PATH}?days={days}", headers=bearer(OPS_TOKEN)
    )

    assert response.status_code == 422, response.text
    body = response.json()
    assert isinstance(body, dict), body
    assert list(body) == ["detail"]
    assert isinstance(body["detail"], list), body


def test_ac6_codes_created_since_returns_the_pairs_of_the_rooms_of_the_period(
    seeded: RoomRegistry,
) -> None:
    now = seeded.clock()

    pairs = seeded.store.codes_created_since(now - 7 * DAY)

    assert sorted(pairs) == sorted([(EDGE_CODE, now - 7 * DAY), (NEW_CODE, now - DAY)])


def test_ac6_codes_created_since_after_the_last_creation_returns_nothing(
    seeded: RoomRegistry,
) -> None:
    now = seeded.clock()

    assert seeded.store.codes_created_since(now) == []


def test_ac6_codes_created_since_a_month_ago_returns_the_three_rooms(
    seeded: RoomRegistry,
) -> None:
    now = seeded.clock()

    pairs = seeded.store.codes_created_since(now - 30 * DAY)

    expected = [
        (OLD_CODE, now - 8 * DAY),
        (EDGE_CODE, now - 7 * DAY),
        (NEW_CODE, now - DAY),
    ]
    assert sorted(pairs) == sorted(expected)


def test_ac6_the_dashboard_reads_a_room_only_in_the_store_without_making_it_live(
    fake_clock: FakeClock, fx01_grid: Grid, dist_dir: Path
) -> None:
    # Ana joined and wrote T; only the store holds the room. Making it live would
    # log her disconnection (spec 018's `after_restart`).
    store = RoomStore(":memory:")
    now = fake_clock()
    state = new_room(NEW_CODE, fx01_grid, now - DAY)
    store.create_room(state)
    joined = join_room(
        state,
        Join(nickname="Ana", resume_token=None),
        now - DAY + 1,
        "p1",
        "token-of-ana-0001",
    )
    store.append(NEW_CODE, joined.entries)
    edit = EditLetter(row=1, column=0, letter="T")
    typed = handle_message(joined.state, "p1", edit, now - DAY + 2)
    store.append(NEW_CODE, typed.entries)
    log_before = store.read_log(NEW_CODE)
    registry = RoomRegistry(clock=fake_clock, store=store)
    try:
        app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)
        with TestClient(app) as client:
            response = client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))
        log_after = store.read_log(NEW_CODE)
    finally:
        registry.close()
        store.close()

    assert response.status_code == 200, response.text
    assert figures_of(response).rooms_created == 1
    assert log_after == log_before


# ---- AC-6: everyone else is refused --------------------------------------------------


REFUSED_REQUESTS = [
    pytest.param(DASHBOARD_PATH, {}, id="no-header"),
    pytest.param(DASHBOARD_PATH, {"Authorization": "Bearer wrong"}, id="bearer-wrong"),
    pytest.param(DASHBOARD_PATH, {"Authorization": f"Basic {OPS_TOKEN}"}, id="basic"),
    pytest.param(f"{DASHBOARD_PATH}?token={OPS_TOKEN}", {}, id="token-in-the-query"),
    # Edge cases: a token that differs by one character, or in another case.
    pytest.param(
        DASHBOARD_PATH,
        {"Authorization": f"Bearer {OPS_TOKEN[:-1]}"},
        id="bearer-one-character-short",
    ),
    pytest.param(
        DASHBOARD_PATH,
        {"Authorization": f"Bearer {OPS_TOKEN}x"},
        id="bearer-one-character-more",
    ),
    pytest.param(
        DASHBOARD_PATH,
        {"Authorization": f"Bearer {OPS_TOKEN.upper()}"},
        id="bearer-in-capitals",
    ),
    # "The token is never read from a URL, a query or a cookie."
    pytest.param(
        DASHBOARD_PATH,
        {"Cookie": f"token={OPS_TOKEN}; nock.ops_token={OPS_TOKEN}"},
        id="token-in-a-cookie",
    ),
    # Rules 2 and 3 apply to both ops routes.
    pytest.param(edits_path(NEW_CODE), {}, id="replay-no-header"),
    pytest.param(
        edits_path(NEW_CODE), {"Authorization": "Bearer wrong"}, id="replay-wrong"
    ),
    # Rule 3 comes before anything else of the request is looked at: its query,
    # its code, its room.
    pytest.param(
        f"{DASHBOARD_PATH}?days=2",
        {"Authorization": "Bearer wrong"},
        id="days-2-bearer-wrong",
    ),
    pytest.param(f"{DASHBOARD_PATH}?days=2", {}, id="days-2-no-header"),
    pytest.param(
        edits_path("abc"),
        {"Authorization": "Bearer wrong"},
        id="replay-code-breaking-the-pattern-wrong",
    ),
    pytest.param(edits_path(UNKNOWN_ROOM), {}, id="replay-unknown-room-no-header"),
]


@pytest.mark.parametrize(("path", "headers"), REFUSED_REQUESTS)
def test_ac6_a_missing_or_wrong_token_answers_401_with_the_bearer_challenge(
    seeded: RoomRegistry, ops_client: TestClient, path: str, headers: dict[str, str]
) -> None:
    response = ops_client.get(path, headers=headers)

    assert_refused_as_not_authorized(response)


def test_ac6_every_ops_answer_has_cache_control_no_store_while_the_pages_are_on(
    seeded: RoomRegistry, ops_client: TestClient
) -> None:
    answers = {
        "dashboard 200": ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN)),
        "dashboard 422": ops_client.get(
            f"{DASHBOARD_PATH}?days=2", headers=bearer(OPS_TOKEN)
        ),
        "replay 200": ops_client.get(edits_path(NEW_CODE), headers=bearer(OPS_TOKEN)),
        "replay 404": ops_client.get(
            edits_path(UNKNOWN_ROOM), headers=bearer(OPS_TOKEN)
        ),
        "dashboard 401": ops_client.get(DASHBOARD_PATH),
    }
    refuse(ops_client, WRONG_CODE_LIMIT - 1)
    answers["dashboard 429"] = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    statuses: dict[str, int] = {}
    cache_controls: dict[str, str | None] = {}
    for name, response in answers.items():
        statuses[name] = response.status_code
        cache_controls[name] = response.headers.get("cache-control")
    assert statuses == {
        "dashboard 200": 200,
        "dashboard 422": 422,
        "replay 200": 200,
        "replay 404": 404,
        "dashboard 401": 401,
        "dashboard 429": 429,
    }
    assert cache_controls == dict.fromkeys(answers, NO_STORE)


# ---- AC-6: the throttle of refused requests -----------------------------------------


def test_ac6_ten_refusals_within_a_minute_throttle_the_address_even_the_right_token(
    ops_client: TestClient, fake_clock: FakeClock
) -> None:
    # Ten refusals, 5 s apart: the first at t0, the last at t0 + 45 s.
    for _ in range(WRONG_CODE_LIMIT):
        response = ops_client.get(DASHBOARD_PATH)
        assert response.status_code == 401
        fake_clock.advance(5)

    throttled = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert_throttled(throttled)


def test_ac6_the_right_token_gets_200_again_60_seconds_after_the_last_refusal(
    ops_client: TestClient, fake_clock: FakeClock
) -> None:
    for _ in range(WRONG_CODE_LIMIT):
        assert ops_client.get(DASHBOARD_PATH).status_code == 401
        fake_clock.advance(5)
    assert ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN)).status_code == 429

    fake_clock.advance(WRONG_CODE_WINDOW_SECONDS)

    response = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))
    assert response.status_code == 200, response.text


def test_ac6_a_wrong_token_is_throttled_too(ops_client: TestClient) -> None:
    refuse(ops_client, WRONG_CODE_LIMIT)

    throttled = ops_client.get(DASHBOARD_PATH, headers=bearer("wrong"))

    assert_throttled(throttled)


def test_ac6_nine_refusals_do_not_throttle(ops_client: TestClient) -> None:
    refuse(ops_client, WRONG_CODE_LIMIT - 1)

    response = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text


def test_ac6_a_throttled_request_is_not_counted(
    ops_client: TestClient, fake_clock: FakeClock
) -> None:
    refuse(ops_client, WRONG_CODE_LIMIT)  # at t0
    fake_clock.advance(30)
    for _ in range(WRONG_CODE_LIMIT):
        assert ops_client.get(DASHBOARD_PATH).status_code == 429  # at t0 + 30 s
    fake_clock.advance(30.5)  # t0 + 60.5 s: the ten refusals of t0 are forgotten

    response = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text


def test_ac6_the_token_in_the_query_counts_as_a_refusal(ops_client: TestClient) -> None:
    for _ in range(WRONG_CODE_LIMIT):
        response = ops_client.get(f"{DASHBOARD_PATH}?token={OPS_TOKEN}")
        assert response.status_code == 401

    throttled = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert_throttled(throttled)


def test_ac6_refusals_of_the_replay_route_count_too(ops_client: TestClient) -> None:
    for _ in range(WRONG_CODE_LIMIT):
        assert ops_client.get(edits_path(NEW_CODE)).status_code == 401

    throttled = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert_throttled(throttled)


def test_ac6_forty_wrong_tokens_at_once_get_ten_401_and_thirty_429(
    ops_client: TestClient, slow_token_check: SlowTokenCheck
) -> None:
    # The clock does not move. Each token check answers a little later
    # (`SlowTokenCheck`), so that the 40 wrong tokens are in flight together.
    wrong_token = bearer(SAME_LENGTH_WRONG_TOKEN)
    answers = at_once(
        BURST_SIZE,
        lambda: status_and_body(ops_client.get(DASHBOARD_PATH, headers=wrong_token)),
    )

    refused = 0
    throttled = 0
    others: list[object] = []
    for answer in answers:
        if answer == (401, NOT_AUTHORIZED):
            refused += 1
        elif answer == (429, TOO_MANY_REQUESTS):
            throttled += 1
        else:
            others.append(answer)
    assert (refused, throttled, others) == (10, 30, [])
    # The tokens were compared by secrets.compare_digest (rule 3), made slow here.
    assert slow_token_check.calls >= WRONG_CODE_LIMIT


def test_ac6_each_app_keeps_its_own_refusals(
    registry: RoomRegistry, dist_dir: Path
) -> None:
    first_app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)
    second_app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)
    with TestClient(first_app) as first, TestClient(second_app) as second:
        refuse(first, WRONG_CODE_LIMIT)
        first_answer = first.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))
        second_answer = second.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert first_answer.status_code == 429
    assert second_answer.status_code == 200, second_answer.text


def test_ac6_ops_refusals_do_not_throttle_the_room_sockets(
    registry: RoomRegistry, ops_client: TestClient, fx01_grid: Grid
) -> None:
    code = registry.register_room(fx01_grid)
    refuse(ops_client, WRONG_CODE_LIMIT)

    with ops_client.websocket_connect(socket_url(code)) as websocket:
        websocket.send_text(Join(nickname="Ana", resume_token=None).model_dump_json())
        first = parse_server_message(receive_text_or_fail(websocket))

    assert isinstance(first, Snapshot), first


def test_ac6_wrong_room_codes_do_not_throttle_the_ops_api(
    ops_client: TestClient,
) -> None:
    for _ in range(WRONG_CODE_LIMIT):
        with ops_client.websocket_connect(socket_url(UNKNOWN_ROOM)) as websocket:
            assert close_code_of_next_read(websocket) == ROOM_NOT_FOUND_CLOSE_CODE
    with ops_client.websocket_connect(socket_url(UNKNOWN_ROOM)) as websocket:
        assert close_code_of_next_read(websocket) == THROTTLED_CLOSE_CODE

    response = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text


# ---- AC-6: the operator pages off, and /ops ------------------------------------------


# The replay path names a room that exists (`OFF_ROOM`, registered by `off_room`).
OFF_ROOM = "OFF234"
OFF_PATHS = [
    pytest.param(DASHBOARD_PATH, id="dashboard"),
    pytest.param(f"{DASHBOARD_PATH}?days=30", id="dashboard-30-days"),
    # A `days` that the pages on would refuse with 422.
    pytest.param(f"{DASHBOARD_PATH}?days=2", id="dashboard-2-days"),
    pytest.param(edits_path(OFF_ROOM), id="replay"),
    pytest.param(OPS_PAGE_PATH, id="ops-page"),
]
# Every path of the ops API, and the edge cases' `/api/ops`, `/api/ops/` and
# `/api/ops/xyz`.
OFF_API_PATHS = [
    pytest.param(DASHBOARD_PATH, id="dashboard"),
    pytest.param(edits_path(OFF_ROOM), id="replay"),
    pytest.param("/api/ops", id="api-ops"),
    pytest.param("/api/ops/", id="api-ops-slash"),
    pytest.param("/api/ops/xyz", id="api-ops-xyz"),
]
METHODS = ["GET", "POST", "DELETE"]


@pytest.fixture
def off_room(registry: RoomRegistry, fx01_grid: Grid) -> str:
    """A room of the registry, with a join in its log, for the replay path."""
    log = Log(registry.clock())
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    seed_room(registry, new_room(OFF_ROOM, fx01_grid, registry.clock()), log.entries)
    return OFF_ROOM


@pytest.mark.usefixtures("off_room")
@pytest.mark.parametrize("path", OFF_PATHS)
def test_ac6_with_the_pages_off_the_ops_paths_answer_as_an_unknown_path(
    off_client: TestClient, path: str
) -> None:
    unknown = off_client.get(UNKNOWN_PATH)

    response = off_client.get(path, headers=bearer(OPS_TOKEN))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert "cache-control" not in response.headers
    assert answer_of(response) == answer_of(unknown)


@pytest.mark.usefixtures("off_room")
@pytest.mark.parametrize("path", OFF_PATHS)
def test_ac6_with_an_empty_variable_the_pages_are_off(
    registry: RoomRegistry,
    dist_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, "")
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with TestClient(app) as client:
        unknown = client.get(UNKNOWN_PATH)
        response = client.get(path, headers=bearer(OPS_TOKEN))

    assert response.status_code == 404
    assert answer_of(response) == answer_of(unknown)


@pytest.mark.usefixtures("off_room")
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("path", OFF_API_PATHS)
def test_ac6_with_the_pages_off_every_method_answers_as_on_an_unknown_api_path(
    off_client: TestClient, path: str, method: str
) -> None:
    unknown = off_client.request(method, UNKNOWN_API_PATH, headers=bearer(OPS_TOKEN))

    response = off_client.request(method, path, headers=bearer(OPS_TOKEN))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert "cache-control" not in response.headers
    assert answer_of(response) == answer_of(unknown)


def test_ac6_with_the_pages_off_wrong_tokens_are_not_refusals(
    off_client: TestClient,
) -> None:
    # Rule 1: none of the other rules applies, so nothing is counted or throttled.
    for _ in range(WRONG_CODE_LIMIT + 1):
        response = off_client.get(DASHBOARD_PATH, headers=bearer("wrong"))
        assert response.status_code == 404
        assert "www-authenticate" not in response.headers


# ---- AC-6: other requests under /api/ops/ while the pages are on ---------------------


UNKNOWN_OPS_PATHS = [
    pytest.param("/api/ops/xyz", id="xyz"),
    pytest.param(f"{DASHBOARD_PATH}/", id="dashboard-slash"),
]
WITH_AND_WITHOUT_THE_TOKEN = [
    pytest.param({}, id="no-token"),
    pytest.param(bearer(OPS_TOKEN), id="the-token"),
]


@pytest.mark.parametrize("headers", WITH_AND_WITHOUT_THE_TOKEN)
@pytest.mark.parametrize("path", UNKNOWN_OPS_PATHS)
def test_ac6_with_the_pages_on_an_unknown_ops_path_gets_a_plain_404_with_no_store(
    ops_client: TestClient, path: str, headers: dict[str, str]
) -> None:
    response = ops_client.get(path, headers=headers)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert response.headers.get("cache-control") == NO_STORE
    assert "www-authenticate" not in response.headers


@pytest.mark.parametrize("headers", WITH_AND_WITHOUT_THE_TOKEN)
def test_ac6_with_the_pages_on_post_on_the_dashboard_gets_fastapis_405_with_no_store(
    ops_client: TestClient, headers: dict[str, str]
) -> None:
    response = ops_client.post(DASHBOARD_PATH, headers=headers)

    assert response.status_code == 405
    assert response.json() == METHOD_NOT_ALLOWED
    assert response.headers.get("cache-control") == NO_STORE
    assert "www-authenticate" not in response.headers


def test_ac6_with_the_pages_on_other_ops_requests_are_not_counted(
    ops_client: TestClient,
) -> None:
    # Ten of each, all without a token: not one of the two routes, so no refusal.
    for _ in range(WRONG_CODE_LIMIT):
        assert ops_client.get("/api/ops/xyz").status_code == 404
        assert ops_client.get(f"{DASHBOARD_PATH}/").status_code == 404
        assert ops_client.post(DASHBOARD_PATH).status_code == 405

    response = ops_client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text


def test_ac6_with_the_pages_on_get_ops_answers_200_with_index_html(
    ops_client: TestClient, dist_dir: Path
) -> None:
    response = ops_client.get(OPS_PAGE_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.content == (dist_dir / "index.html").read_bytes()


def test_ac6_with_the_pages_on_get_ops_needs_no_token(ops_client: TestClient) -> None:
    # The page asks for the token itself (AC-7); the route serves it to anyone.
    refuse(ops_client, WRONG_CODE_LIMIT)

    response = ops_client.get(OPS_PAGE_PATH)

    assert response.status_code == 200


def test_ac6_with_the_pages_on_get_ops_answers_503_when_the_client_is_not_built(
    registry: RoomRegistry, tmp_path: Path
) -> None:
    empty_dist = tmp_path / "empty-dist"
    empty_dist.mkdir()
    app = create_app(rooms=registry, dist_dir=empty_dist, operator_token=OPS_TOKEN)
    with TestClient(app) as client:
        catalogue_answer = client.get("/")
        ops_answer = client.get(OPS_PAGE_PATH)

    assert catalogue_answer.status_code == 503
    assert ops_answer.status_code == 503
    assert ops_answer.content == catalogue_answer.content
