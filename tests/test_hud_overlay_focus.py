"""Tests of `client/hud.md` AC-23, AC-24 and AC-25: the focus stays where a player
can see it in the room's menus, its Salon sheet and its host sheet (rules 12, 13).

AC-23: at 360 by 740 with MIME selected, Tab on « Le mot », the last item of the
open Aide menu, focuses the grid and closes the menu and its scrim; at 1280 by
720 Shift+Tab on « Auteurs » in the open Menu focuses « Menu » and closes the
Menu; a vote that disables the focused « La grille » leaves the menu open.

AC-24: at 360 by 740 with the Salon sheet open, Shift+Tab on « Discussion » focuses
the clue bar's next-word button and closes the sheet, its scrim and « Salon »'s
expansion. From "Edge cases": Tab on the Salon sheet's last control leaves the page
for the browser and closes nothing; the next Tab into the page closes it.

AC-25: at 1280 by 720 in the host's settings, a press in « Lettres à révéler »
released on the backdrop, or a press on the backdrop released in the sheet, leaves
it open with its values; a press and its release both on the backdrop close it and
focus « Menu ».

Readings where the spec leaves room:

- "The grid" focused is the element `grid` (`document.activeElement`); "the menu
  gone" is the `hidden` attribute on `aide-menu` or `room-menu`, "the scrim gone"
  is `room-scrim` not visible, and "expanded" is the button's `aria-expanded`.
- "The last item of the Aide menu" is `reveal-word`: the focus is put there, as a
  Tab walk would reach it, and then Tab is pressed.
- The edge case of the Salon sheet is engine neutral, since an engine moves the
  focus to the browser's own controls, or to the page's start, or leaves it where
  it is. After each Tab on the last control, the sheet is open exactly when the
  focus is inside it or on no element (`body`); the focus is read until that
  holds, and the Tab goes on while the focus is on no element.
- A drag is `mouse.down` at one point, `mouse.move` and `mouse.up` at another.
  "The backdrop" at 1280 by 720 is left of the centred sheet; "the sheet" is its
  heading. "Closes nothing" is read 300 ms after the release.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from hud_harness import (
    COMPUTER_BACKDROP_POINT,
    centre_of,
    open_fx01_room,
    open_host_sheet,
    press_and_release,
)
from nock.grid import Grid
from nock.protocol import HelpMode
from room_panels import is_closed, open_aide, open_menu, show_tab
from spec019_harness import OpenWindow, window_opener
from spec042_harness import wait_until
from spec043_harness import (
    COMPUTER,
    PHONE,
    QUIET_MS,
    RoomMock,
    expect_closed,
    expect_word,
    fr_value,
    fx01_view,
    open_room,
    players_up_to,
    select_mime,
    send_and_wait,
    snapshot_frame,
    vote_opened_frame,
)

SIZES = [PHONE, COMPUTER]
SIZE_IDS = ["360x740", "1280x720"]
SALON_PRESSES = 4  # more Tabs than any engine needs to come back into the page

# The state of the Salon and of the focus: whether the Salon is open, whether the
# focus is on no element (`body` or nothing), and whether it is inside the Salon.
SALON_FOCUS_SCRIPT = r"""
() => {
  const salon = document.querySelector('[data-testid="salon"]');
  const active = document.activeElement;
  const onNothing = active === null || active === document.body
    || active === document.documentElement;
  return {
    isOpen: !salon.hidden,
    onNothing: onNothing,
    inSalon: !onNothing && salon.contains(active),
  };
}
"""

# Put the focus on the last Tab stop of the Salon: the last control that shows.
FOCUS_LAST_CONTROL_SCRIPT = r"""
salon => {
  const selector = 'a[href], button, input, select, textarea, [tabindex]';
  let last = null;
  for (const element of salon.querySelectorAll(selector)) {
    const shows = element.getClientRects().length > 0;
    if (shows && !element.disabled && element.tabIndex >= 0) {
      last = element;
    }
  }
  last.focus();
  return last.getAttribute('data-testid');
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    """Return the fixture grid FX-01, parsed."""
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_vote_mode_room(page: Page, base_url: str, grid: Grid) -> RoomMock:
    """Open FX-01 in help mode `vote`, Ana the host among 3 players."""
    frame = snapshot_frame(fx01_view(grid), players_up_to(3), help_mode=HelpMode.VOTE)
    return open_room(page, base_url, frame)


def salon_focus(page: Page) -> dict[str, bool]:
    """Read the Salon's state and where the focus is."""
    found = page.evaluate(SALON_FOCUS_SCRIPT)
    assert isinstance(found, dict), found
    return found


def salon_matches_focus(page: Page) -> bool:
    """Whether the Salon is open exactly when the focus is in it or on no element."""
    state = salon_focus(page)
    focus_keeps_it = state["onNothing"] or state["inSalon"]
    return state["isOpen"] == focus_keeps_it


# ---- AC-23: the Aide menu and the Menu --------------------------------------------


def test_ac23_tab_on_the_last_item_of_the_aide_menu_focuses_the_grid_and_closes_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], False)
    open_fx01_room(page, live_server, fx01_grid)
    select_mime(page)
    open_aide(page)
    last_item = page.get_by_test_id("reveal-word")
    expect(last_item).to_be_enabled()
    last_item.focus()
    expect(last_item).to_be_focused()

    page.keyboard.press("Tab")

    expect(page.get_by_test_id("grid")).to_be_focused()
    expect_closed(page.get_by_test_id("aide-menu"))
    expect(page.get_by_test_id("room-scrim")).not_to_be_visible()
    expect(page.get_by_test_id("aide-button")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect_word(page, "0,2,0")


def test_ac23_shift_tab_on_the_first_item_of_the_menu_focuses_menu_and_closes_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    open_fx01_room(page, live_server, fx01_grid)
    open_menu(page)
    first_item = page.get_by_test_id("authors-switch")
    expect(first_item).to_be_focused()

    page.keyboard.press("Shift+Tab")

    expect(page.get_by_test_id("menu-button")).to_be_focused()
    expect_closed(page.get_by_test_id("room-menu"))
    expect(page.get_by_test_id("menu-button")).to_have_attribute(
        "aria-expanded", "false"
    )


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_a_vote_that_disables_the_focused_item_leaves_the_menu_open(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = window(size[0], size[1], False)
    mock = open_vote_mode_room(page, live_server, fx01_grid)
    select_mime(page)
    open_aide(page)
    item = page.get_by_test_id("check-grid")
    expect(item).to_be_enabled()
    item.focus()
    expect(item).to_be_focused()

    send_and_wait(page, mock, vote_opened_frame(6))

    expect(item).to_be_disabled()
    page.wait_for_timeout(QUIET_MS)
    assert not is_closed(page.get_by_test_id("aide-menu"))
    expect(page.get_by_test_id("aide-button")).to_have_attribute(
        "aria-expanded", "true"
    )


# ---- AC-24: the Salon sheet -------------------------------------------------------


def test_ac24_shift_tab_on_discussion_focuses_the_clue_bar_and_closes_the_sheet(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], False)
    open_fx01_room(page, live_server, fx01_grid)
    select_mime(page)
    show_tab(page, "discussion")
    discussion = page.get_by_test_id("salon-tab-discussion")
    discussion.focus()
    expect(discussion).to_be_focused()

    page.keyboard.press("Shift+Tab")

    expect(page.get_by_test_id("clue-next")).to_be_focused()
    expect_closed(page.get_by_test_id("salon"))
    expect(page.get_by_test_id("room-scrim")).not_to_be_visible()
    expect(page.get_by_test_id("chat-toggle")).to_have_attribute(
        "aria-expanded", "false"
    )


def test_ac24_tab_out_of_the_page_closes_nothing_until_the_focus_is_in_the_page(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], False)
    open_fx01_room(page, live_server, fx01_grid)
    show_tab(page, "discussion")
    salon = page.get_by_test_id("salon")
    salon.evaluate(FOCUS_LAST_CONTROL_SCRIPT)
    assert salon_focus(page)["inSalon"]

    for _ in range(SALON_PRESSES):
        page.keyboard.press("Tab")
        wait_until(
            page,
            lambda: salon_matches_focus(page),
            "the Salon open exactly while the focus is in it or on no element",
        )
        state = salon_focus(page)
        if not state["onNothing"]:
            break

    final = salon_focus(page)
    assert final["isOpen"] == final["inSalon"], final


# ---- AC-25: the host's settings and the backdrop ----------------------------------


@pytest.mark.parametrize("start", ["field", "backdrop"])
def test_ac25_a_press_and_release_in_two_places_close_nothing(
    window: OpenWindow, live_server: str, fx01_grid: Grid, start: str
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    open_host_sheet(page, live_server, fx01_grid)
    dialog = page.get_by_test_id("host-settings")
    letters = page.get_by_test_id("reveal-letters-input")
    letters.fill("7")
    expect(letters).to_have_value("7")
    heading = dialog.get_by_role("heading", name=fr_value("settings.heading"))
    if start == "field":
        first_point = centre_of(letters)
        last_point = COMPUTER_BACKDROP_POINT
    else:
        first_point = COMPUTER_BACKDROP_POINT
        last_point = centre_of(heading)

    press_and_release(page, first_point, last_point)
    page.wait_for_timeout(QUIET_MS)

    expect(dialog).to_have_attribute("open", "")
    expect(letters).to_have_value("7")


def test_ac25_a_press_and_release_both_on_the_backdrop_close_it_and_focus_menu(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    open_host_sheet(page, live_server, fx01_grid)
    dialog = page.get_by_test_id("host-settings")
    other_backdrop_point = (60.0, 400.0)

    press_and_release(page, COMPUTER_BACKDROP_POINT, other_backdrop_point)

    expect(dialog).not_to_have_attribute("open", "")
    expect(page.get_by_test_id("menu-button")).to_be_focused()
