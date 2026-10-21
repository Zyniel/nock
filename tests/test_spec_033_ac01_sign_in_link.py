"""Tests of spec 033, AC-1: a guest asks a sign-in link from a room and uses it.

Over HTTP, with the app of the "Test harness" on a fake clock: `Ana` (host, colour
0) and `Bob` join a FX-01 room through the TestClient's sockets, and Ana writes `T`
at (1, 0). The link she asks from the room is sent by the recording mailer; the
sign-in creates her account and links her identity, and changes nothing in the
room. A used link and an expired link answer 404; the cookie is `Secure` only
behind an `https://` public URL.

Edge cases checked as well: the trimmed, lower-cased address makes one account of
two spellings; an existing account signs in again and gains the room's identity; a
player removed before the link is used gets an account and no identity; a second
sign-in leaves the first session working; a session older than 90 days signs
nobody in; every answer under `/api/account` carries `Cache-Control: no-store`.

The shared setup is in `spec033_harness`, `spec017_harness` (the socket peers)
and `spec032_harness` (the configuration on which no tick changes anything).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from nock.grid import Grid
from nock.protocol import EditLetter, LetterChanged, Ping, Pong, RemovePlayer
from spec017_harness import FakeClock, Peer, open_peer
from spec032_harness import grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    ANA_EMAIL,
    LINK_LIFE,
    LINK_MARK,
    NOT_FOUND,
    PUBLIC_URL,
    SENDER,
    SESSION_COOKIE,
    SESSION_LIFE,
    SESSION_MAX_AGE,
    SIGNED_OUT,
    TOKEN_PATTERN,
    AccountApp,
    account_app,
    account_settings,
    ask_link,
    body_of,
    cell_state,
    fill,
    last_token,
    link_and_sign_in,
    load_fr,
    room_key,
    set_cookie_of,
    sign_in,
    state_of,
    token_of,
    wait_for,
    with_session,
)

TYPED_ADDRESS = "  Ana.Probe@Example.org "
OTHER_SPELLING = "ANA.PROBE@example.ORG"
NO_STORE = "no-store"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


class AnasRoom(NamedTuple):
    """AC-1's room: Ana (host, colour 0) and Bob joined, Ana wrote `T` at (1, 0)."""

    app: AccountApp
    code: str
    ana: Peer
    bob: Peer
    ana_id: str
    ana_token: str


@contextlib.contextmanager
def anas_room(
    tmp_path: Path, clock: FakeClock, grid: Grid, public_url: str = PUBLIC_URL
) -> Iterator[AnasRoom]:
    """Run AC-1's app and room, up to Ana's `T`, and yield them."""
    settings = account_settings(public_url)
    with (
        account_app(tmp_path, clock, settings=settings) as app,
        contextlib.ExitStack() as stack,
    ):
        code = app.registry.register_room(grid, grid_number=1)
        ana = open_peer(stack, app.client, code, "Ana")
        bob = open_peer(stack, app.client, code, "Bob")
        ana_snapshot = ana.snapshot()
        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.wait_until(lambda: has_letter_changed(ana), "Ana's T on Ana")
        bob.wait_until(lambda: has_letter_changed(bob), "Ana's T on Bob")
        yield AnasRoom(
            app=app,
            code=code,
            ana=ana,
            bob=bob,
            ana_id=ana_snapshot.you,
            ana_token=ana_snapshot.resume_token,
        )


def has_letter_changed(peer: Peer) -> bool:
    return any(isinstance(message, LetterChanged) for message in peer.events())


def pong_count(peer: Peer) -> int:
    return len([message for message in peer.messages() if isinstance(message, Pong)])


def messages_after_a_ping(peer: Peer) -> list[object]:
    """Every message the peer received, once a ping sent now got its pong.

    The pong comes after anything the server queued for the socket before it, so
    the list holds everything sent so far, without the pongs.
    """
    pongs_before = pong_count(peer)
    peer.send(Ping())
    peer.wait_until(lambda: pong_count(peer) > pongs_before, "the pong")
    kept: list[object] = []
    for message in peer.messages():
        if not isinstance(message, Pong):
            kept.append(message)
    return kept


def ask_from_the_room(room: AnasRoom, address: str = TYPED_ADDRESS) -> None:
    """Ana asks a link from her room; the request must be sent."""
    response = ask_link(room.app.client, address, room_key(room.code, room.ana_token))
    assert response.status_code == 202, response.text


# ---- The link -------------------------------------------------------------------


def test_ac1_the_link_request_answers_202_with_an_empty_object(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        key = room_key(room.code, room.ana_token)

        response = ask_link(room.app.client, TYPED_ADDRESS, key)

    assert response.status_code == 202
    assert response.json() == {}


def test_ac1_one_message_goes_to_the_normalised_address_from_the_sender(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        messages = list(room.app.mailer.messages)

    assert len(messages) == 1
    assert messages[0]["To"] == ANA_EMAIL
    assert messages[0]["From"] == SENDER


def test_ac1_the_subject_is_the_french_subject(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    fr = load_fr()
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        message = room.app.mailer.messages[0]

    assert fr["email.sign_in.subject"] == "Votre lien de connexion à Nock"
    assert message["Subject"] == fr["email.sign_in.subject"]


def test_ac1_the_body_is_the_french_body_with_the_link(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    fr = load_fr()
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        message = room.app.mailer.messages[0]
    token = token_of(message)
    link = f"{PUBLIC_URL}{LINK_MARK}{token}"

    assert fr["email.sign_in.body"] == (
        "Bonjour,\n\nOuvrez ce lien pour vous connecter à Nock :\n{link}\n\n"
        "Il est valable 30 minutes et ne sert qu'une fois. Si vous n'avez rien"
        " demandé, ignorez ce message."
    )
    assert message.get_content_type() == "text/plain"
    assert body_of(message) == fill(fr["email.sign_in.body"], {"link": link})


def test_ac1_the_token_is_43_characters_of_the_url_safe_alphabet(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        body = body_of(room.app.mailer.messages[0])

    link_start = body.index(f"{PUBLIC_URL}{LINK_MARK}")
    after_link = body[link_start + len(PUBLIC_URL) + len(LINK_MARK) :]
    token = after_link.split("\n")[0]
    assert TOKEN_PATTERN.fullmatch(token) is not None, token


# ---- The sign-in ----------------------------------------------------------------


def test_ac1_the_sign_in_answers_the_account_the_room_and_its_identity(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)

        response = sign_in(room.app.client, last_token(room.app.mailer))

        identity = {
            "code": room.code,
            "player_id": room.ana_id,
            "resume_token": room.ana_token,
            "nickname": "ANA",
        }
    assert response.status_code == 200
    assert response.json() == {
        "email": ANA_EMAIL,
        "room_code": room.code,
        "rooms": [identity],
    }


def test_ac1_the_session_cookie_is_http_only_lax_for_90_days_and_not_secure(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)

        response = sign_in(room.app.client, last_token(room.app.mailer))

    cookie = set_cookie_of(response)
    assert TOKEN_PATTERN.fullmatch(cookie.value) is not None, cookie
    assert "httponly" in cookie.attributes, cookie
    assert cookie.attributes.get("max-age") == SESSION_MAX_AGE, cookie
    assert cookie.attributes.get("path") == "/", cookie
    assert cookie.attributes.get("samesite", "").lower() == "lax", cookie
    assert "secure" not in cookie.attributes, cookie


def test_ac1_behind_an_https_public_url_the_cookie_is_also_secure(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid, "https://nock.example") as room:
        ask_from_the_room(room)

        response = sign_in(room.app.client, last_token(room.app.mailer))

    assert response.status_code == 200
    cookie = set_cookie_of(response)
    assert "secure" in cookie.attributes, cookie
    assert "httponly" in cookie.attributes, cookie
    assert cookie.attributes.get("samesite", "").lower() == "lax", cookie


def test_ac1_after_the_sign_in_the_account_route_says_signed_in(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        sign_in(room.app.client, last_token(room.app.mailer))

        response = room.app.client.get(ACCOUNT_PATH)

    assert response.status_code == 200
    assert response.json() == {"signed_in": True, "email": ANA_EMAIL}


def test_ac1_without_a_session_the_account_route_says_signed_out(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        response = room.app.client.get(ACCOUNT_PATH)

    assert response.status_code == 200
    assert response.json() == SIGNED_OUT


# ---- The room is untouched ------------------------------------------------------


def test_ac1_the_room_state_and_log_are_the_same_as_before_the_link(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        before = state_of(room.app.registry, room.code)
        log_before = room.app.store.read_log(room.code)

        ask_from_the_room(room)
        sign_in(room.app.client, last_token(room.app.mailer))

        after = state_of(room.app.registry, room.code)
        log_after = room.app.store.read_log(room.code)

    assert after.players == before.players
    assert after.seq == before.seq
    assert after.cells == before.cells
    assert log_after == log_before


def test_ac1_ana_keeps_her_id_nickname_colour_host_role_and_letter(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        sign_in(room.app.client, last_token(room.app.mailer))
        state = state_of(room.app.registry, room.code)

    anas_records = [p for p in state.players if p.player_id == room.ana_id]
    assert len(anas_records) == 1
    ana = anas_records[0]
    assert ana.nickname == "ANA"
    assert ana.colour == 0
    assert ana.is_host is True
    assert ana.joined_seq == 1
    cell = cell_state(state, 1, 0)
    assert cell.letter == "T"
    assert cell.author == room.ana_id


def test_ac1_nothing_is_sent_on_the_sockets(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        anas_before = messages_after_a_ping(room.ana)
        bobs_before = messages_after_a_ping(room.bob)

        ask_from_the_room(room)
        sign_in(room.app.client, last_token(room.app.mailer))

        anas_after = messages_after_a_ping(room.ana)
        bobs_after = messages_after_a_ping(room.bob)

    assert anas_after == anas_before
    assert bobs_after == bobs_before


# ---- Used and expired links -----------------------------------------------------


def test_ac1_using_the_token_again_answers_404(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        token = last_token(room.app.mailer)
        first = sign_in(room.app.client, token)

        second = sign_in(room.app.client, token)

    assert first.status_code == 200
    assert second.status_code == 404
    assert second.json() == NOT_FOUND


def test_ac1_a_link_used_1801_seconds_after_it_was_asked_answers_404(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        token = last_token(room.app.mailer)
        fake_clock.advance(LINK_LIFE + 1)

        response = sign_in(room.app.client, token)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_ac1_a_link_used_1799_seconds_after_it_was_asked_answers_200(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        token = last_token(room.app.mailer)
        fake_clock.advance(LINK_LIFE - 1)

        response = sign_in(room.app.client, token)

    assert response.status_code == 200
    assert response.json()["email"] == ANA_EMAIL


def test_ac1_an_expired_link_signs_nobody_in(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)
        token = last_token(room.app.mailer)
        fake_clock.advance(LINK_LIFE + 1)
        sign_in(room.app.client, token)

        response = room.app.client.get(ACCOUNT_PATH)

    assert response.json() == SIGNED_OUT


def test_ac1_an_unknown_token_answers_404(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        response = sign_in(room.app.client, "A" * 43)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# ---- Edge cases: the address, an existing account, a player gone ----------------


def test_ac1_two_spellings_of_one_address_are_one_account(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        key = room_key(room.code, room.ana_token)
        link_and_sign_in(room.app, TYPED_ADDRESS, key)
        room.app.client.cookies.clear()

        second = link_and_sign_in(room.app, OTHER_SPELLING)

    assert second.json()["email"] == ANA_EMAIL
    assert second.json()["room_code"] is None
    assert [identity["code"] for identity in second.json()["rooms"]] == [room.code]


def test_ac1_a_link_for_an_existing_account_links_the_new_room_to_it(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        link_and_sign_in(room.app, ANA_EMAIL, room_key(room.code, room.ana_token))
        other_code = room.app.registry.register_room(fx01_grid, grid_number=1)
        with contextlib.ExitStack() as stack:
            ana_there = open_peer(stack, room.app.client, other_code, "Ana")
            token_there = ana_there.snapshot().resume_token
            id_there = ana_there.snapshot().you
            key_there = room_key(other_code, token_there)

            second = link_and_sign_in(room.app, ANA_EMAIL, key_there)

    assert second.json()["room_code"] == other_code
    assert second.json()["rooms"] == [
        {
            "code": other_code,
            "player_id": id_there,
            "resume_token": token_there,
            "nickname": "ANA",
        },
        {
            "code": room.code,
            "player_id": room.ana_id,
            "resume_token": room.ana_token,
            "nickname": "ANA",
        },
    ]


def test_ac1_a_player_gone_before_the_link_is_used_gets_no_identity(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app, contextlib.ExitStack() as stack:
        code = app.registry.register_room(fx01_grid, grid_number=1)
        bob = open_peer(stack, app.client, code, "Bob")
        ana = open_peer(stack, app.client, code, "Ana")
        ana_snapshot = ana.snapshot()
        response = ask_link(
            app.client, ANA_EMAIL, room_key(code, ana_snapshot.resume_token)
        )
        assert response.status_code == 202
        bob.send_raw(RemovePlayer(player_id=ana_snapshot.you).model_dump_json())
        wait_for(
            lambda: app.registry.member_id(code, ana_snapshot.resume_token) is None,
            "Ana's removal",
        )

        signed_in = sign_in(app.client, last_token(app.mailer))
        status = app.client.get(ACCOUNT_PATH)

    assert signed_in.status_code == 200
    assert signed_in.json() == {"email": ANA_EMAIL, "room_code": None, "rooms": []}
    assert status.json() == {"signed_in": True, "email": ANA_EMAIL}


# ---- Edge cases: sessions -------------------------------------------------------


def test_ac1_a_second_sign_in_leaves_the_first_session_working(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        first = link_and_sign_in(room.app, ANA_EMAIL)
        first_session = set_cookie_of(first).value
        second = link_and_sign_in(room.app, ANA_EMAIL)
        second_session = set_cookie_of(second).value
        room.app.client.cookies.clear()

        with_first = room.app.client.get(
            ACCOUNT_PATH, headers=with_session(first_session)
        )

    assert second_session != first_session
    assert with_first.json() == {"signed_in": True, "email": ANA_EMAIL}


def test_ac1_a_session_older_than_90_days_signs_nobody_in(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        link_and_sign_in(room.app, ANA_EMAIL)
        fake_clock.advance(SESSION_LIFE + 1)

        response = room.app.client.get(ACCOUNT_PATH)

    assert response.json() == SIGNED_OUT


def test_ac1_a_session_a_second_short_of_90_days_still_signs_in(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        link_and_sign_in(room.app, ANA_EMAIL)
        fake_clock.advance(SESSION_LIFE - 1)

        response = room.app.client.get(ACCOUNT_PATH)

    assert response.json() == {"signed_in": True, "email": ANA_EMAIL}


def test_ac1_the_session_cookie_is_the_only_cookie_of_the_sign_in(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        ask_from_the_room(room)

        response = sign_in(room.app.client, last_token(room.app.mailer))

    names = []
    for header in response.headers.get_list("set-cookie"):
        names.append(header.split("=")[0].strip())
    assert names == [SESSION_COOKIE]


# ---- Edge case: no answer under /api/account is kept by a cache -----------------


def test_ac1_every_answer_of_the_account_routes_is_no_store(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with anas_room(tmp_path, fake_clock, fx01_grid) as room:
        signed_out = room.app.client.get(ACCOUNT_PATH)
        asked = ask_link(
            room.app.client, TYPED_ADDRESS, room_key(room.code, room.ana_token)
        )
        refused = ask_link(room.app.client, "ana")
        unknown = sign_in(room.app.client, "B" * 43)
        signed_in = sign_in(room.app.client, last_token(room.app.mailer))
        status = room.app.client.get(ACCOUNT_PATH)

    answers = [signed_out, asked, refused, unknown, signed_in, status]
    controls = [answer.headers.get("cache-control") for answer in answers]
    assert controls == [NO_STORE] * len(answers)
