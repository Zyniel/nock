"""Shared setup of the tests of spec 032: room resume.

This module is not a test file: pytest does not collect it. The tests of spec 032
are in `tests/test_spec_032_*.py`, one file per criterion group:

- `test_spec_032_ac01_room_life.py`: AC-1 (`RoomStore`'s last edit time, `is_edit`,
  the room life of `RoomConfig`).
- `test_spec_032_ac02_expiry.py`: AC-2 in Python and over HTTP (`expire_rooms`,
  the lookups, the share tokens, the app's sweep).
- `test_spec_032_ac02_ac07_sockets.py`: AC-2 and AC-7 over the room socket with a
  fake clock. Its "within 1 second of real time" checks wait up to that bound
  for a change; they measure no duration, so the file runs in the parallel pass.
- `test_spec_032_ac03_restart.py`: AC-3 over the room socket, with spec 018's
  simulated restart.
- `test_spec_032_ac03_ac05_live_pages.py`: AC-3 and AC-5 in browsers on the live
  server.
- `test_spec_032_ac04_members_and_summaries.py`: AC-4 (past players, members, team
  names, summaries, `POST /api/rooms/summaries`).
- `test_spec_032_ac05_my_rooms.py`: AC-5 with the summaries route mocked.
- `test_spec_032_ac06_my_rooms_a11y_and_layout.py`: AC-6.
- `test_spec_032_ac07_seat_back.py`: AC-7's runs on the rules, the base run of
  which (`ana_wrote_t`, `ana_timed_out`, `seat_back`) is here.
- `test_spec_032_ac07_seat_back_edge_cases.py`: AC-7's edge cases on the same
  runs, and a seat back whose join carries a nickname that spec 012 refuses.
- `test_spec_032_ac07_page_after_the_seat_back.py`: AC-7's page run (a mocked
  socket, spec 019's authors view).

The names that spec 032 adds to `nock.room` (`PastPlayer`, `RoomKey`,
`RoomSummary`, `MAX_PAST_PLAYERS`, `is_edit`, `member_id`, `team_nicknames`,
`room_summary`) are reached as attributes of the module, `nock.room.PastPlayer`,
so that each test fails on the name it needs instead of the whole file failing to
import before they exist. For the same reason, a `RoomConfig` with one of the
fields this spec adds is built inside the test that needs it. The browser tests
import nothing that this spec adds: they answer the summaries route with plain
JSON (`summary_json`), whose form AC-4 checks against `RoomSummary`.

Times. `T0` is the `t0` of the criteria and the time where conftest's fake clock
starts, so a registry on that clock starts at `t0`. Python criteria call the rules
and the store with chosen times. A run of the rules (`Run`) keeps every entry it
logged, so that a test can replay the whole log from `new_room`.

The fixtures (`fx01_grid`, `dist_dir`, `catalogue`, `new_page`...) are defined in
each test file as thin wrappers: a fixture imported from here would be an unused
import for ruff.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from playwright.sync_api import Browser, BrowserContext, Locator, Page, Route, expect

import nock.room
from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClientMessage,
    EditLetter,
    ErrorCode,
    ErrorMessage,
    Join,
    LetterCellView,
    PlayerState,
    PlayerView,
    ServerMessage,
    Snapshot,
)
from nock.room import (
    CellState,
    LogEntry,
    Outcome,
    PlayerRecord,
    RoomConfig,
    RoomState,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    normalize_nickname,
    replay,
    tick,
)
from nock.store import RoomStore
from spec017_harness import FakeClock

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"

# ---- Times ---------------------------------------------------------------------

DAY = 86_400.0
LIFE = 30 * DAY  # 720 hours: the default of RoomConfig's four room lives
T0 = 1_000_000.0  # t0 of the criteria, where conftest's fake clock starts

# ---- Rooms, players and tokens -------------------------------------------------

CODE_A = "AAAAAA"
CODE_B = "BBBBBB"
UNKNOWN_CODE = "ZZZZZZ"
ANA = "p1"
BOB = "p2"
CY = "p3"
DAN = "p4"
TA = "token-of-ana-0001"
TB = "token-of-bob-0002"
TC = "token-of-cy-00003"
TD = "token-of-dan-0004"
NEW_PLAYER_ID = "pNEW"  # the `new_player_id` of a join that must not use it
NEW_TOKEN = "token-never-used-0000"  # the `new_resume_token` of that join
NOBODYS_TOKEN = "token-nobody-had-000"

# ---- Configurations ------------------------------------------------------------

# "No tick changes anything" (spec 032, "Test harness").
NO_TICK_CONFIG = RoomConfig(
    idle_after_seconds=1e9,
    host_handover_seconds=1e9,
    silence_timeout_seconds=1e9,
    resume_window_seconds=1e9,
)
# AC-7: the same, except `resume_window_seconds`, left at its default of 300.
SEAT_BACK_CONFIG = RoomConfig(
    idle_after_seconds=1e9, host_handover_seconds=1e9, silence_timeout_seconds=1e9
)
SOCKET_TICK_SECONDS = 0.05  # AC-7's WebSocket part: `tick_seconds=0.05`
SEAT_BACK_SOCKET_CONFIG = RoomConfig(
    idle_after_seconds=1e9,
    host_handover_seconds=1e9,
    silence_timeout_seconds=1e9,
    tick_seconds=SOCKET_TICK_SECONDS,
)


def sweeping_config() -> RoomConfig:
    """AC-2's WebSocket part: no tick changes anything, a sweep every 0.05 s.

    Built when a test needs it: `expiry_sweep_seconds` is a field this spec adds.
    """
    return RoomConfig(
        idle_after_seconds=1e9,
        host_handover_seconds=1e9,
        silence_timeout_seconds=1e9,
        resume_window_seconds=1e9,
        expiry_sweep_seconds=0.05,
    )


# ---- Fixture bodies ------------------------------------------------------------


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixtures)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """A `dist` directory with a minimal `index.html` (the `dist_dir` fixtures)."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def load_fr() -> dict[str, str]:
    """The French messages of the web client."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def utc(timestamp: float) -> datetime:
    """A clock time as the UTC datetime of a summary's `last_activity_at`."""
    return datetime.fromtimestamp(timestamp, UTC)


# ---- Plays of the rules --------------------------------------------------------


class Run:
    """A FX-01 room played with the rules, and every entry it logged.

    The room is `new_room(code, grid, T0, grid_number)`. Each step method applies
    one rule function to the current state, keeps its state and its entries, and
    returns its outcome.
    """

    def __init__(
        self,
        grid: Grid,
        code: str = CODE_A,
        grid_number: int | None = 1,
        config: RoomConfig = SEAT_BACK_CONFIG,
    ) -> None:
        self.initial: RoomState = new_room(code, grid, T0, grid_number=grid_number)
        self.state: RoomState = self.initial
        self.log: list[LogEntry] = []
        self.config = config

    def keep(self, outcome: Outcome) -> Outcome:
        """Keep a step: its state and its entries."""
        self.state = outcome.state
        self.log.extend(outcome.entries)
        return outcome

    def join(
        self,
        nickname: str,
        resume_token: str | None,
        now: float,
        new_player_id: str = NEW_PLAYER_ID,
        new_resume_token: str = NEW_TOKEN,
    ) -> Outcome:
        """Apply a join with `join_room`."""
        message = Join(nickname=nickname, resume_token=resume_token)
        outcome = join_room(
            self.state, message, now, new_player_id, new_resume_token, self.config
        )
        return self.keep(outcome)

    def join_new(self, nickname: str, player_id: str, token: str, now: float) -> None:
        """Join a new player, who has no resume token yet; the join must succeed."""
        outcome = self.join(nickname, None, now, player_id, token)
        assert snapshot_of(outcome).you == player_id

    def send(self, player_id: str, message: ClientMessage, now: float) -> Outcome:
        """Apply a message of a player with `handle_message`."""
        outcome = handle_message(self.state, player_id, message, now, self.config)
        return self.keep(outcome)

    def disconnect(self, player_id: str, now: float) -> Outcome:
        """Close the player's connection (`disconnect_player`)."""
        return self.keep(disconnect_player(self.state, player_id, now))

    def tick(self, now: float) -> Outcome:
        """Run one `tick`."""
        return self.keep(tick(self.state, now, self.config))

    def replayed(self) -> RoomState:
        """The room rebuilt from `new_room` by `replay` of every logged entry."""
        state = self.initial
        for entry in self.log:
            state = replay(state, entry)
        return state


def events_of(outcome: Outcome) -> list[object]:
    """The event of each entry of a step, in order."""
    events: list[object] = []
    for entry in outcome.entries:
        events.append(entry.event)
    return events


def snapshot_of(outcome: Outcome) -> Snapshot:
    """The one snapshot a successful join replies with."""
    assert len(outcome.reply) == 1, outcome.reply
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot), snapshot
    return snapshot


def error_code_of(reply: tuple[ServerMessage, ...]) -> ErrorCode:
    """The code of the one error a refused step replies with."""
    assert len(reply) == 1, reply
    error = reply[0]
    assert isinstance(error, ErrorMessage), error
    return error.code


def player_of(state: RoomState, player_id: str) -> PlayerRecord:
    """The record of a player of `players`."""
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id} in players")


def player_ids(state: RoomState) -> list[str]:
    """The ids of `players`, in order."""
    ids: list[str] = []
    for player in state.players:
        ids.append(player.player_id)
    return ids


def cell_of(state: RoomState, row: int, column: int) -> CellState:
    """The room's state of one letter cell."""
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


def snapshot_cell(snapshot: Snapshot, row: int, column: int) -> LetterCellView:
    """One letter cell of a snapshot's grid."""
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and (cell.row, cell.column) == (
            row,
            column,
        ):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column}) in the snapshot")


# ---- AC-7's base run -----------------------------------------------------------

LEFT_AT = T0 + 10  # Ana's connection closes
TIMED_OUT_AT = T0 + 311  # the tick that times her out
SEAT_BACK_AT = T0 + 400  # her join with TA
IN_THE_WINDOW_LIMIT = T0 + 310.5  # 300.5 s after she left: the join times her out


def view(
    player_id: str, nickname: str, colour: int, *, is_host: bool, muted: bool = False
) -> PlayerView:
    """The view of an active player with no selection."""
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=PlayerState.ACTIVE,
        is_host=is_host,
        muted=muted,
        selection=None,
    )


def past(
    player_id: str, token: str, nickname: str, colour: int, muted: bool = False
) -> object:
    """A `PastPlayer` record."""
    return nock.room.PastPlayer(
        player_id=player_id,
        resume_token=token,
        nickname=nickname,
        colour=colour,
        muted=muted,
    )


def anas_past_record() -> object:
    return past(ANA, TA, "ANA", 0)


def ana_wrote_t(grid: Grid) -> Run:
    """Ana, Bob and Cy join at t0, then Ana writes `T` at (1, 0): seq 4."""
    run = Run(grid)
    run.join_new("Ana", ANA, TA, T0)
    run.join_new("Bob", BOB, TB, T0)
    run.join_new("Cy", CY, TC, T0)
    run.send(ANA, EditLetter(row=1, column=0, letter="T"), T0)
    assert run.state.seq == 4
    return run


def ana_timed_out(grid: Grid) -> Run:
    """AC-7's base run: Ana leaves at t0 + 10, the tick of t0 + 311 times her out.

    The tick gives her `player_left` (seq 6) and Bob's `host_changed` (seq 7).
    """
    run = ana_wrote_t(grid)
    run.disconnect(ANA, LEFT_AT)
    run.tick(TIMED_OUT_AT)
    assert player_ids(run.state) == [BOB, CY]
    return run


def seat_back(
    run: Run, token: str = TA, now: float = SEAT_BACK_AT, nickname: str = "Autre"
) -> Outcome:
    """A join with a past player's token and another nickname, `Autre` by default."""
    return run.join(nickname, token, now)


def refused_by_spec_012(nickname: str) -> bool:
    """Whether spec 012's `normalize_nickname` refuses a nickname (its step 5)."""
    try:
        normalize_nickname(nickname)
    except ValueError:
        return True
    return False


# ---- Store files ---------------------------------------------------------------


@contextlib.contextmanager
def registry_on_file(
    path: Path, clock: FakeClock, config: RoomConfig
) -> Iterator[tuple[RoomRegistry, RoomStore]]:
    """Yield a registry on a store file and the store; close both afterwards."""
    store = RoomStore(path)
    registry = RoomRegistry(clock=clock, store=store, config=config)
    try:
        yield registry, store
    finally:
        registry.close()
        store.close()


# ---- HTTP ----------------------------------------------------------------------

SUMMARIES_PATH = "/api/rooms/summaries"


def summaries_request(keys: list[tuple[str, str]]) -> dict[str, object]:
    """The JSON body of `POST /api/rooms/summaries` for (code, token) pairs."""
    rooms: list[dict[str, str]] = []
    for code, token in keys:
        rooms.append({"code": code, "resume_token": token})
    return {"rooms": rooms}


def post_summaries(client: TestClient, keys: list[tuple[str, str]]) -> Response:
    """Send `POST /api/rooms/summaries` with one key per (code, token) pair."""
    return client.post(SUMMARIES_PATH, json=summaries_request(keys))


def summary_codes(body: object) -> list[str]:
    """The `code` of each summary of an answer, in order."""
    assert isinstance(body, list), body
    codes: list[str] = []
    for summary in body:
        assert isinstance(summary, dict), summary
        codes.append(summary["code"])
    return codes


# ---- Browser: "My rooms" -------------------------------------------------------

SUMMARIES_ROUTE = "**/api/rooms/summaries"
PARIS = "Europe/Paris"
XYZ = "XYZ789"
ABC = "ABC234"
XYZ_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
ABC_TOKEN = "q3Wm8xYo2vB4tY1zW9nR"
QUIET_MS = 500  # "sends no request": nothing within this pause
WAIT_TIMEOUT_MS = 10_000
# Spec 017's watcher: `window.__formSeen` turns true if the nickname form shows.
FORM_WATCHER = (
    "window.__formSeen = false;"
    "new MutationObserver(() => {"
    " if (document.querySelector('[data-testid=\"nickname-form\"]')) {"
    " window.__formSeen = true; } })"
    ".observe(document, { childList: true, subtree: true });"
)

NewPage = Callable[[int, int], Page]


def identity_value(token: str, player_id: str = ANA, nickname: str = "ANA") -> str:
    """A valid stored identity `nock.identity.<CODE>` (spec 012).

    Its nickname is in capitals, as the server sends it (spec 039).
    """
    return json.dumps(
        {"player_id": player_id, "resume_token": token, "nickname": nickname}
    )


def two_identities() -> dict[str, str]:
    """AC-5's storage: valid identities for XYZ789 and ABC234, a corrupt QQQQQQ."""
    return {
        f"nock.identity.{XYZ}": identity_value(XYZ_TOKEN),
        f"nock.identity.{ABC}": identity_value(ABC_TOKEN),
        "nock.identity.QQQQQQ": "not json",
    }


def summary_json(
    code: str,
    grid_number: int | None,
    size: tuple[int, int],
    players: list[str],
    last_activity_at: str,
    solved: bool,
) -> dict[str, object]:
    """One summary as `RoomSummary.model_dump(mode="json")` writes it.

    AC-4 checks that this is the form of a dumped `RoomSummary`.
    """
    width, height = size
    return {
        "code": code,
        "grid_number": grid_number,
        "width": width,
        "height": height,
        "players": players,
        "last_activity_at": last_activity_at,
        "solved": solved,
    }


def xyz_summary(players: list[str] | None = None) -> dict[str, object]:
    """AC-5's first summary: XYZ789, grid 2, 5 by 5, Ana and Bob, not solved."""
    shown = ["Ana", "Bob"] if players is None else players
    return summary_json(XYZ, 2, (5, 5), shown, "2026-10-14T08:30:00Z", False)


def abc_summary() -> dict[str, object]:
    """AC-5's second summary: ABC234, no grid number, 13 by 17, Ana, solved."""
    return summary_json(ABC, None, (13, 17), ["Ana"], "2026-10-13T20:05:00Z", True)


class SummariesRoute:
    """The answers of `POST /api/rooms/summaries` on a page, and its requests.

    Each request is answered with `answer(<its body>)` when `answer` is given,
    else with `body`, as JSON with `status`.
    """

    def __init__(
        self,
        body: object = None,
        status: int = 200,
        answer: Callable[[object], object] | None = None,
    ) -> None:
        self.body = body
        self.status = status
        self.answer = answer
        self.methods: list[str] = []
        self.bodies: list[object] = []  # each request's body, parsed

    def handle(self, route: Route) -> None:
        """Record one request of the page and answer it (`page.route`'s handler)."""
        request = route.request
        self.methods.append(request.method)
        parsed: object = None
        if request.post_data is not None:
            parsed = json.loads(request.post_data)
        self.bodies.append(parsed)
        answered = self.body
        if self.answer is not None:
            answered = self.answer(parsed)
        route.fulfill(
            status=self.status,
            content_type="application/json",
            body=json.dumps(answered),
        )


class HeldSummariesRoute:
    """A summaries route whose answers wait until the test releases them."""

    def __init__(self) -> None:
        self.routes: list[Route] = []

    def handle(self, route: Route) -> None:
        """Keep the request without answering it (`page.route`'s handler)."""
        self.routes.append(route)

    def release(self, body: object) -> None:
        """Answer every request kept so far with `body`, as JSON."""
        for route in self.routes:
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(body)
            )


def sent_keys(body: object) -> list[tuple[str, str]]:
    """The (code, token) pairs of a summaries request, in the order sent.

    The body must be `{"rooms": [{"code": ..., "resume_token": ...}, ...]}`, with
    no other key.
    """
    assert isinstance(body, dict), body
    assert list(body) == ["rooms"], body
    rooms = body["rooms"]
    assert isinstance(rooms, list), body
    keys: list[tuple[str, str]] = []
    for key in rooms:
        assert isinstance(key, dict), key
        assert sorted(key) == ["code", "resume_token"], key
        keys.append((key["code"], key["resume_token"]))
    return keys


def paris_page_factory(browser: Browser) -> Iterator[NewPage]:
    """Yield `new_page(width, height)`: a page in its own context, in Paris time.

    Every context has `timezone_id="Europe/Paris"` (spec 032, "Test harness") and
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


def seed_storage(page: Page, items: dict[str, str]) -> None:
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


def read_storage(page: Page, key: str) -> str | None:
    """The value of a `localStorage` key, None when it is absent."""
    value = page.evaluate("key => localStorage.getItem(key)", key)
    if value is None:
        return None
    assert isinstance(value, str), value
    return value


def open_catalogue(page: Page, base_url: str, route: object) -> None:
    """Route the summaries requests to `route`, open `/`, wait for the grids.

    Args:
        page: A fresh page, its storage already seeded.
        base_url: The live server.
        route: A `SummariesRoute` or a `HeldSummariesRoute`.
    """
    if isinstance(route, SummariesRoute | HeldSummariesRoute):
        page.route(SUMMARIES_ROUTE, route.handle)
    else:
        pytest.fail(f"not a summaries route: {route!r}")
    page.goto(f"{base_url}/")
    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready", timeout=WAIT_TIMEOUT_MS
    )
    wait_for_fonts(page)


def my_rooms(page: Page) -> Locator:
    return page.get_by_test_id("my-rooms")


def my_room_items(page: Page) -> Locator:
    return page.get_by_test_id("my-room")


def expect_my_rooms_ready(page: Page, count: int) -> None:
    """Wait until "My rooms" is `ready` with `count` items."""
    expect(my_rooms(page)).to_have_attribute(
        "data-state", "ready", timeout=WAIT_TIMEOUT_MS
    )
    expect(my_room_items(page)).to_have_count(count)


def open_two_summaries(page: Page, base_url: str) -> SummariesRoute:
    """Open `/` with AC-5's storage and its two summaries, in that order."""
    route = SummariesRoute(body=[xyz_summary(), abc_summary()])
    seed_storage(page, two_identities())
    open_catalogue(page, base_url, route)
    expect_my_rooms_ready(page, 2)
    return route
