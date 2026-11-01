"""Tests of `account/account.md` AC-34: the account sheet closes on a press and its
release both on the backdrop (rule 14), in a room and on the catalogue.

AC-34: in a room at 1280 by 720 and on the catalogue at 360 by 740, with `lea@exa`
typed in the account sheet, a press in the field released on the backdrop leaves the
sheet open with `lea@exa` still typed; a press and its release both on the backdrop
close it.

Readings where the spec leaves room:

- The sheet is the signed-out one (`GET /api/account` answers signed out), opened
  from « Compte » of the Menu in the room and from the top bar's « Compte » on the
  catalogue; its address field is `account-email-input`.
- A press and release at two places is `mouse.down` at one, `mouse.move`, `mouse.up`
  at the other. The backdrop of the room's sheet (centred) is left of it; the
  catalogue's bottom sheet has the backdrop above it, under the top bar.
- A press on the backdrop released in the sheet is also tried: rule 14 says a press
  that starts on one and ends on the other closes nothing, the reverse as well.
- "Closes nothing" is read 300 ms after the release; "close it" focuses « Menu » in
  the room and « Compte » on the catalogue (rule 14).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from hud_harness import centre_of, press_and_release
from nock.catalogue import Catalogue
from nock.grid import Grid
from room_panels import open_menu
from spec019_harness import OpenWindow, window_opener
from spec033_harness import AccountRoutes
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec043_harness import (
    COMPUTER,
    PHONE,
    QUIET_MS,
    fx01_view,
    open_room,
    players_up_to,
    snapshot_frame,
)
from spec046_harness import SIGNED_OUT, accounts_on, open_catalogue

TYPED_ADDRESS = "lea@exa"


class SheetCase(NamedTuple):
    """Where the account sheet is opened, and what the test needs of it.

    Attributes:
        in_room: True for a room, False for the catalogue.
        size: The window.
        backdrop_points: Two points of the backdrop.
        focus_after_close: The `data-testid` that takes the focus when it closes.
    """

    in_room: bool
    size: tuple[int, int]
    backdrop_points: tuple[tuple[float, float], tuple[float, float]]
    focus_after_close: str


ROOM_CASE = SheetCase(True, COMPUTER, ((20.0, 360.0), (60.0, 400.0)), "menu-button")
CATALOGUE_CASE = SheetCase(
    False, PHONE, ((180.0, 80.0), (240.0, 100.0)), "account-open"
)
CASES = [ROOM_CASE, CATALOGUE_CASE]
CASE_IDS = ["room-1280x720", "catalogue-360x740"]

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    """Return the fixture grid FX-01, parsed."""
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """Return the catalogue the live server serves: the reference one."""
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_sheet_with_address(
    window: OpenWindow, base_url: str, grid: Grid, case: SheetCase
) -> tuple[Page, Locator]:
    """Open the signed-out account sheet where `case` says and type the address.

    Args:
        window: The window opener.
        base_url: The live server.
        grid: FX-01.
        case: A room at 1280 by 720, or the catalogue at 360 by 740.

    Returns:
        The page and the sheet, with `lea@exa` typed in its address field.
    """
    page = window(case.size[0], case.size[1], False)
    if case.in_room:
        AccountRoutes().install(page)
        frame = snapshot_frame(fx01_view(grid), players_up_to(3))
        open_room(page, base_url, frame)
        expect(page.get_by_test_id("account-open")).to_have_count(1)
        open_menu(page)
    else:
        accounts_on(page, SIGNED_OUT)
        open_catalogue(page, base_url)
    page.get_by_test_id("account-open").click()
    dialog = page.get_by_test_id("account-dialog")
    expect(dialog).to_have_attribute("open", "")
    address = page.get_by_test_id("account-email-input")
    address.fill(TYPED_ADDRESS)
    expect(address).to_have_value(TYPED_ADDRESS)
    return page, dialog


@pytest.mark.parametrize("start", ["field", "backdrop"])
@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_ac34_a_press_and_release_in_two_places_keep_the_sheet_and_the_address(
    window: OpenWindow, live_server: str, fx01_grid: Grid, case: SheetCase, start: str
) -> None:
    page, dialog = open_sheet_with_address(window, live_server, fx01_grid, case)
    address = page.get_by_test_id("account-email-input")
    backdrop_point = case.backdrop_points[0]
    if start == "field":
        press_and_release(page, centre_of(address), backdrop_point)
    else:
        press_and_release(page, backdrop_point, centre_of(address))
    page.wait_for_timeout(QUIET_MS)

    expect(dialog).to_have_attribute("open", "")
    expect(address).to_have_value(TYPED_ADDRESS)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_ac34_a_press_and_release_both_on_the_backdrop_close_the_sheet(
    window: OpenWindow, live_server: str, fx01_grid: Grid, case: SheetCase
) -> None:
    page, dialog = open_sheet_with_address(window, live_server, fx01_grid, case)
    first_point, second_point = case.backdrop_points

    press_and_release(page, first_point, second_point)

    expect(dialog).not_to_have_attribute("open", "")
    expect(page.get_by_test_id(case.focus_after_close)).to_be_focused()
