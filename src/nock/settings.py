"""Settings the server reads from its environment (specs 036, 038 and 033).

Three groups of settings live here:

- the operator token of NOCK_OPERATOR_TOKEN, which turns on the operator pages
  (spec 038);
- the account settings (spec 033): the public URL of the server and how it sends
  e-mail, from NOCK_PUBLIC_URL and the NOCK_SMTP_* variables;
- the room lives and the sweep interval (`lobby/lifetime.md`), from the four
  NOCK_*_ROOM_HOURS variables and NOCK_EXPIRY_SWEEP_MINUTES.

The rules of a host and of a port are those of NOCK_HOST and NOCK_PORT (spec 036),
which `nock.__main__` checks with the same functions.

No message of this module ever holds the value of a secret: the operator token or
the SMTP password. A message that refuses any other value shows it as `repr()`
writes it, so that the message stays on one line.
"""

from __future__ import annotations

import ipaddress
import string
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from nock.accounts import normalize_email
from nock.room import (
    DEFAULT_ROOM_LIFE_HOURS,
    MAX_ROOM_LIFE_HOURS,
    MIN_ROOM_LIFE_HOURS,
    RoomConfig,
)

OPERATOR_TOKEN_VARIABLE: str = "NOCK_OPERATOR_TOKEN"
OPERATOR_TOKEN_MIN_LENGTH: int = 32
OPERATOR_TOKEN_MAX_LENGTH: int = 256
# The characters of `secrets.token_urlsafe`: ASCII letters, ASCII digits, "_" and
# "-". They are explicit ASCII sets: str.isalnum() also accepts other scripts.
OPERATOR_TOKEN_CHARACTERS: frozenset[str] = frozenset(
    string.ascii_letters + string.digits + "_-"
)

# The variables of the accounts (spec 033).
PUBLIC_URL_VARIABLE: str = "NOCK_PUBLIC_URL"
SMTP_HOST_VARIABLE: str = "NOCK_SMTP_HOST"
SMTP_PORT_VARIABLE: str = "NOCK_SMTP_PORT"
SMTP_SECURITY_VARIABLE: str = "NOCK_SMTP_SECURITY"
SMTP_USER_VARIABLE: str = "NOCK_SMTP_USER"
SMTP_PASSWORD_VARIABLE: str = "NOCK_SMTP_PASSWORD"
SMTP_FROM_VARIABLE: str = "NOCK_SMTP_FROM"

# The variables of the room lives and the sweep (`lobby/lifetime.md` rule 7).
CREATOR_SOLVED_ROOM_HOURS_VARIABLE: str = "NOCK_CREATOR_SOLVED_ROOM_HOURS"
CREATOR_ROOM_HOURS_VARIABLE: str = "NOCK_CREATOR_ROOM_HOURS"
ANONYMOUS_SOLVED_ROOM_HOURS_VARIABLE: str = "NOCK_ANONYMOUS_SOLVED_ROOM_HOURS"
ANONYMOUS_ROOM_HOURS_VARIABLE: str = "NOCK_ANONYMOUS_ROOM_HOURS"
EXPIRY_SWEEP_MINUTES_VARIABLE: str = "NOCK_EXPIRY_SWEEP_MINUTES"
MIN_SWEEP_MINUTES: int = 1
MAX_SWEEP_MINUTES: int = 1440
DEFAULT_SWEEP_MINUTES: int = 60
SECONDS_PER_MINUTE: float = 60.0

URL_SCHEMES: tuple[str, ...] = ("http://", "https://")
# The usual port of each security mode, used when NOCK_SMTP_PORT is unset.
DEFAULT_SMTP_PORTS: dict[str, int] = {"starttls": 587, "tls": 465, "none": 25}
# Printable ASCII: U+0020 SPACE to U+007E TILDE. The SMTP user, password and
# sender take these characters only (spec 033 decision 14).
FIRST_PRINTABLE_ASCII: str = " "
LAST_PRINTABLE_ASCII: str = "~"

# The characters of a host (NOCK_HOST, spec 036) are explicit ASCII sets:
# str.isalnum() and str.isdigit() also accept the letters and digits of other
# scripts.
HOST_LETTERS: str = string.ascii_letters  # A to Z and a to z: host names are ASCII
HOST_DIGITS: str = string.digits  # 0 to 9 only, not the digits of other scripts
HOST_NAME_MARKS: str = ".-"  # the dot between the labels of a name, the dash in one
IPV6_MARK: str = ":"  # only an IPv6 address holds it, written without brackets
HOST_CHARACTERS: str = HOST_LETTERS + HOST_DIGITS + HOST_NAME_MARKS + IPV6_MARK
# The idna codec's limit on a label: uvicorn would end with a traceback past it.
MAX_LABEL_LENGTH: int = 63
MIN_PORT: int = 1
MAX_PORT: int = 65535

_HOST_RULE = (
    "a host name or an IP address, written with the letters A to Z and a to z, "
    "the digits 0 to 9, dots and dashes only (an IPv6 address also has colons, "
    "and no brackets); the dots of a name cut it into labels of 1 to "
    f"{MAX_LABEL_LENGTH} characters, and only the last label may be empty"
)
_PORT_RULE = (
    f"a whole number from {MIN_PORT} to {MAX_PORT}, written with the digits 0 to 9 "
    "only"
)
_ROOM_LIFE_RULE = (
    f"a whole number of hours from {MIN_ROOM_LIFE_HOURS} to {MAX_ROOM_LIFE_HOURS}, "
    "written with the digits 0 to 9 only"
)
_SWEEP_RULE = (
    f"a whole number of minutes from {MIN_SWEEP_MINUTES} to {MAX_SWEEP_MINUTES}, "
    "written with the digits 0 to 9 only"
)
_PRINTABLE_ASCII_RULE = "written with the printable ASCII characters only"


class SettingsError(ValueError):
    """An environment variable holds a value the server cannot use.

    The message names the variable; it never holds the value of a secret.
    """


class SmtpSettings(BaseModel):
    """How the server sends e-mail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535, strict=True)
    security: Literal["starttls", "tls", "none"]
    user: str | None = None
    password: SecretStr | None = None  # its repr and str show no secret
    sender: str  # an address normalize_email accepts


class AccountSettings(BaseModel):
    """Accounts are on, with these settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    public_url: str  # "<scheme>://<host>[:<port>]", no trailing "/"
    smtp: SmtpSettings


def operator_token_from_env(environ: Mapping[str, str]) -> str | None:
    """Return the operator token of `environ["NOCK_OPERATOR_TOKEN"]`.

    Args:
        environ: The environment to read, such as `os.environ`.

    Returns:
        The token, or None when the variable is unset or empty (operator pages off).

    Raises:
        SettingsError: the value is not 32 to 256 characters, each one of A-Z,
            a-z, 0-9, "_" and "-". The message names the variable and the rule
            broken, never the value.
    """
    token = environ.get(OPERATOR_TOKEN_VARIABLE, "")
    if token == "":
        return None
    if len(token) < OPERATOR_TOKEN_MIN_LENGTH or len(token) > OPERATOR_TOKEN_MAX_LENGTH:
        raise SettingsError(
            f"{OPERATOR_TOKEN_VARIABLE} must have {OPERATOR_TOKEN_MIN_LENGTH} to "
            f"{OPERATOR_TOKEN_MAX_LENGTH} characters"
        )
    for character in token:
        if character not in OPERATOR_TOKEN_CHARACTERS:
            raise SettingsError(
                f"{OPERATOR_TOKEN_VARIABLE} must be written with the letters A to Z "
                "and a to z, the digits 0 to 9, '_' and '-' only"
            )
    return token


def room_config_from_env(environ: Mapping[str, str]) -> RoomConfig:
    """Return the room lives and the sweep interval of `environ`.

    Each of the five variables, unset or empty, takes its default. The other
    fields of the config are at their defaults.

    Args:
        environ: The environment to read, such as `os.environ`.

    Returns:
        The config: the four lives in hours, and the sweep interval in seconds.

    Raises:
        SettingsError: a variable is not a whole number written with ASCII
            digits, or is out of its bounds. The message is one line that names
            the variable and shows the value as `repr()` writes it.
    """
    sweep_minutes = _read_whole_number(
        environ,
        EXPIRY_SWEEP_MINUTES_VARIABLE,
        (MIN_SWEEP_MINUTES, MAX_SWEEP_MINUTES, DEFAULT_SWEEP_MINUTES),
        _SWEEP_RULE,
    )
    return RoomConfig(
        creator_solved_room_hours=_read_room_life(
            environ, CREATOR_SOLVED_ROOM_HOURS_VARIABLE
        ),
        creator_room_hours=_read_room_life(environ, CREATOR_ROOM_HOURS_VARIABLE),
        anonymous_solved_room_hours=_read_room_life(
            environ, ANONYMOUS_SOLVED_ROOM_HOURS_VARIABLE
        ),
        anonymous_room_hours=_read_room_life(environ, ANONYMOUS_ROOM_HOURS_VARIABLE),
        expiry_sweep_seconds=sweep_minutes * SECONDS_PER_MINUTE,
    )


def account_settings_from_env(environ: Mapping[str, str]) -> AccountSettings | None:
    """Return the account settings of `environ`, or None when accounts are off.

    Accounts are on when NOCK_PUBLIC_URL and NOCK_SMTP_HOST are both set. An
    empty variable counts as unset. While accounts are off, the other NOCK_SMTP_*
    variables are not read.

    Args:
        environ: The environment to read, such as `os.environ`.

    Returns:
        The settings, or None when NOCK_PUBLIC_URL and NOCK_SMTP_HOST are both
        unset or empty.

    Raises:
        SettingsError: a variable breaks the rules of spec 033's "Configuration".
            The message is one line that names the variable and shows a refused
            value as `repr()` writes it, except the SMTP password, which it
            never shows.
    """
    public_url_text = environ.get(PUBLIC_URL_VARIABLE, "")
    smtp_host = environ.get(SMTP_HOST_VARIABLE, "")
    if public_url_text == "" and smtp_host == "":
        return None
    if smtp_host == "":
        raise _missing(SMTP_HOST_VARIABLE, f"when {PUBLIC_URL_VARIABLE} is set")
    if public_url_text == "":
        raise _missing(PUBLIC_URL_VARIABLE, f"when {SMTP_HOST_VARIABLE} is set")
    public_url = _read_public_url(public_url_text)
    if not is_host(smtp_host):
        raise _refused(SMTP_HOST_VARIABLE, _HOST_RULE, smtp_host)
    security = _read_security(environ)
    port = _read_smtp_port(environ, security)
    user, password = _read_login(environ, security)
    sender = _read_sender(environ)
    smtp = SmtpSettings(
        host=smtp_host,
        port=port,
        security=security,
        user=user,
        password=password,
        sender=sender,
    )
    return AccountSettings(public_url=public_url, smtp=smtp)


def is_host(text: str) -> bool:
    """Tell whether `text` is a host name or an IP address that NOCK_HOST takes.

    Every character is in HOST_CHARACTERS. A text that holds a colon is an IPv6
    address that `ipaddress.IPv6Address` accepts, and any other text is a name
    whose dots cut it into labels of 1 to MAX_LABEL_LENGTH characters, where
    only the last label may be empty (example.org.). Whether a name resolves is
    not checked.

    Args:
        text: The value to check.

    Returns:
        True when NOCK_HOST takes `text`.
    """
    for character in text:
        if character not in HOST_CHARACTERS:
            return False
    if IPV6_MARK in text:
        return _is_ipv6_address(text)
    return _has_valid_labels(text)


def port_number(text: str) -> int | None:
    """Return the port number written in `text`, or None when it is not one.

    A port number is written with the ASCII digits 0 to 9 only (leading zeros
    are allowed, however many) and is from MIN_PORT to MAX_PORT.

    Args:
        text: The value to read.

    Returns:
        The port, or None when NOCK_PORT would refuse `text`.
    """
    return _bounded_number(text, MIN_PORT, MAX_PORT)


def _bounded_number(text: str, minimum: int, maximum: int) -> int | None:
    """Return the number written in `text`, or None when it is not acceptable.

    The text is ASCII digits 0 to 9 only (leading zeros are allowed, however
    many) and the number is from `minimum` to `maximum`.
    """
    if not text.isascii() or not text.isdigit():
        return None
    significant_digits = text.lstrip("0")
    if len(significant_digits) > len(str(maximum)):
        return None  # far too big, and int() refuses numbers of 4,300 digits
    if significant_digits == "":
        significant_digits = "0"  # all zeros: the number 0
    # Convert without the leading zeros: int() also refuses 4,300 of them.
    number = int(significant_digits)
    if number < minimum or number > maximum:
        return None
    return number


def _read_room_life(environ: Mapping[str, str], variable: str) -> int:
    """Return a room life in hours: the variable's value, else 720.

    Raises:
        SettingsError: the value is not 24 to 8760 in ASCII digits.
    """
    return _read_whole_number(
        environ,
        variable,
        (MIN_ROOM_LIFE_HOURS, MAX_ROOM_LIFE_HOURS, DEFAULT_ROOM_LIFE_HOURS),
        _ROOM_LIFE_RULE,
    )


def _read_whole_number(
    environ: Mapping[str, str],
    variable: str,
    bounds_and_default: tuple[int, int, int],
    rule: str,
) -> int:
    """Return the whole number in `variable`, or its default when unset or empty.

    Args:
        environ: The environment to read.
        variable: The variable's name.
        bounds_and_default: The least value, the greatest, and the default.
        rule: What the variable must be, for the message of a refusal.

    Raises:
        SettingsError: the value is not acceptable (see `_bounded_number`).
    """
    minimum, maximum, default = bounds_and_default
    text = environ.get(variable, "")
    if text == "":
        return default
    number = _bounded_number(text, minimum, maximum)
    if number is None:
        raise _refused(variable, rule, text)
    return number


def _has_valid_labels(name: str) -> bool:
    """Tell whether the dots of the host name `name` cut it into valid labels.

    A label holds 1 to MAX_LABEL_LENGTH characters. Only the last label may be
    empty, so that a name ending with a dot passes (example.org.).
    """
    labels = name.split(".")
    last_label = labels[-1]
    other_labels = labels[:-1]
    for label in other_labels:
        if label == "" or len(label) > MAX_LABEL_LENGTH:
            return False
    return len(last_label) <= MAX_LABEL_LENGTH


def _is_ipv6_address(text: str) -> bool:
    """Tell whether `ipaddress.IPv6Address` accepts `text`."""
    try:
        ipaddress.IPv6Address(text)
    except ipaddress.AddressValueError:
        return False
    return True


def _is_printable_ascii(text: str) -> bool:
    """Tell whether every character of `text` is from U+0020 to U+007E."""
    for character in text:
        if character < FIRST_PRINTABLE_ASCII or character > LAST_PRINTABLE_ASCII:
            return False
    return True


def _read_public_url(text: str) -> str:
    """Return the public URL of NOCK_PUBLIC_URL, without its trailing "/".

    The URL is `http://` or `https://`, a host that NOCK_SMTP_HOST takes and that
    holds no ":" (a name or an IPv4 address), then optionally ":" and a port
    that NOCK_SMTP_PORT takes, then optionally one "/".

    Raises:
        SettingsError: the URL breaks that rule.
    """
    rule = (
        "http:// or https://, then a host name or an IPv4 address, then "
        "optionally ':' and a port from 1 to 65535, with no user, path, query "
        "or fragment"
    )
    scheme = ""
    for known_scheme in URL_SCHEMES:
        if text.startswith(known_scheme):
            scheme = known_scheme
    if scheme == "":
        raise _refused(PUBLIC_URL_VARIABLE, rule, text)
    address = text.removeprefix(scheme).removesuffix("/")
    host, has_port, port_text = address.partition(":")
    if host == "" or not is_host(host):
        raise _refused(PUBLIC_URL_VARIABLE, rule, text)
    if not has_port:
        return f"{scheme}{host}"
    port = port_number(port_text)
    if port is None:
        raise _refused(PUBLIC_URL_VARIABLE, rule, text)
    return f"{scheme}{host}:{port}"


def _read_security(environ: Mapping[str, str]) -> Literal["starttls", "tls", "none"]:
    """Return the security mode of NOCK_SMTP_SECURITY, "starttls" when unset.

    Raises:
        SettingsError: the value is not exactly starttls, tls or none.
    """
    text = environ.get(SMTP_SECURITY_VARIABLE, "")
    if text == "":
        return "starttls"
    if text == "starttls":
        return "starttls"
    if text == "tls":
        return "tls"
    if text == "none":
        return "none"
    raise _refused(SMTP_SECURITY_VARIABLE, "exactly starttls, tls or none", text)


def _read_smtp_port(environ: Mapping[str, str], security: str) -> int:
    """Return the port of NOCK_SMTP_PORT, or the usual port of `security`.

    Raises:
        SettingsError: the value is not a port that NOCK_PORT takes.
    """
    text = environ.get(SMTP_PORT_VARIABLE, "")
    if text == "":
        return DEFAULT_SMTP_PORTS[security]
    port = port_number(text)
    if port is None:
        raise _refused(SMTP_PORT_VARIABLE, _PORT_RULE, text)
    return port


def _read_login(
    environ: Mapping[str, str], security: str
) -> tuple[str | None, SecretStr | None]:
    """Return the SMTP user and password, or (None, None) for no login.

    Raises:
        SettingsError: the user or the password holds a character outside
            printable ASCII, one of them is set without the other, or a password
            is set with the security "none". A message about the password names
            the variable and never shows its value.
    """
    user = environ.get(SMTP_USER_VARIABLE, "")
    password = environ.get(SMTP_PASSWORD_VARIABLE, "")
    if user != "" and not _is_printable_ascii(user):
        raise _refused(SMTP_USER_VARIABLE, _PRINTABLE_ASCII_RULE, user)
    if password != "" and not _is_printable_ascii(password):
        raise SettingsError(f"{SMTP_PASSWORD_VARIABLE} must be {_PRINTABLE_ASCII_RULE}")
    if user == "" and password == "":
        return None, None
    if password == "":
        raise _missing(SMTP_PASSWORD_VARIABLE, f"when {SMTP_USER_VARIABLE} is set")
    if user == "":
        raise SettingsError(
            f"{SMTP_PASSWORD_VARIABLE} is set without {SMTP_USER_VARIABLE}: "
            "set both, or neither"
        )
    if security == "none":
        raise SettingsError(
            f"{SMTP_PASSWORD_VARIABLE} cannot be sent over a plain connection: "
            f"set {SMTP_SECURITY_VARIABLE} to starttls or tls"
        )
    return user, SecretStr(password)


def _read_sender(environ: Mapping[str, str]) -> str:
    """Return the sender address of NOCK_SMTP_FROM, as `normalize_email` gives it.

    Raises:
        SettingsError: the variable is unset or empty, holds a character outside
            printable ASCII (checked before anything strips it), or is not an
            address that `normalize_email` accepts.
    """
    text = environ.get(SMTP_FROM_VARIABLE, "")
    if text == "":
        raise _missing(SMTP_FROM_VARIABLE, "when accounts are on")
    if not _is_printable_ascii(text):
        raise _refused(SMTP_FROM_VARIABLE, _PRINTABLE_ASCII_RULE, text)
    try:
        return normalize_email(text)
    except ValueError as error:
        raise _refused(SMTP_FROM_VARIABLE, "an e-mail address", text) from error


def _refused(variable: str, expected: str, value: str) -> SettingsError:
    """Return the error for a refused `value`, shown as `repr()` writes it.

    `repr()` escapes the control and invisible characters, so the value cannot
    split the message into lines. Never use it for a secret.
    """
    return SettingsError(f"{variable} must be {expected}, not {value!r}")


def _missing(variable: str, when: str) -> SettingsError:
    """Return the error for a variable that must be set; it shows no value."""
    return SettingsError(f"{variable} must be set {when}")
