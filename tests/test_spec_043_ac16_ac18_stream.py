"""Tests of spec 043, AC-16 to AC-18: the stream and the message box.

AC-16: one list holds the messages and the event lines in seq order, with spec
013's texts, each kind keeping its own cap (work package WP-1); each event line
starts with its pictogram (the flag icon for a flag) and has its size, padding and
colour, and each message starts with its player's dot (WP-2). AC-17: a line is
read while the stream shows, and only then, for the unread badge (WP-1) and the
new-events dot (WP-2). AC-18: the message box has the design's look.

Also tested, from "Discussion" and "Edge cases and errors" (AC-16): the kinds
with no pictogram draw none; catch-up lines (spec 034) take the event look; a
chat line of a player who left has no dot.

Choices where the spec leaves room:

- "The chat form" is the `form` that holds `chat-input`; "the chat notes' slot"
  is the element that follows it, the slot of spec 022, which has no test id.
- The 300 frames of AC-16's caps are sent one after another without waiting; the
  test then waits for the last seq.
- An event line's colour is the computed `color` of its `feed-item`; "starting
  with `feed-picto`" means `feed-picto` is the item's first element child. The
  flag line's `svg` is `feed-picto` itself or inside it; "1em" is the line's font
  size (0.5 px), "pole unfilled" a `fill` of `none` or alpha 0 on the first path,
  "filled" the second path's `fill` in the line's colour (`currentColor`).
- "A player of the kept snapshot" follows the events: after `player_left`, the
  player is no longer one, so their lines lose their dot.
- "Makes no `salon-dot`" is read 300 ms after the page applied the event.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import CellTarget, HelpMode, LeaveReason, WordTarget
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
    word_completed_line,
)
from spec041_harness import shadow_of
from spec042_harness import PLAYER_COLOURS, READERS_JS, box_of, colour_of, expect_seq
from spec043_harness import (
    DOT_RING_ALPHA,
    GREEN,
    IDES,
    INK,
    LINE,
    MUTED,
    NAVAL,
    NAVY,
    QUIET_MS,
    REVEAL,
    RULE,
    WORD,
    Reading,
    Rgb,
    RoomMock,
    border_problems,
    chat_frame,
    chat_line,
    check_frame,
    colour_matches,
    expect_closed,
    expect_colour,
    flag_frame,
    font_size_of,
    fr_format,
    fr_value,
    fx01_view,
    icon_problems,
    is_clear,
    joined_frame,
    left_frame,
    open_room,
    padding_matches,
    parts_of,
    pictogram_of,
    pictograms_in,
    player,
    players_up_to,
    reveal_frame,
    same_font_size,
    same_position,
    same_size,
    send_and_wait,
    settings_frame,
    shows_pictogram,
    snapshot_frame,
    stroke_width_problems,
    style_of,
    to_box,
)

SIZES = [(360, 740), (1280, 720)]
SIZE_IDS = ["360x740", "1280x720"]

# The stream's `li` items: their test id and `data-seq`.
ITEMS_SCRIPT = r"""
list => {
  const found = [];
  for (const item of list.children) {
    found.push({tag: item.tagName, testId: item.getAttribute('data-testid'),
      seq: item.getAttribute('data-seq'), text: item.textContent});
  }
  return found;
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def stream_items(page: Page) -> list[Reading]:
    found = page.get_by_test_id("chat-list").evaluate(ITEMS_SCRIPT)
    assert isinstance(found, list), found
    return found


# ---- AC-16: one stream, in seq order, each kind with its cap -------------------------


def ac16_events() -> list[str]:
    """The seven events of AC-16, seq 6 to 12."""
    word = WordTarget(row=0, column=0, clue_index=0)
    return [
        joined_frame(6, player("p4")),
        check_frame(7, "p2"),
        check_frame(8, "p3", word, wrong=[(1, 1)]),
        chat_frame(9, "p3", "Bien vu"),
        reveal_frame(10, "p2", CellTarget(row=2, column=2), 4, 1),
        flag_frame(11, "p2", IDES),
        left_frame(12, "p4", LeaveReason.LEFT),
    ]


def open_ac16(page: Page, base_url: str, grid: Grid) -> RoomMock:
    """AC-16's snapshot (`Salut`, seq 3, by `p2`), then its seven events."""
    frame = snapshot_frame(
        fx01_view(grid),
        players_up_to(3),
        chat=[chat_line(3, "p2", "Salut")],
    )
    mock = open_room(page, base_url, frame)
    for event in ac16_events():
        mock.send(event)
    expect_seq(page, 12)
    return mock


def test_ac16_the_stream_is_one_list_labelled_by_the_discussion_heading(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)
    feed = page.get_by_test_id("activity-feed")

    lists = feed.locator("ul")
    expect(lists).to_have_count(1)
    expect(lists).to_have_attribute("data-testid", "chat-list")
    expect(lists).to_have_attribute("role", "list")
    expect(lists).to_have_attribute("aria-labelledby", "chat-heading")
    heading = page.locator("#chat-heading")
    expect(heading).to_have_text(fr_value("chat.heading"))
    assert heading.evaluate("element => element.tagName") == "H2"
    assert "visually-hidden" in str(heading.get_attribute("class")).split()


def test_ac16_messages_and_event_lines_come_in_seq_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)

    found = [(item["tag"], item["testId"], item["seq"]) for item in stream_items(page)]

    assert found == [
        ("LI", "chat-message", "3"),
        ("LI", "feed-item", "6"),
        ("LI", "feed-item", "7"),
        ("LI", "feed-item", "8"),
        ("LI", "chat-message", "9"),
        ("LI", "feed-item", "10"),
        ("LI", "feed-item", "11"),
        ("LI", "feed-item", "12"),
    ]


def test_ac16_each_event_line_has_spec_013s_text_as_its_whole_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)
    expected = {
        "6": fr_format("feed.player_joined", name="Dee"),
        "7": fr_format("feed.check.grid", name="Bob"),
        "8": fr_format("feed.check.word", name="Cy"),
        "10": fr_format("feed.reveal.letter", name="Bob"),
        "11": fr_format("feed.flag", name="Bob", clue="Fatales à César"),
        "12": fr_format("feed.player_left", name="Dee"),
    }

    texts: dict[str, str] = {}
    for item in stream_items(page):
        if item["testId"] == "feed-item":
            texts[str(item["seq"])] = str(item["text"])

    assert texts == expected


def test_ac16_each_kind_keeps_its_own_cap_with_its_newest_items(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    frame = snapshot_frame(
        fx01_view(grid=fx01_grid),
        players_up_to(3),
        chat=[chat_line(3, "p2", "Salut")],
    )
    mock = open_room(page, live_server, frame)
    for event in ac16_events():
        mock.send(event)
    for seq in range(13, 113):
        mock.send(check_frame(seq, "p2"))
    for seq in range(113, 313):
        mock.send(chat_frame(seq, "p3", f"m{seq}"))
    expect_seq(page, 312)

    events: list[int] = []
    messages: list[int] = []
    for item in stream_items(page):
        if item["testId"] == "feed-item":
            events.append(int(item["seq"]))
        elif item["testId"] == "chat-message":
            messages.append(int(item["seq"]))

    assert events == list(range(13, 113))
    assert messages == list(range(113, 313))


# ---- AC-16: the event lines' pictograms and colours (WP-2) ---------------------------

# The glyph of each event line of AC-16 that draws a text pictogram, by seq.
GLYPH_OF_SEQ = {
    "6": "\N{RIGHTWARDS ARROW}",
    "7": "\N{CHECK MARK}",
    "8": "\N{CHECK MARK}",
    "10": "\N{BLACK UP-POINTING TRIANGLE}",
    "12": "\N{LEFTWARDS ARROW}",
}
# The colour of each event line of AC-16, by seq.
COLOUR_OF_SEQ: dict[str, Rgb] = {
    "6": MUTED,
    "7": GREEN,
    "8": MUTED,
    "10": REVEAL,
    "11": MUTED,
    "12": MUTED,
}
EVENT_FONT_SIZE_PX = 13.12  # 0.82rem
EMPTY_CONTENTS = ("none", "normal")

# The event line's first element child, and where its one `svg` sits.
FEED_ITEM_SCRIPT = r"""
item => {
  const first = item.firstElementChild;
  const svgs = item.querySelectorAll('svg');
  return {
    firstTestId: first === null ? null : first.getAttribute('data-testid'),
    svgCount: svgs.length,
    svgInPicto: svgs.length === 1
      && svgs[0].closest('[data-testid="feed-picto"]') !== null,
  };
}
"""


def feed_item(page: Page, seq: int | str) -> Locator:
    return page.locator(f'[data-testid="feed-item"][data-seq="{seq}"]')


def feed_item_reading(page: Page, seq: int | str) -> Reading:
    found = feed_item(page, seq).evaluate(FEED_ITEM_SCRIPT)
    assert isinstance(found, dict), found
    return found


def picto_problems(page: Page, seq: str, glyph: str) -> list[str]:
    """How the event line of `seq` differs from one starting with `glyph`."""
    item = feed_item(page, seq)
    pictos = item.get_by_test_id("feed-picto")
    if pictos.count() != 1:
        return [f"seq {seq}: {pictos.count()} feed-picto"]
    problems: list[str] = []
    if feed_item_reading(page, seq)["firstTestId"] != "feed-picto":
        problems.append(f"seq {seq}: feed-picto is not the first child")
    reading = pictogram_of(pictos)
    if not shows_pictogram(reading, glyph):
        problems.append(f"seq {seq}: pictogram {reading['before']} {reading['after']}")
    if reading["ariaHidden"] != "true":
        problems.append(f"seq {seq}: aria-hidden {reading['ariaHidden']}")
    if reading["textNodes"] != 0:
        problems.append(f"seq {seq}: {reading['textNodes']} text nodes")
    return problems


def test_ac16_each_event_line_starts_with_its_pictogram(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)

    problems: list[str] = []
    for seq, glyph in GLYPH_OF_SEQ.items():
        problems.extend(picto_problems(page, seq, glyph))

    assert problems == []


def test_ac16_the_flag_line_starts_with_the_filled_flag_icon(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)
    item = feed_item(page, 11)

    found = feed_item_reading(page, 11)
    svgs = parts_of(item)["svgs"]

    assert found["firstTestId"] == "feed-picto"
    assert found["svgCount"] == 1
    assert found["svgInPicto"] is True
    svg = svgs[0]
    assert svg["ariaHidden"] == "true"
    assert icon_problems(svg, "flag") == []
    assert stroke_width_problems(svg, 2.0) == []
    svg_box = to_box(svg["box"])
    assert same_size(svg_box.width, EVENT_FONT_SIZE_PX), svg_box
    assert same_size(svg_box.height, EVENT_FONT_SIZE_PX), svg_box
    pole, flag = svg["shapes"]
    assert pole["fillColour"] is None or is_clear(pole["fillColour"]), pole
    assert flag["fillColour"] is not None, flag
    assert colour_matches(flag["fillColour"], MUTED), flag


def test_ac16_event_lines_are_13_12_px_with_16_px_padding_left(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)

    problems: list[str] = []
    for seq in COLOUR_OF_SEQ:
        item = feed_item(page, seq)
        size = font_size_of(item)
        if not same_font_size(size, EVENT_FONT_SIZE_PX):
            problems.append(f"seq {seq}: font-size {size}")
        padding = style_of(item, "paddingLeft")
        if padding != "16px":
            problems.append(f"seq {seq}: padding-left {padding}")

    assert problems == []


def test_ac16_event_lines_are_muted_green_for_a_clean_check_and_orange_for_a_reveal(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)

    problems: list[str] = []
    for seq, expected in COLOUR_OF_SEQ.items():
        colour = colour_of(feed_item(page, seq), "color")
        if not colour_matches(colour, expected):
            problems.append(f"seq {seq}: colour {colour}, not {expected}")

    assert problems == []
    expect(feed_item(page, 7)).to_have_attribute("data-ok", "true")
    assert feed_item(page, 8).get_attribute("data-ok") != "true"


def test_ac16_setting_and_lock_lines_have_no_pictogram_and_are_muted(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    send_and_wait(page, mock, settings_frame(6, locked=True))
    send_and_wait(page, mock, settings_frame(7, help_mode=HelpMode.VOTE, locked=True))
    expect(feed_item(page, 6)).to_have_attribute("data-kind", "room_locked")
    expect(feed_item(page, 7)).to_have_attribute("data-kind", "settings_changed")

    problems: list[str] = []
    for seq in (6, 7):
        item = feed_item(page, seq)
        for reading in pictograms_in(item):
            drawn = (reading["before"], reading["after"])
            if drawn[0] not in EMPTY_CONTENTS or drawn[1] not in EMPTY_CONTENTS:
                problems.append(f"seq {seq}: draws {drawn}")
        if feed_item_reading(page, seq)["svgCount"] != 0:
            problems.append(f"seq {seq}: holds an svg")
        colour = colour_of(item, "color")
        if not colour_matches(colour, MUTED):
            problems.append(f"seq {seq}: colour {colour}")

    assert problems == []


def test_ac16_catch_up_lines_take_the_event_look(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    lines = [word_completed_line(7, BOB, NAVAL), check_line(8, BOB)]
    route = CatchUpRoute(answer=catch_up_json(5, 9, lines=lines))
    open_mocked_room(page, live_server, fx01_grid, route, record=record_with(5), seq=9)
    expect_catch_up_applied(page, "5-9")

    word_line = feed_item(page, 7)
    check_line_item = feed_item(page, 8)

    expect(word_line).to_have_attribute("data-kind", "word_completed")
    assert same_font_size(font_size_of(word_line), EVENT_FONT_SIZE_PX)
    assert style_of(word_line, "paddingLeft") == "16px"
    expect_colour(word_line, "color", MUTED)
    assert feed_item_reading(page, 7)["svgCount"] == 0
    assert picto_problems(page, "8", "\N{CHECK MARK}") == []
    expect_colour(check_line_item, "color", GREEN)


# ---- AC-16: the messages' player dots (WP-2) -------------------------------------

# A message's children with a test id, in document order, and its dot's values.
MESSAGE_SCRIPT = "message => {\n" + READERS_JS + r"""
const ids = [];
for (const child of message.querySelectorAll('[data-testid]')) {
  ids.push(child.getAttribute('data-testid'));
}
const dot = message.querySelector('[data-testid="chat-dot"]');
const author = message.querySelector('[data-testid="chat-author"]');
const playerId = message.getAttribute('data-player-id');
const row = document.querySelector(
  `[data-testid="roster-player"][data-player-id="${playerId}"]`);
const swatch = row === null ? null
  : row.querySelector('[data-testid="roster-colour"]');
const authorStyle = getComputedStyle(author);
return {
  ids: ids,
  dot: dot === null ? null : {
    box: boxOf(dot),
    radius: getComputedStyle(dot).borderTopLeftRadius,
    background: parseColour(getComputedStyle(dot).backgroundColor),
    colour: dot.getAttribute('data-colour'),
  },
  rosterBackground: swatch === null ? null
    : parseColour(getComputedStyle(swatch).backgroundColor),
  author: {box: boxOf(author), fontWeight: authorStyle.fontWeight,
    colour: parseColour(authorStyle.color)},
};
}"""


def chat_message(page: Page, seq: int) -> Locator:
    return page.locator(f'[data-testid="chat-message"][data-seq="{seq}"]')


def message_reading(page: Page, seq: int) -> Reading:
    found = chat_message(page, seq).evaluate(MESSAGE_SCRIPT)
    assert isinstance(found, dict), found
    return found


def dot_problems(page: Page, seq: int, colour_index: int) -> list[str]:
    """How the dot of the message of `seq` differs from its player's dot."""
    reading = message_reading(page, seq)
    dot = reading["dot"]
    if dot is None:
        return [f"seq {seq}: no chat-dot"]
    problems: list[str] = []
    ids = [test_id for test_id in reading["ids"] if test_id != "player-icon"]
    if ids[:3] != ["chat-dot", "chat-author", "chat-text"]:
        problems.append(f"seq {seq}: children {ids}")
    box = to_box(dot["box"])
    if not (same_size(box.width, 10.0) and same_size(box.height, 10.0)):
        problems.append(f"seq {seq}: dot {box.width} by {box.height}")
    if dot["radius"] != "50%":
        problems.append(f"seq {seq}: radius {dot['radius']}")
    if dot["colour"] != str(colour_index):
        problems.append(f"seq {seq}: data-colour {dot['colour']}")
    if not colour_matches(dot["background"], PLAYER_COLOURS[colour_index]):
        problems.append(f"seq {seq}: background {dot['background']}")
    if dot["background"] != reading["rosterBackground"]:
        problems.append(f"seq {seq}: roster-colour {reading['rosterBackground']}")
    ring = shadow_of(chat_message(page, seq).get_by_test_id("chat-dot"))
    if ring.spread != 1 or ring.colour is None:
        problems.append(f"seq {seq}: ring {ring.text}")
    elif not colour_matches(ring.colour, INK, DOT_RING_ALPHA):
        problems.append(f"seq {seq}: ring colour {ring.colour}")
    return problems


def test_ac16_each_message_starts_with_its_players_ringed_dot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)

    problems = dot_problems(page, 3, 1) + dot_problems(page, 9, 2)

    assert problems == []


def test_ac16_the_author_is_bold_ink_6_px_after_the_dot_then_the_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac16(page, live_server, fx01_grid)

    problems: list[str] = []
    for seq in (3, 9):
        reading = message_reading(page, seq)
        if reading["dot"] is None:
            problems.append(f"seq {seq}: no chat-dot")
            continue
        dot_box = to_box(reading["dot"]["box"])
        author_box = to_box(reading["author"]["box"])
        if not same_position(author_box.left, dot_box.right + 6.0):
            problems.append(f"seq {seq}: author at {author_box.left}, dot {dot_box}")
        if reading["author"]["fontWeight"] != "700":
            problems.append(f"seq {seq}: weight {reading['author']['fontWeight']}")
        if not colour_matches(reading["author"]["colour"], INK):
            problems.append(f"seq {seq}: author colour {reading['author']['colour']}")
        text = chat_message(page, seq).get_by_test_id("chat-text")
        if not same_font_size(font_size_of(text), 14.72):
            problems.append(f"seq {seq}: text font-size {font_size_of(text)}")

    assert problems == []


def test_ac16_a_message_of_someone_who_is_not_a_player_has_no_dot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac16(page, live_server, fx01_grid)

    send_and_wait(page, mock, chat_frame(13, "p9", "Coucou"))

    expect(chat_message(page, 13)).to_have_count(1)
    expect(chat_message(page, 13).get_by_test_id("chat-dot")).to_have_count(0)
    expect(chat_message(page, 3).get_by_test_id("chat-dot")).to_have_count(1)


def test_ac16_a_message_of_a_player_who_left_loses_its_dot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    send_and_wait(page, mock, joined_frame(6, player("p4")))
    send_and_wait(page, mock, chat_frame(7, "p4", "Salut"))
    expect(chat_message(page, 7).get_by_test_id("chat-dot")).to_have_count(1)

    send_and_wait(page, mock, left_frame(8, "p4", LeaveReason.LEFT))

    expect(chat_message(page, 7).get_by_test_id("chat-dot")).to_have_count(0)


# ---- AC-17: lines are read while the stream shows, and only then ---------------------


def test_ac17_messages_that_come_while_the_stream_shows_are_read(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    expect(page.get_by_test_id("chat-panel")).to_be_visible()

    send_and_wait(page, mock, chat_frame(6, "p2", "Salut"))
    send_and_wait(page, mock, chat_frame(7, "p2", "IDES ?"))

    expect(page.get_by_test_id("chat-unread")).to_have_count(0)
    expect(page.get_by_test_id("salon-dot")).to_have_count(0)


def test_ac17_event_lines_that_come_while_the_stream_shows_make_no_dot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    expect(page.get_by_test_id("chat-panel")).to_be_visible()

    send_and_wait(page, mock, check_frame(6, "p2"))
    page.wait_for_timeout(QUIET_MS)

    expect(page.get_by_test_id("salon-dot")).to_have_count(0)


def test_ac17_an_event_line_while_joueurs_shows_makes_the_dot_until_discussion(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    send_and_wait(page, mock, chat_frame(6, "p2", "Salut"))
    send_and_wait(page, mock, chat_frame(7, "p2", "IDES ?"))
    page.get_by_test_id("salon-tab-players").click()
    send_and_wait(page, mock, chat_frame(8, "p2", "Bien"))
    expect(page.get_by_test_id("chat-unread")).to_have_text("1")
    page.get_by_test_id("salon-tab-discussion").click()
    expect(page.get_by_test_id("chat-unread")).to_have_count(0)

    page.get_by_test_id("salon-tab-players").click()
    send_and_wait(page, mock, check_frame(9, "p2"))
    expect(page.get_by_test_id("salon-dot")).to_be_visible()
    page.get_by_test_id("salon-tab-discussion").click()

    expect(page.get_by_test_id("salon-dot")).to_have_count(0)


def test_ac17_a_message_that_comes_while_joueurs_shows_is_unread_until_discussion(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    send_and_wait(page, mock, chat_frame(6, "p2", "Salut"))
    send_and_wait(page, mock, chat_frame(7, "p2", "IDES ?"))

    page.get_by_test_id("salon-tab-players").click()
    send_and_wait(page, mock, chat_frame(8, "p2", "Bien"))
    expect(page.get_by_test_id("chat-unread")).to_have_text("1")

    page.get_by_test_id("salon-tab-discussion").click()
    expect(page.get_by_test_id("chat-unread")).to_have_count(0)


def test_ac17_my_own_message_with_the_salon_closed_is_never_unread(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    for seq in (6, 7, 8):
        send_and_wait(page, mock, chat_frame(seq, "p2", f"m{seq}"))
    page.get_by_test_id("salon-tab-players").click()
    send_and_wait(page, mock, check_frame(9, "p2"))
    page.get_by_test_id("salon-tab-discussion").click()

    page.get_by_test_id("chat-toggle").click()
    expect_closed(page.get_by_test_id("salon"))
    send_and_wait(page, mock, chat_frame(10, "p1", "Moi"))

    expect(page.get_by_test_id("chat-unread")).to_have_count(0)


# ---- AC-18: the message box ----------------------------------------------------------


def open_discussion(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    page = window(size[0], size[1], False)
    open_room(page, base_url, snapshot_frame(fx01_view(grid), players_up_to(3)))
    show_tab(page, "discussion")
    return page


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac18_the_chat_form_has_a_line_above_it_and_its_padding(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_discussion(window, live_server, fx01_grid, size)
    form = page.get_by_test_id("chat-panel").locator(
        "form:has([data-testid='chat-input'])"
    )
    expect(form).to_have_count(1)

    assert border_problems(form, "Top", "1px", "solid", LINE) == []
    assert padding_matches(form, "8px 12px 12px")


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac18_the_input_is_a_rounded_field_with_its_placeholder(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_discussion(window, live_server, fx01_grid, size)
    field = page.get_by_test_id("chat-input")

    assert border_problems(field, "Top", "1px", "solid", RULE) == []
    assert border_problems(field, "Bottom", "1px", "solid", RULE) == []
    assert style_of(field, "borderTopLeftRadius") == "18px"
    assert padding_matches(field, "7px 12px")
    assert same_font_size(float(style_of(field, "fontSize").removesuffix("px")), 14.4)
    expect(field).to_have_attribute("placeholder", fr_value("chat.placeholder"))


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac18_the_send_button_is_the_word_blue_pill_beside_the_input(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_discussion(window, live_server, fx01_grid, size)
    send = page.get_by_test_id("chat-send")

    send_box = box_of(send)
    input_box = box_of(page.get_by_test_id("chat-input"))

    expect(send).to_have_text(fr_value("chat.send"))
    expect_colour(send, "backgroundColor", WORD)
    expect_colour(send, "color", NAVY)
    assert style_of(send, "fontWeight") == "600"
    assert same_font_size(float(style_of(send, "fontSize").removesuffix("px")), 13.6)
    assert style_of(send, "borderTopLeftRadius") == "14px"
    assert padding_matches(send, "6px 12px")
    assert style_of(send, "borderTopWidth") == "0px"
    assert send_box.left >= input_box.right - 1.0, (send_box, input_box)
    assert same_position(send_box.centre_y, input_box.centre_y), (send_box, input_box)


NOTES_SLOT_SCRIPT = r"""
input => {
  const form = input.closest('form');
  const slot = form === null ? null : form.nextElementSibling;
  if (slot === null) {
    return null;
  }
  const formBox = form.getBoundingClientRect();
  const slotBox = slot.getBoundingClientRect();
  return {formBottom: formBox.bottom, top: slotBox.top, left: slotBox.left,
    right: slotBox.right, bottom: slotBox.bottom};
}
"""


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac18_the_chat_notes_slot_is_below_the_form_inside_the_salon(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_discussion(window, live_server, fx01_grid, size)

    found = page.get_by_test_id("chat-input").evaluate(NOTES_SLOT_SCRIPT)
    salon_box = box_of(page.get_by_test_id("salon"))

    assert found is not None
    assert found["top"] >= found["formBottom"] - 1.0, found
    assert found["left"] >= salon_box.left - 1.0, (found, salon_box)
    assert found["right"] <= salon_box.right + 1.0, (found, salon_box)
    assert found["bottom"] <= salon_box.bottom + 1.0, (found, salon_box)
