"""Tests of spec 036 (performance), AC-10 to AC-12: the variables of `python -m nock`.

`nock.__main__.main()` reads NOCK_HOST, NOCK_PORT and NOCK_DATABASE. The tests
call it in the test process, with `uvicorn.Server.run` replaced by the harness's
recorder: AC-10 checks the address it hands uvicorn, AC-11 the values it refuses
and the message it stops with, AC-12 the database paths it accepts. One test of
AC-11 runs `python -m nock` in a subprocess. AC-12's second part starts the app of
`create_app` with `TestClient`, while `nock.server.RoomStore` is a subclass that
records the path of each store the app builds.

The shared setup is in `spec036_harness` and `spec036_frames_harness`. What only
this file uses is defined below the imports. AC-8 and AC-9, `python -m nock`
serving in a subprocess, are in `test_spec_036_ac08_entry_point.py`.

Notes:

- Every test sets or deletes all three variables (with `set_variables` or
  `set_only`, or in the environment of its subprocess), so that a variable left
  in the shell that runs the tests cannot change a case.
- Every test that calls `main()` uses the recorder, so that a `main()` that does
  not refuse a value records a run instead of serving.
- Each of those tests imports `nock.__main__` itself, once the recorder is in
  place: a missing module then fails those tests only, not the collection of this
  file, and an import that started a server could not block the run.
  `uvicorn.Server.serve` is replaced as well, so that a server started without
  `run` fails the test instead of serving.
- Edge cases checked as well: for `main()`, each of NOCK_HOST and NOCK_PORT empty
  or unset on its own, leading zeros and the bounds of NOCK_PORT, the variables
  read and checked at each call, an import that runs nothing; an address of no
  interface of this machine, host names that do not resolve and the ASCII form of
  a name, passed on as given; a newline alone, refused in each variable; signs,
  spaces, underscores, digits outside ASCII and 5,000 zeros before 70000 in
  NOCK_PORT; several invalid variables at once; the characters that Windows
  refuses in a file name, which NOCK_DATABASE takes; and the message and status 1
  of `python -m nock` with an invalid port.
"""

from __future__ import annotations

import importlib
import os
import socket
import subprocess
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

import nock.server
from nock.store import RoomStore
from spec036_frames_harness import MAX_WS_FRAME_BYTES
from spec036_harness import DATABASE_VARIABLE, HOST_VARIABLE, PORT_VARIABLE

# ---- Values of the spec --------------------------------------------------------------

MAIN_VARIABLES = (HOST_VARIABLE, PORT_VARIABLE, DATABASE_VARIABLE)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
SERVER_LOG_LEVEL = "info"  # server_config's default, which main() keeps
MEMORY_DATABASE = ":memory:"  # the store of an unset or empty NOCK_DATABASE (018)

# The general categories that the message of a refused value never holds (AC-11):
# control characters, format characters, line and paragraph separators.
INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})

# 5,000 zeros, then a port number: int() refuses a string of over 4,300 digits.
ZEROS_THEN_8000 = "0" * 5000 + "8000"  # 5,004 characters, the port 8000 (AC-10)
ZEROS_THEN_70000 = "0" * 5000 + "70000"  # refused, as "70000" is (edge cases)

# Digits outside ASCII, which NOCK_PORT refuses (int() reads the first two as 8000;
# str.isdigit() takes all three).
FULLWIDTH_8000 = "\N{FULLWIDTH DIGIT EIGHT}" + "\N{FULLWIDTH DIGIT ZERO}" * 3
ARABIC_INDIC_8000 = "\N{ARABIC-INDIC DIGIT EIGHT}" + "\N{ARABIC-INDIC DIGIT ZERO}" * 3
SUPERSCRIPT_TWO = "\N{SUPERSCRIPT TWO}"

# The values below are the spec's. The spec writes them as Python string literals;
# this file writes each invisible character by its name, as in
# "\N{ZERO WIDTH SPACE}" (U+200B), and each C0 or C1 control with a "\x.." escape
# as the spec does, so that its source holds none of them raw. A raw literal such
# as r"C:\temp\nock.sqlite3" holds backslashes, not escapes.

# AC-10: values of NOCK_HOST that main() hands uvicorn as given.
ACCEPTED_HOSTS = [
    # As AC-10 lists them.
    pytest.param("localhost", id="localhost"),
    pytest.param("Nock-1.example.org", id="name-with-capital-digit-and-dash"),
    pytest.param("::", id="ipv6-unspecified"),
    pytest.param("::1", id="ipv6-loopback"),
    pytest.param("fe80::1", id="ipv6-link-local"),
    pytest.param("2001:DB8::1", id="ipv6-with-capitals"),
    pytest.param("::ffff:192.0.2.1", id="ipv6-mapped-ipv4"),
    # Edge cases: an address of no interface of this machine, and names that do
    # not resolve, are uvicorn's error, not main()'s; a name with letters outside
    # ASCII is given in its ASCII form.
    pytest.param("192.0.2.1", id="no-address-of-this-machine"),
    pytest.param("a..b", id="name-with-an-empty-label"),
    pytest.param("-", id="only-a-dash"),
    pytest.param("xn--bcher-kva.example", id="ascii-form-of-a-name"),
]

# AC-11: the variable and the value of each case; the two other variables are unset.
AC11_INVALID_VALUES = [
    # NOCK_PORT, as AC-11 lists them.
    pytest.param(PORT_VARIABLE, "abc", id="port-letters"),
    pytest.param(PORT_VARIABLE, "0", id="port-zero"),
    pytest.param(PORT_VARIABLE, "65536", id="port-65536"),
    pytest.param(PORT_VARIABLE, "-1", id="port-minus-one"),
    pytest.param(PORT_VARIABLE, "8000.0", id="port-decimal-point"),
    pytest.param(PORT_VARIABLE, " 8000", id="port-leading-space"),
    pytest.param(PORT_VARIABLE, "8000\n", id="port-trailing-newline"),
    pytest.param(PORT_VARIABLE, "\t8000", id="port-leading-tab"),
    pytest.param(PORT_VARIABLE, "80\x1b[2J00", id="port-escape-sequence"),
    pytest.param(PORT_VARIABLE, "8000\x7f", id="port-delete"),
    pytest.param(PORT_VARIABLE, "8000\x85", id="port-c1-next-line"),
    pytest.param(PORT_VARIABLE, "8000\x9b", id="port-c1-control-sequence-introducer"),
    # NOCK_HOST, as AC-11 lists them.
    pytest.param(HOST_VARIABLE, "localhost\n", id="host-trailing-newline"),
    pytest.param(HOST_VARIABLE, "\t127.0.0.1", id="host-leading-tab"),
    pytest.param(HOST_VARIABLE, "local\x1b[2Jhost", id="host-escape-sequence"),
    pytest.param(HOST_VARIABLE, "127.0.0.1\x7f", id="host-delete"),
    pytest.param(HOST_VARIABLE, "::1\x85", id="host-c1-next-line"),
    pytest.param(
        HOST_VARIABLE, "localhost\N{LINE SEPARATOR}", id="host-line-separator"
    ),
    pytest.param(HOST_VARIABLE, " ", id="host-only-a-space"),
    pytest.param(HOST_VARIABLE, "local host", id="host-inner-space"),
    pytest.param(HOST_VARIABLE, "[::1]", id="host-ipv6-in-brackets"),
    pytest.param(HOST_VARIABLE, "localhost:8000", id="host-name-and-port"),
    pytest.param(HOST_VARIABLE, "127.0.0.1:8000", id="host-ipv4-and-port"),
    pytest.param(HOST_VARIABLE, "fe80::1%eth0", id="host-ipv6-zone"),
    pytest.param(HOST_VARIABLE, "my_host", id="host-underscore"),
    pytest.param(HOST_VARIABLE, "bücher.example", id="host-letter-outside-ascii"),
    pytest.param(HOST_VARIABLE, "0.0.0.0/0", id="host-slash"),
    # NOCK_DATABASE, as AC-11 lists them.
    pytest.param(DATABASE_VARIABLE, "\n", id="database-only-a-newline"),
    pytest.param(
        DATABASE_VARIABLE, "data/nock.sqlite3\n", id="database-trailing-newline"
    ),
    pytest.param(DATABASE_VARIABLE, "\tdata/nock.sqlite3", id="database-leading-tab"),
    pytest.param(
        DATABASE_VARIABLE,
        r"C:\Users\François\nock.sqlite3" + "\r\n",
        id="database-windows-path-then-carriage-return-and-newline",
    ),
    pytest.param(DATABASE_VARIABLE, "nock\x01.sqlite3", id="database-start-of-heading"),
    pytest.param(
        DATABASE_VARIABLE, "nock\x1b[2J.sqlite3", id="database-escape-sequence"
    ),
    pytest.param(DATABASE_VARIABLE, "nock\x1f.sqlite3", id="database-unit-separator"),
    pytest.param(DATABASE_VARIABLE, "nock\x7f.sqlite3", id="database-delete"),
    pytest.param(DATABASE_VARIABLE, "nock\x85.sqlite3", id="database-c1-next-line"),
    pytest.param(
        DATABASE_VARIABLE,
        "nock\x9f.sqlite3",
        id="database-c1-application-program-command",
    ),
    pytest.param(
        DATABASE_VARIABLE,
        "nock\N{ZERO WIDTH SPACE}.sqlite3",
        id="database-zero-width-space",
    ),
    pytest.param(
        DATABASE_VARIABLE,
        "\N{ZERO WIDTH NO-BREAK SPACE}data/nock.sqlite3",
        id="database-byte-order-mark",
    ),
    pytest.param(
        DATABASE_VARIABLE,
        "nock\N{RIGHT-TO-LEFT OVERRIDE}.sqlite3",
        id="database-right-to-left-override",
    ),
    pytest.param(
        DATABASE_VARIABLE,
        "nock\N{LINE SEPARATOR}.sqlite3",
        id="database-line-separator",
    ),
    pytest.param(
        DATABASE_VARIABLE,
        "nock\N{PARAGRAPH SEPARATOR}.sqlite3",
        id="database-paragraph-separator",
    ),
    pytest.param(
        DATABASE_VARIABLE, "nock\N{SOFT HYPHEN}.sqlite3", id="database-soft-hyphen"
    ),
    pytest.param(
        DATABASE_VARIABLE, "nock\N{LANGUAGE TAG}.sqlite3", id="database-language-tag"
    ),
]

# Edge cases of AC-11, from "Edge cases and errors".
OTHER_INVALID_VALUES = [
    # Only an unset or empty variable escapes the checks: a newline alone is
    # refused for all three (NOCK_DATABASE's case is in AC-11's list).
    pytest.param(PORT_VARIABLE, "\n", id="port-only-a-newline"),
    pytest.param(HOST_VARIABLE, "\n", id="host-only-a-newline"),
    # NOCK_PORT takes ASCII digits only, for a number from 1 to 65535.
    pytest.param(PORT_VARIABLE, "+8000", id="port-plus-sign"),
    pytest.param(PORT_VARIABLE, "8000 ", id="port-trailing-space"),
    pytest.param(PORT_VARIABLE, " ", id="port-only-a-space"),
    pytest.param(PORT_VARIABLE, "8_000", id="port-underscore"),
    pytest.param(PORT_VARIABLE, "000", id="port-zero-with-leading-zeros"),
    pytest.param(PORT_VARIABLE, "99999999999999999999", id="port-far-over-65535"),
    pytest.param(PORT_VARIABLE, ZEROS_THEN_70000, id="port-5000-zeros-then-70000"),
    pytest.param(PORT_VARIABLE, FULLWIDTH_8000, id="port-fullwidth-digits"),
    pytest.param(PORT_VARIABLE, ARABIC_INDIC_8000, id="port-arabic-indic-digits"),
    pytest.param(PORT_VARIABLE, SUPERSCRIPT_TWO, id="port-superscript-two"),
]

INVALID_VALUES = [*AC11_INVALID_VALUES, *OTHER_INVALID_VALUES]

# Several invalid variables at once (edge cases): main() stops with the message of
# one of them.
SEVERAL_INVALID_VALUES = {
    HOST_VARIABLE: "my_host",
    PORT_VARIABLE: "abc",
    DATABASE_VARIABLE: "nock\x01.sqlite3",
}

# AC-12: values of NOCK_DATABASE that never stop main(); None leaves it unset.
ACCEPTED_DATABASES = [
    # As AC-12 lists them.
    pytest.param(None, id="unset"),
    pytest.param("", id="empty"),
    pytest.param("data/nock.sqlite3", id="relative-path"),
    pytest.param("~/nock.sqlite3", id="home-tilde"),
    pytest.param("/srv/jeu de mots/données/nock.sqlite3", id="spaces-and-accent"),
    pytest.param("/srv/nock\N{NO-BREAK SPACE}data/nock.sqlite3", id="no-break-space"),
    pytest.param(
        "/srv/nock\N{ZERO WIDTH NON-JOINER}data/nock.sqlite3",
        id="zero-width-non-joiner",
    ),
    pytest.param(
        "/srv/nock\N{ZERO WIDTH JOINER}data/nock.sqlite3", id="zero-width-joiner"
    ),
    pytest.param(r"C:\Users\François\nock.sqlite3", id="windows-path-with-accent"),
    pytest.param(r"C:\temp\nock.sqlite3", id="windows-path-backslash-t-backslash-n"),
    pytest.param(":memory:", id="memory"),
    # Edge case: the characters that Windows refuses in a file name pass main()'s
    # check; opening the file stays the app's job (spec 018).
    pytest.param("data/nock*?|.sqlite3", id="characters-windows-refuses"),
]

# AC-12, the app: the cases where it keeps its rooms in memory.
MEMORY_DATABASES = [
    pytest.param(None, id="unset"),
    pytest.param("", id="empty"),
]


# ---- Values of the test harness ------------------------------------------------------

INVALID_PORT = "abc"  # the NOCK_PORT of the subprocess test
PROCESS_EXIT_LIMIT_SECONDS = 30.0


# ---- The production entry point in the test process ----------------------------------


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

    Called by each test of `main()` once the recorder is in place, so that a
    missing module fails those tests, not the collection of this file.
    """
    from nock.__main__ import main

    return main


def set_variable(monkeypatch: pytest.MonkeyPatch, name: str, value: str | None) -> None:
    """Set the environment variable `name` to `value`; None deletes it."""
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)


def set_variables(
    monkeypatch: pytest.MonkeyPatch,
    *,
    host: str | None,
    port: str | None,
    database: str | None,
) -> None:
    """Set or delete the three variables that `main()` reads; None deletes one.

    Every test of AC-10 to AC-12 sets all three (or calls `set_only`), so that a
    variable left in the shell that runs the tests cannot change a case.
    """
    set_variable(monkeypatch, HOST_VARIABLE, host)
    set_variable(monkeypatch, PORT_VARIABLE, port)
    set_variable(monkeypatch, DATABASE_VARIABLE, database)


def set_only(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    """Set the variable `name` to `value`; delete the two others that main() reads."""
    assert name in MAIN_VARIABLES, f"{name} is not a variable that main() reads"
    for variable in MAIN_VARIABLES:
        if variable == name:
            monkeypatch.setenv(variable, value)
        else:
            monkeypatch.delenv(variable, raising=False)


def refusal_message(main: Callable[[], None]) -> str:
    """Call `main`, which must raise SystemExit with a message; return the message.

    Fails the test when `main` returns, or when the code of its SystemExit is not
    a `str`.
    """
    with pytest.raises(SystemExit) as caught:
        main()
    message = caught.value.code
    assert isinstance(message, str), f"the SystemExit code {message!r} is no message"
    return message


def invisible_characters(text: str) -> list[str]:
    """Return the characters of `text` of general category Cc, Cf, Zl or Zp."""
    found: list[str] = []
    for character in text:
        if unicodedata.category(character) in INVISIBLE_CATEGORIES:
            found.append(character)
    return found


# ---- The app's store (AC-12, second part) --------------------------------------------


@pytest.fixture
def store_paths(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace `nock.server.RoomStore` by the harness's recording subclass.

    Returns the list where the subclass's `__init__` appends `str(path)`, for each
    store built, before it calls `RoomStore.__init__`.
    """
    paths: list[str] = []

    class RecordingRoomStore(RoomStore):
        """A RoomStore that records the path it is built with."""

        def __init__(self, path: str | Path) -> None:
            """Record `str(path)`, then open the store as RoomStore does."""
            paths.append(str(path))
            RoomStore.__init__(self, path)

    monkeypatch.setattr(nock.server, "RoomStore", RecordingRoomStore)
    return paths


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
    set_variables(monkeypatch, host=nock_host, port=nock_port, database=None)
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
    set_variables(monkeypatch, host=nock_host, port=nock_port, database=None)
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
    set_variables(monkeypatch, host=None, port=nock_port, database=None)
    main = entry_point()

    main()

    ports = [config.port for config in server_runs]
    assert ports == [expected_port]


def test_ac10_a_port_of_5000_zeros_then_8000_is_8000_beyond_the_int_digit_limit(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_variables(monkeypatch, host=None, port=ZEROS_THEN_8000, database=None)
    main = entry_point()

    main()

    assert len(server_runs) == 1, "main() must run exactly one server"
    config = server_runs[0]
    assert config.app is nock.server.app
    assert config.ws_max_size == MAX_WS_FRAME_BYTES
    assert (config.host, config.port) == (DEFAULT_HOST, DEFAULT_PORT)


@pytest.mark.parametrize("nock_host", ACCEPTED_HOSTS)
def test_ac10_nock_host_is_passed_on_as_given(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config], nock_host: str
) -> None:
    set_variables(monkeypatch, host=nock_host, port=None, database=None)
    main = entry_point()

    main()

    addresses = [(config.host, config.port) for config in server_runs]
    assert addresses == [(nock_host, DEFAULT_PORT)]


def test_ac10_main_reads_the_variables_each_time_it_is_called(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_variables(monkeypatch, host="::1", port="9123", database=None)
    main = entry_point()

    main()
    set_variables(monkeypatch, host="0.0.0.0", port="9124", database=None)
    main()
    set_variables(monkeypatch, host=None, port=None, database=None)
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
    set_variables(monkeypatch, host=None, port=None, database=None)
    main = entry_point()

    main()

    log_levels = [config.log_level for config in server_runs]
    assert log_levels == [SERVER_LOG_LEVEL]


def test_ac10_importing_nock_main_runs_no_server(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_variables(monkeypatch, host=None, port=None, database=None)
    # Run the module's code again, even when an earlier test imported it.
    monkeypatch.delitem(sys.modules, "nock.__main__", raising=False)

    importlib.import_module("nock.__main__")

    assert server_runs == []


# ---- AC-11: an invalid variable stops main() before any server runs ---------------


@pytest.mark.parametrize(("variable", "value"), INVALID_VALUES)
def test_ac11_an_invalid_value_stops_main_before_any_server_runs(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    variable: str,
    value: str,
) -> None:
    set_only(monkeypatch, variable, value)
    main = entry_point()

    refusal_message(main)

    assert server_runs == []


@pytest.mark.usefixtures("server_runs")
@pytest.mark.parametrize(("variable", "value"), INVALID_VALUES)
def test_ac11_the_message_names_the_variable_and_shows_repr_of_the_value(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    set_only(monkeypatch, variable, value)
    main = entry_point()

    message = refusal_message(main)

    assert variable in message
    assert repr(value) in message


@pytest.mark.usefixtures("server_runs")
@pytest.mark.parametrize(("variable", "value"), INVALID_VALUES)
def test_ac11_the_message_is_one_line_without_control_or_invisible_characters(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    set_only(monkeypatch, variable, value)
    main = entry_point()

    message = refusal_message(main)

    assert invisible_characters(message) == []
    assert len(message.splitlines()) == 1


def test_ac11_with_several_invalid_variables_main_stops_with_the_message_of_one(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_variables(
        monkeypatch,
        host=SEVERAL_INVALID_VALUES[HOST_VARIABLE],
        port=SEVERAL_INVALID_VALUES[PORT_VARIABLE],
        database=SEVERAL_INVALID_VALUES[DATABASE_VARIABLE],
    )
    main = entry_point()

    message = refusal_message(main)

    # Which variable the message is about is not specified.
    variables_shown: list[str] = []
    for variable, value in SEVERAL_INVALID_VALUES.items():
        if variable in message and repr(value) in message:
            variables_shown.append(variable)
    assert len(variables_shown) >= 1, message
    assert invisible_characters(message) == []
    assert len(message.splitlines()) == 1
    assert server_runs == []


def test_ac11_main_checks_the_variables_each_time_it_is_called(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_variables(
        monkeypatch, host="localhost", port="9123", database="data/nock.sqlite3"
    )
    main = entry_point()

    main()
    set_variables(
        monkeypatch, host="my_host", port="9123", database="data/nock.sqlite3"
    )
    host_message = refusal_message(main)
    set_variables(
        monkeypatch, host="localhost", port="9123", database="nock\x01.sqlite3"
    )
    database_message = refusal_message(main)

    assert HOST_VARIABLE in host_message
    assert DATABASE_VARIABLE in database_message
    addresses = [(config.host, config.port) for config in server_runs]
    assert addresses == [("localhost", 9123)]


def test_ac11_python_m_nock_with_an_invalid_port_prints_why_and_exits_with_1() -> None:
    environment = dict(os.environ)
    environment.pop(HOST_VARIABLE, None)
    environment.pop(DATABASE_VARIABLE, None)
    environment[PORT_VARIABLE] = INVALID_PORT

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
            f"python -m nock with NOCK_PORT={INVALID_PORT} still ran after "
            f"{PROCESS_EXIT_LIMIT_SECONDS:.0f} s"
        )

    assert PORT_VARIABLE in completed.stderr, completed.stderr
    assert repr(INVALID_PORT) in completed.stderr, completed.stderr
    assert completed.returncode == 1


# ---- AC-12: a NOCK_DATABASE without a refused character never stops main() --------


@pytest.mark.parametrize("nock_database", ACCEPTED_DATABASES)
def test_ac12_a_database_path_without_a_refused_character_never_stops_main(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    nock_database: str | None,
) -> None:
    set_variables(monkeypatch, host=None, port=None, database=nock_database)
    main = entry_point()

    main()

    addresses = [(config.host, config.port) for config in server_runs]
    assert addresses == [(DEFAULT_HOST, DEFAULT_PORT)]


@pytest.mark.usefixtures("server_runs")
@pytest.mark.parametrize("nock_database", ACCEPTED_DATABASES)
def test_ac12_main_leaves_nock_database_as_it_was(
    monkeypatch: pytest.MonkeyPatch, nock_database: str | None
) -> None:
    set_variables(monkeypatch, host=None, port=None, database=nock_database)
    database_before = os.environ.get(DATABASE_VARIABLE)
    main = entry_point()

    main()

    assert os.environ.get(DATABASE_VARIABLE) == database_before


@pytest.mark.parametrize("nock_database", MEMORY_DATABASES)
def test_ac12_the_app_keeps_its_rooms_in_memory_when_nock_database_is_unset_or_empty(
    monkeypatch: pytest.MonkeyPatch,
    store_paths: list[str],
    tmp_path: Path,
    nock_database: str | None,
) -> None:
    set_variables(monkeypatch, host=None, port=None, database=nock_database)
    app = nock.server.create_app(dist_dir=tmp_path)

    with TestClient(app):
        pass

    assert len(store_paths) >= 1, "the app built no store when it started"
    assert "" not in store_paths
    assert store_paths == [MEMORY_DATABASE] * len(store_paths)
