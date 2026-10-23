"""Tests of spec 043, AC-10 to AC-12: the Menu and the popovers' shared rules.

AC-10: `room-menu` holds the design's items in order, the host's and the account's
only when they apply, with its place under each top bar. AC-11: the switches flip
in place, « Inviter », « Réglages de l'hôte » and « Compte » open what they name.
AC-12: both popovers open, close and take the focus the same way, never stack, and
in the sheet layout a scrim covers the page under the top bar.

Choices where the spec leaves room:

- An item's label is its visible text outside `aria-hidden` elements, so without
  its detail (`nock-menu-detail`, which is `aria-hidden`).
- Accounts are on when the mocked `GET /api/account` answers (spec 033's mocked
  account routes), off when it is not routed (the live server answers 404).
- "The first enabled item" of a popover: the first `button` or `a[href]` inside it
  that is not disabled; the popover itself when there is none.
- A pointer that clicks a popover button is then moved away, so no hover style is
  read in place of the state.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import Direction
from room_panels import open_aide, open_menu
from spec019_harness import OpenWindow, window_opener
from spec024_harness import outline_problems
from spec033_harness import AccountRoutes
from spec035_harness import Walker
from spec042_harness import box_of, colour_of
from spec043_harness import (
    INK,
    WHITE,
    Reading,
    cell_at,
    colour_matches,
    expect_closed,
    expect_colour,
    expect_selected,
    focused_test_id,
    fr_value,
    frames_sent_after,
    fx01_view,
    label_of,
    open_room,
    player,
    players_up_to,
    same_position,
    selecting,
    snapshot_frame,
    stored_value,
    style_of,
)

SIZES = [(360, 740), (1280, 720)]
SIZE_IDS = ["360x740", "1280x720"]
POPOVERS = {"aide-button": "aide-menu", "menu-button": "room-menu"}

MENU_ORDER = [
    "authors-switch",
    "others-tint-switch",
    "access-switch",
    "invite-open",
    "host-settings-open",
    "separator",
    "timer-toggle",
    "back-to-grids",
]
LABEL_KEYS = {
    "authors-switch": "authors.switch",
    "others-tint-switch": "others_tint.switch",
    "access-switch": "access.switch",
    "invite-open": "menu.invite",
    "host-settings-open": "settings.heading",
    "timer-toggle": "timer.hide",
    "back-to-grids": "menu.back",
    "account-open": "account.open",
}
ITEM_NAMES = [*LABEL_KEYS]

ORDER_SCRIPT = r"""
(menu, names) => {
  const found = [];
  for (const element of menu.querySelectorAll('*')) {
    const testId = element.getAttribute('data-testid');
    if (names.includes(testId)) {
      found.push(testId);
    } else if (element.classList.contains('nock-menu-separator')) {
      found.push('separator');
    }
  }
  return found;
}
"""

DETAILS_SCRIPT = r"""
item => {
  const found = [];
  for (const detail of item.querySelectorAll('.nock-menu-detail')) {
    found.push({text: detail.textContent.trim(),
      ariaHidden: detail.getAttribute('aria-hidden')});
  }
  return found;
}
"""

# The first enabled item of a popover, or the popover itself.
FIRST_ENABLED_SCRIPT = r"""
popover => {
  for (const element of popover.querySelectorAll('button, a[href]')) {
    if (!element.disabled) {
      return element.getAttribute('data-testid');
    }
  }
  return popover.getAttribute('data-testid');
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_fx01(page: Page, base_url: str, grid: Grid, *, host: str = "p1") -> None:
    frame = snapshot_frame(fx01_view(grid), players_up_to(3, host=host))
    open_room(page, base_url, frame)


def menu_order(page: Page) -> list[str]:
    names = [*ITEM_NAMES]
    found = page.get_by_test_id("room-menu").evaluate(ORDER_SCRIPT, names)
    assert isinstance(found, list), found
    return found


def details_of(page: Page, test_id: str) -> list[Reading]:
    found = page.get_by_test_id(test_id).evaluate(DETAILS_SCRIPT)
    assert isinstance(found, list), found
    return found


def move_pointer_away(page: Page) -> None:
    height = page.evaluate("() => innerHeight")
    page.mouse.move(1, float(height) - 1)


# ---- AC-10: the Menu's items and place -----------------------------------------------


def test_ac10_the_menu_is_a_group_named_menu(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)
    open_menu(page)

    menu = page.get_by_test_id("room-menu")
    expect(menu).to_have_attribute("role", "group")
    expect(menu).to_have_attribute("aria-label", fr_value("topbar.menu"))
    expect(menu).to_have_attribute("id", "room-menu")


def test_ac10_the_menu_holds_the_design_items_in_order(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)
    open_menu(page)

    assert menu_order(page) == MENU_ORDER


def test_ac10_each_item_shows_the_label_of_the_menu_table(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)
    open_menu(page)

    problems: list[str] = []
    for test_id in MENU_ORDER:
        if test_id == "separator":
            continue
        label = label_of(page.get_by_test_id(test_id))
        expected = fr_value(LABEL_KEYS[test_id])
        if label is None or label["text"] != expected:
            problems.append(f"{test_id}: {label}, expected {expected!r}")
    assert problems == []


def test_ac10_back_to_grids_is_a_link_to_the_catalogue(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)
    link = page.get_by_test_id("back-to-grids")

    tag = link.evaluate("element => element.tagName")

    assert tag == "A"
    expect(link).to_have_attribute("href", "/")


def test_ac10_the_details_are_hidden_from_screen_readers_and_read_the_states(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)
    expected = {
        "authors-switch": fr_value("authors.off"),
        "others-tint-switch": fr_value("others_tint.on"),
        "access-switch": fr_value("access.off"),
        "invite-open": fr_value("menu.invite_detail"),
    }

    problems: list[str] = []
    for test_id, text in expected.items():
        details = details_of(page, test_id)
        if details != [{"text": text, "ariaHidden": "true"}]:
            problems.append(f"{test_id}: {details}, expected {text!r} aria-hidden")
    for test_id in ("host-settings-open", "timer-toggle", "back-to-grids"):
        for detail in details_of(page, test_id):
            if detail["ariaHidden"] != "true":
                problems.append(f"{test_id}: a detail without aria-hidden")
    assert problems == []


def test_ac10_on_a_phone_the_menu_hangs_58_px_down_and_6_px_from_the_right(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)
    open_menu(page)
    menu = page.get_by_test_id("room-menu")

    box = box_of(menu)

    assert same_position(box.top, 58.0), box
    assert same_position(box.right, 360.0 - 6.0), box
    assert box.width >= 220.0 - 0.5, box
    expect_colour(menu, "backgroundColor", WHITE)
    assert style_of(menu, "borderTopLeftRadius") == "8px"


def test_ac10_a_guest_has_no_host_settings_item(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid, host="p2")

    expect(page.get_by_test_id("room-menu")).to_have_count(1)
    expect(page.get_by_test_id("host-settings-open")).to_have_count(0)


def test_ac10_with_accounts_on_compte_comes_right_after_the_host_settings(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    AccountRoutes().install(page)
    open_fx01(page, live_server, fx01_grid)
    expect(page.get_by_test_id("account-open")).to_have_count(1)

    order = menu_order(page)

    index = order.index("host-settings-open")
    assert order[index + 1] == "account-open", order
    label = label_of(page.get_by_test_id("account-open"))
    assert label is not None
    assert label["text"] == fr_value("account.open")


def test_ac10_with_accounts_on_a_guest_has_compte_right_after_inviter(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    AccountRoutes().install(page)
    open_fx01(page, live_server, fx01_grid, host="p2")
    expect(page.get_by_test_id("account-open")).to_have_count(1)

    order = menu_order(page)

    index = order.index("invite-open")
    assert order[index + 1] == "account-open", order
    assert order[index + 2] == "separator", order


def test_ac10_on_a_computer_the_menu_hangs_4_px_under_the_bar_at_its_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    open_menu(page)

    box = box_of(page.get_by_test_id("room-menu"))
    bar_box = box_of(page.get_by_test_id("room-topbar"))
    button_box = box_of(page.get_by_test_id("menu-button"))

    assert same_position(box.top, bar_box.bottom + 4.0), (box, bar_box)
    assert same_position(box.right, button_box.right), (box, button_box)


# ---- AC-11: switches flip in place; the other items open what they name --------------


def ac11_frame(grid: Grid) -> str:
    """`p1`, and `p2` (colour 1) and `p3` (colour 2) selecting (2, 2)."""
    on_2_2 = selecting(2, 2, Direction.ACROSS)
    players = [
        player("p1", host=True),
        player("p2", selection=on_2_2),
        player("p3", selection=on_2_2),
    ]
    return snapshot_frame(fx01_view(grid), players)


# Each switch: what a click makes of its `aria-pressed` and detail, and the key and
# value it stores. Since spec 045 AC-1 the Auteurs mode is remembered too: turning
# it on writes "true" under `nock.authors`.
SWITCH_CLICKS = {
    "access-switch": ("true", "access.on", "nock.accessibility", "true"),
    "others-tint-switch": ("false", "others_tint.off", "nock.others_tint", "false"),
    "authors-switch": ("true", "authors.on", "nock.authors", "true"),
}


@pytest.mark.parametrize("test_id", list(SWITCH_CLICKS))
def test_ac11_a_switch_flips_in_place_and_the_menu_stays_open_on_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, ac11_frame(fx01_grid))
    open_menu(page)
    pressed, detail_key, storage_key, stored = SWITCH_CLICKS[test_id]
    switch = page.get_by_test_id(test_id)

    switch.click()

    expect(switch).to_have_attribute("aria-pressed", pressed)
    assert details_of(page, test_id)[0]["text"] == fr_value(detail_key)
    assert stored_value(page, storage_key) == stored
    expect(page.get_by_test_id("room-menu")).to_be_visible()
    assert focused_test_id(page) == test_id


def test_ac11_the_access_switch_turns_the_cursors_into_icons(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, ac11_frame(fx01_grid))
    open_menu(page)

    page.get_by_test_id("access-switch").click()

    cursors = cell_at(page, 2, 2).get_by_test_id("remote-selection")
    expect(cursors).to_have_count(2)
    for index in range(2):
        expect(cursors.nth(index)).to_have_attribute("data-shape", "icon")


def test_ac11_from_the_keyboard_the_menu_opens_on_authors_and_enter_flips_each(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, ac11_frame(fx01_grid))
    walker = Walker(page)

    walker.tab_to("menu-button")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("room-menu")).to_be_visible()
    assert focused_test_id(page) == "authors-switch"

    problems: list[str] = []
    for test_id in ("authors-switch", "others-tint-switch", "access-switch"):
        switch = page.get_by_test_id(test_id)
        before = switch.get_attribute("aria-pressed")
        walker.tab_to(test_id)
        reached = walker.reached[-1]
        page.keyboard.press("Enter")
        flipped = "false" if before == "true" else "true"
        expect(switch).to_have_attribute("aria-pressed", flipped)
        found = outline_problems(
            reached.outline_style, reached.outline_width, reached.outline_contrast
        )
        problems.extend(f"{test_id}: {problem}" for problem in found)
    assert problems == []


def test_ac11_inviter_opens_the_joueurs_tab_with_the_focus_on_copy_link(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, ac11_frame(fx01_grid))
    open_menu(page)

    page.get_by_test_id("invite-open").click()

    expect_closed(page.get_by_test_id("room-menu"))
    expect(page.get_by_test_id("salon")).to_be_visible()
    expect(page.get_by_test_id("salon-tab-players")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.get_by_test_id("copy-link")).to_be_focused()


def test_ac11_the_host_settings_item_opens_the_sheet_and_escape_returns(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, ac11_frame(fx01_grid))
    open_menu(page)
    sheet = page.get_by_test_id("host-settings")

    page.get_by_test_id("host-settings-open").click()
    expect_closed(page.get_by_test_id("room-menu"))
    expect(sheet).to_have_attribute("open", "")
    page.keyboard.press("Escape")

    expect(sheet).not_to_have_attribute("open", "")
    expect(page.get_by_test_id("menu-button")).to_be_focused()


def test_ac11_the_account_item_opens_the_account_dialog_and_escape_returns(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    AccountRoutes().install(page)
    open_room(page, live_server, ac11_frame(fx01_grid))
    expect(page.get_by_test_id("account-open")).to_have_count(1)
    open_menu(page)
    dialog = page.get_by_test_id("account-dialog")

    page.get_by_test_id("account-open").click()
    expect_closed(page.get_by_test_id("room-menu"))
    expect(dialog).to_have_attribute("open", "")
    page.keyboard.press("Escape")

    expect(dialog).not_to_have_attribute("open", "")
    expect(page.get_by_test_id("menu-button")).to_be_focused()


# ---- AC-12: the popovers' shared rules -----------------------------------------------


@pytest.mark.parametrize("button", list(POPOVERS))
@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac12_a_popover_opens_on_its_first_enabled_item_and_closes_both_ways(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    button: str,
) -> None:
    page = window(width, height, False)
    open_fx01(page, live_server, fx01_grid)
    popover = page.get_by_test_id(POPOVERS[button])

    page.get_by_test_id(button).click()
    expect(popover).to_be_visible()
    first_enabled = popover.evaluate(FIRST_ENABLED_SCRIPT)
    assert focused_test_id(page) == first_enabled
    page.keyboard.press("Escape")
    expect_closed(popover)
    assert focused_test_id(page) == button
    page.get_by_test_id(button).click()
    expect(popover).to_be_visible()
    page.get_by_test_id(button).click()

    expect_closed(popover)


def test_ac12_on_a_computer_a_click_on_the_grid_closes_the_menu_and_selects(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    open_menu(page)
    box = box_of(cell_at(page, 2, 2))

    page.mouse.click(box.centre_x, box.centre_y)

    expect_closed(page.get_by_test_id("room-menu"))
    expect_selected(page, 2, 2)


def test_ac12_on_a_phone_the_scrim_covers_the_page_under_the_top_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)
    open_aide(page)
    scrim = page.get_by_test_id("room-scrim")
    expect(scrim).to_be_visible()

    box = box_of(scrim)
    colour = colour_of(scrim, "backgroundColor")

    assert same_position(box.top, 54.0), box
    assert same_position(box.bottom, 740.0), box
    assert same_position(box.left, 0.0), box
    assert same_position(box.right, 360.0), box
    assert colour_matches(colour, INK, 0.35), colour
    assert style_of(scrim, "zIndex") == "7"
    expect(scrim).to_have_attribute("aria-hidden", "true")


def test_ac12_on_a_phone_a_click_on_the_scrim_closes_aide_and_does_nothing_else(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    open_aide(page)

    frames = frames_sent_after(page, mock, lambda: page.mouse.click(20, 400))

    expect_closed(page.get_by_test_id("aide-menu"))
    expect(page.get_by_test_id("room-scrim")).not_to_be_visible()
    assert frames == []
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "")


def test_ac12_on_a_phone_opening_one_overlay_closes_the_others(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)

    open_aide(page)
    page.get_by_test_id("menu-button").click()
    expect(page.get_by_test_id("room-menu")).to_be_visible()
    expect_closed(page.get_by_test_id("aide-menu"))

    page.get_by_test_id("chat-toggle").click()
    expect(page.get_by_test_id("salon")).to_be_visible()
    expect_closed(page.get_by_test_id("room-menu"))


def test_ac12_on_a_phone_opening_the_salon_closes_the_reaction_picker(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_fx01(page, live_server, fx01_grid)
    cell_at(page, 0, 3).click()
    expect_selected(page, 1, 3)  # a clue cell selects its word's first cell
    page.get_by_test_id("react-button").click()
    expect(page.get_by_test_id("reaction-picker")).to_be_visible()

    page.get_by_test_id("chat-toggle").click()

    expect(page.get_by_test_id("salon")).to_be_visible()
    expect(page.get_by_test_id("reaction-picker")).not_to_be_visible()


def test_ac12_on_a_computer_the_salon_column_stays_open_and_no_scrim_shows(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    salon = page.get_by_test_id("salon")
    scrim = page.get_by_test_id("room-scrim")
    expect(salon).to_be_visible()

    open_aide(page)
    expect(salon).to_be_visible()
    expect(scrim).not_to_be_visible()
    open_menu(page)
    expect(salon).to_be_visible()
    expect(scrim).not_to_be_visible()
    expect_closed(page.get_by_test_id("aide-menu"))
    page.keyboard.press("Escape")
    cell_at(page, 0, 3).click()
    expect_selected(page, 1, 3)  # a clue cell selects its word's first cell
    page.get_by_test_id("react-button").click()
    expect(page.get_by_test_id("reaction-picker")).to_be_visible()

    expect(salon).to_be_visible()
    expect(scrim).not_to_be_visible()


def test_ac12_a_closed_aide_menu_is_hidden_and_keeps_its_items(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    menu = page.get_by_test_id("aide-menu")

    expect_closed(menu)
    expect(menu.get_by_test_id("check-grid")).to_have_count(1)
