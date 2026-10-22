"""Shared setup of the tests of spec 029: game history.

This module is not a test file: pytest does not collect it. The tests of spec 029
are in `tests/test_spec_029_*.py`, one file per criterion group:

- `test_spec_029_ac01_finished_rooms.py`: AC-1, `solved_at` and
  `solved_elapsed_ms` of the rules and of `replay`, the summary's `finished_at`
  and `elapsed_ms`, in Python and over `POST /api/rooms/summaries`, also for a
  room stored without the two fields.
- `test_spec_029_ac02_device_history.py`: AC-2 on the catalogue page, with the
  summaries route mocked: the records written to `nock.history` and the list.
- `test_spec_029_ac02_room_page_and_live.py`: AC-2 on the room page (a mocked
  socket and a mocked summaries route), and the live run of two players.
- `test_spec_029_ac03_account_history.py`: AC-3 over HTTP, the code reused, and
  `AccountStore.save_history` and `history`.
- `test_spec_029_ac03_account_pages.py`: AC-3 in browsers: the second device on
  the live server with accounts on, and the account's records merged with the
  device's on mocked routes.
- `test_spec_029_ac04_replay.py`: AC-4 on the live server.
- `test_spec_029_ac05_a11y_and_layout.py`: AC-5 on mocked routes.
- `test_spec_029_ac06_erasure.py`: AC-6 over HTTP, and Ana's page on mocked
  routes.
- `test_spec_029_ac07_after_deletion.py`: AC-7 over HTTP with a fake clock, and
  the delete hook of `RoomRegistry`.

This module holds what more than one of those files uses: plays of FX-01 with the
rules (every entry kept, so that a test can read the `grid_solved` entry), the
values of the spec's "Test harness" (`SOLVED_XYZ`, `OPEN_ABC` and the records of
AC-2), the account helpers of the HTTP criteria, and the catalogue page with its
history list. What only one file uses stays in that file.

The names that this spec adds (`HistoryRecord`, `save_history`, `history`,
`accounts_of_room`, `set_delete_hook`, `solved_at`, `solved_elapsed_ms`, the
summary's `finished_at` and `elapsed_ms`) are reached inside the functions that
need them, never imported at the top of a module: until they exist, each test
fails on the name it needs, and no file fails to load.

Nicknames: the server stores them in capitals (spec 012 decision 12), so a room
played with the rules names its players `ANA`, `BOB`... The mocked summaries and
records hold the nicknames that the spec's "Test harness" gives them (`Bob`,
`Ana`, `Cy`), and a page shows each one through spec 040's `displayNickname`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from playwright.sync_api import Browser, BrowserContext, Locator, Page, Route, expect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.protocol import EditLetter, GridSolved, Join
from nock.room import (
    LogEntry,
    RoomConfig,
    RoomState,
    handle_message,
    join_room,
    new_room,
)
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec026_harness import FIRST_17, LAST_CELL, SOLUTION
from spec032_harness import NO_TICK_CONFIG, PARIS, SummariesRoute, summary_json
from spec033_harness import (
    AccountApp,
    link_and_sign_in,
    room_key,
    set_cookie_of,
    with_session,
)

HISTORY_PATH = "/api/account/history"
HISTORY_KEY = "nock.history"
HISTORY_LIMIT = 100
WAIT_TIMEOUT_MS = 10_000
QUIET_MS = 500  # "shows nothing": nothing within this pause

# ---- Plays of FX-01 with the rules -----------------------------------------------

SOLVE_SECONDS = 754.0  # spec 026 AC-1: the last letter at NOW + 754.0
SOLVE_MS = 754_000


class Player(NamedTuple):
    """A player of a play: the nickname typed, the player id and the token."""

    nickname: str
    player_id: str
    token: str


class Play(NamedTuple):
    """A FX-01 room played with the rules: its first state, its last, its log."""

    initial: RoomState
    state: RoomState
    log: tuple[LogEntry, ...]


def play_fx01(
    grid: Grid,
    code: str,
    players: list[Player],
    *,
    start: float,
    solved_after: float | None = SOLVE_SECONDS,
    grid_number: int | None = 1,
    config: RoomConfig = NO_TICK_CONFIG,
) -> Play:
    """Play a FX-01 room with `join_room` and `handle_message`, keeping every entry.

    The room is `new_room(code, grid, start, grid_number)`. Every player joins at
    `start`, in the order given. When `solved_after` is not None, the first player
    writes the 17 right letters other than (4, 4) at `start`, then the last player
    writes `T` at (4, 4) at `start + solved_after`, as spec 026 AC-1 does, and the
    room is solved. When it is None, the room has the joins only.
    """
    initial = new_room(code, grid, start, grid_number=grid_number)
    state = initial
    log: list[LogEntry] = []
    for player in players:
        join = Join(nickname=player.nickname, resume_token=None)
        outcome = join_room(state, join, start, player.player_id, player.token, config)
        state = outcome.state
        log.extend(outcome.entries)
    if solved_after is None:
        return Play(initial, state, tuple(log))
    first_writer = players[0].player_id
    for position in FIRST_17:
        row, column = position
        edit = EditLetter(row=row, column=column, letter=SOLUTION[position])
        outcome = handle_message(state, first_writer, edit, start, config)
        assert outcome.reply == (), outcome.reply
        state = outcome.state
        log.extend(outcome.entries)
    last_row, last_column = LAST_CELL
    last_edit = EditLetter(row=last_row, column=last_column, letter="T")
    last_writer = players[-1].player_id
    outcome = handle_message(
        state, last_writer, last_edit, start + solved_after, config
    )
    assert outcome.reply == (), outcome.reply
    state = outcome.state
    log.extend(outcome.entries)
    assert state.solved is True
    return Play(initial, state, tuple(log))


def grid_solved_entry(play: Play) -> LogEntry:
    """The one `grid_solved` entry of a play."""
    found: list[LogEntry] = []
    for entry in play.log:
        if isinstance(entry.event, GridSolved):
            found.append(entry)
    assert len(found) == 1, found
    return found[0]


def solved_at_of(play: Play) -> float:
    """The `at` of the play's `grid_solved` entry: the room's date (spec 029)."""
    return grid_solved_entry(play).at


def elapsed_ms_of(play: Play) -> int:
    """The `elapsed_ms` of the play's `grid_solved` entry: its time taken."""
    event = grid_solved_entry(play).event
    assert isinstance(event, GridSolved), event
    return event.elapsed_ms


def parse_time(text: object) -> datetime:
    """A `finished_at` of a JSON answer, read as an aware datetime."""
    assert isinstance(text, str), text
    parsed = datetime.fromisoformat(text)
    assert parsed.tzinfo is not None, text
    return parsed


def with_parsed_time(record: object) -> dict[str, object]:
    """A JSON record or summary, with its `finished_at` read as a datetime."""
    assert isinstance(record, dict), record
    copied: dict[str, object] = dict(record)
    if copied.get("finished_at") is not None:
        copied["finished_at"] = parse_time(copied["finished_at"])
    return copied


def records_with_parsed_times(body: object) -> list[dict[str, object]]:
    """Each record of a JSON array, its `finished_at` read as a datetime."""
    assert isinstance(body, list), body
    records: list[dict[str, object]] = []
    for record in body:
        records.append(with_parsed_time(record))
    return records


# The two fields of this spec: a room stored before it has neither.
NEW_FIELDS = ("solved_at", "solved_elapsed_ms")


def without_new_fields(state: RoomState) -> RoomState:
    """The state as a room stored before this spec holds it: no two new fields."""
    data = json.loads(state.model_dump_json())
    for name in NEW_FIELDS:
        data.pop(name, None)
    return RoomState.model_validate_json(json.dumps(data))


def store_legacy_room(store: RoomStore, play: Play, clock: FakeClock) -> None:
    """Write a room as before this spec: its log, then its solved snapshot.

    The snapshot has `solved` True and neither `solved_at` nor
    `solved_elapsed_ms`; the log holds the play's `grid_solved` entry. The room is
    in the store only: the registry loads it when it is asked for.
    """
    store.create_room(play.initial, last_edit_at=clock())
    store.append(play.initial.code, play.log)
    legacy = without_new_fields(play.state)
    assert legacy.solved is True
    store.save_snapshot(legacy)


# ---- Accounts over HTTP ----------------------------------------------------------


def sign_in_from(app: AccountApp, email: str, code: str, token: str) -> str:
    """Ask a link from room `code` with `token`, use it; return the session value.

    The client's cookie jar is cleared afterwards, so that each later request
    names its session with `with_session`.
    """
    signed_in = link_and_sign_in(app, email, room_key(code, token))
    session = set_cookie_of(signed_in).value
    app.client.cookies.clear()
    return session


def account_id_of(app: AccountApp, session: str) -> str:
    """The id of the account of a session."""
    account = app.accounts.account_of_session(session, app.clock())
    assert account is not None, "the session has no account"
    return account.account_id


def ask_history(client: TestClient, session: str) -> Response:
    """`GET /api/account/history` with the session `session` and no other cookie."""
    client.cookies.clear()
    return client.get(HISTORY_PATH, headers=with_session(session))


def history_body(client: TestClient, session: str) -> list[dict[str, object]]:
    """The records that `GET /api/account/history` answers, `finished_at` parsed."""
    response = ask_history(client, session)
    assert response.status_code == 200, response.text
    return records_with_parsed_times(response.json())


def link_room(client: TestClient, session: str, code: str, token: str) -> None:
    """Link a member of a room to the session's account (`PUT /api/account/rooms`)."""
    client.cookies.clear()
    response = client.put(
        "/api/account/rooms",
        json=room_key(code, token),
        headers=with_session(session),
    )
    assert response.status_code == 204, response.text


# ---- The values of the "Test harness" (browser) ---------------------------------

XYZ = "XYZ789"
ABC = "ABC234"
OLD_CODE = "QQQQQQ"
XYZ_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
ABC_TOKEN = "q3Wm8xYo2vB4tY1zW9nR"
XYZ_FINISHED_AT = "2026-10-14T08:30:00Z"
OLD_FINISHED_AT = "2026-10-01T09:00:00Z"
OLD_ELAPSED_MS = 3_725_000  # 1 h 02 min 05 s


def solved_summary(
    code: str,
    grid_number: int | None,
    players: list[str],
    finished_at: str,
    elapsed_ms: int,
) -> dict[str, object]:
    """A solved room's summary as JSON, with this spec's two fields (5 by 5)."""
    summary = summary_json(code, grid_number, (5, 5), players, finished_at, True)
    summary["finished_at"] = finished_at
    summary["elapsed_ms"] = elapsed_ms
    return summary


def solved_xyz() -> dict[str, object]:
    """`SOLVED_XYZ`: XYZ789, grid 2, 5 by 5, Bob, Ana and Cy, 754,000 ms."""
    return solved_summary(XYZ, 2, ["Bob", "Ana", "Cy"], XYZ_FINISHED_AT, SOLVE_MS)


def open_abc() -> dict[str, object]:
    """`OPEN_ABC`: ABC234, grid 1, 5 by 5, Ana, not solved."""
    summary = summary_json(ABC, 1, (5, 5), ["Ana"], "2026-10-13T20:05:00Z", False)
    summary["finished_at"] = None
    summary["elapsed_ms"] = None
    return summary


def device_record(
    code: str,
    grid: int | None,
    finished_at: str,
    elapsed_ms: int,
    teammates: list[str],
    size: tuple[int, int] = (5, 5),
) -> dict[str, object]:
    """A record of `nock.history` as the spec writes it."""
    width, height = size
    return {
        "code": code,
        "grid": grid,
        "width": width,
        "height": height,
        "finished_at": finished_at,
        "elapsed_ms": elapsed_ms,
        "teammates": teammates,
    }


def xyz_record() -> dict[str, object]:
    """The record that AC-2's catalogue page writes for `SOLVED_XYZ`."""
    return device_record(XYZ, 2, XYZ_FINISHED_AT, SOLVE_MS, ["Bob", "Cy"])


def old_record() -> dict[str, object]:
    """AC-2's older record: QQQQQQ, no grid number, 1 h 02 min 05 s, no team-mate."""
    return device_record(OLD_CODE, None, OLD_FINISHED_AT, OLD_ELAPSED_MS, [])


def account_record(
    code: str,
    grid_number: int | None,
    finished_at: str,
    elapsed_ms: int,
    teammates: list[str],
) -> dict[str, object]:
    """A `HistoryRecord` as `GET /api/account/history` writes it (5 by 5)."""
    return {
        "code": code,
        "grid_number": grid_number,
        "width": 5,
        "height": 5,
        "finished_at": finished_at,
        "elapsed_ms": elapsed_ms,
        "teammates": teammates,
    }


def identity_value(token: str, nickname: str = "Ana", player_id: str = "p1") -> str:
    """A valid stored identity `nock.identity.<CODE>` (spec 012), nickname `Ana`."""
    return json.dumps(
        {"player_id": player_id, "resume_token": token, "nickname": nickname}
    )


def two_identities() -> dict[str, str]:
    """AC-2's storage: identities for XYZ789 and ABC234, nickname `Ana`."""
    return {
        f"nock.identity.{XYZ}": identity_value(XYZ_TOKEN),
        f"nock.identity.{ABC}": identity_value(ABC_TOKEN),
    }


def history_value(records: list[object]) -> str:
    """A `nock.history` value: the records as a JSON array."""
    return json.dumps(records)


# ---- Browser: pages, routes and storage -----------------------------------------

NewPage = Callable[[int, int], Page]


def paris_pages(browser: Browser) -> Iterator[NewPage]:
    """Yield `new_page(width, height)`: a page in its own context, in Paris time.

    Every context has `timezone_id="Europe/Paris"` (spec 029, "Test harness") and
    is closed afterwards.
    """
    contexts: list[BrowserContext] = []

    def make_page(width: int, height: int) -> Page:
        context = browser.new_context(
            viewport={"width": width, "height": height}, timezone_id=PARIS
        )
        contexts.append(context)
        return context.new_page()

    yield make_page
    for context in contexts:
        context.close()


def seed(page: Page, items: dict[str, str]) -> None:
    """Fill absent `localStorage` keys before the page's own scripts run.

    The script runs again on every navigation, so it never overwrites a value
    the client wrote since.
    """
    script = (
        f"const items = {json.dumps(items)};"
        "for (const [key, value] of Object.entries(items)) {"
        " if (localStorage.getItem(key) === null) {"
        " localStorage.setItem(key, value); } }"
    )
    page.context.add_init_script(script)


def read_key(page: Page, key: str) -> str | None:
    """The value of a `localStorage` key, None when it is absent."""
    value = page.evaluate("key => localStorage.getItem(key)", key)
    if value is None:
        return None
    assert isinstance(value, str), value
    return value


def stored_history(page: Page) -> object:
    """`nock.history` parsed, or None when it is absent."""
    raw = read_key(page, HISTORY_KEY)
    if raw is None:
        return None
    return json.loads(raw)


def wait_for_stored_history(page: Page, expected: object) -> None:
    """Wait until `nock.history` parses to `expected`; fail with its last value."""
    waited_ms = 0
    while stored_history(page) != expected:
        if waited_ms >= WAIT_TIMEOUT_MS:
            assert stored_history(page) == expected
        page.wait_for_timeout(50)
        waited_ms += 50


def open_catalogue(page: Page, base_url: str, summaries: SummariesRoute | None) -> None:
    """Route the summaries requests to `summaries` (if any), open `/`, wait for it.

    Args:
        page: A fresh page, its storage already seeded.
        base_url: The live server.
        summaries: The mocked summaries route; None leaves the route alone.
    """
    if summaries is not None:
        page.route("**/api/rooms/summaries", summaries.handle)
    page.goto(f"{base_url}/")
    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready", timeout=WAIT_TIMEOUT_MS
    )
    wait_for_fonts(page)


def history_section(page: Page) -> Locator:
    return page.get_by_test_id("history")


def history_items(page: Page) -> Locator:
    return history_section(page).get_by_test_id("history-item")


def history_item(page: Page, code: str) -> Locator:
    return history_section(page).locator(
        f'[data-testid="history-item"][data-code="{code}"]'
    )


def expect_history_count(page: Page, count: int) -> None:
    """Wait until the history list shows `count` items."""
    expect(history_items(page)).to_have_count(count, timeout=WAIT_TIMEOUT_MS)


def history_codes(page: Page) -> list[str]:
    """The `data-code` of each history item, in document order."""
    codes: list[str] = []
    for item in history_items(page).all():
        code = item.get_attribute("data-code")
        assert code is not None, "a history item has no data-code"
        codes.append(code)
    return codes


def fulfill_json(route: Route, status: int, body: object) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


class SignedInRoutes:
    """The account routes of a signed-in page, answered by `page.route`.

    `GET /api/account` answers signed in, `GET /api/account/rooms` `[]`, and
    `GET /api/account/history` the records given. The history requests are
    counted.
    """

    def __init__(self, records: list[object]) -> None:
        self.records = records
        self.history_requests = 0

    def install(self, page: Page) -> None:
        """Route the page's account requests to these answers."""
        page.route("**/api/account", self._account)
        page.route("**/api/account/rooms", self._rooms)
        page.route("**/api/account/history", self._history)

    def _account(self, route: Route) -> None:
        fulfill_json(route, 200, {"signed_in": True, "email": "ana.probe@example.org"})

    def _rooms(self, route: Route) -> None:
        fulfill_json(route, 200, [])

    def _history(self, route: Route) -> None:
        self.history_requests += 1
        fulfill_json(route, 200, self.records)


def wait_quietly(page: Page) -> None:
    """Give the page time to do something that must not happen."""
    page.wait_for_timeout(QUIET_MS)


def fail_unless(condition: bool, message: str) -> None:
    """Fail the test with `message` unless `condition` holds."""
    if not condition:
        pytest.fail(message)
