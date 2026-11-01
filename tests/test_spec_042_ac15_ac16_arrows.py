"""Tests of spec 042, AC-15 and AC-16: the direction arrows in the letter cells.

On the mocked room of `tests/spec042_harness.py`, 1280 by 720, desktop context.
AC-15 reads every `clue-arrow` of FX-01; AC-16 three hand-built views (`GridView`
values of spec 039, as in spec 007) whose target cells receive two arrows. `L`,
`T` and `s` are the target cell's left, top and side.

Choices where the spec leaves room:

- AC-15, "an `svg` child of the target letter cell": the arrow's parent element
  is the cell.
- AC-15, the shapes of an arrow: every `path` and `polygon` it holds, at any
  depth, in document order (`read_arrows`). Its ink glyph is its last `path` and
  its last `polygon`.
- AC-15, the halo (`_design/cells.md` « Direction arrows », B-043): the arrow's
  computed `filter` is `none`, and it holds exactly two paths and two polygons,
  the halo's copy of the path and of the head both before the ink's (drawn under
  it). The copy of the path has the glyph's `d`, a stroke of exactly
  rgb(255, 255, 255) (`--nock-white`), a computed stroke width of 4.8px, round
  caps and joins and no fill; the copy of the head has the glyph's points, a
  fill and a stroke of that white, a stroke width of 2.4px and round joins. So
  1.2 units of white border every ink edge, the path's round caps included.
- AC-15, the edge cases "Arrow targets" (a hand-built view whose clues point at
  an empty cell and outside the grid draws no arrow for them) and "Taps on an
  arrow" (a click at the centre of the ↓ of (1, 2) selects (1, 2)) are tested
  here.
- AC-16, "overlap by at most 1 px on one axis": the smaller of the two axis
  overlaps of the two boxes is at most 1 px.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Arrow, Grid
from nock.protocol import (
    ClueCellView,
    ClueView,
    EmptyCellView,
    GridView,
    LetterCellView,
)
from spec042_harness import (
    ARROW_SHAPES,
    ARROW_SIDES,
    INK,
    WHITE,
    Box,
    Reading,
    arrow_of,
    arrow_side,
    box_problems,
    colour_problems,
    fx01_view,
    make_catalogue,
    me,
    open_room,
    overlap_px,
    read_arrows,
    to_box,
)

# ---- Fixtures: thin wrappers around the harness ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- The arrows of FX-01 ---------------------------------------------------------

# (clue row, clue column, clue index, data-arrow, the word's first letter cell).
FX01_ARROWS = [
    (0, 0, 0, "down_then_right", (1, 0)),
    (0, 0, 1, "right_then_down", (0, 1)),
    (0, 2, 0, "down", (1, 2)),
    (0, 3, 0, "down", (1, 3)),
    (0, 4, 0, "down", (1, 4)),
    (2, 0, 0, "right", (2, 1)),
    (3, 0, 0, "right", (3, 1)),
    (4, 0, 0, "right", (4, 1)),
]
FX01_IDS = [f"{row}-{column}-clue{index}" for row, column, index, _, _ in FX01_ARROWS]

HALO_PATH_WIDTH = "4.8px"
HALO_HEAD_WIDTH = "2.4px"
# The tags of one drawing of the glyph, sorted: its path and its head.
GLYPH_TAGS = ["path", "polygon"]


def shapes_of(arrow: Reading, tag: str) -> list[Reading]:
    """The arrow's shapes of one tag (`path` or `polygon`), in document order."""
    found: list[Reading] = []
    for shape in arrow["shapes"]:
        if shape["tag"] == tag:
            found.append(shape)
    return found


def points_of(polygon: Reading) -> str:
    """A polygon's `points`, its whitespace made single spaces."""
    return " ".join(str(polygon["attributes"].get("points", "")).split())


def place_problems(arrow: Reading) -> list[str]:
    """The arrow's box in its target cell, by "Position in the target cell"."""
    cell = to_box(arrow["cell"])
    box = to_box(arrow["box"])
    side = cell.width
    a = arrow_side(side)
    name = f"{arrow['arrow']} in ({arrow['cellRow']}, {arrow['cellColumn']})"
    problems = box_problems(name, box, width=a, height=a)
    kind = arrow["arrow"]
    if kind == "right":
        problems += box_problems(
            name, box, left=cell.left - 1, centre_y=cell.top + 0.5 * side
        )
    elif kind == "down":
        problems += box_problems(
            name, box, top=cell.top - 1, centre_x=cell.left + 0.5 * side
        )
    elif kind == "down_then_right":
        problems += box_problems(
            name, box, top=cell.top - 1, left=cell.left + 0.06 * side
        )
    else:
        problems += box_problems(
            name, box, left=cell.left - 1, top=cell.top + 0.06 * side
        )
    return problems


def glyph_problems(arrow: Reading) -> list[str]:
    """The ink `path` and `polygon` of the arrow (its last ones), by its table."""
    name = f"arrow {arrow['arrow']}"
    tags = [shape["tag"] for shape in arrow["shapes"]]
    paths = shapes_of(arrow, "path")
    polygons = shapes_of(arrow, "polygon")
    if not paths or not polygons or len(paths) + len(polygons) != len(tags):
        return [f"{name}: shapes {tags}"]
    path = paths[-1]
    polygon = polygons[-1]
    expected_d, expected_points = ARROW_SHAPES[str(arrow["arrow"])]
    problems: list[str] = []
    if path["attributes"].get("d") != expected_d:
        problems.append(f"{name}: d {path['attributes'].get('d')!r}")
    points = points_of(polygon)
    if points != expected_points:
        problems.append(f"{name}: points {points!r}")
    if path["strokeColour"] is None:
        problems.append(f"{name}: path stroke {path['stroke']!r}")
    else:
        problems += colour_problems(f"{name} path stroke", path["strokeColour"], INK)
    if path["strokeWidth"] != "2.4px":
        problems.append(f"{name}: stroke-width {path['strokeWidth']}")
    if path["linecap"] != "round" or path["linejoin"] != "round":
        problems.append(f"{name}: caps {path['linecap']} {path['linejoin']}")
    if path["fill"] != "none":
        problems.append(f"{name}: path fill {path['fill']}")
    if polygon["fillColour"] is None:
        problems.append(f"{name}: polygon fill {polygon['fill']!r}")
    else:
        problems += colour_problems(f"{name} head", polygon["fillColour"], INK)
    return problems


def white_problems(name: str, colour: object, written: object) -> list[str]:
    """A computed fill or stroke that must be exactly the opaque white."""
    if colour is None:
        return [f"{name} {written!r}"]
    return colour_problems(name, colour, WHITE)


def halo_problems(arrow: Reading) -> list[str]:
    """The arrow's white halo by « Direction arrows »: two copies under the ink."""
    name = f"arrow {arrow['arrow']}"
    problems: list[str] = []
    if arrow["filter"] != "none":
        problems.append(f"{name}: filter {arrow['filter']!r}")
    tags = [shape["tag"] for shape in arrow["shapes"]]
    halo_tags = sorted(tags[:2])
    ink_tags = sorted(tags[2:])
    if halo_tags != GLYPH_TAGS or ink_tags != GLYPH_TAGS:
        return [*problems, f"{name}: shapes {tags}, expected the halo then the ink"]
    halo_path = shapes_of(arrow, "path")[0]
    halo_head = shapes_of(arrow, "polygon")[0]
    expected_d, expected_points = ARROW_SHAPES[str(arrow["arrow"])]
    if halo_path["attributes"].get("d") != expected_d:
        problems.append(f"{name} halo: d {halo_path['attributes'].get('d')!r}")
    problems += white_problems(
        f"{name} halo path stroke", halo_path["strokeColour"], halo_path["stroke"]
    )
    if halo_path["strokeWidth"] != HALO_PATH_WIDTH:
        problems.append(f"{name} halo: path stroke-width {halo_path['strokeWidth']}")
    if halo_path["linecap"] != "round" or halo_path["linejoin"] != "round":
        caps = f"{halo_path['linecap']} {halo_path['linejoin']}"
        problems.append(f"{name} halo: path caps {caps}")
    if halo_path["fill"] != "none":
        problems.append(f"{name} halo: path fill {halo_path['fill']}")
    points = points_of(halo_head)
    if points != expected_points:
        problems.append(f"{name} halo: points {points!r}")
    problems += white_problems(
        f"{name} halo head fill", halo_head["fillColour"], halo_head["fill"]
    )
    problems += white_problems(
        f"{name} halo head stroke", halo_head["strokeColour"], halo_head["stroke"]
    )
    if halo_head["strokeWidth"] != HALO_HEAD_WIDTH:
        problems.append(f"{name} halo: head stroke-width {halo_head['strokeWidth']}")
    if halo_head["linejoin"] != "round":
        problems.append(f"{name} halo: head joins {halo_head['linejoin']}")
    return problems


def open_fx01(page: Page, base_url: str, grid: Grid) -> list[Reading]:
    open_room(page, base_url, fx01_view(grid), [me()])
    return read_arrows(page)


# ---- AC-15: each arrow in its word's first letter cell -----------------------------


def test_ac15_no_clue_cell_holds_an_arrow(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    in_clue_cells = page.locator(
        '[data-testid="cell"][data-type="clue"] [data-testid="clue-arrow"]'
    )

    expect(in_clue_cells).to_have_count(0)
    expect(page.get_by_test_id("clue-arrow")).to_have_count(8)


@pytest.mark.parametrize(
    ("row", "column", "index", "kind", "target"), FX01_ARROWS, ids=FX01_IDS
)
def test_ac15_each_clue_has_one_arrow_in_its_words_first_letter_cell(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    row: int,
    column: int,
    index: int,
    kind: str,
    target: tuple[int, int],
) -> None:
    arrows = open_fx01(page, live_server, fx01_grid)

    arrow = arrow_of(arrows, row, column, index)

    assert arrow["tag"] == "svg"
    assert arrow["parentIsCell"] is True
    assert (arrow["cellRow"], arrow["cellColumn"]) == (str(target[0]), str(target[1]))
    assert arrow["cellType"] == "letter"
    assert arrow["arrow"] == kind
    assert arrow["side"] == ARROW_SIDES[kind]


def test_ac15_each_arrow_is_a_mark_drawn_over_the_others_that_takes_no_tap(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    arrows = open_fx01(page, live_server, fx01_grid)

    assert len(arrows) == 8
    for arrow in arrows:
        assert arrow["ariaHidden"] == "true", arrow
        assert arrow["viewBox"] == "0 0 24 24", arrow
        assert arrow["text"] == "", arrow
        assert arrow["position"] == "absolute", arrow
        assert arrow["pointerEvents"] == "none", arrow
        assert arrow["zIndex"] == "6", arrow


def test_ac15_each_arrow_holds_the_path_and_the_head_of_its_glyph_in_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    arrows = open_fx01(page, live_server, fx01_grid)

    assert len(arrows) == 8
    problems: list[str] = []
    for arrow in arrows:
        problems.extend(glyph_problems(arrow))
    assert problems == []


def test_ac15_each_arrow_has_a_thin_white_halo(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    arrows = open_fx01(page, live_server, fx01_grid)

    assert len(arrows) == 8
    problems: list[str] = []
    for arrow in arrows:
        problems.extend(halo_problems(arrow))
    assert problems == []


def test_ac15_each_arrow_is_a_square_placed_against_the_side_it_comes_from(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    arrows = open_fx01(page, live_server, fx01_grid)

    assert len(arrows) == 8
    problems: list[str] = []
    for arrow in arrows:
        problems.extend(place_problems(arrow))
    assert problems == []


# ---- Hand-built views ----------------------------------------------------------------


def letter(row: int, column: int) -> LetterCellView:
    return LetterCellView(
        row=row,
        column=column,
        letter=None,
        pencil=False,
        author=None,
        locked=False,
        revealed=False,
        wrong=False,
    )


def empty(row: int, column: int) -> EmptyCellView:
    return EmptyCellView(row=row, column=column)


def clue_cell(row: int, column: int, clues: list[tuple[str, Arrow]]) -> ClueCellView:
    views: list[ClueView] = []
    for text, arrow in clues:
        views.append(ClueView(text=text, arrow=arrow))
    return ClueCellView(row=row, column=column, clues=tuple(views))


def test_ac15_a_clue_whose_target_is_not_a_letter_cell_draws_no_arrow(
    page: Page, live_server: str
) -> None:
    view = GridView(
        width=2,
        height=2,
        cells=(
            clue_cell(0, 0, [("Un", Arrow.RIGHT), ("Deux", Arrow.DOWN)]),
            letter(0, 1),
            empty(1, 0),
            clue_cell(1, 1, [("Trois", Arrow.DOWN)]),
        ),
    )
    open_room(page, live_server, view, [me()])

    arrows = read_arrows(page)

    assert len(arrows) == 1, arrows
    assert (arrows[0]["clueRow"], arrows[0]["clueColumn"], arrows[0]["clueIndex"]) == (
        "0",
        "0",
        "0",
    )
    assert (arrows[0]["cellRow"], arrows[0]["cellColumn"]) == ("0", "1")


def test_ac15_a_tap_on_an_arrow_selects_its_letter_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    arrows = open_fx01(page, live_server, fx01_grid)
    box = to_box(arrow_of(arrows, 0, 2, 0)["box"])

    page.mouse.click(box.centre_x, box.centre_y)

    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", "1")
    expect(grid).to_have_attribute("data-selected-column", "2")


# ---- AC-16: two arrows in one cell ---------------------------------------------------


def view_a() -> GridView:
    """Width 2, height 3: (0, 0) holds a → and a ↴ into (0, 1)."""
    return GridView(
        width=2,
        height=3,
        cells=(
            clue_cell(0, 0, [("Un", Arrow.RIGHT), ("Deux", Arrow.RIGHT_THEN_DOWN)]),
            letter(0, 1),
            empty(1, 0),
            letter(1, 1),
            empty(2, 0),
            letter(2, 1),
        ),
    )


def view_b() -> GridView:
    """Width 2, height 1: (0, 0) holds two → into (0, 1)."""
    return GridView(
        width=2,
        height=1,
        cells=(
            clue_cell(0, 0, [("Un", Arrow.RIGHT), ("Deux", Arrow.RIGHT)]),
            letter(0, 1),
        ),
    )


def view_c() -> GridView:
    """Width 3, height 3: a ↳ from (0, 1) and a ↴ from (1, 0) into (1, 1)."""
    return GridView(
        width=3,
        height=3,
        cells=(
            empty(0, 0),
            clue_cell(0, 1, [("Est", Arrow.DOWN_THEN_RIGHT)]),
            empty(0, 2),
            clue_cell(1, 0, [("Sud", Arrow.RIGHT_THEN_DOWN)]),
            letter(1, 1),
            letter(1, 2),
            empty(2, 0),
            letter(2, 1),
            empty(2, 2),
        ),
    )


def target_box(arrow: Reading) -> tuple[Box, float]:
    cell = to_box(arrow["cell"])
    return cell, cell.width


def test_ac16_a_right_arrow_beside_a_right_then_down_takes_the_low_slot(
    page: Page, live_server: str
) -> None:
    open_room(page, live_server, view_a(), [me()])
    arrows = read_arrows(page)

    right = arrow_of(arrows, 0, 0, 0)
    turning = arrow_of(arrows, 0, 0, 1)

    cell, side = target_box(right)
    assert (right["cellRow"], right["cellColumn"]) == ("0", "1")
    assert (turning["cellRow"], turning["cellColumn"]) == ("0", "1")
    problems = box_problems("→", to_box(right["box"]), centre_y=cell.top + 0.72 * side)
    problems += box_problems(
        "↴", to_box(turning["box"]), top=cell.top + 0.06 * side, left=cell.left - 1
    )
    assert problems == []
    assert overlap_px(to_box(right["box"]), to_box(turning["box"])) <= 1


def test_ac16_two_right_arrows_take_the_high_and_the_low_slots_by_index(
    page: Page, live_server: str
) -> None:
    open_room(page, live_server, view_b(), [me()])
    arrows = read_arrows(page)

    first = arrow_of(arrows, 0, 0, 0)
    second = arrow_of(arrows, 0, 0, 1)

    cell, side = target_box(first)
    problems = box_problems(
        "→ 0", to_box(first["box"]), centre_y=cell.top + 0.25 * side
    )
    problems += box_problems(
        "→ 1", to_box(second["box"]), centre_y=cell.top + 0.72 * side
    )
    assert problems == []
    assert overlap_px(to_box(first["box"]), to_box(second["box"])) <= 1


def test_ac16_a_down_then_right_beside_a_right_then_down_moves_right(
    page: Page, live_server: str
) -> None:
    open_room(page, live_server, view_c(), [me()])
    arrows = read_arrows(page)

    hooked = arrow_of(arrows, 0, 1, 0)
    turning = arrow_of(arrows, 1, 0, 0)

    cell, side = target_box(hooked)
    assert (hooked["cellRow"], hooked["cellColumn"]) == ("1", "1")
    assert (turning["cellRow"], turning["cellColumn"]) == ("1", "1")
    problems = box_problems(
        "↳", to_box(hooked["box"]), left=cell.left + 0.4 * side, top=cell.top - 1
    )
    problems += box_problems(
        "↴", to_box(turning["box"]), left=cell.left - 1, top=cell.top + 0.06 * side
    )
    assert problems == []
    assert overlap_px(to_box(hooked["box"]), to_box(turning["box"])) <= 1
