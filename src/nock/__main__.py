"""Run the Nock server: `uv run python -m nock`.

The server listens on the address in NOCK_HOST and the port in NOCK_PORT, with
the limits of `nock.server.server_config`. The rooms are stored in the SQLite
file named by NOCK_DATABASE (spec 018), and NOCK_OPERATOR_TOKEN turns on the
operator pages (spec 038). NOCK_PUBLIC_URL and the NOCK_SMTP_* variables turn
on the accounts (spec 033), and the four NOCK_*_ROOM_HOURS and
NOCK_EXPIRY_SWEEP_MINUTES set the room lives and the sweep interval
(`lobby/lifetime.md`). The variables are checked before the server is built,
and a refused value stops the start (specs 036, 038 and 033).
"""

from __future__ import annotations

import os
import unicodedata

import uvicorn

import nock.server
from nock.settings import (
    MAX_LABEL_LENGTH,
    MAX_PORT,
    MIN_PORT,
    SettingsError,
    account_settings_from_env,
    is_host,
    operator_token_from_env,
    port_number,
    room_config_from_env,
)

HOST_VARIABLE: str = "NOCK_HOST"
PORT_VARIABLE: str = "NOCK_PORT"
DATABASE_VARIABLE: str = nock.server.DATABASE_VARIABLE  # the app reads it (spec 018)
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8000
# NOCK_DATABASE refuses the characters of these Unicode general categories (as
# unicodedata.category gives them): most are invisible, or they end a line, so
# the path could name another file than the one the operator reads.
REFUSED_DATABASE_CATEGORIES: frozenset[str] = frozenset(
    {
        "Cc",  # control characters: newline, tab, escape, DEL, U+0080 to U+009F
        "Cf",  # format characters: zero width space, byte order mark, soft hyphen
        "Zl",  # the line separator, U+2028
        "Zp",  # the paragraph separator, U+2029
    }
)
# These two format characters stay allowed: some scripts need them inside words.
ALLOWED_JOINERS: frozenset[str] = frozenset(
    {"\N{ZERO WIDTH NON-JOINER}", "\N{ZERO WIDTH JOINER}"}
)


def main() -> None:
    """Run `nock.server.app` with `server_config` until the server stops.

    The host comes from NOCK_HOST (default 127.0.0.1) and the port from
    NOCK_PORT (default 8000), once NOCK_OPERATOR_TOKEN (checked first),
    NOCK_HOST, NOCK_PORT and NOCK_DATABASE have passed the checks below. The
    variables are read at each call. An unset or empty NOCK_HOST or
    NOCK_PORT takes its default. An unset or empty NOCK_DATABASE is not checked,
    and the app then keeps its rooms in memory. An unset or empty
    NOCK_OPERATOR_TOKEN is not checked either, and the operator pages are off.

    The values each variable takes:

    - NOCK_OPERATOR_TOKEN: the rule of `nock.settings.operator_token_from_env`
      (spec 038): 32 to 256 characters, each one an ASCII letter, an ASCII
      digit, "_" or "-". The variable is not changed: the app reads it when it
      starts.
    - NOCK_HOST: a host name or an IP address. Each character is an ASCII
      letter, an ASCII digit, a dot, a dash or a colon, and a value that holds
      a colon is an IPv6 address that `ipaddress.IPv6Address` accepts, so it is
      written without brackets (::1, not [::1]). A value without a colon is a
      name, cut at each dot into labels: each label holds 1 to 63 characters,
      and only the last label may be empty, so that a name ending with a dot
      passes (example.org.), while a..b, .example and a label of 64 characters
      are refused. It is passed to uvicorn as given.
    - NOCK_PORT: ASCII digits only, with a value from 1 to 65535.
    - NOCK_DATABASE: a file path without a refused character. A character is
      refused when its Unicode general category is Cc (control characters), Cf
      (format characters), Zl or Zp (line and paragraph separators), except
      U+200C and U+200D. Spaces, accents and path separators are allowed. The
      variable is not changed: the app reads it when it starts.
    - NOCK_CREATOR_SOLVED_ROOM_HOURS, NOCK_CREATOR_ROOM_HOURS,
      NOCK_ANONYMOUS_SOLVED_ROOM_HOURS, NOCK_ANONYMOUS_ROOM_HOURS and
      NOCK_EXPIRY_SWEEP_MINUTES, checked after NOCK_DATABASE: the rule of
      `nock.settings.room_config_from_env` (`lobby/lifetime.md` rule 7). A
      room life is 24 to 8760 hours and the sweep interval 1 to 1440 minutes,
      each in ASCII digits only. The variables are not changed: the app reads
      them when it starts.
    - NOCK_PUBLIC_URL and the NOCK_SMTP_* variables, checked last: the rules of
      `nock.settings.account_settings_from_env` (spec 033). The app reads them
      again when it starts.

    Raises:
        SystemExit: A variable holds a refused value, and no server is built.
            Its code is a one-line message that names the variable. For
            NOCK_HOST, NOCK_PORT and NOCK_DATABASE it shows the value as
            `repr()` writes it; for NOCK_OPERATOR_TOKEN, a secret, it names the
            rule broken and never shows the value.
    """
    _check_operator_token()
    host = _read_host()
    port = _read_port()
    _check_database()
    _check_room_config()
    _check_account_settings()
    config = nock.server.server_config(nock.server.app, host=host, port=port)
    uvicorn.Server(config).run()


def _check_operator_token() -> None:
    """Stop the start when NOCK_OPERATOR_TOKEN breaks the rule of spec 038.

    An unset or empty NOCK_OPERATOR_TOKEN passes: the operator pages are off.
    The variable is only read: the app reads it again when it starts.

    Raises:
        SystemExit: NOCK_OPERATOR_TOKEN breaks the rule. Its code is the message
            of the SettingsError, which never holds the value.
    """
    try:
        operator_token_from_env(os.environ)
    except SettingsError as error:
        raise SystemExit(str(error)) from error


def _check_room_config() -> None:
    """Stop the start when a room life or the sweep interval breaks its rule.

    The variables are only read: the app reads them again when it starts.

    Raises:
        SystemExit: a variable breaks the rule of `room_config_from_env`. Its
            code is the message of the SettingsError, which shows the value.
    """
    try:
        room_config_from_env(os.environ)
    except SettingsError as error:
        raise SystemExit(str(error)) from error


def _check_account_settings() -> None:
    """Stop the start when a variable of the accounts breaks its rule (spec 033).

    While NOCK_PUBLIC_URL and NOCK_SMTP_HOST are both unset or empty, accounts
    are off and the other NOCK_SMTP_* variables are not read. The variables are
    only read: the app reads them again when it starts.

    Raises:
        SystemExit: a variable breaks the rule of `account_settings_from_env`.
            Its code is the message of the SettingsError, which never holds the
            SMTP password.
    """
    try:
        account_settings_from_env(os.environ)
    except SettingsError as error:
        raise SystemExit(str(error)) from error


def _read_host() -> str:
    """Return the host in NOCK_HOST, or DEFAULT_HOST when it is unset or empty.

    Raises:
        SystemExit: NOCK_HOST is not a host name or an IP address.
    """
    host = os.environ.get(HOST_VARIABLE, "")
    if host == "":
        return DEFAULT_HOST
    if not is_host(host):
        raise _refusal(
            HOST_VARIABLE,
            "a host name or an IP address, written with the letters A to Z and "
            "a to z, the digits 0 to 9, dots and dashes only (an IPv6 address "
            "also has colons, and no brackets); the dots of a name cut it into "
            f"labels of 1 to {MAX_LABEL_LENGTH} characters, and only the last "
            "label may be empty (example.org.)",
            host,
        )
    return host


def _read_port() -> int:
    """Return the port in NOCK_PORT, or DEFAULT_PORT when it is unset or empty.

    Raises:
        SystemExit: NOCK_PORT is not ASCII digits for a number from 1 to 65535.
    """
    text = os.environ.get(PORT_VARIABLE, "")
    if text == "":
        return DEFAULT_PORT
    port = port_number(text)
    if port is None:
        raise _refusal(
            PORT_VARIABLE,
            f"a whole number from {MIN_PORT} to {MAX_PORT}, "
            "written with the digits 0 to 9 only",
            text,
        )
    return port


def _check_database() -> None:
    """Stop the start when NOCK_DATABASE holds a refused character.

    An unset or empty NOCK_DATABASE holds none, so it passes. The variable is
    only read: the app reads it again when it starts (spec 018).

    Raises:
        SystemExit: NOCK_DATABASE holds a refused character.
    """
    database = os.environ.get(DATABASE_VARIABLE, "")
    if _holds_refused_character(database):
        raise _refusal(
            DATABASE_VARIABLE,
            "a file path without control characters, line or paragraph "
            "separators, or format characters other than the zero width joiner "
            "and non-joiner",
            database,
        )


def _holds_refused_character(text: str) -> bool:
    """Tell whether `text` holds a character that NOCK_DATABASE refuses."""
    return any(_is_refused_in_database(character) for character in text)


def _is_refused_in_database(character: str) -> bool:
    """Tell whether NOCK_DATABASE refuses `character`.

    It does when the category of `character` is in REFUSED_DATABASE_CATEGORIES,
    unless `character` is one of ALLOWED_JOINERS.
    """
    if character in ALLOWED_JOINERS:
        return False
    return unicodedata.category(character) in REFUSED_DATABASE_CATEGORIES


def _refusal(variable: str, expected: str, value: str) -> SystemExit:
    """Return the SystemExit that stops the start for a refused `value`.

    Its code is a one-line message: the variable, what it must be, and the value
    as `repr()` writes it. `repr()` escapes the control and invisible characters
    and doubles the backslashes, so the value cannot split the message into
    lines or drive the terminal of the operator, and an escape in the message
    never hides a backslash of the value.
    """
    return SystemExit(f"{variable} must be {expected}, not {value!r}")


if __name__ == "__main__":
    main()
