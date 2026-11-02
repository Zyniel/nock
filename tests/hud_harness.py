"""Shared setup of the tests of `client/hud.md`: the room-gone dialog (rule 16) and
the focus kept in the overlays and the room sheets (rules 12 and 13).

Pytest does not collect this module (its name does not start with `test_`). It
holds what the tests of AC-21 and AC-22 (`test_hud_room_gone.py`) share: the
dialog's texts, the two ways a page meets the deletion of its room (joined, and
reconnecting with a letter not yet answered), and the checks of the dialog's look
(`specs/_design/overlays.md`, « Room gone »).

It reuses spec 043's mocked room and snapshots (`open_room`, `RoomMock.close`),
spec 042's box and pixel readers, spec 046's content box and button colours, and
spec 047's checks of the recap's frame, which the dialog shares.

For AC-23 to AC-25 (`test_hud_overlay_focus.py`), and for the tests of
`lobby/host.md` AC-18 to AC-20, `gameplay/hints.md` AC-25 and `account/account.md`
AC-34, which share them: the host's sheet on a mocked room (`open_host_sheet`),
the `host_changed` frame, and a press at one point released at another
(`press_and_release`), the way a drag between a sheet and its backdrop reads.

For AC-26 and AC-27 (`test_hud_status_region.py`), and for every test of another
domain that reads what the status region announces (`client/hud.md` rules 17 and
18): the hooks of the two kinds of region, the checks of "read but not seen" and of
"no live role", the recorder of what a region holds after each change, and the
probe of what a sheet's region holds when the sheet opens.

Readings where the spec leaves room:

- The page's region is the element `data-testid="status-region"`; a room sheet's
  region is the element `data-testid="sheet-status-region"` inside the sheet (its
  own `data-testid`: `host-settings`, `account-dialog`, `recap`, `room-gone`).
  Each has `role="status"` and the class `visually-hidden`.
- "Read but not seen": the region's box is at most 1 px by 1 px, and neither it nor
  an ancestor is `hidden`, `aria-hidden`, `inert`, `display: none` or `visibility:
  hidden`. The page's region is only checked while no sheet is open, since an open
  sheet makes the page inert.
- "No live role": neither the element nor any ancestor has `role` `status`,
  `alert` or `log`, or an `aria-live` attribute.
- "Empty in between" and "not written again" are read from a `MutationObserver`
  that records the region's text after each batch of changes. A region emptied and
  refilled in one run of the page's code shows one batch, the final text: the empty
  state has to be a state the page was in before it wrote the text.
- The dialog is the one element of role `alertdialog`; it is modal when it
  matches `:modal` (a `<dialog>` opened with `showModal`) or has `aria-modal`
  `true`.
- The deletion is the close of the newest socket with 4404, as the server closes
  every socket of a deleted room (`lobby/joining.md` rule 16).
- "No band under the top bar": `connection-banner` is not on the page, `room-status`
  is either not on the page or visually hidden (class `visually-hidden`,
  `_design/room.md` « Connection lost »), and the grid area's top is where it was
  before the socket closed.
- "The scrim covers the whole window, top bar included": the point (2, 2), in the
  top bar, hits no element of the top bar, and its painted colour is the colour
  it had before the deletion under ink at 38 % (`--nock-scrim-dialog`), within 2
  per channel.
"""

from __future__ import annotations

from typing import NamedTuple

from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from nock.protocol import ErrorCode, HostChanged, Undo
from room_panels import open_host_settings, open_host_settings_with_keyboard, show_tab
from spec042_harness import Box, box_of, pixel_at, wait_until
from spec043_harness import (
    FX01_SOLUTION,
    INK,
    MUTED,
    NAVY,
    WAIT_TIMEOUT_MS,
    Rgb,
    RoomMock,
    cell_at,
    error_frame,
    fx01_view,
    open_room,
    players_up_to,
    press_cell,
    same_position,
    snapshot_frame,
)
from spec046_harness import button_colour_problems, content_box
from spec047_harness import (
    SCRIM_DIALOG_ALPHA,
    column_frame_problems,
    sheet_frame_problems,
    type_problems,
)

# The texts of rule 16, as `web/src/i18n/fr.json` holds them.
GONE_TITLE = "Ce salon n'existe plus."  # `room.gone.title`
# `room.status.not_found_detail`
GONE_DETAIL = "Un salon est effacé après un certain temps sans modification."
HOME_LINK_NAME = "Voir les grilles"  # `share.home`

NOT_FOUND_CLOSE_CODE = 4404
LOST_CLOSE_CODE = 1011
CONNECTION_LOSS_MS = 5000  # the band shows within 5 s (`client/hud.md` AC-5)

# A point of the top bar, clear of its buttons and of the brand.
TOP_BAR_POINT = (2.0, 2.0)
PIXEL_TOLERANCE = 2
PIXEL_POLL_MS = 100

# Whether a dialog is modal: open as a modal `<dialog>`, or marked `aria-modal`.
MODAL_SCRIPT = (
    "element => element.matches(':modal')"
    " || element.getAttribute('aria-modal') === 'true'"
)

# Whether the element at (x, y) is `room-topbar` or inside it.
TOP_BAR_HIT_SCRIPT = r"""
([x, y]) => {
  const bar = document.querySelector('[data-testid="room-topbar"]');
  const hit = document.elementFromPoint(x, y);
  return bar !== null && hit !== null && bar.contains(hit);
}
"""


class GonePage(NamedTuple):
    """A room page whose room was deleted, and what it showed before.

    Attributes:
        page: The page.
        mock: Its mocked socket.
        top_bar_pixel: The painted colour at `TOP_BAR_POINT` before the deletion.
        grid_area_top: The top of `grid-area` while the room was joined.
    """

    page: Page
    mock: RoomMock
    top_bar_pixel: Rgb
    grid_area_top: float


# ---- Opening the room and deleting it -------------------------------------------


def fx01_frame(grid: Grid) -> str:
    """FX-01's snapshot for `p1`, the host, with `p2` and `p3`."""
    return snapshot_frame(fx01_view(grid), players_up_to(3))


def open_fx01_room(page: Page, base_url: str, grid: Grid) -> RoomMock:
    """Open /r/ABC123 joined as Ana on FX-01's snapshot."""
    return open_room(page, base_url, fx01_frame(grid))


def grid_area_top(page: Page) -> float:
    """Return the top edge of the grid area, in page pixels."""
    return box_of(page.get_by_test_id("grid-area")).top


def delete_room(mock: RoomMock) -> None:
    """Close the newest socket with 4404, as the server does for a deleted room."""
    mock.close(NOT_FOUND_CLOSE_CODE)


def open_salon_sheet(page: Page) -> None:
    """Open the Salon (in the sheet layout, its sheet) on Discussion."""
    show_tab(page, "discussion")


def delete_while_joined_with_the_salon_open(
    page: Page, base_url: str, grid: Grid
) -> GonePage:
    """Joined on FX-01 with the Salon open, the room is deleted.

    Args:
        page: A fresh page, in the window the test wants (360 by 740 for AC-21).
        base_url: The live server.
        grid: FX-01.

    Returns:
        The page once the 4404 is sent, and what it showed before.
    """
    mock = open_fx01_room(page, base_url, grid)
    noted_top = grid_area_top(page)
    open_salon_sheet(page)
    noted_pixel = pixel_at(page, TOP_BAR_POINT[0], TOP_BAR_POINT[1])
    delete_room(mock)
    return GonePage(page, mock, noted_pixel, noted_top)


def reconnect_with_t_pending(page: Page, mock: RoomMock) -> None:
    """Lose the socket, type `T` at (1, 0) offline, and wait for the page's new join.

    The letter is not answered: the page holds it unconfirmed while it
    reconnects, and the new socket gets the join but no snapshot.
    """
    frames_before = len(mock.received)
    mock.close(LOST_CLOSE_CODE)
    expect(page.get_by_test_id("connection-banner")).to_be_visible(
        timeout=CONNECTION_LOSS_MS
    )
    press_cell(page, 1, 0)
    page.keyboard.press("t")
    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-letter", "T")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    wait_until(page, lambda: mock.has_join_after(frames_before), "the new join")


def delete_while_reconnecting_with_t_pending(
    page: Page, base_url: str, grid: Grid
) -> GonePage:
    """Reconnecting on FX-01 with `T` typed at (1, 0) and unanswered, the room is
    deleted: the new socket closes with 4404.

    Args:
        page: A fresh page, in the window the test wants (1280 by 720 for AC-21).
        base_url: The live server.
        grid: FX-01.

    Returns:
        The page once the 4404 is sent, and what it showed before.
    """
    mock = open_fx01_room(page, base_url, grid)
    noted_top = grid_area_top(page)
    noted_pixel = pixel_at(page, TOP_BAR_POINT[0], TOP_BAR_POINT[1])
    reconnect_with_t_pending(page, mock)
    delete_room(mock)
    return GonePage(page, mock, noted_pixel, noted_top)


# ---- The dialog -------------------------------------------------------------------


def room_gone_dialog(page: Page) -> Locator:
    """Return the locator of the alert dialog of the page."""
    return page.get_by_role("alertdialog")


def home_link(page: Page) -> Locator:
    """Return the locator of the link inside the alert dialog."""
    return room_gone_dialog(page).get_by_role("link")


def expect_room_gone_dialog(page: Page) -> None:
    """Wait until the one alert dialog of the page shows."""
    dialog = room_gone_dialog(page)
    expect(dialog).to_have_count(1, timeout=WAIT_TIMEOUT_MS)
    expect(dialog).to_be_visible()


def is_modal(dialog: Locator) -> bool:
    """Tell whether the dialog is modal, as the browser computes it.

    Args:
        dialog: The locator of the dialog element.

    Returns:
        True when the dialog is modal.
    """
    found = dialog.evaluate(MODAL_SCRIPT)
    assert isinstance(found, bool), found
    return found


def expect_dialog_as_rule_16_says(page: Page) -> None:
    """The dialog of AC-21: modal, named, described, one link to `/`, focused."""
    expect_room_gone_dialog(page)
    dialog = room_gone_dialog(page)
    expect(dialog).to_have_accessible_name(GONE_TITLE)
    expect(dialog).to_have_accessible_description(GONE_DETAIL)
    assert is_modal(dialog)
    expect(dialog.get_by_role("button")).to_have_count(0)
    link = home_link(page)
    expect(link).to_have_count(1)
    expect(link).to_have_accessible_name(HOME_LINK_NAME)
    expect(link).to_have_attribute("href", "/")
    expect(link).to_be_focused()


def expect_no_band(gone: GonePage) -> None:
    """No connection band and no status band under the top bar."""
    page = gone.page
    expect(page.get_by_test_id("connection-banner")).to_have_count(0)
    status = page.get_by_test_id("room-status")
    if status.count() > 0:
        classes = str(status.get_attribute("class")).split()
        assert "visually-hidden" in classes, classes
    top = grid_area_top(page)
    assert same_position(top, gone.grid_area_top), (top, gone.grid_area_top)


# ---- The look (`_design/overlays.md`, « Room gone ») -------------------------------


def frame_problems(page: Page, layout: str) -> list[str]:
    """The recap's frame: the 440 px dialog (column) or the bottom sheet (sheet)."""
    dialog = room_gone_dialog(page)
    if layout == "sheet":
        return sheet_frame_problems(page, dialog)
    return column_frame_problems(page, dialog)


def content_problems(page: Page) -> list[str]:
    """The title, the line and the link: their order, type, colours and place."""
    dialog = room_gone_dialog(page)
    title = dialog.get_by_text(GONE_TITLE, exact=True)
    detail = dialog.get_by_text(GONE_DETAIL, exact=True)
    link = home_link(page)
    problems = type_problems(title, "title", size=19.2, weight="700", colour=NAVY)
    problems += type_problems(detail, "line", size=15.2, colour=MUTED)
    problems += button_colour_problems(link, "primary")
    title_box = box_of(title)
    detail_box = box_of(detail)
    link_box = box_of(link)
    if detail_box.top < title_box.bottom - 1.0:
        problems.append(f"line top {detail_box.top}, title bottom {title_box.bottom}")
    if link_box.top < detail_box.bottom - 1.0:
        problems.append(f"link top {link_box.top}, line bottom {detail_box.bottom}")
    content_right = content_box(dialog).right
    if not same_position(link_box.right, content_right):
        problems.append(f"link right {link_box.right}, content right {content_right}")
    return problems


def under_scrim(colour: Rgb) -> Rgb:
    """A colour under ink at the dialog scrim's alpha."""
    channels: list[int] = []
    for channel, ink in zip(colour, INK, strict=True):
        mixed = channel * (1 - SCRIM_DIALOG_ALPHA) + ink * SCRIM_DIALOG_ALPHA
        channels.append(round(mixed))
    return (channels[0], channels[1], channels[2])


def close_colours(first: Rgb, second: Rgb) -> bool:
    """Tell whether two colours differ by at most `PIXEL_TOLERANCE` per channel.

    Args:
        first: One colour.
        second: The other colour.

    Returns:
        True when every channel is within the tolerance.
    """
    for one, other in zip(first, second, strict=True):
        if abs(one - other) > PIXEL_TOLERANCE:
            return False
    return True


def scrim_problems(gone: GonePage) -> list[str]:
    """How the scrim fails to cover the top bar with `--nock-scrim-dialog`."""
    page = gone.page
    problems: list[str] = []
    in_bar = page.evaluate(TOP_BAR_HIT_SCRIPT, list(TOP_BAR_POINT))
    if in_bar is not False:
        problems.append(f"the point {TOP_BAR_POINT} still hits the top bar")
    expected = under_scrim(gone.top_bar_pixel)
    painted = pixel_at(page, TOP_BAR_POINT[0], TOP_BAR_POINT[1])
    waited_ms = 0
    while not close_colours(painted, expected) and waited_ms < WAIT_TIMEOUT_MS:
        page.wait_for_timeout(PIXEL_POLL_MS)
        waited_ms += PIXEL_POLL_MS
        painted = pixel_at(page, TOP_BAR_POINT[0], TOP_BAR_POINT[1])
    if not close_colours(painted, expected):
        problems.append(
            f"top bar painted {painted}, not {expected}"
            f" ({gone.top_bar_pixel} under the scrim)"
        )
    return problems


def scrim_press_point(page: Page, kept: tuple[int, int]) -> tuple[float, float]:
    """The centre of a letter cell of FX-01, other than `kept`, outside the dialog.

    A press there falls on the scrim over the grid: under a working dialog it
    selects nothing.
    """
    dialog_box = box_of(room_gone_dialog(page))
    for cell in FX01_SOLUTION:
        if cell == kept:
            continue
        cell_box = box_of(cell_at(page, cell[0], cell[1]))
        if not box_holds(dialog_box, cell_box.centre_x, cell_box.centre_y):
            return (cell_box.centre_x, cell_box.centre_y)
    raise AssertionError(f"every letter cell lies under the dialog {dialog_box}")


def box_holds(box: Box, x: float, y: float) -> bool:
    """Whether (x, y) lies in a box or within 1 px of it."""
    inside_x = box.left - 1.0 <= x <= box.right + 1.0
    inside_y = box.top - 1.0 <= y <= box.bottom + 1.0
    return inside_x and inside_y


# ---- The room sheets: the host's settings and the pointer (rule 13) -----------------

# A point of the backdrop at 1280 by 720: left of the centred sheet, clear of the
# top bar's buttons.
COMPUTER_BACKDROP_POINT = (20.0, 360.0)
DRAG_STEPS = 4


def open_host_sheet(
    page: Page, base_url: str, grid: Grid, *, keyboard: bool = False
) -> RoomMock:
    """Open FX-01 as the host `p1` (3 players) and open the host's settings.

    Args:
        page: A fresh page, in the window the test wants.
        base_url: The live server.
        grid: FX-01.
        keyboard: Whether the sheet is opened with the keyboard only.

    Returns:
        The mocked socket, once the sheet is open.
    """
    mock = open_fx01_room(page, base_url, grid)
    if keyboard:
        open_host_settings_with_keyboard(page)
    else:
        open_host_settings(page)
    return mock


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


# ---- The status regions (`client/hud.md` rules 17 and 18) --------------------------

PAGE_REGION_ID = "status-region"
SHEET_REGION_ID = "sheet-status-region"
UNDO_NOTHING_TEXT = "Rien à annuler."  # `undo.nothing`
OFFLINE_TEXT = (  # `room.banner.offline`
    "Connexion perdue. Vous pouvez continuer : vos lettres seront envoyées au "
    "retour du réseau."
)

# What keeps a region out of the accessibility tree or on the screen.
REGION_PROBLEMS_SCRIPT = r"""
region => {
  const problems = [];
  if (region.getAttribute('role') !== 'status') {
    problems.push(`role is ${region.getAttribute('role')}`);
  }
  const box = region.getBoundingClientRect();
  if (box.width > 1.01 || box.height > 1.01) {
    problems.push(`box is ${box.width} by ${box.height}, so it is seen`);
  }
  for (let node = region; node !== null; node = node.parentElement) {
    const style = getComputedStyle(node);
    const name = node.getAttribute('data-testid') || node.tagName.toLowerCase();
    if (style.display === 'none') problems.push(`${name} has display none`);
    if (style.visibility === 'hidden') problems.push(`${name} is visibility hidden`);
    if (node.hasAttribute('hidden')) problems.push(`${name} is hidden`);
    if (node.getAttribute('aria-hidden') === 'true') {
      problems.push(`${name} is aria-hidden`);
    }
    if (node.hasAttribute('inert')) problems.push(`${name} is inert`);
  }
  return problems;
}
"""

# The live roles of an element and of its ancestors.
LIVE_ROLE_PROBLEMS_SCRIPT = r"""
element => {
  const problems = [];
  for (let node = element; node !== null; node = node.parentElement) {
    const name = node.getAttribute('data-testid') || node.tagName.toLowerCase();
    const role = node.getAttribute('role');
    if (role === 'status' || role === 'alert' || role === 'log') {
      problems.push(`${name} has role ${role}`);
    }
    if (node.hasAttribute('aria-live')) {
      problems.push(`${name} has aria-live ${node.getAttribute('aria-live')}`);
    }
  }
  return problems;
}
"""

# Record the page region's text after each batch of changes, in `window`.
RECORD_REGION_SCRIPT = r"""
testId => {
  const region = document.querySelector(`[data-testid="${testId}"]`);
  window.__regionTexts = [];
  const observer = new MutationObserver(() => {
    window.__regionTexts.push(region.textContent.trim());
  });
  observer.observe(region, {childList: true, characterData: true, subtree: true});
}
"""

# Watch a sheet: the text of its region at the first batch in which the sheet is
# open and holds its region, then after each following batch.
WATCH_SHEET_REGION_SCRIPT = r"""
([sheetId, regionId]) => {
  const probe = {textAtOpening: null, texts: []};
  window.__sheetRegion = probe;
  const observer = new MutationObserver(() => {
    const sheet = document.querySelector(`[data-testid="${sheetId}"]`);
    if (sheet === null || !sheet.hasAttribute('open')) return;
    const region = sheet.querySelector(`[data-testid="${regionId}"]`);
    if (region === null) return;
    const text = region.textContent.trim();
    if (probe.textAtOpening === null) probe.textAtOpening = text;
    probe.texts.push(text);
  });
  observer.observe(document, {
    subtree: true, childList: true, characterData: true,
    attributes: true, attributeFilter: ['open'],
  });
}
"""


class SheetRegionWatch(NamedTuple):
    """What a sheet's region held while a `watch_sheet_region` probe ran.

    Attributes:
        text_at_opening: The region's text in the first batch of changes after
            which the sheet was open, or None while the sheet has not opened.
        texts: The region's text after each batch from then on.
    """

    text_at_opening: str | None
    texts: list[str]


def page_region(page: Page) -> Locator:
    """Return the locator of the room page's status region."""
    return page.get_by_test_id(PAGE_REGION_ID)


def sheet_region(page: Page, sheet_test_id: str) -> Locator:
    """Return the locator of the status region of the room sheet `sheet_test_id`."""
    return page.get_by_test_id(sheet_test_id).get_by_test_id(SHEET_REGION_ID)


def region_problems(region: Locator) -> list[str]:
    """How a status region fails to be a `role="status"` read but not seen.

    Args:
        region: The page's region, with no sheet open, or a sheet's region.

    Returns:
        One line per failure; an empty list for a region that is as rule 17 says.
    """
    found = region.evaluate(REGION_PROBLEMS_SCRIPT)
    assert isinstance(found, list), found
    return [str(problem) for problem in found]


def live_role_problems(element: Locator) -> list[str]:
    """The live roles on an element and its ancestors.

    A message that a status region announces is shown by an element with none of
    `role` `status`, `alert` or `log`, nor `aria-live`, on it or above it.

    Args:
        element: The element that shows a message.

    Returns:
        One line per live role found; an empty list when there is none.
    """
    found = element.evaluate(LIVE_ROLE_PROBLEMS_SCRIPT)
    assert isinstance(found, list), found
    return [str(problem) for problem in found]


def expect_page_region_reads(page: Page, text: str) -> None:
    """Wait until the page has one status region and it reads exactly `text`."""
    region = page_region(page)
    expect(region).to_have_count(1)
    expect(region).to_have_text(text, timeout=WAIT_TIMEOUT_MS)


def record_region_texts(page: Page) -> None:
    """Start recording the page region's text after each batch of changes."""
    expect(page_region(page)).to_have_count(1)
    page.evaluate(RECORD_REGION_SCRIPT, PAGE_REGION_ID)


def recorded_region_texts(page: Page) -> list[str]:
    """Return what `record_region_texts` has recorded since it started."""
    found = page.evaluate("() => window.__regionTexts")
    assert isinstance(found, list), found
    return [str(text) for text in found]


def announcements_of(texts: list[str]) -> list[str]:
    """Reduce recorded texts to the states the region was in, in order.

    A text twice in a row is one state, and the empty states before the first
    message and after the last one are left out.

    Args:
        texts: What `recorded_region_texts` returned.

    Returns:
        For example `["Rien", "", "Rien"]` for a message announced twice.
    """
    states: list[str] = []
    for text in texts:
        if not states or states[-1] != text:
            states.append(text)
    while states and states[0] == "":
        states.pop(0)
    while states and states[-1] == "":
        states.pop()
    return states


def watch_sheet_region(page: Page, sheet_test_id: str) -> None:
    """Start watching the region of a sheet that is not open yet."""
    page.evaluate(WATCH_SHEET_REGION_SCRIPT, [sheet_test_id, SHEET_REGION_ID])


def sheet_region_watch(page: Page) -> SheetRegionWatch:
    """Return what `watch_sheet_region` has seen since it started."""
    found = page.evaluate("() => window.__sheetRegion")
    assert isinstance(found, dict), found
    return SheetRegionWatch(found["textAtOpening"], list(found["texts"]))


def press_undo_answered_nothing(page: Page, mock: RoomMock) -> None:
    """Click « Annuler » and answer its `undo` with `nothing_to_undo`."""
    frames_before = len(mock.frames_without_pings())
    page.get_by_test_id("undo-button").click()
    wait_until(
        page,
        lambda: Undo() in mock.parsed_frames_after(frames_before),
        "the undo frame",
    )
    mock.send(error_frame(ErrorCode.NOTHING_TO_UNDO))
