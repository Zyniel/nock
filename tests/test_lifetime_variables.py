"""Tests of lobby/lifetime, AC-7 to AC-10 (first part): the five variables.

`NOCK_CREATOR_SOLVED_ROOM_HOURS`, `NOCK_CREATOR_ROOM_HOURS`,
`NOCK_ANONYMOUS_SOLVED_ROOM_HOURS`, `NOCK_ANONYMOUS_ROOM_HOURS` and
`NOCK_EXPIRY_SWEEP_MINUTES`, read four ways:

- AC-7 and AC-8: `nock.settings.room_config_from_env` on a plain dict.
- AC-8 and AC-9: `nock.__main__.main()` in the test process, with
  `uvicorn.Server.run` replaced by a recorder (a `main()` that does not refuse
  a value records a run instead of serving), and `python -m nock` in a subprocess.
- AC-8 and AC-10: the app of `create_app` started with `TestClient`, which reads
  the variables when it has no registry to use. The registry it builds is read
  through a subclass of `RoomRegistry` that `nock.server` is made to use.

The names this change adds (`room_config_from_env`, the hour fields) are used
inside the tests that need them. The shared setup is in `lifetime_harness`; the
sweeps of a running app (AC-10, second part) are in `test_lifetime_sweep.py`.

Reading taken where the spec leaves room: rule 7's "Each of the five variables"
makes the digits-only rule hold for the sweep interval as well, so it is checked
there with the same kind of values as AC-8 lists for the lives.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

import nock.server
import nock.settings
from lifetime_harness import (
    ANONYMOUS,
    ANONYMOUS_SOLVED,
    CREATOR,
    CREATOR_SOLVED,
    DEFAULT_LIFE_HOURS,
    DEFAULT_SWEEP_SECONDS,
    LIVES,
    STARTUP_VARIABLES,
    SWEEP_VARIABLE,
    Life,
    variables_of,
)
from nock.hub import RoomRegistry
from nock.room import Clock, RoomConfig
from nock.store import RoomStore
from spec032_harness import make_dist_dir

LIFE_IDS = [life.field for life in LIVES]
PROCESS_EXIT_LIMIT_SECONDS = 30.0
BELOW_THE_LIVES = "23"
ABOVE_THE_LIVES = "8761"

# What AC-8 refuses for a life, with "+24", a full-width "24" and a trailing newline
# added: every value is something other than ASCII digits, or out of 24 to 8760.
REFUSED_LIFE_VALUES = [
    BELOW_THE_LIVES,
    ABOVE_THE_LIVES,
    " 24",
    "24.0",
    "-24",
    "24h",
    "\N{ARABIC-INDIC DIGIT TWO}\N{ARABIC-INDIC DIGIT FOUR}",
    "+24",
    "\N{FULLWIDTH DIGIT TWO}\N{FULLWIDTH DIGIT FOUR}",
    "24\n",
    "0",
]
REFUSED_SWEEP_VALUES = [
    "0",
    "1441",
    " 1",
    "1.0",
    "-1",
    "1m",
    "\N{ARABIC-INDIC DIGIT ONE}",
    "+1",
    "1\n",
]


def lives_of(config: RoomConfig) -> dict[str, int]:
    """The four hour fields of a config, by name."""
    return {
        CREATOR_SOLVED.field: getattr(config, CREATOR_SOLVED.field),
        CREATOR.field: getattr(config, CREATOR.field),
        ANONYMOUS_SOLVED.field: getattr(config, ANONYMOUS_SOLVED.field),
        ANONYMOUS.field: getattr(config, ANONYMOUS.field),
    }


def default_lives() -> dict[str, int]:
    """Each life at its default."""
    return {life.field: DEFAULT_LIFE_HOURS for life in LIVES}


def refusal_of(variable: str, value: str) -> str:
    """The message `room_config_from_env` refuses `value` of `variable` with."""
    with pytest.raises(nock.settings.SettingsError) as caught:
        nock.settings.room_config_from_env({variable: value})
    return str(caught.value)


# ---- AC-7: the defaults and the accepted values ----------------------------------


@pytest.mark.parametrize("empty", [False, True], ids=["unset", "empty"])
def test_ac7_unset_or_empty_variables_take_720_hours_and_a_3600_second_sweep(
    empty: bool,
) -> None:
    environ: dict[str, str] = {}
    if empty:
        for variable in STARTUP_VARIABLES:
            environ[variable] = ""

    config = nock.settings.room_config_from_env(environ)

    assert lives_of(config) == default_lives()
    assert config.expiry_sweep_seconds == DEFAULT_SWEEP_SECONDS


@pytest.mark.parametrize("life", LIVES, ids=LIFE_IDS)
@pytest.mark.parametrize(
    ("text", "hours"),
    [
        ("0024", 24),
        ("24", 24),
        ("8760", 8760),
        ("08760", 8760),
        ("0" * 5000 + "24", 24),
    ],
    ids=["leading-zeros", "lower-bound", "upper-bound", "zero-8760", "5000-zeros"],
)
def test_ac7_a_life_takes_its_value_and_leaves_the_others_alone(
    life: Life, text: str, hours: int
) -> None:
    config = nock.settings.room_config_from_env({life.variable: text})

    expected = default_lives()
    expected[life.field] = hours
    assert lives_of(config) == expected
    assert config.expiry_sweep_seconds == DEFAULT_SWEEP_SECONDS


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("1", 60.0), ("01", 60.0), ("1440", 86_400.0), ("60", 3_600.0)],
)
def test_ac7_the_sweep_interval_is_read_in_minutes_and_kept_in_seconds(
    text: str, seconds: float
) -> None:
    config = nock.settings.room_config_from_env({SWEEP_VARIABLE: text})

    assert config.expiry_sweep_seconds == seconds
    assert isinstance(config.expiry_sweep_seconds, float)
    assert lives_of(config) == default_lives()


def test_ac7_the_lives_are_whole_hours() -> None:
    config = nock.settings.room_config_from_env({ANONYMOUS.variable: "48"})

    assert isinstance(config.anonymous_room_hours, int)


def test_ac7_the_other_fields_of_the_config_stay_at_their_defaults() -> None:
    environ = {life.variable: "48" for life in LIVES}
    environ[SWEEP_VARIABLE] = "5"

    config = nock.settings.room_config_from_env(environ)

    expected = RoomConfig.model_validate(
        {
            **{life.field: 48 for life in LIVES},
            "expiry_sweep_seconds": 300.0,
        }
    )
    assert config == expected


# ---- AC-8: refused values -----------------------------------------------------------


@pytest.mark.parametrize("life", LIVES, ids=LIFE_IDS)
@pytest.mark.parametrize("value", REFUSED_LIFE_VALUES, ids=repr)
def test_ac8_a_life_refuses_a_value_that_is_not_24_to_8760_in_ascii_digits(
    life: Life, value: str
) -> None:
    message = refusal_of(life.variable, value)

    assert life.variable in message
    assert repr(value) in message
    assert "\n" not in message


@pytest.mark.parametrize("value", REFUSED_SWEEP_VALUES, ids=repr)
def test_ac8_the_sweep_interval_refuses_a_value_that_is_not_1_to_1440_in_digits(
    value: str,
) -> None:
    message = refusal_of(SWEEP_VARIABLE, value)

    assert SWEEP_VARIABLE in message
    assert repr(value) in message
    assert "\n" not in message


def test_ac8_the_message_names_only_the_variable_that_is_refused() -> None:
    environ = {ANONYMOUS.variable: BELOW_THE_LIVES, CREATOR.variable: "48"}

    with pytest.raises(nock.settings.SettingsError) as caught:
        nock.settings.room_config_from_env(environ)

    assert ANONYMOUS.variable in str(caught.value)
    assert CREATOR.variable not in str(caught.value)


def test_ac8_python_m_nock_prints_the_refusal_on_stderr_and_exits_with_1() -> None:
    environment = dict(os.environ)
    for variable in STARTUP_VARIABLES:
        environment.pop(variable, None)
    environment[ANONYMOUS.variable] = BELOW_THE_LIVES

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
            f"python -m nock with {ANONYMOUS.variable}={BELOW_THE_LIVES} still ran "
            f"after {PROCESS_EXIT_LIMIT_SECONDS:.0f} s"
        )

    assert ANONYMOUS.variable in completed.stderr, completed.stderr
    assert repr(BELOW_THE_LIVES) in completed.stderr, completed.stderr
    assert completed.returncode == 1


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        *[(life.variable, BELOW_THE_LIVES) for life in LIVES],
        (SWEEP_VARIABLE, "0"),
    ],
    ids=[*LIFE_IDS, "expiry_sweep_minutes"],
)
def test_ac8_an_app_with_no_registry_fails_its_start_with_settings_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    variables_of(monkeypatch, {variable: value})
    app = nock.server.create_app(dist_dir=make_dist_dir(tmp_path))

    with pytest.raises(nock.settings.SettingsError, match=variable), TestClient(app):
        pass


def test_ac8_an_app_given_a_registry_uses_its_config_and_reads_no_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    variables_of(monkeypatch, {ANONYMOUS.variable: BELOW_THE_LIVES})
    registry = RoomRegistry()
    app = nock.server.create_app(rooms=registry, dist_dir=make_dist_dir(tmp_path))

    try:
        with TestClient(app):
            config = registry.config
    finally:
        registry.close()

    assert config == RoomConfig()


# ---- AC-9: main() and the order of its checks ------------------------------------


@pytest.fixture
def server_runs(monkeypatch: pytest.MonkeyPatch) -> list[uvicorn.Config]:
    """Replace `uvicorn.Server.run` by a recorder; return the configs it recorded.

    `main()` hands uvicorn a server: the recorder keeps its config and serves
    nothing, so a `main()` that does not refuse a value leaves a record.
    """
    configs: list[uvicorn.Config] = []

    def record_run(server: uvicorn.Server, sockets: list[object] | None = None) -> None:
        configs.append(server.config)

    monkeypatch.setattr(uvicorn.Server, "run", record_run)
    return configs


def refusal_of_main(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    variables: dict[str, str],
) -> str:
    """Call `main()` under only `variables`; return the message it stops with."""
    variables_of(monkeypatch, variables)
    from nock.__main__ import main

    with pytest.raises(SystemExit) as caught:
        main()

    message = caught.value.code
    assert isinstance(message, str), f"the SystemExit code {message!r} is no message"
    assert server_runs == [], "main() served after a refused value"
    return message


def test_ac9_a_refused_port_is_named_before_a_refused_life(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    variables = {"NOCK_PORT": "0", CREATOR.variable: BELOW_THE_LIVES}

    message = refusal_of_main(monkeypatch, server_runs, variables)

    assert "NOCK_PORT" in message
    assert CREATOR.variable not in message


def test_ac9_a_refused_life_is_named_before_the_account_variables(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    # A public URL and an SMTP host without NOCK_SMTP_FROM is refused as well.
    variables = {
        "NOCK_PUBLIC_URL": "https://nock.example.org",
        "NOCK_SMTP_HOST": "smtp.example.org",
        CREATOR.variable: BELOW_THE_LIVES,
    }

    message = refusal_of_main(monkeypatch, server_runs, variables)

    assert CREATOR.variable in message
    assert "NOCK_SMTP_FROM" not in message


def test_ac9_the_account_variables_are_still_checked_when_the_lives_pass(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    variables = {
        "NOCK_PUBLIC_URL": "https://nock.example.org",
        "NOCK_SMTP_HOST": "smtp.example.org",
        CREATOR.variable: "48",
    }

    message = refusal_of_main(monkeypatch, server_runs, variables)

    assert "NOCK_SMTP_FROM" in message


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        *[(life.variable, ABOVE_THE_LIVES) for life in LIVES],
        (SWEEP_VARIABLE, "1441"),
    ],
    ids=[*LIFE_IDS, "expiry_sweep_minutes"],
)
def test_ac9_main_refuses_each_variable_naming_it_and_its_value(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    variable: str,
    value: str,
) -> None:
    message = refusal_of_main(monkeypatch, server_runs, {variable: value})

    assert variable in message
    assert repr(value) in message
    assert "\n" not in message


def test_ac9_main_serves_when_the_five_variables_are_within_their_bounds(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    variables = {life.variable: "24" for life in LIVES}
    variables[SWEEP_VARIABLE] = "1440"
    variables_of(monkeypatch, variables)
    from nock.__main__ import main

    main()

    assert len(server_runs) == 1
    for variable in variables:
        assert os.environ[variable] == variables[variable], "main() changed it"


# ---- AC-10: the registry an app builds from the variables ----------------------------


def test_ac10_an_app_with_no_registry_builds_one_with_the_lives_of_the_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    variables_of(
        monkeypatch,
        {
            SWEEP_VARIABLE: "1",
            CREATOR_SOLVED.variable: "101",
            CREATOR.variable: "202",
            ANONYMOUS_SOLVED.variable: "303",
            ANONYMOUS.variable: "404",
        },
    )
    built: list[RoomRegistry] = []

    class RecordingRegistry(RoomRegistry):
        """A registry that `nock.server` builds, kept for the test to read."""

        def __init__(
            self,
            config: RoomConfig | None = None,
            clock: Clock | None = None,
            store: RoomStore | None = None,
        ) -> None:
            super().__init__(config=config, clock=clock, store=store)
            built.append(self)

    monkeypatch.setattr(nock.server, "RoomRegistry", RecordingRegistry)
    app = nock.server.create_app(dist_dir=make_dist_dir(tmp_path))

    with TestClient(app):
        pass

    assert len(built) == 1
    assert lives_of(built[0].config) == {
        CREATOR_SOLVED.field: 101,
        CREATOR.field: 202,
        ANONYMOUS_SOLVED.field: 303,
        ANONYMOUS.field: 404,
    }
    assert built[0].config.expiry_sweep_seconds == 60.0
