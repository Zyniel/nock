"""Tests of lobby/rooms, AC-16 and AC-17: `NOCK_ROOMS_PER_ADDRESS_PER_HOUR`.

Read three ways:

- AC-16: an app that builds its own registry (so it reads the variable when it
  starts), served by `TestClient`, on the real clock; creations come from one
  address.
- AC-17: `nock.__main__.main()` in the test process with `uvicorn.Server.run`
  replaced by a recorder, `python -m nock` in a subprocess, and the same app
  started with a refused value.

The shared setup is in `rooms_harness`.

Readings of the spec's wording:

- "`"10000"` is taken": the app starts and lets 31 creations of one address
  through, one more than the default limit, which tells it from the default.
- Rule 14's order of checks (after the five variables of `lobby/lifetime.md`,
  before the account variables) has no criterion of its own; it is checked with
  AC-17 because a refused value is what shows it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

import nock.server
import nock.settings
from lifetime_harness import CREATOR, SWEEP_VARIABLE, variables_of
from nock.catalogue import Catalogue
from nock.grid import Grid
from rooms_harness import (
    DEFAULT_LIMIT,
    LIMIT_VARIABLE,
    TOO_MANY_REQUESTS,
    post_room,
    post_rooms,
    record_server_runs,
    refusal_of_main,
    run_python_m_nock,
)
from spec011_harness import make_dist_dir
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text

BELOW_THE_LIVES = "23"
ARABIC_INDIC_THREE = "\N{ARABIC-INDIC DIGIT THREE}"
REFUSED_LIMITS = [
    "0",
    "10001",
    " 30",
    "3.0",
    "-1",
    ARABIC_INDIC_THREE,
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


# ---- AC-16: the accepted values ----------------------------------------------------


@pytest.mark.parametrize(
    ("value", "limit"), [("3", 3), ("0003", 3), ("1", 1)], ids=["3", "0003", "1"]
)
def test_ac16_the_creation_after_the_limit_answers_429(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    value: str,
    limit: int,
) -> None:
    variables_of(monkeypatch, {LIMIT_VARIABLE: value})
    app = nock.server.create_app(dist_dir=make_dist_dir(tmp_path), catalogue=catalogue)

    with TestClient(app) as client:
        within_the_limit = post_rooms(client, limit)
        refused = post_room(client)

    assert within_the_limit == [201] * limit
    assert refused.status_code == 429
    assert refused.json() == TOO_MANY_REQUESTS


def test_ac16_ten_thousand_is_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, catalogue: Catalogue
) -> None:
    variables_of(monkeypatch, {LIMIT_VARIABLE: "10000"})
    app = nock.server.create_app(dist_dir=make_dist_dir(tmp_path), catalogue=catalogue)

    with TestClient(app) as client:
        statuses = post_rooms(client, DEFAULT_LIMIT + 1)

    assert statuses == [201] * (DEFAULT_LIMIT + 1)


# ---- AC-17: the refused values -----------------------------------------------------


@pytest.mark.parametrize("value", REFUSED_LIMITS, ids=repr)
def test_ac17_main_stops_with_a_message_naming_the_variable_and_the_value(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    value: str,
) -> None:
    message = refusal_of_main(monkeypatch, server_runs, {LIMIT_VARIABLE: value})

    assert LIMIT_VARIABLE in message
    assert repr(value) in message
    assert "\n" not in message


def test_ac17_python_m_nock_prints_the_refusal_on_stderr_and_exits_with_1() -> None:
    completed = run_python_m_nock({LIMIT_VARIABLE: "0"})

    assert LIMIT_VARIABLE in completed.stderr, completed.stderr
    assert repr("0") in completed.stderr, completed.stderr
    assert completed.returncode == 1


@pytest.mark.parametrize("value", REFUSED_LIMITS, ids=repr)
def test_ac17_an_app_starting_with_a_refused_value_fails_with_settings_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, catalogue: Catalogue, value: str
) -> None:
    variables_of(monkeypatch, {LIMIT_VARIABLE: value})
    app = nock.server.create_app(dist_dir=make_dist_dir(tmp_path), catalogue=catalogue)

    with (
        pytest.raises(nock.settings.SettingsError, match=LIMIT_VARIABLE),
        TestClient(app),
    ):
        pass


def test_ac17_main_serves_when_the_limit_is_within_its_bounds(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    variables_of(monkeypatch, {LIMIT_VARIABLE: "0010"})
    from nock.__main__ import main

    main()

    assert len(server_runs) == 1
    assert os.environ[LIMIT_VARIABLE] == "0010", "main() changed it"


@pytest.mark.parametrize(
    ("variables", "named", "not_named"),
    [
        ({"NOCK_PORT": "0"}, "NOCK_PORT", LIMIT_VARIABLE),
        ({CREATOR.variable: BELOW_THE_LIVES}, CREATOR.variable, LIMIT_VARIABLE),
        ({SWEEP_VARIABLE: "0"}, SWEEP_VARIABLE, LIMIT_VARIABLE),
        (
            {
                "NOCK_PUBLIC_URL": "https://nock.example.org",
                "NOCK_SMTP_HOST": "smtp.example.org",
            },
            LIMIT_VARIABLE,
            "NOCK_SMTP_FROM",
        ),
    ],
    ids=["port", "room-life", "sweep-interval", "account-variables"],
)
def test_ac17_main_checks_the_limit_after_the_room_lives_and_before_the_accounts(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    variables: dict[str, str],
    named: str,
    not_named: str,
) -> None:
    # Each case holds a refused limit as well as the variable of its own.
    message = refusal_of_main(
        monkeypatch, server_runs, {**variables, LIMIT_VARIABLE: "0"}
    )

    assert named in message
    assert not_named not in message
