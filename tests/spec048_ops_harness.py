"""Shared setup of the tests of spec 048 for the operator page `/ops`.

Pytest does not collect this module. It holds what the test files of AC-6 to
AC-12 and AC-14 use for the ops page: the seeded token, the mocked ops API of the
"Test harness" (spec 038 AC-7's dashboard with AC-5's 7-day figures, the replay
route), the replays `REPLAY`, `REPLAY_FX02` and `REPLAY_EMPTY`, and the readers of
the replay's grid. The readings and tolerances of `spec048_harness.py` hold here.

Readings:

- `REPLAY_FX02`'s one typed edit is at (0, 2), FX-02's first letter cell, as the
  spec's "Test harness" says since the lead's note of 2026-10-23 (it read
  (1, 0), a clue cell of FX-02); the spec names no letter, so it is `A` by `p1`.
  Each edit of a replay is made 5 seconds after the one before.
- The replay's cells are placed by their boxes: a cell's row and column are its
  offset from the first cell, divided by the cell's side, rounded.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from playwright.sync_api import Locator, Page, Route, expect

from fonts_ready import wait_for_fonts
from nock.grid import ClueCell, Grid, LetterCell
from nock.operations import EditKind, RoomEdit, RoomReplay
from nock.protocol import grid_view
from spec038_harness import (
    DASHBOARD_ROUTE,
    OPS_TOKEN,
    OPS_TOKEN_KEY,
    DashboardRoute,
    dashboard_answer,
    seven_day_figures,
)
from spec042_harness import READERS_JS, Box, Colour, to_box, to_colour
from spec046_harness import fulfil_json, same_size
from spec048_harness import ROOM_CODE, WAIT_TIMEOUT_MS

NOW = 1_800_000_000.0  # the dashboard's clock (spec 038's tests)
REPLAY_ROUTE = "**/api/ops/rooms/*/edits"
REPLAY_START = datetime(2026, 10, 22, 19, 2, 11, tzinfo=UTC)
NICKNAMES = {"p1": "ANA", "p2": "BOB"}
REPLAY_COUNT = 7  # the edits of `REPLAY`
STEP_TEXT = "Étape {step} sur {count}"


def step_text(step: int, count: int = REPLAY_COUNT) -> str:
    """`Etape <step> sur <count>` (with an E acute), as the criteria write it."""
    return STEP_TEXT.format(step=step, count=count)


# ---- The ops page ------------------------------------------------------------------


def seed_ops_token(page: Page) -> None:
    """`sessionStorage["nock.ops_token"]` = `OPS_TOKEN`, by an init script."""
    script = (
        f"sessionStorage.setItem({json.dumps(OPS_TOKEN_KEY)}, {json.dumps(OPS_TOKEN)})"
    )
    page.context.add_init_script(script)


def answer_dashboard(page: Page) -> DashboardRoute:
    """Answer the dashboard requests with AC-5's 7-day figures (spec 038)."""
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW))])
    page.route(DASHBOARD_ROUTE, route.handle)
    return route


def expect_ops_state(page: Page, state: str) -> None:
    expect(page.get_by_test_id("ops-page")).to_have_attribute(
        "data-state", state, timeout=WAIT_TIMEOUT_MS
    )


def expect_replay_state(page: Page, state: str) -> None:
    expect(page.get_by_test_id("ops-replay")).to_have_attribute(
        "data-state", state, timeout=WAIT_TIMEOUT_MS
    )


def open_ops(page: Page, base_url: str) -> None:
    """Open `/ops` and wait for the ops page (any state)."""
    page.goto(f"{base_url}/ops")
    expect(page.get_by_test_id("ops-page")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_for_fonts(page)


def open_ready_ops(page: Page, base_url: str) -> None:
    """The token seeded, the 7-day figures answered: wait for `ready`."""
    seed_ops_token(page)
    answer_dashboard(page)
    open_ops(page, base_url)
    expect_ops_state(page, "ready")
    expect(page.get_by_test_id("ops-metric")).to_have_count(6)
    wait_for_fonts(page)


class ReplayRoute:
    """Answers `GET /api/ops/rooms/<code>/edits`: a status and a body, or held."""

    def __init__(self, status: int | None, body: object = None) -> None:
        self.status = status
        self.body = body
        self.held: list[Route] = []
        self.urls: list[str] = []

    def handle(self, route: Route) -> None:
        self.urls.append(route.request.url)
        if self.status is None:
            self.held.append(route)
            return
        fulfil_json(route, self.status, self.body)


def replay_answer(replay: RoomReplay) -> ReplayRoute:
    return ReplayRoute(200, replay.model_dump(mode="json"))


def submit_replay(page: Page, code: str = "k7qm2x") -> None:
    """Type `code` in `ops-replay-code`, check it, then submit."""
    field = page.get_by_test_id("ops-replay-code")
    field.fill(code)
    expect(field).to_have_value(code)
    page.get_by_test_id("ops-replay-submit").click()


def open_replay(
    page: Page, base_url: str, route: ReplayRoute, state: str, code: str = "k7qm2x"
) -> None:
    """The ready ops page, then the replay of `code` until it is `state`."""
    page.route(REPLAY_ROUTE, route.handle)
    open_ready_ops(page, base_url)
    submit_replay(page, code)
    expect_replay_state(page, state)
    wait_for_fonts(page)


def set_position(page: Page, position: int, count: int = REPLAY_COUNT) -> None:
    """Fill `ops-replay-position` with `position` and wait for the step text."""
    page.get_by_test_id("ops-replay-position").fill(str(position))
    expect(page.get_by_test_id("ops-replay-step")).to_have_text(
        step_text(position, count)
    )


# ---- The replays of the test harness -------------------------------------------------


def room_edit(
    seq: int,
    kind: EditKind,
    cell: tuple[int, int],
    letter: str | None,
    player: str | None = None,
    pencil: bool = False,
) -> RoomEdit:
    """One edit, made `seq` times 5 seconds after `REPLAY_START`."""
    row, column = cell
    nickname = None if player is None else NICKNAMES[player]
    return RoomEdit(
        seq=seq,
        at=REPLAY_START + timedelta(seconds=5 * seq),
        kind=kind,
        row=row,
        column=column,
        letter=letter,
        pencil=pencil,
        player_id=player,
        nickname=nickname,
    )


def replay_edits() -> tuple[RoomEdit, ...]:
    """`REPLAY`'s seven edits, in seq order."""
    return (
        room_edit(1, "typed", (1, 0), "T", "p1"),
        room_edit(2, "typed", (1, 1), "A", "p1"),
        room_edit(3, "typed", (1, 2), "M", "p2"),
        room_edit(4, "typed", (2, 3), "D", "p2", pencil=True),
        room_edit(5, "locked", (1, 2), "M"),
        room_edit(6, "revealed", (3, 4), "N"),
        room_edit(7, "typed", (1, 4), "S", "p1"),
    )


def replay_of(grid: Grid, edits: tuple[RoomEdit, ...]) -> RoomReplay:
    return RoomReplay(code=ROOM_CODE, grid=grid_view(grid), edits=edits)


def replay(fx01: Grid) -> RoomReplay:
    """`REPLAY`."""
    return replay_of(fx01, replay_edits())


def replay_fx02(fx02: Grid) -> RoomReplay:
    """`REPLAY_FX02`: one typed edit, at FX-02's first letter cell (0, 2)."""
    return replay_of(fx02, (room_edit(1, "typed", (0, 2), "A", "p1"),))


def replay_empty(fx01: Grid) -> RoomReplay:
    """`REPLAY_EMPTY`."""
    return replay_of(fx01, ())


def letter_cells(grid: Grid) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            cells.add((cell.row, cell.column))
    return cells


def clue_cells(grid: Grid) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            cells.add((cell.row, cell.column))
    return cells


def replay_cell(page: Page, row: int, column: int) -> Locator:
    return page.locator(
        f'[data-testid="ops-replay-cell"][data-row="{row}"][data-column="{column}"]'
    )


# Every cell of `ops-replay-grid` (letter cells and blocks), in document order:
# its test id, `data-row`, `data-column`, `data-type`, box, text, background and
# its right and bottom borders.
REPLAY_CELLS_SCRIPT = "grid => {\n" + READERS_JS + r"""
  const selector = '[data-testid="ops-replay-cell"], [data-testid="ops-replay-block"]';
  const found = [];
  for (const cell of grid.querySelectorAll(selector)) {
    const rect = cell.getBoundingClientRect();
    const style = getComputedStyle(cell);
    found.push({
      testId: cell.getAttribute('data-testid'),
      row: cell.getAttribute('data-row'),
      column: cell.getAttribute('data-column'),
      type: cell.getAttribute('data-type'),
      box: [rect.left, rect.top, rect.right, rect.bottom],
      text: cell.textContent.trim(),
      background: parseColour(style.backgroundColor),
      right: [style.borderRightWidth, style.borderRightStyle,
        parseColour(style.borderRightColor)],
      bottom: [style.borderBottomWidth, style.borderBottomStyle,
        parseColour(style.borderBottomColor)],
    });
  }
  return found;
}
"""

# The boxes of the elements of a cell drawn in `--nock-reveal` that are, or are
# inside, an `aria-hidden="true"` element (the revealed notch).
NOTCHES_SCRIPT = "cell => {\n" + READERS_JS + r"""
  const found = [];
  for (const element of cell.querySelectorAll('*')) {
    const colour = parseColour(getComputedStyle(element).backgroundColor);
    if (colour[3] === 0 || colour[0] !== 194 || colour[1] !== 65
        || colour[2] !== 12) {
      continue;
    }
    const hidden = element.closest('[aria-hidden="true"]');
    const rect = element.getBoundingClientRect();
    found.push({
      hidden: hidden !== null && cell.contains(hidden),
      box: [rect.left, rect.top, rect.right, rect.bottom],
    });
  }
  return found;
}
"""


class ReplayCell(NamedTuple):
    """One cell of the replay's grid, as `REPLAY_CELLS_SCRIPT` reads it."""

    test_id: str
    row: str | None
    column: str | None
    kind: str | None  # `data-type`
    box: Box
    text: str
    background: Colour
    right: tuple[str, str, Colour]
    bottom: tuple[str, str, Colour]


def border_of(raw: object) -> tuple[str, str, Colour]:
    assert isinstance(raw, list), raw
    return (str(raw[0]), str(raw[1]), to_colour(raw[2]))


def replay_cells(page: Page) -> list[ReplayCell]:
    """Every cell of `ops-replay-grid`, letter cells and blocks."""
    found = page.get_by_test_id("ops-replay-grid").evaluate(REPLAY_CELLS_SCRIPT)
    assert isinstance(found, list), found
    cells: list[ReplayCell] = []
    for item in found:
        assert isinstance(item, dict), item
        cells.append(
            ReplayCell(
                test_id=str(item["testId"]),
                row=item["row"],
                column=item["column"],
                kind=item["type"],
                box=to_box(item["box"]),
                text=str(item["text"]),
                background=to_colour(item["background"]),
                right=border_of(item["right"]),
                bottom=border_of(item["bottom"]),
            )
        )
    return cells


def notches_in(cell: Locator) -> list[tuple[bool, Box]]:
    """The revealed notches of a cell: whether each is `aria-hidden`, its box."""
    found = cell.evaluate(NOTCHES_SCRIPT)
    assert isinstance(found, list), found
    notches: list[tuple[bool, Box]] = []
    for item in found:
        assert isinstance(item, dict), item
        notches.append((item["hidden"] is True, to_box(item["box"])))
    return notches


def cell_side_problems(page: Page, side: float) -> list[str]:
    """Every cell of the replay's grid is `side` by `side` px (0.5 px)."""
    cells = replay_cells(page)
    if len(cells) == 0:
        return ["the replay's grid has no cell"]
    problems: list[str] = []
    for cell in cells:
        box = cell.box
        if not same_size(box.width, side) or not same_size(box.height, side):
            problems.append(f"a cell {box.width} by {box.height}, not {side}")
            break
    return problems


def grid_position(box: Box, origin: Box, side: float) -> tuple[int, int]:
    """A cell's (row, column) from its box (see the readings above)."""
    row = round((box.top - origin.top) / side)
    column = round((box.left - origin.left) / side)
    return (row, column)
