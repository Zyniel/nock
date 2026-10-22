"""Shared setup of the tests of spec 021: clue flag.

This module is not a test file: pytest does not collect it. The tests of spec 021
are in `tests/test_spec_021_*.py`, one file per criterion group:

- `test_spec_021_ac01_ac02_flag_reaches_everyone.py`: AC-1 (rule, WebSocket, two
  browsers on the live server) and AC-2 (the feed line, live server);
- `test_spec_021_ac03_flag_clears.py`: AC-3 (rule, WebSocket, page with a mocked
  socket);
- `test_spec_021_ac04_ac05_one_flag_and_refusals.py`: AC-4 (rule, page) and AC-5
  (rule);
- `test_spec_021_ac06_flag_button.py`: AC-6 (page);
- `test_spec_021_ac07_ac08_departures_and_reload.py`: AC-7 (rule, WebSocket with a
  fake clock, page) and AC-8 (`replay`, `RoomStore`, page);
- `test_spec_021_ac09_ac10_marker_and_a11y.py`: AC-9 and AC-10 (page);
- `test_spec_021_ac11_layout.py`: AC-11 (page, every window, desktop and touch).

It holds what more than one of those files uses: the clue references of FX-01,
the flag steps on `handle_message`, the snapshot with flags sent on the mocked
socket, and the reading of a clue's marker. It builds on spec 024's harness (the
rooms `FULL17`, the simulated WebSocket client, the mocked socket that answers
pings, spec 035's walker and scans, spec 013's contexts): the test files import
those from `spec024_harness` directly. The pencil edits of spec 020 come from
`spec020_harness`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from playwright.sync_api import Locator, Page, expect

from fonts_ready import wait_for_fonts
from nock.protocol import (
    ClueRef,
    Flag,
    FlagChanged,
    FlagView,
    GridView,
    HelpMode,
    PlayerView,
    RoomSettings,
    Snapshot,
)
from nock.room import Outcome, RoomConfig, RoomState, handle_message, snapshot_for
from spec024_harness import (
    DEFAULT_BUDGET,
    NOW,
    QUIET_MS,
    ROOM_CODE,
    SNAPSHOT_RESUME_TOKEN,
    WAIT_TIMEOUT_MS,
    MockRoomSocket,
    Peer,
    expect_seq,
    player_record,
    player_view,
    wait_until_page,
)

# ---- The words of FX-01 by clue reference ("Test harness") ----

TAMIS = ClueRef(row=0, column=0, clue_index=0)
NAVAL = ClueRef(row=0, column=0, clue_index=1)
MIME = ClueRef(row=0, column=2, clue_index=0)
IDES = ClueRef(row=0, column=3, clue_index=0)
SENT = ClueRef(row=0, column=4, clue_index=0)
VIDE = ClueRef(row=2, column=0, clue_index=0)
AMEN = ClueRef(row=3, column=0, clue_index=0)
LEST = ClueRef(row=4, column=0, clue_index=0)
EIGHT_WORDS: dict[str, ClueRef] = {
    "TAMIS": TAMIS,
    "NAVAL": NAVAL,
    "MIME": MIME,
    "IDES": IDES,
    "SENT": SENT,
    "VIDE": VIDE,
    "AMEN": AMEN,
    "LEST": LEST,
}

Cell = tuple[int, int]
IDES_CELLS: list[Cell] = [(1, 3), (2, 3), (3, 3), (4, 3)]
MIME_CELLS: list[Cell] = [(1, 2), (2, 2), (3, 2), (4, 2)]
IDES_CLUE_TEXT = "Fatales à César"

# The values of the new `fr.json` keys ("New `fr.json` keys"), which AC-10 checks
# in the file: the page tests compare with them directly.
FLAG_BUTTON_TEXT = "Je bloque"
FLAG_BUTTON_LABEL = "Je bloque sur ce mot"
FLAG_MARKER = "\u2691"  # BLACK FLAG

# The players of the browser tests with a mocked socket ("Test harness").
NICKNAMES = {"p1": "Ana", "p2": "Bob", "p3": "Cy"}


def clue_key(clue: ClueRef) -> str:
    """The key of a word, as the grid's `data-word` shows it, such as `0,2,0`."""
    return f"{clue.row},{clue.column},{clue.clue_index}"


# ---- Flags on handle_message ----


def send_flag(
    state: RoomState,
    player_id: str,
    clue: ClueRef | None,
    now: float = NOW,
    config: RoomConfig | None = None,
) -> Outcome:
    """Send `Flag(clue)` from a player with `handle_message`.

    Args:
        state: The room.
        player_id: The sender.
        clue: The flagged clue, or None to remove the sender's flag.
        now: The clock time of the step.
        config: The room's thresholds; None for the defaults.

    Returns:
        The outcome of the step.
    """
    message = Flag(clue=clue)
    if config is None:
        return handle_message(state, player_id, message, now)
    return handle_message(state, player_id, message, now, config)


def accepted_flag(
    state: RoomState, player_id: str, clue: ClueRef | None, now: float = NOW
) -> Outcome:
    """Send `Flag(clue)`, after checking that no reply answered it."""
    outcome = send_flag(state, player_id, clue, now)
    assert outcome.reply == (), outcome.reply
    return outcome


def flag_of(state: RoomState, player_id: str) -> ClueRef | None:
    """The `flag` of one player's record."""
    return player_record(state, player_id).flag


def flags_by_player(state: RoomState) -> dict[str, ClueRef | None]:
    """The `flag` of every player of the room, by player id."""
    flags: dict[str, ClueRef | None] = {}
    for player in state.players:
        flags[player.player_id] = player.flag
    return flags


def snapshot_flags(state: RoomState) -> tuple[FlagView, ...]:
    """The `flags` of the snapshot that `p1` gets."""
    return snapshot_for(state, "p1").flags


# ---- The WebSocket ----


def flag_changes(peer: Peer) -> list[FlagChanged]:
    """Every `flag_changed` a simulated client received after its snapshot."""
    found: list[FlagChanged] = []
    for message in peer.messages()[1:]:
        if isinstance(message, FlagChanged):
            found.append(message)
    return found


# ---- The page with a mocked socket ----


def three_players() -> list[PlayerView]:
    """`p1` (Ana, `you`, host), `p2` (Bob) and `p3` (Cy)."""
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "Bob", 1),
        player_view("p3", "Cy", 2),
    ]


def snapshot_with_flags(
    view: GridView,
    seq: int,
    players: list[PlayerView],
    flags: list[FlagView],
    solved: bool = False,
) -> Snapshot:
    """A snapshot for `p1` with some flags, help mode `free`, no chat or vote.

    Args:
        view: The grid view.
        seq: The snapshot's seq.
        players: The roster.
        flags: The snapshot's `flags`.
        solved: Whether the grid is solved.

    Returns:
        The snapshot.
    """
    settings = RoomSettings(
        help_mode=HelpMode.FREE, reveal_budget=DEFAULT_BUDGET, locked=False
    )
    return Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=tuple(players),
        settings=settings,
        reveal_budget=DEFAULT_BUDGET,
        flags=tuple(flags),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=solved,
    )


def open_with_snapshot(
    page: Page, base_url: str, snapshot_text: str, seq: int, cell_count: int
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket, join as Ana and send a snapshot frame.

    Args:
        page: A fresh page.
        base_url: The live server, which serves the built client.
        snapshot_text: The JSON text of the snapshot the mock sends.
        seq: The snapshot's seq, which the page shows once it applied it.
        cell_count: The number of cells of the snapshot's grid.

    Returns:
        The mocked socket, which answers each ping with a pong.
    """
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until_page(page, lambda: len(mock.frames_without_pings()) > 0, "the join")
    mock.send(snapshot_text)
    expect_seq(page, seq)
    expect(page.get_by_test_id("cell")).to_have_count(cell_count)
    wait_for_fonts(page)
    return mock


def open_flag_room(
    page: Page,
    base_url: str,
    view: GridView,
    *,
    flags: list[FlagView] | None = None,
    players: list[PlayerView] | None = None,
    seq: int = 5,
) -> MockRoomSocket:
    """Open the room on a mocked socket with a grid view, a roster and flags.

    Args:
        page: A fresh page.
        base_url: The live server, which serves the built client.
        view: The snapshot's grid (FX-01 or FX-02, with its letters).
        flags: The snapshot's `flags` (default: none).
        players: The roster (default: `three_players()`).
        seq: The snapshot's seq.

    Returns:
        The mocked socket.
    """
    shown_flags = [] if flags is None else flags
    shown_players = three_players() if players is None else players
    snapshot = snapshot_with_flags(view, seq, shown_players, shown_flags)
    text = snapshot.model_dump_json()
    return open_with_snapshot(page, base_url, text, seq, len(view.cells))


def flag_changed_frame(seq: int, player_id: str, clue: ClueRef | None) -> str:
    """The JSON text of a `flag_changed` event."""
    return FlagChanged(seq=seq, player_id=player_id, clue=clue).model_dump_json()


def clue_at(page: Page, clue: ClueRef) -> Locator:
    """The `clue` element of a clue reference: its index in its clue cell."""
    cell = f'[data-testid="cell"][data-row="{clue.row}"][data-column="{clue.column}"]'
    selector = f'{cell} [data-testid="clue"][data-clue-index="{clue.clue_index}"]'
    return page.locator(selector)


def select_word(page: Page, clue: ClueRef, touch: bool = False) -> None:
    """Tap the clue of a word (spec 007) and wait until the grid selects it."""
    element = clue_at(page, clue)
    if touch:
        element.tap(timeout=WAIT_TIMEOUT_MS)
    else:
        element.click(timeout=WAIT_TIMEOUT_MS)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-word", clue_key(clue))


def flag_label(names: list[str]) -> str:
    """The text `t("flag.marker_label", {names})` for nicknames in that order.

    It is built from the spec's value of `flag.marker_label` (`Bloqué : {names}`),
    which AC-10 checks in `fr.json`.
    """
    return "Bloqué : " + ", ".join(names)


# What a clue element shows of the flags: its `data-flagged`, how many
# `clue-flag` and `clue-flag-label` elements it holds and, when it holds one of
# each, their attributes and texts.
MARKER_SCRIPT = r"""
clue => {
  const markers = clue.querySelectorAll('[data-testid="clue-flag"]');
  const labels = clue.querySelectorAll('[data-testid="clue-flag-label"]');
  const result = {
    flagged: clue.getAttribute('data-flagged'),
    markers: markers.length,
    labels: labels.length,
  };
  if (markers.length === 1) {
    result.flaggedBy = markers[0].getAttribute('data-flagged-by');
    result.ariaHidden = markers[0].getAttribute('aria-hidden');
    result.markerText = markers[0].textContent.trim();
  }
  if (labels.length === 1) {
    result.labelText = labels[0].textContent.trim();
    result.labelHidden = labels[0].classList.contains('visually-hidden');
  }
  return result;
}
"""

# The `data-flagged` of every `clue` element, by the key of its word.
FLAGGED_MAP_SCRIPT = r"""
() => {
  const found = {};
  for (const clue of document.querySelectorAll('[data-testid="clue"]')) {
    const cell = clue.closest('[data-testid="cell"]');
    const key = [
      cell.getAttribute('data-row'),
      cell.getAttribute('data-column'),
      clue.getAttribute('data-clue-index'),
    ].join(',');
    found[key] = clue.getAttribute('data-flagged');
  }
  return found;
}
"""


def read_marker(page: Page, clue: ClueRef) -> dict[str, Any]:
    """What the clue of a word shows of the flags (a JSON object from the page).

    The values are what the page holds, so their types are the page's (`Any`).
    """
    reading = clue_at(page, clue).evaluate(MARKER_SCRIPT)
    assert isinstance(reading, dict)
    return reading


def flagged_reading(flagged_by: str, names: list[str]) -> dict[str, object]:
    """What a flagged clue must show ("Client: the clue marker").

    Args:
        flagged_by: The expected `data-flagged-by`, such as `p2 p3`.
        names: The flaggers' nicknames, in the same order.

    Returns:
        The expected reading of `read_marker`.
    """
    return {
        "flagged": "true",
        "markers": 1,
        "labels": 1,
        "flaggedBy": flagged_by,
        "ariaHidden": "true",
        "markerText": FLAG_MARKER,
        "labelText": flag_label(names),
        "labelHidden": True,
    }


UNFLAGGED_READING: dict[str, object] = {"flagged": "false", "markers": 0, "labels": 0}


def flagged_map(page: Page) -> dict[str, Any]:
    """The `data-flagged` of every clue element, by word key (`0,3,0`)."""
    found = page.evaluate(FLAGGED_MAP_SCRIPT)
    assert isinstance(found, dict)
    return found


def expected_flagged_map(flagged: list[ClueRef]) -> dict[str, str]:
    """`true` for the flagged words of FX-01 and `false` for the others."""
    expected: dict[str, str] = {}
    flagged_keys = {clue_key(clue) for clue in flagged}
    for clue in EIGHT_WORDS.values():
        key = clue_key(clue)
        expected[key] = "true" if key in flagged_keys else "false"
    return expected


def settle_on(page: Page, read: Callable[[], object], expected: object) -> None:
    """Wait until `read()` gives `expected`, then assert it (the diff on failure).

    Args:
        page: The page whose clock paces the reads.
        read: The reading, made in Python.
        expected: The value it must reach within WAIT_TIMEOUT_MS.
    """
    waited_ms = 0
    while read() != expected and waited_ms < WAIT_TIMEOUT_MS:
        page.wait_for_timeout(50)
        waited_ms += 50
    assert read() == expected


def expect_marker(page: Page, clue: ClueRef, flagged_by: str, names: list[str]) -> None:
    """Wait until a clue shows exactly the flaggers given, else fail."""
    expected = flagged_reading(flagged_by, names)
    settle_on(page, lambda: read_marker(page, clue), expected)


def expect_unflagged(page: Page, clue: ClueRef) -> None:
    """Wait until a clue shows no flag, else fail."""
    settle_on(page, lambda: read_marker(page, clue), UNFLAGGED_READING)


def frames_sent_by(
    page: Page, mock: MockRoomSocket, action: Callable[[], object]
) -> list[str]:
    """Do `action`, then return the frames the page sent, pings left out.

    It waits for a first frame, then QUIET_MS more for any other one.

    Args:
        page: The room page.
        mock: Its mocked socket.
        action: What the test does, such as a click.

    Returns:
        The frames sent after `action` started, in order.
    """
    before = len(mock.frames_without_pings())
    action()
    wait_until_page(page, lambda: len(mock.frames_without_pings()) > before, "a frame")
    page.wait_for_timeout(QUIET_MS)
    return mock.frames_without_pings()[before:]


def wire(frame: str) -> object:
    """A frame's JSON value."""
    return json.loads(frame)
