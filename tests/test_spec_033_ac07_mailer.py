"""Tests of spec 033, AC-7: the sign-in link is sent with the standard library.

Three ways, as the criterion's brackets say:

- A test SMTP server, written here with asyncio streams on 127.0.0.1 and a free
  port (no new dependency): `SmtpMailer` with `security="none"` delivers
  `sign_in_message(SETTINGS, ...)` to it, and the recorded envelope and data are
  checked. A server that answers `550` to `RCPT` makes `send` raise `MailError`,
  whose text and traceback hold no address; through the app, the link request
  then answers 503.
- `smtplib.SMTP` and `smtplib.SMTP_SSL` replaced (`monkeypatch.setattr`) by
  recorders that keep their arguments and calls: `starttls` and `tls` open a
  connection with a timeout of 10 s and a context that checks the certificate and
  the host name, log in when a user is set, send the message and quit.
- HTTP, with the app of the "Test harness".

The arguments of each replaced call are bound to the signature of the real
`smtplib` method, so that a value passed by position or by keyword is read alike.
Calls that ask nothing of the server (`ehlo`, `helo`, `ehlo_or_helo_if_needed`,
`set_debuglevel`, `has_extn`, `noop`, `close`) are left out of the order checked.

Edge cases checked as well: `security="none"` with smtplib replaced opens no TLS;
a refusal raised by `send_message`, and a port where no server listens, also make
`send` raise `MailError`.
"""

from __future__ import annotations

import asyncio
import contextlib
import email
import email.policy
import inspect
import smtplib
import socket
import ssl
import threading
import traceback
from collections.abc import Iterator
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest
from fastapi.testclient import TestClient

from spec017_harness import FakeClock
from spec033_harness import (
    ANA_EMAIL,
    LINK_PATH,
    MAIL_NOT_SENT,
    PUBLIC_URL,
    SENDER,
    FailingMailer,
    account_app,
    account_settings,
    load_fr,
)

if TYPE_CHECKING:
    from nock.settings import AccountSettings, SmtpSettings

TOKEN = "abcdefghijklmnopqrstuvwxyz" + "ABCDEFGHIJKLMNOPQ"  # 43 characters
PASSWORD = "pw-SECRET-9"
SERVER_WAIT_SECONDS = 10.0
QUIET_CALLS = frozenset(
    {
        "ehlo",
        "helo",
        "ehlo_or_helo_if_needed",
        "set_debuglevel",
        "has_extn",
        "noop",
        "close",
    }
)
REAL_SMTP = smtplib.SMTP
REAL_SMTP_SSL = smtplib.SMTP_SSL


def smtp_settings(
    host: str,
    port: int,
    security: str,
    user: str | None = None,
    password: str | None = None,
) -> SmtpSettings:
    """`SmtpSettings` for the sender `nock@example.org`."""
    from nock.settings import SmtpSettings

    return SmtpSettings.model_validate(
        {
            "host": host,
            "port": port,
            "security": security,
            "user": user,
            "password": password,
            "sender": SENDER,
        }
    )


def the_message(to: str = ANA_EMAIL) -> EmailMessage:
    """`sign_in_message(SETTINGS, to, TOKEN)`."""
    from nock.mailer import sign_in_message

    return sign_in_message(account_settings(), to, TOKEN)


def send(settings: SmtpSettings, message: EmailMessage) -> None:
    """`SmtpMailer(settings).send(message)`."""
    from nock.mailer import SmtpMailer

    SmtpMailer(settings).send(message)


def mail_error() -> type[Exception]:
    from nock.mailer import MailError

    return MailError


def free_port() -> int:
    """A port of 127.0.0.1 where nothing listens."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


# ---- The test SMTP server -----------------------------------------------------------


class Delivery(NamedTuple):
    """One message the test server accepted: its envelope and its data."""

    sender: str
    recipients: list[str]
    data: bytes


def address_in(command: str) -> str:
    """The address between `<` and `>` of a MAIL or RCPT command."""
    start = command.find("<")
    end = command.find(">", start)
    return command[start + 1 : end]


class TestSmtpServer:
    """The minimal SMTP server of the "Test harness", run in a thread.

    It greets with 220, answers EHLO and HELO with 250, MAIL and RCPT with 250 (or
    RCPT with 550 when `refuse_recipients` is True), DATA with 354 then 250 after
    the line `.`, QUIT with 221, RSET and NOOP with 250, anything else with 502,
    and records each message it accepts.
    """

    __test__ = False  # not a test class, whatever its name

    def __init__(self, refuse_recipients: bool) -> None:
        self.refuse_recipients = refuse_recipients
        self.deliveries: list[Delivery] = []
        self.port = 0
        self._loop = asyncio.new_event_loop()
        self._server: asyncio.Server | None = None
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)

    def start(self) -> None:
        """Start listening on a free port of 127.0.0.1."""
        self._thread.start()
        started = asyncio.run_coroutine_threadsafe(self._listen(), self._loop)
        started.result(timeout=SERVER_WAIT_SECONDS)

    def stop(self) -> None:
        """Stop listening and end the thread."""
        stopped = asyncio.run_coroutine_threadsafe(self._close(), self._loop)
        stopped.result(timeout=SERVER_WAIT_SECONDS)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=SERVER_WAIT_SECONDS)
        self._loop.close()

    async def _listen(self) -> None:
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def _close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _serve(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await self._reply(writer, "220 test.invalid ESMTP")
        sender = ""
        recipients: list[str] = []
        while True:
            line = await reader.readline()
            if line == b"":
                break
            command = line.decode("ascii", errors="replace").strip()
            verb = command[:4].upper()
            if verb in ("EHLO", "HELO"):
                await self._reply(writer, "250 test.invalid")
            elif verb == "MAIL":
                sender = address_in(command)
                recipients = []
                await self._reply(writer, "250 OK")
            elif verb == "RCPT":
                if self.refuse_recipients:
                    await self._reply(writer, "550 No such user here")
                else:
                    recipients.append(address_in(command))
                    await self._reply(writer, "250 OK")
            elif verb == "DATA":
                await self._reply(writer, "354 End data with <CR><LF>.<CR><LF>")
                data = await self._read_data(reader)
                self.deliveries.append(Delivery(sender, list(recipients), data))
                await self._reply(writer, "250 OK")
            elif verb == "QUIT":
                await self._reply(writer, "221 Bye")
                break
            elif verb in ("RSET", "NOOP"):
                await self._reply(writer, "250 OK")
            else:
                await self._reply(writer, "502 Command not implemented")
        writer.close()

    async def _read_data(self, reader: asyncio.StreamReader) -> bytes:
        """The lines up to the line `.`, with the leading dots removed (RFC 5321)."""
        lines: list[bytes] = []
        while True:
            line = await reader.readline()
            if line in (b".\r\n", b".\n", b""):
                break
            if line.startswith(b".."):
                line = line[1:]
            lines.append(line)
        return b"".join(lines)

    async def _reply(self, writer: asyncio.StreamWriter, text: str) -> None:
        writer.write(text.encode("ascii") + b"\r\n")
        await writer.drain()


@contextlib.contextmanager
def smtp_server(refuse_recipients: bool = False) -> Iterator[TestSmtpServer]:
    server = TestSmtpServer(refuse_recipients)
    server.start()
    try:
        yield server
    finally:
        server.stop()


def delivered_message(server: TestSmtpServer) -> EmailMessage:
    """The one message the server accepted, parsed as the criterion says."""
    assert len(server.deliveries) == 1, server.deliveries
    parsed = email.message_from_bytes(
        server.deliveries[0].data, policy=email.policy.default
    )
    assert isinstance(parsed, EmailMessage)
    return parsed


# ---- AC-7: a real conversation with the test server ---------------------------------


def test_ac7_the_mailer_delivers_one_message_to_the_test_server() -> None:
    with smtp_server() as server:
        send(smtp_settings("127.0.0.1", server.port, "none"), the_message())

        deliveries = list(server.deliveries)

    assert len(deliveries) == 1
    assert deliveries[0].sender == SENDER
    assert deliveries[0].recipients == [ANA_EMAIL]


def test_ac7_the_delivered_subject_is_the_french_subject() -> None:
    with smtp_server() as server:
        send(smtp_settings("127.0.0.1", server.port, "none"), the_message())

        message = delivered_message(server)

    assert message["Subject"] == load_fr()["email.sign_in.subject"]


def test_ac7_the_delivered_body_is_plain_utf_8_text_holding_the_link() -> None:
    with smtp_server() as server:
        send(smtp_settings("127.0.0.1", server.port, "none"), the_message())

        message = delivered_message(server)

    assert message.get_content_type() == "text/plain"
    assert message.get_content_charset() == "utf-8"
    assert f"{PUBLIC_URL}/account#{TOKEN}" in message.get_content()


def test_ac7_the_message_is_from_the_sender_to_the_address() -> None:
    message = the_message()

    assert message["From"] == SENDER
    assert message["To"] == ANA_EMAIL


def test_ac7_a_refused_recipient_makes_send_raise_mail_error() -> None:
    with (
        smtp_server(refuse_recipients=True) as server,
        pytest.raises(mail_error()),
    ):
        send(smtp_settings("127.0.0.1", server.port, "none"), the_message())


def test_ac7_the_error_of_a_refused_recipient_does_not_hold_the_address() -> None:
    with (
        smtp_server(refuse_recipients=True) as server,
        pytest.raises(mail_error()) as caught,
    ):
        send(smtp_settings("127.0.0.1", server.port, "none"), the_message())

    error = caught.value
    assert ANA_EMAIL not in str(error)
    assert ANA_EMAIL not in "".join(traceback.format_exception(error))


def test_ac7_a_port_where_no_server_listens_makes_send_raise_mail_error() -> None:
    settings = smtp_settings("127.0.0.1", free_port(), "none")

    with pytest.raises(mail_error()):
        send(settings, the_message())


def test_ac7_through_the_app_a_refused_recipient_answers_503(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    from nock.settings import AccountSettings

    with smtp_server(refuse_recipients=True) as server:
        smtp = smtp_settings("127.0.0.1", server.port, "none")
        settings = AccountSettings.model_validate(
            {"public_url": PUBLIC_URL, "smtp": smtp}
        )
        # No mailer given: the app sends with SmtpMailer(accounts.smtp).
        with _app_without_mailer(tmp_path, fake_clock, settings) as client:
            response = client.post(LINK_PATH, json={"email": ANA_EMAIL, "room": None})

    assert response.status_code == 503
    assert response.json() == MAIL_NOT_SENT


def test_ac7_through_the_app_the_failing_mailer_answers_503(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock, mailer=FailingMailer()) as app:
        response = app.client.post(LINK_PATH, json={"email": ANA_EMAIL, "room": None})

    assert response.status_code == 503
    assert response.json() == MAIL_NOT_SENT


@contextlib.contextmanager
def _app_without_mailer(
    tmp_path: Path, clock: FakeClock, settings: AccountSettings
) -> Iterator[TestClient]:
    """The app of the "Test harness" with no mailer given; yield its TestClient."""
    from nock.accounts import AccountStore
    from nock.hub import RoomRegistry
    from nock.server import create_app
    from nock.store import RoomStore

    path = tmp_path / "nock.sqlite3"
    store = RoomStore(path)
    registry = RoomRegistry(clock=clock, store=store)
    account_store = AccountStore(path)
    try:
        app = create_app(
            rooms=registry,
            dist_dir=tmp_path,
            accounts=settings,
            account_store=account_store,
        )
        with TestClient(app) as client:
            yield client
    finally:
        account_store.close()
        registry.close()
        store.close()


# ---- AC-7: smtplib replaced ---------------------------------------------------------


class SmtpCall(NamedTuple):
    """One call made on a replaced smtplib class: its name and bound arguments."""

    name: str
    arguments: dict[str, object]


def bound_arguments(
    function: object, args: tuple[object, ...], kwargs: dict[str, object]
) -> dict[str, object]:
    """The arguments of a call, bound to the real function's signature."""
    assert callable(function)
    signature = inspect.signature(function)
    bound = signature.bind(*args, **kwargs)
    arguments = dict(bound.arguments)
    arguments.pop("self", None)
    return arguments


class SmtpRecorder:
    """The recorders of "smtplib replaced": they keep their arguments and calls.

    `SMTP` and `SMTP_SSL` are the classes that stand for `smtplib.SMTP` and
    `smtplib.SMTP_SSL`. `fail_on` names a method that raises the smtplib error
    `failure` instead of answering.
    """

    def __init__(
        self, fail_on: str | None = None, failure: Exception | None = None
    ) -> None:
        self.calls: list[SmtpCall] = []
        self.fail_on = fail_on
        self.failure = failure
        self.SMTP = self._recording_class("SMTP", REAL_SMTP)
        self.SMTP_SSL = self._recording_class("SMTP_SSL", REAL_SMTP_SSL)

    def record(
        self,
        name: str,
        real: object,
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> None:
        self.calls.append(SmtpCall(name, bound_arguments(real, args, kwargs)))
        if name == self.fail_on and self.failure is not None:
            raise self.failure

    def names(self) -> list[str]:
        """The names of the calls that talk to the server, in order."""
        return [call.name for call in self.calls if call.name not in QUIET_CALLS]

    def call(self, name: str) -> SmtpCall:
        """The one call of that name."""
        found = [call for call in self.calls if call.name == name]
        assert len(found) == 1, self.calls
        return found[0]

    def _recording_class(self, class_name: str, real_class: type) -> type:
        recorder = self

        def method(name: str) -> object:
            real = getattr(real_class, name)

            def recorded(self: object, *args: object, **kwargs: object) -> object:
                recorder.record(name, real, (self, *args), kwargs)
                if name == "ehlo" or name == "helo":
                    return (250, b"test.invalid")
                if name == "has_extn":
                    return False
                if name == "send_message":
                    return {}
                if name in ("starttls", "login", "quit", "noop"):
                    return (250, b"OK")
                return None

            return recorded

        def init(self: object, *args: object, **kwargs: object) -> None:
            recorder.record(class_name, real_class, args, kwargs)

        def enter(self: object) -> object:
            return self

        def exit_block(self: object, *args: object) -> None:
            # A real `with` block ends with QUIT when nothing sent it before.
            if "quit" not in recorder.names():
                recorder.calls.append(SmtpCall("quit", {}))

        namespace: dict[str, object] = {
            "__init__": init,
            "__enter__": enter,
            "__exit__": exit_block,
        }
        for name in (
            "ehlo",
            "helo",
            "ehlo_or_helo_if_needed",
            "set_debuglevel",
            "has_extn",
            "noop",
            "starttls",
            "login",
            "send_message",
            "sendmail",
            "quit",
            "close",
        ):
            namespace[name] = method(name)
        return type(f"Recording{class_name}", (), namespace)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> SmtpRecorder:
    replaced = SmtpRecorder()
    monkeypatch.setattr(smtplib, "SMTP", replaced.SMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", replaced.SMTP_SSL)
    return replaced


def assert_checked_context(context: object) -> None:
    """A TLS context that checks the server's certificate and host name."""
    assert isinstance(context, ssl.SSLContext), context
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_ac7_starttls_connects_with_a_timeout_of_10_seconds(
    recorder: SmtpRecorder,
) -> None:
    message = the_message()

    send(smtp_settings("smtp.example", 587, "starttls"), message)

    connection = recorder.call("SMTP")
    assert connection.arguments.get("host") == "smtp.example"
    assert connection.arguments.get("port") == 587
    assert connection.arguments.get("timeout") == 10


def test_ac7_starttls_upgrades_with_a_context_that_checks_the_server(
    recorder: SmtpRecorder,
) -> None:
    send(smtp_settings("smtp.example", 587, "starttls"), the_message())

    assert_checked_context(recorder.call("starttls").arguments.get("context"))


def test_ac7_starttls_with_a_user_logs_in_sends_and_quits_in_order(
    recorder: SmtpRecorder,
) -> None:
    message = the_message()
    settings = smtp_settings("smtp.example", 587, "starttls", "nock", PASSWORD)

    send(settings, message)

    assert recorder.names() == ["SMTP", "starttls", "login", "send_message", "quit"]
    login = recorder.call("login")
    assert login.arguments.get("user") == "nock"
    assert login.arguments.get("password") == PASSWORD
    assert recorder.call("send_message").arguments.get("msg") is message


def test_ac7_starttls_without_a_user_does_not_log_in(
    recorder: SmtpRecorder,
) -> None:
    send(smtp_settings("smtp.example", 587, "starttls"), the_message())

    assert recorder.names() == ["SMTP", "starttls", "send_message", "quit"]


def test_ac7_tls_connects_with_smtp_ssl_a_checked_context_and_a_timeout(
    recorder: SmtpRecorder,
) -> None:
    send(smtp_settings("smtp.example", 465, "tls"), the_message())

    connection = recorder.call("SMTP_SSL")
    assert connection.arguments.get("host") == "smtp.example"
    assert connection.arguments.get("port") == 465
    assert connection.arguments.get("timeout") == 10
    assert_checked_context(connection.arguments.get("context"))


def test_ac7_tls_with_a_user_logs_in_sends_and_quits_without_starttls(
    recorder: SmtpRecorder,
) -> None:
    message = the_message()
    settings = smtp_settings("smtp.example", 465, "tls", "nock", PASSWORD)

    send(settings, message)

    assert recorder.names() == ["SMTP_SSL", "login", "send_message", "quit"]
    assert recorder.call("send_message").arguments.get("msg") is message


def test_ac7_none_connects_without_tls(recorder: SmtpRecorder) -> None:
    send(smtp_settings("smtp.example", 25, "none"), the_message())

    assert recorder.names() == ["SMTP", "send_message", "quit"]
    connection = recorder.call("SMTP")
    assert connection.arguments.get("port") == 25
    assert connection.arguments.get("timeout") == 10


def test_ac7_a_refusal_from_send_message_raises_mail_error_without_the_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = smtplib.SMTPRecipientsRefused({ANA_EMAIL: (550, b"No such user")})
    replaced = SmtpRecorder(fail_on="send_message", failure=refusal)
    monkeypatch.setattr(smtplib, "SMTP", replaced.SMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", replaced.SMTP_SSL)
    settings = smtp_settings("smtp.example", 587, "starttls")
    message = the_message()

    with pytest.raises(mail_error()) as caught:
        send(settings, message)

    error = caught.value
    assert ANA_EMAIL not in str(error)
    assert ANA_EMAIL not in "".join(traceback.format_exception(error))


def test_ac7_a_failed_login_raises_mail_error_without_the_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
    replaced = SmtpRecorder(fail_on="login", failure=refusal)
    monkeypatch.setattr(smtplib, "SMTP", replaced.SMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", replaced.SMTP_SSL)
    settings = smtp_settings("smtp.example", 587, "starttls", "nock", PASSWORD)
    message = the_message()

    with pytest.raises(mail_error()) as caught:
        send(settings, message)

    error = caught.value
    assert PASSWORD not in str(error)
    assert PASSWORD not in "".join(traceback.format_exception(error))
