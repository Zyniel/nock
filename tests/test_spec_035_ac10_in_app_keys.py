"""Tests of spec 035: the in-app keyboard keys stay out of the Tab order (AC-10).

The setup the test files of spec 035 share is in `tests/spec035_harness.py`.

Choices where the spec leaves room:

- AC-10, backward Tab order: the keys come after the grid in document order, so a
  backward walk from the grid never crosses them. The backward walk starts from
  the sentinel of the harness (the last child of `body`, after the keys), must
  come back to the grid without landing on a key, then goes on as the spec's walk
  from the grid.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import (
    FOCUS_OUTLINE_SCRIPT,
    MAX_TABS,
    MIN_FOCUS_CONTRAST,
    MIN_OUTLINE_PX,
    SENTINEL_TEST_ID,
    add_sentinel,
    build_fx01_grid,
    build_reference_catalogue,
    cell_at,
    expect_focus_on_grid,
    expect_focus_on_sentinel,
    load_fr,
    open_room,
)

# ---- Fixtures: thin wrappers around spec035_harness -------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (also served by live_server)."""
    return build_reference_catalogue(fx01_grid)


# ---- AC-10: the in-app keyboard keys stay out of the Tab order --------------------

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

KEY_MARKUP_SCRIPT = """
() => {
  const keys = [...document.querySelectorAll('[data-testid="key"]')];
  const reports = keys.map(key => ({
    name: key.getAttribute('data-key'),
    tag: key.tagName,
    type: key.getAttribute('type'),
    tabindex: key.getAttribute('tabindex'),
    tabIndex: key.tabIndex,
  }));
  const del = document.querySelector('[data-testid="key-delete"]');
  reports.push({
    name: 'delete',
    tag: del.tagName,
    type: del.getAttribute('type'),
    tabindex: del.getAttribute('tabindex'),
    tabIndex: del.tabIndex,
  });
  return reports;
}
"""

KEY_HIDING_SCRIPT = """
() => {
  const targets = [
    ...document.querySelectorAll('[data-testid="key"]'),
    document.querySelector('[data-testid="key-delete"]'),
  ];
  const offenders = [];
  for (const key of targets) {
    for (let node = key; node; node = node.parentElement) {
      const role = node.getAttribute('role');
      const hides = node.getAttribute('aria-hidden') === 'true'
        || node.hasAttribute('inert')
        || role === 'presentation' || role === 'none';
      if (hides) {
        offenders.push([key.getAttribute('data-key'), node.tagName]);
      }
    }
  }
  return offenders;
}
"""

FOCUSED_KIND_SCRIPT = """
() => {
  const element = document.activeElement;
  if (element === null) {
    return null;
  }
  return {
    testId: element.getAttribute('data-testid'),
    isBody: element === document.body,
  };
}
"""

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@pytest.fixture
def touch_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A 360 by 740 touch page, as in spec 009's harness."""
    viewport = {"width": 360, "height": 740}
    if browser_name == "firefox":
        context = browser.new_context(viewport=viewport, has_touch=True)
    else:
        context = browser.new_context(viewport=viewport, has_touch=True, is_mobile=True)
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    yield context.new_page()
    context.close()


def key_of(page: Page, letter: str) -> Locator:
    return page.locator(f'[data-testid="key"][data-key="{letter}"]')


def test_ac10_every_key_is_a_button_with_tabindex_minus_one(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("key")).to_have_count(26)

    reports = touch_page.evaluate(KEY_MARKUP_SCRIPT)

    assert sorted(report["name"] for report in reports) == sorted([*LETTERS, "delete"])
    for report in reports:
        assert report["tag"] == "BUTTON", report
        assert report["type"] == "button", report
        assert report["tabindex"] == "-1", report
        assert report["tabIndex"] == -1, report


def test_ac10_every_letter_key_has_the_letter_as_accessible_name(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    keyboard = touch_page.get_by_test_id("keyboard")

    for letter in LETTERS:
        by_name = keyboard.get_by_role("button", name=letter, exact=True)
        expect(by_name, letter).to_have_count(1)
        expect(by_name, letter).to_have_attribute("data-key", letter)
        expect(by_name, letter).to_have_attribute("data-testid", "key")


def test_ac10_the_delete_key_is_named_effacer(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)

    name = load_fr()["keyboard.delete"]
    assert name == "Effacer"
    by_name = touch_page.get_by_role("button", name=name, exact=True)
    expect(by_name).to_have_count(1)
    expect(by_name).to_have_attribute("data-testid", "key-delete")


def test_ac10_no_key_and_no_ancestor_hides_the_keys_from_assistive_technology(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)

    assert touch_page.evaluate(KEY_HIDING_SCRIPT) == []


def test_ac10_a_tap_on_a_key_keeps_the_focus_on_the_grid(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)

    cell_at(touch_page, 1, 0).tap()
    expect_focus_on_grid(touch_page)
    key_of(touch_page, "T").tap()
    expect(cell_at(touch_page, 1, 0)).to_contain_text("T")
    expect_focus_on_grid(touch_page)
    touch_page.get_by_test_id("key-delete").tap()
    expect_focus_on_grid(touch_page)


KEY_TEST_IDS = ("key", "key-delete")


def walk_the_tab_order(page: Page, key: str, presses: int) -> str | None:
    """Press `key` up to `presses` times; fail as soon as the focus is on a key.

    Args:
        page: The touch page.
        key: `Tab` or `Shift+Tab`.
        presses: How many presses at most.

    Returns:
        `grid` or `body` when the walk stopped because the focus reached the grid
        or `document.body`, or None when it made every press.
    """
    for _ in range(presses):
        page.keyboard.press(key)
        focused = page.evaluate(FOCUSED_KIND_SCRIPT)
        assert focused is not None
        assert focused["testId"] not in KEY_TEST_IDS, (key, focused)
        if focused["testId"] == "grid":
            return "grid"
        if focused["isBody"]:
            return "body"
    return None


def test_ac10_tab_never_lands_on_a_key(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    cell_at(touch_page, 1, 0).tap()
    expect_focus_on_grid(touch_page)

    touch_page.keyboard.press("Escape")
    walk_the_tab_order(touch_page, "Tab", MAX_TABS + 1)


def test_ac10_shift_tab_from_after_the_keys_never_lands_on_a_key(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    cell_at(touch_page, 1, 0).tap()
    expect_focus_on_grid(touch_page)
    # The keys come after the grid in document order, so a backward walk from the
    # grid never crosses them. The sentinel is the last child of `body`, after the
    # keys: from there, Shift+Tab has to cross them to come back to the grid.
    add_sentinel(touch_page)
    touch_page.get_by_test_id(SENTINEL_TEST_ID).focus()
    expect_focus_on_sentinel(touch_page)

    stop = walk_the_tab_order(touch_page, "Shift+Tab", MAX_TABS)

    assert stop == "grid", f"Shift+Tab from the sentinel stopped at {stop}"
    # Then the spec's walk from the grid: Escape, Shift+Tab and up to 60 more.
    touch_page.keyboard.press("Escape")
    walk_the_tab_order(touch_page, "Shift+Tab", MAX_TABS + 1)


def test_ac10_a_key_focused_with_focus_shows_the_visible_focus(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    cell_at(touch_page, 1, 0).tap()
    expect_focus_on_grid(touch_page)
    touch_page.keyboard.press("ArrowRight")

    key_of(touch_page, "A").evaluate("element => element.focus()")

    outline = touch_page.evaluate(FOCUS_OUTLINE_SCRIPT)
    assert outline["style"] not in ("none", "auto"), outline
    assert outline["width"] >= MIN_OUTLINE_PX, outline
    assert outline["ratio"] >= MIN_FOCUS_CONTRAST, outline
