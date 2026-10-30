"""Shared setup of the tests of spec 025: group decision on help.

This module is not a test file: pytest does not collect it. The tests of spec 025
are in `tests/test_spec_025_*.py`, one file per criterion group:

- `test_spec_025_ac01_help_mode_at_creation.py`: AC-1;
- `test_spec_025_ac02_vote_passes.py`: AC-2;
- `test_spec_025_ac03_rejected_and_timed_out.py`: AC-3;
- `test_spec_025_ac04_ac05_hidden_panels_and_free_checks.py`: AC-4 and AC-5;
- `test_spec_025_ac06_one_vote_one_ballot.py`: AC-6;
- `test_spec_025_ac07_vote_banner.py`: AC-7;
- `test_spec_025_ac08_banner_layout_and_keyboard.py`: AC-8;
- `test_spec_025_ac09_reconnection_and_reload.py`: AC-9.

The rules are tested on `handle_message`, `tick`, `replay`, `snapshot_for` and
`after_restart` with exact clock values. `V3` is the room of the spec's "Test
harness": `p1` (host), `p2` and `p3` joined at `NOW` (seq 3), then the host set
the vote mode with a budget of 5 letters and 1 word (seq 4). The WebSocket tests
use spec 011's `TestClient`; the timing one uses the fake clock of conftest. The
page is tested with spec 040's mocked socket, vote frames built with `VoteOpened`
and `VoteClosed`, and, for AC-1 and AC-2, with two browsers on the live server.

The new names of `nock.room` (`OpenVote`, `RoomState.open_vote`,
`RoomState.last_vote_id`, `RoomConfig.vote_timeout_seconds`) are reached through
the helpers below when a test runs. So while they are missing, each test that needs
them fails with an AttributeError, and the collection of the other tests goes on.

This module holds what more than one test file uses. What only one file uses stays
in that file. The fixtures (`fx01_grid`, `dist_dir`, `catalogue`, `registry`,
`client`) are defined in each file that asks for them, as thin wrappers around
`grid_from_text`, `make_dist_dir`, `make_catalogue` and `make_registry`: a fixture
imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import (
    Browser,
    FloatRect,
    Locator,
    Page,
    WebSocketRoute,
    expect,
)
from starlette.testclient import WebSocketTestSession

import nock.room
from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellTarget,
    ChangeSettings,
    Check,
    CheckResult,
    ClientMessage,
    EditLetter,
    ErrorCode,
    ErrorMessage,
    GridTarget,
    HelpMode,
    Join,
    Ping,
    PlayerState,
    PlayerView,
    Pong,
    Reveal,
    RevealBudget,
    RoomSettings,
    ServerMessage,
    SettingsChanged,
    Snapshot,
    Vote,
    VoteClosed,
    VoteOpened,
    VoteOutcome,
    WordTarget,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    LogEntry,
    Outcome,
    PlayerRecord,
    RoomConfig,
    RoomState,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    tick,
)
from room_panels import open_host_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"
INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'

# ---- Rules: the rooms of the spec's "Test harness" ---------------------------

ROOM_CODE = "ABCDEF"
NOW = 2_000_000.0
NICKNAMES = ["Ana", "Bob", "Cy", "Dee", "Eve", "Fay", "Gus", "Hal"]
VOTE_TIMEOUT_SECONDS = 20  # the default of RoomConfig.vote_timeout_seconds
FIVE_AND_ONE = RevealBudget(letters=5, words=1)

# `tick` with only the vote step acting (spec 025, "Test harness").
QUIET = RoomConfig(silence_timeout_seconds=600)

VOTE_SETTINGS = ChangeSettings(help_mode=HelpMode.VOTE, reveal_budget=FIVE_AND_ONE)
REVEAL_1_0 = Reveal(target=CellTarget(row=1, column=0))
GRID_CHECK = Check(target=GridTarget())
TAMIS = WordTarget(row=0, column=0, clue_index=0)
MIME = WordTarget(row=0, column=2, clue_index=0)

Cell = tuple[int, int]

# The solution of FX-01 (specs/_reference.md), in row-major order.
SOLUTION: dict[Cell, str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        SOLUTION[(_row, _offset + 1)] = _letter


def token_of(number: int) -> str:
    """The resume token of player `p<number>`."""
    return f"player-token-number-{number:02d}"


class Play:
    """A room driven through the rules, keeping every entry they logged.

    Each call stores the outcome's state as the room's state, so a test reads the
    room as the live server would hold it, and `entries` holds the log for `replay`.
    """

    def __init__(self, state: RoomState) -> None:
        self.state = state
        self.entries: list[LogEntry] = []

    def apply(self, outcome: Outcome) -> Outcome:
        """Keep the state and the entries of one step, and return the outcome."""
        self.state = outcome.state
        self.entries.extend(outcome.entries)
        return outcome

    def join(self, number: int, now: float = NOW) -> Outcome:
        """Join player `p<number>` with the nickname of that number."""
        join = Join(nickname=NICKNAMES[number - 1], resume_token=None)
        outcome = join_room(self.state, join, now, f"p{number}", token_of(number))
        assert outcome.entries, f"p{number} could not join"
        return self.apply(outcome)

    def send(
        self,
        player_id: str,
        message: ClientMessage,
        now: float = NOW,
        config: RoomConfig = QUIET,
    ) -> Outcome:
        """Apply one message of a player."""
        outcome = handle_message(self.state, player_id, message, now, config)
        return self.apply(outcome)

    def tick(self, now: float) -> Outcome:
        """Apply the passing of time with `QUIET`."""
        return self.apply(tick(self.state, now, QUIET))

    def disconnect(self, player_id: str, now: float = NOW) -> Outcome:
        """Apply the closing of a player's connection."""
        return self.apply(disconnect_player(self.state, player_id, now))


def vote_room(grid: Grid, count: int) -> Play:
    """A FX-01 room where `p1` (host) to `p<count>` joined at NOW, in vote mode.

    The joins take seq 1 to `count`, the host's change of settings seq `count + 1`.
    """
    play = Play(new_room(ROOM_CODE, grid, NOW))
    for number in range(1, count + 1):
        play.join(number)
    outcome = play.send("p1", VOTE_SETTINGS)
    assert outcome.reply == ()
    assert play.state.seq == count + 1
    return play


def v3(grid: Grid) -> Play:
    """The room `V3` of the spec: seq 4, vote mode, budget 5 letters and 1 word."""
    return vote_room(grid, 3)


def write(play: Play, player_id: str, cells: list[tuple[int, int, str]]) -> None:
    """Write letters through the rules, at NOW, one edit after another."""
    for row, column, letter in cells:
        outcome = play.send(
            player_id, EditLetter(row=row, column=column, letter=letter)
        )
        assert outcome.reply == (), f"the edit at ({row}, {column}) was refused"


def all_but_last_cell() -> list[tuple[int, int, str]]:
    """The 17 right letters of FX-01 other than (4, 4), in row-major order."""
    cells: list[tuple[int, int, str]] = []
    for (row, column), letter in SOLUTION.items():
        if (row, column) != (4, 4):
            cells.append((row, column, letter))
    return cells


def events_of(outcome: Outcome) -> list[object]:
    """The event of each entry of an outcome, in order."""
    events: list[object] = []
    for entry in outcome.entries:
        events.append(entry.event)
    return events


def refusal_code(outcome: Outcome) -> ErrorCode:
    """The code of the single error an outcome replies with."""
    assert len(outcome.reply) == 1, outcome.reply
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage), refusal
    return refusal.code


def seen_at(state: RoomState, player_id: str, now: float) -> RoomState:
    """The state with only `last_seen_at` and `last_input_at` of one player set."""
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id == player_id:
            player = player.model_copy(
                update={"last_seen_at": now, "last_input_at": now}
            )
        players.append(player)
    return state.model_copy(update={"players": tuple(players)})


def hint_window_fields() -> list[str]:
    """The names of the player fields that hold the hint-limit window (B-031).

    `hints.md` rule 2 keeps each player's window in the room without naming the
    field, so a field of `PlayerRecord` counts when its name holds `hint`.
    """
    names: list[str] = []
    for name in PlayerRecord.model_fields:
        if "hint" in name:
            names.append(name)
    return names


def with_times_of(state: RoomState, reference: RoomState) -> RoomState:
    """The state with each player's times and hint window taken from `reference`.

    The times are `last_seen_at` and `last_input_at`; the hint window is the
    private count of the hint limit (`hints.md` rule 2), which a request of the
    play fills and a comparison of the rest of the room does not care about.
    """
    times: dict[str, dict[str, object]] = {}
    for player in reference.players:
        kept: dict[str, object] = {
            "last_seen_at": player.last_seen_at,
            "last_input_at": player.last_input_at,
        }
        for name in hint_window_fields():
            kept[name] = getattr(player, name)
        times[player.player_id] = kept
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id in times:
            player = player.model_copy(update=times[player.player_id])
        players.append(player)
    return state.model_copy(update={"players": tuple(players)})


def opened(
    seq: int,
    vote_id: int,
    player_id: str,
    request: Check | Reveal,
    eligible_voters: int,
    timeout_seconds: int = VOTE_TIMEOUT_SECONDS,
) -> VoteOpened:
    """The `vote_opened` event of the rule (spec 025, step 3)."""
    return VoteOpened(
        seq=seq,
        vote_id=vote_id,
        player_id=player_id,
        request=request,
        timeout_seconds=timeout_seconds,
        eligible_voters=eligible_voters,
    )


def closed(
    seq: int,
    vote_id: int,
    outcome: VoteOutcome,
    yes_votes: int,
    eligible_voters: int,
) -> VoteClosed:
    """A `vote_closed` event."""
    return VoteClosed(
        seq=seq,
        vote_id=vote_id,
        outcome=outcome,
        yes_votes=yes_votes,
        eligible_voters=eligible_voters,
    )


# ---- Rules: the new names of nock.room, reached at test time ------------------


def open_vote_of(state: RoomState) -> nock.room.OpenVote | None:
    """The room's `open_vote` (spec 025)."""
    return state.open_vote


def last_vote_id_of(state: RoomState) -> int:
    """The room's `last_vote_id` (spec 025)."""
    return state.last_vote_id


def open_vote(
    opened_event: VoteOpened,
    opened_at: float,
    eligible: tuple[str, ...],
    yes: tuple[str, ...],
    no: tuple[str, ...] = (),
) -> nock.room.OpenVote:
    """An `OpenVote` (spec 025) with the given fields."""
    return nock.room.OpenVote(
        opened=opened_event, opened_at=opened_at, eligible=eligible, yes=yes, no=no
    )


def vote_timeout_of(config: RoomConfig) -> int:
    """The config's `vote_timeout_seconds` (spec 025)."""
    return config.vote_timeout_seconds


def config_with_vote_timeout(seconds: int) -> RoomConfig:
    """`QUIET` with `vote_timeout_seconds` set (spec 025)."""
    return RoomConfig(silence_timeout_seconds=600, vote_timeout_seconds=seconds)


# ---- WebSocket ----------------------------------------------------------------

WAIT_SECONDS = 5.0


class FakeClock(Protocol):
    """The `fake_clock` fixture of conftest: a clock moved by hand."""

    now: float

    def __call__(self) -> float: ...

    def advance(self, seconds: float) -> None: ...


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


def credits() -> dict[str, str]:
    """The credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixtures)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """A `dist` directory with a minimal `index.html` (the `dist_dir` fixtures)."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def make_catalogue(grid: Grid) -> Catalogue:
    """A catalogue holding `grid` as published entry 1 (the `catalogue` fixtures)."""
    entry = CatalogueEntry(
        number=1,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        **credits(),
        grid=grid,
    )
    return Catalogue(entries=(entry,))


def make_registry() -> RoomRegistry:
    """A registry whose throttle never refuses and that never times a socket out."""
    config = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)
    return RoomRegistry(config=config)


class Peer:
    """A simulated client: one socket, one reader thread that keeps what arrives."""

    def __init__(self, websocket: WebSocketTestSession, name: str) -> None:
        self._websocket = websocket
        self.name = name
        self._arrived = threading.Condition()
        self._received: list[ServerMessage] = []
        self._failures: list[str] = []
        reader = threading.Thread(target=self._read, daemon=True)
        reader.start()

    def _read(self) -> None:
        while True:
            try:
                text = self._websocket.receive_text()
            except BaseException:  # the socket closed
                return
            try:
                message = parse_server_message(text)
            except ValueError as error:
                with self._arrived:
                    self._failures.append(f"unparsable message {text!r}: {error}")
                    self._arrived.notify_all()
                continue
            with self._arrived:
                self._received.append(message)
                self._arrived.notify_all()

    def send(self, message: ClientMessage) -> None:
        self._websocket.send_text(message.model_dump_json())

    def send_text(self, text: str) -> None:
        self._websocket.send_text(text)

    def messages(self) -> list[ServerMessage]:
        with self._arrived:
            return list(self._received)

    def snapshot(self) -> Snapshot:
        first = self.messages()[0]
        assert isinstance(first, Snapshot), first
        return first

    def you(self) -> str:
        return self.snapshot().you

    def after_snapshot(self) -> list[ServerMessage]:
        """Every message after the first snapshot, in order."""
        return self.messages()[1:]

    def numbered_from(self, first_seq: int) -> list[ServerMessage]:
        """The events after the snapshot whose seq is `first_seq` or more."""
        found: list[ServerMessage] = []
        for message in self.after_snapshot():
            seq = getattr(message, "seq", None)
            if isinstance(seq, int) and seq >= first_seq:
                found.append(message)
        return found

    def errors(self) -> list[ErrorCode]:
        codes: list[ErrorCode] = []
        for message in self.after_snapshot():
            if isinstance(message, ErrorMessage):
                codes.append(message.code)
        return codes

    def last_seq(self) -> int:
        last = self.snapshot().seq
        for message in self.after_snapshot():
            seq = getattr(message, "seq", None)
            if isinstance(seq, int):
                last = seq
        return last

    def wait_for_seq(self, seq: int, what: str) -> None:
        self.wait_until(lambda: self.last_seq() >= seq, what)

    def wait_until(
        self, condition: Callable[[], bool], what: str, timeout: float = WAIT_SECONDS
    ) -> None:
        """Wait up to `timeout` seconds for `condition`, else fail the test."""
        with self._arrived:
            met = self._arrived.wait_for(
                lambda: condition() or len(self._failures) > 0, timeout
            )
            failures = list(self._failures)
        if failures:
            pytest.fail(failures[0])
        if not met:
            pytest.fail(f"{self.name}: timed out after {timeout}s waiting for {what}")


def connect(
    stack: contextlib.ExitStack, client: TestClient, code: str, name: str
) -> Peer:
    websocket = stack.enter_context(client.websocket_connect(f"/api/rooms/{code}/ws"))
    return Peer(websocket, name)


def join_peer(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    name: str,
    resume_token: str | None = None,
) -> Peer:
    """Open a socket in `stack`, join, and return once the snapshot arrived."""
    peer = connect(stack, client, code, name)
    peer.send(Join(nickname=name, resume_token=resume_token))
    peer.wait_until(lambda: len(peer.messages()) >= 1, f"the snapshot of {name}")
    return peer


def join_peers(
    stack: contextlib.ExitStack, client: TestClient, code: str, names: list[str]
) -> list[Peer]:
    """Join one peer per name in turn; return once all saw every join."""
    peers: list[Peer] = []
    for name in names:
        peers.append(join_peer(stack, client, code, name))
    for peer in peers:
        peer.wait_for_seq(len(names), "every player_joined event")
    return peers


def set_vote_mode(host: Peer, peers: list[Peer]) -> int:
    """The host sets the vote mode (5 letters, 1 word); return its seq once seen."""
    seq = host.last_seq() + 1
    host.send(VOTE_SETTINGS)
    for peer in peers:
        peer.wait_for_seq(seq, "the vote mode")
    return seq


# ---- Browser: mocked socket ---------------------------------------------------

MOCK_CODE = "ABC123"
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400

# Makes `matchMedia("(pointer: coarse)")` report a match, other queries unchanged
# (the script of spec 009, for the touch contexts of Firefox and WebKit).
COARSE_POINTER_SCRIPT = r"""
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\s/g, '') !== '(pointer:coarse)') {
      return result;
    }
    return new Proxy(result, {
      get(target, property) {
        if (property === 'matches') {
          return true;
        }
        const value = target[property];
        return typeof value === 'function' ? value.bind(target) : value;
      },
    });
  };
})();
"""


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def fr_text(key: str, **values: str | int) -> str:
    """The `fr.json` text of `key` with each `{name}` replaced by its value."""
    texts = load_fr()
    if key not in texts:
        pytest.fail(f"fr.json has no key {key!r}")
    text = texts[key]
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def without_pings(frames: list[str]) -> list[str]:
    """The frames without the keep-alive `ping` frames of the page (spec 017)."""
    kept: list[str] = []
    for frame in frames:
        if json.loads(frame)["type"] != "ping":
            kept.append(frame)
    return kept


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test.

    It keeps every socket the page opens (a reconnection opens a new one) and the
    frames each one sent, `ping` frames included. Like the real server (specs 017
    and 039), it answers each `ping` with one `pong` on the socket that sent it:
    without the answer, the page takes 4 s without a frame from the server for a
    lost connection (spec 017, AC-4). `send` and `close` act on the newest socket.
    """

    def __init__(self, page: Page) -> None:
        self.page = page
        self.routes: list[WebSocketRoute] = []
        self.route_frames: list[list[str]] = []

    def handle(self, route: WebSocketRoute) -> None:
        frames: list[str] = []
        self.routes.append(route)
        self.route_frames.append(frames)

        def on_message(message: str | bytes) -> None:
            text = message if isinstance(message, str) else message.decode("utf-8")
            frames.append(text)
            if parse_client_message(text) == Ping():
                route.send(Pong().model_dump_json())

        route.on_message(on_message)

    def send(self, frame: str) -> None:
        self.routes[-1].send(frame)

    def close(self, code: int) -> None:
        self.routes[-1].close(code=code)

    def frames_without_pings(self) -> list[str]:
        """Every frame of every socket, in socket order, without the pings."""
        frames: list[str] = []
        for route_frames in self.route_frames:
            frames.extend(without_pings(route_frames))
        return frames

    def wait_for_frames(self, count: int) -> None:
        """Wait until the page sent `count` frames, `ping` frames not counted."""
        wait_until(self.page, lambda: len(self.frames_without_pings()) >= count)

    def wait_for_join_on_socket(self, index: int) -> Join:
        """Wait for the first frame of socket `index`, which must be a join."""
        wait_until(self.page, lambda: len(self.route_frames) > index)
        wait_until(self.page, lambda: len(without_pings(self.route_frames[index])) > 0)
        first = parse_client_message(without_pings(self.route_frames[index])[0])
        assert isinstance(first, Join), first
        return first

    def votes(self) -> list[Vote]:
        found: list[Vote] = []
        for frame in self.frames_without_pings():
            message = parse_client_message(frame)
            if isinstance(message, Vote):
                found.append(message)
        return found

    def raw_votes(self) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        for frame in self.frames_without_pings():
            parsed = json.loads(frame)
            if parsed["type"] == "vote":
                found.append(parsed)
        return found

    def checks(self) -> list[Check]:
        found: list[Check] = []
        for frame in self.frames_without_pings():
            message = parse_client_message(frame)
            if isinstance(message, Check):
                found.append(message)
        return found

    def reveals(self) -> list[Reveal]:
        found: list[Reveal] = []
        for frame in self.frames_without_pings():
            message = parse_client_message(frame)
            if isinstance(message, Reveal):
                found.append(message)
        return found


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def settle(page: Page) -> None:
    """Give the page time to do things that must not happen."""
    page.wait_for_timeout(SETTLE_MS)


def player_view(
    player_id: str,
    nickname: str,
    colour: int,
    *,
    is_host: bool = False,
    state: PlayerState = PlayerState.ACTIVE,
) -> PlayerView:
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=state,
        is_host=is_host,
        muted=False,
        selection=None,
    )


def three_players() -> list[PlayerView]:
    """`p1` (`you`, `Ana`, host), `p2` (`Bob`) and `p3` (`Cy`)."""
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "Bob", 1),
        player_view("p3", "Cy", 2),
    ]


EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]


def eight_players() -> list[PlayerView]:
    """Spec 013 AC-6's eight players: `p1` (`you`, host) to `p8`."""
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        players.append(
            player_view(f"p{number}", EIGHT_NICKNAMES[number - 1], number - 1)
        )
    return players


def room_settings(help_mode: HelpMode) -> RoomSettings:
    return RoomSettings(help_mode=help_mode, reveal_budget=FIVE_AND_ONE, locked=False)


def snapshot_frame(
    grid: Grid,
    *,
    seq: int = 5,
    players: list[PlayerView] | None = None,
    help_mode: HelpMode = HelpMode.VOTE,
    vote: VoteOpened | None = None,
    reveal_budget: RevealBudget = FIVE_AND_ONE,
    solved: bool = False,
) -> str:
    """A FX-01 snapshot for `p1`, with `vote` as its `open_vote`."""
    shown_players = three_players() if players is None else players
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_TOKEN,
        grid=grid_view(grid),
        players=tuple(shown_players),
        settings=room_settings(help_mode),
        reveal_budget=reveal_budget,
        flags=(),
        chat=(),
        open_vote=vote,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=solved,
    )
    return snapshot.model_dump_json()


def open_room(
    page: Page,
    base_url: str,
    grid: Grid,
    *,
    seq: int = 5,
    players: list[PlayerView] | None = None,
    help_mode: HelpMode = HelpMode.VOTE,
    vote: VoteOpened | None = None,
    reveal_budget: RevealBudget = FIVE_AND_ONE,
    solved: bool = False,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket and show a FX-01 snapshot as `p1`."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{MOCK_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    mock.wait_for_join_on_socket(0)
    frame = snapshot_frame(
        grid,
        seq=seq,
        players=players,
        help_mode=help_mode,
        vote=vote,
        reveal_budget=reveal_budget,
        solved=solved,
    )
    mock.send(frame)
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(25)
    wait_for_fonts(page)
    return mock


def settings_frame(seq: int, help_mode: HelpMode) -> str:
    """A `settings_changed` by `p1` to `help_mode`, budget 5 letters and 1 word."""
    event = SettingsChanged(
        seq=seq,
        player_id="p1",
        settings=room_settings(help_mode),
        reveal_budget=FIVE_AND_ONE,
    )
    return event.model_dump_json()


def grid_check_line_frame(seq: int) -> str:
    """Spec 013 AC-6's feed line: an empty grid check by `p2`."""
    event = CheckResult(
        seq=seq, player_id="p2", target=GridTarget(), correct=(), wrong=()
    )
    return event.model_dump_json()


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def expect_selection(page: Page, row: int, column: int, word: str) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-word", word)


def make_page(
    browser: Browser, browser_name: str, width: int, height: int, touch: bool
) -> tuple[Page, Callable[[], None]]:
    """A desktop or touch page (spec 024's contexts); return it and its closer."""
    viewport = {"width": width, "height": height}
    if not touch:
        context = browser.new_context(viewport=viewport)
    elif browser_name == "firefox":
        context = browser.new_context(
            viewport=viewport, has_touch=True, device_scale_factor=2
        )
    else:
        context = browser.new_context(
            viewport=viewport,
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    if touch and browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    return context.new_page(), context.close


def box_of(locator: Locator) -> FloatRect:
    box = locator.bounding_box()
    assert box is not None, "the element has no box"
    return box


# ---- Browser: live server -----------------------------------------------------


def seed_nickname(page: Page, nickname: str) -> None:
    """Save `nickname` as this device's nickname (spec 010) before the page runs."""
    script = f"localStorage.setItem('nock.nickname', {json.dumps(nickname)})"
    page.context.add_init_script(script)


def feed_lines(page: Page, kind: str) -> Locator:
    selector = f'[data-testid="feed-item"][data-kind="{kind}"]'
    return page.get_by_test_id("activity-feed").locator(selector)


# The centre of the label of the help-mode radio of a mode (spec 043: the
# radios are drawn as a segmented control, so their labels take the click).
MODE_LABEL_CENTRE_SCRIPT = """
mode => {
  const selector = `[data-testid="help-mode-option"][value="${mode}"]`;
  const box = document.querySelector(selector).labels[0].getBoundingClientRect();
  return [box.left + box.width / 2, box.top + box.height / 2];
}
"""


def host_sets_help_mode(page: Page, help_mode: str) -> None:
    """The host picks a help mode in spec 014's settings form and saves it.

    Spec 043: the form is in the host's settings sheet, opened from the Menu, and
    the mode is a radio of a segmented control, chosen with a click on its label.
    """
    open_host_settings(page)
    x, y = page.evaluate(MODE_LABEL_CENTRE_SCRIPT, help_mode)
    page.mouse.click(x, y)
    checked = page.locator(f'[data-testid="help-mode-option"][value="{help_mode}"]')
    expect(checked).to_be_checked(timeout=WAIT_TIMEOUT_MS)
    page.get_by_test_id("settings-save").click(timeout=WAIT_TIMEOUT_MS)
