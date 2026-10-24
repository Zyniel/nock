---
area: social
file: catch-up
status: done
---

# social/catch-up - Catching up after an absence

## Purpose

A player who comes back to a room sees what changed while this device was away:
the changed cells are highlighted for a moment, and the words completed, the
checks and the reveals of the absence join the Salon's stream with the names of
their players.

## Depends on

- `lobby/joining.md`: the stored identity, resume and seat back, the members of a
  room, room expiry.
- `social/chat.md`: the Salon's stream (its order, its cap of 100 event lines
  and its scroll rules), not the text of every event line.
- `platform/realtime.md`: snapshots, `seq`, reconnection, the logged events.

## Rules

### Terms

1. The seen seq, per room and per device, is the `seq` the room page last held.
   Each time that `seq` changes (a snapshot, an applied event), the page keeps it
   in memory and writes it as `seen_seq` in the room record `nock.room.<CODE>`,
   keeping the record's other fields, and creating the record with `grid` and
   `selection` null when there is none. A stored value that is not a whole number
   of 0 or more counts as absent. When storage is refused, the seen seq lives in
   memory only.
2. A return is a snapshot whose `seq` is greater than the seen seq the page had
   when it arrived: the stored one for the first snapshot of a page load, the one
   in memory for every later snapshot (a reconnection). A first snapshot with no
   stored seen seq (a first visit on this device) is no return; nor is a snapshot
   whose `seq` is not greater.
3. The absence is the room's events with seen seq < `seq` <= the return's `seq`.
4. A changed cell is a letter cell named by a `letter_changed` or a `cell_locked`
   of the absence, whoever made it: a letter written, erased, confirmed or undone,
   a lock by a check or a reveal. A cell only marked wrong by a check is not one.
5. A `letter_changed` with a letter, on a cell empty just before it, completes
   each word through that cell whose cells all hold a letter, pencil or not, just
   after it; the word is credited to the event's player. A reveal completes no
   word: its own line says it.

### The server

6. `POST /api/rooms/{code}/catch-up` takes a member's resume token,
   `after_seq` (the seen seq) and `until_seq` (the return's `seq`), both whole
   numbers of 0 or more, and nothing else; any other body answers 422.
7. It answers 404 `{"detail": "Not Found"}` when the code is not a room code, the
   room is unknown or expired, the token is no member's (player or past player),
   or the store holds no state of the room at or before `after_seq`. The answer
   never says which, and the wrong-code throttle does not count it. The request
   makes no room live and logs nothing; an expired room is deleted as by any
   lookup (`lobby/joining.md`).
8. A 200 answer holds the request's two seqs, `cells`, `lines` and `names`, and no
   letter of the grid. It covers the logged events with `after_seq` < `seq` <=
   `until_seq`: an `until_seq` past the room's `seq` reads to its last event, and
   an `after_seq` at or past `until_seq`, or past the room's `seq`, gives no cell,
   line or name.
9. `cells`: each changed cell once, in row-major order.
10. `lines`: each `check_result` and `reveal_result` as logged, and a
    `word_completed` (`seq`, player, clue) for each completed word, in `seq`
    order; the words of one letter in clue order (the clue cell's row, column,
    then the clue's index). Past 100 lines, only the last 100 are kept.
11. `names`: for each player of the kept lines, in order of first appearance, the
    nickname they had in the room when they made their first kept line, even if
    they have left since. A player who was not in the room then (a vote that
    passes after its requester left) gets no name.

### The page

12. On a return, once the snapshot is applied, the page sends one request with
    its token, its seen seq and the snapshot's `seq`. It applies the answer only
    while that snapshot is still its latest; otherwise the answer is dropped and
    that absence is not asked again: the next return asks from the seen seq of
    rule 2, which has already moved past that snapshot. A failed request
    (network error, a status other than 200, a body that is not a catch-up)
    shows nothing and is not retried; the page plays on.
13. Applying a catch-up adds first each name for a player the page cannot name
    yet; a name the page knows stays.
14. Each changed cell is highlighted for 5 seconds from the moment the catch-up is
    applied; a later catch-up that names it again starts its 5 seconds again.
    Typing in it does not end it. A highlighted cell still takes clicks and
    letters, its mark is hidden from assistive technology and reaches 3:1
    against the cell, and the highlight adds to the cell's other looks without
    replacing them.
15. Each line becomes an event item of the Salon's stream, placed in `seq` order
    among the items it holds: after those of `seq` at most the seen seq, before
    the live ones that came since the snapshot; equal seqs keep clue order. A
    check or a reveal reads as its live line (`feed.check.<scope>`,
    `feed.reveal.<scope>`); a word reads `feed.word_completed` (`{name} a
    complété « {clue} »`), with the clue's text. The name is the nickname the
    page knows, shown as `lobby/joining.md` rule 3 says, else « Quelqu'un »
    (`feed.someone`). The stream then keeps its newest 100 event lines (messages
    keep their own cap, `social/chat.md`), and its scroll rules apply as to any
    new item.

### Look

A highlighted cell, `_design/cells.md`, « Catch-up ring » and « Drawing order »;
the stream's event lines, `_design/room.md`, « Salon ».

## Acceptance criteria

The examples use the absence ABSENCE on FX-01 (`specs/_reference.md`): Ana
(`p1`) writes `T` at (1, 0) (seq 3) and leaves; Bob (`p2`) writes `VIDE` across
from (2, 1) (seq 5 to 8), checks that word (seq 9, locks 10 to 13), reveals
(1, 1) (seq 14, 15), writes `A` at (3, 1), `L` at (4, 1) and `N` at (0, 1)
(seq 16 to 18, `N` completing `NAVAL`) and leaves; both time out and become past
players (seq 22).

- **AC-1** A catch-up of ABSENCE with Ana's token from seq 3 to 22 names (0, 1),
  (1, 1), (2, 1), (2, 2), (2, 3), (2, 4), (3, 1), (4, 1) in that order, not
  (1, 0); from 15, (0, 1), (3, 1), (4, 1); from 4 until 8, the four cells of
  `VIDE`; from 22 or 25, no cell, line or name; until 99, the same as until 22,
  with `until_seq` 99. (← 034 AC-1)
- **AC-2** A cell written, erased and written again is named once; from 8 to 13
  of ABSENCE, the four cells of `VIDE`, only locked, are named; a check of `VIDE`
  holding `X` at (2, 1) and `I` at (2, 2) names (2, 2), locked, not (2, 1), only
  marked wrong; from 2, Ana's own `T` at (1, 0) is named with her token.
  (← 034 AC-1)
- **AC-3** Over HTTP, the catch-up of AC-1 answers 200 with Ana's token and with
  Bob's; a token no player ever had, or the code `ZZZZZZ`, answers 404
  `{"detail": "Not Found"}` and adds nothing to the wrong-code throttle; an
  `after_seq` of -1, a missing `until_seq` or an extra key answers 422.
  (← 034 AC-1)
- **AC-4** The request of AC-3 leaves the room's log as it was, and its answer
  holds none of FX-01's eight answers. (← 034 AC-1)
- **AC-5** ABSENCE's lines are the word `VIDE` by `p2` (seq 8), the check of
  seq 9 and the reveal of seq 14 as logged, then the word `NAVAL` by `p2`
  (seq 18), and its names are only `BOB`, although Bob has left. (← 034 AC-3)
- **AC-6** With `VIDE` and `SENT` full but for (2, 4), one letter there gives
  two word lines with one `seq`: `SENT`, clue (0, 4, 0), then `VIDE`, clue
  (2, 0, 0). (← 034 AC-3)
- **AC-7** A letter written over another, a pencil letter confirmed, an erase
  and a reveal that fills a word's last empty cell give no word line; a pencil
  letter that fills it gives one; a word completed, emptied and completed again
  gives two; a word whose last letter came before the absence gives none, even
  when a check locks it during it. (← 034 AC-3)
- **AC-8** An absence of 150 checks gives the last 100 by `seq`. (← 034 AC-3)
- **AC-9** When Bob, who joined during the absence, checks a cell and then Ana
  completes `VIDE`, the names are `BOB` then `ANA`; Bob removed after his check
  is still `BOB`; a check by `p9`, never in the room, gets no name. (← 034 AC-3)
- **AC-10** A first visit, with a record `{"grid": 1, "selection": null}` and a
  snapshot at seq 5, sends no request and applies no catch-up, and the record
  then reads `{"grid": 1, "selection": null, "seen_seq": 5}`, then `"seen_seq":
  7` after events 6 and 7; with no record, one is made with `grid` and
  `selection` null and `seen_seq` 5. (← 034 AC-5)
- **AC-11** With `seen_seq` 5 stored and a snapshot at 9, the page sends one
  request with its token, 5 and 9; after the first visit of AC-10 and a
  reconnection whose snapshot is at 12, one with 7 and 12; with 9 stored and a
  snapshot at 9 or 4, or with `"5"`, -1 or 2.5 stored, none. (← 034 AC-5)
- **AC-12** When the request for 5 to 9 answers 500 or is aborted, no cell is
  highlighted, the stream holds no item, no second request goes out, and typing
  `T` on (1, 0) still sends the letter. (← 034 AC-5)
- **AC-13** While the request for 5 to 9 is pending, a reconnection to seq 15
  sends one for 9 to 15; the answer for 5 to 9, highlighting (1, 0), then changes
  nothing, and the answer for 9 to 15 highlights (2, 2). (← 034 AC-5)
- **AC-14** With `seen_seq` 5, a snapshot at 9 and an answer naming (1, 0) and
  (2, 2), exactly those two letter cells are highlighted, each with one mark that
  follows « Catch-up ring », hidden from assistive technology, its colour
  reaching 3:1 against the cell. (← 034 AC-2)
- **AC-15** In AC-14, Bob's cursor on (2, 2) stays visible and is drawn over the
  ring, a click on (2, 2) selects it, and typing `T` in (1, 0) keeps its
  highlight. (← 034 AC-2)
- **AC-16** The highlight of AC-14 lasts about 5 seconds, then is gone; a later
  catch-up naming the cell again starts its 5 seconds again. (← 034 AC-2)
- **AC-17** On the live server, Ana writes `T` at (1, 0) and closes her page;
  Bob writes `VIDE` and checks it; when Ana opens the room again, (2, 1) to
  (2, 4) are highlighted, (1, 0) is not, and her stream ends with « Bob a complété
  « Sans contenu » » then « Bob a vérifié un mot », in view. (← 034 AC-2, 034
  AC-4)
- **AC-18** An answer with the word `VIDE` by `p2` (seq 7), a word check by `p2`
  (seq 8), a letter reveal by `p3` (seq 9) and the name `CY` adds, in that order,
  « Bob a complété « Sans contenu » », « Bob a vérifié un mot » and « Cy a révélé
  une lettre »; a check by an unnamed `p4` reads « Quelqu'un a vérifié un mot »;
  two words of one letter read « Flaire » then « Sans contenu », with one `seq`.
  (← 034 AC-4)
- **AC-19** The lines of AC-18 come before a live line of seq 10, whether it
  arrives after the answer or before it; a live line of seq 6, held before a
  reconnection to 12, stays before a catch-up line of seq 10; with 99 live
  lines (10 to 108) held before the answer, the stream keeps 100 event lines,
  from seq 9. (← 034 AC-4)
- **AC-20** A stream at its end before the lines go in is at its end within
  300 ms after, the newest line in view; a stream scrolled away from its end
  keeps every item in view in its place. (← 034 AC-4)

## Edge cases

- A device has its own seen seq: another device of the same player, or the same
  token before a reload whose events this page never applied, counts as away
  (AC-2).
- A dropped answer leaves its absence without a catch-up (AC-13).
- With storage refused, only reconnections show a catch-up (rule 1).
- A join refused (full, locked) brings no snapshot, so no return; the stored
  seen seq waits for a later visit (rule 2).
- A code drawn again after expiry may meet an old seen seq: at worst the new
  room's own events show as a catch-up (rules 1, 2).
- A player named by a later line but by no name at their first kept line stays
  unnamed in `names`, and the page names them if it can (rule 11).

## Out of scope

- A summary banner, showing the highlight again, a separator between catch-up
  and live lines, what a changed cell held before, lines for letters, chat, flags
  or presence, a seen seq shared by an account's devices, a catch-up over the
  WebSocket.
- A live word-completed line: live play adds none, so only a catch-up shows
  one. It is a later change already approved, item B-004 of `Backlog.md`, owned
  by `social/chat.md`.
- Resume and seat back: `lobby/joining.md`. The stream, its live lines and their
  texts: `social/chat.md`. The « Salon » dot and 3-second notes:
  `client/hud.md`. Reconnection and the log: `platform/realtime.md`,
  `platform/server.md`.

## Code

- `src/nock/catch_up.py`: the request and answer models, `build_catch_up`.
- `src/nock/store.py`: `load_room_at`. `src/nock/hub.py`: `RoomRegistry.catch_up`.
  `src/nock/server.py`: the catch-up route.
- `web/src/lib/catchUp.ts`: the request, reading and applying the answer;
  `roomRecord.ts`: the seen seq; `RoomPage.svelte`: returns, dropped answers,
  highlight timers; `GridViewport.svelte`: the highlighted cell;
  `activityFeed.ts`: the word line, placing items.
- Tests: `tests/test_spec_034_*`, `tests/spec034_harness.py`.
