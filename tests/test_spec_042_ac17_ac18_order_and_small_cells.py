"""Tests of spec 042, AC-17 and AC-18: the drawing order and small cells.

AC-17 on the mocked room with spec 034's mocked catch-up (`seen_seq` 5 stored,
a snapshot at `seq` 9), 1280 by 720, desktop context: the marks of (0, 1) and the
hit tests of "Test harness". AC-18 on FX-02 at 568 by 320, desktop context.

Choices where the spec leaves room:

- Hit tests: the owner of a point is the nearest element, from the hit element
  up, that has a test id (a shape of an `svg` mark has none, so a hit on it
  returns the mark). Before each hit, the test checks that the point lies where
  the criterion says, and fails otherwise.
- AC-17, "inside the ring's band": at most 3 px inside both edges of the inner
  box, the ring's border width.
- AC-18, L's word: `p2` selects L across when an across word of FX-02 holds L,
  else down (FX-02's L, (0, 2), is only in a down word). "1 px from its corner's
  edges" is checked with the 1 px tolerance of a position.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import ClueRef, Direction, FlagView, GridView, PlayerView, grid_view
from spec019_harness import with_letter_cells
from spec034_harness import CatchUpRoute, catch_up_json
from spec042_harness import (
    ACCESS_SWITCH,
    CORNERS,
    INK,
    NAVY,
    SELECTED,
    Box,
    ChangeList,
    Reading,
    Rgb,
    across_word_holds,
    arrow_of,
    box_problems,
    cell_at,
    click_switch,
    colour_of,
    colour_problems,
    corner_distances,
    corners_on,
    end_hit_test,
    expect_catch_up,
    first_clue_cell,
    flag_side,
    hit_chain,
    hit_owner,
    inner_box,
    inside_triangle,
    letter_cells_of,
    make_catalogue,
    me,
    notch_size,
    open_caught_up_room,
    open_room,
    pixel_at,
    player,
    point_inside,
    px,
    read_arrows,
    read_cursors,
    selecting,
    start_hit_test,
    style_of,
    tap,
    to_box,
    triangle_side,
)

# ---- Fixtures: thin wrappers around the harness ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- AC-17: the drawing order -----------------------------------------------------

RING_PX = 3.0
HIT_INSET_PX = 1.5
AC17_CORNERS = {
    "p2": "top-left",
    "p3": "top-right",
    "p4": "bottom-right",
    "p5": "bottom-left",
}


def ac17_players() -> list[PlayerView]:
    """`p1`, and `p2` to `p5` (colours 1 to 4) selecting (0, 1) down."""
    on_0_1 = selecting(0, 1, Direction.DOWN)
    players = [me()]
    for number in range(2, 6):
        players.append(player(f"p{number}", number - 1, selection=on_0_1))
    return players


def ac17_view(grid: Grid) -> GridView:
    """FX-01 with (0, 1) holding `N` revealed."""
    changes: ChangeList = [
        (0, 1, {"letter": "N", "author": None, "locked": True, "revealed": True})
    ]
    return with_letter_cells(grid_view(grid), changes)


def open_ac17(page: Page, base_url: str, grid: Grid) -> None:
    """The return of AC-17, then a tap on (0, 1)."""
    route = CatchUpRoute(answer=catch_up_json(5, 9, cells=[(0, 1)]))
    open_caught_up_room(
        page, base_url, ac17_view(grid), ac17_players(), route, seen_seq=5, seq=9
    )
    expect_catch_up(page, "5-9")
    tap(page, 0, 1)


def test_ac17_my_selected_cell_has_the_selected_blue_and_the_navy_border(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)
    cell = cell_at(page, 0, 1)

    assert colour_problems("cell", colour_of(cell, "backgroundColor"), SELECTED) == []
    assert style_of(cell, "outlineStyle") == "solid"
    assert px(style_of(cell, "outlineWidth")) == 2.0
    assert colour_problems("outline", colour_of(cell, "outlineColor"), NAVY) == []
    assert px(style_of(cell, "outlineOffset")) == -2.0


def test_ac17_the_cell_holds_four_triangles_the_notch_the_ring_and_the_arrow(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)
    cell = cell_at(page, 0, 1)

    assert corners_on(page, 0, 1) == AC17_CORNERS
    expect(cell.get_by_test_id("reveal-mark")).to_have_count(1)
    expect(cell.get_by_test_id("catch-up-mark")).to_have_count(1)
    arrow = arrow_of(read_arrows(page), 0, 0, 1)
    assert arrow["arrow"] == "right_then_down"
    assert (arrow["cellRow"], arrow["cellColumn"]) == ("0", "1")


def cursor_boxes(page: Page) -> tuple[Box, dict[str, Box]]:
    """The cell's box and each corner's triangle box, read after the scroll."""
    cell, cursors = read_cursors(page, 0, 1)
    boxes: dict[str, Box] = {}
    for cursor in cursors:
        boxes[str(cursor["corner"])] = to_box(cursor["box"])
    return cell, boxes


def test_ac17_the_arrow_is_drawn_over_the_first_players_triangle(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)
    assert corners_on(page, 0, 1) == AC17_CORNERS

    start_hit_test(page, 0, 1)
    try:
        cell, _ = cursor_boxes(page)
        arrow_box = to_box(arrow_of(read_arrows(page), 0, 0, 1)["box"])
        a = arrow_box.width
        x = arrow_box.left + 6 / 24 * a
        y = arrow_box.top + 5 / 24 * a
        inner = inner_box(cell)
        t = triangle_side(cell.width)
        if not inside_triangle(inner, "top-left", t, x, y):
            pytest.fail(f"({x:.1f}, {y:.1f}) is not inside p2's triangle (t {t})")
        chain = hit_chain(page, x, y)
    finally:
        end_hit_test(page)

    assert hit_owner(chain) == "clue-arrow", chain


@pytest.mark.parametrize(
    ("corner", "player_id"),
    [("top-right", "p3"), ("bottom-right", "p4"), ("bottom-left", "p5")],
    ids=["top-right", "bottom-right", "bottom-left"],
)
def test_ac17_the_triangles_are_drawn_over_the_ring(
    page: Page, live_server: str, fx01_grid: Grid, corner: str, player_id: str
) -> None:
    open_ac17(page, live_server, fx01_grid)
    assert corners_on(page, 0, 1) == AC17_CORNERS

    start_hit_test(page, 0, 1)
    try:
        cell, _ = cursor_boxes(page)
        inner = inner_box(cell)
        x, y = point_inside(corner, inner, HIT_INSET_PX)
        dx, dy = corner_distances(inner, corner, x, y)
        if dx > RING_PX or dy > RING_PX:
            pytest.fail(f"({x:.1f}, {y:.1f}) is not inside the ring's band")
        if not inside_triangle(inner, corner, triangle_side(cell.width), x, y):
            pytest.fail(f"({x:.1f}, {y:.1f}) is not inside the {corner} triangle")
        chain = hit_chain(page, x, y)
    finally:
        end_hit_test(page)

    assert hit_owner(chain) == f"remote-selection:{player_id}", chain


def test_ac17_the_notch_is_drawn_over_the_ring_and_the_triangles(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)
    notch = cell_at(page, 0, 1).get_by_test_id("reveal-mark")
    expect(notch).to_have_count(1)

    start_hit_test(page, 0, 1)
    try:
        cell, _ = cursor_boxes(page)
        notch_box = to_box(
            notch.evaluate(
                "e => { const r = e.getBoundingClientRect();"
                " return [r.left, r.top, r.right, r.bottom]; }"
            )
        )
        inner = inner_box(cell)
        x = notch_box.centre_x
        y = inner.bottom - HIT_INSET_PX
        if not (notch_box.left < x < notch_box.right and notch_box.top < y):
            pytest.fail(f"({x:.1f}, {y:.1f}) is not inside the notch {notch_box}")
        chain = hit_chain(page, x, y)
    finally:
        end_hit_test(page)

    assert hit_owner(chain) == "reveal-mark", chain


# ---- AC-17: my selection border, the top layer ------------------------------------

SELECTION = "cell-selection"
SELECTION_Z_INDEX = "7"

# The `cell-selection` of a cell, its computed style, and the cell's padding box
# (its box less its borders) as `[left, top, right, bottom]`.
SELECTION_SCRIPT = r"""
cell => {
  const elements = cell.querySelectorAll('[data-testid="cell-selection"]');
  if (elements.length !== 1) {
    return {count: elements.length};
  }
  const element = elements[0];
  const style = getComputedStyle(element);
  const box = element.getBoundingClientRect();
  const cellBox = cell.getBoundingClientRect();
  const left = cellBox.left + cell.clientLeft;
  const top = cellBox.top + cell.clientTop;
  const borders = {};
  for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
    borders[side] = [
      style['border' + side + 'Style'],
      style['border' + side + 'Width'],
      style['border' + side + 'Color'],
    ];
  }
  return {
    count: 1,
    ariaHidden: element.getAttribute('aria-hidden'),
    position: style.position,
    boxSizing: style.boxSizing,
    zIndex: style.zIndex,
    pointerEvents: style.pointerEvents,
    borders: borders,
    box: [box.left, box.top, box.right, box.bottom],
    paddingBox: [left, top, left + cell.clientWidth, top + cell.clientHeight],
  };
}
"""
NAVY_TEXT = f"rgb({NAVY[0]}, {NAVY[1]}, {NAVY[2]})"


def read_selection(page: Page, row: int, column: int) -> Reading:
    """The one `cell-selection` of a cell, with the cell's padding box."""
    found = cell_at(page, row, column).evaluate(SELECTION_SCRIPT)
    assert isinstance(found, dict), found
    assert found["count"] == 1, found
    return found


def test_ac17_my_selected_cell_holds_one_cell_selection_hidden_from_assistive_tech(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)
    cell = cell_at(page, 0, 1)

    expect(cell.get_by_test_id(SELECTION)).to_have_count(1)
    found = read_selection(page, 0, 1)
    assert found["ariaHidden"] == "true"


def test_ac17_cell_selection_is_absolute_on_top_and_takes_no_pointer_events(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)

    found = read_selection(page, 0, 1)

    assert found["position"] == "absolute"
    assert found["boxSizing"] == "border-box"
    assert found["zIndex"] == SELECTION_Z_INDEX
    assert found["pointerEvents"] == "none"


def test_ac17_cell_selection_has_a_2px_solid_navy_border_on_every_side(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)

    found = read_selection(page, 0, 1)

    for side in ("Top", "Right", "Bottom", "Left"):
        assert found["borders"][side] == ["solid", "2px", NAVY_TEXT], (side, found)


def test_ac17_cell_selection_box_is_the_cells_padding_box(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)

    found = read_selection(page, 0, 1)

    selection_box = to_box(found["box"])
    padding_box = to_box(found["paddingBox"])
    differences = {
        "left": selection_box.left - padding_box.left,
        "top": selection_box.top - padding_box.top,
        "right": selection_box.right - padding_box.right,
        "bottom": selection_box.bottom - padding_box.bottom,
    }
    for edge, difference in differences.items():
        assert abs(difference) <= 0.5, (edge, selection_box, padding_box)


def test_ac17_a_cell_that_is_not_selected_holds_no_cell_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)

    expect(page.get_by_test_id(SELECTION)).to_have_count(1)
    expect(cell_at(page, 2, 2).get_by_test_id(SELECTION)).to_have_count(0)
    # The cell of p2 to p5 is theirs too: their marks are not mine.
    expect(cell_at(page, 0, 1).get_by_test_id(SELECTION)).to_have_count(1)


def test_ac17_after_a_tap_on_another_cell_the_old_cell_holds_none(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)

    tap(page, 1, 1)

    expect(cell_at(page, 0, 1).get_by_test_id(SELECTION)).to_have_count(0)
    expect(cell_at(page, 1, 1).get_by_test_id(SELECTION)).to_have_count(1)
    expect(page.get_by_test_id(SELECTION)).to_have_count(1)


def test_ac17_the_selection_border_is_drawn_over_the_arrow_in_its_band(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)

    start_hit_test(page, 0, 1, with_selection=True)
    try:
        cell, _ = cursor_boxes(page)
        arrow_box = to_box(arrow_of(read_arrows(page), 0, 0, 1)["box"])
        a = arrow_box.width
        # 1 px inside the padding box's left edge, on the ↴'s tail (M2 5H10).
        x = cell.left + 1
        y = arrow_box.top + 5 / 24 * a
        if not arrow_box.left <= x <= arrow_box.right:
            pytest.fail(f"({x:.1f}, {y:.1f}) is not inside the arrow {arrow_box}")
        chain = hit_chain(page, x, y)
    finally:
        end_hit_test(page)

    assert hit_owner(chain) == SELECTION, chain


def test_ac17_the_selection_border_is_drawn_over_another_players_triangle(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)
    assert corners_on(page, 0, 1) == AC17_CORNERS

    start_hit_test(page, 0, 1, with_selection=True)
    try:
        cell, _ = cursor_boxes(page)
        inner = inner_box(cell)
        x, y = point_inside("top-right", inner, 1.0)
        if not inside_triangle(inner, "top-right", triangle_side(cell.width), x, y):
            pytest.fail(f"({x:.1f}, {y:.1f}) is not inside p3's triangle")
        chain = hit_chain(page, x, y)
    finally:
        end_hit_test(page)

    assert hit_owner(chain) == SELECTION, chain


def band_pixels(page: Page) -> tuple[Rgb, Rgb]:
    """The painted pixels of (0, 1) 1 px and 2.5 px inside its left edge.

    The first is in the 2 px band of `cell-selection`, the second in the ring's
    3 px border, a half pixel past the band; both half way down the cell.
    """
    start_hit_test(page, 0, 1, with_selection=True)
    try:
        cell, _ = cursor_boxes(page)
        y = (cell.top + inner_box(cell).bottom) / 2
        in_band = pixel_at(page, cell.left + 1, y)
        past_band = pixel_at(page, cell.left + 2.5, y)
    finally:
        end_hit_test(page)
    return in_band, past_band


def colour_within_one(painted: Rgb, expected: Rgb) -> bool:
    """Tell whether each channel of `painted` is within 1 of `expected`."""
    for channel, wanted in zip(painted, expected, strict=True):
        if abs(channel - wanted) > 1:
            return False
    return True


def test_ac17_the_caught_up_cell_shows_the_navy_band_over_the_ring(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)

    start_hit_test(page, 0, 1, with_selection=True)
    try:
        cell, _ = cursor_boxes(page)
        x = cell.left + 1
        y = (cell.top + inner_box(cell).bottom) / 2
        chain = hit_chain(page, x, y)
    finally:
        end_hit_test(page)
    in_band, _ = band_pixels(page)

    assert hit_owner(chain) == SELECTION, chain
    assert colour_within_one(in_band, NAVY), (in_band, NAVY)


def test_ac17_the_ring_shows_only_past_the_navy_band(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac17(page, live_server, fx01_grid)

    _, past_band = band_pixels(page)

    assert colour_within_one(past_band, INK), (past_band, INK)
    assert not colour_within_one(past_band, NAVY), (past_band, NAVY)


# ---- AC-18: small cells keep the marks' minimum sizes ----------------------------

SMALL_WINDOW = {"width": 568, "height": 320}
MAX_SMALL_SIDE_PX = 20.0


class Fx02Room:
    """The FX-02 page of AC-18: L revealed and selected by `p2`, C's clue 0 flagged."""

    def __init__(self, grid: Grid) -> None:
        self.letter = letter_cells_of(grid)[0]
        self.clue = first_clue_cell(grid)
        direction = (
            Direction.ACROSS if across_word_holds(grid, self.letter) else Direction.DOWN
        )
        row, column = self.letter
        changes: ChangeList = [
            (
                row,
                column,
                {"letter": "A", "author": None, "locked": True, "revealed": True},
            )
        ]
        self.view = with_letter_cells(grid_view(grid), changes)
        self.players = [
            me(),
            player("p2", 1, selection=selecting(row, column, direction)),
        ]
        flagged = ClueRef(row=self.clue[0], column=self.clue[1], clue_index=0)
        self.flags = [FlagView(player_id="p2", clue=flagged)]


def open_ac18(page: Page, base_url: str, grid: Grid) -> tuple[Fx02Room, float]:
    """Open AC-18's page; fail, reporting `s`, unless its cells are below 20 px."""
    page.set_viewport_size(SMALL_WINDOW)
    room = Fx02Room(grid)
    open_room(page, base_url, room.view, room.players, flags=room.flags)
    row, column = room.letter
    cell = cell_at(page, row, column)
    side = float(cell.evaluate("e => e.getBoundingClientRect().width"))
    if side >= MAX_SMALL_SIDE_PX:
        pytest.fail(f"the cells are {side:.2f} px, not below 20 px: revisit AC-18")
    return room, side


def cursor_of_p2(page: Page, room: Fx02Room) -> tuple[Box, Reading]:
    cell, cursors = read_cursors(page, *room.letter)
    assert len(cursors) == 1, cursors
    return cell, cursors[0]


def test_ac18_the_notch_keeps_7_by_4_px(
    page: Page, live_server: str, fx02_grid: Grid
) -> None:
    room, side = open_ac18(page, live_server, fx02_grid)
    notch = cell_at(page, *room.letter).get_by_test_id("reveal-mark")
    expect(notch).to_have_count(1)

    box = to_box(
        notch.evaluate(
            "e => { const r = e.getBoundingClientRect();"
            " return [r.left, r.top, r.right, r.bottom]; }"
        )
    )

    assert notch_size(side) == (7.0, 4.0)
    assert box_problems("notch", box, width=7.0, height=4.0) == []


def test_ac18_the_triangle_keeps_its_minimum_side(
    page: Page, live_server: str, fx02_grid: Grid
) -> None:
    room, side = open_ac18(page, live_server, fx02_grid)

    _, cursor = cursor_of_p2(page, room)

    t = triangle_side(side)
    assert box_problems("triangle", to_box(cursor["box"]), width=t, height=t) == []


def test_ac18_every_arrow_keeps_9_by_9_px(
    page: Page, live_server: str, fx02_grid: Grid
) -> None:
    open_ac18(page, live_server, fx02_grid)

    arrows = read_arrows(page)

    assert len(arrows) > 0
    problems: list[str] = []
    for arrow in arrows:
        name = f"arrow {arrow['clueRow']},{arrow['clueColumn']},{arrow['clueIndex']}"
        problems.extend(box_problems(name, to_box(arrow["box"]), width=9.0, height=9.0))
    assert problems == []


def test_ac18_the_flag_keeps_8_by_8_px(
    page: Page, live_server: str, fx02_grid: Grid
) -> None:
    room, side = open_ac18(page, live_server, fx02_grid)
    row, column = room.clue
    flag = cell_at(page, row, column).locator(
        '[data-testid="clue"][data-clue-index="0"] [data-testid="clue-flag"]'
    )
    expect(flag).to_have_count(1)

    box = to_box(
        flag.evaluate(
            "e => { const r = e.getBoundingClientRect();"
            " return [r.left, r.top, r.right, r.bottom]; }"
        )
    )

    assert flag_side(side) == 8.0
    assert box_problems("flag", box, width=8.0, height=8.0) == []


def test_ac18_every_clue_text_keeps_6_px(
    page: Page, live_server: str, fx02_grid: Grid
) -> None:
    open_ac18(page, live_server, fx02_grid)

    sizes = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-testid=\"clue-text\"]'))"
        ".map(e => getComputedStyle(e).fontSize)"
    )

    assert isinstance(sizes, list)
    assert len(sizes) > 0
    wrong = [size for size in sizes if abs(px(str(size)) - 6.0) > 0.1]
    assert wrong == []


def test_ac18_the_icon_keeps_6_px_and_1_px_from_its_corner(
    page: Page, live_server: str, fx02_grid: Grid
) -> None:
    room, _ = open_ac18(page, live_server, fx02_grid)

    click_switch(page, ACCESS_SWITCH, "true")

    cell, cursor = cursor_of_p2(page, room)
    assert cursor["shape"] == "icon"
    corner = str(cursor["corner"])
    assert corner in CORNERS
    inner = inner_box(cell)
    box = to_box(cursor["box"])
    expected: dict[str, float] = {"width": 6.0, "height": 6.0}
    if corner.endswith("left"):
        expected["left"] = inner.left + 1
    else:
        expected["right"] = inner.right - 1
    if corner.startswith("top"):
        expected["top"] = inner.top + 1
    else:
        expected["bottom"] = inner.bottom - 1
    assert box_problems("icon", box, **expected) == []
