---
id: "034"
title: Catching up after an absence
status: done
---

# 034 - Catching up after an absence

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

(Note from the lead, 2026-10-15: folded in. The answer is decision 7, and "Open
questions" is empty. Spec 013 is refined after this spec is built.)

(Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells
(`_design.md` section 6): the ring is a 3 px `--nock-ink` border on the cell's
inner edge (`inset: 0`, layer 1), under the other players' corner triangles, the
revealed notch and the arrows, and the initials it was tested against are gone.
"Applying a catch-up" step 2 and AC-2 change, so the test-writer updates the test
of AC-2 before the implementer runs. The catch-up lines go into the Salon's stream
in step 3.)

(Note from the lead, 2026-10-22: refined by spec 043, the design's room layout
(`_design.md` section 8): the catch-up lines are items of the Salon's stream, in
seq order among the messages and the other event lines, with the event look of
spec 043 (`check` with ✓, `reveal` in orange-red with ▲, `word_completed` with no
pictogram); they count as new events for the « Salon » dot and make no 3-second
note. The `word_completed` lines stay, as this spec has them, although the design
drops a live « a rempli » line (spec 043's Open question 11), and no live
`word_completed` line is added. No criterion of this spec changes; a test that
measures the feed list shows the Discussion tab first (spec 043's "Test
harness").)

(Note from the lead, 2026-10-17: checked, before this spec's tests are written,
against the code now built and against the specs refined since this spec was
approved: 032 (seat back), 027 (shared timer), 038, and the nickname rule of
2026-10-16 (specs 039, 040 and 012). Changed, each with a dated note: the
nicknames that the server sends are written in capitals (`BOB`, `CY`), and a page
shows them through spec 040's `displayNickname`; a return covers every snapshot
after the first of a page load; the catch-up mark is also drawn under spec 019's
`author-mark` and spec 024's `reveal-mark`; the locked look is spec 035's; decision
4 no longer counts on rooms logged before this spec. Simplified under the human's
rule of 2026-10-16: `load_room_at` has one rule and no range cases,
`RoomRegistry.catch_up` no longer clips the request's seqs, and `build_catch_up`
takes each nickname from the replay it already makes, so it loses its argument
`current` and its four places to look. The criteria now name the models,
attributes and values that the tests check. This spec has no tests yet
(preparation of spec 034).)

Epic E9 Accounts and resume (US-9.3) · Release: V1 · Epic depends on: E3
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine and its
harness are defined in spec 011; the stored identity and the room page flow in spec
012; the activity feed, its lines and its scroll rules in spec 013; reconnection in
spec 017; the store, `replay` and the log in spec 018; filled cells in spec 026;
members, `past_players`, `member_id` and the room record's other fields in specs
032 and 010; checks in spec 023 and reveals in spec 024. The messages are those of
spec 039. This spec is built after specs 032 and 038. (Note from the lead,
2026-10-17: `peek_room` became `member_id`, the one lookup of spec 032 that this
spec's hub now uses (preparation of spec 034).)

## Goal

As a player who plays at different hours from my friends, I want to see what changed, so that I pick up where the team is.

The MVP ships with guests only: a guest can do everything needed to finish a grid. Accounts arrive in V1 and only add memory across devices.

## Public interface

### Terms

- **Seen seq**: for one room on one device, the `seq` the room page last held (spec
  040's `data-seq`). The page keeps it in memory, and in the room record
  `nock.room.<CODE>` (spec 010) as the field `seen_seq`.
- **Return**: a snapshot whose `seq` is greater than the seen seq the page had when
  the snapshot arrived. That seen seq is the stored `seen_seq` for the first
  snapshot of a page load, and the one in memory for every later snapshot (after a
  reconnection, spec 017). The first snapshot of a page load with no stored
  `seen_seq` (a first visit on this device) is no return; neither is a snapshot
  whose `seq` is not greater. (Note from the lead, 2026-10-17: "for every later
  snapshot" read "for a snapshot after a reconnection", which named no seen seq for
  a second snapshot on the same socket, which spec 040 applies; and "has no return"
  now says that only the first snapshot is concerned, as "Seen seq writes" in "Edge
  cases and errors" already says (preparation of spec 034).)
- **Absence**: the room's events with `seen seq < seq <= snapshot seq`.
- **Changed cell**: a letter cell named by a `letter_changed` or a `cell_locked` of
  the absence (a letter written, erased, confirmed or undone, or a lock by a check
  or a reveal), whatever the player.
- **Complete word**: a word whose cells are all filled (spec 026: a cell holding a
  letter, pencil or not). A `letter_changed` with a letter, on a cell that was empty
  just before it, completes each word through that cell that is complete just after
  it, and is credited to the event's `player_id`. A reveal that fills a cell completes
  no word here: its reveal line says it.
- **Catch-up line**: one per `check_result` and per `reveal_result` of the absence,
  and one per word completed by a `letter_changed` of the absence.

(Note from the lead, 2026-10-14: AC-4, which was AC-2, said that the feed lists these
lines "newest first". Spec 013 lists the feed oldest first with the newest line at the
bottom, and its AC-7 keeps a reader's place in that list. Resolved here, consistently
with spec 013: the catch-up lines go into spec 013's feed, in `seq` order, oldest
first and the newest at the bottom, and the list follows spec 013's scroll rules. A
list that nobody scrolled rests at its end, so the newest line of the absence is the
one in view first, which is what "newest first" asks the player to see; reading up
the list goes back in time. A second, newest-first list was rejected: one feed in two
orders would confuse.)

### `nock.store`

```python
# src/nock/store.py (addition)
class RoomStore:
    def load_room_at(self, code: str, seq: int) -> RoomState | None:
        """Return the room's state just after its event `seq`.

        The snapshot with the highest seq at most `seq`, then `replay` of the
        logged entries after it whose seq is at most `seq`. So a `seq` at or above
        the room's last logged seq gives the room's latest stored state, as
        `load_room` does.

        Returns:
            The state, or None when no snapshot of the room has a seq at most
            `seq`: an unknown room, or a room whose first snapshot came after
            `seq` (only a room added in a later state, as `add_room` allows).
        """
```

(Note from the lead, 2026-10-17: the docstring said that a `seq` lower than the
room's first snapshot gives that first snapshot, and that a `seq` higher than the
room's last logged seq gives None. Both cases are gone: one query and one replay,
with no range check. A room made by `register_room` has a snapshot at seq 0, so
only a room seeded in a test can lack one (simplification, human's rule of
2026-10-16).)

### `nock.catch_up` (new, pure: no I/O)

```python
# src/nock/catch_up.py
from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from nock.protocol import (
    CellRef, CheckResult, ClueRef, Nickname, PlayerId, ResumeToken, RevealResult,
    Seq, SnapshotSeq,
)
from nock.room import LogEntry, RoomState

CATCH_UP_LINE_LIMIT: int = 100  # spec 013's feed keeps 100 lines


class CatchUpModel(BaseModel):
    """Base of the catch-up models: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class WordCompleted(CatchUpModel):
    """A word completed during the absence."""

    type: Literal["word_completed"] = "word_completed"
    seq: Seq  # the letter_changed that completed it
    player_id: PlayerId  # that letter_changed's player
    clue: ClueRef  # the word, named by its clue


CatchUpLine = Annotated[
    CheckResult | RevealResult | WordCompleted, Field(discriminator="type")
]


class PlayerName(CatchUpModel):
    player_id: PlayerId
    nickname: Nickname


class CatchUpRequest(CatchUpModel):
    """The body of POST /api/rooms/{code}/catch-up."""

    resume_token: ResumeToken  # the page's own token (snapshot.resume_token)
    after_seq: SnapshotSeq  # the page's seen seq
    until_seq: SnapshotSeq  # the seq of the snapshot of the return


class CatchUp(CatchUpModel):
    """What changed during one absence. It holds no letter of the grid."""

    after_seq: SnapshotSeq  # as in the request
    until_seq: SnapshotSeq  # as in the request
    cells: tuple[CellRef, ...]  # the changed cells, each once, in row-major order
    lines: tuple[CatchUpLine, ...]  # in seq order, at most CATCH_UP_LINE_LIMIT
    names: tuple[PlayerName, ...]  # the nickname of each player_id of `lines`


def build_catch_up(
    after_seq: int,
    until_seq: int,
    before: RoomState,
    entries: Sequence[LogEntry],
) -> CatchUp:
    """Return the catch-up of the absence that `entries` hold.

    Args:
        after_seq: The request's `after_seq`, copied to the answer.
        until_seq: The request's `until_seq`, copied to the answer.
        before: The room just before the first entry (`load_room_at`).
        entries: The logged entries of the absence, in seq order, the first one
            right after `before`.

    Returns:
        `cells`: the changed cells. `lines`: the `CheckResult` and `RevealResult`
        events of `entries` as they are (`entry.event`), and a `WordCompleted`
        for each word completed by a `letter_changed` of `entries` (found by
        replaying `entries` from `before`), in seq order; words completed by one
        letter come in clue order (`row`, `column`, `clue_index`); when there
        are more than CATCH_UP_LINE_LIMIT lines, only the last
        CATCH_UP_LINE_LIMIT are kept. `names`: for each distinct `player_id` of
        `lines`, in order of first appearance, the nickname of that player in
        `players` of the replayed state just before the event of their first
        line, that is, the nickname they had when they made it; a player id
        that is not in `players` then is left out.
    """
```

(Note from the lead, 2026-10-17: `build_catch_up` had a fifth argument,
`current: RoomState`, "the room as it is now (`peek_room`), for the names", and
looked for each nickname in `current.players`, else `current.past_players`, else a
`player_joined` of `entries`, else `before.players`. The replay that finds the
completed words already holds each line's player when they make the line, so the
nickname comes from there, with no search over past, removed or seated-back
players. The name is the one the player had then, as spec 013's live feed showed
it ("The nickname is the one known when the event is applied"); spec 033's erasure
rewrites the stored snapshots and `player_joined` entries, so the replay gives an
erased player `--` (simplification, human's rule of 2026-10-16).)

### `nock.hub`

```python
# src/nock/hub.py (addition)
class RoomRegistry:
    def catch_up(self, code: str, request: CatchUpRequest) -> CatchUp | None:
        """Return the catch-up that a member asks for, or None.

        None when `member_id(code, request.resume_token)` is None (the room is
        unknown or expired, or the token is not a member's, spec 032), or when
        `before = store.load_room_at(code, request.after_seq)` is None.
        Otherwise `build_catch_up(request.after_seq, request.until_seq, before,
        entries)`, with `entries` the entries of
        `store.read_log(code, before.seq)` whose seq is at most
        `request.until_seq`. It only reads: the room is not made live and
        nothing is logged.
        """
```

Every event up to a snapshot's `seq` is in the log when the page asks, since the
hub commits each step before it sends anything (spec 018 AC-4). No range needs a
rule of its own: an `until_seq` above the room's seq reads up to the room's last
event, and an `after_seq` at or above `until_seq`, or above the room's seq, finds
no entry, so the answer holds the request's two seqs and no cell, line or name.
(Note from the lead, 2026-10-17: the docstring clipped `until_seq` to the room's
seq (`u = min(request.until_seq, <room's seq>)`), answered an `after_seq` at or
above `u` by a rule of its own, and passed `peek_room(code)` to `build_catch_up`
for the names. The filter on `request.until_seq` gives the same answers without
the clip or the rule, and the names come from the replay (simplification, human's
rule of 2026-10-16).)

### `nock.server`

| Method and path | Answer |
| --- | --- |
| `POST /api/rooms/{code}/catch-up`, a valid `CatchUpRequest`, and `rooms.catch_up` gives a catch-up | 200, `CatchUp` JSON (`model_dump(mode="json")`) |
| the same, when `rooms.catch_up` gives None, or `code` breaks `ROOM_CODE_PATTERN` | 404, `{"detail": "Not Found"}` |
| a body that is not a valid `CatchUpRequest` | 422, FastAPI's validation body |

The answer never says why it is 404 (unknown room, expired room or no member's
token), so it is no oracle for room codes (spec 011's throttle does not count it).
A `CatchUp` JSON, for example:
`{"after_seq": 5, "until_seq": 9, "cells": [{"row": 2, "column": 1}], "lines": [{"type": "word_completed", "seq": 8, "player_id": "p2", "clue": {"row": 2, "column": 0, "clue_index": 0}}], "names": [{"player_id": "p2", "nickname": "BOB"}]}`. (Note from the lead,
2026-10-17: the nickname read `"Bob"`; the server sends nicknames in capitals,
spec 039's "Nicknames in capitals" (preparation of spec 034).)

### Client

Room record (spec 010): `nock.room.<CODE>` gains the field `seen_seq`, an integer.
Each time the page's `seq` changes (a snapshot, or an applied event), the page writes
it there, keeping the record's other fields, and creating the record with
`"grid": null, "selection": null` when there is none (as spec 010 does for the
selection). A stored `seen_seq` that is not a whole number of 0 or more is read as
absent.

On a return, once the snapshot is applied (spec 040), the page sends
`POST /api/rooms/<code>/catch-up` with
`{"resume_token": <snapshot.resume_token>, "after_seq": <seen seq>, "until_seq": <snapshot.seq>}`,
once. Its answer is applied only while the page's latest snapshot is still that one;
otherwise it is dropped. A failed request (network error, any status other than 200,
a body that is not a catch-up) shows no catch-up and is not retried; the page works
as before.

Applying a catch-up:

1. Names: each `names` item whose `player_id` the page does not know yet is added to
   the names the feed uses (spec 013: known players include those who left).
2. Highlight (AC-2): every letter `cell` has `data-caught-up`, `"false"` from its
   first render; each cell of `cells` gets `"true"` for
   `CATCH_UP_HIGHLIGHT_MS = 5000` milliseconds, then `"false"` again. While
   highlighted, the cell holds one child `data-testid="catch-up-mark"`, with
   `aria-hidden="true"` and a computed `pointer-events` of `none`, drawn as a solid
   ring on the cell's edge: its bounding box equals the cell's (1 px tolerance); its
   computed `border-style` is `solid` and its `border-width` at least 3 px on each
   of the four sides; its border colour has a contrast of at least 3:1 with the
   cell's computed `background-color` (that background, when it has alpha, is first
   composited over white; the border colour, when it has alpha, is first composited
   over that background, not over white, which is what the eye sees). (Note from the
   lead, 2026-10-21, first review of spec 034: the parenthesis read "a colour with
   alpha is first composited over white", which also put a translucent ring over
   white, not over the cell's background that lies behind it on screen. Spec 035's
   contrast scan composites a text colour over its background the same way. Both
   readings give the same ratio for an opaque ring.) The ring is the highlight's
   non-colour sign (spec 035): a shape, unlike
   spec 016's flash. It is drawn under every other mark of the cell, which stay
   visible: spec 013's `remote-selection` outlines, spec 019's `author-mark`, spec
   024's `reveal-mark`, and spec 035's `remote-initials` and `remote-overflow`
   labels (the `+k` of a crowded cell); it never covers the cell's letter. (Note
   from the lead, 2026-10-22: refined by spec 042, the design's grid cells: the
   ring is `--nock-ink`, `inset: 0`, `z-index: 1`; the marks over it are the
   `remote-selection` triangles or icons, `author-mark`, `reveal-mark` and the
   arrows (`clue-arrow`), the labels being gone.) A cell
   highlighted again by a later catch-up starts its 5,000 ms again. (Note from the
   lead, 2026-10-17: "every other `cell` has `"false"`" became the first clause,
   which gives the attribute to the letter cells, the only cells that `cells` can
   name. The marks drawn over the ring read "spec 013's `remote-selection` outlines
   and spec 035's initials and `+k` labels"; they gained `author-mark`, which spec
   019 lets nothing but the corner labels cover, and `reveal-mark`, and the labels
   are named by their test ids (preparation of spec 034).)
3. Lines (AC-4): each line becomes an item of spec 013's feed (`feed-item`,
   `data-seq` = the line's `seq`):

   | Line | `data-kind` | Text |
   | --- | --- | --- |
   | `check_result` | `check` | spec 013's `feed.check.<scope>` text |
   | `reveal_result` | `reveal` | spec 013's `feed.reveal.<scope>` text |
   | `word_completed` | `word_completed` | `t("feed.word_completed", {name, clue})`, `clue` the text of that clue in the snapshot's grid |

   `name` is the nickname the page knows for the line's `player_id`, written by
   spec 040's `displayNickname` (`BOB` shows as `Bob`), else `t("feed.someone")`
   (note from the lead, 2026-10-17: "written by spec 040's `displayNickname`" was
   added for the nickname rule of 2026-10-16 (preparation of spec 034)). The items
   go into the feed in `seq` order among the items it
   already holds (oldest first, the newest at the bottom), so they come after the
   lines of seq at most the seen seq and before the live lines that arrived since the
   snapshot. Then the feed keeps its newest 100 items (spec 013). Items are no longer
   unique by `data-seq`: one letter that completes two words gives two lines with the
   same `data-seq`, in clue order.
4. Scroll: spec 013's rules ("Client: feed scroll position") apply to the catch-up
   items as to any new line. A list at its end before they go in is at its end within
   300 ms after they show, so the newest line is in view. A list that was not at its
   end keeps every item in view in its place (the `top` of its box moves by at most
   1 px), also when the items go in above it.
5. `room-page` gains `data-catch-up`: `""` until a catch-up is applied, then
   `"<after_seq>-<until_seq>"` of the last one applied (for example `"5-9"`).

Live events add no `word_completed` line until spec 013 is refined, after this spec
is built (decision 7). Once it is, a live `letter_changed` adds exactly the lines
that `build_catch_up` gives for it: same rule ("Complete word"), `data-kind`, text,
`data-seq` and clue order. The catch-up covers only the events that this page never
applied (`seen seq < seq <= snapshot seq`), and live lines only the events applied
after the snapshot, so no line shows twice, and a player who stayed and one who
comes back see the same check, reveal and word lines for the time of the absence.
(Note from the lead, 2026-10-15: this paragraph replaced "Live events add no
`word_completed` line (only the catch-up does; open question 1)".)

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `feed.word_completed` | `{name} a complété « {clue} »` |

### Test harness

- Python (AC-1, AC-3): a FX-01 room `ABC123` created at `t` in a store file
  (`RoomStore(tmp_path / "nock.sqlite3")`, then
  `create_room(new_room("ABC123", fx01_grid, t))`, whose snapshot has seq 0),
  driven with `join_room`, `handle_message`, `disconnect_player` and `tick` at
  chosen times, each step's entries appended to the store, as spec 018's harness
  does. `TA` and `TB` stand for two resume tokens that match `ResumeToken` (16 to
  128 characters of `A-Z`, `a-z`, `0-9`, `_` and `-`), so that a request holding
  one is valid. (Note from the lead, 2026-10-17: the room's code, its creation in
  the store and what `TA` and `TB` stand for were added (preparation of spec 034).)
  The reference absence "ABSENCE" below: `Ana` (`p1`, token `TA`) and `Bob` (`p2`, token
  `TB`) join (seq 1, 2); Ana writes `T` at (1, 0) (seq 3); Ana's socket closes (seq
  4); Bob writes `V`, `I`, `D`, `E` from (2, 1) across (seq 5 to 8; `E` completes
  `VIDE`, clue (2, 0, 0)); Bob checks that word (`check_result` seq 9, then four
  `cell_locked` seq 10 to 13); Bob reveals the letter (1, 1) (`reveal_result` seq 14,
  `cell_locked` seq 15); Bob writes `A` at (3, 1) (seq 16), `L` at (4, 1) (seq 17)
  and `N` at (0, 1) (seq 18, which completes `NAVAL`, clue (0, 0, 1)); Bob's socket
  closes (seq 19); every step so far runs at one time `t`, and `tick` at `t + 301`
  times out Ana (`player_left` seq 20), hands the host role to Bob (`host_changed`
  seq 21, spec 014) and times out Bob (`player_left` seq 22); both become past
  players. The absence is `after_seq=3`, `until_seq=22`.
- Registry and HTTP (AC-1, AC-3): `RoomRegistry(clock=<a fake clock at t + 301>,
  store=RoomStore(<the same file>))`, so that the room, last edited at `t`, is far
  from its expiry (spec 032); HTTP criteria use
  `TestClient(create_app(rooms=registry, dist_dir=tmp_path))` on that registry.
  (Note from the lead, 2026-10-17: the clock's time was added, and the registry now
  serves the Python calls of `RoomRegistry.catch_up` too; the item read "HTTP:
  `TestClient(create_app(rooms=registry, dist_dir=tmp_path))` on a registry with a
  fake clock over the same store file" (preparation of spec 034).)
- Browser with mocked socket and mocked catch-up (AC-2, AC-4, AC-5): spec 040's
  mocked socket on `/r/ABC123`, plus
  `page.route("**/api/rooms/ABC123/catch-up", handler)`, which records each request
  body and answers with `CatchUp(...).model_dump_json()` (or a status, or later, as
  the case says). `nock.identity.ABC123` (`p1`, `r7Kq2mXo9vB4tY1zW8nP`, `ANA`) and
  `nock.room.ABC123` are seeded with `context.add_init_script` before `page.goto`;
  the record is `{"grid": null, "selection": null}`, plus the case's `seen_seq`
  when it names one, unless the case gives another record. Snapshots are FX-01,
  with `you` `p1`, `resume_token` `r7Kq2mXo9vB4tY1zW8nP`, and players `p1` (`ANA`,
  colour 0, host) and `p2` (`BOB`, colour 1), in capitals as the server sends them,
  which the page shows as `Ana` and `Bob`. (Note from the lead, 2026-10-17: the
  snapshots' `resume_token`, which AC-5's request body holds, the players' colours
  and host, the record as seeded and the nicknames in capitals were added; the
  harness read "(with or without `seen_seq`)" and "players `p1` (`you`, `Ana`) and
  `p2` (`Bob`)" (preparation of spec 034).)
- Browser with live server (AC-2, AC-4): two contexts, Ana and Bob, on a FX-01 room
  registered on the live server; Ana's page is closed (its context, and so its
  storage, stays) while Bob plays, then Ana opens the room again in a new page of
  her context.
- Highlight timing (AC-2): measured with Playwright's waiting assertions from the
  moment `room-page` gets its `data-catch-up` value. The check that the marks are
  still there 4,500 ms after it measures a time window, and AC-4's scroll checks are
  of the kind that spec 013's serial file makes, so these tests go in test files of
  their own, which the lead adds to `SERIAL_TEST_FILES` (`scripts/gate_browsers.py`,
  tooling). (Note from the lead,
  2026-10-17: added, from the project's rule on timing-sensitive test files
  (preparation of spec 034).)
- Feed scroll measures (AC-4): spec 013's "Feed scroll states" (at its end, settled,
  items in view), at 1280 by 720.
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check of
  this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-9.3.1) (Python; HTTP) The server names the cells that changed during my absence. Python: for ABSENCE, `store.load_room_at("ABC123", 3)` has `seq` 3, the `cells` of the live state after seq 3, and its players' ids and nicknames; `load_room_at("ABC123", 99)` equals `store.load_room("ABC123")`, whose `seq` is 22, and `load_room_at("ZZZZZZ", 3)` is None. (Note from the lead, 2026-10-17: "and `load_room_at(code, 99)` is None" became the two checks before this note, since a `seq` beyond the log now reads the whole log ("`nock.store`") (simplification, human's rule of 2026-10-16).) `RoomRegistry.catch_up("ABC123", CatchUpRequest(resume_token=TA, after_seq=3, until_seq=22))` gives `cells` (0, 1), (1, 1), (2, 1), (2, 2), (2, 3), (2, 4), (3, 1), (4, 1) as `CellRef` values, in that order, which leaves out (1, 0), changed at seq 3; with `after_seq=15` it gives (0, 1), (3, 1), (4, 1); with `after_seq=22` or `after_seq=25` no cell, no line and no name; with `until_seq=99` the same cells, lines and names as with 22, and `until_seq` 99. HTTP: `POST /api/rooms/ABC123/catch-up` with `{"resume_token": TA, "after_seq": 3, "until_seq": 22}` answers 200 with JSON equal to `model_dump(mode="json")` of that catch-up, whose `after_seq` is 3 and `until_seq` 22; with `TB` the same (a past player is a member); with a token no player ever had (one that matches `ResumeToken`, for example 24 times `Z`), or the code `ZZZZZZ`, 404 with `{"detail": "Not Found"}`; with `after_seq` -1, a missing `until_seq`, or an extra key, 422. The request leaves the room's log unchanged, and the body holds none of the eight FX-01 answers and no key `answer` (spec 037). (Note from the lead, 2026-10-17: the room's code, the `CatchUpRequest`, `CellRef`, "the same cells, lines and names" and the kind of token that no player ever had were named (preparation of spec 034).)
- **AC-2** (AC-9.3.1) (browser with mocked socket and catch-up; browser with live server) On my return, the cells changed since my last visit are highlighted for 5 seconds. Mocked: with `seen_seq` 5 stored, when the mock answers the join with a snapshot at `seq` 9 where `p2`'s selection is `Selection(row=2, column=2, direction="across")`, and the route answers `CatchUp(after_seq=5, until_seq=9, cells=(CellRef(row=1, column=0), CellRef(row=2, column=2)), lines=(), names=())`: `room-page` gets `data-catch-up="5-9"`; (1, 0) and (2, 2) have `data-caught-up="true"` and one `catch-up-mark` each, which meets "Applying a catch-up" step 2 (box, solid border of 3 px or more on each side, 3:1 against the cell's background, `aria-hidden="true"`, computed `pointer-events` `none`), the border colour, when it has alpha, being composited over the cell's background and not over white before the contrast is measured (note from the lead, 2026-10-21, first review of spec 034: as step 2 now says); every other letter cell has `data-caught-up="false"` and no mark; on (2, 2), `p2`'s `remote-selection` stays visible; a click on (2, 2) gives it `data-selected="true"` (spec 007); then, once the checks above are made (the style below changes what they read) and after `scrollIntoView` of (2, 2), a test style sets `pointer-events: auto !important` on every descendant of every `cell`, since hit testing follows the drawing order but skips elements with `pointer-events: none`, and `document.elementFromPoint` at the point 1.5 px inside both edges of the inner box's corner that holds `p2`'s triangle (inside the ring's band and the triangle) gives that `remote-selection` or one of its descendants, never the `catch-up-mark`. (Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells; this read "`p2`'s `remote-selection` and its `remote-initials` stay visible" and tested "at the centre of `p2`'s `remote-initials`", which no longer exist.) (Note from the lead, 2026-10-21, first review of spec 034: the hit test read "`document.elementFromPoint` at the centre of the initials gives the initials", which could not fail, since the ring has a computed `pointer-events` of `none` and hit testing never returns it. The method is now that of spec 019 AC-1. The check also moved after the click, since its style changes the computed `pointer-events` that the checks above read.) 4,500 ms after `data-catch-up` appears the two marks are still there; 6,000 ms after it, both cells have `data-caught-up="false"` and no mark is left. Live: Ana and Bob join; Ana types `T` at (1, 0), and once her (1, 0) has `data-letter="T"` and `data-unconfirmed="false"` (her `letter_changed` is applied, so her stored `seen_seq` holds its seq), her page is closed; Bob types `V`, `I`, `D`, `E` from (2, 1) across; Ana opens the room again: her page reaches `data-status="joined"`, (2, 1), (2, 2), (2, 3) and (2, 4) have `data-caught-up="true"` with a `catch-up-mark`, and (1, 0) has `data-caught-up="false"`. (Note from the lead, 2026-10-17: the cells read `((1, 0), (2, 2))`, which do not build `CellRef` values, and the selection read "(2, 2) `across`". The `Selection` and `CellRef` models, `pointer-events`, "letter cell", `data-selected` and the wait before Ana's page is closed were added (preparation of spec 034).)
- **AC-3** (AC-9.3.2) (Python; HTTP) The server lists the words completed, the checks and the reveals of my absence, with the names of their players. Python: for ABSENCE with `TA`, `after_seq=3` and `until_seq=22`, `lines` is exactly `WordCompleted(seq=8, player_id="p2", clue=ClueRef(row=2, column=0, clue_index=0))`, the `CheckResult` of seq 9 as logged (its entry's `event`), the `RevealResult` of seq 14 as logged, then `WordCompleted(seq=18, player_id="p2", clue=ClueRef(row=0, column=0, clue_index=1))`, and `names` is `(PlayerName(player_id="p2", nickname="BOB"),)`, although Bob has left the room. On a FX-01 room where the cells of `VIDE` other than (2, 4) and those of `SENT` other than (2, 4) are filled, one letter at (2, 4) gives two `WordCompleted` with the same `seq`, in clue order: `SENT`'s clue (0, 4, 0) then `VIDE`'s (2, 0, 0). A letter written over another letter, a pencil letter confirmed (spec 020), an erase, and a reveal that fills a word's last empty cell add no `WordCompleted`; a pencil letter that fills a word's last empty cell adds one. With 150 `check_result` events in the absence, `lines` holds the last 100, by seq. HTTP: the 200 answer of AC-1 holds these lines and names. (Note from the lead, 2026-10-17: the nickname read `"Bob"`; the server stores nicknames in capitals, spec 039's "Nicknames in capitals". "(its entry's `event`)" was added (preparation of spec 034).)
- **AC-4** (AC-9.3.2) (browser with mocked socket and catch-up; browser with live server) The activity feed lists the lines of my absence oldest first, with the newest at the bottom and in view (spec 013). Mocked: with `seen_seq` 5 stored and a snapshot at `seq` 9 whose players are `p1` and `p2`, when the route answers `CatchUp(after_seq=5, until_seq=9, cells=(), lines=(WordCompleted(seq=7, player_id="p2", clue=ClueRef(row=2, column=0, clue_index=0)), CheckResult(seq=8, player_id="p2", target=WordTarget(row=2, column=0, clue_index=0), correct=(), wrong=()), RevealResult(seq=9, player_id="p3", target=CellTarget(row=1, column=1), reveal_budget=RevealBudget(letters=4, words=1))), names=(PlayerName(player_id="p3", nickname="CY"),))`: `activity-feed` holds three `feed-item` elements with `data-seq` 7, 8, 9 in that order, `data-kind` `word_completed`, `check`, `reveal`, and the texts `Bob a complété « Sans contenu »`, `Bob a vérifié un mot` and `Cy a révélé une lettre`, built from `fr.json`; the feed list is at its end (spec 013) and the item of seq 9 is in view. Then a live `check_result` with `seq` 10, the line event of spec 013's "Feed scroll states" (by `p2`, scope grid, empty lists), adds its line, `Bob a vérifié la grille`, after them. Live lines first: when the route holds its answer until the mock has sent 16 such line events (`seq` 10 to 25) and the list is at its end, then answers, the items read `data-seq` 7, 8, 9, then 10 to 25, and within 300 ms of `data-catch-up="5-9"` the list is at its end. Lines already held: the catch-up lines go after the lines the page already held (those of seq at most the seen seq) and before the live lines. With no `seen_seq` stored and a first snapshot at `seq` 5 (a first visit: no request), the mock sends a live `check_result` with `seq` 6 (the line event of spec 013's "Feed scroll states": by `p2`, scope grid, empty lists), then closes the socket with 1011 and answers the new join with a snapshot at `seq` 12, and the route answers `CatchUp(after_seq=6, until_seq=12, cells=(), lines=(WordCompleted(seq=10, player_id="p2", clue=ClueRef(row=2, column=0, clue_index=0)),), names=())`: once `room-page` has `data-catch-up="6-12"`, `activity-feed` holds two `feed-item` elements, `data-seq` 6 then 10, `data-kind` `check` then `word_completed`, and the texts `Bob a vérifié la grille` then `Bob a complété « Sans contenu »`. (Note from the lead, 2026-10-21, first review of spec 034: step 3 gives the order against the lines the page already held, but no case tested it; this one holds a live line at seq 6 through a reconnection, and a catch-up line at seq 10 that must come after it.) Reader scrolled up: in the setup of "Live lines first" with the list's `scrollTop` set to the middle of its range (spec 013's harness) and settled before the answer, every item in view keeps the `top` of its box within 1 px, 300 ms after `data-catch-up="5-9"`, once the three lines have gone in above. (Note from the lead, 2026-10-21, second review of spec 034: "in the same setup" read as the setup of "Lines already held", which the first review inserted just before this case; it is the setup of "Live lines first", whose 16 live lines give the list a range to scroll in. Wording only.) Live: in the play of AC-2, Bob also checks the word `VIDE` before Ana comes back; Ana's feed then ends with `Bob a complété « Sans contenu »` then `Bob a vérifié un mot`, the last one in view. (Note from the lead, 2026-10-17: the route's answer is written as the models it is built from; it read "the lines `WordCompleted` (seq 7, `p2`, clue (2, 0, 0)), `CheckResult` (seq 8, `p2`, scope word (2, 0, 0)) and `RevealResult` (seq 9, `p3`, scope letter (1, 1)) and the names `p3` = `Cy`". The nickname is `CY`, as the server sends it, which spec 040's `displayNickname` shows as `Cy`. The live `check_result` and the moment of each scroll check were named (preparation of spec 034).)
- **AC-5** (new) (browser with mocked socket and catch-up) The page remembers what it saw, and asks for a catch-up only on a return. After the first snapshot of a page whose room record holds `{"grid": 1, "selection": null}` and no `seen_seq`, at `seq` 5: the page sends no catch-up request within 1 second, `data-catch-up` is `""`, and `nock.room.ABC123` parses to `{"grid": 1, "selection": null, "seen_seq": 5}`; after `letter_changed` events of `p2` with `seq` 6 and 7 it holds `"seen_seq": 7`. Reconnection: the mock then closes the socket with 1011 and answers the new join with a snapshot at `seq` 12; the page sends one request whose body parses to `CatchUpRequest(resume_token="r7Kq2mXo9vB4tY1zW8nP", after_seq=7, until_seq=12)`. With `seen_seq` 9 stored and a snapshot at `seq` 9, or at `seq` 4, no request is sent within 1 second and `data-catch-up` stays `""`. With `seen_seq` 5 stored and a snapshot at `seq` 9: when the route answers 500, or aborts, no cell gets `data-caught-up="true"`, `activity-feed` holds no `feed-item`, `data-catch-up` stays `""`, no second request is sent within 2 seconds, and typing `T` on (1, 0) still sends an `edit_letter`. Dropped answer: in the same setup, the route holds the request; the mock closes the socket with 1011 and answers the new join with a snapshot at `seq` 15, and the page sends a second request, with `after_seq=9` and `until_seq=15`. The route then answers the first request with `CatchUp(after_seq=5, until_seq=9, cells=(CellRef(row=1, column=0),), lines=(), names=())`; 500 ms later, `data-catch-up` is still `""` and (1, 0) has `data-caught-up="false"`. It then answers the second request with `CatchUp(after_seq=9, until_seq=15, cells=(CellRef(row=2, column=2),), lines=(), names=())`, and `data-catch-up` becomes `"9-15"` with (2, 2) at `data-caught-up="true"`. (Note from the lead, 2026-10-17: the events of `seq` 6 and 7, the wait of 1 second, the empty feed and `data-catch-up` after a failure were named. The last case read "when the mock sends a second snapshot at `seq` 15 before the route answers the first request, that answer is dropped (no highlight from it) and the page sends a second request with `after_seq=9` and `until_seq=15`"; it now names the reconnection that brings that snapshot and the two answers that show the drop (preparation of spec 034).)

## Edge cases and errors

- First visit (AC-5): no stored `seen_seq`, no catch-up: the device has no "last
  visit". Another device of the same player (spec 033) has its own seen seq.
- Coming back after a time-out (AC-2, AC-4): after spec 017's time-out, the page's
  join seats the player back with the same id and token (spec 032 AC-7), and the
  return applies as usual. A full or locked room refuses that join (spec 032 AC-7),
  so no snapshot comes and there is no return; the stored `seen_seq` stays for a
  later visit. A player who comes back without their token joins as a new player,
  whose token is a current member's, and the return applies with it. (Note from the
  lead, 2026-10-15: this item was "Coming back as a new player", where the page always
  joined as a new player; changed after spec 032's decision 11.)
- Expired, then a new room with the same code (AC-5): the stored `seen_seq` of the old
  room may be compared with the new room's seqs; at worst a first visit to the new
  room shows a catch-up of its own events. Codes are drawn from about 10^9, so this is
  left as it is.
- My own changes (AC-1): cells changed by my own token on another device, or before
  a reload whose events this page never applied, count as changed: this device did
  not see them.
- Pending edits (AC-2): an edit typed while offline and resent after the reconnection
  (spec 017) gets a `seq` after the snapshot, so it is not part of the absence.
- Same cell many times (AC-1): listed once.
- Locked by a check (AC-1): a cell locked during the absence is changed, even when
  its letter is the same as before.
- Wrong marks (AC-1): a cell only struck through by a check (`check_result`, no lock)
  is not a changed cell; the check's line says it.
- Words in the absence (AC-3): a word completed, then emptied, then completed again
  gives two lines. A word whose last letter was written before the absence gives no
  line, even if a check locked it during the absence.
- Removed players (AC-3): a player removed during the absence, or gone by time-out,
  was a player of the room when they made their line, so the replay gives their
  name. A line whose player is not in the room when it is made, such as a vote that
  passes after its requester left (spec 025), gets no name: the page shows the name
  it knows, or `t("feed.someone")`. (Note from the lead, 2026-10-17: this item said
  that `before.players` gives the name of a player removed during the absence; the
  names now come from the replay (simplification, human's rule of 2026-10-16).)
- Unknown names (AC-4): a line whose player the page cannot name reads
  `t("feed.someone")` (spec 013).
- Many lines (AC-3, AC-4): the server sends the last 100; the feed then keeps its
  newest 100 items, so live lines that came in meanwhile push out the oldest catch-up
  lines.
- Range limits (AC-1): `until_seq` above the room's seq reads up to the room's last
  event, and `after_seq` at or above `until_seq`, or above the room's seq, gives no
  cell, line or name; neither needs a rule of its own ("`nock.hub`"). A room with no
  snapshot at or below `after_seq`, which only a room added in a later state with
  `add_room` (a test seam) can be, gets None, so 404. (Note from the lead,
  2026-10-17: this item said that an `after_seq` below the room's first snapshot
  reads from that snapshot (simplification, human's rule of 2026-10-16).)
- A long absence (AC-1): the server replays at most `snapshot_every - 1` entries
  (spec 018) to reach the seen seq, then every entry of the absence, once per return.
- Highlight and other looks (AC-2): the ring adds to spec 016's flash, spec 013's
  tint, spec 019's authorship colours and the bold letter of a locked cell (spec
  035); it does not replace them, and the cell's letter keeps its 4.5:1 contrast
  (spec 035). (Note from the lead, 2026-10-17: "spec 016's locked look" became "the
  bold letter of a locked cell (spec 035)", the spec that defines that look
  (preparation of spec 034).)
- Highlight while the player types (AC-2): typing in a highlighted cell does not end
  its highlight; the 5,000 ms run on.
- Feed scroll (AC-4): catch-up lines are new lines for spec 013 AC-7: no special case,
  whether the list was at its end or not.
- Seen seq writes (AC-5): one `localStorage` write per applied event; a browser that
  refuses storage keeps the seen seq in memory only, so only reconnections show a
  catch-up.

## Out of scope

- Payments and subscriptions (epic E9).
- Room resume: spec 032.
- Optional account: spec 033 (a seen seq shared by the devices of an account).
- A "word completed" line for live play, which spec 013's refinement adds after this
  spec is built (decision 7), and lines for letters, chat, flags or presence in the
  catch-up. (Note from the lead, 2026-10-15: "(open question 1)" became the pointer
  to spec 013's refinement and decision 7.)
- A summary banner ("6 cases ont changé"), a button to show the highlight again, a
  marker separating the catch-up lines from the live ones.
- Showing what each changed cell held before.
- Catch-up through the WebSocket (decisions).

## Work packages

None.

## Decisions

Proposed by the spec-writer on 2026-10-14 for the Phase 6 refine, with the human's
answer of the same day (numeric thresholds: keep the backlog defaults, so 5 seconds).
They are part of the spec above and are approved with it.

1. "Newest first" against spec 013 (AC-4). See the note in "Terms": one feed, oldest
   first, newest at the bottom and in view, with spec 013's scroll rules.
2. "My last visit" (AC-5). Options: kept by the server per player, or by the device.
   Pick: by the device, as the seen seq in the room record, since spec 017 forgets a
   player 5 minutes after they leave and the player usually comes back as a new one.
   (Note from the lead, 2026-10-15: since spec 032's decision 11, a player who comes
   back with their token is seated back with the same id. The pick stands: the
   server keeps no seen seq for a past player, and each device keeps its own.)
3. Where the catch-up comes from (AC-1, AC-3). Options: a snapshot as it was at the
   seen seq, then the missed events replayed in the page; a new WebSocket message (a
   change to spec 039, whose decision 12 keeps feed history out of the snapshot); or
   an HTTP route that reads the log, as the architecture says catch-up does. Pick: the
   HTTP route, asked for by the page once the snapshot is in, with the page's token in
   the body; it never makes the room live.
4. Word completion (AC-3). Options: computed live and kept on each log entry, or
   computed when asked by replaying the absence from the seen seq. Pick: when asked,
   with `load_room_at`; the live path and `LogEntry` do not change. (Note from the
   lead, 2026-10-17: ", and rooms logged before this spec work too" was taken out:
   Nock has never been deployed and no store from before this release is kept
   (specs 027 and 032), so no room was logged before this spec (preparation of spec
   034).) "Complete" uses spec 026's "filled", as spec 021 uses
   "every cell of the word is filled"; a reveal's own line covers a word it fills.
5. The highlight's look (AC-2). Spec 035 forbids colour-only signals and keeps the
   outline for the selected cell, the corners for initials and the dashed border for
   other players. Pick: a solid ring of at least 3 px inside the cell's edge, with
   3:1 contrast (WCAG 1.4.11), under the other players' marks, for 5 seconds.
6. Names (AC-3). The page knows only the players of its snapshot and those it saw
   join. Pick: the catch-up carries the nicknames of the players its lines name,
   departed ones included. (Note from the lead, 2026-10-17: each nickname is now
   the one the player had when they made their line, read from the replay of the
   absence; it was looked for among the room's members of now, then in the
   absence's joins, then at the seen seq (simplification, human's rule of
   2026-10-16).)

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question.

7. Live "word completed" lines (former open question 1). Spec 013's live feed had
   no such line, so a player who stays would see fewer lines than one who comes
   back. Options: (a) catch-up only; (b) also add the line live, in spec 013's feed.
   Pick: (b), as a refinement of spec 013 made after this spec is built. What
   changed here: the paragraph after "Applying a catch-up" and "Out of scope" point
   to that refinement; the catch-up itself, its criteria and its tests do not
   change. Spec 013, a `done` spec, is then refined by the lead with dated notes:
   - its list of events that add a feed item gains a row: a `letter_changed` with a
     letter, on a cell that was empty just before it, adds one item per word
     through that cell that is complete just after it (each cell holds a letter,
     pencil or not), with `data-kind` `word_completed`, the text
     `t("feed.word_completed", {name, clue})` of this spec, `clue` the clue's text,
     `data-seq` the event's seq, the words in clue order (`row`, `column`,
     `clue_index`). A reveal's `cell_locked` adds none;
   - "Other events (`letter_changed`, ...) add no item" then names a
     `letter_changed` that completes no word;
   - "empty just before" and "complete just after" are read on the kept snapshot
     (the confirmed letters, spec 040), never on the letters shown with pending
     edits, so the live lines are those that this spec's server finds in the log;
   - feed items are no longer unique by `data-seq`: one `letter_changed` that
     completes two words adds two items with the same `data-seq`, and a
     `letter_changed` adds no other item. The client keys feed items by `seq` and
     clue (or by position), never by `seq` alone. Items still follow `seq` order,
     with equal seqs in clue order, as this spec's step 3 already says;
   - its feed criterion (AC-5) gains a case, for example on FX-01 one letter at
     (2, 4) completing `SENT` then `VIDE` gives two items with one `data-seq`.

## Open questions

None.
