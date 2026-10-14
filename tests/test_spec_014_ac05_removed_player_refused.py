"""Tests of spec 014, AC-5: a removed player can do nothing more.

The rules and the real WebSocket.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.
"""

from __future__ import annotations

import contextlib
import threading
import time
from pathlib import Path

import pytest

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClientMessage,
    ConfirmPencil,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    HelpMode,
    LetterChanged,
    LockRoom,
    MutePlayer,
    PencilEdit,
    Ping,
    PlayerState,
    RemovePlayer,
    SelectCell,
    Undo,
)
from nock.room import RoomConfig, RoomState, disconnect_player, handle_message, tick
from spec014_harness import (
    NICKNAMES,
    NOW,
    QUIET_RULES,
    SETTLE_SECONDS,
    TICK_SECONDS,
    WS_DETECTION_SECONDS,
    FakeClock,
    Peer,
    cell_state,
    change,
    error_codes,
    has_state_change,
    join_in_order,
    keep_seen,
    open_peer,
    ping_and_wait,
    player_ids,
    removed_bob,
    room_of_players,
    room_players,
    running_room,
    socket_url,
    sole_error,
    stored_room,
)
from spec014_harness import dist_dir as dist_dir
from spec014_harness import fx01_grid as fx01_grid

# ---- AC-5: a player who is not in the room can do nothing (rules) -----------


LETTER_ROW = 1
LETTER_COLUMN = 0
FLOOD_FRAMES = 40
FLOOD_POLL_SECONDS = 0.0005
FLOOD_JOIN_SECONDS = 10.0
STRANGER_MESSAGE_IDS = [
    "edit_letter",
    "erase",
    "select_cell",
    "pencil_edit",
    "confirm_pencil",
    "undo",
    "remove_player",
    "lock_room",
    "change_settings",
    "mute_player",
    "ping",
]


def stranger_message(message_id: str) -> ClientMessage:
    """Return the message of the kind `message_id`, as a stranger would send it."""
    if message_id == "edit_letter":
        return EditLetter(row=LETTER_ROW, column=LETTER_COLUMN, letter="Z")
    if message_id == "erase":
        return Erase(row=LETTER_ROW, column=LETTER_COLUMN)
    if message_id == "select_cell":
        return SelectCell(
            row=LETTER_ROW, column=LETTER_COLUMN, direction=Direction.ACROSS
        )
    if message_id == "pencil_edit":
        return PencilEdit(row=LETTER_ROW, column=LETTER_COLUMN, letter="Z")
    if message_id == "confirm_pencil":
        return ConfirmPencil(row=LETTER_ROW, column=LETTER_COLUMN)
    if message_id == "undo":
        return Undo()
    if message_id == "remove_player":
        return RemovePlayer(player_id="p1")
    if message_id == "lock_room":
        return LockRoom(locked=True)
    if message_id == "change_settings":
        return change(HelpMode.NONE, 0, 0)
    if message_id == "mute_player":
        return MutePlayer(player_id="p3", muted=True)
    return Ping()


def assert_refused_as_not_joined(
    room: RoomState, player_id: str, message_id: str
) -> None:
    """Assert `player_id`'s message changes nothing and gets `not_joined`."""
    message = stranger_message(message_id)

    outcome = handle_message(room, player_id, message, NOW + 5)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_JOINED
    assert outcome.entries == ()
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False
    assert outcome.state == room


@pytest.mark.parametrize("message_id", STRANGER_MESSAGE_IDS)
def test_ac5_a_message_from_an_unknown_player_is_refused_as_not_joined(
    fx01_grid: Grid, message_id: str
) -> None:
    room = room_of_players(fx01_grid, 3)

    assert_refused_as_not_joined(room, "zz", message_id)


@pytest.mark.parametrize("message_id", STRANGER_MESSAGE_IDS)
def test_ac5_a_message_from_a_removed_player_is_refused_as_not_joined(
    fx01_grid: Grid, message_id: str
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    assert_refused_as_not_joined(room, "p2", message_id)


@pytest.mark.parametrize("message_id", STRANGER_MESSAGE_IDS)
def test_ac5_a_message_from_a_timed_out_player_is_refused_as_not_joined(
    fx01_grid: Grid, message_id: str
) -> None:
    room = disconnect_player(room_of_players(fx01_grid, 3), "p2", NOW + 10).state
    after_window = NOW + 10 + 300.5
    ticked = tick(keep_seen(room, after_window), after_window, QUIET_RULES)
    assert player_ids(ticked.state) == ["p1", "p3"]

    assert_refused_as_not_joined(ticked.state, "p2", message_id)


def test_ac5_a_removed_player_leaves_no_trace_on_the_cells(fx01_grid: Grid) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))
    edit = EditLetter(row=LETTER_ROW, column=LETTER_COLUMN, letter="Z")

    outcome = handle_message(room, "p2", edit, NOW + 5)

    cell = cell_state(outcome.state, LETTER_ROW, LETTER_COLUMN)
    assert (cell.letter, cell.author, cell.changed_by) == (None, None, None)
    assert outcome.state.cells == room.cells


def test_ac5_the_host_still_edits_after_a_removal(fx01_grid: Grid) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))
    edit = EditLetter(row=LETTER_ROW, column=LETTER_COLUMN, letter="Z")

    outcome = handle_message(room, "p1", edit, NOW + 5)

    assert outcome.reply == ()
    assert len(outcome.entries) == 1
    assert isinstance(outcome.entries[0].event, LetterChanged)


# ---- AC-5: through the real WebSocket ---------------------------------------


def letter_changed_events(peer: Peer) -> list[LetterChanged]:
    found: list[LetterChanged] = []
    for message in peer.events():
        if isinstance(message, LetterChanged):
            found.append(message)
    return found


def flood_once_removed(
    registry: RoomRegistry, code: str, peer: Peer, player_id: str, sent: list[int]
) -> None:
    """From the removed player's own thread: edit as fast as possible.

    Waits for the room to drop the player (never for the player's own error or
    close), then sends FLOOD_FRAMES edit_letter frames back to back.
    """
    deadline = time.monotonic() + FLOOD_JOIN_SECONDS
    while player_id in room_players(registry, code):
        if time.monotonic() > deadline:
            return
        time.sleep(FLOOD_POLL_SECONDS)
    letters = "ABCDE"
    for index in range(FLOOD_FRAMES):
        edit = EditLetter(
            row=LETTER_ROW,
            column=LETTER_COLUMN + index % 3,
            letter=letters[index % len(letters)],
        )
        with contextlib.suppress(Exception):  # the socket may already be closed
            peer.send(edit)
        sent.append(index)


def test_ac5_websocket_40_edits_right_after_a_removal_are_neither_committed_nor_sent(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        stored_room(fx01_grid, dist_dir, fake_clock) as (
            client,
            store,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
        contextlib.ExitStack() as c_stack,
    ):
        peer_a, peer_b, peer_c = join_in_order(
            [a_stack, b_stack, c_stack], client, code
        )
        b_id = peer_b.snapshot().you
        sent: list[int] = []
        flooder = threading.Thread(
            target=flood_once_removed,
            args=(registry, code, peer_b, b_id, sent),
            daemon=True,
        )
        flooder.start()

        peer_a.send(RemovePlayer(player_id=b_id))
        flooder.join(FLOOD_JOIN_SECONDS)
        assert not flooder.is_alive()
        peer_b.wait_until(lambda: peer_b.close_code is not None, "the close of B")
        ping_and_wait(peer_a)
        ping_and_wait(peer_c)
        time.sleep(SETTLE_SECONDS)

        assert len(sent) == FLOOD_FRAMES
        assert letter_changed_events(peer_a) == []
        assert letter_changed_events(peer_c) == []
        state = registry.room_state(code)
        assert state is not None
        for cell in state.cells:
            assert cell.author != b_id
            assert cell.changed_by != b_id
            assert cell.letter is None
        assert state.seq == 4
        logged = store.read_log(code)
        for entry in logged:
            assert not isinstance(entry.event, LetterChanged)
        assert len(logged) == 4


def test_ac5_websocket_a_silence_disconnect_stops_routing_the_late_frames(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    config = RoomConfig(tick_seconds=TICK_SECONDS)
    with (
        running_room(fx01_grid, dist_dir, fake_clock, config) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        b_id = peer_b.snapshot().you
        peer_b.send(
            SelectCell(row=LETTER_ROW, column=LETTER_COLUMN, direction=Direction.ACROSS)
        )
        ping_and_wait(peer_b)
        fake_clock.advance(3)
        ping_and_wait(peer_a)
        fake_clock.advance(3)
        peer_a.wait_until(
            lambda: has_state_change(peer_a, b_id, PlayerState.DISCONNECTED),
            "the silence disconnection of B",
            timeout=WS_DETECTION_SECONDS,
        )
        peer_b.wait_until(
            lambda: peer_b.close_code is not None,
            "the silence close of B",
            timeout=WS_DETECTION_SECONDS,
        )
        assert peer_b.close_code == 4408
        ping_and_wait(peer_a)  # events about B's disconnection are now in
        received_before = len(peer_a.messages())
        before = registry.room_state(code)
        assert before is not None

        for index in range(5):
            late_edit = EditLetter(
                row=LETTER_ROW, column=LETTER_COLUMN, letter="ABCDE"[index]
            )
            with contextlib.suppress(Exception):  # the socket may be closed
                peer_b.send(late_edit)
        time.sleep(SETTLE_SECONDS)
        ping_and_wait(peer_a)

        assert letter_changed_events(peer_a) == []
        received_after = peer_a.messages()[received_before:]
        assert len(received_after) == 1, (  # only the pong
            f"expected only the pong after the baseline, got {received_after!r}"
        )
        after = registry.room_state(code)
        assert after is not None
        assert after.seq == before.seq
        for cell in after.cells:
            assert cell.author != b_id
            assert cell.changed_by != b_id
            assert cell.letter is None


def test_ac5_websocket_a_new_socket_after_a_silence_close_is_routed_again(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    config = RoomConfig(tick_seconds=TICK_SECONDS)
    with (
        running_room(fx01_grid, dist_dir, fake_clock, config) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
        contextlib.ExitStack() as new_b_stack,
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        b_id = peer_b.snapshot().you
        b_token = peer_b.snapshot().resume_token
        peer_b.send(
            SelectCell(row=LETTER_ROW, column=LETTER_COLUMN, direction=Direction.ACROSS)
        )
        ping_and_wait(peer_b)
        fake_clock.advance(3)
        ping_and_wait(peer_a)
        fake_clock.advance(3)
        peer_a.wait_until(
            lambda: has_state_change(peer_a, b_id, PlayerState.DISCONNECTED),
            "the silence disconnection of B",
            timeout=WS_DETECTION_SECONDS,
        )
        peer_b.wait_until(
            lambda: peer_b.close_code is not None,
            "the silence close of B",
            timeout=WS_DETECTION_SECONDS,
        )
        assert peer_b.close_code == 4408

        new_b = open_peer(new_b_stack, client, code, NICKNAMES[1], b_token)
        assert new_b.snapshot().you == b_id
        new_b.send(EditLetter(row=LETTER_ROW, column=LETTER_COLUMN, letter="Q"))
        peer_a.wait_until(
            lambda: len(letter_changed_events(peer_a)) == 1,
            "the edit of the rejoined B",
        )
        changed = letter_changed_events(peer_a)[0]
        assert changed.letter == "Q"
        assert changed.player_id == b_id

        peer_a.send(EditLetter(row=LETTER_ROW, column=LETTER_COLUMN, letter="R"))
        new_b.wait_until(
            lambda: "R" in [event.letter for event in letter_changed_events(new_b)],
            "the events of A reaching the rejoined B",
        )


def test_ac5_websocket_a_socket_that_never_joined_gets_not_joined(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        stored_room(fx01_grid, dist_dir, fake_clock) as (client, _store, _reg, code),
        contextlib.ExitStack() as stack,
    ):
        websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
        stranger = Peer(websocket)

        stranger.send(EditLetter(row=LETTER_ROW, column=LETTER_COLUMN, letter="Z"))
        stranger.wait_until(
            lambda: ErrorCode.NOT_JOINED in error_codes(stranger),
            "not_joined for a socket that never joined",
        )

        assert error_codes(stranger) == [ErrorCode.NOT_JOINED]
