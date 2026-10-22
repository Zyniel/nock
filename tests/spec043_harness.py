"""Shared setup of the tests of spec 043: the room layout (work packages WP-1, WP-2).

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 043 uses: the values of the spec, the
mocked room, its snapshots and event frames, the heavy setup `H8`, the readers
of boxes, labels, icons and pictograms, and the checks of a 3-second note's look
and place. The tests are in these files, one per group of criteria:

- `test_spec_043_ac01_layout.py`: AC-1.
- `test_spec_043_ac02_ac04_top_bar.py`: AC-2 to AC-4.
- `test_spec_043_ac05_ac07_states_timer_band.py`: AC-5 to AC-7.
- `test_spec_043_ac08_ac09_aide_menu.py`: AC-8 and AC-9.
- `test_spec_043_ac10_ac12_menu_and_popovers.py`: AC-10 to AC-12.
- `test_spec_043_ac13_ac15_salon.py`: AC-13 to AC-15.
- `test_spec_043_ac16_ac18_stream.py`: AC-16 to AC-18.
- `test_spec_043_ac19_ac20_players.py`: AC-19 and AC-20.
- `test_spec_043_ac21_ac22_room_sheets.py`: AC-21 and AC-22.
- `test_spec_043_ac23_ac25_clue_bar.py`: AC-23 to AC-25.
- `test_spec_043_ac26_notes.py`: AC-26 (the notes and `undo-message`).
- `test_spec_043_ac26_note_lifetime.py`: AC-26 (how long a note shows).
- `test_spec_043_ac27_ac30_status.py`: AC-27 and AC-30.
- `test_spec_043_ac28_fit.py`: AC-28.
- `test_spec_043_ac29_focus_order.py`: AC-29.
- `test_spec_043_ac31_scans_and_keys.py`: AC-31.

Spec 043 is built in two work packages ("Work packages"): WP-1, the frame, then
WP-2, the feedback (the new-events dot `salon-dot`, the stream's pictograms,
colours and player dots, the reaction pill, the 3-second notes and `undo-message`
as a note, AC-30's icons in the stream, AC-31's `room-note` state). The files
test both.

It reuses the harnesses of the specs it builds on: spec 019's mocked socket (whose
`send` uses the newest socket) and its desktop and touch windows, spec 042's box,
colour and pixel readers, spec 035's French strings and keyboard walker. Every
helper that opens or reloads a page waits for the fonts before it returns (spec
041's rule).

Readings: a reading is a JSON object read from the page with `page.evaluate`. Its
values are the page's (texts, numbers, lists, objects and nulls mixed), so a
reading is typed `dict[str, Any]` (`Reading`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any

import pytest
from playwright.sync_api import Locator, Page, expect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.protocol import (
    CellRef,
    ChatMessage,
    Check,
    CheckResult,
    CheckTarget,
    ClueRef,
    Direction,
    ErrorCode,
    ErrorMessage,
    FlagChanged,
    FlagView,
    GridTarget,
    GridView,
    HelpMode,
    LeaveReason,
    LetterChanged,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerView,
    Reaction,
    ReactionShown,
    RevealBudget,
    RevealResult,
    RevealTarget,
    RoomSettings,
    Selection,
    SelectionMoved,
    SettingsChanged,
    Snapshot,
    VoteClosed,
    VoteOpened,
    VoteOutcome,
    grid_view,
    parse_client_message,
)
from spec019_harness import MockRoomSocket, with_letter_cells
from spec035_harness import load_fr
from spec041_harness import shadow_of
from spec042_harness import (
    READERS_JS,
    Box,
    ChangeList,
    box_of,
    close_to,
    colour_of,
    expect_seq,
    to_box,
    wait_until,
)

# ---- Constants --------------------------------------------------------------

ROOM_CODE = "ABC123"
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
FOLLOW_MS = 300  # "within 300 ms"
QUIET_MS = 300  # "sends nothing within 300 ms"
FX01_CELL_COUNT = 25

# "Test harness": 1 px for a position, 0.5 px for a size, 0.1 px for a font size.
POSITION_TOLERANCE_PX = 1.0
SIZE_TOLERANCE_PX = 0.5
FONT_TOLERANCE_PX = 0.1
ALPHA_TOLERANCE = 0.01

PHONE = (360, 740)
COMPUTER = (1280, 720)
# The column-layout windows at most 500 px high, which use the phone top bar.
LOW_WINDOWS = [(740, 360), (568, 320)]

PHONE_TOP_BAR_HEIGHT = 54.0
COMPUTER_TOP_BAR_HEIGHT = 56.0

Rgb = tuple[int, int, int]
Cell = tuple[int, int]
# A JSON object read from the page: its values are the page's (texts, numbers,
# lists, objects and nulls mixed), so their type is not known here.
Reading = dict[str, Any]

# The colours of the criteria (`_design.md` section 2, spec 041's tokens).
NAVY: Rgb = (27, 47, 85)
WHITE: Rgb = (255, 255, 255)
INK: Rgb = (20, 24, 31)
MUTED: Rgb = (94, 101, 115)
LINE: Rgb = (221, 226, 234)
RULE: Rgb = (154, 163, 178)
WORD: Rgb = (230, 237, 249)
RED: Rgb = (180, 35, 24)
CLUE_BG: Rgb = (238, 242, 248)
GREEN: Rgb = (30, 123, 69)
GREEN_BG: Rgb = (230, 242, 234)
HANDLE: Rgb = (197, 204, 216)
REVEAL: Rgb = (194, 65, 12)
# The translucent tokens: their channels (INK's), then their alpha.
SCRIM_ALPHA = 0.35
SHADOW_ALPHA = 0.45
DOT_RING_ALPHA = 0.55
SHADOW_SOFT_ALPHA = 0.35
SHADOW_STRONG_ALPHA = 0.5

# The players of "Test harness": `p1` is `you`, `ANA`, colour 0 and host.
NICKNAMES = {
    "p1": "ANA",
    "p2": "BOB",
    "p3": "CY",
    "p4": "DEE",
    "p5": "EVE",
    "p6": "FAY",
    "p7": "GUS",
    "p8": "HAL",
}
# How the page shows them (capitalised words, spec 012).
DISPLAY_NICKNAMES = ["Ana", "Bob", "Cy", "Dee", "Eve", "Fay", "Gus", "Hal"]
FX01_CLUE_TEXTS = [
    "Passoire fine",
    "De la marine",
    "Artiste muet",
    "Fatales à César",
    "Flaire",
    "Sans contenu",
    "Fin de prière",
    "Alourdit le ballon",
]
# FX-01's solution, by cell (`specs/_reference.md`).
FX01_SOLUTION: dict[Cell, str] = {
    (0, 1): "N",
    (1, 0): "T",
    (1, 1): "A",
    (1, 2): "M",
    (1, 3): "I",
    (1, 4): "S",
    (2, 1): "V",
    (2, 2): "I",
    (2, 3): "D",
    (2, 4): "E",
    (3, 1): "A",
    (3, 2): "M",
    (3, 3): "E",
    (3, 4): "N",
    (4, 1): "L",
    (4, 2): "E",
    (4, 3): "S",
    (4, 4): "T",
}

IDES = ClueRef(row=0, column=3, clue_index=0)
MIME = ClueRef(row=0, column=2, clue_index=0)
NAVAL = ClueRef(row=0, column=0, clue_index=1)

# The shapes of `ICONS` (spec 041's "Icons", `_design.md` section 5): per name,
# each shape's tag and its attributes.
ICON_SHAPES: dict[str, list[tuple[str, dict[str, str]]]] = {
    "undo": [
        ("path", {"d": "M9 14 4 9l5-5"}),
        ("path", {"d": "M4 9h10a6 6 0 0 1 0 12h-3"}),
    ],
    "aide": [
        ("path", {"d": "M9 18h6M10 22h4"}),
        (
            "path",
            {
                "d": (
                    "M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6"
                    " 1-2.1A7 7 0 0 0 12 2z"
                )
            },
        ),
    ],
    "salon": [
        ("path", {"d": "M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z"})
    ],
    "menu": [("path", {"d": "M4 7h16M4 12h16M4 17h16"})],
    "crayon": [
        ("path", {"d": "M4 20h4L19 9l-4-4L4 16v4z"}),
        ("path", {"d": "M13.5 6.5l4 4"}),
    ],
    "chrono": [
        ("circle", {"cx": "12", "cy": "13.5", "r": "7.5"}),
        ("path", {"d": "M12 10v3.5l2.5 2M9.5 3h5M12 3v3"}),
    ],
    "flag": [("path", {"d": "M6 21V4"}), ("path", {"d": "M6 4h12l-3 4.5 3 4.5H6z"})],
    "chevron-left": [("path", {"d": "M15 5l-7 7 7 7"})],
    "chevron-right": [("path", {"d": "M9 5l7 7-7 7"})],
    "smile": [
        ("circle", {"cx": "12", "cy": "12", "r": "9"}),
        ("path", {"d": "M8.5 14.5c1.8 2 5.2 2 7 0"}),
        ("path", {"d": "M9 9.5h.01M15 9.5h.01"}),
    ],
}
NUMBER_ATTRIBUTES = {"cx", "cy", "r", "x", "y", "width", "height", "rx"}

# The top bars' buttons, in document order, with their icon and label key.
PHONE_BUTTONS = [
    "undo-button",
    "aide-button",
    "chat-toggle",
    "pencil-toggle",
    "menu-button",
]
COMPUTER_BUTTONS = [
    "undo-button",
    "pencil-toggle",
    "aide-button",
    "chat-toggle",
    "menu-button",
]
ICON_OF_BUTTON = {
    "undo-button": "undo",
    "aide-button": "aide",
    "chat-toggle": "salon",
    "pencil-toggle": "crayon",
    "menu-button": "menu",
    "timer-show": "chrono",
}
LABEL_KEY_OF_BUTTON = {
    "undo-button": "room.undo",
    "aide-button": "topbar.aide",
    "chat-toggle": "topbar.salon",
    "pencil-toggle": "pencil.toggle",
    "menu-button": "topbar.menu",
    "timer-show": "timer.label",
}
# The clue bar's four buttons, in document order, with their icon and label key.
CLUE_BAR_BUTTONS = ["clue-prev", "react-button", "flag-button", "clue-next"]
ICON_OF_CLUE_BAR_BUTTON = {
    "clue-prev": "chevron-left",
    "react-button": "smile",
    "flag-button": "flag",
    "clue-next": "chevron-right",
}
LABEL_KEY_OF_CLUE_BAR_BUTTON = {
    "clue-prev": "clue_bar.previous",
    "react-button": "reaction.button_label",
    "flag-button": "flag.button_label",
    "clue-next": "clue_bar.next",
}

# ---- Strings -------------------------------------------------------------------


def fr_value(key: str) -> str:
    """The value of a key of `web/src/i18n/fr.json` (KeyError when it is missing)."""
    return load_fr()[key]


def fr_format(key: str, **values: object) -> str:
    """A `fr.json` template with its `{placeholders}` replaced by `values`."""
    text = fr_value(key)
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


# ---- Players and snapshots --------------------------------------------------------


def player(
    player_id: str,
    *,
    colour: int | None = None,
    nickname: str | None = None,
    host: bool = False,
    state: PlayerState = PlayerState.ACTIVE,
    selection: Selection | None = None,
    muted: bool = False,
) -> PlayerView:
    """A player of the snapshot; `pN` has colour N - 1 and NICKNAMES[pN] by default."""
    shown_colour = int(player_id.removeprefix("p")) - 1 if colour is None else colour
    shown_nickname = NICKNAMES[player_id] if nickname is None else nickname
    return PlayerView(
        player_id=player_id,
        nickname=shown_nickname,
        colour=shown_colour,
        state=state,
        is_host=host,
        muted=muted,
        selection=selection,
    )


def players_up_to(count: int, *, host: str = "p1") -> list[PlayerView]:
    """`p1` to `p<count>`, `host` being the host (`p1` by default)."""
    players: list[PlayerView] = []
    for number in range(1, count + 1):
        player_id = f"p{number}"
        players.append(player(player_id, host=player_id == host))
    return players


def selecting(row: int, column: int, direction: Direction) -> Selection:
    return Selection(row=row, column=column, direction=direction)


def fx01_view(grid: Grid, changes: ChangeList | None = None) -> GridView:
    """FX-01's view, with some letter cells changed with `model_copy`."""
    view = grid_view(grid)
    if changes is None:
        return view
    return with_letter_cells(view, changes)


def letters_of(cells: Sequence[Cell], *, author: str = "p1") -> ChangeList:
    """Changes that put FX-01's solution letter in each of `cells`."""
    changes: ChangeList = []
    for row, column in cells:
        letter = FX01_SOLUTION[(row, column)]
        changes.append((row, column, {"letter": letter, "author": author}))
    return changes


def solved_view(grid: Grid) -> GridView:
    """FX-01 with its 18 letter cells holding their solution."""
    return fx01_view(grid, letters_of(list(FX01_SOLUTION)))


def full_wrong_view(grid: Grid) -> GridView:
    """FX-01 full, with `X` in (1, 1) in place of `A`."""
    changes = letters_of(list(FX01_SOLUTION))
    changes.append((1, 1, {"letter": "X", "author": "p1"}))
    return fx01_view(grid, changes)


def snapshot_frame(
    view: GridView,
    players: Sequence[PlayerView],
    *,
    seq: int = 5,
    help_mode: HelpMode = HelpMode.FREE,
    allowance: RevealBudget | None = None,
    left: RevealBudget | None = None,
    locked: bool = False,
    flags: Sequence[FlagView] = (),
    chat: Sequence[ChatMessage] = (),
    open_vote: VoteOpened | None = None,
    timer_elapsed_ms: int = 0,
    timer_running: bool = False,
    solved: bool = False,
) -> str:
    """A snapshot for `p1` (help mode `free`, 5 letters and 1 word by default).

    Args:
        view: The grid.
        players: The roster, in its order.
        seq: The snapshot's seq.
        help_mode: The room's help mode.
        allowance: The reveal allowance the host set (5 letters, 1 word).
        left: What is left of it (the allowance by default).
        locked: Whether the room is locked.
        flags: The flags.
        chat: The chat history, in seq order.
        open_vote: The open vote, if any.
        timer_elapsed_ms: The timer's value.
        timer_running: Whether the timer runs.
        solved: Whether the grid is solved.

    Returns:
        The snapshot as a JSON frame.
    """
    shown_allowance = (
        RevealBudget(letters=5, words=1) if allowance is None else allowance
    )
    shown_left = shown_allowance if left is None else left
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_TOKEN,
        grid=view,
        players=tuple(players),
        settings=RoomSettings(
            help_mode=help_mode, reveal_budget=shown_allowance, locked=locked
        ),
        reveal_budget=shown_left,
        flags=tuple(flags),
        chat=tuple(chat),
        open_vote=open_vote,
        timer_elapsed_ms=timer_elapsed_ms,
        timer_running=timer_running,
        solved=solved,
    )
    return snapshot.model_dump_json()


# ---- Event frames ------------------------------------------------------------------


def chat_line(seq: int, player_id: str, text: str) -> ChatMessage:
    return ChatMessage(seq=seq, player_id=player_id, text=text)


def chat_frame(seq: int, player_id: str, text: str) -> str:
    return chat_line(seq, player_id, text).model_dump_json()


def check_frame(
    seq: int,
    player_id: str,
    target: CheckTarget | None = None,
    wrong: Sequence[Cell] = (),
) -> str:
    """A `check_result` (scope grid and empty lists by default)."""
    wrong_cells = tuple(CellRef(row=row, column=column) for row, column in wrong)
    result = CheckResult(
        seq=seq,
        player_id=player_id,
        target=GridTarget() if target is None else target,
        correct=(),
        wrong=wrong_cells,
    )
    return result.model_dump_json()


def reveal_frame(
    seq: int, player_id: str, target: RevealTarget, letters: int, words: int
) -> str:
    """A `reveal_result` that leaves `letters` and `words` of the allowance."""
    result = RevealResult(
        seq=seq,
        player_id=player_id,
        target=target,
        reveal_budget=RevealBudget(letters=letters, words=words),
    )
    return result.model_dump_json()


def flag_frame(seq: int, player_id: str, clue: ClueRef | None) -> str:
    return FlagChanged(seq=seq, player_id=player_id, clue=clue).model_dump_json()


def joined_frame(seq: int, joined: PlayerView) -> str:
    return PlayerJoined(seq=seq, player=joined).model_dump_json()


def left_frame(seq: int, player_id: str, reason: LeaveReason) -> str:
    return PlayerLeft(seq=seq, player_id=player_id, reason=reason).model_dump_json()


def settings_frame(
    seq: int,
    *,
    help_mode: HelpMode = HelpMode.FREE,
    allowance: RevealBudget | None = None,
    left: RevealBudget | None = None,
    locked: bool = False,
    player_id: str = "p1",
) -> str:
    """A `settings_changed` by `player_id` (the host `p1` by default)."""
    shown_allowance = (
        RevealBudget(letters=5, words=1) if allowance is None else allowance
    )
    shown_left = shown_allowance if left is None else left
    changed = SettingsChanged(
        seq=seq,
        player_id=player_id,
        settings=RoomSettings(
            help_mode=help_mode, reveal_budget=shown_allowance, locked=locked
        ),
        reveal_budget=shown_left,
    )
    return changed.model_dump_json()


def selection_frame(player_id: str, selection: Selection | None) -> str:
    return SelectionMoved(player_id=player_id, selection=selection).model_dump_json()


def letter_frame(
    seq: int, row: int, column: int, letter: str, player_id: str, pencil: bool = False
) -> str:
    changed = LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=pencil,
        player_id=player_id,
    )
    return changed.model_dump_json()


def reaction_frame(player_id: str, clue: ClueRef, reaction: Reaction) -> str:
    shown = ReactionShown(player_id=player_id, clue=clue, reaction=reaction)
    return shown.model_dump_json()


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


VOTE_ID = 1
VOTE_VOTERS = 3


def vote_opened_frame(seq: int, player_id: str = "p2") -> str:
    """A `vote_opened` (vote 1) by `player_id` asking for a grid check, 3 voters."""
    vote = VoteOpened(
        seq=seq,
        vote_id=VOTE_ID,
        player_id=player_id,
        request=Check(target=GridTarget()),
        timeout_seconds=60,
        eligible_voters=VOTE_VOTERS,
    )
    return vote.model_dump_json()


def vote_closed_frame(seq: int, outcome: VoteOutcome = VoteOutcome.PASSED) -> str:
    """The `vote_closed` of vote 1 (2 yes votes of 3)."""
    closed = VoteClosed(
        seq=seq,
        vote_id=VOTE_ID,
        outcome=outcome,
        yes_votes=2,
        eligible_voters=VOTE_VOTERS,
    )
    return closed.model_dump_json()


# ---- The mocked room ---------------------------------------------------------------


class RoomMock(MockRoomSocket):
    """Spec 019's mocked room socket, which can also close the newest socket."""

    def close(self, code: int) -> None:
        """Close the newest socket with `code`, as the server would."""
        self.routes[-1].close(code=code)

    def parsed_frames_after(self, count: int) -> list[object]:
        """The frames sent after the first `count` (pings left out), parsed."""
        parsed: list[object] = []
        for frame in self.frames_without_pings()[count:]:
            parsed.append(parse_client_message(frame))
        return parsed


def frame_seq(frame: str) -> int:
    seq = json.loads(frame)["seq"]
    assert isinstance(seq, int), frame
    return seq


def frame_cell_count(frame: str) -> int:
    grid = json.loads(frame)["grid"]
    width = grid["width"]
    height = grid["height"]
    assert isinstance(width, int), frame
    assert isinstance(height, int), frame
    return width * height


def show_snapshot(page: Page, mock: RoomMock, frame: str) -> None:
    """Send a snapshot on the newest socket and wait until the page shows it."""
    mock.send(frame)
    expect_seq(page, frame_seq(frame))
    expect(page.get_by_test_id("cell")).to_have_count(frame_cell_count(frame))
    wait_for_fonts(page)


ACTION_TIMEOUT_MS = 10_000
NAVIGATION_TIMEOUT_MS = 30_000


def set_timeouts(page: Page) -> None:
    """Fail an action on a missing element after 10 s; keep 30 s for page loads.

    Playwright's default of 30 s for every action would make each check of an
    element that is not on the page wait 30 s. Page loads keep Playwright's 30 s
    (the handoff's lesson of PR #16).
    """
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    page.set_default_timeout(ACTION_TIMEOUT_MS)


def open_room(page: Page, base_url: str, frame: str) -> RoomMock:
    """Open /r/ABC123 on a mocked socket, join as Ana and show the snapshot `frame`.

    Args:
        page: A fresh page; its `localStorage` starts as the test seeded it.
        base_url: The live server, which serves the built client.
        frame: The snapshot (see `snapshot_frame`).

    Returns:
        The mocked socket, once the page shows the snapshot and its fonts.
    """
    mock = RoomMock()
    set_timeouts(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until(page, lambda: mock.has_join_after(0), "the join")
    show_snapshot(page, mock, frame)
    return mock


def reload_room(page: Page, mock: RoomMock, frame: str) -> None:
    """Reload the page and answer its new join with the snapshot `frame`.

    The page joins again with the identity it stored (spec 012), so no nickname
    form shows.
    """
    frames_before = len(mock.received)
    page.reload()
    wait_until(page, lambda: mock.has_join_after(frames_before), "the second join")
    show_snapshot(page, mock, frame)


def send_and_wait(page: Page, mock: RoomMock, frame: str) -> None:
    """Send an event with a seq and wait until the page has applied it."""
    mock.send(frame)
    expect_seq(page, frame_seq(frame))


def seed_value(page: Page, key: str, value: str) -> None:
    """Store `value` under `key` before the page's first load only.

    The init script runs again on a reload; a flag in `sessionStorage` makes it
    store the value once, so a reload reads what the page wrote meanwhile.
    """
    script = (
        f"if (sessionStorage.getItem('spec043-seeded-{key}') === null) {{"
        f" localStorage.setItem({json.dumps(key)}, {json.dumps(value)});"
        f" sessionStorage.setItem('spec043-seeded-{key}', '1'); }}"
    )
    page.context.add_init_script(script)


def stored_value(page: Page, key: str) -> str | None:
    value = page.evaluate("key => localStorage.getItem(key)", key)
    assert value is None or isinstance(value, str)
    return value


def frames_sent_after(
    page: Page, mock: RoomMock, action: Callable[[], object]
) -> list[str]:
    """Do `action`, wait QUIET_MS, and return the frames sent meanwhile (no pings)."""
    before = len(mock.frames_without_pings())
    action()
    page.wait_for_timeout(QUIET_MS)
    return mock.frames_without_pings()[before:]


# ---- Cells and selections ----------------------------------------------------------

CELL_SELECTOR = '[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(CELL_SELECTOR.format(row=row, column=column))


def press_cell(page: Page, row: int, column: int, touch: bool = False) -> None:
    """Click (or, in a touch context, tap) a cell and wait until the grid selects it."""
    cell = cell_at(page, row, column)
    if touch:
        cell.tap(timeout=WAIT_TIMEOUT_MS)
    else:
        cell.click(timeout=WAIT_TIMEOUT_MS)
    expect_selected(page, row, column)


def expect_selected(page: Page, row: int, column: int) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))


def expect_word(page: Page, word: str) -> None:
    """Wait until `clue-bar` has `data-word` (spec 007), for example `"0,2,0"`."""
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", word)


def select_mime(page: Page, touch: bool = False) -> None:
    """Tap (2, 2) twice: the selection is (2, 2) `down`, MIME (`0,2,0`)."""
    press_cell(page, 2, 2, touch)
    press_cell(page, 2, 2, touch)
    expect_word(page, "0,2,0")


# ---- H8, the heavy setup ------------------------------------------------------------

H8_TIMER_MS = 36_000_000
H8_FEED_ITEMS = 100
H8_LAST_SEQ = 5 + H8_FEED_ITEMS


def h8_frame(
    grid: Grid, *, view: GridView | None = None, flags: Sequence[FlagView] = ()
) -> str:
    """H8's snapshot: `you` host among 8 players, help mode `free`, 5 letters and 1
    word, and the timer at 36,000,000 ms running."""
    shown_view = fx01_view(grid) if view is None else view
    return snapshot_frame(
        shown_view,
        players_up_to(8),
        flags=flags,
        timer_elapsed_ms=H8_TIMER_MS,
        timer_running=True,
    )


def open_h8(
    page: Page,
    base_url: str,
    grid: Grid,
    touch: bool,
    *,
    view: GridView | None = None,
    flags: Sequence[FlagView] = (),
) -> RoomMock:
    """`H8`: its snapshot, spec 013's 100 line events (seq 6 to 105), (3, 1) tapped."""
    mock = open_room(page, base_url, h8_frame(grid, view=view, flags=flags))
    for seq in range(6, H8_LAST_SEQ + 1):
        mock.send(check_frame(seq, "p2"))
    expect_seq(page, H8_LAST_SEQ)
    press_cell(page, 3, 1, touch)
    return mock


# ---- Readers ------------------------------------------------------------------

# The in-page helpers of this spec, after spec 042's readers (`boxOf`, `svgOf`,
# `svgsIn`, `shapeOf`, `parseColour`).
SPEC043_JS = READERS_JS + r"""
function shows(element) {
  return element.getClientRects().length > 0
    && getComputedStyle(element).visibility === 'visible';
}
function insideHidden(node, root) {
  for (let element = node.parentElement; element !== null && element !== root;
       element = element.parentElement) {
    if (element.tagName.toLowerCase() === 'svg'
        || element.getAttribute('aria-hidden') === 'true') {
      return true;
    }
  }
  return false;
}
function labelNodes(root) {
  const found = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    if (node.textContent.trim() !== '' && !insideHidden(node, root)) {
      found.push(node);
    }
  }
  return found;
}
function lineCount(rects) {
  const tops = [];
  for (const rect of rects) {
    if (rect.width === 0 && rect.height === 0) {
      continue;
    }
    if (!tops.some(top => Math.abs(top - rect.top) <= 1)) {
      tops.push(rect.top);
    }
  }
  return tops.length;
}
function labelOf(root) {
  const nodes = labelNodes(root);
  if (nodes.length === 0) {
    return null;
  }
  const range = document.createRange();
  range.setStartBefore(nodes[0]);
  range.setEndAfter(nodes[nodes.length - 1]);
  const rect = range.getBoundingClientRect();
  const holder = nodes[0].parentElement;
  const style = getComputedStyle(holder);
  let text = '';
  for (const node of nodes) {
    text += node.textContent;
  }
  return {
    text: text.trim(),
    box: [rect.left, rect.top, rect.right, rect.bottom],
    lines: lineCount(range.getClientRects()),
    fontSize: style.fontSize,
    fontWeight: style.fontWeight,
    lineHeight: style.lineHeight,
    colour: parseColour(style.color),
    scrollWidth: holder.scrollWidth,
    clientWidth: holder.clientWidth,
    holderIsRoot: holder === root,
  };
}
function pictogramOf(element) {
  let textNodes = 0;
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    if (node.textContent.trim() !== '') {
      textNodes += 1;
    }
  }
  return {
    before: getComputedStyle(element, '::before').content,
    after: getComputedStyle(element, '::after').content,
    ariaHidden: element.getAttribute('aria-hidden'),
    textNodes: textNodes,
  };
}
function partsOf(element) {
  const style = getComputedStyle(element);
  const svgs = [];
  for (const svg of element.querySelectorAll('svg')) {
    const reading = svgOf(svg);
    const widths = [];
    for (const child of svg.children) {
      widths.push(getComputedStyle(child).strokeWidth);
    }
    reading.strokeWidths = widths;
    svgs.push(reading);
  }
  return {
    tag: element.tagName,
    type: element.getAttribute('type'),
    text: element.textContent.trim(),
    ariaLabel: element.getAttribute('aria-label'),
    disabled: element.disabled === true,
    box: boxOf(element),
    background: parseColour(style.backgroundColor),
    radius: style.borderTopLeftRadius,
    paddingLeft: style.paddingLeft,
    paddingRight: style.paddingRight,
    svgs: svgs,
    label: labelOf(element),
  };
}
"""

# The elements with a test id inside a container that show, outermost first: an
# element inside another one found is left out (`chat-unread` in `chat-toggle`).
SHOWN_ITEMS_SCRIPT = "container => {\n" + SPEC043_JS + r"""
const found = [];
const kept = [];
for (const element of container.querySelectorAll('[data-testid]')) {
  if (!shows(element)) {
    continue;
  }
  if (kept.some(outer => outer.contains(element))) {
    continue;
  }
  kept.push(element);
  found.push({testId: element.getAttribute('data-testid'), tag: element.tagName,
    box: boxOf(element)});
}
return found;
}"""

PARTS_SCRIPT = "element => {\n" + SPEC043_JS + "\nreturn partsOf(element);\n}"
LABEL_SCRIPT = "element => {\n" + SPEC043_JS + "\nreturn labelOf(element);\n}"
PICTOGRAM_SCRIPT = "element => {\n" + SPEC043_JS + "\nreturn pictogramOf(element);\n}"

# The pictograms of an element and of each of its descendants, in document order.
PICTOGRAMS_IN_SCRIPT = "element => {\n" + SPEC043_JS + r"""
const found = [pictogramOf(element)];
for (const child of element.querySelectorAll('*')) {
  const reading = pictogramOf(child);
  reading.testId = child.getAttribute('data-testid');
  found.push(reading);
}
return found;
}"""


def shown_items(container: Locator) -> list[Reading]:
    """The test-id'd elements of `container` that show, outermost only, in order."""
    found = container.evaluate(SHOWN_ITEMS_SCRIPT)
    assert isinstance(found, list), found
    return found


def shown_test_ids(container: Locator) -> list[str]:
    ids: list[str] = []
    for item in shown_items(container):
        ids.append(str(item["testId"]))
    return ids


def parts_of(locator: Locator) -> Reading:
    """A control's tag, type, text, box, background, radius, `svg`s and label."""
    found = locator.evaluate(PARTS_SCRIPT)
    assert isinstance(found, dict), found
    return found


def label_of(locator: Locator) -> Reading | None:
    """The visible label of an element: the text outside `svg` and `aria-hidden`.

    Its `box` is the box of the text itself (a range), `lines` the number of
    lines it takes, and its font values those of the element holding the text.
    """
    found = locator.evaluate(LABEL_SCRIPT)
    assert found is None or isinstance(found, dict), found
    return found


def pictogram_of(locator: Locator) -> Reading:
    """The computed `content` of an element's `::before` and `::after`."""
    found = locator.evaluate(PICTOGRAM_SCRIPT)
    assert isinstance(found, dict), found
    return found


def shows_pictogram(reading: Reading, glyph: str) -> bool:
    """Tell whether a pictogram reading draws `glyph` before or after."""
    drawn = f'"{glyph}"'
    return reading["before"] == drawn or reading["after"] == drawn


def pictograms_in(locator: Locator) -> list[Reading]:
    found = locator.evaluate(PICTOGRAMS_IN_SCRIPT)
    assert isinstance(found, list), found
    return found


def any_pictogram(locator: Locator, glyph: str) -> bool:
    """Tell whether an element or one of its descendants draws `glyph`."""
    readings = pictograms_in(locator)
    return any(shows_pictogram(reading, glyph) for reading in readings)


def attribute_matches(name: str, actual: str | None, expected: str) -> bool:
    """A shape attribute: numbers compared as numbers, other values as written."""
    if actual is None:
        return False
    if name in NUMBER_ATTRIBUTES:
        try:
            return abs(float(actual) - float(expected)) <= 1e-9
        except ValueError:
            return False
    return " ".join(actual.split()) == expected


def icon_problems(svg: Reading, name: str) -> list[str]:
    """How an `svg` reading's shapes differ from `ICONS[name]`."""
    expected = ICON_SHAPES[name]
    shapes: list[Reading] = svg["shapes"]
    if len(shapes) != len(expected):
        return [f"{name}: {len(shapes)} shapes, expected {len(expected)}"]
    problems: list[str] = []
    for shape, (tag, attributes) in zip(shapes, expected, strict=True):
        if shape["tag"] != tag:
            problems.append(f"{name}: a {shape['tag']}, expected a {tag}")
            continue
        for attribute, value in attributes.items():
            actual = shape["attributes"].get(attribute)
            if not attribute_matches(attribute, actual, value):
                problems.append(f"{name}: {tag} {attribute}={actual!r}, not {value!r}")
    return problems


def stroke_width_problems(svg: Reading, expected: float) -> list[str]:
    """How the computed `stroke-width` of an `svg`'s shapes differs from `expected`."""
    problems: list[str] = []
    for width in svg["strokeWidths"]:
        value = float(str(width).removesuffix("px"))
        if abs(value - expected) > 0.01:
            problems.append(f"stroke-width {width}, expected {expected}")
    return problems


def colour_matches(actual: Sequence[float], expected: Rgb, alpha: float = 1.0) -> bool:
    """Exact channels and alpha within 0.01 (a token, "Test harness")."""
    channels = (float(actual[0]), float(actual[1]), float(actual[2]))
    wanted = (float(expected[0]), float(expected[1]), float(expected[2]))
    return channels == wanted and abs(float(actual[3]) - alpha) <= ALPHA_TOLERANCE


def is_clear(actual: Sequence[float]) -> bool:
    """Tell whether a parsed colour has alpha 0."""
    return abs(float(actual[3])) <= ALPHA_TOLERANCE


def px(value: str) -> float:
    """Read a computed length such as `15.2px` as a number of px."""
    if not value.endswith("px"):
        pytest.fail(f"{value!r} is not a length in px")
    return float(value.removesuffix("px"))


def style_of(locator: Locator, property_name: str) -> str:
    """The computed style property `property_name` (camelCase) of an element."""
    value = locator.evaluate(
        "(element, name) => getComputedStyle(element)[name]", property_name
    )
    assert isinstance(value, str), value
    return value


def expect_colour(locator: Locator, property_name: str, expected: Rgb) -> None:
    """Fail unless a computed colour property is exactly the token `expected`."""
    colour = colour_of(locator, property_name)
    assert colour_matches(colour, expected), f"{property_name} {colour}, not {expected}"


def border_problems(
    locator: Locator, side: str, width: str, style: str, colour: Rgb
) -> list[str]:
    """How one border side (`Top`, `Right`, `Bottom`, `Left`) differs from the spec."""
    problems: list[str] = []
    actual_width = style_of(locator, f"border{side}Width")
    actual_style = style_of(locator, f"border{side}Style")
    actual_colour = colour_of(locator, f"border{side}Color")
    if actual_width != width:
        problems.append(f"border-{side.lower()}-width {actual_width}, not {width}")
    if actual_style != style:
        problems.append(f"border-{side.lower()}-style {actual_style}, not {style}")
    if not colour_matches(actual_colour, colour):
        problems.append(f"border-{side.lower()}-color {actual_colour}, not {colour}")
    return problems


def padding_of(locator: Locator) -> str:
    """The computed padding as `top right bottom left`, each in px."""
    sides: list[str] = []
    for side in ("Top", "Right", "Bottom", "Left"):
        sides.append(style_of(locator, f"padding{side}"))
    return " ".join(sides)


def padding_matches(locator: Locator, shorthand: str) -> bool:
    """Compare the computed padding with a CSS shorthand of 1 to 4 values."""
    values = shorthand.split()
    if len(values) == 1:
        values = values * 4
    elif len(values) == 2:
        values = [values[0], values[1], values[0], values[1]]
    elif len(values) == 3:
        values = [values[0], values[1], values[2], values[1]]
    return padding_of(locator) == " ".join(values)


def font_size_of(locator: Locator) -> float:
    return px(style_of(locator, "fontSize"))


def same_font_size(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= FONT_TOLERANCE_PX


def same_position(actual: float, expected: float) -> bool:
    return close_to(actual, expected, POSITION_TOLERANCE_PX)


def same_size(actual: float, expected: float) -> bool:
    return close_to(actual, expected, SIZE_TOLERANCE_PX)


def same_box(first: Box, second: Box) -> bool:
    """Two boxes within 1 px on each edge."""
    return (
        same_position(first.left, second.left)
        and same_position(first.top, second.top)
        and same_position(first.right, second.right)
        and same_position(first.bottom, second.bottom)
    )


def window_box(page: Page) -> Box:
    size = page.evaluate("() => [innerWidth, innerHeight]")
    assert isinstance(size, list), size
    return Box(0.0, 0.0, float(size[0]), float(size[1]))


def box_inside(inner: Box, outer: Box) -> bool:
    """Tell whether `inner` lies inside `outer`, with 1 px of tolerance."""
    return (
        inner.left >= outer.left - POSITION_TOLERANCE_PX
        and inner.top >= outer.top - POSITION_TOLERANCE_PX
        and inner.right <= outer.right + POSITION_TOLERANCE_PX
        and inner.bottom <= outer.bottom + POSITION_TOLERANCE_PX
    )


def reading_box(reading: Reading) -> Box:
    return to_box(reading["box"])


def layout_of(page: Page) -> str | None:
    return page.get_by_test_id("room-page").get_attribute("data-layout")


def expect_layout(page: Page, layout: str, timeout: int = WAIT_TIMEOUT_MS) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-layout", layout, timeout=timeout
    )


def is_open(locator: Locator) -> bool:
    """Tell whether a popover or the Salon is on the page without `hidden`."""
    if locator.count() == 0:
        return False
    return locator.get_attribute("hidden") is None


def expect_closed(locator: Locator) -> None:
    """Wait until a popover or the Salon has the `hidden` attribute."""
    expect(locator).to_have_attribute(
        "hidden", re.compile(".*"), timeout=WAIT_TIMEOUT_MS
    )


# The text of `grid-status` without the `recap-open` button it holds while the page
# is solved, with its white space collapsed as Playwright's `to_have_text` does.
STATUS_OWN_TEXT_SCRIPT = r"""
element => {
  const copy = element.cloneNode(true);
  for (const button of copy.querySelectorAll('[data-testid="recap-open"]')) {
    button.remove();
  }
  return copy.textContent.replace(/\s+/g, ' ').trim();
}
"""
STATUS_POLL_MS = 50


def expect_status_text(status: Locator, expected: str) -> None:
    """Wait until `grid-status`'s own text, without `recap-open`, is `expected`.

    Spec 043 puts « Voir le bilan » inside `grid-status` on a solved page, so the
    status's text is read without that button.

    Args:
        status: The `grid-status` locator.
        expected: The text it must show, for example `fr.json["completion.solved"]`.
    """
    expect(status).to_have_count(1)
    text = ""
    for _ in range(WAIT_TIMEOUT_MS // STATUS_POLL_MS):
        text = str(status.evaluate(STATUS_OWN_TEXT_SCRIPT))
        if text == expected:
            return
        status.page.wait_for_timeout(STATUS_POLL_MS)
    raise AssertionError(f"grid-status reads {text!r}, not {expected!r}")


def focused_test_id(page: Page) -> str | None:
    found = page.evaluate(
        "() => document.activeElement === null ? null"
        " : document.activeElement.getAttribute('data-testid')"
    )
    assert found is None or isinstance(found, str)
    return found


# The element at a point is the named element or one of its descendants.
HITS_SCRIPT = r"""
([testId, x, y]) => {
  const own = document.querySelector(`[data-testid="${testId}"]`);
  const hit = document.elementFromPoint(x, y);
  return {
    hits: own !== null && hit !== null && (hit === own || own.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""


def hit_problem(page: Page, test_id: str) -> str | None:
    """None when `elementFromPoint` at the centre of `test_id` returns it."""
    box = box_of(page.get_by_test_id(test_id))
    found = page.evaluate(HITS_SCRIPT, [test_id, box.centre_x, box.centre_y])
    assert isinstance(found, dict), found
    if found["hits"] is True:
        return None
    return f"{test_id}: elementFromPoint at its centre is {found['hit']}"


# ---- 3-second notes (WP-2) -------------------------------------------------------

NOTE_SHOWN_MS = 3000  # "A note shows for 3,000 ms"
NOTE_TOP_GAP_PX = 8.0  # "its top 8 px below the viewport's top"


def note_look_problems(note: Locator) -> list[str]:
    """How an element differs from spec 041's `nock-note` look (its AC-14).

    White 500 13.6 px text with a 16.32 px line height on ink, padding 8 px 12 px,
    radius 6 px, on one line, and the shadow `0 6px 18px -8px` in the strong
    shadow token.
    """
    problems: list[str] = []
    background = colour_of(note, "backgroundColor")
    if not colour_matches(background, INK):
        problems.append(f"background {background}")
    text_colour = colour_of(note, "color")
    if not colour_matches(text_colour, WHITE):
        problems.append(f"colour {text_colour}")
    if style_of(note, "fontWeight") != "500":
        problems.append(f"font-weight {style_of(note, 'fontWeight')}")
    if not same_font_size(px(style_of(note, "fontSize")), 13.6):
        problems.append(f"font-size {style_of(note, 'fontSize')}")
    line_height = style_of(note, "lineHeight")
    if not line_height.endswith("px") or not same_font_size(px(line_height), 16.32):
        problems.append(f"line-height {line_height}")
    if not padding_matches(note, "8px 12px"):
        problems.append(f"padding {padding_of(note)}")
    if style_of(note, "borderTopLeftRadius") != "6px":
        problems.append(f"radius {style_of(note, 'borderTopLeftRadius')}")
    if style_of(note, "whiteSpace") != "nowrap":
        problems.append(f"white-space {style_of(note, 'whiteSpace')}")
    shadow = shadow_of(note)
    if (shadow.x, shadow.y, shadow.blur, shadow.spread) != (0, 6, 18, -8):
        problems.append(f"box-shadow {shadow.text}")
    if shadow.colour is None or not colour_matches(
        shadow.colour, INK, SHADOW_STRONG_ALPHA
    ):
        problems.append(f"box-shadow colour {shadow.colour}")
    return problems


def note_place_problems(page: Page, note: Locator, viewport_before: Box) -> list[str]:
    """How a note's place differs from "3-second notes".

    Centred horizontally on `grid-viewport` (1 px), its top 8 px below the
    viewport's top (1 px), and taking no room: `grid-viewport` keeps the box it
    had before the note (`viewport_before`, 1 px).
    """
    box = box_of(note)
    viewport_box = box_of(page.get_by_test_id("grid-viewport"))
    problems: list[str] = []
    if not same_position(box.centre_x, viewport_box.centre_x):
        problems.append(f"note centre x {box.centre_x}, viewport {viewport_box}")
    if not same_position(box.top, viewport_box.top + NOTE_TOP_GAP_PX):
        problems.append(f"note top {box.top}, viewport top {viewport_box.top}")
    if not same_box(viewport_box, viewport_before):
        problems.append(f"grid-viewport moved: {viewport_before} -> {viewport_box}")
    return problems
