"""Tests of spec 012, AC-8: nicknames are typed and stored in capitals (decision 12).

The rule (`normalize_nickname` and `join_room`) and the real WebSocket store the
capitals: NFC, stripped, `str.upper()`, then NFC again, so that a Greek name typed
in small letters and in capitals is stored alike, its length is counted after the
second NFC, and every stored nickname is in NFC. The browser, with the live server
and with spec 040's mocked socket, shows the nickname input in capitals through CSS
while its value keeps the text as typed, applies the same rule to the join it sends
(from the form, and in case (b) of AC-6), and shows a nickname with capitalised
words, as spec 040's `displayNickname` writes it: in the roster, the host's remove
labels (spec 014), a clue flag's label (spec 021), the author line (spec 019), the
chat authors and the mute rows (spec 022). The shared setup is in `spec012_harness`.

Choices where the spec leaves room:

- "Typing" is `press_sequentially`, one key at a time; a paste, a change of the
  whole text in one step, is `fill`. The value "stays" as typed: it is read once
  more after `SETTLE_MS`.
- The five cells of the places snapshot hold the letters of TAMIS: `T` by `p1`,
  `A` by `p2`, `M` by `p3`, `I` by `p4` and `S` by `p5`. The players have the
  colours 0 to 4 and are all active. The chat lines are `salut`, `bonjour`,
  `coucou`, `bonsoir` and `hello`. The snapshot's seq is 18: five joins, five chat
  lines, five letters, two flags and a mute.
- Only the chat tests open the chat panel, so that it never covers a cell that the
  author-line test taps.
- AC-8 names no `fr.json` key for the author line and writes its texts out
  (`Lettre de Jean-Luc`), so this file does too. The other texts come from the key
  that AC-8 names, filled as `t` fills it.
- The Greek and Devanagari letters, the sharp s, U+2019 and the combining marks
  are written as named escapes, never as raw characters.

Spec 043 (the design's room layout) moves what these tests reach: the chat panel
is the Salon's Discussion tab (`show_tab`), the authors switch is an item of the
room Menu (`open_menu`), and the mute buttons are in the Joueurs rows, named by
each row's `roster-nickname`.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, expect

import nock.room
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    ChatMessage,
    ClueRef,
    ErrorCode,
    FlagView,
    GridView,
    Join,
    LetterCellView,
    PlayerJoined,
    RevealBudget,
    Snapshot,
    grid_view,
)
from nock.room import normalize_nickname
from room_panels import open_menu, show_tab
from spec012_harness import (
    FORM_TIMEOUT_MS,
    MOCK_TOKEN,
    MockRoomSocket,
    active_view,
    grid_from_text,
    join_text,
    load_fr,
    make_app,
    make_dist_dir,
    make_registry,
    make_state,
    only_error_code,
    open_mock_room,
    receive_error_code,
    receive_snapshot,
    run_join,
    settle,
    socket_url,
    submit_form,
)

# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry that ticks fast and never times a silent socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def ws_client(
    registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One client, one event loop, on an app serving the room `room_code`."""
    app = make_app(registry, dist_dir)
    with TestClient(app) as client:
        yield client


# ---- Test data: the rule -----------------------------------------------------

SHARP_S = "\N{LATIN SMALL LETTER SHARP S}"
STREET_NAME = "Stra" + SHARP_S + "enbahnfahrerin"  # 19 characters
STREET_NAME_IN_CAPITALS = "STRASSENBAHNFAHRERIN"  # 20 characters: the sharp s gives SS
ELEVEN_SHARP_S = SHARP_S * 11  # 11 characters, 22 in capitals
NON_EMPTY_MESSAGE = r".+"  # the message names the broken rule

# The name Paisios typed in small letters, whose third letter is U+0390.
PAISIOS_SMALL = (
    "\N{GREEK CAPITAL LETTER PI}"
    "\N{GREEK SMALL LETTER ALPHA}"
    "\N{GREEK SMALL LETTER IOTA WITH DIALYTIKA AND TONOS}"
    "\N{GREEK SMALL LETTER SIGMA}"
    "\N{GREEK SMALL LETTER IOTA}"
    "\N{GREEK SMALL LETTER OMICRON}"
    "\N{GREEK SMALL LETTER FINAL SIGMA}"
)
# The same name typed in capitals, U+03A0 U+0391 U+03AA U+0301 U+03A3 U+0399 U+039F
# U+03A3 (8 characters): also the nickname stored for both.
PAISIOS_CAPITALS = (
    "\N{GREEK CAPITAL LETTER PI}"
    "\N{GREEK CAPITAL LETTER ALPHA}"
    "\N{GREEK CAPITAL LETTER IOTA WITH DIALYTIKA}"
    "\N{COMBINING ACUTE ACCENT}"
    "\N{GREEK CAPITAL LETTER SIGMA}"
    "\N{GREEK CAPITAL LETTER IOTA}"
    "\N{GREEK CAPITAL LETTER OMICRON}"
    "\N{GREEK CAPITAL LETTER SIGMA}"
)

# U+0390 followed by 18 times U+03B1 (19 characters). Its capitals are U+0399
# U+0308 U+0301 followed by 18 times U+0391 (21 characters), which the second NFC
# makes U+03AA U+0301 followed by 18 times U+0391 (20 characters).
IOTA_THEN_18_ALPHAS = (
    "\N{GREEK SMALL LETTER IOTA WITH DIALYTIKA AND TONOS}"
    + "\N{GREEK SMALL LETTER ALPHA}" * 18
)
IOTA_THEN_18_ALPHAS_STORED = (
    "\N{GREEK CAPITAL LETTER IOTA WITH DIALYTIKA}"
    + "\N{COMBINING ACUTE ACCENT}"
    + "\N{GREEK CAPITAL LETTER ALPHA}" * 18
)

# A name that starts with U+1F80, and the same text for Unicode written in parts:
# alpha, the combining ypogegrammeni U+0345 and the combining comma above U+0313.
ALPHA_NAME = (
    "\N{GREEK SMALL LETTER ALPHA WITH PSILI AND YPOGEGRAMMENI}"
    "\N{GREEK SMALL LETTER NU}"
    "\N{GREEK SMALL LETTER ALPHA}"
)
ALPHA_NAME_IN_PARTS = (
    "\N{GREEK SMALL LETTER ALPHA}"
    "\N{COMBINING GREEK YPOGEGRAMMENI}"
    "\N{COMBINING COMMA ABOVE}"
    "\N{GREEK SMALL LETTER NU}"
    "\N{GREEK SMALL LETTER ALPHA}"
)
# Both are stored as U+1F08 U+0399 U+039D U+0391 (4 characters).
ALPHA_NAME_STORED = (
    "\N{GREEK CAPITAL LETTER ALPHA WITH PSILI}"
    "\N{GREEK CAPITAL LETTER IOTA}"
    "\N{GREEK CAPITAL LETTER NU}"
    "\N{GREEK CAPITAL LETTER ALPHA}"
)

# The Devanagari name of AC-1, whose second character is a spacing mark (Mc).
RAM_NAME = (
    "\N{DEVANAGARI LETTER RA}\N{DEVANAGARI VOWEL SIGN AA}\N{DEVANAGARI LETTER MA}"
)

# Every text for which AC-1 or AC-8 says what `normalize_nickname` returns.
TEXTS_OF_AC1_AND_AC8 = [
    pytest.param("  Ana  ", id="ac1-ana-with-spaces"),
    pytest.param("\N{LATIN CAPITAL LETTER E WITH ACUTE}lodie", id="ac1-elodie"),
    pytest.param("Jean-Luc", id="ac1-jean-luc"),
    pytest.param("O'Neil", id="ac1-o-neil-ascii-apostrophe"),
    pytest.param("O\N{RIGHT SINGLE QUOTATION MARK}Neil", id="ac1-o-neil-u2019"),
    pytest.param("bob_42", id="ac1-bob-42"),
    pytest.param("Anne Marie", id="ac1-anne-marie"),
    pytest.param("Zo\N{LATIN SMALL LETTER E WITH DIAERESIS}", id="ac1-zoe"),
    pytest.param("12", id="ac1-digits"),
    pytest.param(RAM_NAME, id="ac1-ram"),
    pytest.param("x" * 20, id="ac1-20-x"),
    pytest.param("ana", id="ac8-ana-in-small-letters"),
    pytest.param("Ana", id="ac8-ana"),
    pytest.param(STREET_NAME, id="ac8-street-name"),
    pytest.param(PAISIOS_SMALL, id="ac8-paisios-in-small-letters"),
    pytest.param(PAISIOS_CAPITALS, id="ac8-paisios-in-capitals"),
    pytest.param(IOTA_THEN_18_ALPHAS, id="ac8-iota-then-18-alphas"),
    pytest.param(ALPHA_NAME, id="ac8-alpha-name"),
    pytest.param(ALPHA_NAME_IN_PARTS, id="ac8-alpha-name-in-parts"),
]


# ---- AC-8: the rule -----------------------------------------------------------


@pytest.mark.parametrize("typed", ["ana", "Ana"])
def test_ac8_normalize_nickname_returns_the_capitals(typed: str) -> None:
    assert normalize_nickname(typed) == "ANA"


def test_ac8_a_letter_whose_capital_is_longer_counts_as_its_capital() -> None:
    assert len(STREET_NAME) == 19

    stored = normalize_nickname(STREET_NAME)

    assert stored == STREET_NAME_IN_CAPITALS
    assert len(stored) == 20


def test_ac8_eleven_sharp_s_are_too_long_once_in_capitals() -> None:
    with pytest.raises(ValueError, match=NON_EMPTY_MESSAGE):
        normalize_nickname(ELEVEN_SHARP_S)


@pytest.mark.parametrize(
    "typed", [PAISIOS_SMALL, PAISIOS_CAPITALS], ids=["small-letters", "capitals"]
)
def test_ac8_a_greek_name_in_small_letters_or_in_capitals_is_stored_alike(
    typed: str,
) -> None:
    stored = normalize_nickname(typed)

    assert stored == PAISIOS_CAPITALS
    assert len(stored) == 8


def test_ac8_the_length_is_counted_after_the_second_nfc() -> None:
    # Without the second NFC the capitals would have 21 characters: the name tests
    # the rule only because of that.
    assert len(IOTA_THEN_18_ALPHAS.upper()) == 21

    stored = normalize_nickname(IOTA_THEN_18_ALPHAS)

    assert stored == IOTA_THEN_18_ALPHAS_STORED
    assert len(stored) == 20


@pytest.mark.parametrize(
    "typed", [ALPHA_NAME, ALPHA_NAME_IN_PARTS], ids=["composed", "in-parts"]
)
def test_ac8_two_texts_that_are_the_same_for_unicode_are_stored_alike(
    typed: str,
) -> None:
    stored = normalize_nickname(typed)

    assert stored == ALPHA_NAME_STORED
    assert len(stored) == 4


@pytest.mark.parametrize("typed", TEXTS_OF_AC1_AND_AC8)
def test_ac8_every_nickname_returned_in_ac1_and_ac8_is_in_nfc(typed: str) -> None:
    stored = normalize_nickname(typed)

    assert unicodedata.is_normalized("NFC", stored) is True


def test_ac8_join_room_stores_the_capitals(fx01_grid: Grid) -> None:
    outcome = run_join(make_state(fx01_grid, []), "ana")

    assert [player.nickname for player in outcome.state.players] == ["ANA"]
    assert len(outcome.entries) == 1
    event = outcome.entries[0].event
    assert event == PlayerJoined(seq=1, player=active_view("joiner1", "ANA", 0, True))


def test_ac8_join_room_refuses_eleven_sharp_s(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [])

    outcome = run_join(state, ELEVEN_SHARP_S)

    assert only_error_code(outcome) == ErrorCode.INVALID_NICKNAME
    assert outcome.state == state


def test_ac8_join_room_suffixes_a_greek_name_typed_in_capitals_then_small_letters(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [])
    first = run_join(state, PAISIOS_CAPITALS, 1)

    second = run_join(first.state, PAISIOS_SMALL, 2)

    nicknames = [player.nickname for player in second.state.players]
    assert nicknames == [PAISIOS_CAPITALS, PAISIOS_CAPITALS + " 2"]


def test_ac8_websocket_eleven_sharp_s_get_invalid_nickname_not_invalid_message(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with ws_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(join_text(ELEVEN_SHARP_S))

        assert receive_error_code(websocket) == ErrorCode.INVALID_NICKNAME

        websocket.send_text(join_text("ana"))
        snapshot = receive_snapshot(websocket)
    assert [view.nickname for view in snapshot.players] == ["ANA"]
    state = registry.room_state(room_code)
    assert state is not None
    assert [player.nickname for player in state.players] == ["ANA"]


# ---- AC-8: the nickname input, live server --------------------------------------


def own_roster_nickname(page: Page) -> Locator:
    own_item = page.locator('[data-testid="roster-player"][data-you="true"]')
    return own_item.get_by_test_id("roster-nickname")


def test_ac8_browser_typed_letters_show_in_capitals_through_css_and_keep_their_value(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    code = room_registry.register_room(fx01_grid)
    page.goto(f"{live_server}/r/{code}")
    nickname_input = page.get_by_test_id("nickname-input")

    nickname_input.press_sequentially("ana", timeout=FORM_TIMEOUT_MS)

    expect(nickname_input).to_have_css("text-transform", "uppercase")
    expect(nickname_input).to_have_value("ana")
    settle(page)
    assert nickname_input.input_value() == "ana"


def test_ac8_browser_the_typed_nickname_joins_and_the_roster_reads_ana(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    code = room_registry.register_room(fx01_grid)
    page.goto(f"{live_server}/r/{code}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.press_sequentially("ana", timeout=FORM_TIMEOUT_MS)

    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")
    expect(own_roster_nickname(page)).to_have_text("Ana")
    state = room_registry.room_state(code)
    assert state is not None
    assert [player.nickname for player in state.players] == ["ANA"]


# ---- AC-8: the page's rule, mocked socket -----------------------------------------


def test_ac8_browser_a_pasted_nickname_keeps_its_value_and_is_sent_in_capitals(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    nickname_input = page.get_by_test_id("nickname-input")

    nickname_input.fill("zoé", timeout=FORM_TIMEOUT_MS)

    expect(nickname_input).to_have_css("text-transform", "uppercase")
    expect(nickname_input).to_have_value("zoé")
    settle(page)
    assert nickname_input.input_value() == "zoé"
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)
    mock.wait_for_frames(1)
    assert mock.joins() == [Join(nickname="ZOÉ", resume_token=None)]


@pytest.mark.parametrize(
    ("typed", "sent"),
    [
        (PAISIOS_SMALL, PAISIOS_CAPITALS),
        (IOTA_THEN_18_ALPHAS, IOTA_THEN_18_ALPHAS_STORED),
        # This case pins the page's first NFC: without it, the parts would give
        # U+0391 U+1F38 U+039D U+0391 where the server's rule gives ALPHA_NAME_STORED.
        (ALPHA_NAME_IN_PARTS, ALPHA_NAME_STORED),
    ],
    ids=["paisios-in-small-letters", "iota-then-18-alphas", "alpha-name-in-parts"],
)
def test_ac8_browser_the_form_sends_the_capitals_after_the_second_nfc(
    page: Page, live_server: str, typed: str, sent: str
) -> None:
    mock = open_mock_room(page, live_server)

    submit_form(page, typed)

    mock.wait_for_frames(1)
    assert mock.joins() == [Join(nickname=sent, resume_token=None)]


CATALOGUE_RECORD = json.dumps({"grid": 1, "selection": None})


def first_join_of_case_b(page: Page, base_url: str, remembered: str) -> Join:
    """The first frame the page sends in case (b) of AC-6, parsed as a Join.

    Args:
        page: A fresh page.
        base_url: The live server, which serves the built client.
        remembered: The `nock.nickname` seeded beside the catalogue record.

    Returns:
        The join the page sent at once, spec 017's `ping` frames left aside.
    """
    items = {"nock.room.ABC123": CATALOGUE_RECORD, "nock.nickname": remembered}
    mock = open_mock_room(page, base_url, items)
    mock.wait_for_frames(1)
    return mock.joins()[0]


def test_ac8_browser_case_b_sends_unchanged_a_name_of_20_after_the_second_nfc(
    page: Page, live_server: str
) -> None:
    join = first_join_of_case_b(page, live_server, IOTA_THEN_18_ALPHAS)

    assert join == Join(nickname=IOTA_THEN_18_ALPHAS, resume_token=None)


def test_ac8_browser_case_b_sends_the_default_nickname_for_eleven_sharp_s(
    page: Page, live_server: str
) -> None:
    default_nickname = load_fr()["room.default_nickname"]

    join = first_join_of_case_b(page, live_server, ELEVEN_SHARP_S)

    assert join == Join(nickname=default_nickname, resume_token=None)


# ---- AC-8: every place that shows a nickname, mocked socket -----------------------

# `p4`'s apostrophe is U+2019. `p5` is U+039D U+038A U+039A U+039F U+03A3, which
# shows as U+039D U+03AF U+03BA U+03BF U+03C2, ending with the final sigma.
O_NEIL_CAPITALS = "O\N{RIGHT SINGLE QUOTATION MARK}NEIL"
O_NEIL_SHOWN = "O\N{RIGHT SINGLE QUOTATION MARK}Neil"
NIKOS_CAPITALS = (
    "\N{GREEK CAPITAL LETTER NU}"
    "\N{GREEK CAPITAL LETTER IOTA WITH TONOS}"
    "\N{GREEK CAPITAL LETTER KAPPA}"
    "\N{GREEK CAPITAL LETTER OMICRON}"
    "\N{GREEK CAPITAL LETTER SIGMA}"
)
NIKOS_SHOWN = (
    "\N{GREEK CAPITAL LETTER NU}"
    "\N{GREEK SMALL LETTER IOTA WITH TONOS}"
    "\N{GREEK SMALL LETTER KAPPA}"
    "\N{GREEK SMALL LETTER OMICRON}"
    "\N{GREEK SMALL LETTER FINAL SIGMA}"
)

PLACES_SEQ = 18
# The five players in roster order, as the page shows them.
SHOWN_NICKNAMES = ["Jean-Luc", "D'Artagnan", "Ana 2", O_NEIL_SHOWN, NIKOS_SHOWN]
# The players other than `p1` (`you`, the host), in roster order, as shown.
OTHERS_SHOWN = [
    ("p2", "D'Artagnan"),
    ("p3", "Ana 2"),
    ("p4", O_NEIL_SHOWN),
    ("p5", NIKOS_SHOWN),
]
MUTED_PLAYER = "p4"
IDES = ClueRef(row=0, column=3, clue_index=0)
LETTERS_BY_AUTHOR = [
    (1, 0, "T", "p1"),
    (1, 1, "A", "p2"),
    (1, 2, "M", "p3"),
    (1, 3, "I", "p4"),
    (1, 4, "S", "p5"),
]
AUTHOR_LINES = [
    ((1, 0), "Lettre de Jean-Luc"),
    ((1, 1), "Lettre de D'Artagnan"),
    ((1, 2), "Lettre de Ana 2"),
    ((1, 3), "Lettre de " + O_NEIL_SHOWN),
    ((1, 4), "Lettre de " + NIKOS_SHOWN),
]


def fr_text(key: str, **values: str) -> str:
    """The `fr.json` text of `key` with each `{name}` replaced, as `t` fills it."""
    text = load_fr()[key]
    for name, value in values.items():
        text = text.replace("{" + name + "}", value)
    return text


def with_authored_letters(view: GridView) -> GridView:
    """The view with the letters of `LETTERS_BY_AUTHOR` in their cells."""
    cells: list[CellView] = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, letter, author in LETTERS_BY_AUTHOR:
                if (cell.row, cell.column) == (row, column):
                    update = {"letter": letter, "author": author}
                    new_cell = cell.model_copy(update=update)
        cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(cells)})


def places_snapshot_frame(grid: Grid) -> str:
    """The FX-01 snapshot of AC-8 that reaches every place showing a nickname."""
    players = (
        active_view("p1", "JEAN-LUC", 0, True),
        active_view("p2", "D'ARTAGNAN", 1),
        active_view("p3", "ANA 2", 2),
        active_view("p4", O_NEIL_CAPITALS, 3).model_copy(update={"muted": True}),
        active_view("p5", NIKOS_CAPITALS, 4),
    )
    chat = (
        ChatMessage(seq=6, player_id="p1", text="salut"),
        ChatMessage(seq=7, player_id="p2", text="bonjour"),
        ChatMessage(seq=8, player_id="p3", text="coucou"),
        ChatMessage(seq=9, player_id="p4", text="bonsoir"),
        ChatMessage(seq=10, player_id="p5", text="hello"),
    )
    flags = (FlagView(player_id="p4", clue=IDES), FlagView(player_id="p5", clue=IDES))
    snapshot = Snapshot(
        seq=PLACES_SEQ,
        you="p1",
        resume_token=MOCK_TOKEN,
        grid=with_authored_letters(grid_view(grid)),
        players=players,
        settings=nock.room.DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=flags,
        chat=chat,
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def open_places_room(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """Join /r/ABC123 from the form and receive the places snapshot of AC-8."""
    mock = open_mock_room(page, base_url)
    submit_form(page, "Jean-Luc")
    mock.wait_for_frames(1)
    mock.send(places_snapshot_frame(grid))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", str(PLACES_SEQ))
    return mock


def roster_item(page: Page, player_id: str) -> Locator:
    return page.locator(f'[data-testid="roster-player"][data-player-id="{player_id}"]')


def clue_of(page: Page, clue: ClueRef) -> Locator:
    """The `clue` element of a word: its index in its clue cell (spec 021)."""
    cell = f'[data-testid="cell"][data-row="{clue.row}"][data-column="{clue.column}"]'
    index = f'[data-testid="clue"][data-clue-index="{clue.clue_index}"]'
    return page.locator(f"{cell} {index}")


def open_chat_panel(page: Page) -> None:
    """Show the Salon's Discussion tab (spec 043's `show_tab`)."""
    show_tab(page, "discussion")


def expected_mute_button(player_id: str, shown: str) -> tuple[str, str]:
    """The text and `aria-label` of a player's `mute-player` (spec 022)."""
    if player_id == MUTED_PLAYER:
        return load_fr()["chat.unmute"], fr_text("chat.unmute_label", name=shown)
    return load_fr()["chat.mute"], fr_text("chat.mute_label", name=shown)


def test_ac8_browser_the_roster_shows_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_places_room(page, live_server, fx01_grid)

    roster = page.get_by_test_id("roster")

    expect(roster.get_by_test_id("roster-nickname")).to_have_text(SHOWN_NICKNAMES)


def test_ac8_browser_the_host_remove_labels_show_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_places_room(page, live_server, fx01_grid)

    for player_id, shown in OTHERS_SHOWN:
        button = roster_item(page, player_id).get_by_test_id("remove-player")
        expected_label = fr_text("host.remove_label", name=shown)
        expect(button).to_have_attribute("aria-label", expected_label)


def test_ac8_browser_the_clue_flag_label_shows_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_places_room(page, live_server, fx01_grid)
    flaggers = ", ".join([O_NEIL_SHOWN, NIKOS_SHOWN])

    label = clue_of(page, IDES).get_by_test_id("clue-flag-label")

    expect(label).to_have_text(fr_text("flag.marker_label", names=flaggers))


def test_ac8_browser_the_author_line_shows_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_places_room(page, live_server, fx01_grid)
    switch = page.get_by_test_id("authors-switch")
    open_menu(page)  # spec 043: the switch is an item of the room Menu
    switch.click()
    expect(switch).to_have_attribute("aria-pressed", "true")
    page.get_by_test_id("menu-button").click()
    author_line = page.get_by_test_id("clue-bar-author")

    for (row, column), expected_line in AUTHOR_LINES:
        cell = page.locator(
            f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
        )
        cell.click()
        expect(author_line).to_have_text(expected_line)


def test_ac8_browser_the_chat_authors_show_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_places_room(page, live_server, fx01_grid)

    open_chat_panel(page)

    chat_list = page.get_by_test_id("chat-list")
    expect(chat_list.get_by_test_id("chat-author")).to_have_text(SHOWN_NICKNAMES)


def test_ac8_browser_the_mute_buttons_show_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # Spec 043: the host's `mute-player` sits in each other player's row of the
    # Joueurs tab, where the chat panel's `mute-row` (with its `mute-name`) was.
    open_places_room(page, live_server, fx01_grid)

    show_tab(page, "players")

    expect(page.get_by_test_id("mute-player")).to_have_count(len(OTHERS_SHOWN))
    for player_id, shown in OTHERS_SHOWN:
        row = roster_item(page, player_id)
        expect(row.get_by_test_id("roster-nickname")).to_have_text(shown)
        button_text, button_label = expected_mute_button(player_id, shown)
        button = row.get_by_test_id("mute-player")
        expect(button).to_have_text(button_text)
        expect(button).to_have_attribute("aria-label", button_label)
