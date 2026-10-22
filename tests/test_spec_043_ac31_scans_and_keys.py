"""Tests of spec 043, AC-31: the new room passes spec 035's scans, and `fr.json`
holds the keys of this spec.

The scans run at 1280 by 720 and 360 by 740 on `H8` with `p2`'s flag on IDES,
(1, 1) holding `X` wrong and a `clap` reaction of `p2` shown on IDES, in the states
of the criterion except a shown `room-note`, which work package WP-2 builds ("Work
packages"): all closed; the Salon on Discussion; the Salon on Joueurs; `aide-menu`
open; `room-menu` open; `host-settings` open; `connection-banner` shown; and
`grid-status` solved, on the solved snapshot of AC-27.

Choices where the spec leaves room:

- The language scan's data are the nicknames as the page shows them and their two
  first letters, the room code, its link and FX-01's clue texts (spec 024's
  `language_data`); `H8` has no chat line.
- The reaction is sent once the state is set, so that it shows during the scan;
  in the `connection-banner` state it is sent just before the socket closes, since
  a closed socket delivers nothing.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import FlagView, Reaction
from room_panels import open_aide, open_host_settings, open_menu, show_tab
from spec019_harness import OpenWindow, window_opener
from spec024_harness import contrast_problems, language_data, language_problems
from spec043_harness import (
    DISPLAY_NICKNAMES,
    IDES,
    RoomMock,
    expect_closed,
    fx01_view,
    is_open,
    load_fr,
    open_h8,
    open_room,
    players_up_to,
    reaction_frame,
    snapshot_frame,
    solved_view,
)

SIZES = [(1280, 720), (360, 740)]
STATES = [
    "closed",
    "discussion",
    "players",
    "aide",
    "menu",
    "host-settings",
    "banner",
    "solved",
]
SCAN_CASES = [(size, state) for size in SIZES for state in STATES]
SCAN_IDS = [f"{width}x{height}-{state}" for (width, height), state in SCAN_CASES]

NEW_KEYS = {
    "topbar.aide": "Aide",
    "topbar.salon": "Salon",
    "topbar.menu": "Menu",
    "topbar.salon_unread": "Salon, {count} messages non lus",
    "topbar.salon_events": "Salon, nouvelle activit\N{LATIN SMALL LETTER E WITH ACUTE}",
    "aide.empty": "L'aide est d\N{LATIN SMALL LETTER E WITH ACUTE}sactiv"
    "\N{LATIN SMALL LETTER E WITH ACUTE}e dans ce salon.",
    "authors.on": "activ\N{LATIN SMALL LETTER E WITH ACUTE}",
    "authors.off": "d\N{LATIN SMALL LETTER E WITH ACUTE}sactiv"
    "\N{LATIN SMALL LETTER E WITH ACUTE}",
    "others_tint.on": "teint\N{LATIN SMALL LETTER E WITH ACUTE}s",
    "others_tint.off": "sans teinte",
    "access.on": "activ\N{LATIN SMALL LETTER E WITH ACUTE}e",
    "access.off": "d\N{LATIN SMALL LETTER E WITH ACUTE}sactiv"
    "\N{LATIN SMALL LETTER E WITH ACUTE}e",
    "menu.invite": "Inviter",
    "menu.invite_detail": "lien",
    "menu.back": "Retour aux grilles",
    "timer.hide": "Masquer le chrono",
    "salon.progress": "{filled} / {total} mots",
    "salon.players_tab": "Joueurs ({count})",
    "clue_bar.previous": "D\N{LATIN SMALL LETTER E WITH ACUTE}finition "
    "pr\N{LATIN SMALL LETTER E WITH ACUTE}c\N{LATIN SMALL LETTER E WITH ACUTE}dente",
    "clue_bar.next": "D\N{LATIN SMALL LETTER E WITH ACUTE}finition suivante",
    "reveal.letters_left": "{count} restantes",
    "reveal.letters_left_one": "1 restante",
    "reveal.words_left": "{count} restants",
    "reveal.words_left_one": "1 restant",
    "note.message": "{name} : {text}",
    "note.own_reaction": "Vous avez r\N{LATIN SMALL LETTER E WITH ACUTE}agi"
    " : {reaction}",
}
CHANGED_KEYS = {
    "check.letter": "La lettre",
    "check.word": "Le mot",
    "check.grid": "La grille",
    "reveal.letter": "La lettre",
    "reveal.word": "Le mot",
    "pencil.confirm": "Confirmer la lettre au crayon",
    "settings.heading": "R\N{LATIN SMALL LETTER E WITH ACUTE}glages de "
    "l'h\N{LATIN SMALL LETTER O WITH CIRCUMFLEX}te",
}
REMOVED_KEYS = (
    "check.letter_label",
    "check.word_label",
    "check.grid_label",
    "reveal.letter_label",
    "reveal.word_label",
    "reveal.letter_none_label",
    "reveal.word_none_label",
    "pencil.confirm_label",
    "host.unlock",
    "host.remove_short",
    "feed.heading",
    "chat.toggle",
    "chat.toggle_label_unread",
    "chat.moderation_heading",
    "reaction.button",
    "flag.button",
    "timer.toggle",
)

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- The states of the scans --------------------------------------------------------


def open_scan_state(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int], state: str
) -> Page:
    """Open the page of AC-31 at `size` in `state`, with the reaction shown."""
    page = window(size[0], size[1], False)
    if state == "solved":
        frame = snapshot_frame(solved_view(grid), players_up_to(8), solved=True)
        mock = open_room(page, base_url, frame)
        expect(page.get_by_test_id("grid-status")).to_have_attribute(
            "data-state", "solved"
        )
    else:
        changes: list[tuple[int, int, dict[str, object]]] = [
            (1, 1, {"letter": "X", "author": "p2", "wrong": True})
        ]
        flags = [FlagView(player_id="p2", clue=IDES)]
        view = fx01_view(grid, changes)
        mock = open_h8(page, base_url, grid, False, view=view, flags=flags)
        if state == "banner":
            send_the_reaction(page, mock)
        set_state(page, mock, state)
    if state != "banner":
        send_the_reaction(page, mock)
    expect(page.get_by_test_id("clue-reaction")).to_have_count(1)
    return page


def send_the_reaction(page: Page, mock: RoomMock) -> None:
    """Send `p2`'s `clap` on IDES and wait until it shows."""
    mock.send(reaction_frame("p2", IDES, Reaction.CLAP))
    expect(page.get_by_test_id("clue-reaction")).to_have_count(1)


def set_state(page: Page, mock: RoomMock, state: str) -> None:
    if state == "closed":
        salon = page.get_by_test_id("salon")
        if is_open(salon):
            page.get_by_test_id("chat-toggle").click()
        expect_closed(salon)
    elif state == "discussion":
        show_tab(page, "discussion")
    elif state == "players":
        show_tab(page, "players")
    elif state == "aide":
        open_aide(page)
    elif state == "menu":
        open_menu(page)
    elif state == "host-settings":
        open_host_settings(page)
    elif state == "banner":
        mock.close(1011)
        expect(page.get_by_test_id("connection-banner")).to_be_visible()


# ---- AC-31: the scans --------------------------------------------------------------


@pytest.mark.parametrize(("size", "state"), SCAN_CASES, ids=SCAN_IDS)
def test_ac31_the_contrast_scan_finds_no_offender(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    state: str,
) -> None:
    page = open_scan_state(window, live_server, fx01_grid, size, state)

    assert contrast_problems(page) == []


@pytest.mark.parametrize(("size", "state"), SCAN_CASES, ids=SCAN_IDS)
def test_ac31_the_language_scan_finds_no_offender(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    state: str,
) -> None:
    page = open_scan_state(window, live_server, fx01_grid, size, state)
    expect(page.locator("html")).to_have_attribute("lang", "fr")

    data = language_data(live_server, DISPLAY_NICKNAMES)

    assert language_problems(page, data) == []


# ---- AC-31: the keys of fr.json ------------------------------------------------------


@pytest.mark.parametrize(("key", "value"), list(NEW_KEYS.items()))
def test_ac31_fr_json_holds_each_new_key(key: str, value: str) -> None:
    assert load_fr().get(key) == value


@pytest.mark.parametrize(("key", "value"), list(CHANGED_KEYS.items()))
def test_ac31_fr_json_holds_each_changed_value(key: str, value: str) -> None:
    assert load_fr().get(key) == value


def test_ac31_fr_json_holds_none_of_the_removed_keys() -> None:
    fr = load_fr()

    present = [key for key in REMOVED_KEYS if key in fr]

    assert present == []
