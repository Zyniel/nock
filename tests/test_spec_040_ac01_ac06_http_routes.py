"""Tests of spec 040, AC-1 to AC-6: the HTTP routes that serve the built client.

`GET /` and `GET /r/{code}` give `index.html`, the assets and the files at the root
of `dist_dir` are served, every other path is a 404, a path never leaves `dist_dir`,
and a client that is not built answers 503. The tests use
`fastapi.testclient.TestClient` on `create_app(rooms=..., dist_dir=tmp_path)`.

Dot files, trailing slashes and the API documentation are in
`test_spec_040_ac27_ac29_dot_files_slashes_docs.py`. The shared setup is in
`tests/spec040_harness.py`.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.server import WEB_DIST_DIR, RoomRegistry, create_app
from spec040_harness import INDEX_HTML, PROJECT_ROOT, grid_from_text, make_dist_dir


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


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
