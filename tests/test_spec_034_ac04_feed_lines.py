"""Tests of spec 034, AC-4: the feed lists the lines of the absence, oldest first.

Browser with the mocked socket and the mocked catch-up: the items, their
`data-seq`, `data-kind` and texts, a live line after them, unknown names, two
words of one letter and the feed's 100 items. The scroll checks are in
`test_spec_034_ac04_feed_scroll.py`, which runs in the serial pass. This file
also checks that the plain JSON the browser tests answer with is the JSON of the
`CatchUp` models the spec builds them from. The shared setup is in
`spec034_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellRef,
    CellTarget,
    CheckResult,
    ClueRef,
    RevealBudget,
    RevealResult,
    WordTarget,
)
from spec034_harness import (
    BOB,
    CY,
    SENT,
    VIDE,
    CatchUpRoute,
    MockRoom,
    catch_up_body,
    catch_up_json,
    check_line,
    expect_catch_up_applied,
    expect_seq,
    feed_item_locator,
    feed_items,
    grid_from_text,
    grid_line_frame,
    load_fr,
    open_mocked_room,
    record_with,
    reveal_line,
    word_completed_line,
)

FEED_LIMIT = 100


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def absence_lines_json() -> str:
    """AC-4's answer: a word by `p2`, a check by `p2`, a reveal by `p3` (`CY`)."""
    return catch_up_json(
        5,
        9,
        lines=[
            word_completed_line(7, BOB, VIDE),
            check_line(8, BOB),
            reveal_line(9, CY),
        ],
        names=[(CY, "CY")],
    )


def open_return(page: Page, base_url: str, grid: Grid, route: CatchUpRoute) -> MockRoom:
    """`seen_seq` 5 stored, a snapshot at 9 with `p1` and `p2`."""
    return open_mocked_room(page, base_url, grid, route, record=record_with(5), seq=9)


def feed_seqs(page: Page) -> list[str]:
    return [seq for _, seq, _ in feed_items(page)]


# ---- The JSON the browser tests answer with ----------------------------------------


def test_ac4_the_mocked_answers_are_the_json_of_catch_up_models() -> None:
    from nock.catch_up import CatchUp, PlayerName, WordCompleted

    expected = CatchUp(
        after_seq=5,
        until_seq=9,
        cells=(CellRef(row=1, column=0), CellRef(row=2, column=2)),
        lines=(
            WordCompleted(
                seq=7, player_id="p2", clue=ClueRef(row=2, column=0, clue_index=0)
            ),
            CheckResult(
                seq=8,
                player_id="p2",
                target=WordTarget(row=2, column=0, clue_index=0),
                correct=(),
                wrong=(),
            ),
            RevealResult(
                seq=9,
                player_id="p3",
                target=CellTarget(row=1, column=1),
                reveal_budget=RevealBudget(letters=4, words=1),
            ),
        ),
        names=(PlayerName(player_id="p3", nickname="CY"),),
    )
    body = catch_up_body(
        5,
        9,
        cells=[(1, 0), (2, 2)],
        lines=[
            word_completed_line(7, BOB, VIDE),
            check_line(8, BOB),
            reveal_line(9, CY),
        ],
        names=[(CY, "CY")],
    )

    assert body == expected.model_dump(mode="json")
    assert CatchUp.model_validate_json(json.dumps(body)) == expected


def test_ac4_fr_json_has_the_word_completed_text() -> None:
    assert load_fr()["feed.word_completed"] == "{name} a complété « {clue} »"


# ---- The items -------------------------------------------------------------------


def test_ac4_the_lines_become_feed_items_in_seq_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute(answer=absence_lines_json())
    open_return(page, live_server, fx01_grid, route)

    expect_catch_up_applied(page, "5-9")

    expect(feed_item_locator(page)).to_have_count(3)
    assert feed_items(page) == [
        ("word_completed", "7", "Bob a complété « Sans contenu »"),
        ("check", "8", "Bob a vérifié un mot"),
        ("reveal", "9", "Cy a révélé une lettre"),
    ]


def test_ac4_the_texts_are_built_from_fr_json(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    route = CatchUpRoute(answer=absence_lines_json())
    open_return(page, live_server, fx01_grid, route)

    expect_catch_up_applied(page, "5-9")

    expect(feed_item_locator(page)).to_have_count(3)
    texts = [text for _, _, text in feed_items(page)]
    assert texts == [
        fr["feed.word_completed"].format(name="Bob", clue="Sans contenu"),
        fr["feed.check.word"].format(name="Bob"),
        fr["feed.reveal.letter"].format(name="Cy"),
    ]


def test_ac4_a_live_line_after_the_catch_up_comes_after_its_lines(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute(answer=absence_lines_json())
    mock = open_return(page, live_server, fx01_grid, route)
    expect_catch_up_applied(page, "5-9")
    expect(feed_item_locator(page)).to_have_count(3)

    mock.send(grid_line_frame(10))

    expect(feed_item_locator(page)).to_have_count(4)
    assert feed_items(page)[3] == ("check", "10", "Bob a vérifié la grille")
    assert feed_seqs(page) == ["7", "8", "9", "10"]


def test_ac4_a_line_whose_player_has_no_name_reads_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # Edge case "Unknown names": `p4` is neither in the snapshot nor in `names`.
    route = CatchUpRoute(answer=catch_up_json(5, 9, lines=[check_line(8, "p4")]))
    open_return(page, live_server, fx01_grid, route)

    expect_catch_up_applied(page, "5-9")

    expect(feed_item_locator(page)).to_have_count(1)
    assert feed_items(page) == [("check", "8", "Quelqu'un a vérifié un mot")]


def test_ac4_one_letter_that_completes_two_words_gives_two_items_with_one_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    lines = [word_completed_line(7, BOB, SENT), word_completed_line(7, BOB, VIDE)]
    route = CatchUpRoute(answer=catch_up_json(5, 9, lines=lines))
    open_return(page, live_server, fx01_grid, route)

    expect_catch_up_applied(page, "5-9")

    expect(feed_item_locator(page)).to_have_count(2)
    assert feed_items(page) == [
        ("word_completed", "7", "Bob a complété « Flaire »"),
        ("word_completed", "7", "Bob a complété « Sans contenu »"),
    ]


def test_ac4_live_lines_that_came_first_follow_the_catch_up_lines(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    mock = open_return(page, live_server, fx01_grid, route)
    route.wait_for_requests(page, 1)
    for seq in range(10, 26):
        mock.send(grid_line_frame(seq))
    expect_seq(page, 25)
    expect(feed_item_locator(page)).to_have_count(16)

    route.answer_json(0, absence_lines_json())

    expect_catch_up_applied(page, "5-9")
    expect(feed_item_locator(page)).to_have_count(19)
    expected = ["7", "8", "9"]
    for seq in range(10, 26):
        expected.append(str(seq))
    assert feed_seqs(page) == expected


def test_ac4_live_lines_push_out_the_oldest_catch_up_lines_past_100_items(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # Edge case "Many lines": the feed keeps its newest 100 items.
    route = CatchUpRoute()
    mock = open_return(page, live_server, fx01_grid, route)
    route.wait_for_requests(page, 1)
    for seq in range(10, 109):
        mock.send(grid_line_frame(seq))
    expect_seq(page, 108)
    expect(feed_item_locator(page)).to_have_count(99)

    route.answer_json(0, absence_lines_json())

    expect_catch_up_applied(page, "5-9")
    expected = ["9"]
    for seq in range(10, 109):
        expected.append(str(seq))
    expect(feed_item_locator(page).first).to_have_attribute("data-seq", "9")
    assert len(expected) == FEED_LIMIT
    assert feed_seqs(page) == expected
