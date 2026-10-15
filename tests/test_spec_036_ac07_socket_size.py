"""Tests of spec 036 (performance), AC-7: the size of a frame at the socket.

AC-7 checks `server_config`, then the frame size limit on a live server built with
it, in every engine.

The shared setup is in `spec036_harness` and `spec036_frames_harness`. What
only this file uses is defined below the imports.

Notes:

- conftest's `live_server` is built with `server_config` (spec decision 9, in a
  commit after the implementer's), so AC-7's live checks use it. They would
  fail if it went back to uvicorn's default `ws_max_size`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import Page

import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ErrorCode,
    ErrorMessage,
    Join,
    Pong,
    ServerMessage,
    Snapshot,
    parse_server_message,
)
from nock.server import create_app
from spec036_frames_harness import (
    MAX_WS_FRAME_BYTES,
    OVERSIZED_FRAME_SCRIPT,
    TOO_BIG_CODE,
    padded_frame,
    socket_url,
)

# The fixtures of the harness. pytest looks for a test's fixtures among the names of
# its module, so they are imported by name. `x as x` is the explicit re-export
# form: it keeps ruff from reporting the import as unused or as redefined.
from spec036_harness import fx01_grid as fx01_grid

# ---- Scripts and options of the live checks ------------------------------------------

# Opens a socket, joins, sends one big frame, then a ping, waiting up to 5
# seconds for an answer to each; reports what arrived and the socket's state.
ANSWERED_FRAME_SCRIPT = """
async ({ url, join, frame, binary }) => {
  const socket = new WebSocket(url);
  const received = [];
  let closeCode = null;
  socket.addEventListener("message", (event) => received.push(event.data));
  socket.addEventListener("close", (event) => {
    closeCode = event.code;
  });
  const waitFor = async (condition) => {
    const deadline = performance.now() + 5000;
    while (!condition() && closeCode === null && performance.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  };
  await waitFor(() => socket.readyState === WebSocket.OPEN);
  socket.send(join);
  await waitFor(() => received.length >= 1);
  const afterJoin = received.length;
  socket.send(binary ? new TextEncoder().encode(frame) : frame);
  await waitFor(() => received.length > afterJoin);
  const afterFrame = received.length;
  socket.send(JSON.stringify({ type: "ping" }));
  await waitFor(() => received.length > afterFrame);
  const readyState = socket.readyState;
  const closeCodeBefore = closeCode;
  socket.close();
  return { received, readyState, closeCode: closeCodeBefore };
}
"""

# uvicorn options that `server_config` leaves at uvicorn's default.
UVICORN_DEFAULT_OPTIONS = (
    "ws",
    "ws_max_queue",
    "ws_ping_interval",
    "ws_ping_timeout",
    "ws_per_message_deflate",
    "http",
    "lifespan",
    "interface",
    "proxy_headers",
    "timeout_keep_alive",
    "limit_concurrency",
    "backlog",
    "root_path",
)


# ---- AC-7: oversized frames are refused at the socket -----------------------------


def test_ac7_ws_max_size_bytes_is_8192() -> None:
    assert nock.server.WS_MAX_SIZE_BYTES == MAX_WS_FRAME_BYTES


def test_ac7_server_config_limits_frames_to_ws_max_size_bytes(tmp_path: Path) -> None:
    app = create_app(dist_dir=tmp_path)

    config = nock.server.server_config(app)

    assert isinstance(config, uvicorn.Config)
    assert config.app is app
    assert config.ws_max_size == nock.server.WS_MAX_SIZE_BYTES == MAX_WS_FRAME_BYTES


def test_ac7_server_config_defaults_to_127_0_0_1_port_8000_and_info(
    tmp_path: Path,
) -> None:
    config = nock.server.server_config(create_app(dist_dir=tmp_path))

    assert (config.host, config.port, config.log_level) == ("127.0.0.1", 8000, "info")


def test_ac7_server_config_uses_the_host_port_and_log_level_it_is_given(
    tmp_path: Path,
) -> None:
    app = create_app(dist_dir=tmp_path)

    config = nock.server.server_config(
        app, host="0.0.0.0", port=9123, log_level="warning"
    )

    assert (config.host, config.port, config.log_level) == ("0.0.0.0", 9123, "warning")
    assert config.ws_max_size == MAX_WS_FRAME_BYTES


def test_ac7_server_config_leaves_every_other_option_at_uvicorns_default(
    tmp_path: Path,
) -> None:
    app = create_app(dist_dir=tmp_path)

    config = nock.server.server_config(app)
    default = uvicorn.Config(app)

    configured: dict[str, object] = {}
    expected: dict[str, object] = {}
    for option in UVICORN_DEFAULT_OPTIONS:
        configured[option] = getattr(config, option)
        expected[option] = getattr(default, option)
    assert configured == expected


@pytest.mark.parametrize("size", [MAX_WS_FRAME_BYTES + 1, 9000])
@pytest.mark.parametrize("binary", [False, True], ids=["text", "binary"])
def test_ac7_a_frame_over_8192_bytes_closes_the_socket_with_1009(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    size: int,
    binary: bool,
) -> None:
    code = room_registry.register_room(fx01_grid)
    frame = padded_frame(size)
    assert len(frame.encode("utf-8")) == size
    page.goto(f"{live_server}/")
    arguments = {
        "url": socket_url(live_server, code),
        "frame": frame,
        "binary": binary,
    }

    result = page.evaluate(OVERSIZED_FRAME_SCRIPT, arguments)

    assert result["opened"] is True
    assert result["closeCode"] == TOO_BIG_CODE
    assert result["received"] == []


@pytest.mark.parametrize("size", [8000, MAX_WS_FRAME_BYTES])
@pytest.mark.parametrize("binary", [False, True], ids=["text", "binary"])
def test_ac7_a_frame_of_4097_to_8192_bytes_gets_invalid_message_and_stays_open(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    size: int,
    binary: bool,
) -> None:
    code = room_registry.register_room(fx01_grid)
    frame = padded_frame(size)
    assert len(frame.encode("utf-8")) == size
    join = Join(nickname="Ana", resume_token=None).model_dump_json()
    page.goto(f"{live_server}/")
    arguments = {
        "url": socket_url(live_server, code),
        "join": join,
        "frame": frame,
        "binary": binary,
    }

    result = page.evaluate(ANSWERED_FRAME_SCRIPT, arguments)

    received: list[ServerMessage] = []
    for text in result["received"]:
        received.append(parse_server_message(text))
    assert len(received) == 3, received
    assert isinstance(received[0], Snapshot)
    refusal = received[1]
    assert isinstance(refusal, ErrorMessage), refusal
    assert refusal.code is ErrorCode.INVALID_MESSAGE
    assert received[2] == Pong()
    assert result["closeCode"] is None
    assert result["readyState"] == 1
