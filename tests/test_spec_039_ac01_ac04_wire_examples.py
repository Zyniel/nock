"""Tests of spec 039, AC-1 to AC-4: the wire examples.

AC-1 and AC-2: each example parses to its class and round trips. AC-3: the
fields carry the values of the JSON. AC-4: an unknown, missing or
wrong-direction type is rejected. The shared setup is in `spec039_harness`.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from nock.grid import Arrow
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
    Reveal,
    RevealResult,
    Snapshot,
    VoteOpened,
    WordTarget,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from spec039_harness import (
    CLIENT_EXAMPLES,
    SERVER_CLASSES,
    SERVER_EXAMPLES,
    Parser,
    build_fx01_grid,
    client_data,
    client_text,
    protocol_class,
    server_data,
    server_text,
    with_key,
)

# Class names of the client table.
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
    "ping": "Ping",
}


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


def test_ac1_client_example_count_is_eighteen() -> None:
    assert len(CLIENT_EXAMPLES) == 18
    assert len(CLIENT_CLASSES) == 18


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


def test_ac2_server_example_count_is_twenty_one() -> None:
    assert len(SERVER_EXAMPLES) == 21
    assert len(SERVER_CLASSES) == 21


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
