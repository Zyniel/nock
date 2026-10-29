"""Tests of lobby/lifetime, AC-10 (second part): the sweeps of a running app.

The app of `host_harness` runs on a file database with accounts on and a sweep
every 0.05 s of real time (`expiry_sweep_seconds`), on the fake clock, so that
moving the clock is the only thing that expires a room and the next sweep, a
few hundredths of a second later, is the one that deletes it. No test measures a
duration: each wait is bounded and ends as soon as the change is seen.

Each cycle (run twice, to show that every sweep does it, not only the first):
the app has a room with one socket in it, and a sign-in link asked for an
address. The clock then moves past the room's life and the link's 30 minutes.
The sweep alone, with no lookup, deletes the room, closes its socket with 4404,
and purges the link. The link is seen through the database files: they hold its
address until the purge empties them (`database_bytes` of `spec033_harness`).

The shared setup is in `lifetime_harness` and `host_harness`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from host_harness import HostApp, create_room_as, host_app, open_member
from lifetime_harness import (
    HOUR,
    config_with_lives,
    wait_until_deleted,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import (
    ANA_EMAIL,
    ZELIE_EMAIL,
    ask_link,
    database_bytes,
    strings_in,
    wait_for,
)

ROOM_NOT_FOUND_CLOSE_CODE = 4404
SHORT_SWEEP_SECONDS = 0.05
ANONYMOUS_LIFE_HOURS = 24


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


def sweep_one_cycle(app: HostApp, email: str) -> None:
    """Make a room and a link, expire them by the clock, and see the sweep act."""
    with contextlib.ExitStack() as stack:
        code = create_room_as(app, None)
        player = open_member(stack, app.client, code, "Ana")
        asked = ask_link(app.client, email)
        assert asked.status_code == 202, asked.text
        assert strings_in(database_bytes(app.database_path), [email]) == [email]

        # Past the room's life and past the link's 30 minutes.
        app.clock.now += ANONYMOUS_LIFE_HOURS * HOUR + 1

        player.wait_until(lambda: player.close_code is not None, "the 4404 close")
        wait_until_deleted(app.store, code)
        wait_for(
            lambda: strings_in(database_bytes(app.database_path), [email]) == [],
            "the purge of the old sign-in link",
        )
        assert player.close_code == ROOM_NOT_FOUND_CLOSE_CODE


def test_ac10_each_sweep_deletes_the_rooms_expired_since_and_purges_old_links(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_with_lives(
        anonymous=ANONYMOUS_LIFE_HOURS, sweep_seconds=SHORT_SWEEP_SECONDS
    )

    with host_app(tmp_path, fake_clock, catalogue, monkeypatch, config=config) as app:
        sweep_one_cycle(app, ZELIE_EMAIL)
        sweep_one_cycle(app, ANA_EMAIL)
