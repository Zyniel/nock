"""Tests of spec 041, AC-9 to AC-14: the styling primitives on probe elements.

Each test opens `/` on the live server, appends its probe to `body` once
`catalogue-page` shows (spec 041, "Test harness") and reads `getComputedStyle`.
The shared setup is in `tests/spec041_harness.py`.

Choices where the spec leaves room:

- AC-10, "a border colour with alpha 0" and AC-11 "border": checked on each of
  the four sides.
- AC-12 reads the widths and positions of the menu, its item and its detail,
  which depend on text, so the test waits for `document.fonts.ready` first (the
  rule of "Edge cases and errors").
- AC-14, "with the attribute `data-off`": a probe that has the attribute from the
  start, so that no fade runs while the test reads its opacity.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec041_harness import (
    CLUE_BG,
    INK,
    LINE,
    MIN_TEXT_CONTRAST,
    MUTED,
    NAVY,
    RED,
    WHITE,
    WORD,
    Rgb,
    add_probe,
    assert_colour,
    assert_transparent,
    colour_of,
    open_catalogue,
    px,
    shadow_of,
    style_of,
    text_contrast,
)

# ---- Fixtures: thin wrappers around the harnesses ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (served by live_server for `/`)."""
    return build_reference_catalogue(fx01_grid)


# ---- Helpers ------------------------------------------------------------------

SIDES = ("Top", "Right", "Bottom", "Left")
CORNERS = ("TopLeft", "TopRight", "BottomRight", "BottomLeft")
LENGTH_TOLERANCE = 0.01


def assert_px(value: str, expected: float) -> None:
    assert abs(px(value) - expected) <= LENGTH_TOLERANCE, f"{value} is not {expected}px"


def assert_radius(element: Locator, expected: float) -> None:
    for corner in CORNERS:
        assert_px(style_of(element, f"border{corner}Radius"), expected)


def assert_padding(element: Locator, vertical: float, horizontal: float) -> None:
    assert_px(style_of(element, "paddingTop"), vertical)
    assert_px(style_of(element, "paddingBottom"), vertical)
    assert_px(style_of(element, "paddingLeft"), horizontal)
    assert_px(style_of(element, "paddingRight"), horizontal)


def assert_border_colour(element: Locator, expected: Rgb) -> None:
    for side in SIDES:
        assert_colour(colour_of(element, f"border{side}Color"), expected)


def assert_transparent_border(element: Locator) -> None:
    for side in SIDES:
        assert_transparent(colour_of(element, f"border{side}Color"))


def assert_no_border(element: Locator) -> None:
    for side in SIDES:
        assert_px(style_of(element, f"border{side}Width"), 0.0)


# ---- AC-9: every button variant has the same shape --------------------------------

BUTTON_PROBES = {
    "primary": '<button type="button" class="nock-button nock-button-primary">'
    "Valider</button>",
    "secondary": '<button type="button" class="nock-button nock-button-secondary">'
    "Valider</button>",
    "quiet": '<button type="button" class="nock-button nock-button-quiet">'
    "Valider</button>",
    "primary-disabled": '<button type="button" '
    'class="nock-button nock-button-primary" disabled>Valider</button>',
}


def add_button(page: Page, base_url: str, variant: str) -> Locator:
    open_catalogue(page, base_url)
    return add_probe(page, f"button-{variant}", BUTTON_PROBES[variant])


@pytest.mark.parametrize("variant", list(BUTTON_PROBES))
def test_ac9_button_radius_is_6px_on_each_corner(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_button(page, live_server, variant)

    assert_radius(button, 6.0)


@pytest.mark.parametrize("variant", list(BUTTON_PROBES))
def test_ac9_button_padding_is_10px_16px(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_button(page, live_server, variant)

    assert_padding(button, 10.0, 16.0)


@pytest.mark.parametrize("variant", list(BUTTON_PROBES))
def test_ac9_button_border_is_1px_solid_on_each_side(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_button(page, live_server, variant)

    for side in SIDES:
        assert_px(style_of(button, f"border{side}Width"), 1.0)
        assert style_of(button, f"border{side}Style") == "solid"


@pytest.mark.parametrize("variant", list(BUTTON_PROBES))
def test_ac9_button_font_is_600_at_15_2px_with_line_height_15_2px(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_button(page, live_server, variant)

    assert style_of(button, "fontWeight") == "600"
    assert_px(style_of(button, "fontSize"), 15.2)
    assert_px(style_of(button, "lineHeight"), 15.2)


# ---- AC-10: each button variant has its colours -----------------------------------

ENABLED_VARIANTS = ("primary", "secondary", "quiet")


def test_ac10_primary_is_white_on_navy(page: Page, live_server: str) -> None:
    button = add_button(page, live_server, "primary")

    assert_colour(colour_of(button, "backgroundColor"), NAVY)
    assert_colour(colour_of(button, "color"), WHITE)


def test_ac10_primary_border_is_transparent(page: Page, live_server: str) -> None:
    button = add_button(page, live_server, "primary")

    assert_transparent_border(button)


def test_ac10_secondary_is_navy_on_white(page: Page, live_server: str) -> None:
    button = add_button(page, live_server, "secondary")

    assert_colour(colour_of(button, "backgroundColor"), WHITE)
    assert_colour(colour_of(button, "color"), NAVY)


def test_ac10_secondary_border_is_navy(page: Page, live_server: str) -> None:
    button = add_button(page, live_server, "secondary")

    assert_border_colour(button, NAVY)


def test_ac10_quiet_is_navy_on_word_blue(page: Page, live_server: str) -> None:
    button = add_button(page, live_server, "quiet")

    assert_colour(colour_of(button, "backgroundColor"), WORD)
    assert_colour(colour_of(button, "color"), NAVY)


def test_ac10_quiet_border_is_transparent(page: Page, live_server: str) -> None:
    button = add_button(page, live_server, "quiet")

    assert_transparent_border(button)


@pytest.mark.parametrize("variant", ENABLED_VARIANTS)
def test_ac10_enabled_button_has_the_pointer_cursor(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_button(page, live_server, variant)

    assert style_of(button, "cursor") == "pointer"


# ---- AC-11: a disabled button keeps a readable text -------------------------------


def add_disabled_button(page: Page, base_url: str, variant: str) -> Locator:
    open_catalogue(page, base_url)
    markup = (
        f'<button type="button" class="nock-button nock-button-{variant}" disabled>'
        "Valider</button>"
    )
    return add_probe(page, f"disabled-{variant}", markup)


@pytest.mark.parametrize("variant", ENABLED_VARIANTS)
def test_ac11_disabled_button_is_muted_on_clue_blue_grey(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_disabled_button(page, live_server, variant)

    assert_colour(colour_of(button, "backgroundColor"), CLUE_BG)
    assert_colour(colour_of(button, "color"), MUTED)


@pytest.mark.parametrize("variant", ENABLED_VARIANTS)
def test_ac11_disabled_button_border_is_line_grey(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_disabled_button(page, live_server, variant)

    assert_border_colour(button, LINE)


@pytest.mark.parametrize("variant", ENABLED_VARIANTS)
def test_ac11_disabled_button_has_the_not_allowed_cursor(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_disabled_button(page, live_server, variant)

    assert style_of(button, "cursor") == "not-allowed"


@pytest.mark.parametrize("variant", ENABLED_VARIANTS)
def test_ac11_disabled_button_text_reaches_4_5_to_1(
    page: Page, live_server: str, variant: str
) -> None:
    button = add_disabled_button(page, live_server, variant)
    # The colours first: any readable pair would pass the ratio alone.
    assert_colour(colour_of(button, "color"), MUTED)

    ratio = text_contrast(button)

    assert ratio >= MIN_TEXT_CONTRAST
    assert abs(ratio - 5.22) <= 0.01


# ---- AC-12: the menu primitive has the menu look ----------------------------------

MENU_PROBE = (
    '<div style="position: fixed; left: 20px; top: 20px">'
    '<div class="nock-menu">'
    '<div class="nock-menu-heading">Vérifier</div>'
    '<button type="button" class="nock-menu-item">La lettre'
    '<span class="nock-menu-detail">4 restantes</span></button>'
    '<hr class="nock-menu-separator">'
    '<button type="button" class="nock-menu-item">Le mot</button>'
    "</div></div>"
)


class MenuParts:
    """The elements of the menu probe."""

    def __init__(self, holder: Locator) -> None:
        self.menu = holder.locator(".nock-menu")
        self.heading = holder.locator(".nock-menu-heading")
        self.item = holder.locator(".nock-menu-item").first
        self.detail = holder.locator(".nock-menu-detail")
        self.separator = holder.locator(".nock-menu-separator")


def add_menu(page: Page, base_url: str) -> MenuParts:
    open_catalogue(page, base_url)
    holder = add_probe(page, "menu", MENU_PROBE)
    return MenuParts(holder)


def test_ac12_menu_is_white_with_radius_8px(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_colour(colour_of(parts.menu, "backgroundColor"), WHITE)
    assert_radius(parts.menu, 8.0)


def test_ac12_menu_padding_is_6px_0(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_padding(parts.menu, 6.0, 0.0)


def test_ac12_menu_min_width_is_220px(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_px(style_of(parts.menu, "minWidth"), 220.0)


def test_ac12_menu_has_no_border(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_no_border(parts.menu)


def test_ac12_menu_shadow_is_0_12px_30px_minus_10px_in_the_shadow_token(
    page: Page, live_server: str
) -> None:
    parts = add_menu(page, live_server)

    shadow = shadow_of(parts.menu)

    assert (shadow.x, shadow.y, shadow.blur, shadow.spread) == (0, 12, 30, -10), shadow
    assert shadow.colour is not None
    assert_colour(shadow.colour, INK, 0.45)


def test_ac12_heading_margin_is_6px_16px_2px(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_px(style_of(parts.heading, "marginTop"), 6.0)
    assert_px(style_of(parts.heading, "marginRight"), 16.0)
    assert_px(style_of(parts.heading, "marginBottom"), 2.0)
    assert_px(style_of(parts.heading, "marginLeft"), 16.0)


def test_ac12_heading_font_is_600_at_11_2px_uppercase(
    page: Page, live_server: str
) -> None:
    parts = add_menu(page, live_server)

    assert style_of(parts.heading, "fontWeight") == "600"
    assert_px(style_of(parts.heading, "fontSize"), 11.2)
    assert style_of(parts.heading, "textTransform") == "uppercase"


def test_ac12_heading_letter_spacing_is_0_896px(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_px(style_of(parts.heading, "letterSpacing"), 0.896)


def test_ac12_heading_is_muted(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_colour(colour_of(parts.heading, "color"), MUTED)


def test_ac12_item_is_a_flex_row_with_space_between(
    page: Page, live_server: str
) -> None:
    parts = add_menu(page, live_server)

    assert style_of(parts.item, "display") == "flex"
    assert style_of(parts.item, "justifyContent") == "space-between"


def test_ac12_item_padding_is_10px_16px(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_padding(parts.item, 10.0, 16.0)


def test_ac12_item_font_is_500_at_16px_with_line_height_19_2px(
    page: Page, live_server: str
) -> None:
    parts = add_menu(page, live_server)

    assert style_of(parts.item, "fontWeight") == "500"
    assert_px(style_of(parts.item, "fontSize"), 16.0)
    assert_px(style_of(parts.item, "lineHeight"), 19.2)


def test_ac12_item_is_navy_with_no_border(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_colour(colour_of(parts.item, "color"), NAVY)
    assert_no_border(parts.item)


def test_ac12_item_is_as_wide_as_the_menu_inside(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)
    wait_for_fonts(page)

    widths = parts.item.evaluate(
        "item => [item.getBoundingClientRect().width,"
        " item.closest('.nock-menu').clientWidth]"
    )

    item_width, menu_inner_width = widths
    assert abs(item_width - menu_inner_width) <= 1.0, widths


def test_ac12_item_background_is_transparent(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_transparent(colour_of(parts.item, "backgroundColor"))


def test_ac12_hovered_item_has_the_word_blue_background(
    page: Page, live_server: str
) -> None:
    parts = add_menu(page, live_server)

    parts.item.hover()

    assert_colour(colour_of(parts.item, "backgroundColor"), WORD)


def test_ac12_detail_is_muted_upright_and_tabular(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_colour(colour_of(parts.detail, "color"), MUTED)
    assert style_of(parts.detail, "fontStyle") == "normal"
    assert style_of(parts.detail, "fontVariantNumeric") == "tabular-nums"


def test_ac12_detail_ends_16px_before_the_item_right_edge(
    page: Page, live_server: str
) -> None:
    parts = add_menu(page, live_server)
    wait_for_fonts(page)

    edges = parts.detail.evaluate(
        "detail => [detail.getBoundingClientRect().right,"
        " detail.closest('.nock-menu-item').getBoundingClientRect().right]"
    )

    detail_right, item_right = edges
    assert abs(detail_right - (item_right - 16.0)) <= 1.0, edges


def test_ac12_separator_has_a_1px_solid_line_grey_top_border_only(
    page: Page, live_server: str
) -> None:
    parts = add_menu(page, live_server)

    assert_px(style_of(parts.separator, "borderTopWidth"), 1.0)
    assert style_of(parts.separator, "borderTopStyle") == "solid"
    assert_colour(colour_of(parts.separator, "borderTopColor"), LINE)
    for side in ("Right", "Bottom", "Left"):
        assert_px(style_of(parts.separator, f"border{side}Width"), 0.0)


def test_ac12_separator_margin_is_4px_0(page: Page, live_server: str) -> None:
    parts = add_menu(page, live_server)

    assert_px(style_of(parts.separator, "marginTop"), 4.0)
    assert_px(style_of(parts.separator, "marginBottom"), 4.0)
    assert_px(style_of(parts.separator, "marginLeft"), 0.0)
    assert_px(style_of(parts.separator, "marginRight"), 0.0)


# ---- AC-13: the badge primitive is white on red -----------------------------------


def add_badge(page: Page, base_url: str) -> Locator:
    open_catalogue(page, base_url)
    return add_probe(page, "badge", '<span class="nock-badge">2</span>')


def test_ac13_badge_is_white_on_red(page: Page, live_server: str) -> None:
    badge = add_badge(page, live_server)

    assert_colour(colour_of(badge, "backgroundColor"), RED)
    assert_colour(colour_of(badge, "color"), WHITE)


def test_ac13_badge_font_is_700_at_9_92px_with_line_height_9_92px(
    page: Page, live_server: str
) -> None:
    badge = add_badge(page, live_server)

    assert style_of(badge, "fontWeight") == "700"
    assert_px(style_of(badge, "fontSize"), 9.92)
    assert_px(style_of(badge, "lineHeight"), 9.92)


def test_ac13_badge_padding_is_2px_4px_and_radius_8px(
    page: Page, live_server: str
) -> None:
    badge = add_badge(page, live_server)

    assert_padding(badge, 2.0, 4.0)
    assert_radius(badge, 8.0)


def test_ac13_badge_text_reaches_4_5_to_1(page: Page, live_server: str) -> None:
    badge = add_badge(page, live_server)
    # The colours first: any readable pair would pass the ratio alone.
    assert_colour(colour_of(badge, "backgroundColor"), RED)

    ratio = text_contrast(badge)

    assert ratio >= MIN_TEXT_CONTRAST
    assert abs(ratio - 6.57) <= 0.01


# ---- AC-14: the note primitive is white on ink and fades only with motion ---------

NOTE_PROBE = '<div class="nock-note">Bruno : SENT</div>'
HIDDEN_NOTE_PROBE = '<div class="nock-note" data-off="">Bruno : SENT</div>'


def add_note(page: Page, base_url: str) -> Locator:
    open_catalogue(page, base_url)
    return add_probe(page, "note", NOTE_PROBE)


def test_ac14_note_is_white_on_ink(page: Page, live_server: str) -> None:
    note = add_note(page, live_server)

    assert_colour(colour_of(note, "backgroundColor"), INK)
    assert_colour(colour_of(note, "color"), WHITE)


def test_ac14_note_font_is_500_at_13_6px_with_line_height_16_32px(
    page: Page, live_server: str
) -> None:
    note = add_note(page, live_server)

    assert style_of(note, "fontWeight") == "500"
    assert_px(style_of(note, "fontSize"), 13.6)
    assert_px(style_of(note, "lineHeight"), 16.32)


def test_ac14_note_padding_is_8px_12px_and_radius_6px(
    page: Page, live_server: str
) -> None:
    note = add_note(page, live_server)

    assert_padding(note, 8.0, 12.0)
    assert_radius(note, 6.0)


def test_ac14_note_does_not_wrap(page: Page, live_server: str) -> None:
    note = add_note(page, live_server)

    assert style_of(note, "whiteSpace") == "nowrap"


def test_ac14_note_shadow_is_0_6px_18px_minus_8px_in_the_strong_shadow_token(
    page: Page, live_server: str
) -> None:
    note = add_note(page, live_server)

    shadow = shadow_of(note)

    assert (shadow.x, shadow.y, shadow.blur, shadow.spread) == (0, 6, 18, -8), shadow
    assert shadow.colour is not None
    assert_colour(shadow.colour, INK, 0.5)


def test_ac14_note_fades_its_opacity_in_0_25s(page: Page, live_server: str) -> None:
    note = add_note(page, live_server)

    assert style_of(note, "transitionProperty") == "opacity"
    assert style_of(note, "transitionDuration") == "0.25s"


def test_ac14_note_with_data_off_is_invisible_and_lets_pointers_through(
    page: Page, live_server: str
) -> None:
    open_catalogue(page, live_server)
    note = add_probe(page, "note-off", HIDDEN_NOTE_PROBE)

    assert style_of(note, "opacity") == "0"
    assert style_of(note, "pointerEvents") == "none"


def test_ac14_note_without_data_off_is_shown(page: Page, live_server: str) -> None:
    note = add_note(page, live_server)
    # The note's own rule first: an unstyled probe is shown too.
    assert_colour(colour_of(note, "backgroundColor"), INK)

    assert style_of(note, "opacity") == "1"


def test_ac14_note_has_no_transition_when_motion_is_reduced(
    page: Page, live_server: str
) -> None:
    page.emulate_media(reduced_motion="reduce")
    note = add_note(page, live_server)
    # The note's own rule first: an unstyled probe has no transition either.
    assert_colour(colour_of(note, "backgroundColor"), INK)

    assert style_of(note, "transitionDuration") == "0s"
