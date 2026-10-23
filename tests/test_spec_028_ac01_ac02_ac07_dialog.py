"""Tests of spec 028 in the room page with a mocked socket: AC-1, AC-2, AC-5 (the
dialog's share link and copy button) and AC-7.

The page is spec 040's mocked room on `/r/ABC123` with a FX-01 snapshot for `p1`
(`you`, Ana, colour 0) and `p2` (Bob, colour 1), `solved` true unless a test says
otherwise, where every letter cell holds its right letter (`solved_view` of
`spec028_harness`). The recap route is answered by `page.route` with plain JSON
(see `spec028_harness`).

Readings that the spec leaves open:

- `data-you` of another player's row: the test only requires that it is not
  `true`.
- "described by a `t("recap.share_label")` label": the link's `aria-describedby`
  names an element whose text is that label.
- "The swatch of a recap player" is read on the `recap-colour` element's own
  computed `background-color`, `background-image` and `box-shadow`.

Refined by spec 043 (the design's room layout): `recap-open` sits inside
`grid-status` (`data-state="solved"`), after its text, where it sat in
`room-toolbar` right after `chat-toggle`; the dialog comes after the top bar and
the play area in document order (spec 043's "Document order").

Refined by spec 047 (the design's room overlays): `recap-revealed` comes with the
other counts, before the players' heading (AC-1's order); a player the page no
longer knows has a swatch that draws nothing, no hatching (AC-2); after a copy,
`recap-copy` keeps its text and `recap-copied` reads « Lien copié » (AC-5).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Locator, Page, Route, expect

from nock.grid import Grid
from nock.protocol import GridSolved, LeaveReason, PlayerLeft
from spec019_harness import SWATCH_COLOURS_JS, Rgba, rgba_from
from spec024_harness import (
    cell_at,
    expect_seq,
    grid_from_text,
    load_fr,
)
from spec027_harness import open_timer_room
from spec028_harness import (
    QUIET_MS,
    RECAP_ROUTE,
    open_solved_page,
    recap_body,
    recap_player,
)

SHARE_PATH = "/recap/tok_ABCDEFGHIJKLMNOP"
ALPHA_TOLERANCE = 0.01  # "a background with alpha 0" (spec 047 AC-9)
# Spec 047: `recap-revealed` comes with the other counts, before the players.
PART_IDS = [
    "recap-time",
    "recap-checks",
    "recap-reveals",
    "recap-revealed",
    "recap-players",
    "recap-share-link",
    "recap-copy",
    "recap-close",
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def open_recap(page: Page) -> None:
    """Click `recap-open` and wait for the dialog."""
    page.get_by_test_id("recap-open").click()
    expect(page.get_by_test_id("recap")).to_be_visible()


def row_of(page: Page, player_id: str) -> Locator:
    return page.locator(f'[data-testid="recap-player"][data-player-id="{player_id}"]')


def active_test_id(page: Page) -> object:
    return page.evaluate(
        "() => document.activeElement"
        " && document.activeElement.getAttribute('data-testid')"
    )


# ---- AC-1: time, checks, reveals ----


def test_ac1_the_dialog_shows_the_time_the_checks_and_the_reveals(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body())

    open_recap(page)

    expect(page.get_by_test_id("recap-time")).to_have_text("Temps : 12:34")
    expect(page.get_by_test_id("recap-checks")).to_have_text("Vérifications : 2")
    expect(page.get_by_test_id("recap-reveals")).to_have_text(
        "Révélations : 1 lettres et 1 mots"
    )


def test_ac1_a_time_over_an_hour_is_written_as_the_timer_writes_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body(elapsed_ms=3_725_000))

    open_recap(page)

    expect(page.get_by_test_id("recap-time")).to_have_text("Temps : 1:02:05")


def test_ac1_other_counts_are_written_as_they_are(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    body = recap_body(checks=0, letter_reveals=3, word_reveals=0, revealed_letters=7)
    open_solved_page(page, live_server, fx01_grid, body)

    open_recap(page)

    expect(page.get_by_test_id("recap-checks")).to_have_text("Vérifications : 0")
    expect(page.get_by_test_id("recap-reveals")).to_have_text(
        "Révélations : 3 lettres et 0 mots"
    )
    expect(page.get_by_test_id("recap-revealed")).to_have_text("Lettres révélées : 7")


def test_ac1_the_dialog_shows_loading_until_the_answer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    held: list[Route] = []
    page.route(RECAP_ROUTE, lambda route: held.append(route))
    open_timer_room(
        page, live_server, fx01_grid, elapsed_ms=754_000, running=False, solved=True
    )

    page.get_by_test_id("recap-open").click()

    expect(page.get_by_test_id("recap-loading")).to_have_text("Chargement du bilan…")
    expect(page.get_by_test_id("recap-time")).to_have_count(0)
    while not held:
        page.wait_for_timeout(50)
    held[0].fulfill(
        status=200, content_type="application/json", body=json.dumps(recap_body())
    )
    expect(page.get_by_test_id("recap-time")).to_have_text("Temps : 12:34")
    expect(page.get_by_test_id("recap-loading")).to_have_count(0)


PARTS_ORDER_SCRIPT = """
ids => {
  const dialog = document.querySelector('[data-testid="recap"]');
  const heading = dialog.querySelector('h2');
  const playersHeading = dialog.querySelector('h3#recap-players-heading');
  const found = [['h2', heading], ['h3', playersHeading]];
  for (const id of ids) {
    found.push([id, dialog.querySelector(`[data-testid="${id}"]`)]);
  }
  const missing = found.filter(([, element]) => element === null).map(([id]) => id);
  const order = ['h2', 'recap-time', 'recap-checks', 'recap-reveals',
    'recap-revealed', 'h3', 'recap-players', 'recap-share-link', 'recap-copy',
    'recap-close'];
  const byId = Object.fromEntries(found);
  const outOfOrder = [];
  for (let index = 0; index + 1 < order.length; index += 1) {
    const first = byId[order[index]];
    const second = byId[order[index + 1]];
    const following = first && second
      && (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
    if (first && second && !following) {
      outOfOrder.push([order[index], order[index + 1]]);
    }
  }
  return {missing: missing, outOfOrder: outOfOrder};
}
"""


def test_ac1_the_dialog_holds_its_parts_in_the_spec_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body(share_path=SHARE_PATH))
    open_recap(page)
    expect(page.get_by_test_id("recap-time")).to_be_visible()

    reading = page.evaluate(PARTS_ORDER_SCRIPT, PART_IDS)

    assert reading == {"missing": [], "outOfOrder": []}


# ---- AC-2: the rows of the players ----


def test_ac2_the_players_are_listed_in_the_recap_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body())

    open_recap(page)

    rows = page.get_by_test_id("recap-players").get_by_test_id("recap-player")
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_have_attribute("data-player-id", "p1")
    expect(rows.nth(1)).to_have_attribute("data-player-id", "p2")


def test_ac2_the_first_row_is_mine_with_its_name_letters_and_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body())
    you_text = load_fr()["roster.you"]

    open_recap(page)

    row = row_of(page, "p1")
    expect(row).to_have_attribute("data-you", "true")
    expect(row).to_have_attribute("data-letters", "8")
    expect(row).to_have_attribute("data-words", "4")
    expect(row.get_by_test_id("recap-name")).to_have_text("Ana")
    expect(row.get_by_text(you_text, exact=True)).to_have_count(1)
    expect(row.get_by_test_id("recap-letters")).to_have_text("8 lettres")
    expect(row.get_by_test_id("recap-words")).to_have_text("4 mots complétés")


def test_ac2_the_second_row_is_not_mine(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body())
    you_text = load_fr()["roster.you"]

    open_recap(page)

    row = row_of(page, "p2")
    assert row.get_attribute("data-you") != "true"
    expect(row).to_have_attribute("data-letters", "5")
    expect(row).to_have_attribute("data-words", "3")
    expect(row.get_by_test_id("recap-name")).to_have_text("Bob")
    expect(row.get_by_text(you_text, exact=True)).to_have_count(0)
    expect(row.get_by_test_id("recap-letters")).to_have_text("5 lettres")
    expect(row.get_by_test_id("recap-words")).to_have_text("3 mots complétés")


def test_ac2_each_swatch_has_the_colour_of_the_roster_swatch(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body())

    open_recap(page)

    for player_id, colour in [("p1", "0"), ("p2", "1")]:
        roster = page.locator(
            f'[data-testid="roster-player"][data-player-id="{player_id}"]'
        ).get_by_test_id("roster-colour")
        expect(roster).to_have_attribute("data-colour", colour)
        swatch = row_of(page, player_id).get_by_test_id("recap-colour")
        expect(swatch).to_have_attribute("data-colour", colour)


# The computed background and shadow of a `recap-colour` swatch: its colour, its
# image and its `box-shadow`, the colour as [red, green, blue, alpha] (spec 019's
# `parseColour`).
SWATCH_SCRIPT = "swatch => {\n" + SWATCH_COLOURS_JS + r"""
  const style = getComputedStyle(swatch);
  return {
    colour: parseColour(style.backgroundColor),
    image: style.backgroundImage,
    shadow: style.boxShadow,
  };
}
"""


class SwatchLook(NamedTuple):
    """How a `recap-colour` swatch is drawn: its computed background and shadow."""

    colour: Rgba
    image: str
    shadow: str


def swatch_look(swatch: Locator) -> SwatchLook:
    """Read the computed background and shadow of one `recap-colour` swatch."""
    raw = swatch.evaluate(SWATCH_SCRIPT)
    return SwatchLook(
        colour=rgba_from(raw["colour"]), image=raw["image"], shadow=raw["shadow"]
    )


def drawn_swatch_problems(look: SwatchLook) -> list[str]:
    """How a swatch fails to draw nothing (empty: it draws nothing).

    Spec 047 (its Decision 4) refines "The swatch of a recap player": with
    `data-colour=""` the swatch draws nothing, a transparent background with
    alpha 0, no `background-image` and no `box-shadow`, in place of spec 028's
    hatching.
    """
    problems: list[str] = []
    if abs(look.colour[3]) > ALPHA_TOLERANCE:
        problems.append(f"background-color {look.colour} is not transparent")
    if look.image != "none":
        problems.append(f"background-image {look.image!r}")
    if look.shadow != "none":
        problems.append(f"box-shadow {look.shadow!r}")
    return problems


def test_ac2_the_swatches_of_the_players_in_the_room_have_no_pattern(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body())

    open_recap(page)

    for player_id, colour in [("p1", "0"), ("p2", "1")]:
        swatch = row_of(page, player_id).get_by_test_id("recap-colour")
        expect(swatch).to_have_attribute("data-colour", colour)
        assert swatch_look(swatch).image == "none", player_id


def test_ac2_a_player_who_left_gets_a_swatch_that_draws_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_solved_page(page, live_server, fx01_grid, recap_body()).mock
    left = PlayerLeft(seq=6, player_id="p2", reason=LeaveReason.TIMED_OUT)
    mock.send(left.model_dump_json())
    expect_seq(page, 6)

    open_recap(page)

    departed = row_of(page, "p2").get_by_test_id("recap-colour")
    expect(departed).to_have_attribute("data-colour", "")
    mine = row_of(page, "p1").get_by_test_id("recap-colour")
    expect(mine).to_have_attribute("data-colour", "0")
    assert swatch_look(mine).image == "none"
    assert drawn_swatch_problems(swatch_look(departed)) == []


def test_ac2_a_player_unknown_to_the_page_gets_a_swatch_that_draws_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [recap_player("p1", "Ana", 8, 4), recap_player("p9", "Zoe", 2, 1)]
    open_solved_page(page, live_server, fx01_grid, recap_body(players=players))

    open_recap(page)

    swatch = row_of(page, "p9").get_by_test_id("recap-colour")
    expect(swatch).to_have_attribute("data-colour", "")
    assert drawn_swatch_problems(swatch_look(swatch)) == []


def test_ac2_a_player_without_nickname_is_written_as_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [recap_player("p1", "Ana", 8, 4), recap_player("p9", None, 2, 1)]
    open_solved_page(page, live_server, fx01_grid, recap_body(players=players))

    open_recap(page)

    name = row_of(page, "p9").get_by_test_id("recap-name")
    expect(name).to_have_text(load_fr()["feed.someone"])


def test_ac2_a_removed_player_with_nothing_gets_no_row(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        recap_player("p1", "Ana", 8, 4),
        recap_player("p2", "Bob", 5, 3),
        recap_player("p3", "Cy", 0, 0, removed=True),
    ]
    open_solved_page(page, live_server, fx01_grid, recap_body(players=players))

    open_recap(page)

    rows = page.get_by_test_id("recap-player")
    expect(rows).to_have_count(2)
    expect(row_of(page, "p3")).to_have_count(0)


@pytest.mark.parametrize(("letters", "words"), [(2, 0), (0, 1)])
def test_ac2_a_removed_player_with_a_letter_or_a_word_keeps_a_row(
    page: Page, live_server: str, fx01_grid: Grid, letters: int, words: int
) -> None:
    players = [
        recap_player("p1", "Ana", 8, 4),
        recap_player("p3", "Cy", letters, words, removed=True),
    ]
    open_solved_page(page, live_server, fx01_grid, recap_body(players=players))

    open_recap(page)

    expect(page.get_by_test_id("recap-player")).to_have_count(2)
    expect(row_of(page, "p3").get_by_test_id("recap-name")).to_have_text("Cy")
    expect(row_of(page, "p3")).to_have_attribute("data-letters", str(letters))
    expect(row_of(page, "p3")).to_have_attribute("data-words", str(words))


# ---- AC-5: the share link and the copy button of the dialog ----


def test_ac5_the_dialog_shows_the_share_link_with_the_origin(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body(share_path=SHARE_PATH))

    open_recap(page)

    link = page.get_by_test_id("recap-share-link")
    expected = f"{live_server}{SHARE_PATH}"
    expect(link).to_have_attribute("href", expected)
    expect(link).to_have_text(expected)
    expect(page.get_by_test_id("recap-copy")).to_have_text(load_fr()["room.share.copy"])


def test_ac5_the_share_link_is_described_by_its_label(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body(share_path=SHARE_PATH))
    open_recap(page)

    link = page.get_by_test_id("recap-share-link")
    description_id = link.get_attribute("aria-describedby")

    assert description_id, "recap-share-link has no aria-describedby"
    text = page.evaluate(
        "id => document.getElementById(id).textContent", description_id
    )
    assert text.strip() == load_fr()["recap.share_label"] == "Lien à partager"


def test_ac5_without_a_share_path_the_dialog_has_no_share_link(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body(share_path=None))

    open_recap(page)

    expect(page.get_by_test_id("recap-time")).to_be_visible()
    expect(page.get_by_test_id("recap-share-link")).to_have_count(0)
    expect(page.get_by_test_id("recap-copy")).to_have_count(0)
    expect(page.get_by_test_id("recap-close")).to_have_text("Fermer")


@pytest.fixture
def clipboard_page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    try:
        yield context.new_page()
    finally:
        context.close()


@pytest.mark.only_browser("chromium")
def test_ac5_a_copy_shows_lien_copie_for_two_seconds_and_the_button_keeps_its_text(
    clipboard_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    """Spec 047 (the human's decision P16): « Lien copié » is the line
    `recap-copied` under the share row; `recap-copy` keeps « Copier le lien »."""
    open_solved_page(
        clipboard_page, live_server, fx01_grid, recap_body(share_path=SHARE_PATH)
    )
    open_recap(clipboard_page)
    fr = load_fr()
    copy_button = clipboard_page.get_by_test_id("recap-copy")

    copy_button.click()

    copied_line = clipboard_page.get_by_test_id("recap-copied")
    expect(copied_line).to_have_text(fr["room.share.copied"])
    expect(copy_button).to_have_text(fr["room.share.copy"])
    copied = clipboard_page.evaluate("navigator.clipboard.readText()")
    assert copied == f"{live_server}{SHARE_PATH}"
    expect(copied_line).to_be_hidden(timeout=4000)


@pytest.mark.parametrize(
    "init_script",
    [
        "Object.defineProperty(navigator, 'clipboard', {value: undefined});",
        "Object.defineProperty(navigator, 'clipboard', {value: "
        "{writeText: () => Promise.reject(new Error('refused'))}});",
    ],
    ids=["missing", "refusing"],
)
def test_ac5_copy_changes_nothing_without_a_usable_clipboard(
    browser: Browser, live_server: str, fx01_grid: Grid, init_script: str
) -> None:
    context = browser.new_context()
    context.add_init_script(init_script)
    try:
        page = context.new_page()
        open_solved_page(
            page, live_server, fx01_grid, recap_body(share_path=SHARE_PATH)
        )
        open_recap(page)
        copy_button = page.get_by_test_id("recap-copy")

        copy_button.click()
        page.wait_for_timeout(QUIET_MS)

        expect(copy_button).to_have_text(load_fr()["room.share.copy"])
        # Spec 047: nor does the « Lien copié » line show.
        expect(page.get_by_test_id("recap-copied")).to_have_count(0)
    finally:
        context.close()


# ---- AC-7: opens only on request, never blocks the grid ----


def test_ac7_an_unsolved_page_has_no_recap_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body(), solved=False)

    expect(page.get_by_test_id("room-topbar")).to_be_visible()
    expect(page.get_by_test_id("recap-open")).to_have_count(0)


# Spec 043: `recap-open` inside `grid-status`, after the status's text.
STATUS_PLACE_SCRIPT = """
() => {
  const status = document.querySelector('[data-testid="grid-status"]');
  const button = document.querySelector('[data-testid="recap-open"]');
  let afterText = false;
  if (status !== null && button !== null) {
    const walker = document.createTreeWalker(status, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
      if (button.contains(node) || node.textContent.trim() === '') {
        continue;
      }
      const position = node.compareDocumentPosition(button);
      afterText = Boolean(position & Node.DOCUMENT_POSITION_FOLLOWING);
      break;
    }
  }
  return {
    state: status === null ? null : status.getAttribute('data-state'),
    inside: status !== null && button !== null && status.contains(button),
    afterText: afterText,
    tag: button === null ? null : button.tagName,
    type: button === null ? null : button.getAttribute('type'),
  };
}
"""


def test_ac7_the_button_shows_after_the_solve_inside_the_end_band(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    opened = open_solved_page(page, live_server, fx01_grid, recap_body(), solved=False)

    opened.mock.send(GridSolved(seq=6, elapsed_ms=754_000).model_dump_json())
    expect_seq(page, 6)

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "true")
    expect(page.get_by_test_id("recap-open")).to_have_text("Voir le bilan")
    reading = page.evaluate(STATUS_PLACE_SCRIPT)
    assert reading["state"] == "solved", reading
    assert reading["inside"] is True, reading
    assert reading["afterText"] is True, reading
    assert (reading["tag"], reading["type"]) == ("BUTTON", "button")


def test_ac7_the_dialog_does_not_open_by_itself_and_the_grid_stays_usable(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    opened = open_solved_page(page, live_server, fx01_grid, recap_body(), solved=False)
    opened.mock.send(GridSolved(seq=6, elapsed_ms=754_000).model_dump_json())
    expect_seq(page, 6)
    expect(page.get_by_test_id("recap-open")).to_be_visible()

    cell_at(page, 1, 0).click()
    page.wait_for_timeout(QUIET_MS)

    expect(page.get_by_test_id("recap")).not_to_be_visible()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "1")
    assert opened.route.requests == []


def test_ac7_a_click_opens_the_dialog_with_one_request_and_the_focus_inside(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    opened = open_solved_page(page, live_server, fx01_grid, recap_body())

    open_recap(page)
    expect(page.get_by_test_id("recap-time")).to_be_visible()

    assert len(opened.route.requests) == 1
    dialog = page.get_by_test_id("recap")
    assert dialog.evaluate("el => el.tagName") == "DIALOG"
    assert dialog.evaluate("el => el.matches(':modal')") is True
    assert dialog.evaluate("el => el.contains(document.activeElement)") is True


def test_ac7_escape_closes_the_dialog_and_the_focus_goes_back_to_the_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body())
    open_recap(page)
    expect(page.get_by_test_id("recap-time")).to_be_visible()

    page.keyboard.press("Escape")

    expect(page.get_by_test_id("recap")).not_to_be_visible()
    assert active_test_id(page) == "recap-open"


def test_ac7_the_close_button_closes_it_the_same_way_and_a_reopen_asks_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    opened = open_solved_page(page, live_server, fx01_grid, recap_body())
    open_recap(page)
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("recap")).not_to_be_visible()

    open_recap(page)
    expect(page.get_by_test_id("recap-close")).to_be_visible()
    page.get_by_test_id("recap-close").click()

    expect(page.get_by_test_id("recap")).not_to_be_visible()
    assert active_test_id(page) == "recap-open"
    assert len(opened.route.requests) == 2


def test_ac7_a_404_shows_the_error_message(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, {"detail": "Not Found"}, status=404)

    open_recap(page)

    error = page.get_by_test_id("recap-error")
    expect(error).to_have_text(load_fr()["recap.error"])
    expect(page.get_by_test_id("recap-loading")).to_have_count(0)
    expect(page.get_by_test_id("recap-time")).to_have_count(0)


def test_ac7_a_failed_request_shows_the_error_message(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    page.route(RECAP_ROUTE, lambda route: route.abort())
    open_timer_room(
        page, live_server, fx01_grid, elapsed_ms=754_000, running=False, solved=True
    )

    open_recap(page)

    expect(page.get_by_test_id("recap-error")).to_have_text(load_fr()["recap.error"])


def test_ac7_a_page_whose_first_snapshot_is_solved_has_the_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body(), solved=True)

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "true")
    expect(page.get_by_test_id("recap-open")).to_be_visible()
    expect(page.get_by_test_id("recap")).not_to_be_visible()


def test_ac7_a_late_joiner_s_own_row_shows_no_letter_and_no_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # Ana (`you`) joined the room once Bob had solved it alone: she comes last.
    players = [recap_player("p2", "Bob", 18, 8), recap_player("p1", "Ana", 0, 0)]
    body = recap_body(
        players=players, letter_reveals=0, word_reveals=0, revealed_letters=0
    )
    open_solved_page(page, live_server, fx01_grid, body)

    open_recap(page)

    rows = page.get_by_test_id("recap-players").get_by_test_id("recap-player")
    expect(rows).to_have_count(2)
    expect(rows.nth(1)).to_have_attribute("data-player-id", "p1")
    mine = row_of(page, "p1")
    expect(mine).to_have_attribute("data-you", "true")
    expect(mine).to_have_attribute("data-letters", "0")
    expect(mine).to_have_attribute("data-words", "0")
    expect(mine.get_by_test_id("recap-letters")).to_have_text("0 lettres")
    expect(mine.get_by_test_id("recap-words")).to_have_text("0 mots complétés")


def test_ac7_the_dialog_comes_after_the_top_bar_and_the_status_in_document_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_page(page, live_server, fx01_grid, recap_body())
    open_recap(page)

    follows = page.evaluate("""() => {
          const dialog = document.querySelector('[data-testid="recap"]');
          const found = [];
          for (const id of ['room-topbar', 'grid-status', 'salon']) {
            const element = document.querySelector(`[data-testid="${id}"]`);
            found.push(element !== null && Boolean(
              element.compareDocumentPosition(dialog)
                & Node.DOCUMENT_POSITION_FOLLOWING
            ));
          }
          return found;
        }""")

    assert follows == [True, True, True]
