"""Tests of spec 011, AC-4: the runtime guarantees of the room engine.

The rule functions of `nock.room` are replaced by recording fakes and the hub is
driven through the real WebSocket with `tick_seconds` small. The shared setup is in
`spec011_harness`.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

import nock.hub
import nock.room
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClientMessage,
    LetterChanged,
    PlayerJoined,
    Pong,
    SelectionMoved,
    Snapshot,
    parse_server_message,
)
from nock.room import LogEntry, Outcome, RoomConfig, RoomState
from nock.server import create_app
from spec011_harness import (
    JOIN_TEXT,
    START_TIME,
    grid_from_text,
    make_dist_dir,
    receive_text_or_fail,
    socket_url,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


# ---- AC-4: the runtime guarantees of the room engine ------------------------

TICK_SECONDS = 0.05
ENGINE_WAIT_SECONDS = 5.0
POLL_SECONDS = 0.01
SETTLE_SECONDS = 0.4
LONG_TICK_SECONDS = 30.0
ENGINE_THREAD_PREFIX = "nock-rooms"
SELECT_TEXT = '{"type": "select_cell", "row": 0, "column": 0, "direction": "across"}'
UNDO_TEXT = '{"type": "undo"}'
PING_TEXT = '{"type": "ping"}'
SHARED_TOKEN = "Z" * 32
RULE_ERROR_TEXT = "rule exploded"


def wait_until(condition: Callable[[], bool], what: str) -> None:
    """Poll `condition` for a few seconds and fail with `what` when it stays false."""
    deadline = time.monotonic() + ENGINE_WAIT_SECONDS
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(POLL_SECONDS)
    pytest.fail(f"timed out after {ENGINE_WAIT_SECONDS}s waiting for: {what}")


def last_seq_of(registry: RoomRegistry, code: str) -> int:
    """Return the seq of the last event of room `code`."""
    state = registry.room_state(code)
    assert state is not None
    return state.seq


def letter_changed(seq: int, player_id: str) -> LetterChanged:
    return LetterChanged(
        seq=seq, row=0, column=0, letter="T", pencil=False, player_id=player_id
    )


def log_entry(seq: int, player_id: str) -> LogEntry:
    return LogEntry(at=START_TIME, event=letter_changed(seq, player_id))


class RuleRecorder:
    """Fakes of the three rule functions, which record each call in order.

    `events` holds "tick", "message:<player>" and "disconnect:<player>", and
    "raised:<rule>" when a fake raised on purpose.
    """

    def __init__(self) -> None:
        self.events: list[str] = []
        self.rule_to_break: str | None = None

    def count(self, prefix: str) -> int:
        matching = [event for event in self.events if event.startswith(prefix)]
        return len(matching)

    def break_first_call_of(self, rule: str) -> None:
        self.rule_to_break = rule

    def _record(self, rule: str, event: str) -> None:
        if self.rule_to_break == rule:
            self.rule_to_break = None
            self.events.append(f"raised:{rule}")
            raise RuntimeError(RULE_ERROR_TEXT)
        self.events.append(event)

    def tick(
        self, state: RoomState, now: float, config: RoomConfig | None = None
    ) -> Outcome:
        self._record("tick", "tick")
        return Outcome(state=state)

    def disconnect_player(
        self, state: RoomState, player_id: str, now: float
    ) -> Outcome:
        self._record("disconnect_player", f"disconnect:{player_id}")
        return Outcome(state=state)

    def handle_message(
        self,
        state: RoomState,
        player_id: str,
        message: ClientMessage,
        now: float,
        config: RoomConfig | None = None,
    ) -> Outcome:
        """Select: two events, a reply and a selection. Undo: one event.

        Entries follow the room's last seq, as the real rules number them.
        """
        self._record("handle_message", f"message:{player_id}")
        if message.type == "select_cell":
            first = state.seq + 1
            return Outcome(
                state=state.model_copy(update={"seq": first + 1}),
                entries=(log_entry(first, player_id), log_entry(first + 1, player_id)),
                reply=(Pong(),),
                to_others=(SelectionMoved(player_id=player_id, selection=None),),
            )
        if message.type == "undo":
            seq = state.seq + 1
            return Outcome(
                state=state.model_copy(update={"seq": seq}),
                entries=(log_entry(seq, player_id),),
            )
        return Outcome(state=state)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> RuleRecorder:
    """Replace the rule functions by recording fakes.

    `nock.hub` imports the rules by name (`from nock.room import tick, ...`), so
    the names to patch are the ones in `nock.hub`. The `nock.room` names are
    patched too, in case the hub ever calls the rules through the module.
    """
    fakes = RuleRecorder()
    monkeypatch.setattr(nock.room, "tick", fakes.tick)
    monkeypatch.setattr(nock.room, "handle_message", fakes.handle_message)
    monkeypatch.setattr(nock.room, "disconnect_player", fakes.disconnect_player)
    monkeypatch.setattr(nock.hub, "tick", fakes.tick, raising=False)
    monkeypatch.setattr(nock.hub, "handle_message", fakes.handle_message, raising=False)
    monkeypatch.setattr(
        nock.hub, "disconnect_player", fakes.disconnect_player, raising=False
    )
    return fakes


@contextlib.contextmanager
def running_room(
    grid: Grid, dist_dir: Path, tick_seconds: float = TICK_SECONDS
) -> Iterator[tuple[TestClient, RoomRegistry, str]]:
    """Yield a client, its registry and the code of one room; close it all."""
    registry = RoomRegistry(config=RoomConfig(tick_seconds=tick_seconds))
    try:
        code = registry.register_room(grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client:
            yield client, registry, code
    finally:
        registry.close()


def open_and_join(
    stack: contextlib.ExitStack, client: TestClient, code: str
) -> tuple[WebSocketTestSession, str]:
    """Open a socket in `stack`, join, and return it with its player id."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    websocket.send_text(JOIN_TEXT)
    snapshot = parse_server_message(receive_text_or_fail(websocket))
    assert isinstance(snapshot, Snapshot)
    return websocket, snapshot.you


def join_and_sync(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    recorder: RuleRecorder,
) -> tuple[WebSocketTestSession, str]:
    """Like `open_and_join`, then wait until the room has attached the socket.

    A ping is the barrier: the room applies inputs in order, so once the rules
    saw the ping, the attach that came before it was applied too.
    """
    websocket, player_id = open_and_join(stack, client, code)
    seen_before = recorder.count("message:")
    websocket.send_text(PING_TEXT)
    wait_until(
        lambda: recorder.count("message:") > seen_before,
        "the room to apply the ping of a new connection",
    )
    return websocket, player_id


def receive_message(websocket: WebSocketTestSession) -> object:
    return parse_server_message(receive_text_or_fail(websocket))


def skip_player_joined(websocket: WebSocketTestSession, count: int) -> None:
    """Read the `player_joined` events that later joins sent to this socket."""
    for _ in range(count):
        assert isinstance(receive_message(websocket), PlayerJoined)


def engine_threads() -> list[threading.Thread]:
    """The live threads named like the engine's."""
    threads: list[threading.Thread] = []
    for thread in threading.enumerate():
        if thread.name.startswith(ENGINE_THREAD_PREFIX):
            threads.append(thread)
    return threads


def test_ac4_tick_runs_repeatedly_while_a_connection_is_attached(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, _registry, code),
        contextlib.ExitStack() as stack,
    ):
        join_and_sync(stack, client, code, recorder)

        wait_until(lambda: recorder.count("tick") >= 5, "5 ticks while attached")


def test_ac4_tick_stops_once_every_connection_has_left(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, _registry, code),
        contextlib.ExitStack() as stack,
    ):
        join_and_sync(stack, client, code, recorder)
        wait_until(lambda: recorder.count("tick") >= 2, "ticks while attached")
        stack.close()
        wait_until(
            lambda: recorder.count("disconnect:") == 1,
            "the room to apply the departure",
        )
        time.sleep(TICK_SECONDS * 2)
        ticks_after_leaving = recorder.count("tick")

        time.sleep(SETTLE_SECONDS)

        assert recorder.count("tick") == ticks_after_leaving


def test_ac4_events_reach_everyone_then_the_reply_then_to_others(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        sender, sender_id = join_and_sync(stack, client, code, recorder)
        first_other, _ = join_and_sync(stack, client, code, recorder)
        second_other, _ = join_and_sync(stack, client, code, recorder)
        skip_player_joined(sender, 2)
        skip_player_joined(first_other, 1)
        last_seq = last_seq_of(registry, code)

        sender.send_text(SELECT_TEXT)

        assert receive_message(sender) == letter_changed(last_seq + 1, sender_id)
        assert receive_message(sender) == letter_changed(last_seq + 2, sender_id)
        assert receive_message(sender) == Pong()
        moved = SelectionMoved(player_id=sender_id, selection=None)
        for other in [first_other, second_other]:
            assert receive_message(other) == letter_changed(last_seq + 1, sender_id)
            assert receive_message(other) == letter_changed(last_seq + 2, sender_id)
            assert receive_message(other) == moved


def test_ac4_the_sender_does_not_receive_to_others_nor_the_others_a_reply(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    """After a select, the next thing every socket gets is the next event."""
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        sender, sender_id = join_and_sync(stack, client, code, recorder)
        other, _ = join_and_sync(stack, client, code, recorder)
        skip_player_joined(sender, 1)
        last_seq = last_seq_of(registry, code)
        sender.send_text(SELECT_TEXT)
        for _ in range(3):
            receive_message(sender)
            receive_message(other)

        sender.send_text(UNDO_TEXT)

        assert receive_message(sender) == letter_changed(last_seq + 3, sender_id)
        assert receive_message(other) == letter_changed(last_seq + 3, sender_id)


def test_ac4_the_task_stops_and_a_new_one_ticks_before_any_input(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    """A tick every 30 s never fires here: only the start of a task ticks."""
    with running_room(fx01_grid, dist_dir, LONG_TICK_SECONDS) as (
        client,
        _registry,
        code,
    ):
        with contextlib.ExitStack() as first_stack:
            join_and_sync(first_stack, client, code, recorder)
        wait_until(
            lambda: recorder.count("disconnect:") == 1,
            "the room to apply the departure",
        )
        time.sleep(SETTLE_SECONDS)
        events_before = list(recorder.events)
        assert events_before.count("tick") == 1

        with contextlib.ExitStack() as second_stack:
            join_and_sync(second_stack, client, code, recorder)

        new_events = recorder.events[len(events_before) :]
        assert new_events[0] == "tick"
        assert new_events[1].startswith("message:")
        assert new_events.count("tick") == 1


@pytest.mark.parametrize("broken_rule", ["handle_message", "tick", "disconnect_player"])
def test_ac4_a_raising_rule_is_logged_and_the_room_goes_on(
    recorder: RuleRecorder,
    fx01_grid: Grid,
    dist_dir: Path,
    caplog: pytest.LogCaptureFixture,
    broken_rule: str,
) -> None:
    recorder.break_first_call_of(broken_rule)
    caplog.set_level(logging.ERROR)
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        stay, stay_id = open_and_join(stack, client, code)
        state_before = registry.room_state(code)
        if broken_rule == "handle_message":
            stay.send_text(UNDO_TEXT)
        if broken_rule == "disconnect_player":
            with contextlib.ExitStack() as leaving:
                open_and_join(leaving, client, code)
                state_before = registry.room_state(code)
            skip_player_joined(stay, 1)
        wait_until(
            lambda: f"raised:{broken_rule}" in recorder.events,
            f"{broken_rule} to be called and to raise",
        )
        assert registry.room_state(code) is state_before
        ticks_at_error = recorder.count("tick")
        wait_until(
            lambda: recorder.count("tick") >= ticks_at_error + 3,
            "the room to keep ticking after the error",
        )

        last_seq = last_seq_of(registry, code)
        stay.send_text(SELECT_TEXT)

        assert receive_message(stay) == letter_changed(last_seq + 1, stay_id)
        assert receive_message(stay) == letter_changed(last_seq + 2, stay_id)
        assert receive_message(stay) == Pong()

    assert RULE_ERROR_TEXT in caplog.text
    error_loggers = [
        record.name for record in caplog.records if record.levelno >= logging.ERROR
    ]
    # asyncio logs a task that died with an error; the engine must log it itself.
    engine_loggers = [name for name in error_loggers if name != "asyncio"]
    assert engine_loggers != []


@pytest.fixture
def one_player_id(monkeypatch: pytest.MonkeyPatch) -> str:
    """Make the server give every connection the same player id.

    The hub draws the ids of a snapshot with `secrets.token_urlsafe`;
    a constant that fits both the player id and the resume token patterns makes
    two sockets attach under one player id.
    """

    def constant_token(_nbytes: int | None = None) -> str:
        return SHARED_TOKEN

    monkeypatch.setattr(nock.hub.secrets, "token_urlsafe", constant_token)
    return SHARED_TOKEN


def test_ac4_two_connections_of_one_player_both_receive(
    recorder: RuleRecorder, one_player_id: str, fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        first, first_id = join_and_sync(stack, client, code, recorder)
        second, second_id = join_and_sync(stack, client, code, recorder)
        assert first_id == second_id == one_player_id
        skip_player_joined(first, 1)

        last_seq = last_seq_of(registry, code)
        first.send_text(UNDO_TEXT)

        undone = letter_changed(last_seq + 1, one_player_id)
        assert receive_message(first) == undone
        assert receive_message(second) == undone


@pytest.mark.parametrize("leaver", ["first", "second"])
def test_ac4_detaching_one_connection_keeps_the_other_one(
    recorder: RuleRecorder,
    one_player_id: str,
    fx01_grid: Grid,
    dist_dir: Path,
    leaver: str,
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stay_stack,
    ):
        with contextlib.ExitStack() as leave_stack:
            if leaver == "first":
                join_and_sync(leave_stack, client, code, recorder)
                stay, _ = join_and_sync(stay_stack, client, code, recorder)
            else:
                stay, _ = join_and_sync(stay_stack, client, code, recorder)
                join_and_sync(leave_stack, client, code, recorder)
                skip_player_joined(stay, 1)
        # Leaving the inner stack closed a socket, and its departure was
        # posted before this ping, which the room applies in order.
        seen_before = recorder.count("message:")
        stay.send_text(PING_TEXT)
        wait_until(
            lambda: recorder.count("message:") > seen_before,
            "the room to apply the ping after the departure",
        )

        last_seq = last_seq_of(registry, code)
        stay.send_text(UNDO_TEXT)

        assert receive_message(stay) == letter_changed(last_seq + 1, one_player_id)


def test_ac4_close_stops_the_engine_thread_and_is_idempotent(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    threads_before = set(engine_threads())
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        join_and_sync(stack, client, code, recorder)
        started = [t for t in engine_threads() if t not in threads_before]
        assert len(started) == 1

        stack.close()
        registry.close()
        started[0].join(timeout=ENGINE_WAIT_SECONDS)
        assert not started[0].is_alive()
        registry.close()

    still_alive = [t for t in engine_threads() if t not in threads_before]
    assert still_alive == []


def test_ac4_an_input_after_close_is_refused_without_a_task(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    threads_before = set(engine_threads())
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        websocket, _ = join_and_sync(stack, client, code, recorder)
        registry.close()
        events_after_close = list(recorder.events)

        websocket.send_text(SELECT_TEXT)
        websocket.send_text(UNDO_TEXT)
        time.sleep(SETTLE_SECONDS)

        assert recorder.events == events_after_close

    assert [t for t in engine_threads() if t not in threads_before] == []
