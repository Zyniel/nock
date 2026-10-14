"""Tests of spec 036 (performance), AC-5 and AC-6: the limits of the hub.

AC-5 and AC-6 drive the hub directly, each scenario on an event loop of its own.

The shared setup is in `spec036_harness`.

Notes:

- Hub scenarios call `asyncio.run` in a thread of their own: once a browser test
  has run, Playwright's sync API leaves its loop marked as running on the test
  thread, where `asyncio.run` refuses to start.
- Edge cases checked as well: 4507 and 1008 are not final for the page; the exact
  outbound and inbound bounds; sockets that have not joined; frames after a
  flood; the socket's close after a flood.
"""

from __future__ import annotations

import inspect

import pytest
from playwright.sync_api import Page
from pydantic import ValidationError

import nock.hub
from nock.grid import Grid
from nock.hub import RoomConnection
from nock.protocol import PlayerState, Snapshot, parse_server_message
from nock.room import RoomConfig
from spec036_harness import (
    DEFAULT_INBOUND_LIMIT,
    DEFAULT_OUTBOUND_LIMIT,
    FLOOD_CODE,
    INBOUND_LIMIT,
    OUTBOUND_LIMIT,
    STALLED_CODE,
    BlockingStore,
    b_edit,
    close_after_flood_scenario,
    error_types,
    expect_reconnection_after_close,
    flood_scenario,
    frame_after_flood_scenario,
    inbound_bound_scenario,
    letter_in_snapshot,
    letter_in_state,
    open_mock_room,
    open_registry,
    outbound_bound_scenario,
    own_letter_changes,
    run_hub_scenario,
    stalled_client_scenario,
    state_changes_of,
    stranger_flood_scenario,
    triples,
)

# The fixtures of the harness. pytest looks for a test's fixtures among the names of
# its module, so they are imported by name. `x as x` is the explicit re-export
# form: it keeps ruff from reporting the import as unused or as redefined.
from spec036_harness import blocking_store as blocking_store
from spec036_harness import fx01_grid as fx01_grid

# ---- AC-5: a client that never reads is disconnected ------------------------------


def test_ac5_the_stalled_close_code_is_4507_and_exported() -> None:
    assert nock.hub.STALLED_CLOSE_CODE == STALLED_CODE
    assert "STALLED_CLOSE_CODE" in nock.hub.__all__


def test_ac5_a_room_allows_1000_outbound_messages_per_connection_by_default() -> None:
    assert RoomConfig().max_outbound_messages == DEFAULT_OUTBOUND_LIMIT


def test_ac5_the_outbound_limit_accepts_one_and_refuses_zero() -> None:
    config = RoomConfig.model_validate({"max_outbound_messages": 1})
    assert config.max_outbound_messages == 1

    with pytest.raises(ValidationError) as caught:
        RoomConfig.model_validate({"max_outbound_messages": 0})

    assert error_types(caught.value) == ["greater_than_equal"]


def test_ac5_a_connection_allows_1000_outbound_messages_unless_told_otherwise() -> None:
    parameter = inspect.signature(RoomConnection).parameters.get("max_outbound")

    assert parameter is not None, "RoomConnection takes no max_outbound"
    assert parameter.default == DEFAULT_OUTBOUND_LIMIT


def test_ac5_a_client_that_never_reads_is_closed_as_stalled_and_disconnected(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_outbound_messages=OUTBOUND_LIMIT, max_edits_per_second=1000)
    with open_registry(config) as registry:
        code = registry.register_room(fx01_grid)
        run = run_hub_scenario(stalled_client_scenario(registry, code))

    assert run.close_codes_within_budget == [STALLED_CODE]
    assert run.writer_returned is True
    first_30 = [b_edit(index) for index in range(30)]
    b_letters = own_letter_changes(run.b_messages_after_30, run.b_id)
    assert triples(b_letters[:30]) == triples(first_30)
    a_states = [
        event.state for event in state_changes_of(run.b_messages_after_30, run.a_id)
    ]
    assert a_states == [PlayerState.DISCONNECTED]
    assert len(run.a_texts) == 1
    assert isinstance(parse_server_message(run.a_texts[0]), Snapshot)
    assert run.final_close_codes == [STALLED_CODE]
    all_40 = [b_edit(index) for index in range(40)]
    assert triples(own_letter_changes(run.b_messages_after_40, run.b_id)) == triples(
        all_40
    )


def test_ac5_twenty_queued_messages_do_not_stall_a_client_the_twenty_first_does(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_outbound_messages=OUTBOUND_LIMIT, max_edits_per_second=1000)
    with open_registry(config) as registry:
        code = registry.register_room(fx01_grid)
        run = run_hub_scenario(outbound_bound_scenario(registry, code))

    assert run.close_codes_at_bound == []
    assert run.writer_done_at_bound is False
    assert run.close_codes_over_bound == [STALLED_CODE]


def test_ac5_a_page_closed_as_stalled_reconnects_and_gets_a_fresh_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    server = open_mock_room(page, live_server, fx01_grid)

    expect_reconnection_after_close(page, server, fx01_grid, STALLED_CODE)


# ---- AC-6: a client that floods is closed, the room keeps working -----------------


def test_ac6_the_flood_close_code_is_1008_and_exported() -> None:
    assert nock.hub.FLOOD_CLOSE_CODE == FLOOD_CODE
    assert "FLOOD_CLOSE_CODE" in nock.hub.__all__


def test_ac6_a_room_allows_100_unapplied_inputs_per_connection_by_default() -> None:
    assert RoomConfig().max_inbound_pending == DEFAULT_INBOUND_LIMIT


def test_ac6_the_inbound_limit_accepts_one_and_refuses_zero() -> None:
    config = RoomConfig.model_validate({"max_inbound_pending": 1})
    assert config.max_inbound_pending == 1

    with pytest.raises(ValidationError) as caught:
        RoomConfig.model_validate({"max_inbound_pending": 0})

    assert error_types(caught.value) == ["greater_than_equal"]


def test_ac6_a_connection_allows_100_unapplied_inputs_unless_told_otherwise() -> None:
    parameter = inspect.signature(RoomConnection).parameters.get("max_inbound")

    assert parameter is not None, "RoomConnection takes no max_inbound"
    assert parameter.default == DEFAULT_INBOUND_LIMIT


def test_ac6_a_client_that_floods_is_closed_and_the_room_keeps_working(
    blocking_store: BlockingStore, fx01_grid: Grid
) -> None:
    config = RoomConfig(max_inbound_pending=INBOUND_LIMIT, max_edits_per_second=1000)
    with open_registry(config, blocking_store) as registry:
        code = registry.register_room(fx01_grid)
        run = run_hub_scenario(flood_scenario(registry, blocking_store, code))

    assert run.close_codes_while_blocked == [FLOOD_CODE]
    assert run.store_still_blocked is True
    assert run.letter_in_room == "T"
    assert letter_in_snapshot(run.c_snapshot, 1, 0) == "T"
    assert run.final_close_codes == [FLOOD_CODE]


def test_ac6_five_unapplied_inputs_are_allowed_a_sixth_closes_the_connection(
    blocking_store: BlockingStore, fx01_grid: Grid
) -> None:
    config = RoomConfig(max_inbound_pending=INBOUND_LIMIT, max_edits_per_second=1000)
    with open_registry(config, blocking_store) as registry:
        code = registry.register_room(fx01_grid)
        run = run_hub_scenario(inbound_bound_scenario(registry, blocking_store, code))

    assert run.close_codes_at_bound == []
    assert run.writer_done_at_bound is False
    assert run.close_codes_over_bound == [FLOOD_CODE]


@pytest.mark.parametrize("frame", ["ping", "invalid"])
def test_ac6_the_inbound_cap_applies_to_a_socket_that_has_not_joined(
    blocking_store: BlockingStore, fx01_grid: Grid, frame: str
) -> None:
    config = RoomConfig(max_inbound_pending=INBOUND_LIMIT, max_edits_per_second=1000)
    with open_registry(config, blocking_store) as registry:
        code = registry.register_room(fx01_grid)
        close_codes = run_hub_scenario(
            stranger_flood_scenario(registry, blocking_store, code, frame)
        )

    assert close_codes == [FLOOD_CODE]


def test_ac6_a_frame_sent_after_the_flood_is_never_applied(
    blocking_store: BlockingStore, fx01_grid: Grid
) -> None:
    config = RoomConfig(max_inbound_pending=INBOUND_LIMIT, max_edits_per_second=1000)
    with open_registry(config, blocking_store) as registry:
        code = registry.register_room(fx01_grid)
        c_snapshot = run_hub_scenario(
            frame_after_flood_scenario(registry, blocking_store, code)
        )
        letter_in_room = letter_in_state(registry.room_state(code), 1, 1)

    assert letter_in_snapshot(c_snapshot, 1, 0) == "T"
    assert letter_in_snapshot(c_snapshot, 1, 1) is None
    assert letter_in_room is None


def test_ac6_the_socket_close_after_a_flood_still_disconnects_the_player(
    blocking_store: BlockingStore, fx01_grid: Grid
) -> None:
    config = RoomConfig(max_inbound_pending=INBOUND_LIMIT, max_edits_per_second=1000)
    with open_registry(config, blocking_store) as registry:
        code = registry.register_room(fx01_grid)
        ana_id, c_snapshot = run_hub_scenario(
            close_after_flood_scenario(registry, blocking_store, code)
        )

    states: dict[str, PlayerState] = {}
    for player in c_snapshot.players:
        states[player.player_id] = player.state
    assert states[ana_id] is PlayerState.DISCONNECTED


def test_ac6_a_page_closed_for_flooding_reconnects_and_gets_a_fresh_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    server = open_mock_room(page, live_server, fx01_grid)

    expect_reconnection_after_close(page, server, fx01_grid, FLOOD_CODE)
