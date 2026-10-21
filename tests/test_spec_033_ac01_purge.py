"""Tests of spec 033, AC-1: the purge of old sign-in links and sessions.

Python, each case on a new `AccountStore(tmp_path / "nock.sqlite3")`. A link asked
at 0.0 is gone after `purge(1_801.0)`: `use_link(token, 0.0)`, at a time when the
link is not too old, gives None, so only the purge can have removed it; and the
database files (`nock.sqlite3` and `nock.sqlite3-wal`, as "Database bytes" of the
"Test harness" reads them) then hold no byte of its address, which they held
before. A session started at 0.0 is gone after `purge(7_776_001.0)`. A link and a
session just under their life are kept: `purge(1_799.0)` and `purge(7_775_999.0)`.

App: a link asked before the app starts is gone after the sweep that the app runs
when it starts (spec 032). The store given to `create_app` is a subclass whose
`purge` calls the original, then sets a `threading.Event`; the test waits for that
event, since the spec does not say that the start waits for its sweep, and
`use_link` cannot be polled (it deletes the link it finds).

The shared setup is in `spec033_harness`, `spec032_harness` (the configuration on
which no tick changes anything) and `spec017_harness` (the fake clock).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest
from fastapi.testclient import TestClient

from nock.hub import RoomRegistry
from nock.server import create_app
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec032_harness import NO_TICK_CONFIG
from spec033_harness import (
    ANA_EMAIL,
    DATABASE_FILE_NAME,
    WAIT_SECONDS,
    RecordingMailer,
    account_settings,
    database_bytes,
    strings_in,
)

if TYPE_CHECKING:
    from nock.accounts import AccountStore

LINK_ASKED_AT = 0.0
JUST_PAST_A_LINK = 1_801.0  # LINK_LIFE_SECONDS + 1
JUST_UNDER_A_LINK = 1_799.0  # LINK_LIFE_SECONDS - 1
JUST_PAST_A_SESSION = 7_776_001.0  # SESSION_LIFE_SECONDS + 1
JUST_UNDER_A_SESSION = 7_775_999.0  # SESSION_LIFE_SECONDS - 1


@pytest.fixture
def account_store(tmp_path: Path) -> Iterator[AccountStore]:
    """A new `AccountStore` on `tmp_path / "nock.sqlite3"`, closed at the end."""
    from nock.accounts import AccountStore

    store = AccountStore(tmp_path / DATABASE_FILE_NAME)
    yield store
    store.close()


# ---- A link -------------------------------------------------------------------


def test_ac1_purge_the_files_hold_the_address_of_a_link_before_the_purge(
    tmp_path: Path, account_store: AccountStore
) -> None:
    account_store.add_link(ANA_EMAIL, None, LINK_ASKED_AT)

    data = database_bytes(tmp_path / DATABASE_FILE_NAME)

    assert strings_in(data, [ANA_EMAIL]) == [ANA_EMAIL]


def test_ac1_purge_removes_a_link_older_than_its_life(
    account_store: AccountStore,
) -> None:
    token = account_store.add_link(ANA_EMAIL, None, LINK_ASKED_AT)

    account_store.purge(JUST_PAST_A_LINK)

    assert account_store.use_link(token, LINK_ASKED_AT) is None


def test_ac1_purge_leaves_no_byte_of_the_purged_address_in_the_files(
    tmp_path: Path, account_store: AccountStore
) -> None:
    account_store.add_link(ANA_EMAIL, None, LINK_ASKED_AT)

    account_store.purge(JUST_PAST_A_LINK)
    data = database_bytes(tmp_path / DATABASE_FILE_NAME)

    assert strings_in(data, [ANA_EMAIL]) == []


def test_ac1_purge_keeps_a_link_just_under_its_life(
    account_store: AccountStore,
) -> None:
    from nock.accounts import LinkUse

    token = account_store.add_link(ANA_EMAIL, None, LINK_ASKED_AT)

    account_store.purge(JUST_UNDER_A_LINK)

    used = account_store.use_link(token, LINK_ASKED_AT)
    assert used == LinkUse(email=ANA_EMAIL, room=None)


# ---- A session ----------------------------------------------------------------


def test_ac1_purge_removes_a_session_older_than_its_life(
    account_store: AccountStore,
) -> None:
    session = account_store.sign_in(ANA_EMAIL, 0.0).session

    account_store.purge(JUST_PAST_A_SESSION)

    assert account_store.account_of_session(session, 0.0) is None


def test_ac1_purge_keeps_a_session_just_under_its_life(
    account_store: AccountStore,
) -> None:
    from nock.accounts import Account

    started = account_store.sign_in(ANA_EMAIL, 0.0)

    account_store.purge(JUST_UNDER_A_SESSION)

    account = account_store.account_of_session(started.session, 0.0)
    assert account == Account(account_id=started.account_id, email=ANA_EMAIL)


# ---- The sweep the app runs when it starts ------------------------------------


class SignallingStore(NamedTuple):
    """An account store whose `purge` is watched, and what it saw."""

    store: AccountStore
    purged: threading.Event  # set once a `purge` has finished
    purged_at: list[float]  # the time of each finished `purge`, in order


def purge_signalling_store(path: Path) -> SignallingStore:
    """An `AccountStore` on `path` whose `purge` calls the original, then signals."""
    from nock.accounts import AccountStore

    purged = threading.Event()
    purged_at: list[float] = []

    class SignallingAccountStore(AccountStore):
        def purge(self, now: float) -> None:
            super().purge(now)
            purged_at.append(now)
            purged.set()

    return SignallingStore(SignallingAccountStore(path), purged, purged_at)


def test_ac1_purge_the_sweep_at_the_start_of_the_app_removes_an_old_link(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    database_path = tmp_path / DATABASE_FILE_NAME
    watched = purge_signalling_store(database_path)
    account_store = watched.store
    room_store = RoomStore(database_path)
    registry = RoomRegistry(clock=fake_clock, store=room_store, config=NO_TICK_CONFIG)
    try:
        asked_at = fake_clock()
        token = account_store.add_link(ANA_EMAIL, None, asked_at)
        fake_clock.advance(JUST_PAST_A_LINK)  # 1,801 seconds
        sweep_time = fake_clock()
        app = create_app(
            rooms=registry,
            dist_dir=tmp_path,
            accounts=account_settings(),
            account_store=account_store,
            mailer=RecordingMailer(),
        )

        with TestClient(app):
            was_purged = watched.purged.wait(timeout=WAIT_SECONDS)
            purged_at = list(watched.purged_at)
            used = account_store.use_link(token, asked_at)
    finally:
        account_store.close()
        registry.close()
        room_store.close()

    assert was_purged is True, "the app ran no purge when it started"
    assert purged_at[0] == sweep_time
    assert used is None
