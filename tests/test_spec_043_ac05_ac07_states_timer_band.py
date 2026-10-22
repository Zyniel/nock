"""Tests of spec 043, AC-5 to AC-7: the top-bar buttons' states, the timer, and the
connection and status bands.

AC-5: the expanded and pressed looks, the unread badge `chat-unread` and the
new-events dot `salon-dot` (work package WP-2) with `chat-toggle`'s `aria-label`,
in both top bars. Also tested, from "Edge cases and errors" (AC-5, AC-17): a
message wins over the dot both ways, and catch-up lines (spec 034) count as new
events.

Choices where the spec leaves room:

- "Makes no `salon-dot`" is read 300 ms after the page applied the event (its
  `data-seq`), as spec 043's other "sends nothing" checks wait.
- The catch-up case runs at 360 by 740 (the Salon closed at load), with spec 034's
  mocked socket and route: `seen_seq` 5 stored, a snapshot at 9 and one check line
  by `p2` (seq 8) in the catch-up.

- A button's pressed look is read with the pointer moved off the top bar, so that
  no hover style is read in its place.
- AC-6, "no Tab stop": the timer's `tabIndex` is negative (it is no control and
  has no `tabindex` of 0 or more).
- AC-6, "the box of a top-bar button at the timer's place": in the phone top bar
  56 by 53 px (AC-2), in the computer top bar 38 px high (AC-3); in both, left of
  `undo-button`, and in the computer top bar right of `topbar-brand`.
- AC-7, "the band's content top" is its top plus its top padding (8 px); the text's
  font values are those of the element that holds the text. The page reconnects
  on its own after the close (spec 017); the test waits up to 10 s for its join.
- AC-7's second run closes the socket with the normal code 1000 after the `error`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import ErrorCode
from room_panels import open_menu, show_tab
from spec019_harness import OpenWindow, window_opener
from spec034_harness import (
    BOB,
    CatchUpRoute,
    catch_up_json,
    check_line,
    expect_catch_up_applied,
    open_mocked_room,
    record_with,
)
from spec042_harness import box_of, colour_of
from spec043_harness import (
    CLUE_BG,
    INK,
    LINE,
    QUIET_MS,
    RED,
    WHITE,
    WORD,
    RoomMock,
    border_problems,
    chat_frame,
    check_frame,
    colour_matches,
    error_frame,
    expect_closed,
    expect_colour,
    focused_test_id,
    fr_format,
    fr_value,
    frames_sent_after,
    fx01_view,
    icon_problems,
    label_of,
    open_room,
    padding_matches,
    parts_of,
    players_up_to,
    reading_box,
    reload_room,
    same_font_size,
    same_position,
    same_size,
    seed_value,
    send_and_wait,
    show_snapshot,
    shown_test_ids,
    snapshot_frame,
    stored_value,
    style_of,
)

POPOVER_BUTTONS = {
    "aide-button": "aide-menu",
    "chat-toggle": "salon",
    "menu-button": "room-menu",
}
TIMER_STORAGE_KEY = "nock.timer_hidden"
RECONNECT_TIMEOUT_MS = 10_000
SIZES = [(360, 740), (1280, 720)]
SIZE_IDS = ["360x740", "1280x720"]

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def fx01_frame(grid: Grid, *, timer_ms: int = 0, running: bool = False) -> str:
    return snapshot_frame(
        fx01_view(grid),
        players_up_to(3),
        timer_elapsed_ms=timer_ms,
        timer_running=running,
    )


def move_pointer_away(page: Page) -> None:
    """Move the pointer to the window's bottom-left corner, off every top-bar button."""
    height = page.evaluate("() => innerHeight")
    page.mouse.move(1, float(height) - 1)


# ---- AC-5: states and the unread badge ----------------------------------------------


def test_ac5_the_popover_buttons_say_what_they_control_and_start_collapsed(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, fx01_frame(fx01_grid))

    for test_id, controlled in POPOVER_BUTTONS.items():
        button = page.get_by_test_id(test_id)
        expect(button).to_have_attribute("aria-expanded", "false")
        expect(button).to_have_attribute("aria-controls", controlled)


def test_ac5_the_clicked_popover_button_is_expanded_and_word_blue_the_others_not(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, fx01_frame(fx01_grid))

    for clicked in POPOVER_BUTTONS:
        page.get_by_test_id(clicked).click()
        move_pointer_away(page)
        expect(page.get_by_test_id(clicked)).to_have_attribute("aria-expanded", "true")
        expect_colour(page.get_by_test_id(clicked), "backgroundColor", WORD)
        for other in POPOVER_BUTTONS:
            if other != clicked:
                expect(page.get_by_test_id(other)).to_have_attribute(
                    "aria-expanded", "false"
                )


def test_ac5_pencil_toggle_shows_its_pressed_state_in_word_blue(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("pencil-toggle")

    toggle.click()
    move_pointer_away(page)

    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect_colour(toggle, "backgroundColor", WORD)


def test_ac5_unread_messages_show_the_red_badge_on_chat_toggle_in_the_phone_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("chat-toggle")

    send_and_wait(page, mock, chat_frame(6, "p2", "Salut"))
    send_and_wait(page, mock, chat_frame(7, "p2", "IDES ?"))

    badge = toggle.get_by_test_id("chat-unread")
    expect(badge).to_have_text("2")
    classes = str(badge.get_attribute("class")).split()
    badge_box = box_of(badge)
    toggle_box = box_of(toggle)
    assert "nock-badge" in classes, classes
    expect_colour(badge, "backgroundColor", RED)
    expect_colour(badge, "color", WHITE)
    assert same_position(badge_box.top, toggle_box.top + 5.0), (badge_box, toggle_box)
    assert same_position(badge_box.right, toggle_box.right - 8.0), (
        badge_box,
        toggle_box,
    )
    expect(toggle).to_have_attribute(
        "aria-label", fr_format("topbar.salon_unread", count=2)
    )


def test_ac5_showing_the_stream_removes_the_badge_and_chat_toggles_label(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("chat-toggle")
    send_and_wait(page, mock, chat_frame(6, "p2", "Salut"))
    expect(toggle.get_by_test_id("chat-unread")).to_have_text("1")

    show_tab(page, "discussion")

    expect(page.get_by_test_id("chat-unread")).to_have_count(0)
    assert toggle.get_attribute("aria-label") is None


def test_ac5_in_the_computer_bar_the_badge_sits_2_px_down_and_24_px_in(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    seed_value(page, "nock.salon_closed", "true")
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("chat-toggle")

    send_and_wait(page, mock, chat_frame(6, "p2", "Salut"))

    badge = toggle.get_by_test_id("chat-unread")
    expect(badge).to_have_text("1")
    badge_box = box_of(badge)
    toggle_box = box_of(toggle)
    assert same_position(badge_box.top, toggle_box.top + 2.0), (badge_box, toggle_box)
    assert same_position(badge_box.left, toggle_box.left + 24.0), (
        badge_box,
        toggle_box,
    )


# ---- AC-5: the new-events dot ---------------------------------------------------


DOT_SCRIPT = r"""
dot => {
  let textNodes = 0;
  const walker = document.createTreeWalker(dot, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    if (node.textContent.trim() !== '') {
      textNodes += 1;
    }
  }
  return {ariaHidden: dot.getAttribute('aria-hidden'), textNodes: textNodes};
}
"""


def expect_no_dot(page: Page) -> None:
    """Wait QUIET_MS, then check that no `salon-dot` is on the page."""
    page.wait_for_timeout(QUIET_MS)
    expect(page.get_by_test_id("salon-dot")).to_have_count(0)


def test_ac5_an_event_line_by_another_player_shows_the_red_dot_in_the_phone_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("chat-toggle")

    send_and_wait(page, mock, check_frame(6, "p2"))

    dot = page.get_by_test_id("salon-dot")
    expect(dot).to_be_visible()
    found = dot.evaluate(DOT_SCRIPT)
    dot_box = box_of(dot)
    toggle_box = box_of(toggle)
    assert same_size(dot_box.width, 8.0), dot_box
    assert same_size(dot_box.height, 8.0), dot_box
    assert style_of(dot, "borderTopLeftRadius") == "50%"
    expect_colour(dot, "backgroundColor", RED)
    assert found == {"ariaHidden": "true", "textNodes": 0}
    assert same_position(dot_box.top, toggle_box.top + 8.0), (dot_box, toggle_box)
    assert same_position(dot_box.right, toggle_box.right - 15.0), (dot_box, toggle_box)
    expect(toggle).to_have_attribute("aria-label", fr_value("topbar.salon_events"))


def test_ac5_a_message_then_hides_the_dot_and_shows_the_badge(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("chat-toggle")
    send_and_wait(page, mock, check_frame(6, "p2"))
    expect(page.get_by_test_id("salon-dot")).to_be_visible()

    send_and_wait(page, mock, chat_frame(7, "p2", "IDES ?"))

    expect(page.get_by_test_id("salon-dot")).to_have_count(0)
    expect(toggle.get_by_test_id("chat-unread")).to_have_text("1")
    expect(toggle).to_have_attribute(
        "aria-label", fr_format("topbar.salon_unread", count=1)
    )


def test_ac5_showing_the_stream_removes_the_dot_the_badge_and_the_label(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("chat-toggle")
    send_and_wait(page, mock, check_frame(6, "p2"))
    expect(page.get_by_test_id("salon-dot")).to_be_visible()
    send_and_wait(page, mock, chat_frame(7, "p2", "IDES ?"))

    show_tab(page, "discussion")

    expect(page.get_by_test_id("salon-dot")).to_have_count(0)
    expect(page.get_by_test_id("chat-unread")).to_have_count(0)
    assert toggle.get_attribute("aria-label") is None


def test_ac5_showing_the_stream_removes_the_dot_alone(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    send_and_wait(page, mock, check_frame(6, "p2"))
    expect(page.get_by_test_id("salon-dot")).to_be_visible()

    show_tab(page, "discussion")
    page.get_by_test_id("chat-toggle").click()
    expect_closed(page.get_by_test_id("salon"))

    expect(page.get_by_test_id("salon-dot")).to_have_count(0)
    assert page.get_by_test_id("chat-toggle").get_attribute("aria-label") is None


def test_ac5_my_own_check_makes_no_dot(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))

    send_and_wait(page, mock, check_frame(6, "p1"))

    expect_no_dot(page)
    assert page.get_by_test_id("chat-toggle").get_attribute("aria-label") is None


def test_ac5_an_event_line_while_a_message_is_unread_makes_no_dot(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("chat-toggle")
    send_and_wait(page, mock, chat_frame(6, "p2", "Salut"))

    send_and_wait(page, mock, check_frame(7, "p2"))

    expect_no_dot(page)
    expect(toggle.get_by_test_id("chat-unread")).to_have_text("1")
    expect(toggle).to_have_attribute(
        "aria-label", fr_format("topbar.salon_unread", count=1)
    )


def test_ac5_in_the_computer_bar_the_dot_sits_at_the_badges_place(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    seed_value(page, "nock.salon_closed", "true")
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    toggle = page.get_by_test_id("chat-toggle")

    send_and_wait(page, mock, check_frame(6, "p2"))

    dot = page.get_by_test_id("salon-dot")
    expect(dot).to_be_visible()
    dot_box = box_of(dot)
    toggle_box = box_of(toggle)
    assert same_position(dot_box.top, toggle_box.top + 2.0), (dot_box, toggle_box)
    assert same_position(dot_box.left, toggle_box.left + 24.0), (dot_box, toggle_box)
    expect(toggle).to_have_attribute("aria-label", fr_value("topbar.salon_events"))


def test_ac5_catch_up_lines_by_another_player_count_as_new_events(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    route = CatchUpRoute(answer=catch_up_json(5, 9, lines=[check_line(8, BOB)]))
    open_mocked_room(page, live_server, fx01_grid, route, record=record_with(5), seq=9)

    expect_catch_up_applied(page, "5-9")

    expect(page.get_by_test_id("salon-dot")).to_be_visible()
    expect(page.get_by_test_id("chat-toggle")).to_have_attribute(
        "aria-label", fr_value("topbar.salon_events")
    )


# ---- AC-6: the timer, hidden from the Menu and shown by « Chrono » -------------------

TIMER_ATTRIBUTES_SCRIPT = r"""
element => ({
  tag: element.tagName,
  role: element.getAttribute('role'),
  tabIndex: element.tabIndex,
})
"""


def test_ac6_the_timer_is_running_text_not_a_button_and_no_tab_stop(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, fx01_frame(fx01_grid, timer_ms=65_000, running=True))
    timer = page.get_by_test_id("timer")

    expect(timer).to_have_text(re.compile(r"^1:0[5-9]$"))
    found = timer.evaluate(TIMER_ATTRIBUTES_SCRIPT)

    assert found["role"] == "timer"
    assert found["tag"] != "BUTTON"
    assert found["tabIndex"] < 0


def open_timer_room(page: Page, base_url: str, grid: Grid) -> RoomMock:
    return open_room(page, base_url, fx01_frame(grid, timer_ms=65_000, running=True))


def hide_from_the_menu(page: Page, mock: RoomMock) -> list[str]:
    """`open_menu`, then a click on `timer-toggle`; return the frames it sent."""
    open_menu(page)
    toggle = page.get_by_test_id("timer-toggle")
    expect(toggle).to_have_text(fr_value("timer.hide"))
    assert toggle.get_attribute("aria-pressed") is None
    return frames_sent_after(page, mock, toggle.click)


def chrono_button_problems(page: Page, phone: bool) -> list[str]:
    """How `timer-show` differs from a top-bar button at the timer's place."""
    parts = parts_of(page.get_by_test_id("timer-show"))
    problems: list[str] = []
    if parts["tag"] != "BUTTON":
        problems.append(f"timer-show is a {parts['tag']}")
    if len(parts["svgs"]) != 1:
        problems.append(f"{len(parts['svgs'])} svg elements")
    else:
        problems.extend(icon_problems(parts["svgs"][0], "chrono"))
    label = parts["label"]
    if label is None or label["text"] != fr_value("timer.label"):
        problems.append(f"label {label}")
    if parts["ariaLabel"] != fr_value("timer.toggle_label"):
        problems.append(f"aria-label {parts['ariaLabel']!r}")
    box = reading_box(parts)
    if phone and not (same_size(box.width, 56.0) and same_position(box.height, 53.0)):
        problems.append(f"phone box {box}")
    if not phone and not same_size(box.height, 38.0):
        problems.append(f"computer box {box}")
    undo_box = box_of(page.get_by_test_id("undo-button"))
    if box.right > undo_box.left + 1.0:
        problems.append(f"timer-show {box} is not left of undo-button {undo_box}")
    return problems


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac6_the_menu_hides_the_timer_and_chrono_takes_its_place(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    mock = open_timer_room(page, live_server, fx01_grid)

    frames = hide_from_the_menu(page, mock)

    expect_closed(page.get_by_test_id("room-menu"))
    assert focused_test_id(page) == "menu-button"
    expect(page.get_by_test_id("timer")).to_have_count(0)
    expect(page.get_by_test_id("timer-show")).to_be_visible()
    assert chrono_button_problems(page, phone=width < 500) == []
    assert stored_value(page, TIMER_STORAGE_KEY) == "true"
    assert frames == []
    expect(page.get_by_test_id("timer-toggle")).to_have_text(
        fr_value("timer.toggle_label")
    )


def test_ac6_in_the_computer_bar_chrono_comes_between_the_brand_and_undo(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_timer_room(page, live_server, fx01_grid)
    hide_from_the_menu(page, mock)
    expect(page.get_by_test_id("timer-show")).to_be_visible()

    shown = shown_test_ids(page.get_by_test_id("room-topbar"))

    assert shown[:3] == ["topbar-brand", "timer-show", "undo-button"], shown


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac6_after_a_reload_chrono_shows_and_a_click_shows_the_timer_again(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    mock = open_timer_room(page, live_server, fx01_grid)
    hide_from_the_menu(page, mock)

    reload_room(page, mock, fx01_frame(fx01_grid, timer_ms=65_000, running=True))
    expect(page.get_by_test_id("timer-show")).to_be_visible()
    frames = frames_sent_after(page, mock, page.get_by_test_id("timer-show").click)

    expect(page.get_by_test_id("timer")).to_be_visible()
    expect(page.get_by_test_id("timer-show")).to_have_count(0)
    assert stored_value(page, TIMER_STORAGE_KEY) is None
    assert frames == []
    expect(page.get_by_test_id("timer-toggle")).to_have_text(fr_value("timer.hide"))


# ---- AC-7: the connection band and the status band -----------------------------------


def wait_for_rejoin(page: Page, mock: RoomMock, frames_before: int) -> None:
    """Wait until the page joined again on a new socket (spec 017)."""
    waited_ms = 0
    while not mock.has_join_after(frames_before):
        if waited_ms >= RECONNECT_TIMEOUT_MS:
            pytest.fail("the page did not join again")
        page.wait_for_timeout(100)
        waited_ms += 100


def lose_connection(page: Page, mock: RoomMock) -> int:
    """Close the socket with 1011; return the frame count before the close."""
    frames_before = len(mock.received)
    mock.close(1011)
    expect(page.get_by_test_id("connection-banner")).to_be_visible(timeout=5000)
    return frames_before


def band_problems(page: Page, width: int) -> list[str]:
    """How `connection-banner` differs from the band of AC-7."""
    band = page.get_by_test_id("connection-banner")
    band_box = box_of(band)
    bar_box = box_of(page.get_by_test_id("room-topbar"))
    problems: list[str] = []
    if not same_position(band_box.top, bar_box.bottom):
        problems.append(f"band top {band_box.top}, top bar bottom {bar_box.bottom}")
    if not same_size(band_box.width, float(width)):
        problems.append(f"band width {band_box.width}")
    background = colour_of(band, "backgroundColor")
    if not colour_matches(background, CLUE_BG):
        problems.append(f"band background {background}")
    problems.extend(border_problems(band, "Bottom", "1px", "solid", LINE))
    if not padding_matches(band, "8px 12px"):
        problems.append("band padding is not 8px 12px")
    return problems


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac7_the_connection_band_sits_under_the_top_bar_with_its_look(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))

    lose_connection(page, mock)

    assert band_problems(page, width) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac7_the_band_starts_with_the_red_dot_then_its_ink_text(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    lose_connection(page, mock)
    band = page.get_by_test_id("connection-banner")

    first_child = band.evaluate(
        "e => e.firstElementChild === null ? null"
        " : e.firstElementChild.getAttribute('data-testid')"
    )
    dot = band.get_by_test_id("connection-dot")
    dot_box = box_of(dot)
    band_box = box_of(band)
    label = label_of(band)

    assert first_child == "connection-dot"
    assert same_size(dot_box.width, 8.0), dot_box
    assert same_size(dot_box.height, 8.0), dot_box
    expect_colour(dot, "backgroundColor", RED)
    expect(dot).to_have_attribute("aria-hidden", "true")
    assert same_position(dot_box.top, band_box.top + 8.0 + 5.0), (dot_box, band_box)
    assert label is not None
    assert label["text"] == fr_value("room.banner.offline")
    assert same_font_size(float(str(label["fontSize"]).removesuffix("px")), 13.6)
    assert label["fontWeight"] == "500"
    assert colour_matches(label["colour"], INK), label


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac7_the_band_pushes_the_grid_down_and_leaves_once_the_page_rejoins(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    frame = fx01_frame(fx01_grid)
    mock = open_room(page, live_server, frame)
    grid_area = page.get_by_test_id("grid-area")
    noted_top = box_of(grid_area).top

    frames_before = lose_connection(page, mock)
    band_box = box_of(page.get_by_test_id("connection-banner"))
    pushed_top = box_of(grid_area).top
    status_classes = str(page.get_by_test_id("room-status").get_attribute("class"))
    wait_for_rejoin(page, mock, frames_before)
    show_snapshot(page, mock, frame)

    assert same_position(pushed_top, band_box.bottom), (pushed_top, band_box)
    assert pushed_top > noted_top + 1.0, (pushed_top, noted_top)
    assert "visually-hidden" in status_classes.split()
    expect(page.get_by_test_id("connection-banner")).to_have_count(0)
    assert same_position(box_of(grid_area).top, noted_top)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac7_a_final_status_shows_in_a_band_without_the_dot(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))

    mock.send(error_frame(ErrorCode.REMOVED))
    mock.close(1000)

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "removed")
    status = page.get_by_test_id("room-status")
    expect(status).to_be_visible()
    expect(status).to_have_text(fr_value("room.status.removed"))
    classes = str(status.get_attribute("class")).split()
    status_box = box_of(status)
    bar_box = box_of(page.get_by_test_id("room-topbar"))
    assert "visually-hidden" not in classes
    assert same_position(status_box.top, bar_box.bottom), (status_box, bar_box)
    expect_colour(status, "backgroundColor", CLUE_BG)
    assert border_problems(status, "Bottom", "1px", "solid", LINE) == []
    expect(status.get_by_test_id("connection-dot")).to_have_count(0)
