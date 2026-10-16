---
id: "027"
title: Shared timer
status: approved
---

# 027 - Shared timer

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.) (Note from the lead, 2026-10-15: done. The human's answers are decisions 7 to 9 below, and "Open questions" says "None." The one refinement of a `done` spec is the one of spec 026, described under "Changes to spec 026".) (Note from the lead, 2026-10-16: refined after the first review of spec 027, with the lead's decision 10 below. A `grid_solved` whose `elapsed_ms` is not a whole number of at least 0 now has a client rule, AC-3 and AC-5 gained cases, and the test harness and two edge cases gained text, so the test-writer adds the tests of the new cases before the implementer runs (review of spec 027).)

Epic E7 Completion and recap (US-7.1) · Release: V1 · Epic depends on: E6
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine (`nock.room`, `nock.hub`, test harness, fake clock) is defined in spec 011,
joining, resuming and `snapshot_for` in spec 012, presence in spec 013,
disconnection, silence and time-out in spec 017, the log, `replay`,
`after_restart` and the store in spec 018, the completion rule and `GridSolved` in
spec 026, the room toolbar in spec 024, the chat toggle in spec 022, the
accessibility rules and scans in spec 035, the messages in spec 039
(`Snapshot.timer_elapsed_ms`, `Snapshot.timer_running`, `GridSolved.elapsed_ms`).
Built after specs 024, 025, 019, 020, 021 and 022.

## Goal

As a team, we want one timer, so that we can compare our time from one grid to the next.

The recap credits contributions without turning a cooperative game into a ranking.

## Public interface

No new protocol message, no new `ErrorCode`. Spec 039 already gives the snapshot
`timer_elapsed_ms` and `timer_running`, and `GridSolved` its `elapsed_ms`; until
this spec, `snapshot_for` sends `0` and `False` (spec 012) and `elapsed_ms` is the
time since the room was created (spec 026, whose edge cases leave its redefinition
to this spec). The protocol has no timer event: a page learns the timer from its
snapshot, from the first `letter_changed` that holds a letter, and from
`grid_solved`.

### Terms

- A player is connected while their state is not `disconnected` (spec 013:
  `active` or `idle`).
- The timer is started once a player typed a letter, running while it counts,
  paused while it is started but nobody is connected, and stopped once the grid is
  solved.
- The room toolbar, its small windows and its rules are spec 024's "Client: room
  toolbar".

### State and functions (`nock.room`)

```python
# src/nock/room.py (fields added by this spec, each with a default, as spec 011 requires)
class RoomState(RoomModel):
    # ... fields of specs 011 to 037, 021 and 022
    timer_started: StrictBool = False                              # a letter was typed
    timer_elapsed_ms: int = Field(default=0, ge=0, strict=True)    # time counted before the current run
    timer_resumed_at: float | None = None                          # start of the current run; None when not running


def timer_value_ms(state: RoomState, now: float) -> int:
    """Return the shared timer at `now`, in whole milliseconds.

    It is `state.timer_elapsed_ms`, plus
    `max(0, round((now - state.timer_resumed_at) * 1000))` while
    `state.timer_resumed_at` is not None.
    """


def snapshot_for(
    state: RoomState, player_id: str, now: float | None = None
) -> Snapshot:
    """As spec 012, with the timer of this spec:

    `timer_elapsed_ms = timer_value_ms(state, now)`, or `state.timer_elapsed_ms`
    when `now` is None; `timer_running = state.timer_resumed_at is not None`.
    The rules always pass the step's `now`; a call without it (a test on a state
    built by hand) gets the time counted before the current run.
    """
```

`snapshot_for` keeps its two-argument form (spec 012's tests call it so); the new
`now` argument is optional.

### Server rules: the timer

The timer rules run after each entry of a step, in the order of the entries. `t`
is the step's `now` in a live step (`join_room`, `disconnect_player`,
`handle_message`, `tick`, `after_restart`) and `entry.at` in `replay`, so that
replaying a step's entries gives the timer of the live step. The first rule that
applies to an entry is used:

1. Start: the entry is a `letter_changed` whose `letter` is not None, and the
   timer is not started and the grid not solved: `timer_started = True`,
   `timer_resumed_at = t`. Erasing (a `letter_changed` with no letter) and a reveal
   (a `cell_locked`, spec 024) do not start the timer; a pencil letter (spec 020)
   does, since it is typed.
2. Stop: the entry is `grid_solved`: `timer_elapsed_ms = event.elapsed_ms`,
   `timer_resumed_at = None`. Nothing starts or resumes the timer after that.
3. Pause: the timer is running and no player is connected after the entry:
   `timer_elapsed_ms = timer_value_ms(state, t)`, `timer_resumed_at = None`.
4. Resume: the timer is started, not running, the grid not solved, and at least
   one player is connected after the entry: `timer_resumed_at = t`.

A step with no entry leaves the timer as it is, so a refusal changes no timer
field. These rules add no entry and change none. In every
state the rules produce, a started timer of an unsolved room runs exactly while at
least one player is connected.

The step that solves the grid: spec 026's completion rule builds
`GridSolved(seq, elapsed_ms=timer_value_ms(state, now))` with the state after the
step's earlier entries (so after the start of a first letter that would also solve
the grid), in place of spec 026's time since the room was created. Applying that
entry stops the timer (rule 2).

The join step: the snapshot in the reply of `join_room` is built with the step's
`now`, after the timer rules ran on the step's entries. A join that makes a paused
room connected again (a new player's `player_joined`, or a resume's
`player_state_changed` to `active`) resumes the timer at `now`, and the snapshot
says `timer_running` True with the time counted so far.

### `replay` (spec 018)

`replay` applies the four timer rules to each entry, with `t = entry.at`. Entries
logged before this spec are replayed the same way.

### Client: the timer

`web/src/lib/roomSession.ts`:

```ts
export interface Snapshot {
  // ... fields of specs 012 to 040, 021 and 022
  timer_elapsed_ms: number
  timer_running: boolean
}
```

The page keeps `timerBaseMs`, `timerRunning` and `timerAnchor` (a
`performance.now()` value):

- On a snapshot: `timerBaseMs = snapshot.timer_elapsed_ms` (0 when it is not a
  whole number of at least 0), `timerRunning = snapshot.timer_running === true`,
  `timerAnchor` = the time the snapshot is applied. (Note from the lead,
  2026-10-16: AC-5 now tests this coercion, with a `timer_elapsed_ms` of -1, 1.5,
  `"65000"`, `null` or absent, and a `timer_running` of `"true"`, 1, `null` or
  absent (review of spec 027).)
- On an applied `grid_solved` whose `elapsed_ms` is not a whole number of at
  least 0 (for example -1, 1.5, a string, `null`, or no `elapsed_ms` at all):
  `timerBaseMs` = the shown value (defined in the last bullet) at the moment the
  event is applied, in whole milliseconds, and `timerRunning = false`. The page
  stops its timer, as it does for a whole number, but keeps the value it shows and
  takes nothing from the event: the timer does not fall to 0, as a snapshot's
  malformed `timer_elapsed_ms` does. Like the snapshot's 0 and false above, this
  is a defensive rule: the server never sends such a value (spec 039's model
  allows only whole numbers of at least 0). AC-5 tests it. (Note from the lead,
  2026-10-16: added, decision 10 (review of spec 027).)
- On an applied `letter_changed` whose `letter` is a string, while `timerRunning`
  is false, `timerBaseMs` is 0 and the page is not solved: `timerRunning = true`,
  `timerAnchor` = now.
- On an applied `grid_solved` whose `elapsed_ms` is a whole number of at least 0:
  `timerBaseMs = elapsed_ms`, `timerRunning = false`. (Note from the lead,
  2026-10-16: "of at least 0" added, so that this bullet and the one above cover
  every value once; a negative whole number used to fall under this bullet
  (review of spec 027).)
- The shown value is `timerBaseMs`, plus `performance.now() - timerAnchor` while
  `timerRunning`, in milliseconds.

`data-testid="timer"` and then `data-testid="timer-toggle"` are the first two
elements of spec 024's `room-toolbar`, before `chat-toggle` (spec 022), so that the
time shows in the toolbar's visible part when a small window has scrolled nothing
yet. Spec 024's toolbar rules apply to `timer-toggle` as to the toolbar's other
controls; `timer` is text, not a control, and is never a Tab stop.

- `timer` has `role="timer"` (whose implicit `aria-live` is `off`, so a screen
  reader does not read every second), the `aria-label` `t("timer.label")`,
  `data-running` (`true` or `false`), and `data-elapsed-ms`: the shown value as a
  whole number, refreshed at least every 250 ms while running.
- Its text is the shown value in whole seconds `s` (rounded down):
  `t("timer.minutes_seconds", { minutes, seconds })` while `s < 3600`, with
  `minutes = floor(s / 60)` and `seconds` on two digits (`0:00`, `1:05`,
  `59:59`); `t("timer.hours_minutes_seconds", { hours, minutes, seconds })` from
  3,600, with minutes and seconds on two digits (`1:02:05`, `10:00:00`). The text
  does not wrap.
- `data-testid="timer-toggle"`: a button with the text `t("timer.toggle")` (`⏱`)
  at every window size, the `aria-label` `t("timer.toggle_label")`, and
  `aria-pressed`: `true` while the timer is shown. A click shows or hides the
  timer on this page only. It sends nothing. (Note from the lead, 2026-10-15:
  "sends nothing" leaves aside the heartbeat `ping` frames of spec 017, which the
  page may send at any time once the socket is open.)
- Hidden: no `timer` element is on the page, and `localStorage` holds
  `nock.timer_hidden` = `true`. Shown: the key is absent. The page reads the key at
  load, so the choice holds for every room opened in this browser. A key holding
  anything else counts as absent.
- Both elements meet spec 035: the visible focus of AC-2 on `timer-toggle`, a
  bounding box of at least 24 by 24 CSS px for it, and text contrast of 4.5:1.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `timer.label` | `Chrono` |
| `timer.minutes_seconds` | `{minutes}:{seconds}` |
| `timer.hours_minutes_seconds` | `{hours}:{minutes}:{seconds}` |
| `timer.toggle` | `⏱` |
| `timer.toggle_label` | `Afficher le chrono` |

`⏱` is U+23F1 (STOPWATCH). Spec 035 AC-9's checker reads every `fr.json` value
as a pattern and must still flag `Loading…`, `Salon` and `Check word`: the two
time patterns need a `:`, which none of those holds. (Note from the lead,
2026-10-16: spec 035's checker now reads `{hours}`, `{minutes}` and `{seconds}`
as ASCII digits only, so the two time patterns need digits on both sides of each
`:`, not a `:` alone, which `Error: connection lost` also holds; see "Language
scan" in spec 035's "Test harness" (second review of spec 027).)

### Changes to spec 026

Spec 026 computes `elapsed_ms` as the time since the room was created and leaves
the shared timer to this spec (its decision 4 and the `elapsed_ms` edge case).
With this spec it is the timer's value (above). The two agree when the first
letter is typed at the room's creation time and a player stays connected, which
is the case in spec 026's rule tests of AC-1. Spec 026's AC-9 test that loads a
full, wrong room from a store and solves it ("a stored full wrong room loads
unsolved and can still be solved") types its first letter at `NOW + 100.0` and
expects `elapsed_ms=754000` at `NOW + 754.0`; the timer gives `654000`. The lead
adds a dated note to spec 026's completion rule, its `elapsed_ms` edge case and its
decision 4 before this spec's tests are written. This spec's test-writer then
updates that expectation before the implementer runs.

(Note from the lead, 2026-10-15: spec 026 is `done`, and this spec changes it in
three places, all dated notes that the lead adds before the test-writer of this
spec starts: the completion rule (its formula for `elapsed_ms`, from
`state.created_at`), the `elapsed_ms` edge case ("time since the room was created")
and decision 4. No acceptance criterion of spec 026 changes: its AC-1
keeps `elapsed_ms=754000`, which the timer gives (AC-6 here). One test of spec 026
changes, `test_ac9_a_stored_full_wrong_room_loads_unsolved_and_can_still_be_solved`
in `tests/test_spec_026_ac08_ac09_letters_and_reload.py`, a test of its AC-9: it
expects `elapsed_ms=754000` and must expect `654000`. The other tests of spec 026
that read `elapsed_ms` (AC-1) type their first letter at `NOW` with a player
connected, so the timer gives them the same value. The human's answers, decisions
7 to 9, change nothing in spec 026. Spec 012 (`done`) already leaves the two
snapshot fields to this spec, and its snapshot criterion (AC-3) reads a room where
no letter was typed through the rules, where they stay `0` and `False`.)

### Test harness

- Rule tests: `new_room("ABC123", fx01_grid, NOW)`, players added with `join_room`
  at the times given, letters written with `handle_message(..., EditLetter(...))`,
  disconnections with `disconnect_player`, resumes with `join_room` and the
  player's token; times are `NOW` plus seconds.
- WebSocket tests: spec 011's `TestClient` with a `FakeClock` and
  `RoomConfig(tick_seconds=0.05, silence_timeout_seconds=3600, max_edits_per_second=1000)`,
  so that advancing the clock disconnects nobody for silence; with the clock
  frozen, values are exact.
- Browser with live server: spec 040's `live_server` (real clock), one browser
  context per player, each entering through `enter_room`; a page reopened in the
  same context resumes the same player (spec 012's stored identity).
- Browser with mocked socket: spec 040's mock on `/r/ABC123`, FX-01 snapshots with
  the chosen `timer_elapsed_ms`, `timer_running` and `solved`. A malformed value
  (AC-5) cannot be built with the protocol models, which refuse it (spec 039): the
  test takes a valid frame as a JSON object, changes or removes the field, and
  sends the text. A reconnection (AC-3): the mock closes the socket (code 1011)
  and answers the join of the page's next socket with a snapshot (spec 017).
  (Note from the lead, 2026-10-16: the last two sentences were added (review of
  spec 027).)
- Reading the timer: `data-elapsed-ms` read with `get_attribute`; "the text reads
  X within T ms" uses Playwright's waiting assertions.
- Contexts, window sizes and scans: as spec 021 (desktop and touch contexts, spec
  006 AC-5's eight sizes, spec 035's scans and `tab_to`).
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check
  of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-7.1.1) (Python; WebSocket with a fake clock) The timer starts at the first letter typed. Python: in a FX-01 room created at `NOW` where `p1` and `p2` joined at `NOW`, `timer_started` is False and `snapshot_for(state, "p2", NOW + 9.0)` has `timer_elapsed_ms == 0` and `timer_running is False`; `Erase(row=1, column=0)` from `p1` at `NOW + 5.0` leaves `timer_started` False; `EditLetter(row=1, column=0, letter="T")` from `p1` at `NOW + 10.0` gives `timer_started` True, `timer_resumed_at == NOW + 10.0` and `timer_elapsed_ms == 0`; then `timer_value_ms(state, NOW + 40.0) == 30000`, `snapshot_for(state, "p2", NOW + 40.0)` has `timer_elapsed_ms == 30000` and `timer_running is True`, and a third player joining with `join_room` at `NOW + 40.0` receives a snapshot with those same two values. WebSocket: A and B join; a client D joins and its snapshot has `timer_elapsed_ms == 0` and `timer_running is False`; after `advance(20)`, A types `T` at (1, 0); after `advance(30)`, a client C joins and its snapshot has `timer_elapsed_ms == 30000` and `timer_running is True`.
- **AC-2** (AC-7.1.1) (browser with live server) The timer reads the same for every player, within 1 second. Ana and Bob join one FX-01 room in two contexts: both `timer` elements read `0:00` with `data-running="false"`, and still read `0:00` 2 seconds later. Ana taps (1, 0) and types `T`; within 1 s both have `data-running="true"`. 3 seconds after the key press, the test reads `data-elapsed-ms` on Ana's page, then on Bob's: both lie between 2,000 and 4,500, they differ by at most 1,000, and the two texts are the same or one second apart. Cy then joins in a third context; within 1 s of Cy's `data-status="joined"`, Cy's `data-elapsed-ms` and Ana's, read right after, differ by at most 1,000.
- **AC-3** (AC-7.1.2) (Python; WebSocket with a fake clock; browser with live server; browser with mocked socket) The timer pauses while no player is connected and resumes at the next connection. Python: in a FX-01 room where `p1` alone joined at `NOW` and typed `T` at (1, 0) at `NOW`, `disconnect_player(state, "p1", NOW + 30.0)` gives `timer_resumed_at` None and `timer_elapsed_ms == 30000`, and `timer_value_ms(state, NOW + 200.0) == 30000`; `join_room` with `p1`'s token at `NOW + 200.0` gives `timer_resumed_at == NOW + 200.0` and a reply whose snapshot has `timer_elapsed_ms == 30000` and `timer_running is True`, and `timer_value_ms(state, NOW + 210.0) == 40000`. With `p2` also joined and connected, `p1`'s disconnection leaves the timer running. From the same running room (`p1` last seen at `NOW`), `tick(state, NOW + 6.0)`, which disconnects `p1` for silence (spec 017), gives `timer_resumed_at` None and `timer_elapsed_ms == 6000`, and `after_restart(state, NOW + 50.0)` gives `timer_resumed_at` None and `timer_elapsed_ms == 50000`. In a FX-01 room where `p1` and `p2` joined at `NOW` and `p1` typed `T` at (1, 0) at `NOW`, `disconnect_player(state, "p1", NOW + 30.0)` leaves `timer_resumed_at == NOW` and `timer_elapsed_ms == 0` (`p2` is still connected), and `join_room` with `p1`'s token at `NOW + 45.0` gives a reply whose snapshot has `timer_elapsed_ms == 45000` and `timer_running is True`, while the room keeps `timer_resumed_at == NOW` and `timer_elapsed_ms == 0`: a player who comes back to a room whose timer runs changes no timer field. (Note from the lead, 2026-10-16: this sentence was added; no earlier text covered a resume into a room whose timer is running (review of spec 027).) WebSocket: A joins alone and types `T` at (1, 0); after `advance(30)`, A's socket closes; after `advance(200)`, A joins again with its token and its snapshot has `timer_elapsed_ms == 30000` and `timer_running is True`; after `advance(10)`, B joins and its snapshot has `timer_elapsed_ms == 40000`. Browser: Ana alone joins a FX-01 room and types `T` at (1, 0); once her `data-elapsed-ms` reads at least 2,000, the test notes it and closes the page; 4 seconds later it opens the room in a new page of the same context; within 1 s of `data-status="joined"`, `data-running` is `true` and `data-elapsed-ms` lies between the noted value and the noted value plus 1,500, so the 4 seconds away were not counted. Browser with mocked socket (a page that loses its socket): given a snapshot with `timer_elapsed_ms` 65,000 and `timer_running` true, once `timer` reads `1:10` or later the mock closes the socket with code 1011; the page keeps `data-running="true"` and its `data-elapsed-ms` keeps growing while it is offline; when the mock answers the join of the page's next socket (spec 017) with a snapshot of 62,000 and true, `timer` reads `1:02` within 300 ms and `data-elapsed-ms` lies between 62,000 and 63,500, so the page shows the snapshot's value although it is lower than the 70,000 or more the page had counted. (Note from the lead, 2026-10-16: this run was added; it is the page-level test of the "Page offline" edge case (review of spec 027).)
- **AC-4** (AC-7.1.3) (browser with mocked socket) Each player can hide the timer on their own screen. Two browser contexts each open the room with a mocked socket and a snapshot whose `timer_elapsed_ms` is 65,000 and `timer_running` is true; both pages show `timer` and `timer-toggle` with `aria-pressed="true"`. On the first page, a click on `timer-toggle` makes it `aria-pressed="false"`, leaves no `timer` element and sends no frame (Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted); the second page still shows its `timer`. The first page reloaded (same context, a new mocked socket with the same snapshot) shows no `timer`, `timer-toggle` has `aria-pressed="false"`, and `localStorage["nock.timer_hidden"]` is `true`. A second click shows the timer again with a text of `1:05` or later and removes the key.
- **AC-5** (new) (browser with mocked socket) The timer shows the room's time in minutes and seconds, then in hours, follows the room's events, and reads a malformed timer value safely. (Note from the lead, 2026-10-16: this clause and the last three runs were added (review of spec 027).) In separate runs:
  - A snapshot with `timer_elapsed_ms` 0, `timer_running` false and `solved` false: `timer` reads `0:00` with `data-running="false"`, and still `0:00` 2 seconds later. A `letter_changed` with `"letter": null` changes nothing. A `letter_changed` with letter `T` from `p2` then sets `data-running="true"`, and the text reads `0:01` within 1,500 ms.
  - A snapshot with 65,000 and true: `1:05` within 300 ms, then `1:06` within 1,300 ms of the first reading; `data-elapsed-ms` grows between two reads 500 ms apart.
  - A snapshot with 3,725,000, false and `solved` true: `1:02:05`, still the same 2 seconds later.
  - A snapshot with 36,000,000 and true: `10:00:00`.
  - A snapshot with 750,000 and true, then `grid_solved` with `elapsed_ms` 754,000: `12:34`, `data-running="false"`, `data-elapsed-ms="754000"`, still the same 2 seconds later.
  - A snapshot whose `timer_elapsed_ms` is -1, 1.5, `"65000"`, `null` or absent (one run for each value) and whose `timer_running` is false, the frame built as the "Test harness" says: `timer` reads `0:00` with `data-running="false"` and `data-elapsed-ms="0"`, and still `0:00` 2 seconds later, since the client counts a `timer_elapsed_ms` that is not a whole number of at least 0 as 0.
  - A snapshot with 65,000 whose `timer_running` is `"true"`, 1, `null` or absent (one run for each value): `timer` reads `1:05` with `data-running="false"`, and still `1:05` 2 seconds later, since the client counts a `timer_running` that is not exactly `true` as false.
  - A snapshot with 750,000 and true, then `grid_solved` whose `elapsed_ms` is -1, 1.5, `"754000"`, `null` or absent (one run for each value): `data-running` becomes `false` within 300 ms, and `data-elapsed-ms` holds the value the page had counted to when the event arrived: at least the value the test read just before it sent the event, and at most that value plus 1,500 (so it is not 0 and not a value taken from the event); the text and `data-elapsed-ms` are still the same 2 seconds later.
- **AC-6** (new) (Python) The solving time is the shared timer, which stops at the solve. From the two-player room (joins at `NOW`, seq 2): `p1` writes the 17 FX-01 letters other than (4, 4) at `NOW + 100.0` (seq 3 to 19, the timer starts at `NOW + 100.0`); `p1` and `p2` disconnect at `NOW + 160.0` (seq 20 and 21; the timer pauses at 60,000); both join again with their tokens at `NOW + 400.0`, within spec 017's resume window (seq 22 and 23); `p2` writes `T` at (4, 4) at `NOW + 454.0`. That step's entries are its `LetterChanged` (seq 24) then `GridSolved(seq=25, elapsed_ms=114000)`; the state has `timer_elapsed_ms == 114000` and `timer_resumed_at` None; `snapshot_for(state, "p1", NOW + 2000.0)` has `timer_elapsed_ms == 114000` and `timer_running is False`; a third player joining at `NOW + 2000.0` leaves it stopped. In spec 026's `FULL17` (letters at `NOW`), the 18th letter at `NOW + 754.0` still gives `GridSolved(seq=21, elapsed_ms=754000)`.
- **AC-7** (new) (Python) The timer survives a reload and a server restart. The entries of AC-6's play, replayed in order with `replay` from `new_room` on FX-01, give after each step's last entry the same `timer_started`, `timer_elapsed_ms` and `timer_resumed_at` as the live state after that step. A `RoomStore` holding the play up to seq 23 loads with `timer_resumed_at == NOW + 400.0` and `timer_elapsed_ms == 60000`; `after_restart(loaded, NOW + 430.0)` gives `timer_resumed_at` None and `timer_elapsed_ms == 90000`; a player who then joins with their token at `NOW + 700.0` gets a snapshot with `timer_elapsed_ms == 90000` and `timer_running is True`, the 270 seconds without a connected player not being counted.
- **AC-8** (new) (browser with mocked socket) The timer and its toggle are accessible and keep the room's layout. `timer` has `role="timer"`, no `aria-live` attribute of `polite` or `assertive`, and the `aria-label` `fr.json["timer.label"]`; `timer`, `timer-toggle` and `chat-toggle` are the first three elements of `room-toolbar`, in that order. `timer-toggle` has the text `fr.json["timer.toggle"]` and the `aria-label` `fr.json["timer.toggle_label"]`; at 1280 by 720, `tab_to` gives it the focus with spec 035 AC-2's outline, and `Enter` hides the timer. With a snapshot of 36,000,000 ms running (`10:00:00`), at 1280 by 720 and 360 by 740, spec 035's contrast scan finds no offending element and its language scan finds no text outside `fr.json` and the test's data (it accepts `10:00:00`, `⏱` and `Chrono`). At each window size of spec 006 AC-5, in desktop and touch contexts, with spec 024 AC-8's setup (spec 013 AC-6's FX-01 snapshot with `you` host among 8 players, 100 feed items, (3, 1) tapped, help mode `free`) and the timer at `10:00:00`: every check of spec 013 AC-6 holds; `timer-toggle` is at least 24 by 24 CSS px; spec 024 AC-8's toolbar checks hold with `timer-toggle` among the toolbar's buttons; on the four small windows, with the toolbar's `scrollLeft` at 0, `timer` lies inside the toolbar's client area and its text is on one line (the vertical ranges of `timer` and `timer-toggle` overlap).

## Edge cases and errors

- Before the first letter (AC-1): the timer reads `0:00` and does not move, also
  while players select cells, chat or flag.
- Erase and reveal (AC-1): neither starts the timer; a grid solved only by reveals
  ends with `elapsed_ms` 0.
- First letter that solves the grid (AC-6): the start then the stop, in one step:
  `elapsed_ms` 0.
- Idle players (AC-3): an idle player is connected, so the timer runs.
- Silence (AC-3): a page that loses its network is seen disconnected after 6 to 7
  seconds (spec 017), so the timer can count up to 7 seconds after the last player
  really left.
- Server restart (AC-7): the timer of a running room counts until the restart step
  (`after_restart`), which pauses it; the time between a crash and the restart is
  counted. See decision 7. (Note from the lead, 2026-10-15: 'See "Open
  questions"' became "See decision 7", the human's answer.)
- Page offline (AC-3): a page that lost its socket keeps counting on its own; the
  next snapshot sets the value again, so the shown time may step back. (Note from
  the lead, 2026-10-16: AC-3 now names a page-level test of this step back: a page
  that reconnects shows the snapshot's value, even when it is lower than what it
  showed (review of spec 027).)
- Solved (AC-6): stopped for good; joins, chat and flags after the solve do not
  move it. A snapshot of a solved room says `timer_running` False with the final
  time, which is `elapsed_ms`.
- The solve moves the shown time (AC-5): a page counts from the moment it applied
  its snapshot or the first letter, so its count runs behind the server's by the
  time that snapshot or letter took to arrive, and `grid_solved` carries the
  server's value, which the page then shows (decision 5). At the solve the shown
  time can move by a few tens of milliseconds, and now and then by one visible
  second, when a whole second lies between the two values. Accepted: the final
  time is the server's, the same for every player. (Note from the lead,
  2026-10-16: added (review of spec 027).)
- Hidden timer (AC-4): hiding changes nothing for the other players, for the
  recap (spec 028) or for `elapsed_ms`.
- Background tabs (AC-2): browsers slow timers in hidden tabs; the shown value is
  computed from `performance.now()`, so it is right again at the next refresh.
- Old logs and snapshots (AC-7): a room is loaded from its newest stored
  snapshot, then the entries logged after it are replayed (spec 018). Those
  entries, also when they were logged before this spec, go through the timer
  rules, and a `grid_solved` entry keeps the `elapsed_ms` it was logged with. A
  snapshot stored before this spec holds no timer field, so the three fields take
  their defaults (`timer_started` False, `timer_elapsed_ms` 0, `timer_resumed_at`
  None) and the room loads as never started, whatever was typed before that
  snapshot: its timer starts at the first letter typed after it, and a room that
  was already solved when the snapshot was stored gives a joining player
  `timer_elapsed_ms` 0 and `timer_running` False, so the page shows `0:00`, while
  its `grid_solved` entry keeps the old time. Accepted: Nock has never been
  deployed and no store from before this release is kept, so there is nothing to
  migrate and no criterion tests it. (Note from the lead, 2026-10-16: this edge
  case used to say that a room whose log was written before this spec "gets its
  timer from the replayed entries", which holds for the entries after the newest
  snapshot and not for the play before it. The lead accepts that loss, for the
  reason above (second review of spec 027).)
- Rounding (AC-1, AC-6): every pause and every value rounds to whole milliseconds,
  `max(0, ...)` keeps a clock that went back from giving a negative time.
- Small windows (AC-8): the timer is first in the toolbar, so it shows until the
  player scrolls the toolbar; a hidden timer leaves only its toggle there.

## Out of scope

- Public leaderboards (epic E7).
- End-of-game recap: spec 028.
- Game history: spec 029.
- A timer event in the protocol, pausing the timer by hand, a countdown, per-player
  times, or time penalties for checks and reveals.
- Announcing the time to screen readers at intervals.
- Counting time while the room is open but every page is in the background.

## Work packages

None.

## Decisions

The backlog's number is kept, as the human answered on 2026-10-14 ("numeric
thresholds keep the backlog defaults"): the same reading for every player within
1 second. The items below were proposed in the Phase 6 refine (2026-10-14) and
approved by the human with this spec. Each one is already part of the spec above.
Item 6 partly answers the last two open questions; the human's answers to all three
are items 7 to 9 below.

1. No protocol change. The snapshot's two timer fields, the first `letter_changed`
   with a letter and `grid_solved` are enough for every page to show the same
   time, because a page is only ever connected while the timer runs.
2. State: three fields on `RoomState`, applied after each entry, so that the live
   steps and `replay` give the same timer; `snapshot_for` gains an optional `now`.
3. "First letter typed": the first `letter_changed` that holds a letter, which
   covers normal and pencil letters, and not erases or reveals.
4. "Connected": a player whose state is not `disconnected`.
5. `GridSolved.elapsed_ms` becomes the timer's value, as spec 026 foresaw.
6. Display: `m:ss`, then `h:mm:ss` from one hour, first in spec 024's
   `room-toolbar` so that it shows before any sideways scroll on a small window,
   with a one-symbol toggle; hiding is a per-browser choice stored in
   `localStorage`.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question. Each one is already part of the spec above.

7. Time while the server is down (former open question 1). Options: counted until
   the restart step pauses the timer, which is simple and the same in `replay`; or
   paused at the last logged event before the crash, which needs the restart step
   to log that time, for example a new field of `LogEntry`. Pick: counted until the
   restart step (`after_restart`).
8. Scope of hiding (former open question 2). Options: one choice per browser for
   every room; or one choice per room (`nock.timer_hidden.<CODE>`). Pick: one
   choice per browser, in `nock.timer_hidden` (decision 6).
9. Small windows (former open question 3). Options: one toolbar row that scrolls
   sideways, with an edge fade; or an `Aide` menu, with the timer still in the
   header since it is read, not used. Pick: the toolbar row, as spec 024 decision 12
   decides for the whole toolbar. The timer comes first in the row, so it shows
   before any sideways scroll (decision 6).

Decided by the lead on 2026-10-16, after the first review of spec 027, under the
human's permission to refine approved and done specs. Each one is already part of
the spec above. (Note from the lead, 2026-10-16: this group was added (review of
spec 027).)

10. A `grid_solved` with an `elapsed_ms` that is not a whole number of at least 0
    (Client: the timer). The server never sends one: spec 039's model allows only
    whole numbers of at least 0. The page still has to do something with it.
    Options: leave the timer as it is (a running timer would then count for ever
    in a solved room); take 0, as a snapshot's malformed `timer_elapsed_ms` is
    taken (a solved room would show `0:00`); or stop the timer at the value the
    page shows at that moment. Pick: stop the timer, as for a whole number, but at
    the shown value and not the event's: the room is solved, so the timer must
    stop, and the page's own count is the best time it has. A defensive rule,
    tested in AC-5. (Note from the lead, 2026-10-16: added (review of spec 027).)

## Open questions

None.
