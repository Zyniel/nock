"""Tests of spec 019, AC-4: the author of the selected letter, in words.

While the switch is on, `clue-bar` names the author of the selected cell's
confirmed letter in `clue-bar-author`, after `clue-bar-text`. The first tests use
the snapshot of AC-1 at the default window, one of them the separate run where the
line follows the cell's confirmed author (decision 12). The last test uses spec
026's `FX02_FULL_WRONG` page with `p2`'s nickname 20 characters long, at the window
sizes of spec 006 AC-5, in desktop and touch contexts; at 568 by 320 and 740 by
360 it also checks the clue bar's row (decision 11). The shared setup is in
`spec019_harness`.

Choices where the spec leaves room:

- Spec 026's page is built as its AC-10 tests build it: the eight players of
  spec 013 AC-6 (`p2` renamed), 100 feed lines (`check_result` events of `p2` on
  the grid, `seq` 6 to 105), then a tap on the clue `On la glisse dans une
  enveloppe` at (0, 6), which selects (1, 6), with the switch still off.
- Spec 009 AC-4's font-size check of `clue-bar-text` (14 px or more) is run in the
  touch contexts it names (360 by 740 and 740 by 360), since the spec says spec
  009 AC-4 keeps holding.
- "It sits on the line of the clue text when there is room" is tested where the
  spec says where it sits: on windows at most 500 px high, at 568 by 320 and 740
  by 360.

Refined by spec 043 (the design's room layout): at 568 by 320 and 740 by 360 the
in-row checks (text, author line and status in the clue bar's row) run in the
touch context, spec 043's sheet layout; in the desktop context these windows are
the column layout, where `grid-status` sits under the clue bar, so there the text
and the author line lie in the bar's row with the same rules for the author line,
and `grid-status` starts at or below the bar's bottom. The switch is pressed in
the room Menu (spec 019's harness opens it).
- The pending edit of decision 12 is seen on the page as spec 015 shows it:
  (1, 1) has `data-letter="Z"` and `data-unconfirmed="true"`, and the page sent
  an `edit_letter` frame for (1, 1) with the letter `Z`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import GridTarget
from spec013_harness import check_frame
from spec019_harness import (
    CONTEXT_KINDS,
    FOLLOW_MS,
    FX02_CELL_COUNT,
    LAYOUT_EPSILON_PX,
    SETTLE_MS,
    WINDOW_IDS,
    WINDOW_SIZES,
    Box,
    MockRoomSocket,
    OpenWindow,
    authors_switch,
    box_inside,
    box_of,
    cell_at,
    cell_locked_frame,
    eight_players,
    expect_seq,
    fx02_full_wrong_view,
    grid_from_text,
    layout_problems,
    letter_changed_frame,
    load_fr,
    open_ac1,
    open_room,
    player_left_frame,
    player_view,
    press,
    turn_switch_off,
    turn_switch_on,
    wait_until,
    window_opener,
)

LONG_NICKNAME = "Bartholomew Lefebvre"
TIGHT_WINDOWS = [(568, 320), (740, 360)]
KEYBOARD_WINDOWS = [(360, 740), (740, 360)]  # spec 009 AC-4's touch contexts
MIN_CLUE_FONT_PX = 14.0
PENDING_WAIT_MS = 500

# Spec 026's status page.
SNAPSHOT_SEQ = 5
LAST_FEED_SEQ = 105
LONGEST_CLUE = "On la glisse dans une enveloppe"
LONGEST_CLUE_CELL = (0, 6)
LONGEST_WORD = "0,6,0"
SELECTED_CELL = (1, 6)

# The author line's minimum width: the smaller of its scrollWidth and 6 times its
# computed font size.
MIN_WIDTH_FONT_SIZES = 6.0
ONE_LINE_STYLES = {
    "white-space": "nowrap",
    "overflow": "hidden",
    "text-overflow": "ellipsis",
}

SETTLE_LAYOUT_SCRIPT = (
    "() => new Promise(resolve =>"
    " requestAnimationFrame(() => requestAnimationFrame(resolve)))"
)

AUTHOR_PLACE_SCRIPT = """
() => {
  const bar = document.querySelector('[data-testid="clue-bar"]');
  const text = document.querySelector('[data-testid="clue-bar-text"]');
  const author = document.querySelector('[data-testid="clue-bar-author"]');
  const position = text.compareDocumentPosition(author);
  return {
    inBar: bar.contains(author),
    afterText: (position & Node.DOCUMENT_POSITION_FOLLOWING) !== 0,
    insideText: text.contains(author),
  };
}
"""

# The widths and styles the clue bar's row is checked with, read at once.
ROW_MEASURES_SCRIPT = """
() => {
  const read = testId => {
    const element = document.querySelector(`[data-testid="${testId}"]`);
    const style = getComputedStyle(element);
    return {
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
      fontSize: parseFloat(style.fontSize),
      'white-space': style.whiteSpace,
      overflow: style.overflow,
      'text-overflow': style.textOverflow,
    };
  };
  return {
    text: read('clue-bar-text'),
    author: read('clue-bar-author'),
    status: read('grid-status'),
  };
}
"""


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return grid_from_text(fx02_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Helpers of these tests -------------------------------------------------


def author_line(page: Page) -> Locator:
    return page.get_by_test_id("clue-bar-author")


def selected_text(name: str) -> str:
    """`t("authors.selected", { name })`, built from `fr.json`."""
    return load_fr()["authors.selected"].replace("{name}", name)


def sent_edit_letter(mock: MockRoomSocket, row: int, column: int, letter: str) -> bool:
    """Tell whether the page sent an `edit_letter` of `letter` at (row, column)."""
    for frame in mock.frames_without_pings():
        message = json.loads(frame)
        if (
            message["type"] == "edit_letter"
            and message["row"] == row
            and message["column"] == column
            and message["letter"] == letter
        ):
            return True
    return False


# ---- AC-4: the snapshot of AC-1 ---------------------------------------------


def test_ac4_fr_json_has_the_selected_author_text() -> None:
    assert load_fr()["authors.selected"] == "Lettre de {name}"


def test_ac4_tapping_a_letter_names_its_author_after_the_clue_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)

    cell_at(page, 1, 1).click()

    expect(author_line(page)).to_have_text(selected_text("Bob"))
    expect(author_line(page)).to_have_text("Lettre de Bob")
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Passoire fine")
    place = page.evaluate(AUTHOR_PLACE_SCRIPT)
    assert place == {"inBar": True, "afterText": True, "insideText": False}


def test_ac4_a_player_who_left_is_still_named(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    mock.send(player_left_frame(6, "p2"))
    expect_seq(page, 6)

    cell_at(page, 1, 3).click()

    expect(author_line(page)).to_have_text("Lettre de Bob")


def test_ac4_an_author_the_page_never_knew_is_named_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)

    cell_at(page, 1, 2).click()

    someone = load_fr()["feed.someone"]
    expect(author_line(page)).to_have_text(selected_text(someone))


def test_ac4_a_revealed_or_empty_cell_shows_no_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    cell_at(page, 1, 1).click()
    expect(author_line(page)).to_have_count(1)

    cell_at(page, 1, 4).click()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-column", "4")
    expect(author_line(page)).to_have_count(0)

    cell_at(page, 2, 1).click()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "2")
    expect(author_line(page)).to_have_count(0)


def test_ac4_switching_the_view_off_removes_the_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    cell_at(page, 1, 1).click()
    expect(author_line(page)).to_have_count(1)

    turn_switch_off(page)

    expect(author_line(page)).to_have_count(0)
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Passoire fine")


def test_ac4_no_author_while_the_switch_is_off(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")

    cell_at(page, 1, 1).click()

    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "0,0,0")
    page.wait_for_timeout(SETTLE_MS)
    expect(author_line(page)).to_have_count(0)


def test_ac4_no_author_while_nothing_is_selected(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "")
    page.wait_for_timeout(SETTLE_MS)
    expect(author_line(page)).to_have_count(0)


def test_ac4_the_name_is_inserted_as_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "<b>Bo</b>", 3),
    ]
    open_ac1(page, live_server, fx01_grid, players)
    turn_switch_on(page)

    cell_at(page, 1, 1).click()

    # Spec 040's displayNickname writes `<b>Bo</b>` as `<b>bo</b>`.
    expect(author_line(page)).to_have_text("Lettre de <b>bo</b>")
    expect(author_line(page).locator("b")).to_have_count(0)


# ---- AC-4: the line follows the cell (decision 12) --------------------------


def test_ac4_the_line_follows_the_selected_cells_confirmed_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    cell_at(page, 1, 0).click()
    expect(author_line(page)).to_have_text("Lettre de Ana")

    mock.send(letter_changed_frame(6, 1, 0, "X", "p2"))
    expect_seq(page, 6)
    expect(author_line(page)).to_have_text("Lettre de Bob", timeout=FOLLOW_MS)

    mock.send(letter_changed_frame(7, 1, 0, None, "p2"))
    expect_seq(page, 7)
    expect(author_line(page)).to_have_count(0, timeout=FOLLOW_MS)

    mock.send(letter_changed_frame(8, 1, 0, "T", "p2"))
    expect_seq(page, 8)
    expect(author_line(page)).to_have_text("Lettre de Bob", timeout=FOLLOW_MS)

    mock.send(cell_locked_frame(9, 1, 0, "T", revealed=True))
    expect_seq(page, 9)
    expect(author_line(page)).to_have_count(0, timeout=FOLLOW_MS)

    cell_at(page, 1, 1).click()
    expect(author_line(page)).to_have_text("Lettre de Bob")
    page.keyboard.press("z")
    pending_cell = cell_at(page, 1, 1)
    expect(pending_cell).to_have_attribute("data-letter", "Z")
    expect(pending_cell).to_have_attribute("data-unconfirmed", "true")
    wait_until(page, lambda: sent_edit_letter(mock, 1, 1, "Z"))
    pending_cell.click()
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", "1")
    expect(grid).to_have_attribute("data-selected-column", "1")
    page.wait_for_timeout(PENDING_WAIT_MS)
    assert author_line(page).all_text_contents() == ["Lettre de Bob"]

    mock.send(letter_changed_frame(10, 1, 1, "Z", "p1"))
    expect_seq(page, 10)
    expect(author_line(page)).to_have_text("Lettre de Ana", timeout=FOLLOW_MS)


# ---- AC-4: spec 026's FX-02 page at every window size -----------------------


def open_fx02_status_page(page: Page, base_url: str, grid: Grid, touch: bool) -> None:
    """Spec 026's `FX02_FULL_WRONG` page, `p2` with a 20-character nickname.

    The snapshot (`seq` 5), 100 feed lines (`seq` 6 to 105), then a tap on the
    clue `On la glisse dans une enveloppe`, which selects (1, 6). The switch is
    still off.
    """
    assert len(LONG_NICKNAME) == 20
    mock = open_room(
        page,
        base_url,
        fx02_full_wrong_view(grid),
        eight_players(LONG_NICKNAME),
        seq=SNAPSHOT_SEQ,
        cell_count=FX02_CELL_COUNT,
    )
    for seq in range(SNAPSHOT_SEQ + 1, LAST_FEED_SEQ + 1):
        mock.send(check_frame(seq, "p2", GridTarget()))
    expect_seq(page, LAST_FEED_SEQ)
    clue = cell_at(page, *LONGEST_CLUE_CELL).get_by_test_id("clue")
    press(clue.filter(has_text=LONGEST_CLUE), touch)
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", LONGEST_WORD)
    grid_element = page.get_by_test_id("grid")
    expect(grid_element).to_have_attribute("data-selected-row", str(SELECTED_CELL[0]))
    expect(grid_element).to_have_attribute(
        "data-selected-column", str(SELECTED_CELL[1])
    )
    expect(page.get_by_test_id("clue-bar-text")).to_have_text(LONGEST_CLUE)
    expect(page.get_by_test_id("grid-status")).to_have_attribute(
        "data-state", "full_wrong"
    )
    if touch:
        expect(page.get_by_test_id("keyboard")).to_be_visible()
    page.evaluate(SETTLE_LAYOUT_SCRIPT)


def bar_height(page: Page) -> float:
    bar = box_of(page.get_by_test_id("clue-bar"))
    return bar.bottom - bar.top


def overlaps_vertically(first: Box, second: Box) -> bool:
    """Whether the vertical ranges of two boxes overlap, with 1 px of tolerance."""
    return (
        first.top < second.bottom + LAYOUT_EPSILON_PX
        and second.top < first.bottom + LAYOUT_EPSILON_PX
    )


def row_place_problems(page: Page, with_status: bool) -> list[str]:
    """Text, author line (and status) inside `clue-bar`, in this order, one row.

    Without the status (spec 043's column layout), `grid-status` starts at or below
    the bar's bottom.
    """
    bar = box_of(page.get_by_test_id("clue-bar"))
    status_box = box_of(page.get_by_test_id("grid-status"))
    named_boxes = [
        ("clue-bar-text", box_of(page.get_by_test_id("clue-bar-text"))),
        ("clue-bar-author", box_of(author_line(page))),
    ]
    problems: list[str] = []
    if with_status:
        named_boxes.append(("grid-status", status_box))
    elif status_box.top < bar.bottom - LAYOUT_EPSILON_PX:
        problems.append(f"grid-status {status_box} is not under clue-bar {bar}")
    for name, box in named_boxes:
        if not box_inside(box, bar):
            problems.append(f"{name} {box} is not inside clue-bar {bar}")
    for index in range(1, len(named_boxes)):
        before_name, before = named_boxes[index - 1]
        name, box = named_boxes[index]
        if box.left < before.right - LAYOUT_EPSILON_PX:
            problems.append(f"{name} {box} starts left of the end of {before_name}")
    for first_index in range(len(named_boxes)):
        for second_index in range(first_index + 1, len(named_boxes)):
            first_name, first = named_boxes[first_index]
            second_name, second = named_boxes[second_index]
            if not overlaps_vertically(first, second):
                problems.append(f"{first_name} and {second_name} are not in one row")
    return problems


def row_width_problems(page: Page, with_status: bool) -> list[str]:
    """The author line shortens first, down to M; the status keeps its text."""
    measures = page.evaluate(ROW_MEASURES_SCRIPT)
    text = measures["text"]
    author = measures["author"]
    status = measures["status"]
    problems: list[str] = []
    for name, expected in ONE_LINE_STYLES.items():
        if author[name] != expected:
            problems.append(f"clue-bar-author has {name} {author[name]!r}")
    minimum = min(author["scrollWidth"], MIN_WIDTH_FONT_SIZES * author["fontSize"])
    if author["clientWidth"] < minimum - LAYOUT_EPSILON_PX:
        problems.append(
            f"clue-bar-author is {author['clientWidth']} px wide, under M {minimum}"
        )
    text_is_whole = text["scrollWidth"] <= text["clientWidth"] + LAYOUT_EPSILON_PX
    if not text_is_whole and author["clientWidth"] > minimum + LAYOUT_EPSILON_PX:
        problems.append(
            f"clue-bar-text is cut ({text['scrollWidth']} > {text['clientWidth']}) "
            f"while clue-bar-author is {author['clientWidth']} px, above M {minimum}"
        )
    status_cut = status["scrollWidth"] > status["clientWidth"] + LAYOUT_EPSILON_PX
    if with_status and status_cut:
        problems.append(
            f"grid-status cuts its text: {status['scrollWidth']} > "
            f"{status['clientWidth']}"
        )
    text_content = page.get_by_test_id("clue-bar-text").text_content() or ""
    shown_text = " ".join(text_content.split())
    if shown_text != LONGEST_CLUE:
        problems.append(f"clue-bar-text holds {shown_text!r}")
    return problems


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac4_fx02_the_grid_keeps_its_room_and_the_author_line_fits_the_bar(
    window: OpenWindow,
    live_server: str,
    fx02_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    tight = (width, height) in TIGHT_WINDOWS
    page = window(width, height, touch)
    open_fx02_status_page(page, live_server, fx02_grid, touch)
    height_off = bar_height(page)

    turn_switch_on(page, touch)

    expect(author_line(page)).to_have_text(selected_text(LONG_NICKNAME))
    page.evaluate(SETTLE_LAYOUT_SCRIPT)
    problems = layout_problems(page, touch)
    if touch and (width, height) in KEYBOARD_WINDOWS:
        font_size = page.get_by_test_id("clue-bar-text").evaluate(
            "el => parseFloat(getComputedStyle(el).fontSize)"
        )
        if font_size < MIN_CLUE_FONT_PX:
            problems.append(f"clue-bar-text has a font-size of {font_size} px")
    if tight:
        height_on = bar_height(page)
        if abs(height_on - height_off) > LAYOUT_EPSILON_PX:
            problems.append(
                f"clue-bar is {height_on:.1f} px high with the author line and "
                f"{height_off:.1f} px without it"
            )
        problems.extend(row_place_problems(page, with_status=touch))
        problems.extend(row_width_problems(page, with_status=touch))
    assert problems == [], f"{width}x{height} {context_kind}: {problems}"
