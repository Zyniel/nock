"""Tests of spec 036 (performance), AC-1 to AC-4: the time budgets.

AC-1, AC-2 and AC-4 measure the room page in Chromium under the spec's phone
profile (CPU throttling, plus the 4G network profile for AC-1 and AC-2, both sent
through CDP before the first `page.goto`), with the in-page timing of the test
harness. AC-3 measures the server's relay with eight simulated clients.

The shared setup is in `spec036_harness`.

Notes:

- FX-02's across words hold at most 7 letters, so two of them hold 12 cells. In
  AC-4 Ana types her two words, then types them again with other letters (so
  every key changes its cell on Bob's page): 20 keys in all.
- Edge cases checked as well: no mark for a room that is not found, nor a second
  one after a reconnection.
"""

from __future__ import annotations

import contextlib
import random
import statistics
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.server import create_app
from spec036_harness import (
    ANA_GAP_MS,
    ANA_KEYS,
    COLD_LOADS,
    EDITS_PER_RELAY_CLIENT,
    FX02_AT_MARK,
    INTERACTIVE_BUDGET_MS,
    LOAD_CLIENT_NAMES,
    LOAD_PLAN_EDITS,
    LOAD_SEED,
    LOAD_WARM_UP_MS,
    LOCAL_ECHO_BUDGET_MS,
    LOCAL_ECHO_GAP_MS,
    LOCAL_ECHO_KEYS,
    MARK_PROBE_SCRIPT,
    MARK_TIMEOUT_MS,
    PAGE_WAIT_MS,
    PROPAGATION_BUDGET_MS,
    RELAY_BUDGET_SECONDS,
    RELAY_CLIENT_NAMES,
    RELAY_EDIT_COUNT,
    RELAY_TIME_COUNT,
    SETTLE_MS,
    TYPING_PROBE_SCRIPT,
    TypingLoad,
    across_words,
    ana_keystrokes,
    ana_words,
    auto_join_script,
    cell_at,
    every_edit_answered,
    every_seq_received,
    expect_fx02_room_shown,
    expect_last_letters_shown,
    expect_reconnection_after_close,
    interactive_mark_times,
    join_simulated_clients,
    letter_cells,
    local_echo_keystrokes,
    local_echo_times,
    measured_times,
    missing_keystrokes,
    open_mock_room,
    open_phone_page,
    percentile_95,
    propagation_times,
    random_edit_plans,
    read_probe,
    relay_times,
    states_at_mark,
    tap_word_start,
    triples,
    type_keystrokes,
    wait_for,
    wait_for_interactive_mark,
)

# The fixtures of the harness. pytest looks for a test's fixtures among the names of
# its module, so they are imported by name. `x as x` is the explicit re-export
# form: it keeps ruff from reporting the import as unused or as redefined.
from spec036_harness import default_registry as default_registry
from spec036_harness import fx01_grid as fx01_grid
from spec036_harness import fx02_grid as fx02_grid

# ---- AC-1: FX-02 is interactive within 2.5 seconds --------------------------------


@pytest.mark.only_browser("chromium")
def test_ac1_three_cold_loads_of_fx02_are_interactive_within_2500_ms_at_the_median(
    browser: Browser, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    code = room_registry.register_room(fx02_grid)
    url = f"{live_server}/r/{code}"
    tap_row, tap_column = across_words(fx02_grid)[0].cells[0]
    start_times: list[float] = []
    for load_number in range(1, COLD_LOADS + 1):
        phone = open_phone_page(browser, with_network=True)
        try:
            phone.page.add_init_script(auto_join_script(code, "Ana"))
            phone.page.add_init_script(MARK_PROBE_SCRIPT)
            phone.page.goto(url)
            wait_for_interactive_mark(phone.page, MARK_TIMEOUT_MS)
            phone.page.wait_for_timeout(SETTLE_MS)
            mark_times = interactive_mark_times(phone.page)
            assert len(mark_times) == 1, f"load {load_number} set {mark_times} marks"
            at_mark = states_at_mark(phone.page)
            assert at_mark == [FX02_AT_MARK], f"load {load_number}, at the mark"
            start_times.append(mark_times[0])
            if load_number == COLD_LOADS:
                tap_word_start(phone.page, tap_row, tap_column)
                phone.page.keyboard.press("A")
                expect(cell_at(phone.page, tap_row, tap_column)).to_have_attribute(
                    "data-letter", "A"
                )
        finally:
            phone.context.close()

    median_ms = statistics.median(start_times)
    assert median_ms <= INTERACTIVE_BUDGET_MS, (
        f"median of the three nock:interactive startTime values {median_ms:.0f} ms, "
        f"limit {INTERACTIVE_BUDGET_MS:.0f} ms (loads: {start_times})"
    )


def test_ac1_a_room_that_is_not_found_sets_no_mark(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/r/ZZZZZZ")
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "not_found"
    )
    page.wait_for_timeout(SETTLE_MS)

    assert interactive_mark_times(page) == []


def test_ac1_a_snapshot_after_a_reconnection_adds_no_mark(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    server = open_mock_room(page, live_server, fx01_grid)
    wait_for_interactive_mark(page, PAGE_WAIT_MS)

    expect_reconnection_after_close(page, server, fx01_grid, 1011)
    page.wait_for_timeout(SETTLE_MS)

    assert len(interactive_mark_times(page)) == 1


# ---- AC-2: a typed letter shows locally within 50 ms ------------------------------


@pytest.mark.only_browser("chromium")
def test_ac2_a_typed_letter_shows_locally_within_50_ms_at_the_p95(
    browser: Browser, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    code = room_registry.register_room(fx02_grid)
    keystrokes = local_echo_keystrokes(fx02_grid)
    assert len(keystrokes) == LOCAL_ECHO_KEYS
    phone = open_phone_page(browser, with_network=True)
    try:
        phone.page.add_init_script(auto_join_script(code, "Ana"))
        phone.page.add_init_script(TYPING_PROBE_SCRIPT)
        phone.page.goto(f"{live_server}/r/{code}")
        expect_fx02_room_shown(phone.page)

        type_keystrokes(phone.page, keystrokes, LOCAL_ECHO_GAP_MS)
        expect_last_letters_shown(phone.page, keystrokes)
        probe = read_probe(phone.page)
    finally:
        phone.context.close()

    times = local_echo_times(probe, keystrokes)
    assert missing_keystrokes(keystrokes, times) == []
    p95_ms = percentile_95(measured_times(times))
    assert p95_ms <= LOCAL_ECHO_BUDGET_MS, (
        f"p95 (38th smallest of 40) from keydown to the cell's data-letter: "
        f"{p95_ms:.1f} ms, limit {LOCAL_ECHO_BUDGET_MS:.0f} ms "
        f"(max {max(measured_times(times)):.1f} ms)"
    )


# ---- AC-3: eight players typing two letters a second, server relay ----------------


def test_ac3_eight_players_typing_two_letters_a_second_are_relayed_within_100_ms(
    default_registry: RoomRegistry, fx02_grid: Grid, tmp_path: Path
) -> None:
    code = default_registry.register_room(fx02_grid)
    plans = random_edit_plans(
        random.Random(LOAD_SEED),
        letter_cells(fx02_grid),
        len(RELAY_CLIENT_NAMES),
        EDITS_PER_RELAY_CLIENT,
    )
    app = create_app(rooms=default_registry, dist_dir=tmp_path)
    with TestClient(app) as test_client, contextlib.ExitStack() as sockets:
        clients = join_simulated_clients(sockets, test_client, code, RELAY_CLIENT_NAMES)
        load = TypingLoad(clients, plans)
        load.start()
        assert load.wait_until_sent() == []
        wait_for(lambda: every_edit_answered(clients), "an answer to every edit")
        for client, plan in zip(clients, plans, strict=True):
            assert client.errors() == [], f"{client.name} got an error"
            assert triples(client.own_letter_changes()) == triples(plan)
        edit_seqs: set[int] = set()
        for client in clients:
            for answer in client.own_letter_changes():
                edit_seqs.add(answer.seq)
        assert len(edit_seqs) == RELAY_EDIT_COUNT
        wait_for(
            lambda: every_seq_received(clients, edit_seqs),
            "every letter_changed on every client",
        )
        for client in clients:
            seqs = [event.seq for event in client.letter_changes()]
            assert sorted(seqs) == sorted(edit_seqs), f"{client.name}'s events"
        times = relay_times(clients)

    assert len(times) == RELAY_TIME_COUNT
    p95 = percentile_95(times)
    assert p95 <= RELAY_BUDGET_SECONDS, (
        f"p95 (1064th smallest of 1120) of the relay times: {p95 * 1000:.1f} ms, "
        f"limit {RELAY_BUDGET_SECONDS * 1000:.0f} ms (max {max(times) * 1000:.1f} ms)"
    )


# ---- AC-4: under the same load, a letter reaches another page within 300 ms -------


@pytest.mark.only_browser("chromium")
def test_ac4_a_letter_typed_in_one_page_shows_in_another_within_300_ms_under_load(
    browser: Browser, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    code = room_registry.register_room(fx02_grid)
    url = f"{live_server}/r/{code}"
    keystrokes = ana_keystrokes(ana_words(fx02_grid))
    assert len(keystrokes) == ANA_KEYS
    ana_cells = {(keystroke.row, keystroke.column) for keystroke in keystrokes}
    load_cells = [cell for cell in letter_cells(fx02_grid) if cell not in ana_cells]
    plans = random_edit_plans(
        random.Random(LOAD_SEED), load_cells, len(LOAD_CLIENT_NAMES), LOAD_PLAN_EDITS
    )
    with contextlib.ExitStack() as pages:
        ana = open_phone_page(browser, with_network=False)
        pages.callback(ana.context.close)
        bob = open_phone_page(browser, with_network=False)
        pages.callback(bob.context.close)
        for phone, nickname in ((ana, "Ana"), (bob, "Bob")):
            phone.page.add_init_script(auto_join_script(code, nickname))
            phone.page.add_init_script(TYPING_PROBE_SCRIPT)
            phone.page.goto(url)
            expect_fx02_room_shown(phone.page)

        simulated_app = create_app(rooms=room_registry)
        with (
            TestClient(simulated_app) as test_client,
            contextlib.ExitStack() as sockets,
        ):
            clients = join_simulated_clients(
                sockets, test_client, code, LOAD_CLIENT_NAMES
            )
            load = TypingLoad(clients, plans)
            load.start()
            try:
                ana.page.wait_for_timeout(LOAD_WARM_UP_MS)
                type_keystrokes(ana.page, keystrokes, ANA_GAP_MS)
                expect_last_letters_shown(bob.page, keystrokes)
            finally:
                load.stop()
            assert load.wait_until_sent() == []
            ana_probe = read_probe(ana.page)
            bob_probe = read_probe(bob.page)
            wait_for(lambda: every_edit_answered(clients), "answers to the load")
            for client in clients:
                assert client.errors() == [], f"{client.name} was refused an edit"

    times = propagation_times(ana_probe, bob_probe, keystrokes)
    assert missing_keystrokes(keystrokes, times) == []
    p95_ms = percentile_95(measured_times(times))
    assert p95_ms <= PROPAGATION_BUDGET_MS, (
        f"p95 (19th smallest of 20) from Ana's keydown to Bob's data-letter: "
        f"{p95_ms:.1f} ms, limit {PROPAGATION_BUDGET_MS:.0f} ms "
        f"(max {max(measured_times(times)):.1f} ms)"
    )
