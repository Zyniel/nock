---
id: "025"
title: Group decision on help
status: done
---

# 025 - Group decision on help

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.) (Note from the lead, 2026-10-15: done. The human's answers are decisions 11 to 15 below, and "Open questions" says "None." The one refinement of a `done` spec is the amendment of spec 023, described under "Edge cases and errors".) (Note from the lead, 2026-10-15: after
the review, decisions 16 to 19 were folded into the text; the one question the
review raised, on the focus when a vote closes, was answered (a) and is part of
decision 19, and "Open questions" says "None." again (review of spec 025))

Epic E6 Help and validation (US-6.3) · Release: V1 · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine (`nock.room`, `nock.hub`, `tick`, delivery order, test harness) is defined
in spec 011, the one-tap start in spec 010, joins and colours in spec 012,
presence, input and the activity feed in spec 013, the host panel and the
settings in spec 014, reconnection in spec 017, the log and `replay` in spec 018,
checks in spec 023, reveals and the room toolbar in spec 024, completion in spec
026, accessibility in spec 035, the messages in spec 039 (`Vote`, `VoteOpened`,
`VoteClosed`, `VoteOutcome`, `HelpMode`, `Snapshot.open_vote`,
`ErrorCode.VOTE_IN_PROGRESS`, `ErrorCode.NO_OPEN_VOTE`). Built after spec 024.

## Goal

As a host, I want to choose how help is granted, so that the room plays at the difficulty it agreed on.

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone.

## Public interface

No new protocol message and no new `ErrorCode`. New public names in `nock.room`:
the model `OpenVote`, two fields of `RoomState` and one of `RoomConfig`, each with
a default (spec 011's rule for new fields). This spec gives `Vote` its meaning,
turns grid checks and reveals into votes in help mode `vote`, extends `tick`,
`replay`, `snapshot_for` and `after_restart`, hides the help controls in help mode
`none`, and adds the vote banner to the room page. (Note from the lead, 2026-10-15:
`after_restart` added to the functions this spec extends, decision 16 (review of
spec 025))

### Help modes

| `settings.help_mode` | Checks of a letter or a word | Check of the grid, reveals |
| --- | --- | --- |
| `free` | applied at once (spec 023) | applied at once (specs 023, 024) |
| `vote` | applied at once, no vote | a vote first (below) |
| `none` | refused `help_disabled`; controls hidden | refused `help_disabled`; controls hidden |

A room starts in `free` (`DEFAULT_SETTINGS`, spec 011). The host picks the mode in
spec 014's settings form (`help-mode-select`), which the creator of a room sees
from the room's first snapshot, before anyone else joins. That moment is "at room
creation" (backlog AC-6.3.1): no step is added before the room exists, so spec
010's one-tap start stays (decisions 1 and 11). (Note from the lead, 2026-10-15:
"decision 1, open question 1" became "decisions 1 and 11", the human's answer.)

### `nock.room` additions

```python
# src/nock/room.py (additions; existing fields and signatures unchanged)
class RoomConfig(RoomModel):
    # ... fields of specs 011 to 037
    vote_timeout_seconds: int = Field(default=20, ge=1)   # spec 025 AC-2


class OpenVote(RoomModel):
    """The vote a room is holding (spec 025). Ballots are not in the log."""

    opened: VoteOpened               # the event that opened it; snapshots send it
    opened_at: float                 # clock time of the step that opened it
    eligible: tuple[PlayerId, ...]   # players not disconnected at the opening, in players order
    yes: tuple[PlayerId, ...]        # the requester first, then the yes ballots in order
    no: tuple[PlayerId, ...] = ()    # the no ballots in order


class RoomState(RoomModel):
    # ... fields of specs 011 to 026
    open_vote: OpenVote | None = None                         # spec 025
    last_vote_id: int = Field(default=0, ge=0, strict=True)   # vote_id of the last vote opened, 0 for none
```

`handle_message`, `tick`, `replay`, `snapshot_for` and `after_restart` keep their
signatures (spec 011). (Note from the lead, 2026-10-15: `after_restart` added,
decision 16 (review of spec 025))

### Server rule: a request that needs a vote

A request needs a vote when `settings.help_mode` is `vote` and it is a `Check`
whose target is `GridTarget()`, or any `Reveal`. A check of a letter or of a word
never needs one (the human's answer of 2026-10-14).

Spec 023's check rule and spec 024's reveal rule keep their refusal steps (solved,
help mode `none`, target, and for a reveal nothing to reveal and budget). After
them, a request that needs a vote, from player `p`:

1. A vote is open (after the expiry below): refused, `vote_in_progress`.
2. The eligible voters are the players whose `state` is not `disconnected`, in
   `players` order, `p` included. If `p` is the only one, the request is applied
   at once, as in `free` mode, with no vote event (decision 4).
3. Otherwise, with `s = state.seq`, the step opens a vote. One entry
   `VoteOpened(seq=s + 1, vote_id=state.last_vote_id + 1, player_id=p, request=<the Check or Reveal as received>, timeout_seconds=config.vote_timeout_seconds, eligible_voters=<their count>)`;
   `state.open_vote = OpenVote(opened=<that event>, opened_at=now, eligible=<their ids>, yes=(p,), no=())`;
   `state.last_vote_id` becomes that `vote_id`. Nothing else changes: no cell, no
   budget.

### Server rule: `Vote` in `nock.room.handle_message`

`Vote(vote_id, yes)` from joined player `v` is input (spec 013) and not an edit
(spec 037's rate limit does not count it). After the expiry below:

1. No vote is open, or `vote_id` is not the open vote's `vote_id`: refused,
   `no_open_vote`.
2. `v` is not in `eligible`, or is already in `yes` or in `no`: nothing happens (no
   entry, no reply). The requester is in `yes` from the start.
3. Otherwise `v` is added to `yes` (or `no`). Then, with `e = len(eligible)`:
   - `len(yes) * 2 > e`: the vote passes (below);
   - `(e - len(no)) * 2 <= e` (a majority of yes can no longer be reached): one
     entry `VoteClosed(seq, vote_id, outcome=rejected, yes_votes=len(yes), eligible_voters=e)`,
     and `open_vote = None`;
   - else nothing is logged, and `open_vote` keeps the ballot.

Majority examples: 2 eligible voters need 2 yes, 3 need 2, 4 need 3, 8 need 5. A
vote is rejected at once with 1 no out of 2, 2 no out of 3, 2 no out of 4.

When a vote passes, its request is checked again at `now`, as if its requester
sent it then: every refusal step of spec 023 (a check) or spec 024 (a reveal) runs
again, the help mode `none` included, and only the vote step is left out.

- If none refuses: one entry `VoteClosed(seq, vote_id, outcome=passed, yes_votes=len(yes), eligible_voters=e)`,
  `open_vote = None`, then the entries of the request exactly as spec 023 or spec
  024 makes them, with `player_id` the requester (`check_result` and its
  `cell_locked`, or `reveal_result` and its `cell_locked`), then spec 026's
  completion entry when it applies.
- If one refuses (meanwhile the grid was solved, the host set `none` or lowered the
  budget, or the target got locked): the vote closes `rejected` instead, with one
  `VoteClosed` entry holding `outcome=rejected` and the yes count, and nothing else
  happens; no error is sent (decisions 6 and 12). (Note from the lead, 2026-10-15:
  "decision 6, open question 2" became "decisions 6 and 12", the human's answer.)

### Expiry

An open vote expires at `opened_at + opened.timeout_seconds`. Once `now` is at or
past that time:

- `tick` closes it with one entry
  `VoteClosed(seq, vote_id, outcome=timed_out, yes_votes=len(yes), eligible_voters=e)`
  and `open_vote = None`. This step comes after spec 014's hand-over step.
- Before a `check`, a `reveal` or a `vote` is applied, the same step closes it the
  same way, with its entry first (after spec 013's wake-up entry, if any). The
  message is then applied with no vote open, so a late ballot gets
  `no_open_vote`.

### `snapshot_for`, `replay` and `after_restart`

- `snapshot_for` sends `open_vote = state.open_vote.opened` while a vote is open,
  else `None`.
- `replay` additions (spec 018 table):

  | Event | Effect on the state |
  | --- | --- |
  | `vote_opened` | `open_vote = OpenVote(opened=event, opened_at=entry.at, eligible=<ids of the players not disconnected in the state before the entry, in players order>, yes=(event.player_id,), no=())`; `last_vote_id = event.vote_id` |
  | `vote_closed` | `open_vote = None` |

  Ballots are not in the log, so `replay` does not restore them, as it does not
  restore selections (spec 018): a vote rebuilt from the log holds the requester's
  yes only.
- `after_restart` resets the ballots of an open vote: `open_vote` keeps its
  `opened` (so its `vote_id` and `request`), `opened_at` and `eligible`, and gets
  `yes=(opened.player_id,)` and `no=()`; `last_vote_id` is unchanged, and the reset
  adds no entry. Spec 018's `save_snapshot` stores the whole state, ballots
  included, while the log holds no ballot; with this reset, a room loaded from a
  snapshot and one rebuilt from the log alone hold the same vote, whenever the
  last snapshot was taken (decision 16). (Note from the lead, 2026-10-15: this
  sentence said "`after_restart` is unchanged"; a restart from a snapshot brought
  back ballots that a restart from the log lost (review of spec 025)) A vote open
  when the server stopped stays open with the requester's yes, and expires at its
  time (its `opened_at` is the time of its `vote_opened` entry, whether it comes
  from the snapshot or from the log). (Note from the lead, 2026-10-15: "its
  `opened_at` comes from the log" became "whether it comes from the snapshot or
  from the log", decision 16 (review of spec 025)) Once reconnected, the players
  whose page has not recorded a ballot for that vote (for example after a reload
  of the page, which empties `votedIds`) can vote again. A page that recorded a
  ballot keeps `vote-status` with `t("vote.cast")` and no button, although the
  server lost that ballot; this is accepted: the vote is decided by the other
  ballots, or closes `timed_out` at its usual time (decision 17). (Note from the
  lead, 2026-10-15: "The players, once reconnected, can vote again" became these
  two sentences, decision 17 (review of spec 025))

### Client: help mode on the room page

- While the kept settings' `help_mode` is `none`, `check-panel` (spec 023) and
  `reveal-panel` (spec 024) are absent from the page. This replaces spec 023's
  "all three are `disabled` while `help_mode` is `none`" (see "Edge cases and
  errors").
- While a vote is open, `check-grid`, `reveal-letter` and `reveal-word` are
  `disabled`; `check-letter` and `check-word` are not.

### Client: votes

`web/src/lib/roomSession.ts`:

```ts
// The open vote as the page keeps it (spec 025).
export interface VoteView {
  vote_id: number
  // The requester, who counts as a yes.
  player_id: string
  // What the vote is about, read from its request.
  kind: 'check_grid' | 'reveal_letter' | 'reveal_word'
}

export interface Snapshot {
  // ... fields of specs 040 to 024
  // From the snapshot's open_vote, then from vote_opened and vote_closed.
  open_vote: VoteView | null
}

export interface RoomSession {
  // ... fields of specs 040 to 024
  // The vote ids this page voted on, kept while the page is open
  // (reconnections included).
  votedIds: number[]
  // The vote that closed last, and how, shown for VOTE_RESULT_MS.
  closedVote: { vote_id: number; outcome: 'passed' | 'rejected' | 'timed_out' } | null
}

// How long the banner shows the result of a vote that closed.
export const VOTE_RESULT_MS = 3000
```

- A snapshot's `open_vote` (a `vote_opened` object or `null`) gives
  `snapshot.open_vote`. An applied `vote_opened` sets it; an applied `vote_closed`
  sets it to `null` and `closedVote` to its `vote_id` and `outcome`. A request of
  any other kind than the three above shows no banner.
- `data-testid="vote-banner"` shows while `snapshot.open_vote` is not `null` and
  the grid is not solved, and for `VOTE_RESULT_MS` after a vote closes, to show
  how it ended. It has `role="group"` and an `aria-labelledby` naming its
  `vote-question` or its `vote-result`. It holds:
  - while the vote is open, `data-testid="vote-question"` with the text
    `t("vote.question.<kind>", { name })`, where `name` is the requester's nickname
    (spec 013's known names; `t("feed.someone")` when unknown), inserted as text
    (spec 037 AC-4); then:
    - on the requester's page, `data-testid="vote-status"` with `t("vote.waiting")`;
    - on any other page that has not voted on this `vote_id`, the buttons
      `data-testid="vote-yes"` (text `t("vote.yes")`) and `data-testid="vote-no"`
      (text `t("vote.no")`). A click sends
      `{"type": "vote", "vote_id": n, "yes": true}` (or `false`) once, adds `n` to
      `votedIds`, and the buttons give way to `vote-status` with `t("vote.cast")`;
    - on a page that voted on it, `vote-status` with `t("vote.cast")`;
  - once the vote has closed, `data-testid="vote-result"` with
    `t("vote.result.<outcome>")`, for `VOTE_RESULT_MS`; a new `vote_opened` in
    that time replaces it at once.
- While the page's status is not `joined` (spec 017: for example `reconnecting`,
  while `connection-banner` shows), `vote-yes` and `vote-no` are shown `disabled`,
  so no ballot is dropped while the page shows it as cast. Once the status is
  `joined` again (the reconnection's snapshot still holding the vote), they are
  enabled, unless `votedIds` holds that vote's id, in which case `vote-status` with
  `t("vote.cast")` shows instead (decision 18). (Note from the lead, 2026-10-15:
  added; `send` drops a frame while no socket is open, so a ballot cast offline was
  lost while the page showed `t("vote.cast")` (review of spec 025))
- `data-testid="vote-announcement"`: an element with the class `visually-hidden`,
  `role="status"`, `aria-live="polite"` and `aria-atomic="true"`, on the page once
  it has a snapshot. Its text becomes the question when a vote opens and the result
  text when a vote closes, so a screen reader hears both.

Where the banner goes (spec 024's toolbar note: no spare height at 568 by 320):

- The banner is laid over the top of `grid-viewport`. Its box lies inside the
  viewport's box (1 px tolerance), and showing it changes no layout: the boxes of
  the room header, `grid-viewport`, `clue-bar` and, on touch screens, `keyboard`
  are the same with and without it (1 px tolerance). It covers part of the grid
  while it shows (decisions 9 and 15). (Note from the lead, 2026-10-15: "decision
  9, open question 5" became "decisions 9 and 15", the human's answer.)
- In document order it comes before the `grid` (spec 035: nothing focusable
  follows the grid), so after `Escape` on the grid, `Shift+Tab` reaches `vote-no`
  first.
- After `Enter` on, or a click on, `vote-yes` or `vote-no`, the buttons give way
  to `vote-status`, and the focus moves to `vote-status`, never to
  `document.body`. `vote-status` has `tabindex="-1"`, so it can take the focus
  without being a Tab stop. When the banner leaves the page while the focus is
  inside it (its result's `VOTE_RESULT_MS` is over, the grid is solved, or a new
  vote replaces it), the focus moves to the `grid` element (spec 035) (decision
  19). (Note from the lead, 2026-10-15: added (review of spec 025)) When the vote
  closes while the focus is inside the banner (on `vote-status`), the focus moves
  to the `grid` element at once, and the result is heard through
  `vote-announcement`; a banner showing `vote-result` holds nothing focusable
  (decision 19). (Note from the lead, 2026-10-15: this sentence said the case was
  open question 1; the lead answered option (a) (review of spec 025))
- `vote-yes` and `vote-no` are at least 24 by 24 CSS px, and
  `document.elementFromPoint` at the centre of each returns it.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `vote.question.check_grid` | `{name} propose de vérifier la grille.` |
| `vote.question.reveal_letter` | `{name} propose de révéler une lettre.` |
| `vote.question.reveal_word` | `{name} propose de révéler un mot.` |
| `vote.yes` | `Oui` |
| `vote.no` | `Non` |
| `vote.waiting` | `En attente des autres joueurs…` |
| `vote.cast` | `Vote enregistré.` |
| `vote.result.passed` | `Vote accepté.` |
| `vote.result.rejected` | `Vote refusé.` |
| `vote.result.timed_out` | `Temps écoulé, vote annulé.` |

### Test harness

- Rule unit tests: as spec 024. `V3` is a FX-01 room with players `p1` (host),
  `p2` and `p3` (seq 3 after the joins at `NOW`), where the host set the vote mode
  with `ChangeSettings(help_mode="vote", reveal_budget=RevealBudget(letters=5, words=1))`
  (seq 4). `tick` is called with `QUIET = RoomConfig(silence_timeout_seconds=600)`
  so that only the vote step acts.
- WebSocket tests: as spec 011. Timing criteria use
  `RoomRegistry(clock=fake_clock, config=RoomConfig(tick_seconds=0.05, max_edits_per_second=1000))`.
- "Browser with mocked socket" and "browser with live server": as spec 023. Vote
  frames are built with `VoteOpened` and `VoteClosed`. The live-server criteria
  never wait for a real 20 seconds: a timed-out vote is checked with the mocked
  socket and with the fake clock.
- The one-tap start (AC-1): spec 010's harness, with a catalogue holding FX-01 as
  published entry 1.
- Window sizes and contexts: as spec 024 (the eight sizes of spec 006 AC-5,
  desktop and touch contexts).
- Engines: every browser criterion runs in Chromium and WebKit locally and also
  Firefox in CI. No check of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-6.3.1) (WebSocket; browser with live server) The host picks the help mode, free, vote or none, from the moment the room exists; the room starts in free. WebSocket: a room created by `POST /api/rooms` gives its first joiner, the host (spec 012), a snapshot whose `settings.help_mode` is `free`; the host sends `change_settings` with `help_mode` `vote` before anyone else joins; a second client then joining gets a snapshot with `help_mode` `vote`, and a third, after the host's `change_settings` to `none`, one with `none`. Browser: on `/`, one click on the `catalogue-play` of item 1 (spec 010) opens the room as host; its `help-mode-select` has the value `free` and exactly the options `free`, `vote` and `none` in that order, with the texts of `fr.json["settings.help_mode.free"]`, `["settings.help_mode.vote"]` and `["settings.help_mode.none"]`; Ana selects `none` and clicks `settings-save`; a second context then opens the room link and joins as `Bob`: on both pages, neither `check-panel` nor `reveal-panel` exists.
- **AC-2** (AC-6.3.2) (rule unit test; WebSocket; browser with live server) In vote mode, a reveal or a grid check needs a yes from more than half of the connected players within 20 seconds; the requester counts as a yes. Rule: given `V3`, `p1`'s `Reveal(target=CellTarget(row=1, column=0))` at `NOW` gives exactly one entry, `VoteOpened(seq=5, vote_id=1, player_id="p1", request=Reveal(target=CellTarget(row=1, column=0)), timeout_seconds=20, eligible_voters=3)`, changes no cell and no budget, and leaves `open_vote` with `eligible=("p1", "p2", "p3")` and `yes=("p1",)`; then `p2`'s `Vote(vote_id=1, yes=True)` at `NOW + 19.9` gives `VoteClosed(seq=6, vote_id=1, outcome="passed", yes_votes=2, eligible_voters=3)`, `RevealResult(seq=7, player_id="p1", target=CellTarget(row=1, column=0), reveal_budget=RevealBudget(letters=4, words=1))` and `CellLocked(seq=8, row=1, column=0, letter="T", revealed=True)`, in that order, and `open_vote` is None. A grid check is voted the same way: `Check(target=GridTarget())` opens a vote whose `request` is that check, and once it passes the `check_result` (with `player_id` the requester) and its `cell_locked` follow the `vote_closed`. The majority counts the players connected at the opening: with 4 connected players a reveal passes with 3 yes and not with 2; with 2, it needs both; a `disconnected` player is not eligible and an `idle` one is. WebSocket: A (host), B and C join a FX-01 room in vote mode; A sends a reveal of (1, 0): A, B and C receive `vote_opened` with `eligible_voters` 3; B sends `{"type": "vote", "vote_id": 1, "yes": true}`: all three receive `vote_closed` (`passed`, 2 yes of 3), then `reveal_result`, then `cell_locked` (1, 0) `T` with `revealed` true, with consecutive seqs. Browser: Ana (host) and Bob join one FX-01 room, and Ana sets `vote` in the host panel; Ana taps (1, 0) and clicks `reveal-letter`: within 1 s both pages show `vote-banner`, whose `vote-question` reads `Ana propose de révéler une lettre.` (built from `fr.json`); Ana's banner shows `vote-status` with `fr.json["vote.waiting"]` and no `vote-yes`; Bob clicks `vote-yes`; within 1 s both pages show (1, 0) with `data-revealed="true"` and `data-letter="T"`, `reveal-letter` reading `Lettre (4)`, and `vote-result` reading `fr.json["vote.result.passed"]`.
- **AC-3** (AC-6.3.3) (rule unit test; WebSocket with a fake clock; browser with mocked socket) A vote that fails or times out changes nothing and spends no budget. Rule: in `V3`, after `p1`'s reveal of (1, 0) opened vote 1 (seq 5), `p2` and then `p3` send `Vote(vote_id=1, yes=False)`: the first gives no entry, the second gives `VoteClosed(seq=6, vote_id=1, outcome="rejected", yes_votes=1, eligible_voters=3)` only, and the state then equals `V3` except `seq` (6), `last_vote_id` (1) and the players' `last_seen_at` and `last_input_at`: the same cells, `reveal_budget` 5 letters and 1 word, `open_vote` None. In a second run, `tick(state, NOW + 19.9, QUIET)` adds nothing and `tick(state, NOW + 20.0, QUIET)` gives `VoteClosed(seq=6, vote_id=1, outcome="timed_out", yes_votes=1, eligible_voters=3)`, with the same unchanged cells and budget; `p2`'s `Vote(vote_id=1, yes=True)` at `NOW + 20.0` with no tick before closes the vote the same way, then is answered `no_open_vote`. A vote that passes when its request can no longer apply closes `rejected`: after vote 1 opened, the host `p1` sets the budget to 0 letters and 1 word (spec 014, seq 6), then `p2` votes yes: the only entry is `VoteClosed(seq=7, vote_id=1, outcome="rejected", yes_votes=2, eligible_voters=3)`, and (1, 0) stays empty. WebSocket: A, B and C join a FX-01 room in vote mode on a fake clock; A sends a reveal; after `advance(20)` each client receives `vote_closed` with outcome `timed_out` within 1 second of real time, nobody receives a `reveal_result`, and `room_state` keeps `reveal_budget` 5 letters and 1 word. Browser: given a FX-01 snapshot in vote mode with budget 5 letters and 1 word, when the mock sends `vote_opened` (seq 6, by `p2`, a reveal of (1, 0)) then `vote_closed` (seq 7, `rejected`), `vote-result` reads `fr.json["vote.result.rejected"]`, (1, 0) is unchanged, `reveal-letter` still reads `Lettre (5)`, and the banner is gone between 2,500 and 4,500 ms later; the same run with `timed_out` shows `fr.json["vote.result.timed_out"]`.
- **AC-4** (AC-6.3.4) (browser with mocked socket) In none mode, the check and reveal controls are hidden. Given a FX-01 snapshot whose `help_mode` is `none`: neither `check-panel` nor `reveal-panel` exists, while `room-toolbar` and `undo-button` do; after a `settings_changed` (seq 6) to `free`, both panels show with their buttons; after a `settings_changed` (seq 7) back to `none`, both are gone again; with `vote`, both show. On the server nothing changes: in `none` mode specs 023 and 024 answer any check or reveal with `help_disabled`.
- **AC-5** (new, from the human's answer of 2026-10-14) (rule unit test; browser with mocked socket) In vote mode, a check of a letter or of a word needs no vote. Rule: in `V3` where `p1` wrote `T` at (1, 0) and `X` at (1, 1), `p2`'s `Check(target=WordTarget(row=0, column=0, clue_index=0))` gives the `check_result` and `cell_locked` of spec 023 at once, with no `vote_opened`, and so does a `Check(target=CellTarget(row=1, column=1))`; while a vote is open (a reveal of (2, 2) by `p1`), both kinds of check are applied the same way and the vote stays open. Browser: given a FX-01 snapshot in vote mode with (1, 1) tapped, while a vote is open (the mock's `vote_opened`, a reveal by `p2`) `check-letter` and `check-word` are enabled and send their checks, while `check-grid`, `reveal-letter` and `reveal-word` are disabled; after the mock's `vote_closed`, all five are enabled again.
- **AC-6** (new) (rule unit test; WebSocket) One vote at a time, and one ballot per eligible player. In `V3` with vote 1 open (`p1`'s reveal of (1, 0)): `p2`'s `Check(target=GridTarget())` and `p3`'s `Reveal(target=WordTarget(row=0, column=2, clue_index=0))` are answered `vote_in_progress`; `Vote(vote_id=2, yes=True)` is answered `no_open_vote`; `p1`'s own `Vote(vote_id=1, yes=False)` changes nothing (no entry, no reply) and `yes` stays `("p1",)`; after `p2` voted no, a second ballot of `p2` (yes) changes nothing; a player `p4` who joined after the opening is not eligible, and their ballot changes nothing. Once the vote has closed, `Vote(vote_id=1, ...)` is answered `no_open_vote`, and a new request opens vote 2. A requester who is the only connected player (in a FX-01 room in vote mode with `p1` and `p2`, where `p2` is `disconnected`) gets the reveal at once: `reveal_result` and `cell_locked` with no `vote_opened`. Each refusal leaves the state as it was apart from the sender's `last_seen_at`, `last_input_at` and, if they were idle, their state and the seq raised by spec 013's wake entry, which a refusal does not undo. (Note from the lead, 2026-10-15: an idle sender is woken even when its message is refused, as spec 013's input rule and the code do.) WebSocket: a refusal reaches its sender only; the other clients receive nothing.
- **AC-7** (new) (browser with mocked socket) The vote banner shows the question to everyone, and the buttons to those who can still vote. Given a FX-01 snapshot in vote mode with players `p1` (`you`, `Ana`), `p2` (`Bob`) and `p3` (`Cy`): when the mock sends `vote_opened` (seq 6, `vote_id` 1, by `p2`, a reveal of the word `0,2,0`), `vote-banner` shows, `vote-question` reads `Bob propose de révéler un mot.` and `vote-announcement` holds the same text; clicking `vote-yes` sends one frame that parses to `Vote(vote_id=1, yes=True)`, and the buttons give way to `vote-status` reading `fr.json["vote.cast"]`; after the mock sends `vote_closed` (seq 7, `passed`), `vote-result` and `vote-announcement` read `fr.json["vote.result.passed"]`, and the banner is gone between 2,500 and 4,500 ms later. A first snapshot whose `open_vote` is a vote by `p1` shows `vote-status` with `fr.json["vote.waiting"]` and no button; one whose `open_vote` is by `p3` shows both buttons, and clicking `vote-no` sends `Vote(vote_id=..., yes=False)`. When the page has voted, the mock closes the socket with code 1011 and answers the next join with a snapshot holding the same `open_vote`: the banner shows `vote-status` with `fr.json["vote.cast"]` and no button. When the page has not voted (a first snapshot whose `open_vote` is by `p3`), the mock closes the socket with code 1011: before the mock answers the next join, `data-status` is `reconnecting` and `vote-yes` and `vote-no` are shown and `disabled`; once the mock answers it with a snapshot holding the same `open_vote`, both are enabled. (Note from the lead, 2026-10-15: added, decision 18 (review of spec 025)) A `grid_solved` while a vote is open hides the banner.
- **AC-8** (new) (browser with mocked socket) The vote banner never takes the grid's room, and it can be reached from the keyboard. Setup: spec 013 AC-6's (FX-01, `you` host among 8 players, 100 feed items, (3, 1) tapped), in vote mode; the test reads the boxes, then the mock sends `vote_opened` by `p2` (a grid check). At every window size of spec 006 AC-5, in desktop and touch contexts: the boxes of the room header, `grid-viewport`, `clue-bar` and, in the touch context, `keyboard` are the same as before the `vote_opened` (1 px tolerance); spec 013 AC-6's checks pass; `vote-banner` lies inside the box of `grid-viewport` (1 px tolerance); `vote-yes` and `vote-no` are each at least 24 by 24 CSS px, and `document.elementFromPoint` at the centre of each returns it (Note from the lead, 2026-10-22: since spec 041, the banner's text is set in Source Sans 3 and its buttons, which set no font, take their parent's size and family, so their widths and heights differ from before; the boxes are read after `document.fonts.ready`, and the muted labels of the disabled buttons reach 5.22:1 on the clue blue-grey). In a separate run with the same snapshot and `vote_opened` and no tap, at 1280 by 720 and at 568 by 320, keyboard only (spec 035's harness): after `tab_to` `grid`, `Escape` then `Shift+Tab` focuses `vote-no`, and `Shift+Tab` again focuses `vote-yes`, each with spec 035 AC-2's outline (Note from the lead, 2026-10-22: since spec 041, that outline is 2 px solid navy, where it was 3 px blue); `Enter` on `vote-yes` sends `Vote(vote_id=1, yes=True)`; then `vote-status` shows, has `tabindex="-1"` and is `document.activeElement` (not `document.body`); the mock then sends `grid_solved` (spec 026, the next seq): `vote-banner` is gone and `document.activeElement` is the `grid` element. At 1280 by 720, with the same snapshot and `vote_opened`, a click on `vote-no` sends `Vote(vote_id=1, yes=False)` and leaves `document.activeElement` on `vote-status`. (Note from the lead, 2026-10-15: added, decision 19 (review of spec 025)) At 1280 by 720 and at 568 by 320, keyboard only, with the same snapshot and `vote_opened`, after `Enter` on `vote-yes` (`vote-status` has the focus) the mock sends `vote_closed` (`passed`, the next seq): `vote-result` shows and `document.activeElement` is the `grid` element. (Note from the lead, 2026-10-15: added, the lead's answer (a) to open question 1, decision 19 (review of spec 025)) In the state before the ballot, at 1280 by 720 and 360 by 740, spec 035's contrast scan and language scan find no offending element. (Note from the lead, 2026-10-15: "In this state" became "In the state before the ballot", so that the scans still see the banner with its buttons, before the steps added above (review of spec 025))
- **AC-9** (new) (rule unit test; WebSocket) An open vote survives a reconnection and a reload. Rule: `snapshot_for` of `V3` with vote 1 open gives `open_vote` equal to vote 1's `VoteOpened` event (seq 5); replaying `V3`'s entries and the `vote_opened` from `new_room` gives an `open_vote` with the same `opened`, `opened_at` equal to that entry's `at`, `eligible=("p1", "p2", "p3")`, `yes=("p1",)` and `last_vote_id` 1; replaying a following `vote_closed` gives `open_vote` None; a ballot cast before the reload is not restored. Store (spec 018's harness, `RoomStore(tmp_path / "nock.sqlite3")`): the room `new_room` gives is recorded with `create_room`, and each step of `V3` and of vote 1 (`p1`'s reveal of (1, 0), seq 5) appends its entries; `p2`'s `Vote(vote_id=1, yes=False)` at `NOW + 1` adds no entry and leaves `no=("p2",)`, then `save_snapshot` stores that state; `load_room` still gives `no == ("p2",)`, and `after_restart(<that state>, NOW + 5)` gives an `open_vote` with `no == ()`, `yes == ("p1",)` and the same `opened`, `opened_at` and `eligible`, and `last_vote_id` 1, equal to the `open_vote` and `last_vote_id` that `load_room` then `after_restart` at `NOW + 5` give from a store holding the same entries and only the `create_room` snapshot (the log-only load). (Note from the lead, 2026-10-15: added, decision 16 (review of spec 025)) WebSocket: A, B and C join a FX-01 room in vote mode; A sends a reveal, which opens vote 1; B's socket closes and B joins again with its resume token: B's snapshot has `open_vote` with `vote_id` 1; B votes yes: every client receives the `vote_closed` (`passed`), the `reveal_result` and the `cell_locked`.

## Edge cases and errors

Spec 023 amendment (spec 023 is `done`; the lead makes the amendment before this
spec's tests are written): spec 023 says the three check buttons are `disabled`
while `help_mode` is `none`, and its AC-9 ends "When the mock then sends
`settings_changed` with `help_mode` `none`, all three buttons are disabled". AC-4
here hides `check-panel` instead. Before this spec's tests are written, the lead
amends spec 023's "Client: check controls" and the last sentence of its AC-9 with a
dated note. This spec's test-writer then updates the two tests of spec 023 that
check it
(`test_ac9_a_help_mode_none_in_the_snapshot_disables_all_three_buttons` and
`test_ac9_settings_changed_to_none_disables_all_three_buttons` in
`tests/test_spec_023_ac08_ac09_feed_and_controls.py`) (Note from the lead, 2026-10-15:
they were in `tests/test_spec_023_check.py` before the spec 023 tests were split into
one file per criterion group) before the implementer runs. Spec 023 AC-10's last
sentence (a word check in vote mode gives AC-1's result) still holds (AC-5 here).
(Note from the lead, 2026-10-15: the amendment concerns spec 023's "Client: check
controls" and its AC-9, and nothing else in spec 023. The test of spec 023 AC-10
for vote mode, `test_ac10_help_mode_vote_acts_as_free`, checks a word check and
still passes. The human's answers, decisions 11 to 15, change nothing in spec 023.
The lead makes the amendment before the test-writer of this spec starts, so that
this test-writer works from an amended spec 023.)

- Who may vote (AC-2, AC-6): the eligible set is fixed when the vote opens. A
  player who joins during the vote is not eligible; their page still shows the
  buttons, since a page cannot tell, and their ballot changes nothing. A player
  who disconnects stays eligible and can vote after reconnecting, within the time.
  A player who leaves or is removed keeps the ballot they cast, until a restart
  resets it like every ballot (decision 16). (Note from the lead, 2026-10-15:
  "until a restart resets it like every ballot" added (review of spec 025))
- The requester leaves (AC-2): the vote goes on; if it passes, the result carries
  the requester's id, and the feed names them from spec 013's known names.
- Settings changed during a vote (AC-3): `change_settings` works as spec 014 says.
  When the vote passes, the request is checked again: `none` or a spent budget
  makes it close `rejected`; `free` lets it apply.
- The grid solved during a vote (AC-3, AC-7): the vote stays open until it is
  rejected, times out, or passes and then closes `rejected` (the grid is solved);
  the page hides the banner once the grid is solved.
- A target locked during a vote (AC-3): for example, a letter check locks the
  cell a reveal vote is about; once the vote passes, the reveal finds nothing to
  reveal and the vote closes `rejected`.
- One voter (AC-6): a requester alone among connected players is a majority of
  one, so the request applies at once, with no vote event and no banner.
- Expiry at 20 seconds (AC-3): a ballot at `opened_at + 19.9` counts; at
  `opened_at + 20.0` the vote has expired. The hub ticks every second (spec 011),
  so with the real clock a vote nobody answers closes between 20 and 21 seconds
  after it opened.
- A room with no connection (AC-3): its task stops (spec 011); the vote expires at
  the first tick of the next task, before any input.
- Restart (AC-7, AC-9): ballots cast before a restart are lost, after a crash or a
  clean stop alike, and whether the room is loaded from a snapshot or from the log
  alone: `after_restart` leaves the requester's yes only (decision 16). The vote
  expires at its time. A page that recorded its ballot still shows
  `t("vote.cast")`, so its player cannot vote again from that page; the vote is
  decided by the other ballots, or closes `timed_out` (decision 17). (Note from the
  lead, 2026-10-15: this item said "ballots cast before a crash are lost; the vote
  keeps the requester's yes"; a clean stop saves a snapshot holding the ballots,
  which `after_restart` now resets too (review of spec 025))
- Votes and the feed (AC-2): spec 013 adds no line for votes; a passed vote's
  `check_result` or `reveal_result` adds its usual line, with the requester's name.
- Votes, input and rate (AC-6): a ballot is input (it wakes an idle player, spec
  013); neither a ballot nor a request is counted by spec 037's rate limit.
- Help mode `none` with a vote open (AC-4): the panels are hidden, and the banner
  still shows the open vote, which will close `rejected` if it passes.
- Names (AC-7): the requester's nickname is inserted as text (spec 037 AC-4).

## Out of scope

- Generated hints and dictionary lookups (epic E6).
- Check a letter, a word or the grid: spec 023.
- Reveal a letter or a word: spec 024.
- Completion detection: spec 026.
- A choice of help mode before the room exists, in the catalogue or in the
  creation request (decision 11). (Note from the lead, 2026-10-15: "open question
  1" became "decision 11", the human's answer.)
- Showing the tally while a vote is open (spec 039 has no ballot event), a
  countdown (the snapshot does not carry the opening time), changing a ballot,
  cancelling a vote.
- Votes on letter or word checks, or on anything else (removing a player,
  settings).
- A visible sign of the help mode for players who are not host (spec 013's feed
  line announces each change).
- Keyboard shortcuts for votes.

## Work packages

None.

## Decisions

Proposed in the Phase 6 refine of 2026-10-14 and approved by the human with the
spec. Each one is already part of the spec above. Items 1, 4, 5, 6 and 9 were also
open questions: the human's answers to them are items 11 to 15 below.

1. "At room creation" is the host panel of spec 014, shown to the creator from the
   room's first snapshot; the room starts in `free`. Nothing is asked before the
   room exists, which keeps spec 010's one-tap start.
2. Which requests are voted: a check of the grid and every reveal; a check of a
   letter or a word never (the human's answer of 2026-10-14).
3. The majority: more than half of the players connected (active or idle) when the
   vote opens, the requester counted as a yes. The vote closes as soon as the
   outcome is sure: passed at a majority of yes, rejected once a majority can no
   longer be reached.
4. A requester alone gets the request at once, with no vote events.
5. One vote at a time (`vote_in_progress`); one ballot per eligible player, and
   any other ballot changes nothing; a ballot for another `vote_id` gets
   `no_open_vote`.
6. A vote that passes when its request can no longer apply closes `rejected`, and
   nothing else happens.
7. Expiry in `tick` and before a check, a reveal or a ballot, so the 20 seconds
   are exact in rule tests. The timeout is the event's `timeout_seconds`, from
   `RoomConfig.vote_timeout_seconds` (default 20, the backlog value).
8. Ballots are not logged, since spec 039 has no event for them; `replay` rebuilds
   an open vote with the requester's yes. No protocol change.
9. The banner is laid over the top of the grid viewport, so it costs no height on
   small windows, and it comes before the grid in document order.
10. `none` mode hides both help panels (AC-4); spec 023's "disabled" rule is
    amended.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question. Each one is already part of the spec above.

11. "At room creation the host picks a help mode" (former open question 1).
    Options: the host panel's select, shown to the creator from the first
    snapshot, with the room starting in `free`; or a choice before the room
    exists, next to the catalogue's `Jouer` button or in `POST /api/rooms`, which
    adds a step to spec 010's one-tap start. Pick: the host panel's select
    (decision 1).
12. A vote that passes when its request can no longer apply: the grid solved, the
    host set `none` or lowered the budget, the target locked meanwhile (former open
    question 2). Options: it closes `rejected` and nothing happens; it closes
    `passed` and nothing happens; or the host cannot change the settings while a
    vote is open, and the solving step closes the vote. Pick: it closes `rejected`
    and nothing happens (decision 6).
13. A requester who is the only connected player (former open question 3). Options:
    the request applies at once with no vote events; or a vote of one opens and
    passes in the same step, which shows a banner for nothing. Pick: it applies at
    once (decision 4).
14. Who votes, and how often (former open question 4). Options: the players
    connected when the vote opens, one ballot each that cannot be changed; also
    players who join during the vote; or ballots that can be changed until the vote
    closes. Pick: the players connected at the opening, one unchangeable ballot
    each (decision 5).
15. Where the vote shows (former open question 5). Options: a banner over the top
    of the grid, which covers part of the grid for at most 20 seconds and changes
    no layout; or a row above the grid, which pushes the grid down and breaks spec
    013 AC-6 at 568 by 320. Pick: the banner over the grid (decision 9).

Decided by the lead on 2026-10-15 after the review, under the owner's delegation
of technical and accessibility choices. Each one is already part of the spec
above. (Note from the lead, 2026-10-15: this group, items 16 to 19, added (review
of spec 025))

16. Restart (blocking review finding). `save_snapshot` (spec 018) stores the whole
    room state, ballots included, so a restart from a snapshot brought back ballots
    that a restart from the log lost, and the result of a reload depended on when
    the last snapshot was taken. Rule: `after_restart` resets an open vote's
    ballots to the requester's yes only (`yes=(requester,)`, `no=()`), keeping its
    id, request, opening time and eligible voters, so a room loaded from a snapshot
    and one rebuilt from the log alone give the same vote (AC-9). (Note from the
    lead, 2026-10-15: added (review of spec 025))
17. A page that voted keeps `t("vote.cast")` across reconnections (`votedIds` is
    kept, as before), because a reconnection without a server restart keeps the
    ballot on the server. After a server restart the ballot is lost while the page
    still shows it as cast; this is accepted: the vote is decided by the other
    ballots, or closes `timed_out` at its usual time. The players who can vote
    again are those whose page has not recorded a ballot for that vote, for
    example after a reload of the page (AC-7, AC-9). (Note from the lead,
    2026-10-15: added (review of spec 025))
18. Ballots offline. While the page's status is not `joined` (for example
    `reconnecting`, under spec 017's offline banner), `vote-yes` and `vote-no` are
    disabled, so no ballot is dropped while the page shows it as cast; they are
    enabled again once the page is joined, unless the page has recorded a ballot
    for that vote (AC-7). (Note from the lead, 2026-10-15: added (review of spec
    025))
19. Focus (spec 035). After `Enter` or a click on `vote-yes` or `vote-no`, the
    buttons give way to `vote-status`, and the focus moves to `vote-status` (which
    has `tabindex="-1"`), never to `document.body`. When the banner leaves the page
    while the focus is inside it (the result's time is over, the grid is solved, or
    a new vote replaces it), the focus moves to the `grid` element (AC-8). (Note
    from the lead, 2026-10-15: added (review of spec 025)) When the vote closes
    while the focus is inside the banner (on `vote-status`), the focus moves to
    the `grid` element at once, and the result is heard through
    `vote-announcement` (AC-8). Options were (a) this, or (b) `vote-result` taking
    the focus until the banner leaves; (a) moves the focus once, never on a timer,
    and a screen reader does not read the result twice. (Note from the lead,
    2026-10-15: added, the lead's answer (a) to the former open question 1 (review
    of spec 025))

## Open questions

None. (Note from the lead, 2026-10-15: the open question on the focus when a vote
closes, raised during the review, was answered (a) and folded into decision 19
and AC-8 (review of spec 025))
