"""Run the Nock server: `uv run python -m nock`.

The server listens on the address in NOCK_HOST and the port in NOCK_PORT, with
the limits of `nock.server.server_config`. The rooms are stored in the SQLite
file named by NOCK_DATABASE (spec 018). The three variables are checked before
the server is built, and a refused value stops the start (spec 036).
"""

from __future__ import annotations

import ipaddress
import os
import string
import unicodedata

import uvicorn

import nock.server

HOST_VARIABLE: str = "NOCK_HOST"
PORT_VARIABLE: str = "NOCK_PORT"
DATABASE_VARIABLE: str = nock.server.DATABASE_VARIABLE  # the app reads it (spec 018)
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8000
MIN_PORT: int = 1
MAX_PORT: int = 65535

# The characters of NOCK_HOST are explicit ASCII sets: str.isalnum() and
# str.isdigit() also accept the letters and digits of other scripts.
HOST_LETTERS: str = string.ascii_letters  # A to Z and a to z: host names are ASCII
HOST_DIGITS: str = string.digits  # 0 to 9 only, not the digits of other scripts
HOST_NAME_MARKS: str = ".-"  # the dot between the labels of a name, the dash in one
IPV6_MARK: str = ":"  # only an IPv6 address holds it, written without brackets
HOST_CHARACTERS: str = HOST_LETTERS + HOST_DIGITS + HOST_NAME_MARKS + IPV6_MARK
# The idna codec's limit on a label: uvicorn would end with a traceback past it.
MAX_LABEL_LENGTH: int = 63

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
    NOCK_PORT (default 8000), once NOCK_HOST, NOCK_PORT and NOCK_DATABASE have
    passed the checks below. The three variables are read at each call. An
    unset or empty NOCK_HOST or NOCK_PORT takes its default. An unset or empty
    NOCK_DATABASE is not checked, and the app then keeps its rooms in memory.

    The values each variable takes:

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

    Raises:
        SystemExit: A variable holds a refused value. Its code is a one-line
            message that names the variable and shows the value as `repr()`
            writes it, and no server is built.
    """
    host = _read_host()
    port = _read_port()
    _check_database()
    config = nock.server.server_config(nock.server.app, host=host, port=port)
    uvicorn.Server(config).run()


def _read_host() -> str:
    """Return the host in NOCK_HOST, or DEFAULT_HOST when it is unset or empty.

    Raises:
        SystemExit: NOCK_HOST is not a host name or an IP address.
    """
    host = os.environ.get(HOST_VARIABLE, "")
    if host == "":
        return DEFAULT_HOST
    if not _is_host(host):
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


def _is_host(text: str) -> bool:
    """Tell whether `text` is a host name or an IP address that NOCK_HOST takes.

    Every character is in HOST_CHARACTERS. A text that holds a colon is an IPv6
    address, and any other text is a name whose labels are valid. Whether a name
    resolves is not checked: uvicorn reports it.
    """
    for character in text:
        if character not in HOST_CHARACTERS:
            return False
    if IPV6_MARK in text:
        return _is_ipv6_address(text)
    return _has_valid_labels(text)


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


def _read_port() -> int:
    """Return the port in NOCK_PORT, or DEFAULT_PORT when it is unset or empty.

    Raises:
        SystemExit: NOCK_PORT is not ASCII digits for a number from 1 to 65535.
    """
    text = os.environ.get(PORT_VARIABLE, "")
    if text == "":
        return DEFAULT_PORT
    port = _port_number(text)
    if port is None:
        raise _refusal(
            PORT_VARIABLE,
            f"a whole number from {MIN_PORT} to {MAX_PORT}, "
            "written with the digits 0 to 9 only",
            text,
        )
    return port


def _port_number(text: str) -> int | None:
    """Return the port number written in `text`, or None when it is not one.

    A port number is written with the ASCII digits 0 to 9 only (leading zeros
    are allowed) and is from MIN_PORT to MAX_PORT.
    """
    if not text.isascii() or not text.isdigit():
        return None
    significant_digits = text.lstrip("0")
    if len(significant_digits) > len(str(MAX_PORT)):
        return None  # far too big, and int() refuses numbers of 4,300 digits
    if significant_digits == "":
        significant_digits = "0"  # all zeros: the number 0, below MIN_PORT
    # Convert without the leading zeros: int() also refuses 4,300 of them.
    port = int(significant_digits)
    if port < MIN_PORT or port > MAX_PORT:
        return None
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
