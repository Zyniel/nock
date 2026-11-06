"""Tests of account/account, AC-24 and AC-25: a slow SMTP server stops no other work.

Fifty link requests, each within the limits of rule 6 (ten from each of five
client addresses, fifty different e-mail addresses), wait on a mailer that holds
every message 5 s. Meanwhile:

- AC-24: `GET /api/grids` answers 200 before any of those sends ends;
- AC-25: a socket that joins an existing room gets its `snapshot` before any of
  those sends ends.

Everything runs on ONE event loop with ONE app, as a server does: the requests go
through httpx `AsyncClient`s over `ASGITransport`, one per client address (the
limits read `request.client.host`), and the socket is driven over the app's ASGI
interface on that same loop. A `TestClient` per address would run its own loop,
with its own pool of threads, and so would not show the sends filling the pool
that every sync route of the app shares.

Readings of the spec's wording:

- "An SMTP server that holds every message 5 s" is `SlowMailer`, given to the app
  through `create_app(mailer=...)`: its `send` blocks the thread that calls it, as
  `SmtpMailer` does while the server holds the message, for 5 s at most. Once the
  test has seen what it checks, it lets every held message go, so that the link
  requests answer and the app stops.
- "While those requests wait" begins once the mailer has received all fifty
  messages, or after `START_LIMIT_SECONDS` with as many as the server lets start.
- "Before any of those sends ends": when the answer (or the snapshot) arrives, the
  mailer has finished no send. Since a send ends only once its 5 s have passed
  (or once the test lets it go, after the check), an app that makes the request
  wait for a send's thread answers only after a send ended.
- Each of the fifty requests answers 202 in the end: it was within the limits and
  waited on the mailer.

The hold of 5 s is a time window, so this file runs on its own
(`SERIAL_TEST_FILES`).
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Awaitable, Callable
from email.message import EmailMessage
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from starlette.types import Message, Scope

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Join, Snapshot, parse_server_message
from nock.server import create_app
from nock.store import RoomStore
from spec014_harness import socket_url
from spec033_harness import (
    DATABASE_FILE_NAME,
    LINK_PATH,
    LINKS_PER_ADDRESS,
    PUBLIC_URL,
    account_settings,
)
from spec036_hub_harness import run_hub_scenario

HOLD_SECONDS = 5.0  # the SMTP server holds every message 5 s
LINK_REQUESTS = 50
CLIENT_COUNT = LINK_REQUESTS // LINKS_PER_ADDRESS  # 5 client addresses, 10 each
# TEST-NET-3 addresses: one per group of ten link requests.
CLIENT_ADDRESSES = [f"203.0.113.{number}" for number in range(1, CLIENT_COUNT + 1)]
OTHER_CLIENT_ADDRESS = "198.51.100.7"  # the one that asks for the grids, or joins
CLIENT_PORT = 50_000
# How long the test waits for the fifty sends to start before it goes on with as
# many as have started; well inside the hold.
START_LIMIT_SECONDS = 2.0
# The bound of an answer or of a snapshot: past the hold, so that an app that
# makes it wait for a send answers late rather than never.
ANSWER_LIMIT_SECONDS = HOLD_SECONDS + 5.0
POLL_SECONDS = 0.01

GRIDS_PATH = "/api/grids"
LINK_ACCEPTED = 202


class SlowMailer:
    """A mailer whose SMTP server holds every message 5 s before it accepts it.

    `send` blocks the calling thread until the hold has passed or the test calls
    `let_go`. The counts are read from the test's event loop while the app's
    threads change them.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._let_go = threading.Event()
        self._started = 0
        self._ended = 0

    def send(self, message: EmailMessage) -> None:
        """Hold `message` 5 s, or until `let_go` is called, then accept it."""
        with self._lock:
            self._started += 1
        self._let_go.wait(HOLD_SECONDS)
        with self._lock:
            self._ended += 1

    def let_go(self) -> None:
        """End the hold of every message, those held now and those to come."""
        self._let_go.set()

    def started(self) -> int:
        """How many sends have reached the server."""
        with self._lock:
            return self._started

    def ended(self) -> int:
        """How many sends have ended."""
        with self._lock:
            return self._ended


class Seen(NamedTuple):
    """What came back while the link requests waited, and the mailer's counts then.

    `answer` is the status of `GET /api/grids` (AC-24) or the kind of the first
    message of the socket (AC-25).
    """

    answer: int | str
    sends_started: int
    sends_ended: int


class Run(NamedTuple):
    """What the test saw, and the statuses of the fifty link requests."""

    seen: Seen
    link_statuses: list[int]


def player_email(number: int) -> str:
    """The e-mail address of the link request `number`, one per request."""
    return f"player{number:02d}@example.org"


def link_clients(app: FastAPI) -> list[AsyncClient]:
    """One HTTP client of `app` per client address of the link requests."""
    clients: list[AsyncClient] = []
    for address in CLIENT_ADDRESSES:
        transport = ASGITransport(app=app, client=(address, CLIENT_PORT))
        clients.append(AsyncClient(transport=transport, base_url=PUBLIC_URL))
    return clients


async def ask_link(client: AsyncClient, email: str) -> int:
    """Ask for a sign-in link from no room; return the status of the answer."""
    response = await client.post(LINK_PATH, json={"email": email, "room": None})
    return response.status_code


async def wait_for_sends_to_start(mailer: SlowMailer) -> None:
    """Return once every link request reached the mailer, or after the limit."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + START_LIMIT_SECONDS
    while mailer.started() < LINK_REQUESTS and loop.time() < deadline:
        await asyncio.sleep(POLL_SECONDS)


async def while_links_wait(
    app: FastAPI, mailer: SlowMailer, check: Callable[[], Awaitable[int | str]]
) -> Run:
    """Run `check` while fifty link requests wait on the mailer, on one loop.

    Args:
        app: The app, started here and stopped before returning.
        mailer: The app's mailer.
        check: What the test asks for meanwhile; returns what came back.

    Returns:
        What `check` returned with the mailer's counts at that moment, and the
        statuses of the link requests once the mailer let them go.
    """
    async with app.router.lifespan_context(app):
        clients = link_clients(app)
        try:
            requests: list[asyncio.Task[int]] = []
            for number in range(LINK_REQUESTS):
                client = clients[number % CLIENT_COUNT]
                asking = ask_link(client, player_email(number))
                requests.append(asyncio.create_task(asking))
            try:
                await wait_for_sends_to_start(mailer)
                answer = await check()
                seen = Seen(answer, mailer.started(), mailer.ended())
            finally:
                mailer.let_go()
            link_statuses = list(await asyncio.gather(*requests))
        finally:
            for client in clients:
                await client.aclose()
    return Run(seen, link_statuses)


def run_with_slow_mail(
    tmp_path: Path,
    grid: Grid,
    check: Callable[[FastAPI, str, SlowMailer], Awaitable[int | str]],
) -> Run:
    """Build the app on a slow mailer and an existing room; run `check` meanwhile.

    Args:
        tmp_path: The test's directory: the database file, and an unbuilt client.
        grid: The grid of the room that exists before the app starts.
        check: Given the app, the room's code and the mailer.

    Returns:
        What `while_links_wait` returns.
    """
    from nock.accounts import AccountStore

    database_path = tmp_path / DATABASE_FILE_NAME
    store = RoomStore(database_path)
    registry = RoomRegistry(store=store)
    account_store = AccountStore(database_path)
    mailer = SlowMailer()
    try:
        code = registry.register_room(grid)
        app = create_app(
            rooms=registry,
            dist_dir=tmp_path,
            accounts=account_settings(),
            account_store=account_store,
            mailer=mailer,
        )

        async def check_this_app() -> int | str:
            return await check(app, code, mailer)

        return run_hub_scenario(while_links_wait(app, mailer, check_this_app))
    finally:
        mailer.let_go()
        account_store.close()
        registry.close()
        store.close()


def fail_late(what: str, mailer: SlowMailer) -> None:
    """Fail the test: `what` did not come within the bound of an answer."""
    pytest.fail(
        f"no {what} within {ANSWER_LIMIT_SECONDS} s; "
        f"{mailer.ended()} sends had ended by then"
    )


async def ask_for_grids(app: FastAPI, _code: str, mailer: SlowMailer) -> int:
    """`GET /api/grids` from another client; return its status."""
    transport = ASGITransport(app=app, client=(OTHER_CLIENT_ADDRESS, CLIENT_PORT))
    async with AsyncClient(transport=transport, base_url=PUBLIC_URL) as client:
        asking = client.get(GRIDS_PATH)
        try:
            response = await asyncio.wait_for(asking, ANSWER_LIMIT_SECONDS)
        except TimeoutError:
            fail_late("answer to GET /api/grids", mailer)
            raise
    return response.status_code


def socket_scope(code: str) -> Scope:
    """The ASGI scope of a socket to room `code`, from another client address."""
    path = socket_url(code)
    return {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "scheme": "ws",
        "server": ("testserver", 80),
        "client": (OTHER_CLIENT_ADDRESS, CLIENT_PORT),
        "root_path": "",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "subprotocols": [],
    }


async def next_sent(
    outgoing: asyncio.Queue[Message], what: str, mailer: SlowMailer
) -> Message:
    """The next ASGI message the app sends on the socket, within the bound.

    Args:
        outgoing: Where the app's messages on the socket arrive.
        what: The message awaited, for the failure's text.
        mailer: The app's mailer, whose count of ended sends the failure gives.

    Returns:
        The message.
    """
    try:
        return await asyncio.wait_for(outgoing.get(), ANSWER_LIMIT_SECONDS)
    except TimeoutError:
        fail_late(what, mailer)
        raise


def kind_of(sent: Message) -> str:
    """The kind of a message the app sent: the server message's class, or the event.

    A text frame is parsed as a server message (`Snapshot`, ...); anything else is
    named by its ASGI event (`websocket.close`, ...).
    """
    if sent["type"] != "websocket.send" or sent.get("text") is None:
        return str(sent["type"])
    return type(parse_server_message(sent["text"])).__name__


async def join_the_room(app: FastAPI, code: str, mailer: SlowMailer) -> str:
    """Open a socket to room `code`, join, and return the kind of its first message.

    The socket goes through the app's ASGI interface on the running loop. It is
    closed before returning; when the test fails first, its handler is
    cancelled instead.
    """
    incoming: asyncio.Queue[Message] = asyncio.Queue()
    outgoing: asyncio.Queue[Message] = asyncio.Queue()
    await incoming.put({"type": "websocket.connect"})
    serving = asyncio.create_task(app(socket_scope(code), incoming.get, outgoing.put))
    try:
        accepted = await next_sent(outgoing, "accept of the socket", mailer)
        assert accepted["type"] == "websocket.accept", accepted
        join = Join(nickname="Ana", resume_token=None)
        await incoming.put(
            {"type": "websocket.receive", "text": join.model_dump_json()}
        )
        first = await next_sent(outgoing, "message after the join", mailer)
    except BaseException:
        serving.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serving
        raise
    await incoming.put({"type": "websocket.disconnect", "code": 1000})
    await asyncio.wait_for(serving, ANSWER_LIMIT_SECONDS)
    return kind_of(first)


def test_ac24_grids_answer_while_fifty_link_sends_wait(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    run = run_with_slow_mail(tmp_path, fx01_grid, ask_for_grids)

    assert run.seen.sends_started > 0, "no send had started"
    assert run.seen.answer == 200
    assert (
        run.seen.sends_ended == 0
    ), f"GET /api/grids answered after {run.seen.sends_ended} sends had ended"
    assert run.link_statuses == [LINK_ACCEPTED] * LINK_REQUESTS


def test_ac25_a_join_gets_its_snapshot_while_fifty_link_sends_wait(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    run = run_with_slow_mail(tmp_path, fx01_grid, join_the_room)

    assert run.seen.sends_started > 0, "no send had started"
    assert run.seen.answer == Snapshot.__name__
    assert (
        run.seen.sends_ended == 0
    ), f"the snapshot came after {run.seen.sends_ended} sends had ended"
    assert run.link_statuses == [LINK_ACCEPTED] * LINK_REQUESTS
