---
area: social
file: chat
status: draft
---

# social/chat - Chat, reactions, the clue flag and mute

## Purpose

The players of a room talk without leaving the grid: messages in the Salon's
stream, a short reaction on a word, and « Je bloque », a flag on the clue where
help is wanted. The host can mute a player's chat and reactions.

## Depends on

- `platform/realtime.md`: the messages `flag`, `chat`, `react`, `mute_player`,
  their events, seq order, delivery and error codes.
- `lobby/rooms.md`: the host rules, `player_muted` (rule 17), the Joueurs rows.
- `client/hud.md`: « Salon », its tabs, badge and dot, the 3-second notes.

## Rules

### The clue flag

1. A player holds at most one flag. `flag` is input (it wakes an idle player,
   `social/presence.md`), not an edit, with no rate limit. For player p, the
   first case that applies decides:
   1. no clue and p holds none: nothing;
   2. no clue: p's flag goes, in one `flag_changed` with no clue;
   3. a clue that names no word, or whose word is full (each cell holds a
      letter, pencil or not): `invalid_target`, changing nothing but the waking;
   4. the clue of p's flag: nothing;
   5. else it becomes p's flag, in one `flag_changed`, replacing any other.
2. After a step whose events hold a `letter_changed` or a `cell_locked` (edit,
   undo, reveal, pencil letter), each player whose flagged word is now full, in
   player order, loses the flag in one `flag_changed` with no clue, after the
   step's own events and before `grid_solved` or `grid_full_wrong`
   (`gameplay/rules.md`). A check fills no cell; emptying the word again does
   not bring the flag back.
3. A player who leaves the room takes the flag along, with no `flag_changed`; a
   disconnected one keeps it. A snapshot lists the players' flags in player
   order, several on one clue allowed. Flags survive replay and a restart.
4. The page keeps the latest snapshot's flags (skipping a malformed one), takes
   each `flag_changed` and drops a flag at `player_left`. A flagged clue shows
   one marker, hidden from assistive technology, labelled `flag.marker_label`
   (« Bloqué : {names} »): the flaggers' nicknames in roster order, then the
   ids the roster lacks, each « Quelqu'un », by id as plain strings. The marker
   never moves the clue text.
5. « Je bloque » (`flag.button_label`, « Je bloque sur ce mot ») is pressed
   while my flag is on the selected word's clue. It is disabled while nothing
   is selected, and while the selected word is full on the page (pending
   letters count) and it is not pressed. A press sends my flag on that clue, or
   `clue: null` when pressed; the button and the marker change only with
   `flag_changed`. An error answering a flag changes nothing on the page.
6. A `flag_changed` with a clue adds the stream line `feed.flag` (« {name}
   bloque sur « {clue} » »); one without a clue adds none.

### Chat

7. `chat` is input. Its text, stripped as Python's `str.strip()` does, holds 1
   to 280 code points, else `invalid_message` (`platform/realtime.md`). Then: a
   muted sender gets `muted`; a sender with 5 messages accepted in the last 10
   seconds (sliding: those after now − 10) is dropped, with no event and no
   answer; else one `chat_message` (seq, player, text unchanged) reaches every
   player, sender included, and joins the room's history. Refused and dropped
   messages do not count. Chat works on a solved grid.
8. The history lives only in the room's log and snapshots, never in another
   table, file or log record; a snapshot carries all of it.
9. The message box (`chat.input_label`, placeholder `chat.placeholder`) takes
   at most 280 characters. « Envoyer » (`chat.send`) is disabled while the text
   trimmed by `trim()` is empty, the page is not joined, I am muted, or pacing
   holds. Enter or « Envoyer » sends the trimmed text, empties the box and
   leaves the focus in it. A line shows only when its `chat_message` arrives,
   once per seq, with its author's nickname (`lobby/joining.md` rule 3), also
   for a player who left, else « Quelqu'un » (`feed.someone`).
10. Pacing: the page sends a message only while fewer than 5 of its own went
    out in the last 12 seconds; meanwhile « Envoyer » is disabled and the note
    `chat.wait` (« Patientez avant d'envoyer. ») shows. Reactions are paced
    alike: every option of the picker is disabled.
11. A message is unread when its seq is above the last seen seq and it is not
    mine. The last seen seq is the first snapshot's, then, while the stream
    shows, the newest message's; a reconnection keeps it. While the stream is
    hidden, « Salon » carries the count (1 to 99, then `chat.unread_many`,
    « 99+ »), hidden from assistive technology, named as `client/hud.md` rule
    7 says; it keeps its height with or without the count.

### Reactions

12. The reactions are `thumbs_up`, `clap`, `laugh`, `wow`, `thinking` (👍 👏 😂
    😮 🤔, `reaction.<value>`, named `reaction.<value>_label`). A well-formed
    `react` is input, never answered with an error, and dropped silently when
    the sender is muted, when its clue names no word, or past 5 reactions
    relayed in the last 10 seconds; dropped ones do not count. Else one
    `reaction`, with no seq and never logged, reaches every player once, the
    sender included, on any word, full or not. A restart empties every
    player's chat and reaction windows, connected or not.
13. « Réagir » (`reaction.button_label`) is disabled while nothing is selected,
    while I am muted and while the vote banner shows (`gameplay/hints.md`). A
    press opens the picker (`reaction.picker_label`, the five in that order),
    the focus on the first option (on « Réagir » while pacing holds). An option
    sends `react` on the selected word's clue and closes the picker; Escape or a
    second press closes it sending nothing; both put the focus on « Réagir ».
    When « Réagir » becomes disabled, an open picker closes at once, sending
    nothing, and a focus inside it goes to the grid.
14. A `reaction`, applied once the page has a snapshot and leaving its seq
    alone, shows on its clue when the grid has that clue: the emoji, hidden from
    assistive technology, labelled `reaction.shown_label` (« {name} :
    {reaction} »), for 3 seconds from its arrival. A newer one on that clue
    replaces it, with its own 3 seconds.

### Mute

15. A mute (`lobby/rooms.md` rule 17) stops chat and reactions only. While I am
    muted, the message box and « Envoyer » are disabled, the note `chat.muted`
    (« L'hôte a coupé votre discussion. ») shows and « Réagir » is disabled; the
    typed text stays, and a focus on the box or « Envoyer » moves to « Salon ».
    An error `muted` changes nothing on the page, and no chat or reaction answer
    touches the pending edits.
16. Only the host sees, in each other player's Joueurs row, « Couper »
    (`chat.mute`, named `chat.mute_label`, « Couper la discussion de {name} »),
    or « Rétablir » (`chat.unmute`, `chat.unmute_label`) while that player is
    muted. A press sends `mute_player` with the opposite; the button follows
    `player_muted`.
17. The chat notes share one slot under the message box, one line high, one
    note at a time: `chat.muted` wins, and `chat.wait` comes back after an
    unmute while pacing holds. A note coming or going moves nothing.

### The stream

18. The Discussion tab holds one stream, named `chat.heading` (« Discussion »),
    oldest first in seq order: the newest 200 messages of the history and the
    newest 100 event lines, each kind with its own cap. Joins and departures
    belong to `social/presence.md`; checks, reveals and the vote line to
    `gameplay/hints.md`; catch-up lines to `social/catch-up.md`; the flag line
    (rule 6) and the lines below to this file. A `settings_changed`, compared
    with the settings held before it, reads `feed.room_locked` (« {name} a
    verrouillé le salon ») or `feed.room_unlocked` (« {name} a déverrouillé le
    salon ») when only the lock changed, else `feed.settings_changed` (« {name}
    a modifié les réglages : aide {help_mode}, {letters} lettres et {words} mots
    à révéler », the mode « libre », « par vote » or « désactivée »). A
    `host_changed` reads `feed.host_changed` (« {name} est maintenant l'hôte »).
    A `letter_changed`, a `cell_locked`, a `player_state_changed` or a
    `selection_moved` adds no line.
19. A new item brings the stream to its end within 300 ms only when it was at
    its end (1 px or less hidden below) just before; otherwise the items in
    view keep their place, also when a cap drops the oldest. My own message or
    action is no exception. A stream at its end is there again within 300 ms
    of a resize, a new root font or its tab shown again. It is a scrolling list
    of `product.md` rule 18.
20. While the vote banner shows, it is drawn above an open Salon, which keeps
    its box, scroll, focus and use; nothing scrolls to uncover it. The Salon
    never covers « Salon » or the vote's buttons, and in the sheet layout moves
    nothing. The picker never covers « Réagir » or the vote's buttons, and moves
    nothing. In the column layout the picker and an open Salon do not overlap
    and leave both buttons uncovered. The grid area, the clue bar and the in-app
    keyboard never hold the message box.

### Look

- `_design/cells.md`, « Clue cells »: the marker. `_design/foundation.md`: the
  flag icon (« Icons »), the disabled « Envoyer » (« Components »).
- `_design/room.md`: « Clue bar » for « Réagir » and « Je bloque »; « Salon »
  for the stream, the message box, the notes and « Couper »; « Reactions » and
  « Layers » for the picker and a shown reaction.

## Acceptance criteria

The examples use FX-01 (`specs/_reference.md`) with Ana (`p1`, host), Bob
(`p2`) and Cy (`p3`); IDES is the clue (0, 3, 0), MIME (0, 2, 0).

- **AC-1** At seq 2, Bob's flag on IDES gives one `flag_changed` seq 3 to both
  players and no reply, and a later joiner's snapshot lists it; within 1 s both
  pages mark IDES, labelled « Bloqué : Bob », Bob's « Je bloque » is pressed,
  and both streams end with « Bob bloque sur « Fatales à César » ».
  (← 021 AC-1, 021 AC-2)
- **AC-2** With Bob's flag on IDES, Ana's `S` at (4, 3) after `I`, `D`, `E`
  gives `letter_changed` seq 7 then `flag_changed` seq 8 with no clue; a letter
  that fills two flagged words and solves the grid gives its letter, the two
  clearings in player order, then `grid_solved`. The page unmarks IDES and adds
  no stream line. (← 021 AC-3)
- **AC-3** Bob's flag on IDES then MIME gives one `flag_changed`, IDES unmarked
  and MIME marked; with Cy's flag on MIME, it has one marker, « Bloqué : Bob,
  Cy »; flags of `p9` then `p7`, not in the roster, give « Bloqué : Bob, Cy,
  Quelqu'un, Quelqu'un ». (← 021 AC-4)
- **AC-4** A flag on (1, 0, 0), (0, 2, 1), (9, 9, 0), on MIME once full, or on
  any word of a solved grid gets `invalid_target`, the room and its seq
  unchanged; removing a flag one lacks, or flagging one's clue again, gives
  nothing; an idle sender is woken all the same. (← 021 AC-5)
- **AC-5** With nothing selected « Je bloque » is disabled; with MIME selected
  a press sends my flag on (0, 2, 0), the button pressed only once
  `flag_changed` comes back, and a second press sends `clue: null`; Bob's flag
  on MIME leaves it unpressed; selecting the full TAMIS disables it; an
  `invalid_target` changes nothing on the page. (← 021 AC-6)
- **AC-6** A marker on IDES, on NAVAL (second clue of (0, 0)) and on FX-02's
  first clue lies in its clue cell as « Clue cells » draws it, the clue text in
  place. « Je bloque » sits in the clue bar between « Réagir » and the next
  button, is reached by Tab with the focus ring, flags by Enter, and in every
  window of `product.md` is at least 24 px square and hit at its centre; the
  contrast and language scans pass. (← 021 AC-9, 021 AC-10, 021 AC-11)
- **AC-7** Bob, flagging IDES, removed or timed out leaves only his
  `player_left`, and the page unmarks IDES; disconnected, he keeps the flag
  until he times out. Replayed from the log, and after a restart, every player
  holds the flag of the live room. (← 021 AC-7, 021 AC-8)
- **AC-8** At seq 2, Ana's « Qui a une idée pour le 3 ? » gives `chat_message`
  seq 3 and no reply; within 1 s both pages end with « Ana » and that text, and
  her box is empty. Two players sending 20 messages each at once get one order,
  the same on both and in a later snapshot, each sender's in sending order.
  (← 022 AC-1)
- **AC-9** 280 `a` are sent; 281 `a`, `""` or three spaces get
  `invalid_message`, unseen by others, the seq unchanged; `" salut "` arrives as
  `salut`. The box keeps 280 of 300 typed characters, « Envoyer » is disabled
  when it is empty or blank, and `  salut  ` sends `salut`. (← 022 AC-2)
- **AC-10** Bob's 👏 on IDES gives no event and reaches Bob and Ana once, with
  no seq and nothing logged; within 1 s both pages show 👏 on IDES. A 😮 shows,
  labelled « Bob : Waouh », and is gone 3.5 s after; a 🤔 a second later
  replaces it for its own 3 s; one on (1, 0, 0) shows nothing.
  (← 022 AC-3, 022 AC-4)
- **AC-11** With VIDE selected, « Réagir » opens the picker with 👍 👏 😂 😮 🤔,
  focus on the first; 😂 sends `react` on (2, 0, 0), closes it and focuses
  « Réagir »; Escape closes it sending nothing; in the column layout it opens
  over the grid while the Salon stays open. (← 022 AC-5)
- **AC-12** With the stream hidden, after a snapshot at seq 5, messages 6 (Bob),
  7 (Cy) and 8 (Ana) make « Salon » read 2, named « Salon, 2 messages non
  lus »; showing the stream clears it; message 10 while hidden reads 1; a
  reconnection bringing 11 and 12 reads 3; 100 read « 99+ »; « Salon » keeps
  its height. (← 022 AC-6, 043 AC-17)
- **AC-13** Muted by Ana, Bob's chat gets `muted`, unseen by Ana, and his
  reaction is dropped, while his letters, checks and flags go on; unmuted, he
  chats again. Only Ana sees « Couper » in Bob's row, named « Couper la
  discussion de Bob »; pressed, it reads « Rétablir », and within 1 s Bob's box
  and « Envoyer » are disabled, « L'hôte a coupé votre discussion. » shows and
  « Réagir » is disabled. (← 022 AC-7)
- **AC-14** A chat text is held only in its room's stored rows and in no log
  record; `<b>salut</b>` and the nickname `<img src=x>` show as text, creating
  no element; every frame of a full game with chat passes the traffic checks of
  `platform/realtime.md` once chat texts, each one a client sent, are set
  aside. (← 022 AC-8, 022 AC-13, 022 AC-14)
- **AC-15** Six messages from Ana at once: five pass, the sixth is dropped
  without answer, one at +9.9 s too, one at +10 s passes; Bob's limit is his
  own; reactions alike; a restart empties every window. After five sends Ana's
  page disables « Envoyer » with « Patientez avant d'envoyer. » until 12 s after
  the first; five reactions disable the options alike. (← 022 AC-9, 022 AC-10)
- **AC-16** Ana's lock, her unlock of a room held locked, her change to no
  help, 3 letters and 2 words, and her taking the host role read « Ana a
  verrouillé le salon », « Ana a déverrouillé le salon », « Ana a modifié les
  réglages : aide désactivée, 3 lettres et 2 mots à révéler » and « Ana est
  maintenant l'hôte »; a letter, a locked cell, an idle state, a removed flag
  or a moved selection add none. Messages and event lines share one stream in
  seq order, each kind dropping only its own oldest past 200 messages or 100
  event lines. A new line puts a stream at its end (1 px included) at its end
  within 300 ms and leaves a scrolled-up stream's items in place, my own
  message or lock too, a full stream included; a stream at its end is there
  again within 300 ms of a resized window, a 20 px root font or its tab shown
  again. (← 013 AC-5, 013 AC-7, 013 AC-8, 022 AC-11, 043 AC-16)
- **AC-17** A stream of 40 messages is one Tab stop named « Discussion », with
  the focus ring, scrolled by ArrowUp, its scroll kept by a new line; with two
  it is no stop. Tab reaches « Réagir », « Salon », each reaction, the box,
  « Envoyer » and « Couper »; after a send by Enter, « Envoyer » or a tap, the
  focus is in the box. The contrast and language scans pass with the stream, a
  reaction and the unread count. (← 022 AC-12, 022 AC-16, 022 AC-20)
- **AC-18** In every window of `product.md`, the open Salon lies inside the
  window with no page scroll, leaves « Salon » and the vote's buttons uncovered
  and, in the sheet layout, moves nothing; the open picker does the same with
  « Réagir » and moves nothing; in the column layout both open do not overlap
  and leave both buttons uncovered; the controls are at least 24 px square. A
  vote opening disables « Réagir » and closes the picker within 300 ms; where
  its banner meets the open Salon it is drawn above, the Salon keeps its box,
  scroll and focus, a typed `ok` is still sent, and the Salon is whole again
  once the banner goes. (← 022 AC-15, 022 AC-17)
- **AC-19** A mute while the picker has the focus closes it within 300 ms,
  sending nothing, focuses the grid and leaves an open Salon as it was; while
  the box or « Envoyer » has the focus, both are disabled, `salut` stays typed
  and the focus is on « Salon ». (← 022 AC-18)
- **AC-20** Muted, or paced, the note sits under the box on one line in every
  window, as « Salon » draws it, and leaves the Salon's box unchanged; muted
  while paced, only the muted note shows, then the wait note after the unmute.
  « Envoyer » takes the disabled look whenever disabled, the muted box too, and
  the muted Discussion tab passes the contrast and language scans of
  `product.md`. (← 022 AC-19, 047 AC-12, 047 AC-14)

## Edge cases

- A text made only of whitespace that `str.strip()` removes but `trim()` keeps
  (U+001C to U+001F, U+0085) gets `invalid_message` and is lost (AC-9).

## Out of scope

- Editing messages, private messages, older history on demand; flagging a
  cell or several clues.
- A live « word completed » line: an approved later change, item B-004 of
  `Backlog.md`; today only a catch-up shows one (`social/catch-up.md`).
- « Salon », its tabs and dot, the 3-second notes (messages, flags, my own
  reaction): `client/hud.md`. Who may mute: `lobby/rooms.md`. Edit limits:
  `platform/realtime.md`.

## Code

- `src/nock/room.py`: `_flag`, `_chat`, `_react`, flag clearing,
  `after_restart`; `RoomConfig` holds the limits.
- `web/src/lib/clueFlags.ts`, `chat.ts`, `activityFeed.ts` (`streamEntries`,
  `trimFeed`, `FEED_LIMIT`), `scrollingLists.ts`, `ChatPanel.svelte`,
  `ReactionPicker.svelte`, `ClueBar.svelte`, `PlayersPanel.svelte` (« Couper »),
  `Salon.svelte`, `RoomPage.svelte`, `roomSession.ts`.
- Tests: `tests/test_spec_021_*`, `test_spec_022_*`, `test_spec_013_ac05_*`,
  `test_spec_013_ac07_ac08_*`, `test_spec_047_ac12_*`, `test_spec_047_ac14_*`,
  `test_spec_043_ac16_ac18_stream.py`.
