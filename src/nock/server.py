"""FastAPI app: serves the built web client and the room WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import re
import threading
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nock.catalogue import (
    GRIDS_DIR,
    Catalogue,
    CatalogueEntry,
    load_catalogue,
    summarize,
)
from nock.hub import SESSION_REPLACED_CLOSE_CODE, RoomConnection, RoomRegistry
from nock.protocol import parse_client_message

__all__ = ["SESSION_REPLACED_CLOSE_CODE", "RoomRegistry", "create_app"]

WEB_DIST_DIR: Path = Path(__file__).resolve().parents[2] / "web" / "dist"
ROOM_CODE_PATTERN: str = r"^[A-Z0-9]{6}$"
GRID_NUMBER_PATTERN: str = r"^[1-9][0-9]{0,8}$"
FORCE_PATTERN: str = r"^[1-4]$"
ROOM_NOT_FOUND_CLOSE_CODE: int = 4404  # WebSocket close code, unknown room
THROTTLED_CLOSE_CODE: int = 4429  # WebSocket close code, too many wrong codes
WRONG_CODE_LIMIT: int = 10
WRONG_CODE_WINDOW_SECONDS: float = 60.0

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


class _WrongCodeThrottle:
    """Remembers the wrong room codes of each client address, in memory.

    The sockets run on several threads, so every access takes the lock.
    """

    def __init__(self) -> None:
        """Create a throttle with no failure."""
        self._lock = threading.Lock()
        self._failure_times: dict[str, list[float]] = {}

    def is_blocked(self, address: str, now: float) -> bool:
        """Tell whether `address` has too many recent wrong codes."""
        with self._lock:
            recent = self._forget_old_failures(address, now)
            return len(recent) >= WRONG_CODE_LIMIT

    def record_failure(self, address: str, now: float) -> None:
        """Remember one wrong code from `address` at time `now`."""
        with self._lock:
            recent = self._forget_old_failures(address, now)
            recent.append(now)
            self._failure_times[address] = recent

    def _forget_old_failures(self, address: str, now: float) -> list[float]:
        """Drop the failures of `address` outside the window; return the rest.

        An address with no failure left has no entry. The caller holds the lock.
        """
        recent: list[float] = []
        for failure_time in self._failure_times.get(address, []):
            if failure_time > now - WRONG_CODE_WINDOW_SECONDS:
                recent.append(failure_time)
        if recent:
            self._failure_times[address] = recent
        else:
            self._failure_times.pop(address, None)
        return recent


def _not_found() -> HTTPException:
    """Return the 404 error with FastAPI's usual body."""
    return HTTPException(status_code=404, detail="Not Found")


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


def create_app(
    rooms: RoomRegistry | None = None,
    dist_dir: Path | None = None,
    catalogue: Catalogue | None = None,
) -> FastAPI:
    """Build the app.

    Args:
        rooms: The rooms the WebSocket serves. None: a new empty registry.
        dist_dir: The built client. None: WEB_DIST_DIR.
        catalogue: The grids served. None: an empty catalogue.

    Never raises because `dist_dir` is missing or empty (see AC-6).
    """
    room_registry = rooms if rooms is not None else RoomRegistry()
    client_dir = dist_dir if dist_dir is not None else WEB_DIST_DIR
    grid_catalogue = catalogue if catalogue is not None else Catalogue()
    room_code_regex = re.compile(ROOM_CODE_PATTERN)
    grid_number_regex = re.compile(GRID_NUMBER_PATTERN)
    wrong_codes = _WrongCodeThrottle()
    # No slash redirect: a path ending with "/" matches no route and is a 404.
    web_app = FastAPI(
        redirect_slashes=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @web_app.get("/", include_in_schema=False)
    def serve_catalogue() -> Response:
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
        code = room_registry.register_room(entry.grid, grid_number=body.grid_number)
        base_url = str(request.base_url).rstrip("/")
        return CreateRoomResponse(code=code, share_url=f"{base_url}/r/{code}")

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
        await websocket.accept()
        address = websocket.client.host if websocket.client is not None else "unknown"
        now = room_registry.clock()
        if wrong_codes.is_blocked(address, now):
            await websocket.close(code=THROTTLED_CLOSE_CODE)
            return
        if room_registry.room_state(code) is None:
            wrong_codes.record_failure(address, now)
            await websocket.close(code=ROOM_NOT_FOUND_CLOSE_CODE)
            return
        await _serve_socket(websocket, room_registry, code)

    return web_app


app: FastAPI = create_app(catalogue=load_catalogue(GRIDS_DIR))
