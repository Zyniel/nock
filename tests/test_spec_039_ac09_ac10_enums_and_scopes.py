"""Tests of spec 039, AC-9 and AC-10: enumerated fields and target scopes.

AC-9: a listed value parses, any other string is rejected. AC-10: a reveal
cannot target the whole grid. The shared setup is in `spec039_harness`.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from nock.protocol import (
    Check,
    GridTarget,
    Reveal,
    VoteOpened,
    parse_client_message,
    parse_server_message,
)
from spec039_harness import (
    ERROR_CODES,
    JsonData,
    Parser,
    client_data,
    error_with,
    server_data,
    with_key,
)

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


def test_ac9_error_code_list_has_nineteen_values() -> None:
    assert len(ERROR_CODES) == 19
    assert len(set(ERROR_CODES)) == 19


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
