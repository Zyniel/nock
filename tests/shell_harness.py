"""Shared setup of the tests of `client/shell.md` AC-29 to AC-33: texts that come from
`fr.json`, the landmarks of the pages, the code fetched per route and the fonts.

Pytest does not collect this module (its name does not start with `test_`). The tests
are in `tests/test_shell_*.py`:

- `test_shell_text_keys.py`: AC-29, the list separator and the units.
- `test_shell_landmarks.py`: AC-30, one banner then one `main` on every page.
- `test_shell_page_code.py`: AC-31, the code fetched on each page's route.
- `test_shell_fonts.py`: AC-32 and AC-33, the font subsets and the room page's preload.

This module holds what more than one of those files uses: the built client's files
(`web/dist`), the way a test reads the scripts a page fetched, and a rewrite of one
value of `fr.json` inside the scripts the page loads (to see which key the page
reads).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Request, Route

from nock.server import WEB_DIST_DIR

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
