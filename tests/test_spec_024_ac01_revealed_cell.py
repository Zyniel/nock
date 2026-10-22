"""Tests of spec 024, AC-1: a revealed cell shows the right letter, is locked and
has no author, for every player.

The rule on `handle_message`, the real WebSocket, two browsers on the live server,
and the page with a mocked socket for a pending edit on a revealed cell. The edge
cases of AC-1 are here too: a right letter revealed all the same, a wrong letter's
strike cleared, undo and checks after a reveal, the feed line. The shared setup is
in `spec024_harness`.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, WebSocket, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellRef,
    CellTarget,
    Check,
    CheckResult,
    EditLetter,
    ErrorCode,
    ErrorMessage,
    LetterCellView,
    PlayerState,
    PlayerStateChanged,
    RevealBudget,
    RevealResult,
    Undo,
    WordTarget,
)
from nock.room import CellState, RoomConfig, handle_message, tick
from nock.server import create_app
from room_panels import open_aide
from spec024_harness import (
    MIME,
    NOW,
    SETTLE_MS,
    TAMIS,
    WAIT_TIMEOUT_MS,
    EnterRoom,
    accepted_reveal,
    cell_at,
    cell_locked_frame,
    cell_state,
    cell_view,
    check_cell,
    computed,
    events_of,
    grid_from_text,
    join_one,
    join_peers,
    load_fr,
    make_catalogue,
    make_dist_dir,
    make_registry,
    mark_problems,
    open_room,
    player_record,
    r1_room,
    refusal_code,
    reveal_result_frame,
    snapshot_cell,
    wait_until_page,
)

BOLD_WEIGHT = 700

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry whose throttle never refuses and that never times a socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


ONE_ONE = CellTarget(row=1, column=1)

# ---- AC-1, rule: a letter reveal ----


def test_ac1_revealing_a_letter_gives_the_result_then_one_lock(
    fx01_grid: Grid,
) -> None:
    outcome = accepted_reveal(r1_room(fx01_grid), ONE_ONE, "p1")

    assert events_of(outcome) == [
        RevealResult(
            seq=6,
            player_id="p1",
            target=ONE_ONE,
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=7, row=1, column=1, letter="A", revealed=True),
    ]


def test_ac1_the_revealed_cell_holds_its_solution_locked_without_author(
    fx01_grid: Grid,
) -> None:
    after = accepted_reveal(r1_room(fx01_grid), ONE_ONE, "p1").state

    assert after.seq == 7
    assert cell_state(after, 1, 1) == CellState(
        row=1,
        column=1,
        letter="A",
        pencil=False,
        author=None,
        locked=True,
        revealed=True,
        wrong=False,
        changed_seq=7,
        changed_by=None,
    )


def test_ac1_the_budget_left_drops_and_the_allowance_stays(fx01_grid: Grid) -> None:
    after = accepted_reveal(r1_room(fx01_grid), ONE_ONE, "p1").state

    assert after.reveal_budget == RevealBudget(letters=4, words=1)
    assert after.settings.reveal_budget == RevealBudget(letters=5, words=1)


def test_ac1_grid_state_shows_the_revealed_cell(fx01_grid: Grid) -> None:
    after = accepted_reveal(r1_room(fx01_grid), ONE_ONE, "p1").state

    assert cell_view(after, 1, 1) == LetterCellView(
        row=1,
        column=1,
        letter="A",
        pencil=False,
        author=None,
        locked=True,
        revealed=True,
        wrong=False,
    )


def test_ac1_the_other_cells_are_unchanged(fx01_grid: Grid) -> None:
    state = r1_room(fx01_grid)

    after = accepted_reveal(state, ONE_ONE, "p1").state

    for cell in state.cells:
        if (cell.row, cell.column) != (1, 1):
            assert cell_state(after, cell.row, cell.column) == cell


# ---- AC-1, rule: a word reveal ----


def test_ac1_revealing_a_word_locks_each_cell_in_reading_order(
    fx01_grid: Grid,
) -> None:
    first = accepted_reveal(r1_room(fx01_grid), ONE_ONE, "p1").state

    outcome = accepted_reveal(first, MIME, "p2")

    assert events_of(outcome) == [
        RevealResult(
            seq=8,
            player_id="p2",
            target=WordTarget(row=0, column=2, clue_index=0),
            reveal_budget=RevealBudget(letters=4, words=0),
        ),
        CellLocked(seq=9, row=1, column=2, letter="M", revealed=True),
        CellLocked(seq=10, row=2, column=2, letter="I", revealed=True),
        CellLocked(seq=11, row=3, column=2, letter="M", revealed=True),
        CellLocked(seq=12, row=4, column=2, letter="E", revealed=True),
    ]
    assert outcome.state.seq == 12


def test_ac1_a_revealed_word_cell_typed_by_a_player_loses_its_author(
    fx01_grid: Grid,
) -> None:
    first = accepted_reveal(r1_room(fx01_grid), ONE_ONE, "p1").state
    assert cell_state(first, 2, 2).author == "p2"

    after = accepted_reveal(first, MIME, "p2").state

    assert cell_state(after, 2, 2) == CellState(
        row=2,
        column=2,
        letter="I",
        pencil=False,
        author=None,
        locked=True,
        revealed=True,
        wrong=False,
        changed_seq=10,
        changed_by=None,
    )


def test_ac1_a_word_reveal_leaves_out_the_locked_cells(fx01_grid: Grid) -> None:
    checked = check_cell(r1_room(fx01_grid), 1, 0)
    assert checked.seq == 7
    assert cell_state(checked, 1, 0).locked is True

    outcome = accepted_reveal(checked, TAMIS, "p1")

    assert events_of(outcome) == [
        RevealResult(
            seq=8,
            player_id="p1",
            target=TAMIS,
            reveal_budget=RevealBudget(letters=5, words=0),
        ),
        CellLocked(seq=9, row=1, column=1, letter="A", revealed=True),
        CellLocked(seq=10, row=1, column=2, letter="M", revealed=True),
        CellLocked(seq=11, row=1, column=3, letter="I", revealed=True),
        CellLocked(seq=12, row=1, column=4, letter="S", revealed=True),
    ]
    kept = cell_state(outcome.state, 1, 0)
    assert (kept.revealed, kept.author, kept.letter) == (False, "p1", "T")


# ---- AC-1, rule: edge cases ----


def test_ac1_a_right_letter_is_revealed_all_the_same_and_costs_a_letter(
    fx01_grid: Grid,
) -> None:
    target = CellTarget(row=1, column=0)

    outcome = accepted_reveal(r1_room(fx01_grid), target, "p2")

    assert events_of(outcome) == [
        RevealResult(
            seq=6,
            player_id="p2",
            target=target,
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=7, row=1, column=0, letter="T", revealed=True),
    ]
    assert cell_state(outcome.state, 1, 0).author is None


def test_ac1_a_reveal_clears_the_strike_of_a_wrong_letter(fx01_grid: Grid) -> None:
    struck = check_cell(r1_room(fx01_grid), 1, 1)
    assert cell_state(struck, 1, 1).wrong is True

    after = accepted_reveal(struck, ONE_ONE, "p1").state

    revealed = cell_state(after, 1, 1)
    assert (revealed.letter, revealed.wrong, revealed.revealed) == ("A", False, True)


def test_ac1_undoing_an_edit_whose_cell_was_revealed_is_refused(
    fx01_grid: Grid,
) -> None:
    after = accepted_reveal(r1_room(fx01_grid), ONE_ONE, "p2").state

    outcome = handle_message(after, "p1", Undo(), NOW)

    assert refusal_code(outcome) is ErrorCode.NOTHING_TO_UNDO
    assert outcome.entries == ()
    assert cell_state(outcome.state, 1, 1).letter == "A"


def test_ac1_a_check_leaves_the_revealed_cell_out(fx01_grid: Grid) -> None:
    after = accepted_reveal(r1_room(fx01_grid), ONE_ONE, "p1").state

    outcome = handle_message(after, "p1", Check(target=TAMIS), NOW)

    assert events_of(outcome) == [
        CheckResult(
            seq=8,
            player_id="p1",
            target=TAMIS,
            correct=(CellRef(row=1, column=0),),
            wrong=(),
        ),
        CellLocked(seq=9, row=1, column=0, letter="T", revealed=False),
    ]


def test_ac1_a_reveal_is_input_that_wakes_an_idle_player_first(
    fx01_grid: Grid,
) -> None:
    quiet = RoomConfig(silence_timeout_seconds=3600)
    idle = tick(r1_room(fx01_grid), NOW + 120, quiet).state
    assert idle.seq == 7
    assert player_record(idle, "p1").state is PlayerState.IDLE

    outcome = accepted_reveal(idle, ONE_ONE, "p1", NOW + 130)

    assert events_of(outcome) == [
        PlayerStateChanged(seq=8, player_id="p1", state=PlayerState.ACTIVE),
        RevealResult(
            seq=9,
            player_id="p1",
            target=ONE_ONE,
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=10, row=1, column=1, letter="A", revealed=True),
    ]
    assert player_record(outcome.state, "p1").last_input_at == NOW + 130
    assert player_record(outcome.state, "p2").state is PlayerState.IDLE


# ---- AC-1, WebSocket ----

LETTER_REVEAL_TEXT = (
    '{"type": "reveal", "target": {"scope": "letter", "row": 1, "column": 1}}'
)


def test_ac1_websocket_both_players_get_the_result_then_the_lock(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        bob.send(EditLetter(row=1, column=1, letter="X"))
        for peer in (ana, bob):
            peer.wait_for_seq(3, f"Bob's letter on {peer.name}")

        ana.send_text(LETTER_REVEAL_TEXT)

        for peer in (ana, bob):
            peer.wait_for_seq(5, f"the reveal on {peer.name}")
            assert peer.errors() == []
            assert peer.reveal_results() == [
                RevealResult(
                    seq=4,
                    player_id=ana.you(),
                    target=ONE_ONE,
                    reveal_budget=RevealBudget(letters=4, words=1),
                )
            ]
            assert peer.cell_locks() == [
                CellLocked(seq=5, row=1, column=1, letter="A", revealed=True)
            ]
            tail = peer.messages()[-2:]
            assert [message.type for message in tail] == [
                "reveal_result",
                "cell_locked",
            ]


def test_ac1_websocket_a_later_joiner_sees_the_revealed_cell(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        bob.send(EditLetter(row=1, column=1, letter="X"))
        ana.wait_for_seq(3, "Bob's letter on Ana")
        ana.send_text(LETTER_REVEAL_TEXT)
        bob.wait_for_seq(5, "the reveal on Bob")

        cy = join_one(stack, client, room_code, "Cy")

        cell = snapshot_cell(cy.snapshot(), 1, 1)
        assert (cell.letter, cell.locked, cell.revealed, cell.author) == (
            "A",
            True,
            True,
            None,
        )


# ---- AC-1, two browsers on the live server ----


class SentFrames:
    """Every frame a page sent on its WebSockets, in order."""

    def __init__(self, page: Page) -> None:
        self.frames: list[str] = []
        page.on("websocket", self._watch)

    def _watch(self, websocket: WebSocket) -> None:
        websocket.on("framesent", self._keep)

    def _keep(self, payload: str | bytes) -> None:
        text = payload if isinstance(payload, str) else payload.decode("utf-8")
        self.frames.append(text)

    def count_of(self, kind: str) -> int:
        count = 0
        for frame in self.frames:
            if json.loads(frame).get("type") == kind:
                count += 1
        return count


def ana_reveals_bobs_letter(
    page: Page, bob_page: Page, url: str, enter_room: EnterRoom
) -> None:
    """Bob types `X` at (1, 1); Ana taps (1, 1) and clicks `reveal-letter`."""
    enter_room(page, url, "Ana")
    enter_room(bob_page, url, "Bob")
    cell_at(bob_page, 1, 1).click()
    bob_page.keyboard.press("x")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "X")
    cell_at(page, 1, 1).click()
    open_aide(page)  # spec 043: the item is in a panel, opened first
    page.get_by_test_id("reveal-letter").click(timeout=WAIT_TIMEOUT_MS)
    for watcher in (page, bob_page):
        expect(cell_at(watcher, 1, 1)).to_have_attribute("data-letter", "A")


def test_ac1_browser_both_pages_show_the_revealed_letter_locked_without_author(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        ana_reveals_bobs_letter(page, bob_page, f"{live_server}/r/{code}", enter_room)

        for watcher in (page, bob_page):
            cell = cell_at(watcher, 1, 1)
            expect(cell).to_have_attribute("data-letter", "A")
            expect(cell).to_have_attribute("data-locked", "true")
            expect(cell).to_have_attribute("data-revealed", "true")
            expect(cell).to_have_attribute("data-author", "")
            assert mark_problems(cell) == []
            assert int(computed(cell, "fontWeight")) >= BOLD_WEIGHT
    finally:
        bob_context.close()


def test_ac1_browser_typing_on_the_revealed_cell_changes_nothing_and_sends_nothing(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        bob_sent = SentFrames(bob_page)
        ana_reveals_bobs_letter(page, bob_page, f"{live_server}/r/{code}", enter_room)
        expect(cell_at(bob_page, 1, 1)).to_have_attribute("data-revealed", "true")
        assert bob_sent.count_of("edit_letter") == 1

        cell_at(bob_page, 1, 1).click()
        bob_page.keyboard.press("b")
        bob_page.wait_for_timeout(SETTLE_MS)

        cell = cell_at(bob_page, 1, 1)
        expect(cell).to_have_attribute("data-letter", "A")
        expect(cell).to_have_attribute("data-unconfirmed", "false")
        expect(cell).to_have_attribute("data-locked", "true")
        expect(cell).to_have_attribute("data-revealed", "true")
        expect(cell).to_have_attribute("data-author", "")
        assert bob_sent.count_of("edit_letter") == 1
    finally:
        bob_context.close()


def test_ac1_browser_each_page_adds_one_reveal_line_to_the_feed(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        ana_reveals_bobs_letter(page, bob_page, f"{live_server}/r/{code}", enter_room)

        line = load_fr()["feed.reveal.letter"].replace("{name}", "Ana")
        for watcher in (page, bob_page):
            feed = watcher.get_by_test_id("activity-feed")
            items = feed.locator('[data-testid="feed-item"][data-kind="reveal"]')
            expect(items).to_have_text([line])
    finally:
        bob_context.close()


# ---- AC-1, page with a mocked socket: a pending edit on a revealed cell ----


def test_ac1_browser_a_revealed_lock_shows_over_my_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 1)
    cell.click()
    page.keyboard.press("b")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    wait_until_page(page, lambda: mock.edit_count() == 1, "the pending edit")

    left = RevealBudget(letters=4, words=1)
    mock.send(reveal_result_frame(6, ONE_ONE, left))
    mock.send(cell_locked_frame(7, 1, 1, "A", revealed=True))

    expect(cell).to_have_attribute("data-letter", "A")
    expect(cell).to_have_attribute("data-locked", "true")
    expect(cell).to_have_attribute("data-revealed", "true")
    expect(cell).to_have_attribute("data-author", "")
    refused = ErrorMessage(code=ErrorCode.CELL_LOCKED, message="locked")
    mock.send(refused.model_dump_json())
    page.wait_for_timeout(SETTLE_MS)
    expect(cell).to_have_attribute("data-letter", "A")
    expect(cell).to_have_attribute("data-unconfirmed", "false")
    expect(cell).to_have_attribute("data-revealed", "true")
