"""FastAPI app: serves the built web client, the room WebSocket and the recaps.

It also answers a member's catch-up request: what changed in a room while their
page was away (spec 034).

While the app runs, it deletes the expired rooms of the registry it serves once
when it starts, then every `expiry_sweep_seconds` (spec 032).

With an operator token, it also serves the operator pages (spec 038): the page
`/ops` and the ops API under `/api/ops/`, the dashboard and the replay of a room,
which only a request carrying the token reaches.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import secrets
import threading
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Annotated, Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nock.catalogue import (
    GRIDS_DIR,
    Catalogue,
    CatalogueEntry,
    load_catalogue,
    summarize,
)
from nock.catch_up import CatchUpRequest
from nock.hub import (
    MAX_FRAME_BYTES,
    ROOM_NOT_FOUND_CLOSE_CODE,
    SESSION_REPLACED_CLOSE_CODE,
    SILENCE_CLOSE_CODE,
    RoomConnection,
    RoomRegistry,
)
from nock.operations import (
    DAY_SECONDS,
    RoomLog,
    RoomReplay,
    dashboard_figures,
    room_edits,
)
from nock.protocol import grid_view, parse_client_message
from nock.room import RoomKey, RoomSummary
from nock.settings import OPERATOR_TOKEN_VARIABLE, operator_token_from_env
from nock.store import RoomStore

__all__ = [
    "ROOM_NOT_FOUND_CLOSE_CODE",
    "SESSION_REPLACED_CLOSE_CODE",
    "SILENCE_CLOSE_CODE",
    "WS_MAX_SIZE_BYTES",
    "RoomRegistry",
    "create_app",
    "server_config",
]

logger = logging.getLogger(__name__)

WEB_DIST_DIR: Path = Path(__file__).resolve().parents[2] / "web" / "dist"
ROOM_CODE_PATTERN: str = r"^[A-Z0-9]{6}$"
GRID_NUMBER_PATTERN: str = r"^[1-9][0-9]{0,8}$"
FORCE_PATTERN: str = r"^[1-4]$"
MAX_SUMMARY_KEYS: int = 100  # spec 032: keys in one POST /api/rooms/summaries
THROTTLED_CLOSE_CODE: int = 4429  # WebSocket close code, too many wrong codes
WRONG_CODE_LIMIT: int = 10
WRONG_CODE_WINDOW_SECONDS: float = 60.0
DATABASE_VARIABLE: str = "NOCK_DATABASE"  # path of the SQLite file (spec 018)
MEMORY_DATABASE: str = ":memory:"
WS_MAX_SIZE_BYTES: int = 8192  # spec 036: uvicorn refuses larger frames (close 1009)
OPS_API_ROOT: str = "/api/ops"  # spec 038: hidden too while the pages are off
OPS_API_PREFIX: str = "/api/ops/"  # spec 038: the paths of the ops API
BEARER_PREFIX: str = "Bearer "  # spec 038: the operator token's header value
NO_STORE: str = "no-store"  # spec 038: the Cache-Control of every ops API answer

# The ?days= of the dashboard as written in the URL: exactly 1, 7 or 30 (spec 038).
DashboardDays = Literal["1", "7", "30"]

_MISSING_BUILD_TEXT = "The web client is not built: run npm --prefix web run build"


class CreateRoomRequest(BaseModel):
    """The body of POST /api/rooms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    grid_number: int = Field(ge=1, strict=True)  # a catalogue number (spec 004)


class CreateRoomResponse(BaseModel):
    """The answer of POST /api/rooms: never any grid data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str  # matches ROOM_CODE_PATTERN
    share_url: str  # absolute: <scheme>://<host>/r/<code>


class RoomSummariesRequest(BaseModel):
    """The body of POST /api/rooms/summaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rooms: tuple[RoomKey, ...] = Field(max_length=MAX_SUMMARY_KEYS)


class _WrongCodeThrottle:
    """The failures of each client address, kept in memory by one app.

    An app has two: one for the wrong room codes (spec 011; spec 028's recap
    route shares it), one for the refused ops API requests (spec 038), each with
    its own count. An address is kept until WRONG_CODE_WINDOW_SECONDS after its
    last failure, and at most until the next failure recorded after that. Every
    method may be called from any thread: each one takes the lock.
    """

    def __init__(self) -> None:
        """Create a throttle that holds no failure."""
        self._lock = threading.Lock()
        self._failure_times: dict[str, list[float]] = {}

    def is_blocked(self, address: str, now: float) -> bool:
        """Tell whether `address` has too many failures in the window at `now`.

        Records and forgets nothing.

        Args:
            address: The client's address.
            now: Clock time of the request.

        Returns:
            True when `address` has at least WRONG_CODE_LIMIT failures whose
            time `t` satisfies `t > now - WRONG_CODE_WINDOW_SECONDS`.
        """
        with self._lock:
            recent = self._recent_failures(address, now)
            return len(recent) >= WRONG_CODE_LIMIT

    def record_unless_blocked(self, address: str, now: float) -> bool:
        """Record one failure of `address` at time `now`, unless it is blocked.

        The check and the record are one step under the lock, so failures that
        arrive at once are counted one after another (spec 011): of a burst,
        exactly the first WRONG_CODE_LIMIT are recorded, however long the
        lookups before them took. Before it records, the throttle forgets every
        address whose failures are all outside the window at `now`, so that an
        address that never comes back is not kept until the process stops.

        Args:
            address: The client's address.
            now: Clock time of the failure: a wrong code, or a wrong token.

        Returns:
            True when the failure is recorded: the client gets the answer of an
            unknown room, or of a missing token. False when the address is
            blocked: the client gets the throttle's answer, and nothing is
            recorded or forgotten.
        """
        with self._lock:
            recent = self._recent_failures(address, now)
            if len(recent) >= WRONG_CODE_LIMIT:
                return False
            self._forget_old_failures(now)
            recent.append(now)
            self._failure_times[address] = recent
            return True

    def held_addresses(self) -> frozenset[str]:
        """Return the addresses whose failures the throttle keeps.

        Records and forgets nothing.
        """
        with self._lock:
            return frozenset(self._failure_times)

    def _recent_failures(self, address: str, now: float) -> list[float]:
        """Return the failure times of `address` inside the window at `now`.

        The caller holds the lock.
        """
        recent: list[float] = []
        for failure_time in self._failure_times.get(address, []):
            if failure_time > now - WRONG_CODE_WINDOW_SECONDS:
                recent.append(failure_time)
        return recent

    def _forget_old_failures(self, now: float) -> None:
        """Keep, for every address, only its failures inside the window at `now`.

        An address left with no failure is forgotten. The caller holds the lock.
        """
        kept: dict[str, list[float]] = {}
        for address in self._failure_times:
            recent = self._recent_failures(address, now)
            if len(recent) > 0:
                kept[address] = recent
        self._failure_times = kept


class _RoomsHolder:
    """The registry an app serves: the one it was given, or one it creates.

    A registry created here opens its database on first use, which is when the
    app starts, and is closed with the app. A registry given is never closed.
    """

    def __init__(self, given: RoomRegistry | None) -> None:
        """Keep `given`, or None to create the registry on first use."""
        self._lock = threading.Lock()
        self._registry = given
        self._is_created_here = False

    def get(self) -> RoomRegistry:
        """Return the registry, creating it from NOCK_DATABASE the first time."""
        with self._lock:
            if self._registry is None:
                database = os.environ.get(DATABASE_VARIABLE, "")
                if database == "":
                    database = MEMORY_DATABASE  # an empty variable counts as unset
                self._registry = RoomRegistry(store=RoomStore(database))
                self._is_created_here = True
            return self._registry

    def close_if_created(self) -> None:
        """Close the registry (and its store) when this holder created it."""
        with self._lock:
            if self._registry is not None and self._is_created_here:
                self._registry.close()
                self._registry = None
                self._is_created_here = False


class _OperatorToken:
    """The operator token an app checks: the one it was given, or its variable.

    A token given follows the rule of NOCK_OPERATOR_TOKEN and is checked when
    the app is built. Without one, the variable is read each time the app
    starts (spec 038). While `token` is None, the operator pages are off.
    """

    def __init__(self, given: str | None) -> None:
        """Check the token given, or wait for the app's start to read the variable.

        Args:
            given: The `operator_token` of `create_app`. "" turns the operator
                pages off, as an empty variable does. None: read
                NOCK_OPERATOR_TOKEN when the app starts.

        Raises:
            SettingsError: `given` breaks the rule of NOCK_OPERATOR_TOKEN. The
                message never holds it.
        """
        self._reads_variable = given is None
        self.token: str | None = None
        if given is not None:
            # The token given goes through the variable's rule, as if it were
            # the variable's value: "" gives None, so the pages are off.
            self.token = operator_token_from_env({OPERATOR_TOKEN_VARIABLE: given})

    def read_at_start(self) -> None:
        """Take the token of NOCK_OPERATOR_TOKEN, unless a token was given.

        Raises:
            SettingsError: the variable breaks the rule of spec 038.
        """
        if self._reads_variable:
            self.token = operator_token_from_env(os.environ)


def _not_found() -> HTTPException:
    """Return the 404 error with FastAPI's usual body."""
    return HTTPException(status_code=404, detail="Not Found")


def _too_many_requests() -> HTTPException:
    """Return the 429 error of a throttled address (wrong room codes or tokens)."""
    return HTTPException(status_code=429, detail="Too Many Requests")


def _not_authorized() -> HTTPException:
    """Return the 401 error of an ops API request without the operator token."""
    return HTTPException(
        status_code=401,
        detail="Not authorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _is_ops_path(path: str) -> bool:
    """Tell whether `path` is `/api/ops` or a path under `/api/ops/` (spec 038)."""
    return path == OPS_API_ROOT or path.startswith(OPS_API_PREFIX)


def _carries_token(request: Request, token: str) -> bool:
    """Tell whether the request carries the header `Authorization: Bearer <token>`.

    The token is read from that header only, never from the URL, the query or a
    cookie. It is compared with `secrets.compare_digest`, whose time does not
    tell how much of the token was right.
    """
    header = request.headers.get("authorization", "")
    if not header.startswith(BEARER_PREFIX):
        return False
    given_token = header.removeprefix(BEARER_PREFIX)
    # As bytes: compare_digest refuses a str that is not ASCII.
    return secrets.compare_digest(given_token.encode("utf-8"), token.encode("utf-8"))


def _room_logs_since(store: RoomStore, since: float) -> list[RoomLog]:
    """Return the log of each room created at `since` or later (spec 038).

    The rooms are read from the store only, so none of them is made live.
    """
    room_logs: list[RoomLog] = []
    for code, created_at in store.codes_created_since(since):
        entries = tuple(store.read_log(code))
        room_logs.append(RoomLog(code=code, created_at=created_at, entries=entries))
    return room_logs


def _client_address(connection: Request | WebSocket) -> str:
    """Return the address of the client of a request or a socket."""
    if connection.client is None:
        return "unknown"
    return connection.client.host


def _index_response(dist_dir: Path) -> Response:
    """Answer with index.html, or 503 when the client is not built.

    The check is made on every request, so a build made after the server
    started is served without a restart.
    """
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        return PlainTextResponse(_MISSING_BUILD_TEXT, status_code=503)
    return FileResponse(index_path)


def _published_entry(
    catalogue: Catalogue, number_regex: re.Pattern[str], number: str
) -> CatalogueEntry:
    """Return the published entry written `number` in a URL.

    Raises:
        HTTPException: 404 when `number` is malformed, unknown or unpublished.
    """
    if number_regex.fullmatch(number) is None:
        raise _not_found()
    entry = catalogue.find_published(int(number))
    if entry is None:
        raise _not_found()
    return entry


def _is_safe_file_name(name: str) -> bool:
    """Tell whether `name` is one plain file name that cannot leave a directory."""
    if name == "":
        return False
    # Dot files are never served; this also rejects "." and "..".
    if name.startswith("."):
        return False
    if "/" in name:
        return False
    if "\\" in name:
        return False
    # ":" would allow Windows drive letters and alternate data streams.
    return ":" not in name


def _file_in_directory(directory: Path, name: str) -> FileResponse:
    """Answer with the regular file `name` directly inside `directory`.

    Raises:
        HTTPException: 404 when there is no such file, or `name` leaves `directory`.
    """
    if not _is_safe_file_name(name):
        raise _not_found()
    file_path = (directory / name).resolve()
    if not file_path.is_relative_to(directory.resolve()):
        raise _not_found()
    if not file_path.is_file():
        raise _not_found()
    return FileResponse(file_path)


def _frame_size(raw_message: str | bytes) -> int:
    """Return the size of a frame in bytes (UTF-8 for a text frame)."""
    if isinstance(raw_message, str):
        return len(raw_message.encode("utf-8"))
    return len(raw_message)


async def _read_frames(websocket: WebSocket, connection: RoomConnection) -> None:
    """Pass each frame of the client to the room until the client disconnects.

    The room task decides what a message means: a join, a message of a joined
    player, or an error for a connection that has not joined.
    """
    while True:
        frame = await websocket.receive()
        if frame["type"] == "websocket.disconnect":
            return
        raw_message = frame.get("text")
        if raw_message is None:
            raw_message = frame.get("bytes", b"")
        if _frame_size(raw_message) > MAX_FRAME_BYTES:
            connection.submit_invalid()
            continue
        try:
            message = parse_client_message(raw_message)
        except ValidationError:
            connection.submit_invalid()
            continue
        connection.submit(message)


async def _serve_socket(
    websocket: WebSocket, room_registry: RoomRegistry, code: str
) -> None:
    """Link the socket to the room and serve it until it closes.

    The writer sends what the room task queues for this connection, in order:
    the snapshot of the join, the events, the errors and the closes.
    """
    connection = room_registry.connect(code)
    if connection is None:
        # The room expired since the route looked it up (spec 032).
        await websocket.close(code=ROOM_NOT_FOUND_CLOSE_CODE)
        return
    writer = asyncio.create_task(
        connection.run_writer(
            websocket.send_text, lambda close_code: websocket.close(close_code)
        )
    )
    try:
        await _read_frames(websocket, connection)
    finally:
        connection.leave()
        writer.cancel()
        # The writer may have failed on a closed socket, and the server may
        # cancel this handler while it shuts down: neither is an error here.
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await writer


async def _sweep_expired_rooms(rooms: RoomRegistry, stop: asyncio.Event) -> None:
    """Delete the expired rooms now, then every `expiry_sweep_seconds`, until `stop`.

    Each sweep runs in a worker thread, since it waits for the disk. A sweep that
    raises is logged, and the next one runs as planned (spec 032).
    """
    while not stop.is_set():
        try:
            await asyncio.to_thread(rooms.expire_rooms)
        except Exception:
            logger.exception("The sweep of the expired rooms failed")
        # The interval, or less when the app stops meanwhile.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), rooms.config.expiry_sweep_seconds)


@contextlib.asynccontextmanager
async def _expiry_sweeps(rooms: RoomRegistry) -> AsyncGenerator[None]:
    """Run the expiry sweeps of `rooms` in the background while the block runs.

    On the way out, a sweep under way is waited for, so that it never meets a
    closed registry.
    """
    stop = asyncio.Event()
    sweeping = asyncio.create_task(_sweep_expired_rooms(rooms, stop))
    try:
        yield
    finally:
        stop.set()
        await sweeping


def create_app(
    rooms: RoomRegistry | None = None,
    dist_dir: Path | None = None,
    catalogue: Catalogue | None = None,
    *,
    operator_token: str | None = None,
) -> FastAPI:
    """Build the app.

    Args:
        rooms: The rooms the WebSocket serves. None: a new registry on the
            database of the environment variable NOCK_DATABASE (in memory when
            it is unset or empty), opened when the app starts and closed when
            it stops.
            A registry given is never closed by the app.
        dist_dir: The built client. None: WEB_DIST_DIR.
        catalogue: The grids served. None: an empty catalogue.
        operator_token: The token of the operator pages (spec 038), checked
            by the rule of NOCK_OPERATOR_TOKEN when `create_app` is called:
            "" turns the pages off, as an unset variable does, and the
            variable is not read. None: the token of NOCK_OPERATOR_TOKEN, read
            when the app starts; the pages are off when the variable is unset
            or empty.

    Never raises because `dist_dir` is missing or empty (see AC-6). The app's
    startup raises SettingsError when it reads a NOCK_OPERATOR_TOKEN that breaks
    the rule of spec 038.

    Raises:
        SettingsError: `operator_token` breaks the rule of NOCK_OPERATOR_TOKEN.
            The message never holds it.
    """
    holder = _RoomsHolder(rooms)
    operator = _OperatorToken(operator_token)
    client_dir = dist_dir if dist_dir is not None else WEB_DIST_DIR
    grid_catalogue = catalogue if catalogue is not None else Catalogue()
    room_code_regex = re.compile(ROOM_CODE_PATTERN)
    grid_number_regex = re.compile(GRID_NUMBER_PATTERN)
    wrong_codes = _WrongCodeThrottle()
    # Spec 038: the refused ops API requests, counted apart from the wrong codes.
    refused_ops_requests = _WrongCodeThrottle()

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        operator.read_at_start()
        room_registry = holder.get()
        try:
            async with _expiry_sweeps(room_registry):
                yield
        finally:
            holder.close_if_created()

    # No slash redirect: a path ending with "/" matches no route and is a 404.
    web_app = FastAPI(
        lifespan=lifespan,
        redirect_slashes=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Spec 038, rule 1: while the operator pages are off, a request of any
    # method to an ops path answers as the same method on an unknown path under
    # /api/ does. The routes cannot answer it: another method than GET on the
    # path of an ops route would get FastAPI's 405. Rule 4: while the pages are
    # on, no browser or proxy keeps an ops API answer, refusals included.
    @web_app.middleware("http")
    async def guard_ops_paths(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if operator.token is None:
            if _is_ops_path(path):
                # FastAPI's own answer to a path that no route matches.
                return await http_exception_handler(request, _not_found())
            return await call_next(request)
        response = await call_next(request)
        if path.startswith(OPS_API_PREFIX):
            response.headers["Cache-Control"] = NO_STORE
        return response

    def check_operator(request: Request) -> None:
        """Let an ops API request through, or refuse it (spec 038, rules 1 to 3).

        Runs before the route reads its parameters, so a wrong token is refused
        before any validation.

        Raises:
            HTTPException: 404 while the operator pages are off, as for any
                unknown path; 429 while the client's address is throttled,
                whatever its token; 401 without the operator token, which
                counts as one refusal of the address.
        """
        token = operator.token
        if token is None:
            # Rule 1. `guard_ops_paths` already answers so while the pages are off.
            raise _not_found()
        address = _client_address(request)
        now = holder.get().clock()
        if refused_ops_requests.is_blocked(address, now):
            raise _too_many_requests()
        if _carries_token(request, token):
            return
        # Checked again as it is recorded: requests run in several threads.
        if not refused_ops_requests.record_unless_blocked(address, now):
            raise _too_many_requests()
        raise _not_authorized()

    @web_app.get("/", include_in_schema=False)
    def serve_catalogue() -> Response:
        return _index_response(client_dir)

    # The operator's page asks for the token itself, so it is served to anyone
    # while the operator pages are on (spec 038).
    @web_app.get("/ops", include_in_schema=False)
    def serve_ops_page() -> Response:
        if operator.token is None:
            raise _not_found()
        return _index_response(client_dir)

    @web_app.get("/r/{code}", include_in_schema=False)
    def serve_room(code: str) -> Response:
        if room_code_regex.fullmatch(code) is None:
            raise _not_found()
        return _index_response(client_dir)

    @web_app.get("/g/{number}", include_in_schema=False)
    def serve_grid(number: str) -> Response:
        _published_entry(grid_catalogue, grid_number_regex, number)
        return _index_response(client_dir)

    @web_app.get("/recap/{token}", include_in_schema=False)
    def serve_shared_recap(token: str) -> Response:
        if holder.get().shared_recap(token) is None:
            raise _not_found()
        return _index_response(client_dir)

    @web_app.get("/api/grids")
    def list_grids(
        force: Annotated[str | None, Query(pattern=FORCE_PATTERN)] = None,
    ) -> list[dict[str, object]]:
        force_number = int(force) if force is not None else None
        summaries = grid_catalogue.published_summaries(force_number)
        bodies: list[dict[str, object]] = []
        for summary in summaries:
            bodies.append(summary.model_dump(mode="json"))
        return bodies

    @web_app.get("/api/grids/{number}")
    def get_grid(number: str) -> dict[str, object]:
        entry = _published_entry(grid_catalogue, grid_number_regex, number)
        return summarize(entry).model_dump(mode="json")

    @web_app.get("/api/rooms", include_in_schema=False)
    def refuse_room_list() -> None:
        raise _not_found()

    @web_app.post("/api/rooms", status_code=201)
    def create_room(body: CreateRoomRequest, request: Request) -> CreateRoomResponse:
        entry = grid_catalogue.find_published(body.grid_number)
        if entry is None:
            raise _not_found()
        code = holder.get().register_room(entry.grid, grid_number=body.grid_number)
        base_url = str(request.base_url).rstrip("/")
        return CreateRoomResponse(code=code, share_url=f"{base_url}/r/{code}")

    # Spec 028. A wrong code counts against the throttle of the room socket, so
    # this route cannot be used to test room codes at full speed.
    @web_app.get("/api/rooms/{code}/recap")
    def get_room_recap(code: str, request: Request) -> dict[str, object]:
        room_registry = holder.get()
        address = _client_address(request)
        now = room_registry.clock()
        if wrong_codes.is_blocked(address, now):
            raise _too_many_requests()
        if room_registry.room_state(code) is None:
            # Checked again as it is recorded: requests run in several threads.
            if not wrong_codes.record_unless_blocked(address, now):
                raise _too_many_requests()
            raise _not_found()
        recap = room_registry.room_recap(code)
        if recap is None:
            raise _not_found()
        return recap.model_dump(mode="json")

    @web_app.get("/api/recaps/{token}")
    def get_shared_recap(token: str) -> dict[str, object]:
        shared = holder.get().shared_recap(token)
        if shared is None:
            raise _not_found()
        return shared.model_dump(mode="json")

    # Spec 032: the rooms a device keeps a member's token of. A room left out is
    # never said why, so this route tests no room code and is not throttled.
    @web_app.post("/api/rooms/summaries")
    def list_room_summaries(body: RoomSummariesRequest) -> list[dict[str, object]]:
        summaries: list[RoomSummary] = holder.get().room_summaries(body.rooms)
        bodies: list[dict[str, object]] = []
        for summary in summaries:
            bodies.append(summary.model_dump(mode="json"))
        return bodies

    # Spec 034: what changed in a room while a member's page was away. A 404
    # never says why, so this route is no oracle for room codes and is not
    # throttled.
    @web_app.post("/api/rooms/{code}/catch-up")
    def get_catch_up(code: str, body: CatchUpRequest) -> dict[str, object]:
        if room_code_regex.fullmatch(code) is None:
            raise _not_found()
        catch_up = holder.get().catch_up(code, body)
        if catch_up is None:
            raise _not_found()
        return catch_up.model_dump(mode="json")

    # Spec 038: the figures of the rooms created in the last `days` days, read
    # from the store without making any room live.
    @web_app.get("/api/ops/dashboard", dependencies=[Depends(check_operator)])
    def get_dashboard(
        days: Annotated[DashboardDays, Query()] = "7",
    ) -> dict[str, object]:
        room_registry = holder.get()
        now = room_registry.clock()
        period_days = int(days)
        since = now - period_days * DAY_SECONDS
        room_logs = _room_logs_since(room_registry.store, since)
        figures = dashboard_figures(room_logs, period_days, now)
        return figures.model_dump(mode="json")

    # Spec 038: the empty grid and the ordered edits of one room, from its log.
    # A 404 here is no refusal: only wrong tokens count against the address.
    @web_app.get("/api/ops/rooms/{code}/edits", dependencies=[Depends(check_operator)])
    def get_room_edits(code: str) -> dict[str, object]:
        if room_code_regex.fullmatch(code) is None:
            raise _not_found()
        room_registry = holder.get()
        state = room_registry.peek_room(code)
        if state is None:
            raise _not_found()
        entries = room_registry.store.read_log(code)
        replay = RoomReplay(
            code=code, grid=grid_view(state.grid), edits=room_edits(entries)
        )
        return replay.model_dump(mode="json")

    @web_app.get("/assets/{file_name}", include_in_schema=False)
    def serve_asset(file_name: str) -> FileResponse:
        return _file_in_directory(client_dir / "assets", file_name)

    @web_app.get("/{file_name}", include_in_schema=False)
    def serve_root_file(file_name: str) -> FileResponse:
        if file_name == "api":
            raise _not_found()
        return _file_in_directory(client_dir, file_name)

    @web_app.websocket("/api/rooms/{code}/ws")
    async def room_socket(websocket: WebSocket, code: str) -> None:
        room_registry = holder.get()
        await websocket.accept()
        address = _client_address(websocket)
        now = room_registry.clock()
        if wrong_codes.is_blocked(address, now):
            await websocket.close(code=THROTTLED_CLOSE_CODE)
            return
        # In a worker thread: the lookup may load the room from the store, or
        # delete it once expired (spec 032), and the event loop must not wait.
        state = await asyncio.to_thread(room_registry.room_state, code)
        if state is None:
            # Checked again as it is recorded: other sockets of the address may
            # have been counted while this one waited for its lookup.
            if wrong_codes.record_unless_blocked(address, now):
                await websocket.close(code=ROOM_NOT_FOUND_CLOSE_CODE)
            else:
                await websocket.close(code=THROTTLED_CLOSE_CODE)
            return
        await _serve_socket(websocket, room_registry, code)

    return web_app


def server_config(
    app: FastAPI, host: str = "127.0.0.1", port: int = 8000, log_level: str = "warning"
) -> uvicorn.Config:
    """Return the uvicorn configuration of the server.

    `ws_max_size` is WS_MAX_SIZE_BYTES: uvicorn refuses a larger frame before
    it is buffered whole, and closes the socket with 1009. `access_log` is
    False and the level defaults to "warning": uvicorn writes the client's
    address in its access log and in its info line for each socket (spec 038).
    Every other option is uvicorn's default.

    Args:
        app: The app to serve.
        host: The address the server listens on.
        port: The port the server listens on.
        log_level: The level of uvicorn's logs.

    Returns:
        The configuration to give to `uvicorn.Server`.
    """
    return uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
        ws_max_size=WS_MAX_SIZE_BYTES,
    )


app: FastAPI = create_app(catalogue=load_catalogue(GRIDS_DIR))
