"""Tests of spec 039, AC-5: a malformed field is rejected.

The cases are walked field by field: booleans and integers are strict,
bounds and patterns hold, and unknown fields are refused. The shared setup is
in `spec039_harness`.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from nock.grid import Arrow
from nock.protocol import (
    ClueCellView,
    ClueView,
    Flag,
    Join,
    LetterCellView,
    PlayerJoined,
    RemovePlayer,
    Snapshot,
    Vote,
    VoteOpened,
    parse_client_message,
    parse_server_message,
)
from spec039_harness import (
    SEQ_TYPES,
    JsonData,
    client_data,
    server_data,
    server_text,
    with_key,
    without_key,
)

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
