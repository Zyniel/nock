"""Shared setup of the tests of spec 033: the optional account.

This module is not a test file: pytest does not collect it. The tests of spec 033
are in `tests/test_spec_033_*.py`, one file per criterion group:

- `test_spec_033_ac01_sign_in_link.py`: AC-1, a link asked from a room and used,
  over HTTP, with the edge cases of the address, the sessions and the cookie.
- `test_spec_033_ac01_purge.py`: AC-1, the purge of old links and sessions, on an
  `AccountStore` and through the sweep the app runs when it starts.
- `test_spec_033_ac02_ac11_devices.py`: AC-2 and the browser part of AC-11, two
  devices on the live server.
- `test_spec_033_ac03_guest_finishes.py`: AC-3, a guest solves FX-01 with accounts
  on.
- `test_spec_033_ac04_erasure.py`: AC-4, the deletion over HTTP and the bytes of
  the database files (also after a restart, sent to a second app, and for an
  account with no room), then the seat back of a former player with the rules.
- `test_spec_033_ac05_former_player_pages.py`: AC-5, what the other players' pages
  show once the account is deleted.
- `test_spec_033_ac06_configuration.py`: AC-6, the variables of "Configuration",
  `main()` and the app's account store.
- `test_spec_033_ac07_mailer.py`: AC-7, `SmtpMailer` with a test SMTP server and
  with `smtplib` replaced.
- `test_spec_033_ac08_link_requests.py`: AC-8, the answers and the limits of a link
  request, and the routes while accounts are off.
- `test_spec_033_ac09_toolbar_layout_and_keyboard.py`: AC-9, the account button in
  the room toolbar (layout and keyboard), on a mocked socket and mocked routes.
- `test_spec_033_ac09_dialog_and_account_page.py`: AC-9, the scans of the dialog and
  of `/account`, and the dialog's edge cases, on mocked answers.
- `test_spec_033_ac10_secrets.py`: AC-10, the logs and the stored tokens.
- `test_spec_033_ac11_account_rooms.py`: AC-11 over HTTP.

This module holds what more than one of those files uses: the values of the spec's
"Test harness" (`account_settings()` is its `SETTINGS`), the recording mailer, the
HTTP app on a fake clock with both stores on one file, the account routes and the
reading of their answers, the link of a recorded message, the live server with
accounts on, and the mocked account routes of AC-9. What only one file uses stays
in that file, next to its tests.

The names that this spec adds (`nock.accounts`, `nock.mailer`, `nock.i18n`, the
account settings of `nock.settings`, the new parameters of `create_app`) are
imported inside the functions that need them, never at the top of a module: until
they exist, each test fails on the name it needs, and no file fails to load.

Nicknames: the server stores them in capitals (spec 012 decision 12), so the
identities of the account routes hold `ANA`, and a page shows them through spec
040's `displayNickname` (`Ana`).
"""

from __future__ import annotations

import contextlib
import json
import re
import socket
import threading
import time
from collections.abc import Callable, Generator
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from playwright.sync_api import Browser, BrowserContext, Locator, Page, Route, expect

from nock.catalogue import Catalogue
from nock.hub import RoomRegistry
from nock.room import CellState, RoomConfig, RoomState
from nock.server import WEB_DIST_DIR, create_app, server_config
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec032_harness import NO_TICK_CONFIG

if TYPE_CHECKING:
    from nock.accounts import AccountStore
    from nock.mailer import Mailer
    from nock.settings import AccountSettings, SmtpSettings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

# ---- Values of the spec --------------------------------------------------------------

PUBLIC_URL = "http://testserver"  # SETTINGS.public_url, the TestClient's base URL
SMTP_HOST = "smtp.invalid"
SMTP_PORT = 587
SENDER = "nock@example.org"
SESSION_COOKIE = "nock_session"
SESSION_MAX_AGE = "7776000"  # SESSION_LIFE_SECONDS, 90 days
LINK_LIFE = 1_800.0  # LINK_LIFE_SECONDS, 30 minutes
SESSION_LIFE = 7_776_000.0  # SESSION_LIFE_SECONDS
HOUR = 3_600.0
LINKS_PER_EMAIL = 3  # LINKS_PER_EMAIL_PER_HOUR
LINKS_PER_ADDRESS = 10  # LINKS_PER_ADDRESS_PER_HOUR
FORMER_NICKNAME = "--"  # FORMER_PLAYER_NICKNAME
FORMER_PLAYER_TEXT = "Ancien joueur"  # t("player.former")

ANA_EMAIL = "ana.probe@example.org"
ZELIE_EMAIL = "zelie.probe@example.org"

ACCOUNT_PAGE_PATH = "/account"
ACCOUNT_PATH = "/api/account"
LINK_PATH = "/api/account/link"
SIGN_IN_PATH = "/api/account/sign-in"
SIGN_OUT_PATH = "/api/account/sign-out"
ROOMS_PATH = "/api/account/rooms"

NOT_FOUND = {"detail": "Not Found"}
NOT_AUTHORIZED = {"detail": "Not authorized"}
TOO_MANY_REQUESTS = {"detail": "Too Many Requests"}
INVALID_ADDRESS = {"detail": "Invalid e-mail address"}
MAIL_NOT_SENT = {"detail": "Mail not sent"}
SIGNED_OUT: dict[str, object] = {"signed_in": False, "email": None}

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
LINK_MARK = "/account#"
TOKEN_LENGTH = 43

# A resume token of the protocol's form that no member of any room holds.
NOBODYS_TOKEN = "token-nobody-had-000"

DATABASE_FILE_NAME = "nock.sqlite3"
MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"
SERVER_START_SECONDS = 10.0
WAIT_SECONDS = 10.0
POLL_SECONDS = 0.02
WAIT_TIMEOUT_MS = 10_000
KEY_PAUSE_MS = 60  # spec 037's harness: 60 ms or more between keys


# ---- French texts --------------------------------------------------------------------

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_]+)\}")


def load_fr() -> dict[str, str]:
    """The French messages of the web client."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def fill(template: str, values: dict[str, str]) -> str:
    """A `fr.json` value with each `{name}` that has a value replaced by it.

    A placeholder with no value stays as written, as spec 040's `t` does.
    """
    filled = template
    for match in PLACEHOLDER.finditer(template):
        name = match.group(1)
        if name in values:
            filled = filled.replace(match.group(0), values[name])
    return filled


# ---- Settings and mailers ------------------------------------------------------------


def smtp_settings(
    *, user: str | None = None, password: str | None = None
) -> SmtpSettings:
    """`SETTINGS.smtp` of the "Test harness", with a user and a password if given."""
    from pydantic import SecretStr

    from nock.settings import SmtpSettings

    secret = None if password is None else SecretStr(password)
    return SmtpSettings(
        host=SMTP_HOST,
        port=SMTP_PORT,
        security="starttls",
        user=user,
        password=secret,
        sender=SENDER,
    )


def account_settings(
    public_url: str = PUBLIC_URL,
    *,
    user: str | None = None,
    password: str | None = None,
) -> AccountSettings:
    """`SETTINGS` of the "Test harness", with another public URL or a login if given."""
    from nock.settings import AccountSettings

    return AccountSettings(
        public_url=public_url, smtp=smtp_settings(user=user, password=password)
    )


class RecordingMailer:
    """The recording mailer of the "Test harness": it keeps each message it sends.

    While `failing` is True, `send` raises `MailError` and keeps nothing, as the
    failing mailer of the harness does. The live server's thread appends to
    `messages`; the test reads it.
    """

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []
        self.failing = False

    def send(self, message: EmailMessage) -> None:
        """Keep `message`, or raise `MailError` while `failing` is True."""
        if self.failing:
            from nock.mailer import MailError

            raise MailError("the test mailer sends nothing")
        self.messages.append(message)


class FailingMailer:
    """The failing mailer of the "Test harness": every `send` raises `MailError`."""

    def send(self, message: EmailMessage) -> None:
        """Raise `MailError`."""
        from nock.mailer import MailError

        raise MailError("the test mailer sends nothing")


def body_of(message: EmailMessage) -> str:
    """The plain-text body of a message, without the line end that ends it.

    `EmailMessage.set_content` ends a text body with one line end; the spec's body
    is `t("email.sign_in.body", ...)`, which has none.
    """
    content = message.get_content()
    assert isinstance(content, str), f"the body is not text: {content!r}"
    return content.removesuffix("\n")


def token_of(message: EmailMessage) -> str:
    """The link token of a sign-in message: the 43 characters after `/account#`."""
    body = body_of(message)
    start = body.find(LINK_MARK)
    assert start >= 0, f"no {LINK_MARK} in the body {body!r}"
    token = body[start + len(LINK_MARK) : start + len(LINK_MARK) + TOKEN_LENGTH]
    assert TOKEN_PATTERN.fullmatch(token) is not None, f"not a link token: {token!r}"
    return token


def last_token(mailer: RecordingMailer) -> str:
    """The link token of the last message the mailer sent."""
    assert len(mailer.messages) > 0, "the mailer sent no message"
    return token_of(mailer.messages[-1])


# ---- The HTTP app of the "Test harness" ----------------------------------------------


class AccountApp(NamedTuple):
    """The app of the HTTP criteria, its stores, its mailer and its fake clock."""

    client: TestClient
    registry: RoomRegistry
    store: RoomStore
    accounts: AccountStore
    mailer: RecordingMailer
    clock: FakeClock
    database_path: Path


@contextlib.contextmanager
def account_app(
    tmp_path: Path,
    clock: FakeClock,
    *,
    settings: AccountSettings | None = None,
    mailer: Mailer | None = None,
    config: RoomConfig = NO_TICK_CONFIG,
    dist_dir: Path | None = None,
    store: RoomStore | None = None,
) -> Generator[AccountApp]:
    """Run the app of the "Test harness" in a `TestClient` and yield it.

    The app is `create_app(rooms=registry, dist_dir=tmp_path, accounts=settings,
    account_store=AccountStore(path), mailer=mailer)`, with `registry =
    RoomRegistry(clock=clock, store=RoomStore(path), config=config)` and `path =
    tmp_path / "nock.sqlite3"` for both stores. The rooms' config changes nothing
    on a tick by default, so that moving the fake clock times nobody out.

    Args:
        tmp_path: The test's directory; also the app's (unbuilt) client.
        clock: The fake clock of the rooms, and so of the account routes.
        settings: The account settings; None: `account_settings()`.
        mailer: The mailer; None: a new `RecordingMailer`, which the result holds.
        config: The thresholds of the rooms.
        dist_dir: The built client; None: `tmp_path`, which holds none.
        store: The rooms' store, opened on `tmp_path / "nock.sqlite3"` by the
            caller (a `RoomStore` subclass that records what it is given); None:
            `RoomStore(path)`. Closed at the end either way.
    """
    from nock.accounts import AccountStore

    database_path = tmp_path / DATABASE_FILE_NAME
    recorder = RecordingMailer()
    app_mailer: Mailer = recorder if mailer is None else mailer
    app_settings = account_settings() if settings is None else settings
    if store is None:
        store = RoomStore(database_path)
    registry = RoomRegistry(clock=clock, store=store, config=config)
    account_store = AccountStore(database_path)
    try:
        app = create_app(
            rooms=registry,
            dist_dir=tmp_path if dist_dir is None else dist_dir,
            accounts=app_settings,
            account_store=account_store,
            mailer=app_mailer,
        )
        with TestClient(app) as client:
            yield AccountApp(
                client=client,
                registry=registry,
                store=store,
                accounts=account_store,
                mailer=recorder,
                clock=clock,
                database_path=database_path,
            )
    finally:
        account_store.close()
        registry.close()
        store.close()


def room_key(code: str, resume_token: str) -> dict[str, str]:
    """A `RoomKey` as JSON."""
    return {"code": code, "resume_token": resume_token}


def ask_link(
    client: TestClient, email: str, room: dict[str, str] | None = None
) -> Response:
    """`POST /api/account/link` with `{"email": email, "room": room}`."""
    return client.post(LINK_PATH, json={"email": email, "room": room})


def sign_in(client: TestClient, token: str) -> Response:
    """`POST /api/account/sign-in` with the link token."""
    return client.post(SIGN_IN_PATH, json={"token": token})


def link_and_sign_in(
    app: AccountApp, email: str, room: dict[str, str] | None = None
) -> Response:
    """Ask a link, check it was sent, and use it; return the sign-in's answer."""
    sent_before = len(app.mailer.messages)
    asked = ask_link(app.client, email, room)
    assert asked.status_code == 202, asked.text
    assert len(app.mailer.messages) == sent_before + 1
    signed_in = sign_in(app.client, last_token(app.mailer))
    assert signed_in.status_code == 200, signed_in.text
    return signed_in


def with_session(session: str) -> dict[str, str]:
    """A `Cookie` header that carries the session `session`, and nothing else."""
    return {"Cookie": f"{SESSION_COOKIE}={session}"}


class SetCookie(NamedTuple):
    """One `Set-Cookie` header: its value and its attributes.

    The attribute names are lower-cased, since a browser reads them so (RFC
    6265); an attribute without `=` (`HttpOnly`) has the value "".
    """

    value: str
    attributes: dict[str, str]


def set_cookie_of(response: Response, name: str = SESSION_COOKIE) -> SetCookie:
    """The one `Set-Cookie` header of `response` for the cookie `name`."""
    found: list[SetCookie] = []
    for header in response.headers.get_list("set-cookie"):
        parts = header.split(";")
        cookie_name, _, cookie_value = parts[0].strip().partition("=")
        if cookie_name != name:
            continue
        attributes: dict[str, str] = {}
        for part in parts[1:]:
            attribute, _, value = part.strip().partition("=")
            attributes[attribute.lower()] = value
        unquoted = cookie_value.removeprefix('"').removesuffix('"')
        found.append(SetCookie(value=unquoted, attributes=attributes))
    assert len(found) == 1, response.headers.get_list("set-cookie")
    return found[0]


def wait_for(condition: Callable[[], bool], what: str) -> None:
    """Wait up to `WAIT_SECONDS` of real time for `condition`, else fail."""
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        if time.monotonic() >= deadline:
            pytest.fail(f"timed out waiting for {what}")
        time.sleep(POLL_SECONDS)


def cell_state(state: RoomState, row: int, column: int) -> CellState:
    """The room's state of one letter cell; fails when there is no such cell."""
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


def state_of(registry: RoomRegistry, code: str) -> RoomState:
    """The room's latest state; fails when the room is unknown."""
    state = registry.room_state(code)
    assert state is not None, f"no room {code}"
    return state


# ---- The database files --------------------------------------------------------------


def database_bytes(database_path: Path) -> bytes:
    """The bytes of `nock.sqlite3`, then of `nock.sqlite3-wal` when it exists."""
    data = database_path.read_bytes()
    wal_path = database_path.with_name(database_path.name + "-wal")
    # No WAL file, or one just removed by a checkpoint: only the main file counts.
    with contextlib.suppress(FileNotFoundError):
        data += wal_path.read_bytes()
    return data


def strings_in(data: bytes, texts: list[str]) -> list[str]:
    """The texts of `texts` whose UTF-8 bytes occur in `data`, in the given order."""
    found: list[str] = []
    for text in texts:
        if text.encode("utf-8") in data:
            found.append(text)
    return found


# ---- The live server with accounts on ------------------------------------------------


class AccountServer(NamedTuple):
    """The live server of the "Test harness", its stores and its mailer."""

    base_url: str
    registry: RoomRegistry
    store: RoomStore
    accounts: AccountStore
    mailer: RecordingMailer
    database_path: Path


def _bind_free_port() -> socket.socket:
    """A socket bound to a free port of 127.0.0.1."""
    listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listening_socket.bind(("127.0.0.1", 0))
    return listening_socket


@contextlib.contextmanager
def _serving(app_of: Callable[[str], FastAPI]) -> Generator[str]:
    """Serve the app that `app_of(<base URL>)` builds, on a free port; yield the URL.

    The server is `uvicorn.Server(server_config(app, log_level="warning"))`, run in
    a thread, as spec 040's `live_server` does.
    """
    listening_socket = _bind_free_port()
    port = listening_socket.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    server: uvicorn.Server | None = None
    thread: threading.Thread | None = None
    try:
        app = app_of(base_url)
        server = uvicorn.Server(server_config(app, log_level="warning"))
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listening_socket]}, daemon=True
        )
        thread.start()
        deadline = time.monotonic() + SERVER_START_SECONDS
        while not server.started and time.monotonic() < deadline:
            if not thread.is_alive():
                break
            time.sleep(POLL_SECONDS)
        if not server.started:
            pytest.fail("the live server with accounts on did not start")
        yield base_url
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=SERVER_START_SECONDS)
        listening_socket.close()


@contextlib.contextmanager
def account_live_server(
    directory: Path, catalogue: Catalogue
) -> Generator[AccountServer]:
    """Run the live server of the "Test harness" and yield it.

    The app is `create_app(rooms=room_registry, dist_dir=WEB_DIST_DIR,
    catalogue=catalogue, accounts=AccountSettings(public_url=<its base URL>,
    smtp=SETTINGS.smtp), account_store=AccountStore(path), mailer=recorder)`, with
    both stores on `<directory>/nock.sqlite3` and the rooms on the real clock.
    Fails (does not skip) when the client is not built. At the end the server
    stops, then the stores are closed.
    """
    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)
    from nock.accounts import AccountStore

    database_path = directory / DATABASE_FILE_NAME
    store = RoomStore(database_path)
    registry = RoomRegistry(store=store)
    account_store = AccountStore(database_path)
    mailer = RecordingMailer()

    def app_of(base_url: str) -> FastAPI:
        return create_app(
            rooms=registry,
            dist_dir=WEB_DIST_DIR,
            catalogue=catalogue,
            accounts=account_settings(base_url),
            account_store=account_store,
            mailer=mailer,
        )

    try:
        with _serving(app_of) as base_url:
            yield AccountServer(
                base_url=base_url,
                registry=registry,
                store=store,
                accounts=account_store,
                mailer=mailer,
                database_path=database_path,
            )
    finally:
        account_store.close()
        registry.close()
        store.close()


# ---- Browser: devices and pages ------------------------------------------------------


class Devices:
    """Browser contexts, one per device (separate storage and cookies).

    `close()` closes every context it opened.
    """

    def __init__(self, browser: Browser) -> None:
        self.browser = browser
        self.contexts: list[BrowserContext] = []

    def new(self) -> BrowserContext:
        """A new device: an empty context."""
        context = self.browser.new_context()
        self.contexts.append(context)
        return context

    def close(self) -> None:
        """Close every context opened."""
        for context in self.contexts:
            context.close()


def room_page(page: Page) -> Locator:
    return page.get_by_test_id("room-page")


def account_page(page: Page) -> Locator:
    return page.get_by_test_id("account-page")


def expect_account_state(page: Page, state: str) -> None:
    """Wait until the account page's `data-state` is `state`."""
    expect(account_page(page)).to_have_attribute(
        "data-state", state, timeout=WAIT_TIMEOUT_MS
    )


def cell_at(page: Page, row: int, column: int) -> Locator:
    """One cell of the room page's grid."""
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def roster_item(page: Page, player_id: str) -> Locator:
    """The roster row of one player."""
    selector = f'[data-testid="roster-player"][data-player-id="{player_id}"]'
    return page.locator(selector)


def type_letter(page: Page, row: int, column: int, key: str) -> None:
    """Click the cell (row, column), press `key`, then pause 60 ms."""
    cell_at(page, row, column).click()
    page.keyboard.press(key)
    page.wait_for_timeout(KEY_PAUSE_MS)


def you_of(page: Page) -> str:
    """The `data-you` of a joined room page."""
    you = room_page(page).get_attribute("data-you")
    assert you is not None, "the room page has no data-you"
    assert you != "", "the room page's data-you is empty"
    return you


def stored_identity(page: Page, code: str) -> dict[str, object] | None:
    """The record `nock.identity.<code>` of the page's `localStorage`, parsed."""
    raw = page.evaluate("key => localStorage.getItem(key)", f"nock.identity.{code}")
    if raw is None:
        return None
    assert isinstance(raw, str), raw
    parsed = json.loads(raw)
    assert isinstance(parsed, dict), parsed
    return parsed


def ask_link_in_form(page: Page, email: str) -> None:
    """Type `email` in `account-email-input` and press `account-email-submit`."""
    page.get_by_test_id("account-email-input").fill(email)
    page.get_by_test_id("account-email-submit").click()


def open_account_dialog(page: Page) -> Locator:
    """Click `account-open` and wait until `account-dialog` is open."""
    page.get_by_test_id("account-open").click()
    dialog = page.get_by_test_id("account-dialog")
    expect(dialog).to_have_attribute("open", "", timeout=WAIT_TIMEOUT_MS)
    return dialog


def wait_for_messages(mailer: RecordingMailer, count: int) -> None:
    """Wait until the live server's mailer holds `count` messages."""
    wait_for(lambda: len(mailer.messages) >= count, f"{count} sent messages")


def link_in(base_url: str, message: EmailMessage) -> str:
    """The sign-in link of a message sent by the live server."""
    return f"{base_url}{LINK_MARK}{token_of(message)}"


def sign_in_with_link(page: Page, link: str) -> None:
    """Open a sign-in link and wait until the account page is `signed_in`."""
    page.goto(link)
    expect_account_state(page, "signed_in")


# ---- Browser: mocked account routes (AC-9) -------------------------------------------


class AccountRoutes:
    """The account routes of a page, answered by `page.route` (mocked answers).

    `GET /api/account` answers `status_body` with 200, or 404 when it is None;
    `DELETE /api/account` 204; `POST /api/account/link` the status `link_status`
    with its body (202 `{}`, 422, 429, 503, or anything else as 500), or holds
    the request while `hold_links` is True; `POST /api/account/sign-in` 200 or
    404 (`sign_in_status`); `PUT /api/account/rooms` and
    `POST /api/account/sign-out` 204. Every request is recorded.
    """

    def __init__(
        self,
        status_body: dict[str, object] | None = None,
        link_status: int = 202,
        sign_in_status: int = 200,
    ) -> None:
        self.status_body = SIGNED_OUT if status_body is None else status_body
        self.account_off = False
        self.link_status = link_status
        self.sign_in_status = sign_in_status
        self.hold_links = False
        self.held: list[Route] = []
        self.requests: list[tuple[str, str]] = []

    def install(self, page: Page) -> None:
        """Route the page's account requests to these answers."""
        page.route("**/api/account", self._account)
        page.route("**/api/account/link", self._link)
        page.route("**/api/account/sign-in", self._sign_in)
        page.route("**/api/account/rooms", self._no_content)
        page.route("**/api/account/sign-out", self._no_content)

    def _keep(self, route: Route) -> None:
        self.requests.append((route.request.method, route.request.url))

    def _account(self, route: Route) -> None:
        self._keep(route)
        if route.request.method == "DELETE":
            route.fulfill(status=204, body="")
        elif self.account_off:
            fulfill_json(route, 404, {"detail": "Not Found"})
        else:
            fulfill_json(route, 200, self.status_body)

    def _link(self, route: Route) -> None:
        self._keep(route)
        if self.hold_links:
            self.held.append(route)
            return
        answer_link(route, self.link_status)

    def _sign_in(self, route: Route) -> None:
        self._keep(route)
        if self.sign_in_status == 200:
            fulfill_json(route, 200, SIGN_IN_ANSWER)
        else:
            fulfill_json(route, 404, {"detail": "Not Found"})

    def _no_content(self, route: Route) -> None:
        self._keep(route)
        route.fulfill(status=204, body="")


def fulfill_json(route: Route, status: int, body: object) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def answer_link(route: Route, status: int) -> None:
    """Answer a link request with `status` and the body the spec gives it."""
    bodies: dict[int, object] = {
        202: {},
        422: INVALID_ADDRESS,
        429: TOO_MANY_REQUESTS,
        503: MAIL_NOT_SENT,
    }
    fulfill_json(route, status, bodies.get(status, {"detail": "Internal Error"}))


# The window sizes of spec 006 AC-5.
WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


SIGNED_IN: dict[str, object] = {"signed_in": True, "email": ANA_EMAIL}
SIGN_IN_ANSWER = {"email": ANA_EMAIL, "room_code": None, "rooms": []}
A_TOKEN = "abcdefghijklmnopqrstuvwxyz" + "ABCDEFGHIJKLMNOPQ"  # 43 characters
