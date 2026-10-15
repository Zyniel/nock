"""Tests of spec 036 (performance), AC-8 to AC-11: the production entry point.

AC-8 and AC-9 run `python -m nock` in a subprocess on a SQLite file holding a
FX-01 room, and talk to it from a page in every engine. AC-10 and AC-11 call
`nock.__main__.main()` in the test process, with `uvicorn.Server.run` replaced by
the harness's recorder.

The shared setup is in `spec036_harness` and `spec036_frames_harness`. What
only this file uses is defined below the imports.

Notes:

- Each test of AC-10 and AC-11 imports `nock.__main__` itself, once the recorder
  is in place: a missing module then fails those tests only, not the collection
  of this file, and an import that started a server could not block the run.
  `uvicorn.Server.serve` is replaced as well, so that a server started without
  `run` fails the test instead of serving.
- AC-8 and AC-9 release their free port before `python -m nock` binds it, as the
  harness says; the process is terminated, then killed, at the end of the test.
- Edge cases checked as well: for `main()`, each variable empty or unset on its
  own, leading zeros and the bounds of NOCK_PORT, NOCK_HOST passed on as given,
  the variables read at each call, an import that runs nothing, signs, spaces,
  underscores and digits outside ASCII in NOCK_PORT, and the message and status 1
  of `python -m nock` with an invalid port.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Generator
from pathlib import Path
from typing import NamedTuple

import pytest
import uvicorn
from playwright.sync_api import Page

import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Join, Snapshot, grid_view, parse_server_message
from nock.server import WEB_DIST_DIR
from nock.store import RoomStore
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

# ---- Values of the spec --------------------------------------------------------------

OVERSIZED_FRAME_BYTES = 9000  # AC-9's frame

HOST_VARIABLE = "NOCK_HOST"
PORT_VARIABLE = "NOCK_PORT"
DATABASE_VARIABLE = "NOCK_DATABASE"  # spec 018
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
SERVER_LOG_LEVEL = "info"  # server_config's default, which main() keeps

# Digits outside ASCII, which NOCK_PORT refuses (int() reads the first two as 8000;
# str.isdigit() takes all three).
FULLWIDTH_8000 = "\N{FULLWIDTH DIGIT EIGHT}" + "\N{FULLWIDTH DIGIT ZERO}" * 3
ARABIC_INDIC_8000 = "\N{ARABIC-INDIC DIGIT EIGHT}" + "\N{ARABIC-INDIC DIGIT ZERO}" * 3
SUPERSCRIPT_TWO = "\N{SUPERSCRIPT TWO}"


# ---- Values of the test harness ------------------------------------------------------

MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"

SERVER_START_SECONDS = 10.0  # also how long AC-8 and AC-9 poll GET /

DATABASE_FILE_NAME = "nock.sqlite3"
LOG_FILE_NAME = "python-m-nock.log"
REQUEST_TIMEOUT_SECONDS = 2.0
START_POLL_SECONDS = 0.05
PROCESS_STOP_SECONDS = 10.0
PROCESS_EXIT_LIMIT_SECONDS = 30.0


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


# ---- The production entry point in the test process (AC-10, AC-11) -------------------


@pytest.fixture
def server_runs(monkeypatch: pytest.MonkeyPatch) -> list[uvicorn.Config]:
    """Replace `uvicorn.Server.run` by the harness's recorder; return what it keeps.

    The recorder keeps the `config` of each server whose `run` is called and
    returns None. `uvicorn.Server.serve` is replaced too, so that a server
    started without `run` fails the test instead of serving in it.
    """
    configs: list[uvicorn.Config] = []

    def record_run(
        server: uvicorn.Server, sockets: list[socket.socket] | None = None
    ) -> None:
        configs.append(server.config)

    async def refuse_serve(
        server: uvicorn.Server, sockets: list[socket.socket] | None = None
    ) -> None:
        raise AssertionError("main() must start its server with uvicorn.Server.run")

    monkeypatch.setattr(uvicorn.Server, "run", record_run)
    monkeypatch.setattr(uvicorn.Server, "serve", refuse_serve)
    return configs


def entry_point() -> Callable[[], None]:
    """Import `nock.__main__` and return its `main`.

    Called by each test of AC-10 and AC-11 once the recorder is in place, so that
    a missing module fails those tests, not the collection of this file.
    """
    from nock.__main__ import main

    return main


def set_variable(monkeypatch: pytest.MonkeyPatch, name: str, value: str | None) -> None:
    """Set the environment variable `name` to `value`; None deletes it."""
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)


def refusal_message(main: Callable[[], None]) -> str:
    """Call `main`, which must raise SystemExit naming NOCK_PORT; return its code.

    Fails the test when the code of the SystemExit is not a `str`.
    """
    with pytest.raises(SystemExit, match=PORT_VARIABLE) as caught:
        main()
    message = caught.value.code
    assert isinstance(message, str), f"the SystemExit code {message!r} is no message"
    return message


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


# ---- AC-10: main() hands uvicorn the address of NOCK_HOST and NOCK_PORT -----------


@pytest.mark.parametrize(
    ("nock_host", "nock_port", "expected_address"),
    [
        (None, None, (DEFAULT_HOST, DEFAULT_PORT)),
        ("", "", (DEFAULT_HOST, DEFAULT_PORT)),
        ("0.0.0.0", "9123", ("0.0.0.0", 9123)),
    ],
    ids=["neither-set", "both-empty", "both-set"],
)
def test_ac10_main_runs_server_config_of_nock_server_app_on_the_address_given(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    nock_host: str | None,
    nock_port: str | None,
    expected_address: tuple[str, int],
) -> None:
    set_variable(monkeypatch, HOST_VARIABLE, nock_host)
    set_variable(monkeypatch, PORT_VARIABLE, nock_port)
    main = entry_point()

    main()

    assert len(server_runs) == 1, "main() must run exactly one server"
    config = server_runs[0]
    assert config.app is nock.server.app
    assert config.ws_max_size == MAX_WS_FRAME_BYTES
    assert (config.host, config.port) == expected_address


@pytest.mark.parametrize(
    ("nock_host", "nock_port", "expected_address"),
    [
        ("", "9123", (DEFAULT_HOST, 9123)),
        (None, "9123", (DEFAULT_HOST, 9123)),
        ("0.0.0.0", "", ("0.0.0.0", DEFAULT_PORT)),
        ("0.0.0.0", None, ("0.0.0.0", DEFAULT_PORT)),
    ],
    ids=["host-empty", "host-unset", "port-empty", "port-unset"],
)
def test_ac10_each_variable_unset_or_empty_takes_its_own_default(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    nock_host: str | None,
    nock_port: str | None,
    expected_address: tuple[str, int],
) -> None:
    set_variable(monkeypatch, HOST_VARIABLE, nock_host)
    set_variable(monkeypatch, PORT_VARIABLE, nock_port)
    main = entry_point()

    main()

    addresses = [(config.host, config.port) for config in server_runs]
    assert addresses == [expected_address]


@pytest.mark.parametrize(
    ("nock_port", "expected_port"),
    [("08000", 8000), ("09123", 9123), ("1", 1), ("65535", 65535)],
)
def test_ac10_a_port_with_leading_zeros_or_at_the_bounds_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    nock_port: str,
    expected_port: int,
) -> None:
    monkeypatch.delenv(HOST_VARIABLE, raising=False)
    monkeypatch.setenv(PORT_VARIABLE, nock_port)
    main = entry_point()

    main()

    ports = [config.port for config in server_runs]
    assert ports == [expected_port]


def test_ac10_a_port_of_5000_zeros_then_8000_is_8000_beyond_the_int_digit_limit(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    long_port = "0" * 5000 + "8000"
    assert len(long_port) == 5004
    monkeypatch.delenv(HOST_VARIABLE, raising=False)
    monkeypatch.setenv(PORT_VARIABLE, long_port)
    main = entry_point()

    main()

    addresses = [(config.host, config.port) for config in server_runs]
    assert addresses == [(DEFAULT_HOST, DEFAULT_PORT)]


@pytest.mark.parametrize(
    "nock_host",
    [
        pytest.param("::1", id="ipv6-loopback"),
        pytest.param("localhost", id="a-name"),
        pytest.param("192.0.2.1", id="no-address-of-this-machine"),
    ],
)
def test_ac10_nock_host_is_passed_on_as_given(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config], nock_host: str
) -> None:
    monkeypatch.setenv(HOST_VARIABLE, nock_host)
    monkeypatch.delenv(PORT_VARIABLE, raising=False)
    main = entry_point()

    main()

    hosts = [config.host for config in server_runs]
    assert hosts == [nock_host]


def test_ac10_main_reads_the_variables_each_time_it_is_called(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    monkeypatch.setenv(HOST_VARIABLE, "::1")
    monkeypatch.setenv(PORT_VARIABLE, "9123")
    main = entry_point()

    main()
    monkeypatch.setenv(HOST_VARIABLE, "0.0.0.0")
    monkeypatch.setenv(PORT_VARIABLE, "9124")
    main()
    monkeypatch.delenv(HOST_VARIABLE)
    monkeypatch.delenv(PORT_VARIABLE)
    main()

    addresses = [(config.host, config.port) for config in server_runs]
    assert addresses == [
        ("::1", 9123),
        ("0.0.0.0", 9124),
        (DEFAULT_HOST, DEFAULT_PORT),
    ]


def test_ac10_main_keeps_the_info_log_level_of_server_config(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    monkeypatch.delenv(HOST_VARIABLE, raising=False)
    monkeypatch.delenv(PORT_VARIABLE, raising=False)
    main = entry_point()

    main()

    log_levels = [config.log_level for config in server_runs]
    assert log_levels == [SERVER_LOG_LEVEL]


def test_ac10_importing_nock_main_runs_no_server(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    monkeypatch.delenv(HOST_VARIABLE, raising=False)
    monkeypatch.delenv(PORT_VARIABLE, raising=False)
    # Run the module's code again, even when an earlier test imported it.
    monkeypatch.delitem(sys.modules, "nock.__main__", raising=False)

    importlib.import_module("nock.__main__")

    assert server_runs == []


# ---- AC-11: an invalid NOCK_PORT stops main() before any server runs --------------


@pytest.mark.parametrize("nock_port", ["abc", "0", "65536", "-1", "8000.0", " 8000"])
def test_ac11_an_invalid_nock_port_raises_system_exit_naming_it_and_runs_nothing(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config], nock_port: str
) -> None:
    monkeypatch.delenv(HOST_VARIABLE, raising=False)
    monkeypatch.setenv(PORT_VARIABLE, nock_port)
    main = entry_point()

    message = refusal_message(main)

    assert nock_port in message
    assert server_runs == []


@pytest.mark.parametrize(
    "nock_port",
    [
        pytest.param("+8000", id="plus-sign"),
        pytest.param("8000 ", id="trailing-space"),
        pytest.param(" ", id="only-a-space"),
        pytest.param("8_000", id="underscore"),
        pytest.param("000", id="zero-with-leading-zeros"),
        pytest.param("99999999999999999999", id="far-over-65535"),
        pytest.param(FULLWIDTH_8000, id="fullwidth-digits"),
        pytest.param(ARABIC_INDIC_8000, id="arabic-indic-digits"),
        pytest.param(SUPERSCRIPT_TWO, id="superscript-two"),
    ],
)
def test_ac11_other_values_than_ascii_digits_from_1_to_65535_are_refused(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config], nock_port: str
) -> None:
    monkeypatch.delenv(HOST_VARIABLE, raising=False)
    monkeypatch.setenv(PORT_VARIABLE, nock_port)
    main = entry_point()

    message = refusal_message(main)

    assert nock_port in message
    assert server_runs == []


def test_ac11_a_port_ending_with_a_newline_is_refused(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    monkeypatch.delenv(HOST_VARIABLE, raising=False)
    monkeypatch.setenv(PORT_VARIABLE, "8000\n")
    main = entry_point()

    # The message must name NOCK_PORT. How it shows a newline (as it is, or
    # escaped) is not stated, so the value is not looked for in it.
    refusal_message(main)

    assert server_runs == []


def test_ac11_python_m_nock_with_an_invalid_port_prints_why_and_exits_with_1() -> None:
    environment = dict(os.environ)
    environment.pop(HOST_VARIABLE, None)
    environment.pop(DATABASE_VARIABLE, None)
    environment[PORT_VARIABLE] = "abc"

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "nock"],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROCESS_EXIT_LIMIT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"python -m nock with NOCK_PORT=abc still ran after "
            f"{PROCESS_EXIT_LIMIT_SECONDS:.0f} s"
        )

    assert PORT_VARIABLE in completed.stderr, completed.stderr
    assert "abc" in completed.stderr, completed.stderr
    assert completed.returncode == 1
