"""Shared setup of the tests of `client/shell.md` AC-29 to AC-31: texts that come from
`fr.json`, the landmarks of the pages and the code fetched per route. The fonts
tests of `client/foundation.md` (`tests/test_foundation_fonts.py`) read the built
files through `built_files` and `ASSETS_DIR` too.

Pytest does not collect this module (its name does not start with `test_`). The tests
are in `tests/test_shell_*.py`:

- `test_shell_text_keys.py`: AC-29, the list separator and the units.
- `test_shell_landmarks.py`: AC-30, one banner then one `main` on every page.
- `test_shell_page_code.py`: AC-31, the code fetched on each page's route.
- `test_shell_malformed_events.py`: AC-34 to AC-36, events and frames of wrong shape.
- `test_shell_placeholders.py`: AC-37, a placeholder with no value.

This module holds what more than one of those files uses: the built client's files
(`web/dist`), the way a test reads the scripts a page fetched, a rewrite of one
value of `fr.json` inside the scripts the page loads (to see which key the page
reads), and the opener of the pages answered with the built `index.html`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Request, Route, expect

from fonts_ready import wait_for_fonts
from nock.server import WEB_DIST_DIR
from spec043_harness import RoomMock
from spec046_harness import WAIT_TIMEOUT_MS

ASSETS_DIR = WEB_DIST_DIR / "assets"
SCRIPT_ROUTE = "**/assets/*.js"
MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"


def built_files(suffix: str) -> list[Path]:
    """The files of `web/dist/assets` with this suffix, sorted. Fails if not built."""
    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)
    found: list[Path] = []
    for path in sorted(ASSETS_DIR.iterdir()):
        if path.suffix == suffix:
            found.append(path)
    return found


def route_client(page: Page, url: str) -> None:
    """Answer `GET url` with the built `index.html`, as the live server would."""
    index_html = (WEB_DIST_DIR / "index.html").read_text(encoding="utf-8")

    def answer(route: Route) -> None:
        route.fulfill(status=200, content_type="text/html", body=index_html)

    page.route(url, answer)


def open_locked_ops(page: Page, base_url: str) -> None:
    """Open `/ops` locked: the path answered with the built client."""
    route_client(page, f"{base_url}/ops")
    page.goto(f"{base_url}/ops")
    expect(page.get_by_test_id("ops-page")).to_have_attribute(
        "data-state", "locked", timeout=WAIT_TIMEOUT_MS
    )
    wait_for_fonts(page)


def send_binary(mock: RoomMock, text: str) -> None:
    """Send `text`, UTF-8 encoded, as a binary frame on the newest mocked socket."""
    mock.routes[-1].send(text.encode("utf-8"))


def built_file_of(url: str) -> Path:
    """The file of `web/dist` that a same-origin URL names (`/assets/x.js`)."""
    return WEB_DIST_DIR / urlsplit(url).path.lstrip("/")


class FetchedScripts:
    """The scripts a page fetches from now on, by URL, in the order they were asked."""

    def __init__(self, page: Page) -> None:
        self.urls: list[str] = []
        page.on("request", self._keep)

    def _keep(self, request: Request) -> None:
        is_script = urlsplit(request.url).path.endswith(".js")
        if request.resource_type == "script" or is_script:
            self.urls.append(request.url)

    def texts(self) -> list[str]:
        """The built text of each script fetched."""
        found: list[str] = []
        for url in self.urls:
            found.append(built_file_of(url).read_text(encoding="utf-8"))
        return found

    def holding(self, sentinel: str) -> list[str]:
        """The URLs of the fetched scripts whose text holds `sentinel`."""
        found: list[str] = []
        for url in self.urls:
            if sentinel in built_file_of(url).read_text(encoding="utf-8"):
                found.append(url)
        return found


class Rewording(NamedTuple):
    """One `fr.json` entry to reword: its key, its value now and the value to show."""

    key: str
    old_value: str
    new_value: str


class ReworkedValues:
    """Rewrites `fr.json` values inside the built scripts a page loads.

    The bundle holds the file's entries as `"key":"value"` (any of the three string
    quotes). The page then shows the new value wherever it reads the key through
    `t()`, and shows the old one wherever its code writes the text itself.
    `counts` says, per key, how many entries were rewritten across the scripts served
    (0 when the bundle holds no such entry).
    """

    def __init__(self, page: Page, rewordings: Sequence[Rewording]) -> None:
        self.rewordings = list(rewordings)
        self.counts: dict[str, int] = {}
        for wording in self.rewordings:
            self.counts[wording.key] = 0
        page.route(SCRIPT_ROUTE, self.handle)

    def handle(self, route: Route) -> None:
        """Serve a script with its entries reworded."""
        response = route.fetch()
        body = response.text()
        for wording in self.rewordings:
            pattern = re.compile(
                r"(\"" + re.escape(wording.key) + r"\"\s*:\s*)"
                r"([\"'`])" + re.escape(wording.old_value) + r"\2"
            )
            replacement = json.dumps(wording.new_value)
            body, replaced = pattern.subn(
                lambda found, text=replacement: found.group(1) + text, body
            )
            self.counts[wording.key] += replaced
        route.fulfill(response=response, body=body)
