---
id: "012"
title: Guest join
status: approved
---

# 012 - Guest join

Epic E3 Rooms and presence (US-3.2) · Release: MVP · Epic depends on: E2
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine (`nock.room`,
`nock.hub`, runtime, test harness) is defined in spec 011; the messages are those of
spec 039; the room page those of specs 040 and 006.

## Goal

As an invited player, I want to join with only a nickname, so that I am playing within seconds.

A room is one grid shared by up to 8 players and reached by a link.

## Public interface

### `nock.room` functions built by this spec

```python
# src/nock/room.py (behaviour defined here; models in spec 011)

NICKNAME_PUNCTUATION: str = " -'’_"     # space, hyphen, apostrophes ' and ’, underscore


def normalize_nickname(text: str) -> str:
    """Return the nickname as stored: NFC-normalised, then stripped.

    Rules, checked on the result:
    - 2 to 20 characters (code points);
    - each character is a Unicode letter (category L*), a combining mark
      (category Mn), an ASCII digit 0-9, or one of NICKNAME_PUNCTUATION;
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
   `resume_window_seconds`). That player is joined again on this connection:
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

Two nicknames are the same when `a.casefold() == b.casefold()` (accents count:
`Elodie` and `Élodie` differ). Taken nicknames are those of `state.players`
(present or disconnected). If the normalised nickname is taken, the stored one is
`f"{base} {n}"` for the smallest `n >= 2` that is not taken, where `base` is the
nickname cut to `20 - len(f" {n}")` characters, trailing spaces removed. Examples:
`Ana`, `ana`, `Ana` join in turn and get `Ana`, `ana 2`, `Ana 3`; a second
`xxxxxxxxxxxxxxxxxxxx` (20 characters) gets `xxxxxxxxxxxxxxxxxx 2`.

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
- After a successful join the socket is bound to that player: every later parsed
  message goes to `handle_message` (a second `Join` is ignored, no reply); the
  socket's close runs `disconnect_player`.
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
| `nock.nickname` | the nickname of the last join this browser sent from the nickname form, as sent (normalised, without any duplicate suffix the server added), written when the snapshot answering that join arrives; a join sent at once (step 2, cases a and b) never writes it |

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
     (join step 2), whether the identity came from the form or from case b.
   - b. No identity, and spec 010's `nock.room.<CODE>` holds a record (a JSON
     object) whose `grid` is a number, which means the room was created from the
     catalogue on this device: send
     `{"type": "join", "nickname": <nickname>, "resume_token": null}`, no form, and
     set `data-status="joining"`, where `<nickname>` is `nock.nickname` when it is
     stored and passes the rule of step 4, else `t("room.default_nickname")`.
   - c. Otherwise (no record, a record whose `grid` is not a number, or a record
     that is not a JSON object): send nothing, set `data-status="nickname"` and
     show the nickname form.

   Since every snapshot stores the identity (step 5), a page reload after any
   successful join takes case a and is the same player.
3. Nickname form `data-testid="nickname-form"`, with heading `t("join.heading")`,
   an input `data-testid="nickname-input"` labelled `t("join.nickname_label")`,
   placeholder `t("room.default_nickname")`, prefilled with `nock.nickname` when
   stored, and a submit button `data-testid="nickname-submit"` with text
   `t("join.submit")`.
4. On submit, the page applies the rule of `normalize_nickname` in TypeScript
   (`String.prototype.normalize("NFC")`, `trim()`, `\p{L}` and `\p{Mn}` with the
   `u` flag). If it fails, it shows `data-testid="nickname-error"` with
   `t("join.error.length")` (length rule) or `t("join.error.characters")` (other
   rules) and sends nothing. Otherwise it sends
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
nickname (plain text, never HTML). The own item also shows `t("roster.you")`.

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

- **AC-1** (AC-3.2.1) (Python; WebSocket; browser with live server) Given a valid link, when I enter a nickname of 2 to 20 characters, then I am in the room. Python: `normalize_nickname` returns `"Ana"` for `"  Ana  "`, `"Élodie"` for `"Élodie"`, and keeps `"Jean-Luc"`, `"O'Neil"`, `"O’Neil"`, `"bob_42"`, `"Anne Marie"`, `"Zoë"`, `"12"` and 20 times `x`; it raises `ValueError` for `"A"`, `""`, `"   "`, 21 times `x`, `"<b>Eve</b>"`, `"Ana!"`, `"a@b"`, `"Ana\tB"` and `"--"`. WebSocket: on a fresh FX-01 room, the join `{"type": "join", "nickname": " Ana ", "resume_token": null}` is answered by a `Snapshot` with `seq == 1` whose `players` is one `PlayerView` with `player_id == snapshot.you`, `nickname == "Ana"`, `colour == 0`, `state == "active"`, `is_host is True`, `muted is False`, `selection is None`; `registry.room_state(code).players` holds the same player. The join `{"type": "join", "nickname": "<b>Eve</b>", "resume_token": null}` is answered by `ErrorMessage(code="invalid_nickname")`, adds no player, and a following valid join on the same socket gets a `Snapshot`. Browser: opening `/r/<code>` shows `nickname-form`; entering `Ana` and submitting reaches `data-status="joined"`, and `roster` holds one `roster-player` with `data-you="true"` whose `roster-nickname` reads `Ana`; entering `A` instead shows `nickname-error` with `fr.json["join.error.length"]` and the page stays on `data-status="nickname"`.
- **AC-2** (AC-3.2.2) (Python; WebSocket) Each player gets a colour no other player in the room has. A duplicate nickname gets a numeric suffix. Python: 8 successive `join_room` calls on a fresh room with nicknames `Ana`, `ana`, `Ana`, `Bob`, `Cy`, `Di`, `Ed`, `Flo` give colours `0` to `7` and nicknames `Ana`, `ana 2`, `Ana 3`, `Bob`, `Cy`, `Di`, `Ed`, `Flo`; the first is host and no other is. WebSocket: three clients join a FX-01 room as `Ana`, `Ana`, `Bob`; the third client's snapshot lists `Ana` (colour 0), `Ana 2` (colour 1), `Bob` (colour 2); the first client receives `player_joined` events with seq 2 and 3 holding the views of `Ana 2` and `Bob`.
- **AC-3** (AC-3.2.3) (WebSocket) I see the current letters, timer and hint budget within 1 second of joining. Given a FX-01 room added with `add_room` whose cell (1, 0) holds `T` (author `p9`) and (1, 1) holds `A` (author `p9`), and whose `reveal_budget` is `RevealBudget(letters=3, words=1)`, when a client sends a join, then a `Snapshot` arrives less than 1.0 second (measured with `time.monotonic()`) after the join was sent, its `grid == grid_state(registry.room_state(code))`, its cell (1, 0) has `letter == "T"` and `author == "p9"`, its `reveal_budget == RevealBudget(letters=3, words=1)`, and its `timer_elapsed_ms == 0` with `timer_running is False`.
- **AC-4** (AC-3.2.4) (Python; WebSocket; browser with live server) Joining a room that already has 8 players shows "room full" and does not add me. Python: `join_room` on a room with 8 players returns `reply == (ErrorMessage(code="room_full", ...),)` (code compared), `close_sender is True`, no entry, and the same state. WebSocket: 8 clients join a FX-01 room; a ninth join is answered by `ErrorMessage(code="room_full")` and then a close with code 1000; the first client receives no event for it; `room_state` still holds 8 players. Browser: for a room added with 8 players (all `disconnected`), opening `/r/<code>` and submitting `Zoé` reaches `data-status="full"` and `room-status` shows `fr.json["room.status.full"]`.
- **AC-5** (new) (WebSocket; browser with live server) Reloading the page keeps me the same player. WebSocket: client A joins as `Ana` and client B as `Bob`; when A's socket closes, B receives `PlayerStateChanged(player_id=<A>, state="disconnected")`; a new socket that sends `{"type": "join", "nickname": "Autre", "resume_token": <A's token>}` receives a `Snapshot` with `you == <A>`, A's view still `nickname == "Ana"`, `colour == 0`, `is_host is True`, `state == "active"`, and B receives `PlayerStateChanged(player_id=<A>, state="active")`; the room still has 2 players. Browser: after joining as `Ana` and reloading the page, the room page reaches `data-status="joined"` without showing `nickname-form`, with the same `data-you` as before the reload, and `roster` holds one player.
- **AC-6** (new) (browser with mocked socket) The room page joins at once only with a stored identity or for a room created from the catalogue on this device. On `/r/ABC123`, `localStorage` seeded before `page.goto`: (a) with `nock.identity.ABC123` = `{"player_id": "p1", "resume_token": "r7Kq2mXo9vB4tY1zW8nP", "nickname": "Ana 2"}`, the first frame the page sends parses to `Join(nickname="Ana 2", resume_token="r7Kq2mXo9vB4tY1zW8nP")`, the page shows `data-status="joining"` and no `nickname-form` exists; the same holds when `nock.room.ABC123` = `{"grid": 1, "selection": null}` is also seeded. (b) With no identity, `nock.room.ABC123` = `{"grid": 1, "selection": null}` and `nock.nickname` = `Zoé`, the first frame parses to `Join(nickname="Zoé", resume_token=None)` and no `nickname-form` exists; with `nock.nickname` absent, or set to `A`, it parses to `Join(nickname=fr.json["room.default_nickname"], resume_token=None)`. (c) With no identity and `nock.room.ABC123` = `{"grid": null, "selection": null}`, or no record, or only `nock.identity.ZZZZZZ` stored (another room), the page sends no frame, reaches `data-status="nickname"` and shows `nickname-form`, whose input holds `Zoé` when `nock.nickname` = `Zoé` is seeded and is empty otherwise.
- **AC-7** (new) (browser with mocked socket) After a join, the identity is always stored and the remembered nickname only for a join from the form. On `/r/ABC123` with nothing seeded, submitting the form with `Ana` and the mock answering with a FX-01 snapshot (`you` = `p1`, `resume_token` = `r7Kq2mXo9vB4tY1zW8nP`, players `p1` named `Ana 2`) makes `localStorage["nock.identity.ABC123"]` parse to `{"player_id": "p1", "resume_token": "r7Kq2mXo9vB4tY1zW8nP", "nickname": "Ana 2"}` and `localStorage["nock.nickname"]` equal `Ana`. In case (b) of AC-6 with `nock.nickname` absent, after the same snapshot with `p1` named `Invité`, `nock.identity.ABC123` holds `p1`, that token and `Invité`, and `nock.nickname` is still absent.

## Edge cases and errors

- Nickname characters (AC-1): letters from any script (`Zoë`, `Łukasz`, `Ἀλέξης`),
  ASCII digits, space, `-`, `'`, `’`, `_`. Rejected: `<`, `>`, `&`, `"`, `@`, `!`,
  `.`, emoji, tabs, newlines, non-ASCII digits (`٣`). A nickname of digits only
  (`"12"`) is accepted; one made only of punctuation (`"--"`, `"_ _"`) is not.
- Length (AC-1): counted after NFC and trimming, in code points: `"É"` is
  `É`, one character, so `"É"` alone is too short. Leading and trailing
  spaces are removed; inner spaces are kept as typed (`"Anne  Marie"` keeps two).
- Protocol length first (AC-1): a nickname of 21 characters after trimming fails
  `parse_client_message` (spec 039) and gets `invalid_message`, not
  `invalid_nickname`; the page never sends one.
- Duplicate check (AC-2): case-insensitive, accent-sensitive; the suffix is added to
  the newcomer only; a resumed player keeps their nickname. A player called
  `Ana 2` already in the room pushes a second `Ana` to `Ana 3`.
- Colours (AC-2): a freed index (spec 017 time-out, spec 014 removal) is reused by
  the next joiner. Disconnected players keep theirs.
- Full room (AC-4): disconnected players hold their seat until they leave (spec 017
  time-out). A resume (step 2) is accepted in a full room, since the player is
  already counted.
- Unknown resume token (AC-5): a token that matches no player (an old room, a
  forged value) is ignored and the join is a new player with the join's nickname.
- Two tabs (AC-5): the same identity opened in a second tab takes over; the first
  tab's socket closes with 4001 and shows `replaced`, with no event to the others.
- Host (AC-1, AC-2): the first player is host; the host's disconnection does not
  move the role (spec 014 AC-3 does, after 60 seconds).
- Snapshot of the joiner (AC-1, AC-3): its `seq` is that of its own
  `player_joined`; the joiner never receives that event.
- Order of refusals (AC-4): removed, then resume, then locked, then full, then
  nickname. A full room answers `room_full` even to an invalid nickname.
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
- Remembered nickname (AC-7): the form's nickname is stored as sent (`Ana`), not
  as the server made it unique (`Ana 2`); the identity holds the server's
  nickname.
- Answers (AC-3): the snapshot is built from `grid_state`, never from `grid`.

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Presence states shown in the roster (idle, text of the state): spec 013.
- Host controls (remove, lock): spec 014.
- Changing one's nickname or colour after joining; choosing a colour.
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
   stays a valid nickname; comparison by `casefold()`.
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

## Open questions

None.
