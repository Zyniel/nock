"""Tests of admin/overrides, AC-11 to AC-14: a save at work.

AC-11 and AC-12 use `host_harness`'s app (accounts off, a file database, a fake
clock) and a socket on room A, which is last edited at `T0` and met by the first
lookup at `T0` plus 30 hours, under the 720-hour lives. A save is a real `PUT`
over `TestClient`; "the registry's config" is `app.registry.config`. A lookup is
`registry.room_state`, which deletes an expired room before it answers
(`lobby/lifetime.md` rule 6). AC-12's sweep runs on a short real interval of the
registry's config (0.05 s), with the clock moved by hand; each wait is bounded and
ends as soon as the change is seen, so no test measures a duration.

AC-13 and AC-14 use an app given no registry (`env_app`): its variable is the
environment value, and the log is read with `caplog`.

Readings taken where the spec leaves room:

- AC-11's "a lookup half a second later" is a lookup after the fake clock moved
  half a second on.
- AC-13's record "holding" the name and the two values: its message holds the
  name as a whole word and, as its only runs of digits, the old then the new
  effective value.
- Rule 9's "a new interval starts after the sweep's current wait" has no criterion
  but AC-12's 120 seconds; it is not tested (it would need a pause of real time).

The shared setup is in `overrides_harness`.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

import pytest

from host_harness import open_member
from lifetime_harness import (
    ANONYMOUS,
    ANONYMOUS_SOLVED,
    CREATOR,
    HALF_SECOND,
    config_with_lives,
    stored_room,
    wait_until_deleted,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from overrides_harness import (
    INTERVAL,
    assert_socket_stays_open,
    body_of,
    env_app,
    hours_after_t0,
    names_row,
    numbers_in,
    ops_host_app,
    overrides_records,
    registry_app,
)
from spec017_harness import FakeClock
from spec032_harness import CODE_A, T0, grid_from_text
from spec038_harness import OPS_TOKEN

ROOM_NOT_FOUND_CLOSE_CODE = 4404
SHORT_SWEEP_SECONDS = 0.05


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-11: the next lookup ----


def test_ac11_a_save_applies_to_the_next_lookup_and_closes_the_room(
    tmp_path: Path,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    fx01_grid: Grid,
) -> None:
    config = config_with_lives()
    with (
        ops_host_app(tmp_path, fake_clock, monkeypatch, config, catalogue) as running,
        contextlib.ExitStack() as stack,
    ):
        app = running.app
        stored_room(app.store, fx01_grid, CODE_A, T0)
        fake_clock.now = hours_after_t0(30)
        owner = open_member(stack, app.client, CODE_A, "Ana")
        served = app.registry.room_state(CODE_A)
        before = app.registry.config

        saved = running.ops.put(ANONYMOUS.field, 24)
        assert saved.status_code == 200, saved.text
        after = app.registry.config
        fake_clock.advance(HALF_SECOND)
        met = app.registry.room_state(CODE_A)
        owner.wait_until(lambda: owner.close_code is not None, "the close of A")

        stored = app.store.has_room(CODE_A)
        close_code = owner.close_code

    assert served is not None
    assert after.anonymous_room_hours == 24
    assert after == before.model_copy(update={"anonymous_room_hours": 24})
    assert met is None
    assert stored is False
    assert close_code == ROOM_NOT_FOUND_CLOSE_CODE


# ---- AC-12: nothing at the save, then a lookup or a sweep ----


def test_ac12_saving_deletes_nothing_by_itself_until_a_lookup(
    tmp_path: Path,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    fx01_grid: Grid,
) -> None:
    config = config_with_lives()
    with (
        ops_host_app(tmp_path, fake_clock, monkeypatch, config, catalogue) as running,
        contextlib.ExitStack() as stack,
    ):
        app = running.app
        stored_room(app.store, fx01_grid, CODE_A, T0)
        fake_clock.now = hours_after_t0(30)
        owner = open_member(stack, app.client, CODE_A, "Ana")

        saved = running.ops.put(ANONYMOUS.field, 24)
        assert saved.status_code == 200, saved.text
        stored_after_the_save = app.store.has_room(CODE_A)
        assert_socket_stays_open(owner)
        met = app.registry.room_state(CODE_A)

    assert stored_after_the_save is True
    assert met is None


def test_ac12_the_sweep_after_a_save_deletes_the_room(
    tmp_path: Path,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    fx01_grid: Grid,
) -> None:
    config = config_with_lives(sweep_seconds=SHORT_SWEEP_SECONDS)
    with (
        ops_host_app(tmp_path, fake_clock, monkeypatch, config, catalogue) as running,
        contextlib.ExitStack() as stack,
    ):
        app = running.app
        stored_room(app.store, fx01_grid, CODE_A, T0)
        fake_clock.now = hours_after_t0(30)
        owner = open_member(stack, app.client, CODE_A, "Ana")
        assert_socket_stays_open(owner)

        saved = running.ops.put(ANONYMOUS.field, 24)
        assert saved.status_code == 200, saved.text
        wait_until_deleted(app.store, CODE_A)
        owner.wait_until(lambda: owner.close_code is not None, "the close of A")

        close_code = owner.close_code

    assert close_code == ROOM_NOT_FOUND_CLOSE_CODE


def test_ac12_a_new_interval_is_held_in_seconds_by_the_config(tmp_path: Path) -> None:
    with registry_app(tmp_path) as running:
        before = running.registry.config

        saved = running.ops.put(INTERVAL, 2)
        after = running.registry.config

    assert saved.status_code == 200, saved.text
    assert after.expiry_sweep_seconds == 120.0
    assert after == before.model_copy(update={"expiry_sweep_seconds": 120.0})


# ---- AC-13: the log ----

CREATOR_VARIABLE_HOURS = "24"


@pytest.mark.parametrize(
    ("earlier_saves", "value", "numbers"),
    [
        pytest.param([], 48, ["24", "48"], id="save"),
        pytest.param([48], None, ["48", "24"], id="reset"),
        pytest.param([], None, ["24", "24"], id="reset-with-no-override"),
    ],
)
def test_ac13_each_200_of_a_put_logs_one_info_record_of_the_old_and_new_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    earlier_saves: list[int],
    value: int | None,
    numbers: list[str],
) -> None:
    caplog.set_level(logging.INFO)
    variables = {CREATOR.variable: CREATOR_VARIABLE_HOURS}
    with env_app(tmp_path, monkeypatch, variables) as ops:
        for earlier in earlier_saves:
            assert ops.put(CREATOR.field, earlier).status_code == 200
        caplog.clear()

        response = ops.put(CREATOR.field, value)

    records = overrides_records(caplog.records, logging.INFO)
    assert response.status_code == 200, response.text
    assert len(records) == 1, [record.getMessage() for record in records]
    message = records[0].getMessage()
    assert names_row(message, CREATOR.field, numbers[0])
    assert numbers_in(message) == numbers
    assert OPS_TOKEN not in caplog.text


def test_ac13_a_422_logs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    variables = {CREATOR.variable: CREATOR_VARIABLE_HOURS}
    with env_app(tmp_path, monkeypatch, variables) as ops:
        caplog.clear()

        response = ops.put(CREATOR.field, 23)

    assert response.status_code == 422, response.text
    for level in (logging.INFO, logging.WARNING, logging.ERROR):
        assert overrides_records(caplog.records, level) == []


# ---- AC-14: the dashboard periods follow the effective lives ----


def test_ac14_the_dashboard_periods_follow_a_save_and_its_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = ANONYMOUS_SOLVED.field
    with env_app(tmp_path, monkeypatch) as ops:
        initially = body_of(ops.dashboard())

        saved = ops.put(name, 100)
        shortened = body_of(ops.dashboard())
        refused = ops.dashboard("?days=7")

        reset = ops.put(name, None)
        restored = body_of(ops.dashboard())

    assert (initially["offered_days"], initially["days"]) == ([1, 7, 30], 7)
    assert saved.status_code == 200, saved.text
    assert (shortened["offered_days"], shortened["days"]) == ([1], 1)
    assert refused.status_code == 422, refused.text
    assert reset.status_code == 200, reset.text
    assert (restored["offered_days"], restored["days"]) == ([1, 7, 30], 7)
