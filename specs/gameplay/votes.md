---
area: gameplay
file: votes
status: done
---

# gameplay/votes - The group vote on help and its banner

## Purpose

In help mode `vote`, a check of the grid or a reveal applies only once more than
half of the players present agree. The server opens the vote, counts the ballots
and closes it; every page shows the banner that asks the question and tells the
result.

## Depends on

- `gameplay/hints.md`: the help modes, the requests and their refusal steps, the
  Aide items disabled while a vote is open.
- `platform/realtime.md`: the messages, their error codes, what a browser may
  receive.
- `social/chat.md`: the stream the `vote` line goes to.

## Rules

### The vote

1. After `gameplay/hints.md` rule 2's steps, a request that needs a vote is
   refused `vote_in_progress` while a vote is open, and applies at once when its
   sender is the only connected player. Otherwise it opens a vote and changes
   nothing else: one `vote_opened` (next vote id, requester, request, 20
   seconds, number of eligible voters), which adds no stream line. The eligible
   voters are the players not disconnected when it opens (idle ones count), the
   requester being a yes. The set never changes: a later joiner is not eligible,
   and a voter who leaves or is removed keeps their ballot.
2. A ballot on no open vote, or on another id, gets `no_open_vote`; one from a
   player who is not eligible, or has voted, is ignored without reply. The vote
   passes once the yes are more than half of the eligible voters, and is
   rejected once that cannot happen: 2 voters need 2 yes, 3 need 2, 4 need 3.
3. A vote that passes runs its request again through `gameplay/hints.md` rule
   2's steps: refused, it closes `rejected` and nothing else happens; else
   `vote_closed` (`passed`) comes first, then the request's entries in the
   requester's name.
4. A vote expires 20 seconds after it opened: the room's tick, the next ballot,
   or the next check or reveal not dropped (closing it first), closes it
   `timed_out`. A vote that does not pass changes no cell and no budget.
5. Snapshots carry the open vote. Ballots are not logged: after a server restart
   an open vote keeps its id, request, opening time and voters, and only the
   requester's yes.

### The vote banner

6. Every page shows the banner while a vote is open and the grid is not solved,
   before the grid in document order; a vote on any request but a grid check or
   a reveal shows none. It holds `vote.question.<kind>` with the requester's
   name (« Quelqu'un » when unknown), as text; then « Oui » and « Non », or
   `vote.waiting` on the requester's page, or `vote.cast` once this page voted
   on that id (remembered while the page is open). The buttons are disabled
   while the page is not joined; a focus on one of them goes to the grid, the
   selection unchanged, before they are. A ballot moves the focus to the line
   that replaces them.
7. For a vote whose `vote_opened` the page applied, the banner shows the seconds
   left (`vote.seconds_left`) and a bar, on the page's own clock, kept across a
   reconnection, down to « 0 s ». A vote known only from a snapshot has neither.
8. On `vote_closed` the banner leaves within 300 ms. A hidden live region
   announces the question when a vote opens, and `vote.result.<outcome>` when
   this page applies its close. The close adds one `vote` line to the stream
   (`social/chat.md`), before the lines of a passed request, and a 3-second note
   of it while the stream is hidden (`client/room.md`); that note replaces any
   note held back during the vote. The `vote` line lights neither the Salon dot
   nor the unread count; chat messages sent during the vote still count. A
   snapshot or a catch-up adds no `vote` line.
9. A focus inside the banner when it leaves goes to the grid.

### Look

The banner, `_design/overlays.md`, « Vote », on its layer of `_design/room.md`,
« Layers ».

## Acceptance criteria

- **AC-1** With Ana, Bob and Cy connected in `vote`, Ana's reveal of (1, 0)
  opens vote 1 with 3 voters and changes nothing; Bob's yes 19.9 seconds later
  closes it `passed`, 2 of 3, then reveals `T` in Ana's name; the pages, which
  read « Ana propose de révéler une lettre. », show `T` revealed, « 4 restantes »
  and the line « Vote accepté. ». A passed reveal by Bob, even after Bob left,
  reads « Bob a révélé une lettre », and a passed grid check gives a
  `check_result` in the requester's name. With 4 connected, 2 yes leave the vote
  open and 3 pass it. (← 025 AC-2)
- **AC-2** Vote 1 closes `rejected`, 1 of 3, at the second no, or `timed_out` at
  20 seconds, by a tick or before a late ballot, which gets `no_open_vote`; a yes
  after the host set 0 letters closes it `rejected`, 2 of 3. The budget stays,
  (1, 0) stays empty, and the page drops the banner within 300 ms and announces
  « Vote refusé. » or « Temps écoulé, vote annulé. ». (← 025 AC-3)
- **AC-3** While vote 1 is open, a grid check or a reveal is
  `vote_in_progress`, a word check applies at once and the vote stays open, and
  the page disables « Vérifier » grid and both reveals until the close; a ballot
  on vote 2 is `no_open_vote`; the requester's, a second, or a later joiner's
  ballot is ignored; a player alone connected reveals at once. (← 025 AC-5,
  025 AC-6)
- **AC-4** Bob reconnects during vote 1: his snapshot holds it and his yes
  passes it; after Bob's no and a restart, the vote holds Ana's yes only, loaded
  from a snapshot or from the log. (← 025 AC-9)
- **AC-5** On a vote by Bob, Ana's page reads « Bob propose de révéler un mot. »
  and announces it; « Oui » sends one yes and gives way, focused, to « Vote
  enregistré. En attente des autres joueurs… », kept after a reconnection; the
  requester's page reads « En attente des autres joueurs… »; an unvoted page's
  buttons are disabled while reconnecting and enabled once joined; `grid_solved`
  hides the banner. (← 025 AC-7, 047 AC-3)
- **AC-6** A vote the page saw open reads « 20 s » with a full bar, « 15 s » and
  three quarters 5 seconds later, « 0 s » and an empty bar at 20 seconds, then
  stays until `vote_closed`, alike with reduced motion; after a reconnection it
  never reads « 20 s » again; a vote from a first snapshot has no count and no
  bar. (← 047 AC-2)
- **AC-7** `vote_closed` `passed` removes the banner within 300 ms, announces
  « Vote accepté. » and ends the stream with that line, shown as the one note
  while the stream is hidden, even after two chat messages during the vote, and
  as no note while it shows; a vote a snapshot dropped is never announced and
  adds no line. (← 047 AC-4, 047 AC-5)
- **AC-8** At every window of `product.md`, opening the banner moves no box of
  the room, and « Oui » and « Non » meet the target size and are hit at their
  centre; on a phone and a computer the banner follows its design section; from
  the grid, Escape then Shift+Tab reaches « Non » then « Oui »
  with the ring inside the banner, and a close or a solve sends the focus from
  the banner to the grid; its states pass the scans of `product.md`, and
  `fr.json` holds the vote texts. (← 025 AC-8, 047 AC-1, 047 AC-13, 047 AC-14)
- **AC-9** On Bob's vote, Ana's unvoted page has « Oui » focused and (1, 0)
  selected; her socket closes: once « Oui » and « Non » are disabled the focus
  is on the grid, (1, 0) still selected, and no ballot was sent. « Non »
  focused does the same.

## Edge cases

- A player who joins during a vote sees the buttons; the ballot is ignored
  (AC-3).
- A requester who leaves: the vote goes on, and a pass is in their name (AC-1).
- `none` set during a vote hides the Aide groups (`gameplay/hints.md` AC-12)
  and keeps the banner; a pass then closes `rejected` (AC-2).
- After a restart, a page that recorded its ballot still reads `vote.cast`; the
  others decide, or the vote times out (AC-4, AC-5).
- A check dropped after a vote's 20 seconds leaves the vote open for the tick
  to close (AC-2; `gameplay/hints.md` AC-23).

## Out of scope

- A tally of ballots, changing a ballot, votes on anything but a grid check or a
  reveal, keyboard shortcuts.
- The requests, their refusal steps, the hint limit, the budget and the Aide
  items: `gameplay/hints.md`. The help mode setting: `lobby/host.md`. « Réagir »
  under the banner: `client/hud.md`; the notes: `client/room.md`. The stream and
  its lines' look: `social/chat.md`. Protocol: `platform/realtime.md`.
  Completion: `gameplay/rules.md`.

## Code

- `src/nock/room.py`: votes, `tick`, `replay`, `snapshot_for`, `after_restart`;
  `RoomConfig` holds the vote time.
- `src/nock/protocol.py`: the vote messages and error codes.
- `web/src/lib/RoomPage.svelte` (the banner), `web/src/lib/roomSession.ts`,
  `web/src/lib/voteCountdown.ts`, `web/src/lib/activityFeed.ts` (the `vote`
  line).
- Tests: `tests/test_spec_025_ac02_*`, `test_spec_025_ac03_*`,
  `test_spec_025_ac04_ac05_*` (its AC-5 tests), `test_spec_025_ac06_*` to
  `..._ac09_*`, `test_spec_047_ac01_ac03_*`, `..._ac02_*`, `..._ac04_*`,
  `..._ac13_*`, `..._ac14_*`, `test_votes_*`.
