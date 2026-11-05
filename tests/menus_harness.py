"""Shared setup of the tests of `client/menus.md`: the room sheets and the pointer.

Pytest does not collect this module (its name does not start with `test_`). It
holds what the tests of AC-9 (`test_menus_overlay_focus.py`) share with the tests
of `lobby/host.md` AC-18 to AC-20, `gameplay/votes.md` AC-9 and `account/my-account.md`
AC-8: the `host_changed` frame, and a press at one point released at another
(`press_and_release`), the way a drag between a sheet and its backdrop reads.
The host's sheet on a mocked room (`open_host_sheet`) stays in `hud_harness.py`,
where the room-gone tests also use it.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from nock.protocol import HostChanged
from spec042_harness import box_of

# ---- The room sheets and the pointer (`client/menus.md` rule 6) -------------------

# A point of the backdrop at 1280 by 720: left of the centred sheet, clear of the
# top bar's buttons.
COMPUTER_BACKDROP_POINT = (20.0, 360.0)
DRAG_STEPS = 4


def host_changed_frame(seq: int, new_host: str) -> str:
    """The `host_changed` frame that gives the host role to `new_host`."""
    return HostChanged(seq=seq, player_id=new_host).model_dump_json()


def centre_of(locator: Locator) -> tuple[float, float]:
    """Return the centre of an element, in page pixels."""
    box = box_of(locator)
    return (box.centre_x, box.centre_y)


def press_and_release(
    page: Page, start: tuple[float, float], end: tuple[float, float]
) -> None:
    """Press the mouse at `start` and release it at `end`: a drag.

    A click is the press and the release at one point; here the two differ, as when
    a player starts in a field of a sheet and lets go over its backdrop.
    """
    page.mouse.move(start[0], start[1])
    page.mouse.down()
    page.mouse.move(end[0], end[1], steps=DRAG_STEPS)
    page.mouse.up()
