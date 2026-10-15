"""Tests of spec 037 (integrity), AC-4: escaping.

AC-4 checks the escaping: a static scan of `web/src`, the server's refusal of tags
in nicknames, and the room page with a mocked socket. The shared setup is in
`spec037_harness`.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Dialog, Page, WebSocketRoute, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClueCellView,
    ErrorCode,
    ErrorMessage,
    GridView,
    HelpMode,
    Join,
    PlayerState,
    PlayerView,
    RevealBudget,
    RoomSettings,
    Snapshot,
    grid_view,
)
from nock.server import create_app
from spec037_harness import (
    SETTLE_MS,
    WAIT_TIMEOUT_MS,
    connect,
    grid_from_text,
    make_catalogue,
    make_dist_dir,
    make_registry,
    state_of,
    wait_until_page,
)

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

# ---- Fixtures -----------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry whose throttle never refuses and that never times a socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


# ---- AC-4: escaping (static scan) ----------------------------------------------------

WEB_SRC_DIR = Path(__file__).resolve().parents[1] / "web" / "src"
HTML_BLOCK = re.compile(r"\{\s*@html")
RAW_HTML_CALLS = re.compile(
    r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|parseFromString"
    r"|createContextualFragment|setHTMLUnsafe|srcdoc"
)


def banned_constructs(text: str, is_svelte: bool) -> list[str]:
    """The places of `text` that insert HTML instead of text."""
    patterns = [RAW_HTML_CALLS]
    if is_svelte:
        patterns.append(HTML_BLOCK)
    found: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            found.append(f"line {number}: {match.group(0)}")
    return found


def test_ac4_static_the_client_never_inserts_html() -> None:
    svelte_files = sorted(WEB_SRC_DIR.rglob("*.svelte"))
    typescript_files = sorted(WEB_SRC_DIR.rglob("*.ts"))
    assert len(svelte_files) >= 1
    assert len(typescript_files) >= 1

    findings: list[str] = []
    for path in svelte_files + typescript_files:
        text = path.read_text(encoding="utf-8")
        for finding in banned_constructs(text, path.suffix == ".svelte"):
            findings.append(f"{path.relative_to(WEB_SRC_DIR)} {finding}")

    assert findings == []


@pytest.mark.parametrize(
    ("text", "is_svelte"),
    [
        ("<p>{@html nickname}</p>", True),
        ("<p>{ @html nickname}</p>", True),
        ("<p>{\n  @html nickname}</p>", True),
        ("new DOMParser().parseFromString(nickname, 'text/html')", False),
        ("range.createContextualFragment(nickname)", False),
        ("element.setHTMLUnsafe(nickname)", False),
        ("frame.srcdoc = nickname", False),
        ("<iframe srcdoc={nickname}></iframe>", True),
        ("element.innerHTML = nickname", False),
        ("element.outerHTML = nickname", True),
        ("element.insertAdjacentHTML('beforeend', nickname)", False),
        ("document.write(nickname)", False),
    ],
)
def test_ac4_static_the_scan_finds_each_banned_construct(
    text: str, is_svelte: bool
) -> None:
    assert len(banned_constructs(text, is_svelte)) == 1


def test_ac4_static_the_html_block_is_only_banned_in_svelte_files() -> None:
    assert banned_constructs("const text = '{@html x}'", False) == []


# ---- AC-4: escaping (WebSocket) ----------------------------------------------


@pytest.mark.parametrize(
    "nickname",
    ["<b>Eve</b>", "Eve<", ">Eve", "Eve&Bob"],
    ids=["tag", "less-than", "greater-than", "ampersand"],
)
def test_ac4_websocket_a_nickname_with_html_characters_is_invalid_nickname(
    registry: RoomRegistry, client: TestClient, room_code: str, nickname: str
) -> None:
    with contextlib.ExitStack() as stack:
        peer = connect(stack, client, room_code, "Eve")

        peer.send(Join(nickname=nickname, resume_token=None))
        peer.wait_for_messages(1, "the answer to the join")

        refusal = peer.messages()[0]
        assert isinstance(refusal, ErrorMessage)
        assert refusal.code is ErrorCode.INVALID_NICKNAME
        assert state_of(registry, room_code).players == ()

        peer.send(Join(nickname="Eve", resume_token=None))
        peer.wait_for_messages(2, "the snapshot after a good nickname")
        assert isinstance(peer.messages()[1], Snapshot)


# ---- AC-4: escaping (browser, mocked socket) ---------------------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self) -> None:
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)
        route.on_message(self._record)

    def _record(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)


def player_view(player_id: str, nickname: str, colour: int) -> PlayerView:
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=PlayerState.ACTIVE,
        is_host=player_id == "p1",
        muted=False,
        selection=None,
    )


def snapshot_frame(view: GridView, players: tuple[PlayerView, ...]) -> str:
    snapshot = Snapshot(
        seq=5,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=players,
        settings=RoomSettings(
            help_mode=HelpMode.FREE,
            reveal_budget=RevealBudget(letters=5, words=1),
            locked=False,
        ),
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def open_mock_room(
    page: Page, base_url: str, view: GridView, players: tuple[PlayerView, ...]
) -> list[str]:
    """Open /r/ABC123 on a mocked socket, send `view` and `players` as a snapshot.

    Returns the list that collects the text of every dialog the page opens.
    """
    dialogs: list[str] = []

    def record_dialog(dialog: Dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", record_dialog)
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until_page(page, lambda: len(mock.received) > 0, "the join of the page")
    mock.send(snapshot_frame(view, players))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return dialogs


def roster_nickname(page: Page, player_id: str) -> str:
    return (
        f'[data-testid="roster-player"][data-player-id="{player_id}"] '
        '[data-testid="roster-nickname"]'
    )


def test_ac4_browser_a_nickname_with_html_is_shown_as_plain_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = (
        player_view("p1", "Ana", 0),
        player_view("p2", "<b>Eve</b>", 3),
        player_view("p3", "<img src=x>", 5),
    )

    dialogs = open_mock_room(page, live_server, grid_view(fx01_grid), players)

    expect(page.get_by_test_id("roster-player")).to_have_count(3)
    expect(page.locator(roster_nickname(page, "p1"))).to_have_text("Ana")
    expect(page.locator(roster_nickname(page, "p2"))).to_have_text("<b>Eve</b>")
    expect(page.locator(roster_nickname(page, "p3"))).to_have_text("<img src=x>")
    expect(page.get_by_test_id("roster").locator("b")).to_have_count(0)
    expect(page.get_by_test_id("roster").locator("img")).to_have_count(0)
    expect(page.locator('img[src="x"]')).to_have_count(0)
    page.wait_for_timeout(SETTLE_MS)
    assert dialogs == []


def test_ac4_browser_html_in_a_clue_text_is_shown_as_plain_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    view = grid_view(fx01_grid)
    cells = []
    for cell in view.cells:
        if isinstance(cell, ClueCellView) and (cell.row, cell.column) == (0, 2):
            clue = cell.clues[0].model_copy(update={"text": "<i>Artiste</i> muet"})
            cell = cell.model_copy(update={"clues": (clue,)})
        cells.append(cell)
    view = view.model_copy(update={"cells": tuple(cells)})

    dialogs = open_mock_room(page, live_server, view, (player_view("p1", "Ana", 0),))

    clue_texts = page.get_by_test_id("clue-text").filter(has_text="<i>Artiste</i> muet")
    expect(clue_texts).to_have_count(1)
    expect(clue_texts).to_have_text("<i>Artiste</i> muet")
    expect(page.get_by_test_id("grid").locator("i")).to_have_count(0)
    page.wait_for_timeout(SETTLE_MS)
    assert dialogs == []
