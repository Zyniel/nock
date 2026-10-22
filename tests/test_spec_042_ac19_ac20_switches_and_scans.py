"""Tests of spec 042, AC-19 and AC-20: the two switches as controls, and the
contrast and language of the new cells.

AC-19 is tested as spec 043 (the design's room layout) refined it: the switches
are items of `room-menu`, opened from `menu-button`. Its earlier reading (the
switches in `room-toolbar`, with their texts, in one row with the toolbar's other
buttons) is the one the criterion's note of 2026-10-22 records.

AC-20 scans the state of AC-17 without the catch-up, plus `p2`'s flag on IDES
and (1, 1) holding `X` wrong, with spec 035's contrast scan (AC-8) and language
scan (AC-9), with `access-switch` off and on.

Choices where the spec leaves room:

- AC-19, "its first three items": the outermost elements with a `data-testid`
  that show inside the open `room-menu`, in document order (spec 043's harness,
  `shown_test_ids`).
- AC-19, "the item's text without its `aria-hidden` detail": the text of the
  switch outside its `aria-hidden` parts and its `svg`s (spec 043's `label_of`).
- AC-19, "inside the window": the switch's box, after `scrollIntoView`, lies in
  the window with 1 px of tolerance (spec 043's position tolerance).
- AC-19, accounts are on when `GET /api/account` answers (spec 033's mocked
  account routes).
- AC-20, the language scan accepts the nicknames as the page shows them, the
  clue texts of FX-01, the room code and its link.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Direction, FlagView, GridView, PlayerView, grid_view
from room_panels import open_menu
from spec019_harness import (
    CONTEXT_KINDS,
    LAYOUT_EPSILON_PX,
    WINDOW_IDS,
    WINDOW_SIZES,
    OpenWindow,
    layout_problems,
    press,
    window_opener,
    with_letter_cells,
)
from spec024_harness import (
    contrast_problems,
    language_data,
    language_problems,
    outline_problems,
)
from spec033_harness import AccountRoutes
from spec035_harness import Walker
from spec042_harness import (
    ACCESS_SWITCH,
    DISPLAY_NICKNAMES,
    IDES,
    TINT_SWITCH,
    WAIT_TIMEOUT_MS,
    ChangeList,
    cell_at,
    click_switch,
    fx01_view,
    load_fr,
    make_catalogue,
    me,
    open_room,
    open_toolbar_setup_room,
    player,
    selecting,
    tap,
)
from spec043_harness import label_of, shown_test_ids

SWITCHES = [TINT_SWITCH, ACCESS_SWITCH]
SWITCH_TEXT_KEYS = {TINT_SWITCH: "others_tint.switch", ACCESS_SWITCH: "access.switch"}
MENU_SWITCHES = ["authors-switch", TINT_SWITCH, ACCESS_SWITCH]
SCAN_SIZES = [(1280, 720), (360, 740)]

# ---- Fixtures: thin wrappers around the harnesses -------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- In-page scripts ------------------------------------------------------------

MARKUP_SCRIPT = r"""
element => ({
  tag: element.tagName,
  type: element.getAttribute('type'),
  pressed: element.getAttribute('aria-pressed'),
  disabled: element.disabled,
})
"""

# The element at the centre of a switch after `scrollIntoView`, and whether the
# switch's box then lies inside the window (`epsilon` px of tolerance).
HIT_SCRIPT = r"""
([testId, epsilon]) => {
  const own = document.querySelector(`[data-testid="${testId}"]`);
  own.scrollIntoView({block: 'nearest', inline: 'nearest'});
  const box = own.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2, box.top + box.height / 2
  );
  return {
    hits: hit !== null && (hit === own || own.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
    inside: box.left >= -epsilon && box.top >= -epsilon
      && box.right <= innerWidth + epsilon && box.bottom <= innerHeight + epsilon,
    box: [box.left, box.top, box.right, box.bottom],
  };
}
"""


# ---- AC-19: the switches as controls --------------------------------------------


def test_ac19_the_menus_first_three_items_are_the_three_switches_in_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    open_menu(page)

    items = shown_test_ids(page.get_by_test_id("room-menu"))

    assert items[:3] == MENU_SWITCHES, items


@pytest.mark.parametrize("test_id", SWITCHES)
def test_ac19_each_switch_is_a_button_with_aria_pressed_and_its_french_label(
    page: Page, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    switch = page.get_by_test_id(test_id)
    expect(switch).to_have_count(1)

    markup = switch.evaluate(MARKUP_SCRIPT)
    tap(page, 2, 2)
    later = switch.evaluate(MARKUP_SCRIPT)
    open_menu(page)
    label = label_of(switch)

    assert markup["tag"] == "BUTTON"
    assert markup["type"] == "button"
    assert markup["pressed"] in ("true", "false")
    assert markup["disabled"] is False
    assert later["disabled"] is False
    assert label is not None
    assert label["text"] == load_fr()[SWITCH_TEXT_KEYS[test_id]]


def test_ac19_with_accounts_on_both_switches_come_before_account_open(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    AccountRoutes().install(page)
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    expect(page.get_by_test_id("account-open")).to_have_count(
        1, timeout=WAIT_TIMEOUT_MS
    )
    open_menu(page)

    items = shown_test_ids(page.get_by_test_id("room-menu"))

    assert items[:3] == MENU_SWITCHES, items
    assert "account-open" in items, items
    assert items.index("account-open") > items.index(ACCESS_SWITCH), items


@pytest.mark.parametrize("test_id", SWITCHES)
def test_ac19_from_the_keyboard_each_switch_shows_the_ring_and_enter_flips_it(
    page: Page, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    switch = page.get_by_test_id(test_id)
    expect(switch).to_have_count(1)
    before = switch.get_attribute("aria-pressed")
    walker = Walker(page)
    walker.tab_to("menu-button")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("room-menu")).to_be_visible(timeout=WAIT_TIMEOUT_MS)

    walker.tab_to(test_id)
    reached = walker.reached[-1]
    page.keyboard.press("Enter")

    assert (
        outline_problems(
            reached.outline_style, reached.outline_width, reached.outline_contrast
        )
        == []
    )
    flipped = "false" if before == "true" else "true"
    expect(switch).to_have_attribute("aria-pressed", flipped)
    expect(switch).to_be_focused()
    expect(page.get_by_test_id("room-menu")).to_be_visible()
    assert page.get_by_test_id("room-menu").get_attribute("hidden") is None


def open_menu_in_toolbar_setup(
    page: Page, base_url: str, grid: Grid, touch: bool
) -> None:
    """Spec 024 AC-8's setup (8 players, 100 feed items, (3, 1) tapped), Menu open."""
    open_toolbar_setup_room(page, base_url, grid)
    press(cell_at(page, 3, 1), touch)
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")
    open_menu(page)


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac19_the_grid_keeps_its_room_with_the_menu_open(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)

    open_menu_in_toolbar_setup(page, live_server, fx01_grid, touch)

    expect(page.get_by_test_id(TINT_SWITCH)).to_have_count(1)
    expect(page.get_by_test_id(ACCESS_SWITCH)).to_have_count(1)
    assert layout_problems(page, touch) == []


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac19_each_switch_lies_in_the_window_and_a_pointer_at_its_centre_reaches_it(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_menu_in_toolbar_setup(page, live_server, fx01_grid, touch)

    problems: list[str] = []
    for test_id in SWITCHES:
        expect(page.get_by_test_id(test_id)).to_have_count(1)
        hit = page.evaluate(HIT_SCRIPT, [test_id, LAYOUT_EPSILON_PX])
        if hit["inside"] is not True:
            problems.append(f"{test_id} {hit['box']} is not inside the window")
        if hit["hits"] is not True:
            problems.append(f"{test_id}: elementFromPoint found {hit['hit']}")
    assert problems == []


# ---- AC-20: contrast and language of the new cells ------------------------------


def ac20_players() -> list[PlayerView]:
    """`p1`, and `p2` to `p5` (colours 1 to 4) selecting (0, 1) down."""
    on_0_1 = selecting(0, 1, Direction.DOWN)
    players = [me()]
    for number in range(2, 6):
        players.append(player(f"p{number}", number - 1, selection=on_0_1))
    return players


def ac20_view(grid: Grid) -> GridView:
    """(0, 1) holds `N` revealed and (1, 1) holds `X` wrong."""
    changes: ChangeList = [
        (0, 1, {"letter": "N", "author": None, "locked": True, "revealed": True}),
        (1, 1, {"letter": "X", "author": "p1", "wrong": True}),
    ]
    return with_letter_cells(grid_view(grid), changes)


def open_ac20(
    page: Page, base_url: str, grid: Grid, size: tuple[int, int], access: bool
) -> None:
    """The state of AC-20 at `size`, with `access-switch` on when `access`."""
    page.set_viewport_size({"width": size[0], "height": size[1]})
    flags = [FlagView(player_id="p2", clue=IDES)]
    open_room(page, base_url, ac20_view(grid), ac20_players(), flags=flags)
    tap(page, 0, 1)
    if access:
        click_switch(page, ACCESS_SWITCH, "true")


SCAN_CASES = [(size, access) for size in SCAN_SIZES for access in (False, True)]
SCAN_IDS = [
    f"{width}x{height}-{'access-on' if access else 'access-off'}"
    for (width, height), access in SCAN_CASES
]


@pytest.mark.parametrize(("size", "access"), SCAN_CASES, ids=SCAN_IDS)
def test_ac20_the_contrast_scan_finds_no_offender(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    access: bool,
) -> None:
    open_ac20(page, live_server, fx01_grid, size, access)

    assert contrast_problems(page) == []


@pytest.mark.parametrize(("size", "access"), SCAN_CASES, ids=SCAN_IDS)
def test_ac20_the_language_scan_finds_no_offender(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    access: bool,
) -> None:
    open_ac20(page, live_server, fx01_grid, size, access)
    expect(page.locator("html")).to_have_attribute("lang", "fr")

    data = language_data(live_server, DISPLAY_NICKNAMES)

    assert language_problems(page, data) == []


def test_ac20_fr_json_holds_the_two_new_keys_and_none_of_the_removed_ones() -> None:
    fr = load_fr()

    assert fr.get("others_tint.switch") == "Mots des autres"
    assert fr.get("access.switch") == "Accessibilit\N{LATIN SMALL LETTER E WITH ACUTE}"
    for removed in ("grid.remote_overflow", "a11y.remote_overflow", "flag.marker"):
        assert removed not in fr, removed
