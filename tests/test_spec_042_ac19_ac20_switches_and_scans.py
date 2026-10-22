"""Tests of spec 042, AC-19 and AC-20: the two switches as controls, and the
contrast and language of the new cells.

AC-19 is tested as this step builds it: the switches sit in spec 024's
`room-toolbar` ("Room toolbar"), so its test reads the criterion's wording from
before spec 043, which its note of 2026-10-22 gives ("toolbar controls",
"`room-toolbar` holds `authors-switch`, `others-tint-switch` and
`access-switch` in this relative order", "with the texts", "`tab_to` each
switch", and spec 024 AC-8's toolbar rules). Spec 043's test-writer moves the
test into `room-menu` before spec 043's implementer runs, as spec 042 says.

AC-20 scans the state of AC-17 without the catch-up, plus `p2`'s flag on IDES
and (1, 1) holding `X` wrong, with spec 035's contrast scan (AC-8) and language
scan (AC-9), with `access-switch` off and on.

Choices where the spec leaves room:

- AC-19, "one row with the other buttons on the four small windows": each
  switch's vertical range overlaps that of every other visible button of the
  toolbar (spec 019 AC-5's reading of the same rule).
- AC-19, "inside the toolbar's client area with an outline that passes 'Not
  clipped'": as spec 019 AC-5's test measures it, 300 ms after the focus came, so
  that a scroll of the toolbar has ended; the toolbar's client area always
  counts as a clip (0.5 px allowance).
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

SWITCHES = [TINT_SWITCH, ACCESS_SWITCH]
SWITCH_TEXT_KEYS = {TINT_SWITCH: "others_tint.switch", ACCESS_SWITCH: "access.switch"}
SMALL_WINDOWS = WINDOW_SIZES[:4]
SMALL_IDS = WINDOW_IDS[:4]
SCAN_SIZES = [(1280, 720), (360, 740)]
CLIP_ALLOWANCE_PX = 0.5
FOCUS_SETTLE_MS = 300

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

# Where the three switches and `account-open` are: inside `room-toolbar`, and the
# document order of each pair, and whether the two of the three switches follow
# each other as next element siblings.
ORDER_SCRIPT = r"""
() => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const ids = ['authors-switch', 'others-tint-switch', 'access-switch',
    'account-open'];
  const found = {};
  for (const id of ids) {
    const elements = document.querySelectorAll(`[data-testid="${id}"]`);
    found[id] = {count: elements.length,
      inToolbar: toolbar !== null && elements.length === 1
        && toolbar.contains(elements[0])};
  }
  const before = (first, second) => {
    const a = document.querySelector(`[data-testid="${first}"]`);
    const b = document.querySelector(`[data-testid="${second}"]`);
    if (a === null || b === null) {
      return null;
    }
    return (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  };
  const nextSibling = (first, second) => {
    const a = document.querySelector(`[data-testid="${first}"]`);
    const b = document.querySelector(`[data-testid="${second}"]`);
    if (a === null || b === null) {
      return null;
    }
    return a.nextElementSibling === b;
  };
  found.order = {
    tintFollowsAuthors: nextSibling('authors-switch', 'others-tint-switch'),
    accessFollowsTint: nextSibling('others-tint-switch', 'access-switch'),
    tintBeforeAccount: before('others-tint-switch', 'account-open'),
    accessBeforeAccount: before('access-switch', 'account-open'),
  };
  return found;
}
"""

MARKUP_SCRIPT = r"""
element => ({
  tag: element.tagName,
  type: element.getAttribute('type'),
  pressed: element.getAttribute('aria-pressed'),
  disabled: element.disabled,
  text: element.textContent.trim(),
})
"""

# The vertical range of a switch and of each other visible toolbar button.
ROWS_SCRIPT = r"""
testId => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const own = document.querySelector(`[data-testid="${testId}"]`);
  const ownBox = own.getBoundingClientRect();
  const others = [];
  for (const button of toolbar.querySelectorAll('button')) {
    const box = button.getBoundingClientRect();
    const shown = box.width > 0 && box.height > 0
      && getComputedStyle(button).visibility === 'visible';
    if (button !== own && shown) {
      others.push([button.getAttribute('data-testid'), box.top, box.bottom]);
    }
  }
  return {top: ownBox.top, bottom: ownBox.bottom, others: others};
}
"""

HIT_SCRIPT = r"""
testId => {
  const own = document.querySelector(`[data-testid="${testId}"]`);
  own.scrollIntoView({block: 'nearest', inline: 'nearest'});
  const box = own.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2, box.top + box.height / 2
  );
  return {
    hits: hit !== null && (hit === own || own.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""

# The focused element's box against the toolbar's client area, and the cuts of its
# outline's outer edge by the window, the toolbar and every ancestor whose overflow
# is not `visible` (spec 035, "Not clipped").
FOCUS_PLACE_SCRIPT = r"""
allowance => {
  const element = document.activeElement;
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const clientArea = node => {
    const rect = node.getBoundingClientRect();
    return {
      left: rect.left + node.clientLeft, top: rect.top + node.clientTop,
      right: rect.left + node.clientLeft + node.clientWidth,
      bottom: rect.top + node.clientTop + node.clientHeight,
    };
  };
  const box = element.getBoundingClientRect();
  const area = clientArea(toolbar);
  const style = getComputedStyle(element);
  const grow = parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth);
  const outer = {
    left: box.left - grow, top: box.top - grow,
    right: box.right + grow, bottom: box.bottom + grow,
  };
  const clips = [
    ['window', {left: 0, top: 0, right: innerWidth, bottom: innerHeight}],
    ['room-toolbar', area],
  ];
  for (let node = element.parentElement; node; node = node.parentElement) {
    const nodeStyle = getComputedStyle(node);
    if (nodeStyle.overflowX === 'visible' && nodeStyle.overflowY === 'visible') {
      continue;
    }
    clips.push([node.getAttribute('data-testid') || node.tagName, clientArea(node)]);
  }
  const cuts = [];
  for (const [name, clip] of clips) {
    const cut = {
      top: clip.top - outer.top, right: outer.right - clip.right,
      bottom: outer.bottom - clip.bottom, left: clip.left - outer.left,
    };
    for (const side of Object.keys(cut)) {
      if (cut[side] > allowance) {
        cuts.push(`${name} cuts the ${side} by ${cut[side]} px`);
      }
    }
  }
  return {
    focused: element.getAttribute('data-testid'),
    box: [box.left, box.top, box.right, box.bottom],
    area: [area.left, area.top, area.right, area.bottom],
    cuts: cuts,
  };
}
"""


# ---- AC-19: the switches as controls --------------------------------------------


def test_ac19_the_two_switches_follow_authors_switch_in_the_toolbar(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    found = page.evaluate(ORDER_SCRIPT)

    for test_id in ("authors-switch", TINT_SWITCH, ACCESS_SWITCH):
        assert found[test_id] == {"count": 1, "inToolbar": True}, found
    assert found["order"]["tintFollowsAuthors"] is True, found
    assert found["order"]["accessFollowsTint"] is True, found


@pytest.mark.parametrize("test_id", SWITCHES)
def test_ac19_each_switch_is_a_button_with_aria_pressed_and_its_french_text(
    page: Page, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    switch = page.get_by_test_id(test_id)
    expect(switch).to_have_count(1)

    markup = switch.evaluate(MARKUP_SCRIPT)
    tap(page, 2, 2)
    later = switch.evaluate(MARKUP_SCRIPT)

    assert markup["tag"] == "BUTTON"
    assert markup["type"] == "button"
    assert markup["pressed"] in ("true", "false")
    assert markup["disabled"] is False
    assert later["disabled"] is False
    assert markup["text"] == load_fr()[SWITCH_TEXT_KEYS[test_id]]


def test_ac19_with_accounts_on_both_switches_come_before_account_open(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    AccountRoutes().install(page)
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    expect(page.get_by_test_id("account-open")).to_have_count(
        1, timeout=WAIT_TIMEOUT_MS
    )

    found = page.evaluate(ORDER_SCRIPT)

    assert found["order"]["tintBeforeAccount"] is True, found
    assert found["order"]["accessBeforeAccount"] is True, found


@pytest.mark.parametrize("test_id", SWITCHES)
def test_ac19_from_the_keyboard_each_switch_shows_the_ring_and_enter_flips_it(
    page: Page, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    switch = page.get_by_test_id(test_id)
    expect(switch).to_have_count(1)
    before = switch.get_attribute("aria-pressed")
    walker = Walker(page)

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


def open_toolbar_setup(page: Page, base_url: str, grid: Grid, touch: bool) -> None:
    """Spec 024 AC-8's setup: 8 players, 100 feed items, (3, 1) tapped."""
    open_toolbar_setup_room(page, base_url, grid)
    press(cell_at(page, 3, 1), touch)
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac19_the_grid_keeps_its_room_with_the_switches_in_the_toolbar(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)

    open_toolbar_setup(page, live_server, fx01_grid, touch)

    expect(page.get_by_test_id(TINT_SWITCH)).to_have_count(1)
    expect(page.get_by_test_id(ACCESS_SWITCH)).to_have_count(1)
    assert layout_problems(page, touch) == []


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), SMALL_WINDOWS, ids=SMALL_IDS)
def test_ac19_on_small_windows_the_switches_share_the_toolbars_one_row(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_toolbar_setup(page, live_server, fx01_grid, touch)

    problems: list[str] = []
    for test_id in SWITCHES:
        expect(page.get_by_test_id(test_id)).to_have_count(1)
        rows = page.evaluate(ROWS_SCRIPT, test_id)
        if rows["others"] == []:
            problems.append(f"{test_id}: no other visible button in room-toolbar")
        for other, top, bottom in rows["others"]:
            if not (top < rows["bottom"] and rows["top"] < bottom):
                problems.append(f"{other} ({top}-{bottom}) is not on {test_id}'s row")
    assert problems == []


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac19_a_pointer_at_the_centre_of_each_switch_reaches_it(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_toolbar_setup(page, live_server, fx01_grid, touch)

    for test_id in SWITCHES:
        expect(page.get_by_test_id(test_id)).to_have_count(1)
        hit = page.evaluate(HIT_SCRIPT, test_id)
        assert hit["hits"] is True, f"{test_id}: elementFromPoint found {hit['hit']}"


@pytest.mark.parametrize("test_id", SWITCHES)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac19_with_the_keyboard_focus_each_switch_is_whole_inside_the_toolbar(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    test_id: str,
) -> None:
    page = window(width, height, False)
    open_toolbar_setup(page, live_server, fx01_grid, False)
    walker = Walker(page)

    walker.tab_to(test_id)
    page.wait_for_timeout(FOCUS_SETTLE_MS)

    place = page.evaluate(FOCUS_PLACE_SCRIPT, CLIP_ALLOWANCE_PX)
    reached = walker.reached[-1]
    assert place["focused"] == test_id
    left, top, right, bottom = place["box"]
    area_left, area_top, area_right, area_bottom = place["area"]
    assert left >= area_left - LAYOUT_EPSILON_PX, place
    assert top >= area_top - LAYOUT_EPSILON_PX, place
    assert right <= area_right + LAYOUT_EPSILON_PX, place
    assert bottom <= area_bottom + LAYOUT_EPSILON_PX, place
    assert place["cuts"] == []
    assert (
        outline_problems(
            reached.outline_style, reached.outline_width, reached.outline_contrast
        )
        == []
    )


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
