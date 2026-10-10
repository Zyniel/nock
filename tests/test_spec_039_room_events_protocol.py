"""Tests of spec 039: the room events protocol."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from nock.grid import Arrow, Grid
from nock.protocol import (
    Chat,
    ChatMessage,
    Check,
    CheckResult,
    ClueCellView,
    ClueView,
    EditLetter,
    EmptyCellView,
    Erase,
    ErrorMessage,
    Flag,
    GridSolved,
    GridTarget,
    GridView,
    Join,
    LetterCellView,
    LetterChanged,
    PencilEdit,
    PlayerJoined,
    RemovePlayer,
    Reveal,
    RevealResult,
    Snapshot,
    Vote,
    VoteOpened,
    WordTarget,
    grid_view,
    parse_client_message,
    parse_server_message,
)

# Raw JSON can hold anything, so these values are typed Any.
JsonData = dict[str, Any]
Parser = Callable[[str | bytes], BaseModel]

PLAYER_P2 = (
    '{"player_id": "p2", "nickname": "Bruno", "colour": 1, "state": "active", '
    '"is_host": false, "muted": false, "selection": null}'
)
SETTINGS = (
    '{"help_mode": "free", "reveal_budget": {"letters": 5, "words": 1}, '
    '"locked": false}'
)

# The JSON text of each wire example, copied from the spec (long lines are
# split into adjacent string literals, the text is unchanged).
CLIENT_EXAMPLES: dict[str, str] = {
    "join": '{"type": "join", "nickname": "Ana", "resume_token": null}',
    "select_cell": (
        '{"type": "select_cell", "row": 1, "column": 0, "direction": "across"}'
    ),
    "edit_letter": (
        '{"type": "edit_letter", "row": 1, "column": 0, "letter": "T", '
        '"base_seq": null}'
    ),
    "erase": '{"type": "erase", "row": 1, "column": 0, "base_seq": 7}',
    "pencil_edit": (
        '{"type": "pencil_edit", "row": 1, "column": 1, "letter": "A", '
        '"base_seq": null}'
    ),
    "confirm_pencil": (
        '{"type": "confirm_pencil", "row": 1, "column": 1, "base_seq": null}'
    ),
    "check": (
        '{"type": "check", "target": {"scope": "word", "row": 0, "column": 2, '
        '"clue_index": 0}}'
    ),
    "reveal": (
        '{"type": "reveal", "target": {"scope": "letter", "row": 4, "column": 4}}'
    ),
    "vote": '{"type": "vote", "vote_id": 3, "yes": true}',
    "flag": ('{"type": "flag", "clue": {"row": 0, "column": 0, "clue_index": 1}}'),
    "chat": '{"type": "chat", "text": "Qui a une idée pour le 3 ?"}',
    "react": (
        '{"type": "react", "clue": {"row": 2, "column": 0, "clue_index": 0}, '
        '"reaction": "clap"}'
    ),
    "undo": '{"type": "undo"}',
    "remove_player": '{"type": "remove_player", "player_id": "p2"}',
    "lock_room": '{"type": "lock_room", "locked": true}',
    "change_settings": (
        '{"type": "change_settings", "help_mode": "vote", '
        '"reveal_budget": {"letters": 5, "words": 1}}'
    ),
    "mute_player": ('{"type": "mute_player", "player_id": "p2", "muted": true}'),
}

# Server examples keep the PLAYER_P2 and SETTINGS placeholders, as in the spec.
SERVER_EXAMPLES: dict[str, str] = {
    "snapshot": (
        '{"type": "snapshot", "seq": 0, "you": "p1", '
        '"resume_token": "r7Kq2mXo9vB4tY1zW8nP", '
        '"grid": {"width": 2, "height": 1, "cells": ['
        '{"type": "clue", "row": 0, "column": 0, "clues": '
        '[{"text": "Note", "arrow": "right"}]}, '
        '{"type": "letter", "row": 0, "column": 1, "letter": null, '
        '"pencil": false, "author": null, "locked": false, "revealed": false, '
        '"wrong": false}]}, "players": [PLAYER_P2], "settings": SETTINGS, '
        '"reveal_budget": {"letters": 5, "words": 1}, "flags": [], "chat": [], '
        '"open_vote": null, "timer_elapsed_ms": 0, "timer_running": false, '
        '"solved": false}'
    ),
    "letter_changed": (
        '{"type": "letter_changed", "seq": 12, "row": 1, "column": 0, '
        '"letter": "T", "pencil": false, "player_id": "p1"}'
    ),
    "cell_locked": (
        '{"type": "cell_locked", "seq": 13, "row": 1, "column": 0, '
        '"letter": "T", "revealed": false}'
    ),
    "player_joined": '{"type": "player_joined", "seq": 2, "player": PLAYER_P2}',
    "player_left": (
        '{"type": "player_left", "seq": 40, "player_id": "p2", "reason": "removed"}'
    ),
    "player_state_changed": (
        '{"type": "player_state_changed", "seq": 41, "player_id": "p1", '
        '"state": "idle"}'
    ),
    "selection_moved": (
        '{"type": "selection_moved", "player_id": "p1", "selection": '
        '{"row": 1, "column": 0, "direction": "across"}}'
    ),
    "check_result": (
        '{"type": "check_result", "seq": 20, "player_id": "p1", '
        '"target": {"scope": "grid"}, "correct": [{"row": 1, "column": 0}], '
        '"wrong": [{"row": 1, "column": 1}]}'
    ),
    "reveal_result": (
        '{"type": "reveal_result", "seq": 22, "player_id": "p1", '
        '"target": {"scope": "letter", "row": 4, "column": 4}, '
        '"reveal_budget": {"letters": 4, "words": 1}}'
    ),
    "vote_opened": (
        '{"type": "vote_opened", "seq": 30, "vote_id": 3, "player_id": "p1", '
        '"request": {"type": "reveal", "target": {"scope": "word", "row": 0, '
        '"column": 4, "clue_index": 0}}, "timeout_seconds": 20, '
        '"eligible_voters": 3}'
    ),
    "vote_closed": (
        '{"type": "vote_closed", "seq": 31, "vote_id": 3, "outcome": "passed", '
        '"yes_votes": 2, "eligible_voters": 3}'
    ),
    "flag_changed": (
        '{"type": "flag_changed", "seq": 15, "player_id": "p2", '
        '"clue": {"row": 0, "column": 3, "clue_index": 0}}'
    ),
    "chat_message": (
        '{"type": "chat_message", "seq": 16, "player_id": "p2", '
        '"text": "IDES, je crois"}'
    ),
    "reaction": (
        '{"type": "reaction", "player_id": "p2", "clue": {"row": 0, '
        '"column": 3, "clue_index": 0}, "reaction": "wow"}'
    ),
    "settings_changed": (
        '{"type": "settings_changed", "seq": 5, "player_id": "p1", '
        '"settings": SETTINGS, "reveal_budget": {"letters": 5, "words": 1}}'
    ),
    "host_changed": '{"type": "host_changed", "seq": 50, "player_id": "p2"}',
    "player_muted": (
        '{"type": "player_muted", "seq": 51, "player_id": "p2", "muted": true}'
    ),
    "grid_solved": '{"type": "grid_solved", "seq": 60, "elapsed_ms": 754000}',
    "grid_full_wrong": '{"type": "grid_full_wrong", "seq": 59}',
    "error": (
        '{"type": "error", "code": "cell_locked", '
        '"message": "cell (1, 0) is locked"}'
    ),
}

# Class names of the client table and of the server table.
CLIENT_CLASSES: dict[str, str] = {
    "join": "Join",
    "select_cell": "SelectCell",
    "edit_letter": "EditLetter",
    "erase": "Erase",
    "pencil_edit": "PencilEdit",
    "confirm_pencil": "ConfirmPencil",
    "check": "Check",
    "reveal": "Reveal",
    "vote": "Vote",
    "flag": "Flag",
    "chat": "Chat",
    "react": "React",
    "undo": "Undo",
    "remove_player": "RemovePlayer",
    "lock_room": "LockRoom",
    "change_settings": "ChangeSettings",
    "mute_player": "MutePlayer",
}
SERVER_CLASSES: dict[str, str] = {
    "snapshot": "Snapshot",
    "letter_changed": "LetterChanged",
    "cell_locked": "CellLocked",
    "player_joined": "PlayerJoined",
    "player_left": "PlayerLeft",
    "player_state_changed": "PlayerStateChanged",
    "selection_moved": "SelectionMoved",
    "check_result": "CheckResult",
    "reveal_result": "RevealResult",
    "vote_opened": "VoteOpened",
    "vote_closed": "VoteClosed",
    "flag_changed": "FlagChanged",
    "chat_message": "ChatMessage",
    "reaction": "ReactionShown",
    "settings_changed": "SettingsChanged",
    "host_changed": "HostChanged",
    "player_muted": "PlayerMuted",
    "grid_solved": "GridSolved",
    "grid_full_wrong": "GridFullWrong",
    "error": "ErrorMessage",
}
SEQ_TYPES: list[str] = [
    "letter_changed",
    "cell_locked",
    "player_joined",
    "player_left",
    "player_state_changed",
    "check_result",
    "reveal_result",
    "vote_opened",
    "vote_closed",
    "flag_changed",
    "chat_message",
    "settings_changed",
    "host_changed",
    "player_muted",
    "grid_solved",
    "grid_full_wrong",
]
NO_SEQ_TYPES: list[str] = ["selection_moved", "reaction", "error"]
ERROR_CODES: list[str] = [
    "invalid_message",
    "not_joined",
    "room_full",
    "room_locked",
    "removed",
    "not_host",
    "not_a_letter_cell",
    "cell_locked",
    "help_disabled",
    "budget_exhausted",
    "vote_in_progress",
    "no_open_vote",
    "muted",
    "rate_limited",
    "nothing_to_undo",
    "grid_solved",
]


def expand(text: str) -> str:
    """Replace the PLAYER_P2 and SETTINGS placeholders of a server example."""
    with_player = text.replace("PLAYER_P2", PLAYER_P2)
    return with_player.replace("SETTINGS", SETTINGS)


def client_text(type_name: str) -> str:
    """Return the JSON text of a client example."""
    return CLIENT_EXAMPLES[type_name]


def server_text(type_name: str) -> str:
    """Return the JSON text of a server example, placeholders replaced."""
    return expand(SERVER_EXAMPLES[type_name])


def client_data(type_name: str) -> JsonData:
    """Return a client example as a fresh dictionary."""
    return json.loads(client_text(type_name))


def server_data(type_name: str) -> JsonData:
    """Return a server example as a fresh dictionary."""
    return json.loads(server_text(type_name))


def protocol_class(class_name: str) -> type:
    """Return a class of nock.protocol by its name."""
    import nock.protocol

    return getattr(nock.protocol, class_name)


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


def snapshot_with(**changes: object) -> str:  # raw JSON values: any
    """Return the snapshot example with some top-level fields replaced."""
    data = server_data("snapshot")
    data.update(changes)
    return json.dumps(data)


def without_key(data: JsonData, key: str) -> JsonData:
    """Return a copy of a dictionary without one key."""
    copied = copy.deepcopy(data)
    del copied[key]
    return copied


def with_key(data: JsonData, key: str, value: object) -> JsonData:
    """Return a copy of a dictionary with one key set (value: raw JSON, any)."""
    copied = copy.deepcopy(data)
    copied[key] = value
    return copied


def edit_letter_with(letter: object) -> str:  # raw JSON value: any
    """Return the edit_letter example with another letter."""
    return json.dumps(with_key(client_data("edit_letter"), "letter", letter))


def pencil_edit_with(letter: object) -> str:  # raw JSON value: any
    """Return the pencil_edit example with another letter."""
    return json.dumps(with_key(client_data("pencil_edit"), "letter", letter))


def join_with(nickname: str) -> str:
    """Return the join example with another nickname."""
    return json.dumps(with_key(client_data("join"), "nickname", nickname))


def chat_with(text: str) -> str:
    """Return the chat example with another text."""
    return json.dumps(with_key(client_data("chat"), "text", text))


def build_fx01_grid(fx01_text: str) -> Grid:
    """Build the FX-01 reference grid."""
    return Grid.model_validate_json(fx01_text)


# ---- AC-1 ---------------------------------------------------------------


@pytest.mark.parametrize("type_name", list(CLIENT_EXAMPLES))
def test_ac1_client_example_parses_to_its_class(type_name: str) -> None:
    message = parse_client_message(client_text(type_name))

    assert type(message) is protocol_class(CLIENT_CLASSES[type_name])


@pytest.mark.parametrize("type_name", list(CLIENT_EXAMPLES))
def test_ac1_client_example_round_trips(type_name: str) -> None:
    message = parse_client_message(client_text(type_name))

    again = parse_client_message(message.model_dump_json())

    assert again == message
    assert type(again) is type(message)


def test_ac1_client_example_count_is_seventeen() -> None:
    assert len(CLIENT_EXAMPLES) == 17
    assert len(CLIENT_CLASSES) == 17


def test_ac1_client_parser_accepts_bytes() -> None:
    message = parse_client_message(client_text("undo").encode("utf-8"))

    assert type(message) is protocol_class("Undo")


def test_ac1_join_without_resume_token_defaults_to_none() -> None:
    message = parse_client_message('{"type": "join", "nickname": "Ana"}')

    assert message == Join(nickname="Ana", resume_token=None)


def test_ac1_cell_edits_without_base_seq_default_to_none() -> None:
    message = parse_client_message(
        '{"type": "edit_letter", "row": 1, "column": 0, "letter": "T"}'
    )

    assert message == EditLetter(row=1, column=0, letter="T", base_seq=None)


def test_ac1_base_seq_zero_is_accepted() -> None:
    text = json.dumps(with_key(client_data("erase"), "base_seq", 0))

    message = parse_client_message(text)

    assert isinstance(message, Erase)
    assert message.base_seq == 0


@pytest.mark.parametrize(
    "type_name", ["edit_letter", "pencil_edit", "confirm_pencil", "erase"]
)
def test_ac1_base_seq_zero_is_accepted_on_every_cell_edit(type_name: str) -> None:
    text = json.dumps(with_key(client_data(type_name), "base_seq", 0))

    message = parse_client_message(text)

    assert type(message) is protocol_class(CLIENT_CLASSES[type_name])
    assert message.model_dump()["base_seq"] == 0


def test_ac1_flag_with_null_clue_round_trips() -> None:
    message = parse_client_message('{"type": "flag", "clue": null}')

    assert message == Flag(clue=None)
    assert parse_client_message(message.model_dump_json()) == message


def test_ac1_chat_with_markup_round_trips_unchanged() -> None:
    message = parse_client_message('{"type": "chat", "text": "<b>salut</b>"}')

    assert message == Chat(text="<b>salut</b>")
    assert parse_client_message(message.model_dump_json()) == message


# ---- AC-2 ---------------------------------------------------------------


@pytest.mark.parametrize("type_name", list(SERVER_EXAMPLES))
def test_ac2_server_example_parses_to_its_class(type_name: str) -> None:
    message = parse_server_message(server_text(type_name))

    assert type(message) is protocol_class(SERVER_CLASSES[type_name])


@pytest.mark.parametrize("type_name", list(SERVER_EXAMPLES))
def test_ac2_server_example_round_trips(type_name: str) -> None:
    message = parse_server_message(server_text(type_name))

    again = parse_server_message(message.model_dump_json())

    assert again == message
    assert type(again) is type(message)


def test_ac2_server_example_count_is_twenty() -> None:
    assert len(SERVER_EXAMPLES) == 20
    assert len(SERVER_CLASSES) == 20


def test_ac2_server_parser_accepts_bytes() -> None:
    message = parse_server_message(server_text("host_changed").encode("utf-8"))

    assert type(message) is protocol_class("HostChanged")


def test_ac2_erased_letter_changed_parses() -> None:
    data = with_key(server_data("letter_changed"), "letter", None)

    message = parse_server_message(json.dumps(data))

    assert isinstance(message, LetterChanged)
    assert message.letter is None
    assert parse_server_message(message.model_dump_json()) == message


def test_ac2_snapshot_of_fx01_view_round_trips(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))
    typed_cell = LetterCellView(
        row=1,
        column=0,
        letter="T",
        pencil=False,
        author="p1",
        locked=False,
        revealed=False,
        wrong=False,
    )
    cells: list[ClueCellView | EmptyCellView | LetterCellView] = []
    for cell in view.cells:
        if cell.row == 1 and cell.column == 0:
            cells.append(typed_cell)
        else:
            cells.append(cell)
    grid = GridView(width=view.width, height=view.height, cells=tuple(cells))
    base = server_data("snapshot")
    base["grid"] = json.loads(grid.model_dump_json())

    snapshot = parse_server_message(json.dumps(base))

    assert type(snapshot) is Snapshot
    assert snapshot.grid == grid
    assert parse_server_message(snapshot.model_dump_json()) == snapshot


def test_ac2_snapshot_built_in_python_round_trips(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))
    base = server_data("snapshot")
    base["grid"] = json.loads(view.model_dump_json())
    snapshot = parse_server_message(json.dumps(base))

    again = parse_server_message(snapshot.model_dump_json())

    assert again == snapshot
    assert isinstance(again, Snapshot)
    assert again.grid.width == 5
    assert len(again.grid.cells) == 25


def test_ac2_empty_reveal_budget_is_valid() -> None:
    data = with_key(
        server_data("reveal_result"), "reveal_budget", {"letters": 0, "words": 0}
    )

    message = parse_server_message(json.dumps(data))

    assert isinstance(message, RevealResult)
    assert message.reveal_budget.letters == 0
    assert message.reveal_budget.words == 0


def test_ac2_cross_field_rules_are_not_checked() -> None:
    erased_pencil = with_key(server_data("letter_changed"), "letter", None)
    erased_pencil["pencil"] = True
    stranger_snapshot = server_data("snapshot")
    stranger_snapshot["you"] = "p99"

    erased_message = parse_server_message(json.dumps(erased_pencil))
    snapshot = parse_server_message(json.dumps(stranger_snapshot))

    assert isinstance(erased_message, LetterChanged)
    assert isinstance(snapshot, Snapshot)
    assert erased_message.letter is None
    assert erased_message.pencil is True
    assert snapshot.you == "p99"


def test_ac2_grid_view_with_duplicate_positions_parses() -> None:
    cell = {"type": "empty", "row": 0, "column": 0}
    data = {"width": 2, "height": 1, "cells": [cell, cell]}

    view = GridView.model_validate(data)

    assert view.cells == (
        EmptyCellView(row=0, column=0),
        EmptyCellView(row=0, column=0),
    )


def test_ac2_grid_view_with_a_position_outside_the_grid_parses() -> None:
    cell = {"type": "empty", "row": 5, "column": 7}
    data = {"width": 2, "height": 1, "cells": [cell]}

    view = GridView.model_validate(data)

    assert view.cells == (EmptyCellView(row=5, column=7),)


def test_ac2_snapshot_with_an_inconsistent_grid_view_parses() -> None:
    data = server_data("snapshot")
    stray_cell = {"type": "empty", "row": 9, "column": 9}
    data["grid"]["cells"] = [stray_cell, stray_cell]

    message = parse_server_message(json.dumps(data))

    assert isinstance(message, Snapshot)
    assert len(message.grid.cells) == 2
    assert parse_server_message(message.model_dump_json()) == message


# ---- AC-3 ---------------------------------------------------------------


def test_ac3_edit_letter_carries_its_values() -> None:
    message = parse_client_message(client_text("edit_letter"))

    assert message == EditLetter(row=1, column=0, letter="T", base_seq=None)


def test_ac3_vote_opened_request_is_a_word_reveal() -> None:
    message = parse_server_message(server_text("vote_opened"))

    assert isinstance(message, VoteOpened)
    assert message.request == Reveal(target=WordTarget(row=0, column=4, clue_index=0))
    assert message.seq == 30
    assert message.vote_id == 3
    assert message.player_id == "p1"
    assert message.timeout_seconds == 20
    assert message.eligible_voters == 3


def test_ac3_check_result_target_is_the_grid() -> None:
    message = parse_server_message(server_text("check_result"))

    assert isinstance(message, CheckResult)
    assert message.target == GridTarget()
    assert [(c.row, c.column) for c in message.correct] == [(1, 0)]
    assert [(c.row, c.column) for c in message.wrong] == [(1, 1)]


def test_ac3_flag_with_null_clue_carries_none() -> None:
    message = parse_client_message('{"type": "flag", "clue": null}')

    assert isinstance(message, Flag)
    assert message.clue is None


def test_ac3_flag_example_carries_the_clue() -> None:
    message = parse_client_message(client_text("flag"))

    assert isinstance(message, Flag)
    assert message.clue is not None
    assert (message.clue.row, message.clue.column) == (0, 0)
    assert message.clue.clue_index == 1


def test_ac3_check_example_carries_a_word_target() -> None:
    message = parse_client_message(client_text("check"))

    assert isinstance(message, Check)
    assert message.target == WordTarget(row=0, column=2, clue_index=0)


def test_ac3_snapshot_example_carries_its_values() -> None:
    message = parse_server_message(server_text("snapshot"))

    assert isinstance(message, Snapshot)
    assert message.seq == 0
    assert message.you == "p1"
    assert message.resume_token == "r7Kq2mXo9vB4tY1zW8nP"
    assert message.grid.width == 2
    assert message.grid.height == 1
    assert len(message.players) == 1
    assert message.players[0].player_id == "p2"
    assert message.players[0].nickname == "Bruno"
    assert message.players[0].colour == 1
    assert message.settings.help_mode == "free"
    assert message.settings.locked is False
    assert message.reveal_budget.letters == 5
    assert message.reveal_budget.words == 1
    assert message.open_vote is None
    assert message.timer_elapsed_ms == 0
    assert message.timer_running is False
    assert message.solved is False


def test_ac3_snapshot_grid_cells_are_typed() -> None:
    message = parse_server_message(server_text("snapshot"))

    assert isinstance(message, Snapshot)
    clue_cell, letter_cell = message.grid.cells
    assert clue_cell.type == "clue"
    assert clue_cell.clues == (ClueView(text="Note", arrow=Arrow.RIGHT),)
    assert letter_cell == LetterCellView(
        row=0,
        column=1,
        letter=None,
        pencil=False,
        author=None,
        locked=False,
        revealed=False,
        wrong=False,
    )


def test_ac3_values_of_other_examples() -> None:
    erase = parse_client_message(client_text("erase"))
    chat = parse_server_message(server_text("chat_message"))
    solved = parse_server_message(server_text("grid_solved"))
    error = parse_server_message(server_text("error"))

    assert isinstance(erase, Erase)
    assert isinstance(chat, ChatMessage)
    assert isinstance(solved, GridSolved)
    assert isinstance(error, ErrorMessage)
    assert (erase.row, erase.column, erase.base_seq) == (1, 0, 7)
    assert chat.text == "IDES, je crois"
    assert chat.seq == 16
    assert solved.elapsed_ms == 754000
    assert error.code == "cell_locked"
    assert error.message == "cell (1, 0) is locked"


# ---- AC-4 ---------------------------------------------------------------

UNKNOWN_TYPE = '{"type": "teleport", "row": 1, "column": 0}'
MISSING_TYPE = '{"row": 1, "column": 0, "letter": "T"}'


@pytest.mark.parametrize("parser", [parse_client_message, parse_server_message])
@pytest.mark.parametrize("text", [UNKNOWN_TYPE, MISSING_TYPE])
def test_ac4_unknown_or_missing_type_is_rejected(parser: Parser, text: str) -> None:
    with pytest.raises(ValidationError):
        parser(text)


def test_ac4_server_message_is_rejected_by_the_client_parser() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(server_text("snapshot"))


def test_ac4_client_message_is_rejected_by_the_server_parser() -> None:
    with pytest.raises(ValidationError):
        parse_server_message(client_text("join"))


@pytest.mark.parametrize("type_name", list(SERVER_EXAMPLES))
def test_ac4_every_server_example_is_rejected_by_the_client_parser(
    type_name: str,
) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(server_text(type_name))


@pytest.mark.parametrize("type_name", list(CLIENT_EXAMPLES))
def test_ac4_every_client_example_is_rejected_by_the_server_parser(
    type_name: str,
) -> None:
    with pytest.raises(ValidationError):
        parse_server_message(client_text(type_name))


# ---- AC-5 ---------------------------------------------------------------


def with_target_without_scope() -> str:
    """Return the check example whose target has no scope."""
    data = client_data("check")
    del data["target"]["scope"]
    return json.dumps(data)


def with_flag_clue_index(clue_index: int) -> str:
    """Return the flag example with another clue_index."""
    data = client_data("flag")
    data["clue"]["clue_index"] = clue_index
    return json.dumps(data)


def with_negative_letters() -> str:
    """Return the change_settings example with a negative letters budget."""
    data = client_data("change_settings")
    data["reveal_budget"]["letters"] = -1
    return json.dumps(data)


def with_player_colour(colour: int) -> str:
    """Return the player_joined example with another colour."""
    data = server_data("player_joined")
    data["player"]["colour"] = colour
    return json.dumps(data)


def edit_with_row(row: object) -> str:  # raw JSON value: any
    """Return the edit_letter example with another row."""
    return json.dumps(with_key(client_data("edit_letter"), "row", row))


def erase_with_base_seq(base_seq: object) -> str:  # raw JSON value: any
    """Return the erase example with another base_seq."""
    return json.dumps(with_key(client_data("erase"), "base_seq", base_seq))


MALFORMED_CLIENT_TEXTS: dict[str, str] = {
    "not_json": "not json",
    "empty_text": "",
    "json_array": "[]",
    "missing_column": json.dumps(without_key(client_data("edit_letter"), "column")),
    "negative_row": edit_with_row(-1),
    "string_row": edit_with_row("1"),
    "float_row": '{"type": "edit_letter", "row": 1.0, "column": 0, "letter": "T"}',
    "boolean_row": '{"type": "edit_letter", "row": true, "column": 0, "letter": "T"}',
    "vote_yes_as_integer": json.dumps(with_key(client_data("vote"), "yes", 1)),
    "vote_yes_as_string": json.dumps(with_key(client_data("vote"), "yes", "true")),
    "vote_id_zero": json.dumps(with_key(client_data("vote"), "vote_id", 0)),
    "undo_with_extra_field": json.dumps(
        with_key(client_data("undo"), "player_id", "p1")
    ),
    "flag_clue_index_two": with_flag_clue_index(2),
    "flag_clue_index_negative": with_flag_clue_index(-1),
    "remove_player_empty_id": json.dumps(
        with_key(client_data("remove_player"), "player_id", "")
    ),
    "remove_player_id_with_space": json.dumps(
        with_key(client_data("remove_player"), "player_id", "p 2")
    ),
    "negative_letters": with_negative_letters(),
    "check_target_without_scope": with_target_without_scope(),
    "negative_base_seq": erase_with_base_seq(-1),
    "string_base_seq": erase_with_base_seq("7"),
    "unknown_extra_field": json.dumps(with_key(client_data("lock_room"), "x", 1)),
    "lock_room_locked_as_integer": json.dumps(
        with_key(client_data("lock_room"), "locked", 1)
    ),
}


@pytest.mark.parametrize(
    "text", list(MALFORMED_CLIENT_TEXTS.values()), ids=list(MALFORMED_CLIENT_TEXTS)
)
def test_ac5_malformed_client_message_is_rejected(text: str) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(text)


@pytest.mark.parametrize("colour", [8, -1])
def test_ac5_player_colour_out_of_palette_is_rejected(colour: int) -> None:
    with pytest.raises(ValidationError):
        parse_server_message(with_player_colour(colour))


@pytest.mark.parametrize("colour", [0, 7])
def test_ac5_player_colour_at_palette_edges_parses(colour: int) -> None:
    message = parse_server_message(with_player_colour(colour))

    assert isinstance(message, PlayerJoined)
    assert message.player.colour == colour


def test_ac5_server_message_with_unknown_field_is_rejected() -> None:
    data = with_key(server_data("host_changed"), "extra", True)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac5_server_boolean_as_integer_is_rejected() -> None:
    data = with_key(server_data("player_muted"), "muted", 1)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac5_server_seq_as_float_is_rejected() -> None:
    text = server_text("host_changed").replace('"seq": 50', '"seq": 50.0')

    with pytest.raises(ValidationError):
        parse_server_message(text)


def test_ac5_server_text_message_cannot_be_built_from_a_number() -> None:
    data = with_key(server_data("chat_message"), "text", 12)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac5_server_not_json_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_server_message("not json")


def test_ac5_resume_token_too_short_is_rejected() -> None:
    data = with_key(client_data("join"), "resume_token", "a" * 15)

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


@pytest.mark.parametrize("length", [16, 128])
def test_ac5_resume_token_length_edges_parse(length: int) -> None:
    token = "a" * length
    data = with_key(client_data("join"), "resume_token", token)

    message = parse_client_message(json.dumps(data))

    assert isinstance(message, Join)
    assert message.resume_token == token


def test_ac5_resume_token_too_long_is_rejected() -> None:
    data = with_key(client_data("join"), "resume_token", "a" * 129)

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac5_resume_token_with_bad_character_is_rejected() -> None:
    data = with_key(client_data("join"), "resume_token", "a" * 15 + "!")

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac5_player_id_of_64_characters_parses_and_65_is_rejected() -> None:
    long_id = with_key(client_data("remove_player"), "player_id", "a" * 64)
    too_long = with_key(client_data("remove_player"), "player_id", "a" * 65)

    message = parse_client_message(json.dumps(long_id))

    assert isinstance(message, RemovePlayer)
    assert message.player_id == "a" * 64
    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(too_long))


def test_ac5_player_id_allows_dash_and_underscore() -> None:
    data = with_key(client_data("remove_player"), "player_id", "a_b-C9")

    message = parse_client_message(json.dumps(data))

    assert isinstance(message, RemovePlayer)
    assert message.player_id == "a_b-C9"


def test_ac5_vote_id_one_parses() -> None:
    data = with_key(client_data("vote"), "vote_id", 1)

    message = parse_client_message(json.dumps(data))

    assert isinstance(message, Vote)
    assert message.vote_id == 1


def test_ac5_flag_clue_index_one_parses() -> None:
    message = parse_client_message(with_flag_clue_index(1))

    assert isinstance(message, Flag)
    assert message.clue is not None
    assert message.clue.clue_index == 1


def test_ac5_vote_opened_timeout_and_voters_must_be_at_least_one() -> None:
    zero_timeout = with_key(server_data("vote_opened"), "timeout_seconds", 0)
    zero_voters = with_key(server_data("vote_opened"), "eligible_voters", 0)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(zero_timeout))
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(zero_voters))


def test_ac5_vote_closed_negative_yes_votes_is_rejected() -> None:
    data = with_key(server_data("vote_closed"), "yes_votes", -1)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac5_client_message_cannot_carry_an_event_seq() -> None:
    data = with_key(client_data("edit_letter"), "seq", 3)

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


PathStep = str | int
FieldPath = tuple[PathStep, ...]
# (side, example type, path of one field inside that example)
FieldCase = tuple[str, str, FieldPath]

BOOLEAN_FIELDS: list[FieldCase] = [
    ("client", "vote", ("yes",)),
    ("client", "lock_room", ("locked",)),
    ("client", "mute_player", ("muted",)),
    ("server", "letter_changed", ("pencil",)),
    ("server", "cell_locked", ("revealed",)),
    ("server", "player_muted", ("muted",)),
    ("server", "player_joined", ("player", "is_host")),
    ("server", "player_joined", ("player", "muted")),
    ("server", "settings_changed", ("settings", "locked")),
    ("server", "snapshot", ("settings", "locked")),
    ("server", "snapshot", ("players", 0, "is_host")),
    ("server", "snapshot", ("grid", "cells", 1, "pencil")),
    ("server", "snapshot", ("grid", "cells", 1, "locked")),
    ("server", "snapshot", ("grid", "cells", 1, "revealed")),
    ("server", "snapshot", ("grid", "cells", 1, "wrong")),
    ("server", "snapshot", ("timer_running",)),
    ("server", "snapshot", ("solved",)),
]

INTEGER_FIELDS: list[FieldCase] = [
    ("client", "edit_letter", ("row",)),
    ("client", "edit_letter", ("column",)),
    ("client", "erase", ("base_seq",)),
    ("client", "vote", ("vote_id",)),
    ("client", "flag", ("clue", "clue_index")),
    ("client", "change_settings", ("reveal_budget", "letters")),
    ("client", "change_settings", ("reveal_budget", "words")),
    ("server", "vote_opened", ("vote_id",)),
    ("server", "vote_opened", ("timeout_seconds",)),
    ("server", "vote_opened", ("eligible_voters",)),
    ("server", "vote_closed", ("vote_id",)),
    ("server", "vote_closed", ("yes_votes",)),
    ("server", "vote_closed", ("eligible_voters",)),
    ("server", "grid_solved", ("elapsed_ms",)),
    ("server", "player_joined", ("player", "colour")),
    ("server", "reveal_result", ("reveal_budget", "letters")),
    ("server", "settings_changed", ("reveal_budget", "words")),
    ("server", "settings_changed", ("settings", "reveal_budget", "letters")),
    ("server", "check_result", ("correct", 0, "row")),
    ("server", "selection_moved", ("selection", "column")),
    ("server", "snapshot", ("seq",)),
    ("server", "snapshot", ("timer_elapsed_ms",)),
    ("server", "snapshot", ("reveal_budget", "letters")),
    ("server", "snapshot", ("reveal_budget", "words")),
    ("server", "snapshot", ("settings", "reveal_budget", "words")),
    ("server", "snapshot", ("grid", "width")),
    ("server", "snapshot", ("grid", "height")),
    ("server", "snapshot", ("grid", "cells", 1, "column")),
    ("client", "select_cell", ("row",)),
    ("client", "select_cell", ("column",)),
    ("client", "erase", ("row",)),
    ("client", "erase", ("column",)),
    ("client", "pencil_edit", ("row",)),
    ("client", "pencil_edit", ("column",)),
    ("client", "confirm_pencil", ("row",)),
    ("client", "confirm_pencil", ("column",)),
    ("client", "check", ("target", "row")),
    ("client", "check", ("target", "column")),
    ("client", "check", ("target", "clue_index")),
    ("client", "reveal", ("target", "row")),
    ("client", "reveal", ("target", "column")),
    ("client", "flag", ("clue", "row")),
    ("client", "flag", ("clue", "column")),
    ("client", "react", ("clue", "row")),
    ("client", "react", ("clue", "column")),
    ("client", "react", ("clue", "clue_index")),
    ("server", "letter_changed", ("row",)),
    ("server", "letter_changed", ("column",)),
    ("server", "cell_locked", ("row",)),
    ("server", "cell_locked", ("column",)),
    ("server", "check_result", ("correct", 0, "column")),
    ("server", "check_result", ("wrong", 0, "row")),
    ("server", "check_result", ("wrong", 0, "column")),
    ("server", "reveal_result", ("target", "row")),
    ("server", "reveal_result", ("target", "column")),
    ("server", "vote_opened", ("request", "target", "row")),
    ("server", "vote_opened", ("request", "target", "column")),
    ("server", "vote_opened", ("request", "target", "clue_index")),
    ("server", "selection_moved", ("selection", "row")),
    ("server", "flag_changed", ("clue", "row")),
    ("server", "flag_changed", ("clue", "column")),
    ("server", "flag_changed", ("clue", "clue_index")),
    ("server", "snapshot", ("grid", "cells", 0, "row")),
    ("server", "snapshot", ("grid", "cells", 0, "column")),
    ("server", "snapshot", ("grid", "cells", 1, "row")),
]
# Every room-changing event carries a strict seq.
for seq_type_name in SEQ_TYPES:
    INTEGER_FIELDS.append(("server", seq_type_name, ("seq",)))


def field_case_ids(cases: list[FieldCase]) -> list[str]:
    """Return a readable test id for each field case."""
    ids = []
    for _side, type_name, path in cases:
        steps = ".".join(str(step) for step in path)
        ids.append(f"{type_name}-{steps}")
    return ids


def example_data(side: str, type_name: str) -> JsonData:
    """Return the client or server example of a type as a dictionary."""
    if side == "client":
        return client_data(type_name)
    return server_data(type_name)


def parse_on_side(side: str, text: str) -> BaseModel:
    """Parse a text with the client or the server parser."""
    if side == "client":
        return parse_client_message(text)
    return parse_server_message(text)


def value_at(data: JsonData, path: FieldPath) -> object:  # raw JSON value
    """Return the value found at a path of keys and indexes."""
    node: Any = data
    for step in path:
        node = node[step]
    return node


def with_value_at(
    data: JsonData, path: FieldPath, value: object  # raw JSON value: any
) -> JsonData:
    """Return a deep copy of the data with the value at one path replaced."""
    copied = copy.deepcopy(data)
    parent: Any = copied
    for step in path[:-1]:
        parent = parent[step]
    parent[path[-1]] = value
    return copied


def assert_field_rejects(case: FieldCase, value: object) -> None:  # raw JSON: any
    """Check that changing only the field of the case to a value is an error."""
    side, type_name, path = case
    data = with_value_at(example_data(side, type_name), path, value)

    with pytest.raises(ValidationError):
        parse_on_side(side, json.dumps(data))


def assert_server_rejects(path: FieldPath, value: object) -> None:  # raw JSON: any
    """Check that changing one field of the snapshot example is an error."""
    data = with_value_at(server_data("snapshot"), path, value)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def assert_server_accepts(path: FieldPath, value: object) -> Snapshot:  # raw: any
    """Check that changing one field of the snapshot example still parses."""
    data = with_value_at(server_data("snapshot"), path, value)

    message = parse_server_message(json.dumps(data))

    assert isinstance(message, Snapshot)
    return message


@pytest.mark.parametrize("case", BOOLEAN_FIELDS, ids=field_case_ids(BOOLEAN_FIELDS))
def test_ac5_every_boolean_field_rejects_a_number(case: FieldCase) -> None:
    side, type_name, path = case
    current = value_at(example_data(side, type_name), path)

    assert isinstance(current, bool)
    assert_field_rejects(case, int(current))


@pytest.mark.parametrize("case", BOOLEAN_FIELDS, ids=field_case_ids(BOOLEAN_FIELDS))
def test_ac5_every_boolean_field_rejects_a_string(case: FieldCase) -> None:
    side, type_name, path = case
    current = value_at(example_data(side, type_name), path)

    assert_field_rejects(case, str(current).lower())


@pytest.mark.parametrize("case", INTEGER_FIELDS, ids=field_case_ids(INTEGER_FIELDS))
def test_ac5_every_integer_field_rejects_a_string(case: FieldCase) -> None:
    side, type_name, path = case
    current = value_at(example_data(side, type_name), path)

    assert isinstance(current, int)
    assert_field_rejects(case, str(current))


@pytest.mark.parametrize("case", INTEGER_FIELDS, ids=field_case_ids(INTEGER_FIELDS))
def test_ac5_every_integer_field_rejects_a_float(case: FieldCase) -> None:
    side, type_name, path = case
    current = value_at(example_data(side, type_name), path)

    assert isinstance(current, int)
    assert_field_rejects(case, float(current))


@pytest.mark.parametrize("bad_seq", ["1", 1.0, True])
@pytest.mark.parametrize("type_name", ["edit_letter", "pencil_edit", "confirm_pencil"])
def test_ac5_base_seq_must_be_a_strict_integer(type_name: str, bad_seq: object) -> None:
    data = with_key(client_data(type_name), "base_seq", bad_seq)

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


@pytest.mark.parametrize("coordinate", ["row", "column"])
@pytest.mark.parametrize("bad_value", ["1", 1.0, True])
def test_ac5_empty_cell_view_position_must_be_a_strict_integer(
    coordinate: str, bad_value: object
) -> None:
    cell: dict[str, object] = {"type": "empty", "row": 1, "column": 1}
    cell[coordinate] = bad_value
    assert_server_rejects(("grid", "cells", 1), cell)


@pytest.mark.parametrize("size_field", ["width", "height"])
def test_ac5_grid_view_size_of_zero_is_rejected(size_field: str) -> None:
    assert_server_rejects(("grid", size_field), 0)


@pytest.mark.parametrize("size_field", ["width", "height"])
def test_ac5_grid_view_size_of_one_parses(size_field: str) -> None:
    message = assert_server_accepts(("grid", size_field), 1)

    assert getattr(message.grid, size_field) == 1


def test_ac5_vote_closed_with_zero_eligible_voters_is_rejected() -> None:
    data = with_key(server_data("vote_closed"), "eligible_voters", 0)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac5_vote_closed_with_one_eligible_voter_parses() -> None:
    data = with_key(server_data("vote_closed"), "eligible_voters", 1)

    message = parse_server_message(json.dumps(data))

    assert message.model_dump()["eligible_voters"] == 1


def test_ac5_vote_opened_with_one_second_and_one_voter_parses() -> None:
    data = with_key(server_data("vote_opened"), "timeout_seconds", 1)
    data["eligible_voters"] = 1

    message = parse_server_message(json.dumps(data))

    assert isinstance(message, VoteOpened)
    assert message.timeout_seconds == 1
    assert message.eligible_voters == 1


@pytest.mark.parametrize(
    "type_name", ["edit_letter", "pencil_edit", "confirm_pencil", "erase"]
)
def test_ac5_negative_base_seq_is_rejected_on_every_cell_edit(type_name: str) -> None:
    data = with_key(client_data(type_name), "base_seq", -1)

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac5_clue_view_text_cannot_be_empty() -> None:
    assert_server_rejects(("grid", "cells", 0, "clues", 0, "text"), "")


def test_ac5_clue_view_text_of_one_character_parses() -> None:
    message = assert_server_accepts(("grid", "cells", 0, "clues", 0, "text"), "N")

    clue_cell = message.grid.cells[0]
    assert isinstance(clue_cell, ClueCellView)
    assert clue_cell.clues[0].text == "N"


CLUE_PATH: FieldPath = ("grid", "cells", 0, "clues")
FIRST_CLUE = {"text": "Note", "arrow": "right"}
SECOND_CLUE = {"text": "Autre", "arrow": "down"}


def test_ac5_clue_cell_view_without_clues_is_rejected() -> None:
    assert_server_rejects(CLUE_PATH, [])


def test_ac5_clue_cell_view_with_three_clues_is_rejected() -> None:
    assert_server_rejects(CLUE_PATH, [FIRST_CLUE, SECOND_CLUE, SECOND_CLUE])


def test_ac5_clue_cell_view_with_two_clues_parses() -> None:
    message = assert_server_accepts(CLUE_PATH, [FIRST_CLUE, SECOND_CLUE])

    clue_cell = message.grid.cells[0]
    assert isinstance(clue_cell, ClueCellView)
    assert clue_cell.clues == (
        ClueView(text="Note", arrow=Arrow.RIGHT),
        ClueView(text="Autre", arrow=Arrow.DOWN),
    )


BAD_PLAYER_IDS: list[str] = ["", "p 2", "a" * 65, "é", "p!"]
PLAYER_ID_PATHS: dict[str, FieldPath] = {
    "author": ("grid", "cells", 1, "author"),
    "you": ("you",),
}


@pytest.mark.parametrize("path_name", list(PLAYER_ID_PATHS))
@pytest.mark.parametrize("player_id", BAD_PLAYER_IDS)
def test_ac5_snapshot_player_ids_follow_the_pattern(
    path_name: str, player_id: str
) -> None:
    assert_server_rejects(PLAYER_ID_PATHS[path_name], player_id)


@pytest.mark.parametrize("path_name", list(PLAYER_ID_PATHS))
@pytest.mark.parametrize("player_id", ["p1", "a_b-C9", "a" * 64])
def test_ac5_snapshot_player_ids_accept_valid_ids(
    path_name: str, player_id: str
) -> None:
    message = assert_server_accepts(PLAYER_ID_PATHS[path_name], player_id)

    if path_name == "you":
        assert message.you == player_id
    else:
        letter_cell = message.grid.cells[1]
        assert isinstance(letter_cell, LetterCellView)
        assert letter_cell.author == player_id


def test_ac5_flag_without_clue_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_client_message('{"type": "flag"}')


@pytest.mark.parametrize("field", ["resume_token", "flags"])
def test_ac5_snapshot_without_a_required_field_is_rejected(field: str) -> None:
    data = without_key(server_data("snapshot"), field)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac5_player_view_without_selection_is_rejected() -> None:
    data = server_data("player_joined")
    del data["player"]["selection"]

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


# ---- AC-6 ---------------------------------------------------------------


@pytest.mark.parametrize("letter", ["A", "Z", "M"])
def test_ac6_edit_letter_accepts_uppercase_letter(letter: str) -> None:
    message = parse_client_message(edit_letter_with(letter))

    assert isinstance(message, EditLetter)
    assert message.letter == letter


@pytest.mark.parametrize("letter", ["A", "Z", "M"])
def test_ac6_pencil_edit_accepts_uppercase_letter(letter: str) -> None:
    message = parse_client_message(pencil_edit_with(letter))

    assert isinstance(message, PencilEdit)
    assert message.letter == letter


BAD_LETTERS: list[Any] = ["a", "É", "AB", "", "1", " ", None, "A\n", "z", "[", "@"]


@pytest.mark.parametrize("letter", BAD_LETTERS)
def test_ac6_edit_letter_rejects_bad_letter(letter: object) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(edit_letter_with(letter))


@pytest.mark.parametrize("letter", BAD_LETTERS)
def test_ac6_pencil_edit_rejects_bad_letter(letter: object) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(pencil_edit_with(letter))


def test_ac6_edit_letter_without_letter_is_rejected() -> None:
    data = without_key(client_data("edit_letter"), "letter")

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac6_letter_changed_rejects_lowercase() -> None:
    data = with_key(server_data("letter_changed"), "letter", "a")

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac6_cell_locked_rejects_lowercase_and_null() -> None:
    lowercase = with_key(server_data("cell_locked"), "letter", "t")
    null_letter = with_key(server_data("cell_locked"), "letter", None)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(lowercase))
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(null_letter))


def test_ac6_letter_cell_view_rejects_lowercase() -> None:
    data = server_data("snapshot")
    data["grid"]["cells"][1]["letter"] = "t"

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac6_letter_cell_view_accepts_uppercase() -> None:
    data = server_data("snapshot")
    data["grid"]["cells"][1]["letter"] = "T"

    message = parse_server_message(json.dumps(data))

    assert isinstance(message, Snapshot)
    letter_cell = message.grid.cells[1]
    assert isinstance(letter_cell, LetterCellView)
    assert letter_cell.letter == "T"


# ---- AC-7 ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("sent", "expected"),
    [
        ("  Ana  ", "Ana"),
        ("Ana", "Ana"),
        ("Al", "Al"),
        ("  Al\t", "Al"),
        ("x" * 20, "x" * 20),
        ("  " + "x" * 20 + "  ", "x" * 20),
        ("Jean Luc", "Jean Luc"),
    ],
)
def test_ac7_nickname_is_trimmed_and_accepted(sent: str, expected: str) -> None:
    message = parse_client_message(join_with(sent))

    assert isinstance(message, Join)
    assert message.nickname == expected


@pytest.mark.parametrize("sent", ["A", "  A  ", "", "   ", "x" * 21, "  " + "x" * 21])
def test_ac7_nickname_outside_two_to_twenty_is_rejected(sent: str) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(join_with(sent))


def test_ac7_join_without_nickname_is_rejected() -> None:
    data = without_key(client_data("join"), "nickname")

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac7_player_view_nickname_uses_the_same_rule() -> None:
    too_long = server_data("player_joined")
    too_long["player"]["nickname"] = "x" * 21
    too_short = server_data("player_joined")
    too_short["player"]["nickname"] = "A"

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(too_long))
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(too_short))


# Code points written as escapes: a thumbs up with a skin tone is 2 code points,
# a family emoji (three people joined by two zero width joiners) is 5.
THUMBS_UP = "👍"
SKIN_TONE = "🏽"
FAMILY = "👨‍👩‍👧"


def test_ac7_emoji_of_two_code_points_counts_as_two() -> None:
    message = parse_client_message(join_with(THUMBS_UP + SKIN_TONE))

    assert isinstance(message, Join)
    assert message.nickname == THUMBS_UP + SKIN_TONE


def test_ac7_emoji_of_one_code_point_counts_as_one() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(join_with(THUMBS_UP))


def test_ac7_four_family_emoji_are_twenty_code_points() -> None:
    message = parse_client_message(join_with(FAMILY * 4))

    assert isinstance(message, Join)
    assert message.nickname == FAMILY * 4


def test_ac7_four_family_emoji_and_one_letter_are_twenty_one_code_points() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(join_with(FAMILY * 4 + "x"))


# ---- AC-8 ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("sent", "expected"),
    [
        ("a" * 280, "a" * 280),
        (" salut ", "salut"),
        ("a", "a"),
        ("  " + "a" * 280 + "  ", "a" * 280),
        ("<b>salut</b>", "<b>salut</b>"),
    ],
)
def test_ac8_chat_text_is_trimmed_and_accepted(sent: str, expected: str) -> None:
    message = parse_client_message(chat_with(sent))

    assert isinstance(message, Chat)
    assert message.text == expected


@pytest.mark.parametrize("sent", ["", " ", "   \t\n", "a" * 281, " " + "a" * 281])
def test_ac8_chat_text_outside_range_is_rejected(sent: str) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(chat_with(sent))


def test_ac8_chat_without_text_is_rejected() -> None:
    data = without_key(client_data("chat"), "text")

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac8_chat_markup_round_trips_unchanged() -> None:
    message = parse_client_message(chat_with("<b>salut</b>"))

    again = parse_client_message(message.model_dump_json())

    assert isinstance(again, Chat)
    assert again.text == "<b>salut</b>"


def test_ac8_server_chat_message_uses_the_same_rule() -> None:
    too_long = with_key(server_data("chat_message"), "text", "a" * 281)
    blank = with_key(server_data("chat_message"), "text", "  ")

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(too_long))
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(blank))


def test_ac8_fifty_six_family_emoji_are_280_code_points() -> None:
    message = parse_client_message(chat_with(FAMILY * 56))

    assert isinstance(message, Chat)
    assert message.text == FAMILY * 56


def test_ac8_family_emoji_over_280_code_points_are_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(chat_with(FAMILY * 56 + "x"))


# ---- AC-9 ---------------------------------------------------------------


def select_cell_with_direction(direction: str) -> str:
    """Return the select_cell example with another direction."""
    return json.dumps(with_key(client_data("select_cell"), "direction", direction))


def player_state_with(state: str) -> str:
    """Return the player_state_changed example with another state."""
    return json.dumps(with_key(server_data("player_state_changed"), "state", state))


def change_settings_with(help_mode: str) -> str:
    """Return the change_settings example with another help mode."""
    return json.dumps(with_key(client_data("change_settings"), "help_mode", help_mode))


def react_with(reaction: str) -> str:
    """Return the react example with another reaction."""
    return json.dumps(with_key(client_data("react"), "reaction", reaction))


def player_left_with(reason: str) -> str:
    """Return the player_left example with another reason."""
    return json.dumps(with_key(server_data("player_left"), "reason", reason))


def vote_closed_with(outcome: str) -> str:
    """Return the vote_closed example with another outcome."""
    return json.dumps(with_key(server_data("vote_closed"), "outcome", outcome))


def error_with(code: str) -> str:
    """Return the error example with another code."""
    return json.dumps(with_key(server_data("error"), "code", code))


def check_with_scope(scope: str) -> str:
    """Return a check message with a target of the given scope."""
    targets: dict[str, JsonData] = {
        "letter": {"scope": "letter", "row": 1, "column": 0},
        "word": {"scope": "word", "row": 0, "column": 2, "clue_index": 0},
        "grid": {"scope": "grid"},
        "region": {"scope": "region", "row": 1, "column": 0},
    }
    return json.dumps({"type": "check", "target": targets[scope]})


def reveal_with_scope(scope: str) -> str:
    """Return a reveal message with a target of the given scope."""
    targets: dict[str, JsonData] = {
        "letter": {"scope": "letter", "row": 1, "column": 0},
        "word": {"scope": "word", "row": 0, "column": 2, "clue_index": 0},
        "region": {"scope": "region", "row": 1, "column": 0},
    }
    return json.dumps({"type": "reveal", "target": targets[scope]})


VALID_ENUM_CASES: list[tuple[Parser, str, str, str]] = []
INVALID_ENUM_CASES: list[tuple[Parser, str, str]] = []


def add_valid(
    parser: Parser, builder: Callable[[str], str], field: str, values: list[str]
) -> None:
    """Record valid enum cases for the parametrized tests."""
    for value in values:
        VALID_ENUM_CASES.append((parser, builder(value), field, value))


def add_invalid(
    parser: Parser, builder: Callable[[str], str], values: list[str]
) -> None:
    """Record invalid enum cases for the parametrized tests."""
    for value in values:
        INVALID_ENUM_CASES.append((parser, builder(value), value))


add_valid(
    parse_client_message, select_cell_with_direction, "direction", ["across", "down"]
)
add_valid(
    parse_server_message,
    player_state_with,
    "state",
    ["active", "idle", "disconnected"],
)
add_valid(
    parse_client_message, change_settings_with, "help_mode", ["free", "vote", "none"]
)
add_valid(
    parse_client_message,
    react_with,
    "reaction",
    ["thumbs_up", "clap", "laugh", "wow", "thinking"],
)
add_valid(
    parse_server_message, player_left_with, "reason", ["left", "removed", "timed_out"]
)
add_valid(
    parse_server_message,
    vote_closed_with,
    "outcome",
    ["passed", "rejected", "timed_out"],
)
add_valid(parse_server_message, error_with, "code", ERROR_CODES)

add_invalid(
    parse_client_message, select_cell_with_direction, ["diagonal", "ACROSS", ""]
)
add_invalid(parse_server_message, player_state_with, ["away", "Active", ""])
add_invalid(parse_client_message, change_settings_with, ["auto", "FREE", ""])
add_invalid(parse_client_message, react_with, ["heart", "CLAP", ""])
add_invalid(parse_server_message, player_left_with, ["quit", "Left", ""])
add_invalid(parse_server_message, vote_closed_with, ["tie", "PASSED", ""])
add_invalid(parse_server_message, error_with, ["unknown_code", "CELL_LOCKED", ""])


@pytest.mark.parametrize(
    ("parser", "text", "field", "value"),
    VALID_ENUM_CASES,
    ids=[f"{case[2]}-{case[3]}" for case in VALID_ENUM_CASES],
)
def test_ac9_listed_enum_value_parses(
    parser: Parser, text: str, field: str, value: str
) -> None:
    message = parser(text)

    # The field name comes from the parametrized case, so it cannot be a
    # literal attribute access.
    assert getattr(message, field) == value
    assert parser(message.model_dump_json()) == message


@pytest.mark.parametrize(
    ("parser", "text", "value"),
    INVALID_ENUM_CASES,
    ids=[f"{index}-{case[2]!r}" for index, case in enumerate(INVALID_ENUM_CASES)],
)
def test_ac9_unlisted_enum_value_is_rejected(
    parser: Parser, text: str, value: str
) -> None:
    with pytest.raises(ValidationError):
        parser(text)


def test_ac9_error_code_list_has_sixteen_values() -> None:
    assert len(ERROR_CODES) == 16
    assert len(set(ERROR_CODES)) == 16


@pytest.mark.parametrize("scope", ["letter", "word", "grid"])
def test_ac9_check_scope_parses(scope: str) -> None:
    message = parse_client_message(check_with_scope(scope))

    assert isinstance(message, Check)
    assert message.target.scope == scope


@pytest.mark.parametrize("scope", ["letter", "word"])
def test_ac9_reveal_scope_parses(scope: str) -> None:
    message = parse_client_message(reveal_with_scope(scope))

    assert isinstance(message, Reveal)
    assert message.target.scope == scope


def test_ac9_unknown_check_scope_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(check_with_scope("region"))


def test_ac9_unknown_reveal_scope_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(reveal_with_scope("region"))


def test_ac9_selection_direction_in_server_message_is_checked() -> None:
    data = server_data("selection_moved")
    data["selection"]["direction"] = "diagonal"

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


# ---- AC-10 --------------------------------------------------------------


def test_ac10_reveal_with_grid_scope_is_rejected() -> None:
    text = '{"type": "reveal", "target": {"scope": "grid"}}'

    with pytest.raises(ValidationError):
        parse_client_message(text)


def test_ac10_check_with_grid_scope_parses_to_grid_target() -> None:
    text = '{"type": "check", "target": {"scope": "grid"}}'

    message = parse_client_message(text)

    assert isinstance(message, Check)
    assert message.target == GridTarget()
    assert parse_client_message(message.model_dump_json()) == message


def test_ac10_reveal_result_with_grid_scope_is_rejected() -> None:
    data = with_key(server_data("reveal_result"), "target", {"scope": "grid"})

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac10_vote_opened_with_reveal_of_grid_is_rejected() -> None:
    data = server_data("vote_opened")
    data["request"] = {"type": "reveal", "target": {"scope": "grid"}}

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac10_vote_opened_with_check_of_grid_parses() -> None:
    data = server_data("vote_opened")
    data["request"] = {"type": "check", "target": {"scope": "grid"}}

    message = parse_server_message(json.dumps(data))

    assert isinstance(message, VoteOpened)
    assert isinstance(message.request, Check)
    assert message.request.target == GridTarget()


# ---- AC-11 --------------------------------------------------------------


SEQ_FIELD = "seq"


@pytest.mark.parametrize("type_name", SEQ_TYPES)
def test_ac11_missing_seq_is_rejected(type_name: str) -> None:
    data = without_key(server_data(type_name), "seq")

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


@pytest.mark.parametrize("seq", [0, -1])
@pytest.mark.parametrize("type_name", SEQ_TYPES)
def test_ac11_seq_below_one_is_rejected(type_name: str, seq: int) -> None:
    data = with_key(server_data(type_name), "seq", seq)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


@pytest.mark.parametrize("type_name", SEQ_TYPES)
def test_ac11_seq_one_parses(type_name: str) -> None:
    data = with_key(server_data(type_name), "seq", 1)

    message = parse_server_message(json.dumps(data))

    assert type(message) is protocol_class(SERVER_CLASSES[type_name])
    # 16 different classes carry seq, so it is read through a variable name.
    assert getattr(message, SEQ_FIELD) == 1


@pytest.mark.parametrize("type_name", SEQ_TYPES)
def test_ac11_seq_has_no_upper_bound(type_name: str) -> None:
    big_seq = 10**15
    data = with_key(server_data(type_name), "seq", big_seq)

    message = parse_server_message(json.dumps(data))

    assert getattr(message, SEQ_FIELD) == big_seq


@pytest.mark.parametrize("bad_seq", ['"1"', "1.0", "true"])
def test_ac11_seq_must_be_a_strict_integer(bad_seq: str) -> None:
    text = server_text("host_changed").replace('"seq": 50', f'"seq": {bad_seq}')

    with pytest.raises(ValidationError):
        parse_server_message(text)


def test_ac11_seq_types_list_has_sixteen_entries() -> None:
    assert len(SEQ_TYPES) == 16
    assert len(set(SEQ_TYPES)) == 16


# ---- AC-12 --------------------------------------------------------------


@pytest.mark.parametrize("type_name", NO_SEQ_TYPES)
def test_ac12_seq_is_rejected_on_messages_without_seq(type_name: str) -> None:
    data = with_key(server_data(type_name), "seq", 5)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


@pytest.mark.parametrize("type_name", NO_SEQ_TYPES)
def test_ac12_message_without_seq_parses_and_has_no_seq_field(
    type_name: str,
) -> None:
    message = parse_server_message(server_text(type_name))

    assert type(message) is protocol_class(SERVER_CLASSES[type_name])
    assert "seq" not in json.loads(message.model_dump_json())


# ---- AC-13 --------------------------------------------------------------


@pytest.mark.parametrize("seq", [0, 42, 10**15])
def test_ac13_snapshot_seq_in_range_parses(seq: int) -> None:
    message = parse_server_message(snapshot_with(seq=seq))

    assert isinstance(message, Snapshot)
    assert message.seq == seq


def test_ac13_snapshot_negative_seq_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_server_message(snapshot_with(seq=-1))


def test_ac13_snapshot_without_seq_is_rejected() -> None:
    data = without_key(server_data("snapshot"), "seq")

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


@pytest.mark.parametrize("seq", ['"0"', "0.0", "false"])
def test_ac13_snapshot_seq_must_be_a_strict_integer(seq: str) -> None:
    text = server_text("snapshot").replace('"seq": 0,', f'"seq": {seq},', 1)

    with pytest.raises(ValidationError):
        parse_server_message(text)


# ---- AC-14 --------------------------------------------------------------


def collect_property_names(node: object, names: set[str]) -> int:
    """Add every property name found under a schema node (any: raw JSON).

    Returns:
        The number of `properties` mappings that were walked.
    """
    walked = 0
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
            walked += 1
        for value in node.values():
            walked += collect_property_names(value, names)
    elif isinstance(node, list):
        for item in node:
            walked += collect_property_names(item, names)
    return walked


def test_ac14_snapshot_schema_has_no_answer_property() -> None:
    schema = Snapshot.model_json_schema()
    names: set[str] = set()

    walked = collect_property_names(schema, names)

    assert walked > 5
    assert "grid" in names
    assert "clues" in names
    assert "answer" not in names
    assert "solution" not in names


def test_ac14_clue_view_is_part_of_the_schema() -> None:
    schema = Snapshot.model_json_schema()

    clue_view = schema["$defs"]["ClueView"]

    assert set(clue_view["properties"]) == {"text", "arrow"}


# ---- AC-15 --------------------------------------------------------------

CLUE_WITH_ANSWER = (
    '{"type": "clue", "row": 0, "column": 0, "clues": '
    '[{"text": "Note", "arrow": "right", "answer": "A"}]}'
)
CLUE_WITHOUT_ANSWER = (
    '{"type": "clue", "row": 0, "column": 0, "clues": '
    '[{"text": "Note", "arrow": "right"}]}'
)


def snapshot_with_clue_cell(clue_cell_text: str) -> str:
    """Return the snapshot example whose first grid cell is the given cell."""
    data = server_data("snapshot")
    data["grid"]["cells"][0] = json.loads(clue_cell_text)
    return json.dumps(data)


def test_ac15_snapshot_with_a_clue_answer_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_server_message(snapshot_with_clue_cell(CLUE_WITH_ANSWER))


def test_ac15_same_snapshot_without_the_answer_parses() -> None:
    message = parse_server_message(snapshot_with_clue_cell(CLUE_WITHOUT_ANSWER))

    assert isinstance(message, Snapshot)
    clue_cell = message.grid.cells[0]
    assert isinstance(clue_cell, ClueCellView)
    assert clue_cell.clues[0].text == "Note"


def test_ac15_clue_view_rejects_an_answer() -> None:
    with pytest.raises(ValidationError):
        ClueView.model_validate({"text": "Note", "arrow": "right", "answer": "A"})


def test_ac15_clue_view_without_answer_validates() -> None:
    clue = ClueView.model_validate({"text": "Note", "arrow": "right"})

    assert clue == ClueView(text="Note", arrow=Arrow.RIGHT)


def test_ac15_clue_view_has_no_answer_field() -> None:
    assert "answer" not in ClueView.model_fields


# ---- AC-16 --------------------------------------------------------------


def test_ac16_view_has_the_size_and_cell_order_of_the_grid(fx01_text: str) -> None:
    grid = build_fx01_grid(fx01_text)

    view = grid_view(grid)

    assert view.width == 5
    assert view.height == 5
    assert len(view.cells) == 25
    for grid_cell, view_cell in zip(grid.cells, view.cells, strict=True):
        assert view_cell.type == grid_cell.type
        assert view_cell.row == grid_cell.row
        assert view_cell.column == grid_cell.column


def test_ac16_clue_cell_keeps_its_clues_in_order(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))

    first_cell = view.cells[0]

    assert first_cell.type == "clue"
    assert (first_cell.row, first_cell.column) == (0, 0)
    assert first_cell.clues == (
        ClueView(text="Passoire fine", arrow=Arrow.DOWN_THEN_RIGHT),
        ClueView(text="De la marine", arrow=Arrow.RIGHT_THEN_DOWN),
    )


def test_ac16_single_clue_cell_keeps_its_clue(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))

    cell = view.cells[2]

    assert isinstance(cell, ClueCellView)
    assert cell.clues == (ClueView(text="Artiste muet", arrow=Arrow.DOWN),)


def test_ac16_letter_cells_are_empty_and_untouched(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))
    letter_cells = [cell for cell in view.cells if cell.type == "letter"]

    assert len(letter_cells) == 18
    for cell in letter_cells:
        assert isinstance(cell, LetterCellView)
        assert cell.letter is None
        assert cell.pencil is False
        assert cell.author is None
        assert cell.locked is False
        assert cell.revealed is False
        assert cell.wrong is False


def test_ac16_cell_kinds_match_the_grid(fx01_text: str) -> None:
    grid = build_fx01_grid(fx01_text)
    view = grid_view(grid)
    grid_kinds = [cell.type for cell in grid.cells]
    view_kinds = [cell.type for cell in view.cells]

    assert view_kinds == grid_kinds
    assert all(
        isinstance(cell, EmptyCellView) for cell in view.cells if cell.type == "empty"
    )


def test_ac16_view_is_a_grid_view_that_round_trips(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))

    again = GridView.model_validate_json(view.model_dump_json())

    assert isinstance(view, GridView)
    assert again == view


def test_ac16_empty_cells_are_kept_in_place() -> None:
    grid = Grid.model_validate(
        {
            "width": 3,
            "height": 2,
            "cells": [
                {
                    "type": "clue",
                    "row": 0,
                    "column": 0,
                    "clues": [{"text": "Note", "arrow": "right", "answer": "AB"}],
                },
                {"type": "letter", "row": 0, "column": 1},
                {"type": "empty", "row": 0, "column": 2},
                {"type": "empty", "row": 1, "column": 0},
                {"type": "letter", "row": 1, "column": 1},
                {"type": "empty", "row": 1, "column": 2},
            ],
        }
    )

    view = grid_view(grid)

    assert view.width == 3
    assert view.height == 2
    assert [cell.type for cell in view.cells] == [
        "clue",
        "letter",
        "empty",
        "empty",
        "letter",
        "empty",
    ]
    assert view.cells[2] == EmptyCellView(row=0, column=2)
    assert view.cells[3] == EmptyCellView(row=1, column=0)
    assert view.cells[5] == EmptyCellView(row=1, column=2)
    assert GridView.model_validate_json(view.model_dump_json()) == view


# ---- AC-17 --------------------------------------------------------------

ANSWERS = ["TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST"]


@pytest.mark.parametrize("answer", ANSWERS)
def test_ac17_view_json_does_not_contain_an_answer(fx01_text: str, answer: str) -> None:
    text = grid_view(build_fx01_grid(fx01_text)).model_dump_json()

    assert answer not in text


def test_ac17_view_json_has_no_answer_key(fx01_text: str) -> None:
    text = grid_view(build_fx01_grid(fx01_text)).model_dump_json()

    assert '"answer"' not in text


def test_ac17_view_json_still_holds_the_clue_texts(fx01_text: str) -> None:
    text = grid_view(build_fx01_grid(fx01_text)).model_dump_json()

    assert "Passoire fine" in text
    assert "De la marine" in text


# ---- AC-18 --------------------------------------------------------------


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
