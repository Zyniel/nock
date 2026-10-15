"""Tests of spec 017, AC-2: the stale rule and the resent offline edits.

The rule (`handle_message`) is tested directly, then through the real WebSocket
with a fake clock, then in the page with spec 040's mocked socket. The shared
setup is in `spec017_harness`.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    LetterChanged,
    PlayerState,
)
from nock.room import CellState, RoomConfig, RoomState, handle_message
from spec017_harness import (
    LONG_SILENCE_CONFIG,
    LOSS_BUDGET_MS,
    NOW,
    SETTLE_SECONDS,
    STORED_JOIN,
    ChangeList,
    Edit,
    FakeClock,
    MockConnection,
    Peer,
    banner,
    cell_at,
    cell_state,
    error_events,
    error_frame,
    events_of,
    expect_cell,
    first_join,
    grid_from_text,
    has_state_change,
    join_two,
    joined_room,
    make_dist_dir,
    open_peer,
    room_page,
    running_room,
    settle,
    snapshot_frame,
    sole_error,
    two_player_room,
    wait_until,
    with_cell,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def stale_room(grid: Grid) -> RoomState:
    """Two players, seq 10; `p2` wrote `B` at (1, 0) with seq 8."""
    room = with_cell(
        two_player_room(grid),
        CellState(
            row=1,
            column=0,
            letter="B",
            author="p2",
            changed_seq=8,
            changed_by="p2",
        ),
    )
    return room.model_copy(update={"seq": 10})


# ---- AC-2: the stale rule on handle_message ----------------------------------


def test_ac2_an_edit_on_a_cell_changed_since_by_someone_else_is_refused(
    fx01_grid: Grid,
) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=7), NOW
    )

    assert sole_error(outcome.reply).code is ErrorCode.STALE_EDIT
    assert outcome.entries == ()
    assert outcome.state.seq == 10
    assert outcome.state.cells == room.cells
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("B", "p2", 8)


def test_ac2_a_base_seq_equal_to_the_changed_seq_is_applied(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=8), NOW
    )

    assert outcome.reply == ()
    assert outcome.state.seq == 11
    assert events_of(outcome.entries) == [
        LetterChanged(seq=11, row=1, column=0, letter="T", pencil=False, player_id="p1")
    ]
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("T", "p1", 11)


@pytest.mark.parametrize("changed_seq", [0, 7])
def test_ac2_a_cell_unchanged_since_the_base_seq_is_applied(
    fx01_grid: Grid, changed_seq: int
) -> None:
    room = stale_room(fx01_grid)
    if changed_seq > 0:
        room = with_cell(
            room,
            CellState(
                row=1,
                column=1,
                letter="Z",
                author="p2",
                changed_seq=changed_seq,
                changed_by="p2",
            ),
        )

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=1, letter="A", base_seq=7), NOW
    )

    assert outcome.reply == ()
    assert outcome.state.seq == 11
    cell = cell_state(outcome.state, 1, 1)
    assert (cell.letter, cell.author, cell.changed_seq) == ("A", "p1", 11)


def test_ac2_my_own_later_change_never_makes_my_edit_stale(fx01_grid: Grid) -> None:
    room = with_cell(
        stale_room(fx01_grid),
        CellState(
            row=1,
            column=0,
            letter="X",
            author="p1",
            changed_seq=9,
            changed_by="p1",
        ),
    )

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=7), NOW
    )

    assert outcome.reply == ()
    assert cell_state(outcome.state, 1, 0).letter == "T"
    assert outcome.state.seq == 11


def test_ac2_a_live_edit_is_never_stale(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=None), NOW
    )

    assert outcome.reply == ()
    assert cell_state(outcome.state, 1, 0).letter == "T"
    assert outcome.state.seq == 11


def test_ac2_a_base_seq_beyond_the_room_seq_is_applied(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=99), NOW
    )

    assert outcome.reply == ()
    assert cell_state(outcome.state, 1, 0).letter == "T"
    assert outcome.state.seq == 11


def test_ac2_resending_offline_edits_to_one_cell_keeps_the_last(
    fx01_grid: Grid,
) -> None:
    room = two_player_room(fx01_grid)

    first = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=2), NOW
    )
    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=0, letter="X", base_seq=2), NOW
    )

    assert first.reply == ()
    assert second.reply == ()
    assert second.state.seq == 4
    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("X", "p1", 4)


def test_ac2_an_offline_erase_that_is_stale_is_refused(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(room, "p1", Erase(row=1, column=0, base_seq=7), NOW)

    assert sole_error(outcome.reply).code is ErrorCode.STALE_EDIT
    assert outcome.entries == ()
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("B", "p2", 8)


def test_ac2_an_offline_erase_that_is_not_stale_is_applied(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(room, "p1", Erase(row=1, column=0, base_seq=8), NOW)

    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        LetterChanged(
            seq=11, row=1, column=0, letter=None, pencil=False, player_id="p1"
        )
    ]
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author) == (None, None)


def test_ac2_a_locked_cell_is_refused_as_locked_before_staleness(
    fx01_grid: Grid,
) -> None:
    room = with_cell(
        stale_room(fx01_grid),
        CellState(
            row=1,
            column=0,
            letter="B",
            author="p2",
            locked=True,
            changed_seq=8,
            changed_by="p2",
        ),
    )

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=7), NOW
    )

    assert sole_error(outcome.reply).code is ErrorCode.CELL_LOCKED


def test_ac2_the_rate_limit_is_checked_before_staleness(fx01_grid: Grid) -> None:
    config = RoomConfig(max_edits_per_second=1)
    room = stale_room(fx01_grid)
    first = handle_message(
        room, "p1", EditLetter(row=1, column=1, letter="A"), NOW, config
    )
    assert first.reply == ()

    outcome = handle_message(
        first.state,
        "p1",
        EditLetter(row=1, column=0, letter="T", base_seq=7),
        NOW,
        config,
    )

    assert sole_error(outcome.reply).code is ErrorCode.RATE_LIMITED


# ---- AC-2: the stale rule through the real WebSocket -------------------------


def letter_events(peer: Peer) -> list[LetterChanged]:
    found: list[LetterChanged] = []
    for message in peer.events():
        if isinstance(message, LetterChanged):
            found.append(message)
    return found


def test_ac2_websocket_an_offline_edit_on_a_changed_cell_gets_stale_edit(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, LONG_SILENCE_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        a_token = peer_a.snapshot().resume_token
        assert peer_a.snapshot().seq == 1
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )
        peer_b.send(EditLetter(row=1, column=0, letter="B"))
        peer_b.wait_until(lambda: len(letter_events(peer_b)) == 1, "B's own letter")
        written_seq = letter_events(peer_b)[0].seq
        assert written_seq == 4

        with contextlib.ExitStack() as second_a_stack:
            second_a = open_peer(second_a_stack, client, code, "Ana", a_token)
            assert second_a.snapshot().you == a_id
            assert second_a.snapshot().seq == 5
            second_a.send(EditLetter(row=1, column=0, letter="T", base_seq=2))
            second_a.send(EditLetter(row=1, column=1, letter="A", base_seq=2))
            second_a.wait_until(
                lambda: len(error_events(second_a)) == 1
                and len(letter_events(second_a)) == 1,
                "the refusal and the applied letter",
            )
            peer_b.wait_until(
                lambda: len(letter_events(peer_b)) == 2, "A's applied letter on B"
            )
            time.sleep(SETTLE_SECONDS)

            assert error_events(second_a)[0].code is ErrorCode.STALE_EDIT
            applied = LetterChanged(
                seq=6, row=1, column=1, letter="A", pencil=False, player_id=a_id
            )
            first_event = second_a.events()[0]
            assert isinstance(first_event, ErrorMessage)
            assert letter_events(second_a) == [applied]
            written_by_b = LetterChanged(
                seq=4, row=1, column=0, letter="B", pencil=False, player_id=b_id
            )
            assert letter_events(peer_b) == [written_by_b, applied]
            assert error_events(peer_b) == []
            state = registry.room_state(code)
            assert state is not None
            assert cell_state(state, 1, 0).letter == "B"
            assert cell_state(state, 1, 1).letter == "A"
            assert state.seq == 6


def letter_changed_frame(
    seq: int, row: int, column: int, letter: str | None, player_id: str
) -> str:
    event = LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=False,
        player_id=player_id,
    )
    return event.model_dump_json()


def wait_for_edits(
    page: Page, connection: MockConnection, expected: list[Edit]
) -> None:
    """Wait for the expected edits, give time for extra ones, then compare."""
    wait_until(page, lambda: len(connection.edits()) >= len(expected))
    settle(page)
    assert connection.edits() == expected


# ---- AC-2: offline edits resent with their base_seq (browser) ----------------


def test_ac2_offline_letters_are_resent_with_base_seq_and_the_server_letter_wins(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    room.connections[0].close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    page.keyboard.press("a")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN
    assert second.edits() == []
    changes: ChangeList = [(1, 0, {"letter": "B", "author": "p2"})]
    second.send(snapshot_frame(fx01_grid, 9, changes))

    expect(room_page(page)).to_have_attribute("data-seq", "9")
    expect(banner(page)).to_be_hidden()
    wait_for_edits(
        page,
        second,
        [
            EditLetter(row=1, column=0, letter="T", base_seq=5),
            EditLetter(row=1, column=1, letter="A", base_seq=5),
        ],
    )
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    second.send(error_frame(ErrorCode.STALE_EDIT))

    expect_cell(page, 1, 0, "B", unconfirmed=False, author="p2")
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    second.send(letter_changed_frame(10, 1, 1, "A", "p1"))

    expect_cell(page, 1, 1, "A", unconfirmed=False, author="p1")
    expect_cell(page, 1, 0, "B", unconfirmed=False, author="p2")


def test_ac2_an_edit_sent_before_the_loss_is_resent_with_its_base_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    first = room.connections[0]
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    wait_for_edits(page, first, [EditLetter(row=1, column=0, letter="T")])
    first.close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    room.wait_for_connections(2)
    second = room.connections[1]
    second.send(snapshot_frame(fx01_grid, 9))

    wait_for_edits(page, second, [EditLetter(row=1, column=0, letter="T", base_seq=5)])
    second.send(letter_changed_frame(10, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")


def test_ac2_an_offline_erase_is_resent_with_its_base_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, {"letter": "T", "author": "p2"})]
    room = joined_room(page, live_server, fx01_grid, seq=5, changes=changes)
    room.connections[0].close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    cell_at(page, 1, 0).click()
    page.keyboard.press("Backspace")
    expect_cell(page, 1, 0, "", unconfirmed=True)

    room.wait_for_connections(2)
    second = room.connections[1]
    second.send(snapshot_frame(fx01_grid, 7, changes))

    wait_for_edits(page, second, [Erase(row=1, column=0, base_seq=5)])


def test_ac2_edits_typed_after_the_reconnection_are_sent_live(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    room.connections[0].close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    room.wait_for_connections(2)
    second = room.connections[1]
    second.send(snapshot_frame(fx01_grid, 9))
    expect(banner(page)).to_be_hidden()
    expect(room_page(page)).to_have_attribute("data-seq", "9")
    cell_at(page, 1, 0).click()

    page.keyboard.press("t")

    wait_for_edits(page, second, [EditLetter(row=1, column=0, letter="T")])
