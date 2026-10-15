"""Tests of spec 024, AC-2 and AC-3: the room's reveal budget.

AC-2: reveals draw on a room budget set by the host, 5 letters and 1 word by
default (the rule, the real WebSocket, the page with a mocked socket). AC-3: at
zero budget the reveal buttons are disabled and say why (the page with a mocked
socket). The edge cases "Rate" and "Allowance changed after reveals" are tested
under AC-2. The shared setup is in `spec024_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellTarget,
    ChangeSettings,
    ErrorCode,
    HelpMode,
    Pong,
    Reveal,
    RevealBudget,
    RevealResult,
    WordTarget,
)
from nock.room import RoomConfig, RoomState, handle_message, new_room
from nock.server import create_app
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    DEFAULT_BUDGET,
    MIME,
    NOW,
    QUIET_MS,
    ROOM_CODE,
    WAIT_TIMEOUT_MS,
    Peer,
    accepted_reveal,
    cell_at,
    events_of,
    expect_seq,
    fr_count,
    grid_from_text,
    host_changes,
    join_one,
    join_peers,
    load_fr,
    make_catalogue,
    make_dist_dir,
    make_registry,
    open_room,
    ping_and_wait,
    player_record,
    refusal_code,
    reveal,
    reveal_result_frame,
    seen_at,
    settings_changed_frame,
    two_player_room,
    write,
)

MIN_TEXT_CONTRAST = 4.5

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry whose throttle never refuses and that never times a socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


# ---- AC-2, rule ----

# Five letter reveals on five different cells, by p1 and p2 in turn.
FIVE_LETTERS: list[tuple[str, int, int]] = [
    ("p1", 0, 1),
    ("p2", 1, 0),
    ("p1", 1, 1),
    ("p2", 1, 3),
    ("p1", 1, 4),
]
VIDE = WordTarget(row=2, column=0, clue_index=0)
AMEN = WordTarget(row=3, column=0, clue_index=0)


def budget_of_result(events: list[object]) -> RevealBudget:
    assert len(events) >= 1, "the reveal logged no entry"
    first = events[0]
    assert isinstance(first, RevealResult), events
    return first.reveal_budget


def after_five_letter_reveals(grid: Grid) -> RoomState:
    state = two_player_room(grid)
    for player_id, row, column in FIVE_LETTERS:
        target = CellTarget(row=row, column=column)
        state = accepted_reveal(state, target, player_id).state
    return state


def test_ac2_a_new_room_has_the_default_budget_and_allowance(fx01_grid: Grid) -> None:
    state = new_room(ROOM_CODE, fx01_grid, NOW)

    assert state.reveal_budget == RevealBudget(letters=5, words=1)
    assert state.settings.reveal_budget == RevealBudget(letters=5, words=1)


def test_ac2_each_letter_reveal_spends_one_letter_down_to_zero(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    budgets: list[RevealBudget] = []
    for player_id, row, column in FIVE_LETTERS:
        target = CellTarget(row=row, column=column)
        outcome = accepted_reveal(state, target, player_id)
        budgets.append(budget_of_result(events_of(outcome)))
        state = outcome.state

    assert budgets == [
        RevealBudget(letters=4, words=1),
        RevealBudget(letters=3, words=1),
        RevealBudget(letters=2, words=1),
        RevealBudget(letters=1, words=1),
        RevealBudget(letters=0, words=1),
    ]
    assert state.reveal_budget == RevealBudget(letters=0, words=1)


def test_ac2_a_sixth_letter_reveal_is_budget_exhausted(fx01_grid: Grid) -> None:
    state = after_five_letter_reveals(fx01_grid)

    outcome = reveal(state, CellTarget(row=2, column=1), "p2", NOW + 5)

    assert refusal_code(outcome) is ErrorCode.BUDGET_EXHAUSTED
    assert outcome.entries == ()
    assert outcome.state == seen_at(state, "p2", NOW + 5)


def test_ac2_one_word_reveal_then_spends_the_word_and_a_second_is_refused(
    fx01_grid: Grid,
) -> None:
    state = after_five_letter_reveals(fx01_grid)

    first = accepted_reveal(state, VIDE, "p1")
    second = reveal(first.state, AMEN, "p2")

    assert budget_of_result(events_of(first)) == RevealBudget(letters=0, words=0)
    assert first.state.reveal_budget == RevealBudget(letters=0, words=0)
    assert refusal_code(second) is ErrorCode.BUDGET_EXHAUSTED
    assert second.entries == ()


def test_ac2_a_word_costs_one_word_and_no_letter(fx01_grid: Grid) -> None:
    outcome = accepted_reveal(two_player_room(fx01_grid), MIME, "p1")

    assert budget_of_result(events_of(outcome)) == RevealBudget(letters=5, words=0)
    assert outcome.state.reveal_budget == RevealBudget(letters=5, words=0)


def two_letters_and_a_word(grid: Grid) -> RoomState:
    state = two_player_room(grid)
    state = accepted_reveal(state, CellTarget(row=1, column=0), "p1").state
    state = accepted_reveal(state, CellTarget(row=1, column=1), "p2").state
    state = accepted_reveal(state, MIME, "p1").state
    assert state.reveal_budget == RevealBudget(letters=3, words=0)
    return state


def test_ac2_a_new_allowance_gives_the_new_allowance_minus_what_was_used(
    fx01_grid: Grid,
) -> None:
    state = two_letters_and_a_word(fx01_grid)

    changed = host_changes(state, HelpMode.FREE, 7, 2)

    assert changed.reveal_budget == RevealBudget(letters=5, words=1)
    assert changed.settings.reveal_budget == RevealBudget(letters=7, words=2)
    following = accepted_reveal(changed, CellTarget(row=1, column=3), "p2")
    assert budget_of_result(events_of(following)) == RevealBudget(letters=4, words=1)


def test_ac2_a_smaller_allowance_never_leaves_less_than_zero(
    fx01_grid: Grid,
) -> None:
    state = two_letters_and_a_word(fx01_grid)

    changed = host_changes(state, HelpMode.FREE, 1, 1)

    assert changed.reveal_budget == RevealBudget(letters=0, words=0)


def test_ac2_reveals_are_not_counted_by_the_edit_rate_limit(fx01_grid: Grid) -> None:
    config = RoomConfig(max_edits_per_second=1)
    state = write(two_player_room(fx01_grid), "p1", 0, 1, "N").state
    edits_before = player_record(state, "p1").recent_edits
    targets: list[CellTarget | WordTarget] = [
        CellTarget(row=1, column=0),
        CellTarget(row=1, column=1),
        MIME,
    ]

    for target in targets:
        message = Reveal(target=target)
        outcome = handle_message(state, "p1", message, NOW + 0.5, config)
        assert outcome.reply == (), outcome.reply
        assert len(outcome.entries) >= 2
        state = outcome.state

    assert player_record(state, "p1").recent_edits == edits_before
    assert player_record(state, "p1").last_input_at == NOW + 0.5


# ---- AC-2, WebSocket ----


def one_letter_spent(
    stack: contextlib.ExitStack, client: TestClient, code: str
) -> tuple[Peer, Peer]:
    """A (host) sets the budget to 1 letter and 1 word, then reveals (1, 0)."""
    ana, bob = join_peers(stack, client, code, ["Ana", "Bob"])
    one_each = RevealBudget(letters=1, words=1)
    ana.send(ChangeSettings(help_mode=HelpMode.FREE, reveal_budget=one_each))
    for peer in (ana, bob):
        peer.wait_for_seq(3, f"the settings on {peer.name}")
    ana.send(Reveal(target=CellTarget(row=1, column=0)))
    for peer in (ana, bob):
        peer.wait_for_seq(5, f"the reveal on {peer.name}")
    return ana, bob


def test_ac2_websocket_both_players_get_the_budget_left(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = one_letter_spent(stack, client, room_code)

        for peer in (ana, bob):
            assert peer.errors() == []
            assert peer.reveal_results() == [
                RevealResult(
                    seq=4,
                    player_id=ana.you(),
                    target=CellTarget(row=1, column=0),
                    reveal_budget=RevealBudget(letters=0, words=1),
                )
            ]


def test_ac2_websocket_a_reveal_past_the_budget_is_refused_to_its_sender_only(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = one_letter_spent(stack, client, room_code)
        seen_by_ana = len(ana.messages())

        bob.send(Reveal(target=CellTarget(row=1, column=1)))
        bob.wait_until(lambda: len(bob.errors()) == 1, "the refusal on Bob")
        ping_and_wait(ana)

        assert [error.code for error in bob.errors()] == [ErrorCode.BUDGET_EXHAUSTED]
        assert ana.messages()[seen_by_ana:] == [Pong()]


def test_ac2_websocket_a_later_joiner_gets_the_budget_left_and_the_allowance(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        one_letter_spent(stack, client, room_code)

        cy = join_one(stack, client, room_code, "Cy")

        snapshot = cy.snapshot()
        assert snapshot.reveal_budget == RevealBudget(letters=0, words=1)
        assert snapshot.settings.reveal_budget == RevealBudget(letters=1, words=1)


# ---- AC-2, page with a mocked socket ----


def test_ac2_the_new_fr_json_keys_of_the_buttons() -> None:
    texts = load_fr()

    assert texts["reveal.letter"] == "Lettre ({count})"
    assert texts["reveal.word"] == "Mot ({count})"
    assert texts["reveal.letter_label"] == "Révéler la lettre (reste {count})"
    assert texts["reveal.word_label"] == "Révéler le mot (reste {count})"


def test_ac2_browser_the_buttons_show_what_is_left_of_the_budget(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()

    letter = page.get_by_test_id("reveal-letter")
    word = page.get_by_test_id("reveal-word")
    expect(letter).to_have_text(fr_count("reveal.letter", 5))
    expect(letter).to_have_attribute("aria-label", fr_count("reveal.letter_label", 5))
    expect(word).to_have_text(fr_count("reveal.word", 1))
    expect(word).to_have_attribute("aria-label", fr_count("reveal.word_label", 1))
    assert fr_count("reveal.letter", 5) == "Lettre (5)"


def test_ac2_browser_a_reveal_result_updates_the_letter_count(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    letter = page.get_by_test_id("reveal-letter")
    expect(letter).to_have_text(fr_count("reveal.letter", 5))

    target = CellTarget(row=4, column=4)
    mock.send(reveal_result_frame(6, target, RevealBudget(letters=4, words=1)))

    expect_seq(page, 6)
    expect(letter).to_have_text(fr_count("reveal.letter", 4))
    expect(letter).to_have_attribute("aria-label", fr_count("reveal.letter_label", 4))
    expect(page.get_by_test_id("reveal-word")).to_have_text(fr_count("reveal.word", 1))


def test_ac2_browser_settings_changed_updates_the_letter_count(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    target = CellTarget(row=4, column=4)
    mock.send(reveal_result_frame(6, target, RevealBudget(letters=4, words=1)))
    letter = page.get_by_test_id("reveal-letter")
    expect(letter).to_have_text(fr_count("reveal.letter", 4))

    allowance = RevealBudget(letters=4, words=1)
    left = RevealBudget(letters=3, words=1)
    mock.send(settings_changed_frame(7, HelpMode.FREE, allowance, left))

    expect_seq(page, 7)
    expect(letter).to_have_text(fr_count("reveal.letter", 3))
    expect(letter).to_have_attribute("aria-label", fr_count("reveal.letter_label", 3))


# ---- AC-3: at zero budget the buttons are disabled and say why ----

# Spec 035's contrast scan, run on one element and its descendants although the
# element is a disabled control (the scan itself leaves disabled controls out).
DISABLED_CONTRAST_SCRIPT = "root => {\n" + COLOUR_CONTRAST_JS + r"""
  const measurements = [];
  const elements = [root, ...root.querySelectorAll('*')];
  for (const element of elements) {
    let ownText = '';
    for (const node of element.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        ownText += node.textContent;
      }
    }
    ownText = ownText.trim();
    if (ownText === '') {
      continue;
    }
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    if (box.width === 0 || box.height === 0 || style.visibility !== 'visible') {
      continue;
    }
    if (element.closest('.visually-hidden')) {
      continue;
    }
    let opacity = 1;
    let background = null;
    for (let node = element; node; node = node.parentElement) {
      const nodeStyle = getComputedStyle(node);
      opacity *= parseFloat(nodeStyle.opacity);
      if (background === null) {
        const candidate = parseColour(nodeStyle.backgroundColor);
        if (candidate[3] > 0) {
          background = candidate;
        }
      }
    }
    const opaqueBackground = background === null ? WHITE : over(background, WHITE);
    const text = parseColour(style.color);
    text[3] = text[3] * opacity;
    const shown = over(text, opaqueBackground);
    measurements.push({text: ownText, ratio: contrast(shown, opaqueBackground)});
  }
  return measurements;
}
"""
NO_LETTER_LEFT = RevealBudget(letters=0, words=1)
NOTHING_LEFT = RevealBudget(letters=0, words=0)


def disabled_text_contrasts(button: Locator) -> list[dict[str, Any]]:
    """What the contrast scan measures on a button and its descendants."""
    measurements = button.evaluate(DISABLED_CONTRAST_SCRIPT)
    assert isinstance(measurements, list)
    return measurements


def assert_text_keeps_contrast(button: Locator) -> None:
    measurements = disabled_text_contrasts(button)
    assert len(measurements) >= 1, "the disabled button shows no text"
    for measurement in measurements:
        assert measurement["ratio"] >= MIN_TEXT_CONTRAST, measurements


def open_no_letter_left(page: Page, live_server: str, grid: Grid) -> None:
    open_room(page, live_server, grid, left=NO_LETTER_LEFT)
    cell_at(page, 2, 2).click()


def test_ac3_the_new_fr_json_keys_of_a_spent_budget() -> None:
    texts = load_fr()

    assert texts["reveal.letter_none"] == "Plus de lettre"
    assert texts["reveal.word_none"] == "Plus de mot"
    assert texts["reveal.letter_none_label"] == (
        "Révéler la lettre : plus de lettre à révéler"
    )
    assert texts["reveal.word_none_label"] == "Révéler le mot : plus de mot à révéler"


def test_ac3_no_letter_left_disables_the_letter_button_and_says_why(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_no_letter_left(page, live_server, fx01_grid)
    texts = load_fr()

    letter = page.get_by_test_id("reveal-letter")
    expect(letter).to_be_disabled()
    expect(letter).to_have_text(texts["reveal.letter_none"])
    expect(letter).to_have_attribute("aria-label", texts["reveal.letter_none_label"])
    word = page.get_by_test_id("reveal-word")
    expect(word).to_be_enabled()
    expect(word).to_have_text(fr_count("reveal.word", 1))


def test_ac3_clicking_the_disabled_letter_button_sends_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, left=NO_LETTER_LEFT)
    cell_at(page, 2, 2).click()
    letter = page.get_by_test_id("reveal-letter")
    expect(letter).to_be_disabled()
    page.wait_for_timeout(QUIET_MS)
    sent_before = len(mock.frames_without_pings())

    letter.click(force=True, timeout=WAIT_TIMEOUT_MS)
    page.wait_for_timeout(QUIET_MS)

    assert mock.frames_without_pings()[sent_before:] == []


def test_ac3_no_word_left_after_a_reveal_result_disables_the_word_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, left=NO_LETTER_LEFT)
    cell_at(page, 2, 2).click()
    word = page.get_by_test_id("reveal-word")
    expect(word).to_be_enabled()

    mock.send(reveal_result_frame(6, MIME, NOTHING_LEFT))

    texts = load_fr()
    expect_seq(page, 6)
    expect(word).to_be_disabled()
    expect(word).to_have_text(texts["reveal.word_none"])
    expect(word).to_have_attribute("aria-label", texts["reveal.word_none_label"])
    expect(page.get_by_test_id("reveal-letter")).to_be_disabled()


def test_ac3_a_disabled_reveal_button_keeps_a_text_contrast_of_4_5(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, left=NO_LETTER_LEFT)
    cell_at(page, 2, 2).click()
    letter = page.get_by_test_id("reveal-letter")
    word = page.get_by_test_id("reveal-word")
    expect(letter).to_be_disabled()
    expect(letter).to_have_text(load_fr()["reveal.letter_none"])
    assert_text_keeps_contrast(letter)

    mock.send(reveal_result_frame(6, MIME, NOTHING_LEFT))
    expect(word).to_be_disabled()
    expect(word).to_have_text(load_fr()["reveal.word_none"])

    assert_text_keeps_contrast(letter)
    assert_text_keeps_contrast(word)


def test_ac3_a_first_snapshot_with_a_zero_allowance_shows_both_buttons_disabled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, left=NOTHING_LEFT, allowance=NOTHING_LEFT)
    cell_at(page, 2, 2).click()
    texts = load_fr()

    letter = page.get_by_test_id("reveal-letter")
    word = page.get_by_test_id("reveal-word")
    expect(letter).to_be_disabled()
    expect(letter).to_have_text(texts["reveal.letter_none"])
    expect(letter).to_have_attribute("aria-label", texts["reveal.letter_none_label"])
    expect(word).to_be_disabled()
    expect(word).to_have_text(texts["reveal.word_none"])
    expect(word).to_have_attribute("aria-label", texts["reveal.word_none_label"])


def test_ac3_the_default_budget_leaves_both_buttons_enabled_as_a_control(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, left=DEFAULT_BUDGET)
    cell_at(page, 2, 2).click()

    expect(page.get_by_test_id("reveal-letter")).to_be_enabled()
    expect(page.get_by_test_id("reveal-word")).to_be_enabled()
