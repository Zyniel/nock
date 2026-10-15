"""Tests of spec 039, AC-11 to AC-13: the sequence numbers.

AC-11: the 16 room-changing events carry a seq of at least 1. AC-12: the
other server messages carry none. AC-13: the snapshot seq may be 0. The
shared setup is in `spec039_harness`.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from nock.protocol import Snapshot, parse_server_message
from spec039_harness import (
    SEQ_TYPES,
    SERVER_CLASSES,
    protocol_class,
    server_data,
    server_text,
    snapshot_with,
    with_key,
    without_key,
)

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


NO_SEQ_TYPES: list[str] = ["selection_moved", "reaction", "pong", "error"]


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
