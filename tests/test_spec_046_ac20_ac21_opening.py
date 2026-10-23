"""Tests of spec 046, AC-20 and AC-21: the room while it opens, and what follows
the room's answer.

Browser with mocked socket on `/r/ABC123` (spec 043's `RoomMock`). AC-20:
`nock.identity.ABC123` seeded (spec 012's case a) and a mock that never answers
the join, so the page stays `joining`: the room's top bar is in place, `inert`,
with no timer, and `grid-area` holds one muted, centred `room-status` line; when
the mock sends a FX-01 snapshot, the room shows within 300 ms. AC-21:
`nock.room.ABC123` seeded (case b): the opening gives way to the status card on
`room_full`, to the nickname card on `invalid_nickname`, and stays on a close
with 1011 before any snapshot.

Choices where the spec leaves room:

- "Its children that show": the test-id'd elements of `room-topbar` that show,
  outermost first (spec 043's `shown_test_ids`).
- "No `timer` and no `timer-show`": neither is on the page.
- "Holds only `room-status`": the test-id'd elements of `grid-area` that show are
  `room-status` alone.
- In the touch context, `keyboard-toggle` has `aria-pressed="false"` (spec 044's
  note of 2026-10-22: the keyboard does not show before a snapshot).
- AC-21's third run reads the page right after the close: spec 017 retries
  later, and the page keeps the opening meanwhile.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.protocol import ErrorCode
from spec035_harness import build_fx01_grid
from spec042_harness import box_of
from spec043_harness import (
    COMPUTER_BUTTONS,
    MUTED,
    NAVY,
    PHONE_BUTTONS,
    error_frame,
    label_of,
)
from spec044_harness import TOUCH_PHONE_BUTTONS
from spec046_harness import (
    FOLLOW_MS,
    OpenWindow,
    code_line_problems,
    colour_matches,
    entry_home_problems,
    expect_status,
    font_problems,
    fr_value,
    frames_after,
    fx01_snapshot,
    is_visually_hidden,
    no_progress_or_animation,
    open_mocked_room,
    open_opening,
    same_position,
    same_size,
    seed_room_record,
    status_card_problems,
    topbar_ids,
    wait_for_join,
    window_opener,
)

PHONE_DESKTOP = ((360, 740), False)
PHONE_TOUCH = ((360, 740), True)
COMPUTER = ((1280, 720), False)
OPENINGS = [PHONE_DESKTOP, PHONE_TOUCH, COMPUTER]
OPENING_IDS = ["360x740-desktop", "360x740-touch", "1280x720"]
BAR_IDS = {
    "360x740-desktop": PHONE_BUTTONS,
    "360x740-touch": TOUCH_PHONE_BUTTONS,
    "1280x720": ["topbar-brand", *COMPUTER_BUTTONS],
}
ABSENT_IDS = [
    "grid-viewport",
    "clue-bar",
    "keyboard",
    "salon",
    "page-topbar",
    "grid-status",
    "connection-banner",
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_at(
    window: OpenWindow, base_url: str, opening: tuple[tuple[int, int], bool]
) -> Page:
    (width, height), touch = opening
    page = window(width, height, touch)
    open_opening(page, base_url)
    return page


def opening_problems(page: Page, status_key: str) -> list[str]:
    """The opening's frame: the top bar inert, `data-layout`, one status line."""
    problems: list[str] = []
    top_bar = page.get_by_test_id("room-topbar")
    if top_bar.count() != 1:
        return [f"{top_bar.count()} room-topbar elements"]
    if top_bar.get_attribute("inert") is None:
        problems.append("room-topbar is not inert")
    if page.get_by_test_id("room-page").get_attribute("data-layout") is None:
        problems.append("room-page has no data-layout")
    room_status = page.get_by_test_id("room-status")
    if room_status.inner_text().strip() != fr_value(status_key):
        problems.append(f"room-status reads {room_status.inner_text()!r}")
    if is_visually_hidden(room_status):
        problems.append("room-status is visually hidden")
    if page.get_by_test_id("page-topbar").count() != 0:
        problems.append("a page-topbar shows")
    return problems


# ---- AC-20: the top bar -------------------------------------------------------


@pytest.mark.parametrize("opening", OPENINGS, ids=OPENING_IDS)
def test_ac20_the_top_bar_shows_its_buttons_inert_with_no_timer(
    window: OpenWindow,
    live_server: str,
    opening: tuple[tuple[int, int], bool],
) -> None:
    page = open_at(window, live_server, opening)
    case_id = OPENING_IDS[OPENINGS.index(opening)]

    shown = topbar_ids(page)

    assert shown == BAR_IDS[case_id], shown
    assert page.get_by_test_id("room-topbar").get_attribute("inert") is not None
    expect(page.get_by_test_id("timer")).to_have_count(0)
    expect(page.get_by_test_id("timer-show")).to_have_count(0)


@pytest.mark.parametrize("opening", OPENINGS[:2], ids=OPENING_IDS[:2])
def test_ac20_on_a_phone_the_bar_is_54_px_with_its_56_px_buttons_in_place(
    window: OpenWindow, live_server: str, opening: tuple[tuple[int, int], bool]
) -> None:
    page = open_at(window, live_server, opening)
    case_id = OPENING_IDS[OPENINGS.index(opening)]

    bar_box = box_of(page.get_by_test_id("room-topbar"))
    menu_box = box_of(page.get_by_test_id("menu-button"))

    assert same_size(bar_box.height, 54.0), bar_box
    assert same_size(bar_box.width, 360.0), bar_box
    assert same_position(360.0 - menu_box.right, 4.0), menu_box
    for test_id in BAR_IDS[case_id]:
        assert same_size(box_of(page.get_by_test_id(test_id)).width, 56.0), test_id


@pytest.mark.parametrize("opening", OPENINGS, ids=OPENING_IDS)
def test_ac20_the_buttons_labels_are_navy_as_once_joined(
    window: OpenWindow, live_server: str, opening: tuple[tuple[int, int], bool]
) -> None:
    page = open_at(window, live_server, opening)
    case_id = OPENING_IDS[OPENINGS.index(opening)]

    problems: list[str] = []
    for test_id in BAR_IDS[case_id]:
        if test_id == "topbar-brand":
            continue
        label = label_of(page.get_by_test_id(test_id))
        if label is None or not colour_matches(label["colour"], NAVY):
            problems.append(f"{test_id}: label {label}")

    assert problems == []


def test_ac20_on_a_touch_screen_clavier_is_there_not_pressed(
    window: OpenWindow, live_server: str
) -> None:
    page = open_at(window, live_server, PHONE_TOUCH)

    expect(page.get_by_test_id("keyboard-toggle")).to_have_attribute(
        "aria-pressed", "false"
    )


def test_ac20_on_a_computer_the_bar_is_the_56_px_computer_top_bar(
    window: OpenWindow, live_server: str
) -> None:
    page = open_at(window, live_server, COMPUTER)

    bar_box = box_of(page.get_by_test_id("room-topbar"))

    assert same_size(bar_box.height, 56.0), bar_box
    assert same_size(bar_box.width, 1280.0), bar_box


# ---- AC-20: the page under the top bar --------------------------------------------


@pytest.mark.parametrize("opening", OPENINGS, ids=OPENING_IDS)
def test_ac20_the_room_page_has_its_layout_from_the_opening_on(
    window: OpenWindow, live_server: str, opening: tuple[tuple[int, int], bool]
) -> None:
    page = open_at(window, live_server, opening)
    (width, _), _ = opening

    expected = "column" if width == 1280 else "sheet"
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-layout", expected)


@pytest.mark.parametrize("opening", OPENINGS, ids=OPENING_IDS)
def test_ac20_the_grid_area_fills_the_window_under_the_bar_with_one_line(
    window: OpenWindow, live_server: str, opening: tuple[tuple[int, int], bool]
) -> None:
    page = open_at(window, live_server, opening)
    (_, height), _ = opening
    area = page.get_by_test_id("grid-area")

    area_box = box_of(area)
    bar_box = box_of(page.get_by_test_id("room-topbar"))

    assert same_position(area_box.top, bar_box.bottom), (area_box, bar_box)
    assert same_position(area_box.bottom, float(height)), area_box
    assert topbar_ids(page, "grid-area") == ["room-status"]


@pytest.mark.parametrize("opening", OPENINGS, ids=OPENING_IDS)
def test_ac20_room_status_is_a_muted_line_centred_in_the_grid_area(
    window: OpenWindow, live_server: str, opening: tuple[tuple[int, int], bool]
) -> None:
    page = open_at(window, live_server, opening)
    room_status = page.get_by_test_id("grid-area").get_by_test_id("room-status")

    expect(room_status).to_have_text(fr_value("room.status.joining"))
    status_box = box_of(room_status)
    area_box = box_of(page.get_by_test_id("grid-area"))

    assert not is_visually_hidden(room_status)
    assert font_problems(room_status, "room-status", 16.0, colour=MUTED) == []
    assert same_position(status_box.centre_x, area_box.centre_x), status_box
    assert same_position(status_box.centre_y, area_box.centre_y), status_box


@pytest.mark.parametrize("opening", OPENINGS, ids=OPENING_IDS)
def test_ac20_nothing_of_the_room_shows_yet_and_nothing_spins(
    window: OpenWindow, live_server: str, opening: tuple[tuple[int, int], bool]
) -> None:
    page = open_at(window, live_server, opening)
    heading = page.get_by_test_id("room-page").locator("h1")

    expect(heading).to_have_count(1)
    assert is_visually_hidden(heading)
    for test_id in ABSENT_IDS:
        expect(page.get_by_test_id(test_id)).to_have_count(0)
    assert no_progress_or_animation(page) == []


@pytest.mark.parametrize("opening", [PHONE_DESKTOP, COMPUTER], ids=["360", "1280"])
def test_ac20_a_click_on_menu_opens_nothing_and_sends_nothing(
    window: OpenWindow, live_server: str, opening: tuple[tuple[int, int], bool]
) -> None:
    (width, height), touch = opening
    page = window(width, height, touch)
    mock = open_opening(page, live_server)
    menu_box = box_of(page.get_by_test_id("menu-button"))

    sent = frames_after(
        page, mock, lambda: page.mouse.click(menu_box.centre_x, menu_box.centre_y)
    )

    assert sent == []
    expect(page.get_by_test_id("room-menu")).not_to_be_visible()
    # The popovers render only once a snapshot came, so the button itself shows
    # that the click did nothing: it stays closed and never takes the focus.
    menu = page.get_by_test_id("menu-button")
    expect(menu).to_have_attribute("aria-expanded", "false")
    # WebKit never focuses a button on a click, so this check cannot fail there;
    # the `aria-expanded` check above is the one that does the work in WebKit.
    expect(menu).not_to_be_focused()


@pytest.mark.parametrize("opening", OPENINGS, ids=OPENING_IDS)
def test_ac20_the_snapshot_brings_the_room_within_300_ms(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    opening: tuple[tuple[int, int], bool],
) -> None:
    (width, height), touch = opening
    page = window(width, height, touch)
    mock = open_opening(page, live_server)

    mock.send(fx01_snapshot(fx01_grid))

    top_bar = page.get_by_test_id("room-topbar")
    expect(top_bar).not_to_have_attribute("inert", "", timeout=FOLLOW_MS)
    expect(page.get_by_test_id("timer")).to_be_visible()
    expect(page.get_by_test_id("clue-bar")).to_have_count(1)
    expect(page.get_by_test_id("grid-viewport")).to_have_count(1)
    assert top_bar.get_attribute("inert") is None


# ---- AC-21: the opening gives way -------------------------------------------------


def test_ac21_while_unanswered_the_page_shows_the_opening(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    seed_room_record(page)
    mock = open_mocked_room(page, live_server)
    wait_for_join(page, mock)
    expect_status(page, "joining")

    assert opening_problems(page, "room.status.joining") == []


def test_ac21_a_full_room_gives_its_status_card_within_300_ms(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    seed_room_record(page)
    mock = open_mocked_room(page, live_server)
    wait_for_join(page, mock)
    expect(page.get_by_test_id("room-topbar")).to_be_visible()

    mock.send(error_frame(ErrorCode.ROOM_FULL))

    expect(page.get_by_test_id("room-topbar")).to_have_count(0, timeout=FOLLOW_MS)
    assert page.get_by_test_id("room-page").get_attribute("data-layout") is None
    expect_status(page, "full")
    wait_for_fonts(page)
    assert status_card_problems(page, "full") == []
    assert entry_home_problems(page, "secondary") == []


def test_ac21_a_refused_nickname_gives_the_nickname_card_with_its_reason(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    seed_room_record(page)
    mock = open_mocked_room(page, live_server)
    wait_for_join(page, mock)
    expect(page.get_by_test_id("room-topbar")).to_be_visible()

    mock.send(error_frame(ErrorCode.INVALID_NICKNAME))

    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    wait_for_fonts(page)
    expect(page.get_by_test_id("nickname-error")).to_have_text(
        fr_value("join.error.characters")
    )
    expect(page.get_by_test_id("room-topbar")).to_have_count(0)
    assert code_line_problems(page, "ABC123") == []


def test_ac21_a_close_before_any_snapshot_keeps_the_opening_with_no_banner(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    seed_room_record(page)
    mock = open_mocked_room(page, live_server)
    wait_for_join(page, mock)
    expect(page.get_by_test_id("room-topbar")).to_be_visible()

    mock.close(1011)

    expect_status(page, "connecting")
    assert opening_problems(page, "room.status.connecting") == []
    expect(page.get_by_test_id("connection-banner")).to_be_hidden()
