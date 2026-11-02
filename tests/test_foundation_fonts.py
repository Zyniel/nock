"""Tests of `client/foundation.md` AC-15 and AC-16: the fonts are served in
their `latin` and `latin-ext` subsets only, and the room page preloads the grid's
two faces (rule 5).

AC-15: the built client declares its font faces for the `latin` and `latin-ext`
subsets only, and ships no font file of another subset.

AC-16: `/r/ABC123` preloads, from Nock's origin, the `latin` files of Source Sans 3 at
500 and of IBM Plex Sans Condensed at 600.

AC-15 reads the built files of `web/dist/assets` with Python only. AC-16 runs in a
browser on the live server with the room's socket mocked.

Readings where the spec leaves room:

- A font file or a face is of the subset its `@fontsource` name says:
  `<family>-<subset>-<weight>-<style>-<hash>.woff2` (or `.woff`), the subset being
  `latin` or `latin-ext` (`cyrillic-ext`, `greek`, `vietnamese`... are others).
- "Declares its font faces for the subsets only": every `@font-face` of the built CSS
  has `src` files of those two subsets; the eight faces of `client/foundation.md` rule 4
  (Source Sans 3 at 400, 500, 600, 700 and in italic 500 and 700, IBM Plex Sans
  Condensed at 500 and 600) are each declared in both.
- "Preloads" is a `<link rel="preload" as="font">` of the page, once the nickname form
  shows, whose `href` is a file of the built client on the page's own origin. The
  files are the `woff2` ones, the first of each face's `src`. The preloads may be
  more than the two; these two have to be among them, and the browser has to have
  fetched them, each answered 200.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Browser, Page, Request

from shell_harness import ASSETS_DIR, built_files
from spec046_harness import OpenWindow, open_nickname_card, window_opener

SUBSETS = {"latin", "latin-ext"}
FONT_FILE = re.compile(
    r"^(?P<family>source-sans-3|ibm-plex-sans-condensed)-(?P<subset>[a-z-]+?)"
    r"-(?P<weight>\d{3})-(?P<style>normal|italic)-[^.]+\.(?P<format>woff2?)$"
)
FONT_FACE_BLOCK = re.compile(r"@font-face\s*\{([^}]*)\}")
CSS_URL = re.compile(r"url\(\s*[\"']?([^)\"']+)[\"']?\s*\)")
FAMILY_RULE = re.compile(r"font-family\s*:\s*[\"']?([^;\"']+)[\"']?")
WEIGHT_RULE = re.compile(r"font-weight\s*:\s*(\d+)")
STYLE_RULE = re.compile(r"font-style\s*:\s*(normal|italic)")

# The eight faces: (family as the file names write it, weight, style).
FACES = [
    ("source-sans-3", "400", "normal"),
    ("source-sans-3", "500", "normal"),
    ("source-sans-3", "600", "normal"),
    ("source-sans-3", "700", "normal"),
    ("source-sans-3", "500", "italic"),
    ("source-sans-3", "700", "italic"),
    ("ibm-plex-sans-condensed", "500", "normal"),
    ("ibm-plex-sans-condensed", "600", "normal"),
]
PRELOADED = [
    r"/assets/source-sans-3-latin-500-normal-[^/]+\.woff2$",
    r"/assets/ibm-plex-sans-condensed-latin-600-normal-[^/]+\.woff2$",
]

FONT_PRELOADS_SCRIPT = """
() => [...document.querySelectorAll('link[rel="preload"]')]
  .filter(link => link.getAttribute('as') === 'font')
  .map(link => link.href)
"""


class DeclaredFace(NamedTuple):
    """One `@font-face` of the built CSS, by the files its `src` names."""

    family: str
    weight: str
    style: str
    file_names: list[str]


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


# ---- Reading the build  --------------------------------------------------------------


def declared_faces() -> list[DeclaredFace]:
    """Every `@font-face` of the built CSS."""
    faces: list[DeclaredFace] = []
    for path in built_files(".css"):
        css = path.read_text(encoding="utf-8")
        for block in FONT_FACE_BLOCK.finditer(css):
            body = block.group(1)
            family = FAMILY_RULE.search(body)
            weight = WEIGHT_RULE.search(body)
            style = STYLE_RULE.search(body)
            assert family is not None, body
            assert weight is not None, body
            names: list[str] = []
            for url in CSS_URL.finditer(body):
                names.append(urlsplit(url.group(1)).path.rsplit("/", 1)[-1])
            faces.append(
                DeclaredFace(
                    family.group(1),
                    weight.group(1),
                    "normal" if style is None else style.group(1),
                    names,
                )
            )
    return faces


def subset_of(file_name: str) -> str:
    """The subset a font file's name says; fails for a name of another shape."""
    found = FONT_FILE.match(file_name)
    assert found is not None, f"not a fontsource file name: {file_name}"
    return found.group("subset")


def font_files() -> list[str]:
    """The names of the font files in `web/dist/assets`."""
    names: list[str] = []
    for suffix in (".woff2", ".woff", ".ttf", ".otf", ".eot"):
        for path in built_files(suffix):
            names.append(path.name)
    return names


# ---- AC-15  --------------------------------------------------------------------------


def test_ac15_every_declared_face_is_of_the_latin_or_latin_ext_subset() -> None:
    faces = declared_faces()

    other_subsets: list[str] = []
    for face in faces:
        assert face.file_names != [], face
        for name in face.file_names:
            if subset_of(name) not in SUBSETS:
                other_subsets.append(name)

    assert faces != []
    assert other_subsets == []


def test_ac15_each_of_the_eight_faces_is_declared_in_both_subsets() -> None:
    declared: set[tuple[str, str, str, str]] = set()
    for face in declared_faces():
        family_file = face.family.lower().replace(" ", "-")
        for name in face.file_names:
            declared.add((family_file, face.weight, face.style, subset_of(name)))

    expected: set[tuple[str, str, str, str]] = set()
    for family_file, weight, style in FACES:
        for subset in SUBSETS:
            expected.add((family_file, weight, style, subset))
    assert declared == expected


def test_ac15_no_font_file_of_another_subset_is_shipped() -> None:
    names = font_files()

    other_subsets = [name for name in names if subset_of(name) not in SUBSETS]

    assert names != []
    assert other_subsets == []


@pytest.mark.parametrize(
    ("name", "subset"),
    [
        ("source-sans-3-latin-400-normal-DQi5PRDE.woff2", "latin"),
        ("source-sans-3-latin-ext-500-italic-B76wlzAS.woff", "latin-ext"),
        (
            "ibm-plex-sans-condensed-cyrillic-ext-600-normal-DegcPR6g.woff2",
            "cyrillic-ext",
        ),
        ("source-sans-3-vietnamese-700-normal--5ui7us-.woff2", "vietnamese"),
    ],
)
def test_ac15_the_subset_reader_reads_the_subset_of_a_file_name(
    name: str, subset: str
) -> None:
    assert subset_of(name) == subset


# ---- AC-16  --------------------------------------------------------------------------


def font_preloads(page: Page) -> list[str]:
    """The `href` of each `<link rel="preload" as="font">` of the page."""
    found = page.evaluate(FONT_PRELOADS_SCRIPT)
    assert isinstance(found, list), found
    return [str(href) for href in found]


def test_ac16_the_room_page_preloads_the_latin_files_of_the_grid_faces(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    requests: list[Request] = []

    def keep(request: Request) -> None:
        requests.append(request)

    page.on("request", keep)

    open_nickname_card(page, live_server)
    hrefs = font_preloads(page)

    origin = urlsplit(live_server)
    for pattern in PRELOADED:
        matching = [href for href in hrefs if re.search(pattern, href)]
        assert len(matching) == 1, (pattern, hrefs)
        url = urlsplit(matching[0])
        assert (url.scheme, url.netloc) == (origin.scheme, origin.netloc), matching
        assert (ASSETS_DIR / url.path.rsplit("/", 1)[-1]).is_file(), matching
        fetched = [request for request in requests if request.url == matching[0]]
        assert fetched != [], f"{matching[0]} was never fetched"
        response = fetched[0].response()
        assert response is not None, matching
        assert response.status == 200, matching
