"""Tests of spec 025, AC-4 and AC-5: the help controls by help mode.

AC-4: in `none` mode the check and reveal panels are absent (the page with a
mocked socket; the server's `help_disabled` of specs 023 and 024). AC-5: in vote
mode a check of a letter or of a word needs no vote (the rule on
`handle_message`, then the page while a vote is open). The shared setup is in
`spec025_harness`.

Refined by spec 043 (the design's room layout): the two panels are groups of the
Aide menu, which stays in `none` mode (`aide-button` and `aide-menu` exist where
`room-toolbar` did); a test that checks the panels show, or clicks an item, opens
the menu first with spec 043's `open_aide`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    CellRef,
    CellTarget,
    ChangeSettings,
    Check,
    CheckResult,
    ClientMessage,
    ErrorCode,
    GridTarget,
    HelpMode,
    Reveal,
    VoteOutcome,
    WordTarget,
)
from nock.room import new_room
from room_panels import open_aide
from spec025_harness import (
    FIVE_AND_ONE,
    MIME,
    NOW,
    ROOM_CODE,
    TAMIS,
    Play,
    cell_at,
    closed,
    events_of,
    grid_from_text,
    last_vote_id_of,
    open_room,
    open_vote_of,
    opened,
    refusal_code,
    seen_at,
    settings_frame,
    v3,
    write,
)

PANELS = ("check-panel", "reveal-panel")
HELP_BUTTONS = (
    "check-letter",
    "check-word",
    "check-grid",
    "reveal-letter",
    "reveal-word",
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def expect_no_help_controls(page: Page) -> None:
    for test_id in (*PANELS, *HELP_BUTTONS):
        expect(page.get_by_test_id(test_id)).to_have_count(0)


def expect_help_controls(page: Page) -> None:
    open_aide(page)
    for test_id in (*PANELS, *HELP_BUTTONS):
        expect(page.get_by_test_id(test_id)).to_be_visible()


# ---- AC-4: in none mode, the check and reveal controls are hidden ----


def test_ac4_a_none_snapshot_shows_neither_panel_but_the_aide_menu_and_undo(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, help_mode=HelpMode.NONE)

    expect(page.get_by_test_id("aide-button")).to_be_visible()
    expect(page.get_by_test_id("aide-menu")).to_have_count(1)
    expect(page.get_by_test_id("undo-button")).to_be_visible()
    expect_no_help_controls(page)


def test_ac4_free_shows_both_panels_and_back_to_none_hides_them_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, help_mode=HelpMode.NONE)
    expect(page.get_by_test_id("undo-button")).to_be_visible()
    expect_no_help_controls(page)

    mock.send(settings_frame(6, HelpMode.FREE))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_help_controls(page)

    mock.send(settings_frame(7, HelpMode.NONE))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect_no_help_controls(page)


def test_ac4_a_settings_changed_to_vote_shows_both_panels(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, help_mode=HelpMode.NONE)
    expect(page.get_by_test_id("undo-button")).to_be_visible()
    expect_no_help_controls(page)

    mock.send(settings_frame(6, HelpMode.VOTE))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_help_controls(page)


def test_ac4_a_vote_snapshot_shows_both_panels(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, help_mode=HelpMode.VOTE)

    expect_help_controls(page)


def test_ac4_none_during_an_open_vote_hides_the_panels_and_keeps_the_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    vote = opened(5, 1, "p2", Check(target=GridTarget()), 3)
    mock = open_room(page, live_server, fx01_grid, vote=vote)
    banner = page.get_by_test_id("vote-banner")
    expect(banner).to_be_visible()
    question = banner.get_by_test_id("vote-question")
    question_text = question.text_content()

    mock.send(settings_frame(6, HelpMode.NONE))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_no_help_controls(page)
    expect(banner).to_be_visible()
    expect(question).to_have_text(question_text or "")


def none_room(grid: Grid) -> Play:
    """A FX-01 room with `p1` (host), `p2` and `p3`, in `none` mode (seq 4)."""
    play = Play(new_room(ROOM_CODE, grid, NOW))
    for number in (1, 2, 3):
        play.join(number)
    change = ChangeSettings(help_mode=HelpMode.NONE, reveal_budget=FIVE_AND_ONE)
    assert play.send("p1", change).reply == ()
    assert play.state.seq == 4
    return play


@pytest.mark.parametrize(
    "message",
    [
        Check(target=GridTarget()),
        Check(target=CellTarget(row=1, column=0)),
        Check(target=TAMIS),
        Reveal(target=CellTarget(row=1, column=0)),
        Reveal(target=MIME),
    ],
    ids=["check-grid", "check-letter", "check-word", "reveal-letter", "reveal-word"],
)
def test_ac4_server_in_none_mode_every_check_and_reveal_is_help_disabled(
    fx01_grid: Grid, message: ClientMessage
) -> None:
    play = none_room(fx01_grid)
    before = play.state

    outcome = play.send("p2", message, NOW + 1.0)

    assert refusal_code(outcome) is ErrorCode.HELP_DISABLED
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, "p2", NOW + 1.0)
    assert open_vote_of(outcome.state) is None


# ---- AC-5: in vote mode, a check of a letter or of a word needs no vote ----


def v3_with_two_letters(grid: Grid) -> Play:
    """`V3` where `p1` wrote `T` at (1, 0) and `X` at (1, 1): seq 6."""
    play = v3(grid)
    write(play, "p1", [(1, 0, "T"), (1, 1, "X")])
    assert play.state.seq == 6
    return play


def word_check_events(first_seq: int, player_id: str) -> list[object]:
    """Spec 023's events for a check of TAMIS holding `T` and `X`."""
    return [
        CheckResult(
            seq=first_seq,
            player_id=player_id,
            target=TAMIS,
            correct=(CellRef(row=1, column=0),),
            wrong=(CellRef(row=1, column=1),),
        ),
        CellLocked(seq=first_seq + 1, row=1, column=0, letter="T", revealed=False),
    ]


def letter_check_event(seq: int, player_id: str) -> CheckResult:
    """Spec 023's result for a check of (1, 1) holding `X`."""
    return CheckResult(
        seq=seq,
        player_id=player_id,
        target=CellTarget(row=1, column=1),
        correct=(),
        wrong=(CellRef(row=1, column=1),),
    )


def test_ac5_a_word_check_in_vote_mode_applies_at_once(fx01_grid: Grid) -> None:
    play = v3_with_two_letters(fx01_grid)

    outcome = play.send("p2", Check(target=TAMIS))

    assert events_of(outcome) == word_check_events(7, "p2")
    assert outcome.reply == ()
    assert open_vote_of(play.state) is None
    assert last_vote_id_of(play.state) == 0


def test_ac5_a_letter_check_in_vote_mode_applies_at_once(fx01_grid: Grid) -> None:
    play = v3_with_two_letters(fx01_grid)

    outcome = play.send("p2", Check(target=CellTarget(row=1, column=1)))

    assert events_of(outcome) == [letter_check_event(7, "p2")]
    assert outcome.reply == ()
    assert open_vote_of(play.state) is None
    assert last_vote_id_of(play.state) == 0


def test_ac5_during_a_vote_letter_and_word_checks_apply_and_the_vote_stays_open(
    fx01_grid: Grid,
) -> None:
    play = v3_with_two_letters(fx01_grid)
    request = Reveal(target=CellTarget(row=2, column=2))
    assert events_of(play.send("p1", request)) == [opened(7, 1, "p1", request, 3)]
    vote = open_vote_of(play.state)
    assert vote is not None

    word_check = play.send("p2", Check(target=TAMIS))

    assert events_of(word_check) == word_check_events(8, "p2")
    assert word_check.reply == ()
    assert open_vote_of(play.state) == vote

    letter_check = play.send("p3", Check(target=CellTarget(row=1, column=1)))

    assert events_of(letter_check) == [letter_check_event(10, "p3")]
    assert letter_check.reply == ()
    assert open_vote_of(play.state) == vote


def test_ac5_browser_during_a_vote_only_the_letter_and_word_checks_are_enabled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    cell_at(page, 1, 1).click()
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-word", "0,0,0")
    for test_id in HELP_BUTTONS:
        expect(page.get_by_test_id(test_id)).to_be_enabled()

    vote = opened(6, 1, "p2", Reveal(target=CellTarget(row=2, column=2)), 3)
    mock.send(vote.model_dump_json())

    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    expect(page.get_by_test_id("check-letter")).to_be_enabled()
    expect(page.get_by_test_id("check-word")).to_be_enabled()
    for test_id in ("check-grid", "reveal-letter", "reveal-word"):
        expect(page.get_by_test_id(test_id)).to_be_disabled()

    open_aide(page)
    page.get_by_test_id("check-letter").click()
    open_aide(page)
    page.get_by_test_id("check-word").click()

    expected_checks = [
        Check(target=CellTarget(row=1, column=1)),
        Check(target=WordTarget(row=0, column=0, clue_index=0)),
    ]
    mock.wait_for_frames(len(expected_checks) + 1)
    assert mock.checks() == expected_checks

    mock.send(closed(7, 1, VoteOutcome.REJECTED, 1, 3).model_dump_json())

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    for test_id in HELP_BUTTONS:
        expect(page.get_by_test_id(test_id)).to_be_enabled()
