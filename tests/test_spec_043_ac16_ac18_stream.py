"""Tests of spec 043, AC-16 to AC-18: the stream and the message box.

AC-16 is tested for its order and caps only ("Work packages": WP-1 builds "the
stream without pictograms, colours and dots"): one list holds the messages and the
event lines in seq order, with spec 013's texts, each kind keeping its own cap.
The pictograms, the colours, the event lines' size and padding, and the player
dots of the messages are WP-2's. AC-17 is tested without its new-events dot: a
message is read while the stream shows, and only then. AC-18: the message box has
the design's look.

Choices where the spec leaves room:

- "The chat form" is the `form` that holds `chat-input`; "the chat notes' slot"
  is the element that follows it, the slot of spec 022, which has no test id.
- The 300 frames of AC-16's caps are sent one after another without waiting; the
  test then waits for the last seq.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import CellTarget, LeaveReason, WordTarget
from room_panels import show_tab
from spec019_harness import OpenWindow, window_opener
from spec042_harness import box_of, expect_seq
from spec043_harness import (
    IDES,
    LINE,
    NAVY,
    RULE,
    WORD,
    Reading,
    border_problems,
    chat_frame,
    chat_line,
    check_frame,
    expect_closed,
    expect_colour,
    flag_frame,
    fr_format,
    fr_value,
    fx01_view,
    joined_frame,
    left_frame,
    open_room,
    padding_matches,
    player,
    players_up_to,
    reveal_frame,
    same_font_size,
    same_position,
    send_and_wait,
    snapshot_frame,
    style_of,
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


def open_ac16(page: Page, base_url: str, grid: Grid) -> None:
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
