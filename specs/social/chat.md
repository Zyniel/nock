---
area: social
file: chat
status: approved
---

# social/chat - Chat, the stream and mute

## Purpose

The players of a room talk without leaving the grid: messages in the Salon's
stream, which also tells what happens in the room. The host can mute a
player's chat and reactions.

## Depends on

- `platform/realtime.md`: the messages `chat` and `mute_player`, their events,
  seq order, delivery and error codes.
- `lobby/host.md`: the host rules, `player_muted` (rule 5), the host's buttons.
- `client/room.md`: « Salon », its tabs, badge and dot, the 3-second notes.

## Rules

### Chat

7. `chat` is input. Its text, stripped as Python's `str.strip()` does, holds 1
   to 280 code points and no character of Unicode general category Cc, Cf, Zl
   or Zp but U+000A, U+200C, U+200D and the tags U+E0020 to U+E007F (the
   controls and the bidirectional overrides and isolates, such as U+202E,
   that nicknames refuse), else
   `invalid_message` (`platform/realtime.md`). The check is the `chat`
   message's: a message already in the history keeps its text. Then: a
   muted sender gets `muted`; a sender with 5 messages accepted in the last 10
   seconds (sliding: those after now − 10) is dropped, with no event and no
   answer; else one `chat_message` (seq, player, text unchanged) reaches every
   player, sender included, and joins the room's history. Refused and dropped
   messages do not count. A restart empties every player's chat window,
   connected or not. Chat works on a solved grid.
8. The history is the room's newest 200 messages, the stream's cap (rule 18):
   an older one stays in the log alone, and no snapshot, reload or restart
   brings it back. The history lives only in the room's log and snapshots,
   never in another table, file or log record; a snapshot carries all of it.
9. The message box (`chat.input_label`, placeholder `chat.placeholder`) takes
   at most 280 characters. « Envoyer » (`chat.send`) is disabled while the text
   trimmed by `trim()` is empty, the page is not joined, I am muted, or pacing
   holds. Enter or « Envoyer » sends the trimmed text, empties the box and
   leaves the focus in it. A line shows only when its `chat_message` arrives,
   once per seq, with its author's nickname (`lobby/joining.md` rule 3), also
   for a player who left, else « Quelqu'un » (`feed.someone`).
10. Pacing: the page sends a message only while fewer than 5 of its own went
    out in the last 12 seconds, counting only those that went out on an open
    socket; meanwhile « Envoyer » is disabled and the note
    `chat.wait` (« Patientez avant d'envoyer. ») shows. Reactions are paced
    alike: every option of the picker (`social/reactions.md` rule 8) is
    disabled.
11. A message is unread when its seq is above the last seen seq and it is not
    mine. The last seen seq is the first snapshot's, then, while the stream
    shows, the newest message's; a reconnection keeps it. While the stream is
    hidden, « Salon » carries the count (1 to 99, then `chat.unread_many`,
    « 99+ »), hidden from assistive technology, named as `client/room.md` rule
    1 says; it keeps its height with or without the count.

### Mute

15. A mute (`lobby/host.md` rule 5) stops chat and reactions only. While I am
    muted, the message box and « Envoyer » are disabled, the note `chat.muted`
    (« L'hôte a coupé votre discussion. ») shows and « Réagir »
    (`social/reactions.md` rule 8) is disabled; the
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
    belong to `social/presence.md`; checks and reveals to
    `gameplay/hints.md`, the vote line to `gameplay/votes.md`; catch-up lines to `social/catch-up.md`; the flag line
    to `social/reactions.md` rule 6; the lines below to this file. A `settings_changed`, compared
    with the settings held before it, reads `feed.room_locked` (« {name} a
    verrouillé le salon ») or `feed.room_unlocked` (« {name} a déverrouillé le
    salon ») when only the lock changed, else `feed.settings_changed` (« {name}
    a modifié les réglages : aide {help_mode}, {letters} lettres et {words} mots
    à révéler », the mode « libre », « par vote » or « désactivée »). A
    `host_changed` reads `feed.host_changed` (« {name} est maintenant l'hôte »).
    Any other event adds no line.
19. A new item brings the stream to its end within 300 ms only when it was at
    its end (1 px or less hidden below) just before; otherwise the items in
    view keep their place, also when a cap drops the oldest. My own message or
    action is no exception. A stream at its end is there again within 300 ms
    of a resize, a new root font or its tab shown again. It is a scrolling list
    of `product.md` rule 18.
20. While the vote banner shows, it is drawn above an open Salon, which keeps
    its box, scroll, focus and use; nothing scrolls to uncover it. The Salon
    never covers « Salon » or the vote's buttons, and in the sheet layout moves
    nothing. The picker (`social/reactions.md` rule 8) never covers « Réagir »
    or the vote's buttons, and moves
    nothing. In the column layout the picker and an open Salon do not overlap
    and leave both buttons uncovered. The grid area, the clue bar and the in-app
    keyboard never hold the message box.

### Look

- `_design/foundation.md`, « Components »: the disabled « Envoyer ».
- `_design/room.md`: « Salon » for the stream, the message box, the notes and
  « Couper »; « Layers » for the Salon, the picker and the vote banner.

## Acceptance criteria

The examples use FX-01 (`specs/_reference.md`) with Ana (`p1`, host), Bob
(`p2`) and Cy (`p3`).

- **AC-8** At seq 2, Ana's « Qui a une idée pour le 3 ? » gives `chat_message`
  seq 3 and no reply; within 1 s both pages end with « Ana » and that text, and
  her box is empty. Two players sending 20 messages each at once get one order,
  the same on both and in a later snapshot, each sender's in sending order.
  (← 022 AC-1)
- **AC-9** 280 `a` are sent; 281 `a`, `""`, three spaces, `"a\u202eb"`,
  `"a\u0007b"` or `"a\u2028b"` get `invalid_message`, unseen by others, the
  seq unchanged; `" salut "` arrives as `salut`, `"a\nb"`,
  `"\U0001F469\u200d\U0001F4BB"` and
  `"\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"`
  as sent. The box keeps 280 of 300 typed characters, « Envoyer » is disabled
  when it is empty or blank, and `  salut  ` sends `salut`. (← 022 AC-2)
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
  `platform/fair-play.md` once chat texts, each one a client sent, are set
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
- **AC-21** After 205 messages in a room, a joiner's snapshot carries the
  newest 200 in seq order, and so does the room loaded from the store; the
  stream shows those 200. A stored message holding U+202E loads with it.
- **AC-23** With four reactions sent in the last 12 s, a fifth chosen while
  the socket is no longer open but the page has not yet seen its close (still
  joined) reaches no player and does not count: once the page is joined
  again, a fifth that goes out disables the options. A chat message sent in
  that state does not count either.

## Edge cases

- A text made only of whitespace that `str.strip()` removes but `trim()` keeps
  (U+001C to U+001F, U+0085), or one holding a pasted U+202E, gets
  `invalid_message` and is lost (AC-9).
- A stored message holding a character rule 7 refuses loads and shows as it
  is (AC-21).
- The 201st message drops the oldest from the history (AC-21).
- A room loaded with more than 200 messages in its history comes down to the
  newest 200 at its next message (AC-21).

## Out of scope

- Editing messages, private messages, older history on demand.
- The clue flag, « Réagir », the picker and a shown reaction:
  `social/reactions.md`.
- A live « word completed » line: only a catch-up shows one
  (`social/catch-up.md`).
- « Salon », its tabs and dot, the 3-second notes: `client/room.md`. Who may
  mute: `lobby/host.md`. Edit limits: `platform/fair-play.md`.

## Code

- `src/nock/room.py`: `_chat`, `after_restart`; `RoomConfig` holds the limits.
  `src/nock/protocol.py`: `is_refused_character`, the one helper that holds
  the refused categories (shared with `NOCK_DATABASE`, `platform/serving.md`);
  the chat check passes the characters rule 7 allows.
- `web/src/lib/chat.ts`, `activityFeed.ts` (`streamEntries`, `trimFeed`,
  `FEED_LIMIT`), `scrollingLists.ts`, `ChatPanel.svelte`,
  `ReactionPicker.svelte` (its pacing), `PlayersPanel.svelte` (« Couper »),
  `Salon.svelte`, `RoomPage.svelte` (the chat message), `roomSession.ts`.
- Tests: `tests/test_spec_022_*` but `ac03_ac05`, `test_spec_013_ac05_*`,
  `test_spec_013_ac07_ac08_*`, `test_spec_047_ac12_*`, `test_spec_047_ac14_*`,
  `test_spec_043_ac16_ac18_stream.py`; `tests/test_chat_*` for AC-21 and AC-23.
