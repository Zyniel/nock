"""Tests of spec 033, AC-3: no action needed to finish a grid requires an account.

On the live server of the "Test harness", with accounts on: a page in a fresh
context (no cookie, no storage) opens the room link of a FX-01 room, enters as
`Ana` and types the 18 letters word by word, with `X` in place of `I` at (2, 2),
60 ms or more between keys (spec 037's harness). She selects the word `MIME`,
presses `check-word` (spec 023), types `I` at (2, 2), and the grid is solved (spec
026). No response had status 401 or 403 or a `set-cookie` header, the context has
no cookie, `account-dialog` never had the `open` attribute, and every frame the
page sent parses with `parse_client_message` (spec 039 has no account field).

The whole play runs once per test; each test checks one of these outcomes. The
shared setup is in `spec033_harness` and `spec024_harness` (the catalogue).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Page, Response, WebSocket, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import parse_client_message
from room_panels import open_aide
from spec011_harness import EnterRoom
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import (
    WAIT_TIMEOUT_MS,
    AccountServer,
    account_live_server,
    cell_at,
    room_page,
    state_of,
    type_letter,
)

# The 18 letters word by word: TAMIS, NAVAL, MIME, IDES, SENT, then VIDE, AMEN and
# LEST through the crossing letters, with X in place of I at (2, 2).
GAME_WITH_X: list[tuple[int, int, str]] = [
    (1, 0, "t"),
    (1, 1, "a"),
    (1, 2, "m"),
    (1, 3, "i"),
    (1, 4, "s"),
    (0, 1, "n"),
    (2, 1, "v"),
    (3, 1, "a"),
    (4, 1, "l"),
    (2, 2, "x"),
    (3, 2, "m"),
    (4, 2, "e"),
    (2, 3, "d"),
    (3, 3, "e"),
    (4, 3, "s"),
    (2, 4, "e"),
    (3, 4, "n"),
    (4, 4, "t"),
]
MIME_WORD = "0,2,0"  # the `data-word` of MIME: its clue cell (0, 2), clue 0
MAX_CLICKS = 3

# Sets `window.__accountDialogOpened` once an `account-dialog` has `open`.
DIALOG_WATCHER = (
    "window.__accountDialogOpened = false;"
    "const watchDialog = () => {"
    " for (const dialog of document.querySelectorAll("
    "'[data-testid=\"account-dialog\"]')) {"
    " if (dialog.hasAttribute('open')) { window.__accountDialogOpened = true; } } };"
    "new MutationObserver(watchDialog).observe(document, {"
    " childList: true, subtree: true, attributes: true,"
    " attributeFilter: ['open'] });"
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def account_server(tmp_path: Path, fx01_grid: Grid) -> Iterator[AccountServer]:
    catalogue: Catalogue = make_catalogue(fx01_grid)
    with account_live_server(tmp_path, catalogue) as server:
        yield server


class Finished(NamedTuple):
    """What a guest's play left: its room, its traffic and its cookies."""

    code: str
    refused: list[tuple[str, int]]  # the URL and status of each 401 or 403
    cookie_setters: list[str]  # the URL of each response with `set-cookie`
    sent_frames: list[str]
    cookie_count: int
    dialog_opened: object


def select_mime(page: Page) -> None:
    """Click (2, 2) until the selected word is MIME (down from (1, 2))."""
    grid = page.get_by_test_id("grid")
    for _ in range(MAX_CLICKS):
        cell_at(page, 2, 2).click()
        if grid.get_attribute("data-word") == MIME_WORD:
            return
    expect(grid).to_have_attribute("data-word", MIME_WORD)


def guest_solves(
    browser: Browser, server: AccountServer, grid: Grid, enter_room: EnterRoom
) -> Finished:
    """AC-3's play, in a fresh context, up to the solved grid."""
    code = server.registry.register_room(grid, grid_number=1)
    context = browser.new_context()
    try:
        page = context.new_page()
        responses: list[Response] = []
        sent_frames: list[str] = []

        def keep_sent(payload: str | bytes) -> None:
            text = payload if isinstance(payload, str) else payload.decode("utf-8")
            sent_frames.append(text)

        def watch_socket(websocket: WebSocket) -> None:
            websocket.on("framesent", keep_sent)

        def keep_response(response: Response) -> None:
            responses.append(response)

        page.on("response", keep_response)
        page.on("websocket", watch_socket)
        page.add_init_script(DIALOG_WATCHER)

        enter_room(page, f"{server.base_url}/r/{code}", "Ana")
        for row, column, key in GAME_WITH_X:
            type_letter(page, row, column, key)
        expect(cell_at(page, 4, 4)).to_have_attribute("data-letter", "T")
        select_mime(page)
        open_aide(page)  # spec 043: the item is in a panel, opened first
        page.get_by_test_id("check-word").click()
        expect(cell_at(page, 2, 2)).to_have_attribute(
            "data-wrong", "true", timeout=WAIT_TIMEOUT_MS
        )
        type_letter(page, 2, 2, "i")
        expect(room_page(page)).to_have_attribute(
            "data-solved", "true", timeout=WAIT_TIMEOUT_MS
        )
        expect(page.get_by_test_id("grid-status")).to_have_attribute(
            "data-state", "solved", timeout=WAIT_TIMEOUT_MS
        )
        dialog_opened = page.evaluate("() => window.__accountDialogOpened")
        cookie_count = len(context.cookies())
        refused: list[tuple[str, int]] = []
        cookie_setters: list[str] = []
        for response in responses:
            if response.status in (401, 403):
                refused.append((response.url, response.status))
            if response.header_value("set-cookie") is not None:
                cookie_setters.append(response.url)
    finally:
        context.close()
    return Finished(
        code, refused, cookie_setters, sent_frames, cookie_count, dialog_opened
    )


def test_ac3_a_guest_solves_the_grid_with_accounts_on(
    browser: Browser,
    account_server: AccountServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    finished = guest_solves(browser, account_server, fx01_grid, enter_room)

    assert state_of(account_server.registry, finished.code).solved is True


def test_ac3_no_response_was_401_or_403(
    browser: Browser,
    account_server: AccountServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    finished = guest_solves(browser, account_server, fx01_grid, enter_room)

    assert finished.refused == []


def test_ac3_no_response_set_a_cookie_and_the_context_has_none(
    browser: Browser,
    account_server: AccountServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    finished = guest_solves(browser, account_server, fx01_grid, enter_room)

    assert finished.cookie_setters == []
    assert finished.cookie_count == 0


def test_ac3_the_account_dialog_never_opened(
    browser: Browser,
    account_server: AccountServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    finished = guest_solves(browser, account_server, fx01_grid, enter_room)

    assert finished.dialog_opened is False


def test_ac3_every_frame_the_page_sent_is_a_protocol_message(
    browser: Browser,
    account_server: AccountServer,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    finished = guest_solves(browser, account_server, fx01_grid, enter_room)

    unparsable: list[str] = []
    for frame in finished.sent_frames:
        try:
            parse_client_message(frame)
        except ValueError:
            unparsable.append(frame)
    assert len(finished.sent_frames) > 0
    assert unparsable == []
