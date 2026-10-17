"""Tests of spec 038 (privacy and operations), AC-10: the operator token's variable.

`operator_token_from_env` reads NOCK_OPERATOR_TOKEN from a mapping; `main()` checks
it first, with `uvicorn.Server.run` replaced by spec 036's recorder (the
`server_runs` fixture below, as in spec 036's tests); `python -m nock` runs in a
subprocess once; the app of `create_app` reads the variable when it starts
(`TestClient`). The shared setup is in `spec038_harness` and `spec036_harness`.

Edge cases checked as well, from "Operator access" and "Edge cases and errors": the
64 allowed characters, a value of spaces only, control characters, the characters
of base64 that the rule refuses (`=`, `+`, `/`), digits and letters outside ASCII
and an invisible character; `main()` checks the token before the other variables
and at each call, and leaves the variable as it was; the app reads the variable
when it starts, not when it is built, and keeps it while it runs; a token given to
`create_app` wins over the variable, which is then never read; and an invalid
variable fails the app's startup with the same `SettingsError`. A token given to
`create_app` follows the variable's rule: `""` turns the pages off whatever the
variable holds, a valid one or one breaking the rule, and any value the rule
refuses raises `SettingsError` when `create_app` is called, with a message that
never holds it (checked on distinctive values, never on `a`).

`nock.settings` and `nock.__main__` are imported inside the tests, so that each
test fails on the name it needs (see `spec038_harness`).
"""

from __future__ import annotations

import os
import socket
import string
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.room import new_room
from nock.server import create_app
from spec036_harness import DATABASE_VARIABLE, HOST_VARIABLE, PORT_VARIABLE
from spec038_harness import (
    DASHBOARD_PATH,
    NOT_FOUND,
    OPERATOR_TOKEN_VARIABLE,
    OPS_PAGE_PATH,
    OPS_TOKEN,
    UNKNOWN_API_PATH,
    UNKNOWN_PATH,
    answer_of,
    bearer,
    edits_path,
)

# ---- Values of the spec --------------------------------------------------------------

# Every character the rule allows: A-Z, a-z, 0-9, "_" and "-" (64 in all).
ALLOWED_CHARACTERS = string.ascii_uppercase + string.ascii_lowercase + string.digits
ALLOWED_CHARACTERS += "_-"
TOKEN_32 = "AZaz09_-" * 4  # 32 characters, each kind of allowed character
TOKEN_256 = "AZaz09_-" * 32
TOKEN_31 = TOKEN_32[:31]
TOKEN_257 = TOKEN_256 + "A"
SHORT_TOKEN = "Zq9Zq9"  # main()'s first case
DOLLAR_TOKEN = "Zq9" * 11 + "$"  # main()'s second case: 34 characters

# Refused values, each long and distinctive enough for "the message never holds
# the value" to mean something.
REFUSED_VALUES = [
    # As AC-10 lists them.
    pytest.param(TOKEN_31, id="31-characters"),
    pytest.param(TOKEN_257, id="257-characters"),
    pytest.param(DOLLAR_TOKEN, id="dollar"),
    pytest.param("Zq9" * 5 + " " + "Zq9" * 6, id="space"),
    pytest.param(
        "Zq9" * 5 + "\N{LATIN SMALL LETTER E WITH ACUTE}" + "Zq9" * 6, id="e-acute"
    ),
    pytest.param(SHORT_TOKEN, id="6-characters"),
    # Edge cases: what the rule's character set leaves out.
    pytest.param("Zq9" * 11 + "\n", id="trailing-newline"),
    pytest.param("\t" + "Zq9" * 11, id="leading-tab"),
    pytest.param("Zq9" * 11 + "=", id="base64-padding"),
    pytest.param("Zq9" * 11 + "+", id="plus"),
    pytest.param("Zq9" * 11 + "/", id="slash"),
    pytest.param("Zq9" * 11 + ".", id="dot"),
    pytest.param("Zq9" * 11 + "\N{FULLWIDTH DIGIT ONE}", id="fullwidth-digit"),
    pytest.param("Zq9" * 11 + "\N{ARABIC-INDIC DIGIT ONE}", id="arabic-indic-digit"),
    pytest.param("Zq9" * 11 + "\N{SUPERSCRIPT TWO}", id="superscript-two"),
    pytest.param("Zq9" * 11 + "\N{LATIN SMALL LETTER SHARP S}", id="sharp-s"),
    pytest.param("Zq9" * 11 + "\N{ZERO WIDTH SPACE}", id="zero-width-space"),
]

ACCEPTED_VALUES = [
    pytest.param(TOKEN_32, id="32-characters"),
    pytest.param(TOKEN_256, id="256-characters"),
    pytest.param(ALLOWED_CHARACTERS, id="every-allowed-character"),
    pytest.param(OPS_TOKEN, id="the-ops-token-of-the-harness"),
]

OTHER_TOKEN = "Ops-" + "y" * 40  # a valid token other than OPS_TOKEN

# ---- Values of the test harness ------------------------------------------------------

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
PROCESS_EXIT_LIMIT_SECONDS = 20.0
GIVEN_ROOM = "GIVEN1"  # a room of the registry, for the replay path


# ---- Fixtures and helpers ------------------------------------------------------------


@pytest.fixture
def server_runs(monkeypatch: pytest.MonkeyPatch) -> list[uvicorn.Config]:
    """Replace `uvicorn.Server.run` by spec 036's recorder; return what it keeps.

    The recorder keeps the `config` of each server whose `run` is called and
    returns None. `uvicorn.Server.serve` is replaced too, so that a server started
    without `run` fails the test instead of serving in it.
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
    """Import `nock.__main__` and return its `main`."""
    from nock.__main__ import main

    return main


def set_token_only(monkeypatch: pytest.MonkeyPatch, token: str | None) -> None:
    """Set NOCK_OPERATOR_TOKEN (None deletes it); delete spec 036's three variables."""
    for variable in (HOST_VARIABLE, PORT_VARIABLE, DATABASE_VARIABLE):
        monkeypatch.delenv(variable, raising=False)
    if token is None:
        monkeypatch.delenv(OPERATOR_TOKEN_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, token)


def refusal_message(main: Callable[[], None]) -> str:
    """Call `main`, which must raise SystemExit with a `str` code; return it."""
    with pytest.raises(SystemExit) as caught:
        main()
    message = caught.value.code
    assert isinstance(message, str), f"the SystemExit code {message!r} is no message"
    return message


def forms_of(value: str) -> list[str]:
    """The value as given, as `repr()` writes it and as `ascii()` writes it."""
    return [value, repr(value), ascii(value)]


def token_of(environ: dict[str, str]) -> str | None:
    """`operator_token_from_env(environ)`."""
    from nock.settings import operator_token_from_env

    return operator_token_from_env(environ)


def settings_error_of(value: str) -> ValueError:
    """The SettingsError that `operator_token_from_env` raises for `value`."""
    from nock.settings import SettingsError

    with pytest.raises(SettingsError) as caught:
        token_of({OPERATOR_TOKEN_VARIABLE: value})
    return caught.value


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def given_room(registry: RoomRegistry, fx01_text: str) -> str:
    """Add the FX-01 room GIVEN_ROOM to the registry; return its code."""
    grid = Grid.model_validate_json(fx01_text)
    registry.add_room(new_room(GIVEN_ROOM, grid, time.time()))
    return GIVEN_ROOM


def dashboard_status(client: TestClient, token: str) -> int:
    return client.get(DASHBOARD_PATH, headers=bearer(token)).status_code


def start_and_stop(app: FastAPI) -> None:
    """Start the app (its lifespan) and stop it at once, as `TestClient` does."""
    with TestClient(app):
        pass


# ---- AC-10: operator_token_from_env --------------------------------------------------


def test_ac10_settings_error_is_a_value_error() -> None:
    from nock.settings import SettingsError

    assert issubclass(SettingsError, ValueError)


def test_ac10_no_variable_gives_none() -> None:
    assert token_of({}) is None


def test_ac10_an_empty_variable_gives_none() -> None:
    assert token_of({OPERATOR_TOKEN_VARIABLE: ""}) is None


def test_ac10_other_variables_give_none() -> None:
    environ = {HOST_VARIABLE: "localhost", "NOCK_TOKEN": OPS_TOKEN}

    assert token_of(environ) is None


@pytest.mark.parametrize("value", ACCEPTED_VALUES)
def test_ac10_a_value_of_32_to_256_allowed_characters_is_the_token(value: str) -> None:
    assert token_of({OPERATOR_TOKEN_VARIABLE: value}) == value


@pytest.mark.parametrize("value", REFUSED_VALUES)
def test_ac10_a_value_breaking_the_rule_raises_settings_error(value: str) -> None:
    error = settings_error_of(value)

    assert OPERATOR_TOKEN_VARIABLE in str(error)


@pytest.mark.parametrize("value", REFUSED_VALUES)
def test_ac10_the_message_never_holds_the_value(value: str) -> None:
    message = str(settings_error_of(value))

    shown: list[str] = []
    for form in forms_of(value):
        if form in message:
            shown.append(form)
    assert shown == [], message


def test_ac10_a_value_of_spaces_only_raises_settings_error() -> None:
    # Only an unset or empty variable turns the pages off.
    error = settings_error_of(" ")

    assert OPERATOR_TOKEN_VARIABLE in str(error)


# ---- AC-10: main() checks the token first --------------------------------------------


@pytest.mark.parametrize("value", [SHORT_TOKEN, DOLLAR_TOKEN])
def test_ac10_main_with_an_invalid_token_raises_system_exit_naming_the_variable(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config], value: str
) -> None:
    set_token_only(monkeypatch, value)
    main = entry_point()

    message = refusal_message(main)

    assert OPERATOR_TOKEN_VARIABLE in message
    shown: list[str] = []
    for form in forms_of(value):
        if form in message:
            shown.append(form)
    assert shown == [], message
    assert server_runs == []


def test_ac10_main_with_the_ops_token_runs_the_server_once(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_token_only(monkeypatch, OPS_TOKEN)
    main = entry_point()

    main()

    assert len(server_runs) == 1, "main() must run exactly one server"
    assert server_runs[0].app is nock.server.app


@pytest.mark.parametrize("value", [None, ""], ids=["unset", "empty"])
def test_ac10_main_without_a_token_runs_the_server_with_the_pages_off(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    value: str | None,
) -> None:
    set_token_only(monkeypatch, value)
    main = entry_point()

    main()

    assert len(server_runs) == 1


def test_ac10_main_checks_the_token_before_the_other_variables(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_token_only(monkeypatch, SHORT_TOKEN)
    monkeypatch.setenv(PORT_VARIABLE, "abc")
    main = entry_point()

    message = refusal_message(main)

    assert OPERATOR_TOKEN_VARIABLE in message
    assert SHORT_TOKEN not in message
    assert server_runs == []


def test_ac10_main_checks_the_token_each_time_it_is_called(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_token_only(monkeypatch, OPS_TOKEN)
    main = entry_point()

    main()
    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, SHORT_TOKEN)
    message = refusal_message(main)

    assert OPERATOR_TOKEN_VARIABLE in message
    assert len(server_runs) == 1


def test_ac10_main_leaves_the_variable_as_it_was(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_token_only(monkeypatch, OPS_TOKEN)
    main = entry_point()

    main()

    assert os.environ.get(OPERATOR_TOKEN_VARIABLE) == OPS_TOKEN
    assert len(server_runs) == 1


def free_local_port() -> int:
    """A free port of 127.0.0.1: bound with port 0, then released."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


def test_ac10_python_m_nock_with_an_invalid_token_prints_why_and_exits_with_1() -> None:
    environment = dict(os.environ)
    environment.pop(HOST_VARIABLE, None)
    environment.pop(DATABASE_VARIABLE, None)
    # A free port: a server that started anyway would not take a port in use.
    environment[PORT_VARIABLE] = str(free_local_port())
    environment[OPERATOR_TOKEN_VARIABLE] = SHORT_TOKEN

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
            f"python -m nock with an invalid {OPERATOR_TOKEN_VARIABLE} still ran "
            f"after {PROCESS_EXIT_LIMIT_SECONDS:.0f} s"
        )

    assert OPERATOR_TOKEN_VARIABLE in completed.stderr, completed.stderr
    assert SHORT_TOKEN not in completed.stderr
    assert SHORT_TOKEN not in completed.stdout
    assert completed.returncode == 1


# ---- AC-10: the app reads the variable when it starts --------------------------------


def test_ac10_an_app_without_a_token_takes_the_variable_when_it_starts(
    registry: RoomRegistry, dist_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, OPS_TOKEN)
    app = create_app(rooms=registry, dist_dir=dist_dir)

    with TestClient(app) as client:
        right = dashboard_status(client, OPS_TOKEN)
        wrong = dashboard_status(client, OTHER_TOKEN)

    assert (right, wrong) == (200, 401)


def test_ac10_the_variable_is_read_when_the_app_starts_not_when_it_is_built(
    registry: RoomRegistry, dist_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(OPERATOR_TOKEN_VARIABLE, raising=False)
    app = create_app(rooms=registry, dist_dir=dist_dir)
    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, OPS_TOKEN)

    with TestClient(app) as client:
        status = dashboard_status(client, OPS_TOKEN)

    assert status == 200


def test_ac10_the_app_keeps_the_token_it_started_with(
    registry: RoomRegistry, dist_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, OPS_TOKEN)
    app = create_app(rooms=registry, dist_dir=dist_dir)

    with TestClient(app) as client:
        monkeypatch.delenv(OPERATOR_TOKEN_VARIABLE)
        status = dashboard_status(client, OPS_TOKEN)

    assert status == 200


def test_ac10_a_token_given_to_create_app_wins_over_the_variable(
    registry: RoomRegistry, dist_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, OTHER_TOKEN)
    app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)

    with TestClient(app) as client:
        given = dashboard_status(client, OPS_TOKEN)
        from_the_variable = dashboard_status(client, OTHER_TOKEN)

    assert (given, from_the_variable) == (200, 401)


@pytest.mark.parametrize("value", [SHORT_TOKEN, DOLLAR_TOKEN])
def test_ac10_an_invalid_variable_fails_the_apps_startup_with_settings_error(
    registry: RoomRegistry,
    dist_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    from nock.settings import SettingsError

    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, value)
    app = create_app(rooms=registry, dist_dir=dist_dir)

    with pytest.raises(SettingsError, match=OPERATOR_TOKEN_VARIABLE) as caught:
        start_and_stop(app)

    assert value not in str(caught.value)


# ---- AC-10: a token given to create_app follows the same rule ------------------------


# Each path of the operator pages, with the unknown path that rule 1 compares it
# with: one under /api/ for the ops API, any unknown path for /ops.
PAGES_OFF_REQUESTS = [
    pytest.param(DASHBOARD_PATH, UNKNOWN_API_PATH, id="dashboard"),
    pytest.param(edits_path(GIVEN_ROOM), UNKNOWN_API_PATH, id="replay"),
    pytest.param(OPS_PAGE_PATH, UNKNOWN_PATH, id="ops-page"),
]
# "`""` turns the pages off whatever NOCK_OPERATOR_TOKEN holds."
VARIABLE_VALUES = [
    pytest.param(OPS_TOKEN, id="variable-ops-token"),
    pytest.param(SHORT_TOKEN, id="variable-breaking-the-rule"),
]


@pytest.mark.usefixtures("given_room")
@pytest.mark.parametrize("variable", VARIABLE_VALUES)
@pytest.mark.parametrize(("path", "unknown_path"), PAGES_OFF_REQUESTS)
def test_ac10_create_app_with_an_empty_token_has_the_pages_off_whatever_the_variable(
    registry: RoomRegistry,
    dist_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    unknown_path: str,
    variable: str,
) -> None:
    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, variable)
    app = create_app(rooms=registry, dist_dir=dist_dir, operator_token="")

    with TestClient(app) as client:
        unknown = client.get(unknown_path, headers=bearer(OPS_TOKEN))
        response = client.get(path, headers=bearer(OPS_TOKEN))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert "cache-control" not in response.headers
    assert answer_of(response) == answer_of(unknown)


@pytest.mark.parametrize("value", [pytest.param("a", id="one-letter"), *REFUSED_VALUES])
def test_ac10_create_app_with_a_token_breaking_the_rule_raises_settings_error(
    registry: RoomRegistry, dist_dir: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    from nock.settings import SettingsError

    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, OPS_TOKEN)

    # When create_app is called, not when the app starts.
    with pytest.raises(SettingsError):
        create_app(rooms=registry, dist_dir=dist_dir, operator_token=value)


@pytest.mark.parametrize("value", REFUSED_VALUES)
def test_ac10_the_message_of_create_apps_settings_error_never_holds_the_token(
    registry: RoomRegistry, dist_dir: Path, value: str
) -> None:
    from nock.settings import SettingsError

    with pytest.raises(SettingsError) as caught:
        create_app(rooms=registry, dist_dir=dist_dir, operator_token=value)

    message = str(caught.value)
    shown: list[str] = []
    for form in forms_of(value):
        if form in message:
            shown.append(form)
    assert shown == [], message


def test_ac10_a_token_given_to_create_app_leaves_the_variable_unread(
    registry: RoomRegistry, dist_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The variable is read only when no token is given (None): one that breaks
    # the rule does not stop the app's startup.
    monkeypatch.setenv(OPERATOR_TOKEN_VARIABLE, SHORT_TOKEN)
    app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)

    with TestClient(app) as client:
        status = dashboard_status(client, OPS_TOKEN)

    assert status == 200
