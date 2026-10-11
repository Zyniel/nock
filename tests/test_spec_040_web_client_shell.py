"""Tests of spec 040: the web client shell (server frame and Svelte app)."""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from playwright.sync_api import Page, WebSocketRoute, expect
from starlette.websockets import WebSocketDisconnect

from nock.grid import Grid
from nock.protocol import (
    ErrorCode,
    ErrorMessage,
    HelpMode,
    Join,
    LetterChanged,
    RevealBudget,
    RoomSettings,
    Snapshot,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.server import (
    ROOM_CODE_PATTERN,
    ROOM_NOT_FOUND_CLOSE_CODE,
    WEB_DIST_DIR,
    RoomRegistry,
    create_app,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
WEB_SRC_DIR = WEB_DIR / "src"
FR_JSON_PATH = WEB_SRC_DIR / "i18n" / "fr.json"

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
JOIN_TEXT = '{"type": "join", "nickname": "Ana", "resume_token": null}'
ROOM_CODE_REGEX = re.compile(r"^[A-Z0-9]{6}$")
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
REQUIRED_KEYS = [
    "app.title",
    "catalogue.heading",
    "catalogue.empty",
    "room.heading",
    "room.default_nickname",
    "room.status.connecting",
    "room.status.joined",
    "room.status.not_found",
    "room.status.closed",
    "not_found.heading",
]
EXPECTED_SETTINGS = RoomSettings(
    help_mode=HelpMode.FREE,
    reveal_budget=RevealBudget(letters=5, words=1),
    locked=False,
)
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000


# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    """A built client: index.html, assets/app.js and favicon.svg."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    return dist


@pytest.fixture
def empty_client(dist_dir: Path, registry: RoomRegistry) -> TestClient:
    """A client on an app with a built dist and no room."""
    return TestClient(create_app(rooms=registry, dist_dir=dist_dir))


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def room_client(registry: RoomRegistry, room_code: str, dist_dir: Path) -> TestClient:
    """A client on an app that serves the room `room_code` (FX-01)."""
    return TestClient(create_app(rooms=registry, dist_dir=dist_dir))


def socket_url(code: str) -> str:
    return f"/api/rooms/{code}/ws"


def join_and_get_snapshot(client: TestClient, code: str) -> Snapshot:
    with client.websocket_connect(socket_url(code)) as websocket:
        websocket.send_text(JOIN_TEXT)
        message = parse_server_message(websocket.receive_text())
    assert isinstance(message, Snapshot)
    return message


def close_code_on_first_read(
    client: TestClient, code: str, first_message: str | None
) -> int:
    """Connect, optionally send a message, and return the close code received."""
    try:
        with client.websocket_connect(socket_url(code)) as websocket:
            if first_message is not None:
                websocket.send_text(first_message)
            websocket.receive_text()
    except WebSocketDisconnect as closed:
        return closed.code
    pytest.fail("the server sent a message instead of closing the socket")


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


# ---- Markup scan of AC-23 ---------------------------------------------------

_TEXT_ATTRIBUTE_NAMES = (
    "alt|title|placeholder|label|aria-label|aria-description|aria-placeholder"
    "|aria-roledescription|aria-valuetext"
)
_TEXT_ATTRIBUTE = re.compile(
    rf"(?<![\w:-])(?:{_TEXT_ATTRIBUTE_NAMES})\s*=\s*(?:\"([^\"]*)\"|'([^']*)')"
)
_TAG = re.compile(r"<[^>]*>")


def _remove_braces_groups(text: str) -> str:
    """Remove every {...} group, nested braces included."""
    kept: list[str] = []
    depth = 0
    for character in text:
        if character == "{":
            depth += 1
        elif character == "}" and depth > 0:
            depth -= 1
        elif depth == 0:
            kept.append(character)
    return "".join(kept)


def scan_markup(text: str) -> list[str]:
    """Return the user-visible literal strings found in a .svelte file."""
    violations: list[str] = []
    text = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = _remove_braces_groups(text)
    for tag in _TAG.findall(text):
        for match in _TEXT_ATTRIBUTE.finditer(tag):
            value = match.group(1) if match.group(1) is not None else match.group(2)
            if value.strip():
                violations.append(f"attribute: {match.group(0)}")
    remaining = _TAG.sub("", text)
    if remaining.strip():
        violations.append(f"text: {remaining.strip()}")
    return violations


# ---- Mocked room socket (browser tests) --------------------------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self, page: Page) -> None:
        self.page = page
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

    def close(self, code: int) -> None:
        self.routes[0].close(code=code)

    def wait_for_join(self) -> None:
        wait_until(self.page, lambda: len(self.received) > 0)


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def settle(page: Page) -> None:
    """Give the page time to process frames that must change nothing."""
    page.wait_for_timeout(300)


def open_mock_room(page: Page, base_url: str) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket and wait for the page's join."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    mock.wait_for_join()
    return mock


def snapshot_frame(grid: Grid, seq: int) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=grid_view(grid),
        players=(),
        settings=EXPECTED_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def event_frame(seq: int) -> str:
    event = LetterChanged(
        seq=seq, row=1, column=0, letter="T", pencil=False, player_id="p1"
    )
    return event.model_dump_json()


def joined_mock_room(page: Page, base_url: str, grid: Grid, seq: int) -> MockRoomSocket:
    """Open /r/ABC123, send a snapshot of `seq` and wait until it is shown."""
    mock = open_mock_room(page, base_url)
    mock.send(snapshot_frame(grid, seq))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    return mock


# ---- AC-1 to AC-6: HTTP -----------------------------------------------------


def test_ac1_root_serves_index_html(empty_client: TestClient) -> None:
    response = empty_client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == INDEX_HTML


def test_ac2_room_path_serves_index_html_for_unknown_room(
    empty_client: TestClient,
) -> None:
    response = empty_client.get("/r/ABC123")

    assert response.status_code == 200
    assert response.text == INDEX_HTML


def test_ac2_room_path_serves_index_html_for_registered_room(
    room_client: TestClient, room_code: str
) -> None:
    response = room_client.get(f"/r/{room_code}")

    assert response.status_code == 200
    assert response.text == INDEX_HTML


@pytest.mark.parametrize(
    "path", ["/api/nope", "/api", "/api/rooms", "/api/rooms/ABC123/ws"]
)
def test_ac3_api_paths_answer_json_404(empty_client: TestClient, path: str) -> None:
    response = empty_client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize(
    "path",
    [
        "/catalogue",
        "/r/abc123",
        "/r/ABC12",
        "/r/ABC1234",
        "/r/ABC123/extra",
        "/r",
    ],
)
def test_ac4_other_paths_are_404_and_not_the_app(
    empty_client: TestClient, path: str
) -> None:
    response = empty_client.get(path)

    assert response.status_code == 404
    assert response.text != INDEX_HTML


def test_ac5_assets_and_root_files_are_served(empty_client: TestClient) -> None:
    script = empty_client.get("/assets/app.js")
    favicon = empty_client.get("/favicon.svg")

    assert script.status_code == 200
    assert script.text == "console.log(1)"
    assert favicon.status_code == 200
    assert favicon.text == "<svg></svg>"


def test_ac5_missing_files_answer_404_not_the_app(empty_client: TestClient) -> None:
    missing_asset = empty_client.get("/assets/missing.js")
    missing_file = empty_client.get("/missing.svg")

    assert missing_asset.status_code == 404
    assert missing_asset.text != INDEX_HTML
    assert missing_file.status_code == 404
    assert missing_file.text != INDEX_HTML


def test_ac5_a_directory_is_not_served_as_a_file(empty_client: TestClient) -> None:
    response = empty_client.get("/assets")

    assert response.status_code == 404
    assert response.text != INDEX_HTML


@pytest.mark.parametrize(
    "path",
    [
        "/..%2Fsecret.txt",
        "/assets/..%2F..%2Fsecret.txt",
        "/..%5Csecret.txt",
        "/assets/..%5C..%5Csecret.txt",
    ],
)
def test_ac5_path_traversal_never_leaves_dist_dir(
    dist_dir: Path, registry: RoomRegistry, path: str
) -> None:
    (dist_dir.parent / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")
    client = TestClient(create_app(rooms=registry, dist_dir=dist_dir))

    response = client.get(path)

    assert response.status_code == 404
    assert "TOP-SECRET" not in response.text


def test_ac5_alternate_data_stream_of_index_is_not_served(
    empty_client: TestClient,
) -> None:
    response = empty_client.get("/index.html::$DATA")

    assert response.status_code != 200
    assert response.text != INDEX_HTML


@pytest.mark.parametrize("encoded_colon", [False, True])
def test_ac5_drive_letter_paths_never_leave_dist_dir(
    dist_dir: Path,
    registry: RoomRegistry,
    monkeypatch: pytest.MonkeyPatch,
    encoded_colon: bool,
) -> None:
    # The secret sits next to this test file. The check only bites when the
    # test file and the temporary dist_dir are on different drives: joining a
    # drive-relative name naively onto dist_dir would then reach the secret
    # from the current directory on Windows. Elsewhere a ':' is legal in a
    # file name, and the spec only requires that nothing outside dist_dir is
    # returned.
    drive = Path(__file__).resolve().drive or "C:"
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as outside_name:
        outside = Path(outside_name).resolve()
        secret = outside / "secret.txt"
        secret.write_text("TOP-SECRET", encoding="utf-8")
        monkeypatch.chdir(outside)
        try:
            client = TestClient(create_app(rooms=registry, dist_dir=dist_dir))
            path = f"/{drive}secret.txt"
            if encoded_colon:
                path = path.replace(":", "%3A")

            response = client.get(path)
        finally:
            # Leave the folder: Windows cannot delete the current directory.
            monkeypatch.undo()

    assert response.status_code == 404
    assert "TOP-SECRET" not in response.text


def test_ac6_missing_dist_answers_503_and_api_still_works(tmp_path: Path) -> None:
    app = create_app(dist_dir=tmp_path / "does-not-exist")
    client = TestClient(app)

    for path in ("/", "/r/ABC123"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.headers["content-type"].startswith("text/plain")
        assert "npm --prefix web run build" in response.text
    assert client.get("/api/nope").status_code == 404
    assert client.get("/assets/app.js").status_code == 404


def test_ac6_empty_dist_answers_503(tmp_path: Path) -> None:
    empty_dist = tmp_path / "empty"
    empty_dist.mkdir()
    client = TestClient(create_app(dist_dir=empty_dist))

    response = client.get("/")

    assert response.status_code == 503
    assert "npm --prefix web run build" in response.text


def test_ac6_app_is_served_once_built_without_restart(tmp_path: Path) -> None:
    dist = tmp_path / "late"
    client = TestClient(create_app(dist_dir=dist))
    assert client.get("/").status_code == 503

    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")

    response = client.get("/")
    assert response.status_code == 200
    assert response.text == INDEX_HTML


def test_ac6_default_dist_dir_is_the_repository_web_dist() -> None:
    assert WEB_DIST_DIR == PROJECT_ROOT / "web" / "dist"


# ---- AC-27 and AC-28: dot files and trailing slashes -------------------------

NOT_FOUND_BODY = {"detail": "Not Found"}
DOT_FILE_PATHS = [
    "/.env",
    "/.htaccess",
    "/assets/.hidden.js",
    "/.well-known/security.txt",
    "/%2Eenv",
]
TRAILING_SLASH_PATHS = [
    "/api/",
    "/api/rooms/",
    "/assets/",
    "/assets/app.js/",
    "/favicon.svg/",
    "/r/",
    "/r/ABC123/",
    "/catalogue/",
]


@pytest.fixture
def dot_dist_dir(dist_dir: Path) -> Path:
    """A built client that also holds dot files and dot directories."""
    (dist_dir / ".env").write_text("SECRET=1", encoding="utf-8")
    (dist_dir / ".htaccess").write_text("Deny from all", encoding="utf-8")
    (dist_dir / "..config").write_text("SECRET=3", encoding="utf-8")
    (dist_dir / "assets" / ".hidden.js").write_text("console.log(2)", encoding="utf-8")
    (dist_dir / "assets" / ".cache").mkdir()
    (dist_dir / "assets" / ".cache" / "inner.js").write_text(
        "console.log(4)", encoding="utf-8"
    )
    (dist_dir / ".well-known").mkdir()
    (dist_dir / ".well-known" / "security.txt").write_text(
        "Contact: nobody", encoding="utf-8"
    )
    return dist_dir


@pytest.fixture
def dot_client(dot_dist_dir: Path, registry: RoomRegistry) -> TestClient:
    return TestClient(create_app(rooms=registry, dist_dir=dot_dist_dir))


def assert_plain_not_found(response: Response) -> None:
    """Check a direct 404 with FastAPI's JSON body and nothing of the app."""
    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert "location" not in response.headers
    assert response.text != INDEX_HTML


@pytest.mark.parametrize("path", DOT_FILE_PATHS)
def test_ac27_dot_files_answer_json_404(dot_client: TestClient, path: str) -> None:
    response = dot_client.get(path, follow_redirects=False)

    assert_plain_not_found(response)
    for secret in ("SECRET=1", "console.log(2)", "Contact: nobody", "Deny from all"):
        assert secret not in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/..config",
        "/assets/.cache/inner.js",
        "/.well-known/security.txt",
        "/%2Ewell-known/security.txt",
        "/assets/%2Ehidden.js",
    ],
)
def test_ac27_every_dot_segment_counts_after_decoding(
    dot_client: TestClient, path: str
) -> None:
    response = dot_client.get(path, follow_redirects=False)

    assert_plain_not_found(response)
    for secret in ("SECRET=3", "console.log(2)", "console.log(4)", "Contact: nobody"):
        assert secret not in response.text


def test_ac27_dot_files_do_not_hide_regular_files(dot_client: TestClient) -> None:
    script = dot_client.get("/assets/app.js")
    favicon = dot_client.get("/favicon.svg")
    root = dot_client.get("/")

    assert script.status_code == 200
    assert script.text == "console.log(1)"
    assert favicon.status_code == 200
    assert favicon.text == "<svg></svg>"
    assert root.status_code == 200
    assert root.text == INDEX_HTML


@pytest.mark.parametrize("path", DOT_FILE_PATHS)
def test_ac27_unbuilt_client_answers_404_not_503_for_dot_files(
    tmp_path: Path, registry: RoomRegistry, path: str
) -> None:
    unbuilt = tmp_path / "unbuilt"
    unbuilt.mkdir()
    (unbuilt / ".env").write_text("SECRET=1", encoding="utf-8")
    client = TestClient(create_app(rooms=registry, dist_dir=unbuilt))

    response = client.get(path, follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac27_missing_dist_dir_answers_404_for_dot_files(tmp_path: Path) -> None:
    client = TestClient(create_app(dist_dir=tmp_path / "does-not-exist"))

    response = client.get("/.env", follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


@pytest.mark.parametrize("path", TRAILING_SLASH_PATHS)
def test_ac28_trailing_slash_answers_404_without_redirect(
    empty_client: TestClient, path: str
) -> None:
    response = empty_client.get(path, follow_redirects=False)

    assert_plain_not_found(response)
    assert not 300 <= response.status_code < 400


def test_ac28_root_is_still_served(empty_client: TestClient) -> None:
    response = empty_client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert response.text == INDEX_HTML


def test_ac28_registered_room_with_trailing_slash_is_404(
    room_client: TestClient, room_code: str
) -> None:
    served = room_client.get(f"/r/{room_code}", follow_redirects=False)
    response = room_client.get(f"/r/{room_code}/", follow_redirects=False)

    assert served.status_code == 200
    assert_plain_not_found(response)


@pytest.mark.parametrize("path", ["/r/ABC123/", "/api/", "/favicon.svg/"])
def test_ac28_unbuilt_client_answers_404_not_503(tmp_path: Path, path: str) -> None:
    client = TestClient(create_app(dist_dir=tmp_path / "does-not-exist"))

    response = client.get(path, follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert "location" not in response.headers


def test_ac28_no_response_of_the_app_is_a_redirect(
    room_client: TestClient, room_code: str
) -> None:
    paths = ["/", f"/r/{room_code}", "/assets/app.js", "/favicon.svg"]
    paths += ["/api", "/api/nope", "/assets", "/catalogue", "/r/abc123"]
    paths += [*TRAILING_SLASH_PATHS, f"/r/{room_code}/"]
    paths += [*DOT_FILE_PATHS, socket_url(room_code)]

    for path in paths:
        response = room_client.get(path, follow_redirects=False)
        assert not 300 <= response.status_code < 400, path
        assert "location" not in response.headers, path


API_DOCS_PATHS = ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"]


@pytest.mark.parametrize("path", API_DOCS_PATHS)
def test_ac29_api_docs_answer_json_404_with_a_built_client(
    empty_client: TestClient, path: str
) -> None:
    response = empty_client.get(path, follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


@pytest.mark.parametrize("path", API_DOCS_PATHS)
def test_ac29_api_docs_answer_json_404_without_a_built_client(
    tmp_path: Path, path: str
) -> None:
    client = TestClient(create_app(dist_dir=tmp_path / "does-not-exist"))

    response = client.get(path, follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


# ---- AC-7: RoomRegistry -----------------------------------------------------


def test_ac7_register_room_gives_distinct_valid_codes(
    registry: RoomRegistry, fx01_grid: Grid
) -> None:
    first = registry.register_room(fx01_grid)
    second = registry.register_room(fx01_grid)

    assert ROOM_CODE_REGEX.match(first)
    assert ROOM_CODE_REGEX.match(second)
    assert first != second
    assert registry.find_room(first) == fx01_grid
    assert registry.find_room(second) == fx01_grid


def test_ac7_find_room_returns_none_for_unknown_code(
    registry: RoomRegistry, fx01_grid: Grid
) -> None:
    registry.register_room(fx01_grid)
    other_registry = RoomRegistry()

    try:
        assert registry.find_room("abc123") is None
        assert other_registry.find_room("ABC123") is None
    finally:
        other_registry.close()


def test_ac7_many_codes_are_all_distinct(
    registry: RoomRegistry, fx01_grid: Grid
) -> None:
    codes = [registry.register_room(fx01_grid) for _ in range(200)]

    assert len(set(codes)) == 200


def test_ac7_constants_of_the_interface() -> None:
    assert ROOM_CODE_PATTERN == r"^[A-Z0-9]{6}$"
    assert ROOM_NOT_FOUND_CLOSE_CODE == 4404


# ---- AC-8 to AC-13: WebSocket -----------------------------------------------


def test_ac8_join_gets_the_snapshot_of_the_room(
    room_client: TestClient, room_code: str, fx01_grid: Grid
) -> None:
    snapshot = join_and_get_snapshot(room_client, room_code)

    assert snapshot.seq == 0
    assert snapshot.grid == grid_view(fx01_grid)
    assert snapshot.players == ()
    assert snapshot.settings == EXPECTED_SETTINGS
    assert snapshot.reveal_budget == RevealBudget(letters=5, words=1)
    assert snapshot.flags == ()
    assert snapshot.chat == ()
    assert snapshot.open_vote is None
    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False
    assert snapshot.solved is False


def test_ac8_binary_join_frame_is_handled_like_text(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_bytes(JOIN_TEXT.encode("utf-8"))
        message = parse_server_message(websocket.receive_text())

    assert isinstance(message, Snapshot)
    assert message.seq == 0


def test_ac8_resume_token_of_the_join_is_ignored(
    room_client: TestClient, room_code: str
) -> None:
    sent_token = "A" * 24
    join_text = Join(nickname="Ana", resume_token=sent_token).model_dump_json()

    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(join_text)
        message = parse_server_message(websocket.receive_text())

    assert isinstance(message, Snapshot)
    assert message.resume_token != sent_token


def test_ac9_snapshot_text_holds_no_answer(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(JOIN_TEXT)
        raw_text = websocket.receive_text()

    assert isinstance(parse_server_message(raw_text), Snapshot)
    forbidden = ["answer", "TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE"]
    forbidden += ["AMEN", "LEST"]
    for word in forbidden:
        assert word not in raw_text


def test_ac10_two_clients_get_different_identities(
    room_client: TestClient, room_code: str
) -> None:
    url = socket_url(room_code)
    with (
        room_client.websocket_connect(url) as first_socket,
        room_client.websocket_connect(url) as second_socket,
    ):
        first_socket.send_text(JOIN_TEXT)
        second_socket.send_text(JOIN_TEXT)
        first = parse_server_message(first_socket.receive_text())
        second = parse_server_message(second_socket.receive_text())

    assert isinstance(first, Snapshot)
    assert isinstance(second, Snapshot)
    assert first.you != second.you
    assert first.resume_token != second.resume_token


@pytest.mark.parametrize("code", ["ZZZZZZ", "abc"])
def test_ac11_unknown_room_closes_with_4404_and_no_message(
    empty_client: TestClient, code: str
) -> None:
    assert close_code_on_first_read(empty_client, code, None) == 4404


def test_ac11_unknown_room_closes_even_when_another_room_exists(
    room_client: TestClient,
) -> None:
    assert close_code_on_first_read(room_client, "ZZZZZZ", JOIN_TEXT) == 4404


@pytest.mark.parametrize(
    "bad_message",
    ["not json", '{"type": "join", "nickname": "A"}', '{"type": "nope"}'],
)
def test_ac12_invalid_message_gets_invalid_message_error(
    room_client: TestClient, room_code: str, bad_message: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(bad_message)
        error = parse_server_message(websocket.receive_text())
        websocket.send_text(JOIN_TEXT)
        snapshot = parse_server_message(websocket.receive_text())

    assert isinstance(error, ErrorMessage)
    assert error.code == ErrorCode.INVALID_MESSAGE
    assert error.message != ""
    assert isinstance(snapshot, Snapshot)


def test_ac12_invalid_binary_frame_gets_invalid_message_error(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_bytes(b"not json")
        error = parse_server_message(websocket.receive_text())

    assert isinstance(error, ErrorMessage)
    assert error.code == ErrorCode.INVALID_MESSAGE


def test_ac13_message_before_join_gets_not_joined_error(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text('{"type": "undo"}')
        error = parse_server_message(websocket.receive_text())
        websocket.send_text(JOIN_TEXT)
        snapshot = parse_server_message(websocket.receive_text())

    assert isinstance(error, ErrorMessage)
    assert error.code == ErrorCode.NOT_JOINED
    assert error.message != ""
    assert isinstance(snapshot, Snapshot)


def test_ac13_binary_message_before_join_gets_not_joined_error(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_bytes(b'{"type": "undo"}')
        error = parse_server_message(websocket.receive_text())

    assert isinstance(error, ErrorMessage)
    assert error.code == ErrorCode.NOT_JOINED


# ---- AC-14 to AC-17: browser, live server -----------------------------------


def test_ac14_catalogue_page_is_shown_on_root(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/")

    catalogue = page.get_by_test_id("catalogue-page")
    expect(catalogue).to_be_visible()
    expect(catalogue).to_contain_text(load_fr()["catalogue.heading"])
    expect(catalogue).to_contain_text(load_fr()["catalogue.empty"])
    expect(page.get_by_test_id("room-page")).to_have_count(0)


@pytest.mark.parametrize("path", ["/", "/r/ABC123"])
def test_ac15_title_and_language(page: Page, live_server: str, path: str) -> None:
    page.goto(f"{live_server}{path}")

    expect(page).to_have_title(load_fr()["app.title"])
    expect(page.locator("html")).to_have_attribute("lang", "fr")


def test_ac16_room_page_joins_and_shows_the_grid(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    code = room_registry.register_room(fx01_grid)

    page.goto(f"{live_server}/r/{code}")

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-room-code", code)
    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-seq", "0")
    expect(room).to_have_attribute("data-grid", "5x5")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.joined"]
    )
    expected_heading = load_fr()["room.heading"].replace("{code}", code)
    expect(room).to_contain_text(expected_heading)
    expect(page.get_by_test_id("catalogue-page")).to_have_count(0)


def test_ac17_unknown_room_shows_not_found(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/r/ZZZZZZ")

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "not_found")
    expect(room).to_have_attribute("data-seq", "")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.not_found"]
    )


# ---- AC-18 to AC-21: browser, mocked socket ---------------------------------


def test_ac18_page_sends_the_default_join(page: Page, live_server: str) -> None:
    mock = open_mock_room(page, live_server)

    first_message = parse_client_message(mock.received[0])
    assert first_message == Join(
        nickname=load_fr()["room.default_nickname"], resume_token=None
    )
    assert len(mock.routes) == 1


def test_ac18_before_a_snapshot_the_page_is_connecting(
    page: Page, live_server: str
) -> None:
    open_mock_room(page, live_server)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-room-code", "ABC123")
    expect(room).to_have_attribute("data-status", "connecting")
    expect(room).to_have_attribute("data-seq", "")
    expect(room).to_have_attribute("data-grid", "")
    expect(room).to_have_attribute("data-pending", "0")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.connecting"]
    )


def test_ac19_events_are_ordered_and_gaps_buffered(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-grid", "5x5")

    for seq in (4, 5, 7):
        mock.send(event_frame(seq))
    expect(room).to_have_attribute("data-pending", "1")
    expect(room).to_have_attribute("data-seq", "5")

    mock.send(event_frame(6))
    expect(room).to_have_attribute("data-seq", "7")
    expect(room).to_have_attribute("data-pending", "0")


def test_ac19_next_event_is_applied_at_once(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(6))

    expect(room).to_have_attribute("data-seq", "6")
    expect(room).to_have_attribute("data-pending", "0")


def test_ac19_a_duplicate_buffered_event_is_ignored(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(7))
    mock.send(event_frame(7))
    expect(room).to_have_attribute("data-pending", "1")
    settle(page)

    expect(room).to_have_attribute("data-pending", "1")
    expect(room).to_have_attribute("data-seq", "5")


def test_ac19_a_gap_that_never_fills_keeps_the_buffer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(8))
    mock.send(event_frame(10))
    expect(room).to_have_attribute("data-pending", "2")
    settle(page)

    expect(room).to_have_attribute("data-pending", "2")
    expect(room).to_have_attribute("data-seq", "5")
    assert len(mock.received) == 1


def test_ac19_junk_frames_are_ignored(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send("not json")
    mock.send("[1, 2]")
    mock.send('{"seq": 6}')
    mock.send('{"type": 3, "seq": 6}')
    mock.send("null")
    mock.send(event_frame(6))

    expect(room).to_have_attribute("data-seq", "6")
    expect(room).to_have_attribute("data-pending", "0")
    expect(room).to_have_attribute("data-status", "joined")


def test_ac19_events_before_the_first_snapshot_are_dropped(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(1))
    mock.send(snapshot_frame(fx01_grid, 0))
    expect(room).to_have_attribute("data-seq", "0")
    settle(page)

    expect(room).to_have_attribute("data-seq", "0")
    expect(room).to_have_attribute("data-pending", "0")


def test_ac19_a_second_snapshot_replaces_the_first(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(8))
    expect(room).to_have_attribute("data-pending", "1")
    mock.send(snapshot_frame(fx01_grid, 7))

    expect(room).to_have_attribute("data-seq", "8")
    expect(room).to_have_attribute("data-pending", "0")


def test_ac19_a_second_snapshot_drops_buffered_events_it_includes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(7))
    expect(room).to_have_attribute("data-pending", "1")
    mock.send(snapshot_frame(fx01_grid, 9))

    expect(room).to_have_attribute("data-seq", "9")
    expect(room).to_have_attribute("data-pending", "0")
    settle(page)
    expect(room).to_have_attribute("data-seq", "9")


def test_ac20_events_without_seq_change_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")
    selection_moved = (
        '{"type": "selection_moved", "player_id": "p1", "selection": '
        '{"row": 1, "column": 0, "direction": "across"}}'
    )
    reaction = (
        '{"type": "reaction", "player_id": "p2", "clue": '
        '{"row": 0, "column": 3, "clue_index": 0}, "reaction": "wow"}'
    )
    error = '{"type": "error", "code": "cell_locked", "message": "cell is locked"}'

    for frame in (selection_moved, reaction, error):
        mock.send(frame)
    mock.send(event_frame(6))

    expect(room).to_have_attribute("data-seq", "6")
    expect(room).to_have_attribute("data-pending", "0")
    expect(room).to_have_attribute("data-status", "joined")


def test_ac21_other_close_codes_mean_closed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 0)

    mock.close(1011)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "closed")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.closed"]
    )


def test_ac21_close_before_a_snapshot_keeps_seq_empty(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)

    mock.close(1011)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "closed")
    expect(room).to_have_attribute("data-seq", "")


def test_ac21_close_4404_means_not_found(page: Page, live_server: str) -> None:
    mock = open_mock_room(page, live_server)

    mock.close(4404)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "not_found")
    expect(room).to_have_attribute("data-seq", "")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.not_found"]
    )


# ---- AC-22 to AC-26: static -------------------------------------------------


def svelte_files() -> list[Path]:
    return sorted(WEB_SRC_DIR.rglob("*.svelte"))


def test_ac22_fr_json_is_a_flat_catalogue_with_the_required_keys() -> None:
    messages = json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))

    assert isinstance(messages, dict)
    for key, value in messages.items():
        assert KEY_PATTERN.match(key), key
        assert isinstance(value, str), key
        assert value != "", key
    for required_key in REQUIRED_KEYS:
        assert required_key in messages


@pytest.mark.parametrize(
    "markup",
    [
        "<p>Bonjour</p>",
        '<img alt="Logo" />',
        '<button title="Salon {code}">',
        "<svelte:head><title>Nock</title></svelte:head>",
        "{#if ready}<p>Bonjour</p>{/if}",
        "<input placeholder='Pseudo' />",
        '<div aria-label="Fermer"></div>',
        '<p>{t("a.b")}</p> Reste',
    ],
)
def test_ac23_scan_finds_violations(markup: str) -> None:
    assert scan_markup(markup) != []


@pytest.mark.parametrize(
    "markup",
    [
        '<p>{t("a.b")}</p>',
        '<img alt="" />',
        '<img alt={t("a.b")} />',
        "<input placeholder=\"{t('a.b')}\" />",
        "<script lang=\"ts\">const x = 'Bonjour';</script><p>{x}</p>",
        "<!-- Bonjour --><p>{t('a.b')}</p>",
        "<style>p { content: 'Bonjour'; }</style>",
        '{#if ok}<p>{t("a.b")}</p>{:else}<p>{t("a.c")}</p>{/if}',
    ],
)
def test_ac23_scan_accepts_clean_markup(markup: str) -> None:
    assert scan_markup(markup) == []


def test_ac23_svelte_files_hold_no_literal_text() -> None:
    files = svelte_files()
    assert files != []

    violations: dict[str, list[str]] = {}
    for svelte_file in files:
        found = scan_markup(svelte_file.read_text(encoding="utf-8"))
        if found:
            violations[svelte_file.name] = found

    assert violations == {}


def test_ac24_every_translation_key_used_exists() -> None:
    messages = load_fr()
    key_call = re.compile(r"\bt\(\s*[\"']([^\"']+)[\"']")
    used_keys: list[str] = []
    for pattern in ("*.svelte", "*.ts"):
        for source_file in sorted(WEB_SRC_DIR.rglob(pattern)):
            text = source_file.read_text(encoding="utf-8")
            used_keys.extend(key_call.findall(text))

    assert used_keys != []
    unknown_keys = [key for key in used_keys if key not in messages]
    assert unknown_keys == []


def test_ac25_index_html_has_no_text_and_french_lang() -> None:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

    html_tag = re.search(r"<html\b[^>]*>", html, flags=re.IGNORECASE)
    assert html_tag is not None
    assert re.search(r"\blang\s*=\s*[\"']fr[\"']", html_tag.group(0))
    title = re.search(r"<title>(.*?)</title>", html, flags=re.DOTALL | re.IGNORECASE)
    assert title is not None
    assert title.group(1).strip() == ""
    body = re.search(r"<body\b[^>]*>(.*)</body>", html, flags=re.DOTALL)
    assert body is not None
    body_text = re.sub(r"<[^>]*>", "", body.group(1))
    assert body_text.strip() == ""
    assert 'id="app"' in body.group(1)


@pytest.mark.parametrize(
    "demo_path",
    [
        "web/src/lib/Counter.svelte",
        "web/src/assets/hero.png",
        "web/src/assets/svelte.svg",
        "web/src/assets/vite.svg",
        "web/public/icons.svg",
    ],
)
def test_ac26_demo_files_are_removed(demo_path: str) -> None:
    assert not (PROJECT_ROOT / demo_path).exists()


def test_ac26_no_demo_text_left_in_web_src() -> None:
    offending: list[str] = []
    for source_file in sorted(WEB_SRC_DIR.rglob("*")):
        if not source_file.is_file():
            continue
        content = source_file.read_bytes()
        if b"Counter" in content or b"svelte.svg" in content:
            offending.append(source_file.name)

    assert offending == []
    assert (WEB_SRC_DIR / "App.svelte").is_file()
