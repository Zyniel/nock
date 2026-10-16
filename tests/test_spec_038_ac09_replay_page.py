"""Tests of spec 038 (privacy and operations), AC-9: the ops page replays a room.

The live server is the one of the spec's "Test harness" (a file database and
`operator_token=OPS_TOKEN`, `ops_live_server` of `spec038_harness`). A page enters
a FX-01 room as `Ana` (spec 011's `enter_room`), types `T`, `A`, `M`, `I`, `S` from
(1, 0) across, then taps (1, 4) and presses `Backspace`. The ops page runs in
another context, with `timezone_id="Europe/Paris"`, and gets the token through its
form. Its texts are built from `fr.json`: the time is the spec's
`Intl.DateTimeFormat("fr-FR", ...)` of each edit's `at`, computed in the ops page
from the time the page received, and the name is `Ana`, how spec 040's
`displayNickname` shows the stored `ANA`. The criterion's own texts (`Étape 6 sur
6`, `Étape 0 sur 6`) are written as it writes them.

Edge cases checked as well, from "Client: the ops page" and "Edge cases and
errors": every kind of edit and its text, a player with no `player_joined`
(`feed.someone`), the grid after locks and an undo, a lowercase code (sent in
upper case), a code that breaks the pattern, a room with no edit, and a long
replay whose every edit is listed. Rooms other than the played one are written to
the live server's store by hand (`seed_room`).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, Protocol

import pytest
from playwright.sync_api import Browser, BrowserContext, Locator, Page, expect

from nock.grid import Grid, LetterCell
from nock.protocol import LetterChanged
from nock.room import new_room
from nock.store import RoomStore
from spec010_harness import catalogue_from_grid
from spec038_harness import (
    FX01_LETTER_CELLS,
    PARIS,
    Log,
    OpsServer,
    attributes_of,
    cell_at,
    edits_path,
    fill,
    load_fr,
    open_dashboard,
    ops_live_server,
    seed_room,
    texts_of,
    type_across,
)

# ---- Values of the spec --------------------------------------------------------------

ANA_SHOWN = "Ana"  # how displayNickname shows the stored ANA
STEP_6_OF_6 = "\N{LATIN CAPITAL LETTER E WITH ACUTE}tape 6 sur 6"
STEP_0_OF_6 = "\N{LATIN CAPITAL LETTER E WITH ACUTE}tape 0 sur 6"

# ---- Values of the test harness ------------------------------------------------------

REPLAY_TIMEOUT_MS = 10_000
LOG_WAIT_SECONDS = 10.0
UNKNOWN_ROOM = "ZZZZZZ"
SEEDED_ROOM = "SEED23"
EMPTY_ROOM = "EMPTY4"
LONG_ROOM = "LONG56"
LONG_REPLAY_EDITS = 60

Cell = tuple[int, int]

# Formats a time as the spec's `time`, in the page's own time zone.
TIME_SCRIPT = """
(milliseconds) => new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit", minute: "2-digit", second: "2-digit",
}).format(new Date(milliseconds))
"""


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


# ---- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def server(tmp_path: Path, fx01_grid: Grid) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue_from_grid(fx01_grid)) as running:
        yield running


@pytest.fixture
def new_ops_page(browser: Browser) -> Iterator[Callable[[], Page]]:
    """Yield `new_ops_page()`: a page in a context of its own, in Paris time."""
    contexts: list[BrowserContext] = []

    def make_page() -> Page:
        context = browser.new_context(timezone_id=PARIS)
        contexts.append(context)
        return context.new_page()

    yield make_page
    for context in contexts:
        context.close()


# ---- Helpers -------------------------------------------------------------------------


def letter_cells(grid: Grid) -> list[Cell]:
    """The (row, column) of each letter cell of the grid, in its order."""
    cells: list[Cell] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            cells.append((cell.row, cell.column))
    return cells


def wait_for_letter_entries(store: RoomStore, code: str, count: int) -> None:
    """Wait until the room's log holds `count` letter_changed entries."""
    deadline = time.monotonic() + LOG_WAIT_SECONDS
    while True:
        found = 0
        for entry in store.read_log(code):
            if isinstance(entry.event, LetterChanged):
                found += 1
        if found >= count:
            return
        if time.monotonic() >= deadline:
            pytest.fail(f"the log holds {found} letter_changed, not {count}")
        time.sleep(0.05)


def cell_in_replay(page: Page, row: int, column: int) -> Locator:
    """One cell of the replay's grid."""
    selector = (
        f'[data-testid="ops-replay-cell"][data-row="{row}"][data-column="{column}"]'
    )
    return page.locator(selector)


def ask_for_replay(
    page: Page, typed_code: str, sent_code: str
) -> list[dict[str, object]]:
    """Type a code in the replay form, submit it, and return the edits received.

    Waits for the page's request of `/api/ops/rooms/<sent_code>/edits`, and
    returns the `edits` of its JSON answer.
    """
    page.get_by_test_id("ops-replay-code").fill(typed_code)
    with page.expect_response(
        lambda response: edits_path(sent_code) in response.url,
        timeout=REPLAY_TIMEOUT_MS,
    ) as caught:
        page.get_by_test_id("ops-replay-submit").click()
    body = caught.value.json()
    assert isinstance(body, dict), body
    edits = body["edits"]
    assert isinstance(edits, list), body
    return edits


def expect_replay_state(page: Page, state: str) -> None:
    expect(page.get_by_test_id("ops-replay")).to_have_attribute(
        "data-state", state, timeout=REPLAY_TIMEOUT_MS
    )


def time_text(page: Page, at: object) -> str:
    """The spec's `time` of an edit's `at` (as received), formatted in `page`."""
    assert isinstance(at, str), at
    milliseconds = datetime.fromisoformat(at).timestamp() * 1000
    shown = page.evaluate(TIME_SCRIPT, milliseconds)
    assert isinstance(shown, str), shown
    return shown


def edit_text(page: Page, received: dict[str, object], name: str) -> str:
    """The text of one edit: `t("ops.edit.<kind>", {time, name, letter, row, column})`.

    A typed letter in pencil uses `ops.edit.typed_pencil`.
    """
    fr = load_fr()
    kind = str(received["kind"])
    key = f"ops.edit.{kind}"
    if kind == "typed" and received["pencil"] is True:
        key = "ops.edit.typed_pencil"
    letter = received["letter"]
    values = {
        "time": time_text(page, received["at"]),
        "name": name,
        "letter": "" if letter is None else str(letter),
        "row": str(received["row"]),
        "column": str(received["column"]),
    }
    return fill(fr[key], values)


def shown_cells(page: Page) -> dict[Cell, tuple[str | None, str]]:
    """Each replay cell's `data-letter` and text, by (row, column)."""
    cells = page.get_by_test_id("ops-replay-cell")
    rows = attributes_of(cells, "data-row")
    columns = attributes_of(cells, "data-column")
    letters = attributes_of(cells, "data-letter")
    texts = texts_of(cells)
    shown: dict[Cell, tuple[str | None, str]] = {}
    for index in range(len(texts)):
        row = rows[index]
        column = columns[index]
        assert row is not None, "a replay cell has no data-row"
        assert column is not None, "a replay cell has no data-column"
        shown[(int(row), int(column))] = (letters[index], texts[index])
    return shown


def expected_cells(grid: Grid, letters: dict[Cell, str]) -> dict[Cell, tuple[str, str]]:
    """Every letter cell with its letter (as `data-letter` and as text), else ""."""
    expected: dict[Cell, tuple[str, str]] = {}
    for cell in letter_cells(grid):
        letter = letters.get(cell, "")
        expected[cell] = (letter, letter)
    return expected


# ---- The criterion's run -------------------------------------------------------------


class ReplayRun(NamedTuple):
    """The ops page once the played room's replay is `ready`, and what it got."""

    ops: Page
    ana_id: str
    received: list[dict[str, object]]


def play_then_replay(
    page: Page,
    new_ops_page: Callable[[], Page],
    server: OpsServer,
    grid: Grid,
    enter_room: EnterRoom,
) -> ReplayRun:
    """Ana types TAMIS from (1, 0) and erases (1, 4); the ops page replays it."""
    code = server.registry.register_room(grid)
    enter_room(page, f"{server.base_url}/r/{code}", "Ana")
    ana_id = page.get_by_test_id("room-page").get_attribute("data-you")
    assert ana_id, "the room page shows no data-you"
    type_across(page, 1, 0, "tamis")
    cell_at(page, 1, 4).click()
    page.keyboard.press("Backspace")
    wait_for_letter_entries(server.store, code, 6)

    ops = new_ops_page()
    open_dashboard(ops, server.base_url)
    received = ask_for_replay(ops, code, code)
    expect_replay_state(ops, "ready")
    return ReplayRun(ops=ops, ana_id=ana_id, received=received)


# ---- AC-9: the replay of the played room ---------------------------------------------


def test_ac9_the_replay_lists_five_typed_letters_then_the_erase_in_seq_order(
    page: Page,
    new_ops_page: Callable[[], Page],
    server: OpsServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    run = play_then_replay(page, new_ops_page, server, fx01_grid, enter_room)
    edits = run.ops.get_by_test_id("ops-edit")

    expect(edits).to_have_count(6)
    received_seqs = [str(received["seq"]) for received in run.received]
    received_times = [str(received["at"]) for received in run.received]
    assert attributes_of(edits, "data-seq") == received_seqs
    assert [int(seq) for seq in received_seqs] == sorted(
        int(seq) for seq in received_seqs
    )
    assert attributes_of(edits, "data-kind") == ["typed"] * 5 + ["erased"]
    assert attributes_of(edits, "data-letter") == ["T", "A", "M", "I", "S", ""]
    assert attributes_of(edits, "data-row") == ["1"] * 6
    assert attributes_of(edits, "data-column") == ["0", "1", "2", "3", "4", "4"]
    assert attributes_of(edits, "data-player-id") == [run.ana_id] * 6
    assert attributes_of(edits, "data-at") == received_times


def test_ac9_each_edit_text_is_built_from_fr_json_with_ana(
    page: Page,
    new_ops_page: Callable[[], Page],
    server: OpsServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    run = play_then_replay(page, new_ops_page, server, fx01_grid, enter_room)

    expected: list[str] = []
    for received in run.received:
        expected.append(edit_text(run.ops, received, ANA_SHOWN))
    assert texts_of(run.ops.get_by_test_id("ops-edit")) == expected


def test_ac9_the_replay_starts_at_step_6_of_6_with_t_a_m_i_on_row_1(
    page: Page,
    new_ops_page: Callable[[], Page],
    server: OpsServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    run = play_then_replay(page, new_ops_page, server, fx01_grid, enter_room)
    position = run.ops.get_by_test_id("ops-replay-position")

    expect(position).to_have_value("6")
    expect(position).to_have_attribute("type", "range")
    expect(position).to_have_attribute("min", "0")
    expect(position).to_have_attribute("max", "6")
    expect(position).to_have_attribute("step", "1")
    expect(run.ops.get_by_test_id("ops-replay-step")).to_have_text(STEP_6_OF_6)
    expect(run.ops.get_by_test_id("ops-replay-cell")).to_have_count(FX01_LETTER_CELLS)
    letters = {(1, 0): "T", (1, 1): "A", (1, 2): "M", (1, 3): "I"}
    assert shown_cells(run.ops) == expected_cells(fx01_grid, letters)


def test_ac9_position_5_shows_s_and_position_0_empties_the_grid(
    page: Page,
    new_ops_page: Callable[[], Page],
    server: OpsServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    run = play_then_replay(page, new_ops_page, server, fx01_grid, enter_room)
    position = run.ops.get_by_test_id("ops-replay-position")
    step = run.ops.get_by_test_id("ops-replay-step")

    position.fill("5")
    expect(cell_in_replay(run.ops, 1, 4)).to_have_attribute("data-letter", "S")
    at_five = shown_cells(run.ops)
    position.fill("0")
    expect(step).to_have_text(STEP_0_OF_6)
    at_zero = shown_cells(run.ops)

    tamis = {(1, 0): "T", (1, 1): "A", (1, 2): "M", (1, 3): "I", (1, 4): "S"}
    assert at_five == expected_cells(fx01_grid, tamis)
    assert at_zero == expected_cells(fx01_grid, {})


# ---- AC-9: codes with no room --------------------------------------------------------


def test_ac9_a_code_with_no_room_shows_not_found(
    new_ops_page: Callable[[], Page], server: OpsServer
) -> None:
    ops = new_ops_page()
    open_dashboard(ops, server.base_url)

    ask_for_replay(ops, UNKNOWN_ROOM, UNKNOWN_ROOM)

    expect_replay_state(ops, "not_found")
    expect(ops.get_by_test_id("ops-replay")).to_contain_text(
        load_fr()["ops.replay_not_found"]
    )
    expect(ops.get_by_test_id("ops-edit")).to_have_count(0)


def test_ac9_a_code_breaking_the_pattern_shows_not_found(
    new_ops_page: Callable[[], Page], server: OpsServer
) -> None:
    ops = new_ops_page()
    open_dashboard(ops, server.base_url)

    ask_for_replay(ops, "abc", "ABC")

    expect_replay_state(ops, "not_found")
    expect(ops.get_by_test_id("ops-replay")).to_contain_text(
        load_fr()["ops.replay_not_found"]
    )


# ---- AC-9: rooms written by hand -----------------------------------------------------


def seeded_log(start: float) -> Log:
    """Every kind of edit, and a letter of a player who never joined (p9)."""
    log = Log(start)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.letter("p1", 1, 0, "T")
    log.letter("p1", 1, 1, "A", pencil=True)
    log.letter("p1", 1, 0, None)
    log.letter("p1", 1, 0, "T", undo=True)
    log.lock(1, 1, "A", revealed=False)
    log.lock(1, 2, "M", revealed=True)
    log.letter("p9", 1, 3, "I")
    return log


def test_ac9_every_kind_of_edit_has_its_text(
    new_ops_page: Callable[[], Page], server: OpsServer, fx01_grid: Grid
) -> None:
    now = time.time()
    log = seeded_log(now)
    seed_room(server.registry, new_room(SEEDED_ROOM, fx01_grid, now), log.entries)
    ops = new_ops_page()
    open_dashboard(ops, server.base_url)

    received = ask_for_replay(ops, SEEDED_ROOM, SEEDED_ROOM)
    expect_replay_state(ops, "ready")

    someone = load_fr()["feed.someone"]
    names = [ANA_SHOWN] * 4 + ["", "", someone]
    expected: list[str] = []
    for index, edit in enumerate(received):
        expected.append(edit_text(ops, edit, names[index]))
    edits = ops.get_by_test_id("ops-edit")
    kinds = ["typed", "typed", "erased", "undone", "locked", "revealed", "typed"]
    assert attributes_of(edits, "data-kind") == kinds
    assert attributes_of(edits, "data-player-id") == ["p1"] * 4 + ["", "", "p9"]
    assert attributes_of(edits, "data-letter") == ["T", "A", "", "T", "A", "M", "I"]
    assert texts_of(edits) == expected


def test_ac9_the_grid_shows_the_letter_of_the_last_edit_of_each_cell(
    new_ops_page: Callable[[], Page], server: OpsServer, fx01_grid: Grid
) -> None:
    now = time.time()
    log = seeded_log(now)
    seed_room(server.registry, new_room(SEEDED_ROOM, fx01_grid, now), log.entries)
    ops = new_ops_page()
    open_dashboard(ops, server.base_url)
    ask_for_replay(ops, SEEDED_ROOM, SEEDED_ROOM)
    expect_replay_state(ops, "ready")
    position = ops.get_by_test_id("ops-replay-position")

    at_seven = shown_cells(ops)
    position.fill("3")  # T, A in pencil, then the erase of (1, 0)
    expect(cell_in_replay(ops, 1, 0)).to_have_attribute("data-letter", "")
    at_three = shown_cells(ops)

    all_seven = {(1, 0): "T", (1, 1): "A", (1, 2): "M", (1, 3): "I"}
    assert at_seven == expected_cells(fx01_grid, all_seven)
    assert at_three == expected_cells(fx01_grid, {(1, 1): "A"})


def test_ac9_a_lowercase_code_is_sent_in_upper_case(
    new_ops_page: Callable[[], Page], server: OpsServer, fx01_grid: Grid
) -> None:
    now = time.time()
    log = seeded_log(now)
    seed_room(server.registry, new_room(SEEDED_ROOM, fx01_grid, now), log.entries)
    ops = new_ops_page()
    open_dashboard(ops, server.base_url)

    received = ask_for_replay(ops, SEEDED_ROOM.lower(), SEEDED_ROOM)

    expect_replay_state(ops, "ready")
    assert len(received) == 7
    expect(ops.get_by_test_id("ops-edit")).to_have_count(7)


def test_ac9_a_room_with_no_edit_shows_the_empty_text(
    new_ops_page: Callable[[], Page], server: OpsServer, fx01_grid: Grid
) -> None:
    server.registry.add_room(new_room(EMPTY_ROOM, fx01_grid, time.time()))
    ops = new_ops_page()
    open_dashboard(ops, server.base_url)

    received = ask_for_replay(ops, EMPTY_ROOM, EMPTY_ROOM)

    expect_replay_state(ops, "ready")
    assert received == []
    expect(ops.get_by_test_id("ops-edit")).to_have_count(0)
    expect(ops.get_by_test_id("ops-replay")).to_contain_text(
        load_fr()["ops.replay_empty"]
    )


def test_ac9_every_edit_of_a_long_replay_is_listed(
    new_ops_page: Callable[[], Page], server: OpsServer, fx01_grid: Grid
) -> None:
    now = time.time()
    log = Log(now)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    cells = letter_cells(fx01_grid)
    for index in range(LONG_REPLAY_EDITS):
        row, column = cells[index % len(cells)]
        log.letter("p1", row, column, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[index % 26])
    seed_room(server.registry, new_room(LONG_ROOM, fx01_grid, now), log.entries)
    ops = new_ops_page()
    open_dashboard(ops, server.base_url)

    ask_for_replay(ops, LONG_ROOM, LONG_ROOM)

    expect_replay_state(ops, "ready")
    expect(ops.get_by_test_id("ops-edit")).to_have_count(LONG_REPLAY_EDITS)
    expect(ops.get_by_test_id("ops-replay-position")).to_have_value(
        str(LONG_REPLAY_EDITS)
    )


def test_ac9_the_replay_texts_and_labels_come_from_fr_json(
    new_ops_page: Callable[[], Page], server: OpsServer, fx01_grid: Grid
) -> None:
    now = time.time()
    log = seeded_log(now)
    seed_room(server.registry, new_room(SEEDED_ROOM, fx01_grid, now), log.entries)
    fr = load_fr()
    ops = new_ops_page()
    open_dashboard(ops, server.base_url)

    expect(ops.get_by_role("heading", name=fr["ops.replay_heading"])).to_be_visible()
    expect(ops.get_by_label(fr["ops.replay_code_label"], exact=True)).to_have_attribute(
        "data-testid", "ops-replay-code"
    )
    expect(ops.get_by_test_id("ops-replay-submit")).to_have_text(
        fr["ops.replay_submit"]
    )
    expect_replay_state(ops, "idle")
    ask_for_replay(ops, SEEDED_ROOM, SEEDED_ROOM)
    expect_replay_state(ops, "ready")
    expect(
        ops.get_by_label(fr["ops.replay_position_label"], exact=True)
    ).to_have_attribute("data-testid", "ops-replay-position")
    expect(ops.get_by_label(fr["ops.replay_grid_label"], exact=True)).to_have_attribute(
        "data-testid", "ops-replay-grid"
    )
