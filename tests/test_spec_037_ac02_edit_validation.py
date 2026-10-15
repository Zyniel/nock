"""Tests of spec 037 (integrity), AC-2: the validation of an edit.

AC-2 checks the edit validation on `handle_message` and on the WebSocket, and the
frame size limit. The shared setup is in `spec037_harness`.

Interpretation (see the report): the invalid-frame answer of a joined socket is
tested under AC-2.

Not tested here: a removed player's socket being closed (spec 014). A text frame
whose size in bytes differs from its size in characters is covered only for a join
(Unicode spaces around the nickname are stripped, so the frame stays valid).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import nock.hub
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClientMessage,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    Join,
    LetterChanged,
    SelectCell,
    Snapshot,
    Undo,
)
from nock.room import grid_state, handle_message
from nock.server import create_app
from spec037_harness import (
    NOW,
    Peer,
    connect,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    player_record,
    refusal_code,
    state_of,
    two_player_room,
)

MAX_FRAME_BYTES = 4096

# ---- Fixtures -----------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1."""
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


# ---- Helpers for the WebSocket tests ------------------------------------------


def edit_frame(letter: str, row: int = 1, column: int = 0) -> str:
    """The JSON text of an `edit_letter`, with any `letter` value."""
    return json.dumps(
        {"type": "edit_letter", "row": row, "column": column, "letter": letter}
    )


def erase_frame(row: int, column: int) -> str:
    return json.dumps({"type": "erase", "row": row, "column": column})


def padded_to(text: str, size: int) -> str:
    """`text` followed by JSON whitespace until it is `size` bytes long."""
    assert len(text.encode("utf-8")) <= size
    return text + " " * (size - len(text.encode("utf-8")))


def check_refusal(
    registry: RoomRegistry,
    code: str,
    ana: Peer,
    bob: Peer,
    sender: Peer,
    send_refused: Callable[[], None],
    expected: ErrorCode,
) -> None:
    """Check one refused frame, then one valid edit of Ana.

    The refused frame is answered `expected` to `sender` only, changes neither the
    `seq` nor the grid, and reaches nobody else; the valid `T` at (1, 0) of Ana is
    then accepted, and Bob's whole list of messages is that event alone.
    """
    ana_start = len(ana.messages())
    bob_start = len(bob.messages())
    sender_start = len(sender.messages())
    before = state_of(registry, code)

    send_refused()
    sender.wait_for_messages(sender_start + 1, "the refusal")

    after = state_of(registry, code)
    assert after.seq == before.seq
    assert grid_state(after) == grid_state(before)

    ana.send(EditLetter(row=1, column=0, letter="T"))
    ana.wait_for_letter_events(1, "the valid edit of Ana")
    bob.wait_for_letter_events(1, "the valid edit of Ana, on Bob")

    refusal = sender.messages()[sender_start]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is expected
    accepted = LetterChanged(
        seq=before.seq + 1,
        row=1,
        column=0,
        letter="T",
        pencil=False,
        player_id=ana.you(),
    )
    assert bob.messages()[bob_start:] == [accepted]
    if sender is ana:
        assert ana.messages()[ana_start:] == [refusal, accepted]
    else:
        assert ana.messages()[ana_start:] == [accepted]
        assert sender.messages()[sender_start:] == [refusal]


# ---- AC-2: only a letter, on a letter cell, from a member (Python) ----------------

NOT_LETTER_CELLS = [(0, 0), (5, 0), (0, 5), (9, 9), (4, 5), (0, 2)]


@pytest.mark.parametrize(("row", "column"), NOT_LETTER_CELLS)
@pytest.mark.parametrize("kind", ["edit_letter", "erase"])
def test_ac2_python_an_edit_off_a_letter_cell_is_refused_and_changes_nothing(
    fx01_grid: Grid, row: int, column: int, kind: str
) -> None:
    before = two_player_room(fx01_grid)
    message: ClientMessage
    if kind == "edit_letter":
        message = EditLetter(row=row, column=column, letter="T")
    else:
        message = Erase(row=row, column=column)

    outcome = handle_message(before, "p1", message, NOW)

    assert outcome.state == before
    assert outcome.entries == ()
    assert refusal_code(outcome.reply) is ErrorCode.NOT_A_LETTER_CELL
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


def test_ac2_python_a_refused_edit_does_not_count_for_the_rate_limit(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    outcome = handle_message(state, "p1", EditLetter(row=0, column=0, letter="T"), NOW)

    assert player_record(outcome.state, "p1").recent_edits == ()


# ---- AC-2: only a letter, on a letter cell, from a member (WebSocket) --------------


@pytest.mark.parametrize("letter", ["a", "É", "AB", "1", ""])
def test_ac2_websocket_an_edit_with_a_bad_letter_is_an_invalid_message(
    registry: RoomRegistry, client: TestClient, room_code: str, letter: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            ana,
            lambda: ana.send_text(edit_frame(letter)),
            ErrorCode.INVALID_MESSAGE,
        )


@pytest.mark.parametrize(("row", "column"), [(0, 0), (5, 0), (0, 5), (9, 9)])
@pytest.mark.parametrize("kind", ["edit_letter", "erase"])
def test_ac2_websocket_an_edit_off_a_letter_cell_is_not_a_letter_cell(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    row: int,
    column: int,
    kind: str,
) -> None:
    frame = (
        edit_frame("T", row, column)
        if kind == "edit_letter"
        else erase_frame(row, column)
    )
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            ana,
            lambda: ana.send_text(frame),
            ErrorCode.NOT_A_LETTER_CELL,
        )


def test_ac2_websocket_an_edit_from_a_socket_that_has_not_joined_is_not_joined(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        stranger = connect(stack, client, room_code, "Stranger")

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            stranger,
            lambda: stranger.send_text(edit_frame("T", 1, 0)),
            ErrorCode.NOT_JOINED,
        )


@pytest.mark.parametrize(
    "message",
    [
        Undo(),
        SelectCell(row=1, column=0, direction=Direction.ACROSS),
        Erase(row=1, column=0),
    ],
    ids=["undo", "select_cell", "erase"],
)
def test_ac2_websocket_every_valid_message_before_join_is_not_joined(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    message: ClientMessage,
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        stranger = connect(stack, client, room_code, "Stranger")

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            stranger,
            lambda: stranger.send(message),
            ErrorCode.NOT_JOINED,
        )


def test_ac2_websocket_a_valid_edit_of_a_member_is_accepted(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.wait_for_letter_events(1, "the accepted edit")
        bob.wait_for_letter_events(1, "the accepted edit, on Bob")

        expected = LetterChanged(
            seq=3, row=1, column=0, letter="T", pencil=False, player_id=ana.you()
        )
        assert ana.letter_events() == [expected]
        assert bob.letter_events() == [expected]
        assert state_of(registry, room_code).seq == 3


def test_ac2_websocket_an_edit_reaches_the_players_of_its_room_only(
    registry: RoomRegistry, client: TestClient, room_code: str, fx01_grid: Grid
) -> None:
    other_code = registry.register_room(fx01_grid)
    with contextlib.ExitStack() as stack:
        (ana,) = join_peers(stack, client, room_code, ["Ana"])
        (zed,) = join_peers(stack, client, other_code, ["Zed"])
        zed_start = len(zed.messages())

        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.wait_for_letter_events(1, "the edit of Ana")
        zed.send(EditLetter(row=2, column=1, letter="V"))
        zed.wait_for_letter_events(1, "the edit of Zed")

        zed_events = zed.messages()[zed_start:]
        assert zed_events == [
            LetterChanged(
                seq=2,
                row=2,
                column=1,
                letter="V",
                pencil=False,
                player_id=zed.you(),
            )
        ]
    other_state = state_of(registry, other_code)
    assert [(c.row, c.column, c.letter) for c in other_state.cells if c.letter] == [
        (2, 1, "V")
    ]


# ---- AC-2: frames over 4096 bytes -------------------------------------------------


def test_ac2_max_frame_bytes_is_4096() -> None:
    assert nock.hub.MAX_FRAME_BYTES == MAX_FRAME_BYTES


@pytest.mark.parametrize("as_bytes", [False, True], ids=["text", "binary"])
def test_ac2_websocket_a_frame_of_4097_bytes_is_an_invalid_message(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    as_bytes: bool,
) -> None:
    # The frame is a valid edit followed by spaces: only its size is wrong.
    frame = padded_to(edit_frame("T"), MAX_FRAME_BYTES + 1)
    assert len(frame.encode("utf-8")) == 4097

    def send_oversized() -> None:
        if as_bytes:
            ana.send_bytes(frame.encode("utf-8"))
        else:
            ana.send_text(frame)

    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            ana,
            send_oversized,
            ErrorCode.INVALID_MESSAGE,
        )


@pytest.mark.parametrize("as_bytes", [False, True], ids=["text", "binary"])
def test_ac2_websocket_a_frame_of_exactly_4096_bytes_is_parsed(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    as_bytes: bool,
) -> None:
    frame = padded_to(edit_frame("T"), MAX_FRAME_BYTES)
    assert len(frame.encode("utf-8")) == 4096
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        if as_bytes:
            ana.send_bytes(frame.encode("utf-8"))
        else:
            ana.send_text(frame)
        ana.wait_for_letter_events(1, "the edit in the 4096-byte frame")
        bob.wait_for_letter_events(1, "the edit in the 4096-byte frame, on Bob")

        assert ana.errors() == []
        assert ana.letter_events()[0].letter == "T"
        assert state_of(registry, room_code).seq == 3


def test_ac2_websocket_an_oversized_join_frame_is_an_invalid_message(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    join_text = Join(nickname="Ana", resume_token=None).model_dump_json()
    with contextlib.ExitStack() as stack:
        peer = connect(stack, client, room_code, "Ana")

        peer.send_text(padded_to(join_text, MAX_FRAME_BYTES + 1))
        peer.wait_for_messages(1, "the answer to the oversized join")

        refusal = peer.messages()[0]
        assert isinstance(refusal, ErrorMessage)
        assert refusal.code is ErrorCode.INVALID_MESSAGE
        assert state_of(registry, room_code).players == ()

        peer.send_text(padded_to(join_text, MAX_FRAME_BYTES))
        peer.wait_for_messages(2, "the snapshot")
        assert isinstance(peer.messages()[1], Snapshot)


def test_ac2_websocket_a_join_frame_over_4096_bytes_but_few_characters_is_refused(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    # Ana followed by ideographic spaces: valid once stripped, 1457 characters
    # but 4257 bytes, so only a size measured in bytes refuses it.
    nickname = "Ana" + "　" * 1400
    frame = json.dumps(
        {"type": "join", "nickname": nickname, "resume_token": None},
        ensure_ascii=False,
    )
    assert len(frame) < MAX_FRAME_BYTES
    assert len(frame.encode("utf-8")) > MAX_FRAME_BYTES
    with contextlib.ExitStack() as stack:
        peer = connect(stack, client, room_code, "Ana")

        peer.send_text(frame)
        peer.wait_for_messages(1, "the answer to the multi-byte join")

        refusal = peer.messages()[0]
        assert isinstance(refusal, ErrorMessage)
        assert refusal.code is ErrorCode.INVALID_MESSAGE
        assert state_of(registry, room_code).players == ()
