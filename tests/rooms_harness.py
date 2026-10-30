"""Shared setup of the tests of lobby/rooms about the creation limit (AC-13 to AC-17).

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_rooms_*.py`:

- `test_rooms_creation_limit.py`: AC-13 to AC-15, the limit over HTTP with the app of
  `host_harness` (a fake clock, the rooms' store on a file, one client address for
  `app.client` and another one for `other_address_client`).
- `test_rooms_limit_variable.py`: AC-16 and AC-17, the variable
  `NOCK_ROOMS_PER_ADDRESS_PER_HOUR` read by an app that builds its own registry,
  by `main()` and by `python -m nock`.

The limit is counted on the registry's clock, so the tests of the hour give the
registry the fake clock. An app that is given a registry may or may not read the
variable, so the tests of AC-16 and AC-17 give the app none.

Every test of these files clears the variables an app reads at its start first
(`lifetime_harness.variables_of`), so that a value left in the shell changes
nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import uvicorn
from fastapi.testclient import TestClient
from httpx2 import Response

from host_harness import HostApp
from lifetime_harness import STARTUP_VARIABLES, variables_of

LIMIT_VARIABLE = "NOCK_ROOMS_PER_ADDRESS_PER_HOUR"
DEFAULT_LIMIT = 30
HOUR = 3_600.0
TOO_MANY_REQUESTS = {"detail": "Too Many Requests"}
OTHER_ADDRESS = "10.0.0.2"
GRID_NUMBER = 1  # the number of the grid of `spec024_harness.make_catalogue`
UNKNOWN_GRID_NUMBER = 99
PROCESS_EXIT_LIMIT_SECONDS = 30.0


def post_room(client: TestClient, body: object | None = None) -> Response:
    """`POST /api/rooms` for the catalogue's grid, or with this JSON `body`."""
    if body is None:
        body = {"grid_number": GRID_NUMBER}
    return client.post("/api/rooms", json=body)


def post_rooms(client: TestClient, count: int) -> list[int]:
    """The status of `count` creations of a room, one after the other."""
    statuses: list[int] = []
    for _ in range(count):
        statuses.append(post_room(client).status_code)
    return statuses


def other_address_client(app: HostApp) -> TestClient:
    """A client of the same running app that comes from another address.

    It is not entered as a context: the app is already started by `host_app`.
    """
    return TestClient(app.client.app, client=(OTHER_ADDRESS, 50000))


def room_count(app: HostApp) -> int:
    """How many rooms the store holds."""
    return len(app.store.read_room_times())


def record_server_runs(monkeypatch: pytest.MonkeyPatch) -> list[uvicorn.Config]:
    """Replace `uvicorn.Server.run` by a recorder; return the configs it recorded.

    `main()` hands uvicorn a server: the recorder keeps its config and serves
    nothing, so a `main()` that does not refuse a value leaves a record.
    """
    configs: list[uvicorn.Config] = []

    def record_run(server: uvicorn.Server, sockets: list[object] | None = None) -> None:
        configs.append(server.config)

    monkeypatch.setattr(uvicorn.Server, "run", record_run)
    return configs


def refusal_of_main(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    variables: dict[str, str],
) -> str:
    """Call `main()` under only `variables`; return the message it stops with."""
    variables_of(monkeypatch, variables)
    from nock.__main__ import main

    with pytest.raises(SystemExit) as caught:
        main()

    message = caught.value.code
    assert isinstance(message, str), f"the SystemExit code {message!r} is no message"
    assert server_runs == [], "main() served after a refused value"
    return message


def run_python_m_nock(variables: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run `python -m nock` under only `variables` (and the rest of the environment).

    The process is expected to stop on its own; the test fails when it still runs
    after `PROCESS_EXIT_LIMIT_SECONDS`.
    """
    environment = dict(os.environ)
    for name in STARTUP_VARIABLES:
        environment.pop(name, None)
    environment.update(variables)
    try:
        return subprocess.run(
            [sys.executable, "-m", "nock"],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROCESS_EXIT_LIMIT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"python -m nock with {variables} still ran after "
            f"{PROCESS_EXIT_LIMIT_SECONDS:.0f} s"
        )
