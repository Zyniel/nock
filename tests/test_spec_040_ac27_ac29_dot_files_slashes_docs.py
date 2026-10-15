"""Tests of spec 040, AC-27 to AC-29: dot files, trailing slashes, API docs.

Paths that the app must answer with FastAPI's JSON 404 and never with a file, a
redirect or `index.html`: a path with a segment that starts with `.` (AC-27), a
path other than `/` that ends with `/` (AC-28), and the generated documentation
(AC-29). The tests use `fastapi.testclient.TestClient` on
`create_app(rooms=..., dist_dir=tmp_path)`, without following redirects.

The shared setup is in `tests/spec040_harness.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from nock.grid import Grid
from nock.server import RoomRegistry, create_app
from spec040_harness import INDEX_HTML, grid_from_text, make_dist_dir, socket_url


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


# ---- AC-27 to AC-29: dot files, trailing slashes and API docs ----------------

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
