"""Tests of spec 038 (privacy and operations), AC-3: what the production server logs.

`python -m nock` runs in a subprocess as spec 036's harness runs it (a SQLite file
holding a FX-01 room, `NOCK_DATABASE`, `NOCK_PORT` a free port, no `NOCK_HOST`),
plus `NOCK_OPERATOR_TOKEN=OPS_TOKEN`; its stdout and stderr go to one file. A page
on the server's origin loads `/`, then, with `page.evaluate`, opens a socket to
the stored room, joins as `Ana`, sends three `edit_letter` and a `chat`, then
requests the dashboard with a wrong token and with `OPS_TOKEN`, and
`GET /nothing-here`. The test stops the process and reads what it wrote.

The run also checks the answers it got (the snapshot, the three letters, the chat
and the statuses 401, 200 and 404), so that the log check cannot pass on a run
that never reached the paths it is about.
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

import pytest
from playwright.sync_api import Page

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Chat, EditLetter, Join
from nock.server import WEB_DIST_DIR, create_app, server_config
from nock.store import RoomStore
from spec036_harness import DATABASE_VARIABLE, HOST_VARIABLE, PORT_VARIABLE
from spec038_harness import (
    DASHBOARD_PATH,
    DATABASE_FILE_NAME,
    MISSING_BUILD_MESSAGE,
    OPERATOR_TOKEN_VARIABLE,
    OPS_TOKEN,
)

# ---- Values of the spec --------------------------------------------------------------

CHAT_TEXT = "chat-probe-5521"
MISSING_PATH = "/nothing-here"
WRONG_TOKEN = "wrong-token-of-the-probe"
# What the logs never hold (with the resume token of Ana's snapshot).
LOG_STRINGS = ["127.0.0.1", "GET /", "WebSocket /", CHAT_TEXT, OPS_TOKEN]

# ---- Values of the test harness ------------------------------------------------------

LOG_FILE_NAME = "python-m-nock.log"
SERVER_START_SECONDS = 10.0
REQUEST_TIMEOUT_SECONDS = 2.0
START_POLL_SECONDS = 0.05
PROCESS_STOP_SECONDS = 10.0

# Joins, sends the edits and the chat, waiting up to 10 seconds for each answer,
# then requests the dashboard twice and a path that does not exist.
RUN_SCRIPT = """
async (run) => {
  const { url, join, edits, chat } = run;
  const socket = new WebSocket(url);
  const received = [];
  let closeCode = null;
  socket.addEventListener("message", (event) => {
    received.push(JSON.parse(event.data));
  });
  socket.addEventListener("close", (event) => {
    closeCode = event.code;
  });
  const deadline = performance.now() + 10000;
  const waitFor = async (condition) => {
    while (!condition() && closeCode === null && performance.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  };
  const countOf = (type) => {
    return received.filter((message) => message.type === type).length;
  };
  await waitFor(() => socket.readyState === WebSocket.OPEN);
  socket.send(join);
  await waitFor(() => countOf("snapshot") >= 1);
  for (const edit of edits) {
    socket.send(edit);
  }
  await waitFor(() => countOf("letter_changed") >= edits.length);
  socket.send(chat);
  await waitFor(() => countOf("chat_message") >= 1);
  const snapshot = received.find((message) => message.type === "snapshot");
  const letters = countOf("letter_changed");
  const chats = countOf("chat_message");
  socket.close();
  const statusOf = async (path, token) => {
    const headers = token === null ? {} : { Authorization: `Bearer ${token}` };
    const response = await fetch(path, { headers });
    return response.status;
  };
  return {
    resumeToken: snapshot === undefined ? null : snapshot.resume_token,
    letters,
    chats,
    wrongStatus: await statusOf(run.dashboardPath, run.wrongToken),
    rightStatus: await statusOf(run.dashboardPath, run.rightToken),
    missingStatus: await statusOf(run.missingPath, null),
  };
}
"""


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


# ---- The production server in a subprocess -------------------------------------------


def database_with_room(path: Path, grid: Grid) -> str:
    """Write a SQLite file at `path` holding one room on `grid`; return its code."""
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
    """The test's environment, plus NOCK_DATABASE, NOCK_PORT and the operator token.

    NOCK_HOST is deleted.
    """
    environment = dict(os.environ)
    environment.pop(HOST_VARIABLE, None)
    environment[DATABASE_VARIABLE] = str(database)
    environment[PORT_VARIABLE] = str(port)
    environment[OPERATOR_TOKEN_VARIABLE] = OPS_TOKEN
    return environment


def process_output(log_path: Path) -> str:
    """What the process wrote on stdout and stderr so far."""
    return log_path.read_text(encoding="utf-8", errors="replace")


def wait_for_first_answer(
    process: subprocess.Popen[bytes], url: str, log_path: Path
) -> None:
    """Poll GET `url` until the server answers, for up to 10 seconds, else fail."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + SERVER_START_SECONDS
    while True:
        exit_status = process.poll()
        if exit_status is not None:
            pytest.fail(
                f"python -m nock ended with status {exit_status} before answering "
                f"GET {url}:\n{process_output(log_path)}"
            )
        try:
            with opener.open(url, timeout=REQUEST_TIMEOUT_SECONDS):
                return
        except urllib.error.HTTPError:
            return  # an answer all the same
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


@contextlib.contextmanager
def nock_process(database: Path, log_path: Path) -> Generator[str]:
    """Run `python -m nock` on `database` and a free port; yield its base URL.

    Its stdout and stderr go to `log_path`. The process is stopped at the end.
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
            wait_for_first_answer(process, f"{base_url}/", log_path)
            yield base_url
        finally:
            stop_process(process)


# ---- AC-3: the logs hold no address, no request line and no secret -----------------


def test_ac3_python_m_nock_logs_no_address_no_request_line_and_no_secret(
    page: Page, fx01_grid: Grid, tmp_path: Path
) -> None:
    database = tmp_path / DATABASE_FILE_NAME
    code = database_with_room(database, fx01_grid)
    log_path = tmp_path / LOG_FILE_NAME
    edits: list[str] = []
    for column, letter in enumerate("TAM"):
        edits.append(EditLetter(row=1, column=column, letter=letter).model_dump_json())
    arguments = {
        "join": Join(nickname="Ana", resume_token=None).model_dump_json(),
        "edits": edits,
        "chat": Chat(text=CHAT_TEXT).model_dump_json(),
        "dashboardPath": DASHBOARD_PATH,
        "wrongToken": WRONG_TOKEN,
        "rightToken": OPS_TOKEN,
        "missingPath": MISSING_PATH,
    }

    with nock_process(database, log_path) as base_url:
        page.goto(f"{base_url}/")
        socket_url = base_url.replace("http://", "ws://", 1) + f"/api/rooms/{code}/ws"
        run = page.evaluate(RUN_SCRIPT, {"url": socket_url, **arguments})
    output = process_output(log_path)

    resume_token = run["resumeToken"]
    assert isinstance(resume_token, str), run
    found: list[str] = []
    for text in [*LOG_STRINGS, resume_token]:
        if text in output:
            found.append(text)
    assert found == [], output
    # The run reached every path it is about.
    assert (run["letters"], run["chats"]) == (3, 1), run
    statuses = (run["wrongStatus"], run["rightStatus"], run["missingStatus"])
    assert statuses == (401, 200, 404), run


# ---- AC-3: server_config -------------------------------------------------------------


def test_ac3_server_config_turns_the_access_log_off(tmp_path: Path) -> None:
    config = server_config(create_app(dist_dir=tmp_path))

    assert config.access_log is False


def test_ac3_server_config_logs_at_warning_by_default(tmp_path: Path) -> None:
    config = server_config(create_app(dist_dir=tmp_path))

    assert config.log_level == "warning"


def test_ac3_server_config_turns_the_access_log_off_at_any_level(
    tmp_path: Path,
) -> None:
    config = server_config(create_app(dist_dir=tmp_path), log_level="info")

    assert config.access_log is False
