"""Tests of spec 046, AC-11 to AC-13: « Mes salons » and « Grilles terminées » as
list rows, and « Mes salons »' states.

Browser with mocked routes: the live server serves `CAT` and the client (accounts
off), in Paris time; `page.route` answers `POST /api/rooms/summaries` with
`ROOMS2` (`XYZ789`, grid 2, 5 by 5, `Ana` and `Bob`, not solved; `ABC234`, no
grid number, 13 by 17, `Ana`, solved), whose identities are seeded, and holds,
empties or fails it for AC-12. `HIST2` is `nock.history` seeded with spec 029
AC-2's two records (`XYZ789` with `Bob` and `Cy`; `QQQQQQ` alone).

Choices where the spec leaves room:

- "`my-room-title` reads `Grille n° 2` then a `meta-sep` then the size" is read as
  what the title holds in order, an element without a test id read through; the
  solved pill shows there as `#my-room-solved`. The same reading gives
  `history-line`'s order.
- "Under it, 3 px apart": `my-room-players` 3 px under the title and
  `my-room-activity` 3 px under `my-room-players` (the text column's lines).
- "On the right": the button's right edge 14 px left of the row's right edge
  (1 px, as AC-11 gives it for `my-room-link`).
- "`my-room-players` wraps": its text takes more than one line.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec029_harness import OLD_CODE
from spec032_harness import ABC, XYZ
from spec035_harness import build_fx01_grid, build_reference_catalogue, load_fr
from spec042_harness import box_of
from spec043_harness import (
    GREEN,
    GREEN_BG,
    INK,
    MUTED,
    RED,
    fr_value,
    label_of,
)
from spec046_harness import (
    SIZES,
    SUMMARIES_ROUTE,
    WIDE,
    HeldRoute,
    OpenWindow,
    answer_json,
    button_colour_problems,
    child_ids,
    children_of,
    colour_problem,
    error_line_problems,
    expect_history_count,
    expect_my_rooms_ready,
    fail_play,
    font_problems,
    history_item_of,
    long_names,
    my_room_of,
    open_catalogue,
    padding_matches,
    pill_problems,
    row_problems,
    same_position,
    section_heading_problems,
    seed_hist2,
    seed_rooms2,
    seed_rooms2_identities,
    separator_problems,
    sequence_of,
    size_ids,
    style_of,
    to_box,
    window_opener,
)

TIMES = "\N{MULTIPLICATION SIGN}"
GRID_2 = "Grille n\N{DEGREE SIGN} 2"
SEP = "\N{MIDDLE DOT}"
OLD_LOADING_TEXT = "Chargement de vos salons\N{HORIZONTAL ELLIPSIS}"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_rooms2(window: OpenWindow, base_url: str, size: tuple[int, int]) -> Page:
    page = window(*size)
    seed_rooms2(page)
    open_catalogue(page, base_url)
    expect_my_rooms_ready(page, 2)
    return page


def open_hist2(window: OpenWindow, base_url: str, size: tuple[int, int]) -> Page:
    page = window(*size)
    seed_hist2(page)
    open_catalogue(page, base_url)
    expect_history_count(page, 2)
    return page


def heading_of_column(page: Page) -> Locator:
    return page.get_by_test_id("catalogue-column").locator(":scope > h1")


def rows_problems(rows: list[Locator]) -> list[str]:
    """Each row in the list row look, each next one 10 px below the one before."""
    problems: list[str] = []
    for row in rows:
        problems.extend(row_problems(row))
    for before, after in pairwise(rows):
        gap = box_of(after).top - box_of(before).bottom
        if not same_position(gap, 10.0):
            problems.append(f"rows {gap} px apart")
    return problems


def on_the_right(row: Locator, button: Locator) -> bool:
    return same_position(box_of(row).right - box_of(button).right, 14.0)


# ---- AC-11: « Mes salons » ---------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac11_my_rooms_comes_16_px_under_the_heading_before_the_filters(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_rooms2(window, live_server, (width, height))

    ids = child_ids(page.get_by_test_id("catalogue-column"))
    gap = box_of(page.get_by_test_id("my-rooms")).top
    gap -= box_of(heading_of_column(page)).bottom

    assert ids[1:3] == ["my-rooms", "catalogue-filters"], ids
    assert same_position(gap, 16.0), gap


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac11_the_heading_is_the_section_heading(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_rooms2(window, live_server, (width, height))
    heading = page.get_by_test_id("my-rooms").locator("h2")

    expect(heading).to_have_text(fr_value("my_rooms.heading"))
    assert section_heading_problems(heading) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac11_the_two_rows_are_list_rows_10_px_apart(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_rooms2(window, live_server, (width, height))

    rows = [my_room_of(page, XYZ), my_room_of(page, ABC)]

    assert rows_problems(rows) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac11_an_open_rooms_title_is_its_grid_and_size_in_ink_700(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_rooms2(window, live_server, (width, height))
    title = my_room_of(page, XYZ).get_by_test_id("my-room-title")

    assert title.evaluate("element => element.tagName") == "H3"
    assert sequence_of(title) == [GRID_2, SEP, f"5 {TIMES} 5"]
    assert separator_problems(title) == []
    assert style_of(title, "fontWeight") == "700"
    assert colour_problem(title, "title", "color", INK) == []
    expect(my_room_of(page, XYZ).get_by_test_id("my-room-solved")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac11_the_players_and_activity_lines_are_muted_3_px_apart(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_rooms2(window, live_server, (width, height))
    row = my_room_of(page, XYZ)
    players = row.get_by_test_id("my-room-players")
    activity = row.get_by_test_id("my-room-activity")

    title_box = box_of(row.get_by_test_id("my-room-title"))
    players_box = box_of(players)
    activity_box = box_of(activity)

    assert same_position(players_box.top - title_box.bottom, 3.0), players_box
    assert same_position(activity_box.top - players_box.bottom, 3.0), activity_box
    assert font_problems(players, "players", 13.6, colour=MUTED) == []
    assert font_problems(activity, "activity", 13.6, colour=MUTED) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac11_an_open_rooms_link_is_a_primary_button_on_the_right(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_rooms2(window, live_server, (width, height))
    row = my_room_of(page, XYZ)
    link = row.get_by_test_id("my-room-link")

    expect(link).to_have_text(fr_value("my_rooms.open"))
    assert on_the_right(row, link), (box_of(row), box_of(link))
    assert button_colour_problems(link, "primary") == []
    assert padding_matches(link, "10px 16px")
    assert style_of(link, "borderTopLeftRadius") == "6px"


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac11_a_solved_room_has_the_terminee_pill_after_its_size(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_rooms2(window, live_server, (width, height))
    title = my_room_of(page, ABC).get_by_test_id("my-room-title")
    solved = title.get_by_test_id("my-room-solved")

    expect(solved).to_have_text(fr_value("catalogue.progress.finished"))
    assert sequence_of(title) == [
        fr_value("my_rooms.unnumbered"),
        SEP,
        f"13 {TIMES} 17",
        "#my-room-solved",
    ]
    assert pill_problems(solved, GREEN_BG, GREEN) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac11_a_solved_rooms_link_is_a_secondary_button(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_rooms2(window, live_server, (width, height))
    link = my_room_of(page, ABC).get_by_test_id("my-room-link")

    assert button_colour_problems(link, "secondary") == []


def test_ac11_eight_long_names_wrap_without_widening_the_page(
    window: OpenWindow, live_server: str
) -> None:
    page = window(320, 568)
    seed_rooms2(page, players=long_names(8))
    open_catalogue(page, live_server)
    expect_my_rooms_ready(page, 2)

    label = label_of(my_room_of(page, XYZ).get_by_test_id("my-room-players"))
    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )

    assert label is not None
    assert label["lines"] > 1, label
    assert sizes[0] <= sizes[1], sizes


# ---- AC-12: « Mes salons »' states -----------------------------------------------


def test_ac12_while_the_summaries_load_my_rooms_is_hidden_and_takes_no_room(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    seed_rooms2_identities(page)
    HeldRoute(page, SUMMARIES_ROUTE)
    open_catalogue(page, live_server)
    section = page.get_by_test_id("my-rooms")

    expect(section).to_have_attribute("data-state", "loading")
    box = box_of(section)
    gap = box_of(page.get_by_test_id("catalogue-filters")).top
    gap -= box_of(heading_of_column(page)).bottom

    assert section.get_attribute("hidden") is not None
    assert (box.width, box.height) == (0.0, 0.0), box
    assert same_position(gap, 16.0), gap
    expect(page.locator("body")).not_to_contain_text(OLD_LOADING_TEXT)


def test_ac12_an_empty_answer_leaves_my_rooms_hidden_with_no_row(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    seed_rooms2_identities(page)
    answer_json(page, SUMMARIES_ROUTE, 200, [])
    open_catalogue(page, live_server)
    section = page.get_by_test_id("my-rooms")

    expect(section).to_have_attribute("data-state", "ready")
    assert section.get_attribute("hidden") is not None
    expect(page.get_by_test_id("my-room")).to_have_count(0)
    expect(section).to_be_hidden()


def test_ac12_a_failed_request_shows_the_heading_then_the_error_line(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    seed_rooms2_identities(page)
    answer_json(page, SUMMARIES_ROUTE, 500, {"detail": "Internal Server Error"})
    open_catalogue(page, live_server)
    section = page.get_by_test_id("my-rooms")

    expect(section).to_have_attribute("data-state", "error")
    wait_for_fonts(page)
    error = section.get_by_test_id("my-rooms-error")
    expect(section.locator("h2")).to_be_visible()
    expect(error).to_have_text(fr_value("my_rooms.error"))
    sequence = [child["tag"] for child in children_of(section)]

    assert sequence[:1] == ["H2"], sequence
    assert error_line_problems(error) == []
    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready"
    )


def test_ac12_fr_json_has_neither_the_loading_nor_the_empty_text() -> None:
    fr = load_fr()

    assert "my_rooms.loading" not in fr
    assert "my_rooms.empty" not in fr


# ---- AC-13: « Grilles terminées » --------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac13_the_history_is_the_last_section_16_px_under_the_list(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_hist2(window, live_server, (width, height))
    column = page.get_by_test_id("catalogue-column")

    children = children_of(column)
    gap = to_box(children[-1]["box"]).top - to_box(children[-2]["box"]).bottom

    assert children[-1]["testId"] == "history", children
    assert children[-2]["testId"] == "catalogue-list", children
    assert same_position(gap, 16.0), gap


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac13_the_heading_and_the_rows_have_the_look_of_my_rooms(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_hist2(window, live_server, (width, height))
    heading = page.get_by_test_id("history").locator("h2")

    rows = [history_item_of(page, XYZ), history_item_of(page, OLD_CODE)]

    expect(heading).to_have_text(fr_value("history.heading"))
    assert section_heading_problems(heading) == []
    assert rows_problems(rows) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac13_a_rows_title_is_its_grid_and_size_in_700(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_hist2(window, live_server, (width, height))
    title = history_item_of(page, XYZ).get_by_test_id("history-title")

    assert title.evaluate("element => element.tagName") == "H3"
    assert sequence_of(title) == [GRID_2, SEP, f"5 {TIMES} 5"]
    assert separator_problems(title) == []
    assert style_of(title, "fontWeight") == "700"


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac13_the_line_holds_the_date_the_time_and_the_team_between_separators(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_hist2(window, live_server, (width, height))
    row = history_item_of(page, XYZ)
    line = row.get_by_test_id("history-line")

    expect(line.get_by_test_id("history-date")).to_have_text(
        "Termin\N{LATIN SMALL LETTER E WITH ACUTE}e le 14 octobre 2026"
    )
    expect(line.get_by_test_id("history-time")).to_have_text("en 12 min 34 s")
    expect(line.get_by_test_id("history-teammates")).to_have_text("Avec Bob, Cy")
    assert sequence_of(line) == [
        "#history-date",
        SEP,
        "#history-time",
        SEP,
        "#history-teammates",
    ]
    assert separator_problems(line) == []
    assert font_problems(line, "history-line", 13.6, colour=MUTED) == []


def test_ac13_on_a_computer_the_three_texts_are_on_one_line(
    window: OpenWindow, live_server: str
) -> None:
    page = open_hist2(window, live_server, WIDE)
    line = history_item_of(page, XYZ).get_by_test_id("history-line")

    boxes = [
        box_of(line.get_by_test_id(test_id))
        for test_id in ("history-date", "history-time", "history-teammates")
    ]

    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            assert first.top < second.bottom, boxes
            assert second.top < first.bottom, boxes


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac13_the_replay_is_a_secondary_button_on_the_right(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_hist2(window, live_server, (width, height))
    row = history_item_of(page, XYZ)
    replay = row.get_by_test_id("history-replay")

    assert on_the_right(row, replay), (box_of(row), box_of(replay))
    assert button_colour_problems(replay, "secondary") == []
    expect(
        history_item_of(page, OLD_CODE).get_by_test_id("history-replay")
    ).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac13_a_failed_replay_shows_the_error_line_under_the_rows_line(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    seed_hist2(page)
    fail_play(page)
    open_catalogue(page, live_server)
    expect_history_count(page, 2)
    row = history_item_of(page, XYZ)

    row.get_by_test_id("history-replay").click()

    error = row.get_by_test_id("history-error")
    expect(error).to_be_visible()
    wait_for_fonts(page)
    line_box = box_of(row.get_by_test_id("history-line"))
    assert box_of(error).top >= line_box.bottom - 1.0, (box_of(error), line_box)
    assert font_problems(error, "history-error", 13.6, colour=RED) == []
