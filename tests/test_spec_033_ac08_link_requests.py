"""Tests of spec 033, AC-8: link requests reveal nothing and cannot flood a mailbox.

HTTP, with the app of the "Test harness" on a fake clock. Every request comes from
the TestClient, so from one client address. An address that has an account and one
that has none get the same 202 `{}`; a refused address gets 422 with exactly
`{"detail": "Invalid e-mail address"}`, and a room key whose token is no member's
gets 404; neither sends anything nor counts toward the limits. Three links per
address and ten per client address are sent in an hour of the fake clock; the next
one answers 429 and sends nothing; a request is counted while its time `t`
satisfies `t > now - 3600`, so one hour later a link is sent again. With accounts
off, every account route and page answers 404.

Edge cases checked as well: a request refused 429 counts toward neither limit; a
failed mail (503) counts; the limits start again at zero in a new app; with
accounts on, `GET /account` serves the client, or 503 while it is not built.

The addresses are Python string literals, or expressions that join or repeat them,
as in the spec's "Test harness".
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.server import create_app
from nock.store import RoomStore
from spec017_harness import FakeClock, open_peer
from spec032_harness import grid_from_text, make_dist_dir
from spec033_harness import (
    ACCOUNT_PAGE_PATH,
    ACCOUNT_PATH,
    ANA_EMAIL,
    HOUR,
    INVALID_ADDRESS,
    LINK_PATH,
    LINKS_PER_ADDRESS,
    LINKS_PER_EMAIL,
    NOBODYS_TOKEN,
    NOT_FOUND,
    ROOMS_PATH,
    SIGN_IN_PATH,
    SIGN_OUT_PATH,
    TOO_MANY_REQUESTS,
    AccountApp,
    RecordingMailer,
    account_app,
    ask_link,
    link_and_sign_in,
    room_key,
)

UNKNOWN_CODE = "ZZZZZZ"
BOB_EMAIL = "bob.probe@example.org"
ADDRESS_OF_255 = "ana@" + "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 59
REFUSED_ADDRESSES = [
    pytest.param("", id="empty"),
    pytest.param("ana", id="no-at"),
    pytest.param("ana@", id="no-domain"),
    pytest.param("@example.org", id="no-local-part"),
    pytest.param("ana@example", id="one-label"),
    pytest.param("ana @example.org", id="space"),
    pytest.param(
        "fran\N{LATIN SMALL LETTER C WITH CEDILLA}ois@example.org", id="cedilla"
    ),
    pytest.param("x1,victim@example.org", id="comma"),
    pytest.param("a<b@example.org", id="less-than"),
    pytest.param('a"b@example.org', id="quote"),
    pytest.param(ADDRESS_OF_255, id="255-characters"),
]
# Decision 15: local parts that a mailer could split into another address.
SPLITTABLE_ADDRESSES = [
    "x1,victim@example.org",
    "x2,victim@example.org",
    "a<b@example.org",
    'a"b@example.org',
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def addresses(count: int) -> list[str]:
    """`count` different addresses."""
    return [f"player{number}@example.org" for number in range(count)]


def sent_count(app: AccountApp) -> int:
    return len(app.mailer.messages)


# ---- The same answer whether an account exists ----------------------------------


def test_ac8_the_answer_is_the_same_with_or_without_an_account(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        link_and_sign_in(app, ANA_EMAIL)
        app.client.cookies.clear()

        with_account = ask_link(app.client, ANA_EMAIL)
        without_account = ask_link(app.client, BOB_EMAIL)

    assert with_account.status_code == 202
    assert without_account.status_code == 202
    assert with_account.json() == {}
    assert without_account.json() == {}
    assert with_account.content == without_account.content


def test_ac8_the_address_of_255_characters_breaks_the_length_rule_only() -> None:
    local_part, domain = ADDRESS_OF_255.split("@")
    labels = domain.split(".")

    assert len(ADDRESS_OF_255) == 255
    assert local_part == "ana"
    assert [len(label) for label in labels] == [63, 63, 63, 59]


# ---- Refused addresses and rooms ------------------------------------------------


@pytest.mark.parametrize("address", REFUSED_ADDRESSES)
def test_ac8_a_refused_address_answers_422_with_exactly_the_generic_detail(
    tmp_path: Path, fake_clock: FakeClock, address: str
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        response = ask_link(app.client, address)
        sent = sent_count(app)

    assert response.status_code == 422
    assert response.json() == INVALID_ADDRESS
    assert sent == 0


def test_ac8_a_room_key_whose_token_is_no_members_answers_404(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app, contextlib.ExitStack() as stack:
        code = app.registry.register_room(fx01_grid, grid_number=1)
        open_peer(stack, app.client, code, "Ana")

        response = ask_link(app.client, ANA_EMAIL, room_key(code, NOBODYS_TOKEN))
        sent = sent_count(app)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert sent == 0


def test_ac8_a_room_key_with_an_unknown_code_answers_404(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        response = ask_link(
            app.client, ANA_EMAIL, room_key(UNKNOWN_CODE, NOBODYS_TOKEN)
        )
        sent = sent_count(app)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert sent == 0


def test_ac8_refused_requests_count_toward_neither_limit(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        code = app.registry.register_room(fx01_grid, grid_number=1)
        refusals = []
        for _ in range(LINKS_PER_ADDRESS + 1):
            refusals.append(ask_link(app.client, "ana").status_code)
            wrong_key = room_key(code, NOBODYS_TOKEN)
            refusals.append(ask_link(app.client, ANA_EMAIL, wrong_key).status_code)

        for_ana = []
        for _ in range(LINKS_PER_EMAIL):
            for_ana.append(ask_link(app.client, ANA_EMAIL).status_code)
        for_others = []
        for address in addresses(LINKS_PER_ADDRESS - LINKS_PER_EMAIL):
            for_others.append(ask_link(app.client, address).status_code)
        sent = sent_count(app)

    assert sorted(set(refusals)) == [404, 422]
    assert for_ana == [202] * LINKS_PER_EMAIL
    assert for_others == [202] * (LINKS_PER_ADDRESS - LINKS_PER_EMAIL)
    assert sent == LINKS_PER_ADDRESS


def test_ac8_local_parts_a_mailer_could_split_count_toward_neither_limit(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        refusals = []
        for _ in range(LINKS_PER_ADDRESS + 1):
            for address in SPLITTABLE_ADDRESSES:
                refusals.append(ask_link(app.client, address).status_code)

        for_ana = []
        for _ in range(LINKS_PER_EMAIL):
            for_ana.append(ask_link(app.client, ANA_EMAIL).status_code)
        for_others = []
        for address in addresses(LINKS_PER_ADDRESS - LINKS_PER_EMAIL):
            for_others.append(ask_link(app.client, address).status_code)
        sent = sent_count(app)

    assert refusals == [422] * ((LINKS_PER_ADDRESS + 1) * len(SPLITTABLE_ADDRESSES))
    assert for_ana == [202] * LINKS_PER_EMAIL
    assert for_others == [202] * (LINKS_PER_ADDRESS - LINKS_PER_EMAIL)
    assert sent == LINKS_PER_ADDRESS


# ---- The limit per address ------------------------------------------------------


def test_ac8_three_links_for_one_address_are_sent_and_the_fourth_answers_429(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        answers = []
        for _ in range(LINKS_PER_EMAIL):
            answers.append(ask_link(app.client, ANA_EMAIL).status_code)
            fake_clock.advance(60)
        fourth = ask_link(app.client, ANA_EMAIL)
        sent = sent_count(app)

    assert answers == [202] * LINKS_PER_EMAIL
    assert fourth.status_code == 429
    assert fourth.json() == TOO_MANY_REQUESTS
    assert sent == LINKS_PER_EMAIL


def test_ac8_the_limit_counts_the_normalised_address(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    spellings = [ANA_EMAIL, "Ana.Probe@Example.org", "  ANA.PROBE@EXAMPLE.ORG "]
    with account_app(tmp_path, fake_clock) as app:
        answers = []
        for spelling in spellings:
            answers.append(ask_link(app.client, spelling).status_code)
        fourth = ask_link(app.client, ANA_EMAIL)

    assert answers == [202] * LINKS_PER_EMAIL
    assert fourth.status_code == 429


def test_ac8_an_hour_later_one_is_sent_again(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        for _ in range(LINKS_PER_EMAIL):
            assert ask_link(app.client, ANA_EMAIL).status_code == 202
        assert ask_link(app.client, ANA_EMAIL).status_code == 429
        fake_clock.advance(HOUR)

        again = ask_link(app.client, ANA_EMAIL)
        sent = sent_count(app)

    assert again.status_code == 202
    assert sent == LINKS_PER_EMAIL + 1


def test_ac8_a_second_short_of_an_hour_the_address_is_still_refused(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        for _ in range(LINKS_PER_EMAIL):
            assert ask_link(app.client, ANA_EMAIL).status_code == 202
        fake_clock.advance(HOUR - 1)

        response = ask_link(app.client, ANA_EMAIL)

    assert response.status_code == 429


def test_ac8_requests_refused_429_are_not_counted(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        for _ in range(LINKS_PER_EMAIL):
            assert ask_link(app.client, ANA_EMAIL).status_code == 202
        fake_clock.advance(HOUR / 2)
        for _ in range(5):
            assert ask_link(app.client, ANA_EMAIL).status_code == 429
        fake_clock.advance(HOUR / 2)

        response = ask_link(app.client, ANA_EMAIL)

    assert response.status_code == 202


def test_ac8_a_failed_mail_counts_toward_the_limits(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    mailer = RecordingMailer()
    mailer.failing = True
    with account_app(tmp_path, fake_clock, mailer=mailer) as app:
        answers = []
        for _ in range(LINKS_PER_EMAIL):
            answers.append(ask_link(app.client, ANA_EMAIL).status_code)
        mailer.failing = False

        fourth = ask_link(app.client, ANA_EMAIL)

    assert answers == [503] * LINKS_PER_EMAIL
    assert fourth.status_code == 429
    assert mailer.messages == []


# ---- The limit per client address -----------------------------------------------


def test_ac8_ten_links_from_one_client_address_are_sent_and_the_eleventh_429(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        answers = []
        for address in addresses(LINKS_PER_ADDRESS):
            answers.append(ask_link(app.client, address).status_code)
        eleventh = ask_link(app.client, BOB_EMAIL)
        sent = sent_count(app)

    assert answers == [202] * LINKS_PER_ADDRESS
    assert eleventh.status_code == 429
    assert eleventh.json() == TOO_MANY_REQUESTS
    assert sent == LINKS_PER_ADDRESS


def test_ac8_an_hour_later_the_client_address_is_sent_again(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        for address in addresses(LINKS_PER_ADDRESS):
            assert ask_link(app.client, address).status_code == 202
        fake_clock.advance(HOUR)

        response = ask_link(app.client, BOB_EMAIL)

    assert response.status_code == 202


def test_ac8_the_limits_start_again_at_zero_in_a_new_app(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as first:
        for _ in range(LINKS_PER_EMAIL):
            assert ask_link(first.client, ANA_EMAIL).status_code == 202
        assert ask_link(first.client, ANA_EMAIL).status_code == 429

    with account_app(tmp_path, fake_clock) as second:
        response = ask_link(second.client, ANA_EMAIL)

    assert response.status_code == 202


# ---- GET /account with accounts on ----------------------------------------------


def test_ac8_with_accounts_on_get_account_serves_the_client(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    dist = make_dist_dir(tmp_path)
    index = (dist / "index.html").read_text(encoding="utf-8")
    with account_app(tmp_path, fake_clock, dist_dir=dist) as app:
        response = app.client.get(ACCOUNT_PAGE_PATH)

    assert response.status_code == 200
    assert response.text == index


def test_ac8_with_accounts_on_and_no_built_client_get_account_answers_503(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        response = app.client.get(ACCOUNT_PAGE_PATH)

    assert response.status_code == 503


# ---- Accounts off -----------------------------------------------------------------


@contextlib.contextmanager
def accounts_off_client(
    tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """The app of "Accounts off" in the "Test harness", with a built client."""
    monkeypatch.delenv("NOCK_PUBLIC_URL", raising=False)
    monkeypatch.delenv("NOCK_SMTP_HOST", raising=False)
    store = RoomStore(tmp_path / "nock.sqlite3")
    registry = RoomRegistry(clock=clock, store=store)
    try:
        app = create_app(rooms=registry, dist_dir=make_dist_dir(tmp_path))
        with TestClient(app) as client:
            yield client
    finally:
        registry.close()
        store.close()


OFF_REQUESTS = [
    pytest.param("GET", ACCOUNT_PAGE_PATH, None, id="get-account-page"),
    pytest.param("GET", ACCOUNT_PATH, None, id="get-account"),
    pytest.param("POST", LINK_PATH, {"email": ANA_EMAIL, "room": None}, id="post-link"),
    pytest.param("DELETE", ACCOUNT_PATH, None, id="delete-account"),
    pytest.param("POST", SIGN_IN_PATH, {"token": "A" * 43}, id="post-sign-in"),
    pytest.param("POST", SIGN_OUT_PATH, None, id="post-sign-out"),
    pytest.param("GET", ROOMS_PATH, None, id="get-rooms"),
    pytest.param(
        "PUT", ROOMS_PATH, room_key(UNKNOWN_CODE, NOBODYS_TOKEN), id="put-rooms"
    ),
]


@pytest.mark.parametrize(("method", "path", "body"), OFF_REQUESTS)
def test_ac8_with_accounts_off_every_account_route_answers_404(
    tmp_path: Path,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    body: object,
) -> None:
    with accounts_off_client(tmp_path, fake_clock, monkeypatch) as client:
        response = client.request(method, path, json=body)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
