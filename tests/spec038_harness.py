"""Shared setup of the tests of spec 038: privacy and operations.

This module is not a test file: pytest does not collect it. The tests of spec 038
are in `tests/test_spec_038_*.py`, one file per criterion group:

- `test_spec_038_ac01_ac02_privacy_in_the_browser.py`: AC-1 and AC-2, a probe
  browser on a live server with a file database.
- `test_spec_038_ac03_production_logs.py`: AC-3, `python -m nock` in a subprocess.
- `test_spec_038_ac04_deletion_leaves_no_copy.py`: AC-4, the bytes of the database
  files once a room expired.
- `test_spec_038_ac05_dashboard_figures.py`: AC-5, `dashboard_figures`.
- `test_spec_038_ac06_ops_api.py`: AC-6, the ops API and `/ops` over HTTP.
- `test_spec_038_ac07_ops_page.py`: AC-7, the ops page.
- `test_spec_038_ac08_room_edits.py`: AC-8, `room_edits` and the replay route.
- `test_spec_038_ac09_replay_page.py`: AC-9, the replay on the ops page.
- `test_spec_038_ac10_operator_token.py`: AC-10, `NOCK_OPERATOR_TOKEN`.
- `test_spec_038_ac11_relay_time.py`: AC-11, `relay_ms`. It measures durations (a
  store blocked for 300 ms against a bound of 250 ms), so it runs in the serial
  pass (`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`).

This module holds what more than one of those files uses: the values of the
spec's "Test harness" (`OPS_TOKEN`, `DAY`, `LIFE`), the paths of the ops API, the
hand-made room logs (`Log`), the bytes of the database files, the live server
with a file database, the ops page helpers and the dashboard figures of AC-5.
What only one file uses stays in that file, next to its tests.

The names that this spec adds (`nock.operations`, `nock.settings`, the
`operator_token` of `create_app`, `LogEntry.relay_ms`) are imported or used inside
the functions that need them, never at the top of a module: until they exist,
each test fails on the name it needs, and no file fails to load.

Nicknames: the server stores them in capitals (spec 012 decision 12), so the
hand-made logs hold `ANA` and `BOB`, and a page shows them through spec 040's
`displayNickname` (`Ana`).
"""

from __future__ import annotations

import contextlib
import json
import re
import socket
import threading
import time
from collections.abc import Generator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Locator, Page, Route, expect

from nock.catalogue import Catalogue
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellRef,
    CellTarget,
    ChatMessage,
    CheckResult,
    GridSolved,
    LeaveReason,
    LetterChanged,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    RevealBudget,
    RevealResult,
)
from nock.room import LogEntry, RoomState, SeqEvent
from nock.server import WEB_DIST_DIR, create_app, server_config
from nock.store import RoomStore
from spec032_harness import DAY as DAY
from spec032_harness import LIFE as LIFE
from spec036_harness import OPERATOR_TOKEN_VARIABLE as OPERATOR_TOKEN_VARIABLE

if TYPE_CHECKING:
    from nock.operations import DashboardFigures

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

# ---- Values of the spec --------------------------------------------------------------

# The operator token of the "Test harness": 44 characters of the allowed set.
OPS_TOKEN = "Ops-" + "x" * 40
OPS_TOKEN_KEY = "nock.ops_token"  # the page's sessionStorage key

DASHBOARD_PATH = "/api/ops/dashboard"
OPS_PAGE_PATH = "/ops"

NOT_FOUND = {"detail": "Not Found"}
NOT_AUTHORIZED = {"detail": "Not authorized"}
TOO_MANY_REQUESTS = {"detail": "Too Many Requests"}

WRONG_CODE_LIMIT = 10  # spec 011's constant, which the ops API's throttle uses
WRONG_CODE_WINDOW_SECONDS = 60.0

# The eight answers of FX-01 (specs/_reference.md).
FX01_ANSWERS = ("TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST")
FX01_LETTER_CELLS = 18

# ---- Values of the test harness ------------------------------------------------------

DATABASE_FILE_NAME = "nock.sqlite3"
MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"
SERVER_START_SECONDS = 10.0
PARIS = "Europe/Paris"
OPS_TIMEOUT_MS = 10_000
KEY_PAUSE_MS = 60  # spec 037's harness: 60 ms or more between keys


# ---- The ops API ---------------------------------------------------------------------


def edits_path(code: str) -> str:
    """The path of a room's replay, `GET /api/ops/rooms/<code>/edits`."""
    return f"/api/ops/rooms/{code}/edits"


def bearer(token: str) -> dict[str, str]:
    """The header `Authorization: Bearer <token>`."""
    return {"Authorization": f"Bearer {token}"}


def utc(timestamp: float) -> datetime:
    """A clock time as an aware datetime in UTC."""
    return datetime.fromtimestamp(timestamp, UTC)


# ---- Hand-made room logs -------------------------------------------------------------


def player_view(
    player_id: str, nickname: str, colour: int, *, is_host: bool = False
) -> PlayerView:
    """The view of an active player with no selection."""
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=PlayerState.ACTIVE,
        is_host=is_host,
        muted=False,
        selection=None,
    )


def log_entry(
    at: float,
    event: SeqEvent,
    *,
    resume_token: str | None = None,
    undo: bool = False,
    relay_ms: int | None = None,
) -> LogEntry:
    """One logged entry. `relay_ms` is passed only when it is not None.

    So an entry without a relay time can be built before spec 038 adds the
    field, and one with a relay time fails on the missing field until then.
    """
    if relay_ms is None:
        return LogEntry(at=at, event=event, resume_token=resume_token, undo=undo)
    return LogEntry(
        at=at, event=event, resume_token=resume_token, undo=undo, relay_ms=relay_ms
    )


class Log:
    """A room's log written by hand, in seq order.

    Each method appends one entry and returns it. The entries are numbered from
    1, and each one is one second after the previous one, from `start`.
    """

    def __init__(self, start: float) -> None:
        self.entries: list[LogEntry] = []
        self.next_at = start

    def _add(
        self,
        event: SeqEvent,
        *,
        resume_token: str | None = None,
        undo: bool = False,
        relay_ms: int | None = None,
    ) -> LogEntry:
        entry = log_entry(
            self.next_at,
            event,
            resume_token=resume_token,
            undo=undo,
            relay_ms=relay_ms,
        )
        self.entries.append(entry)
        self.next_at += 1.0
        return entry

    def next_seq(self) -> int:
        """The seq of the next entry."""
        return len(self.entries) + 1

    def join(
        self,
        player_id: str,
        nickname: str,
        colour: int,
        token: str,
        *,
        relay_ms: int | None = None,
    ) -> LogEntry:
        """A `player_joined`, logged with the player's resume token."""
        is_host = colour == 0
        view = player_view(player_id, nickname, colour, is_host=is_host)
        event = PlayerJoined(seq=self.next_seq(), player=view)
        return self._add(event, resume_token=token, relay_ms=relay_ms)

    def letter(
        self,
        player_id: str,
        row: int,
        column: int,
        letter: str | None,
        *,
        pencil: bool = False,
        undo: bool = False,
        relay_ms: int | None = None,
    ) -> LogEntry:
        """A `letter_changed`: a letter written, or erased when `letter` is None."""
        event = LetterChanged(
            seq=self.next_seq(),
            row=row,
            column=column,
            letter=letter,
            pencil=pencil,
            player_id=player_id,
        )
        return self._add(event, undo=undo, relay_ms=relay_ms)

    def presence(self, player_id: str, state: PlayerState) -> LogEntry:
        """A `player_state_changed`."""
        event = PlayerStateChanged(
            seq=self.next_seq(), player_id=player_id, state=state
        )
        return self._add(event)

    def leave(self, player_id: str, reason: LeaveReason) -> LogEntry:
        """A `player_left`."""
        event = PlayerLeft(seq=self.next_seq(), player_id=player_id, reason=reason)
        return self._add(event)

    def chat(
        self, player_id: str, text: str, *, relay_ms: int | None = None
    ) -> LogEntry:
        """A `chat_message`."""
        event = ChatMessage(seq=self.next_seq(), player_id=player_id, text=text)
        return self._add(event, relay_ms=relay_ms)

    def check(self, player_id: str, row: int, column: int) -> LogEntry:
        """The `check_result` of a check of one letter that finds it right."""
        event = CheckResult(
            seq=self.next_seq(),
            player_id=player_id,
            target=CellTarget(row=row, column=column),
            correct=(CellRef(row=row, column=column),),
            wrong=(),
        )
        return self._add(event)

    def reveal(self, player_id: str, row: int, column: int) -> LogEntry:
        """The `reveal_result` of a reveal of one letter (4 letters, 1 word left)."""
        event = RevealResult(
            seq=self.next_seq(),
            player_id=player_id,
            target=CellTarget(row=row, column=column),
            reveal_budget=RevealBudget(letters=4, words=1),
        )
        return self._add(event)

    def lock(self, row: int, column: int, letter: str, *, revealed: bool) -> LogEntry:
        """A `cell_locked`: by a check, or by a reveal when `revealed` is True."""
        event = CellLocked(
            seq=self.next_seq(),
            row=row,
            column=column,
            letter=letter,
            revealed=revealed,
        )
        return self._add(event)

    def solved(self, elapsed_ms: int) -> LogEntry:
        """A `grid_solved`."""
        event = GridSolved(seq=self.next_seq(), elapsed_ms=elapsed_ms)
        return self._add(event)


def seed_room(
    registry: RoomRegistry, state: RoomState, entries: Sequence[LogEntry]
) -> None:
    """Register `state` (`add_room`), then append `entries` to the registry's store."""
    registry.add_room(state)
    if len(entries) > 0:
        registry.store.append(state.code, entries)


# ---- The database files --------------------------------------------------------------


def database_bytes(database_path: Path) -> bytes:
    """The bytes of the database file, then of its WAL file when it exists.

    Read as the spec's "Test harness" says: `nock.sqlite3` and, when it exists,
    `nock.sqlite3-wal`.
    """
    data = database_path.read_bytes()
    wal_path = database_path.with_name(database_path.name + "-wal")
    # No WAL file, or one just removed: then only the main file counts.
    with contextlib.suppress(FileNotFoundError):
        data += wal_path.read_bytes()
    return data


def strings_in(data: bytes, texts: Sequence[str]) -> list[str]:
    """The texts of `texts` whose UTF-8 bytes occur in `data`, in the given order."""
    found: list[str] = []
    for text in texts:
        if text.encode("utf-8") in data:
            found.append(text)
    return found


# ---- French texts --------------------------------------------------------------------

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_]+)\}")


def load_fr() -> dict[str, str]:
    """The French messages of the web client."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def fill(template: str, values: dict[str, str]) -> str:
    """A `fr.json` value with each `{name}` replaced, as spec 040's `t` does.

    A placeholder with no value is left as written.
    """
    filled = template
    for match in PLACEHOLDER.finditer(template):
        name = match.group(1)
        if name in values:
            filled = filled.replace(match.group(0), values[name])
    return filled


def shown_text(text: str) -> str:
    """A text as a reader sees it: runs of ASCII spaces and line breaks made one.

    Other spaces, such as U+00A0 or U+202F, are kept, so they never pass for a
    plain space.
    """
    return re.sub(r"[ \t\r\n\f]+", " ", text).strip()


# ---- The live server with a file database (AC-1, AC-2, AC-7, AC-9) ------------------


def _bind_free_port() -> socket.socket:
    """A socket bound to a free port of 127.0.0.1."""
    listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listening_socket.bind(("127.0.0.1", 0))
    return listening_socket


@contextlib.contextmanager
def serving(app: FastAPI) -> Generator[str]:
    """Serve `app` on a free port of 127.0.0.1, as spec 040's `live_server` does.

    The server is `uvicorn.Server(server_config(app, log_level="warning"))`, run in
    a thread. Yields the base URL; the server stops at the end.
    """
    listening_socket = _bind_free_port()
    port = listening_socket.getsockname()[1]
    server = uvicorn.Server(server_config(app, log_level="warning"))
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listening_socket]}, daemon=True
    )
    thread.start()
    try:
        deadline = time.monotonic() + SERVER_START_SECONDS
        while not server.started and time.monotonic() < deadline:
            if not thread.is_alive():
                break
            time.sleep(0.02)
        if not server.started:
            pytest.fail("the live server with the operator token did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=SERVER_START_SECONDS)
        listening_socket.close()


class OpsServer(NamedTuple):
    """The live server of the "Test harness": its URL, registry, store and file."""

    base_url: str
    registry: RoomRegistry
    store: RoomStore
    database_path: Path


@contextlib.contextmanager
def ops_live_server(directory: Path, catalogue: Catalogue) -> Generator[OpsServer]:
    """Run the app of the spec's "Test harness" and yield it.

    The app is `create_app(rooms=RoomRegistry(store=RoomStore(<directory> /
    "nock.sqlite3")), dist_dir=WEB_DIST_DIR, catalogue=catalogue,
    operator_token=OPS_TOKEN)`, served by `serving`. Fails (does not skip) when
    the client is not built. At the end the server stops, then the registry and
    the store are closed; a test may close them earlier.
    """
    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)
    database_path = directory / DATABASE_FILE_NAME
    store = RoomStore(database_path)
    registry = RoomRegistry(store=store)
    try:
        app = create_app(
            rooms=registry,
            dist_dir=WEB_DIST_DIR,
            catalogue=catalogue,
            operator_token=OPS_TOKEN,
        )
        with serving(app) as base_url:
            yield OpsServer(
                base_url=base_url,
                registry=registry,
                store=store,
                database_path=database_path,
            )
    finally:
        registry.close()
        store.close()


# ---- The room page -------------------------------------------------------------------


def cell_at(page: Page, row: int, column: int) -> Locator:
    """One cell of the room page's grid."""
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def type_across(page: Page, row: int, column: int, keys: str) -> None:
    """Tap the cell (row, column), then press each key, 60 ms apart."""
    cell_at(page, row, column).click()
    for key in keys:
        page.keyboard.press(key)
        page.wait_for_timeout(KEY_PAUSE_MS)


def letters_of(state: RoomState | None) -> dict[tuple[int, int], str]:
    """The letters a room holds, by (row, column)."""
    assert state is not None, "the room is unknown"
    letters: dict[tuple[int, int], str] = {}
    for cell in state.cells:
        if cell.letter is not None:
            letters[(cell.row, cell.column)] = cell.letter
    return letters


def wait_for_room_letters(
    registry: RoomRegistry, code: str, expected: dict[tuple[int, int], str]
) -> None:
    """Wait up to 10 seconds until the room holds exactly the `expected` letters."""
    deadline = time.monotonic() + SERVER_START_SECONDS
    while letters_of(registry.room_state(code)) != expected:
        if time.monotonic() >= deadline:
            letters = letters_of(registry.room_state(code))
            pytest.fail(f"the room holds {letters}, not {expected}")
        time.sleep(0.05)


# ---- The ops page --------------------------------------------------------------------


def ops_page(page: Page) -> Locator:
    """The root of the ops page."""
    return page.get_by_test_id("ops-page")


def open_ops_page(page: Page, base_url: str) -> None:
    """Open `<base>/ops` and wait for the ops page."""
    page.goto(f"{base_url}{OPS_PAGE_PATH}")
    expect(ops_page(page)).to_be_visible(timeout=OPS_TIMEOUT_MS)


def expect_ops_state(page: Page, state: str) -> None:
    """Wait until the ops page's `data-state` is `state`."""
    expect(ops_page(page)).to_have_attribute(
        "data-state", state, timeout=OPS_TIMEOUT_MS
    )


def give_token(page: Page, token: str) -> None:
    """Type `token` in the token form and submit it with its button."""
    page.get_by_test_id("ops-token-input").fill(token)
    page.get_by_test_id("ops-token-submit").click()


def open_dashboard(page: Page, base_url: str, token: str = OPS_TOKEN) -> None:
    """Open the ops page, give `token` and wait until the page is `ready`."""
    open_ops_page(page, base_url)
    expect_ops_state(page, "locked")
    give_token(page, token)
    expect_ops_state(page, "ready")


def texts_of(locator: Locator) -> list[str]:
    """The text of each element of `locator`, as `shown_text` reads it."""
    raw_texts = locator.evaluate_all(
        "elements => elements.map(element => element.textContent)"
    )
    texts: list[str] = []
    for raw_text in raw_texts:
        texts.append(shown_text(str(raw_text)))
    return texts


def attributes_of(locator: Locator, name: str) -> list[str | None]:
    """The value of the attribute `name` of each element of `locator`."""
    values = locator.evaluate_all(
        "(elements, name) => elements.map(element => element.getAttribute(name))",
        name,
    )
    found: list[str | None] = []
    for value in values:
        found.append(None if value is None else str(value))
    return found


# ---- The dashboard figures of AC-5 ---------------------------------------------------


def seven_day_figures(now: float) -> DashboardFigures:
    """AC-5's result for 7 days: the figures of R1, R2 and R3."""
    from nock.operations import DashboardFigures

    return DashboardFigures(
        days=7,
        since=utc(now - 7 * DAY),
        rooms_created=3,
        players_per_room=2.0,
        completion_rate=2 / 3,
        median_solving_ms=750_000.0,
        latency_median_ms=30.0,
        latency_p95_ms=50,
        disconnection_rate=0.5,
    )


def no_room_figures(now: float, days: int = 7) -> DashboardFigures:
    """AC-5's result with no room: 0 rooms and every other figure None."""
    from nock.operations import DashboardFigures

    return DashboardFigures(
        days=days,
        since=utc(now - days * DAY),
        rooms_created=0,
        players_per_room=None,
        completion_rate=None,
        median_solving_ms=None,
        latency_median_ms=None,
        latency_p95_ms=None,
        disconnection_rate=None,
    )


class DashboardRoute:
    """Answers the page's dashboard requests (`page.route`) and records their URLs.

    Each request gets the next answer of `answers`; once they are used up, the
    last one again. An answer is a status and a JSON body, or None for a network
    failure (`route.abort()`).
    """

    def __init__(self, answers: Sequence[tuple[int, str] | None]) -> None:
        self.answers = list(answers)
        self.urls: list[str] = []

    def handle(self, route: Route) -> None:
        """Record one request and answer it."""
        self.urls.append(route.request.url)
        index = min(len(self.urls), len(self.answers)) - 1
        answer = self.answers[index]
        if answer is None:
            route.abort()
            return
        status, body = answer
        route.fulfill(status=status, content_type="application/json", body=body)


def dashboard_answer(figures: DashboardFigures) -> tuple[int, str]:
    """A 200 answer whose body is `figures` as JSON."""
    return (200, figures.model_dump_json())
