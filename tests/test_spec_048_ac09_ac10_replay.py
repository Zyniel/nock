"""Tests of spec 048, AC-9 and AC-10: the replay card, its list of edits with the
current step marked, its two forms, and its grid drawn with the playing grid's
cells.

The server is spec 038's live server with `operator_token=OPS_TOKEN`; the token
is seeded, the dashboard answered with AC-5's 7-day figures, and
`page.route("**/api/ops/rooms/*/edits", ...)` answers `REPLAY`, `REPLAY_FX02` or
`REPLAY_EMPTY` (`spec048_ops_harness`) after a submit of `k7qm2x`. Windows:
desktop contexts in Paris time, at 1280 by 720 and 360 by 740 unless a test
says otherwise.

Readings of the spec's wording:

- "On one row, the button's bottom on the input's bottom": the bottoms within
  1 px and the button right of the input.
- "`ops-replay-position-field` is under the grid, as wide as it": its top is not
  above the grid's bottom (1 px) and its width is the grid's (1 px).
- "`ops-replay-step` is under it, its left edge on the grid's left edge (1 px)
  and no wider than the grid (1 px), as wide as its text" (refined by the lead on
  2026-10-23, after the first version of these tests, which wanted it as wide as
  the grid): its top is not above the field's bottom (1 px), its left edge on the
  grid's (1 px), its width at most the grid's plus 1 px, and its width that of
  its text plus its horizontal paddings and borders (1 px).
- "Seven `ops-edit` items 4 px apart": from one item's bottom to the next one's
  top, 4 px (1 px).
- "Top to bottom ... each as wide as the card's content or narrower": each
  part's top is not above the previous part's bottom (1 px), and each lies
  inside the card's content box horizontally (1 px).
- "25 cells in 5 rows of 5": the 25 `ops-replay-cell` and `ops-replay-block`
  elements of `ops-replay-grid` fill the 25 places of a 5 by 5 grid of 44 px
  cells, placed by their boxes.
- "(1, 0) shows `T`": its `data-letter` is `T` and its text `T`; "shows
  nothing": `data-letter` is `""` and it holds no text.
- The letter's look is read on the element that holds its text (see
  `spec048_harness`); "on rgb(...)" is the colour behind that element.
- "The notch ... its bottom on the cell's inner bottom edge": the cell's box less
  its 1 px bottom line (spec 042's inner box), 1 px; "horizontally centred on
  the cell": its centre on the inner box's centre (1 px).
- The edge cases of AC-9 and AC-10 are checked as well: a window of exactly
  900 px has the two-column form and one of 899 px the one-column form; a pencil
  letter later locked is not a pencil letter; an undo that puts back a pencil
  letter makes it a pencil letter again.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.operations import RoomReplay
from spec038_harness import OpsServer, ops_live_server
from spec042_harness import Box, box_of
from spec043_harness import (
    INK,
    MUTED,
    RULE,
    WHITE,
    WORD,
    colour_matches,
    colour_of,
    fr_value,
    is_clear,
    style_of,
)
from spec046_harness import (
    SUBPIXEL_PX,
    OpenWindow,
    button_colour_problems,
    card_problems,
    colour_problem,
    content_box,
    font_problems,
    inside_horizontally,
    same_font,
    same_position,
    same_size,
    window_opener,
)
from spec048_harness import (
    CLUE_BG,
    LOCKED,
    PENCIL,
    SIZE_IDS,
    SIZES,
    box_inside,
    letter_of,
    no_horizontal_scroll,
    others_in,
    radius_padding_problems,
    role_problems,
    text_problems,
    text_width,
)
from spec048_ops_harness import (
    REPLAY_COUNT,
    ReplayCell,
    cell_side_problems,
    clue_cells,
    expect_replay_state,
    grid_position,
    letter_cells,
    notches_in,
    open_replay,
    replay,
    replay_answer,
    replay_cell,
    replay_cells,
    replay_empty,
    replay_fx02,
    replay_of,
    room_edit,
    set_position,
    step_text,
)

WIDE_SIDE = 44.0
PHONE_SIDE = 36.0
FX02_PHONE_SIDE = 22.0  # floor((294 - 1) / 13)
REPLAY_PARTS = [
    "ops-replay-grid",
    "ops-replay-position-field",
    "ops-replay-step",
    "ops-edits",
]


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def server(tmp_path: Path, catalogue: Catalogue) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue) as running:
        yield running


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


def replay_page(
    window: OpenWindow,
    server: OpsServer,
    size: tuple[int, int],
    answer: RoomReplay,
) -> Page:
    """The ops page showing `answer`'s replay, `ready`, at its maximum position."""
    page = window(*size)
    open_replay(page, server.base_url, replay_answer(answer), "ready")
    if len(answer.edits) > 0:
        expect(page.get_by_test_id("ops-edit")).to_have_count(len(answer.edits))
        expect(page.get_by_test_id("ops-replay-cell").first).to_be_visible()
    return page


def steps_of(page: Page) -> list[str | None]:
    items = page.get_by_test_id("ops-edit")
    steps: list[str | None] = []
    for index in range(items.count()):
        steps.append(items.nth(index).get_attribute("data-step"))
    return steps


def step_look_problems(page: Page) -> list[str]:
    """Each `ops-edit`'s colours and weight for its `data-step`."""
    items = page.get_by_test_id("ops-edit")
    problems: list[str] = []
    for index in range(items.count()):
        item = items.nth(index)
        name = f"ops-edit {index + 1}"
        step = item.get_attribute("data-step")
        if step == "done":
            problems.extend(colour_problem(item, name, "color", INK))
            if not is_clear(colour_of(item, "backgroundColor")):
                problems.append(f"{name}: a background on a done step")
        elif step == "current":
            problems.extend(colour_problem(item, name, "backgroundColor", WORD))
            problems.extend(colour_problem(item, name, "color", INK))
            if style_of(item, "fontWeight") != "600":
                problems.append(f"{name}: weight {style_of(item, 'fontWeight')}")
        else:
            problems.extend(colour_problem(item, name, "color", MUTED))
    return problems


def cell_attributes(page: Page, row: int, column: int) -> dict[str, str | None]:
    cell = replay_cell(page, row, column)
    expect(cell).to_have_count(1)
    found: dict[str, str | None] = {}
    for name in ("data-letter", "data-locked", "data-revealed", "data-pencil"):
        found[name] = cell.get_attribute(name)
    return found


def letter_look_problems(
    page: Page,
    cell_at: tuple[int, int],
    letter: str,
    weight: str,
    style: str,
    colour: tuple[int, int, int],
    behind: tuple[int, int, int],
) -> list[str]:
    """The letter a cell shows, its size (0.56 of 44 px), weight, style, colours."""
    reading = letter_of(replay_cell(page, *cell_at))
    name = f"cell {cell_at}"
    if reading is None:
        return [f"{name} shows no letter"]
    problems: list[str] = []
    if reading["text"] != letter:
        problems.append(f"{name} shows {reading['text']!r}")
    size = float(str(reading["fontSize"]).removesuffix("px"))
    if not same_font(size, 0.56 * WIDE_SIDE):
        problems.append(f"{name}: font-size {size}")
    if reading["fontWeight"] != weight:
        problems.append(f"{name}: weight {reading['fontWeight']}")
    if reading["fontStyle"] != style:
        problems.append(f"{name}: style {reading['fontStyle']}")
    text_colour = reading["colour"]
    assert isinstance(text_colour, list), reading
    if not colour_matches(text_colour, colour):
        problems.append(f"{name}: colour {text_colour}")
    background = reading["behind"]
    if not isinstance(background, list) or not colour_matches(background, behind):
        problems.append(f"{name}: on {background}")
    return problems


def column_of(page: Page, test_id: str) -> Box:
    return box_of(page.get_by_test_id(test_id))


def is_two_column_form(page: Page) -> bool:
    """The edits left of the grid, their tops level (AC-9's two-column form)."""
    edits = column_of(page, "ops-edits")
    grid = column_of(page, "ops-replay-grid")
    return grid.left >= edits.right and same_position(grid.top, edits.top)


# ---- AC-9: the card, its form and its two forms ------------------------------------


def test_ac9_the_replay_is_a_card_whose_form_is_one_row(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))
    card = page.get_by_test_id("ops-replay")
    form = card.get_by_test_id("ops-replay-form")
    label = form.get_by_text(fr_value("ops.replay_code_label"), exact=True)
    expect(label).to_have_count(1)
    field = box_of(form.get_by_test_id("ops-replay-code"))
    submit = form.get_by_test_id("ops-replay-submit")

    problems = card_problems(card)
    problems.extend(button_colour_problems(submit, "primary"))
    if not same_position(box_of(submit).bottom, field.bottom):
        problems.append(f"the button's bottom {box_of(submit).bottom}, {field.bottom}")
    if box_of(submit).left < field.right - 1.0:
        problems.append("ops-replay-submit is not right of the input")

    assert problems == []


def test_ac9_on_a_wide_window_the_edits_are_left_of_the_grid(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))
    body = page.get_by_test_id("ops-replay-body")
    expect(body.get_by_test_id("ops-edits")).to_have_count(1)
    expect(body.get_by_test_id("ops-replay-grid")).to_have_count(1)
    edits = column_of(page, "ops-edits")
    grid = column_of(page, "ops-replay-grid")

    problems: list[str] = []
    if not same_position(grid.left - edits.right, 20.0):
        problems.append(f"the grid is {grid.left - edits.right} px right of the list")
    if not same_position(grid.top, edits.top):
        problems.append(f"the tops {grid.top} and {edits.top} differ")
    field = column_of(page, "ops-replay-position-field")
    if field.top < grid.bottom - 1.0:
        problems.append("ops-replay-position-field is not under the grid")
    if not same_position(field.width, grid.width):
        problems.append(f"the field is {field.width} px wide, the grid {grid.width}")
    problems.extend(step_line_problems(page, grid, field))

    assert problems == []


def step_line_problems(page: Page, grid: Box, field: Box) -> list[str]:
    """`ops-replay-step` under the field, on the grid's left edge, as wide as its
    text and no wider than the grid (spec 048 AC-9, refined on 2026-10-23)."""
    step = page.get_by_test_id("ops-replay-step")
    box = box_of(step)
    problems: list[str] = []
    if box.top < field.bottom - 1.0:
        problems.append("ops-replay-step is not under ops-replay-position-field")
    if not same_position(box.left, grid.left):
        problems.append(
            f"ops-replay-step's left edge {box.left}, the grid's {grid.left}"
        )
    if box.width > grid.width + 1.0 + SUBPIXEL_PX:
        problems.append(
            f"ops-replay-step is {box.width} px wide, the grid {grid.width}"
        )
    sides = 0.0
    for part in ("paddingLeft", "paddingRight", "borderLeftWidth", "borderRightWidth"):
        sides += float(style_of(step, part).removesuffix("px"))
    expected = text_width(step) + sides
    if not same_position(box.width, expected):
        problems.append(f"ops-replay-step is {box.width} px wide, its text {expected}")
    return problems


def test_ac9_the_edits_are_a_plain_list_of_lines_4_px_apart(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))
    edits = page.get_by_test_id("ops-edits")
    items = edits.get_by_test_id("ops-edit")
    expect(items).to_have_count(REPLAY_COUNT)

    problems: list[str] = []
    if edits.evaluate("element => element.tagName") != "OL":
        problems.append("ops-edits is not an ol")
    problems.extend(role_problems(edits, "ops-edits", "list"))
    if style_of(items.first, "listStyleType") != "none":
        problems.append(f"list-style-type {style_of(items.first, 'listStyleType')}")
    previous: Box | None = None
    for index in range(REPLAY_COUNT):
        item = items.nth(index)
        name = f"ops-edit {index + 1}"
        problems.extend(font_problems(item, name, 13.6))
        if style_of(item, "fontVariantNumeric") != "tabular-nums":
            problems.append(f"{name}: {style_of(item, 'fontVariantNumeric')}")
        problems.extend(radius_padding_problems(item, name, "4px", "4px 8px"))
        box = box_of(item)
        if previous is not None and not same_position(box.top - previous.bottom, 4.0):
            problems.append(f"{name} is {box.top - previous.bottom} px under the last")
        previous = box

    assert problems == []


def test_ac9_at_the_maximum_the_last_edit_is_current(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))

    expect(page.get_by_test_id("ops-replay-position")).to_have_value("7")
    assert steps_of(page) == ["done"] * 6 + ["current"]
    assert step_look_problems(page) == []


def test_ac9_at_the_position_4_the_steps_are_done_current_and_later(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))

    set_position(page, 4)

    step = page.get_by_test_id("ops-replay-step")
    assert steps_of(page) == ["done"] * 3 + ["current"] + ["later"] * 3
    assert step_look_problems(page) == []
    assert text_problems(step, "ops-replay-step", step_text(4)) == []
    assert font_problems(step, "ops-replay-step", 13.6, colour=MUTED) == []


def test_ac9_at_the_position_0_every_edit_is_later(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))

    set_position(page, 0)

    assert steps_of(page) == ["later"] * REPLAY_COUNT
    assert step_look_problems(page) == []


def test_ac9_on_a_phone_the_grid_slider_step_and_edits_stack(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (360, 740), replay(fx01_grid))
    inner = content_box(page.get_by_test_id("ops-replay"))

    problems: list[str] = []
    previous: Box | None = None
    for test_id in REPLAY_PARTS:
        box = column_of(page, test_id)
        if previous is not None and box.top < previous.bottom - 1.0:
            problems.append(f"{test_id} is not under the part before it")
        if not inside_horizontally(box, inner):
            problems.append(f"{test_id} {box} is wider than the card's content")
        previous = box

    assert problems == []
    assert no_horizontal_scroll(page)


@pytest.mark.parametrize(
    ("width", "two_columns", "side"),
    [(900, True, WIDE_SIDE), (899, False, PHONE_SIDE)],
    ids=["900", "899"],
)
def test_ac9_the_replay_has_two_columns_from_a_900_px_window(
    window: OpenWindow,
    server: OpsServer,
    fx01_grid: Grid,
    width: int,
    two_columns: bool,
    side: float,
) -> None:
    page = replay_page(window, server, (width, 720), replay(fx01_grid))

    assert is_two_column_form(page) is two_columns
    assert cell_side_problems(page, side) == []


# ---- AC-10: the replay's grid ------------------------------------------------------


def place_problems(cells: list[ReplayCell], grid: Grid, side: float) -> list[str]:
    """The cells fill the grid's places; letter cells and clue blocks are FX-01's."""
    origin = cells[0].box
    for cell in cells:
        if cell.box.left < origin.left or cell.box.top < origin.top:
            origin = Box(
                min(origin.left, cell.box.left),
                min(origin.top, cell.box.top),
                origin.right,
                origin.bottom,
            )
    letters: set[tuple[int, int]] = set()
    blocks: set[tuple[int, int]] = set()
    places: set[tuple[int, int]] = set()
    problems: list[str] = []
    for cell in cells:
        place = grid_position(cell.box, origin, side)
        places.add(place)
        if cell.test_id == "ops-replay-cell":
            letters.add(place)
            if (cell.row, cell.column) != (str(place[0]), str(place[1])):
                problems.append(f"the cell at {place} says {cell.row}, {cell.column}")
        else:
            blocks.add(place)
            if cell.kind != "clue":
                problems.append(f"the block at {place} has data-type {cell.kind}")
            if not colour_matches(cell.background, CLUE_BG):
                problems.append(f"the block at {place} is {cell.background}")
            if cell.text != "":
                problems.append(f"the block at {place} reads {cell.text!r}")
    every_place = {(row, column) for row in range(5) for column in range(5)}
    if places != every_place:
        problems.append(f"the cells fill {sorted(places)}")
    if letters != letter_cells(grid):
        problems.append(f"letter cells at {sorted(letters)}")
    if blocks != clue_cells(grid):
        problems.append(f"clue blocks at {sorted(blocks)}")
    return problems


def line_problems(cells: list[ReplayCell]) -> list[str]:
    """Each cell's right and bottom lines: 1 px solid `--nock-rule`."""
    problems: list[str] = []
    for cell in cells:
        for side, (width, style, colour) in (
            ("right", cell.right),
            ("bottom", cell.bottom),
        ):
            if width != "1px" or style != "solid" or not colour_matches(colour, RULE):
                problems.append(f"a cell's {side} line is {width} {style} {colour}")
                return problems
    return problems


def test_ac10_the_grid_has_25_cells_of_44_px_with_its_lines(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))
    grid = page.get_by_test_id("ops-replay-grid")
    cells = replay_cells(page)

    problems: list[str] = []
    for side in ("Left", "Top"):
        if style_of(grid, f"border{side}Width") != "1px":
            problems.append(
                f"the grid's {side} line {style_of(grid, f'border{side}Width')}"
            )
        if style_of(grid, f"border{side}Style") != "solid":
            problems.append(f"the grid's {side} line is not solid")
        problems.extend(colour_problem(grid, "grid", f"border{side}Color", RULE))
    problems.extend(cell_side_problems(page, WIDE_SIDE))
    problems.extend(line_problems(cells))

    assert len(cells) == 25
    assert problems == []


def test_ac10_the_letter_cells_and_clue_blocks_sit_at_fx01_s_cells(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))
    cells = replay_cells(page)

    expect(page.get_by_test_id("ops-replay-cell")).to_have_count(18)
    expect(page.get_by_test_id("ops-replay-block")).to_have_count(7)
    assert place_problems(cells, fx01_grid, WIDE_SIDE) == []


def test_ac10_at_the_maximum_each_letter_shows_its_marks(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))

    attributes = {
        (1, 0): cell_attributes(page, 1, 0),
        (2, 3): cell_attributes(page, 2, 3),
        (1, 2): cell_attributes(page, 1, 2),
        (3, 4): cell_attributes(page, 3, 4),
    }
    problems = letter_look_problems(page, (1, 0), "T", "500", "normal", INK, WHITE)
    problems.extend(
        letter_look_problems(page, (2, 3), "D", "500", "italic", PENCIL, WHITE)
    )
    problems.extend(
        letter_look_problems(page, (1, 2), "M", "700", "normal", INK, LOCKED)
    )
    problems.extend(
        letter_look_problems(page, (3, 4), "N", "700", "normal", INK, LOCKED)
    )

    assert attributes[(1, 0)]["data-letter"] == "T"
    assert attributes[(1, 0)]["data-locked"] == "false"
    assert attributes[(1, 0)]["data-pencil"] == "false"
    assert attributes[(2, 3)]["data-letter"] == "D"
    assert attributes[(2, 3)]["data-pencil"] == "true"
    assert attributes[(1, 2)]["data-letter"] == "M"
    assert attributes[(1, 2)]["data-locked"] == "true"
    assert attributes[(1, 2)]["data-revealed"] == "false"
    assert attributes[(3, 4)]["data-letter"] == "N"
    assert attributes[(3, 4)]["data-locked"] == "true"
    assert attributes[(3, 4)]["data-revealed"] == "true"
    assert problems == []


def test_ac10_a_revealed_cell_has_one_hidden_notch_on_its_bottom_edge(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))
    cell = box_of(replay_cell(page, 3, 4))
    inner = Box(cell.left, cell.top, cell.right - 1.0, cell.bottom - 1.0)

    notches = notches_in(replay_cell(page, 3, 4))
    others = notches_in(replay_cell(page, 1, 2))

    assert len(notches) == 1
    hidden, notch = notches[0]
    assert hidden
    assert same_size(notch.width, 0.22 * WIDE_SIDE), notch
    assert same_size(notch.height, 0.11 * WIDE_SIDE), notch
    assert same_position(notch.centre_x, inner.centre_x), (notch, inner)
    assert same_position(notch.bottom, inner.bottom), (notch, inner)
    assert others == []


def test_ac10_no_cell_holds_an_arrow_a_selection_a_player_or_clue_text(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))
    grid = page.get_by_test_id("ops-replay-grid")

    for test_id in ("clue-arrow", "remote-selection", "player-icon", "clue-text"):
        expect(grid.get_by_test_id(test_id)).to_have_count(0)
    blocks = page.get_by_test_id("ops-replay-block")
    texts = blocks.evaluate_all("blocks => blocks.map(b => b.textContent.trim())")
    assert texts == [""] * 7


def test_ac10_at_the_position_4_the_lock_and_the_reveal_are_not_there_yet(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (1280, 720), replay(fx01_grid))

    set_position(page, 4)

    locked = cell_attributes(page, 1, 2)
    revealed = cell_attributes(page, 3, 4)
    pencil = cell_attributes(page, 2, 3)
    assert locked["data-locked"] == "false"
    assert revealed["data-letter"] == ""
    assert revealed["data-revealed"] == "false"
    assert letter_of(replay_cell(page, 3, 4)) is None
    assert pencil["data-letter"] == "D"
    assert pencil["data-pencil"] == "true"


def test_ac10_on_a_phone_the_cells_are_36_px(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = replay_page(window, server, (360, 740), replay(fx01_grid))

    assert cell_side_problems(page, PHONE_SIDE) == []


def test_ac10_fx02_on_a_phone_has_22_px_cells_inside_the_card(
    window: OpenWindow, server: OpsServer, fx02_grid: Grid
) -> None:
    page = replay_page(window, server, (360, 740), replay_fx02(fx02_grid))
    grid = box_of(page.get_by_test_id("ops-replay-grid"))
    card = box_of(page.get_by_test_id("ops-replay"))

    assert cell_side_problems(page, FX02_PHONE_SIDE) == []
    assert box_inside(grid, card)
    assert no_horizontal_scroll(page)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac10_a_room_with_no_edit_shows_its_empty_line_only(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = replay_page(window, server, size, replay_empty(fx01_grid))
    card = page.get_by_test_id("ops-replay")
    line = card.get_by_test_id("ops-replay-state-line")
    expect(line).to_have_count(1)
    expect_replay_state(page, "ready")

    problems = text_problems(line, "line", fr_value("ops.replay_empty"))
    problems.extend(font_problems(line, "line", 15.2, colour=MUTED))
    problems.extend(role_problems(line, "line", None))
    selectors = ["h2", '[data-testid="ops-replay-form"]']
    selectors.append('[data-testid="ops-replay-state-line"]')
    problems.extend(others_in(card, selectors))
    if box_of(line).top < box_of(card.get_by_test_id("ops-replay-form")).bottom - 1.0:
        problems.append("the line is not under the form")

    assert problems == []
    for test_id in ("ops-replay-grid", "ops-replay-position", "ops-edits"):
        expect(page.get_by_test_id(test_id)).to_have_count(0)


def test_ac10_a_pencil_letter_later_locked_is_not_a_pencil_letter(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    edits = (
        room_edit(1, "typed", (2, 3), "D", "p2", pencil=True),
        room_edit(2, "locked", (2, 3), "D"),
    )
    page = replay_page(window, server, (1280, 720), replay_of(fx01_grid, edits))

    attributes = cell_attributes(page, 2, 3)
    reading = letter_of(replay_cell(page, 2, 3))

    assert attributes["data-locked"] == "true"
    assert attributes["data-pencil"] == "false"
    assert reading is not None
    assert reading["fontStyle"] == "normal"


def test_ac10_an_undo_that_puts_back_a_pencil_letter_makes_it_pencil_again(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    edits = (
        room_edit(1, "typed", (1, 1), "A", "p1", pencil=True),
        room_edit(2, "erased", (1, 1), None, "p1"),
        room_edit(3, "undone", (1, 1), "A", "p1", pencil=True),
    )
    page = replay_page(window, server, (1280, 720), replay_of(fx01_grid, edits))
    at_three = cell_attributes(page, 1, 1)
    reading = letter_of(replay_cell(page, 1, 1))

    set_position(page, 2, 3)

    assert at_three["data-letter"] == "A"
    assert at_three["data-pencil"] == "true"
    assert reading is not None
    assert reading["fontStyle"] == "italic"
    assert cell_attributes(page, 1, 1)["data-pencil"] == "false"
