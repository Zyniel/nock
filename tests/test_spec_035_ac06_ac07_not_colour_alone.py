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
    Cell,
    build_fx01_grid,
    build_reference_catalogue,
    cell_at,
    computed,
    open_k2,
    open_room,
    page_factory,
    player_view,
    remote_initials,
    selection_frame,
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


def initials_players() -> list[PlayerView]:
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


def assert_initials_inside_the_cell(page: Page, row: int, column: int) -> None:
    cell_box = cell_at(page, row, column).bounding_box()
    assert cell_box is not None
    initials = remote_initials(page, row, column)
    for index in range(initials.count()):
        box = initials.nth(index).bounding_box()
        assert box is not None
        assert box["x"] >= cell_box["x"] - EPSILON
        assert box["y"] >= cell_box["y"] - EPSILON
        assert box["x"] + box["width"] <= cell_box["x"] + cell_box["width"] + EPSILON
        assert box["y"] + box["height"] <= cell_box["y"] + cell_box["height"] + EPSILON
        assert computed(initials.nth(index), "visibility") == "visible"


def corners_of(page: Page, row: int, column: int) -> list[str | None]:
    """The `data-corner` of each `remote-initials` of a cell, in document order."""
    corners: list[str | None] = []
    initials = remote_initials(page, row, column)
    for index in range(initials.count()):
        corners.append(initials.nth(index).get_attribute("data-corner"))
    return corners


def test_ac6_each_remote_cursor_carries_the_initials_of_its_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, players=initials_players())

    shared = cell_at(page, 2, 2).get_by_test_id("remote-selection")
    expect(shared).to_have_count(2)
    expect(remote_initials(page, 2, 2)).to_have_text(["JL", "AN"])
    expect(cell_at(page, 1, 0).get_by_test_id("remote-selection")).to_have_count(1)
    expect(remote_initials(page, 1, 0)).to_have_text(["ZO"])
    assert_initials_inside_the_cell(page, 2, 2)
    assert_initials_inside_the_cell(page, 1, 0)


def test_ac6_data_corner_holds_the_name_of_the_corner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, players=initials_players())

    expect(remote_initials(page, 2, 2)).to_have_text(["JL", "AN"])
    assert corners_of(page, 2, 2) == ["top-left", "bottom-right"]
    assert corners_of(page, 1, 0) == ["top-left"]


def test_ac6_each_labelled_cursor_holds_exactly_one_initials_element(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, players=initials_players())

    cursors = page.get_by_test_id("remote-selection")
    expect(cursors).to_have_count(3)
    for index in range(3):
        initials = cursors.nth(index).get_by_test_id("remote-initials")
        expect(initials).to_have_count(1)


def test_ac6_the_initials_follow_a_moved_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, players=initials_players())
    expect(remote_initials(page, 2, 2)).to_have_text(["JL", "AN"])

    mock.send(selection_frame("p2", 3, 1, Direction.DOWN))

    expect(remote_initials(page, 3, 1)).to_have_text(["JL"])
    expect(remote_initials(page, 2, 2)).to_have_text(["AN"])
    assert_initials_inside_the_cell(page, 3, 1)
    assert corners_of(page, 3, 1) == ["top-left"]
    assert corners_of(page, 2, 2) == ["top-left"]


def test_ac6_two_players_with_the_same_initials_are_both_shown(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view(
            "p2",
            "Anne",
            1,
            selection=Selection(row=2, column=2, direction=Direction.DOWN),
        ),
        player_view(
            "p3",
            "Anouk",
            2,
            selection=Selection(row=2, column=2, direction=Direction.ACROSS),
        ),
    ]

    open_room(page, live_server, fx01_grid, players=players)

    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)
    expect(remote_initials(page, 2, 2)).to_have_text(["AN", "AN"])
    assert_initials_inside_the_cell(page, 2, 2)


def test_ac6_a_disconnected_player_has_no_cursor_and_no_initials(
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

    expect(page.get_by_test_id("remote-initials")).to_have_count(0)


INITIALS_EXAMPLES = [
    ("Ana", "AN"),
    ("Jean-Luc", "JL"),
    ("marie ève", "MÈ"),
    ("R2", "R2"),
    ("Zoé", "ZO"),
    ("_Max_", "MA"),
    ("O" + chr(0x2019) + "Neil", "ON"),
]
MORE_INITIALS_EXAMPLES = [
    ("O'Neil", "ON"),
    ("Anne Marie", "AM"),
    ("a-b-c", "AB"),
    ("Élodie", "ÉL"),
    ("Jean Luc Paul", "JL"),
    ("\U0001d49cbc", "\U0001d49cB"),
]
INITIALS_CELLS: list[Cell] = [
    (1, 0),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (0, 1),
    (2, 1),
]


def players_with_nicknames(nicknames: list[str]) -> list[PlayerView]:
    players = [player_view("p1", "Host", 0, is_host=True)]
    for index, nickname in enumerate(nicknames):
        row, column = INITIALS_CELLS[index]
        selection = Selection(row=row, column=column, direction=Direction.ACROSS)
        players.append(
            player_view(f"p{index + 2}", nickname, index % 8, selection=selection)
        )
    return players


@pytest.mark.parametrize(
    "examples",
    [INITIALS_EXAMPLES, MORE_INITIALS_EXAMPLES],
    ids=["spec_examples", "more_examples"],
)
def test_ac6_initials_follow_the_rule_of_initials_of(
    page: Page, live_server: str, fx01_grid: Grid, examples: list[tuple[str, str]]
) -> None:
    nicknames = [nickname for nickname, _ in examples]
    open_room(page, live_server, fx01_grid, players=players_with_nicknames(nicknames))

    for index, (nickname, initials) in enumerate(examples):
        row, column = INITIALS_CELLS[index]
        shown = remote_initials(page, row, column)
        expect(shown, f"initials of {nickname}").to_have_text([initials])


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
