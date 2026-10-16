"""Shared setup of the spec 036 tests: what files of different themes share.

The setup of the `tests/test_spec_036_*.py` files is split by theme over four
modules. Their names match none of pytest's `python_files` patterns, so pytest does
not collect them; each test file imports the names it uses. A fixture defined in
one of them is imported by name in every test file that uses it, because pytest
looks for the fixtures of a test among the names of the test module.

- `spec036_harness` (this module): the `fx01_grid` fixture, the waiting times,
  `triples` and the names of the variables of `python -m nock`, which test files
  of different themes use.
- `spec036_browser_harness`: the room page in a browser (the phone profile, the
  in-page timing, the page actions) and the mocked room socket. AC-1 to AC-4 use
  the page; AC-1, AC-5 and AC-6 use the mocked socket.
- `spec036_hub_harness`: the hub scenarios, with fake sockets (AC-5 and AC-6).
- `spec036_frames_harness`: the frames sent at a real socket (AC-7 and AC-9).

A name that only one test file uses is defined in that file, unless that would make
the file too long: the browser and hub code above is kept apart for that reason.

"The harness" in the comments of these files is the "Test harness" section of
the spec; these modules are its Python code, with the helpers of the tests.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from nock.grid import Grid
from nock.protocol import EditLetter, LetterChanged

# ---- Values of the spec --------------------------------------------------------------

# The variables that `python -m nock` reads (AC-8 to AC-12); NOCK_DATABASE is spec
# 018's. `main()` also reads spec 038's NOCK_OPERATOR_TOKEN, first: no case of this
# spec sets it, and each one deletes it, so that a value left in the environment
# that runs the tests cannot stop a case (spec 036's "Test harness", refined for
# spec 038).
HOST_VARIABLE = "NOCK_HOST"
PORT_VARIABLE = "NOCK_PORT"
DATABASE_VARIABLE = "NOCK_DATABASE"
OPERATOR_TOKEN_VARIABLE = "NOCK_OPERATOR_TOKEN"


# ---- Values of the test harness ------------------------------------------------------

WAIT_SECONDS = 10.0
POLL_SECONDS = 0.01


# ---- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


# ---- Messages ------------------------------------------------------------------------


def triples(edits: Sequence[EditLetter | LetterChanged]) -> list[tuple[int, int, str]]:
    """The (row, column, letter) of each edit or letter_changed."""
    found: list[tuple[int, int, str]] = []
    for edit in edits:
        assert edit.letter is not None, edit
        found.append((edit.row, edit.column, edit.letter))
    return found
