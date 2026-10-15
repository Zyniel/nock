---
id: "021"
title: Clue flag
status: approved
---

# 021 - Clue flag

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.) (Note from the lead, 2026-10-15: done. The human's answers are decisions 7 and 8 below, and "Open questions" says "None.")

Epic E5 Collaboration aids (US-5.3) · Release: V1 · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine (`nock.room`, `nock.hub`, delivery order, test harness) is defined in spec
011, joining and the roster in spec 012, the activity feed in spec 013, removals in
spec 014, edits in spec 015, time-outs in spec 017, the log and `replay` in spec
018, "filled" and the completion rule in spec 026, the clue elements in spec 006,
the selected word and the clue tap in spec 007, the room toolbar in spec 024, the
authors switch in spec 019, the accessibility rules and scans in spec 035, the
messages in spec 039 (`Flag`, `FlagChanged`, `FlagView`, `Snapshot.flags`). Built
after specs 024, 025, 019 and 020.

## Goal

As a stuck player, I want to flag a clue, so that my team-mates know where help is wanted.

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking.

## Public interface

No new protocol message and no new `ErrorCode`: spec 039 already has `Flag`
(`clue: null` removes the sender's flag, its decision 16), `FlagChanged`,
`FlagView` and `Snapshot.flags`. This spec adds one field to `PlayerRecord`, gives
`Flag` its meaning in `nock.room.handle_message`, extends `snapshot_for` and
`replay`, and adds the flag button and the clue marker to the room page.

### Terms

- The word of a clue reference `ClueRef(row, column, clue_index)` is
  `state.grid.word_cells(row, column, clue_index)` (spec 002). The reference
  names a word when that call does not raise. It names none when the position is
  outside the grid or not a clue cell, when the clue cell has no clue at that
  index, or when `word_cells` rejects the word.
- A word is full when every one of its cells is filled in spec 026's sense: the
  cell holds a letter, pencil or not. Locked and revealed cells are filled.
- On the page, a word is full when every one of its cells has a shown letter
  (spec 015: the newest pending edit, else the confirmed letter).
- The room toolbar, its small windows (`window.innerHeight <= 500` or
  `window.innerWidth <= 480`) and its rules are spec 024's "Client: room toolbar":
  one row that scrolls sideways on a small window, with an edge fade, keyboard
  focus scrolled into view, and spec 013 AC-6's guarantees kept.

### State (`nock.room`)

```python
# src/nock/room.py (field added by this spec, with a default, as spec 011 requires)
class PlayerRecord(RoomModel):
    # ... fields of specs 011 to 037
    flag: ClueRef | None = None   # spec 021: the clue this player flagged
```

A player holds at most one flag because the flag is one field of their record
(AC-4).

### Server rule: `Flag` in `nock.room.handle_message`

`Flag(clue)` from joined player `p` is input (spec 013: it sets `last_input_at`
and wakes an idle player). It is not an edit, so spec 037's rate limit does not
count it. With `s` the room's seq before this message's own entries (after spec
013's entry that wakes an idle player, if there is one), the first case that
applies decides:

1. `clue` is None and `p.flag` is None: nothing happens. No entry, no reply.
2. `clue` is None: `p.flag = None`, and one entry
   `FlagChanged(seq=s + 1, player_id=p, clue=None)`.
3. `clue` names no word: refused with `ErrorMessage(code=INVALID_TARGET)`.
4. The word of `clue` is full: refused with `ErrorMessage(code=INVALID_TARGET)`.
5. `clue == p.flag`: nothing happens. No entry, no reply.
6. Otherwise `p.flag = clue`, and one entry
   `FlagChanged(seq=s + 1, player_id=p, clue=clue)`. A flag `p` held on another
   clue is replaced by this one, with no separate clearing entry.

A refusal leaves the state as it was apart from the sender's `last_seen_at`,
`last_input_at` and, if they were idle, their state (specs 013 and 017), writes no
entry of its own (an idle sender is first woken by spec 013's entry, which a
refusal does not undo) and sends one `ErrorMessage` to the sender only. (Note from
the lead, 2026-10-15: an idle sender is woken even when its message is refused, as
spec 013's input rule and the code do.) A solved grid does not refuse `Flag` (spec 026 keeps flags
working), but every word of a solved grid is full, so case 4 refuses every new
flag there while cases 1 and 2 still apply.

### Server rule: a flag clears when its word is full

After any accepted step of `handle_message` whose entries contain a
`letter_changed` or a `cell_locked` (the trigger of spec 026's completion rule:
edits, undo, reveals of spec 024 and the pencil letters of spec 020), each player
whose `flag` names a word that is now full, taken in `players` order, gets
`flag = None` and one entry `FlagChanged(seq, player_id=<that player>, clue=None)`.
These entries take the next seqs after the step's own entries. Spec 026's
completion entry (`grid_solved` or `grid_full_wrong`), when the step has one,
comes after them.

Example on FX-01, from spec 026's `FULL17` (seq 19): `p1` flags LEST (seq 20) and
`p2` flags SENT (seq 21); `p2` writes `T` at (4, 4) at `NOW + 754.0`. The step's
entries are `LetterChanged(seq=22, row=4, column=4, letter="T", pencil=False, player_id="p2")`,
`FlagChanged(seq=23, player_id="p1", clue=None)`,
`FlagChanged(seq=24, player_id="p2", clue=None)`, then
`GridSolved(seq=25, elapsed_ms=754000)`.

### Server rule: departures

A player who leaves the room (`player_left` with reason `removed`, spec 014, or
`timed_out`, spec 017) leaves with their flag: it goes with their record, and no
`flag_changed` entry is written. A disconnected player keeps their flag until they
leave or the flag clears.

### `snapshot_for` (spec 012)

`flags` holds one `FlagView(player_id=p.player_id, clue=p.flag)` per player whose
`flag` is not None, in `players` order. Several players may flag the same clue.

### `replay` additions (spec 018 table)

| Event | Effect on the state |
| --- | --- |
| `flag_changed` | the player's `flag` becomes the event's `clue` (`None` clears it); nothing when the player is not in the room |

`player_left` already removes the player, and their flag with them.

### Client: kept flags

`web/src/lib/roomSession.ts`:

```ts
export interface ClueRefView {
  row: number
  column: number
  clue_index: number
}

export interface FlagView {
  player_id: string
  clue: ClueRefView
}

export interface Snapshot {
  // ... fields of specs 012 to 040
  // The flags of the room, one per flagging player (spec 021).
  flags: FlagView[]
}
```

- A snapshot's `flags` become the kept flags. An entry that is not an object with
  a string `player_id` and a `clue` of three integers is skipped.
- An applied `flag_changed` with a clue sets that player's flag, replacing their
  previous one. With `clue: null` it removes the player's flag.
- An applied `player_left` removes that player's flag.

The activity feed already adds a line for each `flag_changed` that has a clue,
`data-kind="flag"`, with the text `t("feed.flag", { name, clue })`, and none for
`clue: null` (spec 013 AC-5 and decision 4). This spec does not change it.

### Client: the clue marker

On the `clue` elements of spec 006:

- Every `clue` element has `data-flagged`: `true` when at least one kept flag names
  that clue (the `data-row` and `data-column` of its cell and its
  `data-clue-index`), else `false`.
- A flagged clue holds exactly one `data-testid="clue-flag"` element, with
  `aria-hidden="true"`, the text `t("flag.marker")` (`⚑`), and `data-flagged-by`:
  the ids of the flagging players separated by one space, in roster order (the
  order of the snapshot's `players`, joiners appended). It also holds one
  `data-testid="clue-flag-label"` element with the class `visually-hidden` and the
  text `t("flag.marker_label", { names })`, where `names` is their nicknames in the
  same order joined by `, ` (an unknown id gives `t("feed.someone")`).
- An unflagged clue holds neither element.
- Order of the flaggers: the order of `data-flagged-by` and of the label's `names`
  is "roster order" as written above for the flaggers whose id is in the roster.
  The flaggers whose id is not in the roster (their name is `t("feed.someone")`,
  `Quelqu'un`) come after all of those, in the ascending order of their ids,
  compared as plain strings (`p7` before `p9`). (Note from the lead, 2026-10-15:
  the implementation assumed this order and the spec did not say it; it is now a
  rule, and AC-4 checks it (review of spec 021).)
- Look: the `clue-flag` element lies inside its clue cell's bounding box (1 px
  tolerance), has a computed `visibility` of `visible` and a computed `font-size`
  of at least 7 px, and its text reaches 4.5:1 against its background (spec 035's
  contrast scan). It takes no room from the clue: the `clue-text` of a flagged clue
  has the same bounding box as when it is not flagged (1 px tolerance), for
  example because the marker is positioned over a corner. The `⚑` sign is the
  signal that does not depend on colour (spec 035). (Note from the lead,
  2026-10-15: the rule on the `clue-text` box is kept as it is. It holds because
  spec 013 now gives the feed list a fixed height ("Client: feed height" there):
  the flag arrives as a `flag_changed`, which adds a feed line (spec 013 AC-5), and
  that line no longer makes the list taller and moves the grid down (review of
  spec 021).)

### Client: the flag button

- `data-testid="flag-button"`, a `<button type="button">` in spec 024's
  `room-toolbar`, after `reveal-panel` (spec 024) and before `authors-switch`
  (spec 019, which stays last), shown once the page has a snapshot. Spec 024's
  toolbar rules apply to it as to the toolbar's other controls.
- `aria-label` `t("flag.button_label")` (`Je bloque sur ce mot`), visible text
  `t("flag.button")` (`Je bloque`) at every window size.
- `aria-pressed`: `true` when a word is selected and my kept flag (the flag whose
  `player_id` is `you`) names that word's clue, else `false`.
- Disabled while nothing is selected, and while the selected word is full on the
  page and my flag is not on it. Enabled otherwise.
- A click when `aria-pressed` is `false` sends
  `{"type": "flag", "clue": {"row": r, "column": c, "clue_index": i}}` with the
  selected word's clue. A click when it is `true` sends
  `{"type": "flag", "clue": null}`. The page makes no local guess: `aria-pressed`
  and the marker follow the kept flags, so they change when the server's
  `flag_changed` is applied.
- An `error` answering a flag (`invalid_target`) changes nothing on the page. It is
  not one of the edit answers of spec 015, so the pending edits are not touched.
- The button meets spec 035: the visible focus of AC-2, a bounding box of at least
  24 by 24 CSS px (the target size of spec 014 AC-7), and text contrast of 4.5:1.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `flag.button` | `Je bloque` |
| `flag.button_label` | `Je bloque sur ce mot` |
| `flag.marker` | `⚑` |
| `flag.marker_label` | `Bloqué : {names}` |

`⚑` is U+2691 (BLACK FLAG). Spec 035 AC-9's checker reads every `fr.json` value
as a pattern and must still flag `Loading…`, `Salon` and `Check word`; none of
these four values matches them.

### Test harness

- Rule tests: `new_room("ABC123", fx01_grid, NOW)`, players `p1` and `p2` added
  with `join_room` at `NOW` (seq 2), letters written with
  `handle_message(..., EditLetter(...), NOW)`, then `handle_message(state, "p2",
  Flag(clue=...), NOW)`. `FULL17` is spec 026's state (seq 19).
- FX-01 words by clue reference: TAMIS `(0, 0, 0)`, NAVAL `(0, 0, 1)`, MIME
  `(0, 2, 0)`, IDES `(0, 3, 0)`, SENT `(0, 4, 0)`, VIDE `(2, 0, 0)`, AMEN
  `(3, 0, 0)`, LEST `(4, 0, 0)`. IDES holds (1, 3), (2, 3), (3, 3), (4, 3).
- WebSocket tests: spec 011's `TestClient` on a FX-01 room with
  `RoomConfig(max_edits_per_second=1000)`; time-outs use spec 011's `FakeClock`
  with `RoomConfig(tick_seconds=0.05, silence_timeout_seconds=3600)`, so that only
  a player whose socket closed times out while the clock is advanced.
- Browser with mocked socket: spec 040's mock on `/r/ABC123`, FX-01 snapshots
  built with `grid_view` and `model_copy`, players `p1` (`you`, `Ana`, host), `p2`
  (`Bob`) and `p3` (`Cy`), `flags` built with `FlagView`.
- Browser with live server: spec 040's `live_server`, one browser context per
  player, each entering through `enter_room` (spec 011).
- A word is selected by tapping its clue (spec 007): the `clue` element with that
  `data-clue-index` in the clue cell. For example the clue cell (0, 3) selects IDES.
- Contexts: desktop (that viewport, no touch) and touch (spec 009: the viewport,
  `has_touch=True`, `is_mobile=True` except under Firefox, and under Firefox and
  WebKit spec 009's `(pointer: coarse)` init script). Window sizes are spec 006
  AC-5's eight.
- Scans: spec 035's contrast scan and language scan ("Test harness" there), whose
  test data are the nicknames of the snapshot, their initials and the clue texts of
  FX-01. `tab_to` is spec 035's helper.
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check
  of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-5.3.1) (Python; WebSocket; browser with live server) Flagging a clue shows a marker on its clue cell for every player. Python: in the two-player FX-01 room (seq 2, no letter), `Flag(clue=ClueRef(row=0, column=3, clue_index=0))` from `p2` gives exactly one entry, `FlagChanged(seq=3, player_id="p2", clue=ClueRef(row=0, column=3, clue_index=0))`, no reply, `p2`'s `flag` equal to that clue, and `snapshot_for(state, "p1").flags == (FlagView(player_id="p2", clue=ClueRef(row=0, column=3, clue_index=0)),)`. WebSocket: clients A and B join; B sends `{"type": "flag", "clue": {"row": 0, "column": 3, "clue_index": 0}}`; A and B each receive one `flag_changed` with B's id, that clue and the next seq; a client C joining afterwards gets a snapshot whose `flags` hold that one `FlagView`. Browser: Ana (context 1) and Bob (context 2) join one FX-01 room; Bob taps the clue cell (0, 3) and clicks `flag-button`; within 1 s, on both pages, the clue of (0, 3) with `data-clue-index="0"` has `data-flagged="true"` and holds one `clue-flag` whose `data-flagged-by` is Bob's player id and whose text is `fr.json["flag.marker"]`, and its `clue-flag-label` reads `Bloqué : Bob`; on Bob's page `flag-button` has `aria-pressed="true"`.
- **AC-2** (AC-5.3.1) (browser with live server) A flag adds a line to the activity feed of every player. In the room of AC-1, after Bob's flag, the last `feed-item` of both pages has `data-kind="flag"` and the text `Bob bloque sur « Fatales à César »` (`fr.json["feed.flag"]` with `{name}` = `Bob` and `{clue}` = the clue text, spec 013).
- **AC-3** (AC-5.3.2) (Python; WebSocket; browser with mocked socket) The flag clears when every cell of the word is filled. Python: in the room of AC-1 after `p2` flagged IDES (seq 3), `p1` writes `I` at (1, 3), `D` at (2, 3) and `E` at (3, 3): each step's only entry is its `letter_changed`. `p1` then writes `S` at (4, 3): the entries are `LetterChanged(seq=7, row=4, column=3, letter="S", pencil=False, player_id="p1")` then `FlagChanged(seq=8, player_id="p2", clue=None)`, `p2`'s `flag` is None and the snapshot's `flags` is empty. From `FULL17`, the example of "Server rule: a flag clears when its word is full" gives exactly the four entries written there, in that order. WebSocket: A and B join; B flags MIME; A types `M`, `I`, `M`, `E` at (1, 2), (2, 2), (3, 2), (4, 2); A and B each receive, right after the `letter_changed` of the `E`, a `flag_changed` with B's id, `"clue": null` and the next seq. Browser: given a FX-01 snapshot with `seq` 5 whose `flags` hold `p2` on IDES, when the mock sends `flag_changed` seq 6 for `p2` with `clue: null`, the IDES clue gets `data-flagged="false"`, holds no `clue-flag` and no `clue-flag-label`, and `activity-feed` gets no new item.
- **AC-4** (AC-5.3.3) (Python; browser with mocked socket) A player holds one flag at a time, and a new flag replaces the previous one. Python: after `p2` flagged IDES (seq 3), `Flag(clue=ClueRef(row=0, column=2, clue_index=0))` from `p2` gives exactly one entry, `FlagChanged(seq=4, player_id="p2", clue=ClueRef(row=0, column=2, clue_index=0))`; `p2`'s `flag` is MIME and the snapshot's `flags` hold one `FlagView`. When `p1` then flags MIME too, the snapshot's `flags` are `p1` on MIME then `p2` on MIME (players order). Browser: given a snapshot whose `flags` hold `p2` on IDES, the mock sends `flag_changed` seq 6 for `p2` on MIME: IDES has `data-flagged="false"` and MIME `data-flagged="true"` with `data-flagged-by="p2"`; then `flag_changed` seq 7 for `p3` on MIME: MIME still holds one `clue-flag`, with `data-flagged-by="p2 p3"`, and its `clue-flag-label` reads `Bloqué : Bob, Cy`; then `flag_changed` seq 8 for `p9` and seq 9 for `p7` on MIME (two ids that are not in the roster): `data-flagged-by` is `p2 p3 p7 p9` and the label reads `Bloqué : Bob, Cy, Quelqu'un, Quelqu'un`. (Note from the lead, 2026-10-15: the last check is added, for the "Order of the flaggers" rule (review of spec 021).)
- **AC-5** (new) (Python) A flag that cannot apply is refused, and a flag that changes nothing writes nothing. In the two-player FX-01 room: `Flag(clue=None)` from `p1`, who has no flag, and `Flag` from `p2` on the clue `p2` already flagged each give no entry and no reply. `ClueRef(row=1, column=0, clue_index=0)` (a letter cell), `ClueRef(row=0, column=2, clue_index=1)` (that cell has one clue) and `ClueRef(row=9, column=9, clue_index=0)` (outside the grid) are each answered with one `ErrorMessage` with code `invalid_target`. After `p1` writes MIME's four letters, `Flag` on MIME is answered `invalid_target`; in `FULL17`, `Flag` on TAMIS is answered `invalid_target` and `Flag` on SENT is accepted; in the solved state of spec 026 AC-1, `Flag` on any of the eight words is answered `invalid_target`. Each refusal returns the state it was given apart from the sender's `last_seen_at`, `last_input_at` and, if they were idle, their state, with the same seq and no entry of its own (an idle sender is first woken by spec 013's entry, which takes one seq and which a refusal does not undo). (Note from the lead, 2026-10-15: an idle sender is woken even when its message is refused, as spec 013's input rule and the code do.)
- **AC-6** (new) (browser with mocked socket) The flag button sends a flag for the selected word and shows whether it holds mine. Given a FX-01 snapshot with `seq` 5 (`you` `p1`) where TAMIS holds `T`, `A`, `M`, `I`, `S` and no flag, at 1280 by 720: `flag-button` is inside `room-toolbar`, after `reveal-panel` and before `authors-switch` in document order, with the text `fr.json["flag.button"]`, the `aria-label` `fr.json["flag.button_label"]`, `aria-pressed="false"`, and it is disabled. After a tap on the clue cell (0, 2) (MIME), it is enabled; a click sends exactly one frame, which parses to `Flag(clue=ClueRef(row=0, column=2, clue_index=0))`, and `aria-pressed` stays `false` until the mock answers `flag_changed` seq 6 for `p1` on MIME, then reads `true`. A second click sends `Flag(clue=None)`; after `flag_changed` seq 7 for `p1` with `null` it reads `false`. With `p2`'s flag on MIME (`flag_changed` seq 8), `aria-pressed` stays `false` and a click sends `p1`'s own flag on MIME. A tap on the `clue` element of (0, 0) with `data-clue-index="0"` (TAMIS, full) makes the button disabled. An `error` with code `invalid_target` sent by the mock changes no attribute on the page.
- **AC-7** (new) (Python; WebSocket with a fake clock; browser with mocked socket) A player who leaves takes their flag with them. Python: after `p2` flagged IDES, `RemovePlayer(player_id="p2")` from the host `p1` (spec 014) gives the single entry `PlayerLeft(player_id="p2", reason="removed")` and the snapshot's `flags` are empty; `disconnect_player` of `p2` keeps the flag, and a `tick` past the resume window (spec 017) gives `PlayerLeft(timed_out)` and leaves no flag. WebSocket: A, B join; B flags IDES; B's socket closes; after `advance(301)` and one tick, a client C joining gets a snapshot with empty `flags`. Browser: given a snapshot whose `flags` hold `p2` on IDES, after the mock's `player_left` seq 6 for `p2` (reason `timed_out`), IDES has `data-flagged="false"`.
- **AC-8** (new) (Python) Flags survive a reload and a server restart. The entries of this play, replayed with `replay` in order from `new_room` on FX-01, give each player the same `flag` as the live state after every step: joins of `p1` and `p2`; `p2` flags IDES; `p1` flags MIME; `p1` sends `Flag(clue=None)`; `p2` flags SENT. A room created in a `RoomStore` with those entries appended loads with `snapshot_for(state, "p1").flags == (FlagView(player_id="p2", clue=ClueRef(row=0, column=4, clue_index=0)),)`, and still does so after `after_restart` (spec 018), which disconnects both players.
- **AC-9** (new) (browser with mocked socket) The marker sits inside its clue cell and does not move the clue text. With `p2`'s flag on IDES at 1280 by 720, and with `p2`'s flag on the first clue of FX-02 (the first clue cell in row-major order, clue index 0) at 360 by 740 and at 568 by 320: the `clue-flag` bounding box lies inside the clue cell's box (1 px tolerance), its computed `visibility` is `visible` and its computed `font-size` is at least 7 px; the `clue-text` of that clue has the same bounding box (1 px tolerance) as on the same page before the flag arrived; at 1280 by 720 on FX-01, spec 035's contrast scan finds no offending element. A clue of index 1: at 1280 by 720 on FX-01, with `p2`'s flag on NAVAL (`ClueRef(row=0, column=0, clue_index=1)`, the clue `De la marine`, second in the cell (0, 0)), the same checks on the `clue-flag` bounding box, `visibility` and `font-size` and on the `clue-text` box hold for it, and the marker is drawn just under the separator, inside the cell, clear of the clue text: the top of the `clue-flag` is at least the bottom of that cell's `clue-separator` minus 1 px and at most one tenth of the cell's height below it, and the `clue-flag` box and the `clue-text` box of NAVAL overlap by at most 1 px. (Note from the lead, 2026-10-15: the clue of index 1 is added, because its marker sits at another place than the first clue's, under the separator (review of spec 021).)
- **AC-10** (new) (browser with mocked socket, keyboard only after the setup) The flag button is reachable from the keyboard and readable in French. At 1280 by 720 after a tap on the clue cell (0, 2): `tab_to(page, "flag-button")` gives it the focus with spec 035 AC-2's outline (style neither `none` nor `auto`, width at least 2 px, contrast at least 3:1 against white), and `Enter` sends `Flag(clue=ClueRef(row=0, column=2, clue_index=0))`. With `p2`'s flag on IDES shown, at 1280 by 720 and 360 by 740, spec 035's language scan finds no text outside `fr.json` and the test's data (it accepts `Je bloque`, `⚑` and `Bloqué : Bob`), and the contrast scan finds no offending element.
- **AC-11** (new) (browser with mocked socket) The flag button keeps the room's layout on every window. Setup: spec 024 AC-8's (spec 013 AC-6's FX-01 snapshot with `you` host among 8 players, 100 feed items, (3, 1) tapped, help mode `free`) plus `p2`'s flag on IDES. At each window size of spec 006 AC-5, in desktop and touch contexts: every check of spec 013 AC-6 holds (the `grid-viewport` at least 100 px high, no page scroll, the grid inside the viewport at zoom 1, the clue bar inside the window and above the keyboard); `flag-button` is at least 24 by 24 CSS px; and spec 024 AC-8's toolbar checks hold with `flag-button` among the toolbar's buttons: on the four small windows its vertical range overlaps those of the six buttons of spec 024 AC-8; with the keyboard focus (desktop context), its box lies inside the toolbar's client area and its outline passes the "Not clipped" measure; after `scrollIntoView({block: "nearest", inline: "nearest"})`, `document.elementFromPoint` at its centre returns it.

## Edge cases and errors

- Several flaggers (AC-4): one clue holds one marker; `data-flagged-by` and the
  label list every flagger in roster order.
- Flag of a full word (AC-5): refused, so a flag never stays on a full word, also
  when the grid is full but wrong (spec 026). See decision 7. (Note from the lead,
  2026-10-15: 'See "Open questions"' became "See decision 7", the human's answer.)
- A reveal (spec 024) or a pencil letter (spec 020) that fills the last empty cell
  of a flagged word clears the flag like an edit (AC-3). A check (spec 023) never
  fills a cell, so it never clears a flag by itself.
- An undo or an erase that empties a cell of a word whose flag was cleared does not
  bring the flag back (AC-3).
- Disconnected flagger (AC-7): the flag stays while the player may still resume
  (spec 017's five minutes), then goes with them.
- Flag of a removed or timed-out player in a late joiner's snapshot (AC-7): absent,
  since the snapshot lists only the players' flags.
- Snapshot after a reconnection (AC-8): its `flags` replace the kept flags.
- Unknown player id in a `flag_changed` (AC-4): the flag is kept by id and the
  label shows `t("feed.someone")` for it; the page never fails on it.
- Idle player (AC-1): a flag is input and wakes an idle player (spec 013). A
  refused `Flag` from an idle player (AC-5) wakes them just the same: the outcome's
  entries are the one `PlayerStateChanged(state=active)` entry (spec 013), then the
  refusal, which is the one `ErrorMessage` in `reply` and writes no `FlagChanged`;
  the player is `active` afterwards. (Note from the lead, 2026-10-15: an idle sender
  is woken even when its message is refused, as spec 013's input rule and the code
  do.)
- Order of entries (AC-3): a step's own entries, then the clearing entries in
  `players` order, then spec 026's completion entry.
- Rate (AC-1): flags are not throttled, like checks (spec 023); each change is
  logged and adds a feed line for every player. The host's answer to a player who
  abuses it is removal (spec 014).
- Answers (spec 037 AC-1): `flag_changed` carries a clue position, never a letter,
  so spec 037's traffic checker accepts it as it is.
- Escaping (spec 037 AC-4): nicknames in `clue-flag-label` and in the feed line are
  inserted as text.
- Pending edits (AC-6): the button uses the shown grid, so a word that the player
  just filled is full for the button before the server confirms it.
- Phone keyboard (spec 009): `flag-button` is in the room toolbar, outside the grid
  area, the clue bar and the in-app keyboard; tapping it moves the focus off the
  grid like the toolbar's other controls.
- Small windows (AC-11): the button may be scrolled out of the toolbar's visible
  part; the edge fade of spec 024 shows that more controls follow.

## Out of scope

- Voice and video (epic E5).
- Authorship view: spec 019.
- Pencil letters: spec 020.
- Chat and reactions: spec 022.
- Flagging a full word, a single cell, or several clues at once.
- A list of all flags, showing the flaggers in the clue bar, sounds or
  notifications.
- Limiting how often a player flags.
- A screen reader announcement when another player flags (spec 035 leaves other
  players' actions out of the live region); the label is read with the clue.

## Work packages

None.

## Decisions

Proposed in the Phase 6 refine (2026-10-14) and approved by the human with this
spec. Each one is already part of the spec above. Items 7 and 8 below record the
human's answers to the two open questions.

1. Where the flag lives. Options: a list on `RoomState`, or a field on each
   `PlayerRecord`. Pick: `PlayerRecord.flag`, so "one flag per player" holds by
   construction and a departing player's flag goes with them.
2. Refusals. Pick: reuse `invalid_target` (spec 039 decision 19, as spec 023 does
   for a bad word target) for a clue that names no word and for a full word; no
   new `ErrorCode`.
3. Clearing. Pick: checked after every step that changes letters or locks, the
   trigger of spec 026's completion rule, with the clearing entries before the
   completion entry. A word filled by a reveal clears its flag too.
4. Departures. Pick: no `flag_changed` entry when a player leaves; the flag goes
   with the record, and pages drop it on `player_left`.
5. Controls. Pick: one toggle button in spec 024's `room-toolbar`, after the
   reveal controls and before the authors switch, acting on the selected word like
   `check-word` and `reveal-word`; on a small window it scrolls with the toolbar,
   so it costs no height; no local guess before the server's `flag_changed`.
6. Marker. Pick: a `⚑` sign over a corner of the flagged clue, which adds no layout
   and does not move the clue text; who flagged is in a visually hidden label and
   in `data-flagged-by`.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question. Each one is already part of the spec above.

7. Flagging a full word (former open question 1). Options: refused, so a flag never
   stays on a full word (the backlog's AC-5.3.2 read literally); or allowed, and
   cleared at the next letter change in that word, which lets players point at a
   doubtful word when the grid is full but wrong (spec 026). Pick: refused. AC-5
   and the server rule above (case 4 of `Flag`) are written with it.
8. Small windows (former open question 2). Options: one toolbar row that scrolls
   sideways, with an edge fade; or an `Aide` menu, where `flag-button` would move
   (AC-6 and AC-11 would change). Pick: the toolbar row, as spec 024 decision 12
   decides for the whole toolbar. `flag-button` stays in the row, after
   `reveal-panel` (decision 5).

Decided by the lead on 2026-10-15 after the review of spec 021, under the owner's
delegation of layout choices. Each one is already part of the spec above.

9. The clue text and the feed (Look, AC-9). The review measured at 1280 by 720
   that, with 1 or 2 feed lines, each new line made the feed list about 15 px
   taller and moved the grid's clue text down, so "the same bounding box" failed
   for a flag that adds a feed line. Options: loosen the rule, or fix the feed's
   height. Pick: spec 013 now fixes the feed list's height (its decision of the
   same date), and the rule here stays as written.
10. Flaggers who are not in the roster (marker label). Options: the order in which
    the page kept their flags, or the order of their ids. Pick: after the roster's
    players, in the ascending order of their ids as plain strings, so that the
    marker does not depend on the order the events came in. AC-4 checks it.
11. A marker on the second clue (AC-9). Pick: AC-9 measures a flag on NAVAL
    `(0, 0, 1)` of FX-01 too, because the marker of a clue of index 1 is placed
    under the separator, not at the cell's corner: just under the separator,
    inside the cell and clear of the clue text.

## Open questions

None.
