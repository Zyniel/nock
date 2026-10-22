"""Tests of spec 043, AC-26: others' actions show as a 3-second note, and
`undo-message` takes the note's look and place (work package WP-2).

A note (`room-note`, a `nock-note` button that no one tabs to or hears) shows over
the top of `grid-viewport` while the stream is not shown: for a message of
another player, for the event lines of "3-second notes" (a check only when it is
another player's) and for my own reaction. One note shows at a time, the newest
replacing the older at once. A click opens the Salon on its Discussion tab. No
note is made while the stream shows, and a note made while `vote-banner` is on
the page waits for it to go. `undo-message` answers my own « Annuler » with the
note's look and place, whatever shows. How long a note shows is tested in
`test_spec_043_ac26_note_lifetime.py`.

Also tested, from "3-second notes" and "Edge cases and errors": each kind of
event line that makes a note (joins, the three departures, a flag and a reveal,
mine too), the kinds that make none, the snapshot and catch-up lines (spec 034)
making none, a click on a note selecting Discussion after Joueurs, a note while
the Salon column shows Joueurs, and `undo-message` replacing a shown note and
showing during a vote.

Not tested, a question for the lead: AC-26's end of a vote as spec 047 refines it
("once the mock's `vote_closed` (`passed`) comes, the banner is gone within 300 ms
and one note shows, reading `fr.json["vote.result.passed"]`"). Spec 047 is not
built: until it is, the banner shows spec 025's result for 2.5 to 4.5 s, the
stream has no `vote` line, and the note that waited (`Bob : deux`) shows after
the banner, as AC-26 read before spec 047's note. Spec 043 has no "until spec 047
is built" reading for it (as it has for AC-27 and spec 044), and spec 047's
"Refined specs" gives this test to spec 047's test-writer. What holds in both
readings is tested: no note while the banner is on the page, and once it has gone
exactly one note shows, never the older waiting `Bob : un`.

Choices where the spec leaves room:

- "Makes no note" is read 300 ms after the page applied the event (its
  `data-seq`), or, for a `reaction`, after its `clue-reaction` shows.
- "Its first child has the pictogram": the note's first element child draws the
  glyph (spec 043's pictogram rule); "the flag icon first": that child is, or
  holds, an `svg` with the shapes of `ICONS.flag`.
- Unless a case says otherwise, the tests run at 360 by 740, where the Salon is
  closed at load (AC-14).
- The notes after the vote are noted in the page by a `MutationObserver`, so that
  a note that shows and goes between two reads is not missed.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    ChatMessage,
    ErrorCode,
    FlagView,
    HelpMode,
    HostChanged,
    LeaveReason,
    PlayerView,
    Reaction,
    Undo,
)
from room_panels import show_tab
from spec019_harness import OpenWindow, window_opener
from spec034_harness import (
    BOB,
    CatchUpRoute,
    catch_up_json,
    check_line,
    expect_catch_up_applied,
    open_mocked_room,
    record_with,
    reveal_line,
)
from spec042_harness import Box, box_of
from spec043_harness import (
    FOLLOW_MS,
    FX01_CLUE_TEXTS,
    IDES,
    QUIET_MS,
    WAIT_TIMEOUT_MS,
    Reading,
    RoomMock,
    chat_frame,
    chat_line,
    check_frame,
    error_frame,
    expect_closed,
    flag_frame,
    fr_format,
    fr_value,
    fx01_view,
    icon_problems,
    joined_frame,
    left_frame,
    note_look_problems,
    note_place_problems,
    open_room,
    pictogram_of,
    player,
    players_up_to,
    reaction_frame,
    reveal_frame,
    send_and_wait,
    settings_frame,
    shows_pictogram,
    snapshot_frame,
    style_of,
    vote_closed_frame,
    vote_opened_frame,
    wait_until,
)

PHONE = (360, 740)
COMPUTER = (1280, 720)
REPLACE_AFTER_MS = 1000  # "a flag_changed ... 1,000 ms later"
BANNER_GONE_TIMEOUT_MS = 10_000  # spec 025's result shows up to 4.5 s
SETTLE_AFTER_NOTE_MS = 500
FLAG_GLYPH = "flag"  # the note starts with the flag icon, not a text pictogram
IDES_CLUE = FX01_CLUE_TEXTS[3]  # « Fatales à César »
STABLE_READ_GAP_MS = 100

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Setup -------------------------------------------------------------------------


def open_fx01(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    *,
    size: tuple[int, int] = PHONE,
    players: Sequence[PlayerView] | None = None,
    help_mode: HelpMode = HelpMode.FREE,
    chat: Sequence[ChatMessage] = (),
    flags: Sequence[FlagView] = (),
) -> tuple[Page, RoomMock]:
    """The FX-01 room at `size` (360 by 740 by default) with `p1` to `p3`."""
    page = window(size[0], size[1], False)
    shown_players = players_up_to(3) if players is None else players
    frame = snapshot_frame(
        fx01_view(grid), shown_players, help_mode=help_mode, chat=chat, flags=flags
    )
    mock = open_room(page, base_url, frame)
    return page, mock


def notes(page: Page) -> Locator:
    return page.get_by_test_id("room-note")


def settled_viewport_box(page: Page) -> Box:
    """`grid-viewport`'s box once two reads 100 ms apart agree (the grid refitted)."""
    viewport = page.get_by_test_id("grid-viewport")
    previous = box_of(viewport)
    for _ in range(WAIT_TIMEOUT_MS // STABLE_READ_GAP_MS):
        page.wait_for_timeout(STABLE_READ_GAP_MS)
        current = box_of(viewport)
        if current == previous:
            return current
        previous = current
    raise AssertionError(f"grid-viewport keeps moving: {previous}")


def expect_note(page: Page, text: str, timeout: int = WAIT_TIMEOUT_MS) -> Locator:
    """Wait until exactly one note shows, reading `text`; return it."""
    note = notes(page)
    expect(note).to_have_count(1, timeout=timeout)
    expect(note).to_have_text(text, timeout=timeout)
    expect(note).to_be_visible()
    return note


def expect_no_note(page: Page) -> None:
    """Wait QUIET_MS, then check that no note is on the page."""
    page.wait_for_timeout(QUIET_MS)
    expect(notes(page)).to_have_count(0)


# The note's first element child: its pictogram, and the `svg` it is or holds.
FIRST_CHILD_SCRIPT = r"""
note => {
  const first = note.firstElementChild;
  if (first === null) {
    return null;
  }
  const svg = first.tagName.toLowerCase() === 'svg' ? first
    : first.querySelector('svg');
  const shapes = [];
  if (svg !== null) {
    for (const child of svg.children) {
      const attributes = {};
      for (const attribute of child.attributes) {
        attributes[attribute.name] = attribute.value;
      }
      shapes.push({tag: child.tagName.toLowerCase(), attributes: attributes});
    }
  }
  return {svg: svg === null ? null : {shapes: shapes}};
}
"""


def first_child_problems(note: Locator, glyph: str) -> list[str]:
    """How the note's first element child differs from the line's pictogram.

    Args:
        note: The shown note.
        glyph: The text pictogram (→ ← ✓ ▲), or `FLAG_GLYPH` for the flag icon.

    Returns:
        What is wrong; empty when the first child draws the pictogram.
    """
    found = note.evaluate(FIRST_CHILD_SCRIPT)
    if found is None:
        return ["the note has no element child"]
    assert isinstance(found, dict), found
    if glyph == FLAG_GLYPH:
        svg: Reading | None = found["svg"]
        if svg is None:
            return ["the note's first child is no flag icon"]
        return icon_problems(svg, "flag")
    reading = pictogram_of(note.locator(":scope > *").first)
    if shows_pictogram(reading, glyph):
        return []
    return [f"first child draws {reading['before']} {reading['after']}, not {glyph}"]


# ---- A message of another player -------------------------------------------------


def test_ac26_a_message_of_another_player_shows_a_note_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)

    mock.send(chat_frame(6, "p2", "IDES ?"))

    note = expect_note(
        page, fr_format("note.message", name="Bob", text="IDES ?"), FOLLOW_MS
    )
    assert note.evaluate("element => element.tagName") == "BUTTON"
    expect(note).to_have_attribute("type", "button")
    expect(note).to_have_attribute("tabindex", "-1")
    expect(note).to_have_attribute("aria-hidden", "true")
    assert "nock-note" in str(note.get_attribute("class")).split()


def test_ac26_the_note_has_the_look_of_spec_041s_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)

    mock.send(chat_frame(6, "p2", "IDES ?"))
    note = expect_note(page, fr_format("note.message", name="Bob", text="IDES ?"))

    assert note_look_problems(note) == []


@pytest.mark.parametrize("size", [PHONE, COMPUTER], ids=["360x740", "1280x720"])
def test_ac26_the_note_sits_8_px_under_the_viewports_top_on_layer_6_and_takes_no_room(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid, size=size)
    if size == COMPUTER:
        page.get_by_test_id("chat-toggle").click()
        expect_closed(page.get_by_test_id("salon"))
    viewport_before = settled_viewport_box(page)

    mock.send(chat_frame(6, "p2", "IDES ?"))
    note = expect_note(page, fr_format("note.message", name="Bob", text="IDES ?"))

    assert note_place_problems(page, note, viewport_before) == []
    assert style_of(note, "zIndex") == "6"


# ---- Event lines -------------------------------------------------------------------


def test_ac26_a_reveal_shows_its_line_after_the_reveal_pictogram(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)

    send_and_wait(page, mock, reveal_frame(6, "p2", CellTarget(row=2, column=2), 4, 1))

    note = expect_note(page, fr_format("feed.reveal.letter", name="Bob"))
    assert first_child_problems(note, "\N{BLACK UP-POINTING TRIANGLE}") == []


def test_ac26_a_newer_note_replaces_the_shown_one_at_once(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)
    send_and_wait(page, mock, reveal_frame(6, "p2", CellTarget(row=2, column=2), 4, 1))
    expect_note(page, fr_format("feed.reveal.letter", name="Bob"))
    page.wait_for_timeout(REPLACE_AFTER_MS)

    mock.send(flag_frame(7, "p2", IDES))

    flag_text = fr_format("feed.flag", name="Bob", clue=IDES_CLUE)
    note = expect_note(page, flag_text, FOLLOW_MS)
    assert first_child_problems(note, FLAG_GLYPH) == []


def kind_case(kind: str) -> tuple[str, str, str]:
    """The frame, the note's text and the pictogram of one kind of event line.

    Args:
        kind: A case of `NOTE_KINDS`.

    Returns:
        The event frame (seq 6), the text of its line (spec 013) and its glyph.
    """
    joined = "\N{RIGHTWARDS ARROW}"
    gone = "\N{LEFTWARDS ARROW}"
    if kind == "player_joined":
        frame = joined_frame(6, player("p4"))
        return frame, fr_format("feed.player_joined", name="Dee"), joined
    if kind == "player_left":
        frame = left_frame(6, "p3", LeaveReason.LEFT)
        return frame, fr_format("feed.player_left", name="Cy"), gone
    if kind == "player_removed":
        frame = left_frame(6, "p3", LeaveReason.REMOVED)
        return frame, fr_format("feed.player_removed", name="Cy"), gone
    if kind == "player_timed_out":
        frame = left_frame(6, "p3", LeaveReason.TIMED_OUT)
        return frame, fr_format("feed.player_timed_out", name="Cy"), gone
    if kind == "check_by_another":
        frame = check_frame(6, "p2")
        return frame, fr_format("feed.check.grid", name="Bob"), "\N{CHECK MARK}"
    if kind == "my_flag":
        frame = flag_frame(6, "p1", IDES)
        return frame, fr_format("feed.flag", name="Ana", clue=IDES_CLUE), FLAG_GLYPH
    if kind == "my_reveal":
        frame = reveal_frame(6, "p1", CellTarget(row=2, column=2), 4, 1)
        text = fr_format("feed.reveal.letter", name="Ana")
        return frame, text, "\N{BLACK UP-POINTING TRIANGLE}"
    raise ValueError(f"unknown kind of event line: {kind!r}")


NOTE_KINDS = [
    "player_joined",
    "player_left",
    "player_removed",
    "player_timed_out",
    "check_by_another",
    "my_flag",
    "my_reveal",
]


@pytest.mark.parametrize("kind", NOTE_KINDS)
def test_ac26_each_kind_of_noted_event_line_shows_its_text_after_its_pictogram(
    window: OpenWindow, live_server: str, fx01_grid: Grid, kind: str
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)
    frame, text, glyph = kind_case(kind)

    send_and_wait(page, mock, frame)

    note = expect_note(page, text)
    assert first_child_problems(note, glyph) == []


def test_ac26_my_own_check_makes_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)

    send_and_wait(page, mock, check_frame(6, "p1"))

    expect_no_note(page)


def test_ac26_my_own_message_makes_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)

    send_and_wait(page, mock, chat_frame(6, "p1", "Moi"))

    expect_no_note(page)


def unnoted_frame(kind: str) -> str:
    """An event line by `p2`, the host, of a kind that makes no note (seq 6)."""
    if kind == "room_locked":
        return settings_frame(6, locked=True, player_id="p2")
    if kind == "settings_changed":
        return settings_frame(6, help_mode=HelpMode.VOTE, player_id="p2")
    if kind == "host_changed":
        return HostChanged(seq=6, player_id="p3").model_dump_json()
    raise ValueError(f"unknown kind of event line: {kind!r}")


@pytest.mark.parametrize("kind", ["room_locked", "settings_changed", "host_changed"])
def test_ac26_lock_settings_and_host_lines_make_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid, kind: str
) -> None:
    players = [player("p1"), player("p2", host=True), player("p3")]
    page, mock = open_fx01(window, live_server, fx01_grid, players=players)

    send_and_wait(page, mock, unnoted_frame(kind))

    expect(page.locator('[data-testid="feed-item"][data-seq="6"]')).to_have_count(1)
    expect_no_note(page)


def test_ac26_the_snapshot_makes_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    chat = [chat_line(3, "p2", "Salut"), chat_line(4, "p3", "IDES ?")]
    flags = [FlagView(player_id="p2", clue=IDES)]

    page, _ = open_fx01(window, live_server, fx01_grid, chat=chat, flags=flags)

    expect_no_note(page)


def test_ac26_catch_up_lines_make_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], False)
    lines = [check_line(7, BOB), reveal_line(8, BOB)]
    route = CatchUpRoute(answer=catch_up_json(5, 9, lines=lines))
    open_mocked_room(page, live_server, fx01_grid, route, record=record_with(5), seq=9)

    expect_catch_up_applied(page, "5-9")
    expect(page.get_by_test_id("feed-item")).to_have_count(2)

    expect_no_note(page)


# ---- Reactions -------------------------------------------------------------------


def test_ac26_my_own_reaction_shows_a_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)

    mock.send(reaction_frame("p1", IDES, Reaction.WOW))

    expect_note(page, fr_format("note.own_reaction", reaction=fr_value("reaction.wow")))


def test_ac26_another_players_reaction_makes_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)

    mock.send(reaction_frame("p2", IDES, Reaction.WOW))
    expect(page.get_by_test_id("clue-reaction")).to_have_count(1)

    expect_no_note(page)


# ---- A click on a note, and the stream ------------------------------------------


def expect_discussion_shown(page: Page) -> None:
    expect(page.get_by_test_id("salon")).to_be_visible()
    expect(page.get_by_test_id("salon-tab-discussion")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.get_by_test_id("chat-panel")).to_be_visible()


def test_ac26_a_click_on_a_note_opens_the_salon_on_discussion_and_removes_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)
    mock.send(chat_frame(6, "p2", "IDES ?"))
    note = expect_note(page, fr_format("note.message", name="Bob", text="IDES ?"))

    note.click()

    expect_discussion_shown(page)
    expect(notes(page)).to_have_count(0)


def test_ac26_a_click_on_a_note_selects_discussion_after_joueurs(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)
    show_tab(page, "players")
    page.get_by_test_id("chat-toggle").click()
    expect_closed(page.get_by_test_id("salon"))
    mock.send(chat_frame(6, "p2", "IDES ?"))
    note = expect_note(page, fr_format("note.message", name="Bob", text="IDES ?"))

    note.click()

    expect_discussion_shown(page)
    expect(notes(page)).to_have_count(0)


@pytest.mark.parametrize("size", [PHONE, COMPUTER], ids=["360x740", "1280x720"])
def test_ac26_while_the_stream_shows_a_message_makes_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid, size=size)
    show_tab(page, "discussion")

    send_and_wait(page, mock, chat_frame(6, "p2", "IDES ?"))

    expect_no_note(page)


def test_ac26_with_the_salon_column_on_joueurs_a_message_shows_a_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid, size=COMPUTER)
    show_tab(page, "players")

    send_and_wait(page, mock, chat_frame(6, "p2", "IDES ?"))

    expect_note(page, fr_format("note.message", name="Bob", text="IDES ?"))


# ---- Notes during a vote ----------------------------------------------------------

# From now on, note the text of each note that shows, and each new text of a
# note (a note replaced in place), in order, in `window.spec043Notes`.
RECORD_NOTES_SCRIPT = r"""
() => {
  const texts = [];
  const last = new Map();
  const record = () => {
    for (const note of document.querySelectorAll('[data-testid="room-note"]')) {
      const text = note.textContent.replace(/\s+/g, ' ').trim();
      if (last.get(note) !== text) {
        last.set(note, text);
        texts.push(text);
      }
    }
  };
  window.spec043Notes = texts;
  new MutationObserver(record).observe(document.body,
    {childList: true, subtree: true, characterData: true, attributes: true});
  record();
}
"""


def start_recording_notes(page: Page) -> None:
    page.evaluate(RECORD_NOTES_SCRIPT)


def recorded_notes(page: Page) -> list[str]:
    found = page.evaluate("() => window.spec043Notes")
    assert isinstance(found, list), found
    return [str(text) for text in found]


def open_vote(window: OpenWindow, base_url: str, grid: Grid) -> tuple[Page, RoomMock]:
    """The room at 360 by 740 in help mode `vote`, once `p2`'s grid check vote shows."""
    page, mock = open_fx01(window, base_url, grid, help_mode=HelpMode.VOTE)
    send_and_wait(page, mock, vote_opened_frame(6, "p2"))
    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    return page, mock


def test_ac26_while_the_vote_banner_shows_messages_make_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_vote(window, live_server, fx01_grid)
    start_recording_notes(page)

    send_and_wait(page, mock, chat_frame(7, "p2", "un"))
    send_and_wait(page, mock, chat_frame(8, "p2", "deux"))
    page.wait_for_timeout(SETTLE_AFTER_NOTE_MS)

    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    assert recorded_notes(page) == []


def test_ac26_after_the_vote_one_note_shows_and_never_the_older_waiting_one(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_vote(window, live_server, fx01_grid)
    send_and_wait(page, mock, chat_frame(7, "p2", "un"))
    send_and_wait(page, mock, chat_frame(8, "p2", "deux"))
    start_recording_notes(page)

    send_and_wait(page, mock, vote_closed_frame(9))
    expect(page.get_by_test_id("vote-banner")).to_have_count(
        0, timeout=BANNER_GONE_TIMEOUT_MS
    )
    expect(notes(page)).to_have_count(1)
    page.wait_for_timeout(SETTLE_AFTER_NOTE_MS)

    texts = recorded_notes(page)
    assert len(texts) == 1, texts
    assert texts[0] != fr_format("note.message", name="Bob", text="un"), texts


# ---- Reduced motion --------------------------------------------------------------


def test_ac26_under_reduced_motion_the_note_has_no_transition(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)
    page.emulate_media(reduced_motion="reduce")

    mock.send(chat_frame(6, "p2", "IDES ?"))
    note = expect_note(page, fr_format("note.message", name="Bob", text="IDES ?"))

    assert style_of(note, "transitionDuration") == "0s"


# ---- undo-message as a note --------------------------------------------------------


def answer_undo_with_nothing(page: Page, mock: RoomMock) -> Locator:
    """Click `undo-button`, answer `nothing_to_undo`; return the shown message."""
    before = len(mock.frames_without_pings())
    page.get_by_test_id("undo-button").click()
    wait_until(
        page,
        lambda: Undo() in mock.parsed_frames_after(before),
        "the undo frame",
    )
    mock.send(error_frame(ErrorCode.NOTHING_TO_UNDO))
    message = page.get_by_test_id("undo-message")
    expect(message).to_be_visible()
    expect(message).to_have_attribute("role", "status")
    expect(message).to_have_text(fr_value("undo.nothing"))
    return message


def test_ac26_undo_message_has_the_notes_look_and_place(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)
    viewport_before = settled_viewport_box(page)

    message = answer_undo_with_nothing(page, mock)

    assert note_look_problems(message) == []
    assert note_place_problems(page, message, viewport_before) == []


@pytest.mark.parametrize("size", [PHONE, COMPUTER], ids=["360x740", "1280x720"])
def test_ac26_undo_message_shows_as_a_note_also_with_the_stream_shown(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid, size=size)
    show_tab(page, "discussion")
    viewport_before = settled_viewport_box(page)

    message = answer_undo_with_nothing(page, mock)

    expect(page.get_by_test_id("chat-panel")).to_be_visible()
    assert note_look_problems(message) == []
    assert note_place_problems(page, message, viewport_before) == []


def test_ac26_undo_message_replaces_a_shown_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_grid)
    mock.send(chat_frame(6, "p2", "IDES ?"))
    expect_note(page, fr_format("note.message", name="Bob", text="IDES ?"))

    answer_undo_with_nothing(page, mock)

    expect(notes(page)).to_have_count(0, timeout=FOLLOW_MS)


def test_ac26_undo_message_shows_while_the_vote_banner_is_on_the_page(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_vote(window, live_server, fx01_grid)

    answer_undo_with_nothing(page, mock)

    expect(page.get_by_test_id("vote-banner")).to_be_visible()
