"""Viewport AC-9: the dashes of a hyphen edge in every state, and the revealed notch.

On the mocked room of `tests/spec042_harness.py`, desktop context, FX-01 with
`VI-DE` and `NA-VAL`. The tests read what the page paints, decoded from
screenshots by `tests/viewport_harness.py`, against `specs/_design/cells.md`
« Hyphen edges ». The edge at rest is in `test_viewport_hyphen_edges_ac9_edges.py`.

Choices where the spec leaves room:

- "The same in every state": the same look by the formula for the cell's
  current size. Before and after the state, the dashes match the formula at the
  side read then (Auteurs mode shows its legend under the grid, which refits it
  from about 57.4 to 49.8 px, 7 dashes to 6); every pixel row (or column) of the
  thickness holds the same dashes; while the side is unchanged, the hyphen grey
  pixels are exactly those of before. Each other pixel the dashes cover is the
  background of one of the two cells (read 4 px from the line), never the rule
  grey. The flash is read in the screenshot that shows its colour.
- The revealed notch over a down hyphen: at 56 px the dashes (2 px, the line's
  pixel and the next one down) do not reach into (1, 1), so the notch is read on
  72 px cells and more (1024 by 768, about 130 px), where the dashes are 3 px
  and their top pixel row is the bottom row of (1, 1).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellRef,
    CheckResult,
    Direction,
    GridView,
    WordTarget,
)
from spec019_harness import (
    MockRoomSocket,
    cell_locked_frame,
    letter_changed_frame,
    turn_switch_on,
)
from spec042_harness import (
    RULE,
    WAIT_TIMEOUT_MS,
    ChangeList,
    Rgb,
    box_of,
    cell_at,
    flash_composite,
    fx01_view,
    me,
    open_room,
    player,
    selection_frame,
)
from viewport_harness import (
    HYPHEN,
    INTERIOR_OFFSET,
    LARGE_SIDES,
    LARGE_WINDOW,
    MEDIUM_SIDES,
    MEDIUM_WINDOW,
    NAVAL_EDGE,
    VIDE_EDGE,
    EdgeReading,
    Side,
    dash_count,
    dash_thickness,
    expected_runs,
    grid_picture,
    hyphen_positions,
    open_fx01,
    read_edge,
    require_side,
    run_problems,
    runs_of,
    thickness_offsets,
)
from viewport_harness import hyphen_grid as hyphen_grid

CATALOGUE_KIND = "published_force_1"


# ---- AC-9: the same dashes in every state ----------------------------------------

STATE_SEQ = 5
P2_COLOUR = 5  # Magenta, the darkest flash


def state_view(grid: Grid) -> GridView:
    """FX-01 with `X` by `p1` at (2, 2) and `D` by `p2` at (2, 3)."""
    changes: ChangeList = [
        (2, 2, {"letter": "X", "author": "p1"}),
        (2, 3, {"letter": "D", "author": "p2"}),
    ]
    return fx01_view(grid, changes)


def read_vide_edge(page: Page) -> EdgeReading:
    return read_edge(page, grid_picture(page), VIDE_EDGE, Side.RIGHT, (3, 2))


FLASH_SCRIPT = """
() => {
  const cell = document.querySelector(
    '[data-testid="cell"][data-row="2"][data-column="2"]'
  );
  return cell !== null && cell.getAttribute('data-flash') !== '';
}
"""


def apply_state(page: Page, mock: MockRoomSocket, state: str) -> None:
    """Put the room in one state of AC-9, and wait until the page shows it."""
    mock_send = mock.send
    vide_cell = cell_at(page, *VIDE_EDGE)
    if state == "tint":
        mock_send(selection_frame("p2", 2, 1, Direction.ACROSS))
        expect(vide_cell).to_have_attribute("data-tinted-by", "p2")
    elif state == "locked":
        mock_send(cell_locked_frame(STATE_SEQ + 1, 2, 2, "I", revealed=False))
        expect(vide_cell).to_have_attribute("data-locked", "true")
    elif state == "wrong":
        result = CheckResult(
            seq=STATE_SEQ + 1,
            player_id="p1",
            target=WordTarget(row=2, column=0, clue_index=0),
            correct=(),
            wrong=(CellRef(row=2, column=2),),
        )
        mock_send(result.model_dump_json())
        expect(vide_cell).to_have_attribute("data-wrong", "true")
    elif state == "flash":
        mock_send(letter_changed_frame(STATE_SEQ + 1, 2, 2, "Y", "p2"))
        page.wait_for_function(FLASH_SCRIPT, timeout=WAIT_TIMEOUT_MS)
    elif state == "authors":
        turn_switch_on(page)
    else:
        raise ValueError(f"unknown state {state!r}")


def close_to(colour: Rgb, expected: tuple[float, float, float]) -> bool:
    """Each channel within 2 of the expected one."""
    for channel, wanted in zip(colour, expected, strict=True):
        if abs(channel - wanted) > 2:
            return False
    return True


def gap_problems(reading: EdgeReading) -> list[str]:
    """Pixels the dashes cover that are neither hyphen grey nor a cell's background.

    A cell's background is read 4 px from the line, in the same row (or column).
    """
    covered = thickness_offsets(dash_thickness(reading.cell_side))
    before_cell = reading.inner(-INTERIOR_OFFSET)
    after_cell = reading.inner(INTERIOR_OFFSET)
    problems: list[str] = []
    for offset in covered:
        for index, colour in enumerate(reading.inner(offset)):
            backgrounds: list[Rgb] = []
            if offset <= 0:
                backgrounds.append(before_cell[index])
            if offset >= 0:
                backgrounds.append(after_cell[index])
            if colour != HYPHEN and (colour == RULE or colour not in backgrounds):
                problems.append(f"offset {offset}, pixel {index}: {colour}")
    return problems


def dash_problems(reading: EdgeReading) -> list[str]:
    """How an edge's dashes differ from the formula at the side it was read at.

    Each offset of the thickness holds the formula's dashes in hyphen grey, the
    same at every offset, and no offset outside the thickness holds any.
    """
    covered = thickness_offsets(dash_thickness(reading.cell_side))
    expected = expected_runs(reading.cell_side)
    dashes = hyphen_positions(reading)
    problems: list[str] = []
    for offset in covered:
        for problem in run_problems(runs_of(reading.inner(offset), HYPHEN), expected):
            problems.append(f"offset {offset}: {problem}")
        if dashes[offset] != dashes[0]:
            problems.append(f"offset {offset}: dashes {dashes[offset]}")
    for offset, indexes in dashes.items():
        if offset not in covered and indexes:
            problems.append(f"offset {offset} outside the thickness: {indexes}")
    return problems


@pytest.mark.parametrize("state", ["tint", "locked", "wrong", "flash", "authors"])
def test_ac9_the_dashes_read_the_same_in_every_state_of_the_two_cells(
    page: Page, live_server: str, hyphen_grid: Grid, state: str
) -> None:
    page.set_viewport_size(MEDIUM_WINDOW)
    players = [me(), player("p2", P2_COLOUR)]
    mock = open_room(page, live_server, state_view(hyphen_grid), players)
    require_side(page, VIDE_EDGE, MEDIUM_SIDES)
    before = read_vide_edge(page)
    assert len(runs_of(before.inner(0), HYPHEN)) == dash_count(before.cell_side)

    apply_state(page, mock, state)
    after = read_vide_edge(page)

    if state == "flash":
        inside = after.inner(-INTERIOR_OFFSET)[after.length // 2]
        assert close_to(inside, flash_composite(P2_COLOUR)), "read after the flash"
    assert dash_problems(before) == []
    assert dash_problems(after) == []
    if after.cell_side == before.cell_side:
        assert hyphen_positions(after) == hyphen_positions(before)
    assert gap_problems(after) == []


# ---- AC-9: the revealed notch over a down hyphen ---------------------------------

NOTCH_MARGIN_PX = 3


def test_ac9_a_revealed_cell_puts_its_notch_over_the_down_hyphens_dashes(
    page: Page, live_server: str, hyphen_grid: Grid
) -> None:
    changes: ChangeList = [
        (1, 1, {"letter": "A", "author": None, "locked": True, "revealed": True})
    ]
    open_fx01(page, live_server, fx01_view(hyphen_grid, changes), LARGE_WINDOW)
    side = require_side(page, NAVAL_EDGE, LARGE_SIDES)
    expect(cell_at(page, *NAVAL_EDGE).get_by_test_id("reveal-mark")).to_have_count(1)
    notch = box_of(cell_at(page, *NAVAL_EDGE).get_by_test_id("reveal-mark"))

    reading = read_edge(page, grid_picture(page), NAVAL_EDGE, Side.BOTTOM, (1, 2))

    assert dash_thickness(side) == 3
    dashes = hyphen_positions(reading)
    assert run_problems(runs_of(reading.inner(0), HYPHEN), expected_runs(side)) == []
    assert dashes[1] == dashes[0]
    under_notch: list[int] = []
    beside_notch: list[int] = []
    for index in dashes[0]:
        x = reading.first_inner + index
        if notch.left + NOTCH_MARGIN_PX <= x <= notch.right - NOTCH_MARGIN_PX:
            under_notch.append(index)
        elif x < notch.left - 1 or x > notch.right + 1:
            beside_notch.append(index)
    assert under_notch, (dashes[0], notch)
    in_the_cell = reading.inner(-1)
    for index in under_notch:
        assert in_the_cell[index] != HYPHEN, f"pixel {index} shows a dash"
    for index in beside_notch:
        assert in_the_cell[index] == HYPHEN, f"pixel {index}: {in_the_cell[index]}"
