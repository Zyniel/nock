"""Tests of spec 009, AC-3 and AC-4: the in-app keyboard and the clue bar above it.

AC-3 and AC-4 use a mocked socket on FX-01 and touch contexts (AC-3 also a
desktop context and a narrow desktop window with a fine pointer, which show no
keyboard). In Chromium the touch emulation alone makes `(pointer: coarse)` true;
in Firefox and WebKit the touch contexts also run an init script that makes
`window.matchMedia("(pointer: coarse)")` report a match. The shared setup is in
`spec009_harness`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import EditLetter, Erase, grid_view
from spec009_harness import (
    ACROSS_AMEN,
    ACROSS_W1,
    MockRoomSocket,
    cell_at,
    expect_selection,
    grid_from_text,
    open_fx01,
    open_mock_room,
    sent_messages,
    settle,
    snapshot_frame,
    tap,
    wait_until,
)

MIN_CLUE_FONT_PX = 14.0
MIN_GRID_VIEWPORT_PX = 100.0
EPSILON = 0.01

KEYBOARD_ROWS = ["AZERTYUIOP", "QSDFGHJKLM", "WXCVBN"]

# Makes `matchMedia("(pointer: coarse)")` report a match, other queries unchanged.
COARSE_POINTER_SCRIPT = """
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\\s/g, '') !== '(pointer:coarse)') {
      return result;
    }
    return new Proxy(result, {
      get(target, property) {
        if (property === 'matches') {
          return true;
        }
        const value = target[property];
        return typeof value === 'function' ? value.bind(target) : value;
      },
    });
  };
})();
"""


# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def make_touch_page(
    browser: Browser, browser_name: str, width: int, height: int
) -> tuple[Page, Callable[[], None]]:
    """Open a touch page of the spec's harness; return it and its closer."""
    viewport = {"width": width, "height": height}
    if browser_name == "firefox":
        context = browser.new_context(
            viewport=viewport, has_touch=True, device_scale_factor=2
        )
    else:
        context = browser.new_context(
            viewport=viewport,
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    return context.new_page(), context.close


@pytest.fixture
def touch_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A 360 by 740 touch page."""
    page, close = make_touch_page(browser, browser_name, 360, 740)
    try:
        yield page
    finally:
        close()


@pytest.fixture(params=[(360, 740), (740, 360)], ids=["portrait", "landscape"])
def oriented_touch_page(
    request: pytest.FixtureRequest, browser: Browser, browser_name: str
) -> Iterator[Page]:
    """A touch page in portrait (360 by 740) and in landscape (740 by 360)."""
    width, height = request.param
    page, close = make_touch_page(browser, browser_name, width, height)
    try:
        yield page
    finally:
        close()


@pytest.fixture
def narrow_desktop_page(browser: Browser) -> Iterator[Page]:
    """A narrow window with a fine pointer: no touch, no init script."""
    context = browser.new_context(viewport={"width": 360, "height": 740})
    try:
        yield context.new_page()
    finally:
        context.close()


def touch_tap(page: Page, row: int, column: int) -> None:
    cell_at(page, row, column).tap()


def expect_letter(page: Page, row: int, column: int, letter: str) -> None:
    expect(cell_at(page, row, column)).to_have_attribute("data-letter", letter)


def sent_edits(mock: MockRoomSocket) -> list[EditLetter | Erase]:
    """The `edit_letter` and `erase` messages the page sent, in order."""
    edits: list[EditLetter | Erase] = []
    for message in sent_messages(mock):
        if isinstance(message, EditLetter | Erase):
            edits.append(message)
    return edits


def put(row: int, column: int, letter: str) -> EditLetter:
    return EditLetter(row=row, column=column, letter=letter)


def rub(row: int, column: int) -> Erase:
    return Erase(row=row, column=column)


# ---- AC-3: the in-app keyboard -----------------------------------------------


def keys_of_row(row: Locator) -> str:
    """The `data-key` values of the keys of a row, joined."""
    script = "(elements) => elements.map((e) => e.getAttribute('data-key')).join('')"
    return str(row.locator('[data-testid="key"]').evaluate_all(script))


def key_named(page: Page, letter: str) -> Locator:
    return page.locator(f'[data-testid="key"][data-key="{letter}"]')


def active_element_is_editable(page: Page) -> bool:
    script = (
        "() => { const e = document.activeElement;"
        " if (!e) { return false; }"
        " return ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.tagName)"
        " || e.isContentEditable; }"
    )
    return bool(page.evaluate(script))


def count_editable_in_page_areas(page: Page) -> int:
    """Count editable elements in the grid area, the clue bar and the keyboard."""
    script = (
        "() => { let total = 0;"
        " for (const id of ['grid-viewport', 'clue-bar', 'keyboard', 'grid']) {"
        ' const area = document.querySelector(`[data-testid="${id}"]`);'
        " if (!area) { continue; }"
        " total += area.querySelectorAll("
        "'input, textarea, select, [contenteditable]').length; }"
        " return total; }"
    )
    return int(page.evaluate(script))


def test_ac3_touch_context_shows_the_azerty_keyboard(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)

    keyboard = touch_page.get_by_test_id("keyboard")
    expect(keyboard).to_be_visible()
    expect(keyboard).to_have_attribute("aria-label", "Clavier")
    rows = touch_page.get_by_test_id("keyboard-row")
    expect(rows).to_have_count(3)
    for index, expected_keys in enumerate(KEYBOARD_ROWS):
        assert keys_of_row(rows.nth(index)) == expected_keys
    expect(touch_page.get_by_test_id("key")).to_have_count(26)
    expect(touch_page.get_by_test_id("key-delete")).to_have_count(1)
    expect(keyboard.get_by_test_id("key-delete")).to_have_count(1)


def test_ac3_keys_are_buttons_showing_their_letter(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()

    script = (
        "(elements) => elements.map((e) => [e.tagName,"
        " e.getAttribute('data-key'), e.textContent.trim()])"
    )
    keys = touch_page.get_by_test_id("key").evaluate_all(script)

    assert len(keys) == 26
    for tag, data_key, text in keys:
        assert tag == "BUTTON"
        assert text == data_key


def test_ac3_the_delete_key_is_an_icon_button_after_the_last_letters(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)
    delete_key = touch_page.get_by_test_id("key-delete")

    expect(delete_key).to_be_visible()
    expect(delete_key).to_have_attribute("aria-label", "Effacer")
    assert delete_key.evaluate("(element) => element.tagName") == "BUTTON"
    assert delete_key.evaluate("(element) => element.textContent.trim()") == ""
    third_row = touch_page.get_by_test_id("keyboard-row").nth(2)
    last_testid = third_row.evaluate(
        "(row) => row.lastElementChild.getAttribute('data-testid')"
    )
    assert last_testid == "key-delete"
    assert third_row.get_by_test_id("key-delete").count() == 1


def test_ac3_tapping_keys_types_then_delete_erases_through_spec_008_rules(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    grid = touch_page.get_by_test_id("grid")
    touch_tap(touch_page, 1, 0)
    expect_selection(touch_page, 1, 0, "across", ACROSS_W1)

    key_named(touch_page, "T").tap()
    expect_letter(touch_page, 1, 0, "T")
    expect_selection(touch_page, 1, 1, "across", ACROSS_W1)
    expect(grid).to_be_focused()

    key_named(touch_page, "A").tap()
    expect_letter(touch_page, 1, 1, "A")
    expect_selection(touch_page, 1, 2, "across", ACROSS_W1)
    expect(grid).to_be_focused()
    assert sent_edits(mock) == [put(1, 0, "T"), put(1, 1, "A")]

    touch_page.get_by_test_id("key-delete").tap()

    expect_letter(touch_page, 1, 1, "")
    expect_letter(touch_page, 1, 0, "T")
    expect_selection(touch_page, 1, 1, "across", ACROSS_W1)
    expect(grid).to_be_focused()
    wait_until(touch_page, lambda: len(sent_edits(mock)) == 3)
    assert sent_edits(mock) == [put(1, 0, "T"), put(1, 1, "A"), rub(1, 1)]


def test_ac3_each_tap_on_the_same_key_is_one_letter(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    touch_tap(touch_page, 1, 0)

    key_named(touch_page, "E").tap()
    key_named(touch_page, "E").tap()
    key_named(touch_page, "E").tap()

    expect_letter(touch_page, 1, 2, "E")
    expect_letter(touch_page, 1, 0, "E")
    expect_letter(touch_page, 1, 1, "E")
    expect_selection(touch_page, 1, 3, "across", ACROSS_W1)
    settle(touch_page)
    assert sent_edits(mock) == [put(1, 0, "E"), put(1, 1, "E"), put(1, 2, "E")]


def test_ac3_keys_do_nothing_without_a_selection(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    frames_before = len(mock.frames_without_pings())

    key_named(touch_page, "Q").tap()
    touch_page.get_by_test_id("key-delete").tap()

    settle(touch_page)
    expect(touch_page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(18)
    assert len(mock.frames_without_pings()) == frames_before


def test_ac3_focus_is_never_on_an_editable_element_and_none_exists(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    assert count_editable_in_page_areas(touch_page) == 0
    assert active_element_is_editable(touch_page) is False

    touch_tap(touch_page, 1, 0)
    assert active_element_is_editable(touch_page) is False
    for letter in ["T", "A", "M"]:
        key_named(touch_page, letter).tap()
        assert active_element_is_editable(touch_page) is False
    touch_page.get_by_test_id("key-delete").tap()
    assert active_element_is_editable(touch_page) is False
    touch_page.get_by_test_id("clue-bar").tap()
    assert active_element_is_editable(touch_page) is False
    assert count_editable_in_page_areas(touch_page) == 0


def test_ac3_desktop_context_has_no_keyboard(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    settle(page)
    expect(page.get_by_test_id("keyboard")).to_have_count(0)
    expect(page.get_by_test_id("key")).to_have_count(0)
    expect(page.get_by_test_id("key-delete")).to_have_count(0)
    page.keyboard.press("T")
    expect_letter(page, 1, 0, "T")


def test_ac3_a_narrow_window_with_a_fine_pointer_has_no_keyboard(
    narrow_desktop_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(narrow_desktop_page, live_server, fx01_grid)

    settle(narrow_desktop_page)
    expect(narrow_desktop_page.get_by_test_id("keyboard")).to_have_count(0)
    expect(narrow_desktop_page.get_by_test_id("key")).to_have_count(0)


def test_ac3_no_keyboard_before_the_first_snapshot_then_it_appears(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(touch_page, live_server)
    settle(touch_page)
    expect(touch_page.get_by_test_id("keyboard")).to_have_count(0)

    mock.send(snapshot_frame(grid_view(fx01_grid), 0))

    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    expect(touch_page.get_by_test_id("key")).to_have_count(26)


# ---- AC-4: the clue bar stays above the keyboard -----------------------------


def test_ac4_clue_bar_is_above_the_keyboard_inside_the_window(
    oriented_touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    page = oriented_touch_page
    open_fx01(page, live_server, fx01_grid)
    keyboard = page.get_by_test_id("keyboard")
    expect(keyboard).to_be_visible()

    touch_tap(page, 3, 1)

    bar = page.get_by_test_id("clue-bar")
    text = page.get_by_test_id("clue-bar-text")
    expect(bar).to_have_attribute("data-word", ACROSS_AMEN)
    expect(text).to_be_visible()
    expect(text).to_have_text("Fin de prière")
    bar_box = bar.bounding_box()
    keyboard_box = keyboard.bounding_box()
    viewport_box = page.get_by_test_id("grid-viewport").bounding_box()
    assert bar_box is not None
    assert keyboard_box is not None
    assert viewport_box is not None
    window_height = float(page.evaluate("() => window.innerHeight"))
    font_size = str(text.evaluate("(e) => getComputedStyle(e).fontSize"))

    assert bar_box["y"] + bar_box["height"] <= keyboard_box["y"] + EPSILON
    assert keyboard_box["y"] + keyboard_box["height"] <= window_height + EPSILON
    assert bar_box["y"] >= 0
    assert float(font_size.removesuffix("px")) >= MIN_CLUE_FONT_PX
    assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX
