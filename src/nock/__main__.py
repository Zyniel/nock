"""Run the Nock server: `uv run python -m nock`.

The server listens on the address in NOCK_HOST and the port in NOCK_PORT, with
the limits of `nock.server.server_config`. The rooms are stored in the SQLite
file named by NOCK_DATABASE (spec 018).
"""

from __future__ import annotations

import os

import uvicorn

import nock.server

HOST_VARIABLE: str = "NOCK_HOST"
PORT_VARIABLE: str = "NOCK_PORT"
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8000
MIN_PORT: int = 1
MAX_PORT: int = 65535


def main() -> None:
    """Run `nock.server.app` with `server_config` until the server stops.

    The host is NOCK_HOST and the port is NOCK_PORT, read at each call. A
    variable that is unset or empty takes its default: 127.0.0.1 and 8000.
    The host is passed to uvicorn as given.

    Raises:
        SystemExit: NOCK_PORT is not a port number. Its message names the
            variable and its value, and no server is built.
    """
    host = os.environ.get(HOST_VARIABLE, "")
    if host == "":
        host = DEFAULT_HOST
    port = _read_port()
    config = nock.server.server_config(nock.server.app, host=host, port=port)
    uvicorn.Server(config).run()


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
        raise SystemExit(
            f"{PORT_VARIABLE} must be a whole number from {MIN_PORT} to {MAX_PORT}, "
            f'written with the digits 0 to 9 only, not "{text}"'
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


if __name__ == "__main__":
    main()
