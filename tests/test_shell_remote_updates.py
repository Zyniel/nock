"""Tests of shell AC-22 to AC-25 and AC-28: a remote update redraws only its cells.

`client/shell.md` rule 18: once the room shows, a frame mutates no node of the
grid outside the cells whose drawing it changes; a pinch mutates no cell. These
tests count mutations; the pace of rule 18 (AC-26, AC-27) is measured in
`test_shell_remote_pace.py`.

Setup: spec 042's mocked room on FX-01 (`spec042_harness.open_room`, Ana `p1`
with colour 0, Bob `p2` with colour 1) in the default 1280 by 720 window; AC-25
in spec 024's touch phone context of 360 by 740 (`spec019_harness.new_context`),
pinched through CDP with spec 006's `pinch`; AC-28 on spec 034's mocked socket
and catch-up route, as the tests of `social/catch-up.md` AC-11 set it up.

How the mutations are counted:

- A `MutationObserver` on the grid (`[data-testid="grid"]`) with `childList`,
  `attributes`, `characterData` and `subtree`. It starts once the state of the
  criterion is set up (the room's first draw, and in AC-28 the reconnection's
  snapshot, are not counted), and the recording starts only once the grid has
  been quiet for 300 ms, so a refit still running from the setup is not counted
  either; a grid that never goes quiet within 5 s fails the test.
- Each mutation is given the place it changed: the cell (`"row,column"`) that
  holds its target, a text node by its parent. A `childList` change whose
  target is outside every cell (a row adding or removing a cell) is given the
  places of the nodes it added or removed, so a cell replaced whole counts as a
  change of that cell; any other change outside the cells is `"outside"`. A
  grid element replaced by another counts as `"grid-replaced"`.
- "Mutates no node of the grid": no mutation at all, the grid element's own
  attributes included. "No node outside (1, 2)": every mutation's places are
  (1, 2). "No cell" (AC-25): every mutation's places are `"outside"` (the grid's
  own `--cell` may change).
- A change of drawing has to show in its cell, so where a criterion names the
  cells a frame changes, the test also checks that each of them did mutate:
  that proves the observer saw the frame.

When a frame has been applied: `chat_message`, `letter_changed` and the catch-up
show on the page (`data-seq`, `data-letter`, `data-caught-up`); a `pong` and a
`selection_moved` that change nothing are sent before the `chat_message`, on the
same socket, so they are applied once it is. Then the test waits 300 ms (the
frames' drawing is synchronous; the wait lets any later task run) before it
reads the mutations.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import ChatMessage, Direction, LetterChanged, PlayerView, Pong
from spec006_harness import pinch
from spec019_harness import MockRoomSocket, new_context
from spec034_harness import (
    CatchUpRoute,
    catch_up_json,
    open_mocked_room,
    reconnect_with_snapshot,
    request_body,
)
from spec042_harness import (
    QUIET_MS,
    WAIT_TIMEOUT_MS,
    box_problems,
    cell_at,
    expect_seq,
    fx01_view,
    me,
    open_room,
    player,
    read_cursors,
    selecting,
    selection_frame,
    to_box,
    triangle_side,
)

# ---- Values of the criteria ------------------------------------------------------

BOB = "p2"
BOB_COLOUR = 1
SNAPSHOT_SEQ = 5
CATCH_UP_SNAPSHOT_SEQ = 9
PINCH_START_DISTANCE = 100.0
PINCH_END_DISTANCE = 150.0  # zoom 1 times 150 / 100
ZOOM_AFTER_PINCH = "1.5"

# FX-01's words of AC-24: TAMIS across row 1, MIME down column 2.
TAMIS = [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)]
MIME = [(1, 2), (2, 2), (3, 2), (4, 2)]

# ---- Values of the test harness --------------------------------------------------

PHONE_WIDTH = 360
PHONE_HEIGHT = 740
FLASH_TIMEOUT_MS = 5_000  # the flash lasts 1 s (`gameplay/co-op.md`)
RING_TIMEOUT_MS = 10_000  # the ring lasts 5 s (`social/catch-up.md` rule 14)
OUTSIDE = "outside"

# ---- The grid's mutation recorder ------------------------------------------------

START_RECORDING_SCRIPT = r"""
() => {
  const grid = document.querySelector('[data-testid="grid"]');
  const placeOf = (node) => {
    const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    if (element === null) {
      return 'detached';
    }
    const cell = element.closest('[data-testid="cell"]');
    if (cell === null) {
      return 'outside';
    }
    return cell.getAttribute('data-row') + ',' + cell.getAttribute('data-column');
  };
  const nameOf = (node) => {
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return '#text';
    }
    return node.getAttribute('data-testid') ?? node.tagName.toLowerCase();
  };
  const records = [];
  const keep = (list) => {
    for (const record of list) {
      const places = [];
      const targetPlace = placeOf(record.target);
      if (record.type === 'childList' && targetPlace === 'outside') {
        for (const node of [...record.addedNodes, ...record.removedNodes]) {
          places.push(placeOf(node));
        }
      }
      if (places.length === 0) {
        places.push(targetPlace);
      }
      records.push({
        kind: record.type,
        attribute: record.attributeName,
        target: nameOf(record.target),
        places: places,
      });
    }
  };
  const observer = new MutationObserver(keep);
  observer.observe(grid, {
    childList: true,
    attributes: true,
    characterData: true,
    subtree: true,
  });
  window.__shellGridMutations = {grid, observer, records, keep};
}
"""

# Returns the mutations recorded since the last call, and forgets them.
TAKE_MUTATIONS_SCRIPT = r"""
() => {
  const recorder = window.__shellGridMutations;
  recorder.keep(recorder.observer.takeRecords());
  const taken = recorder.records.splice(0);
  if (document.querySelector('[data-testid="grid"]') !== recorder.grid) {
    taken.push({
      kind: 'childList', attribute: null, target: 'grid', places: ['grid-replaced'],
    });
  }
  return taken;
}
"""


class GridMutation(NamedTuple):
    """One mutation of the grid: its kind, attribute, target and the places it hit."""

    kind: str  # childList, attributes or characterData
    attribute: str | None
    target: str  # the target's test id, else its tag; "#text" for a text node
    places: tuple[str, ...]  # "row,column", "outside", "detached", "grid-replaced"


def place(row: int, column: int) -> str:
    """The place of a cell in a mutation's places."""
    return f"{row},{column}"


def take_mutations(page: Page) -> list[GridMutation]:
    """The grid's mutations recorded since the last call; they are then forgotten."""
    raw = page.evaluate(TAKE_MUTATIONS_SCRIPT)
    assert isinstance(raw, list), raw
    mutations: list[GridMutation] = []
    for item in raw:
        mutations.append(
            GridMutation(
                kind=str(item["kind"]),
                attribute=item["attribute"],
                target=str(item["target"]),
                places=tuple(str(found) for found in item["places"]),
            )
        )
    return mutations


def start_recording(page: Page) -> None:
    """Observe the grid, then forget what changed until it has been quiet 300 ms."""
    page.evaluate(START_RECORDING_SCRIPT)
    waited_ms = 0
    while True:
        page.wait_for_timeout(QUIET_MS)
        waited_ms += QUIET_MS
        if take_mutations(page) == []:
            return
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail(f"the grid still changed {waited_ms} ms after the setup")


def mutations_after_settling(page: Page) -> list[GridMutation]:
    """Wait 300 ms, then take the mutations recorded so far."""
    page.wait_for_timeout(QUIET_MS)
    return take_mutations(page)


def mutated_places(mutations: list[GridMutation]) -> set[str]:
    """Every place the mutations hit."""
    places: set[str] = set()
    for mutation in mutations:
        places.update(mutation.places)
    return places


def mutations_outside(
    mutations: list[GridMutation], allowed: set[str]
) -> list[GridMutation]:
    """The mutations that hit a place not in `allowed`."""
    found: list[GridMutation] = []
    for mutation in mutations:
        for hit in mutation.places:
            if hit not in allowed:
                found.append(mutation)
                break
    return found


def places_of(cells: list[tuple[int, int]]) -> set[str]:
    """The places of cells, as a mutation's places name them.

    Args:
        cells: The (row, column) of each cell.

    Returns:
        Each cell's place, `"row,column"`.
    """
    return {place(row, column) for row, column in cells}


# ---- Fixtures and setup ----------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    """Return the FX-01 reference grid (5 by 5)."""
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def phone_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A page of a 360 by 740 touch phone (spec 024's touch context)."""
    context = new_context(browser, browser_name, PHONE_WIDTH, PHONE_HEIGHT, True)
    try:
        yield context.new_page()
    finally:
        context.close()


def ana_and_bob(row: int, column: int, direction: Direction) -> list[PlayerView]:
    """Ana (`you`) and Bob, whose cursor is on (row, column) in `direction`."""
    bob = player(BOB, BOB_COLOUR, selection=selecting(row, column, direction))
    return [me(), bob]


def bob_cursor(page: Page, row: int, column: int) -> Locator:
    """Bob's `remote-selection` in a cell (none when his cursor is elsewhere)."""
    return cell_at(page, row, column).locator(
        f'[data-testid="remote-selection"][data-player-id="{BOB}"]'
    )


def open_with_bob_on(
    page: Page, base_url: str, grid: Grid, row: int, column: int
) -> MockRoomSocket:
    """Open FX-01 with Bob's cursor on (row, column) across, and wait for it."""
    players = ana_and_bob(row, column, Direction.ACROSS)
    mock = open_room(page, base_url, fx01_view(grid), players, seq=SNAPSHOT_SEQ)
    expect(bob_cursor(page, row, column)).to_have_count(1)
    return mock


def bob_letter_frame(seq: int, row: int, column: int, letter: str) -> str:
    """A confirmed `letter_changed` of Bob."""
    event = LetterChanged(
        seq=seq, row=row, column=column, letter=letter, pencil=False, player_id=BOB
    )
    return event.model_dump_json()


# ---- AC-22: a frame that changes no cell mutates nothing -------------------------


def test_ac22_a_pong_a_chat_message_and_a_selection_in_place_mutate_no_node(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_bob_on(page, live_server, fx01_grid, 1, 1)
    start_recording(page)

    mock.send(Pong().model_dump_json())
    mock.send(selection_frame(BOB, 1, 1, Direction.ACROSS))
    chat = ChatMessage(seq=SNAPSHOT_SEQ + 1, player_id=BOB, text="Salut")
    mock.send(chat.model_dump_json())
    expect_seq(page, SNAPSHOT_SEQ + 1)

    assert mutations_after_settling(page) == []
    expect(bob_cursor(page, 1, 1)).to_have_count(1)


# ---- AC-23: a letter change mutates only its cell, its flash included ------------


def test_ac23_bobs_letter_in_an_empty_cell_mutates_only_that_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [me(), player(BOB, BOB_COLOUR)]
    mock = open_room(page, live_server, fx01_view(fx01_grid), players)
    start_recording(page)

    mock.send(bob_letter_frame(SNAPSHOT_SEQ + 1, 1, 2, "M"))
    expect(cell_at(page, 1, 2)).to_have_attribute("data-letter", "M")

    mutations = mutations_after_settling(page)
    assert mutations_outside(mutations, {place(1, 2)}) == []
    assert mutated_places(mutations) == {place(1, 2)}


def test_ac23_bobs_letter_over_mine_mutates_only_that_cell_through_its_flash(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    view = fx01_view(fx01_grid, [(1, 2, {"letter": "M", "author": "p1"})])
    players = [me(), player(BOB, BOB_COLOUR)]
    mock = open_room(page, live_server, view, players)
    flash = cell_at(page, 1, 2).get_by_test_id("cell-flash")
    start_recording(page)

    mock.send(bob_letter_frame(SNAPSHOT_SEQ + 1, 1, 2, "X"))
    expect(flash).to_have_count(1)
    expect(cell_at(page, 1, 2)).to_have_attribute("data-letter", "X")
    expect(flash).to_have_count(0, timeout=FLASH_TIMEOUT_MS)

    mutations = mutations_after_settling(page)
    assert mutations_outside(mutations, {place(1, 2)}) == []
    assert mutated_places(mutations) == {place(1, 2)}


# ---- AC-24: a cursor's move mutates the cells it and its tint leave and enter ----


def test_ac24_bobs_cursor_moving_along_his_word_mutates_only_the_two_cells(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_bob_on(page, live_server, fx01_grid, 1, 1)
    start_recording(page)

    mock.send(selection_frame(BOB, 1, 2, Direction.ACROSS))
    expect(bob_cursor(page, 1, 2)).to_have_count(1)
    expect(bob_cursor(page, 1, 1)).to_have_count(0)

    mutations = mutations_after_settling(page)
    two_cells = {place(1, 1), place(1, 2)}
    assert mutations_outside(mutations, two_cells) == []
    assert mutated_places(mutations) == two_cells


def test_ac24_bob_turning_down_mutates_only_the_cells_of_tamis_and_mime(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_bob_on(page, live_server, fx01_grid, 1, 1)
    mock.send(selection_frame(BOB, 1, 2, Direction.ACROSS))
    expect(bob_cursor(page, 1, 2)).to_have_count(1)
    start_recording(page)

    mock.send(selection_frame(BOB, 1, 2, Direction.DOWN))
    expect(cell_at(page, 4, 2)).to_have_attribute("data-tinted-by", BOB)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-tinted-by", "")

    mutations = mutations_after_settling(page)
    assert mutations_outside(mutations, places_of(TAMIS + MIME)) == []
    expect(bob_cursor(page, 1, 2)).to_have_count(1)


# ---- AC-25: a pinch mutates no cell, and the triangles follow the new side -------


@pytest.mark.only_browser("chromium")
def test_ac25_a_pinch_from_zoom_1_to_1_5_mutates_no_cell(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_bob_on(phone_page, live_server, fx01_grid, 1, 1)
    viewport = phone_page.get_by_test_id("grid-viewport")
    expect(viewport).to_have_attribute("data-zoom", "1")
    start_recording(phone_page)

    pinch(phone_page, viewport, PINCH_START_DISTANCE, PINCH_END_DISTANCE)
    expect(viewport).to_have_attribute("data-zoom", ZOOM_AFTER_PINCH)

    mutations = mutations_after_settling(phone_page)
    assert mutations_outside(mutations, {OUTSIDE}) == []


@pytest.mark.only_browser("chromium")
def test_ac25_after_the_pinch_bobs_triangle_has_the_leg_of_the_new_side(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_bob_on(phone_page, live_server, fx01_grid, 1, 1)
    viewport = phone_page.get_by_test_id("grid-viewport")
    side_before = read_cursors(phone_page, 1, 1)[0].width

    pinch(phone_page, viewport, PINCH_START_DISTANCE, PINCH_END_DISTANCE)
    expect(viewport).to_have_attribute("data-zoom", ZOOM_AFTER_PINCH)
    phone_page.wait_for_timeout(QUIET_MS)

    cell_box, cursors = read_cursors(phone_page, 1, 1)
    assert cell_box.width > side_before
    assert [cursor["playerId"] for cursor in cursors] == [BOB]
    leg = triangle_side(cell_box.width)
    cursor_box = to_box(cursors[0]["box"])
    assert box_problems("Bob's triangle", cursor_box, width=leg, height=leg) == []


# ---- AC-28: a catch-up ring mutates only its cell, from its start to its end -----


def test_ac28_a_catch_up_naming_one_cell_mutates_only_it_until_its_ring_ends(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    record = {"grid": 1, "selection": None}
    mock = open_mocked_room(
        page, live_server, fx01_grid, route, record=record, seq=SNAPSHOT_SEQ
    )
    reconnect_with_snapshot(mock, fx01_grid, CATCH_UP_SNAPSHOT_SEQ)
    route.wait_for_requests(page, 1)
    assert route.parsed_bodies() == [request_body(SNAPSHOT_SEQ, CATCH_UP_SNAPSHOT_SEQ)]
    start_recording(page)

    answer = catch_up_json(SNAPSHOT_SEQ, CATCH_UP_SNAPSHOT_SEQ, cells=[(1, 2)])
    route.answer_json(0, answer)
    ringed = cell_at(page, 1, 2)
    expect(ringed).to_have_attribute("data-caught-up", "true")
    expect(ringed).to_have_attribute("data-caught-up", "false", timeout=RING_TIMEOUT_MS)

    mutations = mutations_after_settling(page)
    assert mutations_outside(mutations, {place(1, 2)}) == []
    assert mutated_places(mutations) == {place(1, 2)}
