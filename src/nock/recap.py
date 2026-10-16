"""The end-of-game recap of a solved room (spec 028): what each player brought.

The recap is worked out from the room's state and its log by pure functions: no
I/O and no clock. The server answers it over HTTP (`nock.server`). The share page
gets only a `PublicRecap`, which holds no letter, no grid and no room code.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, StrictBool

from nock.grid import ClueCell, Grid, Position
from nock.protocol import (
    CellLocked,
    CellTarget,
    CheckResult,
    Count,
    GridSolved,
    LeaveReason,
    LetterChanged,
    Nickname,
    PlayerId,
    PlayerJoined,
    PlayerLeft,
    RevealResult,
)
from nock.room import LogEntry, RoomState

SHARE_PATH_PREFIX: str = "/recap/"


class RecapModel(BaseModel):
    """Base of the recap models: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RecapPlayer(RecapModel):
    """What one player brought to the solved grid."""

    player_id: PlayerId
    nickname: Nickname | None  # None: an author with no player_joined
    letters: Count  # letters authored in the solved grid
    words: Count  # words whose last missing letter they wrote
    removed: StrictBool  # removed by the host (spec 014)


class Recap(RecapModel):
    """The recap of a solved room, as its players see it."""

    grid_number: int | None  # RoomState.grid_number
    elapsed_ms: Count  # the grid_solved entry's elapsed_ms
    checks: Count
    letter_reveals: Count
    word_reveals: Count
    revealed_letters: Count  # letter cells revealed, credited to nobody
    letter_cells: Count  # 18 on FX-01
    word_count: Count  # clues of the grid, 8 on FX-01
    players: tuple[RecapPlayer, ...]  # join order, then authors with no join
    # SHARE_PATH_PREFIX + share_token, None without a token
    share_path: str | None


class PublicRecap(RecapModel):
    """What the share page shows: the grid number, the time and the team."""

    grid_number: int | None
    elapsed_ms: Count
    team: tuple[Nickname, ...]


class _HelpUsed(NamedTuple):
    """How many checks and reveals a log holds."""

    checks: int
    letter_reveals: int
    word_reveals: int


class _FillChange(NamedTuple):
    """How one log entry changes a cell: filled or emptied, and who did it."""

    position: Position
    is_filled: bool
    player_id: str | None  # None: a reveal, which credits nobody


def build_recap(state: RoomState, log: Sequence[LogEntry]) -> Recap:
    """Return the recap of a solved room, as spec 028's "What the recap counts" says.

    Only the entries of `log` with seq <= state.seq are used.

    Args:
        state: The room, solved.
        log: The room's log from seq 1. Entries after `state.seq` are left out.

    Returns:
        The recap: the time, the checks and reveals used, and what each player
        brought, in join order.

    Raises:
        ValueError: `state.solved` is False, or those entries are not exactly
            seq 1 to state.seq, in order, with one `grid_solved` among them.
    """
    if not state.solved:
        raise ValueError(f"Room {state.code} is not solved, so it has no recap")
    entries = _entries_up_to(log, state.seq)
    _check_numbering(entries, state.seq)
    solved_event = _only_grid_solved(entries)
    help_used = _count_help(entries)
    words = _grid_words(state.grid)
    letters_by_player = _letters_by_player(state)
    words_by_player = _words_by_player(words, entries)
    revealed_cells = [cell for cell in state.cells if cell.revealed]
    share_path = None
    if state.share_token is not None:
        share_path = SHARE_PATH_PREFIX + state.share_token
    return Recap(
        grid_number=state.grid_number,
        elapsed_ms=solved_event.elapsed_ms,
        checks=help_used.checks,
        letter_reveals=help_used.letter_reveals,
        word_reveals=help_used.word_reveals,
        revealed_letters=len(revealed_cells),
        letter_cells=len(state.cells),
        word_count=len(words),
        players=_recap_players(entries, letters_by_player, words_by_player),
        share_path=share_path,
    )


def public_recap(recap: Recap) -> PublicRecap:
    """Return what the share page shows: grid number, time and team.

    Args:
        recap: The recap of a solved room.

    Returns:
        The public recap. Its team is the nickname of every player the host did
        not remove, in the recap's order, each nickname once. A player with no
        nickname (an author with no player_joined) is not in it.
    """
    team: list[str] = []
    for player in recap.players:
        if player.removed or player.nickname is None:
            continue
        if player.nickname not in team:
            team.append(player.nickname)
    return PublicRecap(
        grid_number=recap.grid_number, elapsed_ms=recap.elapsed_ms, team=tuple(team)
    )


def _entries_up_to(log: Sequence[LogEntry], last_seq: int) -> list[LogEntry]:
    """Return the entries of `log` whose seq is at most `last_seq`, in log order."""
    kept: list[LogEntry] = []
    for entry in log:
        if entry.event.seq <= last_seq:
            kept.append(entry)
    return kept


def _check_numbering(entries: list[LogEntry], last_seq: int) -> None:
    """Check that the entries are exactly seq 1 to `last_seq`, in order.

    Raises:
        ValueError: an entry is missing, repeated or out of order.
    """
    if len(entries) != last_seq:
        raise ValueError(
            f"The log holds {len(entries)} entries up to seq {last_seq}, "
            f"expected {last_seq} (seq 1 to {last_seq})"
        )
    for expected_seq, entry in enumerate(entries, start=1):
        if entry.event.seq != expected_seq:
            raise ValueError(
                f"Expected the entry with seq {expected_seq}, "
                f"got seq {entry.event.seq}"
            )


def _only_grid_solved(entries: list[LogEntry]) -> GridSolved:
    """Return the one `grid_solved` event of the entries.

    Raises:
        ValueError: the entries hold no `grid_solved`, or more than one.
    """
    found: list[GridSolved] = []
    for entry in entries:
        if isinstance(entry.event, GridSolved):
            found.append(entry.event)
    if len(found) != 1:
        raise ValueError(f"The log holds {len(found)} grid_solved entries, expected 1")
    return found[0]


def _count_help(entries: list[LogEntry]) -> _HelpUsed:
    """Count the checks, whatever their scope, and the reveals of each scope.

    A check counts once its result is logged (spec 023), also after a vote
    (spec 025); a refused check or a vote that failed logs no result.
    """
    checks = 0
    letter_reveals = 0
    word_reveals = 0
    for entry in entries:
        event = entry.event
        if isinstance(event, CheckResult):
            checks += 1
        elif isinstance(event, RevealResult):
            if isinstance(event.target, CellTarget):
                letter_reveals += 1
            else:
                word_reveals += 1
    return _HelpUsed(checks, letter_reveals, word_reveals)


def _letters_by_player(state: RoomState) -> dict[str, int]:
    """Count the letter cells each player authored in the solved grid.

    The author is spec 019's, kept in the state. A revealed cell is credited to
    nobody (spec 024).
    """
    letters: dict[str, int] = {}
    for cell in state.cells:
        if cell.revealed or cell.author is None:
            continue
        letters[cell.author] = letters.get(cell.author, 0) + 1
    return letters


def _grid_words(grid: Grid) -> list[list[Position]]:
    """Return the cells of each word of the grid: one word per clue, in grid order.

    A clue whose word does not resolve is left out; a grid of the catalogue has
    none (spec 003).
    """
    words: list[list[Position]] = []
    for cell in grid.cells:
        if not isinstance(cell, ClueCell):
            continue
        for clue_index in range(len(cell.clues)):
            try:
                positions = grid.word_cells(cell.row, cell.column, clue_index)
            except (IndexError, ValueError):
                continue
            words.append(positions)
    return words


def _words_by_player(
    words: list[list[Position]], entries: list[LogEntry]
) -> dict[str, int]:
    """Count the words each player completed, as they stand at the end of the log."""
    counts: dict[str, int] = {}
    for completer in _completers(words, entries):
        if completer is None:
            continue
        counts[completer] = counts.get(completer, 0) + 1
    return counts


def _completers(
    words: list[list[Position]], entries: list[LogEntry]
) -> list[str | None]:
    """Return who completed each word at the end of the log, None for nobody.

    The log is walked in seq order from an empty grid. A word gets a completer
    each time an entry turns it from not full to full: the player of a
    `letter_changed`, or nobody for a `cell_locked` (a reveal). An entry that
    empties a cell of a full word takes its completer away. One entry can
    complete two words, the across and the down word of its cell.
    """
    words_of_cell: dict[Position, list[int]] = {}
    for word_index, positions in enumerate(words):
        for position in positions:
            words_of_cell.setdefault(position, []).append(word_index)
    filled: set[Position] = set()
    completers: list[str | None] = [None] * len(words)
    for entry in entries:
        change = _fill_change(entry)
        if change is None:
            continue
        touched = words_of_cell.get(change.position, [])
        full_before: set[int] = set()
        for word_index in touched:
            if _is_full(words[word_index], filled):
                full_before.add(word_index)
        if change.is_filled:
            filled.add(change.position)
        else:
            filled.discard(change.position)
        for word_index in touched:
            is_full_now = _is_full(words[word_index], filled)
            was_full = word_index in full_before
            if is_full_now and not was_full:
                completers[word_index] = change.player_id
            elif was_full and not is_full_now:
                completers[word_index] = None
    return completers


def _fill_change(entry: LogEntry) -> _FillChange | None:
    """Return how an entry changes which cells are filled; None when it does not.

    Only `letter_changed` and `cell_locked` touch the letters. A letter fills
    its cell, pencil or not, and an erase empties it. A `cell_locked` leaves its
    cell filled: a reveal fills it for nobody, and a check locks only cells that
    are already filled.
    """
    event = entry.event
    if isinstance(event, LetterChanged):
        is_filled = event.letter is not None
        return _FillChange((event.row, event.column), is_filled, event.player_id)
    if isinstance(event, CellLocked):
        return _FillChange((event.row, event.column), True, None)
    return None


def _is_full(word: list[Position], filled: set[Position]) -> bool:
    """Tell whether every cell of a word is filled."""
    return all(position in filled for position in word)


def _recap_players(
    entries: list[LogEntry],
    letters_by_player: dict[str, int],
    words_by_player: dict[str, int],
) -> tuple[RecapPlayer, ...]:
    """Return one row per player: those who joined, then credited ids with no join.

    Args:
        entries: The log, seq 1 to the room's seq.
        letters_by_player: The letters each player authored.
        words_by_player: The words each player completed.

    Returns:
        The players who joined, in the order of their first join, with the
        nickname of their last join; then every other id credited with a letter
        or a word (only in a state built by hand), with no nickname.
    """
    nicknames = _nicknames_in_join_order(entries)
    removed = _removed_players(entries)
    player_ids = list(nicknames)
    for credited_id in [*letters_by_player, *words_by_player]:
        if credited_id not in player_ids:
            player_ids.append(credited_id)
    players: list[RecapPlayer] = []
    for player_id in player_ids:
        player = RecapPlayer(
            player_id=player_id,
            nickname=nicknames.get(player_id),
            letters=letters_by_player.get(player_id, 0),
            words=words_by_player.get(player_id, 0),
            removed=player_id in removed,
        )
        players.append(player)
    return tuple(players)


def _nicknames_in_join_order(entries: list[LogEntry]) -> dict[str, str]:
    """Return the nickname of each player who joined, by id, in first-join order.

    A player id that joined several times (seated back after a time-out, spec
    032) keeps the place of its first join and gets the nickname of its last
    one: giving a new value to a key a dict already holds keeps its place.
    """
    nicknames: dict[str, str] = {}
    for entry in entries:
        event = entry.event
        if isinstance(event, PlayerJoined):
            nicknames[event.player.player_id] = event.player.nickname
    return nicknames


def _removed_players(entries: list[LogEntry]) -> set[str]:
    """Return the ids of the players the host removed (spec 014)."""
    removed: set[str] = set()
    for entry in entries:
        event = entry.event
        if isinstance(event, PlayerLeft) and event.reason == LeaveReason.REMOVED:
            removed.add(event.player_id)
    return removed
