"""Tests of spec 039, AC-18 and AC-19: the roster limit and frozen messages.

AC-18: a snapshot holds at most 8 players. AC-19: a parsed message cannot be
changed. The shared setup is in `spec039_harness`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nock.protocol import (
    EditLetter,
    Reveal,
    Snapshot,
    VoteOpened,
    WordTarget,
    parse_client_message,
    parse_server_message,
)
from spec039_harness import JsonData, client_text, server_text, snapshot_with

# ---- AC-18 --------------------------------------------------------------


def player_data(index: int) -> JsonData:
    """Return a player view dictionary for the player p<index>."""
    return {
        "player_id": f"p{index}",
        "nickname": f"Player{index}",
        "colour": index % 8,
        "state": "active",
        "is_host": index == 1,
        "muted": False,
        "selection": None,
    }


def snapshot_with_players(count: int) -> str:
    """Return the snapshot example holding players p1 to p<count>."""
    players = []
    for index in range(1, count + 1):
        players.append(player_data(index))
    return snapshot_with(players=players)


def test_ac18_snapshot_with_eight_players_parses() -> None:
    message = parse_server_message(snapshot_with_players(8))

    assert isinstance(message, Snapshot)
    assert [player.player_id for player in message.players] == [
        "p1",
        "p2",
        "p3",
        "p4",
        "p5",
        "p6",
        "p7",
        "p8",
    ]


def test_ac18_snapshot_with_nine_players_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_server_message(snapshot_with_players(9))


def test_ac18_snapshot_with_no_player_parses() -> None:
    message = parse_server_message(snapshot_with_players(0))

    assert isinstance(message, Snapshot)
    assert message.players == ()


# ---- AC-19 --------------------------------------------------------------


def test_ac19_assigning_a_field_raises_and_keeps_the_message() -> None:
    message = parse_client_message(client_text("edit_letter"))

    # setattr with a variable name: the type checker rejects a direct
    # assignment to a frozen field, which is what this test must attempt.
    field = "row"
    with pytest.raises(ValidationError):
        setattr(message, field, 2)

    assert isinstance(message, EditLetter)
    assert message.row == 1
    assert message == EditLetter(row=1, column=0, letter="T", base_seq=None)


@pytest.mark.parametrize("type_name", ["host_changed", "grid_solved", "error"])
def test_ac19_server_messages_are_frozen(type_name: str) -> None:
    message = parse_server_message(server_text(type_name))
    before = message.model_dump_json()

    field = "type"  # variable name: see test_ac19_assigning_a_field_raises
    with pytest.raises(ValidationError):
        setattr(message, field, "other")

    assert message.model_dump_json() == before


def test_ac19_nested_model_is_frozen() -> None:
    message = parse_server_message(server_text("vote_opened"))

    assert isinstance(message, VoteOpened)
    assert isinstance(message.request, Reveal)
    target = message.request.target
    assert isinstance(target, WordTarget)
    field = "row"  # variable name: see test_ac19_assigning_a_field_raises
    with pytest.raises(ValidationError):
        setattr(target, field, 9)

    assert target.row == 0


def test_ac19_snapshot_is_frozen() -> None:
    message = parse_server_message(server_text("snapshot"))

    assert isinstance(message, Snapshot)
    field = "solved"  # variable name: see test_ac19_assigning_a_field_raises
    with pytest.raises(ValidationError):
        setattr(message, field, True)

    assert message.solved is False
