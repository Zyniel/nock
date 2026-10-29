"""Tests of admin/overrides, AC-1 to AC-5: the settings routes `GET` and `PUT`.

Every test runs on an app given no registry (`env_app`), so that the variables
are the environment values and an unset variable means `environment` null; the
registry, the store and the log it builds are not seen, only the routes.
`TestClient` carries no real time: no test measures a duration.

Readings taken where the spec leaves room:

- AC-2's `durable` is read on the app's own store: `NOCK_DATABASE` a file gives
  true, unset gives false.
- AC-2's edge case (a registry given with an interval that is a fraction of a
  minute) is checked with a registry of `expiry_sweep_seconds` 30: the interval's
  `environment` and `value` read 0.5.
- The bounds are inclusive on both sides (rule 4: "within the bounds"; the
  variable's own bounds are 24 to 8760 and 1 to 1440).
- Rule 3's `environment` is null only when the variable is unset (the lead's
  reading): on an app given no registry it is the variable's value whenever the
  variable is set to a value `room_config_from_env` accepts, even one equal to
  the default (a refused value counts as unset); on an app given a registry the
  config's values are the environment values (`overrides_harness`).

The shared setup is in `overrides_harness`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lifetime_harness import (
    ANONYMOUS,
    CREATOR,
    CREATOR_SOLVED,
    SWEEP_VARIABLE,
    config_with_lives,
)
from overrides_harness import (
    INTERVAL,
    SETTING_NAMES,
    body_of,
    default_rows,
    env_app,
    expected_row,
    registry_app,
    rows_of,
)

CREATOR_NAME = CREATOR.field
ANONYMOUS_NAME = ANONYMOUS.field


# ---- AC-1: the effective value and its source ----


def test_ac1_with_no_variable_and_no_override_the_value_is_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch) as ops:
        row = ops.row(CREATOR_NAME)

    assert row["value"] == 720
    assert row["source"] == "default"
    assert row["environment"] is None
    assert row["override"] is None


def test_ac1_a_variable_gives_the_environment_value_and_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch, {CREATOR.variable: "48"}) as ops:
        row = ops.row(CREATOR_NAME)

    assert row == expected_row(
        CREATOR_NAME, value=48, source="environment", environment=48
    )


def test_ac1_an_override_outranks_the_variable_and_keeps_it_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch, {CREATOR.variable: "48"}) as ops:
        saved = ops.put(CREATOR_NAME, 96)

        row = rows_of(saved)[CREATOR_NAME]

    assert row == expected_row(
        CREATOR_NAME, value=96, source="override", environment=48, override=96
    )


def test_ac1_an_override_equal_to_the_variable_is_still_an_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch, {CREATOR.variable: "48"}) as ops:
        saved = ops.put(CREATOR_NAME, 48)

        row = rows_of(saved)[CREATOR_NAME]

    assert row == expected_row(
        CREATOR_NAME, value=48, source="override", environment=48, override=48
    )


@pytest.mark.parametrize(
    ("name", "variable", "text", "value"),
    [
        (CREATOR_NAME, CREATOR.variable, "720", 720),
        (INTERVAL, SWEEP_VARIABLE, "60", 60),
    ],
    ids=["life-720", "interval-60"],
)
def test_ac1_a_variable_set_to_the_default_is_still_the_environment_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    variable: str,
    text: str,
    value: int,
) -> None:
    with env_app(tmp_path, monkeypatch, {variable: text}) as ops:
        row = ops.row(name)

    assert row == expected_row(
        name, value=value, source="environment", environment=value
    )


# ---- AC-2: the list ----


def test_ac2_the_five_settings_come_in_order_with_their_bounds_in_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch) as ops:
        response = ops.settings()

    assert response.status_code == 200, response.text
    assert response.json() == {"durable": False, "settings": default_rows()}
    assert list(rows_of(response)) == SETTING_NAMES


def test_ac2_durable_is_true_on_a_database_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch, database=True) as ops:
        response = ops.settings()

    assert response.status_code == 200, response.text
    assert body_of(response)["durable"] is True


def test_ac2_a_fraction_of_a_minute_is_the_intervals_environment_value(
    tmp_path: Path,
) -> None:
    config = config_with_lives(sweep_seconds=30.0)

    with registry_app(tmp_path, config=config) as running:
        row = running.ops.row(INTERVAL)

    assert row["environment"] == 0.5
    assert row["value"] == 0.5


# ---- AC-3: a save ----


def test_ac3_a_put_answers_the_list_with_that_row_overridden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch) as ops:
        response = ops.put(ANONYMOUS_NAME, 48)
        read_back = ops.settings()

    expected_rows = default_rows()
    expected_rows[3] = expected_row(
        ANONYMOUS_NAME, value=48, source="override", override=48
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"durable": False, "settings": expected_rows}
    assert read_back.json() == response.json()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        (CREATOR_NAME, 24),
        (CREATOR_NAME, 8760),
        (INTERVAL, 1),
        (INTERVAL, 1440),
    ],
    ids=["life-min", "life-max", "interval-min", "interval-max"],
)
def test_ac3_the_bounds_themselves_are_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, value: int
) -> None:
    with env_app(tmp_path, monkeypatch) as ops:
        response = ops.put(name, value)

    assert response.status_code == 200, response.text
    assert rows_of(response)[name]["override"] == value


# ---- AC-4: a reset ----


def test_ac4_a_reset_falls_back_to_the_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch, {ANONYMOUS.variable: "48"}) as ops:
        ops.put(ANONYMOUS_NAME, 96)

        response = ops.put(ANONYMOUS_NAME, None)

    assert response.status_code == 200, response.text
    assert rows_of(response)[ANONYMOUS_NAME] == expected_row(
        ANONYMOUS_NAME, value=48, source="environment", environment=48
    )


def test_ac4_a_reset_without_a_variable_falls_back_to_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch) as ops:
        ops.put(ANONYMOUS_NAME, 96)

        response = ops.put(ANONYMOUS_NAME, None)

    assert response.status_code == 200, response.text
    assert rows_of(response)[ANONYMOUS_NAME] == expected_row(ANONYMOUS_NAME)


def test_ac4_a_reset_of_a_setting_with_no_override_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    variables = {CREATOR_SOLVED.variable: "100", SWEEP_VARIABLE: "5"}
    with env_app(tmp_path, monkeypatch, variables) as ops:
        before = ops.settings().json()

        response = ops.put(ANONYMOUS_NAME, None)
        after = ops.settings().json()

    assert response.status_code == 200, response.text
    assert response.json() == before
    assert after == before


# ---- AC-5: refused bodies ----

REFUSED_BODIES = [
    pytest.param({"name": CREATOR_NAME, "value": 23}, id="life-23"),
    pytest.param({"name": CREATOR_NAME, "value": 8761}, id="life-8761"),
    pytest.param({"name": CREATOR_NAME, "value": 24.5}, id="life-24.5"),
    pytest.param({"name": CREATOR_NAME, "value": "24"}, id="life-text"),
    pytest.param({"name": CREATOR_NAME, "value": True}, id="life-true"),
    pytest.param({"name": INTERVAL, "value": 0}, id="interval-0"),
    pytest.param({"name": INTERVAL, "value": 1441}, id="interval-1441"),
    pytest.param({"name": "room_hours", "value": 48}, id="unknown-name"),
    pytest.param({"name": CREATOR_NAME}, id="no-value"),
    pytest.param({"value": 48}, id="no-name"),
]


@pytest.mark.parametrize("body", REFUSED_BODIES)
def test_ac5_a_refused_put_answers_422_and_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: dict[str, object]
) -> None:
    with env_app(tmp_path, monkeypatch) as ops:
        ops.put(ANONYMOUS_NAME, 96)
        before = ops.settings().json()

        response = ops.put_body(body)
        after = ops.settings().json()

    assert response.status_code == 422, response.text
    assert after == before
