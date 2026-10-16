"""Tests of spec 028 in browsers on the live server: AC-5 and AC-6.

Two kinds of room. The "live game" tests play a FX-01 room in two browser contexts
(spec 026 AC-3's solve: Ana types the 17 letters other than (4, 4), Bob types `T`
there) and open the share link in a third context. The "stored room" tests serve
`PLAY_R`'s room (Ana and Bob, 754 s, grid 1) from a `RoomStore` through the
`room_registry` fixture overridden below, which is the load-from-the-store path of
spec 018: its recap is known, so the share page's texts can be compared exactly.
Where a test needs a public recap that the stored room does not give (no grid
number, nicknames with markup), the stored room's share page is opened with its API
route answered by `page.route`.

The clipboard check is Chromium only (`only_browser("chromium")`).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Response,
    Route,
    WebSocket,
    expect,
)
from playwright.sync_api import Error as PlaywrightError

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.store import RoomStore
from spec024_harness import LANGUAGE_SCAN_SCRIPT, ROOM_CODE, grid_from_text, load_fr
from spec026_harness import EnterRoom, play_live_game
from spec028_harness import (
    QUIET_MS,
    SHARE_TOKEN,
    format_time,
    share_route,
    stored_play_r,
    traffic_problems,
)
from spec035_harness import contrast_offenders, unknown_texts

SOLVE_TIMEOUT_MS = 15_000


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def room_registry(tmp_path: Path, fx01_grid: Grid) -> Iterator[RoomRegistry]:
    """The registry the live server serves: it loads `PLAY_R`'s room from a file."""
    path = tmp_path / "rooms.db"
    stored_play_r(path, fx01_grid)
    store = RoomStore(path)
    registry = RoomRegistry(store=store)
    yield registry
    registry.close()
    store.close()


def is_text_content_type(content_type: str) -> bool:
    lowered = content_type.lower()
    return "text/" in lowered or "json" in lowered or "javascript" in lowered


def play_live_room(
    browser: Browser,
    live_server: str,
    registry: RoomRegistry,
    grid: Grid,
    enter_room: EnterRoom,
    permissions: list[str] | None = None,
) -> tuple[Page, BrowserContext, BrowserContext, str]:
    """Ana and Bob solve a new FX-01 room; return Ana's page, both contexts, token.

    Args:
        browser: The browser of the test.
        live_server: The live server's base URL.
        registry: The registry the server serves.
        grid: FX-01.
        enter_room: The `enter_room` fixture.
        permissions: Permissions of Ana's context (the clipboard ones).

    Returns:
        Ana's page, her context, Bob's context and the room's share token.
    """
    code = registry.register_room(grid, grid_number=1)
    state = registry.room_state(code)
    assert state is not None
    assert state.share_token is not None
    ana_context = browser.new_context(permissions=permissions)
    bob_context = browser.new_context()
    ana_page = ana_context.new_page()
    bob_page = bob_context.new_page()
    play_live_game(ana_page, bob_page, f"{live_server}/r/{code}", enter_room, "t")
    solved = ana_page.get_by_test_id("room-page")
    expect(solved).to_have_attribute("data-solved", "true", timeout=SOLVE_TIMEOUT_MS)
    return ana_page, ana_context, bob_context, state.share_token


# ---- AC-5: a share link shows the time and the team ----


def test_ac5_ana_s_recap_links_to_the_share_page(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    ana, ana_context, bob_context, token = play_live_room(
        browser, live_server, room_registry, fx01_grid, enter_room
    )
    try:
        ana.get_by_test_id("recap-open").click()

        link = ana.get_by_test_id("recap-share-link")
        expected = f"{live_server}/recap/{token}"
        expect(link).to_have_attribute("href", expected)
        expect(link).to_have_text(expected)
    finally:
        ana_context.close()
        bob_context.close()


def test_ac5_a_third_context_sees_the_team_and_the_time_and_no_room(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    _, ana_context, bob_context, token = play_live_room(
        browser, live_server, room_registry, fx01_grid, enter_room
    )
    third_context = browser.new_context()
    try:
        third = third_context.new_page()
        sockets: list[str] = []
        third.on("websocket", lambda websocket: sockets.append(websocket.url))

        third.goto(f"{live_server}/recap/{token}")

        expect(third.get_by_test_id("recap-page")).to_be_visible()
        expect(third.get_by_test_id("share-team")).to_have_text("Équipe : Ana, Bob")
        shared = third.request.get(f"{live_server}/api/recaps/{token}").json()
        shown = load_fr()["recap.time"].replace(
            "{time}", format_time(shared["elapsed_ms"])
        )
        expect(third.get_by_test_id("share-time")).to_have_text(shown)
        third.wait_for_timeout(QUIET_MS)
        expect(third.get_by_test_id("room-page")).to_have_count(0)
        expect(third.get_by_test_id("nickname-form")).to_have_count(0)
        assert sockets == []
    finally:
        third_context.close()
        ana_context.close()
        bob_context.close()


@pytest.mark.only_browser("chromium")
def test_ac5_the_copy_button_puts_the_share_url_in_the_clipboard(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    ana, ana_context, bob_context, token = play_live_room(
        browser,
        live_server,
        room_registry,
        fx01_grid,
        enter_room,
        permissions=["clipboard-read", "clipboard-write"],
    )
    try:
        ana.get_by_test_id("recap-open").click()
        copy_button = ana.get_by_test_id("recap-copy")

        copy_button.click()

        expect(copy_button).to_have_text(load_fr()["room.share.copied"])
        copied = ana.evaluate("navigator.clipboard.readText()")
        assert copied == f"{live_server}/recap/{token}"
    finally:
        ana_context.close()
        bob_context.close()


def test_ac5_the_stored_room_s_share_page_shows_all_its_parts(
    page: Page, live_server: str
) -> None:
    fr = load_fr()

    page.goto(f"{live_server}/recap/{SHARE_TOKEN}")

    expect(page.get_by_test_id("recap-page")).to_be_visible()
    expect(page.locator("h1")).to_have_text(fr["share.heading"])
    expect(page.get_by_test_id("share-grid")).to_have_text("Grille n° 1")
    expect(page.get_by_test_id("share-time")).to_have_text("Temps : 12:34")
    expect(page.get_by_test_id("share-team")).to_have_text("Équipe : Ana, Bob")
    home = page.get_by_test_id("share-home")
    expect(home).to_have_text(fr["share.home"])
    expect(home).to_have_attribute("href", "/")
    expect(page.get_by_test_id("recap-loading")).to_have_count(0)
    expect(page.get_by_test_id("share-error")).to_have_count(0)
    assert page.title() == fr["app.title"]
    assert ROOM_CODE not in page.content()


def test_ac5_the_share_page_stores_nothing_and_opens_no_socket(
    page: Page, live_server: str
) -> None:
    sockets: list[str] = []
    page.on("websocket", lambda websocket: sockets.append(websocket.url))

    page.goto(f"{live_server}/recap/{SHARE_TOKEN}")
    expect(page.get_by_test_id("share-team")).to_be_visible()
    page.wait_for_timeout(QUIET_MS)

    assert sockets == []
    assert page.evaluate("window.localStorage.length") == 0


def test_ac5_the_share_page_shows_loading_until_the_answer(
    page: Page, live_server: str
) -> None:
    held: list[Route] = []
    page.route(f"**/api/recaps/{SHARE_TOKEN}", lambda route: held.append(route))

    page.goto(f"{live_server}/recap/{SHARE_TOKEN}")

    expect(page.get_by_test_id("recap-loading")).to_have_text("Chargement du bilan…")
    expect(page.get_by_test_id("share-team")).to_have_count(0)
    while not held:
        page.wait_for_timeout(50)
    held[0].continue_()
    expect(page.get_by_test_id("share-team")).to_have_text("Équipe : Ana, Bob")
    expect(page.get_by_test_id("recap-loading")).to_have_count(0)


def test_ac5_a_failed_request_shows_the_share_error(
    page: Page, live_server: str
) -> None:
    page.route(
        f"**/api/recaps/{SHARE_TOKEN}",
        lambda route: route.fulfill(
            status=500, content_type="application/json", body="{}"
        ),
    )

    page.goto(f"{live_server}/recap/{SHARE_TOKEN}")

    error = page.get_by_test_id("share-error")
    expect(error).to_have_text("Ce bilan n'est pas disponible.")
    expect(page.get_by_test_id("share-team")).to_have_count(0)


def test_ac5_without_a_grid_number_the_share_page_shows_no_grid(
    page: Page, live_server: str
) -> None:
    body = {"grid_number": None, "elapsed_ms": 754_000, "team": ["Ana", "Bob"]}
    share_route(page, SHARE_TOKEN, body)

    page.goto(f"{live_server}/recap/{SHARE_TOKEN}")

    expect(page.get_by_test_id("share-team")).to_have_text("Équipe : Ana, Bob")
    expect(page.get_by_test_id("share-time")).to_have_text("Temps : 12:34")
    expect(page.get_by_test_id("share-grid")).to_have_count(0)


def test_ac5_a_link_to_a_room_that_does_not_exist_is_a_404(
    page: Page, live_server: str
) -> None:
    response = page.goto(f"{live_server}/recap/tok_unknown_0123456789")

    assert response is not None
    assert response.status == 404


# ---- AC-6: the share link shows no letter of the solution ----


def test_ac6_everything_the_share_page_receives_passes_the_three_rules(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    _, ana_context, bob_context, token = play_live_room(
        browser, live_server, room_registry, fx01_grid, enter_room
    )
    third_context = browser.new_context()
    try:
        third = third_context.new_page()
        responses: list[Response] = []
        frames: list[str] = []

        def keep_frame(payload: str | bytes) -> None:
            text = payload if isinstance(payload, str) else payload.decode("utf-8")
            frames.append(text)

        def watch_socket(websocket: WebSocket) -> None:
            websocket.on("framereceived", keep_frame)

        third.on("websocket", watch_socket)
        third.on("response", lambda response: responses.append(response))

        third.goto(f"{live_server}/recap/{token}")
        expect(third.get_by_test_id("share-team")).to_be_visible()
        third.wait_for_timeout(QUIET_MS)

        bodies: dict[str, str] = {}
        for response in responses:
            content_type = response.headers.get("content-type", "")
            if not is_text_content_type(content_type):
                continue
            try:
                bodies[response.url] = response.body().decode("utf-8")
            except PlaywrightError:
                continue  # the browser no longer holds this body
    finally:
        third_context.close()
        ana_context.close()
        bob_context.close()

    api_url = f"{live_server}/api/recaps/{token}"
    assert api_url in bodies
    assert sorted(json.loads(bodies[api_url])) == ["elapsed_ms", "grid_number", "team"]
    for url, body in bodies.items():
        assert traffic_problems(body) == [], url
    for frame in frames:
        assert traffic_problems(frame) == [], frame
    assert frames == []


def test_ac6_the_stored_room_s_share_page_receives_only_the_public_recap(
    page: Page, live_server: str
) -> None:
    responses: list[Response] = []
    page.on("response", lambda response: responses.append(response))

    page.goto(f"{live_server}/recap/{SHARE_TOKEN}")
    expect(page.get_by_test_id("share-team")).to_be_visible()

    api_urls = [r.url for r in responses if "/api/" in r.url]
    assert api_urls == [f"{live_server}/api/recaps/{SHARE_TOKEN}"]
    body = responses[[r.url for r in responses].index(api_urls[0])].json()
    assert body == {"grid_number": 1, "elapsed_ms": 754000, "team": ["Ana", "Bob"]}


# ---- AC-10: the share page is accessible and shows nicknames as text ----

SCAN_SIZES = [(1280, 720), (360, 740)]
HOSTILE_NAMES = ["<b>Eve</b>", "<img src=x>"]
SCAN_IDS = ["1280x720", "360x740"]


def open_share_page(page: Page, live_server: str, team: list[str]) -> None:
    """Open the stored room's share page, its API route answered by the test."""
    body = {"grid_number": 1, "elapsed_ms": 754_000, "team": team}
    share_route(page, SHARE_TOKEN, body)
    page.goto(f"{live_server}/recap/{SHARE_TOKEN}")
    expect(page.get_by_test_id("share-team")).to_be_visible()


@pytest.mark.parametrize(
    ("width", "height"), SCAN_SIZES, ids=[f"{w}x{h}" for w, h in SCAN_SIZES]
)
def test_ac10_the_share_page_has_no_contrast_offender(
    browser: Browser, live_server: str, width: int, height: int
) -> None:
    context = browser.new_context(viewport={"width": width, "height": height})
    try:
        page = context.new_page()
        open_share_page(page, live_server, ["Ana", "Bob"])

        offenders = contrast_offenders(page)
    finally:
        context.close()

    assert offenders == []


@pytest.mark.parametrize(
    ("width", "height"), SCAN_SIZES, ids=[f"{w}x{h}" for w, h in SCAN_SIZES]
)
def test_ac10_the_share_page_has_no_text_outside_fr_json_and_the_test_data(
    browser: Browser, live_server: str, width: int, height: int
) -> None:
    context = browser.new_context(viewport={"width": width, "height": height})
    try:
        page = context.new_page()
        open_share_page(page, live_server, ["Ana", "Bob"])

        texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    finally:
        context.close()

    data = {"Ana", "Bob", f"{live_server}/recap/{SHARE_TOKEN}"}
    assert len(texts) > 0
    assert unknown_texts(texts, data) == []


def test_ac10_nicknames_with_markup_show_as_text_on_the_share_page(
    page: Page, live_server: str
) -> None:
    open_share_page(page, live_server, HOSTILE_NAMES)

    team = page.get_by_test_id("share-team")
    expect(team).to_have_text("Équipe : <b>Eve</b>, <img src=x>")
    page_box = page.get_by_test_id("recap-page")
    expect(page_box.locator("b")).to_have_count(0)
    expect(page_box.locator("img")).to_have_count(0)
