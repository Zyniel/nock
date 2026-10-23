"""Tests of spec 025, AC-7: the vote banner.

It shows the question to everyone, and the buttons to those who can still vote.
The page is driven with a mocked socket: a FX-01 snapshot in vote mode with `p1`
(`you`, `Ana`), `p2` (`Bob`) and `p3` (`Cy`), and vote frames built with
`VoteOpened` and `VoteClosed`. The shared setup is in `spec025_harness`.

Refined by spec 047 (the design's room overlays): `vote.cast` reads « Vote
enregistré. En attente des autres joueurs… »; when the vote closes the banner is
gone within 300 ms and never shows `vote-result` (the result time of 2,500 to
4,500 ms is gone), while `vote-announcement` reads the result; a new vote after a
closed one shows a new banner with its own question and buttons.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    Check,
    GridSolved,
    GridTarget,
    Reveal,
    Vote,
    VoteOutcome,
    WordTarget,
)
from spec025_harness import (
    MockRoomSocket,
    closed,
    fr_text,
    grid_from_text,
    load_fr,
    open_room,
    opened,
    player_view,
    settle,
    snapshot_frame,
)

VISUALLY_HIDDEN = re.compile(r"(^|\s)visually-hidden(\s|$)")
BANNER_GONE_MS = 300  # spec 047: "within 300 ms" of the `vote_closed`
WORD_REVEAL = Reveal(target=WordTarget(row=0, column=2, clue_index=0))
NEW_KEYS = {
    "vote.question.check_grid": "{name} propose de vérifier la grille.",
    "vote.question.reveal_letter": "{name} propose de révéler une lettre.",
    "vote.question.reveal_word": "{name} propose de révéler un mot.",
    "vote.yes": "Oui",
    "vote.no": "Non",
    "vote.waiting": "En attente des autres joueurs…",
    # Spec 047 (the human's decision P6) changed this value.
    "vote.cast": "Vote enregistré. En attente des autres joueurs…",
    "vote.result.passed": "Vote accepté.",
    "vote.result.rejected": "Vote refusé.",
    "vote.result.timed_out": "Temps écoulé, vote annulé.",
}


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def open_with_bobs_word_vote(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """The snapshot (seq 5), then `vote_opened` seq 6: vote 1, by `p2`, MIME."""
    mock = open_room(page, base_url, grid)
    mock.send(opened(6, 1, "p2", WORD_REVEAL, 3).model_dump_json())
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    return mock


def labelled_by(page: Page, test_id: str) -> None:
    """The banner's `aria-labelledby` names the element with `test_id`."""
    banner = page.get_by_test_id("vote-banner")
    target = banner.get_by_test_id(test_id)
    expect(target).to_have_count(1)
    target_id = target.get_attribute("id")
    assert target_id, f"{test_id} has no id"
    expect(banner).to_have_attribute("aria-labelledby", target_id)


def expect_no_buttons(page: Page) -> None:
    expect(page.get_by_test_id("vote-yes")).to_have_count(0)
    expect(page.get_by_test_id("vote-no")).to_have_count(0)


# ---- AC-7: the new texts ----


def test_ac7_the_new_fr_json_keys_have_the_texts_of_the_spec() -> None:
    texts = load_fr()

    for key, value in NEW_KEYS.items():
        assert texts.get(key) == value, key


# ---- AC-7: a vote opened by another player ----


def test_ac7_a_vote_by_bob_shows_the_question_the_announcement_and_both_buttons(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_bobs_word_vote(page, live_server, fx01_grid)

    question = fr_text("vote.question.reveal_word", name="Bob")
    assert question == "Bob propose de révéler un mot."
    banner = page.get_by_test_id("vote-banner")
    expect(banner).to_be_visible()
    expect(banner).to_have_attribute("role", "group")
    expect(banner.get_by_test_id("vote-question")).to_have_text(question)
    labelled_by(page, "vote-question")
    expect(page.get_by_test_id("vote-announcement")).to_have_text(question)
    expect(banner.get_by_test_id("vote-yes")).to_have_text(fr_text("vote.yes"))
    expect(banner.get_by_test_id("vote-no")).to_have_text(fr_text("vote.no"))
    expect(page.get_by_test_id("vote-status")).to_have_count(0)


def test_ac7_clicking_yes_sends_one_ballot_and_the_buttons_give_way_to_vote_cast(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_bobs_word_vote(page, live_server, fx01_grid)

    page.get_by_test_id("vote-yes").click()

    expect(page.get_by_test_id("vote-status")).to_have_text(fr_text("vote.cast"))
    expect_no_buttons(page)
    settle(page)
    assert mock.votes() == [Vote(vote_id=1, yes=True)]
    assert mock.raw_votes() == [{"type": "vote", "vote_id": 1, "yes": True}]


def test_ac7_a_closed_vote_is_announced_and_the_banner_goes_within_300_ms(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_bobs_word_vote(page, live_server, fx01_grid)
    page.get_by_test_id("vote-yes").click()
    expect(page.get_by_test_id("vote-status")).to_have_text(fr_text("vote.cast"))
    banner = page.get_by_test_id("vote-banner")

    mock.send(closed(7, 1, VoteOutcome.PASSED, 2, 3).model_dump_json())

    # Spec 047: the banner leaves at once and never shows a result.
    expect(banner).to_have_count(0, timeout=BANNER_GONE_MS)
    result = fr_text("vote.result.passed")
    expect(page.get_by_test_id("vote-announcement")).to_have_text(result)
    expect(page.get_by_test_id("vote-result")).to_have_count(0)


def test_ac7_the_announcement_region_is_on_the_page_once_it_has_a_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    announcement = page.get_by_test_id("vote-announcement")
    expect(announcement).to_have_count(1)
    expect(announcement).to_have_class(VISUALLY_HIDDEN)
    expect(announcement).to_have_attribute("role", "status")
    expect(announcement).to_have_attribute("aria-live", "polite")
    expect(announcement).to_have_attribute("aria-atomic", "true")
    expect(page.get_by_test_id("vote-banner")).to_be_hidden()


@pytest.mark.parametrize(
    ("request_message", "kind"),
    [
        (Check(target=GridTarget()), "check_grid"),
        (Reveal(target=CellTarget(row=1, column=0)), "reveal_letter"),
        (WORD_REVEAL, "reveal_word"),
    ],
    ids=["check-grid", "reveal-letter", "reveal-word"],
)
def test_ac7_the_question_names_the_requester_and_the_kind_of_request(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    request_message: Check | Reveal,
    kind: str,
) -> None:
    mock = open_room(page, live_server, fx01_grid)

    mock.send(opened(6, 1, "p3", request_message, 3).model_dump_json())

    question = fr_text(f"vote.question.{kind}", name="Cy")
    expect(page.get_by_test_id("vote-question")).to_have_text(question)
    expect(page.get_by_test_id("vote-announcement")).to_have_text(question)


def test_ac7_an_unknown_requester_is_named_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)

    mock.send(opened(6, 1, "p9", Check(target=GridTarget()), 3).model_dump_json())

    question = fr_text("vote.question.check_grid", name=fr_text("feed.someone"))
    expect(page.get_by_test_id("vote-question")).to_have_text(question)


def test_ac7_the_requesters_nickname_is_inserted_as_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    nickname = "<b>Bo</b>"
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", nickname, 1),
        player_view("p3", "Cy", 2),
    ]
    mock = open_room(page, live_server, fx01_grid, players=players)

    mock.send(opened(6, 1, "p2", WORD_REVEAL, 3).model_dump_json())

    question = page.get_by_test_id("vote-question")
    # Spec 040's displayNickname writes `<b>Bo</b>` as `<b>bo</b>`.
    shown_name = "<b>bo</b>"
    expect(question).to_have_text(fr_text("vote.question.reveal_word", name=shown_name))
    expect(page.get_by_test_id("vote-banner").locator("b")).to_have_count(0)


def test_ac7_a_vote_on_another_kind_of_request_shows_no_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    letter_check = Check(target=CellTarget(row=1, column=1))

    mock.send(opened(6, 1, "p2", letter_check, 3).model_dump_json())

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    settle(page)
    expect(page.get_by_test_id("vote-banner")).to_be_hidden()


# ---- AC-7: a first snapshot holding an open vote ----


def test_ac7_a_snapshot_with_my_own_vote_shows_waiting_and_no_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    vote = opened(5, 3, "p1", Check(target=GridTarget()), 3)

    open_room(page, live_server, fx01_grid, vote=vote)

    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    expect(page.get_by_test_id("vote-status")).to_have_text(fr_text("vote.waiting"))
    expect_no_buttons(page)


def test_ac7_a_snapshot_with_a_vote_by_cy_shows_both_buttons_and_no_sends_false(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    vote = opened(5, 4, "p3", Check(target=GridTarget()), 3)
    mock = open_room(page, live_server, fx01_grid, vote=vote)
    expect(page.get_by_test_id("vote-yes")).to_be_visible()

    page.get_by_test_id("vote-no").click()

    expect(page.get_by_test_id("vote-status")).to_have_text(fr_text("vote.cast"))
    settle(page)
    assert mock.votes() == [Vote(vote_id=4, yes=False)]


def test_ac7_a_page_that_voted_still_shows_vote_cast_after_a_reconnection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_bobs_word_vote(page, live_server, fx01_grid)
    page.get_by_test_id("vote-yes").click()
    expect(page.get_by_test_id("vote-status")).to_have_text(fr_text("vote.cast"))

    mock.close(1011)
    mock.wait_for_join_on_socket(1)
    vote = opened(6, 1, "p2", WORD_REVEAL, 3)
    mock.send(snapshot_frame(fx01_grid, seq=6, vote=vote))

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")
    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    expect(page.get_by_test_id("vote-status")).to_have_text(fr_text("vote.cast"))
    expect_no_buttons(page)
    assert mock.votes() == [Vote(vote_id=1, yes=True)]


def test_ac7_the_buttons_are_disabled_while_reconnecting_and_enabled_once_joined(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    vote = opened(5, 4, "p3", Check(target=GridTarget()), 3)
    mock = open_room(page, live_server, fx01_grid, vote=vote)
    room = page.get_by_test_id("room-page")
    buttons = [page.get_by_test_id("vote-yes"), page.get_by_test_id("vote-no")]
    for button in buttons:
        expect(button).to_be_enabled()

    mock.close(1011)

    expect(room).to_have_attribute("data-status", "reconnecting")
    for button in buttons:
        expect(button).to_be_visible()
        expect(button).to_be_disabled()
    # The new socket is open and its join sent, but not answered yet.
    mock.wait_for_join_on_socket(1)
    expect(room).to_have_attribute("data-status", "reconnecting")
    for button in buttons:
        expect(button).to_be_visible()
        expect(button).to_be_disabled()

    mock.send(snapshot_frame(fx01_grid, seq=5, vote=vote))

    expect(room).to_have_attribute("data-status", "joined")
    for button in buttons:
        expect(button).to_be_visible()
        expect(button).to_be_enabled()
    expect(page.get_by_test_id("vote-status")).to_have_count(0)
    assert mock.votes() == []


def test_ac7_a_new_vote_after_a_closed_one_shows_its_own_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    """Spec 047: there is no result time any more; the closed vote's banner is
    gone, and the next vote shows a new banner with its question and buttons."""
    mock = open_with_bobs_word_vote(page, live_server, fx01_grid)
    page.get_by_test_id("vote-yes").click()
    mock.send(closed(7, 1, VoteOutcome.REJECTED, 1, 3).model_dump_json())
    expect(page.get_by_test_id("vote-banner")).to_have_count(0, timeout=BANNER_GONE_MS)

    mock.send(opened(8, 2, "p3", Check(target=GridTarget()), 3).model_dump_json())

    question = fr_text("vote.question.check_grid", name="Cy")
    expect(page.get_by_test_id("vote-question")).to_have_text(question)
    expect(page.get_by_test_id("vote-result")).to_have_count(0)
    expect(page.get_by_test_id("vote-yes")).to_be_visible()
    expect(page.get_by_test_id("vote-no")).to_be_visible()
    expect(page.get_by_test_id("vote-announcement")).to_have_text(question)


# ---- AC-7: a solved grid hides the banner ----


def test_ac7_a_grid_solved_while_a_vote_is_open_hides_the_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_bobs_word_vote(page, live_server, fx01_grid)
    expect(page.get_by_test_id("vote-banner")).to_be_visible()

    mock.send(GridSolved(seq=7, elapsed_ms=1000).model_dump_json())

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "true")
    expect(page.get_by_test_id("vote-banner")).to_be_hidden()


def test_ac7_a_solved_snapshot_with_an_open_vote_shows_no_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    vote = opened(5, 1, "p2", WORD_REVEAL, 3)

    open_room(page, live_server, fx01_grid, vote=vote, solved=True)

    expect(page.get_by_test_id("vote-announcement")).to_have_count(1)
    settle(page)
    expect(page.get_by_test_id("vote-banner")).to_be_hidden()
