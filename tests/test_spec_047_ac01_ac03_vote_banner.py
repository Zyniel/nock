"""Tests of spec 047, AC-1 and AC-3: the vote banner's look, and the line that
takes the buttons' place once I have voted.

AC-1: on `VOTE_ROOM`, after the mock's `VOTE`, at 360 by 740 and at 1280 by 720,
`vote-banner` floats over the top of the grid area (layer 9, 8 px inside it, no
layout shift) with the design's box, and holds `vote-question`, `vote-row` (the
two buttons, then `vote-seconds` on the right) and `vote-timebar`, 8 px apart.
AC-3: after a click on `vote-yes`, `vote-status` takes the buttons' place with the
muted line `fr.json["vote.cast"]`; on the requester's page it reads
`fr.json["vote.waiting"]` from the start.

Readings where the spec leaves room:

- "The grid area" is `grid-area` at 360 by 740 (the sheet layout) and
  `grid-viewport` at 1280 by 720 (the column layout), as the criterion says.
- "Top to bottom with 8 px between them" is the gap between one part's bottom and
  the next one's top, each 8 px (1 px).
- "8 px apart" for the buttons is the gap between `vote-yes`'s right edge and
  `vote-no`'s left edge.
- "Its left edge on the row's left edge" is read against `vote-row`'s content box
  (the row has no padding of its own in the design; its content box and its box
  are then the same).
- The requester's page of AC-3 is a first snapshot (seq 6) whose `open_vote` is
  `VOTE` asked by `p1`: a vote known only from a snapshot, so it has no
  `vote-seconds` (AC-2); the look of `vote-status` is the same.
- The boxes "read before `VOTE`" are read once two reads 100 ms apart agree.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import Vote
from spec019_harness import OpenWindow, window_opener
from spec042_harness import Box, box_of, colour_of, contrast_ratio
from spec043_harness import (
    INK,
    RoomMock,
    fr_value,
    same_position,
    same_size,
    style_of,
)
from spec046_harness import button_colour_problems, content_box
from spec047_harness import (
    MIN_TEXT_CONTRAST,
    MUTED,
    NAVY,
    PHONE,
    SHADOW_ALPHA,
    SIZE_IDS,
    SIZES,
    VOTE_QUESTION,
    WHITE,
    WORD,
    border_problems,
    colour_problem,
    open_vote_room,
    padding_problems,
    parts_of,
    radius_problems,
    shadow_problems,
    show_vote,
    tabular_problems,
    type_problems,
    vote_by_me,
)

SETTLE_STEP_MS = 100
SETTLE_READS = 30

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Setup -------------------------------------------------------------------------


def open_with_vote(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> tuple[Page, RoomMock]:
    """`VOTE_ROOM` at `size` (desktop), then the mock's `VOTE`."""
    page = window(size[0], size[1], False)
    mock = open_vote_room(page, base_url, grid)
    show_vote(page, mock)
    return page, mock


def settled_box(page: Page, test_id: str) -> Box:
    """The box of an element once two reads 100 ms apart agree."""
    locator = page.get_by_test_id(test_id)
    previous = box_of(locator)
    for _ in range(SETTLE_READS):
        page.wait_for_timeout(SETTLE_STEP_MS)
        current = box_of(locator)
        if current == previous:
            return current
        previous = current
    raise AssertionError(f"{test_id} keeps moving: {previous}")


def grid_area_id(size: tuple[int, int]) -> str:
    """The grid area of the banner ("Terms"): by layout."""
    if size == PHONE:
        return "grid-area"
    return "grid-viewport"


def banner(page: Page) -> Locator:
    return page.get_by_test_id("vote-banner")


# ---- AC-1: the banner's box ------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_banner_is_absolute_on_layer_9(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)

    assert style_of(banner(page), "position") == "absolute"
    assert style_of(banner(page), "zIndex") == "9"


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_banner_has_the_designs_box(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)
    box = banner(page)

    problems = colour_problem(box, "vote-banner", "backgroundColor", WHITE)
    problems += border_problems(box, "vote-banner", "2px", NAVY)
    problems += radius_problems(box, "vote-banner", ["10px"] * 4)
    problems += padding_problems(box, "vote-banner", "10px 12px")
    problems += shadow_problems(box, "vote-banner", (0, 10, 24, -12), SHADOW_ALPHA)

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_banner_lies_8_px_inside_the_top_of_the_grid_area(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)

    area = box_of(page.get_by_test_id(grid_area_id(size)))
    box = box_of(banner(page))

    assert same_position(box.top, area.top + 8.0), (box, area)
    assert same_position(box.left, area.left + 8.0), (box, area)
    assert same_position(box.right, area.right - 8.0), (box, area)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_banner_moves_neither_the_viewport_nor_the_clue_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = window(size[0], size[1], False)
    mock = open_vote_room(page, live_server, fx01_grid)
    before = {
        "grid-viewport": settled_box(page, "grid-viewport"),
        "clue-bar": settled_box(page, "clue-bar"),
    }

    show_vote(page, mock)

    moved: list[str] = []
    for test_id, was in before.items():
        now = settled_box(page, test_id)
        same = (
            same_position(now.left, was.left)
            and same_position(now.top, was.top)
            and same_position(now.right, was.right)
            and same_position(now.bottom, was.bottom)
        )
        if not same:
            moved.append(f"{test_id}: {was} -> {now}")
    assert moved == []


# ---- AC-1: the banner's parts -------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_question_row_and_timebar_come_top_to_bottom_8_px_apart(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)

    parts = parts_of(banner(page))

    names = [part.name for part in parts]
    assert names == ["vote-question", "vote-row", "vote-timebar"]
    gaps = [lower.box.top - upper.box.bottom for upper, lower in pairwise(parts)]
    assert all(same_position(gap, 8.0) for gap in gaps), gaps


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_question_has_the_designs_type(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)
    question = page.get_by_test_id("vote-question")

    expect(question).to_have_text(VOTE_QUESTION)
    problems = type_problems(
        question,
        "vote-question",
        size=15.2,
        weight="600",
        colour=INK,
        line_height=19.76,
    )
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_row_holds_yes_no_then_the_seconds_on_its_right(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)
    row = page.get_by_test_id("vote-row")

    parts = parts_of(row)

    assert [part.name for part in parts] == ["vote-yes", "vote-no", "vote-seconds"]
    yes_box, no_box, seconds_box = (part.box for part in parts)
    assert yes_box.right <= no_box.left <= seconds_box.left, parts
    assert same_position(no_box.left - yes_box.right, 8.0), (yes_box, no_box)
    assert same_position(seconds_box.right, content_box(row).right), seconds_box
    assert box_of(row).height >= 31.0 - 0.5, box_of(row)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_yes_no_and_the_seconds_share_one_vertical_centre(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)

    centres: list[float] = []
    for test_id in ("vote-yes", "vote-no", "vote-seconds"):
        centres.append(box_of(page.get_by_test_id(test_id)).centre_y)

    assert max(centres) - min(centres) <= 1.0, centres


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_yes_is_primary_and_no_is_secondary_with_7_16_padding(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)
    yes = page.get_by_test_id("vote-yes")
    no = page.get_by_test_id("vote-no")

    expect(yes).to_have_text(fr_value("vote.yes"))
    expect(no).to_have_text(fr_value("vote.no"))
    problems = button_colour_problems(yes, "primary")
    problems += button_colour_problems(no, "secondary")
    problems += padding_problems(yes, "vote-yes", "7px 16px")
    problems += padding_problems(no, "vote-no", "7px 16px")
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_seconds_have_the_muted_tabular_type(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)
    seconds = page.get_by_test_id("vote-seconds")

    problems = type_problems(
        seconds, "vote-seconds", size=13.6, weight="500", colour=MUTED
    )
    problems += tabular_problems(seconds, "vote-seconds")

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_timebar_is_a_4_px_word_blue_track_with_a_navy_fill(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_with_vote(window, live_server, fx01_grid, size)
    bar = page.get_by_test_id("vote-timebar")
    fill = bar.get_by_test_id("vote-timebar-fill")

    expect(bar).to_have_attribute("aria-hidden", "true")
    expect(fill).to_have_count(1)
    assert same_size(box_of(bar).height, 4.0), box_of(bar)
    problems = radius_problems(bar, "vote-timebar", ["2px"] * 4)
    problems += colour_problem(bar, "vote-timebar", "backgroundColor", WORD)
    problems += colour_problem(fill, "vote-timebar-fill", "backgroundColor", NAVY)
    assert problems == []


# ---- AC-3: after a ballot ---------------------------------------------------------


def click_yes(page: Page, mock: RoomMock) -> list[object]:
    """Click `vote-yes`; return the frames sent within 300 ms, parsed."""
    before = len(mock.frames_without_pings())
    page.get_by_test_id("vote-yes").click()
    expect(page.get_by_test_id("vote-status")).to_be_visible()
    page.wait_for_timeout(300)
    return mock.parsed_frames_after(before)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_a_yes_sends_one_ballot_and_the_status_takes_the_buttons_place(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_with_vote(window, live_server, fx01_grid, size)

    sent = click_yes(page, mock)

    assert sent == [Vote(vote_id=1, yes=True)]
    row = page.get_by_test_id("vote-row")
    expect(row.get_by_test_id("vote-yes")).to_have_count(0)
    expect(row.get_by_test_id("vote-no")).to_have_count(0)
    status = row.get_by_test_id("vote-status")
    expect(status).to_have_text(fr_value("vote.cast"))
    assert fr_value("vote.cast") == (
        "Vote enregistré. En attente des autres joueurs\N{HORIZONTAL ELLIPSIS}"
    )


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_the_status_is_a_muted_line_left_of_the_seconds(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_with_vote(window, live_server, fx01_grid, size)
    click_yes(page, mock)
    row = page.get_by_test_id("vote-row")
    status = page.get_by_test_id("vote-status")

    problems = type_problems(
        status,
        "vote-status",
        size=13.6,
        weight="500",
        colour=MUTED,
        line_height=17.68,
    )
    names = [part.name for part in parts_of(row)]
    status_box = box_of(status)
    seconds_box = box_of(page.get_by_test_id("vote-seconds"))
    row_box = content_box(row)

    assert problems == []
    assert names == ["vote-status", "vote-seconds"]
    assert same_position(status_box.left, row_box.left), (status_box, row_box)
    assert same_position(seconds_box.right, row_box.right), (seconds_box, row_box)
    expect(page.get_by_test_id("vote-timebar")).to_be_visible()


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_the_status_has_the_focus_and_reads_on_the_white_banner(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_with_vote(window, live_server, fx01_grid, size)
    click_yes(page, mock)
    status = page.get_by_test_id("vote-status")

    expect(status).to_be_focused()
    ratio = contrast_ratio(colour_of(status, "color"), (255.0, 255.0, 255.0, 1.0))
    assert ratio >= MIN_TEXT_CONTRAST, ratio


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_the_requesters_page_shows_the_waiting_line_and_no_button(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = window(size[0], size[1], False)
    open_vote_room(page, live_server, fx01_grid, open_vote=vote_by_me())
    row = page.get_by_test_id("vote-row")
    status = row.get_by_test_id("vote-status")

    expect(status).to_have_text(fr_value("vote.waiting"))
    expect(page.get_by_test_id("vote-yes")).to_have_count(0)
    expect(page.get_by_test_id("vote-no")).to_have_count(0)
    problems = type_problems(
        status,
        "vote-status",
        size=13.6,
        weight="500",
        colour=MUTED,
        line_height=17.68,
    )
    assert problems == []
    status_box = box_of(status)
    assert same_position(status_box.left, content_box(row).left), status_box
