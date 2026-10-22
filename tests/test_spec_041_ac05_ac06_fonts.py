"""Tests of spec 041, AC-5 and AC-6: Nock serves its fonts itself, from the decided
packages, and credits them.

AC-5 runs in a browser on the live server and records every request the page
makes from `page.goto("/")` on. AC-6 reads files with Python only. The shared
setup is in `tests/spec041_harness.py`.

Choices where the spec leaves room:

- AC-5: the check that every font request is on the live server's origin would
  hold with no font request at all, so the test also requires at least one: the
  faces are WOFF2 files served by Nock ("Fonts").
- AC-5: "no recorded request goes to another host" covers the requests whose
  URL has a host (`http`, `https`, `ws`, `wss`); a `data:` or `blob:` URL has no
  host.
- AC-6: "lists" accepts the package under `dependencies` or `devDependencies`.
  An `@fontsource/` import is any quoted module name that starts with
  `@fontsource/` in a `.ts` or `.svelte` file under `web/src`, comments removed.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, Request

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec041_harness import (
    PACKAGE_JSON_PATH,
    README_PATH,
    open_catalogue,
    remove_script_comments,
    source_files,
    split_svelte,
)

# ---- Fixtures: thin wrappers around the harnesses ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (served by live_server for `/`)."""
    return build_reference_catalogue(fx01_grid)


# ---- AC-5: Nock serves its fonts itself -------------------------------------------

FACES = [
    '400 16px "Source Sans 3"',
    '500 16px "Source Sans 3"',
    '600 16px "Source Sans 3"',
    '700 16px "Source Sans 3"',
    'italic 500 16px "Source Sans 3"',
    'italic 700 16px "Source Sans 3"',
    '500 16px "IBM Plex Sans Condensed"',
    '600 16px "IBM Plex Sans Condensed"',
]

LOAD_FACE_SCRIPT = """
async font => {
  const faces = await document.fonts.load(font);
  return faces.map(face => face.status);
}
"""

HOST_SCHEMES = ("http", "https", "ws", "wss")


def open_catalogue_recording(page: Page, base_url: str) -> list[Request]:
    """Open `/`, recording every request from `page.goto` on; wait for the fonts."""
    requests: list[Request] = []

    def record(request: Request) -> None:
        requests.append(request)

    page.on("request", record)
    open_catalogue(page, base_url)
    wait_for_fonts(page)
    return requests


def load_face(page: Page, font: str) -> list[str]:
    """The `status` of each `FontFace` that `document.fonts.load(font)` gives."""
    statuses = page.evaluate(LOAD_FACE_SCRIPT, font)
    assert isinstance(statuses, list)
    return [str(status) for status in statuses]


def load_every_face(page: Page) -> None:
    """Ask the page to load every face of `FACES`."""
    for font in FACES:
        load_face(page, font)


@pytest.mark.parametrize("font", FACES)
def test_ac5_document_fonts_load_gives_loaded_faces(
    page: Page, live_server: str, font: str
) -> None:
    open_catalogue_recording(page, live_server)

    statuses = load_face(page, font)

    assert statuses != [], f"no FontFace for {font}"
    assert statuses == ["loaded"] * len(statuses), f"{font}: {statuses}"


def test_ac5_every_font_request_is_on_the_live_server_with_status_200(
    page: Page, live_server: str
) -> None:
    requests = open_catalogue_recording(page, live_server)
    load_every_face(page)
    origin = urlsplit(live_server)

    font_requests = [request for request in requests if request.resource_type == "font"]

    assert font_requests != [], "the page made no font request"
    for request in font_requests:
        url = urlsplit(request.url)
        assert (url.scheme, url.netloc) == (origin.scheme, origin.netloc), request.url
        response = request.response()
        assert response is not None, f"no response for {request.url}"
        assert response.status == 200, request.url


def test_ac5_no_request_goes_to_another_host(page: Page, live_server: str) -> None:
    requests = open_catalogue_recording(page, live_server)
    load_every_face(page)
    origin = urlsplit(live_server)

    elsewhere: list[str] = []
    for request in requests:
        url = urlsplit(request.url)
        if url.scheme in HOST_SCHEMES and url.netloc != origin.netloc:
            elsewhere.append(request.url)

    assert elsewhere == []


# ---- AC-6: the font packages are the decided ones and are credited ----------------

FONT_PACKAGES = ("@fontsource/source-sans-3", "@fontsource/ibm-plex-sans-condensed")
FONT_IMPORTS = [
    "@fontsource/source-sans-3/400.css",
    "@fontsource/source-sans-3/500.css",
    "@fontsource/source-sans-3/600.css",
    "@fontsource/source-sans-3/700.css",
    "@fontsource/source-sans-3/500-italic.css",
    "@fontsource/source-sans-3/700-italic.css",
    "@fontsource/ibm-plex-sans-condensed/500.css",
    "@fontsource/ibm-plex-sans-condensed/600.css",
]
FONTSOURCE_NAME = re.compile(r"""(['"`])(@fontsource/[^'"`]*)\1""")
README_CREDITS = (
    "Source Sans 3",
    "IBM Plex Sans Condensed",
    "SIL Open Font License 1.1",
)


def listed_packages() -> set[str]:
    """The packages of `web/package.json`, dependencies and devDependencies."""
    package = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for section in ("dependencies", "devDependencies"):
        names.update(package.get(section, {}))
    return names


def code_without_comments(text: str, suffix: str) -> str:
    """The code of a `.ts` or `.svelte` file, comments removed."""
    if suffix == ".ts":
        return remove_script_comments(text)
    parts = split_svelte(text)
    return "\n".join([*parts.scripts, *parts.styles, parts.markup])


def fontsource_imports() -> Counter[str]:
    """Each `@fontsource/` module name of `web/src`, with how often it appears."""
    found: Counter[str] = Counter()
    for path in source_files(".ts", ".svelte"):
        code = code_without_comments(path.read_text(encoding="utf-8"), path.suffix)
        for match in FONTSOURCE_NAME.finditer(code):
            found[match.group(2)] += 1
    return found


@pytest.mark.parametrize("package", FONT_PACKAGES)
def test_ac6_package_json_lists_the_font_package(package: str) -> None:
    assert package in listed_packages()


def test_ac6_the_fontsource_imports_are_exactly_the_eight_files_each_once() -> None:
    assert fontsource_imports() == Counter(FONT_IMPORTS)


def test_ac6_the_import_scan_finds_imports_and_leaves_comments_out() -> None:
    code = (
        "import '@fontsource/source-sans-3/400.css'\n"
        "// import '@fontsource/source-sans-3/800.css'\n"
        "/* import '@fontsource/source-sans-3/900.css' */\n"
        'import "@fontsource/ibm-plex-sans-condensed/600.css"\n'
    )

    found = FONTSOURCE_NAME.findall(code_without_comments(code, ".ts"))

    assert [name for _, name in found] == [
        "@fontsource/source-sans-3/400.css",
        "@fontsource/ibm-plex-sans-condensed/600.css",
    ]


@pytest.mark.parametrize("credit", README_CREDITS)
def test_ac6_readme_credits_the_fonts(credit: str) -> None:
    assert credit in README_PATH.read_text(encoding="utf-8")
