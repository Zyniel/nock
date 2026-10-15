"""Tests of spec 039, AC-20 and AC-21: ping and pong, and the error codes.

The shared setup is in `spec039_harness`.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from nock.protocol import ErrorMessage, parse_client_message, parse_server_message
from spec039_harness import ERROR_CODES, error_with, protocol_class

# ---- AC-20 --------------------------------------------------------------
# Ping and Pong are looked up by name so that only these tests fail while
# the classes do not exist yet.


def test_ac20_ping_parses_to_ping() -> None:
    message = parse_client_message('{"type": "ping"}')

    assert message == protocol_class("Ping")()
    assert type(message) is protocol_class("Ping")


def test_ac20_pong_parses_to_pong() -> None:
    message = parse_server_message('{"type": "pong"}')

    assert message == protocol_class("Pong")()
    assert type(message) is protocol_class("Pong")


def test_ac20_ping_and_pong_serialise_to_their_type_only() -> None:
    ping_json = protocol_class("Ping")().model_dump_json()
    pong_json = protocol_class("Pong")().model_dump_json()

    assert json.loads(ping_json) == {"type": "ping"}
    assert json.loads(pong_json) == {"type": "pong"}


def test_ac20_ping_is_rejected_by_the_server_parser() -> None:
    with pytest.raises(ValidationError):
        parse_server_message('{"type": "ping"}')


def test_ac20_pong_is_rejected_by_the_client_parser() -> None:
    with pytest.raises(ValidationError):
        parse_client_message('{"type": "pong"}')


@pytest.mark.parametrize("extra_field", ["seq", "id"])
def test_ac20_ping_with_an_extra_field_is_rejected(extra_field: str) -> None:
    text = json.dumps({"type": "ping", extra_field: 1})

    with pytest.raises(ValidationError):
        parse_client_message(text)


# ---- AC-21 --------------------------------------------------------------

NEW_ERROR_CODES: dict[str, str] = {
    "invalid_nickname": "INVALID_NICKNAME",
    "invalid_target": "INVALID_TARGET",
    "stale_edit": "STALE_EDIT",
}


def test_ac21_error_code_has_nineteen_members() -> None:
    assert len(protocol_class("ErrorCode")) == 19


def test_ac21_error_code_values_are_the_listed_ones() -> None:
    members = list(protocol_class("ErrorCode"))
    values = [member.value for member in members]

    assert sorted(values) == sorted(ERROR_CODES)


@pytest.mark.parametrize("value", list(NEW_ERROR_CODES))
def test_ac21_new_code_maps_to_its_member(value: str) -> None:
    error_code = protocol_class("ErrorCode")

    member = error_code(value)

    assert member is getattr(error_code, NEW_ERROR_CODES[value])


@pytest.mark.parametrize("value", list(NEW_ERROR_CODES))
def test_ac21_error_message_with_new_code_parses(value: str) -> None:
    error_code = protocol_class("ErrorCode")

    message = parse_server_message(error_with(value))

    assert isinstance(message, ErrorMessage)
    assert message.code is getattr(error_code, NEW_ERROR_CODES[value])
    assert message.message == "cell (1, 0) is locked"
    assert parse_server_message(message.model_dump_json()) == message
