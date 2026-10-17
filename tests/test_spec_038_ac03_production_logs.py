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

In process ("In-process logs" of the spec's "Test harness"), the same steps run
on `TestClient(app, client=("127.0.0.1", 50000))`, with the `nock` loggers at
`DEBUG`, and no `nock.*` record may hold any of those strings: a record holds a
string when the text of `logging.Formatter().format(record)`, its traceback
included, holds it. That session checks its answers the same way.
"""

from __future__ import annotations

import contextlib
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Generator, Sequence
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page
from starlette.testclient import WebSocketTestSession

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    Chat,
    ChatMessage,
    EditLetter,
    Join,
    LetterChanged,
    Snapshot,
    parse_server_message,
)
from nock.server import WEB_DIST_DIR, create_app, server_config
from nock.store import RoomStore
from spec012_harness import receive_text_or_fail, socket_url
from spec036_harness import DATABASE_VARIABLE, HOST_VARIABLE, PORT_VARIABLE
from spec038_harness import (
    DASHBOARD_PATH,
    DATABASE_FILE_NAME,
    MISSING_BUILD_MESSAGE,
    OPERATOR_TOKEN_VARIABLE,
    OPS_TOKEN,
    bearer,
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
# "In-process logs": the client's address is the 127.0.0.1 searched for.
IN_PROCESS_CLIENT = ("127.0.0.1", 50000)
INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
EDITED_LETTERS = "TAM"  # three edit_letter, from (1, 0) across
MAX_MESSAGES_READ = 50  # the session reads no more than that many messages

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


# ---- AC-3: the app's own records at DEBUG, in process --------------------------------


class InProcessRun(NamedTuple):
    """What the in-process session got back, to show it reached every path."""

    resume_token: str  # that of Ana's snapshot
    letters: int  # letter_changed received
    chats: int  # chat_message received
    statuses: tuple[int, int, int, int]  # GET /, wrong token, OPS_TOKEN, unknown


def next_snapshot(websocket: WebSocketTestSession) -> Snapshot:
    """Read the socket's messages until the snapshot of the join; return it."""
    for _ in range(MAX_MESSAGES_READ):
        message = parse_server_message(receive_text_or_fail(websocket))
        if isinstance(message, Snapshot):
            return message
    pytest.fail(f"no snapshot in the first {MAX_MESSAGES_READ} messages")


def join_and_play(client: TestClient, code: str) -> tuple[str, int, int]:
    """Join room `code` as Ana, send three `edit_letter` and a `chat`.

    Returns:
        The resume token of Ana's snapshot, then how many `letter_changed` and
        `chat_message` came back before the chat's (included).
    """
    with client.websocket_connect(socket_url(code)) as websocket:
        websocket.send_text(Join(nickname="Ana", resume_token=None).model_dump_json())
        snapshot = next_snapshot(websocket)
        for column, letter in enumerate(EDITED_LETTERS):
            edit = EditLetter(row=1, column=column, letter=letter)
            websocket.send_text(edit.model_dump_json())
        websocket.send_text(Chat(text=CHAT_TEXT).model_dump_json())
        letters = 0
        chats = 0
        for _ in range(MAX_MESSAGES_READ):
            message = parse_server_message(receive_text_or_fail(websocket))
            if isinstance(message, LetterChanged):
                letters += 1
            elif isinstance(message, ChatMessage):
                chats += 1
                break
    return snapshot.resume_token, letters, chats


def run_in_process_session(client: TestClient, code: str) -> InProcessRun:
    """The steps of AC-3: `GET /`, the room's socket, the dashboard twice, a 404."""
    home = client.get("/")
    resume_token, letters, chats = join_and_play(client, code)
    wrong = client.get(DASHBOARD_PATH, headers=bearer(WRONG_TOKEN))
    right = client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))
    missing = client.get(MISSING_PATH)
    return InProcessRun(
        resume_token=resume_token,
        letters=letters,
        chats=chats,
        statuses=(
            home.status_code,
            wrong.status_code,
            right.status_code,
            missing.status_code,
        ),
    )


def nock_record_texts(records: Sequence[logging.LogRecord]) -> list[str]:
    """The text of each record of the `nock` loggers, traceback included."""
    formatter = logging.Formatter()
    texts: list[str] = []
    for record in records:
        if record.name == "nock" or record.name.startswith("nock."):
            texts.append(formatter.format(record))
    return texts


def records_holding(record_texts: list[str], strings: list[str]) -> list[str]:
    """For each string held by a record text, `<string>: <that record's text>`."""
    found: list[str] = []
    for searched in strings:
        for record_text in record_texts:
            if searched in record_text:
                found.append(f"{searched}: {record_text}")
    return found


def test_ac3_in_process_no_nock_record_at_debug_holds_an_address_or_a_secret(
    caplog: pytest.LogCaptureFixture, fx01_grid: Grid, tmp_path: Path
) -> None:
    caplog.set_level(logging.DEBUG, logger="nock")
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    registry = RoomRegistry()
    try:
        code = registry.register_room(fx01_grid)
        app = create_app(rooms=registry, dist_dir=tmp_path, operator_token=OPS_TOKEN)
        with TestClient(app, client=IN_PROCESS_CLIENT) as client:
            run = run_in_process_session(client, code)
    finally:
        registry.close()

    record_texts = nock_record_texts(caplog.records)
    assert records_holding(record_texts, [*LOG_STRINGS, run.resume_token]) == []
    # The session reached every path it is about.
    assert (run.letters, run.chats) == (len(EDITED_LETTERS), 1), run
    assert run.statuses == (200, 401, 200, 404), run


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
