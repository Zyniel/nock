---
id: "012"
title: Guest join
status: done
---

# 012 - Guest join

Epic E3 Rooms and presence (US-3.2) · Release: MVP · Epic depends on: E2
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine (`nock.room`,
`nock.hub`, runtime, test harness) is defined in spec 011; the messages are those of
spec 039; the room page those of specs 040 and 006.

(Note from the lead, 2026-10-16: refined for spec 032's seat back (its decisions 11
and 12): a join whose token belongs to a past player of the room, one who left by a
time-out, seats that player back with their id and token. Changed: "Join" (step 2's
time-out and the new step 4a), the socket binding, case a of the room page flow, and
the edge cases "Duplicate check", "Colours", "Full room", "Unknown resume token" and
"Order of refusals". No criterion changes, since none of them joins with the token
of a player who timed out; the steps marked with spec 032 apply once it is built.)

(Note from the lead, 2026-10-16: refined for the human's rule that nicknames are
typed and stored in capitals and shown with capitalised words, decision 12.
`normalize_nickname` returns the capitals, duplicates compare exactly, the nickname
input holds capitals as it is typed, and pages show a nickname through spec 040's
`displayNickname`. Changed: `normalize_nickname`, "Duplicate nicknames", the
`nock.nickname` row, steps 3 and 4 of the room page flow, the player list, AC-1,
AC-2, AC-6 and AC-7, the edge cases "Length", "Duplicate check" and "Remembered
nickname", decision 4 and "Out of scope"; added: AC-8 and decision 12. AC-1, AC-2,
AC-6 and AC-7 changed, so their tests follow (human's rule of 2026-10-16: nicknames
in capitals).)

(Note from the lead, 2026-10-16: refined after the first review of the nickname
rule, decision 12. `normalize_nickname` applies NFC again after the capitals,
since the capitals of 8 Greek letters are not in NFC, and the page's rule (room
page flow step 4) does the same. The nickname input shows its text in capitals
through CSS and keeps its value as typed, since rewriting the value at each change
broke input methods and the caret. Spec 040's `displayNickname` now keeps Greek's
final sigma. AC-2 pins the exact comparison with `STRAẞE` (whose `ẞ` is U+1E9E)
and `STRASSE`, and AC-8 also reads the nickname in the host's remove labels (spec
014), a clue flag's label (spec 021) and the chat's mute rows (spec 022). Changed:
`normalize_nickname`, steps 3 and 4 of the room page flow, AC-2, AC-6, AC-8, the
edge case "Length" and decision 12. AC-2, AC-6 and AC-8 changed, so their tests
follow. The note above that says the nickname input holds capitals as it is typed
describes text that is gone (review of the nickname rule, 2026-10-16).)

## Goal

As an invited player, I want to join with only a nickname, so that I am playing within seconds.

A room is one grid shared by up to 8 players and reached by a link.

## Public interface

### `nock.room` functions built by this spec

```python
# src/nock/room.py (behaviour defined here; models in spec 011)

NICKNAME_PUNCTUATION: str = " -'’_"     # space, hyphen, apostrophes ' and ’, underscore


# (Note from the lead, 2026-10-16: "then in capitals, with str.upper()" and
# "(the capitals)" were added; the first line read "NFC-normalised, then
# stripped" (human's rule of 2026-10-16: nicknames in capitals).)
# (Note from the lead, 2026-10-16: the first line read "NFC-normalised,
# stripped, then in capitals, with str.upper()", and "(the capitals)" became
# "(the capitals, after the second NFC)": the capitals of some Greek letters
# are not in NFC, decision 12 (review of the nickname rule, 2026-10-16).)
def normalize_nickname(text: str) -> str:
    """Return the nickname as stored: NFC-normalised, stripped, put in
    capitals with str.upper(), then NFC-normalised again.

    Rules, checked on the result (the capitals, after the second NFC):
    - 2 to 20 characters (code points);
    - each character is a Unicode letter (category L*), a mark that attaches
      to a letter (category Mn or Mc), an ASCII digit 0-9, or one of
      NICKNAME_PUNCTUATION; an enclosing mark (category Me) is refused;
    - at least one character is a letter or a digit.

    Raises:
        ValueError: a rule is broken; the message names the rule.
    """


def player_views(state: RoomState) -> tuple[PlayerView, ...]:
    """The players of the room as PlayerView, in `state.players` order.

    Each view copies player_id, nickname, colour, state, is_host, muted and
    selection of its PlayerRecord. No resume_token.
    """


def snapshot_for(state: RoomState, player_id: str) -> Snapshot:
    """The snapshot that player `player_id` receives.

    seq = state.seq, you = player_id, resume_token = that player's token,
    grid = grid_state(state), players = player_views(state),
    settings = state.settings, reveal_budget = state.reveal_budget,
    flags = (), chat = (), open_vote = None, timer_elapsed_ms = 0,
    timer_running = False, solved = state.solved. (Specs 021, 022, 025, 027
    fill the fields they own.)

    Raises:
        KeyError: no player `player_id` in the room.
    """


def join_room(
    state: RoomState,
    message: Join,
    now: float,
    new_player_id: str,
    new_resume_token: str,
) -> Outcome:
    """Apply a join on a connection that has not joined yet. See "Join"."""


def disconnect_player(state: RoomState, player_id: str, now: float) -> Outcome:
    """The player's connection closed. See "Disconnection"."""
```

### Join

`join_room` tries these steps in order and stops at the first that applies. The
steps marked with another spec are built by that spec; until then they never apply.

1. (spec 014) `message.resume_token` is in `state.removed_tokens`: refused,
   `reply = (ErrorMessage(code=REMOVED),)`, `close_sender = True`.
2. Resume: `message.resume_token` is the token of a player of `state.players`
   (spec 017 adds: and that player has been disconnected for at most
   `resume_window_seconds`; a player disconnected for longer times out in this
   step, becomes a past player of spec 032, and the join goes on with step 3).
   (Note from the lead, 2026-10-16: the clause after the semicolon was added for
   spec 032's seat back.) That player is joined again on this connection:
   - if their state is `disconnected`: state becomes `active`,
     `disconnected_at = None`, and one entry
     `PlayerStateChanged(player_id, state=active)`;
   - otherwise (another connection of theirs is still open): no entry; the hub
     closes the older connection with `SESSION_REPLACED_CLOSE_CODE` (4001) and
     sends it nothing else;
   - `last_seen_at = last_input_at = now`; nickname, colour, `is_host`,
     `joined_seq` and authorship are unchanged; `message.nickname` is ignored;
   - `reply = (snapshot_for(new_state, player_id),)`.
3. (spec 014) `state.settings.locked`: refused, `ROOM_LOCKED`, `close_sender`.
4. `len(state.players) == MAX_PLAYERS`: refused,
   `reply = (ErrorMessage(code=ROOM_FULL),)`, `close_sender = True`.

4a. (spec 032) Seat back: `message.resume_token` equals, compared with
`secrets.compare_digest`, the `resume_token` of a past player of the room (a
`PastPlayer` of `state.past_players`: a player who left the room by a time-out, or
on purpose, never one the host removed). That player is appended to
`state.players` as step 6 builds a new player, except that they keep their
`player_id` and `resume_token` (`new_player_id` and `new_resume_token` are not
used) and their `muted` flag (spec 032 decision 13); their nickname is the past
player's, made unique as "Duplicate nicknames" says; their colour is the past
player's when no player of `state.players` has it, else the lowest index 0 to 7
that none has; and `message.nickname` is ignored, as in a resume, so step 5 does
not apply. The `PastPlayer` leaves `past_players`. The
one entry is step 6's `PlayerJoined`, logged with the player's token, and
`reply = (snapshot_for(new_state, player_id),)`. Spec 032's "Seat back" gives the
whole rule. (Note from the lead, 2026-10-16: this step was added for spec 032's
seat back, its decision 11. It is numbered 4a so that steps 5 and 6, which other
specs cite, keep their numbers.) (Note from the lead, 2026-10-16: "and their
`muted` flag (spec 032 decision 13)" was added to the exceptions; without it,
building the player as step 6 does would unmute them (first review of spec 032).)

5. `normalize_nickname(message.nickname)` raises: refused,
   `reply = (ErrorMessage(code=INVALID_NICKNAME),)`, socket left open (the page may
   send another join).
6. New player, with `seq = state.seq + 1`:
   - `player_id = new_player_id`, `resume_token = new_resume_token`;
   - `nickname`: the normalised nickname, made unique (see "Duplicate nicknames");
   - `colour`: the lowest index 0 to 7 that no player of the room has;
   - `is_host`: True when no player of the room is host (the first joiner, spec
     011 decision 6), else False;
   - `state = active`, `joined_seq = seq`, `last_input_at = last_seen_at = now`;
   - appended at the end of `state.players`; `state.seq = seq`;
   - one entry `LogEntry(at=now, event=PlayerJoined(seq, player=<its view>),
     resume_token=new_resume_token)`;
   - `reply = (snapshot_for(new_state, new_player_id),)`, so the snapshot's `seq`
     includes the join and `players` includes the joiner.

The joiner's connection is not joined before this step, so it receives the
snapshot and not its own `player_joined` (spec 011 delivery order).

### Duplicate nicknames

Two nicknames are the same when they are equal, `a == b`. Every nickname is in
capitals (`normalize_nickname`), so two names that `str.upper()` puts in the
same capitals are already equal, and accents count: `ELODIE` and `ÉLODIE` differ.
(Note from the lead, 2026-10-16: "two that differ only in case" became "two names
that `str.upper()` puts in the same capitals": `STRAẞE` keeps its `ẞ` (U+1E9E), so it
is not stored like `Straße` (second review of the nickname rule, 2026-10-16).)
Taken nicknames are those
of `state.players` (present or disconnected). If the normalised nickname is taken,
the stored one is `f"{base} {n}"` for the smallest `n >= 2` that is not taken,
where `base` is the nickname cut to `20 - len(f" {n}")` characters, trailing
spaces removed. Examples: `Ana`, `ana`, `Ana` join in turn and get `ANA`, `ANA 2`,
`ANA 3`; a second `xxxxxxxxxxxxxxxxxxxx` (20 characters) gets
`XXXXXXXXXXXXXXXXXX 2`. (Note from the lead, 2026-10-16: the rule was
`a.casefold() == b.casefold()`, with `Elodie` and `Élodie` as the accents example,
and the examples gave `Ana`, `ana 2`, `Ana 3` and `xxxxxxxxxxxxxxxxxx 2` (human's
rule of 2026-10-16: nicknames in capitals).)

### Disconnection

`disconnect_player(state, player_id, now)`: if the player is in the room and not
`disconnected`: `state = disconnected`, `disconnected_at = now`, one entry
`PlayerStateChanged(player_id, state=disconnected)`. Otherwise the state is
unchanged and there is no entry. The player keeps their seat, colour, nickname and
letters. (Spec 013 adds clearing the selection; spec 017 adds the time-out that
frees the seat.)

### `nock.hub` and `nock.server` changes

- After a successful parse of the first `Join` on a socket, the hub runs
  `join_room` in the room task with `new_player_id = secrets.token_urlsafe(8)` and
  `new_resume_token = secrets.token_urlsafe(24)`, replacing spec 040's fixed
  snapshot. A refused join (`INVALID_NICKNAME`) leaves the socket waiting for
  another `Join`, as before the first join.
- After a successful join the socket is bound to that player, the snapshot's `you`
  (the new player, the resumed one, or, with spec 032, the one seated back): every
  later parsed message goes to `handle_message` (a second `Join` is ignored, no
  reply); the socket's close runs `disconnect_player`. (Note from the lead,
  2026-10-16: "the snapshot's `you`" and its parenthesis were added for spec 032's
  seat back, whose player keeps their id.)
- A close of a bound socket that the server itself made (4001, a refusal) does not
  run `disconnect_player` for the player that took it over.
- New constant in `nock.server` (re-exported from `nock.hub`):
  `SESSION_REPLACED_CLOSE_CODE: int = 4001`.

### Protocol (spec 039)

`ErrorCode.INVALID_NICKNAME = "invalid_nickname"` is part of spec 039 (added when
spec 039 was reopened on 2026-10-10, its decision 18); this spec gives it its
meaning (join step 5). No other protocol change.

### Client: `web/`

Stored in `localStorage`:

| Key | Value |
| --- | --- |
| `nock.identity.<CODE>` | JSON `{"player_id": "...", "resume_token": "...", "nickname": "..."}`, written after every snapshot from `snapshot.you`, `snapshot.resume_token` and the player's own `nickname` in `snapshot.players` |
| `nock.nickname` | the nickname of the last join this browser sent from the nickname form, as sent (normalised, so in capitals, without any duplicate suffix the server added), written when the snapshot answering that join arrives; a join sent at once (step 2, cases a and b) never writes it. (Note from the lead, 2026-10-16: "so in capitals" was added (human's rule of 2026-10-16: nicknames in capitals).) |

`nock.identity.<CODE>` is the one identity record of a player in a room, for every
player, the creator of spec 010 included. Spec 010's `nock.room.<CODE>` holds no
identity (only the grid number and the selection). A stored identity that is not
JSON, not an object, or lacks one of its three fields as a non-empty string is
ignored (as if absent).

Room page flow (replaces spec 040 step 2):

1. On mount, open the socket. `data-status="connecting"`.
2. When it opens, the first case that applies:
   - a. `nock.identity.<CODE>` is stored (valid): send
     `{"type": "join", "nickname": <stored nickname>, "resume_token": <stored token>}`,
     no form, and set `data-status="joining"`. This resumes the same player
     (join step 2), or seats the same player back after spec 017's time-out (join
     step 4a, spec 032), whether the identity came from the form or from case b.
     (Note from the lead, 2026-10-16: "or seats the same player back after spec
     017's time-out" and its reference were added for spec 032's seat back.)
   - b. No identity, and spec 010's `nock.room.<CODE>` holds a record (a JSON
     object) whose `grid` is a number, which means the room was created from the
     catalogue on this device: send
     `{"type": "join", "nickname": <nickname>, "resume_token": null}`, no form, and
     set `data-status="joining"`, where `<nickname>` is `nock.nickname` when it is
     stored and passes the rule of step 4, else `t("room.default_nickname")`.
   - c. Otherwise (no record, a record whose `grid` is not a number, or a record
     that is not a JSON object): send nothing, set `data-status="nickname"` and
     show the nickname form. (Note from the lead, 2026-10-15: "send nothing"
     leaves aside the heartbeat `ping` frames of spec 017, which the page may
     send at any time once the socket is open.)

   Since every snapshot stores the identity (step 5), a page reload after any
   successful join takes case a and is the same player.
3. Nickname form `data-testid="nickname-form"`, with heading `t("join.heading")`,
   an input `data-testid="nickname-input"` labelled `t("join.nickname_label")`,
   placeholder `t("room.default_nickname")`, prefilled with `nock.nickname` as
   stored, when there is one, and a submit button `data-testid="nickname-submit"`
   with text `t("join.submit")`. The input shows its text in capitals: its style
   has `text-transform: uppercase`, which also shows the placeholder in capitals.
   Its value keeps the text as the player types it, so an input method composes as
   usual and the caret stays where the player puts it. On submit, step 4's rule
   puts the value in capitals for the join it sends. (Note from the lead,
   2026-10-16: for the human's rule of 2026-10-16, a sentence had been added here:
   "The input's value is always in capitals: each change of its text, typed or
   pasted, sets the value to `toUpperCase()` of that text, and the prefill is
   `toUpperCase()` of `nock.nickname`." Before it, the input kept the text as typed.
   That sentence became the three sentences from "The input shows its text in
   capitals", and "prefilled with `nock.nickname` when stored" became "prefilled
   with `nock.nickname` as stored, when there is one". Rewriting the value at each
   change broke input methods (Chinese, Japanese, and every Android keyboard, which
   composes each word) and moved the caret wrongly after a `ß`, whose capitals are
   two characters, decision 12 (review of the nickname rule, 2026-10-16).)
4. On submit, the page applies the rule of `normalize_nickname` in TypeScript
   (`String.prototype.normalize("NFC")`, `trim()`, `toUpperCase()`,
   `normalize("NFC")` again, then `\p{L}`, `\p{Mn}` and `\p{Mc}` with the `u` flag;
   `\p{Me}` is not allowed) to the input's value, and checks the rules on the
   result of the second `normalize("NFC")`. (Note from the lead, 2026-10-16:
   "`toUpperCase()`, then" and "to the input's value" were added (human's rule of
   2026-10-16: nicknames in capitals).) (Note from the lead, 2026-10-16:
   "`normalize("NFC")` again, " and ", and checks the rules on the result of the
   second `normalize("NFC")`" were added: NFC comes before and after the capitals,
   as in `normalize_nickname`, decision 12 (review of the nickname rule,
   2026-10-16).)
   If it fails, it shows `data-testid="nickname-error"` with
   `t("join.error.length")` (length rule) or `t("join.error.characters")` (other
   rules) and sends nothing (Note from the lead, 2026-10-15: "sends nothing"
   means no `join` and no other message caused by the player's action; it
   leaves aside the heartbeat `ping` frames of spec 017, which the page may send
   at any time once the socket is open, also before a join). Otherwise it sends
   `{"type": "join", "nickname": <normalised>, "resume_token": null}`, sets
   `data-status="joining"` and disables the submit button.
5. On a snapshot: `data-status="joined"`, the form is removed, and
   `nock.identity.<CODE>` is stored; when the join it answers was sent from the
   form, `nock.nickname` is stored too (see the table above).
6. On `error` with code `invalid_nickname` (whichever case sent the join): back
   to `data-status="nickname"`, the form is shown with `t("join.error.characters")`.
7. On `error` with code `room_full`: `data-status="full"`, no form. Final.
8. On close with code 4001: `data-status="replaced"`. Final.

`data-status` values after this spec: `connecting`, `nickname`, `joining`,
`joined`, `full`, `replaced`, `not_found`, `throttled`, `closed`. Each has a
`fr.json` key `room.status.<value>` shown in `room-status`.

Room page root gains `data-you`: `""` before the first snapshot, then
`snapshot.you`.

Player list, shown once joined: `data-testid="roster"` with heading
`t("roster.heading")`, holding one `data-testid="roster-player"` per player, in the
order of the snapshot's `players` with joiners appended. Each item has
`data-player-id`, `data-colour` (the index), `data-state` (`active`, `idle` or
`disconnected`), `data-you` (`true` on the receiving player's item, else
`false`), a `data-testid="roster-colour"` swatch whose background is that
player's colour, and a `data-testid="roster-nickname"` element whose text is the
nickname as spec 040's `displayNickname` writes it, with capitalised words (`ANA`
shows as `Ana`), in plain text, never HTML. The own item also shows
`t("roster.you")`. (Note from the lead, 2026-10-16: "whose text is the nickname
(plain text, never HTML)" became the text above (human's rule of 2026-10-16:
nicknames in capitals).)

The kept snapshot is updated by these events (spec 040 "applying an event"):
`player_joined` appends the player; `player_state_changed` sets the player's
`state`; `player_left` removes the player.

Player colours: 8 CSS colours, one per index 0 to 7, defined once (for example
CSS custom properties `--player-colour-0` to `--player-colour-7`), pairwise
different. Later specs (013, 016) reuse them.

New `fr.json` keys:

| Key | Value |
| --- | --- |
| `join.heading` | `Choisissez un pseudo` |
| `join.nickname_label` | `Pseudo` |
| `join.submit` | `Entrer dans le salon` |
| `join.error.length` | `Le pseudo doit faire de 2 à 20 caractères.` |
| `join.error.characters` | `Lettres, chiffres, espaces, tirets, apostrophes et _ uniquement.` |
| `room.status.nickname` | `Choisissez un pseudo pour entrer.` |
| `room.status.joining` | `Entrée dans le salon…` |
| `room.status.full` | `Ce salon est complet (8 joueurs).` |
| `room.status.replaced` | `Ce salon est ouvert dans un autre onglet.` |
| `roster.heading` | `Joueurs` |
| `roster.you` | `(vous)` |

### Test harness

As spec 011. Seeded rooms: `new_room(...)` then `model_copy(update=...)` (or a
new `RoomState(...)`) with chosen `cells` and `players`, registered with
`registry.add_room(state)`. Mocked-socket tests seed `localStorage` with
`context.add_init_script(...)` when they need a stored identity, room record or
nickname. Every browser criterion runs in Chromium, Firefox and WebKit
(`specs/_architecture.md`); no check of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-3.2.1) (Python; WebSocket; browser with live server) Given a valid link, when I enter a nickname of 2 to 20 characters, then I am in the room. Python: `normalize_nickname` returns `"ANA"` for `"  Ana  "`, `"ÉLODIE"` for `"Élodie"`, and returns `text.upper()` for each `text` among `"Jean-Luc"`, `"O'Neil"`, `"O’Neil"`, `"bob_42"`, `"Anne Marie"`, `"Zoë"`, `"12"`, `"राम"` (`"राम"`, whose `ा` is category Mc) and 20 times `x`; it raises `ValueError` for `"A"`, `""`, `"   "`, 21 times `x`, `"<b>Eve</b>"`, `"Ana!"`, `"a@b"`, `"Ana\tB"`, `"--"` and `"Ana⃝"` (`"Ana⃝"`, whose `⃝` is category Me). WebSocket: on a fresh FX-01 room, the join `{"type": "join", "nickname": " Ana ", "resume_token": null}` is answered by a `Snapshot` with `seq == 1` whose `players` is one `PlayerView` with `player_id == snapshot.you`, `nickname == "ANA"`, `colour == 0`, `state == "active"`, `is_host is True`, `muted is False`, `selection is None`; `registry.room_state(code).players` holds the same player. The join `{"type": "join", "nickname": "<b>Eve</b>", "resume_token": null}` is answered by `ErrorMessage(code="invalid_nickname")`, adds no player, and a following valid join on the same socket gets a `Snapshot`. Browser: opening `/r/<code>` shows `nickname-form`; entering `Ana` and submitting reaches `data-status="joined"`, and `roster` holds one `roster-player` with `data-you="true"` whose `roster-nickname` reads `Ana`; entering `A` instead shows `nickname-error` with `fr.json["join.error.length"]` and the page stays on `data-status="nickname"`. (Note from the lead, 2026-10-16: the Python part said that `normalize_nickname` returns `"Ana"` and `"Élodie"` and "keeps" the other accepted values, and the WebSocket part had `nickname == "Ana"`; the roster still reads `Ana`, through `displayNickname` (human's rule of 2026-10-16: nicknames in capitals).)
- **AC-2** (AC-3.2.2) (Python; WebSocket) Each player gets a colour no other player in the room has. A duplicate nickname gets a numeric suffix. Python: 8 successive `join_room` calls on a fresh room with nicknames `Ana`, `ana`, `Ana`, `Bob`, `Cy`, `Di`, `Ed`, `Flo` give colours `0` to `7` and nicknames `ANA`, `ANA 2`, `ANA 3`, `BOB`, `CY`, `DI`, `ED`, `FLO`; the first is host and no other is. On a room holding a player named `STRAẞE`, whose `ẞ` is U+1E9E, the capital sharp s, which `str.upper()` keeps, a `join_room` with `Strasse` stores `STRASSE`, with no suffix: nicknames compare exactly, and `ẞ` and `SS` differ. (Note from the lead, 2026-10-16: the sentence before this note was added, to pin the exact comparison (review of the nickname rule, 2026-10-16).) WebSocket: three clients join a FX-01 room as `Ana`, `Ana`, `Bob`; the third client's snapshot lists `ANA` (colour 0), `ANA 2` (colour 1), `BOB` (colour 2); the first client receives `player_joined` events with seq 2 and 3 holding the views of `ANA 2` and `BOB`. (Note from the lead, 2026-10-16: the Python nicknames were `Ana`, `ana 2`, `Ana 3`, `Bob`, `Cy`, `Di`, `Ed`, `Flo`, and the WebSocket ones `Ana`, `Ana 2`, `Bob` (human's rule of 2026-10-16: nicknames in capitals).)
- **AC-3** (AC-3.2.3) (WebSocket) I see the current letters, timer and hint budget within 1 second of joining. Given a FX-01 room added with `add_room` whose cell (1, 0) holds `T` (author `p9`) and (1, 1) holds `A` (author `p9`), and whose `reveal_budget` is `RevealBudget(letters=3, words=1)`, when a client sends a join, then a `Snapshot` arrives less than 1.0 second (measured with `time.monotonic()`) after the join was sent, its `grid == grid_state(registry.room_state(code))`, its cell (1, 0) has `letter == "T"` and `author == "p9"`, its `reveal_budget == RevealBudget(letters=3, words=1)`, and its `timer_elapsed_ms == 0` with `timer_running is False`.
- **AC-4** (AC-3.2.4) (Python; WebSocket; browser with live server) Joining a room that already has 8 players shows "room full" and does not add me. Python: `join_room` on a room with 8 players returns `reply == (ErrorMessage(code="room_full", ...),)` (code compared), `close_sender is True`, no entry, and the same state. WebSocket: 8 clients join a FX-01 room; a ninth join is answered by `ErrorMessage(code="room_full")` and then a close with code 1000; the first client receives no event for it; `room_state` still holds 8 players. Browser: for a room added with 8 players (all `disconnected`), opening `/r/<code>` and submitting `Zoé` reaches `data-status="full"` and `room-status` shows `fr.json["room.status.full"]`.
- **AC-5** (new) (WebSocket; browser with live server) Reloading the page keeps me the same player. WebSocket: client A joins as `Ana` and client B as `Bob`; when A's socket closes, B receives `PlayerStateChanged(player_id=<A>, state="disconnected")`; a new socket that sends `{"type": "join", "nickname": "Autre", "resume_token": <A's token>}` receives a `Snapshot` with `you == <A>`, A's view still `nickname == "Ana"`, `colour == 0`, `is_host is True`, `state == "active"`, and B receives `PlayerStateChanged(player_id=<A>, state="active")`; the room still has 2 players. Browser: after joining as `Ana` and reloading the page, the room page reaches `data-status="joined"` without showing `nickname-form`, with the same `data-you` as before the reload, and `roster` holds one player.
- **AC-6** (new) (browser with mocked socket) The room page joins at once only with a stored identity or for a room created from the catalogue on this device. On `/r/ABC123`, `localStorage` seeded before `page.goto`: (a) with `nock.identity.ABC123` = `{"player_id": "p1", "resume_token": "r7Kq2mXo9vB4tY1zW8nP", "nickname": "Ana 2"}`, the first frame the page sends parses to `Join(nickname="Ana 2", resume_token="r7Kq2mXo9vB4tY1zW8nP")`, the page shows `data-status="joining"` and no `nickname-form` exists; the same holds when `nock.room.ABC123` = `{"grid": 1, "selection": null}` is also seeded. (b) With no identity, `nock.room.ABC123` = `{"grid": 1, "selection": null}` and `nock.nickname` = `Zoé`, the first frame parses to `Join(nickname="Zoé", resume_token=None)` and no `nickname-form` exists; with `nock.nickname` absent, or set to `A`, it parses to `Join(nickname=fr.json["room.default_nickname"], resume_token=None)`. (c) With no identity and `nock.room.ABC123` = `{"grid": null, "selection": null}`, or no record, or only `nock.identity.ZZZZZZ` stored (another room), the page sends no frame (Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted), reaches `data-status="nickname"` and shows `nickname-form`, whose input holds `Zoé` when `nock.nickname` = `Zoé` is seeded (room page flow step 3) and is empty otherwise. (Note from the lead, 2026-10-16: the input held `Zoé`, the stored text as it was (human's rule of 2026-10-16: nicknames in capitals).) (Note from the lead, 2026-10-16: the change that the note before this one records is undone: the input held `ZOÉ`, the `toUpperCase()` of the stored text, and it holds `Zoé` again, as before 2026-10-16. The input's value keeps the stored text, which CSS shows in capitals (room page flow step 3), since rewriting the value broke input methods and the caret (review of the nickname rule, 2026-10-16).)
- **AC-7** (new) (browser with mocked socket) After a join, the identity is always stored and the remembered nickname only for a join from the form. On `/r/ABC123` with nothing seeded, submitting the form with `Ana` typed and the mock answering with a FX-01 snapshot (`you` = `p1`, `resume_token` = `r7Kq2mXo9vB4tY1zW8nP`, players `p1` named `ANA 2`) makes `localStorage["nock.identity.ABC123"]` parse to `{"player_id": "p1", "resume_token": "r7Kq2mXo9vB4tY1zW8nP", "nickname": "ANA 2"}` and `localStorage["nock.nickname"]` equal `ANA`. In case (b) of AC-6 with `nock.nickname` absent, after the same snapshot with `p1` named `INVITÉ`, `nock.identity.ABC123` holds `p1`, that token and `INVITÉ`, and `nock.nickname` is still absent. (Note from the lead, 2026-10-16: `nock.nickname` was to equal `Ana`, as typed; the mock's nicknames `Ana 2` and `Invité`, and the identity's, are now written in capitals, as the server sends them (human's rule of 2026-10-16: nicknames in capitals).)
- **AC-8** (new, decision 12) (Python; browser with live server; browser with mocked socket) A nickname is typed and stored in capitals, and shown with capitalised words. Python: `normalize_nickname` returns `"ANA"` for `"ana"` and for `"Ana"`, and `"STRASSENBAHNFAHRERIN"` (20 characters) for `"Straßenbahnfahrerin"` (19), whose `ß` gives `SS`; it raises `ValueError` for 11 times `ß`, whose capitals have 22 characters. A name typed in small letters and the same name typed in the capitals that `str.upper()` gives are stored alike: `normalize_nickname("Παΐσιος")`, whose `ΐ` is U+0390, and `normalize_nickname` of U+03A0 U+0391 U+03AA U+0301 U+03A3 U+0399 U+039F U+03A3 (`ΠΑ`, then `Ϊ` U+03AA and the combining acute accent U+0301, then `ΣΙΟΣ`) both return U+03A0 U+0391 U+03AA U+0301 U+03A3 U+0399 U+039F U+03A3 (8 characters). (Note from the lead, 2026-10-16: "in capitals" became "in the capitals that `str.upper()` gives": `STRAẞE` keeps its `ẞ` (U+1E9E), so it is not stored like `Straße` (second review of the nickname rule, 2026-10-16).) The length is counted after the second NFC: `normalize_nickname` of `ΐ` (U+0390) followed by 18 times `α` (U+03B1) returns U+03AA U+0301 followed by 18 times U+0391 (20 characters), so it is accepted. Two texts that are the same for Unicode are stored alike: `normalize_nickname("ᾀνα")`, whose `ᾀ` is U+1F80, and `normalize_nickname` of U+03B1 U+0345 U+0313 U+03BD U+03B1 (`α`, then the combining ypogegrammeni U+0345 and the combining comma above U+0313, then `να`) both return U+1F08 U+0399 U+039D U+0391 (4 characters). Every value that `normalize_nickname` returns in AC-1 and in AC-8 is in NFC: `unicodedata.is_normalized("NFC", value)` is True. (Note from the lead, 2026-10-16: the four sentences before this note were added (review of the nickname rule, 2026-10-16).) Live server: on `/r/<code>`, typing `ana` in `nickname-input` shows it in capitals: the input's computed `text-transform` is `uppercase`, and its value stays `ana`. After the submit, the room page reaches `data-status="joined"` and the own `roster-nickname` reads `Ana`. (Note from the lead, 2026-10-16: typing `ana` made the input's value `ANA`, rewritten as it was typed; the field now shows capitals through CSS, room page flow step 3 (review of the nickname rule, 2026-10-16).) Mocked socket, the page's rule in case (b) of AC-6, with no identity and `nock.room.ABC123` = `{"grid": 1, "selection": null}`: with `nock.nickname` = `ΐ` (U+0390) followed by 18 times `α` (U+03B1), which counts 20 characters after the capitals and the second NFC (edge case "Length"), the first frame parses to `Join(nickname=<that stored text, unchanged>, resume_token=None)`; with `nock.nickname` = 11 times `ß` (U+00DF), 22 characters in capitals, it parses to `Join(nickname=fr.json["room.default_nickname"], resume_token=None)`. (Note from the lead, 2026-10-16: the two runs of case (b) were added (review of the nickname rule, 2026-10-16).) Mocked socket, every place that shows a nickname: given a FX-01 snapshot whose players are, in this order, `p1` `JEAN-LUC` (`you`, host), `p2` `D'ARTAGNAN`, `p3` `ANA 2`, `p4` `O’NEIL` (whose apostrophe is U+2019; muted, `muted` True) and `p5` `ΝΊΚΟΣ` (whose `Ί` is U+038A), whose `chat` holds one line from each of them in that order, whose cells (1, 0) to (1, 4) hold letters by `p1` to `p5`, and whose `flags` hold `p4` and `p5` on IDES (`ClueRef(row=0, column=3, clue_index=0)`). Below, `Νίκος` is U+039D U+03AF U+03BA U+03BF U+03C2, ending with the final sigma, and `O’Neil` keeps U+2019. On that page:
  - the five `roster-nickname`, in roster order, read `Jean-Luc`, `D'Artagnan`, `Ana 2`, `O’Neil` and `Νίκος`;
  - the `remove-player` in the `roster-player` of `p2`, `p3`, `p4` and `p5` (spec 014) has the `aria-label` `Retirer D'Artagnan du salon`, `Retirer Ana 2 du salon`, `Retirer O’Neil du salon` and `Retirer Νίκος du salon` (`fr.json["host.remove_label"]`);
  - the `clue-flag-label` of IDES (spec 021), in the `clue` of the clue cell (0, 3) with `data-clue-index="0"`, reads `Bloqué : O’Neil, Νίκος` (`fr.json["flag.marker_label"]`);
  - with `authors-switch` on (spec 019), a tap on each of the cells (1, 0) to (1, 4) shows `clue-bar-author` reading `Lettre de Jean-Luc`, `Lettre de D'Artagnan`, `Lettre de Ana 2`, `Lettre de O’Neil` and `Lettre de Νίκος`;
  - with the chat panel open (spec 022), the five `chat-author` read the same five names, in the order of the lines;
  - in that panel, `chat-moderation` holds four `mute-row`, for `p2` to `p5` in roster order, whose `mute-name` read `D'Artagnan`, `Ana 2`, `O’Neil` and `Νίκος`; the `mute-player` of `p2`, `p3` and `p5` reads `fr.json["chat.mute"]`, with the `aria-label` `Couper la discussion de D'Artagnan`, `Couper la discussion de Ana 2` and `Couper la discussion de Νίκος` (`fr.json["chat.mute_label"]`), and that of `p4`, who is muted, reads `fr.json["chat.unmute"]`, with the `aria-label` `Rétablir la discussion de O’Neil` (`fr.json["chat.unmute_label"]`).

  (Note from the lead, 2026-10-16: added (human's rule of 2026-10-16: nicknames in capitals).) (Note from the lead, 2026-10-16: the last part read: "given a FX-01 snapshot whose players are `p1` (`you`) `JEAN-LUC`, `p2` `D'ARTAGNAN` and `p3` `ANA 2`, whose `chat` holds one line from each, and whose cells (1, 0), (1, 1) and (1, 2) hold letters by `p1`, `p2` and `p3`: the three `roster-nickname` read `Jean-Luc`, `D'Artagnan` and `Ana 2`; with the chat panel open (spec 022), the three `chat-author` read the same; and with `authors-switch` on (spec 019), a tap on each of the three cells shows `clue-bar-author` reading `Lettre de Jean-Luc`, `Lettre de D'Artagnan` and `Lettre de Ana 2`." The review found no test that would notice a missing `displayNickname` in the mute rows and their labels, the host's remove labels, a clue flag's names, or `’` as a word break. So the snapshot gained `p4` and `p5`, `p1` as host, `p4`'s mute, the letters at (1, 3) and (1, 4) and the flags on IDES, with the list of what each place reads (review of the nickname rule, 2026-10-16).)

## Edge cases and errors

- Nickname characters (AC-1): letters from any script (`Zoë`, `Łukasz`, `Ἀλέξης`,
  `राम`) with the marks that attach to them (categories Mn and Mc, such as the
  Devanagari vowel sign U+093E in `राम`), ASCII digits, space, `-`, `'`, `’`, `_`.
  Rejected: `<`, `>`, `&`, `"`, `@`, `!`, `.`, emoji, enclosing marks (category
  Me, such as U+20DD in `Ana⃝`), tabs, newlines, non-ASCII digits (`٣`). A nickname of digits only
  (`"12"`) is accepted; one made only of punctuation (`"--"`, `"_ _"`) is not.
- Length (AC-1, AC-8): counted on the result after the second NFC (NFC,
  trimming, the capitals, then NFC again), in code points: `"É"` is
  `É`, one character, so `"É"` alone is too short. Leading and trailing
  spaces are removed; inner spaces are kept as typed (`"Anne  Marie"` keeps two).
  A letter whose capital is longer counts as its capital: 11 times `ß` passes spec
  039's length check (11 characters) and gets `invalid_nickname` (22 in capitals).
  (Note from the lead, 2026-10-16: "AC-8", "on the capitals" and the sentence
  before this note were added; the item said "counted after NFC and trimming"
  (human's rule of 2026-10-16: nicknames in capitals).) A capital that the second
  NFC recomposes counts as recomposed: `ΐ` (U+0390) followed by 18 times `α`
  counts 20 and is accepted, since the capital of `ΐ` is U+03AA U+0301 after the
  second NFC, 2 characters (U+0399 U+0308 U+0301 before it, which would make 21).
  (Note from the lead, 2026-10-16: "on the capitals, after NFC and trimming"
  became "on the result after the second NFC (NFC, trimming, the capitals, then
  NFC again)", and the sentence before this note was added (review of the
  nickname rule, 2026-10-16).)
- Protocol length first (AC-1): a nickname of 21 characters after trimming fails
  `parse_client_message` (spec 039) and gets `invalid_message`, not
  `invalid_nickname`; the page never sends one.
- Duplicate check (AC-2): exact, so accent-sensitive, and case never tells two
  nicknames apart since all are in capitals; the suffix is added to
  the joiner only, a newcomer or a past player seated back (step 4a, spec 032),
  never to a player already in the room; a resumed player keeps their nickname. A
  player called `ANA 2` already in the room pushes a second `Ana` to `ANA 3`, and
  `ANA`, who timed out, comes back as `ANA 2` when `ana` joined meanwhile as `ANA`.
  (Note from the lead, 2026-10-16: "the newcomer only" became "the joiner only, a
  newcomer or a past player seated back (step 4a, spec 032), never to a player
  already in the room", and the example of `Ana` who timed out was added.) (Note
  from the lead, 2026-10-16: "case-insensitive, accent-sensitive" became the text
  before the first semicolon, and the examples, which named `Ana 2`, `Ana 3`, `Ana`
  and `Ana 2`, now write the stored nicknames in capitals (human's rule of
  2026-10-16: nicknames in capitals).)
- Colours (AC-2): a freed index (spec 017 time-out, spec 014 removal) is reused by
  the next joiner. Disconnected players keep theirs. A past player seated back
  (step 4a, spec 032) gets their old index again when no player of `players` has
  it, else the lowest free one, so they may come back in another colour. (Note from
  the lead, 2026-10-16: the last sentence was added for spec 032's seat back.)
- Full room (AC-4): disconnected players hold their seat until they leave (spec 017
  time-out). A resume (step 2) is accepted in a full room, since the player is
  already counted. A seat back (step 4a) is not: a past player holds no seat, so a
  full room refuses them with `room_full`, and they stay a past player, whom the
  same token seats back once a seat is free (spec 032). (Note from the lead,
  2026-10-16: the last sentence was added for spec 032's seat back.)
- Unknown resume token (AC-5): a token that matches no player and no past player
  (an old room, a forged value, a past player dropped by spec 032's cap of 100) is
  ignored and the join is a new player with the join's nickname. A past player's
  token is not unknown: step 4a seats that player back (spec 032). (Note from the
  lead, 2026-10-16: "and no past player", the dropped past player and the last
  sentence were added for spec 032's seat back; the item said "a token that
  matches no player (an old room, a forged value)".)
- Two tabs (AC-5): the same identity opened in a second tab takes over; the first
  tab's socket closes with 4001 and shows `replaced`, with no event to the others.
- Host (AC-1, AC-2): the first player is host; the host's disconnection does not
  move the role (spec 014 AC-3 does, after 60 seconds).
- Snapshot of the joiner (AC-1, AC-3): its `seq` is that of its own
  `player_joined`; the joiner never receives that event.
- Order of refusals (AC-4): removed, then resume, then locked, then full, then seat
  back (step 4a, spec 032), then nickname. A full room answers `room_full` even to
  an invalid nickname, and a locked or full room refuses a past player's token as
  it refuses a newcomer. A seat back is never refused for its nickname, which it
  ignores. (Note from the lead, 2026-10-16: "then seat back (step 4a, spec 032)",
  the clause on a past player's token and the last sentence were added for spec
  032's seat back; the order went from full straight to nickname.)
- Socket after a refusal (AC-4): `room_full` closes the socket (code 1000);
  `invalid_nickname` does not.
- Form (AC-1): the submit button is disabled while `joining`; pressing Enter in the
  input submits. An identity stored for another room code is not used.
- Corrupt identity (AC-6): `nock.identity.ABC123` set to `not json`, `[]`,
  `{"player_id": "p1"}` or with an empty `resume_token` is ignored; the page goes
  on with case b or c.
- Room record without a number (AC-6): a record whose `grid` is `null`, `"1"` or
  missing gives case c (the form); only a JSON number gives case b.
- Creator refused (AC-6): a join sent by case b and answered `invalid_nickname`
  shows the form (step 6); the form's join then follows the usual rules.
- Remembered nickname (AC-7): the form's nickname is stored as sent (`ANA`), not
  as the server made it unique (`ANA 2`); the identity holds the server's
  nickname. (Note from the lead, 2026-10-16: the examples were `Ana` and `Ana 2`
  (human's rule of 2026-10-16: nicknames in capitals).)
- Answers (AC-3): the snapshot is built from `grid_state`, never from `grid`.

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Presence states shown in the roster (idle, text of the state): spec 013.
- Host controls (remove, lock): spec 014.
- Changing one's nickname or colour after joining; choosing a colour.
- Keeping the case a player typed: a nickname is stored in capitals and shown with
  capitalised words, so `McLean` shows as `Mclean` (decision 12). (Note from the
  lead, 2026-10-16: added (human's rule of 2026-10-16: nicknames in capitals).)
- Leaving the room on purpose (spec 039: closing the socket is leaving); the
  `left` leave reason is not produced in the MVP.
- Showing the timer (spec 027) and the reveal budget (spec 024); the snapshot
  carries them, which is what AC-3 checks.
- Accounts (spec 033).

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written,
except: item 1, settled by reopening spec 039; item 7, completed by the human's
decision on the creator's nickname (one identity record per room, shared with
spec 010). Each one is already part of the spec above.

1. Protocol: an error code for a refused nickname. Options: reuse
   `invalid_message`, or add `invalid_nickname` to `ErrorCode`. Pick: add
   `invalid_nickname`. Decision (human): spec 039 was reopened to add it (spec
   039 decision 18, with its AC-9 count of error codes updated there), so it is
   no longer a change this spec makes.
2. Spec 040 amendments. This spec changes what spec 040's tests observe: AC-8
   expects `seq == 0` and `players == ()`; AC-16 expects `data-seq="0"` with no
   nickname step; AC-18 expects the first sent message to be
   `Join(nickname="Invité")` and `data-status="connecting"` until the snapshot.
   Pick: the lead reopens spec 040 in this spec's branch, as was done before, with:
   AC-8 `seq == 1` and `players == (<the joiner's view>,)`; AC-16 through
   `enter_room` with `data-seq="1"`; AC-18 the first message after submitting the
   form with `Ana` is `Join(nickname="Ana", resume_token=None)`, and the page shows
   `data-status="nickname"` before the submit and `joining` after it.
3. Allowed characters (answered by the human): letters with accents, digits, spaces,
   hyphens, apostrophes, underscores. Picks within that answer: any Unicode letter
   script; ASCII digits only; both `'` and `’` (phones type `’`); combining marks
   allowed; NFC first; at least one letter or digit.
4. Duplicate suffix. Options: `Ana2`, `Ana 2`, `Ana (2)`. Pick: `Ana 2`, which
   stays a valid nickname; exact comparison, every nickname being in capitals
   (decision 12). (Note from the lead, 2026-10-16: this read "comparison by
   `casefold()`" (human's rule of 2026-10-16: nicknames in capitals).)
5. Host. Pick: the first joiner (spec 011 decision 6); if the room has no host
   (spec 014, 017), the next joiner becomes host.
6. Basic resume here. Spec 017 owns reconnection, but without a resume a page
   reload would add a new player and fill the room. Pick: this spec stores the
   identity and resumes with the token (AC-5); spec 017 adds the 5-minute window,
   the time-out and automatic reconnection.
7. Remembered nickname. Options: join at once with `nock.nickname`, or prefill the
   form with it. Pick: prefill, so each room asks once, for a guest arriving by
   link. Decision (human) for the creator: the player who starts a grid from the
   catalogue (spec 010) joins at once, no form, with `nock.nickname` or, if none
   (or not valid), `t("room.default_nickname")` (`Invité`). One identity record
   per room: `nock.identity.<CODE>` is the identity of everyone, the creator
   included; spec 010's `nock.room.<CODE>` keeps only the grid number and the
   selection (kept separate because it exists before the first snapshot and also
   for rooms joined by link). The room page's rule is "Room page flow" step 2:
   (a) stored identity, join at once with its nickname and token; (b) otherwise a
   room record with a numeric `grid`, join at once as a new player with
   `nock.nickname` or `Invité`; (c) otherwise the form. A reload after any join
   takes (a), so it resumes the same player (AC-5 here, spec 010 AC-3). To keep
   `nock.nickname` meaning "what I typed", it is written only after a join sent
   from the form, as sent (AC-7). AC-6 and AC-7 check the rule.
8. "Within 1 second" (AC-3). Pick: measured on the WebSocket from sending the join
   to receiving the snapshot, on localhost. Not covered: a slow mobile network
   (spec 036 measures under a 4G profile). The timer and budget are checked in the
   snapshot, not on screen, until specs 024 and 027 show them.
9. Two tabs with one identity. Pick: the newest connection wins; the older one is
   closed with 4001 and shows `replaced`, so two tabs never fight in a loop.
10. Player list in this spec. The backlog puts the roster in spec 013, but this
    spec has to show who joined, and spec 037 AC-4 needs a nickname on screen
    before 013 is built. Pick: a plain list here (nickname, colour, `data-state`);
    spec 013 adds the visible state and the rest of presence.

Added after the review, decided by the lead on 2026-10-11 under the human's
instruction to take technical decisions. It is part of the spec above.

11. Combining marks. Reviewer finding: allowing only category Mn refused many
    Indic-script names, for example `राम` (U+0930 U+093E U+092E, where U+093E is
    a spacing mark, category Mc), which contradicts "letters from any script"
    and item 3. Decision: allow categories Mn and Mc, the marks that attach to
    letters and that Indic and other scripts need; still refuse Me (enclosing
    marks such as U+20DD, which are decorative). The Python rule
    (`normalize_nickname`) and the client rule (Room page flow step 4) change
    together; AC-1 gains `राम` as accepted and `Ana⃝` as refused. No criterion
    is renumbered.

Decided by the human on 2026-10-16. It is part of the spec above. (Note from the
lead, 2026-10-16: this group was added (human's rule of 2026-10-16: nicknames in
capitals).)

12. Nicknames in capitals. The human's words: "Force player names to be input as
    caps, stored as caps, and rendered as Camel case. Make things simple from a
    backend perspective, don't generate edge cases by making things
    complicated." "Camel case" means capitalised words, `ANA` shown as `Ana`: the
    lead's reading, which the human was told. So `normalize_nickname` puts the
    nickname in capitals with `str.upper()` right after NFC and stripping, applies
    NFC again to the capitals, and checks its rules on that form, so a letter
    whose capital is longer (`ß` gives `SS`) needs no rule of its own; duplicates
    compare exactly, with no `casefold()`; the nickname input shows its text in
    capitals through CSS and keeps its value as typed; and every page shows a
    nickname through spec 040's `displayNickname`. (Note from the lead,
    2026-10-16: ", applies NFC again to the capitals," was added, and "the
    nickname input holds capitals as it is typed" became "the nickname input shows
    its text in capitals through CSS and keeps its value as typed" (review of the
    nickname rule, 2026-10-16).) What it changed here:
    `normalize_nickname`, "Duplicate nicknames", the `nock.nickname` row, steps 3
    and 4 of the room page flow, the player list, AC-1, AC-2, AC-6, AC-7, the new
    AC-8, the edge cases "Length", "Duplicate check" and "Remembered nickname",
    decision 4 and "Out of scope". Spec 039's "Nicknames in capitals" says how the
    other specs read a nickname written in another case; spec 040 holds
    `displayNickname`; specs 022, 028, 029, 032, 033, 035, 037 and 038 were
    refined where a comparison, a stored value or a shown text changed.

    After the first review of the rule, the lead decided on 2026-10-16 how the
    capitals are made, typed and shown:

    - NFC before and after the capitals. The capitals of 8 Greek letters are not
      in NFC: U+0390, U+03B0, U+1FD2, U+1FD3, U+1FD7, U+1FE2, U+1FE3 and U+1FE7.
      For example `ΐ` (U+0390) gives U+0399 U+0308 U+0301, where NFC is U+03AA
      U+0301. So `Παΐσιος` typed in small letters and the same name typed in
      capitals were stored differently, and two players could show the same name
      with no suffix; the second NFC recomposes after the capitals. The first NFC
      puts accents in their canonical order before the capitals: without it, `α`
      followed by U+0345 and U+0313, the same text as `ᾀ` (U+1F80) for Unicode,
      would give `ΑἸ` (U+0391 U+1F38), where `ᾀ` gives `ἈΙ` (U+1F08 U+0399), a
      visibly different name.
    - The field in capitals through CSS. The field shows capitals with
      `text-transform: uppercase` rather than rewriting its value, because
      rewriting the value at each change of its text breaks input methods
      (Chinese, Japanese, and every Android keyboard, which composes each word)
      and moves the caret wrongly after a `ß`, whose capitals are two characters.
      Step 4 puts the value in capitals for the join it sends.
    - The display keeps Greek's final sigma: spec 040's `displayNickname` puts the
      whole nickname through one `toLowerCase()` before it puts the first
      character of each word in capitals, so a Greek name that ends with `Σ` shows
      with the final `ς` (U+03C2), not `σ` (U+03C3).
    - AC-2, and spec 032 AC-4, pin the exact comparison: `STRAẞE`, whose `ẞ` is
      U+1E9E, and `STRASSE` are two nicknames. AC-8 also reads the nickname in
      the places that the review found untested: the chat's mute rows and their
      labels, the host's remove labels and a clue flag's names, with `’` (U+2019)
      as a word break.

    What these changed here: `normalize_nickname`, steps 3 and 4 of the room page
    flow, AC-2, AC-6, AC-8, the edge case "Length" and this decision. (Note from
    the lead, 2026-10-16: this paragraph and its list were added (review of the
    nickname rule, 2026-10-16).)

## Open questions

None.
