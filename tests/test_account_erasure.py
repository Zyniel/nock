"""Tests of account/account, AC-24 and AC-26, and the sweep of AC-25: an erasure that
always finishes.

HTTP, on the app of spec 033's "Test harness" (accounts on, both stores on one file,
a fake clock, a recording mailer). Zoé plays R, which is live (a socket stays open),
and S, a room only in the store, signs in from R, and created U (`zoe_in_rooms` of
`account_harness`). She then sends `DELETE /api/account`.

- AC-24: the answer, the cookie, R's and S's players named `--`, U gone, the one
  e-mail (sender, recipient, subject, exact body, no link), the row of
  `account_erasures` (read on a connection of its own, the table of the spec's "New
  interface"), `account_erasure_players` empty, and the database files without her
  address or `ZOÉ`. `deleted_message` of `nock.mailer` builds the message.
- AC-26: the same deletion with the mailer raising `MailError`: 204, one record at
  WARNING or above without the address, the erasure done with no e-mail time, no
  address in the files, and no later sweep (an app restarted on the file, which
  sweeps every 0.1 s) sends anything.
- AC-25, the sweep: an erasure written by `AccountStore.delete_account` alone,
  with no attempt of the route, is finished by the next sweep of the same app,
  which sends the e-mail once. The held engine of AC-25 is in
  `test_account_erasure_retry.py`.

The count of log records is that of the `nock.*` loggers at WARNING or above, since
rule 26 says "WARNING or above".
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Iterator
from email.message import EmailMessage
from pathlib import Path
from typing import NamedTuple

import pytest
from httpx2 import Response

from account_harness import (
    DELETED_BODY,
    DELETED_SUBJECT,
    FAST_SWEEP_CONFIG,
    TZ,
    U_CODE,
    ZOE,
    ZOE_EMAIL,
    ZOE_NICKNAME,
    ZOE_STORED,
    ErasureRow,
    ZoeRooms,
    erasure_rows,
    listed_players,
    nicknames_of,
    zoe_in_rooms,
)
from nock.grid import Grid
from operations_harness import LOGGER_PREFIX
from spec017_harness import FakeClock
from spec029_harness import Player, account_id_of, link_room, play_fx01, sign_in_from
from spec032_harness import grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    FORMER_NICKNAME,
    SENDER,
    SIGNED_OUT,
    account_app,
    account_settings,
    body_of,
    database_bytes,
    load_fr,
    set_cookie_of,
    state_of,
    strings_in,
    wait_for,
    with_session,
)

SECRETS = [ZOE_EMAIL, ZOE_STORED]
LATER_SWEEPS_SECONDS = 1.0  # ten sweeps of FAST_SWEEP_CONFIG


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


class Outcome(NamedTuple):
    """What Zoé's deletion left, read before the app stopped."""

    rooms: ZoeRooms
    deletion: Response
    status_after: Response
    requested_at: float
    sent: list[EmailMessage]
    records: list[logging.LogRecord]
    nicknames_in_r: list[str]
    nicknames_in_s: list[str]
    u_exists: bool
    rows: list[ErasureRow]
    listed: list[tuple[str, str]]
    secrets_in_files: list[str]


def nock_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """The records of the `nock.*` loggers at WARNING or above."""
    found: list[logging.LogRecord] = []
    for record in caplog.records:
        if record.name.startswith(LOGGER_PREFIX) and record.levelno >= logging.WARNING:
            found.append(record)
    return found


@contextlib.contextmanager
def zoe_deletes(
    tmp_path: Path,
    clock: FakeClock,
    grid: Grid,
    caplog: pytest.LogCaptureFixture,
    *,
    mail_fails: bool = False,
) -> Iterator[Outcome]:
    """Zoé's play, her deletion, and what it left; the app is still running."""
    caplog.set_level(logging.DEBUG, logger=LOGGER_PREFIX)
    with account_app(tmp_path, clock) as app, contextlib.ExitStack() as stack:
        rooms = zoe_in_rooms(app, stack, grid, s_live=False)
        sent_before = len(app.mailer.messages)
        app.mailer.failing = mail_fails
        caplog.clear()
        deletion = app.client.delete(ACCOUNT_PATH, headers=with_session(rooms.session))
        records = nock_records(caplog)
        app.mailer.failing = False
        status_after = app.client.get(ACCOUNT_PATH, headers=with_session(rooms.session))
        r_state = state_of(app.registry, rooms.r_code)
        s_state = state_of(app.registry, rooms.s_code)
        yield Outcome(
            rooms=rooms,
            deletion=deletion,
            status_after=status_after,
            requested_at=app.clock(),
            sent=list(app.mailer.messages[sent_before:]),
            records=records,
            nicknames_in_r=nicknames_of(r_state, rooms.zoe_in_r),
            nicknames_in_s=nicknames_of(s_state, rooms.zoe_in_s),
            u_exists=app.store.has_room(U_CODE),
            rows=erasure_rows(app.database_path),
            listed=listed_players(app.database_path),
            secrets_in_files=strings_in(database_bytes(app.database_path), SECRETS),
        )


# ---- AC-24: the deletion that finishes at once -----------------------------------


def test_ac24_the_deletion_answers_204_and_her_rooms_are_erased(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with zoe_deletes(tmp_path, fake_clock, fx01_grid, caplog) as erased:
        pass

    cookie = set_cookie_of(erased.deletion)
    assert erased.deletion.status_code == 204
    assert (cookie.value, cookie.attributes.get("max-age")) == ("", "0")
    assert erased.status_after.json() == SIGNED_OUT
    assert erased.nicknames_in_r == [FORMER_NICKNAME]
    assert erased.nicknames_in_s == [FORMER_NICKNAME]
    assert erased.u_exists is False
    assert erased.records == []


def test_ac24_her_address_receives_one_e_mail_with_the_text_of_rule_27(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fr = load_fr()
    with zoe_deletes(tmp_path, fake_clock, fx01_grid, caplog) as erased:
        pass

    assert len(erased.sent) == 1
    message = erased.sent[0]
    body = body_of(message)
    assert (message["From"], message["To"]) == (SENDER, ZOE_EMAIL)
    assert message["Subject"] == DELETED_SUBJECT
    assert message.get_content_type() == "text/plain"
    assert message.get_content_charset() == "utf-8"
    assert body == DELETED_BODY
    assert "://" not in body
    assert fr["email.deleted.subject"] == DELETED_SUBJECT
    assert fr["email.deleted.body"] == DELETED_BODY


def test_ac24_deleted_message_is_the_one_the_erasure_sends() -> None:
    from nock.mailer import deleted_message

    message = deleted_message(account_settings(), ZOE_EMAIL)

    assert (message["From"], message["To"]) == (SENDER, ZOE_EMAIL)
    assert message["Subject"] == DELETED_SUBJECT
    assert message.get_content_type() == "text/plain"
    assert message.get_content_charset() == "utf-8"
    assert body_of(message) == DELETED_BODY


def test_ac24_the_erasure_is_one_done_row_with_its_counts_and_no_address(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with zoe_deletes(tmp_path, fake_clock, fx01_grid, caplog) as erased:
        pass

    now = erased.requested_at
    assert erased.rows == [ErasureRow(None, None, now, now, now, 1, 2, 1)]
    assert erased.listed == []


def test_ac24_the_files_hold_neither_her_address_nor_her_nickname(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with zoe_deletes(tmp_path, fake_clock, fx01_grid, caplog) as erased:
        pass

    assert erased.secrets_in_files == []


# ---- AC-26: the mailer raises at completion --------------------------------------


def test_ac26_a_failing_mailer_leaves_the_erasure_done_with_no_e_mail_time(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with zoe_deletes(
        tmp_path, fake_clock, fx01_grid, caplog, mail_fails=True
    ) as erased:
        pass

    now = erased.requested_at
    assert erased.deletion.status_code == 204
    assert erased.sent == []
    assert erased.rows == [ErasureRow(None, None, now, now, None, 1, 2, 1)]
    assert erased.listed == []
    assert erased.nicknames_in_r == [FORMER_NICKNAME]
    assert erased.nicknames_in_s == [FORMER_NICKNAME]
    assert erased.u_exists is False
    assert erased.secrets_in_files == []


def test_ac26_the_failure_is_logged_once_without_the_address(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with zoe_deletes(
        tmp_path, fake_clock, fx01_grid, caplog, mail_fails=True
    ) as erased:
        pass

    assert len(erased.records) == 1
    formatted = logging.Formatter().format(erased.records[0])
    assert ZOE_EMAIL not in formatted


def test_ac26_no_later_sweep_sends_anything(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with zoe_deletes(
        tmp_path, fake_clock, fx01_grid, caplog, mail_fails=True
    ) as erased:
        rows_after_the_deletion = erased.rows

    with account_app(tmp_path, fake_clock, config=FAST_SWEEP_CONFIG) as app:
        time.sleep(LATER_SWEEPS_SECONDS)
        sent = list(app.mailer.messages)
        rows = erasure_rows(app.database_path)

    assert sent == []
    assert rows == rows_after_the_deletion


# ---- AC-25: the next sweep finishes a pending erasure ----------------------------


def test_ac25_the_next_sweep_of_the_app_finishes_a_pending_erasure(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock, config=FAST_SWEEP_CONFIG) as app:
        play = play_fx01(
            fx01_grid,
            "RRRRRR",
            [Player(ZOE_NICKNAME, ZOE, TZ)],
            start=app.clock(),
            solved_after=None,
        )
        app.registry.add_room(play.state)
        session = sign_in_from(app, ZOE_EMAIL, "RRRRRR", TZ)
        link_room(app.client, session, "RRRRRR", TZ)
        account_id = account_id_of(app, session)
        sent_before = len(app.mailer.messages)

        pending = app.accounts.delete_account(account_id, app.clock())
        wait_for(lambda: len(app.mailer.messages) > sent_before, "the e-mail")
        wait_for(lambda: app.accounts.pending_erasures() == [], "the erasure done")
        time.sleep(LATER_SWEEPS_SECONDS)
        sent = app.mailer.messages[sent_before:]
        state = state_of(app.registry, "RRRRRR")
        rows = erasure_rows(app.database_path)

    assert pending is not None
    assert len(sent) == 1
    assert (sent[0]["To"], sent[0]["Subject"]) == (ZOE_EMAIL, DELETED_SUBJECT)
    assert nicknames_of(state, ZOE) == [FORMER_NICKNAME]
    assert [(row.account_id, row.email, row.attempts, row.players) for row in rows] == [
        (None, None, 1, 1)
    ]
