"""Tests of spec 008: letter entry (FX-01 with a mocked socket).

Keys: ASCII keys go through `page.keyboard.press`. Playwright cannot press a key
such as "é" (`keyboard.press` raises "Unknown key" and `keyboard.type` sends no
keydown at all, in Chromium and WebKit), so every non-ASCII key is dispatched as a
`keydown` KeyboardEvent with that `key` on the focused `grid` element. That works
the same in every engine.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Locator, Page, WebSocketRoute, expect

from nock.grid import Grid
from nock.protocol import (
    EditLetter,
    Erase,
    GridView,
    HelpMode,
    LetterCellView,
    RevealBudget,
    RoomSettings,
    SelectCell,
    Snapshot,
    grid_view,
    parse_client_message,
)

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 300

ACROSS_W1 = "0,0,0"
DOWN_W2 = "0,0,1"
ACROSS_W7 = "3,0,0"
ACROSS_W8 = "4,0,0"

ChangeList = list[tuple[int, int, dict[str, object]]]

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)
        route.on_message(self._record)

    def _record(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)

    def close(self, code: int) -> None:
        self.routes[0].close(code=code)


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def open_mock_room(page: Page, base_url: str) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket and wait for the page's join."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    wait_until(page, lambda: len(mock.received) > 0)
    return mock


def snapshot_frame(view: GridView, seq: int) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=(),
        settings=RoomSettings(
            help_mode=HelpMode.FREE,
            reveal_budget=RevealBudget(letters=5, words=1),
            locked=False,
        ),
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def with_letter_cells(view: GridView, changes: ChangeList) -> GridView:
    """Return `view` with the given letter cells replaced by updated copies."""
    new_cells = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, update in changes:
                if cell.row == row and cell.column == column:
                    new_cell = cell.model_copy(update=update)
        new_cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: ChangeList | None = None,
) -> MockRoomSocket:
    """Open a mocked room showing FX-01, with `changes` applied to its letters."""
    mock = open_mock_room(page, base_url)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    mock.send(snapshot_frame(view, 0))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", "0")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def tap(page: Page, row: int, column: int) -> None:
    cell_at(page, row, column).click()


def expect_selection(
    page: Page, row: int, column: int, direction: str, word: str
) -> None:
    """Wait until the grid shows exactly this selection."""
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)
    expect(grid).to_have_attribute("data-word", word)


def expect_letter(page: Page, row: int, column: int, letter: str) -> None:
    """Wait until the cell shows `letter` ("" for an empty cell)."""
    expect(cell_at(page, row, column)).to_have_attribute("data-letter", letter)


def expect_letters(page: Page, letters: dict[tuple[int, int], str]) -> None:
    for (row, column), letter in letters.items():
        expect_letter(page, row, column, letter)


def settle(page: Page) -> None:
    """Give the page time to send a message it should not send."""
    page.wait_for_timeout(SETTLE_MS)


def dispatch_key(
    page: Page,
    key: str,
    ctrl: bool = False,
    meta: bool = False,
    alt: bool = False,
    composing: bool = False,
) -> bool:
    """Dispatch a keydown on the grid; return True if it was NOT prevented."""
    script = (
        "([key, init]) => document.querySelector('[data-testid=\"grid\"]')"
        ".dispatchEvent(new KeyboardEvent('keydown',"
        " {key, bubbles: true, cancelable: true, ...init}))"
    )
    init = {
        "ctrlKey": ctrl,
        "metaKey": meta,
        "altKey": alt,
        "isComposing": composing,
    }
    return bool(page.evaluate(script, [key, init]))


def press(page: Page, key: str) -> None:
    """Press one key on the focused grid (see the module docstring)."""
    if key.isascii():
        page.keyboard.press(key)
    else:
        dispatch_key(page, key)


def press_all(page: Page, keys: list[str]) -> None:
    for key in keys:
        press(page, key)


def sent_messages(mock: MockRoomSocket) -> list[object]:
    """Every frame the page sent, parsed."""
    return [parse_client_message(frame) for frame in mock.received]


def sent_edits(mock: MockRoomSocket) -> list[EditLetter | Erase]:
    """The `edit_letter` and `erase` messages the page sent, in order."""
    edits: list[EditLetter | Erase] = []
    for message in sent_messages(mock):
        if isinstance(message, EditLetter | Erase):
            edits.append(message)
    return edits


def sent_selections(mock: MockRoomSocket) -> list[SelectCell]:
    """The `select_cell` messages the page sent, in order."""
    selections: list[SelectCell] = []
    for message in sent_messages(mock):
        if isinstance(message, SelectCell):
            selections.append(message)
    return selections


def across(row: int, column: int) -> SelectCell:
    return SelectCell(row=row, column=column, direction="across")


def down(row: int, column: int) -> SelectCell:
    return SelectCell(row=row, column=column, direction="down")


def put(row: int, column: int, letter: str) -> EditLetter:
    return EditLetter(row=row, column=column, letter=letter)


def rub(row: int, column: int) -> Erase:
    return Erase(row=row, column=column)


def expect_edits(
    page: Page, mock: MockRoomSocket, expected: list[EditLetter | Erase]
) -> None:
    """Wait for the expected edits, give time for extra ones, then compare."""
    if expected:
        wait_until(page, lambda: len(sent_edits(mock)) >= len(expected))
    settle(page)
    assert sent_edits(mock) == expected


# ---- AC-1: typing fills the cell and moves along the word --------------------


def test_ac1_typing_fills_the_word_and_stays_on_its_last_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    press(page, "t")

    expect_letter(page, 1, 0, "T")
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 0, "T")])

    press_all(page, ["a", "m", "i", "s"])

    expect_letters(
        page, {(1, 0): "T", (1, 1): "A", (1, 2): "M", (1, 3): "I", (1, 4): "S"}
    )
    expect_selection(page, 1, 4, "across", ACROSS_W1)

    press(page, "x")

    expect_letter(page, 1, 4, "X")
    expect_selection(page, 1, 4, "across", ACROSS_W1)
    expect_letters(page, {(1, 0): "T", (1, 1): "A", (1, 2): "M", (1, 3): "I"})
    expect_edits(
        page,
        mock,
        [
            put(1, 0, "T"),
            put(1, 1, "A"),
            put(1, 2, "M"),
            put(1, 3, "I"),
            put(1, 4, "S"),
            put(1, 4, "X"),
        ],
    )
    # One select_cell per selection change, none when the cursor stays.
    assert sent_selections(mock) == [
        across(1, 0),
        across(1, 1),
        across(1, 2),
        across(1, 3),
        across(1, 4),
    ]


def test_ac1_the_edit_letter_frame_has_a_null_base_seq_and_an_upper_case_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    press(page, "t")

    wait_until(page, lambda: len(sent_edits(mock)) == 1)
    edit_frames = []
    for frame in mock.received:
        if json.loads(frame)["type"] == "edit_letter":
            edit_frames.append(json.loads(frame))
    assert edit_frames == [
        {
            "type": "edit_letter",
            "row": 1,
            "column": 0,
            "letter": "T",
            "base_seq": None,
        }
    ]


def test_ac1_the_direction_is_kept_when_typing_down_a_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", DOWN_W2)

    press(page, "x")

    expect_letter(page, 1, 1, "X")
    expect_selection(page, 2, 1, "down", DOWN_W2)

    press_all(page, ["v", "a", "l"])

    expect_letters(page, {(2, 1): "V", (3, 1): "A", (4, 1): "L"})
    expect_selection(page, 4, 1, "down", DOWN_W2)

    press(page, "z")

    expect_letter(page, 4, 1, "Z")
    expect_selection(page, 4, 1, "down", DOWN_W2)
    expect_letters(page, {(1, 1): "X", (2, 1): "V", (3, 1): "A"})
    expect_edits(
        page,
        mock,
        [
            put(1, 1, "X"),
            put(2, 1, "V"),
            put(3, 1, "A"),
            put(4, 1, "L"),
            put(4, 1, "Z"),
        ],
    )
    assert sent_selections(mock) == [
        across(1, 1),
        down(1, 1),
        down(2, 1),
        down(3, 1),
        down(4, 1),
    ]


def test_ac1_typing_the_letter_already_there_sends_nothing_and_moves_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [(1, 0, {"letter": "T"}), (1, 1, {"letter": "A"})],
    )
    tap(page, 1, 0)

    press(page, "t")

    expect_letter(page, 1, 0, "T")
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_edits(page, mock, [])

    press(page, "a")

    expect_letter(page, 1, 1, "A")
    expect_selection(page, 1, 2, "across", ACROSS_W1)
    expect_edits(page, mock, [])

    press(page, "m")

    expect_letter(page, 1, 2, "M")
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 2, "M")])
    assert sent_selections(mock) == [
        across(1, 0),
        across(1, 1),
        across(1, 2),
        across(1, 3),
    ]


def test_ac1_the_cursor_stays_when_every_later_cell_is_locked(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [
            (1, 3, {"letter": "I", "locked": True}),
            (1, 4, {"letter": "S", "locked": True}),
        ],
    )
    tap(page, 1, 2)

    press(page, "m")

    expect_letter(page, 1, 2, "M")
    expect_selection(page, 1, 2, "across", ACROSS_W1)
    expect_letters(page, {(1, 3): "I", (1, 4): "S"})
    expect_edits(page, mock, [put(1, 2, "M")])
    assert sent_selections(mock) == [across(1, 2)]


def test_ac1_keys_do_nothing_without_a_selection_or_with_the_focus_elsewhere(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    grid = page.get_by_test_id("grid")
    grid.focus()

    press(page, "a")
    # Not pressed for real: with nothing handling it, WebKit goes back in history.
    dispatch_key(page, "Backspace")

    settle(page)
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(page.locator('[data-testid="cell"][data-letter="A"]')).to_have_count(0)
    assert len(mock.received) == 1

    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    page.evaluate(
        "() => { const input = document.createElement('input');"
        " input.id = 'other-input'; document.body.append(input); }"
    )
    page.locator("#other-input").focus()
    expect(page.locator("#other-input")).to_be_focused()

    press_all(page, ["b", "c"])

    expect(page.locator("#other-input")).to_have_value("bc")
    page.evaluate("() => document.activeElement.blur()")
    press(page, "d")
    settle(page)
    expect_letter(page, 1, 0, "")
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_edits(mock) == []
    assert sent_selections(mock) == [across(1, 0)]


def test_ac1_after_the_socket_closes_cells_change_locally_and_nothing_is_sent(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    mock.close(1011)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "closed")
    sent_before = len(mock.received)

    tap(page, 1, 0)
    press_all(page, ["t", "a"])

    expect_letters(page, {(1, 0): "T", (1, 1): "A"})
    expect_selection(page, 1, 2, "across", ACROSS_W1)
    settle(page)
    assert len(mock.received) == sent_before
    assert page_errors == []


# ---- AC-2: accents fold, other keys are ignored ------------------------------


def test_ac2_accented_letters_enter_the_letter_without_accent(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    press_all(page, ["é", "à", "ç"])

    expect_letters(page, {(1, 0): "E", (1, 1): "A", (1, 2): "C"})
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 0, "E"), put(1, 1, "A"), put(1, 2, "C")])


def test_ac2_other_french_accents_and_capitals_fold_to_one_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    # e grave, e circumflex, e diaeresis, E acute, i circumflex
    press_all(page, ["è", "ê", "ë", "É", "î"])

    expect_letters(
        page, {(1, 0): "E", (1, 1): "E", (1, 2): "E", (1, 3): "E", (1, 4): "I"}
    )
    tap(page, 3, 1)
    # a circumflex, i diaeresis, o circumflex, u grave
    press_all(page, ["â", "ï", "ô", "ù"])
    expect_letters(page, {(3, 1): "A", (3, 2): "I", (3, 3): "O", (3, 4): "U"})
    tap(page, 4, 1)
    # u circumflex, u diaeresis, C cedilla, A grave
    press_all(page, ["û", "ü", "Ç", "À"])
    expect_letters(page, {(4, 1): "U", (4, 2): "U", (4, 3): "C", (4, 4): "A"})
    expected: list[EditLetter | Erase] = [
        put(1, 0, "E"),
        put(1, 1, "E"),
        put(1, 2, "E"),
        put(1, 3, "E"),
        put(1, 4, "I"),
        put(3, 1, "A"),
        put(3, 2, "I"),
        put(3, 3, "O"),
        put(3, 4, "U"),
        put(4, 1, "U"),
        put(4, 2, "U"),
        put(4, 3, "C"),
        put(4, 4, "A"),
    ]
    expect_edits(page, mock, expected)


def test_ac2_digits_space_and_punctuation_are_ignored(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    press_all(page, ["é", "à", "ç"])
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 0, "E"), put(1, 1, "A"), put(1, 2, "C")])
    frames_before = len(mock.received)

    press_all(page, ["1", "Space", ".", "-", "'", "?"])

    settle(page)
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_letters(
        page, {(1, 0): "E", (1, 1): "A", (1, 2): "C", (1, 3): "", (1, 4): ""}
    )
    assert len(mock.received) == frames_before


def test_ac2_ligatures_and_other_letters_that_do_not_fold_are_ignored(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    frames_before = len(mock.received)

    # oe ligature, ae ligature, sharp s, o with stroke, then named keys
    press_all(page, ["œ", "æ", "ß", "ø"])
    dispatch_key(page, "Dead")
    dispatch_key(page, "F2")
    dispatch_key(page, "Enter")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect(page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(18)
    assert len(mock.received) == frames_before


def test_ac2_shift_a_gives_a_capital_a(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    page.keyboard.press("Shift+A")

    expect_letter(page, 1, 0, "A")
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 0, "A")])


def test_ac2_modifier_combinations_are_left_to_the_browser(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    page.keyboard.press("Control+a")
    page.keyboard.press("Meta+r")
    page.keyboard.press("Alt+e")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect(page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(18)
    assert dispatch_key(page, "a", ctrl=True) is True
    assert dispatch_key(page, "r", meta=True) is True
    assert dispatch_key(page, "e", alt=True) is True
    assert dispatch_key(page, "a", composing=True) is True
    settle(page)
    expect(page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(18)
    assert sent_edits(mock) == []
    assert sent_selections(mock) == [across(1, 0)]


def test_ac2_handled_keys_are_prevented_and_ignored_keys_are_not(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    assert dispatch_key(page, "q") is False
    assert dispatch_key(page, "é") is False
    assert dispatch_key(page, "Backspace") is False
    assert dispatch_key(page, "1") is True
    assert dispatch_key(page, "œ") is True


# ---- AC-3: Backspace clears, then moves back ---------------------------------


def test_ac3_backspace_clears_the_cell_then_moves_back_and_clears(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [(1, 0, {"letter": "T"}), (1, 1, {"letter": "A"})],
    )
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    press(page, "Backspace")

    expect_letter(page, 1, 1, "")
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_letter(page, 1, 0, "T")
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letter(page, 1, 0, "")
    expect_edits(page, mock, [rub(1, 1), rub(1, 0)])

    # First cell of the word and empty: nothing changes, nothing is sent.
    assert dispatch_key(page, "Backspace") is False
    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letters(page, {(1, 0): "", (1, 1): ""})
    expect_edits(page, mock, [rub(1, 1), rub(1, 0)])
    assert sent_selections(mock) == [across(1, 1), across(1, 0)]


def test_ac3_the_erase_frame_has_a_null_base_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(1, 1, {"letter": "A"})])
    tap(page, 1, 1)

    press(page, "Backspace")

    wait_until(page, lambda: len(sent_edits(mock)) == 1)
    erase_frames = []
    for frame in mock.received:
        if json.loads(frame)["type"] == "erase":
            erase_frames.append(json.loads(frame))
    assert erase_frames == [{"type": "erase", "row": 1, "column": 1, "base_seq": None}]


def test_ac3_backspace_on_an_empty_cell_moves_back_without_sending_for_an_empty_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(1, 1, {"letter": "A"})])
    tap(page, 1, 2)

    press(page, "Backspace")

    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_letter(page, 1, 1, "")
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_edits(page, mock, [rub(1, 1)])
    assert sent_selections(mock) == [across(1, 2), across(1, 1), across(1, 0)]


def test_ac3_backspace_moves_back_along_a_down_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(0, 1, {"letter": "N"})])
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", DOWN_W2)

    press(page, "Backspace")

    expect_selection(page, 0, 1, "down", DOWN_W2)
    expect_letter(page, 0, 1, "")
    expect_edits(page, mock, [rub(0, 1)])


def test_ac3_backspace_on_a_locked_cell_moves_back_and_never_clears_a_locked_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [
            (1, 0, {"letter": "T", "locked": True}),
            (1, 1, {"letter": "A"}),
            (1, 2, {"letter": "M", "locked": True}),
        ],
    )
    tap(page, 1, 2)
    expect_selection(page, 1, 2, "across", ACROSS_W1)

    press(page, "Backspace")

    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_letters(page, {(1, 1): "", (1, 2): "M", (1, 0): "T"})
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letters(page, {(1, 0): "T", (1, 2): "M"})
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letter(page, 1, 0, "T")
    expect_edits(page, mock, [rub(1, 1)])
    assert sent_selections(mock) == [across(1, 2), across(1, 1), across(1, 0)]


# ---- AC-4: typing over a letter, unless the cell is locked -------------------


def test_ac4_typing_replaces_a_letter_and_skips_over_a_locked_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [
            (1, 1, {"letter": "A", "author": "p2"}),
            (1, 2, {"letter": "M", "locked": True}),
        ],
    )
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    press(page, "e")

    expect_letter(page, 1, 1, "E")
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_letter(page, 1, 2, "M")
    expect_edits(page, mock, [put(1, 1, "E")])
    assert sent_selections(mock) == [across(1, 1), across(1, 3)]


def test_ac4_typing_on_a_locked_cell_changes_nothing_sends_nothing_and_stays(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [
            (1, 1, {"letter": "A", "author": "p2"}),
            (1, 2, {"letter": "M", "locked": True}),
        ],
    )
    tap(page, 1, 2)
    expect_selection(page, 1, 2, "across", ACROSS_W1)

    press(page, "x")
    press(page, "m")

    settle(page)
    expect_letter(page, 1, 2, "M")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")
    expect_selection(page, 1, 2, "across", ACROSS_W1)
    expect_edits(page, mock, [])
    assert sent_selections(mock) == [across(1, 2)]


def test_ac4_a_snapshot_lock_on_a_first_cell_blocks_typing_there(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [(1, 0, {"letter": "T", "locked": True})],
    )
    tap(page, 1, 0)

    press(page, "z")

    settle(page)
    expect_letter(page, 1, 0, "T")
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letter(page, 1, 1, "")
    expect_edits(page, mock, [])
