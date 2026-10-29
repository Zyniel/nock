"""Tests of `client/hud.md` AC-21 and AC-22: the room-gone dialog (rule 16).

AC-21: once the room has shown, the 4404 of a deleted room closes the Salon sheet,
takes every band away, drops the letter waiting to be sent and shows a modal
alert dialog named « Ce salon n'existe plus. », described by the 30-day line,
whose one control, the link « Voir les grilles » to `/`, takes the focus. The two
cases of the criterion: joined at 360 by 740 with the Salon sheet open, and
reconnecting at 1280 by 720 with `T` typed at (1, 0) and not yet answered. Both
follow « Room gone » (`_design/overlays.md`) and pass spec 035's contrast and
language scans. From "Edge cases": a 4404 before the first snapshot shows no
dialog (the entry card is `client/shell.md`'s, tested by spec 040).

AC-22: under the dialog, with (1, 0) selected, Escape, a press on the scrim, Tab
and Shift+Tab leave the focus on the link and the dialog open; a typed `A`
leaves (1, 0) empty; a press on the link loads `/`.

Readings where the spec leaves room are in `hud_harness`. Also:

- "The sheet closes": `salon` has the `hidden` attribute (spec 043's reading).
- AC-22 runs in both layouts. "A press on the scrim" is a click at the centre of
  a letter cell outside the dialog's box, so that a press reaching the room would
  select that cell; "nothing changes" is read 300 ms after the action: the dialog
  still shows, the link has the focus and (1, 0) is still selected.
- The letter `A` is typed with the key `a`, as the grid takes lower case.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from hud_harness import (
    GONE_DETAIL,
    GONE_TITLE,
    HOME_LINK_NAME,
    GonePage,
    content_problems,
    delete_room,
    delete_while_joined_with_the_salon_open,
    delete_while_reconnecting_with_t_pending,
    expect_dialog_as_rule_16_says,
    expect_no_band,
    expect_room_gone_dialog,
    frame_problems,
    home_link,
    open_fx01_room,
    room_gone_dialog,
    scrim_press_point,
    scrim_problems,
)
from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec024_harness import contrast_problems, language_data, language_problems
from spec042_harness import wait_until
from spec043_harness import (
    COMPUTER,
    DISPLAY_NICKNAMES,
    PHONE,
    QUIET_MS,
    ROOM_CODE,
    RoomMock,
    cell_at,
    expect_closed,
    expect_layout,
    expect_selected,
    fr_value,
    press_cell,
    set_timeouts,
)

OpenGone = Callable[[Page, str, Grid], GonePage]

# The two cases of AC-21: how the page meets the deletion, and its window.
GONE_CASES: list[tuple[OpenGone, tuple[int, int]]] = [
    (delete_while_joined_with_the_salon_open, PHONE),
    (delete_while_reconnecting_with_t_pending, COMPUTER),
]
LAYOUT_OF_SIZE = {PHONE: "sheet", COMPUTER: "column"}
GONE_IDS = ["joined-360x740", "reconnecting-1280x720"]

SIZES = [PHONE, COMPUTER]
SIZE_IDS = ["360x740", "1280x720"]
KEPT_ACTIONS = ["Escape", "scrim", "Tab", "Shift+Tab"]

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    """Return the fixture grid FX-01, parsed."""
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_gone(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    open_case: OpenGone,
    size: tuple[int, int],
) -> GonePage:
    """Open one case of AC-21 in a desktop window of `size`, room deleted."""
    page = window(size[0], size[1], False)
    return open_case(page, base_url, grid)


def delete_with_1_0_selected(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    """AC-22's page: joined on FX-01, (1, 0) selected, the room deleted."""
    page = window(size[0], size[1], False)
    mock = open_fx01_room(page, base_url, grid)
    press_cell(page, 1, 0)
    delete_room(mock)
    expect_room_gone_dialog(page)
    expect(home_link(page)).to_be_focused()
    return page


# ---- AC-21: the strings ----------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("room.gone.title", GONE_TITLE),
        ("room.status.not_found_detail", GONE_DETAIL),
        ("share.home", HOME_LINK_NAME),
    ],
)
def test_ac21_fr_json_holds_the_dialogs_texts(key: str, value: str) -> None:
    assert fr_value(key) == value


# ---- AC-21: the deletion while joined, and while reconnecting --------------------


def test_ac21_joined_with_the_salon_sheet_open_the_deletion_shows_the_dialog(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    gone = open_gone(
        window, live_server, fx01_grid, delete_while_joined_with_the_salon_open, PHONE
    )
    page = gone.page

    expect_dialog_as_rule_16_says(page)
    expect_layout(page, "sheet")
    expect_closed(page.get_by_test_id("salon"))
    expect_no_band(gone)


def test_ac21_reconnecting_the_deletion_drops_the_pending_t_and_shows_the_dialog(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    gone = open_gone(
        window,
        live_server,
        fx01_grid,
        delete_while_reconnecting_with_t_pending,
        COMPUTER,
    )
    page = gone.page

    expect_dialog_as_rule_16_says(page)
    expect_layout(page, "column")
    expect_no_band(gone)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "")


# ---- AC-21: the look and the scans ------------------------------------------------


@pytest.mark.parametrize(("open_case", "size"), GONE_CASES, ids=GONE_IDS)
def test_ac21_the_dialog_has_the_recaps_frame_over_the_dialog_scrim(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    open_case: OpenGone,
    size: tuple[int, int],
) -> None:
    gone = open_gone(window, live_server, fx01_grid, open_case, size)
    expect_room_gone_dialog(gone.page)

    problems = frame_problems(gone.page, LAYOUT_OF_SIZE[size])
    problems += scrim_problems(gone)

    assert problems == []


@pytest.mark.parametrize(("open_case", "size"), GONE_CASES, ids=GONE_IDS)
def test_ac21_the_dialog_holds_its_title_line_and_primary_link_in_order(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    open_case: OpenGone,
    size: tuple[int, int],
) -> None:
    gone = open_gone(window, live_server, fx01_grid, open_case, size)
    expect_room_gone_dialog(gone.page)

    assert content_problems(gone.page) == []


@pytest.mark.parametrize(("open_case", "size"), GONE_CASES, ids=GONE_IDS)
def test_ac21_the_room_stays_drawn_under_the_dialog(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    open_case: OpenGone,
    size: tuple[int, int],
) -> None:
    gone = open_gone(window, live_server, fx01_grid, open_case, size)
    page = gone.page
    expect_room_gone_dialog(page)

    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(page.get_by_test_id("grid")).to_be_visible()
    expect(page.get_by_test_id("room-topbar")).to_be_visible()
    expect(page.get_by_test_id("clue-bar")).to_be_visible()


@pytest.mark.parametrize(("open_case", "size"), GONE_CASES, ids=GONE_IDS)
def test_ac21_the_contrast_scan_finds_no_offender(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    open_case: OpenGone,
    size: tuple[int, int],
) -> None:
    gone = open_gone(window, live_server, fx01_grid, open_case, size)
    expect_room_gone_dialog(gone.page)

    assert contrast_problems(gone.page) == []


@pytest.mark.parametrize(("open_case", "size"), GONE_CASES, ids=GONE_IDS)
def test_ac21_the_language_scan_finds_no_offender(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    open_case: OpenGone,
    size: tuple[int, int],
) -> None:
    gone = open_gone(window, live_server, fx01_grid, open_case, size)
    page = gone.page
    expect_room_gone_dialog(page)
    expect(page.locator("html")).to_have_attribute("lang", "fr")

    data = language_data(live_server, DISPLAY_NICKNAMES)

    assert language_problems(page, data) == []


# ---- AC-21, edge case: before the first snapshot ------------------------------------


def test_ac21_a_4404_before_the_first_snapshot_shows_no_dialog(
    page: Page, live_server: str
) -> None:
    mock = RoomMock()
    set_timeouts(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{live_server}/r/{ROOM_CODE}")
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana")
    expect(nickname_input).to_have_value("Ana")
    nickname_input.press("Enter")
    wait_until(page, lambda: mock.has_join_after(0), "the join")

    delete_room(mock)

    expect(room).to_have_attribute("data-status", "not_found")
    expect(room).to_have_attribute("data-seq", "")
    page.wait_for_timeout(QUIET_MS)
    expect(room_gone_dialog(page)).to_have_count(0)


# ---- AC-22: the room under the dialog is inert -----------------------------------


@pytest.mark.parametrize("action", KEPT_ACTIONS)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac22_escape_a_press_on_the_scrim_and_tab_keep_the_focus_and_the_dialog(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    action: str,
) -> None:
    page = delete_with_1_0_selected(window, live_server, fx01_grid, size)

    if action == "scrim":
        x, y = scrim_press_point(page, (1, 0))
        page.mouse.click(x, y)
    else:
        page.keyboard.press(action)
    page.wait_for_timeout(QUIET_MS)

    expect(room_gone_dialog(page)).to_be_visible()
    expect(home_link(page)).to_be_focused()
    expect_selected(page, 1, 0)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac22_a_typed_a_leaves_the_selected_cell_empty(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = delete_with_1_0_selected(window, live_server, fx01_grid, size)

    page.keyboard.press("a")
    page.wait_for_timeout(QUIET_MS)

    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "")
    expect(room_gone_dialog(page)).to_be_visible()


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac22_a_press_on_the_link_loads_the_catalogue(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = delete_with_1_0_selected(window, live_server, fx01_grid, size)

    home_link(page).click()

    expect(page).to_have_url(f"{live_server}/")
