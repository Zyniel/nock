"""Tests of spec 028, AC-10: the recap dialog and the share page are accessible and
fit every window (page with a mocked socket; the share page on the live server).

The room page is spec 027's toolbar setup (spec 013 AC-6's FX-01 snapshot, `you`
host among 8 players, 100 feed items, (3, 1) tapped) but solved, with the recap
route answering the recap of AC-2 plus a `share_path`. Spec 027's harness holds the
toolbar readings; the button lists below add `recap-open`.

Readings the spec leaves open:

- On a solved page the three check buttons and `undo-button` are disabled (spec
  026 AC-5), so they cannot take the keyboard focus. The keyboard test therefore
  walks to `recap-open` only, and checks its box, its outline and its clipping with
  spec 024 AC-8's readings; the "edge fade is not visible" rule of those readings
  is left out, since `recap-open` is not the last button of the toolbar.
- "Spec 024 AC-8's toolbar checks" for the other buttons (order, one row, hit at the
  centre, pointer focus) run on the buttons of spec 027's list plus `recap-open`.
- The share page of the scans is the stored room's page (`PLAY_R`, loaded from a
  `RoomStore`), with its API route answered by `page.route`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec024_harness import (
    LANGUAGE_SCAN_SCRIPT,
    cell_at,
    expect_seq,
    grid_from_text,
    language_data,
    load_fr,
    open_context_page,
    outline_problems,
    player_view,
)
from spec027_harness import open_timer_room
from spec027_toolbar_harness import (
    CONTEXTS,
    FIRST_THREE,
    FOCUS_IN_TOOLBAR_SCRIPT,
    FOCUS_SHARE_LINK_SCRIPT,
    FOCUSED_TEST_ID_SCRIPT,
    HIT_AT_CENTRE_SCRIPT,
    MAX_TABS,
    SCROLL_INTO_VIEW_SCRIPT,
    SCROLL_TO_START_SCRIPT,
    SEVEN_BUTTONS,
    SIX_BUTTONS,
    SMALL_WINDOWS,
    TEN_HOURS_MS,
    TOOLBAR_SCRIPT,
    WINDOW_SIZES,
    check_frame,
    eight_players,
    keyboard_focus_problems,
    pairs_that_do_not_overlap,
    press_partly_hidden_button,
    size_ids,
    spec013_layout_problems,
)
from spec028_harness import (
    recap_body,
    recap_player,
    serve_recap,
)
from spec035_harness import (
    SETTLE_MS,
    WAIT_TIMEOUT_MS,
    Walker,
    contrast_offenders,
    unknown_texts,
)

SHARE_PATH = "/recap/tok_ABCDEFGHIJKLMNOP"
EIGHT_BUTTONS = [*SEVEN_BUTTONS, "recap-open"]
FEED_ITEMS = 100
EPSILON = 1.0
SCAN_SIZES = [(1280, 720), (360, 740)]
HOSTILE_NAMES = ["<b>Eve</b>", "<img src=x>"]
FR_KEYS = {
    "recap.open": "Voir le bilan",
    "recap.heading": "Bilan de la partie",
    "recap.loading": "Chargement du bilan…",
    "recap.error": "Le bilan n'est pas disponible.",
    "recap.time": "Temps : {time}",
    "recap.checks": "Vérifications : {count}",
    "recap.reveals": "Révélations : {letters} lettres et {words} mots",
    "recap.players_heading": "Qui a fait quoi",
    "recap.player_letters": "{count} lettres",
    "recap.player_words": "{count} mots complétés",
    "recap.revealed_letters": "Lettres révélées : {count}",
    "recap.share_label": "Lien à partager",
    "recap.close": "Fermer",
    "share.heading": "Grille terminée",
    "share.team": "Équipe : {names}",
    "share.home": "Voir les grilles",
    "share.error": "Ce bilan n'est pas disponible.",
}


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def open_solved_toolbar_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
    touch: bool,
) -> tuple[Page, Callable[[], None]]:
    """Spec 027's toolbar room, solved, with the recap route; page and closer."""
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        serve_recap(page, recap_body(share_path=SHARE_PATH))
        mock = open_timer_room(
            page,
            live_server,
            grid,
            elapsed_ms=TEN_HOURS_MS,
            running=False,
            solved=True,
            players=eight_players(),
        )
        expect(page.get_by_test_id("recap-open")).to_be_visible()
        last_seq = 5 + FEED_ITEMS
        for seq in range(6, last_seq + 1):
            mock.send(check_frame(seq))
        expect_seq(page, last_seq)
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=WAIT_TIMEOUT_MS)
        else:
            cell.click(timeout=WAIT_TIMEOUT_MS)
        expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")
    except BaseException:
        close()
        raise
    return page, close


def open_dialog_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
    touch: bool,
    players: list[dict[str, Any]] | None = None,
) -> tuple[Page, Callable[[], None]]:
    """The mocked solved room at a window size with the recap dialog open."""
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        body = recap_body(players=players, share_path=SHARE_PATH)
        serve_recap(page, body)
        open_timer_room(
            page, live_server, grid, elapsed_ms=754_000, running=False, solved=True
        )
        page.get_by_test_id("recap-open").click()
        expect(page.get_by_test_id("recap-close")).to_be_visible()
    except BaseException:
        close()
        raise
    return page, close


# ---- fr.json ----


def test_ac10_fr_json_has_the_recap_and_share_keys() -> None:
    fr = load_fr()

    found = {key: fr.get(key) for key in FR_KEYS}

    assert found == FR_KEYS


# ---- The dialog fits the window and every control can be reached ----

DIALOG_BOX_SCRIPT = """
() => {
  const dialog = document.querySelector('[data-testid="recap"]');
  const box = dialog.getBoundingClientRect();
  return {
    box: [box.left, box.top, box.right, box.bottom],
    window: [innerWidth, innerHeight],
    scrollable: dialog.scrollHeight > dialog.clientHeight,
    overflowY: getComputedStyle(dialog).overflowY,
  };
}
"""
IN_DIALOG_SCRIPT = """
() => {
  const dialog = document.querySelector('[data-testid="recap"]');
  const active = document.activeElement;
  return {
    inside: dialog.contains(active),
    testId: active && active.getAttribute('data-testid'),
  };
}
"""


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac10_the_open_dialog_lies_inside_the_window(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    page, close = open_dialog_room(
        browser,
        browser_name,
        live_server,
        fx01_grid,
        width,
        height,
        context_kind == "touch",
    )
    try:
        reading = page.evaluate(DIALOG_BOX_SCRIPT)
    finally:
        close()

    left, top, right, bottom = reading["box"]
    window_width, window_height = reading["window"]
    assert left >= -EPSILON, reading
    assert top >= -EPSILON, reading
    assert right <= window_width + EPSILON, reading
    assert bottom <= window_height + EPSILON, reading


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac10_close_copy_and_the_share_link_take_the_focus_with_tab(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    page, close = open_dialog_room(
        browser,
        browser_name,
        live_server,
        fx01_grid,
        width,
        height,
        context_kind == "touch",
    )
    wanted = {"recap-close", "recap-copy", "recap-share-link"}
    reached: set[str] = set()
    outside: list[object] = []
    try:
        for _ in range(MAX_TABS):
            if wanted <= reached:
                break
            page.keyboard.press("Tab")
            reading = page.evaluate(IN_DIALOG_SCRIPT)
            if reading["inside"] is not True:
                outside.append(reading["testId"])
            if reading["testId"] in wanted:
                reached.add(reading["testId"])
    finally:
        close()

    assert reached == wanted
    assert outside == []


# ---- The solved page: spec 013 AC-6 and spec 024 AC-8 with recap-open ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac10_spec_013_layout_holds_on_the_solved_page(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_solved_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        expect(page.get_by_test_id("recap-open")).to_be_visible()
        problems = spec013_layout_problems(page, touch)
    finally:
        close()

    assert problems == []


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac10_the_toolbar_holds_recap_open_in_order_on_one_row(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    small = (width, height) in SMALL_WINDOWS
    page, close = open_solved_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        reading = page.evaluate(
            TOOLBAR_SCRIPT, {"sevenIds": EIGHT_BUTTONS, "sixIds": SIX_BUTTONS}
        )
        ids = page.evaluate("""() => Array.from(
              document.querySelectorAll('[data-testid="room-toolbar"] [data-testid]')
            ).map(element => element.getAttribute('data-testid'))""")
    finally:
        close()

    assert reading["counts"] == dict.fromkeys(EIGHT_BUTTONS, 1), reading
    assert reading["outside"] == [], reading
    assert reading["outOfOrder"] == [], reading
    assert reading["firstThree"] == FIRST_THREE, reading
    assert ids.index("recap-open") == ids.index("chat-toggle") + 1, ids
    if small:
        assert pairs_that_do_not_overlap(reading["ranges"]) == [], reading


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(
    ("width", "height"), SMALL_WINDOWS, ids=size_ids(SMALL_WINDOWS)
)
def test_ac10_on_a_small_window_recap_open_shows_before_any_sideways_scroll(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    page, close = open_solved_toolbar_room(
        browser,
        browser_name,
        live_server,
        fx01_grid,
        width,
        height,
        context_kind == "touch",
    )
    try:
        page.evaluate(SCROLL_TO_START_SCRIPT)
        page.wait_for_timeout(SETTLE_MS)
        reading = page.evaluate("""() => {
              const toolbar = document.querySelector('[data-testid="room-toolbar"]');
              const box = document.querySelector('[data-testid="recap-open"]')
                .getBoundingClientRect();
              const toolbarBox = toolbar.getBoundingClientRect();
              return {
                left: box.left,
                right: box.right,
                areaLeft: toolbarBox.left + toolbar.clientLeft,
                areaRight: toolbarBox.left + toolbar.clientLeft + toolbar.clientWidth,
                scrollLeft: toolbar.scrollLeft,
              };
            }""")
    finally:
        close()

    assert reading["scrollLeft"] == 0, reading
    assert reading["left"] >= reading["areaLeft"] - EPSILON, reading
    assert reading["left"] < reading["areaRight"], reading


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac10_recap_open_is_hit_at_its_centre_once_scrolled_into_view(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    page, close = open_solved_toolbar_room(
        browser,
        browser_name,
        live_server,
        fx01_grid,
        width,
        height,
        context_kind == "touch",
    )
    try:
        page.evaluate(SCROLL_INTO_VIEW_SCRIPT, "recap-open")
        page.wait_for_timeout(SETTLE_MS)
        result = page.evaluate(HIT_AT_CENTRE_SCRIPT, "recap-open")
    finally:
        close()

    assert result["hits"] is True, result


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac10_a_keyboard_focus_keeps_recap_open_and_its_outline_in_the_toolbar(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_solved_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, False
    )
    reading: dict[str, Any] | None = None
    try:
        page.evaluate(FOCUS_SHARE_LINK_SCRIPT)
        for _ in range(MAX_TABS):
            page.keyboard.press("Tab")
            if page.evaluate(FOCUSED_TEST_ID_SCRIPT) == "recap-open":
                page.wait_for_timeout(SETTLE_MS)
                reading = page.evaluate(FOCUS_IN_TOOLBAR_SCRIPT)
                break
    finally:
        close()

    assert reading is not None, f"recap-open not focused in {MAX_TABS} presses of Tab"
    problems = keyboard_focus_problems(reading)
    other_problems = [text for text in problems if "room-toolbar-more" not in text]
    assert other_problems == []


@pytest.mark.parametrize("context_kind", CONTEXTS)
def test_ac10_a_pointer_focus_on_recap_open_makes_no_scroll_call(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_solved_toolbar_room(
        browser, browser_name, live_server, fx01_grid, 320, 568, touch
    )
    try:
        after = press_partly_hidden_button(page, "recap-open", touch)
    finally:
        close()

    assert after["calls"] == [], after
    if after["hiddenPastRight"] > 1:
        assert after["fadeVisible"] is True, after


def test_ac10_tab_reaches_recap_open_with_the_outline_and_enter_opens_the_dialog(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_solved_toolbar_room(
        browser, browser_name, live_server, fx01_grid, 1280, 720, False
    )
    try:
        walker = Walker(page)
        walker.tab_to("recap-open")
        reached = walker.reached[-1]
        page.keyboard.press("Enter")

        expect(page.get_by_test_id("recap")).to_be_visible()
    finally:
        close()

    assert reached.test_id == "recap-open"
    problems = outline_problems(
        reached.outline_style, reached.outline_width, reached.outline_contrast
    )
    assert problems == []


# ---- Semantics of the dialog ----


def test_ac10_the_dialog_is_labelled_by_its_heading_and_the_list_by_its_own(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    serve_recap(page, recap_body(share_path=SHARE_PATH))
    open_timer_room(
        page, live_server, fx01_grid, elapsed_ms=754_000, running=False, solved=True
    )
    page.get_by_test_id("recap-open").click()
    expect(page.get_by_test_id("recap-players")).to_be_visible()
    fr = load_fr()

    reading = page.evaluate("""() => {
          const dialog = document.querySelector('[data-testid="recap"]');
          const heading = dialog.querySelector('h2');
          const labelId = dialog.getAttribute('aria-labelledby');
          const list = dialog.querySelector('[data-testid="recap-players"]');
          const playersHeading = dialog.querySelector('#recap-players-heading');
          return {
            tag: dialog.tagName,
            labelIsHeading: !!heading && labelId !== '' && heading.id === labelId,
            heading: heading && heading.textContent.trim(),
            listTag: list.tagName,
            listRole: list.getAttribute('role'),
            listLabel: list.getAttribute('aria-labelledby'),
            playersHeadingTag: playersHeading && playersHeading.tagName,
            playersHeading: playersHeading && playersHeading.textContent.trim(),
            itemTags: Array.from(list.children).map(item => item.tagName),
          };
        }""")

    assert reading == {
        "tag": "DIALOG",
        "labelIsHeading": True,
        "heading": fr["recap.heading"],
        "listTag": "UL",
        "listRole": "list",
        "listLabel": "recap-players-heading",
        "playersHeadingTag": "H3",
        "playersHeading": fr["recap.players_heading"],
        "itemTags": ["LI", "LI"],
    }


# ---- Scans ----


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac10_the_open_dialog_has_no_contrast_offender(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_dialog_room(
        browser, browser_name, live_server, fx01_grid, width, height, False
    )
    try:
        offenders = contrast_offenders(page)
    finally:
        close()

    assert offenders == []


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac10_the_open_dialog_has_no_text_outside_fr_json_and_the_test_data(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_dialog_room(
        browser, browser_name, live_server, fx01_grid, width, height, False
    )
    try:
        texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    finally:
        close()

    data = language_data(live_server, ["Ana", "Bob"])
    data |= {"Temps : 12:34", "8 lettres", f"{live_server}{SHARE_PATH}"}
    assert len(texts) > 0
    assert unknown_texts(texts, data) == []


# ---- Nicknames are text ----


def test_ac10_nicknames_with_markup_show_as_text_in_the_dialog(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        recap_player("p1", HOSTILE_NAMES[0], 8, 4),
        recap_player("p2", HOSTILE_NAMES[1], 5, 3),
    ]
    serve_recap(page, recap_body(players=players, share_path=SHARE_PATH))
    open_timer_room(
        page,
        live_server,
        fx01_grid,
        elapsed_ms=754_000,
        running=False,
        solved=True,
        players=[
            player_view("p1", "Ana", 0, is_host=True),
            player_view("p2", "Bob", 1),
        ],
    )

    page.get_by_test_id("recap-open").click()

    names = page.get_by_test_id("recap-name")
    expect(names.nth(0)).to_have_text("<b>Eve</b>")
    expect(names.nth(1)).to_have_text("<img src=x>")
    dialog = page.get_by_test_id("recap")
    expect(dialog.locator("b")).to_have_count(0)
    expect(dialog.locator("img")).to_have_count(0)
