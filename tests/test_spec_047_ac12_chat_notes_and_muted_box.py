"""Tests of spec 047, AC-12: the chat notes are one muted line under the message
box, and a muted player's box looks disabled.

On a FX-01 snapshot (spec 043's harness, `p1` host among `p1` to `p3`), with
`show_tab(page, "discussion")` at 360 by 740 and at 1280 by 720 in the desktop
context: `chat-send`'s disabled and enabled looks; after the mock's
`player_muted` (seq 6, `p1`, `muted` true) the look and place of `chat-muted` and
the disabled look of `chat-input` and `chat-send`; after five messages `m1` to
`m5` (the pacing of spec 022, 5 in 12 s) the look of `chat-wait`.

Readings where the spec leaves room:

- "The chat form" is the `form` that holds `chat-input` (spec 043's test reads it
  the same way; it has no test id).
- "On one line": the rectangles of a range over the note's text share one top
  (spec 043's `label_of`).
- "Each text keeps a contrast of at least 4.5:1 against its background": the
  colour of `chat-muted`, `chat-input` and `chat-send` against what lies behind
  it, its own background over its ancestors' (composited over white).
- The pacing run types each text with the keyboard and presses `Enter`; the mock
  answers each with its `chat_message` from `p1` (seq 6 to 10) before the next.
  The pacing holds 12 s after the first send; the checks are read well within
  that time, and only wait up to a bound, so the file runs in the parallel pass.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import PlayerMuted
from room_panels import show_tab
from spec019_harness import OpenWindow, window_opener
from spec042_harness import box_of
from spec043_harness import (
    RoomMock,
    chat_frame,
    fr_value,
    fx01_view,
    label_of,
    open_room,
    players_up_to,
    same_position,
    send_and_wait,
    snapshot_frame,
)
from spec047_harness import (
    CLUE_BG,
    MIN_TEXT_CONTRAST,
    MUTED,
    NAVY,
    SIZE_IDS,
    SIZES,
    WORD,
    colour_problem,
    surface_contrast,
    type_problems,
)

PACED_MESSAGES = ["m1", "m2", "m3", "m4", "m5"]
FIRST_MESSAGE_SEQ = 6

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Setup -------------------------------------------------------------------------


def open_discussion(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> tuple[Page, RoomMock]:
    """The FX-01 room at `size` (desktop) with the Salon on its Discussion tab."""
    page = window(size[0], size[1], False)
    frame = snapshot_frame(fx01_view(grid), players_up_to(3))
    mock = open_room(page, base_url, frame)
    show_tab(page, "discussion")
    return page, mock


def mute_me(page: Page, mock: RoomMock) -> None:
    """The mock's `player_muted` (seq 6, `p1`, `muted` true); wait for the note."""
    muted = PlayerMuted(seq=6, player_id="p1", muted=True)
    send_and_wait(page, mock, muted.model_dump_json())
    expect(page.get_by_test_id("chat-muted")).to_be_visible()


def send_paced_messages(page: Page, mock: RoomMock) -> None:
    """Type `m1` to `m5`, each with `Enter`, the mock answering each one."""
    chat_input = page.get_by_test_id("chat-input")
    for index, text in enumerate(PACED_MESSAGES):
        chat_input.press_sequentially(text)
        chat_input.press("Enter")
        seq = FIRST_MESSAGE_SEQ + index
        send_and_wait(page, mock, chat_frame(seq, "p1", text))
    expect(page.get_by_test_id("chat-wait")).to_be_visible()


def disabled_look_problems(locator: Locator, name: str) -> list[str]:
    """The disabled look: the clue blue-grey background and muted text."""
    problems = colour_problem(locator, name, "backgroundColor", CLUE_BG)
    problems += colour_problem(locator, name, "color", MUTED)
    return problems


def note_problems(page: Page, test_id: str) -> list[str]:
    """How a chat note differs from the muted line under the form, 12 px in."""
    note = page.get_by_test_id(test_id)
    problems = type_problems(
        note, test_id, size=13.6, weight="500", colour=MUTED, line_height=17.68
    )
    label = label_of(note)
    if label is None or label["lines"] != 1:
        problems.append(f"{test_id}: {label} is not one line")
    note_box = box_of(note)
    salon_box = box_of(page.get_by_test_id("salon"))
    if not same_position(note_box.left - salon_box.left, 12.0):
        problems.append(f"{test_id}: {note_box.left - salon_box.left} px in")
    form = page.get_by_test_id("chat-input").locator("xpath=ancestor::form[1]")
    form_bottom = box_of(form).bottom
    if note_box.top < form_bottom - 1.0:
        problems.append(f"{test_id}: top {note_box.top}, form bottom {form_bottom}")
    return problems


# ---- Envoyer, enabled and disabled ---------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac12_an_empty_box_leaves_envoyer_disabled_with_the_disabled_look(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_discussion(window, live_server, fx01_grid, size)
    send = page.get_by_test_id("chat-send")

    expect(send).to_be_disabled()
    assert disabled_look_problems(send, "chat-send") == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac12_typing_gives_envoyer_its_word_blue_look(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, _ = open_discussion(window, live_server, fx01_grid, size)
    send = page.get_by_test_id("chat-send")

    page.get_by_test_id("chat-input").press_sequentially("salut")

    expect(send).to_be_enabled()
    problems = colour_problem(send, "chat-send", "backgroundColor", WORD)
    problems += colour_problem(send, "chat-send", "color", NAVY)
    assert problems == []


# ---- While I am muted ---------------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac12_the_muted_line_is_one_muted_line_12_px_in_under_the_form(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_discussion(window, live_server, fx01_grid, size)

    mute_me(page, mock)

    expect(page.get_by_test_id("chat-muted")).to_have_text(fr_value("chat.muted"))
    assert note_problems(page, "chat-muted") == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac12_while_muted_the_box_and_envoyer_look_disabled(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_discussion(window, live_server, fx01_grid, size)

    mute_me(page, mock)

    chat_input = page.get_by_test_id("chat-input")
    send = page.get_by_test_id("chat-send")
    expect(chat_input).to_be_disabled()
    expect(send).to_be_disabled()
    problems = disabled_look_problems(chat_input, "chat-input")
    problems += disabled_look_problems(send, "chat-send")
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac12_while_muted_each_text_reads_at_4_5_to_1(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_discussion(window, live_server, fx01_grid, size)

    mute_me(page, mock)

    low: list[str] = []
    for test_id in ("chat-muted", "chat-input", "chat-send"):
        ratio = surface_contrast(page.get_by_test_id(test_id))
        if ratio < MIN_TEXT_CONTRAST:
            low.append(f"{test_id}: {ratio}")
    assert low == []


# ---- While the pacing holds ---------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac12_the_wait_line_has_the_muted_lines_look(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_discussion(window, live_server, fx01_grid, size)

    send_paced_messages(page, mock)

    expect(page.get_by_test_id("chat-wait")).to_have_text(fr_value("chat.wait"))
    assert note_problems(page, "chat-wait") == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac12_while_paced_envoyer_looks_disabled(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_discussion(window, live_server, fx01_grid, size)
    send_paced_messages(page, mock)

    page.get_by_test_id("chat-input").press_sequentially("m6")

    send = page.get_by_test_id("chat-send")
    expect(send).to_be_disabled()
    assert disabled_look_problems(send, "chat-send") == []
