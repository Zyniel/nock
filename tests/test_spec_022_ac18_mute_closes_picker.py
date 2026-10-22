"""Tests of spec 022, AC-18: a mute closes the reaction picker and moves the focus
off the disabled chat controls.

Browser with spec 025's mocked socket, on a FX-01 snapshot with `seq` 5 in which
`p2` is host (so `you`, `p1`, is not), at 1280 by 720 and at 360 by 740. "The mute"
is the mock's `player_muted` with seq 6 for `p1`, `muted` true.

"Within 300 ms" is one deadline for all the checks of a case, counted from the
moment the mock sends the mute (second review of spec 022): `send_mute` notes it
just before the frame is sent, and every check then gets the time left to it
(`remaining_ms`), not 300 ms of its own. A check that is already true when its turn
comes passes at once, even after the deadline.

In the second picker run the clue cell (2, 0) is tapped before the panel is
opened (the state is the one the criterion describes: panel open, VIDE selected,
picker open, its first option focused), so that the tap cannot depend on where the
panel is drawn on a narrow window.

Refined by spec 043 (the design's room layout): the second picker run is at 1280
by 720 only (the column layout, where the Salon and the picker may be open
together; in the sheet layout the picker closes the Salon), with the Salon open on
its Discussion tab, and checks `salon`'s box where it checked `chat-panel`'s.

Timing: the 300 ms are the criterion's and are counted on the test's side. The
checks of a case pass within about 10 to 100 ms of the mute on a busy machine, but a
heavier load can break the bound: the file is a candidate for the gate's serial
pass.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import PlayerMuted
from spec021_harness import VIDE, select_word
from spec022_harness import (
    frames_of_type,
    open_chat_room,
    open_panel,
    remaining_ms,
    three_players,
    wait_for_reading,
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
  const panel = document.querySelector('[data-testid="salon"]');
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


def send_mute(mock: MockRoomSocket) -> float:
    """The mock tells the page that `you` (`p1`) is muted.

    Returns:
        The case's deadline, a `time.monotonic` value: 300 ms after the moment
        just before the frame is sent.
    """
    deadline = time.monotonic() + WITHIN_MS / 1000
    event = PlayerMuted(seq=MUTE_SEQ, player_id="p1", muted=True)
    mock.send(event.model_dump_json())
    return deadline


def active_element(page: Page) -> str | None:
    """What has the focus now: its `data-testid`, else its tag name."""
    found = page.evaluate(ACTIVE_SCRIPT)
    assert found is None or isinstance(found, str), found
    return found


def expect_focus_on(page: Page, test_id: str, deadline: float) -> None:
    """Wait until the deadline for the focus to be on `test_id`, else fail.

    The focus is read every few milliseconds, and once more at the deadline.
    """
    wait_for_reading(page, lambda: active_element(page), test_id, deadline)


def expect_picker_closed_by_the_mute(
    page: Page, mock: MockRoomSocket, deadline: float
) -> None:
    """The checks of the first two cases after the mute, but the focus and the box."""
    picker = page.get_by_test_id("reaction-picker")
    expect(picker).to_have_count(0, timeout=remaining_ms(deadline))
    react_button = page.get_by_test_id("react-button")
    expect(react_button).to_be_disabled(timeout=remaining_ms(deadline))
    expect(react_button).to_have_attribute(
        "aria-expanded", "false", timeout=remaining_ms(deadline)
    )
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

        deadline = send_mute(mock)
        expect_picker_closed_by_the_mute(page, mock, deadline)
        expect_focus_on(page, "grid", deadline)
    finally:
        close()


def test_ac18_browser_a_mute_closes_the_picker_and_keeps_the_open_salon(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
) -> None:
    page, mock, close = open_room_where_you_are_not_host(
        browser, browser_name, live_server, fx01_grid, 1280, 720
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

        deadline = send_mute(mock)
        expect_picker_closed_by_the_mute(page, mock, deadline)
        expect_focus_on(page, "grid", deadline)
        salon = page.get_by_test_id("salon")
        expect(salon).to_be_visible(timeout=remaining_ms(deadline))
        panel_after = page.evaluate(PANEL_BOX_SCRIPT)
    finally:
        close()

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

        deadline = send_mute(mock)
        expect(chat_input).to_be_disabled(timeout=remaining_ms(deadline))
        send = page.get_by_test_id("chat-send")
        expect(send).to_be_disabled(timeout=remaining_ms(deadline))
        muted_note = page.get_by_test_id("chat-muted")
        expect(muted_note).to_be_visible(timeout=remaining_ms(deadline))
        panel = page.get_by_test_id("chat-panel")
        expect(panel).to_have_count(1, timeout=remaining_ms(deadline))
        expect(chat_input).to_have_value("salut", timeout=remaining_ms(deadline))
        expect_focus_on(page, "chat-toggle", deadline)
    finally:
        close()


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

        deadline = send_mute(mock)
        expect(send).to_be_disabled(timeout=remaining_ms(deadline))
        expect(chat_input).to_be_disabled(timeout=remaining_ms(deadline))
        muted_note = page.get_by_test_id("chat-muted")
        expect(muted_note).to_be_visible(timeout=remaining_ms(deadline))
        panel = page.get_by_test_id("chat-panel")
        expect(panel).to_have_count(1, timeout=remaining_ms(deadline))
        expect(chat_input).to_have_value("salut", timeout=remaining_ms(deadline))
        expect_focus_on(page, "chat-toggle", deadline)
    finally:
        close()
