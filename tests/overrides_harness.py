"""Shared setup of the tests of admin/overrides: the `/ops` overrides of the room lives.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_overrides_*.py`:

- `test_overrides_values.py`: AC-1 to AC-5, the settings routes `GET` and `PUT`.
- `test_overrides_dry_run.py`: AC-6 and AC-7, the dry run.
- `test_overrides_access.py`: AC-8, the token, the throttle, `no-store`, pages off.
- `test_overrides_storage.py`: AC-9 and AC-10, the table `overrides`.
- `test_overrides_applying.py`: AC-11 to AC-14, a save at work: expiry, the sweep,
  the log, the dashboard periods.
- `test_overrides_page_rows.py`: AC-15, AC-16 and AC-18, the card's rows.
- `test_overrides_page_question.py`: AC-17, the question before a shorter life.
- `test_overrides_page_states.py`: AC-19, the card's states.
- `test_overrides_page_keys.py`: AC-20, the keyboard, the scans, the phone.

Three kinds of app, whichever a criterion needs:

- `env_app`: an app given no registry, so it builds its own from the variables
  (`room_config_from_env`) and from `NOCK_DATABASE`. Its environment values are the
  variables'. The criteria that read `environment` and `source` use it: an app
  given a registry takes the registry's config for its environment values
  (`admin/overrides.md` rule 1), so a default registry is not a "variable unset".
- `registry_app`: an app given a registry (on the fake clock, on a file or in
  memory), whose config the test reads after a save.
- `ops_host_app`: `host_harness`'s app (a fake clock, a file database, sockets)
  with the operator token, for the criteria with an open socket.

The page tests run on `settings_server`: the real app on a live port, given no
registry, with `NOCK_DATABASE` a file or unset, so `durable` is true or false.

The card has no test id in the spec: the page tests find it by its heading, a
row by the number input named with the row's name, and the row as the nearest
ancestor of that input that holds the name, a source tag and no other input.
The text of a row reads, in the order of rule 11 and of the design, the name, the
effective value, the source, then the two buttons (`row_text`).
"""

from __future__ import annotations

import contextlib
import logging
import re
import sqlite3
import time
from collections.abc import Generator, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from playwright.sync_api import Locator, Page, Request, Route, expect

from host_harness import HostApp, host_app
from lifetime_harness import (
    ANONYMOUS,
    ANONYMOUS_SOLVED,
    CREATOR,
    CREATOR_SOLVED,
    HOUR,
    SWEEP_VARIABLE,
    T0,
    letter_entry,
    select_rows,
    variables_of,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import GridSolved, Ping, Pong
from nock.room import LogEntry, RoomConfig, new_room
from nock.server import WEB_DIST_DIR, create_app
from nock.store import RoomStore
from spec014_harness import Peer
from spec017_harness import FakeClock
from spec033_harness import DATABASE_FILE_NAME
from spec038_harness import (
    MISSING_BUILD_MESSAGE,
    OPS_TOKEN,
    bearer,
    serving,
    shown_text,
)
from spec042_harness import Box, box_of
from spec046_harness import fulfil_json
from spec048_harness import WAIT_TIMEOUT_MS
from spec048_ops_harness import expect_ops_state, open_ops, seed_ops_token

SETTINGS_PATH = "/api/ops/settings"
DRY_RUN_PATH = "/api/ops/settings/dry-run"
DASHBOARD_PATH = "/api/ops/dashboard"
NO_STORE = "no-store"
OVERRIDES_LOGGER = "nock.overrides"
DATABASE_VARIABLE = "NOCK_DATABASE"
CODE_C = "CCCCCC"
SCHEMA_VERSION = 2

OVERRIDES_TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS overrides "
    "(name TEXT PRIMARY KEY, value INTEGER NOT NULL)"
)


# ---- The five settings ----


class Setting(NamedTuple):
    """One setting of `admin/overrides.md` rule 1: its name, variable and bounds."""

    name: str
    variable: str
    unit: str
    minimum: int
    maximum: int
    default: int


SETTINGS = (
    Setting(CREATOR_SOLVED.field, CREATOR_SOLVED.variable, "hours", 24, 8760, 720),
    Setting(CREATOR.field, CREATOR.variable, "hours", 24, 8760, 720),
    Setting(ANONYMOUS_SOLVED.field, ANONYMOUS_SOLVED.variable, "hours", 24, 8760, 720),
    Setting(ANONYMOUS.field, ANONYMOUS.variable, "hours", 24, 8760, 720),
    Setting("expiry_sweep_minutes", SWEEP_VARIABLE, "minutes", 1, 1440, 60),
)
SETTING_NAMES = [setting.name for setting in SETTINGS]
LIFE_NAMES = SETTING_NAMES[:4]
SETTING_BY_NAME = {setting.name: setting for setting in SETTINGS}
INTERVAL = "expiry_sweep_minutes"


def expected_row(
    name: str,
    *,
    value: float | None = None,
    source: str = "default",
    environment: float | None = None,
    override: int | None = None,
) -> dict[str, object]:
    """The nine fields of a setting's row (`admin/overrides.md` rule 3).

    Args:
        name: The setting.
        value: The effective value; None: the default.
        source: `default`, `environment` or `override`.
        environment: The variable's value; None when the variable is unset.
        override: The saved override; None when there is none.
    """
    setting = SETTING_BY_NAME[name]
    return {
        "name": name,
        "unit": setting.unit,
        "min": setting.minimum,
        "max": setting.maximum,
        "default": setting.default,
        "environment": environment,
        "override": override,
        "value": setting.default if value is None else value,
        "source": source,
    }


def default_rows() -> list[dict[str, object]]:
    """The five rows of an app with no variable and no override."""
    rows: list[dict[str, object]] = []
    for name in SETTING_NAMES:
        rows.append(expected_row(name))
    return rows


def rows_of(response: Response) -> dict[str, dict[str, object]]:
    """The rows of a 200 answer of rule 3, by name, in the answer's order."""
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict), body
    assert set(body) == {"durable", "settings"}, body
    settings = body["settings"]
    assert isinstance(settings, list), body
    rows: dict[str, dict[str, object]] = {}
    for row in settings:
        assert isinstance(row, dict), row
        rows[str(row["name"])] = row
    return rows


def body_of(response: Response) -> dict[str, object]:
    """The JSON object of an answer."""
    body = response.json()
    assert isinstance(body, dict), body
    return body


# ---- The settings routes over HTTP ----


class OpsClient:
    """The ops routes of a `TestClient`, sent with the operator token."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def settings(self) -> Response:
        """`GET /api/ops/settings`."""
        return self.client.get(SETTINGS_PATH, headers=bearer(OPS_TOKEN))

    def put(self, name: str, value: object) -> Response:
        """`PUT /api/ops/settings` of one setting: a value, or None to reset."""
        return self.put_body({"name": name, "value": value})

    def put_body(self, body: Mapping[str, object]) -> Response:
        """`PUT /api/ops/settings` with a body written as it is."""
        return self.client.put(
            SETTINGS_PATH, json=dict(body), headers=bearer(OPS_TOKEN)
        )

    def dry_run(self, name: str, value: object) -> Response:
        """`POST /api/ops/settings/dry-run` of one setting."""
        return self.dry_run_body({"name": name, "value": value})

    def dry_run_body(self, body: Mapping[str, object]) -> Response:
        """`POST /api/ops/settings/dry-run` with a body written as it is."""
        return self.client.post(
            DRY_RUN_PATH, json=dict(body), headers=bearer(OPS_TOKEN)
        )

    def dashboard(self, query: str = "") -> Response:
        """`GET /api/ops/dashboard`, with a query such as `?days=7`."""
        return self.client.get(f"{DASHBOARD_PATH}{query}", headers=bearer(OPS_TOKEN))

    def row(self, name: str) -> dict[str, object]:
        """The row of one setting, from a `GET`."""
        return rows_of(self.settings())[name]


# ---- Apps ----


@contextlib.contextmanager
def env_app(
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    variables: Mapping[str, str] | None = None,
    *,
    database: bool = False,
) -> Generator[OpsClient]:
    """Run an app given no registry under only `variables`, and yield its ops client.

    Args:
        directory: A directory; the database file, when there is one, is in it.
        monkeypatch: Clears the variables the app reads, then sets `variables`.
        variables: The variables to set, by name.
        database: True: `NOCK_DATABASE` is the file `nock.sqlite3` of `directory`,
            which a second app of the test may open again; False: in memory.
    """
    given = {} if variables is None else dict(variables)
    variables_of(monkeypatch, given)
    if database:
        monkeypatch.setenv(DATABASE_VARIABLE, str(directory / DATABASE_FILE_NAME))
    app = create_app(dist_dir=directory, operator_token=OPS_TOKEN)
    with TestClient(app) as client:
        yield OpsClient(client)


class RegistryApp(NamedTuple):
    """An app given a registry: its client, its ops client, its registry and store."""

    client: TestClient
    ops: OpsClient
    registry: RoomRegistry
    store: RoomStore


@contextlib.contextmanager
def registry_app(
    directory: Path,
    *,
    clock: FakeClock | None = None,
    config: RoomConfig | None = None,
    database: Path | None = None,
    token: str | None = OPS_TOKEN,
) -> Generator[RegistryApp]:
    """Run an app given a new registry, in memory or on the `database` file.

    The registry and its store are closed on the way out, so the same file can be
    opened again by the next app of the test.

    Args:
        directory: The app's `dist_dir`; nothing is read there.
        clock: The registry's clock; None: the real one.
        config: The registry's config; None: the defaults.
        database: The store's file; None: in memory.
        token: The operator token given to `create_app`; None: the environment's,
            which the tests leave unset, so the operator pages are off.
    """
    store = RoomStore(":memory:" if database is None else database)
    registry = RoomRegistry(clock=clock, config=config, store=store)
    try:
        app = create_app(rooms=registry, dist_dir=directory, operator_token=token)
        with TestClient(app) as client:
            yield RegistryApp(client, OpsClient(client), registry, store)
    finally:
        registry.close()
        store.close()


class OpsHostApp(NamedTuple):
    """`host_harness`'s app, and its ops client."""

    app: HostApp
    ops: OpsClient


@contextlib.contextmanager
def ops_host_app(
    directory: Path,
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    config: RoomConfig,
    catalogue: Catalogue,
) -> Generator[OpsHostApp]:
    """The app of `host_app` (accounts off) with the operator token."""
    monkeypatch.setenv("NOCK_OPERATOR_TOKEN", OPS_TOKEN)
    with host_app(
        directory, clock, catalogue, monkeypatch, accounts_on=False, config=config
    ) as app:
        yield OpsHostApp(app, OpsClient(app.client))


# ---- Rooms written by hand ----


def solved_stored_room(
    store: RoomStore, grid: Grid, code: str, solved_at: float
) -> None:
    """Store an anonymous room whose last letter and solve time are `solved_at`."""
    store.create_room(new_room(code, grid, T0))
    solving = LogEntry(at=solved_at, event=GridSolved(seq=2, elapsed_ms=1_000))
    store.append(code, [letter_entry(1, solved_at), solving])


def hours_after_t0(hours: float) -> float:
    """The fake clock time `hours` after `T0`."""
    return T0 + hours * HOUR


def count_pongs(peer: Peer) -> int:
    """How many pongs the peer received."""
    count = 0
    for message in peer.messages():
        if isinstance(message, Pong):
            count += 1
    return count


def assert_socket_stays_open(peer: Peer) -> None:
    """A ping is answered after everything the server did so far, and no close came."""
    pongs_before = count_pongs(peer)
    peer.send(Ping())
    peer.wait_until(lambda: count_pongs(peer) > pongs_before, "a pong")
    assert peer.close_code is None


# ---- The database file ----


def prepare_database(path: Path) -> None:
    """Create the store's tables in the file (and nothing else), then close it."""
    RoomStore(path).close()


def insert_override_rows(path: Path, rows: Sequence[tuple[str, object]]) -> None:
    """Insert rows in the table `overrides` of the file, creating the table first.

    The table is created as `admin/overrides.md` rule 7 writes it, so that the
    rows exist before the app starts whatever the store does.
    """
    prepare_database(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(OVERRIDES_TABLE_SQL)
        for name, value in rows:
            connection.execute(
                "INSERT INTO overrides (name, value) VALUES (?, ?)", (name, value)
            )
        connection.commit()
    finally:
        connection.close()


def stored_overrides(path: Path) -> list[tuple[object, ...]]:
    """The rows (name, value) of the table `overrides`, by name."""
    return select_rows(path, "SELECT name, value FROM overrides ORDER BY name")


# ---- Logs ----


def overrides_records(
    records: Sequence[logging.LogRecord], level: int
) -> list[logging.LogRecord]:
    """The records of the logger `nock.overrides` at exactly this level."""
    found: list[logging.LogRecord] = []
    for record in records:
        if record.name == OVERRIDES_LOGGER and record.levelno == level:
            found.append(record)
    return found


def numbers_in(message: str) -> list[str]:
    """The runs of digits of a message, in order."""
    return re.findall(r"\d+", message)


def names_row(message: str, name: str, value: str) -> bool:
    """Whether a message names the row `name` as a whole word and shows `value`."""
    named = re.search(rf"(?<!\w){re.escape(name)}(?!\w)", message) is not None
    return named and value in message


# ---- The page ----

HEADING = "Durées de vie des salons"
TITLES = {
    "creator_solved_room_hours": "Salon d'un compte, résolu",
    "creator_room_hours": "Salon d'un compte, en cours",
    "anonymous_solved_room_hours": "Salon anonyme, résolu",
    "anonymous_room_hours": "Salon anonyme, en cours",
    "expiry_sweep_minutes": "Intervalle de nettoyage",
}
SAVE = "Enregistrer"
RESET = "Rétablir"
CONFIRM = "Confirmer"
CANCEL = "Annuler"
LOADING = "Chargement…"
LOAD_ERROR = "Impossible de charger les données."
IN_MEMORY = "Sans base de données, ces réglages sont perdus au redémarrage."
SOURCES = {
    "default": "par défaut",
    "environment": "variable",
    "override": "modifiée",
}
ONE_DAY = "Dernières 24 heures"
THREE_PERIODS = ["Dernières 24 heures", "7 derniers jours", "30 derniers jours"]


def value_text(name: str, value: float) -> str:
    """The effective value as the card writes it: `720 h` or `60 min`."""
    unit = "min" if name == INTERVAL else "h"
    return f"{value} {unit}"


def bounds_text(name: str) -> str:
    """`ops.setting_out_of_bounds` for a setting."""
    setting = SETTING_BY_NAME[name]
    unit = "min" if name == INTERVAL else "h"
    return f"Valeur hors limites ({setting.minimum} à {setting.maximum} {unit})."


def question_text(count: int) -> str:
    """`ops.setting_confirm_one` or `ops.setting_confirm_many`."""
    if count <= 1:
        return f"Cela effacera {count} salon maintenant."
    return f"Cela effacera {count} salons maintenant."


def row_summary(name: str, value: float, source: str) -> str:
    """The first part of a row's text: its name, effective value and source."""
    return f"{TITLES[name]} {value_text(name, value)} {SOURCES[source]}"


def row_line(name: str, value: float, source: str) -> str:
    """The text of a row: its name, value, source and the two buttons."""
    return f"{row_summary(name, value, source)} {SAVE} {RESET}"


class SettingsServer(NamedTuple):
    """The live app of the page tests: its URL and its database file, if any."""

    base_url: str
    database_path: Path | None


@contextlib.contextmanager
def settings_server(
    monkeypatch: pytest.MonkeyPatch,
    directory: Path,
    catalogue: Catalogue,
    variables: Mapping[str, str] | None = None,
    *,
    database: bool = True,
) -> Generator[SettingsServer]:
    """Serve the real app on a free port, given no registry, with the operator token.

    The app reads `variables` and `NOCK_DATABASE` when it starts, so a file that
    holds rooms or overrides is prepared before this is entered. Fails (does not
    skip) when the client is not built.

    Args:
        monkeypatch: Clears the variables the app reads, then sets `variables`.
        directory: The database file `nock.sqlite3` is in it.
        catalogue: The grids served.
        variables: The variables to set.
        database: True: the file; False: in memory (`durable` false).
    """
    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)
    given = {} if variables is None else dict(variables)
    variables_of(monkeypatch, given)
    database_path: Path | None = None
    if database:
        database_path = directory / DATABASE_FILE_NAME
        monkeypatch.setenv(DATABASE_VARIABLE, str(database_path))
    app = create_app(
        dist_dir=WEB_DIST_DIR, catalogue=catalogue, operator_token=OPS_TOKEN
    )
    with serving(app) as base_url:
        yield SettingsServer(base_url, database_path)


def card_of(page: Page) -> Locator:
    """The settings card: the parent of its heading."""
    heading = page.get_by_role("heading", name=HEADING, exact=True)
    return heading.locator("xpath=..")


def input_of(page: Page, name: str) -> Locator:
    """The number input of a setting, named with the row's name."""
    return card_of(page).get_by_role("spinbutton", name=TITLES[name], exact=True)


def row_of(page: Page, name: str) -> Locator:
    """The row of a setting: the nearest ancestor of its input that holds the name, a
    source tag and no other input."""
    title = TITLES[name]
    tags = " or ".join(f'contains(., "{tag}")' for tag in SOURCES.values())
    path = f'xpath=ancestor::*[count(.//input)=1][contains(., "{title}")][{tags}][1]'
    return input_of(page, name).locator(path)


def button_in(row: Locator, label: str) -> Locator:
    """A button of a row, by its exact name."""
    return row.get_by_role("button", name=label, exact=True)


NODE_TEXT_SCRIPT = """
element => {
  const parts = [];
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const text = walker.currentNode.textContent.trim();
    if (text !== '') {
      parts.push(text);
    }
  }
  return parts.join(' ');
}
"""


def node_text(locator: Locator) -> str:
    """The text of an element as its text nodes read, one space between them.

    A markup that puts the name, the value and the source in three elements
    with no space between them reads the same as one that does.
    """
    raw = locator.evaluate(NODE_TEXT_SCRIPT)
    assert isinstance(raw, str), raw
    return shown_text(raw)


def expect_node_text(locator: Locator, expected: str) -> None:
    """Wait up to the page timeout until `node_text` of the element is `expected`."""
    deadline = time.monotonic() + WAIT_TIMEOUT_MS / 1000
    actual = node_text(locator)
    while actual != expected:
        if time.monotonic() >= deadline:
            pytest.fail(f"the text reads {actual!r}, not {expected!r}")
        time.sleep(0.05)
        actual = node_text(locator)


def row_text(page: Page, name: str) -> str:
    """The text of a row, as `node_text` reads it."""
    return node_text(row_of(page, name))


def open_card(page: Page, base_url: str) -> None:
    """Open `/ops` with the token kept, and wait until the card shows its five rows."""
    seed_ops_token(page)
    open_ops(page, base_url)
    expect_ops_state(page, "ready")
    expect(card_of(page).get_by_role("spinbutton")).to_have_count(
        len(SETTINGS), timeout=WAIT_TIMEOUT_MS
    )


def type_and_save(page: Page, name: str, text: str) -> None:
    """Type `text` in the input of a setting and press its « Enregistrer »."""
    field = input_of(page, name)
    field.fill(text)
    expect(field).to_have_value(text)
    button_in(row_of(page, name), SAVE).click()


def expect_row(page: Page, name: str, value: float, source: str) -> None:
    """Wait until the row reads this value and source."""
    expect_node_text(row_of(page, name), row_line(name, value, source))


def question_of(page: Page, count: int) -> Locator:
    """The line of the question with this count of rooms."""
    return card_of(page).get_by_text(question_text(count), exact=True)


def period_texts(page: Page) -> list[str]:
    """The text of each period chip of the dashboard, in order."""
    chips = page.get_by_test_id("ops-period")
    texts: list[str] = []
    for index in range(chips.count()):
        texts.append(shown_text(chips.nth(index).inner_text()))
    return texts


class Sent(NamedTuple):
    """One request of the page to the ops API."""

    method: str
    path: str
    query: str
    body: object


class RequestLog:
    """Records every request the page sends to `/api/ops/` from now on."""

    def __init__(self, page: Page) -> None:
        self.sent: list[Sent] = []
        page.on("request", self._record)

    def _record(self, request: Request) -> None:
        parts = urlsplit(request.url)
        if not parts.path.startswith("/api/ops/"):
            return
        self.sent.append(
            Sent(request.method, parts.path, parts.query, request.post_data_json)
        )

    def saves(self) -> list[object]:
        """The bodies of the `PUT`s."""
        return [sent.body for sent in self.sent if sent.method == "PUT"]

    def dry_runs(self) -> list[object]:
        """The bodies of the dry runs."""
        return [sent.body for sent in self.sent if sent.path == DRY_RUN_PATH]

    def dashboards(self) -> list[str]:
        """The query of each dashboard request."""
        return [sent.query for sent in self.sent if sent.path == DASHBOARD_PATH]


DIVIDER_SCRIPT = """
element => {
  let current = element;
  while (current !== null && current.querySelector('input') === null) {
    const style = getComputedStyle(current);
    if (parseFloat(style.borderTopWidth) > 0 && style.borderTopStyle !== 'none') {
      return true;
    }
    const before = current.previousElementSibling;
    if (before !== null
        && (before.tagName === 'HR' || before.getAttribute('role') === 'separator')) {
      return true;
    }
    current = current.parentElement;
  }
  return false;
}
"""


def has_divider(question: Locator) -> bool:
    """Whether a divider stands right above the question's own block.

    Walks up from the question while the block holds no number input, so it never
    reaches a row: a block on the way has a top border of its own, or an `hr` or
    a `role="separator"` element is its previous sibling. The bottom border of an
    element before the block does not count: every list row has a border on each
    side, so a question with no divider of its own would pass.
    """
    found = question.evaluate(DIVIDER_SCRIPT)
    return found is True


# ---- The question as a disclosure ----


def question_block(page: Page, button: Locator) -> Locator:
    """The element the button names with `aria-controls` (fails without one)."""
    controlled = button.get_attribute("aria-controls")
    assert controlled is not None, "the button has no aria-controls"
    assert controlled.strip() != "", "the button's aria-controls is empty"
    return page.locator(f'[id="{controlled}"]')


def expect_asking(page: Page, button: Locator, count: int) -> None:
    """The button that asked is an open disclosure of the question with `count`.

    `aria-expanded` is "true" and `aria-controls` names the question's block, which
    holds the question's line, « Confirmer » and « Annuler », as on the account page
    (`account/account.md` rule 17).
    """
    expect(button).to_have_attribute("aria-expanded", "true")
    block = question_block(page, button)
    expect(block).to_be_visible()
    expect(block.get_by_text(question_text(count), exact=True)).to_have_count(1)
    expect(block.get_by_role("button", name=CONFIRM, exact=True)).to_have_count(1)
    expect(block.get_by_role("button", name=CANCEL, exact=True)).to_have_count(1)


def expect_not_asking(button: Locator) -> None:
    """The button is a closed disclosure: `aria-expanded` is "false"."""
    expect(button).to_have_attribute("aria-expanded", "false")


# ---- A save the server refuses ----

SETTINGS_ROUTE = "**/api/ops/settings"
TOKEN_REFUSED = "Jeton refusé."
THROTTLED = "Trop d'essais. Réessayez dans une minute."


def answer_saves(page: Page, status: int, body: object) -> None:
    """Answer every `PUT /api/ops/settings` with `body` as JSON and `status`.

    The `GET` of the same path still reaches the real app.
    """

    def handle(route: Route) -> None:
        if route.request.method == "PUT":
            fulfil_json(route, status, body)
        else:
            route.fallback()

    page.route(SETTINGS_ROUTE, handle)


def box_below(lower: Box, upper: Box) -> bool:
    """Whether `lower` starts at or under the bottom of `upper` (1 px)."""
    return lower.top >= upper.bottom - 1.0


def input_box(page: Page, name: str) -> Box:
    """The box of a setting's number input."""
    return box_of(input_of(page, name))
