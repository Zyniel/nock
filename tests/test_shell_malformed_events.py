"""Tests of `client/shell.md` AC-34 to AC-36: an event applies whole, a part of
the wrong shape skipped, and only an empty `wrong` list is a clean check (rule 4); a
frame that is not a text message with a `type` is dropped (rule 3).

Ana's page at 1280 by 720 on spec 043's mocked room, joined on FX-01 with Bob's `X`
at (1, 0) and `Y` at (1, 1), snapshot at seq 5. The mock sends Bob's grid check as
`check_result` 6 whose `wrong` is `[null, {"row": 1, "column": 0}, {"row": "1",
"column": 1}]` (the JSON of a valid `CheckResult` with that list put in): the page
takes seq 6, strikes (1, 0) (`data-wrong` true) and not (1, 1), and adds the
stream line « Bob a vérifié la grille ». Event 7, Bob's `V` at (2, 1), then gives
seq 7 and shows.

AC-35: on the same room, the mock sends Bob's check of the word MIME as `check_result`
6 whose `wrong` is `[null, {"row": "1", "column": 1}]`: no cell is struck, and its
stream line (« Bob a vérifié un mot ») is in `--nock-muted`, the look of a check that
found a wrong letter. With `wrong` `[]` the line is in green, the
look of a clean check (`specs/_design/room.md`, « Salon »).

AC-36: on the same room, the mock sends letter event 6 `W` at (2, 1) as a binary
frame (UTF-8 JSON), or the text frame `{"seq": 6}` with no `type`, then the text
letter event 7 `T` at (1, 0). The page buffers `T`: one pending, still at seq 5. The
text letter event 6 `V` at (2, 1) then gives seq 7 with nothing buffered, the page
still joined, (2, 1) showing `V` and (1, 0) `T`.

No fixed delay is waited. The page is read after a round trip (an `expect` on
`data-pending`) before `V` is sent, so a decoder of binary frames, synchronous or
reading a `Blob` (which always waits), has had the time to apply `W` at seq 6 first:
`T` then applies at once and nothing is pending, and the text `V` comes as a
duplicate, dropped, leaving `W` at (2, 1).
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget, WordTarget
from spec043_harness import (
    GREEN,
    MUTED,
    Rgb,
    RoomMock,
    cell_at,
    expect_colour,
    expect_seq,
    fr_format,
    fx01_view,
    letter_frame,
    open_room,
    players_up_to,
    snapshot_frame,
)

MALFORMED_WRONG: list[object] = [
    None,
    {"row": 1, "column": 0},
    {"row": "1", "column": 1},
]
X_AND_Y: list[tuple[int, int, dict[str, object]]] = [
    (1, 0, {"letter": "X", "author": "p2"}),
    (1, 1, {"letter": "Y", "author": "p2"}),
]


def malformed_check_frame() -> str:
    """Bob's grid check at seq 6, its `wrong` list holding two malformed cells."""
    result = CheckResult(
        seq=6, player_id="p2", target=GridTarget(), correct=(), wrong=()
    )
    event = result.model_dump(mode="json")
    event["wrong"] = MALFORMED_WRONG
    return json.dumps(event)


def test_ac34_a_check_result_with_malformed_cells_strikes_only_the_valid_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    frame = snapshot_frame(fx01_view(fx01_grid, X_AND_Y), players_up_to(3))
    mock = open_room(page, live_server, frame)

    mock.send(malformed_check_frame())

    expect_seq(page, 6)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-wrong", "true")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "false")
    check_lines = page.get_by_test_id("activity-feed").locator(
        '[data-testid="feed-item"][data-kind="check"]'
    )
    expect(check_lines).to_have_text([fr_format("feed.check.grid", name="Bob")])

    mock.send(letter_frame(7, 2, 1, "V", "p2"))

    expect_seq(page, 7)
    expect(cell_at(page, 2, 1)).to_have_attribute("data-letter", "V")


# ---- AC-35: only an empty wrong list is a clean check ------------------------------

MIME_TARGET = WordTarget(row=0, column=2, clue_index=0)


def word_check_frame(wrong: list[object]) -> str:
    """Bob's check of MIME at seq 6, its `wrong` list put in as given."""
    result = CheckResult(
        seq=6, player_id="p2", target=MIME_TARGET, correct=(), wrong=()
    )
    event = result.model_dump(mode="json")
    event["wrong"] = wrong
    return json.dumps(event)


@pytest.mark.parametrize(
    ("wrong", "line_colour"),
    [
        ([None, {"row": "1", "column": 1}], MUTED),
        ([], GREEN),
    ],
    ids=["entries all skipped", "empty list"],
)
def test_ac35_only_an_empty_wrong_list_gives_the_clean_check_look(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    wrong: list[object],
    line_colour: Rgb,
) -> None:
    frame = snapshot_frame(fx01_view(fx01_grid, X_AND_Y), players_up_to(3))
    mock = open_room(page, live_server, frame)

    mock.send(word_check_frame(wrong))

    expect_seq(page, 6)
    expect(page.locator('[data-testid="cell"][data-wrong="true"]')).to_have_count(0)
    line = page.locator('[data-testid="feed-item"][data-seq="6"]')
    expect(line).to_have_text(fr_format("feed.check.word", name="Bob"))
    expect_colour(line, "color", line_colour)


# ---- AC-36: a frame that is not a text message with a type is dropped ---------------

LETTER_ROW = 2
LETTER_COLUMN = 1
LETTER = "V"
BINARY_LETTER = "W"
LATER_ROW = 1
LATER_COLUMN = 0
LATER_LETTER = "T"


def _send_binary(mock: RoomMock, text: str) -> None:
    """Send a text as a binary frame on the newest mocked socket.

    Args:
        mock: The mocked room whose newest socket sends the frame.
        text: Text to send, encoded as UTF-8.
    """
    mock.routes[-1].send(text.encode("utf-8"))


def binary_letter_frame(mock: RoomMock) -> None:
    """Send letter event 6 as a binary frame holding its UTF-8 JSON."""
    _send_binary(mock, letter_frame(6, LETTER_ROW, LETTER_COLUMN, BINARY_LETTER, "p2"))


def typeless_frame(mock: RoomMock) -> None:
    """Send the text frame `{"seq": 6}`, which has no `type`."""
    mock.send(json.dumps({"seq": 6}))


@pytest.mark.parametrize(
    "send_dropped_frame",
    [binary_letter_frame, typeless_frame],
    ids=["binary frame", "text frame without type"],
)
def test_ac36_a_binary_or_typeless_frame_is_dropped_and_event_6_then_applies(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    send_dropped_frame: Callable[[RoomMock], None],
) -> None:
    frame = snapshot_frame(fx01_view(fx01_grid, X_AND_Y), players_up_to(3))
    mock = open_room(page, live_server, frame)
    room = page.get_by_test_id("room-page")

    send_dropped_frame(mock)
    mock.send(letter_frame(7, LATER_ROW, LATER_COLUMN, LATER_LETTER, "p2"))

    expect(room).to_have_attribute("data-pending", "1")
    expect_seq(page, 5)

    mock.send(letter_frame(6, LETTER_ROW, LETTER_COLUMN, LETTER, "p2"))

    expect_seq(page, 7)
    expect(room).to_have_attribute("data-pending", "0")
    expect(room).to_have_attribute("data-status", "joined")
    expect(cell_at(page, LETTER_ROW, LETTER_COLUMN)).to_have_attribute(
        "data-letter", LETTER
    )
    expect(cell_at(page, LATER_ROW, LATER_COLUMN)).to_have_attribute(
        "data-letter", LATER_LETTER
    )
