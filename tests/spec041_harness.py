"""Shared setup of the tests of spec 041: visual foundation.

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 041 uses: the token tables of the
spec's "Public interface", the probes, the readers of computed colours and
shadows, the room pages and the comment removers of the static checks. The tests
are in these files, one per group of criteria:

- `test_spec_041_ac01_ac04_tokens_and_page_base.py`: AC-1 to AC-4.
- `test_spec_041_ac05_ac06_fonts.py`: AC-5, AC-6.
- `test_spec_041_ac07_ac08_focus_ring.py`: AC-7, AC-8.
- `test_spec_041_ac09_ac14_primitives.py`: AC-9 to AC-14.
- `test_spec_041_ac15_room_colours.py`: AC-15.
- `test_spec_041_ac16_ac17_flash.py`: AC-16, AC-17.
- `test_spec_041_ac18_ac20_static_scans.py`: AC-18 to AC-20.
- `test_spec_041_ac21_form_controls.py`: AC-21.

It reuses spec 035's harness: the colour helpers of `tests/colour_contrast.js`
(`parseColour`, `over`, `contrast`), the reference catalogue CAT of spec 004, the
mocked room (`open_room`) and the keyboard `Walker`. Each test file defines its
fixtures (`fx01_grid`, `catalogue`) as thin wrappers, as spec 035's files do: a
fixture imported from here would be an unused import for ruff.

Probes (spec 041, "Test harness"): a criterion that checks a token or a primitive
appends its own elements to `body` with `page.evaluate`, then reads
`getComputedStyle`. A token is read through a probe whose style uses it, never
from the custom property's text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, BrowserContext, Locator, Page, expect

from fonts_ready import wait_for_fonts
from nock.protocol import LetterChanged
from spec013_harness import COARSE_POINTER_SCRIPT
from spec035_harness import COLOUR_CONTRAST_JS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
WEB_SRC_DIR = WEB_DIR / "src"
WEB_DIST_DIR = WEB_DIR / "dist"
WEB_DIST_ASSETS_DIR = WEB_DIST_DIR / "assets"
README_PATH = PROJECT_ROOT / "README.md"
PACKAGE_JSON_PATH = WEB_DIR / "package.json"
ICONS_PATH = WEB_SRC_DIR / "lib" / "icons.ts"

# Spec 040's message when the client is not built.
MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"

WAIT_TIMEOUT_MS = 5000

# A colour as `parseColour` of tests/colour_contrast.js gives it: red, green and
# blue from 0 to 255, then alpha from 0 to 1.
Colour = tuple[float, float, float, float]
Rgb = tuple[int, int, int]

ALPHA_TOLERANCE = 0.01
MIX_TOLERANCE = 1.0


def hex_to_rgb(hex_colour: str) -> Rgb:
    """Read `#RRGGBB` as its three channels."""
    digits = hex_colour.removeprefix("#")
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


# ---- The tables of "Public interface" -------------------------------------------

COLOUR_TOKENS: dict[str, str] = {
    "--nock-navy": "#1B2F55",
    "--nock-ink": "#14181F",
    "--nock-muted": "#5E6573",
    "--nock-pencil": "#555B67",
    "--nock-white": "#FFFFFF",
    "--nock-page": "#F6F7F9",
    "--nock-clue-bg": "#EEF2F8",
    "--nock-clue-ink": "#1B2230",
    "--nock-word": "#E6EDF9",
    "--nock-selected": "#CFDDF3",
    "--nock-locked": "#E3E7EE",
    "--nock-rule": "#9AA3B2",
    "--nock-line": "#DDE2EA",
    "--nock-red": "#B42318",
    "--nock-reveal": "#C2410C",
    "--nock-green": "#1E7B45",
    "--nock-green-bg": "#E6F2EA",
    "--nock-key": "#E9ECF1",
    "--nock-keyboard-bg": "#D9DEE6",
    "--nock-handle": "#C5CCD8",
    "--nock-thumb": "#C9D2E0",
}

# Each translucent token: its channels and its alpha.
TRANSLUCENT_TOKENS: dict[str, tuple[Rgb, float]] = {
    "--nock-scrim": ((20, 24, 31), 0.35),
    "--nock-scrim-dialog": ((20, 24, 31), 0.38),
    "--nock-dot-ring": ((20, 24, 31), 0.55),
    "--nock-key-shadow": ((20, 24, 31), 0.25),
    "--nock-shadow-soft": ((20, 24, 31), 0.35),
    "--nock-shadow": ((20, 24, 31), 0.45),
    "--nock-shadow-strong": ((20, 24, 31), 0.50),
    "--nock-legend-bg": ((255, 255, 255), 0.96),
    "--nock-pen-fill": ((255, 255, 255), 0.35),
}

# `--player-colour-N` and `--player-ink-N`, by N.
PLAYER_COLOURS: tuple[str, ...] = (
    "#604800",
    "#608838",
    "#008878",
    "#6838E0",
    "#B83850",
    "#D000A0",
    "#B06000",
    "#784030",
)
PLAYER_INKS: tuple[str, ...] = (
    "#604800",
    "#4B6A2C",
    "#006D60",
    "#6838E0",
    "#AD354B",
    "#B3008A",
    "#904F00",
    "#784030",
)


def player_colour_token(index: int) -> str:
    """The name of the CSS token holding player colour `index`."""
    return f"--player-colour-{index}"


def player_ink_token(index: int) -> str:
    """The name of the CSS token holding the ink for player colour `index`."""
    return f"--player-ink-{index}"


def colour_token_rgb(token: str) -> Rgb:
    """The channels of a token of the first table of "Colour tokens"."""
    return hex_to_rgb(COLOUR_TOKENS[token])


NAVY = colour_token_rgb("--nock-navy")
INK = colour_token_rgb("--nock-ink")
MUTED = colour_token_rgb("--nock-muted")
PENCIL = colour_token_rgb("--nock-pencil")
WHITE = colour_token_rgb("--nock-white")
CLUE_BG = colour_token_rgb("--nock-clue-bg")
CLUE_INK = colour_token_rgb("--nock-clue-ink")
WORD = colour_token_rgb("--nock-word")
SELECTED = colour_token_rgb("--nock-selected")
LOCKED = colour_token_rgb("--nock-locked")
RULE = colour_token_rgb("--nock-rule")
LINE = colour_token_rgb("--nock-line")
RED = colour_token_rgb("--nock-red")

UI_FONT_STACK = ["Source Sans 3", "Segoe UI", "system-ui", "sans-serif"]
CLUE_FONT_STACK = [
    "IBM Plex Sans Condensed",
    "Arial Narrow",
    "Roboto Condensed",
    "sans-serif",
]

MIN_TEXT_CONTRAST = 4.5

# ---- In-page scripts --------------------------------------------------------------

# The colour helpers of tests/colour_contrast.js (spec 035), then the readers of
# this spec: `readColour` parses one computed colour property, `readShadow` the
# one shadow of a computed `box-shadow` (its colour parsed, its four lengths in
# px), `textContrast` the contrast of an element's text against its own
# background (composited over white), by spec 035's formula.
STYLE_READERS_JS = COLOUR_CONTRAST_JS + r"""
function readColour(element, property) {
  return parseColour(getComputedStyle(element)[property]);
}
function readShadow(element) {
  const text = getComputedStyle(element).boxShadow;
  const colourMatch = text.match(/(rgba?|color|hsla?|oklch|oklab|lab|lch)\([^)]*\)/);
  const colourText = colourMatch === null ? '' : colourMatch[0];
  const rest = text.replace(colourText, ' ');
  const lengths = [];
  for (const part of rest.trim().split(/\s+/)) {
    if (part.endsWith('px') || part === '0') {
      lengths.push(parseFloat(part));
    }
  }
  return {
    text: text,
    colour: colourText === '' ? null : parseColour(colourText),
    lengths: lengths,
  };
}
function textContrast(element) {
  const style = getComputedStyle(element);
  const background = over(parseColour(style.backgroundColor), WHITE);
  const text = over(parseColour(style.color), background);
  return contrast(text, background);
}
"""

READ_COLOUR_SCRIPT = (
    "(element, property) => {\n"
    + STYLE_READERS_JS
    + "\nreturn readColour(element, property);\n}"
)
READ_SHADOW_SCRIPT = (
    "element => {\n" + STYLE_READERS_JS + "\nreturn readShadow(element);\n}"
)
TEXT_CONTRAST_SCRIPT = (
    "element => {\n" + STYLE_READERS_JS + "\nreturn textContrast(element);\n}"
)

# The colour of a CSS colour value as the page computes it: a probe `div` whose
# `color` is that value, appended to `body`, read, then removed.
VALUE_COLOUR_SCRIPT = "value => {\n" + STYLE_READERS_JS + r"""
const probe = document.createElement('div');
probe.style.cssText = `color: ${value}`;
probe.textContent = 'probe';
document.body.appendChild(probe);
const colour = readColour(probe, 'color');
probe.remove();
return colour;
}"""

# Appends the first element of `markup` to `body`, marked with
# `data-spec041-probe="<name>"` so that a locator finds it.
ADD_PROBE_SCRIPT = r"""
([name, markup]) => {
  const holder = document.createElement('template');
  holder.innerHTML = markup.trim();
  const probe = holder.content.firstElementChild;
  probe.setAttribute('data-spec041-probe', name);
  // The page's Content-Security-Policy does not apply a `style` attribute that
  // markup brings in (Firefox even empties it when the element joins the page);
  // the same declarations set through the CSSOM, before that, apply.
  const styled = [probe, ...probe.querySelectorAll('[style]')];
  for (const element of styled) {
    if (element.hasAttribute('style')) {
      element.style.cssText = element.getAttribute('style');
    }
  }
  document.body.appendChild(probe);
}
"""

# ---- Pages ------------------------------------------------------------------------


def open_catalogue(page: Page, base_url: str) -> None:
    """Open `/` and wait until `catalogue-page` shows."""
    page.goto(f"{base_url}/")
    expect(page.get_by_test_id("catalogue-page")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_for_fonts(page)


def add_probe(page: Page, name: str, markup: str) -> Locator:
    """Append a probe element to `body` and return a locator for it.

    Args:
        page: A page that shows its content.
        name: A name for the probe, unique on the page.
        markup: HTML whose first element is the probe; it may hold children.

    Returns:
        The probe element (the first element of `markup`).
    """
    page.evaluate(ADD_PROBE_SCRIPT, [name, markup])
    return page.locator(f'[data-spec041-probe="{name}"]')


def touch_context(browser: Browser, browser_name: str) -> BrowserContext:
    """A 360 by 740 touch context, as spec 035 AC-10's (spec 009's harness).

    Firefox has no `is_mobile`; Firefox and WebKit get the script that makes
    `matchMedia("(pointer: coarse)")` match (spec 013's harness).
    """
    viewport = {"width": 360, "height": 740}
    if browser_name == "firefox":
        context = browser.new_context(viewport=viewport, has_touch=True)
    else:
        context = browser.new_context(viewport=viewport, has_touch=True, is_mobile=True)
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    return context


def cell_at(page: Page, row: int, column: int) -> Locator:
    """Return a locator for the grid cell at `row` and `column`."""
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def letter_changed_frame(
    seq: int, row: int, column: int, letter: str, player_id: str, pencil: bool
) -> str:
    """A `letter_changed` event as the mocked server sends it."""
    event = LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=pencil,
        player_id=player_id,
    )
    return event.model_dump_json()


# ---- Computed styles ----------------------------------------------------------


def style_of(locator: Locator, property_name: str) -> str:
    """The computed style property `property_name` (camelCase) of an element."""
    value = locator.evaluate(
        "(element, name) => getComputedStyle(element)[name]", property_name
    )
    assert isinstance(value, str)
    return value


def px(value: str) -> float:
    """Read a computed length such as `15.2px` as a number of px."""
    if not value.endswith("px"):
        pytest.fail(f"{value!r} is not a length in px")
    return float(value.removesuffix("px"))


def to_colour(found: object) -> Colour:
    """Check and convert what `parseColour` returned to the page."""
    assert isinstance(found, list), found
    assert len(found) == 4, found
    channels: list[float] = []
    for value in found:
        assert isinstance(value, (int, float)), found
        channels.append(float(value))
    return (channels[0], channels[1], channels[2], channels[3])


def colour_of(locator: Locator, property_name: str) -> Colour:
    """The computed colour property `property_name` (camelCase), parsed."""
    found = locator.evaluate(READ_COLOUR_SCRIPT, property_name)
    return to_colour(found)


def value_colour(page: Page, value: str) -> Colour:
    """The colour a probe with `color: <value>` computes to, parsed."""
    return to_colour(page.evaluate(VALUE_COLOUR_SCRIPT, value))


def token_colour(page: Page, token: str) -> Colour:
    """The colour of a token, read through a probe with `color: var(<token>)`."""
    return value_colour(page, f"var({token})")


def text_contrast(locator: Locator) -> float:
    """The contrast of an element's text against its own background."""
    ratio = locator.evaluate(TEXT_CONTRAST_SCRIPT)
    assert isinstance(ratio, (int, float))
    return float(ratio)


class Shadow(NamedTuple):
    """One shadow of a computed `box-shadow`."""

    text: str
    colour: Colour | None
    x: float
    y: float
    blur: float
    spread: float


def shadow_of(locator: Locator) -> Shadow:
    """The one shadow of an element's computed `box-shadow`."""
    found = locator.evaluate(READ_SHADOW_SCRIPT)
    assert isinstance(found, dict)
    text = str(found["text"])
    lengths = found["lengths"]
    assert isinstance(lengths, list)
    if found["colour"] is None or len(lengths) != 4:
        pytest.fail(f"box-shadow {text!r} is not one shadow with four lengths")
    return Shadow(
        text=text,
        colour=to_colour(found["colour"]),
        x=float(lengths[0]),
        y=float(lengths[1]),
        blur=float(lengths[2]),
        spread=float(lengths[3]),
    )


def font_families(value: str) -> list[str]:
    """A computed `font-family` as a list of family names, quotes removed."""
    families: list[str] = []
    for part in value.split(","):
        families.append(part.strip().strip('"').strip("'"))
    return families


# ---- Colour assertions ----------------------------------------------------------


def assert_colour(actual: Colour, expected: Rgb, alpha: float = 1.0) -> None:
    """Exact channels and alpha within 0.01 (a token, "Test harness")."""
    channels = (actual[0], actual[1], actual[2])
    assert channels == expected, f"colour {actual} is not {expected} at {alpha}"
    assert (
        abs(actual[3] - alpha) <= ALPHA_TOLERANCE
    ), f"colour {actual} has not the alpha {alpha}"


def assert_mixed_colour(actual: Colour, expected: Rgb) -> None:
    """Channels within 1 and opaque (a `color-mix`, "Test harness")."""
    for index in range(3):
        assert (
            abs(actual[index] - expected[index]) <= MIX_TOLERANCE
        ), f"colour {actual} is not within 1 of {expected}"
    assert abs(actual[3] - 1.0) <= ALPHA_TOLERANCE, f"colour {actual} is not opaque"


def assert_transparent(actual: Colour) -> None:
    """Alpha 0, whatever the channels."""
    assert abs(actual[3]) <= ALPHA_TOLERANCE, f"colour {actual} is not transparent"


# ---- Comment removal for the static checks ------------------------------------

SCRIPT_BLOCK = re.compile(
    r"<script\b[^>]*>(.*?)</script\s*>", re.DOTALL | re.IGNORECASE
)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.DOTALL | re.IGNORECASE)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def remove_css_comments(css: str) -> str:
    """Remove every `/* ... */` comment of a CSS text."""
    return CSS_COMMENT.sub(" ", css)


def remove_html_comments(markup: str) -> str:
    """Remove every `<!-- ... -->` comment of a markup text."""
    return HTML_COMMENT.sub(" ", markup)


def remove_script_comments(code: str) -> str:
    """Remove the `//` and `/* ... */` comments of a script.

    Quoted strings (single, double and backtick quotes) are kept as written, so a
    `//` inside a string (a URL) is not taken for a comment. A single or double
    quoted string ends at the end of its line at the latest, so that a quote
    inside a regular expression literal never hides the lines after it.
    """
    kept: list[str] = []
    index = 0
    quote = ""
    while index < len(code):
        character = code[index]
        if quote != "":
            kept.append(character)
            if character == "\\" and index + 1 < len(code):
                kept.append(code[index + 1])
                index += 2
                continue
            if character == quote or (character == "\n" and quote != "`"):
                quote = ""
            index += 1
            continue
        if code.startswith("//", index):
            line_end = code.find("\n", index)
            index = len(code) if line_end == -1 else line_end
            continue
        if code.startswith("/*", index):
            comment_end = code.find("*/", index + 2)
            index = len(code) if comment_end == -1 else comment_end + 2
            kept.append(" ")
            continue
        if character in "'\"`":
            quote = character
        kept.append(character)
        index += 1
    return "".join(kept)


class SvelteParts(NamedTuple):
    """A `.svelte` file split into its parts, comments removed."""

    scripts: list[str]
    styles: list[str]
    markup: str


def split_svelte(text: str) -> SvelteParts:
    """Split a `.svelte` file into its scripts, its styles and its markup.

    Comments are removed: `//` and `/* ... */` in the scripts, `/* ... */` in the
    styles and `<!-- ... -->` in the markup.
    """
    scripts: list[str] = []
    for match in SCRIPT_BLOCK.finditer(text):
        scripts.append(remove_script_comments(match.group(1)))
    styles: list[str] = []
    for match in STYLE_BLOCK.finditer(text):
        styles.append(remove_css_comments(match.group(1)))
    markup = SCRIPT_BLOCK.sub(" ", text)
    markup = STYLE_BLOCK.sub(" ", markup)
    markup = remove_html_comments(markup)
    return SvelteParts(scripts=scripts, styles=styles, markup=markup)


def source_files(*suffixes: str) -> list[Path]:
    """The files under `web/src` with one of `suffixes`, sorted."""
    found: list[Path] = []
    for path in sorted(WEB_SRC_DIR.rglob("*")):
        if path.is_file() and path.suffix in suffixes:
            found.append(path)
    return found


def require_build() -> None:
    """Fail with spec 040's message when `web/dist/index.html` is missing."""
    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)
