"""Open the room's popovers, the Salon and the room sheets (spec 043, "Test harness").

Spec 043 moves many controls of the room page into the Aide menu (`aide-menu`), the
Menu (`room-menu`), the Salon (`salon`, with its Discussion and Joueurs tabs) and
the room sheets (`host-settings`, `account-dialog`). They stay in the DOM while
closed, with the `hidden` attribute, so a test that only reads their attributes,
texts or computed colours needs not open them. A test that clicks, taps, types into
or measures such an element first opens what holds it with these helpers, in the
tests of every spec.

Spec 043's "Test harness" names these helpers as additions to `tests/conftest.py`.
A test module cannot import a conftest reliably (pytest imports it under its own
name), so they live here, next to `fonts_ready.py`, which the conftest and the
tests share the same way. Pytest does not collect this module (its name does not
start with `test_`).

Every helper waits until what it opened shows, and fails after `WAIT_TIMEOUT_MS`
when the element it needs is not on the page.
"""

from __future__ import annotations

from typing import Literal

from playwright.sync_api import Locator, Page, expect

from spec035_harness import Walker

WAIT_TIMEOUT_MS = 5000

Tab = Literal["discussion", "players"]

# The popover of each top-bar button.
POPOVER_OF_BUTTON = {"aide-button": "aide-menu", "menu-button": "room-menu"}
# The panel that each tab of the Salon shows.
PANEL_OF_TAB = {"discussion": "chat-panel", "players": "roster"}


def is_closed(locator: Locator) -> bool:
    """Tell whether a popover, the Salon or a panel is closed (`hidden` is set).

    Args:
        locator: The element; the call fails when it is not on the page.

    Returns:
        True while the element has the `hidden` attribute.
    """
    hidden = locator.get_attribute("hidden", timeout=WAIT_TIMEOUT_MS)
    return hidden is not None


def expect_open(locator: Locator) -> None:
    """Wait until an element shows and has no `hidden` attribute."""
    expect(locator).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    expect(locator).not_to_have_attribute("hidden", "", timeout=WAIT_TIMEOUT_MS)


def _open_popover(page: Page, button_id: str) -> None:
    popover = page.get_by_test_id(POPOVER_OF_BUTTON[button_id])
    if is_closed(popover):
        page.get_by_test_id(button_id).click(timeout=WAIT_TIMEOUT_MS)
    expect_open(popover)


def open_aide(page: Page) -> None:
    """Click `aide-button` when `aide-menu` is closed, then wait until it is open."""
    _open_popover(page, "aide-button")


def open_menu(page: Page) -> None:
    """Click `menu-button` when `room-menu` is closed, then wait until it is open."""
    _open_popover(page, "menu-button")


def show_tab(page: Page, tab: Tab) -> None:
    """Open the Salon on one of its tabs and wait until the tab's panel shows.

    Clicks `chat-toggle` when the Salon is closed, then the tab when it is not
    selected.

    Args:
        page: The room page, once it shows a snapshot.
        tab: `"discussion"` (`salon-tab-discussion`, panel `chat-panel`) or
            `"players"` (`salon-tab-players`, panel `roster`).
    """
    salon = page.get_by_test_id("salon")
    if is_closed(salon):
        page.get_by_test_id("chat-toggle").click(timeout=WAIT_TIMEOUT_MS)
    expect_open(salon)
    tab_button = page.get_by_test_id(f"salon-tab-{tab}")
    if tab_button.get_attribute("aria-selected", timeout=WAIT_TIMEOUT_MS) != "true":
        tab_button.click(timeout=WAIT_TIMEOUT_MS)
    expect(tab_button).to_have_attribute("aria-selected", "true")
    expect_open(page.get_by_test_id(PANEL_OF_TAB[tab]))


def open_host_settings(page: Page) -> None:
    """`open_menu`, then a click on `host-settings-open`; wait until it is open."""
    open_menu(page)
    page.get_by_test_id("host-settings-open").click(timeout=WAIT_TIMEOUT_MS)
    expect(page.get_by_test_id("host-settings")).to_have_attribute(
        "open", "", timeout=WAIT_TIMEOUT_MS
    )


# ---- Keyboard variants, for keyboard-only tests -----------------------------------


def press_with_keyboard(page: Page, test_id: str) -> None:
    """Move the focus to a control with spec 035's `tab_to`, then press `Enter`."""
    Walker(page).tab_to(test_id)
    page.keyboard.press("Enter")


def _open_popover_with_keyboard(page: Page, button_id: str) -> None:
    popover = page.get_by_test_id(POPOVER_OF_BUTTON[button_id])
    if is_closed(popover):
        press_with_keyboard(page, button_id)
    expect_open(popover)


def open_aide_with_keyboard(page: Page) -> None:
    """`tab_to` `aide-button`, `Enter` when `aide-menu` is closed; wait until open."""
    _open_popover_with_keyboard(page, "aide-button")


def open_menu_with_keyboard(page: Page) -> None:
    """`tab_to` `menu-button`, `Enter` when `room-menu` is closed; wait until open."""
    _open_popover_with_keyboard(page, "menu-button")


def show_tab_with_keyboard(page: Page, tab: Tab) -> None:
    """Open the Salon on a tab with the keyboard only.

    `tab_to` `chat-toggle` and `Enter` when the Salon is closed; then, when the tab
    is not selected, `tab_to` the selected tab (the one Tab stop of the tab list)
    and `ArrowRight`, which selects the other tab.
    """
    salon = page.get_by_test_id("salon")
    if is_closed(salon):
        press_with_keyboard(page, "chat-toggle")
    expect_open(salon)
    tab_button = page.get_by_test_id(f"salon-tab-{tab}")
    if tab_button.get_attribute("aria-selected", timeout=WAIT_TIMEOUT_MS) != "true":
        other = "players" if tab == "discussion" else "discussion"
        Walker(page).tab_to(f"salon-tab-{other}")
        page.keyboard.press("ArrowRight")
    expect(tab_button).to_have_attribute("aria-selected", "true")
    expect_open(page.get_by_test_id(PANEL_OF_TAB[tab]))


def open_host_settings_with_keyboard(page: Page) -> None:
    """`open_menu_with_keyboard`, then `tab_to` `host-settings-open` and `Enter`."""
    open_menu_with_keyboard(page)
    press_with_keyboard(page, "host-settings-open")
    expect(page.get_by_test_id("host-settings")).to_have_attribute(
        "open", "", timeout=WAIT_TIMEOUT_MS
    )
