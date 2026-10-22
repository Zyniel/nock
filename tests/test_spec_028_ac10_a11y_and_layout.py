"""Tests of spec 028, AC-10: the recap dialog and the share page are accessible and
fit every window (page with a mocked socket; the share page on the live server).

The room page is spec 013 AC-6's FX-01 snapshot (`you` host among 8 players, 100
feed items, (3, 1) tapped) but solved, with the recap route answering the recap of
AC-2 plus a `share_path`.

Refined by spec 043 (the design's room layout) and spec 047's note on this
criterion: the toolbar is gone and `recap-open` is in the end band (`grid-status`),
so spec 024 AC-8's toolbar checks (order, one row, the edge fade, the keyboard
focus inside the toolbar, the pointer focus) go; on the solved page spec 043
AC-28's checks hold (`room-topbar` and `clue-bar` inside the window, each of their
buttons hit at its centre) and `elementFromPoint` at the centre of `recap-open`
returns it.

Readings the spec leaves open:

- Every measure and scan of the open dialog waits for `recap-time`, so that it
  reads the loaded recap and not `recap-loading` (the spec names no other ready
  state).
- The share page of the scans is the stored room's page (`PLAY_R`, loaded from a
  `RoomStore`), with its API route answered by `page.route`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec019_harness import CONTEXT_KINDS, WINDOW_SIZES, layout_problems
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
from spec028_harness import (
    eight_players,
    recap_body,
    recap_player,
    serve_recap,
)
from spec035_harness import (
    MAX_TABS,
    WAIT_TIMEOUT_MS,
    Walker,
    contrast_offenders,
    unknown_texts,
)
from spec042_harness import box_of
from spec043_harness import (
    CLUE_BAR_BUTTONS,
    H8_TIMER_MS,
    box_inside,
    check_frame,
    hit_problem,
    shown_items,
    window_box,
)

SHARE_PATH = "/recap/tok_ABCDEFGHIJKLMNOP"
FEED_ITEMS = 100
EPSILON = 1.0
SCAN_SIZES = [(1280, 720), (360, 740)]


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    """Readable ids of window sizes for `parametrize`."""
    return [f"{width}x{height}" for width, height in sizes]


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
            elapsed_ms=H8_TIMER_MS,
            running=False,
            solved=True,
            players=eight_players(),
        )
        expect(page.get_by_test_id("recap-open")).to_be_visible()
        last_seq = 5 + FEED_ITEMS
        for seq in range(6, last_seq + 1):
            mock.send(check_frame(seq, "p2"))
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
    """The mocked solved room at a window size with the recap dialog open and loaded.

    Returns once `recap-time` shows: `recap-close` already shows while the dialog
    is loading.
    """
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        body = recap_body(players=players, share_path=SHARE_PATH)
        serve_recap(page, body)
        open_timer_room(
            page, live_server, grid, elapsed_ms=754_000, running=False, solved=True
        )
        page.get_by_test_id("recap-open").click()
        expect(page.get_by_test_id("recap-time")).to_be_visible()
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


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
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


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
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


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
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
        problems = layout_problems(page, touch)
    finally:
        close()

    assert problems == []


def solved_page_reach_problems(page: Page) -> list[str]:
    """Spec 043 AC-28's checks on the solved page, and the hit of `recap-open`.

    `room-topbar` and `clue-bar` lie inside the window, and `elementFromPoint` at
    the centre of each top-bar button, each clue-bar button and `recap-open`
    returns it.
    """
    window = window_box(page)
    problems: list[str] = []
    for test_id in ("room-topbar", "clue-bar"):
        box = box_of(page.get_by_test_id(test_id))
        if not box_inside(box, window):
            problems.append(f"{test_id} {box} is not inside the window")
    targets: list[str] = []
    for item in shown_items(page.get_by_test_id("room-topbar")):
        if item["tag"] == "BUTTON":
            targets.append(str(item["testId"]))
    targets.extend(CLUE_BAR_BUTTONS)
    targets.append("recap-open")
    for test_id in targets:
        found = hit_problem(page, test_id)
        if found is not None:
            problems.append(found)
    return problems


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac10_on_the_solved_page_every_button_and_recap_open_can_be_hit(
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
        problems = solved_page_reach_problems(page)
    finally:
        close()

    assert problems == []


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
    data.add(f"{live_server}{SHARE_PATH}")
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
    # The nicknames as spec 040's displayNickname writes them.
    expect(names.nth(0)).to_have_text("<b>eve</b>")
    expect(names.nth(1)).to_have_text("<img Src=x>")
    dialog = page.get_by_test_id("recap")
    expect(dialog.locator("b")).to_have_count(0)
    expect(dialog.locator("img")).to_have_count(0)
