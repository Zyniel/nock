"""Tests of spec 029, AC-2 on the catalogue page: my history on this device.

Browser with mocked routes, on the live server with an empty catalogue and accounts
off (so `GET /api/account` answers 404, "no account"), in Paris time. The device
holds identities for `XYZ789` and `ABC234` (nickname `Ana`), and the summaries route
answers `SOLVED_XYZ` and `OPEN_ABC` (spec 029, "Test harness"): the catalogue page
writes `nock.history` as exactly XYZ789's record, team-mates `Bob` and `Cy`, and the
`history` section lists it with its grid, size, date, time, team-mates and replay
button. An older record of `QQQQQQ`, which the summaries no longer return, is listed
second as a bare grid played alone, without a replay button. A `nock.history` of
`not json` reads as empty, an item whose `elapsed_ms` is a string is ignored, and
with no record and no account the page has no `history` element.

Edge cases checked as well: a record replaces the record of its code; one grid
finished twice gives two records; the 101st record drops the oldest; my nickname is
removed from the team-mates by an exact comparison; the new `fr.json` keys.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from spec029_harness import (
    ABC,
    ABC_TOKEN,
    HISTORY_KEY,
    HISTORY_LIMIT,
    OLD_CODE,
    XYZ,
    XYZ_FINISHED_AT,
    XYZ_TOKEN,
    NewPage,
    device_record,
    expect_history_count,
    history_codes,
    history_item,
    history_items,
    history_section,
    history_value,
    identity_value,
    old_record,
    open_abc,
    open_catalogue,
    paris_pages,
    seed,
    solved_summary,
    solved_xyz,
    stored_history,
    two_identities,
    wait_for_stored_history,
    wait_quietly,
    xyz_record,
)
from spec032_harness import SummariesRoute, load_fr

NEW_KEYS = {
    "history.heading": "Grilles terminées",
    "history.finished": "Terminée le {date}",
    "history.time": "en {duration}",
    "history.teammates": "Avec {names}",
    "history.alone": "En solo",
    "history.replay": "Rejouer",
    "history.replay_label": "Rejouer la grille n° {number}",
}


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    yield from paris_pages(browser)


def open_with_summaries(
    page: Page, live_server: str, extra: dict[str, str] | None = None
) -> SummariesRoute:
    """Open `/` with AC-2's identities, `extra` keys, and its two summaries."""
    items = two_identities()
    if extra is not None:
        items.update(extra)
    seed(page, items)
    route = SummariesRoute(body=[solved_xyz(), open_abc()])
    open_catalogue(page, live_server, route)
    return route


def open_with_old_record(page: Page, live_server: str) -> None:
    """AC-2's second case: `nock.history` also holds the older QQQQQQ record."""
    extra = {HISTORY_KEY: history_value([old_record()])}
    open_with_summaries(page, live_server, extra)
    expect_history_count(page, 2)


# ---- The record written from the summaries ----------------------------------------


def test_ac2_the_catalogue_page_writes_exactly_the_solved_rooms_record(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_summaries(page, live_server)

    wait_for_stored_history(page, [xyz_record()])
    expect_history_count(page, 1)
    assert stored_history(page) == [xyz_record()]


def test_ac2_the_list_shows_one_item_with_the_records_attributes(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_summaries(page, live_server)

    expect_history_count(page, 1)
    item = history_items(page)
    expect(item).to_have_attribute("data-code", XYZ)
    expect(item).to_have_attribute("data-grid", "2")
    expect(item).to_have_attribute("data-finished-at", XYZ_FINISHED_AT)
    expect(item).to_have_attribute("data-elapsed-ms", "754000")


def test_ac2_the_section_has_its_heading(new_page: NewPage, live_server: str) -> None:
    page = new_page(1280, 720)

    open_with_summaries(page, live_server)

    expect_history_count(page, 1)
    expect(history_section(page).locator("h2")).to_have_text("Grilles terminées")


def test_ac2_the_item_shows_its_grid_number_and_size(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_summaries(page, live_server)

    expect_history_count(page, 1)
    item = history_item(page, XYZ)
    expect(item).to_contain_text("Grille n° 2")
    expect(item).to_contain_text("5 \N{MULTIPLICATION SIGN} 5")


def test_ac2_the_item_shows_its_date_and_time(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_summaries(page, live_server)

    expect_history_count(page, 1)
    item = history_item(page, XYZ)
    expect(item.get_by_test_id("history-date")).to_have_text(
        "Terminée le 14 octobre 2026"
    )
    expect(item.get_by_test_id("history-time")).to_have_text("en 12 min 34 s")


def test_ac2_the_item_shows_my_teammates_without_me(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_summaries(page, live_server)

    expect_history_count(page, 1)
    teammates = history_item(page, XYZ).get_by_test_id("history-teammates")
    expect(teammates).to_have_text("Avec Bob, Cy")


def test_ac2_the_item_has_a_replay_button_with_its_label(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_summaries(page, live_server)

    expect_history_count(page, 1)
    replay = history_item(page, XYZ).get_by_test_id("history-replay")
    expect(replay).to_have_text("Rejouer")
    expect(replay).to_have_attribute("aria-label", "Rejouer la grille n° 2")
    assert replay.evaluate("element => element.tagName") == "BUTTON"


# ---- An older record that the summaries no longer return --------------------------


def test_ac2_an_older_record_is_listed_second(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_old_record(page, live_server)

    assert history_codes(page) == [XYZ, OLD_CODE]


def test_ac2_the_older_record_shows_a_bare_grid_its_time_and_alone(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_old_record(page, live_server)

    item = history_item(page, OLD_CODE)
    expect(item).to_have_attribute("data-grid", "")
    expect(item).to_contain_text("Grille hors catalogue")
    expect(item.get_by_test_id("history-time")).to_have_text("en 1 h 02 min 05 s")
    expect(item.get_by_test_id("history-teammates")).to_have_text("En solo")


def test_ac2_the_older_record_has_no_replay_button(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_old_record(page, live_server)

    expect(history_item(page, OLD_CODE).get_by_test_id("history-replay")).to_have_count(
        0
    )


def test_ac2_the_older_record_stays_on_the_device(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_old_record(page, live_server)

    wait_for_stored_history(page, [xyz_record(), old_record()])


# ---- Stored values that are not records -------------------------------------------


def test_ac2_a_history_that_is_not_json_reads_as_empty(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)

    open_with_summaries(page, live_server, {HISTORY_KEY: "not json"})

    expect_history_count(page, 1)
    wait_for_stored_history(page, [xyz_record()])


def test_ac2_an_item_whose_elapsed_ms_is_a_string_is_ignored(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    bad = device_record("BADBAD", 1, XYZ_FINISHED_AT, 0, ["Bob"])
    bad["elapsed_ms"] = "754000"
    seed(page, {HISTORY_KEY: history_value([bad, old_record()])})

    open_catalogue(page, live_server, None)

    expect_history_count(page, 1)
    assert history_codes(page) == [OLD_CODE]


def test_ac2_with_no_record_and_no_account_there_is_no_history_section(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    seed(page, {f"nock.identity.{ABC}": identity_value(ABC_TOKEN)})
    route = SummariesRoute(body=[open_abc()])

    open_catalogue(page, live_server, route)

    expect(page.get_by_test_id("my-room")).to_have_count(1)
    wait_quietly(page)
    expect(history_section(page)).to_have_count(0)
    assert stored_history(page) in (None, [])


# ---- Edge cases ---------------------------------------------------------------------


def test_ac2_a_new_record_replaces_the_record_of_its_code(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    stale = device_record(XYZ, 2, "2026-10-13T08:00:00Z", 1_000, ["Zoé"])

    open_with_summaries(page, live_server, {HISTORY_KEY: history_value([stale])})

    expect_history_count(page, 1)
    wait_for_stored_history(page, [xyz_record()])


def test_ac2_one_grid_finished_twice_gives_two_records(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    seed(page, two_identities())
    again = solved_summary(ABC, 2, ["Ana", "Bob"], "2026-10-13T20:05:00Z", 600_000)
    route = SummariesRoute(body=[solved_xyz(), again])

    open_catalogue(page, live_server, route)

    expect_history_count(page, 2)
    second = device_record(ABC, 2, "2026-10-13T20:05:00Z", 600_000, ["Bob"])
    wait_for_stored_history(page, [xyz_record(), second])


def hundred_old_records() -> list[object]:
    """100 records of 1 September 2026, newest first; `H00000` is the oldest."""
    records: list[object] = []
    for number in range(HISTORY_LIMIT - 1, -1, -1):
        finished_at = f"2026-09-01T{number // 60:02d}:{number % 60:02d}:00Z"
        records.append(device_record(f"H{number:05d}", 1, finished_at, 1_000, []))
    return records


def test_ac2_the_101st_record_drops_the_oldest(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    seeded = hundred_old_records()

    open_with_summaries(page, live_server, {HISTORY_KEY: history_value(seeded)})

    expected: list[object] = [xyz_record()]
    expected.extend(seeded[: HISTORY_LIMIT - 1])
    wait_for_stored_history(page, expected)
    stored = stored_history(page)
    assert isinstance(stored, list)
    assert len(stored) == HISTORY_LIMIT


def test_ac2_my_nickname_is_removed_by_an_exact_comparison(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    seed(page, {f"nock.identity.{XYZ}": identity_value(XYZ_TOKEN, nickname="ANA")})
    players = ["BOB", "ANA", "Ana"]
    route = SummariesRoute(
        body=[solved_summary(XYZ, 2, players, XYZ_FINISHED_AT, 754_000)]
    )

    open_catalogue(page, live_server, route)

    expect_history_count(page, 1)
    expected = device_record(XYZ, 2, XYZ_FINISHED_AT, 754_000, ["BOB", "Ana"])
    wait_for_stored_history(page, [expected])


def test_ac2_fr_json_holds_the_history_keys() -> None:
    messages = load_fr()

    found: dict[str, str | None] = {}
    for key in NEW_KEYS:
        found[key] = messages.get(key)

    assert found == NEW_KEYS
