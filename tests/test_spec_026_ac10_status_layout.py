"""Tests of spec 026, AC-10: where the completion status sits.

The room page is driven with a mocked socket, as "Status snapshots (AC-10)" in the
spec's "Test harness" says: an FX-02 snapshot (`seq` 5) with the eight players of
spec 013 AC-6, 100 feed lines (`seq` 6 to 105), then a tap on the clue at (0, 6).
Each test opens one page, at one window size, in one context (desktop or touch),
with one snapshot (`FX02_FULL_WRONG` or `FX02_SOLVED`), and checks everything
AC-10 asks of that page:

- at every window size of spec 006 AC-5: `grid-status` shows with the snapshot's
  `data-state` and text, and spec 013 AC-6's layout checks pass;
- at 568 by 320 and 740 by 360 (windows at most 500 px high), also: the status
  sits in `clue-bar`'s row, `clue-bar-text` is one line (computed `text-overflow`
  `ellipsis`, `white-space` `nowrap`, `overflow` `hidden`), and `clue-bar` is as
  high as on a page given `FX02_EMPTY` with the same feed, tap, window and context
  (FX-02's 31-character clue fits on one line, so "never higher" is "as high"
  here);
- at 568 by 320 in the touch context, also: spec 035's contrast and language
  scans find nothing;
- at 1280 by 720: the status sits under the clue bar, inside the window.

One more test covers the edge case "Low windows (AC-10)": a page resized across
500 px moves the status to its other place, with the same text and `data-state`.

The layout problems of a page are collected and reported together, so a failing
test names every check its page misses. The mocked socket (which answers each
`ping` with a `pong`), the desktop and touch contexts and the feed events come
from `spec013_harness`; the scans from `spec035_harness`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from fonts_ready import wait_for_fonts
from nock.grid import Arrow, ClueCell, Grid, LetterCell
from nock.protocol import (
    GridTarget,
    GridView,
    PlayerView,
    RevealBudget,
    Snapshot,
    grid_view,
)
from spec013_harness import (
    DEFAULT_ROOM_SETTINGS,
    FEED_LIMIT,
    FORM_TIMEOUT_MS,
    SNAPSHOT_TOKEN,
    MockRoomSocket,
    cell_at,
    check_frame,
    grid_from_text,
    make_page,
    player_view,
    wait_until,
)
from spec026_harness import Cell, ChangeList, load_fr, with_letter_cells
from spec035_harness import (
    FX01_CLUES,
    LANGUAGE_SCAN_SCRIPT,
    ROOM_CODE,
    contrast_offenders,
    unknown_texts,
)

NewPage = Callable[[int, int, bool], Page]

# ---- Fixtures: thin wrappers around the harness helpers ----


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    """FX-02, read from the text of `tests/fixtures/fx02.json` (spec 006)."""
    return grid_from_text(fx02_text)


@pytest.fixture
def new_page(browser: Browser, browser_name: str) -> Iterator[NewPage]:
    """Yield `new_page(width, height, touch)`; close its contexts afterwards."""
    closers: list[Callable[[], None]] = []

    def open_page(width: int, height: int, touch: bool) -> Page:
        """Open a page in a fresh desktop (`touch` false) or touch context."""
        page, close = make_page(browser, browser_name, width, height, touch)
        closers.append(close)
        return page

    yield open_page
    for close in closers:
        close()


# ---- The setup of "Status snapshots (AC-10)" ----

SPEC_006_WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]
LOW_WINDOW_MAX_HEIGHT = 500  # `window.innerHeight <= 500`: the status joins the row
LOW_WINDOW_SIZES = [
    size for size in SPEC_006_WINDOW_SIZES if size[1] <= LOW_WINDOW_MAX_HEIGHT
]
TALL_WINDOW_SIZES = [
    size for size in SPEC_006_WINDOW_SIZES if size[1] > LOW_WINDOW_MAX_HEIGHT
]
DESKTOP_WINDOW = (1280, 720)
SCAN_WINDOW = (568, 320)  # the scans run there, in the touch context
# The edge case "Low windows (AC-10)": a page opened at 740 by 360, then resized
# to each of these sizes in turn, across 500 px and back, then to 1 px above it.
RESIZE_START = (740, 360)
RESIZE_STEPS = [(740, 720), (740, 500), (740, 501)]
CONTEXTS = ["desktop", "touch"]
STATES = ["full_wrong", "solved"]
STATUS_TEXT_KEYS = {
    "full_wrong": "completion.full_wrong",
    "solved": "completion.solved",
}

SNAPSHOT_SEQ = 5
LAST_FEED_SEQ = SNAPSHOT_SEQ + FEED_LIMIT  # 100 feed lines: seq 6 to 105
FX02_CELL_COUNT = 13 * 17
LONGEST_CLUE = "On la glisse dans une enveloppe"
LONGEST_CLUE_CELL: Cell = (0, 6)
LONGEST_WORD = "0,6,0"

EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
# Their initials by spec 035's rule (one part: its first two characters).
EIGHT_INITIALS = ["AN", "BO", "CL", "DA", "EV", "FA", "GU", "HA"]

TAP_TIMEOUT_MS = 3000
MIN_GRID_VIEWPORT_PX = 100.0
MIN_CLUE_FONT_PX = 14.0
EPSILON = 1.0  # every comparison of boxes has 1 px of tolerance

# Where the word of a clue starts, seen from its clue cell, and the step from one
# letter to the next (spec 002, "Clue resolution"): row offset, column offset, row
# step, column step.
WORD_STARTS: dict[Arrow, tuple[int, int, int, int]] = {
    Arrow.RIGHT: (0, 1, 0, 1),
    Arrow.DOWN: (1, 0, 1, 0),
    Arrow.DOWN_THEN_RIGHT: (1, 0, 0, 1),
    Arrow.RIGHT_THEN_DOWN: (0, 1, 1, 0),
}

SETTLE_LAYOUT_SCRIPT = (
    "() => new Promise(resolve =>"
    " requestAnimationFrame(() => requestAnimationFrame(resolve)))"
)
WINDOW_SCRIPT = (
    "() => [window.innerWidth, window.innerHeight,"
    " document.documentElement.scrollWidth, document.documentElement.scrollHeight]"
)
WIDTHS_SCRIPT = "el => [el.scrollWidth, el.clientWidth]"
FONT_SIZE_SCRIPT = "el => getComputedStyle(el).fontSize"
ONE_LINE_STYLE_SCRIPT = (
    "el => { const style = getComputedStyle(el); return {"
    " 'text-overflow': style.textOverflow,"
    " 'white-space': style.whiteSpace,"
    " 'overflow': style.overflow }; }"
)
# The computed styles of `clue-bar-text` while the status sits in the row.
ONE_LINE_STYLES = {
    "text-overflow": "ellipsis",
    "white-space": "nowrap",
    "overflow": "hidden",
}


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    """Name each window size for the ids of a parametrized test.

    Args:
        sizes: The window sizes, as (width, height) in CSS pixels.

    Returns:
        One id per size, such as `568x320`, in the same order.
    """
    return [f"{width}x{height}" for width, height in sizes]


def letter_positions_of(grid: Grid) -> set[Cell]:
    """Find the letter cells of a grid.

    Args:
        grid: The grid to read.

    Returns:
        The (row, column) of every letter cell.
    """
    positions: set[Cell] = set()
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.add((cell.row, cell.column))
    return positions


def word_of(
    clue_cell: ClueCell, arrow: Arrow, letter_positions: set[Cell]
) -> list[Cell]:
    """The cells of a clue's word: from its start, up to the first non-letter cell."""
    row_offset, column_offset, row_step, column_step = WORD_STARTS[arrow]
    row = clue_cell.row + row_offset
    column = clue_cell.column + column_offset
    word: list[Cell] = []
    while (row, column) in letter_positions:
        word.append((row, column))
        row += row_step
        column += column_step
    return word


def solution_of(grid: Grid) -> dict[Cell, str]:
    """The solution letter of every letter cell (spec 026, "Definitions")."""
    letter_positions = letter_positions_of(grid)
    solution: dict[Cell, str] = {}
    for cell in grid.cells:
        if not isinstance(cell, ClueCell):
            continue
        for clue in cell.clues:
            word = word_of(cell, clue.arrow, letter_positions)
            if len(word) != len(clue.answer):
                pytest.fail(f"the word of {clue.text!r} does not fit {clue.answer!r}")
            for position, letter in zip(word, clue.answer, strict=True):
                if solution.get(position, letter) != letter:
                    pytest.fail(f"two answers of FX-02 disagree at {position}")
                solution[position] = letter
    if set(solution) != letter_positions:
        pytest.fail("a letter cell of FX-02 is in no word")
    return solution


def clue_texts_of(grid: Grid) -> list[str]:
    """List the clue texts of a grid (data of the test for the language scan).

    Args:
        grid: The grid to read.

    Returns:
        The text of every clue of every clue cell.
    """
    texts: list[str] = []
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            for clue in cell.clues:
                texts.append(clue.text)
    return texts


def letters_by_p2(letters: dict[Cell, str]) -> ChangeList:
    """Confirmed letters written by `p2`, the other fields as `grid_view` gives."""
    changes: ChangeList = []
    for (row, column), letter in letters.items():
        update: dict[str, object] = {"letter": letter, "author": "p2"}
        changes.append((row, column, update))
    return changes


def full_wrong_view(grid: Grid) -> GridView:
    """`FX02_FULL_WRONG`: every letter cell holds `E` by `p2`."""
    letters: dict[Cell, str] = {}
    for position in letter_positions_of(grid):
        letters[position] = "E"
    return with_letter_cells(grid_view(grid), letters_by_p2(letters))


def solved_view(grid: Grid) -> GridView:
    """`FX02_SOLVED`: every letter cell holds its solution letter by `p2`."""
    return with_letter_cells(grid_view(grid), letters_by_p2(solution_of(grid)))


def status_view(grid: Grid, state: str) -> GridView:
    """Build the grid of a status snapshot.

    Args:
        grid: FX-02.
        state: `full_wrong` or `solved`, the `data-state` the snapshot shows.

    Returns:
        The grid of `FX02_FULL_WRONG` or of `FX02_SOLVED`.
    """
    if state == "full_wrong":
        return full_wrong_view(grid)
    return solved_view(grid)


def eight_players() -> list[PlayerView]:
    """Spec 013 AC-6's players: `p1` (`Ana`, host, colour 0), `p2` to `p8`."""
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        players.append(
            player_view(f"p{number}", EIGHT_NICKNAMES[number - 1], number - 1)
        )
    return players


def status_snapshot_frame(view: GridView, solved: bool) -> str:
    """Build the snapshot of "Status snapshots (AC-10)" as a frame of the socket.

    Args:
        view: The grid the snapshot holds.
        solved: The snapshot's `solved` field.

    Returns:
        The JSON text of the snapshot: `seq` 5, `you` `p1`, the eight players.
    """
    snapshot = Snapshot(
        seq=SNAPSHOT_SEQ,
        you="p1",
        resume_token=SNAPSHOT_TOKEN,
        grid=view,
        players=tuple(eight_players()),
        settings=DEFAULT_ROOM_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=solved,
    )
    return snapshot.model_dump_json()


def tap(locator: Locator, touch: bool) -> None:
    """A click in the desktop context, `locator.tap()` in the touch context."""
    if touch:
        locator.tap(timeout=TAP_TIMEOUT_MS)
    else:
        locator.click(timeout=TAP_TIMEOUT_MS)


def open_status_page(
    page: Page, base_url: str, view: GridView, solved: bool, touch: bool
) -> None:
    """Show a snapshot and the 100 feed lines on /r/ABC123, then tap (0, 6)."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=FORM_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)
    wait_until(page, lambda: len(mock.received) > 0)

    mock.send(status_snapshot_frame(view, solved))
    room_page = page.get_by_test_id("room-page")
    expect(room_page).to_have_attribute("data-seq", str(SNAPSHOT_SEQ))
    expect(page.get_by_test_id("cell")).to_have_count(FX02_CELL_COUNT)
    for seq in range(SNAPSHOT_SEQ + 1, LAST_FEED_SEQ + 1):
        mock.send(check_frame(seq, "p2", GridTarget()))
    expect(room_page).to_have_attribute("data-seq", str(LAST_FEED_SEQ))

    row, column = LONGEST_CLUE_CELL
    clue = cell_at(page, row, column).get_by_test_id("clue")
    tap(clue.filter(has_text=LONGEST_CLUE), touch)
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", LONGEST_WORD)
    expect(page.get_by_test_id("clue-bar-text")).to_have_text(LONGEST_CLUE)
    if touch:
        expect(page.get_by_test_id("keyboard")).to_be_visible()
    page.evaluate(SETTLE_LAYOUT_SCRIPT)
    wait_for_fonts(page)


def expect_status_shows(page: Page, state: str) -> None:
    """One `grid-status`, shown, with `role`, `data-state` and text of `state`."""
    status = page.get_by_test_id("grid-status")
    expect(status).to_have_count(1)
    expect(status).to_be_visible()
    expect(status).to_have_attribute("role", "status")
    expect(status).to_have_attribute("data-state", state)
    expect(status).to_have_text(load_fr()[STATUS_TEXT_KEYS[state]])


# ---- Measures ----


class Box(NamedTuple):
    """A bounding box, in CSS pixels from the window's top left."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def height(self) -> float:
        """The height of the box, in CSS pixels."""
        return self.bottom - self.top


class WindowMeasures(NamedTuple):
    """The window's inner size and the page's scroll size, in CSS pixels.

    Attributes:
        inner_width: `window.innerWidth`.
        inner_height: `window.innerHeight`.
        scroll_width: `document.documentElement.scrollWidth`.
        scroll_height: `document.documentElement.scrollHeight`.
    """

    inner_width: int
    inner_height: int
    scroll_width: int
    scroll_height: int


def box_of(page: Page, test_id: str) -> Box:
    """Read the bounding box of the one element with a `data-testid`.

    The test fails when the element is not shown, since it then has no box.

    Args:
        page: The room page.
        test_id: The `data-testid` of the element.

    Returns:
        Its box, read with `locator.bounding_box()`.
    """
    rect = page.get_by_test_id(test_id).bounding_box()
    if rect is None:
        pytest.fail(f"{test_id} has no box: it is not shown")
    left = rect["x"]
    top = rect["y"]
    return Box(left, top, left + rect["width"], top + rect["height"])


def window_measures(page: Page) -> WindowMeasures:
    """Read the window's inner size and the page's scroll size.

    Args:
        page: The room page.

    Returns:
        The four measures, in CSS pixels.
    """
    inner_width, inner_height, scroll_width, scroll_height = page.evaluate(
        WINDOW_SCRIPT
    )
    return WindowMeasures(
        int(inner_width), int(inner_height), int(scroll_width), int(scroll_height)
    )


def is_inside(inner: Box, outer: Box) -> bool:
    """Whether `inner` lies inside `outer`, with 1 px of tolerance on each side."""
    return (
        inner.left >= outer.left - EPSILON
        and inner.top >= outer.top - EPSILON
        and inner.right <= outer.right + EPSILON
        and inner.bottom <= outer.bottom + EPSILON
    )


def overlaps_vertically(first: Box, second: Box) -> bool:
    """Whether the vertical ranges of two boxes overlap, with 1 px of tolerance."""
    return first.top < second.bottom + EPSILON and second.top < first.bottom + EPSILON


def font_size_px(page: Page, test_id: str) -> float:
    """Read the computed `font-size` of the one element with a `data-testid`.

    Args:
        page: The room page.
        test_id: The `data-testid` of the element.

    Returns:
        The font size, in CSS pixels.
    """
    font_size = page.get_by_test_id(test_id).evaluate(FONT_SIZE_SCRIPT)
    return float(str(font_size).removesuffix("px"))


# ---- The checks of AC-10, each returning the problems it found ----


def room_layout_problems(page: Page, touch: bool) -> list[str]:
    """Spec 013 AC-6's checks, as "Status snapshots (AC-10)" lists them."""
    problems: list[str] = []
    window = window_measures(page)
    viewport = box_of(page, "grid-viewport")
    # No tolerance on this floor, as in spec 013's own test.
    if viewport.height < MIN_GRID_VIEWPORT_PX:
        problems.append(f"grid-viewport is {viewport.height:.1f} px high")
    if window.scroll_width > window.inner_width:
        problems.append(f"horizontal page scroll: {window}")
    if window.scroll_height > window.inner_height:
        problems.append(f"vertical page scroll: {window}")
    zoom = page.get_by_test_id("grid-viewport").get_attribute("data-zoom")
    if zoom != "1":
        problems.append(f"grid-viewport has data-zoom {zoom!r}, not '1'")
    grid = box_of(page, "grid")
    if not is_inside(grid, viewport):
        problems.append(f"the grid {grid} is not inside grid-viewport {viewport}")
    bar = box_of(page, "clue-bar")
    window_box = Box(0.0, 0.0, window.inner_width, window.inner_height)
    if not is_inside(bar, window_box):
        problems.append(f"clue-bar {bar} is not inside the window {window_box}")
    if touch:
        keyboard = box_of(page, "keyboard")
        if bar.bottom > keyboard.top + EPSILON:
            problems.append(f"clue-bar {bar} goes below the keyboard's top {keyboard}")
    return problems


def in_the_clue_bar_row_problems(page: Page) -> list[str]:
    """Check that `grid-status` sits in `clue-bar`'s row, after `clue-bar-text`.

    Its box lies inside the box of `clue-bar`, its vertical range overlaps that of
    `clue-bar-text`, and its left edge is at or right of the right edge of
    `clue-bar-text`.

    Args:
        page: The room page, showing `grid-status`.

    Returns:
        One line per check the page misses; an empty list when it passes them all.
    """
    problems: list[str] = []
    status = box_of(page, "grid-status")
    bar = box_of(page, "clue-bar")
    clue_text = box_of(page, "clue-bar-text")
    if not is_inside(status, bar):
        problems.append(f"grid-status {status} is not inside clue-bar {bar}")
    if not overlaps_vertically(status, clue_text):
        problems.append(
            f"grid-status {status} is not in the row of clue-bar-text {clue_text}"
        )
    if status.left < clue_text.right - EPSILON:
        problems.append(
            f"grid-status {status} starts left of the end of clue-bar-text "
            f"{clue_text}"
        )
    return problems


def one_line_problems(page: Page) -> list[str]:
    """Check the computed styles that keep `clue-bar-text` on one line.

    While the status sits in the row, `text-overflow` is `ellipsis`, `white-space`
    is `nowrap` and `overflow` is `hidden`.

    Args:
        page: The room page, with the status in the clue bar's row.

    Returns:
        One line per style with another value; an empty list when all three match.
    """
    problems: list[str] = []
    styles = page.get_by_test_id("clue-bar-text").evaluate(ONE_LINE_STYLE_SCRIPT)
    assert isinstance(styles, dict), styles
    for name, expected in ONE_LINE_STYLES.items():
        found = styles.get(name)
        if found != expected:
            problems.append(f"clue-bar-text has {name} {found!r}, not {expected!r}")
    return problems


def clue_bar_row_problems(page: Page, height_without_status: float) -> list[str]:
    """The checks at 568 by 320 and 740 by 360: the status in the clue bar's row."""
    problems = in_the_clue_bar_row_problems(page)
    scroll_width, client_width = page.get_by_test_id("grid-status").evaluate(
        WIDTHS_SCRIPT
    )
    if scroll_width > client_width + 1:
        problems.append(
            f"grid-status cuts its text: scrollWidth {scroll_width}, "
            f"clientWidth {client_width}"
        )
    text_content = page.get_by_test_id("clue-bar-text").text_content() or ""
    shown_text = " ".join(text_content.split())
    if shown_text != LONGEST_CLUE:
        problems.append(f"clue-bar-text holds {shown_text!r}, not the whole clue")
    font_size = font_size_px(page, "clue-bar-text")
    if font_size < MIN_CLUE_FONT_PX:
        problems.append(f"clue-bar-text has a font-size of {font_size} px")
    problems.extend(one_line_problems(page))
    bar = box_of(page, "clue-bar")
    if abs(bar.height - height_without_status) > EPSILON:
        problems.append(
            f"clue-bar is {bar.height:.1f} px high with the status and "
            f"{height_without_status:.1f} px without it"
        )
    return problems


def under_the_clue_bar_problems(page: Page) -> list[str]:
    """Check that `grid-status` sits under the clue bar, inside the window.

    These are the checks at 1280 by 720, and those of a window taller than 500 px
    after a resize.

    Args:
        page: The room page, showing `grid-status`.

    Returns:
        One line per check the page misses; an empty list when it passes them all.
    """
    problems: list[str] = []
    status = box_of(page, "grid-status")
    bar = box_of(page, "clue-bar")
    window = window_measures(page)
    if status.top < bar.bottom - EPSILON:
        problems.append(f"grid-status {status} starts above the bottom of {bar}")
    if status.bottom > window.inner_height + EPSILON:
        problems.append(
            f"grid-status {status} ends below the window ({window.inner_height})"
        )
    return problems


def scan_problems(page: Page, base_url: str, grid: Grid) -> list[str]:
    """Spec 035's contrast scan (AC-8) and language scan (AC-9) on the page."""
    problems: list[str] = []
    offenders = contrast_offenders(page)
    if offenders:
        problems.append(f"the contrast scan flags {offenders}")
    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    assert isinstance(texts, list)
    if not texts:
        problems.append("the language scan found no text at all")
    # Data of the test: spec 035's list, plus FX-02's clue texts (AC-10).
    data = {
        *EIGHT_NICKNAMES,
        *EIGHT_INITIALS,
        *FX01_CLUES,
        *clue_texts_of(grid),
        ROOM_CODE,
        f"{base_url}/r/{ROOM_CODE}",
    }
    unknown = unknown_texts(texts, data)
    if unknown:
        problems.append(f"the language scan flags {unknown}")
    return problems


def clue_bar_height_without_status(
    new_page: NewPage, base_url: str, grid: Grid, size: tuple[int, int], touch: bool
) -> float:
    """The height of `clue-bar` on a page given `FX02_EMPTY` (no `grid-status`)."""
    width, height = size
    page = new_page(width, height, touch)
    open_status_page(page, base_url, grid_view(grid), solved=False, touch=touch)
    expect(page.get_by_test_id("grid-status")).to_have_count(0)
    return box_of(page, "clue-bar").height


def resize(page: Page, size: tuple[int, int]) -> None:
    """Give the page a new window size and wait for its layout to settle.

    Args:
        page: The room page.
        size: The new size, as (width, height) in CSS pixels.
    """
    width, height = size
    page.set_viewport_size({"width": width, "height": height})
    page.evaluate(SETTLE_LAYOUT_SCRIPT)


def status_place_problems(page: Page, size: tuple[int, int]) -> list[str]:
    """Check that `grid-status` sits where the window's height puts it.

    In `clue-bar`'s row when `window.innerHeight <= 500`, under the clue bar
    otherwise. The window must also have the height the page was given last, or
    the resize did not reach the page.

    Args:
        page: The room page, showing `grid-status`.
        size: The window size the page was given last, as (width, height).

    Returns:
        One line per check the page misses; an empty list when it passes them all.
    """
    problems: list[str] = []
    window = window_measures(page)
    given_height = size[1]
    if window.inner_height != given_height:
        problems.append(
            f"window.innerHeight is {window.inner_height}, not {given_height}"
        )
    if window.inner_height <= LOW_WINDOW_MAX_HEIGHT:
        problems.extend(in_the_clue_bar_row_problems(page))
    else:
        problems.extend(under_the_clue_bar_problems(page))
    return problems


# ---- AC-10: the completion status never takes the grid's room ----


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(
    ("width", "height"), LOW_WINDOW_SIZES, ids=size_ids(LOW_WINDOW_SIZES)
)
def test_ac10_on_a_low_window_the_status_sits_in_the_clue_bar_row(
    new_page: NewPage,
    live_server: str,
    fx02_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
    state: str,
) -> None:
    touch = context_kind == "touch"
    height_without_status = clue_bar_height_without_status(
        new_page, live_server, fx02_grid, (width, height), touch
    )
    page = new_page(width, height, touch)
    open_status_page(
        page, live_server, status_view(fx02_grid, state), state == "solved", touch
    )

    expect_status_shows(page, state)
    problems = room_layout_problems(page, touch)
    problems.extend(clue_bar_row_problems(page, height_without_status))
    if touch and (width, height) == SCAN_WINDOW:
        problems.extend(scan_problems(page, live_server, fx02_grid))

    assert problems == [], f"{width}x{height} {context_kind} {state}: {problems}"


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(
    ("width", "height"), TALL_WINDOW_SIZES, ids=size_ids(TALL_WINDOW_SIZES)
)
def test_ac10_on_a_tall_window_the_status_shows_and_the_grid_keeps_its_room(
    new_page: NewPage,
    live_server: str,
    fx02_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
    state: str,
) -> None:
    touch = context_kind == "touch"
    page = new_page(width, height, touch)
    open_status_page(
        page, live_server, status_view(fx02_grid, state), state == "solved", touch
    )

    expect_status_shows(page, state)
    problems = room_layout_problems(page, touch)

    assert problems == [], f"{width}x{height} {context_kind} {state}: {problems}"


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("context_kind", CONTEXTS)
def test_ac10_at_1280_by_720_the_status_sits_under_the_clue_bar(
    new_page: NewPage,
    live_server: str,
    fx02_grid: Grid,
    context_kind: str,
    state: str,
) -> None:
    touch = context_kind == "touch"
    width, height = DESKTOP_WINDOW
    page = new_page(width, height, touch)
    open_status_page(
        page, live_server, status_view(fx02_grid, state), state == "solved", touch
    )

    expect_status_shows(page, state)
    problems = under_the_clue_bar_problems(page)

    assert problems == [], f"{width}x{height} {context_kind} {state}: {problems}"


# ---- AC-10, edge case "Low windows (AC-10)": a resize across 500 px ----


@pytest.mark.parametrize("state", STATES)
def test_ac10_a_resize_across_500_px_moves_the_status(
    new_page: NewPage, live_server: str, fx02_grid: Grid, state: str
) -> None:
    width, height = RESIZE_START
    page = new_page(width, height, False)
    open_status_page(
        page, live_server, status_view(fx02_grid, state), state == "solved", False
    )
    expect_status_shows(page, state)
    problems: dict[str, list[str]] = {}
    found = status_place_problems(page, RESIZE_START)
    if found:
        problems[f"{width}x{height}"] = found

    for size in RESIZE_STEPS:
        resize(page, size)
        # One `grid-status`, with the same text and `data-state` as before.
        expect_status_shows(page, state)
        found = status_place_problems(page, size)
        if found:
            problems[f"{size[0]}x{size[1]}"] = found

    assert problems == {}, f"{state}: {problems}"
