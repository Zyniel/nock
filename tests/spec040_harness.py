"""Shared setup of the tests of spec 040: the web client shell.

This module is not a test file: pytest does not collect it. The tests of spec 040
are in `tests/test_spec_040_*.py`, one file per criterion group:

- `test_spec_040_ac01_ac06_http_routes.py`: the HTTP routes and the unbuilt client.
- `test_spec_040_ac07_ac13_registry_and_socket.py`: `RoomRegistry` and the room
  WebSocket.
- `test_spec_040_ac14_ac21_room_page_browser.py`: the pages in a browser, on the
  live server and on a mocked socket.
- `test_spec_040_ac22_ac26_static_client.py`: static checks of the files under `web/`.
- `test_spec_040_ac27_ac29_dot_files_slashes_docs.py`: dot files, trailing slashes
  and the API documentation.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures that several files need are
defined in each of them: `fx01_grid` and `dist_dir` as thin wrappers around
`grid_from_text` and `make_dist_dir`, and `empty_client`, `registry`, `room_code`
and `room_client` as the same few lines. A fixture imported from here would be an
unused import for ruff.
"""

from __future__ import annotations

import json
from pathlib import Path

from nock.grid import Grid
from nock.protocol import HelpMode, RevealBudget, RoomSettings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
WEB_SRC_DIR = WEB_DIR / "src"
FR_JSON_PATH = WEB_SRC_DIR / "i18n" / "fr.json"

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
EXPECTED_SETTINGS = RoomSettings(
    help_mode=HelpMode.FREE,
    reveal_budget=RevealBudget(letters=5, words=1),
    locked=False,
)


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """A built client: index.html, assets/app.js and favicon.svg (`dist_dir`)."""
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    return dist


def socket_url(code: str) -> str:
    return f"/api/rooms/{code}/ws"


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))
