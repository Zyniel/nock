"""Tests of spec 033, AC-5: other players then see "former player".

The play of AC-4 on the live server of the "Test harness", in room R: `Bob` enters
first, so he is host, then `Zélie-Probe`, who writes `T` at (1, 0), asks a link
from the room's account dialog and opens it in a new page of her device. There she
deletes her account: `account-delete` shows the warning, and only
`account-delete-confirm` sends the deletion, after which the page is `deleted`;
`account-delete-cancel` keeps the account.

Then Bob's page, reloaded, names her `Ancien joueur` in the roster and in the
`aria-label` of her remove button; after Zélie, still in the room as a guest,
checks a word, Bob's feed reads `Ancien joueur a vérifié un mot`; on `/`, his "My
rooms" item of R reads `Joueurs : Bob, Ancien joueur`; and once R is solved, spec
028's recap names her `Ancien joueur`. No page shows `--`.

Each test runs the play up to the deletion, then checks one of these. Room S and
the unused link of AC-4 change nothing that these pages show, so they are left out
here; AC-4 checks them. The shared setup is in `spec033_harness`, `spec032_harness`
("My rooms") and `spec024_harness` (the catalogue).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Page, Request, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec011_harness import EnterRoom
from spec024_harness import make_catalogue
from spec032_harness import expect_my_rooms_ready, grid_from_text, my_room_items
from spec033_harness import (
    ACCOUNT_PATH,
    FORMER_NICKNAME,
    FORMER_PLAYER_TEXT,
    WAIT_TIMEOUT_MS,
    ZELIE_EMAIL,
    AccountServer,
    Devices,
    account_live_server,
    account_page,
    ask_link_in_form,
    cell_at,
    expect_account_state,
    link_in,
    load_fr,
    open_account_dialog,
    room_page,
    roster_item,
    sign_in_with_link,
    type_letter,
    wait_for_messages,
    you_of,
)

ZELIE_NICKNAME = "Zélie-Probe"
# The letters of FX-01 other than the `T` at (1, 0), word by word.
OTHER_LETTERS: list[tuple[int, int, str]] = [
    (1, 1, "a"),
    (1, 2, "m"),
    (1, 3, "i"),
    (1, 4, "s"),
    (0, 1, "n"),
    (2, 1, "v"),
    (3, 1, "a"),
    (4, 1, "l"),
    (2, 2, "i"),
    (3, 2, "m"),
    (4, 2, "e"),
    (2, 3, "d"),
    (3, 3, "e"),
    (4, 3, "s"),
    (2, 4, "e"),
    (3, 4, "n"),
    (4, 4, "t"),
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def account_server(tmp_path: Path, fx01_grid: Grid) -> Iterator[AccountServer]:
    catalogue: Catalogue = make_catalogue(fx01_grid)
    with account_live_server(tmp_path, catalogue) as server:
        yield server


@pytest.fixture
def devices(browser: Browser) -> Iterator[Devices]:
    opened = Devices(browser)
    yield opened
    opened.close()


class SignedIn(NamedTuple):
    """Room R with Bob (host) and Zélie, and Zélie's account page, signed in."""

    code: str
    bob: Page
    zelie: Page
    zelie_id: str
    account: Page


def zelie_signs_in(
    server: AccountServer, devices: Devices, grid: Grid, enter_room: EnterRoom
) -> SignedIn:
    """Bob, then Zélie, enter R; Zélie writes `T`, asks a link and opens it."""
    code = server.registry.register_room(grid, grid_number=1)
    room_url = f"{server.base_url}/r/{code}"
    bob = devices.new().new_page()
    enter_room(bob, room_url, "Bob")
    zelie_context = devices.new()
    zelie = zelie_context.new_page()
    enter_room(zelie, room_url, ZELIE_NICKNAME)
    zelie_id = you_of(zelie)
    type_letter(zelie, 1, 0, "t")
    expect(cell_at(zelie, 1, 0)).to_have_attribute("data-letter", "T")
    open_account_dialog(zelie)
    ask_link_in_form(zelie, ZELIE_EMAIL)
    wait_for_messages(server.mailer, 1)
    zelie.keyboard.press("Escape")
    account = zelie_context.new_page()
    sign_in_with_link(account, link_in(server.base_url, server.mailer.messages[0]))
    return SignedIn(code, bob, zelie, zelie_id, account)


def zelie_deletes(
    server: AccountServer, devices: Devices, grid: Grid, enter_room: EnterRoom
) -> SignedIn:
    """AC-5's play up to the `deleted` state of Zélie's account page."""
    signed_in = zelie_signs_in(server, devices, grid, enter_room)
    account = signed_in.account
    account.get_by_test_id("account-delete").click()
    account.get_by_test_id("account-delete-confirm").click()
    expect_account_state(account, "deleted")
    return signed_in


def shows_no_dashes(page: Page) -> bool:
    text = page.inner_text("body")
    return FORMER_NICKNAME not in text


def reload_bob(play: SignedIn) -> None:
    """Reload Bob's room page and wait until it is joined with two players."""
    play.bob.reload()
    expect(room_page(play.bob)).to_have_attribute(
        "data-status", "joined", timeout=WAIT_TIMEOUT_MS
    )
    expect(play.bob.get_by_test_id("roster-player")).to_have_count(2)


# ---- The account page -----------------------------------------------------------


def test_ac5_account_delete_shows_the_warning_and_the_two_choices(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    play = zelie_signs_in(account_server, devices, fx01_grid, enter_room)
    fr = load_fr()

    play.account.get_by_test_id("account-delete").click()

    warning = play.account.get_by_test_id("account-delete-warning")
    expect(warning).to_have_text(fr["account.delete_warning"])
    confirm = play.account.get_by_test_id("account-delete-confirm")
    expect(confirm).to_have_text(fr["account.delete_confirm"])
    cancel = play.account.get_by_test_id("account-delete-cancel")
    expect(cancel).to_have_text(fr["account.delete_cancel"])


def test_ac5_the_confirm_deletes_and_the_page_says_so(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    play = zelie_deletes(account_server, devices, fx01_grid, enter_room)

    deleted_text = load_fr()["account.deleted"]
    assert deleted_text == "Votre compte a été supprimé."
    expect(account_page(play.account)).to_contain_text(deleted_text)
    status = play.account.request.get(f"{account_server.base_url}{ACCOUNT_PATH}")
    assert status.json() == {"signed_in": False, "email": None}


def test_ac5_the_cancel_keeps_the_account_and_sends_no_deletion(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    play = zelie_signs_in(account_server, devices, fx01_grid, enter_room)
    deletions: list[str] = []

    def keep_deletion(request: Request) -> None:
        if request.method == "DELETE":
            deletions.append(request.url)

    play.account.on("request", keep_deletion)

    play.account.get_by_test_id("account-delete").click()
    play.account.get_by_test_id("account-delete-cancel").click()
    play.account.wait_for_timeout(500)

    status = play.account.request.get(f"{account_server.base_url}{ACCOUNT_PATH}")
    assert status.json() == {"signed_in": True, "email": ZELIE_EMAIL}
    assert deletions == []
    expect_account_state(play.account, "signed_in")


# ---- Bob's room page ------------------------------------------------------------


def test_ac5_bobs_reloaded_roster_names_her_ancien_joueur(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    play = zelie_deletes(account_server, devices, fx01_grid, enter_room)

    reload_bob(play)

    row = roster_item(play.bob, play.zelie_id)
    expect(row.get_by_test_id("roster-nickname")).to_have_text(FORMER_PLAYER_TEXT)
    assert shows_no_dashes(play.bob)


def test_ac5_her_remove_button_is_labelled_with_ancien_joueur(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    play = zelie_deletes(account_server, devices, fx01_grid, enter_room)

    reload_bob(play)

    button = roster_item(play.bob, play.zelie_id).get_by_test_id("remove-player")
    expect(button).to_have_attribute("aria-label", "Retirer Ancien joueur du salon")


def test_ac5_her_word_check_reads_ancien_joueur_in_bobs_feed(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    play = zelie_deletes(account_server, devices, fx01_grid, enter_room)
    reload_bob(play)

    cell_at(play.zelie, 1, 0).click()
    play.zelie.get_by_test_id("check-word").click()

    feed = play.bob.get_by_test_id("activity-feed")
    line = feed.get_by_text("Ancien joueur a vérifié un mot", exact=True)
    expect(line).to_have_count(1, timeout=WAIT_TIMEOUT_MS)
    assert shows_no_dashes(play.bob)


def test_ac5_bobs_my_rooms_names_her_ancien_joueur(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    play = zelie_deletes(account_server, devices, fx01_grid, enter_room)

    play.bob.goto(f"{account_server.base_url}/")

    expect_my_rooms_ready(play.bob, 1)
    item = my_room_items(play.bob)
    expect(item).to_have_attribute("data-code", play.code)
    players = item.get_by_test_id("my-room-players")
    expect(players).to_have_text("Joueurs : Bob, Ancien joueur")
    assert shows_no_dashes(play.bob)


def test_ac5_the_recap_names_her_ancien_joueur(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    play = zelie_deletes(account_server, devices, fx01_grid, enter_room)
    reload_bob(play)

    for row, column, key in OTHER_LETTERS:
        type_letter(play.bob, row, column, key)
    expect(room_page(play.bob)).to_have_attribute(
        "data-solved", "true", timeout=WAIT_TIMEOUT_MS
    )
    play.bob.get_by_test_id("recap-open").click()
    expect(play.bob.get_by_test_id("recap")).to_be_visible(timeout=WAIT_TIMEOUT_MS)

    selector = f'[data-testid="recap-player"][data-player-id="{play.zelie_id}"]'
    row = play.bob.locator(selector)
    expect(row.get_by_test_id("recap-name")).to_have_text(FORMER_PLAYER_TEXT)
    assert shows_no_dashes(play.bob)
