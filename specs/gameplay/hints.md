---
area: gameplay
file: hints
status: approved
---

# gameplay/hints - Check, reveal and the vote on help

## Purpose

A stuck group can check its letters or reveal the right ones. The server decides
and the whole room sees the result, within the limits the host sets: a help mode,
a reveal budget and, in vote mode, a majority of the players. Each player may
ask only a few times in a short while.

## Depends on

- `gameplay/board.md`: letter cells, the selection and its word, pending edits.
- `lobby/host.md`: the host settings, which set the help mode and the allowance.
- `platform/realtime.md`: the messages, their error codes, what a browser may
  receive.

## Rules

### Help modes

1. A room's help mode is `free` (a new room), `vote` or `none`, set by the host
   from the room's first snapshot. `free`: every check and reveal applies at
   once. `vote`: a check of a letter or a word applies at once; a check of the
   grid and every reveal need a vote (rule 14). `none`: every check and reveal is
   refused, and no page shows the « Vérifier » and « Révéler » groups.

### Requests

2. A check, a reveal or a ballot is input (it wakes an idle player,
   `social/presence.md`); the edit rate limit counts none of them. A check or a
   reveal, whatever its target, meets the hint limit first: when its sender
   already has `RoomConfig.hint_limit` (5) counted requests in the last
   `hint_window_seconds` (10) seconds (sliding: those after now − 10), it is
   dropped. A dropped request gets no reply, adds no entry, closes no expired
   vote and changes nothing but the sender's presence. A request counts when it
   is applied at once or opens a vote; a dropped or refused one does not, nor a
   ballot, which no limit holds back, nor the request of a vote that passes.
   Each player has their own window, never logged; a restart empties them all.
   Then the first step that applies refuses a check or a reveal:
   1. the grid is solved: `grid_solved`;
   2. help mode `none`: `help_disabled`;
   3. a letter target that is not a letter cell: `not_a_letter_cell`; a word
      target whose cell is outside the grid or not a clue cell, or whose clue
      index is not one of that cell's: `invalid_target`;
   4. a reveal with nothing left to reveal (its cell, or every cell of its word,
      locked): `invalid_target`;
   5. a reveal whose kind of budget is 0: `budget_exhausted`.

   A refusal is one error to its sender only; it adds no entry of its own and
   changes nothing but the sender's presence.

### Check

3. A check's scope is its cell, its word's cells in reading order, or every
   letter cell row by row. Locked, empty and pencil cells are left out; each
   other cell is compared, on the server, with its solution letter.
4. An accepted check sends every player one `check_result` (checker, target,
   right and wrong cells in scope order), then one `cell_locked` per right cell,
   on consecutive seqs. Right cells are locked, wrong ones marked wrong; both
   keep their letter and author. An empty result is still logged. The stream
   gets one line `feed.check.<scope>` naming the checker.
5. A wrong mark lasts until an accepted edit or undo of the cell, or a lock. A
   page strikes a wrong letter only while the cell shows its confirmed letter.

### Reveal

6. A reveal takes its cell, or its word's unlocked cells in reading order. Each
   gets its solution letter, whatever it held, and is locked and revealed, with
   no author, no wrong mark and no pencil.
7. An accepted reveal sends every player one `reveal_result` (revealer, target,
   budget left), then one revealed `cell_locked` per cell, then, when the grid
   fills, the completion entry of `gameplay/rules.md` (flag-clearing entries of
   `gameplay/co-op.md` may come before it). The stream gets one line
   `feed.reveal.<scope>` naming the revealer. A check or reveal applied by a vote
   names the requester, even one who has left.
8. The allowance is 5 letters and 1 word by default. A letter reveal costs one
   letter; a word reveal one word, whatever its length. The room counts its
   accepted reveals of each kind, across reloads (a stored state without the
   count counts 0); what is left is, per kind, the allowance less that count,
   never below 0. Pages see only what is left and the allowance.
9. A revealed letter is earned at its cell by its `cell_locked`: no HTTP body, no
   earlier frame and no snapshot of a lower seq shows it there.

### The Aide items

10. While the help mode is not `none`, the Aide menu (`client/hud.md`) holds the
    group « Vérifier » (`check.letter`, `check.word`, `check.grid`), then
    « Révéler » (`reveal.letter`, `reveal.word`). A reveal item's detail says
    what is left: `reveal.letters_left` (`_one` at 1), `reveal.letter_none` at
    0, the same for words. An item's name is its visible text.
11. An item sends its request once, for the selected cell, the selected word's
    clue or the grid, and closes the menu; it moves no selection and guesses no
    result. The request goes after the edits pending when it was made and
    before any later one: kept while the page is not joined, queued behind a
    resend (`platform/realtime.md` rules 20 and 22). An error answering it
    changes nothing on the page.
12. Disabled: « Vérifier » letter or word while nothing is selected; « Révéler »
    letter while nothing is selected, the cell is locked or no letter is left;
    « Révéler » word while nothing is selected, its cells are all locked or no
    word is left; every item once the grid is solved; « Vérifier » grid and both
    reveals while a vote is open. A reveal item disabled at 0 keeps its text
    readable.
13. A revealed cell is a locked cell with the revealed notch and the hidden text
    `a11y.revealed`; a cell locked by a check has neither. A flash on the cell
    (`gameplay/co-op.md`) keeps its whole time.

### Votes

14. After rule 2's steps, a request that needs a vote is refused
    `vote_in_progress` while a vote is open, and applies at once when its sender
    is the only connected player. Otherwise it opens a vote and changes nothing
    else: one `vote_opened` (next vote id, requester, request, 20 seconds, number
    of eligible voters), which adds no stream line. The eligible voters are the
    players not disconnected when it opens (idle ones count), the requester being
    a yes. The set never changes: a later joiner is not eligible, and a voter who
    leaves or is removed keeps their ballot.
15. A ballot on no open vote, or on another id, gets `no_open_vote`; one from a
    player who is not eligible, or has voted, is ignored without reply. The vote
    passes once the yes are more than half of the eligible voters, and is
    rejected once that cannot happen: 2 voters need 2 yes, 3 need 2, 4 need 3.
16. A vote that passes runs its request again through rule 2's steps: refused,
    it closes `rejected` and nothing else happens; else `vote_closed`
    (`passed`) comes first, then the request's entries in the requester's name.
17. A vote expires 20 seconds after it opened: the room's tick, the next
    ballot, or the next check or reveal not dropped (closing it first), closes
    it `timed_out`. A vote that does not pass changes no cell and no budget.
18. Snapshots carry the open vote. Ballots are not logged: after a server
    restart an open vote keeps its id, request, opening time and voters, and only
    the requester's yes.

### The vote banner

19. Every page shows the banner while a vote is open and the grid is not solved,
    before the grid in document order; a vote on any request but a grid check or
    a reveal shows none. It holds `vote.question.<kind>` with the
    requester's name (« Quelqu'un » when unknown), as text; then « Oui » and
    « Non », or `vote.waiting` on the requester's page, or `vote.cast` once this
    page voted on that id (remembered while the page is open). The buttons are
    disabled while the page is not joined; a focus on one of them goes to the
    grid, the selection unchanged, before they are. A ballot moves the focus to
    the line that replaces them.
20. For a vote whose `vote_opened` the page applied, the banner shows the seconds
    left (`vote.seconds_left`) and a bar, on the page's own clock, kept across a
    reconnection, down to « 0 s ». A vote known only from a snapshot has neither.
21. On `vote_closed` the banner leaves within 300 ms. A hidden live region
    announces the question when a vote opens, and `vote.result.<outcome>` when
    this page applies its close. The close adds one `vote` line to the stream
    (`social/chat.md`), before the lines of a passed request, and a 3-second note
    of it while the stream is hidden (`client/room.md`); that note replaces any
    note held back during the vote. The `vote` line lights neither the Salon dot
    nor the unread count; chat messages sent during the vote still count. A
    snapshot or a catch-up adds no `vote` line.
22. A focus inside the banner when it leaves goes to the grid.

### Look

The Aide groups, `_design/room.md`, « Aide menu »; the strike and the notch,
`_design/cells.md`, « Letter marks »; the banner, `_design/overlays.md`, « Vote »,
on its layer of `_design/room.md`, « Layers ».

## Acceptance criteria

- **AC-1** In FX-01 with `T`, `X`, `I`, `S` at (1, 0), (1, 1), (1, 3), (1, 4) and
  `V`, `Q` at (2, 1), (2, 2), a check of TAMIS gives every player right (1, 0),
  (1, 3), (1, 4) and wrong (1, 1), then three `cell_locked`, and a later joiner
  sees them locked and (1, 1) wrong with `X`; from the same start the grid gives
  right (1, 0), (1, 3), (1, 4), (2, 1) and wrong (1, 1), (2, 2), MIME only (2, 2)
  wrong, the empty (1, 2) an empty result. (← 023 AC-1, 023 AC-2, 023 AC-3,
  023 AC-6)
- **AC-2** Ana types `T`, `X` from (1, 0) and checks the word: on her page and
  Bob's, `X` is struck, (1, 0) locked and not struck, and the stream reads « Ana
  a vérifié un mot »; Bob's letter then grid checks add « Bob a vérifié une
  lettre » and « Bob a vérifié la grille ». (← 023 AC-4, 023 AC-8)
- **AC-3** A struck `X` at (1, 1) loses its strike when another player's `A`
  replaces it, a struck (2, 2) when a reveal locks it, and a typed `B` shows
  unstruck while it waits for the server. (← 023 AC-5)
- **AC-4** Bob types `X` at (1, 1), Ana reveals it: every player gets 4 letters
  and 1 word left, then `A` revealed, shown locked with no author, the stream
  reads « Ana a révélé une lettre », and Bob's `B` there changes nothing; a
  reveal of TAMIS after a check locked (1, 0) locks the other four; with the
  17 other letters right, a reveal of (4, 4) is followed by `grid_solved`, by
  `grid_full_wrong` if one is wrong. (← 024 AC-1, 024 AC-6)
- **AC-5** A new room has 5 letters and 1 word; a sixth letter reveal is
  `budget_exhausted`; a word reveal leaves the letters. After 3 letter reveals
  and MIME, the allowance set to 1 and 0 leaves 0 and 0, then 5 and 1 leaves 2
  and 0, not 4 and 1, and so does the room reloaded from its log alone or from a
  snapshot. (← 024 AC-2, 024 AC-10)
- **AC-6** With 5 letters and 1 word left the details read « 5 restantes » and
  « 1 restant », then « 4 restantes » after a reveal; at 0 letters « Révéler »
  letter is disabled, reads « Plus de lettre », sends nothing and keeps the text
  contrast of `product.md`, and the word item stays enabled.
  (← 024 AC-2, 024 AC-3)
- **AC-7** In a full game with a grid check after three wrong letters and
  reveals of (4, 4) and MIME, no payload to a browser shows an unearned letter: a
  player who joined before the reveals gets no letter at (4, 4) or MIME's empty
  cells, one who joined after gets them revealed; a check after `A` replaced `X`
  at (1, 1) finds it right. (← 023 AC-7, 024 AC-5)
- **AC-8** In `none` any check or reveal is `help_disabled`; in `free` a letter
  target on the clue (0, 0) is `not_a_letter_cell`, a word target on (1, 0) or a
  reveal of a revealed cell `invalid_target`, a reveal at 0 letters
  `budget_exhausted`; each reaches its sender only and changes nothing. In `vote`
  a word check gives AC-1's result. (← 023 AC-10, 024 AC-4)
- **AC-9** A revealed (1, 0) has the notch and « lettre révélée », a (1, 1)
  locked by a check neither; the notch keeps the contrast of `product.md`,
  selected or not and during a flash in each player colour, the flash still
  running; the page passes the scans, and Tab reaches both reveal items with the
  focus ring. (← 024 AC-9)
- **AC-10** With nothing selected only « Vérifier » grid is enabled, and it sends
  a grid check; after two taps on (2, 2) (MIME) the four others send that cell or
  MIME, leaving the selection and the cells as they were; a locked (2, 2)
  disables « Révéler » letter, a locked MIME « Révéler » word, `grid_solved`
  every item. (← 023 AC-9, 024 AC-7)
- **AC-11** With the Aide menu open, at every window of `product.md` in desktop
  and touch contexts, the menu lies in the window, each of the five items is hit
  at its centre, the grid keeps the room `client/hud.md` gives it, and Tab walks
  the five in order with the focus ring inside the menu. (← 024 AC-8)
- **AC-12** A room started from the catalogue is `free`, with the choices free,
  vote, none in that order; once the host sets `none`, every page, a later
  joiner's too, has no « Vérifier » or « Révéler » but keeps « Aide » and undo;
  `free` or `vote` brings both back. (← 025 AC-1, 025 AC-4)
- **AC-13** With Ana, Bob and Cy connected in `vote`, Ana's reveal of (1, 0)
  opens vote 1 with 3 voters and changes nothing; Bob's yes 19.9 seconds later
  closes it `passed`, 2 of 3, then reveals `T` in Ana's name; the pages, which
  read « Ana propose de révéler une lettre. », show `T` revealed, « 4 restantes »
  and the line « Vote accepté. ». A passed reveal by Bob, even after Bob left,
  reads « Bob a révélé une lettre », and a passed grid check gives a
  `check_result` in the requester's name. With 4 connected, 2 yes leave the vote
  open and 3 pass it. (← 025 AC-2)
- **AC-14** Vote 1 closes `rejected`, 1 of 3, at the second no, or `timed_out` at
  20 seconds, by a tick or before a late ballot, which gets `no_open_vote`; a yes
  after the host set 0 letters closes it `rejected`, 2 of 3. The budget stays,
  (1, 0) stays empty, and the page drops the banner within 300 ms and announces
  « Vote refusé. » or « Temps écoulé, vote annulé. ». (← 025 AC-3)
- **AC-15** While vote 1 is open, a grid check or a reveal is
  `vote_in_progress`, a word check applies at once and the vote stays open, and
  the page disables « Vérifier » grid and both reveals until the close; a ballot
  on vote 2 is `no_open_vote`; the requester's, a second, or a later joiner's
  ballot is ignored; a player alone connected reveals at once. (← 025 AC-5,
  025 AC-6)
- **AC-16** Bob reconnects during vote 1: his snapshot holds it and his yes
  passes it; after Bob's no and a restart, the vote holds Ana's yes only, loaded
  from a snapshot or from the log. (← 025 AC-9)
- **AC-17** On a vote by Bob, Ana's page reads « Bob propose de révéler un mot. »
  and announces it; « Oui » sends one yes and gives way, focused, to « Vote
  enregistré. En attente des autres joueurs… », kept after a reconnection; the
  requester's page reads « En attente des autres joueurs… »; an unvoted page's
  buttons are disabled while reconnecting and enabled once joined; `grid_solved`
  hides the banner. (← 025 AC-7, 047 AC-3)
- **AC-18** A vote the page saw open reads « 20 s » with a full bar, « 15 s » and
  three quarters 5 seconds later, « 0 s » and an empty bar at 20 seconds, then
  stays until `vote_closed`, alike with reduced motion; after a reconnection it
  never reads « 20 s » again; a vote from a first snapshot has no count and no
  bar. (← 047 AC-2)
- **AC-19** `vote_closed` `passed` removes the banner within 300 ms, announces
  « Vote accepté. » and ends the stream with that line, shown as the one note
  while the stream is hidden, even after two chat messages during the vote, and
  as no note while it shows; a vote a snapshot dropped is never announced and
  adds no line. (← 047 AC-4, 047 AC-5)
- **AC-20** At every window of `product.md`, opening the banner moves no box of
  the room, and « Oui » and « Non » meet the target size and are hit at their
  centre; on a phone and a computer the banner follows its design section; from
  the grid, Escape then Shift+Tab reaches « Non » then « Oui »
  with the ring inside the banner, and a close or a solve sends the focus from
  the banner to the grid; its states pass the scans of `product.md`, and
  `fr.json` holds the vote texts. (← 025 AC-8, 047 AC-1, 047 AC-13, 047 AC-14)
- **AC-21** In `free`, Ana's six grid checks at one instant give five
  `check_result`, each to every player; the sixth gets no reply, adds no event
  and leaves the seq where the fifth left it. One more at +9.9 s is dropped too
  and one at +10 s applies; Bob's grid check at the same instant applies, and
  after a restart within those 10 seconds five checks of Ana's apply at once.
- **AC-22** In `free`, after Ana's letter check, word check, grid check and
  letter reveal, her reveal of the clue (0, 0) gets `not_a_letter_cell` and her
  reveal of MIME applies; then her letter check is dropped, and so is a reveal
  of (0, 0), with no `not_a_letter_cell`.
- **AC-23** In `vote` with Ana, Bob and Cy connected, after Bob's five word
  checks, Ana's reveal of (1, 0) opens vote 1 and Bob's yes passes it, revealing
  `T`, while Bob's next word check is dropped; Ana's next four letter checks
  apply and a fifth is dropped. With Ana's window full, her grid check opens no
  vote.
- **AC-24** Offline, Ana types `T`, `X` from (1, 0), the selection moving to
  (1, 2), then picks « Vérifier » « Le mot » and « Révéler » « La lettre »:
  after her reconnection snapshot the server receives the two edits, the
  check of TAMIS, then the reveal of (1, 2), so the check marks (1, 1) wrong.
- **AC-25** On Bob's vote, Ana's unvoted page has « Oui » focused and (1, 0)
  selected; her socket closes: once « Oui » and « Non » are disabled the focus
  is on the grid, (1, 0) still selected, and no ballot was sent. « Non »
  focused does the same.

## Edge cases

- A player who joins during a vote sees the buttons; the ballot is ignored
  (AC-15).
- A requester who leaves: the vote goes on, and a pass is in their name (AC-13).
- `none` set during a vote hides the Aide groups and keeps the banner; a pass
  then closes `rejected` (AC-12, AC-14).
- After a restart, a page that recorded its ballot still reads `vote.cast`; the
  others decide, or the vote times out (AC-16, AC-17).
- A check dropped after a vote's 20 seconds leaves the vote open for the tick
  to close (AC-23).
- While the page reconnects, the Aide items stay as rule 12 sets them; a
  request made then waits for the resent edits (AC-24).

## Out of scope

- Generated hints, revealing the whole grid, undoing a reveal, keyboard
  shortcuts, a tally of ballots, changing a ballot, votes on anything else, a
  message telling a player their request was dropped.
- The host settings: `lobby/host.md`. The Aide menu's place, « Réagir » under
  the banner: `client/hud.md`; the notes: `client/room.md`. Cell marks and
  pending edits: `gameplay/board.md`. Completion: `gameplay/rules.md`. The
  stream and its lines' look: `social/chat.md`. Protocol and fair play:
  `platform/realtime.md`. The recap's counts: `gameplay/results.md`.

## Code

- `src/nock/room.py`: check, reveal, the budget and its count, votes, `tick`,
  `replay`, `snapshot_for`, `after_restart`, the hint limit; `RoomConfig` holds
  the vote time and the limit's numbers.
- `src/nock/protocol.py`: messages and error codes.
- `web/src/lib/AideMenu.svelte`, `RoomPage.svelte` (what is enabled, the
  banner), `GridViewport.svelte` (strike, notch), `roomSession.ts`,
  `voteCountdown.ts`, `activityFeed.ts` (the stream lines).
- Tests: `tests/test_spec_023_*`, `test_spec_024_*`, `test_spec_025_*`,
  `test_spec_047_ac01*` to `..._ac05*`, `..._ac13*`, `..._ac14*`,
  `test_hints_*`.
