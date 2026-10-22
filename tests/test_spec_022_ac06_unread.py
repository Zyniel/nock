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

Refined by spec 043 (the design's room layout): each page seeds
`localStorage["nock.salon_closed"]` with `"true"` so that the Salon is closed at
load in every layout; `chat-panel` is the Salon's Discussion tab, always in the DOM
and hidden while not shown; `chat-toggle` is the « Salon » button
(`aria-controls="salon"`, no `aria-label` without unread lines, the `aria-label`
`fr.json["topbar.salon_unread"]` with them); a click on `chat-toggle` closes the
Salon where `Escape` closed the panel; the host's moderation section is gone from
the panel.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import ChatMessage
from spec022_harness import (
    ChatLine,
    chat_frame,
    chat_snapshot,
    expect_seq,
    frames_of_type,
    open_chat_room,
    open_panel,
    read_chat_lines,
    three_players,
)
from spec024_harness import grid_from_text, load_fr, open_context_page
from spec025_harness import fr_text

SNAPSHOT_CHAT = [
    ChatMessage(seq=3, player_id="p2", text="Salut"),
    ChatMessage(seq=4, player_id="p1", text="Bonjour"),
]
RECONNECT_CLOSE_CODE = 1011
SALON_CLOSED_SCRIPT = (
    "if (sessionStorage.getItem('spec043-seeded-salon') === null) {"
    " localStorage.setItem('nock.salon_closed', 'true');"
    " sessionStorage.setItem('spec043-seeded-salon', '1'); }"
)
HEIGHT_SIZES = [(1280, 720), (568, 320)]
HEIGHT_TOLERANCE_PX = 1.0  # "the same height (1 px tolerance)"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def seed_salon_closed(page: Page) -> None:
    """Store `nock.salon_closed` = `"true"` before the page's first load (spec 043)."""
    page.context.add_init_script(SALON_CLOSED_SCRIPT)


def line(seq: int, player_id: str) -> ChatMessage:
    """A chat line of the test, with the text `Ligne <seq>`."""
    return ChatMessage(seq=seq, player_id=player_id, text=f"Ligne {seq}")


# The panel's parts in document order ("Client: chat toggle and panel", as spec
# 043's "Discussion" refines it): its heading, the list and the input; no
# moderation section.
PANEL_MARKUP_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="chat-panel"]');
  const heading = document.getElementById('chat-heading');
  const list = document.querySelector('[data-testid="chat-list"]');
  const input = document.querySelector('[data-testid="chat-input"]');
  const follows = (first, second) => first !== null && second !== null && Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const inside = (element) => element !== null && panel.contains(element);
  return {
    id: panel.id,
    headingTag: heading === null ? null : heading.tagName,
    headingText: heading === null ? null : heading.textContent.trim(),
    listTag: list === null ? null : list.tagName,
    listRole: list === null ? null : list.getAttribute('role'),
    listLabelledBy: list === null ? null : list.getAttribute('aria-labelledby'),
    allInside: inside(heading) && inside(list) && inside(input),
    inOrder: follows(heading, list) && follows(list, input),
    moderation: document.querySelectorAll('[data-testid="chat-moderation"]').length,
  };
}
"""


def expected_panel_markup() -> dict[str, object]:
    return {
        "id": "chat-panel",
        "headingTag": "H2",
        "headingText": load_fr()["chat.heading"],
        "listTag": "UL",
        "listRole": "list",
        "listLabelledBy": "chat-heading",
        "allInside": True,
        "inOrder": True,
        "moderation": 0,
    }


def unread_label(count: int) -> str:
    """`t("topbar.salon_unread", { count })`, from `fr.json` (spec 043)."""
    return fr_text("topbar.salon_unread", count=count)


def test_ac6_browser_the_collapsed_chat_counts_the_unread_lines(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    seed_salon_closed(page)
    mock = open_chat_room(page, live_server, fx01_grid, seq=5, chat=SNAPSHOT_CHAT)
    toggle = page.get_by_test_id("chat-toggle")
    unread = page.get_by_test_id("chat-unread")
    panel = page.get_by_test_id("chat-panel")
    salon = page.get_by_test_id("salon")

    # At load.
    expect(toggle).to_have_attribute("type", "button")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).to_have_attribute("aria-controls", "salon")
    assert toggle.get_attribute("aria-label") is None
    expect(toggle).to_have_accessible_name(fr["topbar.salon"])
    expect(panel).to_be_hidden()
    expect(unread).to_have_count(0)

    # Three lines, my own last: two are unread, and the panel stays closed.
    for seq, player_id in ((6, "p2"), (7, "p3"), (8, "p1")):
        mock.send(chat_frame(seq, player_id, f"Ligne {seq}"))
    expect_seq(page, 8)
    expect(unread).to_have_text("2")
    expect(unread).to_have_attribute("aria-hidden", "true")
    expect(toggle.get_by_test_id("chat-unread")).to_have_count(1)
    expect(toggle).to_have_attribute("aria-label", "Salon, 2 messages non lus")
    assert unread_label(2) == "Salon, 2 messages non lus"
    expect(panel).to_be_hidden()

    # Open.
    toggle.click()
    expect(panel).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_test_id("chat-message")).to_have_count(5)
    lines = read_chat_lines(page)
    expect(unread).to_have_count(0)
    expect(page.get_by_test_id("chat-input")).to_be_focused()
    markup = page.evaluate(PANEL_MARKUP_SCRIPT)

    # A line while open, then the Salon closed with a click on its button, then
    # one more line.
    mock.send(chat_frame(9, "p2", "Ligne 9"))
    expect_seq(page, 9)
    expect(page.get_by_test_id("chat-message").last).to_have_attribute("data-seq", "9")
    toggle.click()
    expect(salon).to_be_hidden()
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
    expect(toggle).to_have_attribute("aria-label", "Salon, 3 messages non lus")

    assert lines == [
        ChatLine("3", "p2", "false", "Bob", "Salut"),
        ChatLine("4", "p1", "true", "Ana", "Bonjour"),
        ChatLine("6", "p2", "false", "Bob", "Ligne 6"),
        ChatLine("7", "p3", "false", "Cy", "Ligne 7"),
        ChatLine("8", "p1", "true", "Ana", "Ligne 8"),
    ]
    assert markup == expected_panel_markup()


def test_ac6_browser_more_than_99_unread_lines_read_99_plus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    seed_salon_closed(page)
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
    expect(toggle).to_have_attribute("aria-label", "Salon, 100 messages non lus")


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
    open_panel(page)  # the spec does not say whether the panel stays shown
    chat_input.fill("salut")
    expect(send).to_be_enabled()

    assert chats_while_away == []


def toggle_height(page: Page) -> float:
    """The height of `chat-toggle`'s bounding box now."""
    box = page.get_by_test_id("chat-toggle").bounding_box()
    assert box is not None, "chat-toggle has no box"
    return box["height"]


def height_ids() -> list[str]:
    return [f"{width}x{height}" for width, height in HEIGHT_SIZES]


@pytest.mark.parametrize(("width", "height"), HEIGHT_SIZES, ids=height_ids())
def test_ac6_browser_the_toggle_keeps_its_height_as_the_count_comes_and_goes(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        seed_salon_closed(page)
        mock = open_chat_room(page, live_server, fx01_grid, seq=5, chat=SNAPSHOT_CHAT)
        toggle = page.get_by_test_id("chat-toggle")
        unread = page.get_by_test_id("chat-unread")
        heights: dict[str, float] = {"at load": toggle_height(page)}

        for seq, player_id in ((6, "p2"), (7, "p3"), (8, "p1")):
            mock.send(chat_frame(seq, player_id, f"Ligne {seq}"))
        expect(unread).to_have_text("2")
        heights["unread 2"] = toggle_height(page)

        toggle.click()
        expect(page.get_by_test_id("chat-panel")).to_be_visible()
        expect(unread).to_have_count(0)
        heights["panel open"] = toggle_height(page)

        toggle.click()
        expect(page.get_by_test_id("salon")).to_be_hidden()
        mock.send(chat_frame(9, "p2", "Ligne 9"))
        expect(unread).to_have_text("1")
        heights["unread 1"] = toggle_height(page)
    finally:
        close()

    reference = heights["at load"]
    off_reference = {}
    for state, state_height in heights.items():
        if abs(state_height - reference) > HEIGHT_TOLERANCE_PX:
            off_reference[state] = state_height
    assert off_reference == {}, (reference, heights)


@pytest.mark.parametrize(("width", "height"), HEIGHT_SIZES, ids=height_ids())
def test_ac6_browser_the_toggle_keeps_its_height_with_the_99_plus_count(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        seed_salon_closed(page)
        mock = open_chat_room(page, live_server, fx01_grid, seq=5)
        height_at_load = toggle_height(page)
        for seq in range(6, 106):
            mock.send(chat_frame(seq, "p2", f"Ligne {seq}"))
        expect(page.get_by_test_id("chat-unread")).to_have_text(
            load_fr()["chat.unread_many"]
        )
        height_with_99_plus = toggle_height(page)
    finally:
        close()

    assert abs(height_with_99_plus - height_at_load) <= HEIGHT_TOLERANCE_PX, (
        height_at_load,
        height_with_99_plus,
    )
