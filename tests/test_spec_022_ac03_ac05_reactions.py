"""Tests of spec 022, AC-3 to AC-5: reactions on a word.

AC-3 is tested on `handle_message` (the relay through `reply` and `to_others`, a
full word, a solved grid), on the real WebSocket (one frame each, no seq, nothing
logged) and with two browsers on the live server. AC-4's server edge case (a
reaction whose clue names no word is dropped, and an idle sender is still woken,
the lead's note of 2026-10-15) is tested on `handle_message`; its page part runs
with a mocked socket, where an in-page probe reads the reaction at every animation
frame and times its life with `performance.now()`. AC-5 checks the button and the
picker with a mocked socket. The order in the toolbar is relative (spec 024
AC-8). "Sends nothing" and "exactly one frame" leave the heartbeat `ping` frames
aside (the lead's note of 2026-10-15). AC-5's last step opens the panel, then the
picker, and checks their document order with both open (decision 15); after
`Escape` in the picker, the test waits SETTLE_MS before it checks that the panel
is still there, so that a panel closing with a transition is not missed.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClueRef,
    LetterChanged,
    PlayerState,
    PlayerStateChanged,
    React,
    Reaction,
    ReactionShown,
    parse_client_message,
    parse_server_message,
)
from nock.room import RoomConfig, tick
from nock.store import RoomStore
from spec021_harness import IDES, SENT, VIDE, clue_at, clue_key, select_word
from spec022_harness import (
    LIVE_WITHIN_SECONDS,
    POPOVER_PLACE,
    REACTION_VALUES,
    SETTLE_MS,
    WS_CONFIG,
    assert_sends_nothing,
    chat_room,
    expect_seq,
    frames_after,
    new_player_page,
    open_chat_room,
    open_panel,
    own_player_id,
    popover_place,
    reaction_frame,
    reactions_on_page,
    read_reaction,
    room_seq,
    send_react,
    shown,
    shown_reading,
    wait_for_reaction_count,
    wait_for_reading,
)
from spec024_harness import (
    NOW,
    EnterRoom,
    Received,
    TrafficLog,
    cell_at,
    events_of,
    full17,
    grid_from_text,
    join_peers,
    load_fr,
    make_dist_dir,
    ping_and_wait,
    player_record,
    seen_at,
    two_player_room,
    write,
)

QUIET_RULES = RoomConfig(silence_timeout_seconds=3600)
NO_WORD_CLUES = [
    pytest.param(ClueRef(row=1, column=0, clue_index=0), id="letter-cell"),
    pytest.param(ClueRef(row=0, column=3, clue_index=1), id="no-second-clue"),
    pytest.param(ClueRef(row=7, column=7, clue_index=0), id="outside-the-grid"),
]
REACTION_LIMIT = 5  # the default of RoomConfig.reaction_limit
SHOWN_MS = 3000
STILL_THERE_MS = 2700  # "still there 2,700 ms after it appeared"
GONE_BY_MS = 3500  # "no clue-reaction is left 3,500 ms after it appeared"
APPEAR_WITHIN_MS = 300
SECOND_REACTION_AFTER_MS = 1000
GONE_TIMEOUT_MS = 6000


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


# ---- AC-3: the rule ----


def test_ac3_python_a_reaction_is_relayed_to_everyone_and_gets_no_entry(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    outcome = send_react(state, "p2", IDES, Reaction.CLAP)

    expected = (
        ReactionShown(
            player_id="p2",
            clue=ClueRef(row=0, column=3, clue_index=0),
            reaction=Reaction.CLAP,
        ),
    )
    assert outcome.entries == ()
    assert outcome.reply == expected
    assert outcome.to_others == expected
    assert outcome.state.seq == state.seq == 2


def test_ac3_python_a_reaction_works_on_a_full_word_and_on_a_solved_grid(
    fx01_grid: Grid,
) -> None:
    filled = full17(fx01_grid)  # IDES is full: only (4, 4) is empty

    on_full_word = send_react(filled, "p2", IDES, Reaction.WOW)
    solved = write(on_full_word.state, "p1", 4, 4, "T").state
    on_solved_grid = send_react(solved, "p2", SENT, Reaction.THUMBS_UP)

    assert solved.solved is True
    assert on_full_word.entries == ()
    assert on_full_word.reply == (shown("p2", IDES, Reaction.WOW),)
    assert on_full_word.to_others == (shown("p2", IDES, Reaction.WOW),)
    assert on_solved_grid.entries == ()
    assert on_solved_grid.reply == (shown("p2", SENT, Reaction.THUMBS_UP),)
    assert on_solved_grid.to_others == (shown("p2", SENT, Reaction.THUMBS_UP),)


# ---- AC-3: the WebSocket ----


def reaction_texts(log: TrafficLog, client: str) -> list[str]:
    """The raw `reaction` frames one simulated client received, in order."""
    found: list[str] = []
    for item in log.items():
        if isinstance(item, Received) and item.client == client:
            parsed = json.loads(item.text)
            if isinstance(parsed, dict) and parsed.get("type") == "reaction":
                found.append(item.text)
    return found


def test_ac3_websocket_each_player_receives_the_reaction_once_without_a_seq(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    store = RoomStore(":memory:")
    log = TrafficLog()
    react_frame = json.dumps(
        {
            "type": "react",
            "clue": {"row": 0, "column": 3, "clue_index": 0},
            "reaction": "clap",
        }
    )
    try:
        with (
            chat_room(fx01_grid, dist_dir, WS_CONFIG, store=store) as (
                client,
                registry,
                code,
            ),
            contextlib.ExitStack() as stack,
        ):
            ana, bob = join_peers(stack, client, code, ["Ana", "Bob"], log)
            logged_before = store.read_log(code)
            bob.send_text(react_frame)
            wait_for_reaction_count(bob, 1)
            wait_for_reaction_count(ana, 1)
            ping_and_wait(bob)
            ping_and_wait(ana)
            bob_id = bob.you()
            seq_after = room_seq(registry, code)
            logged_after = store.read_log(code)
    finally:
        store.close()

    expected = ReactionShown(player_id=bob_id, clue=IDES, reaction=Reaction.CLAP)
    for name in ("Ana", "Bob"):
        frames = reaction_texts(log, name)
        assert len(frames) == 1, (name, frames)
        parsed = json.loads(frames[0])
        assert isinstance(parsed, dict)
        assert "seq" not in parsed
        assert parse_server_message(frames[0]) == expected
    assert seq_after == 2
    assert logged_after == logged_before


# ---- AC-3: two browsers on the live server ----


def shown_on_ides(page: Page) -> tuple[object, object, object, object]:
    """The count, `data-reaction`, `data-player-id` and text of IDES's reaction."""
    reading = read_reaction(page, IDES)
    return (
        reading["reactions"],
        reading.get("reaction"),
        reading.get("playerId"),
        reading.get("text"),
    )


def test_ac3_browser_a_reaction_shows_on_the_word_for_both_players(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    clap = load_fr()["reaction.clap"]
    code = room_registry.register_room(fx01_grid)
    ana, close_ana = new_player_page(browser, live_server, code, "Ana", enter_room)
    try:
        bob, close_bob = new_player_page(browser, live_server, code, "Bob", enter_room)
        try:
            expect(ana.get_by_test_id("roster-player")).to_have_count(2)
            bob_id = own_player_id(bob)
            cell_at(bob, 0, 3).click()
            expect(bob.get_by_test_id("grid")).to_have_attribute("data-word", "0,3,0")
            bob.get_by_test_id("react-button").click()
            option = bob.locator(
                '[data-testid="reaction-option"][data-reaction="clap"]'
            )
            option.click()
            deadline = time.monotonic() + LIVE_WITHIN_SECONDS
            expected = (1, "clap", bob_id, clap)
            wait_for_reading(ana, lambda: shown_on_ides(ana), expected, deadline)
            wait_for_reading(bob, lambda: shown_on_ides(bob), expected, deadline)
        finally:
            close_bob()
    finally:
        close_ana()


# ---- AC-4: the server drops a reaction whose clue names no word ----


@pytest.mark.parametrize("clue", NO_WORD_CLUES)
def test_ac4_python_a_reaction_on_a_clue_that_names_no_word_leaves_no_trace(
    fx01_grid: Grid, clue: ClueRef
) -> None:
    state = two_player_room(fx01_grid)
    for _ in range(REACTION_LIMIT):
        dropped = send_react(state, "p2", clue, Reaction.WOW, NOW + 1)
        assert dropped.entries == ()
        assert dropped.reply == ()
        assert dropped.to_others == ()
        assert dropped.state == seen_at(state, "p2", NOW + 1)
        state = dropped.state

    # The drops were not counted: a reaction on a word is still relayed.
    relayed = send_react(state, "p2", IDES, Reaction.WOW, NOW + 1)

    assert relayed.reply == (shown("p2", IDES, Reaction.WOW),)
    assert relayed.to_others == (shown("p2", IDES, Reaction.WOW),)


def test_ac4_python_a_dropped_reaction_still_wakes_an_idle_sender(
    fx01_grid: Grid,
) -> None:
    idle = tick(two_player_room(fx01_grid), NOW + 120, QUIET_RULES).state
    assert player_record(idle, "p2").state == PlayerState.IDLE
    letter_cell = ClueRef(row=1, column=0, clue_index=0)

    outcome = send_react(idle, "p2", letter_cell, Reaction.WOW, NOW + 130)

    woken = PlayerStateChanged(
        seq=idle.seq + 1, player_id="p2", state=PlayerState.ACTIVE
    )
    assert events_of(outcome) == [woken]
    assert outcome.reply == ()
    assert outcome.to_others == ()


# ---- AC-4: a shown reaction on the page ----


class Change(NamedTuple):
    """A frame where what IDES shows of the reactions changed (the probe)."""

    at_ms: float  # since the probe started
    count: int
    reaction: str | None
    player_id: str | None


# The probe: from now on, at every animation frame, read the `clue-reaction`
# elements of one clue and note each change of their count, `data-reaction` and
# `data-player-id`, with its time since the probe started (`performance.now()`).
START_PROBE_SCRIPT = r"""
selector => {
  const probe = {startedAt: performance.now(), changes: [], done: false};
  window.reactionProbe = probe;
  let lastKey = null;
  const look = () => {
    if (probe.done) {
      return;
    }
    const clue = document.querySelector(selector);
    const found = clue === null
      ? [] : clue.querySelectorAll('[data-testid="clue-reaction"]');
    const first = found.length > 0 ? found[0] : null;
    const change = [
      performance.now() - probe.startedAt,
      found.length,
      first === null ? null : first.getAttribute('data-reaction'),
      first === null ? null : first.getAttribute('data-player-id'),
    ];
    const key = change.slice(1).join('|');
    if (key !== lastKey) {
      probe.changes.push(change);
      lastKey = key;
    }
    requestAnimationFrame(look);
  };
  look();
}
"""
STOP_PROBE_SCRIPT = r"""
() => {
  const probe = window.reactionProbe;
  probe.done = true;
  return probe.changes;
}
"""


def ides_selector() -> str:
    """The CSS selector of the `clue` element of IDES."""
    cell = '[data-testid="cell"][data-row="0"][data-column="3"]'
    return f'{cell} [data-testid="clue"][data-clue-index="0"]'


def start_probe(page: Page) -> None:
    """Start the probe on IDES's clue."""
    page.evaluate(START_PROBE_SCRIPT, ides_selector())


def stop_probe(page: Page) -> list[Change]:
    """Stop the probe and return the changes it noted, in order."""
    found = page.evaluate(STOP_PROBE_SCRIPT)
    changes: list[Change] = []
    for at_ms, count, reaction, player_id in found:
        changes.append(Change(float(at_ms), int(count), reaction, player_id))
    return changes


def states_of(changes: list[Change]) -> list[tuple[int, str | None, str | None]]:
    """What each noted change showed, without its time."""
    return [(change.count, change.reaction, change.player_id) for change in changes]


def expect_no_reaction_on_ides(page: Page) -> None:
    """Wait until IDES shows no reaction, at most GONE_TIMEOUT_MS."""
    reactions = clue_at(page, IDES).get_by_test_id("clue-reaction")
    expect(reactions).to_have_count(0, timeout=GONE_TIMEOUT_MS)


def test_ac4_browser_a_reaction_lasts_3_seconds_and_a_newer_one_replaces_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    mock = open_chat_room(page, live_server, fx01_grid, seq=5)
    nothing = (0, None, None)

    # First run: a `wow` of `p2` on IDES.
    start_probe(page)
    mock.send(reaction_frame("p2", IDES, Reaction.WOW))
    expect(clue_at(page, IDES).get_by_test_id("clue-reaction")).to_have_count(1)
    wow_reading = read_reaction(page, IDES)
    expect_no_reaction_on_ides(page)
    first_run = stop_probe(page)
    expect_seq(page, 5)

    # Second run: a `thinking` of `p3` 1,000 ms after a `wow` of `p2`.
    start_probe(page)
    mock.send(reaction_frame("p2", IDES, Reaction.WOW))
    page.wait_for_timeout(SECOND_REACTION_AFTER_MS)
    mock.send(reaction_frame("p3", IDES, Reaction.THINKING))
    expect_no_reaction_on_ides(page)
    second_run = stop_probe(page)
    expect_seq(page, 5)

    # A reaction on a letter cell shows nothing; a later event is applied.
    letter_cell = ClueRef(row=1, column=0, clue_index=0)
    mock.send(reaction_frame("p2", letter_cell, Reaction.CLAP))
    page.wait_for_timeout(SETTLE_MS)
    shown_after_letter_cell = reactions_on_page(page)
    expect_seq(page, 5)
    letter = LetterChanged(
        seq=6, row=1, column=0, letter="T", pencil=False, player_id="p2"
    )
    mock.send(letter.model_dump_json())
    expect_seq(page, 6)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")

    assert wow_reading == shown_reading("p2", "wow", fr["reaction.wow"], "Bob : Waouh")
    assert states_of(first_run) == [nothing, (1, "wow", "p2"), nothing], first_run
    appeared = first_run[1].at_ms
    lasted = first_run[2].at_ms - appeared
    assert appeared <= APPEAR_WITHIN_MS, first_run
    assert STILL_THERE_MS <= lasted <= GONE_BY_MS, first_run
    assert states_of(second_run) == [
        nothing,
        (1, "wow", "p2"),
        (1, "thinking", "p3"),
        nothing,
    ], second_run
    newer_lasted = second_run[3].at_ms - second_run[2].at_ms
    assert STILL_THERE_MS <= newer_lasted <= GONE_BY_MS, second_run
    assert shown_after_letter_cell == 0


# ---- AC-5: the reaction button and the picker ----

BUTTON_ORDER_SCRIPT = r"""
() => {
  const byId = (id) => document.querySelector(`[data-testid="${id}"]`);
  const follows = (first, second) => Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const toolbar = byId('room-toolbar');
  const button = byId('react-button');
  const flag = byId('flag-button');
  const authors = byId('authors-switch');
  return {
    insideToolbar: toolbar !== null && button !== null && toolbar.contains(button),
    afterFlag: flag !== null && button !== null && follows(flag, button),
    beforeAuthors: authors !== null && button !== null && follows(button, authors),
  };
}
"""
OPTIONS_SCRIPT = r"""
() => {
  const selector = '[data-testid="reaction-picker"] [data-testid="reaction-option"]';
  const options = [];
  for (const option of document.querySelectorAll(selector)) {
    options.push([
      option.getAttribute('data-reaction'),
      option.textContent.trim(),
      option.getAttribute('aria-label'),
    ]);
  }
  return options;
}
"""
# With both open: whether the picker comes before the panel in document order,
# neither holding the other.
PICKER_BEFORE_PANEL_SCRIPT = r"""
() => {
  const picker = document.querySelector('[data-testid="reaction-picker"]');
  const panel = document.querySelector('[data-testid="chat-panel"]');
  if (picker === null || panel === null) {
    return {picker: picker !== null, panel: panel !== null};
  }
  const position = picker.compareDocumentPosition(panel);
  return {
    pickerBeforePanel: Boolean(position & Node.DOCUMENT_POSITION_FOLLOWING),
    nested: picker.contains(panel) || panel.contains(picker),
  };
}
"""
PICKER_BEFORE_PANEL = {"pickerBeforePanel": True, "nested": False}


def expected_options() -> list[list[str]]:
    """The five options: value, `t("reaction.<value>")`, its `_label`."""
    fr = load_fr()
    options: list[list[str]] = []
    for value in REACTION_VALUES:
        options.append([value, fr[f"reaction.{value}"], fr[f"reaction.{value}_label"]])
    return options


def test_ac5_browser_the_picker_offers_the_five_reactions_on_the_selected_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    mock = open_chat_room(page, live_server, fx01_grid)
    button = page.get_by_test_id("react-button")
    picker = page.get_by_test_id("reaction-picker")

    expect(button).to_have_count(1)
    order = page.evaluate(BUTTON_ORDER_SCRIPT)
    expect(button).to_have_attribute("type", "button")
    expect(button).to_have_text(fr["reaction.button"])
    expect(button).to_have_attribute("aria-label", fr["reaction.button_label"])
    expect(button).to_have_attribute("aria-controls", "reaction-picker")
    expect(button).to_have_attribute("aria-expanded", "false")
    expect(button).to_be_disabled()
    expect(picker).to_have_count(0)

    select_word(page, VIDE)
    expect(button).to_be_enabled()
    button.click()
    expect(picker).to_be_visible()
    expect(button).to_have_attribute("aria-expanded", "true")
    expect(picker).to_have_attribute("id", "reaction-picker")
    expect(picker).to_have_attribute("role", "group")
    expect(picker).to_have_attribute("aria-label", fr["reaction.picker_label"])
    options = page.evaluate(OPTIONS_SCRIPT)
    expect(page.get_by_test_id("reaction-option").first).to_be_focused()
    place = popover_place(page, "reaction-picker")

    laugh = picker.locator('[data-reaction="laugh"]')
    frames = frames_after(page, mock, lambda: laugh.click())
    expect(picker).to_have_count(0)
    expect(button).to_be_focused()
    expect(button).to_have_attribute("aria-expanded", "false")

    button.click()
    expect(picker).to_be_visible()
    assert_sends_nothing(page, mock, lambda: page.keyboard.press("Escape"))
    expect(picker).to_have_count(0)
    expect(button).to_be_focused()

    button.click()
    expect(picker).to_be_visible()
    assert_sends_nothing(page, mock, lambda: button.click())
    expect(picker).to_have_count(0)
    expect(button).to_be_focused()

    # Last: with VIDE still selected, the panel, then the picker (decision 15).
    panel = page.get_by_test_id("chat-panel")
    open_panel(page)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-word", clue_key(VIDE))
    button.click()
    expect(picker).to_be_visible()
    expect(panel).to_be_visible()
    expect(page.get_by_test_id("reaction-option").first).to_be_focused()
    picker_place_with_panel = popover_place(page, "reaction-picker")
    panel_place_with_picker = popover_place(page, "chat-panel")
    pair_order = page.evaluate(PICKER_BEFORE_PANEL_SCRIPT)
    page.keyboard.press("Escape")
    expect(picker).to_have_count(0)
    expect(button).to_be_focused()
    page.wait_for_timeout(SETTLE_MS)
    expect(panel).to_be_visible()

    assert order == {"insideToolbar": True, "afterFlag": True, "beforeAuthors": True}
    assert options == expected_options()
    assert place == POPOVER_PLACE
    assert picker_place_with_panel == POPOVER_PLACE
    assert panel_place_with_picker == POPOVER_PLACE
    assert pair_order == PICKER_BEFORE_PANEL
    assert len(frames) == 1, frames
    parsed = parse_client_message(json.dumps(frames[0]))
    assert parsed == React(
        clue=ClueRef(row=2, column=0, clue_index=0), reaction=Reaction.LAUGH
    )
