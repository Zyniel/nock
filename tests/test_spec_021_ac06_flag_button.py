"""Tests of spec 021, AC-6: the flag button sends a flag for the selected word and
shows whether it holds mine.

One page with a mocked socket at 1280 by 720 walks AC-6 in its order: the button's
place in the room toolbar and its texts, disabled with nothing selected; enabled
on MIME, a click that sends one frame and no local guess before the server's
`flag_changed`; the second click that sends `clue: null`; another player's flag
on MIME; disabled on the full word TAMIS; then the edge case "Pending edits" (a
word I just typed full is full for the button) and an `invalid_target` error that
changes no attribute on the page, pending edits included. A third page holds my
flag on a word I then type full: the button stays enabled and pressed, since my
flag is on it ("Client: the flag button"), and a click removes my flag. The shared
setup is in `spec021_harness`.

Spec 019 is built, so the page has an `authors-switch` and the button must come
before it.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import (
    ErrorCode,
    ErrorMessage,
    Flag,
    grid_view,
    parse_client_message,
)
from spec021_harness import (
    FLAG_BUTTON_LABEL,
    FLAG_BUTTON_TEXT,
    LEST,
    MIME,
    TAMIS,
    clue_at,
    flag_changed_frame,
    frames_sent_by,
    open_flag_room,
    select_word,
    wire,
)
from spec024_harness import (
    SETTLE_MS,
    ChangeList,
    MockRoomSocket,
    expect_seq,
    grid_from_text,
    make_catalogue,
    open_context_page,
    wait_until_page,
    with_letter_cells,
)

WIDTH, HEIGHT = 1280, 720
MIME_WIRE = {"type": "flag", "clue": {"row": 0, "column": 2, "clue_index": 0}}
NULL_WIRE = {"type": "flag", "clue": None}

# The place of `flag-button`: inside `room-toolbar`, after `reveal-panel`, and
# before `authors-switch` (spec 019), which must exist.
PLACE_SCRIPT = """
() => {
  const follows = (first, second) => Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const buttons = document.querySelectorAll('[data-testid="flag-button"]');
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const reveal = document.querySelector('[data-testid="reveal-panel"]');
  const authors = document.querySelector('[data-testid="authors-switch"]');
  if (buttons.length !== 1) {
    return {count: buttons.length};
  }
  const button = buttons[0];
  return {
    count: 1,
    tag: button.tagName,
    type: button.getAttribute('type'),
    inToolbar: toolbar !== null && toolbar.contains(button),
    afterReveal: reveal !== null && follows(reveal, button),
    beforeAuthors: authors !== null && follows(button, authors),
  };
}
"""

# Every element of the page with its attributes, in document order.
ATTRIBUTES_SCRIPT = """
() => {
  const found = [];
  for (const element of document.querySelectorAll('*')) {
    const attributes = [];
    for (const attribute of element.attributes) {
      attributes.push(`${attribute.name}=${attribute.value}`);
    }
    found.push(`${element.tagName} ${attributes.join(' ')}`);
  }
  return found;
}
"""

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Helpers ----


def tamis_written() -> ChangeList:
    """TAMIS holds `T`, `A`, `M`, `I`, `S`, written by `p1`."""
    changes: ChangeList = []
    for column, letter in enumerate("TAMIS"):
        changes.append((1, column, {"letter": letter, "author": "p1"}))
    return changes


def page_attributes(page: Page) -> list[str]:
    found = page.evaluate(ATTRIBUTES_SCRIPT)
    assert isinstance(found, list)
    return found


def assert_one_flag_frame(frames: list[str], expected_wire: object) -> None:
    """Exactly one frame was sent: the flag of the expected wire form."""
    assert len(frames) == 1, frames
    assert wire(frames[0]) == expected_wire
    sent = parse_client_message(frames[0])
    assert isinstance(sent, Flag)


def type_lest_pending(page: Page, mock: MockRoomSocket) -> None:
    """Type `lest` in the selected LEST: four edits the mock leaves pending."""
    for letter in "lest":
        page.keyboard.press(letter)
    wait_until_page(page, lambda: mock.edit_count() == 4, "the four edits")
    for column in range(1, 5):
        cell = page.locator(
            f'[data-testid="cell"][data-row="4"][data-column="{column}"]'
        )
        expect(cell).to_have_attribute("data-unconfirmed", "true")


# ---- AC-6 ----


def test_ac6_browser_the_flag_button_sends_my_flag_and_follows_the_kept_flags(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, WIDTH, HEIGHT, False)
    try:
        view = with_letter_cells(grid_view(fx01_grid), tamis_written())
        mock = open_flag_room(page, live_server, view)
        button = page.get_by_test_id("flag-button")

        # Place, texts, and disabled while nothing is selected.
        expect(button).to_have_count(1)
        assert page.evaluate(PLACE_SCRIPT) == {
            "count": 1,
            "tag": "BUTTON",
            "type": "button",
            "inToolbar": True,
            "afterReveal": True,
            "beforeAuthors": True,
        }
        expect(button).to_have_text(FLAG_BUTTON_TEXT)
        expect(button).to_have_attribute("aria-label", FLAG_BUTTON_LABEL)
        expect(button).to_have_attribute("aria-pressed", "false")
        expect(button).to_be_disabled()

        # MIME selected: one click, one frame, no local guess.
        select_word(page, MIME)
        expect(button).to_be_enabled()
        frames = frames_sent_by(page, mock, button.click)
        assert_one_flag_frame(frames, MIME_WIRE)
        assert parse_client_message(frames[0]) == Flag(clue=MIME)
        expect(button).to_have_attribute("aria-pressed", "false")
        expect(clue_at(page, MIME)).to_have_attribute("data-flagged", "false")
        mock.send(flag_changed_frame(6, "p1", MIME))
        expect_seq(page, 6)
        expect(button).to_have_attribute("aria-pressed", "true")

        # The second click removes my flag, once the server says so.
        frames = frames_sent_by(page, mock, button.click)
        assert_one_flag_frame(frames, NULL_WIRE)
        assert parse_client_message(frames[0]) == Flag(clue=None)
        expect(button).to_have_attribute("aria-pressed", "true")
        mock.send(flag_changed_frame(7, "p1", None))
        expect_seq(page, 7)
        expect(button).to_have_attribute("aria-pressed", "false")

        # Another player's flag on MIME is not mine.
        mock.send(flag_changed_frame(8, "p2", MIME))
        expect_seq(page, 8)
        expect(clue_at(page, MIME)).to_have_attribute("data-flagged", "true")
        expect(page.get_by_test_id("grid")).to_have_attribute("data-word", "0,2,0")
        expect(button).to_have_attribute("aria-pressed", "false")
        frames = frames_sent_by(page, mock, button.click)
        assert_one_flag_frame(frames, MIME_WIRE)

        # A full word that holds no flag of mine: disabled.
        select_word(page, TAMIS)
        expect(button).to_be_disabled()
        expect(button).to_have_attribute("aria-pressed", "false")
    finally:
        close()


def test_ac6_browser_a_word_i_typed_full_disables_it_and_an_error_changes_nothing(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, WIDTH, HEIGHT, False)
    try:
        mock = open_flag_room(page, live_server, grid_view(fx01_grid))
        button = page.get_by_test_id("flag-button")
        select_word(page, LEST)
        expect(button).to_be_enabled()

        # The shown grid counts: four pending letters make LEST full.
        type_lest_pending(page, mock)
        expect(button).to_be_disabled()

        # An `invalid_target` error answering a flag changes no attribute.
        page.wait_for_timeout(SETTLE_MS)
        before = page_attributes(page)
        refused = ErrorMessage(code=ErrorCode.INVALID_TARGET, message="bad clue")
        mock.send(refused.model_dump_json())
        page.wait_for_timeout(SETTLE_MS)
        after = page_attributes(page)
        assert after == before
    finally:
        close()


def test_ac6_browser_my_flag_on_a_word_full_on_the_page_keeps_the_button_pressed(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, WIDTH, HEIGHT, False)
    try:
        mock = open_flag_room(page, live_server, grid_view(fx01_grid))
        button = page.get_by_test_id("flag-button")
        select_word(page, LEST)
        mock.send(flag_changed_frame(6, "p1", LEST))
        expect_seq(page, 6)
        expect(button).to_have_attribute("aria-pressed", "true")

        # LEST is full on the page and my flag is still on it: enabled, pressed.
        type_lest_pending(page, mock)
        expect(page.get_by_test_id("grid")).to_have_attribute("data-word", "4,0,0")
        expect(button).to_be_enabled()
        expect(button).to_have_attribute("aria-pressed", "true")

        # A click removes my flag; once the server says so, the full word with no
        # flag of mine disables the button.
        frames = frames_sent_by(page, mock, button.click)
        assert_one_flag_frame(frames, NULL_WIRE)
        expect(button).to_have_attribute("aria-pressed", "true")
        mock.send(flag_changed_frame(7, "p1", None))
        expect_seq(page, 7)
        expect(button).to_have_attribute("aria-pressed", "false")
        expect(button).to_be_disabled()
    finally:
        close()
