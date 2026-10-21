"""Tests of spec 033, AC-10: secrets and addresses never reach a log; tokens are
stored hashed.

HTTP with captured logs: `caplog` at level DEBUG for every logger, and a record
holds a string when `logging.Formatter().format(record)`, which adds its
traceback, holds it (the "Logs" of the spec's "Test harness"). The app has
`SETTINGS` with the user `nock` and the password `pw-SECRET-9`. Ana joins a room
(token `TA`), asks a link from it, signs in, asks `GET /api/account`, links the
room with `PUT /api/account/rooms`, signs out, asks a link that the mailer fails
to send, then signs in again and deletes her account. No record holds a link
token, a session value, `TA`, her address or the SMTP password.

The database files (`nock.sqlite3` and `nock.sqlite3-wal`) hold the address after
the sign-in, but neither the link token nor the session value: their SHA-256 hex
digests are stored instead. A link is deleted once used, so its digest is checked
while the link is pending.

Edge cases checked as well: the sign-out answers 204, clears the cookie and ends
the session; the failed mail is logged by a `nock.*` logger at `warning` or above
(the mailer row of "HTTP routes"), the level an operator sees by default.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
from pathlib import Path
from typing import NamedTuple

import pytest

from nock.grid import Grid
from spec017_harness import FakeClock, open_peer
from spec032_harness import grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    ANA_EMAIL,
    ROOMS_PATH,
    SIGN_OUT_PATH,
    SIGNED_OUT,
    RecordingMailer,
    account_app,
    account_settings,
    ask_link,
    database_bytes,
    last_token,
    room_key,
    set_cookie_of,
    sign_in,
    strings_in,
    with_session,
)

PASSWORD = "pw-SECRET-9"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


class Secrets(NamedTuple):
    """What no log record may hold, gathered during AC-10's play."""

    texts: list[str]
    failed_link_status: int
    deletion_status: int


def hex_digest(text: str) -> str:
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def holds_digest(data: bytes, text: str) -> bool:
    """Whether `data` holds the SHA-256 hex digest of `text`, in either case."""
    digest = hex_digest(text)
    return digest.encode("ascii") in data or digest.upper().encode("ascii") in data


def formatted_records(records: list[logging.LogRecord]) -> list[str]:
    """Each record as `logging.Formatter().format` writes it, traceback included."""
    formatter = logging.Formatter()
    texts: list[str] = []
    for record in records:
        texts.append(formatter.format(record))
    return texts


def play_with_logs(
    tmp_path: Path, clock: FakeClock, grid: Grid, caplog: pytest.LogCaptureFixture
) -> Secrets:
    """AC-10's play with every logger captured at DEBUG; return its secrets."""
    caplog.set_level(logging.DEBUG)
    mailer = RecordingMailer()
    settings = account_settings(user="nock", password=PASSWORD)
    with (
        account_app(tmp_path, clock, settings=settings, mailer=mailer) as app,
        contextlib.ExitStack() as stack,
    ):
        code = app.registry.register_room(grid, grid_number=1)
        ana = open_peer(stack, app.client, code, "Ana")
        ana_token = ana.snapshot().resume_token
        key = room_key(code, ana_token)

        assert ask_link(app.client, ANA_EMAIL, key).status_code == 202
        first_link = last_token(mailer)
        first = sign_in(app.client, first_link)
        assert first.status_code == 200, first.text
        first_session = set_cookie_of(first).value
        assert app.client.get(ACCOUNT_PATH).status_code == 200
        assert app.client.put(ROOMS_PATH, json=key).status_code == 204
        assert app.client.post(SIGN_OUT_PATH).status_code == 204

        mailer.failing = True
        failed_link_status = ask_link(app.client, ANA_EMAIL, key).status_code
        mailer.failing = False

        assert ask_link(app.client, ANA_EMAIL).status_code == 202
        second_link = last_token(mailer)
        second = sign_in(app.client, second_link)
        assert second.status_code == 200, second.text
        second_session = set_cookie_of(second).value
        deletion_status = app.client.delete(ACCOUNT_PATH).status_code

    texts = [
        first_link,
        second_link,
        first_session,
        second_session,
        ana_token,
        ANA_EMAIL,
        PASSWORD,
    ]
    return Secrets(texts, failed_link_status, deletion_status)


# ---- Logs -----------------------------------------------------------------------


def test_ac10_the_play_runs_its_failed_link_and_its_deletion(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secrets = play_with_logs(tmp_path, fake_clock, fx01_grid, caplog)

    assert secrets.failed_link_status == 503
    assert secrets.deletion_status == 204


def test_ac10_no_log_record_holds_a_token_a_session_the_address_or_the_password(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secrets = play_with_logs(tmp_path, fake_clock, fx01_grid, caplog)

    leaks: list[tuple[str, str]] = []
    for text in formatted_records(caplog.records):
        for secret in secrets.texts:
            if secret in text:
                leaks.append((secret, text))
    assert leaks == []


def is_app_logger(name: str) -> bool:
    """Whether a logger is `nock` or one of the `nock.*` loggers."""
    return name == "nock" or name.startswith("nock.")


def test_ac10_the_failed_mail_is_logged_by_the_app_at_warning_or_above(
    tmp_path: Path, fake_clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    mailer = RecordingMailer()
    mailer.failing = True
    with account_app(tmp_path, fake_clock, mailer=mailer) as app:
        caplog.clear()
        response = ask_link(app.client, ANA_EMAIL)
        records = list(caplog.records)

    # Specs 036 and 038: the operator's log level is `warning` by default.
    seen_by_the_operator = []
    for record in records:
        if is_app_logger(record.name) and record.levelno >= logging.WARNING:
            seen_by_the_operator.append(record)
    assert response.status_code == 503
    every_record = [(r.name, r.levelname) for r in records]
    assert len(seen_by_the_operator) >= 1, every_record


# ---- Stored tokens --------------------------------------------------------------


def test_ac10_after_the_sign_in_the_files_hold_the_address(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        assert ask_link(app.client, ANA_EMAIL).status_code == 202
        assert sign_in(app.client, last_token(app.mailer)).status_code == 200
        data = database_bytes(app.database_path)

    assert strings_in(data, [ANA_EMAIL]) == [ANA_EMAIL]


def test_ac10_after_the_sign_in_the_files_hold_neither_the_link_nor_the_session(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        assert ask_link(app.client, ANA_EMAIL).status_code == 202
        link = last_token(app.mailer)
        response = sign_in(app.client, link)
        session = set_cookie_of(response).value
        data = database_bytes(app.database_path)

    assert strings_in(data, [link, session]) == []


def test_ac10_the_session_is_stored_as_its_sha256_hex_digest(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        assert ask_link(app.client, ANA_EMAIL).status_code == 202
        response = sign_in(app.client, last_token(app.mailer))
        session = set_cookie_of(response).value
        data = database_bytes(app.database_path)

    assert holds_digest(data, session)


def test_ac10_a_pending_link_is_stored_as_its_sha256_hex_digest_only(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        assert ask_link(app.client, ANA_EMAIL).status_code == 202
        link = last_token(app.mailer)
        data = database_bytes(app.database_path)

    assert strings_in(data, [link]) == []
    assert holds_digest(data, link)


# ---- Edge case: the sign-out ------------------------------------------------------


def test_ac10_the_sign_out_answers_204_and_clears_the_cookie(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        assert ask_link(app.client, ANA_EMAIL).status_code == 202
        assert sign_in(app.client, last_token(app.mailer)).status_code == 200

        response = app.client.post(SIGN_OUT_PATH)

    assert response.status_code == 204
    cookie = set_cookie_of(response)
    assert cookie.value == ""
    assert cookie.attributes.get("max-age") == "0", cookie
    assert cookie.attributes.get("path") == "/", cookie


def test_ac10_the_sign_out_ends_the_session(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        assert ask_link(app.client, ANA_EMAIL).status_code == 202
        signed_in = sign_in(app.client, last_token(app.mailer))
        session = set_cookie_of(signed_in).value
        app.client.post(SIGN_OUT_PATH)
        app.client.cookies.clear()

        response = app.client.get(ACCOUNT_PATH, headers=with_session(session))

    assert response.json() == SIGNED_OUT


def test_ac10_the_sign_out_without_a_session_answers_204(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        response = app.client.post(SIGN_OUT_PATH)

    assert response.status_code == 204
