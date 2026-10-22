"""Tests of spec 043, AC-8 and AC-9: the Aide menu.

AC-8: `aide-menu` holds the pencil confirm (while a pencil letter is selected),
then « Vérifier » and « Révéler » with their items and details, or one muted line
in help mode `none`. AC-9: an enabled item sends its message once, closes the menu
and puts the focus back on `aide-button`; a disabled one does nothing.

Also tested, from "Edge cases and errors": the pencil confirm appearing while the
menu is open is added at the top and the focus stays where it was (AC-8); an item
disabled by a `vote_opened` while the menu is open leaves it open (AC-9).

Choices where the spec leaves room:

- An item's text is its visible label (the text outside `aria-hidden` elements, so
  without its detail); its colour and weight are those of the element holding it.
- A click on a disabled item is a click with Playwright's `force`, which skips the
  wait for an enabled element; the browser then gives the button no click.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    Check,
    ConfirmPencil,
    GridTarget,
    HelpMode,
    Reveal,
    VoteOpened,
    WordTarget,
    parse_client_message,
)
from room_panels import open_aide
from spec042_harness import colour_of, contrast_ratio
from spec043_harness import (
    MUTED,
    WHITE,
    RoomMock,
    any_pictogram,
    colour_matches,
    expect_closed,
    expect_selected,
    expect_word,
    focused_test_id,
    fr_format,
    fr_value,
    frames_sent_after,
    fx01_view,
    label_of,
    letter_frame,
    open_room,
    players_up_to,
    press_cell,
    reveal_frame,
    select_mime,
    send_and_wait,
    settings_frame,
    snapshot_frame,
)

# The items of the menu with nothing selected, in document order.
ORDERED_NAMES = [
    "check-heading",
    "check-letter",
    "check-word",
    "check-grid",
    "separator",
    "reveal-heading",
    "reveal-letter",
    "reveal-word",
]
ITEM_TEXT_KEYS = {
    "check-letter": "check.letter",
    "check-word": "check.word",
    "check-grid": "check.grid",
    "reveal-letter": "reveal.letter",
    "reveal-word": "reveal.word",
}

ORDER_SCRIPT = r"""
(menu, names) => {
  const found = [];
  for (const element of menu.querySelectorAll('*')) {
    const testId = element.getAttribute('data-testid');
    if (names.includes(testId)) {
      found.push(testId);
    } else if (element.classList.contains('nock-menu-separator')) {
      found.push('separator');
    }
  }
  return found;
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


def ac8_frame(grid: Grid, *, help_mode: HelpMode = HelpMode.FREE) -> str:
    """AC-8's snapshot: help mode `free`, 5 letters and 1 word, a pencil `T` by
    `p2` in (1, 0)."""
    changes: list[tuple[int, int, dict[str, object]]] = [
        (1, 0, {"letter": "T", "pencil": True, "author": "p2"})
    ]
    return snapshot_frame(
        fx01_view(grid, changes), players_up_to(3), help_mode=help_mode
    )


def open_ac8(page: Page, base_url: str, grid: Grid) -> RoomMock:
    return open_room(page, base_url, ac8_frame(grid))


def menu_order(page: Page) -> list[str]:
    menu = page.get_by_test_id("aide-menu")
    names = [name for name in ORDERED_NAMES if name != "separator"]
    names.append("confirm-pencil")
    found = menu.evaluate(ORDER_SCRIPT, names)
    assert isinstance(found, list), found
    return found


# ---- AC-8: what the menu holds -------------------------------------------------------


def test_ac8_the_aide_menu_is_a_group_named_aide(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac8(page, live_server, fx01_grid)
    open_aide(page)

    menu = page.get_by_test_id("aide-menu")
    expect(menu).to_have_attribute("role", "group")
    expect(menu).to_have_attribute("aria-label", fr_value("topbar.aide"))
    expect(menu).to_have_attribute("id", "aide-menu")


def test_ac8_with_nothing_selected_it_holds_check_then_reveal_in_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac8(page, live_server, fx01_grid)
    open_aide(page)

    order = menu_order(page)

    expect(page.get_by_test_id("confirm-pencil")).to_have_count(0)
    assert order == ORDERED_NAMES


def test_ac8_the_headings_and_items_have_their_visible_texts_and_no_aria_label(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac8(page, live_server, fx01_grid)
    open_aide(page)

    expect(page.get_by_test_id("check-heading")).to_have_text(fr_value("check.label"))
    expect(page.get_by_test_id("reveal-heading")).to_have_text(fr_value("reveal.label"))
    for test_id, key in ITEM_TEXT_KEYS.items():
        item = page.get_by_test_id(test_id)
        label = label_of(item)
        assert label is not None, test_id
        if test_id.startswith("check"):
            assert label["text"] == fr_value(key), (test_id, label["text"])
        else:
            assert str(label["text"]).startswith(fr_value(key)), (test_id, label)
        assert item.get_attribute("aria-label") is None, test_id


@pytest.mark.parametrize(
    ("panel", "heading"),
    [("check-panel", "check-heading"), ("reveal-panel", "reveal-heading")],
)
def test_ac8_each_panel_is_a_group_labelled_by_its_heading(
    page: Page, live_server: str, fx01_grid: Grid, panel: str, heading: str
) -> None:
    open_ac8(page, live_server, fx01_grid)

    heading_id = page.get_by_test_id(heading).get_attribute("id")

    assert heading_id is not None
    assert heading_id != ""
    expect(page.get_by_test_id(panel)).to_have_attribute("role", "group")
    expect(page.get_by_test_id(panel)).to_have_attribute("aria-labelledby", heading_id)


def test_ac8_the_reveal_details_say_how_many_letters_and_words_are_left(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac8(page, live_server, fx01_grid)

    expect(page.get_by_test_id("reveal-letter-detail")).to_have_text(
        fr_format("reveal.letters_left", count=5)
    )
    expect(page.get_by_test_id("reveal-word-detail")).to_have_text(
        fr_value("reveal.words_left_one")
    )


def test_ac8_a_selected_pencil_letter_puts_the_confirm_item_first(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac8(page, live_server, fx01_grid)
    press_cell(page, 1, 0)
    open_aide(page)
    confirm = page.get_by_test_id("confirm-pencil")

    first_child = page.get_by_test_id("aide-menu").evaluate(
        "menu => menu.firstElementChild.getAttribute('data-testid')"
    )
    next_is_separator = confirm.evaluate(
        "item => item.nextElementSibling !== null"
        " && item.nextElementSibling.classList.contains('nock-menu-separator')"
    )
    label = label_of(confirm)

    assert first_child == "confirm-pencil"
    assert next_is_separator is True
    assert label is not None
    assert label["text"] == fr_value("pencil.confirm")
    assert label["fontWeight"] == "600"
    assert any_pictogram(confirm, "\N{LOWER RIGHT PENCIL}")


def test_ac8_the_letter_detail_reads_one_left_after_a_reveal(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac8(page, live_server, fx01_grid)

    send_and_wait(page, mock, reveal_frame(6, "p2", CellTarget(row=2, column=2), 1, 1))

    expect(page.get_by_test_id("reveal-letter-detail")).to_have_text(
        fr_value("reveal.letters_left_one")
    )


def test_ac8_with_nothing_left_the_details_say_so_and_the_items_are_muted(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac8(page, live_server, fx01_grid)
    press_cell(page, 2, 2)

    send_and_wait(page, mock, reveal_frame(6, "p2", CellTarget(row=2, column=2), 0, 0))
    open_aide(page)

    expect(page.get_by_test_id("reveal-letter-detail")).to_have_text(
        fr_value("reveal.letter_none")
    )
    expect(page.get_by_test_id("reveal-word-detail")).to_have_text(
        fr_value("reveal.word_none")
    )
    for test_id in ("reveal-letter", "reveal-word"):
        item = page.get_by_test_id(test_id)
        expect(item).to_be_disabled()
        label = label_of(item)
        assert label is not None, test_id
        assert colour_matches(label["colour"], MUTED), (test_id, label)
        detail = colour_of(page.get_by_test_id(f"{test_id}-detail"), "color")
        assert colour_matches(detail, MUTED), (test_id, detail)
        assert contrast_ratio(label["colour"], WHITE) >= 4.5, test_id


def test_ac8_with_help_mode_none_only_the_muted_line_is_left(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac8(page, live_server, fx01_grid)
    send_and_wait(page, mock, settings_frame(6, help_mode=HelpMode.NONE))
    press_cell(page, 2, 1)

    open_aide(page)

    menu = page.get_by_test_id("aide-menu")
    expect(menu.get_by_test_id("check-panel")).to_have_count(0)
    expect(menu.get_by_test_id("reveal-panel")).to_have_count(0)
    expect(menu.get_by_test_id("aide-empty")).to_have_count(1)
    expect(menu.get_by_test_id("aide-empty")).to_have_text(fr_value("aide.empty"))


def test_ac8_a_pencil_letter_coming_while_the_menu_is_open_is_added_at_the_top(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac8(page, live_server, fx01_grid)
    press_cell(page, 1, 1)
    open_aide(page)
    focused_before = focused_test_id(page)

    send_and_wait(page, mock, letter_frame(6, 1, 1, "A", "p2", pencil=True))

    expect(page.get_by_test_id("confirm-pencil")).to_have_count(1)
    assert menu_order(page)[0] == "confirm-pencil"
    assert focused_test_id(page) == focused_before


# ---- AC-9: an item sends, closes and gives the focus back ----------------------------

ITEM_MESSAGES = {
    "check-word": Check(target=WordTarget(row=0, column=2, clue_index=0)),
    "check-letter": Check(target=CellTarget(row=2, column=2)),
    "check-grid": Check(target=GridTarget()),
    "reveal-letter": Reveal(target=CellTarget(row=2, column=2)),
    "reveal-word": Reveal(target=WordTarget(row=0, column=2, clue_index=0)),
}


@pytest.mark.parametrize("test_id", list(ITEM_MESSAGES))
def test_ac9_an_item_sends_once_closes_the_menu_and_refocuses_aide_button(
    page: Page, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    mock = open_ac8(page, live_server, fx01_grid)
    select_mime(page)
    open_aide(page)

    frames = frames_sent_after(page, mock, page.get_by_test_id(test_id).click)

    parsed = [parse_client_message(frame) for frame in frames]
    assert parsed == [ITEM_MESSAGES[test_id]]
    expect_closed(page.get_by_test_id("aide-menu"))
    assert focused_test_id(page) == "aide-button"
    expect_selected(page, 2, 2)
    expect_word(page, "0,2,0")


def test_ac9_confirm_pencil_sends_its_message_and_keeps_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac8(page, live_server, fx01_grid)
    press_cell(page, 1, 0)
    open_aide(page)

    frames = frames_sent_after(page, mock, page.get_by_test_id("confirm-pencil").click)

    parsed = [parse_client_message(frame) for frame in frames]
    assert parsed == [ConfirmPencil(row=1, column=0, base_seq=5)]
    expect_closed(page.get_by_test_id("aide-menu"))
    expect_selected(page, 1, 0)


def test_ac9_a_disabled_item_sends_nothing_and_leaves_the_menu_open(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac8(page, live_server, fx01_grid)
    open_aide(page)
    item = page.get_by_test_id("check-letter")
    expect(item).to_be_disabled()

    frames = frames_sent_after(page, mock, lambda: item.click(force=True))

    assert frames == []
    expect(page.get_by_test_id("aide-menu")).to_be_visible()


def test_ac9_items_disabled_by_a_vote_while_the_menu_is_open_leave_it_open(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, ac8_frame(fx01_grid, help_mode=HelpMode.VOTE))
    select_mime(page)
    open_aide(page)
    expect(page.get_by_test_id("check-grid")).to_be_enabled()

    vote = VoteOpened(
        seq=6,
        vote_id=1,
        player_id="p2",
        request=Check(target=GridTarget()),
        timeout_seconds=60,
        eligible_voters=3,
    )
    send_and_wait(page, mock, vote.model_dump_json())

    expect(page.get_by_test_id("check-grid")).to_be_disabled()
    expect(page.get_by_test_id("reveal-letter")).to_be_disabled()
    expect(page.get_by_test_id("reveal-word")).to_be_disabled()
    expect(page.get_by_test_id("aide-menu")).to_be_visible()
