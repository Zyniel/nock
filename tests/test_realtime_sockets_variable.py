"""Tests of platform/realtime, AC-23: `NOCK_SOCKETS_PER_ADDRESS`.

Read three ways, as `NOCK_ROOMS_PER_ADDRESS_PER_HOUR` is in `test_rooms_limit_variable`:

- the accepted values: an app that builds its own registry (so it reads the
  variable when it starts), served by `TestClient`, and sockets from one address;
- the refused values: `nock.__main__.main()` in the test process with
  `uvicorn.Server.run` replaced by a recorder, `python -m nock` in a subprocess,
  and the same app started with a refused value.

The shared setup is in `realtime_harness`, `rooms_harness` and `lifetime_harness`.

Readings of the spec's wording:

- "The third socket of an address closes with 4503" with the value `"2"`: the
  first two sockets are served (they ping and get a pong) and the third is closed
  with 4503 without a message. The sockets never join, which the cap does not
  need.
- "`"10000"` is taken": the app starts and serves 51 sockets of one address, one
  more than the default cap, which tells it from the default.
- The order of the checks (after `NOCK_ROOMS_PER_ADDRESS_PER_HOUR`, before the
  account variables) has no criterion of its own; it is checked here because a
  refused value is what shows it, in the way `test_rooms_limit_variable` does.
"""

from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

import nock.server
import nock.settings
from lifetime_harness import CREATOR, SWEEP_VARIABLE, variables_of
from nock.catalogue import Catalogue
from nock.grid import Grid
from realtime_harness import (
    DEFAULT_SOCKET_CAP,
    GRID_NUMBER,
    SOCKETS_VARIABLE,
    TOO_MANY_SOCKETS_CLOSE_CODE,
    fill_address,
    is_served,
    try_socket,
)
from rooms_harness import (
    LIMIT_VARIABLE,
    record_server_runs,
    refusal_of_main,
    run_python_m_nock,
)
from spec011_harness import make_dist_dir
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text

BELOW_THE_LIVES = "23"
ARABIC_INDIC_FIVE = "\N{ARABIC-INDIC DIGIT FIVE}"
REFUSED_CAPS = [
    "0",
    "10001",
    " 50",
    "5.0",
    "-1",
    ARABIC_INDIC_FIVE,
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


@pytest.fixture
def server_runs(monkeypatch: pytest.MonkeyPatch) -> list[uvicorn.Config]:
    return record_server_runs(monkeypatch)


def create_room_code(client: TestClient) -> str:
    """`POST /api/rooms` for the catalogue's grid; the code of the new room."""
    response = client.post("/api/rooms", json={"grid_number": GRID_NUMBER})
    assert response.status_code == 201, response.text
    code = response.json()["code"]
    assert isinstance(code, str)
    return code


# ---- The accepted values ------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "cap"), [("2", 2), ("0002", 2), ("1", 1)], ids=["2", "0002", "1"]
)
def test_ac23_the_socket_after_the_cap_is_closed_with_4503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    value: str,
    cap: int,
) -> None:
    variables_of(monkeypatch, {SOCKETS_VARIABLE: value})
    app = nock.server.create_app(dist_dir=make_dist_dir(tmp_path), catalogue=catalogue)

    with TestClient(app) as client, ExitStack() as stack:
        code = create_room_code(client)
        within_the_cap = fill_address(client, code, stack, cap)
        refused = try_socket(client, code, stack)

    assert [is_served(socket) for socket in within_the_cap] == [True] * cap
    assert refused.peer.close_code == TOO_MANY_SOCKETS_CLOSE_CODE
    assert refused.peer.messages() == []


def test_ac23_ten_thousand_is_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, catalogue: Catalogue
) -> None:
    variables_of(monkeypatch, {SOCKETS_VARIABLE: "10000"})
    app = nock.server.create_app(dist_dir=make_dist_dir(tmp_path), catalogue=catalogue)

    with TestClient(app) as client, ExitStack() as stack:
        code = create_room_code(client)
        sockets = fill_address(client, code, stack, DEFAULT_SOCKET_CAP + 1)

    assert [is_served(socket) for socket in sockets] == [True] * (
        DEFAULT_SOCKET_CAP + 1
    )


# ---- The refused values -------------------------------------------------------------


@pytest.mark.parametrize("value", REFUSED_CAPS, ids=repr)
def test_ac23_main_stops_with_a_message_naming_the_variable_and_the_value(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    value: str,
) -> None:
    message = refusal_of_main(monkeypatch, server_runs, {SOCKETS_VARIABLE: value})

    assert SOCKETS_VARIABLE in message
    assert repr(value) in message
    assert "\n" not in message


def test_ac23_python_m_nock_prints_the_refusal_on_stderr_and_exits_with_1() -> None:
    completed = run_python_m_nock({SOCKETS_VARIABLE: "0"})

    assert SOCKETS_VARIABLE in completed.stderr, completed.stderr
    assert repr("0") in completed.stderr, completed.stderr
    assert completed.returncode == 1


@pytest.mark.parametrize("value", REFUSED_CAPS, ids=repr)
def test_ac23_an_app_starting_with_a_refused_value_fails_with_settings_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, catalogue: Catalogue, value: str
) -> None:
    variables_of(monkeypatch, {SOCKETS_VARIABLE: value})
    app = nock.server.create_app(dist_dir=make_dist_dir(tmp_path), catalogue=catalogue)

    with (
        pytest.raises(nock.settings.SettingsError, match=SOCKETS_VARIABLE),
        TestClient(app),
    ):
        pass


def test_ac23_main_serves_when_the_cap_is_within_its_bounds(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    variables_of(monkeypatch, {SOCKETS_VARIABLE: "0010"})
    from nock.__main__ import main

    main()

    assert len(server_runs) == 1
    assert os.environ[SOCKETS_VARIABLE] == "0010", "main() changed it"


@pytest.mark.parametrize(
    ("variables", "named", "not_named"),
    [
        ({"NOCK_PORT": "0"}, "NOCK_PORT", SOCKETS_VARIABLE),
        ({CREATOR.variable: BELOW_THE_LIVES}, CREATOR.variable, SOCKETS_VARIABLE),
        ({SWEEP_VARIABLE: "0"}, SWEEP_VARIABLE, SOCKETS_VARIABLE),
        ({LIMIT_VARIABLE: "0"}, LIMIT_VARIABLE, SOCKETS_VARIABLE),
        (
            {
                "NOCK_PUBLIC_URL": "https://nock.example.org",
                "NOCK_SMTP_HOST": "smtp.example.org",
            },
            SOCKETS_VARIABLE,
            "NOCK_SMTP_FROM",
        ),
    ],
    ids=["port", "room-life", "sweep-interval", "creation-limit", "account-variables"],
)
def test_ac23_main_checks_the_cap_after_the_creation_limit_and_before_the_accounts(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    variables: dict[str, str],
    named: str,
    not_named: str,
) -> None:
    # Each case holds a refused cap as well as the variable of its own.
    message = refusal_of_main(
        monkeypatch, server_runs, {**variables, SOCKETS_VARIABLE: "0"}
    )

    assert named in message
    assert not_named not in message
