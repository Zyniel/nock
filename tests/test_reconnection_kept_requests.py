"""Tests of `platform/reconnection.md` AC-10 to AC-12: the undos, checks and reveals
a loss keeps, and the one it takes away.

Rule 7. Ana's page on spec 017's mocked room (`joined_room`, FX-01, seq 5), its
page clock frozen and moved by hand (`advance_page`), so that the resend after a
snapshot, one message every 100 ms, is read message by message. The request is a
check of the letter (1, 0), « Vérifier » « La lettre » with (1, 0) selected:
`Check` of `CellTarget(1, 0)`. What a socket was given is read from the frames
the mocked server got on it, edits and requests only (`sent_actions`): the pings
and the `select_cell` sent again after a loss (AC-5) are left out.

AC-10: the first socket closes with 1011; offline Ana types `T` at (1, 0) and
checks it. The next socket's snapshot is followed by the `T` 100 ms later; that
socket closes with 1011 before the check, due at 200 ms, goes out. After the next
socket's snapshot the page sends the `T` then the check.

AC-11: every socket is a controlled stand-in (`reconnection_harness.
CONTROL_ALL_SCRIPT`). `cut_quietly` gives the joined socket the state of one the
server closed with 1011 whose close event the page has not heard yet: it reads
CLOSING and drops what it is given; the server side then closes with 1011. Still
joined, Ana types `T` at (1, 0), checks it and types `A` at (1, 1); then
`deliver_close` gives the page the close 1011. After the next socket's snapshot
the page sends the `T`, the check, then the `A`.

AC-12: "her network has gone silent" is a mocked server that sends nothing after
the snapshot, its pings unanswered, so the socket still reads open until the
page's silence check drops it 4 seconds after the snapshot. At 2 seconds Ana
types `T` at (1, 0) and checks it: both are handed to the open socket (the mock
gets them, as a socket whose network is gone takes them), the `T` sent at once
with no `base_seq`. After the next socket's snapshot the page sends the `T` again,
with `base_seq` 5, and no check.

All durations are page-clock time, so this file runs in the parallel pass.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    Check,
    ClientMessage,
    EditLetter,
    Erase,
    Reveal,
    Undo,
    parse_client_message,
)
from reconnection_harness import CONTROL_ALL_SCRIPT, cut_quietly, deliver_close
from room_panels import open_aide
from spec017_harness import (
    STEP_SETTLE_MS,
    STORED_JOIN,
    MockConnection,
    MockRoom,
    advance_page,
    cell_at,
    expect_cell,
    expect_status,
    first_join,
    joined_room,
    snapshot_frame,
    wait_until,
)

SEQ = 5  # the seq of every snapshot: the base_seq of Ana's edits
LOST_CLOSE = 1011
FIRST_DELAY_LATEST_MS = 1200  # the first retry delay at its highest
SEND_INTERVAL_MS = 100  # one message every 100 ms after a snapshot
SILENT_BEFORE_THE_EDIT_MS = 2000  # AC-12: half-way to the 4 s of silence
SILENCE_LIMIT_MS = 4000

T_AT_1_0 = EditLetter(row=1, column=0, letter="T", base_seq=SEQ)
LIVE_T_AT_1_0 = EditLetter(row=1, column=0, letter="T")  # sent at once: no base_seq
A_AT_1_1 = EditLetter(row=1, column=1, letter="A", base_seq=SEQ)
CHECK_1_0 = Check(target=CellTarget(row=1, column=0))


def sent_actions(connection: MockConnection) -> list[ClientMessage]:
    """The edits, undos, checks and reveals the page sent on one socket, in order."""
    actions: list[ClientMessage] = []
    for frame in connection.frames:
        message = parse_client_message(frame)
        if isinstance(message, EditLetter | Erase | Undo | Check | Reveal):
            actions.append(message)
    return actions


def type_letter_at(page: Page, row: int, column: int, key: str) -> None:
    """Select a cell, type a letter there and wait until the page shows it."""
    cell_at(page, row, column).click()
    page.keyboard.press(key)
    expect_cell(page, row, column, key.upper(), unconfirmed=True)


def check_the_letter_at(page: Page, row: int, column: int) -> None:
    """Select a cell, then pick « Vérifier » « La lettre » in the Aide menu."""
    cell_at(page, row, column).click()
    expect(cell_at(page, row, column)).to_have_attribute("data-selected", "true")
    open_aide(page)
    page.get_by_test_id("check-letter").click()
    expect(page.get_by_test_id("aide-menu")).to_be_hidden()


def answer_the_next_join(page: Page, room: MockRoom, grid: Grid) -> MockConnection:
    """After a loss, let the next socket open and answer its join with a snapshot.

    Returns:
        The new socket, the page joined on it and its clock not yet moved past
        the snapshot.
    """
    expect_status(page, "reconnecting")
    count = len(room.connections)
    advance_page(page, FIRST_DELAY_LATEST_MS + 1)
    room.wait_for_connections(count + 1)
    connection = room.connections[count]
    assert first_join(page, connection) == STORED_JOIN
    connection.send(snapshot_frame(grid, SEQ))
    expect_status(page, "joined")
    return connection


def send_every_waiting_message(page: Page, count: int) -> None:
    """Move the page clock past `count` more messages of the resend."""
    for _ in range(count):
        advance_page(page, SEND_INTERVAL_MS)


# ---- AC-10: a loss during the resend keeps the requests not sent yet -------------


def test_ac10_a_check_not_yet_resent_at_a_loss_goes_after_the_next_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=SEQ, frozen=True)
    room.connections[0].close(LOST_CLOSE)
    expect_status(page, "reconnecting")
    type_letter_at(page, 1, 0, "t")
    check_the_letter_at(page, 1, 0)
    resending = answer_the_next_join(page, room, fx01_grid)
    advance_page(page, SEND_INTERVAL_MS)
    assert sent_actions(resending) == [T_AT_1_0]

    resending.close(LOST_CLOSE)
    next_socket = answer_the_next_join(page, room, fx01_grid)
    send_every_waiting_message(page, 3)

    assert sent_actions(next_socket) == [T_AT_1_0, CHECK_1_0]
    assert sent_actions(resending) == [T_AT_1_0]


# ---- AC-11: a socket already closing keeps what the page cannot hand to it -------


def test_ac11_a_check_made_before_the_close_is_heard_goes_in_its_place(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        seq=SEQ,
        frozen=True,
        init_script=CONTROL_ALL_SCRIPT,
    )
    first = room.connections[0]
    cut_quietly(page)
    first.close(LOST_CLOSE)
    page.wait_for_timeout(STEP_SETTLE_MS)

    type_letter_at(page, 1, 0, "t")
    check_the_letter_at(page, 1, 0)
    type_letter_at(page, 1, 1, "a")
    expect_status(page, "joined")
    assert sent_actions(first) == []
    deliver_close(page, LOST_CLOSE)
    next_socket = answer_the_next_join(page, room, fx01_grid)
    send_every_waiting_message(page, 4)

    assert sent_actions(next_socket) == [T_AT_1_0, CHECK_1_0, A_AT_1_1]


# ---- AC-12: a check handed to a silent socket is lost with it ----------------------


def test_ac12_a_check_handed_to_a_silent_socket_is_lost_and_the_t_is_sent_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page, live_server, fx01_grid, seq=SEQ, frozen=True, answer_pings=False
    )
    silent = room.connections[0]
    advance_page(page, SILENT_BEFORE_THE_EDIT_MS)
    type_letter_at(page, 1, 0, "t")
    check_the_letter_at(page, 1, 0)
    wait_until(page, lambda: len(sent_actions(silent)) == 2)
    expect_status(page, "joined")
    assert sent_actions(silent) == [LIVE_T_AT_1_0, CHECK_1_0]

    advance_page(page, SILENCE_LIMIT_MS - SILENT_BEFORE_THE_EDIT_MS)
    next_socket = answer_the_next_join(page, room, fx01_grid)
    send_every_waiting_message(page, 3)

    assert sent_actions(next_socket) == [T_AT_1_0]
