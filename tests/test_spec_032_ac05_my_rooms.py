"""Tests of spec 032, AC-5 with the summaries route mocked: "My rooms" lists my open
rooms with their grid, players and last activity.

The live server serves the client and an empty catalogue; `page.route` answers
`POST /api/rooms/summaries` with plain JSON (`summary_json`, the form that AC-4
checks against `RoomSummary`) and records each request. Identities are seeded
before `page.goto`, and every context has `timezone_id="Europe/Paris"`, so
`2026-10-14T08:30:00Z` reads `14 octobre 2026 à 10:30`. The page sends only the
identities whose code and token match their patterns, so an odd stored token
neither shows the section nor spoils the request. The live part of AC-5 is in
`test_spec_032_ac03_ac05_live_pages.py`.

Refined by spec 046 (the design's catalogue, screens sheet P4): "My rooms" has the
`hidden` attribute and shows no text while it loads and when the answer is empty,
so `my_rooms.loading` and `my_rooms.empty` leave `fr.json`; a failed request
shows `my-rooms-error` with `my_rooms.error`. Spec 046 also shows no force filter
on an empty catalogue (its "States"), so the test of the section's place between
the title and the force filter serves spec 004's reference catalogue `CAT`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from spec032_harness import (
    ABC,
    ABC_TOKEN,
    QUIET_MS,
    WAIT_TIMEOUT_MS,
    XYZ,
    XYZ_TOKEN,
    HeldSummariesRoute,
    NewPage,
    SummariesRoute,
    abc_summary,
    expect_my_rooms_ready,
    identity_value,
    load_fr,
    my_room_items,
    my_rooms,
    open_catalogue,
    open_two_summaries,
    paris_page_factory,
    read_storage,
    seed_storage,
    sent_keys,
    summary_json,
    two_identities,
    xyz_summary,
)
from spec035_harness import build_fx01_grid, build_reference_catalogue

GRID_2 = "Grille n\N{DEGREE SIGN} 2"
SIZE_5_BY_5 = "5 \N{MULTIPLICATION SIGN} 5"
SIZE_13_BY_17 = "13 \N{MULTIPLICATION SIGN} 17"
NEW_KEYS = {
    "my_rooms.heading": "Mes salons",
    "my_rooms.error": "Impossible de charger vos salons.",
    "my_rooms.unnumbered": "Grille hors catalogue",
    "my_rooms.players": "Joueurs : {names}",
    "my_rooms.last_activity": "Dernière activité : {date} à {time}",
    "my_rooms.open": "Reprendre",
    "my_rooms.open_label": "Reprendre le salon {code}",
}
# Spec 046 removed these two keys: nothing shows them any more.
REMOVED_KEYS = {
    "my_rooms.loading": "Chargement de vos salons\N{HORIZONTAL ELLIPSIS}",
    "my_rooms.empty": "Aucun salon ouvert.",
}
HOSTILE_NAMES = ["<b>Eve</b>", "<img src=x>"]
MANY_ROOMS = 101
# An identity valid by spec 012's rule whose token breaks `ResumeToken`'s pattern
# `^[A-Za-z0-9_-]{16,128}$` (spec 039): 15 characters, as in AC-5, or a character
# outside the pattern, as in the edge case "Odd token".
DEF = "DEF567"
ODD_TOKENS = pytest.mark.parametrize(
    "odd_token",
    ["abcdefghijklmno", "abcdefghij+klmnopqrs"],
    ids=["15_characters", "a_character_outside_the_pattern"],
)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    yield from paris_page_factory(browser)


@pytest.fixture
def page_1280(new_page: NewPage) -> Page:
    return new_page(1280, 720)


def test_ac5_fr_json_has_the_my_rooms_keys() -> None:
    fr = load_fr()

    found = {key: fr.get(key) for key in NEW_KEYS}

    assert found == NEW_KEYS


def test_ac5_fr_json_has_no_loading_or_empty_text_for_my_rooms() -> None:
    fr = load_fr()

    present = [key for key in REMOVED_KEYS if key in fr]

    assert present == []


# ---- The request ---------------------------------------------------------------


def test_ac5_the_page_sends_one_request_with_the_valid_identities_only(
    page_1280: Page, live_server: str
) -> None:
    route = open_two_summaries(page_1280, live_server)
    page_1280.wait_for_timeout(QUIET_MS)

    assert route.methods == ["POST"]
    assert sorted(sent_keys(route.bodies[0])) == sorted(
        [(XYZ, XYZ_TOKEN), (ABC, ABC_TOKEN)]
    )


def test_ac5_an_identity_under_a_key_of_another_shape_is_not_sent(
    page_1280: Page, live_server: str
) -> None:
    identities = two_identities()
    identities["nock.identity.abc"] = identity_value("tokenOfLowerCaseKey0")
    identities["nock.identity.ABC2345"] = identity_value("tokenOfSevenCharKey0")
    route = SummariesRoute(body=[xyz_summary(), abc_summary()])
    seed_storage(page_1280, identities)

    open_catalogue(page_1280, live_server, route)
    expect_my_rooms_ready(page_1280, 2)

    assert len(route.bodies) == 1
    assert sorted(sent_keys(route.bodies[0])) == sorted(
        [(XYZ, XYZ_TOKEN), (ABC, ABC_TOKEN)]
    )


def test_ac5_without_any_identity_there_is_no_section_and_no_request(
    page_1280: Page, live_server: str
) -> None:
    route = SummariesRoute(body=[])

    open_catalogue(page_1280, live_server, route)
    page_1280.wait_for_timeout(QUIET_MS)

    expect(my_rooms(page_1280)).to_have_count(0)
    assert route.methods == []


def test_ac5_corrupt_or_misnamed_identities_alone_show_no_section(
    page_1280: Page, live_server: str
) -> None:
    route = SummariesRoute(body=[])
    seed_storage(
        page_1280,
        {
            "nock.identity.QQQQQQ": "not json",
            "nock.identity.RRRRRR": "[]",
            "nock.identity.SSSSSS": '{"player_id": "p1"}',
            "nock.identity.TTTTTT": identity_value(""),
            "nock.identity.abc": identity_value(XYZ_TOKEN),
        },
    )

    open_catalogue(page_1280, live_server, route)
    page_1280.wait_for_timeout(QUIET_MS)

    expect(my_rooms(page_1280)).to_have_count(0)
    assert route.methods == []


@ODD_TOKENS
def test_ac5_an_identity_with_an_odd_token_is_left_out_of_the_one_request(
    page_1280: Page, live_server: str, odd_token: str
) -> None:
    identities = two_identities()
    identities[f"nock.identity.{DEF}"] = identity_value(odd_token)
    route = SummariesRoute(body=[xyz_summary(), abc_summary()])
    seed_storage(page_1280, identities)

    open_catalogue(page_1280, live_server, route)
    expect_my_rooms_ready(page_1280, 2)
    page_1280.wait_for_timeout(QUIET_MS)

    assert route.methods == ["POST"]
    assert sorted(sent_keys(route.bodies[0])) == sorted(
        [(XYZ, XYZ_TOKEN), (ABC, ABC_TOKEN)]
    )
    items = my_room_items(page_1280)
    expect(items.nth(0)).to_have_attribute("data-code", XYZ)
    expect(items.nth(1)).to_have_attribute("data-code", ABC)


@ODD_TOKENS
def test_ac5_an_identity_with_an_odd_token_alone_shows_no_section_and_no_request(
    page_1280: Page, live_server: str, odd_token: str
) -> None:
    route = SummariesRoute(body=[])
    seed_storage(page_1280, {f"nock.identity.{DEF}": identity_value(odd_token)})

    open_catalogue(page_1280, live_server, route)
    page_1280.wait_for_timeout(QUIET_MS)

    expect(my_rooms(page_1280)).to_have_count(0)
    assert route.methods == []


# ---- The section ---------------------------------------------------------------


PLACE_SCRIPT = """
() => {
  const page = document.querySelector('[data-testid="catalogue-page"]');
  const section = document.querySelector('[data-testid="my-rooms"]');
  const title = page.querySelector('h1');
  const filter = page.querySelector('[data-testid="force-filter"]');
  const heading = section.querySelector('h2');
  const follows = (first, second) => Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  return {
    tag: section.tagName,
    heading: heading === null ? null : heading.textContent.trim(),
    inPage: page.contains(section),
    afterTitle: follows(title, section),
    beforeFilter: follows(section, filter),
  };
}
"""


class TestWithGrids:
    """The live server of spec 004's reference catalogue `CAT`.

    Spec 046 shows the force filter only when the catalogue has grids, so the
    place of the section is checked on a catalogue that shows it.
    """

    @pytest.fixture
    def catalogue(self, fx01_text: str) -> Catalogue:
        return build_reference_catalogue(build_fx01_grid(fx01_text))

    def test_ac5_my_rooms_is_a_section_between_the_title_and_the_force_filter(
        self, page_1280: Page, live_server: str
    ) -> None:
        open_two_summaries(page_1280, live_server)
        expect(page_1280.get_by_test_id("force-filter")).to_have_count(5)

        place = page_1280.evaluate(PLACE_SCRIPT)

        assert place == {
            "tag": "SECTION",
            "heading": "Mes salons",
            "inPage": True,
            "afterTitle": True,
            "beforeFilter": True,
        }


def test_ac5_my_rooms_lists_the_summaries_in_the_order_received(
    page_1280: Page, live_server: str
) -> None:
    open_two_summaries(page_1280, live_server)

    items = my_room_items(page_1280)
    expect(items.nth(0)).to_have_attribute("data-code", XYZ)
    expect(items.nth(1)).to_have_attribute("data-code", ABC)


def test_ac5_the_first_room_has_its_code_grid_state_and_activity_attributes(
    page_1280: Page, live_server: str
) -> None:
    open_two_summaries(page_1280, live_server)

    first = my_room_items(page_1280).nth(0)
    expect(first).to_have_attribute("data-code", "XYZ789")
    expect(first).to_have_attribute("data-grid", "2")
    expect(first).to_have_attribute("data-solved", "false")
    expect(first).to_have_attribute("data-last-activity", "2026-10-14T08:30:00Z")


def test_ac5_the_first_room_shows_its_grid_size_players_and_last_activity(
    page_1280: Page, live_server: str
) -> None:
    open_two_summaries(page_1280, live_server)

    first = my_room_items(page_1280).nth(0)
    expect(first).to_contain_text(GRID_2)
    expect(first).to_contain_text(SIZE_5_BY_5)
    expect(first.get_by_test_id("my-room-players")).to_have_text("Joueurs : Ana, Bob")
    expect(first.get_by_test_id("my-room-activity")).to_have_text(
        "Dernière activité : 14 octobre 2026 à 10:30"
    )
    expect(first.get_by_test_id("my-room-solved")).to_have_count(0)


def test_ac5_the_first_room_has_a_link_that_resumes_it(
    page_1280: Page, live_server: str
) -> None:
    open_two_summaries(page_1280, live_server)

    link = my_room_items(page_1280).nth(0).get_by_test_id("my-room-link")
    expect(link).to_have_attribute("href", "/r/XYZ789")
    expect(link).to_have_text("Reprendre")
    expect(link).to_have_attribute("aria-label", "Reprendre le salon XYZ789")
    expect(link).to_have_attribute("tabindex", "0")
    assert link.evaluate("element => element.tagName") == "A"


def test_ac5_the_second_room_shows_an_unnumbered_grid_and_the_solved_sign(
    page_1280: Page, live_server: str
) -> None:
    open_two_summaries(page_1280, live_server)

    second = my_room_items(page_1280).nth(1)
    expect(second).to_have_attribute("data-grid", "")
    expect(second).to_have_attribute("data-solved", "true")
    expect(second).to_contain_text("Grille hors catalogue")
    expect(second).to_contain_text(SIZE_13_BY_17)
    expect(second.get_by_test_id("my-room-players")).to_have_text("Joueurs : Ana")
    expect(second.get_by_test_id("my-room-activity")).to_have_text(
        "Dernière activité : 13 octobre 2026 à 22:05"
    )
    expect(second.get_by_test_id("my-room-solved")).to_have_text("Terminée")
    link = second.get_by_test_id("my-room-link")
    expect(link).to_have_attribute("href", "/r/ABC234")


def test_ac5_nicknames_are_shown_as_text(page_1280: Page, live_server: str) -> None:
    route = SummariesRoute(body=[xyz_summary(players=HOSTILE_NAMES)])
    seed_storage(page_1280, two_identities())

    open_catalogue(page_1280, live_server, route)
    expect_my_rooms_ready(page_1280, 1)

    item = my_room_items(page_1280)
    # The nicknames as spec 040's displayNickname writes them.
    expect(item.get_by_test_id("my-room-players")).to_have_text(
        "Joueurs : <b>eve</b>, <img Src=x>"
    )
    expect(item.locator("b")).to_have_count(0)
    expect(item.locator("img")).to_have_count(0)


# ---- Loading, empty, error -----------------------------------------------------


def test_ac5_while_the_summaries_load_the_section_is_hidden(
    page_1280: Page, live_server: str
) -> None:
    route = HeldSummariesRoute()
    seed_storage(page_1280, two_identities())

    # The catalogue reaches `ready` while the summaries request waits.
    open_catalogue(page_1280, live_server, route)

    section = my_rooms(page_1280)
    expect(section).to_have_attribute("data-state", "loading")
    # Spec 046 (P4): nothing shows while it loads.
    assert section.get_attribute("hidden") is not None
    expect(section).to_be_hidden()
    expect(page_1280.locator("body")).not_to_contain_text(
        REMOVED_KEYS["my_rooms.loading"]
    )
    route.release([xyz_summary()])
    expect_my_rooms_ready(page_1280, 1)
    expect(section).to_be_visible()


def test_ac5_an_empty_answer_leaves_the_section_hidden_with_no_text(
    page_1280: Page, live_server: str
) -> None:
    route = SummariesRoute(body=[])
    seed_storage(page_1280, two_identities())

    open_catalogue(page_1280, live_server, route)

    expect_my_rooms_ready(page_1280, 0)
    # Spec 046 (P4): an empty answer shows no section.
    section = my_rooms(page_1280)
    assert section.get_attribute("hidden") is not None
    expect(section).to_be_hidden()
    expect(page_1280.locator("body")).not_to_contain_text(
        REMOVED_KEYS["my_rooms.empty"]
    )


def test_ac5_a_failed_request_shows_the_error_while_the_catalogue_loads(
    page_1280: Page, live_server: str
) -> None:
    route = SummariesRoute(body={"detail": "Internal Server Error"}, status=500)
    seed_storage(page_1280, two_identities())

    open_catalogue(page_1280, live_server, route)

    section = my_rooms(page_1280)
    expect(section).to_have_attribute("data-state", "error", timeout=WAIT_TIMEOUT_MS)
    # Spec 046: the error is the line `my-rooms-error`, under the heading.
    expect(section.get_by_test_id("my-rooms-error")).to_have_text(
        load_fr()["my_rooms.error"]
    )
    expect(page_1280.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready"
    )


@pytest.mark.parametrize(
    "answer",
    [{"rooms": []}, [{"code": XYZ}], "not a list"],
    ids=["an_object", "items_that_are_no_summaries", "a_string"],
)
def test_ac5_an_answer_that_is_not_an_array_of_summaries_shows_the_error(
    page_1280: Page, live_server: str, answer: object
) -> None:
    route = SummariesRoute(body=answer)
    seed_storage(page_1280, two_identities())

    open_catalogue(page_1280, live_server, route)

    section = my_rooms(page_1280)
    expect(section).to_have_attribute("data-state", "error", timeout=WAIT_TIMEOUT_MS)
    expect(section.get_by_test_id("my-rooms-error")).to_have_text(
        load_fr()["my_rooms.error"]
    )


def test_ac5_a_room_left_out_is_not_listed_and_its_identity_stays(
    page_1280: Page, live_server: str
) -> None:
    route = SummariesRoute(body=[xyz_summary()])
    seed_storage(page_1280, two_identities())

    open_catalogue(page_1280, live_server, route)

    expect_my_rooms_ready(page_1280, 1)
    expect(my_room_items(page_1280)).to_have_attribute("data-code", XYZ)
    assert read_storage(page_1280, f"nock.identity.{ABC}") == identity_value(ABC_TOKEN)


# ---- More than 100 identities --------------------------------------------------


def room_number(code: str) -> int:
    return int(code[1:])


def minute_of(number: int) -> int:
    """The minute of the last activity of room number `number`.

    Rooms 50 and 51 share one, so that the code decides their order.
    """
    if number == 51:
        return 50
    return number


def many_summary(code: str) -> dict[str, object]:
    minute = minute_of(room_number(code))
    hours, minutes = divmod(minute, 60)
    last_activity = f"2026-10-01T{hours:02d}:{minutes:02d}:00Z"
    return summary_json(code, 1, (5, 5), ["Ana"], last_activity, False)


def server_order(codes: list[str]) -> list[str]:
    """The codes sorted as the server sorts summaries: newest, then code order."""
    by_code = sorted(codes)
    return sorted(by_code, key=lambda code: -minute_of(room_number(code)))


def answer_many(body: object) -> object:
    """Answer one request with the summaries of its codes, in the server's order."""
    codes = [code for code, _ in sent_keys(body)]
    summaries: list[dict[str, object]] = []
    for code in server_order(codes):
        summaries.append(many_summary(code))
    return summaries


def many_identities() -> dict[str, str]:
    identities: dict[str, str] = {}
    for number in range(MANY_ROOMS):
        code = f"R{number:05d}"
        identities[f"nock.identity.{code}"] = identity_value(
            f"token-of-room-{number:05d}"
        )
    return identities


def open_many_rooms(page: Page, live_server: str) -> SummariesRoute:
    route = SummariesRoute(answer=answer_many)
    seed_storage(page, many_identities())
    open_catalogue(page, live_server, route)
    expect_my_rooms_ready(page, MANY_ROOMS)
    return route


def test_ac5_more_than_100_identities_go_in_requests_of_at_most_100_keys(
    page_1280: Page, live_server: str
) -> None:
    route = open_many_rooms(page_1280, live_server)

    sizes: list[int] = []
    sent: list[tuple[str, str]] = []
    for body in route.bodies:
        keys = sent_keys(body)
        sizes.append(len(keys))
        sent.extend(keys)
    expected: list[tuple[str, str]] = []
    for number in range(MANY_ROOMS):
        expected.append((f"R{number:05d}", f"token-of-room-{number:05d}"))

    assert len(sizes) >= 2
    assert max(sizes) <= 100
    assert sorted(sent) == expected


def test_ac5_the_summaries_of_several_requests_are_listed_as_the_server_sorts(
    page_1280: Page, live_server: str
) -> None:
    open_many_rooms(page_1280, live_server)

    shown = my_room_items(page_1280).evaluate_all(
        "items => items.map(item => item.getAttribute('data-code'))"
    )
    all_codes = [f"R{number:05d}" for number in range(MANY_ROOMS)]

    assert shown == server_order(all_codes)
