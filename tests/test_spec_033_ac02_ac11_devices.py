"""Tests of spec 033, AC-2 and the browser part of AC-11: two devices, one account.

On the live server of the "Test harness" (accounts on, the recording mailer, both
stores on one file, the built client). Each device is a browser context, with its
own storage and cookies.

AC-2: device 1 enters a FX-01 room as `Ana`, types `T` at (1, 0), asks a link from
the room's account dialog and opens it in a new page: the account page signs her in
and links back to the room, and her room page keeps its seat, colour and letter.
Device 2, with empty storage, signs in from `/account` with the same address: it
stores Ana's identity of the room, opens the room as Ana without the nickname
form, and device 1's page is `replaced` (spec 012).

AC-11 (browser): device 2, once signed in, lists Ana's room in "My rooms" on `/`,
whose `account-link` points to `/account`; its room page sends one
`PUT /api/account/rooms` with its code and token after its first snapshot.

Edge case checked as well: an identity already stored on a device is never
replaced, neither by the sign-in nor by the catalogue page.

The shared setup is in `spec033_harness`, `spec032_harness` ("My rooms" and the
nickname form watcher) and `spec024_harness` (the catalogue).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Request,
    WebSocket,
    expect,
)
from playwright.sync_api import Response as PageResponse

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec011_harness import EnterRoom
from spec024_harness import make_catalogue
from spec032_harness import (
    FORM_WATCHER,
    expect_my_rooms_ready,
    grid_from_text,
    my_room_items,
    seed_storage,
)
from spec033_harness import (
    ACCOUNT_PAGE_PATH,
    ANA_EMAIL,
    ROOMS_PATH,
    SIGN_IN_PATH,
    WAIT_TIMEOUT_MS,
    AccountServer,
    Devices,
    account_live_server,
    ask_link_in_form,
    cell_at,
    cell_state,
    expect_account_state,
    link_in,
    open_account_dialog,
    room_page,
    roster_item,
    sign_in_with_link,
    state_of,
    stored_identity,
    type_letter,
    wait_for_messages,
    you_of,
)

QUIET_MS = 1000  # "sends one": no second request within this pause


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


class DeviceOne(NamedTuple):
    """Device 1 in the room: Ana's room page, her id and her roster colour."""

    code: str
    context: BrowserContext
    page: Page
    you: str
    colour: str | None


def ana_writes_t(
    server: AccountServer, devices: Devices, grid: Grid, enter_room: EnterRoom
) -> DeviceOne:
    """Device 1 enters a new FX-01 room as Ana and types `T` at (1, 0)."""
    code = server.registry.register_room(grid, grid_number=1)
    context = devices.new()
    page = context.new_page()
    enter_room(page, f"{server.base_url}/r/{code}", "Ana")
    type_letter(page, 1, 0, "t")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    you = you_of(page)
    colour = roster_item(page, you).get_attribute("data-colour")
    return DeviceOne(code, context, page, you, colour)


def ana_asks_a_link(server: AccountServer, device: DeviceOne) -> None:
    """Device 1 asks a link from the room's account dialog."""
    open_account_dialog(device.page)
    ask_link_in_form(device.page, ANA_EMAIL)
    expect(device.page.get_by_test_id("account-sent")).to_be_visible(
        timeout=WAIT_TIMEOUT_MS
    )
    wait_for_messages(server.mailer, 1)


def ana_opens_the_link(server: AccountServer, device: DeviceOne) -> Page:
    """A new page of device 1 opens the link of the first message."""
    link = link_in(server.base_url, server.mailer.messages[0])
    account = device.context.new_page()
    sign_in_with_link(account, link)
    return account


def device_two_signs_in(server: AccountServer, devices: Devices) -> Page:
    """Device 2 signs in from `/account` with Ana's address."""
    page = devices.new().new_page()
    page.goto(f"{server.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(page, "signed_out")
    sent_before = len(server.mailer.messages)
    ask_link_in_form(page, ANA_EMAIL)
    wait_for_messages(server.mailer, sent_before + 1)
    sign_in_with_link(page, link_in(server.base_url, server.mailer.messages[-1]))
    return page


# ---- AC-2: device 1 asks a link from the room -----------------------------------


def test_ac2_the_dialog_opens_with_the_focus_on_the_address(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)

    open_account_dialog(device.page)

    expect(device.page.get_by_test_id("account-email-input")).to_be_focused()


def test_ac2_the_dialog_shows_where_the_link_was_sent(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)

    ana_asks_a_link(account_server, device)

    expect(device.page.get_by_test_id("account-sent")).to_have_text(
        "Lien envoyé à ana.probe@example.org. Il est valable 30 minutes."
    )
    assert len(account_server.mailer.messages) == 1
    assert account_server.mailer.messages[0]["To"] == ANA_EMAIL


def test_ac2_the_dialog_sends_the_address_and_the_rooms_key(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    identity = stored_identity(device.page, device.code)
    assert identity is not None
    bodies: list[object] = []

    def keep_link_request(request: Request) -> None:
        if request.method == "POST" and request.url.endswith("/api/account/link"):
            bodies.append(json.loads(request.post_data or "null"))

    device.page.on("request", keep_link_request)
    ana_asks_a_link(account_server, device)

    room = {"code": device.code, "resume_token": identity["resume_token"]}
    assert bodies == [{"email": ANA_EMAIL, "room": room}]


# ---- AC-2: device 1 opens the link ----------------------------------------------


def test_ac2_the_link_signs_device_1_in_and_shows_the_address(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)

    account = ana_opens_the_link(account_server, device)

    expect(account.get_by_test_id("account-email")).to_have_text(
        "Connecté avec ana.probe@example.org"
    )


def test_ac2_the_account_page_drops_the_token_from_its_url(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)

    account = ana_opens_the_link(account_server, device)

    assert account.url == f"{account_server.base_url}{ACCOUNT_PAGE_PATH}"
    assert account.evaluate("() => location.hash") == ""


def test_ac2_the_account_page_links_back_to_the_room(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)

    account = ana_opens_the_link(account_server, device)

    link = account.get_by_test_id("account-room-link")
    expect(link).to_have_attribute("href", f"/r/{device.code}")


def test_ac2_device_1_keeps_its_seat_colour_and_letter(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)

    ana_opens_the_link(account_server, device)

    expect(room_page(device.page)).to_have_attribute("data-status", "joined")
    expect(room_page(device.page)).to_have_attribute("data-you", device.you)
    roster_row = roster_item(device.page, device.you)
    expect(roster_row).to_have_attribute("data-colour", device.colour or "")
    state = state_of(account_server.registry, device.code)
    cell = cell_state(state, 1, 0)
    assert (cell.letter, cell.author) == ("T", device.you)


# ---- AC-2: device 2 -------------------------------------------------------------


def test_ac2_device_2_stores_anas_identity_of_the_room(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)
    ana_opens_the_link(account_server, device)
    anas_identity = stored_identity(device.page, device.code)
    assert anas_identity is not None

    second = device_two_signs_in(account_server, devices)

    identity = stored_identity(second, device.code)
    assert identity is not None
    assert identity["player_id"] == anas_identity["player_id"] == device.you
    assert identity["resume_token"] == anas_identity["resume_token"]


def test_ac2_device_2_opens_the_room_as_ana_without_the_nickname_form(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)
    ana_opens_the_link(account_server, device)
    second = device_two_signs_in(account_server, devices)
    second.add_init_script(FORM_WATCHER)

    second.goto(f"{account_server.base_url}/r/{device.code}")

    expect(room_page(second)).to_have_attribute(
        "data-status", "joined", timeout=WAIT_TIMEOUT_MS
    )
    expect(room_page(second)).to_have_attribute("data-you", device.you)
    assert second.evaluate("() => window.__formSeen") is False
    roster_row = roster_item(second, device.you)
    expect(roster_row.get_by_test_id("roster-nickname")).to_have_text("Ana")
    expect(roster_row).to_have_attribute("data-colour", device.colour or "")


def test_ac2_device_1_is_then_replaced(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)
    ana_opens_the_link(account_server, device)
    second = device_two_signs_in(account_server, devices)

    second.goto(f"{account_server.base_url}/r/{device.code}")
    expect(room_page(second)).to_have_attribute(
        "data-status", "joined", timeout=WAIT_TIMEOUT_MS
    )

    expect(room_page(device.page)).to_have_attribute(
        "data-status", "replaced", timeout=WAIT_TIMEOUT_MS
    )


def test_ac2_device_2_sends_no_room_from_the_account_page(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    ana_writes_t(account_server, devices, fx01_grid, enter_room)
    page = devices.new().new_page()

    def is_link_request(request: Request) -> bool:
        return request.method == "POST" and request.url.endswith("/api/account/link")

    page.goto(f"{account_server.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(page, "signed_out")

    # The request is read through Playwright: the mailer wait below does not
    # call it, so a "request" handler could still be pending after that wait.
    with page.expect_request(is_link_request) as request_info:
        ask_link_in_form(page, ANA_EMAIL)
    wait_for_messages(account_server.mailer, 1)

    assert request_info.value.post_data_json == {"email": ANA_EMAIL, "room": None}


# ---- AC-11 (browser) ------------------------------------------------------------


def test_ac11_device_2_lists_anas_room_in_my_rooms(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)
    ana_opens_the_link(account_server, device)
    second = device_two_signs_in(account_server, devices)

    second.goto(f"{account_server.base_url}/")

    expect_my_rooms_ready(second, 1)
    expect(my_room_items(second)).to_have_attribute("data-code", device.code)


def test_ac11_the_catalogue_links_to_the_account_page(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)
    ana_opens_the_link(account_server, device)
    second = device_two_signs_in(account_server, devices)

    second.goto(f"{account_server.base_url}/")

    link = second.get_by_test_id("account-link")
    expect(link).to_have_attribute("href", ACCOUNT_PAGE_PATH, timeout=WAIT_TIMEOUT_MS)
    expect(link).to_have_text("Compte")


class PageTraffic:
    """The snapshots a page received and the account PUTs it sent, in order."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.put_bodies: list[object] = []

    def watch(self, page: Page) -> None:
        page.on("websocket", self._watch_socket)
        page.on("request", self._keep_request)

    def _watch_socket(self, websocket: WebSocket) -> None:
        websocket.on("framereceived", self._keep_frame)

    def _keep_frame(self, payload: str | bytes) -> None:
        text = payload if isinstance(payload, str) else payload.decode("utf-8")
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("type") == "snapshot":
            self.events.append("snapshot")

    def _keep_request(self, request: Request) -> None:
        if request.method == "PUT" and request.url.endswith(ROOMS_PATH):
            self.events.append("put")
            self.put_bodies.append(json.loads(request.post_data or "null"))


def test_ac11_a_signed_in_room_page_sends_one_put_after_its_first_snapshot(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    ana_asks_a_link(account_server, device)
    ana_opens_the_link(account_server, device)
    second = device_two_signs_in(account_server, devices)
    traffic = PageTraffic()
    traffic.watch(second)

    second.goto(f"{account_server.base_url}/r/{device.code}")
    expect(room_page(second)).to_have_attribute(
        "data-status", "joined", timeout=WAIT_TIMEOUT_MS
    )
    deadline = time.monotonic() + WAIT_TIMEOUT_MS / 1000
    while "put" not in traffic.events and time.monotonic() < deadline:
        second.wait_for_timeout(50)
    second.wait_for_timeout(QUIET_MS)

    identity = stored_identity(second, device.code)
    assert identity is not None
    key = {"code": device.code, "resume_token": identity["resume_token"]}
    assert traffic.put_bodies == [key]
    assert traffic.events.index("snapshot") < traffic.events.index("put")


def test_ac11_an_identity_on_the_device_is_never_replaced(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    device = ana_writes_t(account_server, devices, fx01_grid, enter_room)
    # Ana's account gets her identity of the room, which a sign-in then serves.
    ana_asks_a_link(account_server, device)
    ana_opens_the_link(account_server, device)
    bob_page = devices.new().new_page()
    enter_room(bob_page, f"{account_server.base_url}/r/{device.code}", "Bob")
    bobs_identity = stored_identity(bob_page, device.code)
    assert bobs_identity is not None
    third = devices.new().new_page()
    seed_storage(third, {f"nock.identity.{device.code}": json.dumps(bobs_identity)})
    sign_in_answers: list[object] = []

    def keep_sign_in_answer(response: PageResponse) -> None:
        if response.request.method == "POST" and response.url.endswith(SIGN_IN_PATH):
            sign_in_answers.append(response.json())

    third.on("response", keep_sign_in_answer)
    third.goto(f"{account_server.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(third, "signed_out")
    ask_link_in_form(third, ANA_EMAIL)
    wait_for_messages(account_server.mailer, 2)
    sign_in_with_link(
        third, link_in(account_server.base_url, account_server.mailer.messages[-1])
    )
    after_sign_in = stored_identity(third, device.code)

    third.goto(f"{account_server.base_url}/")
    expect_my_rooms_ready(third, 1)

    assert len(sign_in_answers) == 1
    answer = sign_in_answers[0]
    assert isinstance(answer, dict)
    served = [(room["code"], room["player_id"]) for room in answer["rooms"]]
    assert served == [(device.code, device.you)]
    assert after_sign_in == bobs_identity
    assert stored_identity(third, device.code) == bobs_identity
