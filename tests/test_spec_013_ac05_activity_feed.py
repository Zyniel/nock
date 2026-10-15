"""Tests of spec 013, AC-5: the activity feed.

The feed lines for checks, reveals, flags, lock, settings and host changes are
tested with mocked events only: the server does not produce them yet (specs 014,
021, 023 and 024). The shared setup is in `spec013_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    CellTarget,
    ClueRef,
    Direction,
    FlagChanged,
    GridTarget,
    HelpMode,
    HostChanged,
    LeaveReason,
    LetterChanged,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    RevealBudget,
    RevealResult,
    RoomSettings,
    SettingsChanged,
    WordTarget,
)
from spec013_harness import (
    FEED_LIMIT,
    check_frame,
    feed_items,
    feed_locator,
    feed_snapshot_players,
    grid_from_text,
    load_fr,
    open_room,
    player_view,
    selection_frame,
    settle,
    state_frame,
)

CLUE_FATALES = ClueRef(row=0, column=3, clue_index=0)
CLUE_MARINE = ClueRef(row=0, column=0, clue_index=1)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-5: the activity feed ----


def joined_frame(seq: int, player_id: str, nickname: str, colour: int) -> str:
    event = PlayerJoined(seq=seq, player=player_view(player_id, nickname, colour))
    return event.model_dump_json()


def left_frame(seq: int, player_id: str, reason: LeaveReason) -> str:
    return PlayerLeft(seq=seq, player_id=player_id, reason=reason).model_dump_json()


def reveal_frame(seq: int, player_id: str, target: CellTarget | WordTarget) -> str:
    event = RevealResult(
        seq=seq,
        player_id=player_id,
        target=target,
        reveal_budget=RevealBudget(letters=4, words=1),
    )
    return event.model_dump_json()


def flag_frame(seq: int, player_id: str, clue: ClueRef | None) -> str:
    return FlagChanged(seq=seq, player_id=player_id, clue=clue).model_dump_json()


def settings_frame(
    seq: int,
    player_id: str,
    help_mode: HelpMode,
    letters: int,
    words: int,
    locked: bool,
) -> str:
    settings = RoomSettings(
        help_mode=help_mode,
        reveal_budget=RevealBudget(letters=letters, words=words),
        locked=locked,
    )
    event = SettingsChanged(
        seq=seq,
        player_id=player_id,
        settings=settings,
        reveal_budget=RevealBudget(letters=0, words=0),
    )
    return event.model_dump_json()


def host_frame(seq: int, player_id: str) -> str:
    return HostChanged(seq=seq, player_id=player_id).model_dump_json()


NONE_SETTINGS_TEXT = (
    "Ana a modifié les réglages : aide désactivée, 3 lettres et 2 mots à révéler"
)

SPEC_EXAMPLE_ITEMS = [
    ("player_joined", "6", "Cy a rejoint le salon"),
    ("check", "7", "Bob a vérifié un mot"),
    ("reveal", "8", "Cy a révélé une lettre"),
    ("flag", "9", "Bob bloque sur « Fatales à César »"),
    (
        "settings_changed",
        "10",
        "Ana a modifié les réglages : aide par vote, 5 lettres et 1 mots à révéler",
    ),
    ("room_locked", "11", "Ana a verrouillé le salon"),
    ("player_removed", "12", "Cy a été retiré du salon"),
]


def spec_example_frames() -> list[str]:
    return [
        joined_frame(6, "p3", "Cy", 2),
        check_frame(7, "p2", WordTarget(row=0, column=3, clue_index=0)),
        reveal_frame(8, "p3", CellTarget(row=1, column=0)),
        flag_frame(9, "p2", CLUE_FATALES),
        settings_frame(10, "p1", HelpMode.VOTE, 5, 1, False),
        settings_frame(11, "p1", HelpMode.VOTE, 5, 1, True),
        left_frame(12, "p3", LeaveReason.REMOVED),
    ]


def test_ac5_browser_the_feed_lists_the_events_of_the_spec_in_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
    expect(page.get_by_test_id("activity-feed")).to_be_visible()
    assert feed_items(page) == []

    for frame in spec_example_frames():
        mock.send(frame)

    expect(feed_locator(page)).to_have_count(7)
    assert feed_items(page) == SPEC_EXAMPLE_ITEMS


def test_ac5_browser_events_sent_out_of_order_are_listed_by_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
    frames = spec_example_frames()
    sending_order = [0, 1, 3, 2, 4, 6, 5]

    for index in sending_order:
        mock.send(frames[index])

    expect(feed_locator(page)).to_have_count(7)
    assert feed_items(page) == SPEC_EXAMPLE_ITEMS


def test_ac5_browser_the_feed_has_its_heading_and_no_item_from_the_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    feed = page.get_by_test_id("activity-feed")
    expect(feed).to_contain_text("Activité")
    expect(feed).to_contain_text(load_fr()["feed.heading"])
    expect(feed_locator(page)).to_have_count(0)
    settle(page)
    assert feed_items(page) == []


def test_ac5_browser_the_other_kinds_of_departure_check_reveal_and_settings(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
    frames = [
        joined_frame(6, "p3", "Cy", 2),
        left_frame(7, "p3", LeaveReason.LEFT),
        check_frame(8, "p3", GridTarget()),
        left_frame(9, "p2", LeaveReason.TIMED_OUT),
        reveal_frame(10, "p1", WordTarget(row=0, column=0, clue_index=1)),
        flag_frame(11, "p1", CLUE_MARINE),
        settings_frame(12, "p1", HelpMode.FREE, 5, 1, True),
        settings_frame(13, "p1", HelpMode.FREE, 5, 1, False),
        settings_frame(14, "p1", HelpMode.NONE, 3, 2, False),
        settings_frame(15, "p1", HelpMode.NONE, 3, 2, False),
        settings_frame(16, "p1", HelpMode.FREE, 3, 2, True),
        host_frame(17, "p1"),
        check_frame(18, "p1", CellTarget(row=1, column=0)),
    ]

    for frame in frames:
        mock.send(frame)

    expect(feed_locator(page)).to_have_count(13)
    assert feed_items(page) == [
        ("player_joined", "6", "Cy a rejoint le salon"),
        ("player_left", "7", "Cy a quitté le salon"),
        ("check", "8", "Cy a vérifié la grille"),
        ("player_timed_out", "9", "Bob est parti (déconnecté trop longtemps)"),
        ("reveal", "10", "Ana a révélé un mot"),
        ("flag", "11", "Ana bloque sur « De la marine »"),
        ("room_locked", "12", "Ana a verrouillé le salon"),
        ("room_unlocked", "13", "Ana a déverrouillé le salon"),
        (
            "settings_changed",
            "14",
            NONE_SETTINGS_TEXT,
        ),
        (
            "settings_changed",
            "15",
            NONE_SETTINGS_TEXT,
        ),
        (
            "settings_changed",
            "16",
            "Ana a modifié les réglages : aide libre, 3 lettres et 2 mots à révéler",
        ),
        ("host_changed", "17", "Ana est maintenant l'hôte"),
        ("check", "18", "Ana a vérifié une lettre"),
    ]


def test_ac5_browser_the_settings_are_compared_with_the_snapshot_settings(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    locked_settings = RoomSettings(
        help_mode=HelpMode.FREE,
        reveal_budget=RevealBudget(letters=5, words=1),
        locked=True,
    )
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        feed_snapshot_players(),
        seq=5,
        settings=locked_settings,
    )

    mock.send(settings_frame(6, "p1", HelpMode.FREE, 5, 1, False))

    expect(feed_locator(page)).to_have_count(1)
    assert feed_items(page) == [("room_unlocked", "6", "Ana a déverrouillé le salon")]


def test_ac5_browser_events_without_a_line_add_no_item(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
    silent_frames = [
        LetterChanged(
            seq=6, row=1, column=0, letter="T", pencil=False, player_id="p2"
        ).model_dump_json(),
        CellLocked(
            seq=7, row=1, column=0, letter="T", revealed=False
        ).model_dump_json(),
        state_frame(8, "p2", PlayerState.IDLE),
        flag_frame(9, "p2", None),
    ]

    for frame in silent_frames:
        mock.send(frame)
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    mock.send(check_frame(10, "p2", GridTarget()))

    expect(feed_locator(page)).to_have_count(1)
    assert feed_items(page) == [("check", "10", "Bob a vérifié la grille")]


def test_ac5_browser_an_unknown_player_is_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    mock.send(check_frame(6, "p9", WordTarget(row=0, column=3, clue_index=0)))
    mock.send(left_frame(7, "p9", LeaveReason.TIMED_OUT))
    mock.send(check_frame(8, "p2", GridTarget()))

    expect(feed_locator(page)).to_have_count(3)
    assert feed_items(page) == [
        ("check", "6", "Quelqu'un a vérifié un mot"),
        ("player_timed_out", "7", "Quelqu'un est parti (déconnecté trop longtemps)"),
        ("check", "8", "Bob a vérifié la grille"),
    ]


def test_ac5_browser_the_feed_keeps_the_last_100_items(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    for seq in range(6, 6 + FEED_LIMIT):
        mock.send(check_frame(seq, "p2", GridTarget()))
    expect(feed_locator(page)).to_have_count(FEED_LIMIT)
    assert feed_items(page)[0][1] == "6"

    mock.send(check_frame(6 + FEED_LIMIT, "p2", GridTarget()))

    last_seq = 6 + FEED_LIMIT
    expect(feed_locator(page).last).to_have_attribute("data-seq", str(last_seq))
    items = feed_items(page)
    assert len(items) == FEED_LIMIT
    seqs = [int(seq) for _, seq, _ in items]
    assert seqs == list(range(7, last_seq + 1))


def test_ac5_browser_a_departed_player_keeps_their_nickname_in_later_items(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    mock.send(joined_frame(6, "p3", "Cy", 2))
    mock.send(left_frame(7, "p3", LeaveReason.REMOVED))
    mock.send(reveal_frame(8, "p3", CellTarget(row=1, column=0)))

    expect(feed_locator(page)).to_have_count(3)
    assert feed_items(page)[1:] == [
        ("player_removed", "7", "Cy a été retiré du salon"),
        ("reveal", "8", "Cy a révélé une lettre"),
    ]


def test_ac5_browser_a_nickname_is_inserted_as_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    mock.send(joined_frame(6, "p3", "<b>Eve</b>", 2))

    expect(feed_locator(page)).to_have_count(1)
    assert feed_items(page) == [("player_joined", "6", "<b>Eve</b> a rejoint le salon")]
    expect(feed_locator(page).locator("b")).to_have_count(0)


def test_ac5_fr_json_has_the_feed_texts() -> None:
    fr = load_fr()

    assert fr["feed.heading"] == "Activité"
    assert fr["feed.someone"] == "Quelqu'un"
    assert fr["feed.player_joined"] == "{name} a rejoint le salon"
    assert fr["feed.player_left"] == "{name} a quitté le salon"
    assert fr["feed.player_removed"] == "{name} a été retiré du salon"
    assert fr["feed.player_timed_out"] == "{name} est parti (déconnecté trop longtemps)"
    assert fr["feed.check.letter"] == "{name} a vérifié une lettre"
    assert fr["feed.check.word"] == "{name} a vérifié un mot"
    assert fr["feed.check.grid"] == "{name} a vérifié la grille"
    assert fr["feed.reveal.letter"] == "{name} a révélé une lettre"
    assert fr["feed.reveal.word"] == "{name} a révélé un mot"
    assert fr["feed.flag"] == "{name} bloque sur « {clue} »"
    assert fr["feed.room_locked"] == "{name} a verrouillé le salon"
    assert fr["feed.room_unlocked"] == "{name} a déverrouillé le salon"
    assert fr["feed.settings_changed"] == (
        "{name} a modifié les réglages : aide {help_mode}, "
        "{letters} lettres et {words} mots à révéler"
    )
    assert fr["feed.host_changed"] == "{name} est maintenant l'hôte"
    assert fr["settings.help_mode.free"] == "libre"
    assert fr["settings.help_mode.vote"] == "par vote"
    assert fr["settings.help_mode.none"] == "désactivée"
