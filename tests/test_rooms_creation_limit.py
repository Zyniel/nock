"""Tests of lobby/rooms, AC-13 to AC-15: the creation limit per client address.

Over HTTP, with the app of `host_harness` on a fake clock: `app.client` comes from
one address and `other_address_client(app)` from another. The variable is unset
(or empty), so the limit is the default, 30 rooms in an hour. The shared setup is
in `rooms_harness`.

Readings of the spec's wording:

- "The first creation" of AC-13 is the only one of the thirty made at an earlier
  time: the other twenty-nine are made 10 s later, so that the boundary at 3,600 s
  is the first creation's alone (a request counts while its time `t` satisfies
  `t > now - 3600`).
- "Thirty rooms exist" (AC-14) is read from the store's rooms.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from host_harness import LEA_EMAIL, create_room_as, host_app, sign_in_as
from lifetime_harness import variables_of
from nock.catalogue import Catalogue
from nock.grid import Grid
from rooms_harness import (
    DEFAULT_LIMIT,
    GRID_NUMBER,
    HOUR,
    LIMIT_VARIABLE,
    TOO_MANY_REQUESTS,
    UNKNOWN_GRID_NUMBER,
    other_address_client,
    post_room,
    post_rooms,
    room_count,
)
from spec011_harness import BURST_SIZE, at_once
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import with_session

REFUSED_EACH = 20
LATER_SECONDS = 10.0
JUST_BEFORE_THE_HOUR = HOUR - 0.1


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


# ---- AC-13: thirty an hour from an address -----------------------------------------


@pytest.mark.parametrize("empty", [False, True], ids=["unset", "empty"])
def test_ac13_the_thirty_first_creation_of_an_address_answers_429_and_makes_no_room(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
    empty: bool,
) -> None:
    variables_of(monkeypatch, {LIMIT_VARIABLE: ""} if empty else {})

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as app:
        first_thirty = post_rooms(app.client, DEFAULT_LIMIT)
        refused = post_room(app.client)
        rooms_after_refusal = room_count(app)
        from_another_address = post_room(other_address_client(app))
        rooms_after_another = room_count(app)

    assert first_thirty == [201] * DEFAULT_LIMIT
    assert refused.status_code == 429
    assert refused.json() == TOO_MANY_REQUESTS
    assert rooms_after_refusal == DEFAULT_LIMIT
    assert from_another_address.status_code == 201
    assert rooms_after_another == DEFAULT_LIMIT + 1


def test_ac13_an_address_gets_a_room_again_when_its_first_creation_is_an_hour_old(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variables_of(monkeypatch, {})
    first_at = fake_clock.now

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as app:
        first = post_room(app.client)
        fake_clock.now = first_at + LATER_SECONDS
        others = post_rooms(app.client, DEFAULT_LIMIT - 1)
        fake_clock.now = first_at + JUST_BEFORE_THE_HOUR
        just_before = post_room(app.client)
        fake_clock.now = first_at + HOUR
        at_the_hour = post_room(app.client)
        after_it = post_room(app.client)

    assert first.status_code == 201
    assert others == [201] * (DEFAULT_LIMIT - 1)
    assert just_before.status_code == 429
    assert just_before.json() == TOO_MANY_REQUESTS
    assert at_the_hour.status_code == 201
    assert after_it.status_code == 429


def test_ac13_the_refusals_within_the_hour_do_not_delay_the_next_room(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variables_of(monkeypatch, {})
    first_at = fake_clock.now

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as app:
        thirty = post_rooms(app.client, DEFAULT_LIMIT)
        fake_clock.now = first_at + HOUR / 2
        refused = post_rooms(app.client, 5)
        fake_clock.now = first_at + HOUR
        after_the_hour = post_room(app.client)

    assert thirty == [201] * DEFAULT_LIMIT
    assert refused == [429] * 5
    assert after_the_hour.status_code == 201


def test_ac13_a_signed_in_creator_counts_with_the_anonymous_creations_of_its_address(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variables_of(monkeypatch, {})
    half = DEFAULT_LIMIT // 2

    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app:
        session = sign_in_as(app, LEA_EMAIL)
        for _ in range(half):
            create_room_as(app, None)
            create_room_as(app, session)
        anonymous = post_room(app.client)
        signed_in = app.client.post(
            "/api/rooms",
            json={"grid_number": GRID_NUMBER},
            headers=with_session(session),
        )
        rooms = room_count(app)

    assert anonymous.status_code == 429
    assert signed_in.status_code == 429
    assert rooms == 2 * half


# ---- AC-14: creations at once ------------------------------------------------------


def test_ac14_forty_creations_at_once_give_thirty_201_and_ten_429(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variables_of(monkeypatch, {})

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as app:
        results = at_once(BURST_SIZE, lambda: post_room(app.client).status_code)
        rooms = room_count(app)

    assert len(results) == BURST_SIZE
    assert results.count(201) == DEFAULT_LIMIT
    assert results.count(429) == BURST_SIZE - DEFAULT_LIMIT
    assert rooms == DEFAULT_LIMIT


# ---- AC-15: what counts, and a new app ---------------------------------------------


def test_ac15_refused_bodies_and_unknown_grids_count_nothing(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variables_of(monkeypatch, {})
    unknown_grid = {"grid_number": UNKNOWN_GRID_NUMBER}

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as app:
        invalid: list[int] = []
        unknown: list[int] = []
        for _ in range(REFUSED_EACH):
            invalid.append(post_room(app.client, {}).status_code)
            unknown.append(post_room(app.client, unknown_grid).status_code)
        thirty = post_rooms(app.client, DEFAULT_LIMIT)
        thirty_first = post_room(app.client)
        rooms = room_count(app)

    assert invalid == [422] * REFUSED_EACH
    assert unknown == [404] * REFUSED_EACH
    assert thirty == [201] * DEFAULT_LIMIT
    assert thirty_first.status_code == 429
    assert rooms == DEFAULT_LIMIT


def test_ac15_a_new_app_on_the_same_store_counts_from_zero(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variables_of(monkeypatch, {})

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as app:
        thirty = post_rooms(app.client, DEFAULT_LIMIT)
        refused = post_room(app.client)
    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as restarted:
        after_restart = post_room(restarted.client)
        rooms = room_count(restarted)

    assert thirty == [201] * DEFAULT_LIMIT
    assert refused.status_code == 429
    assert after_restart.status_code == 201
    assert rooms == DEFAULT_LIMIT + 1
