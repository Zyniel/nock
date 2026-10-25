"""Shared setup of the tests of spec 048: plain pages and states.

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 048 uses: the values of the spec, the
seeds of its "Test harness" (`PUBLIC`, the account answers, `REPLAY`,
`REPLAY_FX02`, `REPLAY_EMPTY`), the helpers that open the three pages in each of
their states, and the readers and checks of the frames, cards, fields, state
lines and the replay. The tests are in these files, one per group of criteria:

- `test_spec_048_ac01_ac02_shared_recap.py`: AC-1 and AC-2.
- `test_spec_048_ac03_ac04_account_and_deletion.py`: AC-3 and AC-4.
- `test_spec_048_ac05_account_states.py`: AC-5.
- `test_spec_048_ac06_ac08_ops_page.py`: AC-6 to AC-8.
- `test_spec_048_ac09_ac10_replay.py`: AC-9 and AC-10.
- `test_spec_048_ac11_ac12_slider_and_replay_states.py`: AC-11 and AC-12.
- `test_spec_048_ac13_no_spinner.py`: AC-13 (static).
- `test_spec_048_ac14_scans_fit_and_keys.py`: AC-14.

The ops page's helpers and the replays (`REPLAY`, `REPLAY_FX02`, `REPLAY_EMPTY`)
are in `spec048_ops_harness.py`, which builds on this module.

It reuses the harnesses of the specs it builds on: spec 046's windows (desktop
contexts in Paris time), held route, card, button and font checks and content
box; spec 043's colour and style readers; spec 042's boxes; spec 038's ops server,
token and dashboard figures; spec 033's account server and link answers; spec
035's keyboard walker; spec 047's focus ring check. Every helper that opens a
page waits for the fonts before it returns (spec 041's rule).

Readings of the spec's wording, shared by the test files:

- "The page's `header`" is the one `header` element of the page; "the page
  under it" is the colour drawn at a point 8 px below the header and 8 px from
  the window's left edge, beside the column's cards: the first ancestor of the
  element there (itself included) whose background is not transparent.
- "X holds only Y" (or "after its title only Y"): every element inside X that
  shows (a box with a width and a height) is one of the named elements, inside
  one, or an ancestor of one (a wrapper); `header` and `visually-hidden`
  elements are left out.
- "Each the next one's top 12 px or more above": the gap from one element's
  bottom to the next one's top is at least 12 px (1 px).
- A letter's look is read on the element that holds the letter's text node, and
  its background is the first ancestor of that element (itself included) whose
  background is not transparent.
- The replay's cells are placed by their boxes: a cell's row and column are its
  offset from the first cell, divided by the cell's side, rounded.

Tolerances ("Test harness"): 1 px for a position, 0.5 px for a size, 0.1 px for a
font size; colours with exact channels and alpha within 0.01.
"""

from __future__ import annotations

from collections.abc import Sequence

from playwright.sync_api import Locator, Page, Route, expect

from fonts_ready import wait_for_fonts
from nock.recap import PublicRecap
from nock.server import WEB_DIST_DIR
from spec033_harness import A_TOKEN, ANA_EMAIL, answer_link
from spec042_harness import READERS_JS, Box, box_of
from spec043_harness import (
    INK,
    MUTED,
    NAVY,
    RED,
    RULE,
    WHITE,
    WORD,
    Rgb,
    colour_matches,
    colour_of,
    fr_value,
    is_clear,
    padding_matches,
    padding_of,
    style_of,
)
from spec046_harness import (
    SUBPIXEL_PX,
    HeldRoute,
    button_colour_problems,
    card_problems,
    colour_problem,
    content_box,
    font_problems,
    fulfil_json,
    same_font,
    same_position,
    same_size,
    window_size,
)
from sure_click import click_until_pressed

# ---- Values of the spec ------------------------------------------------------------

PHONE = (360, 740)
COMPUTER = (1280, 720)
SIZES = [PHONE, COMPUTER]
SIZE_IDS = ["360x740", "1280x720"]
SMALL = (320, 568)
WAIT_TIMEOUT_MS = 10_000

PAGE_GREY: Rgb = (246, 247, 249)
GREEN: Rgb = (30, 123, 69)
CLUE_BG: Rgb = (238, 242, 248)
LOCKED: Rgb = (227, 231, 238)
PENCIL: Rgb = (85, 91, 103)
REVEAL: Rgb = (194, 65, 12)
NOCK_MARK_POINTS = "0,0 10,0 10,14 5,10 0,14"

# The entry-page frame ("Terms").
NARROW_BAR = 54.0
WIDE_BAR = 56.0
COLUMN_WIDTH = 420.0
WIDE_COLUMN_TOP = 48.0
NARROW_COLUMN_TOP = 20.0
NARROW_SIDE = 16.0
# The catalogue frame ("Terms").
CATALOGUE_COLUMN = 920.0
WIDE_CATALOGUE_PADDING = 24.0
NARROW_CATALOGUE_PADDING = 16.0
CARD_PART_GAP = 12.0

# ---- Values of the test harness ----------------------------------------------------

SHARE_TOKEN = "tok_ABCDEFGHIJKLMNOP"
SHARE_PATH = f"/recap/{SHARE_TOKEN}"
SHARE_API_ROUTE = f"**/api/recaps/{SHARE_TOKEN}"
PUBLIC = PublicRecap(grid_number=12, elapsed_ms=754000, team=("ANA", "BOB"))
PUBLIC_NO_NUMBER = PublicRecap(grid_number=None, elapsed_ms=754000, team=("ANA", "BOB"))
NOT_FOUND = {"detail": "Not Found"}

ROOM_CODE = "K7QM2X"
LINK_TOKEN = A_TOKEN  # 43 characters
SIGNED_IN: dict[str, object] = {"signed_in": True, "email": ANA_EMAIL}
SIGNED_OUT: dict[str, object] = {"signed_in": False, "email": None}
SIGN_IN_ANSWER: dict[str, object] = {
    "email": ANA_EMAIL,
    "room_code": ROOM_CODE,
    "rooms": [],
}


# ---- Comparisons -------------------------------------------------------------------


def gap_at_least(first: Box, second: Box, gap: float) -> bool:
    """Tell whether `second` starts `gap` px or more under `first` (1 px)."""
    return second.top - first.bottom >= gap - 1.0 - SUBPIXEL_PX


def box_inside(inner: Box, outer: Box) -> bool:
    """Tell whether `inner` lies inside `outer`, with 1 px of tolerance."""
    tolerance = 1.0 + SUBPIXEL_PX
    return (
        inner.left >= outer.left - tolerance
        and inner.top >= outer.top - tolerance
        and inner.right <= outer.right + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def no_horizontal_scroll(page: Page) -> bool:
    found = page.evaluate(
        "() => document.documentElement.scrollWidth <= window.innerWidth"
    )
    return found is True


# ---- Readers ---------------------------------------------------------------------

# The colour drawn at a point: the first ancestor of the element there, itself
# included, whose background is not transparent.
BACKGROUND_AT_SCRIPT = "([x, y]) => {\n" + READERS_JS + r"""
  let element = document.elementFromPoint(x, y);
  while (element !== null) {
    const colour = parseColour(getComputedStyle(element).backgroundColor);
    if (colour[3] > 0) {
      return colour;
    }
    element = element.parentElement;
  }
  return null;
}
"""

# The elements inside a container that show and are neither one of the allowed
# elements, inside one, nor an ancestor of one ("X holds only Y").
OTHERS_SCRIPT = r"""
(container, selectors) => {
  const allowed = [];
  for (const selector of selectors) {
    for (const element of container.querySelectorAll(selector)) {
      allowed.push(element);
    }
  }
  const others = [];
  for (const element of container.querySelectorAll('*')) {
    if (element.closest('header') !== null
        || element.closest('.visually-hidden') !== null) {
      continue;
    }
    const rect = element.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      continue;
    }
    let kept = false;
    for (const one of allowed) {
      if (one === element || one.contains(element) || element.contains(one)) {
        kept = true;
        break;
      }
    }
    if (!kept) {
      const testId = element.getAttribute('data-testid');
      const text = element.textContent.replace(/\s+/g, ' ').trim().slice(0, 40);
      others.push(`${element.tagName}${testId ? '#' + testId : ''} "${text}"`);
    }
  }
  return others;
}
"""

# The width of an element's text: the box of a range over its contents.
TEXT_WIDTH_SCRIPT = r"""
element => {
  const range = document.createRange();
  range.selectNodeContents(element);
  return range.getBoundingClientRect().width;
}
"""

# The element of a cell that holds its letter's text node, its style and the
# colour behind it.
LETTER_SCRIPT = "cell => {\n" + READERS_JS + r"""
  let holder = null;
  const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    if (walker.currentNode.textContent.trim() !== '') {
      holder = walker.currentNode.parentElement;
      break;
    }
  }
  if (holder === null) {
    return null;
  }
  const style = getComputedStyle(holder);
  let behind = null;
  let element = holder;
  while (element !== null) {
    const colour = parseColour(getComputedStyle(element).backgroundColor);
    if (colour[3] > 0) {
      behind = colour;
      break;
    }
    element = element.parentElement;
  }
  return {
    text: holder.textContent.trim(),
    fontSize: style.fontSize,
    fontWeight: style.fontWeight,
    fontStyle: style.fontStyle,
    colour: parseColour(style.color),
    behind: behind,
  };
}
"""

# Every element inside a container whose computed background, top border colour
# or text colour is a given colour (AC-4's "no red").
COLOURED_SCRIPT = "(container, wanted) => {\n" + READERS_JS + r"""
  const found = [];
  const elements = [container, ...container.querySelectorAll('*')];
  for (const element of elements) {
    const style = getComputedStyle(element);
    for (const name of ['backgroundColor', 'borderTopColor', 'color']) {
      const colour = parseColour(style[name]);
      if (colour[3] > 0 && colour[0] === wanted[0] && colour[1] === wanted[1]
          && colour[2] === wanted[2]) {
        found.push(`${element.tagName}#${element.getAttribute('data-testid')}`
          + ` ${name}`);
      }
    }
  }
  return found;
}
"""


# The ids of an element's `aria-describedby`, each with whether an element of
# the page has that id.
DESCRIBED_BY_SCRIPT = r"""
element => {
  const value = element.getAttribute('aria-describedby') || '';
  const ids = value.split(/\s+/).filter(id => id !== '');
  return ids.map(id => [id, document.getElementById(id) !== null]);
}
"""


def described_by(field: Locator) -> list[tuple[str, bool]]:
    """The ids of `field`'s `aria-describedby`, each with whether it names an
    element of the page."""
    found = field.evaluate(DESCRIBED_BY_SCRIPT)
    assert isinstance(found, list), found
    pairs: list[tuple[str, bool]] = []
    for item in found:
        assert isinstance(item, list), item
        pairs.append((str(item[0]), item[1] is True))
    return pairs


def described_by_problems(field: Locator, line: Locator, name: str) -> list[str]:
    """`line` has an id that is one of the ids of `field`'s `aria-describedby`
    (spec 048 AC-5 and AC-6, added after review round 1)."""
    line_id = line.get_attribute("id")
    if line_id is None or line_id == "":
        return [f"{name} has no id"]
    ids = [found_id for found_id, _ in described_by(field)]
    if line_id not in ids:
        return [f"{name}'s id {line_id!r} is not in aria-describedby {ids}"]
    return []


def background_at(page: Page, x: float, y: float) -> tuple[float, ...] | None:
    found = page.evaluate(BACKGROUND_AT_SCRIPT, [x, y])
    if found is None:
        return None
    assert isinstance(found, list), found
    return tuple(float(value) for value in found)


def others_in(container: Locator, selectors: Sequence[str]) -> list[str]:
    """What `container` shows besides the elements of `selectors` (see above)."""
    found = container.evaluate(OTHERS_SCRIPT, list(selectors))
    assert isinstance(found, list), found
    return [str(item) for item in found]


def text_width(locator: Locator) -> float:
    found = locator.evaluate(TEXT_WIDTH_SCRIPT)
    assert isinstance(found, (int, float)), found
    return float(found)


def letter_of(cell: Locator) -> dict[str, object] | None:
    """The letter a cell shows and its look, or None when it shows no text."""
    found = cell.evaluate(LETTER_SCRIPT)
    if found is None:
        return None
    assert isinstance(found, dict), found
    return found


def coloured_in(container: Locator, colour: Rgb) -> list[str]:
    found = container.evaluate(COLOURED_SCRIPT, list(colour))
    assert isinstance(found, list), found
    return [str(item) for item in found]


def font_size_of(locator: Locator) -> float:
    value = style_of(locator, "fontSize")
    return float(value.removesuffix("px"))


# ---- Checks of the frames ----------------------------------------------------------


def header_problems(page: Page, height: float, links_allowed: bool = True) -> list[str]:
    """The page's one `header`: across the top, `height` high, the mark and Nock.

    It holds the Nock mark (an `svg` whose `polygon` has `NOCK_MARK_POINTS` and is
    filled navy), the text `fr.json["app.title"]` and no `button` (and no link
    but the brand link `topbar-brand`, `client/shell.md` rule 17, when
    `links_allowed` is False).
    """
    headers = page.locator("header")
    if headers.count() != 1:
        return [f"{headers.count()} header elements"]
    header = headers.first
    width, _ = window_size(page)
    box = box_of(header)
    problems: list[str] = []
    if not (same_position(box.left, 0.0) and same_position(box.top, 0.0)):
        problems.append(f"header at {box}")
    if not same_size(box.width, width) or not same_size(box.height, height):
        problems.append(f"header {box.width} by {box.height}, not {width} by {height}")
    polygons = header.locator("svg polygon")
    marks: list[Locator] = []
    for index in range(polygons.count()):
        polygon = polygons.nth(index)
        points = " ".join((polygon.get_attribute("points") or "").split())
        if points == NOCK_MARK_POINTS:
            marks.append(polygon)
    if len(marks) != 1:
        problems.append(f"{len(marks)} Nock marks in the header")
    else:
        problems.extend(colour_problem(marks[0], "mark", "fill", NAVY))
    text = header.inner_text().strip()
    if text != fr_value("app.title"):
        problems.append(f"header reads {text!r}")
    if header.locator("button").count() != 0:
        problems.append("the header holds a button")
    other_links = header.locator('a:not([data-testid="topbar-brand"])')
    if not links_allowed and other_links.count() != 0:
        problems.append("the header holds a link other than the brand")
    return problems


def header_box(page: Page) -> Box:
    return box_of(page.locator("header").first)


def page_colour_problems(page: Page) -> list[str]:
    """The page under the header is `--nock-page` (8 px down, 8 px in)."""
    bar = header_box(page)
    colour = background_at(page, 8.0, bar.bottom + 8.0)
    if colour is None or not colour_matches(colour, PAGE_GREY):
        return [f"the page under the header is {colour}, not {PAGE_GREY}"]
    return []


def entry_frame_problems(page: Page, card: Locator) -> list[str]:
    """`card` in the entry-page frame: the header, the page grey, the column.

    At 360 by 740 the header is 54 px high and the card 328 px wide, 16 px from
    the left, its top 20 px under the header; at 1280 by 720 the header is 56 px
    high and the card 420 px wide, 430 px from the left, 48 px under the header.
    The card has the card look.
    """
    width, _ = window_size(page)
    narrow = width < 900
    problems = header_problems(page, NARROW_BAR if narrow else WIDE_BAR)
    if page.locator("header").count() != 1:
        return problems
    problems.extend(page_colour_problems(page))
    bar = header_box(page)
    box = box_of(card)
    if narrow:
        expected_width = width - 2 * NARROW_SIDE
        expected_left = NARROW_SIDE
        expected_top = NARROW_COLUMN_TOP
    else:
        expected_width = COLUMN_WIDTH
        expected_left = (width - COLUMN_WIDTH) / 2
        expected_top = WIDE_COLUMN_TOP
    if not same_size(box.width, expected_width):
        problems.append(f"card {box.width} px wide, not {expected_width}")
    if not same_position(box.left, expected_left):
        problems.append(f"card left {box.left}, not {expected_left}")
    if not same_position(box.top - bar.bottom, expected_top):
        problems.append(f"card {box.top - bar.bottom} px under the header")
    problems.extend(card_problems(card))
    return problems


# ---- Checks of the looks -----------------------------------------------------------


def card_title_problems(locator: Locator, name: str) -> list[str]:
    """The card title: 700, 20 px (1.25rem), navy."""
    return font_problems(locator, name, 20.0, "700", NAVY)


def waiting_line_problems(locator: Locator, name: str) -> list[str]:
    """A waiting or empty line: 400 15.2 px (0.95rem), muted."""
    return font_problems(locator, name, 15.2, "400", MUTED)


def error_line_problems(locator: Locator, name: str) -> list[str]:
    """The error line: 500 13.6 px (0.85rem), red."""
    return font_problems(locator, name, 13.6, "500", RED)


def done_line_problems(locator: Locator, name: str) -> list[str]:
    """The confirmation line: 500 13.6 px (0.85rem), green."""
    return font_problems(locator, name, 13.6, "500", GREEN)


def role_problems(locator: Locator, name: str, role: str | None) -> list[str]:
    actual = locator.get_attribute("role")
    if actual != role:
        return [f"{name}: role {actual!r}, not {role!r}"]
    return []


def text_problems(locator: Locator, name: str, expected: str) -> list[str]:
    actual = " ".join(locator.inner_text().split())
    if actual != " ".join(expected.split()):
        return [f"{name} reads {actual!r}, not {expected!r}"]
    return []


def radius_padding_problems(
    locator: Locator, name: str, radius: str, padding: str
) -> list[str]:
    problems: list[str] = []
    if style_of(locator, "borderTopLeftRadius") != radius:
        problems.append(f"{name}: radius {style_of(locator, 'borderTopLeftRadius')}")
    if not padding_matches(locator, padding):
        problems.append(f"{name}: padding {padding_of(locator)}")
    return problems


def all_borders_problems(locator: Locator, name: str, colour: Rgb) -> list[str]:
    """The four border sides are 1 px solid `colour`."""
    problems: list[str] = []
    for side in ("Top", "Right", "Bottom", "Left"):
        if style_of(locator, f"border{side}Width") != "1px":
            problems.append(f"{name}: border-{side} width")
        if style_of(locator, f"border{side}Style") != "solid":
            problems.append(f"{name}: border-{side} style")
        problems.extend(colour_problem(locator, name, f"border{side}Color", colour))
    return problems


def border_colour_problems(locator: Locator, name: str, colour: Rgb) -> list[str]:
    """The four border sides have the colour `colour`."""
    problems: list[str] = []
    for side in ("Top", "Right", "Bottom", "Left"):
        problems.extend(colour_problem(locator, name, f"border{side}Color", colour))
    return problems


def primary_link_problems(link: Locator, name: str) -> list[str]:
    """A link drawn as a primary button (AC-1's `share-home`).

    An `A` to `/`, navy background, white text, radius 6 px, padding 10 px 16 px,
    600 15.2 px, no underline, as wide as its text plus its padding and borders.
    """
    problems: list[str] = []
    if link.evaluate("element => element.tagName") != "A":
        problems.append(f"{name} is not an A")
    if link.get_attribute("href") != "/":
        problems.append(f"{name} href {link.get_attribute('href')}")
    problems.extend(colour_problem(link, name, "backgroundColor", NAVY))
    problems.extend(colour_problem(link, name, "color", WHITE))
    problems.extend(radius_padding_problems(link, name, "6px", "10px 16px"))
    problems.extend(font_problems(link, name, 15.2, "600"))
    if style_of(link, "textDecorationLine") != "none":
        problems.append(
            f"{name}: text-decoration {style_of(link, 'textDecorationLine')}"
        )
    sides = 0.0
    for part in ("paddingLeft", "paddingRight", "borderLeftWidth", "borderRightWidth"):
        sides += float(style_of(link, part).removesuffix("px"))
    expected = text_width(link) + sides
    width = box_of(link).width
    if not same_position(width, expected):
        problems.append(f"{name} {width} px wide, its text and padding {expected}")
    return problems


def quiet_button_problems(locator: Locator, name: str) -> list[str]:
    """The quiet look: word-blue background, navy text, a clear border."""
    problems = colour_problem(locator, name, "backgroundColor", WORD)
    problems.extend(colour_problem(locator, name, "color", NAVY))
    if not is_clear(colour_of(locator, "borderTopColor")):
        problems.append(f"{name}: border {colour_of(locator, 'borderTopColor')}")
    return problems


def secondary_button_problems(locator: Locator, name: str) -> list[str]:
    """Secondary colours, radius 6 px and padding 10 px 16 px."""
    problems = [
        f"{name}: {item}" for item in button_colour_problems(locator, "secondary")
    ]
    problems.extend(radius_padding_problems(locator, name, "6px", "10px 16px"))
    return problems


def field_label_problems(locator: Locator, name: str) -> list[str]:
    """The field label: 600 13.6 px (0.85rem), ink."""
    return font_problems(locator, name, 13.6, "600", INK)


def text_input_problems(
    field: Locator, card: Locator, name: str, border: Rgb = RULE
) -> list[str]:
    """The text input of AC-5: 1 px solid border, radius 6 px, padding 10 px 12 px,
    16 px, as wide as the card's content (1 px)."""
    problems = all_borders_problems(field, name, border)
    problems.extend(radius_padding_problems(field, name, "6px", "10px 12px"))
    if not same_font(font_size_of(field), 16.0):
        problems.append(f"{name}: font-size {style_of(field, 'fontSize')}")
    inner = content_box(card)
    if not same_position(box_of(field).width, inner.width):
        problems.append(f"{name} {box_of(field).width} wide, content {inner.width}")
    return problems


def ring_problems(locator: Locator, name: str) -> list[str]:
    """The focus ring: a `2px` `solid` navy outline at offset `2px`."""
    problems: list[str] = []
    width = style_of(locator, "outlineWidth")
    outline_style = style_of(locator, "outlineStyle")
    offset = style_of(locator, "outlineOffset")
    if width != "2px" or outline_style != "solid" or offset != "2px":
        problems.append(f"{name}: outline {width} {outline_style}, offset {offset}")
    problems.extend(colour_problem(locator, name, "outlineColor", NAVY))
    return problems


# ---- The shared recap page ----------------------------------------------------------


def route_share_html(page: Page, base_url: str) -> None:
    """Answer `GET /recap/tok_ABCDEFGHIJKLMNOP` with the built `index.html`.

    The live server serves that path only for a token it knows, and the recap is
    the API route's answer, so the page itself is routed too.
    """
    index_html = (WEB_DIST_DIR / "index.html").read_text(encoding="utf-8")

    def answer(route: Route) -> None:
        route.fulfill(status=200, content_type="text/html", body=index_html)

    page.route(f"{base_url}{SHARE_PATH}", answer)


def answer_share(page: Page, status: int, body: object) -> None:
    def answer(route: Route) -> None:
        fulfil_json(route, status, body)

    page.route(SHARE_API_ROUTE, answer)


def open_share(page: Page, base_url: str, public: PublicRecap = PUBLIC) -> None:
    """Open the shared recap page with its API route answering `public`."""
    route_share_html(page, base_url)
    answer_share(page, 200, public.model_dump(mode="json"))
    page.goto(f"{base_url}{SHARE_PATH}")
    expect(page.get_by_test_id("share-team")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_for_fonts(page)


def open_share_loading(page: Page, base_url: str) -> HeldRoute:
    """Open the shared recap page with its API route held unanswered."""
    route_share_html(page, base_url)
    held = HeldRoute(page, SHARE_API_ROUTE)
    page.goto(f"{base_url}{SHARE_PATH}")
    expect(page.get_by_test_id("recap-loading")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_for_fonts(page)
    return held


def open_share_unavailable(page: Page, base_url: str) -> None:
    """Open the shared recap page with its API route answering 404."""
    route_share_html(page, base_url)
    answer_share(page, 404, NOT_FOUND)
    page.goto(f"{base_url}{SHARE_PATH}")
    expect(page.get_by_test_id("share-error")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_for_fonts(page)


# ---- The account page ---------------------------------------------------------------


class AccountMock:
    """The account routes of a page (spec 033 AC-9's mocked routes).

    `GET /api/account` answers `status` (a status and a body) or is held while it
    is None; `DELETE /api/account` answers 204; `POST /api/account/sign-in`
    answers 200 with `SIGN_IN_ANSWER` (`room_code` `K7QM2X`), or `sign_in` when
    it is another status, or is held while it is None; each link request gets the
    next status of `link_statuses` (the last one again once they are used up);
    `PUT /api/account/rooms` and `POST /api/account/sign-out` answer 204. Every
    request is recorded as (method, URL).
    """

    def __init__(
        self,
        status: tuple[int, object] | None = (200, SIGNED_OUT),
        sign_in: int | None = 200,
        link_statuses: Sequence[int] = (202,),
    ) -> None:
        self.status = status
        self.sign_in = sign_in
        self.link_statuses = list(link_statuses)
        self.link_count = 0
        self.held: list[Route] = []
        self.requests: list[tuple[str, str]] = []

    def install(self, page: Page) -> None:
        """Route the page's account requests to these answers."""
        page.route("**/api/account", self.account)
        page.route("**/api/account/sign-in", self.sign_in_route)
        page.route("**/api/account/link", self.link)
        page.route("**/api/account/rooms", self.no_content)
        page.route("**/api/account/sign-out", self.no_content)

    def keep(self, route: Route) -> None:
        self.requests.append((route.request.method, route.request.url))

    def account(self, route: Route) -> None:
        """`GET` or `DELETE /api/account`."""
        self.keep(route)
        if route.request.method == "DELETE":
            route.fulfill(status=204, body="")
        elif self.status is None:
            self.held.append(route)
        else:
            fulfil_json(route, self.status[0], self.status[1])

    def sign_in_route(self, route: Route) -> None:
        self.keep(route)
        if self.sign_in is None:
            self.held.append(route)
        elif self.sign_in == 200:
            fulfil_json(route, 200, SIGN_IN_ANSWER)
        else:
            fulfil_json(route, self.sign_in, NOT_FOUND)

    def link(self, route: Route) -> None:
        self.keep(route)
        index = min(self.link_count, len(self.link_statuses) - 1)
        self.link_count += 1
        answer_link(route, self.link_statuses[index])

    def no_content(self, route: Route) -> None:
        self.keep(route)
        route.fulfill(status=204, body="")

    def deletions(self) -> int:
        """How many `DELETE /api/account` the page sent."""
        return sum(1 for method, _ in self.requests if method == "DELETE")


def account_card(page: Page) -> Locator:
    return page.get_by_test_id("account-card")


def expect_account_state(page: Page, state: str) -> None:
    expect(page.get_by_test_id("account-page")).to_have_attribute(
        "data-state", state, timeout=WAIT_TIMEOUT_MS
    )


def open_account(
    page: Page, base_url: str, mock: AccountMock, state: str, link: bool = False
) -> None:
    """Open `/account` (or `/account#<token>` when `link`) and wait for `state`."""
    mock.install(page)
    fragment = f"#{LINK_TOKEN}" if link else ""
    page.goto(f"{base_url}/account{fragment}")
    expect_account_state(page, state)
    wait_for_fonts(page)


def open_signed_in(page: Page, base_url: str) -> AccountMock:
    """Sign in through `/account#<token>`, answered with `room_code` `K7QM2X`."""
    mock = AccountMock(status=(200, SIGNED_IN))
    open_account(page, base_url, mock, "signed_in", link=True)
    expect(page.get_by_test_id("account-room-link")).to_be_visible()
    wait_for_fonts(page)
    return mock


def ask_deletion(page: Page) -> None:
    """Click `account-delete` and wait for the panel."""
    page.get_by_test_id("account-delete").click()
    expect(page.get_by_test_id("account-delete-panel")).to_be_visible()


def submit_address(page: Page, address: str) -> None:
    """Type `address`, check the field holds it, then submit the form."""
    field = page.get_by_test_id("account-email-input")
    field.fill(address)
    expect(field).to_have_value(address)
    # 2026-10-23: Firefox under load lost the press; main's run after #43.
    click_until_pressed(page.get_by_test_id("account-email-submit"))
