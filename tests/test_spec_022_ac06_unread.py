"""Tests of spec 022, AC-6: the chat can be collapsed, and then shows an unread
count.

Browser with spec 025's mocked socket, which answers pings and takes the page's
new socket after a reconnection. The first test runs the criterion's steps in its
order on one page; the separate run of 100 lines is its own test (it also reads
the count at 99, the last count written in digits). The edge cases of AC-6 run
here too: my own line is never unread and does not open the panel, the first
snapshot's history is not unread, lines that came during a reconnection count,
and sending is disabled while the page is not `joined`. The panel's markup
("Client: chat toggle and panel") is read once the panel is open.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import ChatMessage
from spec022_harness import (
    POPOVER_PLACE,
    ChatLine,
    chat_frame,
    chat_snapshot,
    expect_seq,
    frames_of_type,
    open_chat_room,
    open_panel,
    popover_place,
    read_chat_lines,
    three_players,
)
from spec024_harness import grid_from_text, load_fr
from spec025_harness import fr_text

SNAPSHOT_CHAT = [
    ChatMessage(seq=3, player_id="p2", text="Salut"),
    ChatMessage(seq=4, player_id="p1", text="Bonjour"),
]
RECONNECT_CLOSE_CODE = 1011


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def line(seq: int, player_id: str) -> ChatMessage:
    """A chat line of the test, with the text `Ligne <seq>`."""
    return ChatMessage(seq=seq, player_id=player_id, text=f"Ligne {seq}")


# The panel's parts in document order ("Client: chat toggle and panel"): the
# section, its heading, the list, the host's moderation section and the input.
PANEL_MARKUP_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="chat-panel"]');
  const heading = document.getElementById('chat-heading');
  const list = document.querySelector('[data-testid="chat-list"]');
  const moderation = document.querySelector('[data-testid="chat-moderation"]');
  const input = document.querySelector('[data-testid="chat-input"]');
  const follows = (first, second) => first !== null && second !== null && Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const inside = (element) => element !== null && panel.contains(element);
  return {
    tag: panel.tagName,
    id: panel.id,
    labelledBy: panel.getAttribute('aria-labelledby'),
    headingTag: heading === null ? null : heading.tagName,
    headingText: heading === null ? null : heading.textContent.trim(),
    listTag: list === null ? null : list.tagName,
    listRole: list === null ? null : list.getAttribute('role'),
    listLabelledBy: list === null ? null : list.getAttribute('aria-labelledby'),
    allInside: inside(heading) && inside(list) && inside(moderation) && inside(input),
    inOrder: follows(heading, list) && follows(list, moderation)
      && follows(moderation, input),
  };
}
"""


def expected_panel_markup() -> dict[str, object]:
    return {
        "tag": "SECTION",
        "id": "chat-panel",
        "labelledBy": "chat-heading",
        "headingTag": "H2",
        "headingText": load_fr()["chat.heading"],
        "listTag": "UL",
        "listRole": "list",
        "listLabelledBy": "chat-heading",
        "allInside": True,
        "inOrder": True,
    }


def unread_label(count: int) -> str:
    """`t("chat.toggle_label_unread", { count })`, from `fr.json`."""
    return fr_text("chat.toggle_label_unread", count=count)


def test_ac6_browser_the_collapsed_chat_counts_the_unread_lines(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    mock = open_chat_room(page, live_server, fx01_grid, seq=5, chat=SNAPSHOT_CHAT)
    toggle = page.get_by_test_id("chat-toggle")
    unread = page.get_by_test_id("chat-unread")
    panel = page.get_by_test_id("chat-panel")

    # At load.
    expect(toggle).to_have_attribute("type", "button")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).to_have_attribute("aria-controls", "chat-panel")
    expect(toggle).to_have_attribute("aria-label", fr["chat.toggle"])
    expect(toggle).to_have_text(fr["chat.toggle"])
    expect(panel).to_have_count(0)
    expect(unread).to_have_count(0)

    # Three lines, my own last: two are unread, and the panel stays closed.
    for seq, player_id in ((6, "p2"), (7, "p3"), (8, "p1")):
        mock.send(chat_frame(seq, player_id, f"Ligne {seq}"))
    expect_seq(page, 8)
    expect(unread).to_have_text("2")
    expect(unread).to_have_attribute("aria-hidden", "true")
    expect(toggle.get_by_test_id("chat-unread")).to_have_count(1)
    expect(toggle).to_have_attribute("aria-label", "Discussion, 2 messages non lus")
    expect(panel).to_have_count(0)

    # Open.
    toggle.click()
    expect(panel).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_test_id("chat-message")).to_have_count(5)
    lines = read_chat_lines(page)
    expect(unread).to_have_count(0)
    expect(page.get_by_test_id("chat-input")).to_be_focused()
    markup = page.evaluate(PANEL_MARKUP_SCRIPT)
    place = popover_place(page, "chat-panel")

    # A line while open, then closed with Escape, then one more line.
    mock.send(chat_frame(9, "p2", "Ligne 9"))
    expect_seq(page, 9)
    expect(page.get_by_test_id("chat-message").last).to_have_attribute("data-seq", "9")
    page.keyboard.press("Escape")
    expect(panel).to_have_count(0)
    expect(toggle).to_be_focused()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(unread).to_have_count(0)
    mock.send(chat_frame(10, "p2", "Ligne 10"))
    expect_seq(page, 10)
    expect(unread).to_have_text("1")

    # A reconnection whose snapshot brings two more lines.
    mock.close(RECONNECT_CLOSE_CODE)
    mock.wait_for_join_on_socket(1)
    history = [
        *SNAPSHOT_CHAT,
        line(6, "p2"),
        line(7, "p3"),
        line(8, "p1"),
        line(9, "p2"),
        line(10, "p2"),
        line(11, "p2"),
        line(12, "p3"),
    ]
    snapshot = chat_snapshot(fx01_grid, seq=12, players=three_players(), chat=history)
    mock.send(snapshot.model_dump_json())
    expect_seq(page, 12)
    expect(unread).to_have_text("3")
    expect(toggle).to_have_attribute("aria-label", "Discussion, 3 messages non lus")

    assert lines == [
        ChatLine("3", "p2", "false", "Bob", "Salut"),
        ChatLine("4", "p1", "true", "Ana", "Bonjour"),
        ChatLine("6", "p2", "false", "Bob", "Ligne 6"),
        ChatLine("7", "p3", "false", "Cy", "Ligne 7"),
        ChatLine("8", "p1", "true", "Ana", "Ligne 8"),
    ]
    assert markup == expected_panel_markup()
    assert place == POPOVER_PLACE


def test_ac6_browser_more_than_99_unread_lines_read_99_plus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    mock = open_chat_room(page, live_server, fx01_grid, seq=5)
    toggle = page.get_by_test_id("chat-toggle")
    unread = page.get_by_test_id("chat-unread")

    for seq in range(6, 105):
        mock.send(chat_frame(seq, "p2", f"Ligne {seq}"))
    expect_seq(page, 104)
    expect(unread).to_have_text("99")
    expect(toggle).to_have_attribute("aria-label", unread_label(99))

    mock.send(chat_frame(105, "p2", "Ligne 105"))
    expect_seq(page, 105)
    expect(unread).to_have_text(fr["chat.unread_many"])
    expect(toggle).to_have_attribute("aria-label", "Discussion, 100 messages non lus")


def test_ac6_browser_sending_is_disabled_while_the_page_is_reconnecting(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_chat_room(page, live_server, fx01_grid, seq=5)
    open_panel(page)
    chat_input = page.get_by_test_id("chat-input")
    send = page.get_by_test_id("chat-send")
    chat_input.fill("salut")
    expect(send).to_be_enabled()

    mock.close(RECONNECT_CLOSE_CODE)
    room = page.get_by_test_id("room-page")
    expect(room).not_to_have_attribute("data-status", "joined")
    expect(send).to_be_disabled()
    if chat_input.is_enabled():
        chat_input.press("Enter")
    mock.wait_for_join_on_socket(1)
    page.wait_for_timeout(300)
    chats_while_away = frames_of_type(mock, "chat")

    snapshot = chat_snapshot(fx01_grid, seq=5, players=three_players(), chat=[])
    mock.send(snapshot.model_dump_json())
    expect(room).to_have_attribute("data-status", "joined")
    if page.get_by_test_id("chat-panel").count() == 0:
        open_panel(page)  # the spec does not say whether the panel stays open
    chat_input.fill("salut")
    expect(send).to_be_enabled()

    assert chats_while_away == []
