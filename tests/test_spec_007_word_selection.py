"""Tests of spec 007: word selection and direction (FX-01 with a mocked socket)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import (
    Browser,
    FloatRect,
    Locator,
    Page,
    WebSocketRoute,
    expect,
)

from nock.grid import Arrow, Grid
from nock.protocol import (
    ClueCellView,
    ClueView,
    EmptyCellView,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    RevealBudget,
    RoomSettings,
    SelectCell,
    Snapshot,
    grid_view,
    parse_client_message,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 300
MIN_BAR_FONT_SIZE_PX = 14.0
FX01_LETTER_CELL_COUNT = 18

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def phone_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A 360 by 640 phone page (no is_mobile under Firefox)."""
    if browser_name == "firefox":
        context = browser.new_context(
            viewport={"width": 360, "height": 640},
            has_touch=True,
            device_scale_factor=2,
        )
    else:
        context = browser.new_context(
            viewport={"width": 360, "height": 640},
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    try:
        yield context.new_page()
    finally:
        context.close()


@pytest.fixture
def touch_page(browser: Browser) -> Iterator[Page]:
    """A page in a touch context, for locator.tap()."""
    context = browser.new_context(has_touch=True)
    try:
        yield context.new_page()
    finally:
        context.close()


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def clue_named(page: Page, text: str) -> Locator:
    """The `clue` element whose text is exactly `text`."""
    clue_text = page.get_by_test_id("clue-text").get_by_text(text, exact=True)
    return page.get_by_test_id("clue").filter(has=clue_text)


def box_of(locator: Locator) -> FloatRect:
    box = locator.bounding_box()
    assert box is not None, "the element has no box on screen"
    return box


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


def with_letter_cells(
    view: GridView, changes: list[tuple[int, int, dict[str, object]]]
) -> GridView:
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


def show_snapshot(page: Page, mock: MockRoomSocket, view: GridView, seq: int) -> None:
    """Send a snapshot and wait until the room page shows its `seq`."""
    mock.send(snapshot_frame(view, seq))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", str(seq))


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: list[tuple[int, int, dict[str, object]]] | None = None,
) -> MockRoomSocket:
    """Open a mocked room showing FX-01, with `changes` applied to its letters."""
    mock = open_mock_room(page, base_url)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    show_snapshot(page, mock, view, 0)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def note_view() -> GridView:
    """The 3 by 1 grid of the spec: clue "Note", an empty letter cell, empty."""
    clue_cell = ClueCellView(
        row=0,
        column=0,
        clues=(ClueView(text="Note", arrow=Arrow.RIGHT),),
    )
    letter_cell = LetterCellView(
        row=0,
        column=1,
        letter=None,
        pencil=False,
        author=None,
        locked=False,
        revealed=False,
        wrong=False,
    )
    empty_cell = EmptyCellView(row=0, column=2)
    return GridView(width=3, height=1, cells=(clue_cell, letter_cell, empty_cell))


def letter_cell_view(row: int, column: int) -> LetterCellView:
    """An empty letter cell."""
    return LetterCellView(
        row=row,
        column=column,
        letter=None,
        pencil=False,
        author=None,
        locked=False,
        revealed=False,
        wrong=False,
    )


def nested_run_view() -> GridView:
    """A 2 by 4 grid whose column 1 holds two down words ending on the same cell.

    "Long" starts at (0, 1) and runs to (3, 1). "Court" starts at (1, 1), in the
    middle of that run, and ends on the same cell.
    """
    long_clue_cell = ClueCellView(
        row=0,
        column=0,
        clues=(ClueView(text="Long", arrow=Arrow.RIGHT_THEN_DOWN),),
    )
    short_clue_cell = ClueCellView(
        row=1,
        column=0,
        clues=(ClueView(text="Court", arrow=Arrow.RIGHT_THEN_DOWN),),
    )
    cells = (
        long_clue_cell,
        letter_cell_view(0, 1),
        short_clue_cell,
        letter_cell_view(1, 1),
        EmptyCellView(row=2, column=0),
        letter_cell_view(2, 1),
        EmptyCellView(row=3, column=0),
        letter_cell_view(3, 1),
    )
    return GridView(width=2, height=4, cells=cells)


LONG_WORD_CELLS = [(0, 1), (1, 1), (2, 1), (3, 1)]
SHORT_WORD_CELLS = [(1, 1), (2, 1), (3, 1)]


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


def expect_nothing_selected(page: Page) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(grid).to_have_attribute("data-selected-column", "")
    expect(grid).to_have_attribute("data-direction", "")
    expect(grid).to_have_attribute("data-word", "")


def positions_with(page: Page, attribute: str) -> list[tuple[int, int]]:
    """Positions of the letter cells whose `attribute` is "true", sorted."""
    script = (
        "attribute => Array.from(document.querySelectorAll("
        '\'[data-testid="cell"][data-type="letter"]\'))'
        ".filter(e => e.getAttribute(attribute) === 'true')"
        ".map(e => [Number(e.dataset.row), Number(e.dataset.column)])"
    )
    found = page.evaluate(script, attribute)
    positions = [(row, column) for row, column in found]
    return sorted(positions)


def active_clue_texts(page: Page) -> list[str]:
    script = (
        "() => Array.from(document.querySelectorAll('[data-testid=\"clue\"]'))"
        ".filter(e => e.getAttribute('data-active') === 'true')"
        ".map(e => e.querySelector('[data-testid=\"clue-text\"]').textContent)"
    )
    return page.evaluate(script)


def background_of(locator: Locator) -> str:
    return locator.evaluate("element => getComputedStyle(element).backgroundColor")


def sent_messages(mock: MockRoomSocket) -> list[object]:
    """Every frame the page sent, parsed."""
    return [parse_client_message(frame) for frame in mock.received]


def sent_selections(mock: MockRoomSocket) -> list[SelectCell]:
    """The `select_cell` messages the page sent, in order."""
    selections: list[SelectCell] = []
    for message in sent_messages(mock):
        if isinstance(message, SelectCell):
            selections.append(message)
    return selections


def select_cell_message(row: int, column: int, direction: str) -> SelectCell:
    return SelectCell(row=row, column=column, direction=direction)


def settle(page: Page) -> None:
    """Give the page time to send a message it should not send."""
    page.wait_for_timeout(SETTLE_MS)


# ---- AC-1: tapping a letter cell selects it and highlights its word ----------


def test_ac1_nothing_is_selected_at_start(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    expect_nothing_selected(page)
    assert positions_with(page, "data-selected") == []
    assert positions_with(page, "data-in-word") == []
    assert active_clue_texts(page) == []
    expect(page.locator('[data-testid="cell"][data-selected="false"]')).to_have_count(
        FX01_LETTER_CELL_COUNT
    )
    assert sent_selections(mock) == []


def test_ac1_tapping_a_letter_cell_selects_its_across_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 2, 2)

    expect_selection(page, 2, 2, "across", "2,0,0")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-selected", "true")
    assert positions_with(page, "data-selected") == [(2, 2)]
    assert positions_with(page, "data-in-word") == [(2, 1), (2, 2), (2, 3), (2, 4)]
    expect(page.locator('[data-testid="cell"][data-in-word="false"]')).to_have_count(
        FX01_LETTER_CELL_COUNT - 4
    )
    assert active_clue_texts(page) == ["Sans contenu"]


def test_ac1_selected_word_other_cells_and_outside_cells_have_three_colours(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 2, 2)

    expect_selection(page, 2, 2, "across", "2,0,0")
    selected = background_of(cell_at(page, 2, 2))
    in_word = background_of(cell_at(page, 2, 3))
    other_in_word = background_of(cell_at(page, 2, 1))
    outside = background_of(cell_at(page, 3, 3))
    assert in_word == other_in_word
    assert len({selected, in_word, outside}) == 3


def test_ac1_active_clue_has_another_background_than_an_inactive_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    inactive_before = background_of(clue_named(page, "Sans contenu"))

    tap(page, 2, 2)

    expect(clue_named(page, "Sans contenu")).to_have_attribute("data-active", "true")
    active = background_of(clue_named(page, "Sans contenu"))
    inactive = background_of(clue_named(page, "Fin de prière"))
    assert active != inactive
    assert active != inactive_before
    expect(clue_named(page, "Fin de prière")).to_have_attribute("data-active", "false")


def test_ac1_a_touch_tap_selects_the_cell(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)

    cell_at(touch_page, 2, 2).tap()

    expect_selection(touch_page, 2, 2, "across", "2,0,0")
    assert positions_with(touch_page, "data-in-word") == [
        (2, 1),
        (2, 2),
        (2, 3),
        (2, 4),
    ]


def test_ac1_first_tap_on_a_cell_with_only_a_down_word_selects_down(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 0, 1)

    expect_selection(page, 0, 1, "down", "0,0,1")
    assert positions_with(page, "data-in-word") == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
    ]
    assert positions_with(page, "data-selected") == [(0, 1)]
    assert active_clue_texts(page) == ["De la marine"]


def test_ac1_first_tap_on_a_cell_with_only_an_across_word_selects_across(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 1, 0)

    expect_selection(page, 1, 0, "across", "0,0,0")
    assert positions_with(page, "data-in-word") == [
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
    ]
    assert active_clue_texts(page) == ["Passoire fine"]


def test_ac1_the_current_direction_is_kept_on_a_cell_with_a_word_in_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")

    tap(page, 2, 2)
    expect_selection(page, 2, 2, "down", "0,2,0")
    assert active_clue_texts(page) == ["Artiste muet"]
    assert positions_with(page, "data-in-word") == [(1, 2), (2, 2), (3, 2), (4, 2)]

    tap(page, 2, 1)
    expect_selection(page, 2, 1, "down", "0,0,1")
    assert active_clue_texts(page) == ["De la marine"]


def test_ac1_across_is_kept_when_it_is_the_current_direction(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")

    tap(page, 1, 1)

    expect_selection(page, 1, 1, "across", "0,0,0")


def test_ac1_the_direction_is_forced_when_the_cell_has_no_word_in_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")

    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", "0,0,0")

    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", "0,0,1")


def test_ac1_selecting_a_cell_gives_keyboard_focus_to_the_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("tabindex", "0")

    tap(page, 2, 2)

    expect_selection(page, 2, 2, "across", "2,0,0")
    expect(grid).to_be_focused()


def test_ac1_locked_cells_are_selectable(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(
        page,
        live_server,
        fx01_grid,
        [(2, 2, {"letter": "I", "locked": True})],
    )

    tap(page, 2, 2)

    expect_selection(page, 2, 2, "across", "2,0,0")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-selected", "true")


def test_ac1_tapping_an_empty_cell_changes_nothing_and_sends_nothing(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    show_snapshot(page, mock, note_view(), 0)
    expect(page.get_by_test_id("cell")).to_have_count(3)

    cell_at(page, 0, 2).click()
    settle(page)
    expect_nothing_selected(page)
    assert sent_selections(mock) == []

    cell_at(page, 0, 1).click()
    expect_selection(page, 0, 1, "across", "0,0,0")
    cell_at(page, 0, 2).click()
    settle(page)
    expect_selection(page, 0, 1, "across", "0,0,0")
    assert sent_selections(mock) == [select_cell_message(0, 1, "across")]


def test_ac1_tapping_the_only_word_cell_again_changes_nothing(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    show_snapshot(page, mock, note_view(), 0)

    cell_at(page, 0, 1).click()
    expect_selection(page, 0, 1, "across", "0,0,0")
    cell_at(page, 0, 1).click()
    settle(page)

    expect_selection(page, 0, 1, "across", "0,0,0")
    assert sent_selections(mock) == [select_cell_message(0, 1, "across")]


def test_ac1_tapping_a_clue_separator_changes_nothing_and_sends_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    separator = cell_at(page, 0, 0).get_by_test_id("clue-separator")

    separator.dispatch_event("click")
    settle(page)
    expect_nothing_selected(page)

    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")
    separator.dispatch_event("click")
    settle(page)

    expect_selection(page, 2, 2, "across", "2,0,0")
    assert positions_with(page, "data-in-word") == [(2, 1), (2, 2), (2, 3), (2, 4)]
    assert sent_selections(mock) == [select_cell_message(2, 2, "across")]


def test_ac1_tapping_outside_the_grid_changes_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")

    page.mouse.click(2, 2)
    page.get_by_test_id("clue-bar").click()
    settle(page)

    expect_selection(page, 2, 2, "across", "2,0,0")
    assert sent_selections(mock) == [select_cell_message(2, 2, "across")]


def test_ac1_a_second_snapshot_keeps_a_selection_that_still_has_a_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")
    next_view = with_letter_cells(
        grid_view(fx01_grid), [(1, 1, {"letter": "A"}), (2, 2, {"letter": "I"})]
    )

    show_snapshot(page, mock, next_view, 1)
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    settle(page)

    expect_selection(page, 1, 1, "down", "0,0,1")
    assert positions_with(page, "data-in-word") == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
    ]
    assert active_clue_texts(page) == ["De la marine"]
    assert len(sent_selections(mock)) == 2


def test_ac1_a_second_snapshot_clears_a_selection_without_a_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", "0,0,1")

    show_snapshot(page, mock, note_view(), 1)
    settle(page)

    expect_nothing_selected(page)
    assert positions_with(page, "data-selected") == []
    assert positions_with(page, "data-in-word") == []
    assert sent_selections(mock) == [select_cell_message(0, 1, "down")]


# ---- AC-2: tapping the selected cell switches direction ----------------------


def test_ac2_tapping_the_selected_cell_switches_between_its_two_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", "0,0,0")
    assert positions_with(page, "data-in-word") == [
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
    ]
    assert active_clue_texts(page) == ["Passoire fine"]

    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")
    assert positions_with(page, "data-in-word") == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
    ]
    assert positions_with(page, "data-selected") == [(1, 1)]
    assert active_clue_texts(page) == ["De la marine"]

    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", "0,0,0")
    assert active_clue_texts(page) == ["Passoire fine"]


def test_ac2_tapping_a_cell_with_a_down_word_only_leaves_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", "0,0,1")
    tap(page, 0, 1)
    settle(page)

    expect_selection(page, 0, 1, "down", "0,0,1")
    assert active_clue_texts(page) == ["De la marine"]
    assert positions_with(page, "data-selected") == [(0, 1)]


def test_ac2_tapping_a_cell_with_an_across_word_only_leaves_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", "0,0,0")
    tap(page, 1, 0)
    settle(page)

    expect_selection(page, 1, 0, "across", "0,0,0")
    assert active_clue_texts(page) == ["Passoire fine"]
    assert positions_with(page, "data-selected") == [(1, 0)]


def test_ac2_switching_works_on_another_two_word_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")
    tap(page, 2, 2)

    expect_selection(page, 2, 2, "down", "0,2,0")
    assert positions_with(page, "data-in-word") == [(1, 2), (2, 2), (3, 2), (4, 2)]
    assert active_clue_texts(page) == ["Artiste muet"]


# ---- AC-3: tapping a clue selects the first empty cell of its word -----------


def test_ac3_tapping_a_clue_selects_the_first_empty_cell_of_its_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, [(1, 2, {"letter": "M"})])

    clue_named(page, "Artiste muet").click()

    expect_selection(page, 2, 2, "down", "0,2,0")
    assert positions_with(page, "data-selected") == [(2, 2)]
    assert positions_with(page, "data-in-word") == [(1, 2), (2, 2), (3, 2), (4, 2)]
    assert active_clue_texts(page) == ["Artiste muet"]


def test_ac3_each_half_of_a_two_clue_cell_selects_its_own_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, [(1, 2, {"letter": "M"})])
    clue_named(page, "Artiste muet").click()
    expect_selection(page, 2, 2, "down", "0,2,0")

    clue_named(page, "Passoire fine").click()
    expect_selection(page, 1, 0, "across", "0,0,0")
    assert active_clue_texts(page) == ["Passoire fine"]
    assert positions_with(page, "data-in-word") == [
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
    ]

    clue_named(page, "De la marine").click()
    expect_selection(page, 0, 1, "down", "0,0,1")
    assert active_clue_texts(page) == ["De la marine"]
    assert positions_with(page, "data-selected") == [(0, 1)]


def test_ac3_a_clue_sets_the_direction_of_its_word_over_the_current_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")

    clue_named(page, "Flaire").click()
    expect_selection(page, 1, 4, "down", "0,4,0")

    clue_named(page, "Alourdit le ballon").click()
    expect_selection(page, 4, 1, "across", "4,0,0")
    assert active_clue_texts(page) == ["Alourdit le ballon"]


def test_ac3_a_word_with_every_cell_filled_selects_its_first_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: list[tuple[int, int, dict[str, object]]] = [
        (1, 3, {"letter": "I"}),
        (2, 3, {"letter": "D"}),
        (3, 3, {"letter": "E"}),
        (4, 3, {"letter": "S"}),
    ]
    open_fx01(page, live_server, fx01_grid, changes)

    clue_named(page, "Fatales à César").click()

    expect_selection(page, 1, 3, "down", "0,3,0")
    assert positions_with(page, "data-in-word") == [(1, 3), (2, 3), (3, 3), (4, 3)]


def test_ac3_a_locked_cell_counts_as_filled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(
        page,
        live_server,
        fx01_grid,
        [(2, 1, {"letter": "V", "locked": True})],
    )

    clue_named(page, "Sans contenu").click()

    expect_selection(page, 2, 2, "across", "2,0,0")


def test_ac3_the_first_unfilled_cell_is_chosen_when_later_cells_are_filled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(
        page,
        live_server,
        fx01_grid,
        [(3, 1, {"letter": "A"}), (3, 3, {"letter": "E"})],
    )

    clue_named(page, "Fin de prière").click()

    expect_selection(page, 3, 2, "across", "3,0,0")


def test_ac3_tapping_the_active_clue_again_selects_the_first_unfilled_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(1, 2, {"letter": "M"})])
    clue_named(page, "Artiste muet").click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    tap(page, 3, 2)
    expect_selection(page, 3, 2, "down", "0,2,0")

    clue_named(page, "Artiste muet").click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    clue_named(page, "Artiste muet").click()
    settle(page)

    expect_selection(page, 2, 2, "down", "0,2,0")
    assert sent_selections(mock) == [
        select_cell_message(2, 2, "down"),
        select_cell_message(3, 2, "down"),
        select_cell_message(2, 2, "down"),
    ]


def test_ac3_tapping_a_clue_gives_keyboard_focus_to_the_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    clue_named(page, "Sans contenu").click()

    expect_selection(page, 2, 1, "across", "2,0,0")
    expect(page.get_by_test_id("grid")).to_be_focused()


# ---- AC-4: the clue bar stays visible, at 14 px or more ----------------------


def window_height(page: Page) -> float:
    return float(page.evaluate("() => window.innerHeight"))


def expect_bar_inside_window(page: Page) -> None:
    bar = page.get_by_test_id("clue-bar")
    expect(bar).to_be_visible()
    box = box_of(bar)
    assert box["height"] > 0
    assert box["y"] >= 0
    assert box["y"] + box["height"] <= window_height(page)


def test_ac4_fr_json_holds_the_clue_bar_texts() -> None:
    fr = load_fr()

    assert fr["clue_bar.label"] == "Définition en cours"
    assert fr["clue_bar.empty"] == "Touchez une case ou une définition."


def test_ac4_there_is_no_clue_bar_before_the_first_snapshot(
    page: Page, live_server: str
) -> None:
    open_mock_room(page, live_server)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "connecting")
    expect(page.get_by_test_id("clue-bar")).to_have_count(0)
    expect(page.get_by_test_id("clue-bar-text")).to_have_count(0)


def test_ac4_the_bar_is_shown_with_the_empty_text_before_any_tap(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(phone_page, live_server, fx01_grid)

    bar = phone_page.get_by_test_id("clue-bar")
    expect(bar).to_be_visible()
    expect(bar).to_have_attribute("data-word", "")
    expect(bar).to_have_attribute("aria-label", load_fr()["clue_bar.label"])
    text = phone_page.get_by_test_id("clue-bar-text")
    expect(text).to_have_text(load_fr()["clue_bar.empty"])
    expect_bar_inside_window(phone_page)


def test_ac4_the_bar_repeats_the_clue_of_the_selected_word_on_a_phone(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(phone_page, live_server, fx01_grid)

    tap(phone_page, 3, 1)

    expect_selection(phone_page, 3, 1, "across", "3,0,0")
    bar = phone_page.get_by_test_id("clue-bar")
    text = phone_page.get_by_test_id("clue-bar-text")
    expect(text).to_have_text("Fin de prière")
    expect(bar).to_have_attribute("data-word", "3,0,0")
    expect(bar).to_have_attribute("aria-label", load_fr()["clue_bar.label"])
    font_size = text.evaluate(
        "element => parseFloat(getComputedStyle(element).fontSize)"
    )
    assert font_size >= MIN_BAR_FONT_SIZE_PX
    expect_bar_inside_window(phone_page)


def test_ac4_the_bar_stays_inside_the_window_after_scrolling(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(phone_page, live_server, fx01_grid)
    tap(phone_page, 3, 1)
    expect(phone_page.get_by_test_id("clue-bar-text")).to_have_text("Fin de prière")

    phone_page.evaluate("() => window.scrollTo(0, 10000)")
    expect_bar_inside_window(phone_page)
    expect(phone_page.get_by_test_id("clue-bar-text")).to_have_text("Fin de prière")

    viewport = phone_page.get_by_test_id("grid-viewport")
    viewport.evaluate(
        "element => element.scrollTo(element.scrollWidth, element.scrollHeight)"
    )
    expect_bar_inside_window(phone_page)
    bar = phone_page.get_by_test_id("clue-bar")
    expect(bar).to_have_attribute("data-word", "3,0,0")


def test_ac4_the_bar_is_outside_the_scrolling_grid_viewport(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(phone_page, live_server, fx01_grid)

    expect(phone_page.get_by_test_id("clue-bar")).to_have_count(1)
    inside = phone_page.locator(
        '[data-testid="grid-viewport"] [data-testid="clue-bar"]'
    )
    expect(inside).to_have_count(0)


def test_ac4_the_bar_follows_the_selection_and_the_direction(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    bar = page.get_by_test_id("clue-bar")
    text = page.get_by_test_id("clue-bar-text")

    tap(page, 1, 1)
    expect(text).to_have_text("Passoire fine")
    expect(bar).to_have_attribute("data-word", "0,0,0")

    tap(page, 1, 1)
    expect(text).to_have_text("De la marine")
    expect(bar).to_have_attribute("data-word", "0,0,1")

    tap(page, 2, 2)
    expect(text).to_have_text("Artiste muet")
    expect(bar).to_have_attribute("data-word", "0,2,0")

    clue_named(page, "Sans contenu").click()
    expect(text).to_have_text("Sans contenu")
    expect(bar).to_have_attribute("data-word", "2,0,0")
    expect(page.get_by_test_id("grid")).to_have_attribute("data-word", "2,0,0")


def test_ac4_the_bar_shows_the_empty_text_again_when_the_selection_is_cleared(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 0, 1)
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("De la marine")

    show_snapshot(page, mock, note_view(), 1)

    text = page.get_by_test_id("clue-bar-text")
    expect(text).to_have_text(load_fr()["clue_bar.empty"])
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "")


# ---- AC-5: one select_cell per selection change ------------------------------


def test_ac5_each_selection_change_sends_one_select_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", "0,0,0")
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")
    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", "0,0,1")
    tap(page, 0, 1)
    settle(page)

    messages = sent_messages(mock)
    assert isinstance(messages[0], Join)
    assert messages[1:] == [
        select_cell_message(1, 1, "across"),
        select_cell_message(1, 1, "down"),
        select_cell_message(0, 1, "down"),
    ]


def test_ac5_nothing_is_sent_before_a_selection_change(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    settle(page)

    messages = sent_messages(mock)
    assert len(messages) == 1
    assert isinstance(messages[0], Join)


def test_ac5_a_move_to_a_cell_with_a_forced_direction_is_sent_once(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")

    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", "0,0,0")
    settle(page)

    assert sent_selections(mock) == [
        select_cell_message(1, 1, "across"),
        select_cell_message(1, 1, "down"),
        select_cell_message(1, 0, "across"),
    ]


def test_ac5_a_clue_tap_that_changes_the_selection_sends_its_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(1, 2, {"letter": "M"})])

    clue_named(page, "Artiste muet").click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    settle(page)

    assert sent_selections(mock) == [select_cell_message(2, 2, "down")]


def test_ac5_selecting_still_works_locally_when_the_socket_is_closed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    mock.close(1011)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "closed")
    sent_before = len(mock.received)

    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "down", "0,2,0")
    settle(page)

    assert len(mock.received) == sent_before
    assert sent_selections(mock) == []
    assert page_errors == []
    assert positions_with(page, "data-in-word") == [(1, 2), (2, 2), (3, 2), (4, 2)]
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Artiste muet")


# ---- AC-6: a clue tap selects its own word, even inside a longer run ---------


def open_nested_run(page: Page, base_url: str) -> MockRoomSocket:
    mock = open_mock_room(page, base_url)
    show_snapshot(page, mock, nested_run_view(), 0)
    expect(page.get_by_test_id("cell")).to_have_count(8)
    return mock


def test_ac6_tapping_the_clue_of_a_word_inside_a_longer_run_selects_its_own_word(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)

    clue_named(page, "Court").click()

    expect_selection(page, 1, 1, "down", "1,0,0")
    assert positions_with(page, "data-in-word") == SHORT_WORD_CELLS
    assert positions_with(page, "data-selected") == [(1, 1)]
    assert active_clue_texts(page) == ["Court"]


def test_ac6_the_clue_bar_shows_the_clue_that_was_tapped(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)

    clue_named(page, "Court").click()

    expect_selection(page, 1, 1, "down", "1,0,0")
    bar = page.get_by_test_id("clue-bar")
    expect(bar).to_have_attribute("data-word", "1,0,0")
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Court")


def test_ac6_tapping_the_clue_of_the_longer_word_selects_the_longer_word(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)
    clue_named(page, "Court").click()
    expect_selection(page, 1, 1, "down", "1,0,0")

    clue_named(page, "Long").click()

    expect_selection(page, 0, 1, "down", "0,0,0")
    assert positions_with(page, "data-in-word") == LONG_WORD_CELLS
    assert active_clue_texts(page) == ["Long"]


def test_ac6_tapping_another_cell_of_the_run_applies_the_longest_word_rule(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)
    clue_named(page, "Court").click()
    expect_selection(page, 1, 1, "down", "1,0,0")

    tap(page, 2, 1)

    expect_selection(page, 2, 1, "down", "0,0,0")
    assert positions_with(page, "data-in-word") == LONG_WORD_CELLS
    assert active_clue_texts(page) == ["Long"]
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Long")


def test_ac6_tapping_the_selected_cell_keeps_the_word_chosen_by_its_clue(
    page: Page, live_server: str
) -> None:
    mock = open_nested_run(page, live_server)
    clue_named(page, "Court").click()
    expect_selection(page, 1, 1, "down", "1,0,0")

    tap(page, 1, 1)
    settle(page)

    expect_selection(page, 1, 1, "down", "1,0,0")
    assert positions_with(page, "data-in-word") == SHORT_WORD_CELLS
    assert active_clue_texts(page) == ["Court"]
    assert sent_selections(mock) == [select_cell_message(1, 1, "down")]


def test_ac6_a_change_of_word_alone_sends_no_second_select_cell(
    page: Page, live_server: str
) -> None:
    mock = open_nested_run(page, live_server)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,0")

    clue_named(page, "Court").click()
    settle(page)

    expect_selection(page, 1, 1, "down", "1,0,0")
    assert active_clue_texts(page) == ["Court"]
    assert sent_selections(mock) == [select_cell_message(1, 1, "down")]


def test_ac6_a_shared_cell_tapped_with_no_clue_involved_selects_the_longest_word(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)

    tap(page, 1, 1)

    expect_selection(page, 1, 1, "down", "0,0,0")
    assert positions_with(page, "data-in-word") == LONG_WORD_CELLS
    assert positions_with(page, "data-selected") == [(1, 1)]
    assert active_clue_texts(page) == ["Long"]
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Long")


def test_ac6_the_clue_bar_is_a_labelled_region(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    bar = page.get_by_test_id("clue-bar")

    expect(bar).to_have_attribute("role", "region")
    expect(bar).to_have_attribute("aria-label", load_fr()["clue_bar.label"])
