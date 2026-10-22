"""Tests of spec 035: colour is not the only signal (AC-6, AC-7).

They use a mocked socket. The setup the test files of spec 035 share is in
`tests/spec035_harness.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Direction, PlayerState, PlayerView, Selection
from spec035_harness import (
    EPSILON,
    WINDOW_SIZES,
    MockRoomSocket,
    build_fx01_grid,
    build_reference_catalogue,
    cell_at,
    computed,
    open_k2,
    open_room,
    page_factory,
    player_view,
    selection_frame,
)
from spec042_harness import (
    ACCESS_SWITCH,
    click_switch,
    icon_shape_problems,
    read_cursors,
    read_swatches,
    to_box,
)

# ---- Fixtures: thin wrappers around spec035_harness -------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (also served by live_server)."""
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Return `new_page(width, height)`, a page in a fresh context of that size."""
    yield from page_factory(browser)


BOLD_WEIGHT = 700


# ---- AC-6: colour is not the only signal of a cursor ----------------------------
#
# Spec 042 (the design's grid cells) refines AC-6, as the human decided on
# 2026-10-16: the non-colour sign of a cursor is its player's own icon while the
# Accessibilité mode is on (`access-switch`), shown in the roster too; with the
# mode off the cursors are triangles with no text. The initials are gone. The
# readers and the icon table are spec 042's (`tests/spec042_harness.py`).


def icon_players() -> list[PlayerView]:
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view(
            "p2",
            "Jean-Luc",
            1,
            selection=Selection(row=2, column=2, direction=Direction.DOWN),
        ),
        player_view(
            "p3",
            "Ana",
            2,
            selection=Selection(row=2, column=2, direction=Direction.ACROSS),
        ),
        player_view(
            "p4",
            "zoé",
            3,
            selection=Selection(row=1, column=0, direction=Direction.ACROSS),
        ),
    ]


def open_icon_room(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """The snapshot of AC-6, then a click on `access-switch` (spec 042)."""
    mock = open_room(page, base_url, grid, players=icon_players())
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)
    click_switch(page, ACCESS_SWITCH, "true")
    return mock


def icons_on(page: Page, row: int, column: int) -> dict[str, str | None]:
    """The `data-icon` of each cursor's `player-icon` on a cell, by player id."""
    _, cursors = read_cursors(page, row, column)
    icons: dict[str, str | None] = {}
    for cursor in cursors:
        found: str | None = None
        for svg in cursor["svgs"]:
            if svg["testId"] == "player-icon":
                found = svg["dataIcon"]
        icons[str(cursor["playerId"])] = found
    return icons


def icon_place_problems(page: Page, row: int, column: int) -> list[str]:
    """Each cursor of a cell: an icon of its colour, visible, inside the cell."""
    cell, cursors = read_cursors(page, row, column)
    problems: list[str] = []
    for cursor in cursors:
        name = f"({row}, {column}) {cursor['playerId']}"
        if cursor["shape"] != "icon":
            problems.append(f"{name}: data-shape {cursor['shape']!r}")
        icons = [svg for svg in cursor["svgs"] if svg["testId"] == "player-icon"]
        if len(icons) != 1:
            problems.append(f"{name}: {len(icons)} player-icon elements")
            continue
        problems.extend(icon_shape_problems(icons[0], int(cursor["colour"])))
        box = to_box(icons[0]["box"])
        inside = (
            box.left >= cell.left - EPSILON
            and box.top >= cell.top - EPSILON
            and box.right <= cell.right + EPSILON
            and box.bottom <= cell.bottom + EPSILON
        )
        if not inside:
            problems.append(f"{name}: icon {box} outside the cell {cell}")
    return problems


def test_ac6_with_the_mode_on_each_cursor_is_its_players_own_icon(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_icon_room(page, live_server, fx01_grid)

    assert icons_on(page, 2, 2) == {"p2": "1", "p3": "2"}
    assert icons_on(page, 1, 0) == {"p4": "3"}
    assert icon_place_problems(page, 2, 2) == []
    assert icon_place_problems(page, 1, 0) == []
    for player_id in ("p2", "p3", "p4"):
        selector = f'[data-testid="remote-selection"][data-player-id="{player_id}"]'
        assert computed(page.locator(selector), "visibility") == "visible"


def test_ac6_the_roster_shows_which_icon_is_whose(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_icon_room(page, live_server, fx01_grid)

    shown: dict[str, list[str | None]] = {}
    for swatch in read_swatches(page):
        icons: list[str | None] = []
        for svg in swatch["svgs"]:
            if svg["testId"] == "player-icon":
                icons.append(svg["dataIcon"])
        shown[str(swatch["playerId"])] = icons

    assert shown["p2"] == ["1"]
    assert shown["p3"] == ["2"]
    assert shown["p4"] == ["3"]


def test_ac6_an_icon_follows_a_moved_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_icon_room(page, live_server, fx01_grid)

    mock.send(selection_frame("p2", 3, 1, Direction.DOWN))

    expect(cell_at(page, 3, 1).get_by_test_id("remote-selection")).to_have_count(1)
    assert icons_on(page, 3, 1) == {"p2": "1"}
    assert icons_on(page, 2, 2) == {"p3": "2"}


def test_ac6_with_the_mode_off_the_cursors_are_triangles_with_no_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, players=icon_players())
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)

    problems: list[str] = []
    for row, column in ((2, 2), (1, 0)):
        _, cursors = read_cursors(page, row, column)
        for cursor in cursors:
            if cursor["shape"] != "triangle" or cursor["text"] != "":
                problems.append(f"{cursor['playerId']}: {cursor['shape']!r}")
    assert problems == []
    expect(page.get_by_test_id("access-switch")).to_have_attribute(
        "aria-pressed", "false"
    )


def test_ac6_a_disconnected_player_has_no_cursor(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view(
            "p2",
            "Bob",
            1,
            state=PlayerState.DISCONNECTED,
            selection=Selection(row=2, column=2, direction=Direction.DOWN),
        ),
    ]

    open_room(page, live_server, fx01_grid, players=players)

    expect(page.get_by_test_id("remote-selection")).to_have_count(0)


# ---- AC-7: locked letters differ by more than colour -----------------------------


def test_ac7_a_locked_letter_is_bold_and_an_unlocked_one_is_not(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_k2(page, live_server, fx01_grid)

    locked = cell_at(page, 1, 0)
    expect(locked).to_have_attribute("data-locked", "true")
    assert int(computed(locked, "fontWeight")) >= BOLD_WEIGHT
    unlocked = cell_at(page, 1, 2)
    expect(unlocked).to_have_attribute("data-locked", "false")
    assert int(computed(unlocked, "fontWeight")) < BOLD_WEIGHT


def test_ac7_other_unlocked_letters_are_not_bold(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_k2(page, live_server, fx01_grid)

    for row, column in [(1, 1), (1, 3), (1, 4), (2, 2)]:
        weight = int(computed(cell_at(page, row, column), "fontWeight"))
        assert weight < BOLD_WEIGHT, (row, column)


ROSTER_ROWS = [
    ("p2", "actif", "normal", False),
    ("p3", "inactif", "italic", False),
    ("p4", "déconnecté", "italic", True),
]

NON_OPAQUE_SCRIPT = """
row => {
  const found = [];
  const nodes = [row, ...row.querySelectorAll('*')];
  for (let node = row.parentElement; node; node = node.parentElement) {
    nodes.push(node);
  }
  for (const node of nodes) {
    const opacity = getComputedStyle(node).opacity;
    if (opacity !== '1') {
      found.push([node.getAttribute('data-testid') || node.tagName, opacity]);
    }
  }
  return found;
}
"""


def roster_row(page: Page, player_id: str) -> Locator:
    selector = f'[data-testid="roster-player"][data-player-id="{player_id}"]'
    return page.locator(selector)


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
@pytest.mark.parametrize(("player_id", "state_text", "style", "struck"), ROSTER_ROWS)
def test_ac7_roster_rows_use_no_opacity(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    player_id: str,
    state_text: str,
    style: str,
    struck: bool,
) -> None:
    page = new_page(width, height)
    open_k2(page, live_server, fx01_grid)

    row = roster_row(page, player_id)
    expect(row).to_have_count(1)
    assert row.evaluate(NON_OPAQUE_SCRIPT) == []


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
@pytest.mark.parametrize(("player_id", "state_text", "style", "struck"), ROSTER_ROWS)
def test_ac7_roster_state_is_shown_by_font_style_and_line_through(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    player_id: str,
    state_text: str,
    style: str,
    struck: bool,
) -> None:
    page = new_page(width, height)
    open_k2(page, live_server, fx01_grid)

    nickname = roster_row(page, player_id).get_by_test_id("roster-nickname")
    assert computed(nickname, "fontStyle") == style
    line = computed(nickname, "textDecorationLine")
    assert ("line-through" in line) is struck, line


@pytest.mark.parametrize("player_id", ["p2", "p3", "p4"])
def test_ac7_roster_state_is_written_in_the_row(
    page: Page, live_server: str, fx01_grid: Grid, player_id: str
) -> None:
    open_k2(page, live_server, fx01_grid)

    expected = {"p2": "actif", "p3": "inactif", "p4": "déconnecté"}[player_id]
    state = roster_row(page, player_id).get_by_test_id("roster-state")
    expect(state).to_have_text(expected)
