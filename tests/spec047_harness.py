"""Shared setup of the tests of spec 047: the room overlays.

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 047 uses: the values of the spec, the
frames of its "Test harness" (`VOTE_ROOM`, `VOTE`, `CLOSED(outcome)`, `SOLVED`,
`RECAP`), the helpers that open those pages, and the readers and checks of the
banner, the recap and the notes. The tests are in these files, one per group of
criteria:

- `test_spec_047_ac01_ac03_vote_banner.py`: AC-1 and AC-3 (the banner's look,
  the line after a ballot).
- `test_spec_047_ac02_countdown.py`: AC-2 (the seconds and the bar, on
  Playwright's page clock).
- `test_spec_047_ac04_ac05_end_of_a_vote.py`: AC-4 and AC-5 (the banner leaves,
  the stream line, the note).
- `test_spec_047_ac06_end_band.py`: AC-6 (the end band on narrow windows).
- `test_spec_047_ac07_ac08_recap_frame_and_parts.py`: AC-7 and AC-8.
- `test_spec_047_ac09_recap_rows.py`: AC-9.
- `test_spec_047_ac10_ac11_share_and_states.py`: AC-10 (no clipboard) and AC-11.
- `test_spec_047_ac10_copied_line.py`: AC-10's clipboard check, Chromium only
  (it times the 2-second « Lien copié » line).
- `test_spec_047_ac12_chat_notes_and_muted_box.py`: AC-12.
- `test_spec_047_ac13_keyboard.py`: AC-13.
- `test_spec_047_ac14_scans_and_keys.py`: AC-14.

It reuses the harnesses of the specs it builds on, as spec 047's "Test harness"
says: spec 043's mocked room, snapshots, frames and readers of boxes, labels,
colours and pictograms; spec 044's `SOLVED` and `FULL_WRONG`; spec 028's recap
route and `Recap` JSON; spec 046's held route, content box and button colours;
spec 027's frozen page clock; spec 019's desktop and touch windows. Every helper
that opens a page waits for the fonts before it returns (spec 041's rule).

Tolerances ("Test harness"): 1 px for a position, 0.5 px for a size, 0.1 px for a
font size or a line height; colours with exact channels and alpha within 0.01.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple

from playwright.sync_api import Locator, Page, expect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    ChatMessage,
    HelpMode,
    Reveal,
    VoteClosed,
    VoteOpened,
    VoteOutcome,
)
from spec028_harness import RECAP_ROUTE, RecapRoute, recap_body, serve_recap
from spec035_harness import COLOUR_CONTRAST_JS
from spec041_harness import shadow_of
from spec042_harness import Box, box_of, colour_of, expect_seq
from spec043_harness import (
    INK,
    WAIT_TIMEOUT_MS,
    Rgb,
    RoomMock,
    colour_matches,
    fr_format,
    fr_value,
    fx01_view,
    open_room,
    padding_matches,
    padding_of,
    players_up_to,
    px,
    same_font_size,
    same_position,
    snapshot_frame,
    style_of,
    window_box,
)
from spec046_harness import HeldRoute, content_box

# ---- Windows -------------------------------------------------------------------

PHONE = (360, 740)
COMPUTER = (1280, 720)
NARROW = (320, 568)
LOW = (568, 320)
SIZES = [PHONE, COMPUTER]
SIZE_IDS = ["360x740", "1280x720"]

FOLLOW_MS = 300  # "within 300 ms"
QUIET_MS = 300  # "makes no note": nothing within this pause

# The tokens the criteria name (spec 041), and the translucent ones' alpha.
NAVY: Rgb = (27, 47, 85)
WHITE: Rgb = (255, 255, 255)
MUTED: Rgb = (94, 101, 115)
WORD: Rgb = (230, 237, 249)
RULE: Rgb = (154, 163, 178)
RED: Rgb = (180, 35, 24)
CLUE_BG: Rgb = (238, 242, 248)
GREEN: Rgb = (30, 123, 69)
SHADOW_ALPHA = 0.45
SHADOW_STRONG_ALPHA = 0.5
DOT_RING_ALPHA = 0.55
SCRIM_DIALOG_ALPHA = 0.38
MIN_TEXT_CONTRAST = 4.5

# ---- The frames of "Test harness" -------------------------------------------------

VOTE = VoteOpened(
    seq=6,
    vote_id=1,
    player_id="p2",
    request=Reveal(target=CellTarget(row=1, column=0)),
    timeout_seconds=20,
    eligible_voters=3,
)
VOTE_QUESTION = "Bob propose de révéler une lettre."
OUTCOMES = [VoteOutcome.PASSED, VoteOutcome.REJECTED, VoteOutcome.TIMED_OUT]
OUTCOME_IDS = ["passed", "rejected", "timed_out"]

SHARE_PATH = "/recap/tok_ABCDEFGHIJKLMNOP"
RECAP = recap_body(share_path=SHARE_PATH)


def closed(outcome: VoteOutcome, seq: int = 7) -> VoteClosed:
    """`CLOSED(outcome)`: vote 1 closed with 2 yes of 3 (seq 7 by default)."""
    return VoteClosed(
        seq=seq, vote_id=1, outcome=outcome, yes_votes=2, eligible_voters=3
    )


def result_text(outcome: VoteOutcome) -> str:
    """`fr.json["vote.result.<outcome>"]`."""
    return fr_value(f"vote.result.{outcome.value}")


def seconds_text(count: int) -> str:
    """`t("vote.seconds_left", { count })`, for example `20 s`."""
    return fr_format("vote.seconds_left", count=count)


def vote_room_frame(
    grid: Grid,
    *,
    seq: int = 5,
    open_vote: VoteOpened | None = None,
    chat: Sequence[ChatMessage] = (),
) -> str:
    """`VOTE_ROOM`: FX-01, `p1` to `p3`, help mode `vote`, 5 letters and 1 word."""
    return snapshot_frame(
        fx01_view(grid),
        players_up_to(3),
        seq=seq,
        help_mode=HelpMode.VOTE,
        open_vote=open_vote,
        chat=chat,
    )


def open_vote_room(
    page: Page,
    base_url: str,
    grid: Grid,
    *,
    open_vote: VoteOpened | None = None,
    chat: Sequence[ChatMessage] = (),
) -> RoomMock:
    """Open `VOTE_ROOM` on a mocked socket (seq 6 when it holds `open_vote`)."""
    seq = 5 if open_vote is None else open_vote.seq
    frame = vote_room_frame(grid, seq=seq, open_vote=open_vote, chat=chat)
    return open_room(page, base_url, frame)


def show_vote(page: Page, mock: RoomMock) -> None:
    """The mock sends `VOTE`; return once the banner shows and the fonts are in."""
    mock.send(VOTE.model_dump_json())
    expect_seq(page, VOTE.seq)
    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    wait_for_fonts(page)


def vote_by_me() -> VoteOpened:
    """`VOTE`, but asked by `p1` (`you`): the requester's page."""
    return VOTE.model_copy(update={"player_id": "p1"})


# ---- The solved page and the recap -------------------------------------------------


def open_solved(
    page: Page,
    base_url: str,
    frame: str,
    *,
    body: object = RECAP,
    status: int = 200,
) -> tuple[RoomMock, RecapRoute]:
    """Open a snapshot (`SOLVED` from spec 044) with the recap route answering."""
    route = serve_recap(page, body, status)
    mock = open_room(page, base_url, frame)
    return mock, route


def open_solved_held(page: Page, base_url: str, frame: str) -> HeldRoute:
    """Open a snapshot with the recap route held unanswered."""
    held = HeldRoute(page, RECAP_ROUTE)
    open_room(page, base_url, frame)
    return held


def click_recap_open(page: Page) -> Locator:
    """Click `recap-open`; return `recap` once it is open."""
    page.get_by_test_id("recap-open").click(timeout=WAIT_TIMEOUT_MS)
    recap = page.get_by_test_id("recap")
    expect(recap).to_have_attribute("open", "", timeout=WAIT_TIMEOUT_MS)
    return recap


def open_loaded_recap(page: Page) -> Locator:
    """Open the recap and wait until its loaded parts show (`recap-time`)."""
    recap = click_recap_open(page)
    expect(page.get_by_test_id("recap-time")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_for_fonts(page)
    return recap


def players_heading(page: Page) -> Locator:
    """The players' `h3` (spec 028 gives it `id="recap-players-heading"`)."""
    return page.locator(
        '#recap-players-heading, [data-testid="recap-players-heading"]'
    ).first


def row_of(page: Page, player_id: str) -> Locator:
    return page.locator(f'[data-testid="recap-player"][data-player-id="{player_id}"]')


# The parts of an element that show, in document order: each element child with
# a box, named by its test id, else its `id`, else its tag (`h2` always by its
# tag); an anonymous `div`, `section`, `header`, `footer` or `form` (no test id,
# no `id`) is read through, so that a wrapper the dialog may hold does not hide
# its parts. A visually hidden child does not show.
PARTS_SCRIPT = r"""
element => {
  const wrappers = new Set(['DIV', 'SECTION', 'HEADER', 'FOOTER', 'FORM']);
  const found = [];
  function nameOf(child) {
    if (child.tagName === 'H2') {
      return 'h2';
    }
    const testId = child.getAttribute('data-testid');
    if (testId !== null) {
      return testId;
    }
    if (child.id !== '') {
      return child.id;
    }
    return null;
  }
  function read(node) {
    for (const child of node.children) {
      if (child.getClientRects().length === 0
          || child.classList.contains('visually-hidden')) {
        continue;
      }
      const name = nameOf(child);
      if (name === null && wrappers.has(child.tagName)) {
        read(child);
        continue;
      }
      const rect = child.getBoundingClientRect();
      found.push({
        name: name === null ? child.tagName.toLowerCase() : name,
        box: [rect.left, rect.top, rect.right, rect.bottom],
      });
    }
  }
  read(element);
  return found;
}
"""


class Part(NamedTuple):
    """One part of an element that shows: its name and its box."""

    name: str
    box: Box


def parts_of(locator: Locator) -> list[Part]:
    """The parts of an element that show, in document order (see `PARTS_SCRIPT`)."""
    found = locator.evaluate(PARTS_SCRIPT)
    assert isinstance(found, list), found
    parts: list[Part] = []
    for item in found:
        raw_box = item["box"]
        box = Box(
            float(raw_box[0]), float(raw_box[1]), float(raw_box[2]), float(raw_box[3])
        )
        parts.append(Part(str(item["name"]), box))
    return parts


# ---- Readers of the look ---------------------------------------------------------

BACKDROP_SCRIPT = (
    "element => {\n"
    + COLOUR_CONTRAST_JS
    + "\nreturn parseColour(getComputedStyle(element, '::backdrop')"
    ".backgroundColor);\n}"
)

# The contrast of an element's text against what lies behind it: its own
# background over its ancestors' backgrounds, composited over white.
SURFACE_CONTRAST_SCRIPT = "element => {\n" + COLOUR_CONTRAST_JS + r"""
const layers = [];
for (let node = element; node !== null; node = node.parentElement) {
  layers.push(parseColour(getComputedStyle(node).backgroundColor));
}
let background = WHITE;
for (let index = layers.length - 1; index >= 0; index -= 1) {
  background = over(layers[index], background);
}
const text = over(parseColour(getComputedStyle(element).color), background);
return contrast(text, background);
}"""


def backdrop_colour(locator: Locator) -> tuple[float, float, float, float]:
    """The computed `background-color` of a dialog's `::backdrop`, parsed."""
    found = locator.evaluate(BACKDROP_SCRIPT)
    assert isinstance(found, list), found
    return (float(found[0]), float(found[1]), float(found[2]), float(found[3]))


def surface_contrast(locator: Locator) -> float:
    found = locator.evaluate(SURFACE_CONTRAST_SCRIPT)
    assert isinstance(found, (int, float)), found
    return float(found)


def colour_problem(locator: Locator, name: str, prop: str, expected: Rgb) -> list[str]:
    """How a computed colour property differs from a token (exact channels)."""
    colour = colour_of(locator, prop)
    if colour_matches(colour, expected):
        return []
    return [f"{name}: {prop} {colour}, not {expected}"]


def type_problems(
    locator: Locator,
    name: str,
    *,
    size: float,
    weight: str | None = None,
    colour: Rgb | None = None,
    line_height: float | None = None,
) -> list[str]:
    """How an element's font size, weight, colour and line height differ."""
    problems: list[str] = []
    actual_size = px(style_of(locator, "fontSize"))
    if not same_font_size(actual_size, size):
        problems.append(f"{name}: font-size {actual_size}, not {size}")
    if weight is not None and style_of(locator, "fontWeight") != weight:
        problems.append(f"{name}: font-weight {style_of(locator, 'fontWeight')}")
    if colour is not None:
        problems.extend(colour_problem(locator, name, "color", colour))
    if line_height is not None:
        actual = style_of(locator, "lineHeight")
        if not actual.endswith("px") or not same_font_size(px(actual), line_height):
            problems.append(f"{name}: line-height {actual}, not {line_height}")
    return problems


def tabular_problems(locator: Locator, name: str) -> list[str]:
    value = style_of(locator, "fontVariantNumeric")
    if value == "tabular-nums":
        return []
    return [f"{name}: font-variant-numeric {value}"]


def radius_problems(locator: Locator, name: str, corners: Sequence[str]) -> list[str]:
    """How the four corner radii differ (top left, top right, bottom right, left)."""
    properties = [
        "borderTopLeftRadius",
        "borderTopRightRadius",
        "borderBottomRightRadius",
        "borderBottomLeftRadius",
    ]
    problems: list[str] = []
    for prop, expected in zip(properties, corners, strict=True):
        actual = style_of(locator, prop)
        if actual != expected:
            problems.append(f"{name}: {prop} {actual}, not {expected}")
    return problems


def padding_problems(locator: Locator, name: str, shorthand: str) -> list[str]:
    if padding_matches(locator, shorthand):
        return []
    return [f"{name}: padding {padding_of(locator)}, not {shorthand}"]


def shadow_problems(
    locator: Locator,
    name: str,
    lengths: tuple[float, float, float, float],
    alpha: float,
) -> list[str]:
    """How the one shadow differs: offsets, blur, spread, and ink at `alpha`."""
    if style_of(locator, "boxShadow") == "none":
        return [f"{name}: no box-shadow"]
    shadow = shadow_of(locator)
    problems: list[str] = []
    actual = (shadow.x, shadow.y, shadow.blur, shadow.spread)
    if actual != lengths:
        problems.append(f"{name}: box-shadow {shadow.text}")
    if shadow.colour is None or not colour_matches(shadow.colour, INK, alpha):
        problems.append(f"{name}: box-shadow colour {shadow.colour}")
    return problems


def border_problems(locator: Locator, name: str, width: str, colour: Rgb) -> list[str]:
    """How each of the four border sides differs from `width` solid `colour`."""
    problems: list[str] = []
    for side in ("Top", "Right", "Bottom", "Left"):
        actual_width = style_of(locator, f"border{side}Width")
        actual_style = style_of(locator, f"border{side}Style")
        if actual_width != width or actual_style != "solid":
            problems.append(f"{name}: border-{side} {actual_width} {actual_style}")
        problems.extend(colour_problem(locator, name, f"border{side}Color", colour))
    return problems


def ring_problems(locator: Locator, name: str) -> list[str]:
    """How the focus ring differs from `2px solid` navy at offset `2px`."""
    problems: list[str] = []
    width = style_of(locator, "outlineWidth")
    outline_style = style_of(locator, "outlineStyle")
    offset = style_of(locator, "outlineOffset")
    if width != "2px" or outline_style != "solid" or offset != "2px":
        problems.append(f"{name}: outline {width} {outline_style}, offset {offset}")
    problems.extend(colour_problem(locator, name, "outlineColor", NAVY))
    return problems


# ---- The recap's frame (AC-7, AC-11) -------------------------------------------------


def column_frame_problems(page: Page, dialog: Locator | None = None) -> list[str]:
    """The dialog of the column layout: 440 px, centred, its look (AC-7).

    Args:
        page: The page that shows the dialog.
        dialog: The dialog to check: the recap unless given (the room-gone
            dialog has the recap's frame, `client/hud.md` AC-21).

    Returns:
        How the dialog differs from the recap's frame (empty: not at all).
    """
    recap = page.get_by_test_id("recap") if dialog is None else dialog
    box = box_of(recap)
    window = window_box(page)
    problems: list[str] = []
    if not same_position(box.width, 440.0):
        problems.append(f"recap {box.width} px wide, not 440")
    if not same_position(box.centre_x, window.centre_x):
        problems.append(f"recap centre x {box.centre_x}, window {window.centre_x}")
    if not same_position(box.centre_y, window.centre_y):
        problems.append(f"recap centre y {box.centre_y}, window {window.centre_y}")
    problems.extend(radius_problems(recap, "recap", ["12px"] * 4))
    problems.extend(padding_problems(recap, "recap", "20px 22px"))
    problems.extend(colour_problem(recap, "recap", "backgroundColor", WHITE))
    problems.extend(
        shadow_problems(recap, "recap", (0, 20, 40, -16), SHADOW_STRONG_ALPHA)
    )
    return problems


def sheet_frame_problems(page: Page, dialog: Locator | None = None) -> list[str]:
    """The bottom sheet of the sheet layout (AC-7).

    Args:
        page: The page that shows the sheet.
        dialog: The sheet to check: the recap unless given (the room-gone
            dialog has the recap's frame, `client/hud.md` AC-21).

    Returns:
        How the sheet differs from the recap's frame (empty: not at all).
    """
    recap = page.get_by_test_id("recap") if dialog is None else dialog
    box = box_of(recap)
    window = window_box(page)
    problems: list[str] = []
    if not same_position(box.width, window.width):
        problems.append(f"recap {box.width} px wide, window {window.width}")
    if not same_position(box.left, 0.0):
        problems.append(f"recap left {box.left}")
    if not same_position(box.bottom, window.bottom):
        problems.append(f"recap bottom {box.bottom}, window {window.bottom}")
    if box.top < 54.0 - 1.0:
        problems.append(f"recap top {box.top}, under 54 px")
    problems.extend(radius_problems(recap, "recap", ["16px", "16px", "0px", "0px"]))
    problems.extend(padding_problems(recap, "recap", "14px 18px 18px"))
    return problems


def frame_problems(page: Page, size: tuple[int, int]) -> list[str]:
    """The recap's frame for a window of "Test harness": dialog or sheet."""
    if size == PHONE:
        return sheet_frame_problems(page)
    return column_frame_problems(page)


def backdrop_problems(page: Page) -> list[str]:
    colour = backdrop_colour(page.get_by_test_id("recap"))
    if colour_matches(colour, INK, SCRIM_DIALOG_ALPHA):
        return []
    return [f"::backdrop {colour}, not ink at {SCRIM_DIALOG_ALPHA}"]


def right_on_content_edge(page: Page, test_id: str) -> list[str]:
    """Whether an element's right edge is on `recap`'s content right edge (1 px)."""
    edge = content_box(page.get_by_test_id("recap")).right
    right = box_of(page.get_by_test_id(test_id)).right
    if same_position(right, edge):
        return []
    return [f"{test_id} right {right}, recap content right {edge}"]


# ---- Notes -------------------------------------------------------------------------

# From now on, note the text of each note that shows, and each new text of a note
# (a note replaced in place), in order, in `window.spec047Notes`; and whether a
# note was on the page while `vote-banner` was (`window.spec047NoteUnderBanner`).
RECORD_NOTES_SCRIPT = r"""
() => {
  const texts = [];
  const last = new Map();
  window.spec047NoteUnderBanner = false;
  const record = () => {
    const banner = document.querySelector('[data-testid="vote-banner"]');
    for (const note of document.querySelectorAll('[data-testid="room-note"]')) {
      if (banner !== null) {
        window.spec047NoteUnderBanner = true;
      }
      const text = note.textContent.replace(/\s+/g, ' ').trim();
      if (last.get(note) !== text) {
        last.set(note, text);
        texts.push(text);
      }
    }
  };
  window.spec047Notes = texts;
  new MutationObserver(record).observe(document.body,
    {childList: true, subtree: true, characterData: true, attributes: true});
  record();
}
"""


def start_recording_notes(page: Page) -> None:
    page.evaluate(RECORD_NOTES_SCRIPT)


def recorded_notes(page: Page) -> list[str]:
    found = page.evaluate("() => window.spec047Notes")
    assert isinstance(found, list), found
    return [str(text) for text in found]


def note_shown_under_banner(page: Page) -> bool:
    found = page.evaluate("() => window.spec047NoteUnderBanner")
    assert isinstance(found, bool), found
    return found


def vote_lines(page: Page) -> Locator:
    return page.locator('[data-testid="feed-item"][data-kind="vote"]')


def seconds_shown(text: str) -> int | None:
    """The count of a `vote-seconds` text such as `15 s`, None for another text."""
    template = fr_value("vote.seconds_left")
    pattern = re.escape(template).replace(re.escape("{count}"), "([0-9]+)")
    found = re.fullmatch(pattern, text.strip())
    if found is None:
        return None
    return int(found.group(1))
