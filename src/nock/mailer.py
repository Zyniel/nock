"""Sending the e-mails of the accounts: the sign-in link and the deletion notice.

This is the only module of the server that opens a network connection: it sends
mail with the standard library's `smtplib`, over TLS that checks the server's
certificate and host name (spec 005 decision 7 allows `smtplib` and `ssl` here
only).
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from nock.i18n import t
from nock.settings import AccountSettings, SmtpSettings

SMTP_TIMEOUT_SECONDS: int = 10


class MailError(Exception):
    """A message could not be sent.

    Neither its text nor its traceback (`traceback.format_exception`) holds a
    password, a token or a player's address: the `smtplib` error behind it, whose
    text may hold the address, does not show in that traceback (for example
    `raise MailError(...) from None`).
    """


class Mailer(Protocol):
    """Something that sends e-mail: `SmtpMailer`, or a stand-in in the tests."""

    def send(self, message: EmailMessage) -> None:
        """Send one message. Raises MailError when it is not sent."""
        ...


class SmtpMailer:
    """A Mailer that sends with `smtplib`."""

    def __init__(self, settings: SmtpSettings) -> None:
        """Keep the settings of the SMTP server; nothing is opened yet.

        Args:
            settings: The SMTP server and how to reach it.
        """
        self._settings = settings

    def send(self, message: EmailMessage) -> None:
        """Send `message` through the SMTP server, with a timeout of 10 seconds.

        - `tls`: `smtplib.SMTP_SSL(host, port, context=<context>, timeout=10)`;
        - `starttls`: `smtplib.SMTP(host, port, timeout=10)`, then
          `starttls(context=<context>)`;
        - `none`: `smtplib.SMTP(host, port, timeout=10)`, no TLS;

        where `<context>` is `ssl.create_default_context()`, which checks the
        server's certificate and host name. Then `login(user, password)` when a
        user is set, `send_message(message)` and `quit()`.

        Args:
            message: The message, with its `From` and `To`.

        Raises:
            MailError: any failure (connection, TLS, login, refusal, timeout).
                It names the kind of failure only.
        """
        try:
            self._send(message)
        except (smtplib.SMTPException, OSError, UnicodeError) as error:
            # `from None`: the smtplib error may name the recipient, and a
            # chained error would show in the traceback that a log writes.
            failure = type(error).__name__
            raise MailError(f"The message was not sent ({failure})") from None

    def _send(self, message: EmailMessage) -> None:
        """Talk to the SMTP server; its errors go to the caller as they are."""
        settings = self._settings
        if settings.security == "tls":
            connection = smtplib.SMTP_SSL(
                settings.host,
                settings.port,
                context=ssl.create_default_context(),
                timeout=SMTP_TIMEOUT_SECONDS,
            )
        else:
            connection = smtplib.SMTP(
                settings.host, settings.port, timeout=SMTP_TIMEOUT_SECONDS
            )
        # The block closes the connection, also when a step fails.
        with connection:
            if settings.security == "starttls":
                connection.starttls(context=ssl.create_default_context())
            if settings.user is not None and settings.password is not None:
                connection.login(settings.user, settings.password.get_secret_value())
            connection.send_message(message)
            connection.quit()


def sign_in_message(settings: AccountSettings, to: str, token: str) -> EmailMessage:
    """Return the sign-in e-mail of a link.

    Args:
        settings: The account settings: the sender and the public URL.
        to: The normalised address the link is for.
        token: The raw token of the link.

    Returns:
        A message `From` the sender, `To` the address, with the `Subject`
        `t("email.sign_in.subject")` and a plain-text UTF-8 body
        `t("email.sign_in.body", link=f"{settings.public_url}/account#{token}")`.
    """
    link = f"{settings.public_url}/account#{token}"
    message = EmailMessage()
    message["From"] = settings.smtp.sender
    message["To"] = to
    message["Subject"] = t("email.sign_in.subject")
    # Quoted-printable: the body stays 7-bit, which every SMTP server takes.
    message.set_content(
        t("email.sign_in.body", link=link), charset="utf-8", cte="quoted-printable"
    )
    return message


def deleted_message(settings: AccountSettings, to: str) -> EmailMessage:
    """Return the e-mail that says an account's erasure is done.

    Args:
        settings: The account settings: the sender.
        to: The address of the deleted account, as the pending erasure holds it.

    Returns:
        A message `From` the sender, `To` the address, with the `Subject`
        `t("email.deleted.subject")` and a plain-text UTF-8 body
        `t("email.deleted.body")`, which holds no link.
    """
    message = EmailMessage()
    message["From"] = settings.smtp.sender
    message["To"] = to
    message["Subject"] = t("email.deleted.subject")
    message.set_content(
        t("email.deleted.body"), charset="utf-8", cte="quoted-printable"
    )
    return message
