"""Tests of spec 043, AC-21 and AC-22: the room sheets.

AC-21: the host's settings are a modal dialog with a switch, a segmented control
and two number fields, centred on a computer and a bottom sheet on a phone. AC-22:
the account dialog of spec 033 is a room sheet too.

Choices where the spec leaves room:

- The switch's track is the element (`lock-room` or one of its descendants) whose
  box is 42 by 24 px; the knob is read on painted pixels (a context with a device
  scale factor of 1): the pixel at the knob's centre is white and the pixel where
  the knob is not, on the same line, has the track's colour. So the knob may be
  drawn by any element or pseudo-element.
- "Centred in the window": the dialog's centre is the window's (1 px each way).
- A radio of the segmented control is chosen by a click on its label (the radio
  itself may be hidden by the control's look).
- "The dialog's content right edge" is its box less its right padding and border.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import (
    ChangeSettings,
    HelpMode,
    LockRoom,
    RevealBudget,
    parse_client_message,
)
from room_panels import open_host_settings, open_menu
from spec019_harness import OpenWindow, window_opener
from spec033_harness import AccountRoutes
from spec042_harness import READERS_JS, box_of, colour_of, pixel_at
from spec043_harness import (
    NAVY,
    RULE,
    WHITE,
    Box,
    Reading,
    RoomMock,
    colour_matches,
    expect_colour,
    focused_test_id,
    fr_value,
    frames_sent_after,
    fx01_view,
    is_clear,
    open_room,
    padding_matches,
    players_up_to,
    same_font_size,
    same_position,
    same_size,
    send_and_wait,
    settings_frame,
    snapshot_frame,
    style_of,
    to_box,
)

HELP_MODES = ["free", "vote", "none"]

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_settings(page: Page, base_url: str, grid: Grid) -> RoomMock:
    """A FX-01 room (help mode `free`, 5 letters and 1 word, unlocked), the host's
    settings open."""
    mock = open_room(page, base_url, snapshot_frame(fx01_view(grid), players_up_to(3)))
    open_host_settings(page)
    return mock


def title_of(dialog: Locator) -> Locator:
    """The element that labels a dialog (`aria-labelledby`)."""
    title_id = dialog.get_attribute("aria-labelledby")
    assert title_id is not None, "the dialog has no aria-labelledby"
    return dialog.page.locator(f"[id='{title_id}']")


def title_problems(title: Locator, key: str) -> list[str]:
    problems: list[str] = []
    text = title.text_content()
    if text is None or text.strip() != fr_value(key):
        problems.append(f"title {text!r}")
    if style_of(title, "fontWeight") != "700":
        problems.append(f"title weight {style_of(title, 'fontWeight')}")
    size = float(style_of(title, "fontSize").removesuffix("px"))
    if not same_font_size(size, 19.2):
        problems.append(f"title size {size}")
    if not colour_matches(colour_of(title, "color"), NAVY):
        problems.append("title colour")
    return problems


def centred_problems(page: Page, dialog: Locator) -> list[str]:
    """How a dialog differs from the computer's centred room sheet."""
    box = box_of(dialog)
    size = page.evaluate("() => [innerWidth, innerHeight]")
    problems: list[str] = []
    if not same_position(box.width, 440.0):
        problems.append(f"width {box.width}")
    if not same_position(box.centre_x, size[0] / 2):
        problems.append(f"centre x {box.centre_x}")
    if not same_position(box.centre_y, size[1] / 2):
        problems.append(f"centre y {box.centre_y}")
    if style_of(dialog, "borderTopLeftRadius") != "12px":
        problems.append(f"radius {style_of(dialog, 'borderTopLeftRadius')}")
    return problems


def bottom_sheet_problems(dialog: Locator) -> list[str]:
    """How a dialog differs from the phone's bottom room sheet at 360 by 740."""
    box = box_of(dialog)
    problems: list[str] = []
    if not (same_position(box.left, 0.0) and same_size(box.width, 360.0)):
        problems.append(f"not full width: {box}")
    if not same_position(box.bottom, 740.0):
        problems.append(f"bottom {box.bottom}")
    if box.top < 54.0 - 1.0:
        problems.append(f"top {box.top}")
    if style_of(dialog, "borderTopLeftRadius") != "16px":
        problems.append(f"radius {style_of(dialog, 'borderTopLeftRadius')}")
    if not padding_matches(dialog, "14px 18px 18px"):
        problems.append("padding is not 14px 18px 18px")
    return problems


# ---- AC-21: the host's settings sheet ------------------------------------------------


def test_ac21_the_host_settings_are_a_modal_dialog_named_by_its_title(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_settings(page, live_server, fx01_grid)
    dialog = page.get_by_test_id("host-settings")

    tag = dialog.evaluate("element => element.tagName")
    modal = dialog.evaluate("element => element.matches(':modal')")

    assert tag == "DIALOG"
    expect(dialog).to_have_attribute("open", "")
    assert modal is True
    assert title_problems(title_of(dialog), "settings.heading") == []


def test_ac21_on_a_computer_the_sheet_is_440_px_wide_and_centred(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_settings(page, live_server, fx01_grid)
    dialog = page.get_by_test_id("host-settings")

    assert centred_problems(page, dialog) == []
    assert padding_matches(dialog, "20px 22px")


ORDER_SCRIPT = r"""
dialog => {
  const found = [];
  for (const element of dialog.querySelectorAll('[data-testid]')) {
    const testId = element.getAttribute('data-testid');
    if (['lock-room', 'settings-form', 'help-mode-select', 'reveal-letters-input',
         'reveal-words-input', 'settings-save'].includes(testId)) {
      found.push(testId);
    }
  }
  return found;
}
"""


def test_ac21_the_sheet_holds_the_switch_then_the_form_in_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_settings(page, live_server, fx01_grid)
    dialog = page.get_by_test_id("host-settings")

    order = dialog.evaluate(ORDER_SCRIPT)
    in_form = page.get_by_test_id("settings-form").evaluate(
        "form => ['help-mode-select', 'reveal-letters-input', 'reveal-words-input',"
        " 'settings-save'].every(id =>"
        ' form.querySelector(`[data-testid="${id}"]`) !== null)'
    )

    assert order == [
        "lock-room",
        "settings-form",
        "help-mode-select",
        "reveal-letters-input",
        "reveal-words-input",
        "settings-save",
    ]
    assert in_form is True


RADIOS_SCRIPT = r"""
fieldset => {
  const legend = fieldset.querySelector('legend');
  const radios = [];
  for (const radio of fieldset.querySelectorAll('[data-testid="help-mode-option"]')) {
    const label = radio.labels.length > 0 ? radio.labels[0] : null;
    radios.push({
      type: radio.getAttribute('type'),
      name: radio.getAttribute('name'),
      value: radio.value,
      checked: radio.checked,
      label: label === null ? null : label.textContent.trim(),
    });
  }
  return {tag: fieldset.tagName,
    legend: legend === null ? null : legend.textContent.trim(), radios: radios};
}
"""


def test_ac21_the_help_mode_is_a_fieldset_of_three_labelled_radios(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_settings(page, live_server, fx01_grid)

    found = page.get_by_test_id("help-mode-select").evaluate(RADIOS_SCRIPT)

    assert found["tag"] == "FIELDSET"
    assert found["legend"] == fr_value("settings.help_mode_label")
    expected = []
    for mode in HELP_MODES:
        expected.append(
            {
                "type": "radio",
                "name": "help-mode",
                "value": mode,
                "checked": mode == "free",
                "label": fr_value(f"settings.help_mode.{mode}"),
            }
        )
    assert found["radios"] == expected


LABEL_SCRIPT = "radio => {\n" + READERS_JS + r"""
const label = radio.labels[0];
const style = getComputedStyle(label);
return {box: boxOf(label), background: parseColour(style.backgroundColor),
  colour: parseColour(style.color)};
}"""


def radio_label(page: Page, mode: str) -> Reading:
    """The box and colours of the label of the help-mode radio of `mode`."""
    radio = page.locator(f'[data-testid="help-mode-option"][value="{mode}"]')
    found = radio.evaluate(LABEL_SCRIPT)
    assert isinstance(found, dict), found
    return found


def click_mode(page: Page, mode: str) -> None:
    """Click the label of the help-mode radio of `mode`, at its centre."""
    box = to_box(radio_label(page, mode)["box"])
    page.mouse.click(box.centre_x, box.centre_y)


def test_ac21_the_checked_mode_is_navy_and_the_others_clear(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_settings(page, live_server, fx01_grid)

    checked = radio_label(page, "free")
    assert colour_matches(checked["background"], NAVY), checked
    assert colour_matches(checked["colour"], WHITE), checked
    for mode in ("vote", "none"):
        label = radio_label(page, mode)
        assert is_clear(label["background"]), (mode, label)
        assert colour_matches(label["colour"], NAVY), (mode, label)


def test_ac21_the_two_number_fields_are_64_px_centred_and_16_px_apart(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_settings(page, live_server, fx01_grid)
    letters = page.get_by_test_id("reveal-letters-input")
    words = page.get_by_test_id("reveal-words-input")

    letters_box = box_of(letters)
    words_box = box_of(words)

    for field in (letters, words):
        assert same_size(box_of(field).width, 64.0), box_of(field)
        assert style_of(field, "textAlign") == "center"
    expect(letters).to_have_value("5")
    expect(words).to_have_value("1")
    assert same_position(words_box.left - letters_box.right, 16.0), (
        letters_box,
        words_box,
    )


def test_ac21_save_is_the_primary_button_on_the_forms_right_edge(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_settings(page, live_server, fx01_grid)
    save = page.get_by_test_id("settings-save")

    form_box = box_of(page.get_by_test_id("settings-form"))

    expect_colour(save, "backgroundColor", NAVY)
    expect_colour(save, "color", WHITE)
    assert same_position(box_of(save).right, form_box.right), (box_of(save), form_box)


TRACK_SCRIPT = r"""
button => {
  const found = [];
  for (const element of [button, ...button.querySelectorAll('*')]) {
    const rect = element.getBoundingClientRect();
    if (Math.abs(rect.width - 42) <= 0.5 && Math.abs(rect.height - 24) <= 0.5) {
      found.push([rect.left, rect.top, rect.right, rect.bottom]);
    }
  }
  return found;
}
"""


def track_box(page: Page) -> Box:
    found = page.get_by_test_id("lock-room").evaluate(TRACK_SCRIPT)
    assert isinstance(found, list), found
    assert len(found) >= 1, "no 42 by 24 px track in lock-room"
    return to_box(found[0])


def knob_problems(page: Page, on: bool) -> list[str]:
    """The knob's white centre 3 (off) or 21 (on) px from the track's left."""
    track = track_box(page)
    middle = track.top + 12.0
    knob_left = track.left + (21.0 if on else 3.0)
    other_left = track.left + (3.0 if on else 21.0)
    track_colour = NAVY if on else RULE
    problems: list[str] = []
    knob_centre = pixel_at(page, knob_left + 9.0, middle)
    other_centre = pixel_at(page, other_left + 9.0, middle)
    if knob_centre != WHITE:
        problems.append(f"knob centre {knob_centre}, not white")
    if other_centre != track_colour:
        problems.append(f"track {other_centre}, not {track_colour}")
    return problems


def test_ac21_the_lock_switch_starts_off_with_a_grey_track_and_its_knob_left(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_settings(page, live_server, fx01_grid)
    switch = page.get_by_test_id("lock-room")

    tag = switch.evaluate("element => [element.tagName, element.type]")

    assert tag == ["BUTTON", "button"]
    expect(switch).to_have_attribute("aria-pressed", "false")
    expect(switch).to_have_attribute("aria-label", fr_value("host.lock"))
    assert knob_problems(page, on=False) == []


def test_ac21_the_lock_switch_sends_at_once_and_the_echo_turns_it_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_settings(page, live_server, fx01_grid)
    switch = page.get_by_test_id("lock-room")

    frames = frames_sent_after(page, mock, switch.click)
    send_and_wait(page, mock, settings_frame(6, locked=True))

    assert [parse_client_message(frame) for frame in frames] == [LockRoom(locked=True)]
    expect(switch).to_have_attribute("aria-pressed", "true")
    page.mouse.move(1, 1)
    assert knob_problems(page, on=True) == []


def test_ac21_saving_sends_the_settings_closes_and_refocuses_menu_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_settings(page, live_server, fx01_grid)
    before = len(mock.frames_without_pings())

    click_mode(page, "vote")
    page.get_by_test_id("reveal-letters-input").fill("3")
    page.get_by_test_id("settings-save").click()

    expect(page.get_by_test_id("host-settings")).not_to_have_attribute("open", "")
    page.wait_for_timeout(300)
    frames = mock.frames_without_pings()[before:]
    sent = [parse_client_message(frame) for frame in frames]
    assert sent == [
        ChangeSettings(
            help_mode=HelpMode.VOTE, reveal_budget=RevealBudget(letters=3, words=1)
        )
    ]
    assert focused_test_id(page) == "menu-button"


def test_ac21_on_a_phone_the_settings_are_a_bottom_sheet_closed_by_the_backdrop(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_settings(page, live_server, fx01_grid)
    dialog = page.get_by_test_id("host-settings")

    problems = bottom_sheet_problems(dialog)
    page.mouse.click(180, 100)

    assert problems == []
    expect(dialog).not_to_have_attribute("open", "")


def test_ac21_a_guest_has_no_host_settings(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    frame = snapshot_frame(fx01_view(fx01_grid), players_up_to(3, host="p2"))
    open_room(page, live_server, frame)

    expect(page.get_by_test_id("room-menu")).to_have_count(1)
    expect(page.get_by_test_id("host-settings")).to_have_count(0)


# ---- AC-22: the account dialog as a room sheet ---------------------------------------


def open_account(page: Page, base_url: str, grid: Grid) -> Locator:
    AccountRoutes().install(page)
    open_room(page, base_url, snapshot_frame(fx01_view(grid), players_up_to(3)))
    expect(page.get_by_test_id("account-open")).to_have_count(1)
    open_menu(page)
    page.get_by_test_id("account-open").click()
    dialog = page.get_by_test_id("account-dialog")
    expect(dialog).to_have_attribute("open", "")
    return dialog


CONTENT_RIGHT_SCRIPT = r"""
element => {
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return rect.right - parseFloat(style.paddingRight)
    - parseFloat(style.borderRightWidth);
}
"""


def test_ac22_on_a_computer_the_account_dialog_is_the_centred_room_sheet(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    dialog = open_account(page, live_server, fx01_grid)

    assert centred_problems(page, dialog) == []
    assert title_problems(title_of(dialog), "account.dialog_heading") == []


def test_ac22_its_buttons_are_the_primary_submit_and_the_secondary_close(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    dialog = open_account(page, live_server, fx01_grid)
    submit = page.get_by_test_id("account-email-submit")
    close = page.get_by_test_id("account-close")

    content_right = dialog.evaluate(CONTENT_RIGHT_SCRIPT)

    expect_colour(submit, "backgroundColor", NAVY)
    expect_colour(submit, "color", WHITE)
    expect_colour(close, "backgroundColor", WHITE)
    expect_colour(close, "color", NAVY)
    expect_colour(close, "borderTopColor", NAVY)
    assert same_position(box_of(close).right, float(content_right))


def test_ac22_on_a_phone_the_account_dialog_is_a_bottom_sheet(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    dialog = open_account(page, live_server, fx01_grid)

    assert bottom_sheet_problems(dialog) == []


@pytest.mark.parametrize(("width", "height"), [(1280, 720), (360, 740)])
def test_ac22_escape_closes_the_account_dialog_and_refocuses_menu_button(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    dialog = open_account(page, live_server, fx01_grid)

    page.keyboard.press("Escape")

    expect(dialog).not_to_have_attribute("open", "")
    expect(page.get_by_test_id("menu-button")).to_be_focused()
