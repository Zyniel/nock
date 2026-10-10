"""FastAPI app: serves the built web client and the room WebSocket."""

from __future__ import annotations

import re
import secrets
import string
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, WebSocket
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import ValidationError

from nock.grid import Grid
from nock.protocol import (
    ErrorCode,
    ErrorMessage,
    HelpMode,
    Join,
    RevealBudget,
    RoomSettings,
    Snapshot,
    grid_view,
    parse_client_message,
)

WEB_DIST_DIR: Path = Path(__file__).resolve().parents[2] / "web" / "dist"
ROOM_CODE_PATTERN: str = r"^[A-Z0-9]{6}$"
ROOM_NOT_FOUND_CLOSE_CODE: int = 4404  # WebSocket close code, unknown room

_ROOM_CODE_LENGTH = 6
_ROOM_CODE_ALPHABET = string.ascii_uppercase + string.digits
_MISSING_BUILD_TEXT = "The web client is not built: run npm --prefix web run build"


class RoomRegistry:
    """In-memory rooms of this process, by room code.

    A seam for tests until spec 011 (room creation) replaces or extends it.
    A plain class, not a Pydantic model: it is a mutable service, not data.
    """

    def __init__(self) -> None:
        """Create a registry with no room."""
        self._grids_by_code: dict[str, Grid] = {}

    def register_room(self, grid: Grid) -> str:
        """Register a new room on `grid` and return its fresh room code.

        The code matches ROOM_CODE_PATTERN and differs from every code already
        registered in this registry.
        """
        code = self._draw_code()
        while code in self._grids_by_code:
            code = self._draw_code()
        self._grids_by_code[code] = grid
        return code

    def find_room(self, code: str) -> Grid | None:
        """Return the grid of the room `code`, or None when it is not registered."""
        return self._grids_by_code.get(code)

    def _draw_code(self) -> str:
        """Return a random room code, which may already be taken."""
        letters: list[str] = []
        for _ in range(_ROOM_CODE_LENGTH):
            letters.append(secrets.choice(_ROOM_CODE_ALPHABET))
        return "".join(letters)


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


def _snapshot_for(grid: Grid) -> Snapshot:
    """Build the snapshot of a fresh room on `grid` for a new connection."""
    budget = RevealBudget(letters=5, words=1)
    settings = RoomSettings(help_mode=HelpMode.FREE, reveal_budget=budget, locked=False)
    return Snapshot(
        seq=0,
        you=secrets.token_urlsafe(8),
        resume_token=secrets.token_urlsafe(24),
        grid=grid_view(grid),
        players=(),
        settings=settings,
        reveal_budget=budget,
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )


async def _wait_for_join(websocket: WebSocket) -> bool:
    """Read client messages until a Join arrives, answering the others.

    Returns:
        True when a Join was received, False when the client disconnected.
    """
    while True:
        frame = await websocket.receive()
        if frame["type"] == "websocket.disconnect":
            return False
        raw_message = frame.get("text")
        if raw_message is None:
            raw_message = frame.get("bytes", b"")
        try:
            message = parse_client_message(raw_message)
        except ValidationError:
            error = ErrorMessage(
                code=ErrorCode.INVALID_MESSAGE,
                message="The message is not a valid client message.",
            )
            await websocket.send_text(error.model_dump_json())
            continue
        if isinstance(message, Join):
            return True
        error = ErrorMessage(
            code=ErrorCode.NOT_JOINED,
            message="Send a join message before anything else.",
        )
        await websocket.send_text(error.model_dump_json())


async def _ignore_until_disconnect(websocket: WebSocket) -> None:
    """Read and drop every frame until the client disconnects."""
    while True:
        frame = await websocket.receive()
        if frame["type"] == "websocket.disconnect":
            return


def create_app(
    rooms: RoomRegistry | None = None, dist_dir: Path | None = None
) -> FastAPI:
    """Build the app.

    Args:
        rooms: The rooms the WebSocket serves. None: a new empty registry.
        dist_dir: The built client. None: WEB_DIST_DIR.

    Never raises because `dist_dir` is missing or empty (see AC-6).
    """
    room_registry = rooms if rooms is not None else RoomRegistry()
    client_dir = dist_dir if dist_dir is not None else WEB_DIST_DIR
    room_code_regex = re.compile(ROOM_CODE_PATTERN)
    # No slash redirect: a path ending with "/" matches no route and is a 404.
    web_app = FastAPI(redirect_slashes=False)

    @web_app.get("/", include_in_schema=False)
    def serve_catalogue() -> Response:
        return _index_response(client_dir)

    @web_app.get("/r/{code}", include_in_schema=False)
    def serve_room(code: str) -> Response:
        if room_code_regex.fullmatch(code) is None:
            raise _not_found()
        return _index_response(client_dir)

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
        grid = room_registry.find_room(code)
        if grid is None:
            await websocket.close(code=ROOM_NOT_FOUND_CLOSE_CODE)
            return
        has_joined = await _wait_for_join(websocket)
        if not has_joined:
            return
        await websocket.send_text(_snapshot_for(grid).model_dump_json())
        await _ignore_until_disconnect(websocket)

    return web_app


app: FastAPI = create_app()
