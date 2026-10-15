"""Shared setup of the tests of spec 039: the room events protocol.

This module is not a test file: pytest does not collect it. The tests of spec 039
are in `tests/test_spec_039_*.py`, one file per criterion group.

It holds what more than one of those files uses: the wire examples copied from the
spec, the class and error code tables, and the small helpers that read or change
an example. What only one file uses stays in that file, next to its tests. The
only fixture the tests use is `fx01_text`, which comes from `conftest.py`.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from nock.grid import Grid

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
    "ping": '{"type": "ping"}',
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
    "pong": '{"type": "pong"}',
    "error": (
        '{"type": "error", "code": "cell_locked", '
        '"message": "cell (1, 0) is locked"}'
    ),
}

# Class names of the server table.
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
    "pong": "Pong",
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
    "invalid_nickname",
    "invalid_target",
    "stale_edit",
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


def build_fx01_grid(fx01_text: str) -> Grid:
    """Build the FX-01 reference grid."""
    return Grid.model_validate_json(fx01_text)


def error_with(code: str) -> str:
    """Return the error example with another code."""
    return json.dumps(with_key(server_data("error"), "code", code))
