"""Tests of spec 022, AC-16: the chat and reaction controls are reachable from the
keyboard and readable in French.

The keyboard walk is keyboard only after its setup (the snapshot with `you` host
and the tap on the clue cell (0, 3)) and uses spec 035's `tab_to`. The contrast
and language scans are spec 035's; the language scan's test data holds the
nicknames, the clues, the room code and link, and the chat texts the test sent
("Test harness": chat text is user content). The static test reads the new keys
of `fr.json` against the table of "New `fr.json` keys" and checks that spec 035
AC-9's checker still flags its three samples.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import ChatMessage, Reaction
from spec021_harness import IDES, clue_at, select_word
from spec022_harness import (
    REACTION_VALUES,
    chat_frame,
    expect_seq,
    frames_of_type,
    open_chat_room,
    open_panel,
    reaction_frame,
    wait_for_frame_count,
)
from spec024_harness import (
    contrast_problems,
    grid_from_text,
    language_data,
    language_problems,
    load_fr,
    make_walker,
    open_context_page,
    outline_problems,
)
from spec035_harness import unknown_texts

NEW_FR_KEYS = {
    "chat.toggle": "Discussion",
    "chat.toggle_label_unread": "Discussion, {count} messages non lus",
    "chat.unread_many": "99+",
    "chat.heading": "Discussion",
    "chat.input_label": "Message",
    "chat.placeholder": "Écrire au salon",
    "chat.send": "Envoyer",
    "chat.wait": "Patientez un instant avant le prochain message.",
    "chat.muted": "L'hôte a coupé votre discussion.",
    "chat.moderation_heading": "Sourdine",
    "chat.mute": "Couper",
    "chat.unmute": "Rétablir",
    "chat.mute_label": "Couper la discussion de {name}",
    "chat.unmute_label": "Rétablir la discussion de {name}",
    "reaction.button": "Réagir",
    "reaction.button_label": "Réagir sur ce mot",
    "reaction.picker_label": "Réactions",
    "reaction.thumbs_up": "\U0001f44d",
    "reaction.clap": "\U0001f44f",
    "reaction.laugh": "\U0001f602",
    "reaction.wow": "\U0001f62e",
    "reaction.thinking": "\U0001f914",
    "reaction.thumbs_up_label": "Pouce levé",
    "reaction.clap_label": "Bravo",
    "reaction.laugh_label": "Rire",
    "reaction.wow_label": "Waouh",
    "reaction.thinking_label": "Je réfléchis",
    "reaction.shown_label": "{name} : {reaction}",
}
CHECKER_SAMPLES = ["Loading…", "Salon", "Check word"]
SCAN_SIZES = [(1280, 720), (360, 740)]
NICKNAMES = ["Ana", "Bob", "Cy"]
OPEN_CHAT = [
    ChatMessage(seq=3, player_id="p2", text="IDES, je crois"),
    ChatMessage(seq=4, player_id="p3", text="Bonne idée !"),
]
UNREAD_TEXTS = ["Ligne 6", "Ligne 7", "Ligne 8"]
ACCEPTED_SAMPLES = ["Discussion, 3 messages non lus", "Bob : Bravo", "\U0001f44f"]
TYPED_TEXT = "Bonne idée !"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- `fr.json` ----


def test_ac16_fr_json_holds_the_new_keys_with_their_values() -> None:
    texts = load_fr()

    found = {key: texts.get(key) for key in NEW_FR_KEYS}

    assert found == NEW_FR_KEYS


def test_ac16_the_language_checker_still_flags_its_samples() -> None:
    assert unknown_texts(CHECKER_SAMPLES, set()) == CHECKER_SAMPLES


# ---- The keyboard ----


def test_ac16_browser_every_chat_and_reaction_control_is_reached_from_the_keyboard(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_chat_room(page, live_server, fx01_grid, seq=5)
    select_word(page, IDES)
    walker = make_walker(page)

    # Keyboard only from here.
    walker.tab_to("react-button")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("reaction-picker")).to_be_visible()
    for value in REACTION_VALUES:
        walker.tab_to("reaction-option", f'[data-reaction="{value}"]')
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("reaction-picker")).to_have_count(0)

    walker.tab_to("chat-toggle")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("chat-panel")).to_be_visible()
    walker.tab_to("chat-input")
    page.keyboard.type(TYPED_TEXT)
    walker.tab_to("chat-send")
    p2_row = '[data-testid="mute-row"][data-player-id="p2"] [data-testid="mute-player"]'
    walker.tab_to("mute-player", p2_row)
    walker.tab_to("chat-input")
    page.keyboard.press("Enter")
    wait_for_frame_count(page, mock, "chat", 1)

    reached = [step.test_id for step in walker.reached]
    expected = [
        "react-button",
        *(["reaction-option"] * len(REACTION_VALUES)),
        "chat-toggle",
        "chat-input",
        "chat-send",
        "mute-player",
        "chat-input",
    ]
    assert reached == expected
    for step in walker.reached:
        assert (
            outline_problems(
                step.outline_style, step.outline_width, step.outline_contrast
            )
            == []
        ), step
    assert frames_of_type(mock, "chat") == [{"type": "chat", "text": TYPED_TEXT}]


# ---- Contrast and French ----


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=["1280x720", "360x740"])
def test_ac16_browser_the_chat_and_reactions_pass_the_contrast_and_language_scans(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    data = language_data(live_server, NICKNAMES)
    for line in OPEN_CHAT:
        data.add(line.text)
    data.update(UNREAD_TEXTS)
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        mock = open_chat_room(page, live_server, fx01_grid, seq=5, chat=OPEN_CHAT)

        # The panel open, and a `clap` of `p2` shown on IDES.
        open_panel(page)
        mock.send(reaction_frame("p2", IDES, Reaction.CLAP))
        expect(clue_at(page, IDES).get_by_test_id("clue-reaction")).to_have_count(1)
        open_contrast = contrast_problems(page)
        open_language = language_problems(page, data)

        # The panel closed, with 3 unread lines.
        page.keyboard.press("Escape")
        expect(page.get_by_test_id("chat-panel")).to_have_count(0)
        for seq, text in zip((6, 7, 8), UNREAD_TEXTS, strict=True):
            mock.send(chat_frame(seq, "p2", text))
        expect_seq(page, 8)
        expect(page.get_by_test_id("chat-unread")).to_have_text("3")
        closed_contrast = contrast_problems(page)
        closed_language = language_problems(page, data)
    finally:
        close()

    assert open_contrast == []
    assert open_language == []
    assert closed_contrast == []
    assert closed_language == []
    assert unknown_texts(ACCEPTED_SAMPLES, data) == []
