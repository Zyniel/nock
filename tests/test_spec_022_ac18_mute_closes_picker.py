"""Tests of spec 022, AC-18: a mute closes the reaction picker and moves the focus
off the disabled chat controls.

Browser with spec 025's mocked socket, on a FX-01 snapshot with `seq` 5 in which
`p2` is host (so `you`, `p1`, is not), at 1280 by 720 and at 360 by 740. "The mute"
is the mock's `player_muted` with seq 6 for `p1`, `muted` true. Every reading
after the mute is made within 300 ms.

In the second picker run the clue cell (2, 0) is tapped before the panel is
opened (the state is the one the criterion describes: panel open, VIDE selected,
picker open, its first option focused), so that the tap cannot depend on where the
panel is drawn on a narrow window.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, expect
from playwright.sync_api import Error as PlaywrightError

from nock.grid import Grid
from nock.protocol import PlayerMuted
from spec021_harness import VIDE, select_word
from spec022_harness import (
    frames_of_type,
    open_chat_room,
    open_panel,
    three_players,
)
from spec024_harness import grid_from_text, open_context_page
from spec025_harness import MockRoomSocket

SIZES = [(1280, 720), (360, 740)]
WITHIN_MS = 300
TOLERANCE_PX = 1.0
MUTE_SEQ = 6

# What has the focus: its `data-testid`, else its tag name.
ACTIVE_SCRIPT = r"""
() => {
  const active = document.activeElement;
  if (active === null) {
    return null;
  }
  return active.getAttribute('data-testid') || active.tagName;
}
"""
PANEL_BOX_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="chat-panel"]');
  if (panel === null) {
    return null;
  }
  const box = panel.getBoundingClientRect();
  return [box.left, box.top, box.width, box.height];
}
"""


def size_ids() -> list[str]:
    return [f"{width}x{height}" for width, height in SIZES]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def open_room_where_you_are_not_host(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
) -> tuple[Page, MockRoomSocket, Callable[[], None]]:
    """A desktop page at one size, joined; the page, its mock and its closer."""
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        players = three_players(host="p2")
        mock = open_chat_room(page, live_server, grid, seq=5, players=players)
    except BaseException:
        close()
        raise
    return page, mock, close


def send_mute(mock: MockRoomSocket) -> None:
    """The mock tells the page that `you` (`p1`) is muted."""
    event = PlayerMuted(seq=MUTE_SEQ, player_id="p1", muted=True)
    mock.send(event.model_dump_json())


def focus_reaches(page: Page, test_id: str) -> str | None:
    """Wait up to 300 ms for the focus to be on `test_id`; what has it then."""
    script = f"""() => {{
      const active = document.activeElement;
      return active !== null && active.getAttribute('data-testid') === '{test_id}';
    }}"""
    with contextlib.suppress(PlaywrightError):
        page.wait_for_function(script, timeout=WITHIN_MS)
    return page.evaluate(ACTIVE_SCRIPT)


def expect_picker_closed_by_the_mute(page: Page, mock: MockRoomSocket) -> None:
    """The checks of the first two cases after the mute, but the panel's box."""
    expect(page.get_by_test_id("reaction-picker")).to_have_count(0, timeout=WITHIN_MS)
    react_button = page.get_by_test_id("react-button")
    expect(react_button).to_be_disabled(timeout=WITHIN_MS)
    expect(react_button).to_have_attribute("aria-expanded", "false", timeout=WITHIN_MS)
    assert frames_of_type(mock, "react") == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids())
def test_ac18_browser_a_mute_closes_the_picker_and_focuses_the_grid(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, mock, close = open_room_where_you_are_not_host(
        browser, browser_name, live_server, fx01_grid, width, height
    )
    try:
        select_word(page, VIDE)
        page.get_by_test_id("react-button").click()
        expect(page.get_by_test_id("reaction-picker")).to_be_visible()
        first_option = page.get_by_test_id("reaction-option").first
        expect(first_option).to_be_focused()

        send_mute(mock)
        expect_picker_closed_by_the_mute(page, mock)
        active = focus_reaches(page, "grid")
    finally:
        close()

    assert active == "grid"


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids())
def test_ac18_browser_a_mute_closes_the_picker_and_keeps_the_open_panel(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, mock, close = open_room_where_you_are_not_host(
        browser, browser_name, live_server, fx01_grid, width, height
    )
    try:
        select_word(page, VIDE)
        open_panel(page)
        page.get_by_test_id("react-button").click()
        expect(page.get_by_test_id("reaction-picker")).to_be_visible()
        expect(page.get_by_test_id("reaction-option").first).to_be_focused()
        expect(page.get_by_test_id("chat-panel")).to_be_visible()
        page.wait_for_timeout(300)
        panel_before = page.evaluate(PANEL_BOX_SCRIPT)

        send_mute(mock)
        expect_picker_closed_by_the_mute(page, mock)
        active = focus_reaches(page, "grid")
        panel_after = page.evaluate(PANEL_BOX_SCRIPT)
    finally:
        close()

    assert active == "grid"
    assert panel_before is not None
    assert panel_after is not None
    for before, after in zip(panel_before, panel_after, strict=True):
        assert abs(before - after) <= TOLERANCE_PX, (panel_before, panel_after)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids())
def test_ac18_browser_a_mute_moves_the_focus_from_chat_input_to_the_toggle(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, mock, close = open_room_where_you_are_not_host(
        browser, browser_name, live_server, fx01_grid, width, height
    )
    try:
        open_panel(page)
        chat_input = page.get_by_test_id("chat-input")
        expect(chat_input).to_be_focused()
        page.keyboard.type("salut")

        send_mute(mock)
        expect(chat_input).to_be_disabled(timeout=WITHIN_MS)
        expect(page.get_by_test_id("chat-send")).to_be_disabled(timeout=WITHIN_MS)
        expect(page.get_by_test_id("chat-muted")).to_be_visible(timeout=WITHIN_MS)
        active = focus_reaches(page, "chat-toggle")
        panel_count = page.get_by_test_id("chat-panel").count()
        typed = chat_input.input_value()
    finally:
        close()

    assert active == "chat-toggle"
    assert panel_count == 1
    assert typed == "salut"


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids())
def test_ac18_browser_a_mute_moves_the_focus_from_chat_send_to_the_toggle(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, mock, close = open_room_where_you_are_not_host(
        browser, browser_name, live_server, fx01_grid, width, height
    )
    try:
        open_panel(page)
        chat_input = page.get_by_test_id("chat-input")
        expect(chat_input).to_be_focused()
        page.keyboard.type("salut")
        page.keyboard.press("Tab")
        send = page.get_by_test_id("chat-send")
        expect(send).to_be_focused()
        expect(send).to_be_enabled()

        send_mute(mock)
        expect(send).to_be_disabled(timeout=WITHIN_MS)
        expect(chat_input).to_be_disabled(timeout=WITHIN_MS)
        expect(page.get_by_test_id("chat-muted")).to_be_visible(timeout=WITHIN_MS)
        active = focus_reaches(page, "chat-toggle")
        panel_count = page.get_by_test_id("chat-panel").count()
        typed = chat_input.input_value()
    finally:
        close()

    assert active == "chat-toggle"
    assert panel_count == 1
    assert typed == "salut"
