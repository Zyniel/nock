"""Tests of spec 036 (performance), AC-8 and AC-9: the production entry point.

AC-8 and AC-9 run `python -m nock` in a subprocess on a SQLite file holding a
FX-01 room, and talk to it from a page in every engine. The tests of AC-10 to
AC-12, which call `nock.__main__.main()` in the test process, are in
`test_spec_036_ac10_ac12_variables.py`.

The shared setup is in `spec036_harness` and `spec036_frames_harness`. What
only this file uses is defined below the imports.

Notes:

- AC-8 and AC-9 release their free port before `python -m nock` binds it, as the
  harness says; the process is terminated, then killed, at the end of the test.
- The process gets the test's own environment with NOCK_DATABASE and NOCK_PORT
  set and NOCK_HOST deleted, as the harness says.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Generator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Page

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Join, Snapshot, grid_view, parse_server_message
from nock.server import WEB_DIST_DIR
from nock.store import RoomStore
from spec036_frames_harness import (
    OVERSIZED_FRAME_SCRIPT,
    TOO_BIG_CODE,
    padded_frame,
    socket_url,
)
from spec036_harness import DATABASE_VARIABLE, HOST_VARIABLE, PORT_VARIABLE

# The fixtures of the harness. pytest looks for a test's fixtures among the names of
# its module, so they are imported by name. `x as x` is the explicit re-export
# form: it keeps ruff from reporting the import as unused or as redefined.
from spec036_harness import fx01_grid as fx01_grid

# ---- Values of the spec --------------------------------------------------------------

OVERSIZED_FRAME_BYTES = 9000  # AC-9's frame


# ---- Values of the test harness ------------------------------------------------------

MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"

SERVER_START_SECONDS = 10.0  # also how long AC-8 and AC-9 poll GET /

DATABASE_FILE_NAME = "nock.sqlite3"
LOG_FILE_NAME = "python-m-nock.log"
REQUEST_TIMEOUT_SECONDS = 2.0
START_POLL_SECONDS = 0.05
PROCESS_STOP_SECONDS = 10.0


# ---- The production entry point in a subprocess (AC-8, AC-9) -------------------------


def database_with_room(path: Path, grid: Grid) -> str:
    """Write a SQLite file at `path` holding one room on `grid`; return its code.

    The room is registered by `RoomRegistry(store=RoomStore(path))`; then the
    registry, then the store, are closed.
    """
    store = RoomStore(path)
    registry = RoomRegistry(store=store)
    code = registry.register_room(grid)
    registry.close()
    store.close()
    return code


def free_local_port() -> int:
    """A free port of 127.0.0.1: bound with port 0, then released."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


def nock_environment(database: Path, port: int) -> dict[str, str]:
    """The test's own environment plus NOCK_DATABASE and NOCK_PORT, no NOCK_HOST."""
    environment = dict(os.environ)
    environment.pop(HOST_VARIABLE, None)
    environment[DATABASE_VARIABLE] = str(database)
    environment[PORT_VARIABLE] = str(port)
    return environment


class HttpAnswer(NamedTuple):
    """The status and the body of an HTTP answer."""

    status: int
    body: bytes


def get_directly(url: str) -> HttpAnswer:
    """GET `url` without the proxies of the environment; return the answer.

    Raises:
        OSError: nothing answered (connection refused or reset, timeout).
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return HttpAnswer(status=response.status, body=response.read())
    except urllib.error.HTTPError as error:
        return HttpAnswer(status=error.code, body=error.read())


def process_output(log_path: Path) -> str:
    """What the process wrote on stdout and stderr so far."""
    return log_path.read_text(encoding="utf-8", errors="replace")


def wait_for_first_answer(
    process: subprocess.Popen[bytes], url: str, log_path: Path
) -> HttpAnswer:
    """Poll GET `url` until the server answers, for up to 10 seconds.

    Fails the test when the process ends first, or when nothing answers in time.
    """
    deadline = time.monotonic() + SERVER_START_SECONDS
    while True:
        exit_status = process.poll()
        if exit_status is not None:
            pytest.fail(
                f"python -m nock ended with status {exit_status} before answering "
                f"GET {url}:\n{process_output(log_path)}"
            )
        try:
            return get_directly(url)
        except OSError as error:
            if time.monotonic() >= deadline:
                pytest.fail(
                    f"python -m nock did not answer GET {url} within "
                    f"{SERVER_START_SECONDS:.0f} s ({error}):\n"
                    f"{process_output(log_path)}"
                )
        time.sleep(START_POLL_SECONDS)


def stop_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate the process, then kill it when it has not ended in 10 seconds."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=PROCESS_STOP_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=PROCESS_STOP_SECONDS)


class NockServer(NamedTuple):
    """A running `python -m nock`: its base URL and its first answer to GET /."""

    base_url: str
    first_answer: HttpAnswer


@contextlib.contextmanager
def nock_process(database: Path, log_path: Path) -> Generator[NockServer]:
    """Run `python -m nock` on the SQLite file `database`, on a free port.

    Runs `[sys.executable, "-m", "nock"]` with the environment of
    `nock_environment`, its output going to `log_path`, and yields once GET /
    got an answer. Fails (not skips) when the client is not built. The process
    is terminated at the end, then killed if it does not stop.
    """
    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)
    port = free_local_port()
    base_url = f"http://127.0.0.1:{port}"
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "nock"],
            env=nock_environment(database, port),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            first_answer = wait_for_first_answer(process, f"{base_url}/", log_path)
            yield NockServer(base_url=base_url, first_answer=first_answer)
        finally:
            stop_process(process)


# Opens a socket and sends a join as soon as it is open; reports the first
# message it received, or the close that came instead. Gives up after 5 seconds.
FIRST_MESSAGE_SCRIPT = """
async ({ url, join }) => {
  const socket = new WebSocket(url);
  let firstMessage = null;
  let closeCode = null;
  socket.addEventListener("message", (event) => {
    if (firstMessage === null) {
      firstMessage = typeof event.data === "string" ? event.data : "(binary)";
    }
  });
  socket.addEventListener("close", (event) => {
    closeCode = event.code;
  });
  const deadline = performance.now() + 5000;
  const waitFor = async (condition) => {
    while (!condition() && closeCode === null && performance.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  };
  await waitFor(() => socket.readyState === WebSocket.OPEN);
  const opened = socket.readyState === WebSocket.OPEN;
  if (opened) {
    socket.send(join);
    await waitFor(() => firstMessage !== null);
  }
  const closeCodeBefore = closeCode;
  socket.close();
  return { opened, firstMessage, closeCode: closeCodeBefore };
}
"""


# ---- AC-8: python -m nock serves the app on the port of NOCK_PORT -----------------


def test_ac8_python_m_nock_answers_get_with_the_built_client_on_nock_port(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    database = tmp_path / DATABASE_FILE_NAME
    database_with_room(database, fx01_grid)

    with nock_process(database, tmp_path / LOG_FILE_NAME) as server:
        answer = server.first_answer

    built_client = (WEB_DIST_DIR / "index.html").read_bytes()
    assert answer.status == 200
    assert answer.body == built_client


def test_ac8_a_join_on_the_room_of_nock_database_gets_a_snapshot_first(
    page: Page, fx01_grid: Grid, tmp_path: Path
) -> None:
    database = tmp_path / DATABASE_FILE_NAME
    code = database_with_room(database, fx01_grid)
    join = Join(nickname="Ana", resume_token=None).model_dump_json()

    with nock_process(database, tmp_path / LOG_FILE_NAME) as server:
        page.goto(f"{server.base_url}/")
        arguments = {"url": socket_url(server.base_url, code), "join": join}
        result = page.evaluate(FIRST_MESSAGE_SCRIPT, arguments)

    assert result["opened"] is True
    first_message = result["firstMessage"]
    assert first_message is not None, f"no message, closed with {result['closeCode']}"
    snapshot = parse_server_message(first_message)
    assert isinstance(snapshot, Snapshot), snapshot
    assert snapshot.grid == grid_view(fx01_grid)


# ---- AC-9: python -m nock refuses oversized frames at the socket ------------------


def test_ac9_python_m_nock_closes_a_socket_sending_9000_bytes_with_1009(
    page: Page, fx01_grid: Grid, tmp_path: Path
) -> None:
    database = tmp_path / DATABASE_FILE_NAME
    code = database_with_room(database, fx01_grid)
    frame = padded_frame(OVERSIZED_FRAME_BYTES)
    assert len(frame.encode("utf-8")) == OVERSIZED_FRAME_BYTES

    with nock_process(database, tmp_path / LOG_FILE_NAME) as server:
        page.goto(f"{server.base_url}/")
        arguments = {
            "url": socket_url(server.base_url, code),
            "frame": frame,
            "binary": False,
        }
        result = page.evaluate(OVERSIZED_FRAME_SCRIPT, arguments)

    assert result["opened"] is True
    assert result["closeCode"] == TOO_BIG_CODE
    assert result["received"] == []
