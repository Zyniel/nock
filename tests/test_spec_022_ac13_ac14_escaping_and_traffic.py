"""Tests of spec 022, AC-13 and AC-14: chat shows as plain text, and chat and
reactions pass spec 037's traffic checker.

AC-13 runs in a browser with a mocked socket. AC-14 replays spec 037 AC-1's full
game on the real WebSocket (spec 037's "Test harness": `POST /api/rooms` on FX-01
catalogue entry 1, Ana and Bob type the 18 letters with three mistakes and one
erase, Cy joins after the first letters), with Bob's and Ana's chat lines and
Bob's reaction before Cy joins. The checker is spec 037 AC-1's (the three rules of
"What a browser may receive", replayed in order with the letters earned so far,
random identifier values set aside), copied from
`tests/test_spec_037_ac01_full_game_traffic.py`, with the chat texts set aside
as AC-14 says.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Dialog, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    Chat,
    ChatMessage,
    EditLetter,
    Erase,
    GridSolved,
    Join,
    LetterChanged,
    React,
    Reaction,
)
from nock.server import create_app
from spec021_harness import IDES, clue_at
from spec022_harness import (
    SETTLE_MS,
    chat_messages_of,
    open_chat_room,
    open_panel,
    reaction_frame,
    read_chat_lines,
    wait_for_chat_count,
    wait_for_reaction_count,
)
from spec024_harness import (
    Earned,
    Peer,
    Received,
    TrafficLog,
    connect,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    player_view,
)

ANSWERS = ("TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST")
FORBIDDEN_KEYS = ("answer", "solution")
# Values that are random identifiers: they could by chance spell a short answer.
IDENTIFIER_KEYS = ("resume_token", "player_id", "you", "author", "code")

Cell = tuple[int, int]
Step = tuple[int, int, str | None]  # row, column, letter (None: erase)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


# ---- AC-13: plain text ----


def test_ac13_browser_chat_texts_and_names_show_as_plain_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    dialogs: list[str] = []

    def note_dialog(dialog: Dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", note_dialog)
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "<b>Eve</b>", 1),
        player_view("p3", "<img src=x>", 2),
    ]
    chat = [
        ChatMessage(seq=3, player_id="p2", text="<b>salut</b>"),
        ChatMessage(seq=4, player_id="p3", text="<img src=x onerror=alert(1)>"),
    ]
    mock = open_chat_room(
        page, live_server, fx01_grid, seq=5, players=players, chat=chat
    )
    open_panel(page)
    expect(page.get_by_test_id("chat-message")).to_have_count(2)
    lines = read_chat_lines(page)

    mock.send(reaction_frame("p3", IDES, Reaction.CLAP))
    label = clue_at(page, IDES).get_by_test_id("clue-reaction-label")
    # Spec 040's displayNickname writes `<b>Eve</b>` as `<b>eve</b>` and
    # `<img src=x>` as `<img Src=x>`.
    expect(label).to_have_text("<img Src=x> : Bravo")
    page.wait_for_timeout(SETTLE_MS)
    bold_count = page.locator("b").count()
    image_count = page.locator("img").count()

    shown = [(line.author, line.text) for line in lines]
    assert shown == [
        ("<b>eve</b>", "<b>salut</b>"),
        ("<img Src=x>", "<img src=x onerror=alert(1)>"),
    ]
    assert bold_count == 0
    assert image_count == 0
    assert dialogs == []


# ---- AC-14: spec 037's traffic checker, with chat texts set aside ----


def keys_of(value: object) -> list[str]:
    """Every key of every object inside a parsed JSON value."""
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(keys_of(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(keys_of(child))
    return keys


def without_identifiers(value: object) -> object:
    """A copy of a parsed JSON value without the random identifier values."""
    if isinstance(value, dict):
        kept: dict[str, object] = {}
        for key, child in value.items():
            if key in IDENTIFIER_KEYS:
                continue
            kept[str(key)] = without_identifiers(child)
        return kept
    if isinstance(value, list):
        kept_list: list[object] = []
        for child in value:
            kept_list.append(without_identifiers(child))
        return kept_list
    return value


def letters_in(value: object) -> list[tuple[int, int, str]]:
    """Every (row, column, letter) a parsed payload shows at a cell."""
    found: list[tuple[int, int, str]] = []
    if isinstance(value, dict):
        kind = value.get("type")
        row = value.get("row")
        column = value.get("column")
        letter = value.get("letter")
        shows_letter = kind in ("letter_changed", "cell_locked", "letter")
        has_position = isinstance(row, int) and isinstance(column, int)
        if shows_letter and has_position and isinstance(letter, str):
            assert isinstance(row, int)
            assert isinstance(column, int)
            found.append((row, column, letter))
        for child in value.values():
            found.extend(letters_in(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(letters_in(child))
    return found


def rule_problems(parsed: object, raw: str, earned: dict[Cell, set[str]]) -> list[str]:
    """The rules of "What a browser may receive" (spec 037) that a payload breaks.

    Args:
        parsed: The payload's JSON value, None when it is not JSON.
        raw: The payload's text, scanned as it is when it is not JSON.
        earned: The letters earned so far, by cell.
    """
    problems: list[str] = []
    scanned = raw
    if parsed is not None:
        for key in keys_of(parsed):
            if key in FORBIDDEN_KEYS:
                problems.append(f"the key {key!r}")
        scanned = json.dumps(without_identifiers(parsed))
        for row, column, letter in letters_in(parsed):
            if letter not in earned.get((row, column), set()):
                problems.append(f"the unearned letter {letter!r} at ({row}, {column})")
    for answer in ANSWERS:
        if answer in scanned:
            problems.append(f"the answer {answer!r}")
    return problems


def set_chat_texts_aside(parsed: object) -> tuple[object, list[str]]:
    """A copy without the `text` of a `chat_message` or of a snapshot's chat lines.

    Returns:
        The copy, and the texts set aside, in order.
    """
    if not isinstance(parsed, dict):
        return parsed, []
    copy: dict[str, object] = dict(parsed)
    texts: list[str] = []
    kind = copy.get("type")
    if kind == "chat_message" and "text" in copy:
        texts.append(str(copy.pop("text")))
    chat = copy.get("chat")
    if kind == "snapshot" and isinstance(chat, list):
        lines: list[object] = []
        for line in chat:
            if isinstance(line, dict) and "text" in line:
                line_copy: dict[str, object] = dict(line)
                texts.append(str(line_copy.pop("text")))
                lines.append(line_copy)
            else:
                lines.append(line)
        copy["chat"] = lines
    return copy, texts


class TrafficReport:
    """What the replay of a traffic log found."""

    def __init__(self) -> None:
        self.problems: list[str] = []
        self.unsent_texts: list[str] = []
        self.reaction_frames = 0


def parse_or_none(text: str) -> object:
    """A payload's JSON value, or None when it is not JSON."""
    try:
        return json.loads(text)
    except ValueError:
        return None


def check_traffic(log: TrafficLog, sent_texts: set[str]) -> TrafficReport:
    """Replay the log in order and check every payload as AC-14 says."""
    earned: dict[Cell, set[str]] = {}
    report = TrafficReport()
    for item in log.items():
        if isinstance(item, Earned):
            earned.setdefault((item.row, item.column), set()).add(item.letter)
            continue
        source = item.client if isinstance(item, Received) else item.source
        parsed = parse_or_none(item.text)
        is_reaction = isinstance(parsed, dict) and parsed.get("type") == "reaction"
        if is_reaction:
            report.reaction_frames += 1
            checked = parsed
        else:
            checked, texts = set_chat_texts_aside(parsed)
            for text in texts:
                if text not in sent_texts:
                    report.unsent_texts.append(text)
        for problem in rule_problems(checked, item.text, earned):
            report.problems.append(f"{source} received {problem}: {item.text[:120]}")
    return report


def test_ac14_the_checker_sets_only_chat_texts_aside() -> None:
    chat_line = '{"type": "chat_message", "seq": 4, "player_id": "p2", "text": "IDES"}'
    reaction = (
        '{"type": "reaction", "player_id": "p2", "reaction": "wow",'
        ' "clue": {"row": 0, "column": 3, "clue_index": 0}}'
    )
    leaky = '{"type": "error", "code": "x", "message": "it is IDES"}'
    log = TrafficLog()
    for text in (chat_line, reaction, leaky):
        log.receive("Ana", text)

    report = check_traffic(log, {"IDES"})

    assert report.problems == [f"Ana received the answer 'IDES': {leaky}"]
    assert report.unsent_texts == []
    assert report.reaction_frames == 1


WRONG_LETTERS: list[Step] = [(1, 0, "X"), (2, 2, "X"), (4, 4, "X")]
FIRST_NINE_AND_ERASE: list[Step] = [
    (1, 0, "T"),
    (1, 1, "A"),
    (1, 2, "M"),
    (1, 3, "I"),
    (1, 4, "S"),
    (2, 1, "V"),
    (2, 2, "I"),
    (2, 3, "D"),
    (2, 4, "E"),
    (4, 4, None),
]
BOBS_LETTER: list[Step] = [(0, 1, "N")]
ANAS_LAST_WORDS: list[Step] = [
    (3, 1, "A"),
    (3, 2, "M"),
    (3, 3, "E"),
    (3, 4, "N"),
    (4, 1, "L"),
    (4, 2, "E"),
    (4, 3, "S"),
    (4, 4, "T"),
]
EVENTS_BEFORE_CY = len(WRONG_LETTERS) + len(FIRST_NINE_AND_ERASE)
EVENTS_OF_THE_GAME = EVENTS_BEFORE_CY + len(BOBS_LETTER) + len(ANAS_LAST_WORDS)
CHAT_TEXTS = ["IDES, je crois", "<b>VIDE</b> ?", "oui"]


def send_steps(peer: Peer, log: TrafficLog, steps: list[Step]) -> None:
    """Send the steps in order, noting each letter as earned before it leaves."""
    for row, column, letter in steps:
        if letter is None:
            peer.send(Erase(row=row, column=column))
        else:
            log.earn(row, column, letter)
            peer.send(EditLetter(row=row, column=column, letter=letter))


def letter_event_count(peer: Peer) -> int:
    count = 0
    for message in peer.messages():
        if isinstance(message, LetterChanged):
            count += 1
    return count


def wait_for_letter_events(peer: Peer, count: int) -> None:
    peer.wait_until(
        lambda: letter_event_count(peer) >= count, f"{count} letter_changed events"
    )


def has_grid_solved(peer: Peer) -> bool:
    return any(isinstance(message, GridSolved) for message in peer.messages())


def wait_for_grid_solved(peer: Peer) -> None:
    """The last letter completes the grid: wait for its `grid_solved` (spec 026)."""
    peer.wait_until(lambda: has_grid_solved(peer), f"grid_solved on {peer.name}")


def say(peer: Peer, text: str, sent_texts: set[str]) -> None:
    """Send a chat message and note its text as sent by a client."""
    sent_texts.add(text)
    peer.send(Chat(text=text))


def test_ac14_websocket_chat_and_reactions_pass_the_traffic_checker(
    client: TestClient,
) -> None:
    log = TrafficLog()
    sent_texts: set[str] = set()
    created = client.post("/api/rooms", json={"grid_number": 1})
    assert created.status_code == 201
    log.http_body("POST /api/rooms", created.text)
    code = created.json()["code"]
    for path in ("/api/grids", "/api/grids/1"):
        listed = client.get(path)
        assert listed.status_code == 200
        log.http_body(f"GET {path}", listed.text)

    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, code, ["Ana", "Bob"], log)
        say(bob, CHAT_TEXTS[0], sent_texts)  # before any letter of IDES
        wait_for_chat_count(ana, 1)
        wait_for_chat_count(bob, 1)
        send_steps(ana, log, WRONG_LETTERS)
        send_steps(ana, log, FIRST_NINE_AND_ERASE)
        wait_for_letter_events(ana, EVENTS_BEFORE_CY)
        wait_for_letter_events(bob, EVENTS_BEFORE_CY)
        say(bob, CHAT_TEXTS[1], sent_texts)
        wait_for_chat_count(ana, 2)
        wait_for_chat_count(bob, 2)
        say(ana, CHAT_TEXTS[2], sent_texts)
        wait_for_chat_count(ana, 3)
        wait_for_chat_count(bob, 3)
        bob.send(React(clue=IDES, reaction=Reaction.WOW))
        wait_for_reaction_count(ana, 1)
        wait_for_reaction_count(bob, 1)

        cy = connect(stack, client, code, "Cy", log)
        cy.send(Join(nickname="Cy", resume_token=None))
        cy.wait_for_messages(1, "the snapshot of Cy")
        send_steps(bob, log, BOBS_LETTER)
        wait_for_letter_events(bob, EVENTS_BEFORE_CY + 1)
        send_steps(ana, log, ANAS_LAST_WORDS)
        for peer in (ana, bob, cy):
            wait_for_grid_solved(peer)
        cy_chat = [line.text for line in cy.snapshot().chat]
        ana_chat = [message.text for message in chat_messages_of(ana)]
        errors = [*ana.errors(), *bob.errors(), *cy.errors()]

    report = check_traffic(log, sent_texts)

    assert cy_chat == CHAT_TEXTS
    assert ana_chat == CHAT_TEXTS
    assert errors == []
    assert report.reaction_frames == 2  # Ana's and Bob's; Cy joined after it
    assert report.unsent_texts == []
    assert report.problems == []
