"""Tests of spec 043, AC-29: the page reads in the design's order and every control
shows its ring.

At 1280 by 720 the focusable elements that show come in the order: the brand link
(`client/hud.md` AC-20), the computer top bar's five buttons, the grid, the
clue bar's four buttons, then the Salon. From the grid, `Escape` then `Tab` reaches
`clue-prev` and `Escape` then `Shift+Tab` reaches `menu-button`. The brand and each
top-bar button have the navy ring outside them, each clue bar button the white ring
inside it. At 360 by 740 the phone top bar's order holds (it has no brand).

Choices where the spec leaves room:

- "The focusable elements that show": the `a[href]`, `button`, `input`, `select`,
  `textarea` and `[tabindex]` elements that are not disabled, have a `tabIndex` of
  0 or more, a box and `visibility: visible`, and are not inside an `inert`
  element. They are named by their test id (their tag when they have none).
- `react-button` and `flag-button` are focusable once a word is selected, so the
  order is read after a tap on (1, 0), the cell the criterion selects.
- "Inside the window" for a ring: the outline's outer edge (the box grown by the
  outline's offset and width) lies inside the window, 1 px tolerance.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec035_harness import Walker
from spec042_harness import colour_of
from spec043_harness import (
    CLUE_BAR_BUTTONS,
    COMPUTER_BUTTONS,
    NAVY,
    PHONE_BUTTONS,
    WHITE,
    colour_matches,
    expect_selected,
    focused_test_id,
    fx01_view,
    open_room,
    players_up_to,
    press_cell,
    snapshot_frame,
    style_of,
)

FOCUSABLE_SCRIPT = r"""
() => {
  const salon = document.querySelector('[data-testid="salon"]');
  const found = [];
  const selector = 'a[href], button, input, select, textarea, [tabindex]';
  for (const element of document.querySelectorAll(selector)) {
    if (element.disabled || element.tabIndex < 0) {
      continue;
    }
    if (element.getClientRects().length === 0
        || getComputedStyle(element).visibility !== 'visible') {
      continue;
    }
    if (element.closest('[inert]') !== null) {
      continue;
    }
    found.push({
      name: element.getAttribute('data-testid') || element.tagName.toLowerCase(),
      inSalon: salon !== null && salon.contains(element),
    });
  }
  return found;
}
"""

RING_SCRIPT = r"""
() => {
  const element = document.activeElement;
  const style = getComputedStyle(element);
  const box = element.getBoundingClientRect();
  const grow = parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth);
  return {
    inside: box.left - grow >= -1 && box.top - grow >= -1
      && box.right + grow <= innerWidth + 1 && box.bottom + grow <= innerHeight + 1,
  };
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


def open_at(
    window: OpenWindow, base_url: str, grid: Grid, width: int, height: int
) -> Page:
    page = window(width, height, False)
    open_room(page, base_url, snapshot_frame(fx01_view(grid), players_up_to(3)))
    press_cell(page, 1, 0)
    return page


def focusable(page: Page) -> list[dict[str, object]]:
    found = page.evaluate(FOCUSABLE_SCRIPT)
    assert isinstance(found, list), found
    return found


def ring_problems(
    page: Page, test_id: str, colour: tuple[int, int, int], offset: str
) -> list[str]:
    """How the focused element's ring differs from a 2 px solid ring of `colour`."""
    element = page.get_by_test_id(test_id)
    problems: list[str] = []
    if style_of(element, "outlineStyle") != "solid":
        problems.append(f"{test_id}: outline style {style_of(element, 'outlineStyle')}")
    if style_of(element, "outlineWidth") != "2px":
        problems.append(f"{test_id}: outline width {style_of(element, 'outlineWidth')}")
    outline_colour = colour_of(element, "outlineColor")
    if not colour_matches(outline_colour, colour):
        problems.append(f"{test_id}: outline colour {outline_colour}")
    if style_of(element, "outlineOffset") != offset:
        problems.append(
            f"{test_id}: outline offset {style_of(element, 'outlineOffset')}"
        )
    return problems


# ---- AC-29 ---------------------------------------------------------------------------


def test_ac29_on_a_computer_the_page_reads_top_bar_grid_clue_bar_then_salon(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_at(window, live_server, fx01_grid, 1280, 720)

    found = focusable(page)
    names = [str(item["name"]) for item in found]
    expected = [
        "topbar-brand",
        *COMPUTER_BUTTONS,
        "grid",
        *CLUE_BAR_BUTTONS,
        "salon-tab-discussion",
    ]

    assert names[: len(expected)] == expected
    for item in found[len(expected) - 1 :]:
        assert item["inSalon"] is True, item


def test_ac29_on_a_phone_the_page_reads_the_phone_top_bar_then_grid_and_clue_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_at(window, live_server, fx01_grid, 360, 740)

    names = [str(item["name"]) for item in focusable(page)]
    expected = [*PHONE_BUTTONS, "grid", *CLUE_BAR_BUTTONS]

    assert names[: len(expected)] == expected


def test_ac29_escape_then_tab_leaves_the_grid_for_clue_prev(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_at(window, live_server, fx01_grid, 1280, 720)
    expect(page.get_by_test_id("grid")).to_be_focused()

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect(page.get_by_test_id("clue-prev")).to_be_focused()
    expect_selected(page, 1, 0)


def test_ac29_escape_then_shift_tab_leaves_the_grid_for_menu_button(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_at(window, live_server, fx01_grid, 1280, 720)
    expect(page.get_by_test_id("grid")).to_be_focused()

    page.keyboard.press("Escape")
    page.keyboard.press("Shift+Tab")

    expect(page.get_by_test_id("menu-button")).to_be_focused()


@pytest.mark.parametrize("test_id", ["topbar-brand", *COMPUTER_BUTTONS])
def test_ac29_each_top_bar_button_shows_the_navy_ring_inside_the_window(
    window: OpenWindow, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    page = open_at(window, live_server, fx01_grid, 1280, 720)

    Walker(page).tab_to(test_id)
    place = page.evaluate(RING_SCRIPT)

    assert focused_test_id(page) == test_id
    assert ring_problems(page, test_id, NAVY, "2px") == []
    assert place["inside"] is True


@pytest.mark.parametrize("test_id", CLUE_BAR_BUTTONS)
def test_ac29_each_clue_bar_button_shows_the_white_ring_inside_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    page = open_at(window, live_server, fx01_grid, 1280, 720)

    Walker(page).tab_to(test_id)

    assert focused_test_id(page) == test_id
    assert ring_problems(page, test_id, WHITE, "-4px") == []
