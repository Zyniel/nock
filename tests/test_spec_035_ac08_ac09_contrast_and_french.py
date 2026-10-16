"""Tests of spec 035: text contrast and a French interface (AC-8, AC-9).

Every test runs in a browser, except the static ones of AC-9 (the language
checker on its samples and the new `fr.json` keys). AC-8 and AC-9 scan the
rendered pages of the states K1 to K7 of the spec. The setup the test files of
spec 035 share is in `tests/spec035_harness.py`.

Not tested here, and why:

- State K7 `/g/99`: the live server answers `GET /g/99` with the 404 JSON body of
  spec 004 AC-4 and never serves the app there, so no page with `<html lang="fr">`
  exists to scan (see the report). `/r/ZZZZZZ` is scanned.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import PlayerJoined
from spec035_harness import (
    FX01_CLUES,
    LANGUAGE_SCAN_SCRIPT,
    NEW_KEYS,
    ROOM_CODE,
    ROOM_TIMEOUT_MS,
    WINDOW_SIZES,
    Cell,
    ChangeList,
    build_fx01_grid,
    build_reference_catalogue,
    cell_at,
    contrast_measurements,
    contrast_offenders,
    letter_changed_frame,
    load_fr,
    open_k2,
    open_nickname_form,
    open_room,
    page_factory,
    player_view,
    unknown_texts,
)

# ---- Fixtures: thin wrappers around spec035_harness -------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (also served by live_server)."""
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Return `new_page(width, height)`, a page in a fresh context of that size."""
    yield from page_factory(browser)


UNKNOWN_CODE = "ZZZZZZ"

# The solution of FX-01 (specs/_reference.md), in row-major order.
SOLUTION: dict[Cell, str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        SOLUTION[(_row, _offset + 1)] = _letter


# ---- States K1 to K7 for AC-8 and AC-9 -------------------------------------------


def all_right_changes() -> ChangeList:
    changes: ChangeList = []
    for position, letter in SOLUTION.items():
        update: dict[str, object] = {"letter": letter, "author": "p2"}
        changes.append((position[0], position[1], update))
    return changes


def open_k1(page: Page, live_server: str, grid: Grid) -> None:
    progress = json.dumps({"1": "started", "2": "finished"})
    script = f"localStorage.setItem('nock.progress', {json.dumps(progress)})"
    page.context.add_init_script(script)
    page.goto(f"{live_server}/")
    expect(page.get_by_test_id("catalogue-item").first).to_be_visible(
        timeout=ROOM_TIMEOUT_MS
    )
    expect(page.get_by_test_id("catalogue-progress").first).to_be_visible()


def open_k3(page: Page, live_server: str, grid: Grid) -> None:
    mock = open_k2(page, live_server, grid)
    mock.send(letter_changed_frame(14, 1, 3, "O", "p2"))
    expect(cell_at(page, 1, 3)).to_have_attribute("data-flash", "1")


def open_k4(page: Page, live_server: str, grid: Grid) -> None:
    mock = open_k2(page, live_server, grid)
    mock.routes[0].close(code=1011)
    expect(page.get_by_test_id("connection-banner")).to_be_visible(
        timeout=ROOM_TIMEOUT_MS
    )


def open_k5(page: Page, live_server: str, grid: Grid) -> None:
    open_nickname_form(page, live_server)
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana!")
    nickname_input.press("Enter")
    expect(page.get_by_test_id("nickname-error")).to_have_text(
        load_fr()["join.error.characters"]
    )


def open_k6_solved(page: Page, live_server: str, grid: Grid) -> None:
    open_room(page, live_server, grid, changes=all_right_changes(), solved=True)
    expect(page.get_by_test_id("grid-status")).to_have_attribute("data-state", "solved")


def open_k6_full_wrong(page: Page, live_server: str, grid: Grid) -> None:
    changes = all_right_changes()
    changes.append((4, 4, {"letter": "X", "author": "p2"}))
    open_room(page, live_server, grid, changes=changes)
    expect(page.get_by_test_id("grid-status")).to_have_attribute(
        "data-state", "full_wrong"
    )


def open_k7(page: Page, live_server: str, grid: Grid) -> None:
    page.goto(f"{live_server}/r/{UNKNOWN_CODE}")
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "not_found", timeout=ROOM_TIMEOUT_MS
    )


def open_k2_state(page: Page, live_server: str, grid: Grid) -> None:
    open_k2(page, live_server, grid)


STATE_OPENERS: dict[str, Callable[[Page, str, Grid], None]] = {
    "k1_catalogue": open_k1,
    "k2_room": open_k2_state,
    "k3_flash": open_k3,
    "k4_connection_banner": open_k4,
    "k5_nickname_error": open_k5,
    "k6_solved": open_k6_solved,
    "k6_full_wrong": open_k6_full_wrong,
    "k7_room_not_found": open_k7,
}
STATE_NAMES = list(STATE_OPENERS)


# ---- AC-8: text contrast ------------------------------------------------------------


@pytest.mark.parametrize("state", STATE_NAMES)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
def test_ac8_text_contrast_is_at_least_4_5_to_1(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    STATE_OPENERS[state](page, live_server, fx01_grid)

    offenders = contrast_offenders(page)

    assert offenders == [], f"{state} at {width}x{height}: {offenders}"
    if state == "k3_flash":
        # The flash must not have ended during the scan.
        expect(cell_at(page, 1, 3)).to_have_attribute("data-flash", "1")


# Who replaces my letter to make a cell flash in each colour 0 to 7: colour 0 is the
# flash of a player not in the roster, the others are the roster's colours.
FLASH_PLAYERS = {
    0: "p9",
    1: "p2",
    2: "p3",
    3: "p4",
    4: "p5",
    5: "p6",
    6: "p7",
    7: "p8",
}
FLASH_COLOURS = list(FLASH_PLAYERS)


@pytest.mark.parametrize("colour", FLASH_COLOURS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
def test_ac8_text_contrast_holds_on_a_cell_flashing_in_every_colour(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    colour: int,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    mock = open_k2(page, live_server, fx01_grid)
    seq = 14
    for index, joining in enumerate(["p6", "p7", "p8"]):
        joined = PlayerJoined(
            seq=seq, player=player_view(joining, f"Joueur{index}", 5 + index)
        )
        mock.send(joined.model_dump_json())
        seq += 1
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq - 1))

    # Make (1, 3) mine again, then let the player of this colour replace it.
    mock.send(letter_changed_frame(seq, 1, 3, "I", "p1"))
    mock.send(letter_changed_frame(seq + 1, 1, 3, "O", FLASH_PLAYERS[colour]))
    expect(cell_at(page, 1, 3)).to_have_attribute("data-flash", str(colour))

    offenders = contrast_offenders(page)

    assert offenders == [], f"flash colour {colour} at {width}x{height}: {offenders}"
    # The flash must not have ended during the scan.
    expect(cell_at(page, 1, 3)).to_have_attribute("data-flash", str(colour))


def test_ac8_the_idle_and_disconnected_nicknames_are_scanned_and_reach_4_5_to_1(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_k2(page, live_server, fx01_grid)

    measurements = contrast_measurements(page)

    nickname_of_state = {"idle": "Cleo", "disconnected": "Dan"}
    for state, nickname in nickname_of_state.items():
        found: list[dict[str, Any]] = []
        for measurement in measurements:
            is_nickname = measurement["testid"] == "roster-nickname"
            if is_nickname and measurement["rowState"] == state:
                found.append(measurement)
        # The scan reached the nickname exactly once.
        assert [item["text"] for item in found] == [nickname], (state, found)
        assert found[0]["ratio"] >= 4.5, (state, found[0])


INJECT_PROBE_SCRIPT = """
opacity => {
  let probe = document.querySelector('[data-testid="opacity-probe"]');
  if (probe === null) {
    probe = document.createElement('p');
    probe.setAttribute('data-testid', 'opacity-probe');
    probe.textContent = 'Sonde opacité';
    document.body.appendChild(probe);
  }
  probe.style.color = '#5b6070';
  probe.style.backgroundColor = '#ffffff';
  probe.style.opacity = String(opacity);
}
"""


def probe_measurement(page: Page, opacity: float) -> dict[str, Any]:
    """Inject the probe text at an opacity and return what the scan measured."""
    page.evaluate(INJECT_PROBE_SCRIPT, opacity)
    found: list[dict[str, Any]] = []
    for measurement in contrast_measurements(page):
        if measurement["testid"] == "opacity-probe":
            found.append(measurement)
    assert len(found) == 1, found
    return found[0]


def test_ac8_the_contrast_scan_folds_in_opacity(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_k2(page, live_server, fx01_grid)

    # The same colours pass at full opacity and fail once the element is faded.
    opaque = probe_measurement(page, 1)
    opaque_flagged = opaque in contrast_offenders(page)
    faded = probe_measurement(page, 0.45)
    faded_flagged = faded in contrast_offenders(page)

    assert opaque["ratio"] >= 4.5, opaque
    assert not opaque_flagged
    assert faded["ratio"] < 4.5, faded
    assert faded["ratio"] < opaque["ratio"]
    assert faded_flagged


# ---- AC-9: the interface is in French, every string from fr.json -----------------


def test_ac9_the_checker_flags_english_and_a_bare_salon() -> None:
    samples = ["Loading…", "Salon", "Check word"]

    assert unknown_texts(samples, set()) == samples


def test_ac9_the_checker_accepts_templates_filled_in() -> None:
    samples = ["Salon ABC123", "Grille n° 2", "Ana a rejoint le salon"]

    assert unknown_texts(samples, set()) == []


# A number placeholder ("Language scan" in the spec's "Test harness") matches ASCII
# digits only. Before that rule, the two time patterns of spec 027
# (`{minutes}:{seconds}` and `{hours}:{minutes}:{seconds}`) accepted any text with a
# colon in the middle, and `Grille n° {number}` accepted `Grille n° deux`.
@pytest.mark.parametrize(
    "sample", ["Error: connection lost", "Score: 3", "Grille n° deux"]
)
def test_ac9_the_checker_flags_a_number_placeholder_filled_with_other_than_digits(
    sample: str,
) -> None:
    assert unknown_texts([sample], set()) == [sample]


@pytest.mark.parametrize("sample", ["0:00", "1:02:05"])
def test_ac9_the_checker_accepts_a_time_made_of_digits(sample: str) -> None:
    assert unknown_texts([sample], set()) == []


# Digits to a reader, but not the ASCII digits `0` to `9` that a number placeholder
# matches: U+0663 ARABIC-INDIC DIGIT THREE and U+FF12 FULLWIDTH DIGIT TWO.
NON_ASCII_DIGITS = [chr(0x0663), chr(0xFF12)]


@pytest.mark.parametrize("digit", NON_ASCII_DIGITS, ids=["arabic-indic", "fullwidth"])
def test_ac9_the_checker_reads_a_number_placeholder_as_ascii_digits_only(
    digit: str,
) -> None:
    sample = f"Grille n° {digit}"

    assert unknown_texts([sample], set()) == [sample]


def test_ac9_the_checker_accepts_any_characters_in_the_other_placeholders() -> None:
    # `{date}` is not a number placeholder: a date reads `12 octobre 2026`.
    samples = ["Publiée le 12 octobre 2026"]

    assert unknown_texts(samples, set()) == []


def test_ac9_the_checker_accepts_the_data_of_the_test() -> None:
    samples = ["Bob", "BO", "Artiste muet", "Z", "42", "ABC123"]
    data = {"Bob", "BO", "Artiste muet", "ABC123"}

    assert unknown_texts(samples, data) == []
    assert unknown_texts(["Bobby"], data) == ["Bobby"]


def test_ac9_the_new_keys_exist_with_their_values() -> None:
    fr_json = load_fr()

    for key, value in NEW_KEYS.items():
        assert fr_json.get(key) == value, key


NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve"]
INITIALS = ["AN", "BO", "CL", "DA", "EV"]


@pytest.mark.parametrize("state", STATE_NAMES)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
def test_ac9_the_page_is_in_french_with_every_string_from_fr_json(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    STATE_OPENERS[state](page, live_server, fx01_grid)

    assert page.evaluate("document.documentElement.lang") == "fr"
    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    assert isinstance(texts, list)
    assert len(texts) > 0, "the language scan found no text at all"
    data = {
        *NICKNAMES,
        *INITIALS,
        *FX01_CLUES,
        ROOM_CODE,
        UNKNOWN_CODE,
        f"{live_server}/r/{ROOM_CODE}",
    }
    unknown = unknown_texts(texts, data)
    assert unknown == [], f"{state} at {width}x{height}: {unknown}"
