"""Tests of spec 023, AC-8 and AC-9: the activity feed and the check controls.

AC-8 runs two browsers on the live server. AC-9 drives the room page with a
mocked socket. Spec 026 adds to AC-9 the check buttons disabled once the grid is
solved. The shared setup is in `spec023_harness`.

Refined by spec 043 (the design's room layout): `check-panel` is inside
`aide-menu`, labelled by its heading `check-heading` (`fr.json["check.label"]`),
and its items have the visible texts « La lettre », « Le mot », « La grille » and
no `aria-label` (the `check.*_label` keys are removed). Each click is made with the
Aide menu open (spec 043's `open_aide`), and closes it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellTarget,
    Check,
    ErrorCode,
    ErrorMessage,
    GridSolved,
    GridTarget,
    HelpMode,
    RevealBudget,
    RoomSettings,
    SettingsChanged,
    WordTarget,
    parse_client_message,
)
from room_panels import open_aide
from spec023_harness import (
    MIME,
    EnterRoom,
    MockRoomSocket,
    cell_at,
    grid_from_text,
    make_catalogue,
    open_fx01,
    play_ana_checks_the_word,
    sent_letters,
    wait_until_page,
)

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
SETTLE_MS = 400


# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Helpers for the page tests ----


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def sent_checks(mock: MockRoomSocket) -> list[Check]:
    checks: list[Check] = []
    for frame in mock.received:
        message = parse_client_message(frame)
        if isinstance(message, Check):
            checks.append(message)
    return checks


def settings_frame(seq: int, help_mode: HelpMode) -> str:
    settings = RoomSettings(
        help_mode=help_mode,
        reveal_budget=RevealBudget(letters=5, words=1),
        locked=False,
    )
    event = SettingsChanged(
        seq=seq,
        player_id="p1",
        settings=settings,
        reveal_budget=RevealBudget(letters=5, words=1),
    )
    return event.model_dump_json()


def expect_selection(
    page: Page, row: int, column: int, direction: str, word: str
) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)
    expect(grid).to_have_attribute("data-word", word)


def check_items(page: Page) -> Locator:
    feed = page.get_by_test_id("activity-feed")
    return feed.locator('[data-testid="feed-item"][data-kind="check"]')


def feed_text(key: str, name: str) -> str:
    return load_fr()[key].replace("{name}", name)


# ---- AC-8: each check adds a line to the activity feed (live server) ----


def test_ac8_each_check_adds_a_feed_line_with_the_player_and_the_scope(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        play_ana_checks_the_word(page, bob_page, f"{live_server}/r/{code}", enter_room)
        word_line = feed_text("feed.check.word", "Ana")
        for watcher in (page, bob_page):
            expect(check_items(watcher)).to_have_text([word_line])
            expect(check_items(watcher).first).to_have_attribute("data-kind", "check")

        cell_at(bob_page, 2, 1).click()
        open_aide(bob_page)
        bob_page.get_by_test_id("check-letter").click()
        open_aide(bob_page)
        bob_page.get_by_test_id("check-grid").click()

        expected = [
            word_line,
            feed_text("feed.check.letter", "Bob"),
            feed_text("feed.check.grid", "Bob"),
        ]
        for watcher in (page, bob_page):
            expect(check_items(watcher)).to_have_text(expected)
    finally:
        bob_context.close()


# ---- AC-9: the check controls ----


def test_ac9_the_new_fr_json_keys_have_the_texts_of_the_spec() -> None:
    texts = load_fr()

    assert texts["check.label"] == "Vérifier"
    assert texts["check.letter"] == "La lettre"
    assert texts["check.word"] == "Le mot"
    assert texts["check.grid"] == "La grille"
    for removed in ("check.letter_label", "check.word_label", "check.grid_label"):
        assert removed not in texts, removed


def test_ac9_the_panel_holds_three_labelled_buttons_in_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    texts = load_fr()

    panel = page.get_by_test_id("check-panel")
    heading = page.get_by_test_id("check-heading")
    expect(panel).to_have_attribute("role", "group")
    heading_id = heading.get_attribute("id")
    assert heading_id
    expect(panel).to_have_attribute("aria-labelledby", heading_id)
    expect(heading).to_have_text(texts["check.label"])
    in_aide = panel.evaluate("el => el.closest('[data-testid=\"aide-menu\"]') !== null")
    assert in_aide is True
    identifiers = panel.evaluate(
        "el => Array.from(el.querySelectorAll('button'))"
        ".map(b => b.getAttribute('data-testid'))"
    )
    assert identifiers == ["check-letter", "check-word", "check-grid"]
    for scope in ("letter", "word", "grid"):
        button = page.get_by_test_id(f"check-{scope}")
        expect(button).to_have_text(texts[f"check.{scope}"])
        assert button.get_attribute("aria-label") is None, scope


def test_ac9_with_nothing_selected_only_the_grid_button_is_enabled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    expect(page.get_by_test_id("check-letter")).to_be_disabled()
    expect(page.get_by_test_id("check-word")).to_be_disabled()
    expect(page.get_by_test_id("check-grid")).to_be_enabled()


def test_ac9_the_grid_button_sends_one_grid_check(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    open_aide(page)
    page.get_by_test_id("check-grid").click()

    wait_until_page(page, lambda: len(sent_checks(mock)) >= 1)
    page.wait_for_timeout(SETTLE_MS)
    assert sent_checks(mock) == [Check(target=GridTarget())]
    raw_checks = [
        json.loads(frame)
        for frame in mock.received
        if json.loads(frame).get("type") == "check"
    ]
    assert raw_checks == [{"type": "check", "target": {"scope": "grid"}}]


def test_ac9_the_letter_and_word_buttons_send_the_selected_cell_and_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    cell_at(page, 2, 2).click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    expect(page.get_by_test_id("check-letter")).to_be_enabled()
    expect(page.get_by_test_id("check-word")).to_be_enabled()

    open_aide(page)
    page.get_by_test_id("check-letter").click()
    wait_until_page(page, lambda: len(sent_checks(mock)) >= 1)
    open_aide(page)
    page.get_by_test_id("check-word").click()
    wait_until_page(page, lambda: len(sent_checks(mock)) >= 2)
    page.wait_for_timeout(SETTLE_MS)

    assert sent_checks(mock) == [
        Check(target=CellTarget(row=2, column=2)),
        Check(target=MIME),
    ]
    raw_checks = [
        json.loads(frame)
        for frame in mock.received
        if json.loads(frame).get("type") == "check"
    ]
    assert raw_checks == [
        {"type": "check", "target": {"scope": "letter", "row": 2, "column": 2}},
        {
            "type": "check",
            "target": {"scope": "word", "row": 0, "column": 2, "clue_index": 0},
        },
    ]
    expect_selection(page, 2, 2, "down", "0,2,0")


def test_ac9_pressing_a_button_does_not_guess_the_result(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 1, {"letter": "X", "author": "p2"})],
    )

    open_aide(page)
    page.get_by_test_id("check-grid").click()
    wait_until_page(page, lambda: len(sent_checks(mock)) >= 1)
    page.wait_for_timeout(SETTLE_MS)

    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "false")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")


def expect_no_check_panel(page: Page) -> None:
    expect(page.get_by_test_id("check-panel")).to_have_count(0)
    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_have_count(0)


def test_ac9_a_help_mode_none_in_the_snapshot_shows_no_check_panel(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, help_mode=HelpMode.NONE)
    expect(page.get_by_test_id("undo-button")).to_be_visible()

    expect_no_check_panel(page)


def test_ac9_settings_changed_to_none_removes_the_check_panel(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    cell_at(page, 2, 2).click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_be_enabled()

    mock.send(settings_frame(6, HelpMode.NONE))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_no_check_panel(page)


@pytest.mark.parametrize("help_mode", [HelpMode.FREE, HelpMode.VOTE])
def test_ac9_settings_changed_from_none_to_free_or_vote_shows_the_panel_again(
    page: Page, live_server: str, fx01_grid: Grid, help_mode: HelpMode
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    cell_at(page, 2, 2).click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    mock.send(settings_frame(6, HelpMode.NONE))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_no_check_panel(page)

    mock.send(settings_frame(7, help_mode))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    open_aide(page)
    panel = page.get_by_test_id("check-panel")
    expect(panel).to_be_visible()
    identifiers = panel.evaluate(
        "el => Array.from(el.querySelectorAll('button'))"
        ".map(b => b.getAttribute('data-testid'))"
    )
    assert identifiers == ["check-letter", "check-word", "check-grid"]
    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_be_enabled()
    expect_selection(page, 2, 2, "down", "0,2,0")


@pytest.mark.parametrize(
    ("taps", "row", "column", "word"),
    [(1, 0, 1, "0,0,1"), (2, 1, 1, "0,0,1")],
    ids=["tap-n-once", "tap-a-twice"],
)
def test_ac9_the_word_button_sends_the_clue_index_of_the_second_clue(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    taps: int,
    row: int,
    column: int,
    word: str,
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    for _ in range(taps):
        cell_at(page, row, column).click()
    expect_selection(page, row, column, "down", word)

    open_aide(page)
    page.get_by_test_id("check-word").click()

    wait_until_page(page, lambda: len(sent_checks(mock)) >= 1)
    page.wait_for_timeout(SETTLE_MS)
    naval = WordTarget(row=0, column=0, clue_index=1)
    assert sent_checks(mock) == [Check(target=naval)]
    raw_checks = [
        json.loads(frame)
        for frame in mock.received
        if json.loads(frame).get("type") == "check"
    ]
    assert raw_checks == [
        {
            "type": "check",
            "target": {"scope": "word", "row": 0, "column": 0, "clue_index": 1},
        }
    ]
    expect_selection(page, row, column, "down", word)


@pytest.mark.parametrize(
    "code",
    [ErrorCode.HELP_DISABLED, ErrorCode.INVALID_TARGET],
    ids=["help-disabled", "invalid-target"],
)
def test_ac9_a_refused_check_leaves_the_pending_edit_alone(
    page: Page, live_server: str, fx01_grid: Grid, code: ErrorCode
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 1).click()
    page.keyboard.press("b")
    cell = cell_at(page, 1, 1)
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    wait_until_page(page, lambda: len(sent_letters(mock)) == 1)

    mock.send(ErrorMessage(code=code, message="refused").model_dump_json())
    page.wait_for_timeout(SETTLE_MS)

    expect(cell).to_have_attribute("data-letter", "B")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")
    # Control: an edit answer still drops the pending edit, so it was there.
    locked_answer = ErrorMessage(code=ErrorCode.CELL_LOCKED, message="locked")
    mock.send(locked_answer.model_dump_json())
    expect(cell).to_have_attribute("data-letter", "")
    expect(cell).to_have_attribute("data-unconfirmed", "false")


# ---- Spec 026: the check buttons are disabled once solved ----


def test_ac9_a_solved_snapshot_disables_the_three_buttons(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, solved=True)
    cell_at(page, 2, 2).click()

    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_be_disabled()
    page.wait_for_timeout(SETTLE_MS)
    assert sent_checks(mock) == []


def test_ac9_a_grid_solved_event_disables_the_three_buttons(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    expect(page.get_by_test_id("check-letter")).to_be_enabled()
    expect(page.get_by_test_id("check-word")).to_be_enabled()
    expect(page.get_by_test_id("check-grid")).to_be_enabled()

    mock.send(GridSolved(seq=6, elapsed_ms=1000).model_dump_json())

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_be_disabled()
