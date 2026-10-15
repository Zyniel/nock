---
id: "022"
title: Chat and reactions
status: done
---

# 022 - Chat and reactions

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.) (Note from the lead, 2026-10-15: done. The human's answers are decisions 9 to 13 below, and "Open questions" says "None.")

Epic E5 Collaboration aids (US-5.4) · Release: V1 · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine (`nock.room`, `nock.hub`, `Outcome`, delivery order, test harness) is
defined in spec 011, joining and the roster in spec 012, presence, the activity
feed and its scroll rules in spec 013, host actions and `mute_player` in spec 014,
the pending edits in spec 015, reconnection in spec 017, the log, `replay` and the
store in spec 018, the clue elements in spec 006, the selected word in spec 007,
the phone keyboard in spec 009, the room toolbar in spec 024, the vote banner in
spec 025, the authors switch in spec 019, the flag button in spec 021, the
accessibility rules and scans in spec 035, the frame limit, the traffic checker
and escaping in spec 037, the messages in spec 039 (`Chat`, `ChatMessage`,
`ChatText`, `React`, `ReactionShown`, `Reaction`, `MutePlayer`, `PlayerMuted`,
`ErrorCode.MUTED`, `Snapshot.chat`). Room expiry is spec 032's. Built after specs
024, 025, 019, 020 and 021.

## Goal

As a player, I want to talk to the room, so that we can share half-ideas without leaving the grid.

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking.

## Public interface

No new protocol message and no new `ErrorCode`. Spec 039 already has `Chat` and
`ChatMessage` (with a seq, logged), `ChatText` (stripped as Python's
`str.strip()` does, then 1 to 280 code points, its AC-8), `React` and
`ReactionShown` (no seq, never logged, its decision 2), the five `Reaction` values
(its decision 9), `MutePlayer`, `PlayerMuted`, `ErrorCode.MUTED` and
`Snapshot.chat` (the full history in seq order, its decision 12). (Note from the
lead, 2026-10-15: "after trimming" became "stripped as Python's `str.strip()`
does", the refined rule of spec 039 AC-8, decision 14 (spec 022's tests).) Spec 014 built the `mute_player` rule (its AC-6) and left
its effect on chat, and the mute button, to this spec.

### Terms

- The word of a clue reference and a reference that names a word are those of
  spec 021's "Terms". The room toolbar, its small windows and its rules are spec
  024's "Client: room toolbar".
- A chat line is one `ChatMessage`: its `seq`, `player_id` and `text`.

### State and configuration (`nock.room`)

```python
# src/nock/room.py (fields added by this spec, each with a default, as spec 011 requires)
class RoomConfig(RoomModel):
    # ... fields of specs 011 to 037
    chat_limit: int = Field(default=5, ge=1)                 # chat messages per player per window
    chat_window_seconds: float = Field(default=10.0, gt=0)
    reaction_limit: int = Field(default=5, ge=1)             # reactions per player per window
    reaction_window_seconds: float = Field(default=10.0, gt=0)


class PlayerRecord(RoomModel):
    # ... fields of specs 011 to 037 and 021
    recent_chat: tuple[float, ...] = ()       # times of the chat messages accepted in the window
    recent_reactions: tuple[float, ...] = ()  # times of the reactions relayed in the window


class RoomState(RoomModel):
    # ... fields of specs 011 to 037 and 021
    chat: tuple[ChatMessage, ...] = ()        # every chat message of the room, in seq order


class Outcome(RoomModel):
    # ... fields of spec 011; this spec widens the type of `to_others`
    to_others: tuple[SelectionMoved | ReactionShown, ...] = ()
```

`to_others` was `tuple[SelectionMoved, ...]`. The hub's delivery does not change:
each item goes to every joined connection except the sender's and except the
connections of the item's own `player_id` (spec 011 delivery step 4; both types
have a `player_id`). (Note from the lead, 2026-10-15: this widens a field of spec
011's `Outcome`, and spec 011 is `done`. No criterion of spec 011 changes: its steps
still put only `SelectionMoved` there, and its delivery rule is the one quoted
above.)

### Server rule: `Chat` in `nock.room.handle_message`

`Chat(text)` from joined player `p` is input (spec 013). It is not an edit, so
spec 037's edit limit does not count it. The first case that applies decides:

1. `p.muted`: refused with `ErrorMessage(code=MUTED)`.
2. Limit: with `recent = [t for t in p.recent_chat if t > now - config.chat_window_seconds]`,
   when `len(recent) >= config.chat_limit`, the message is dropped: no entry of its
   own and no reply (an idle sender is first woken by spec 013's entry, which a drop
   does not undo). (Note from the lead, 2026-10-15: an idle sender is woken even
   when its message is refused, as spec 013's input rule and the code do.)
3. Otherwise, with `seq` the next seq: `p.recent_chat = (*recent, now)`,
   `state.chat` gains `ChatMessage(seq=seq, player_id=p, text=text)` at its end,
   and that message is the step's one entry, delivered to every joined connection,
   the sender's included (spec 011).

The text is the protocol's trimmed text (spec 039), stored and sent unchanged: no
escaping and no filter on the server (spec 037 AC-4 escapes on display). A refused
or dropped message leaves the state as it was apart from `p`'s `last_seen_at`,
`last_input_at` and, if `p` was idle, their state (and the seq, which spec 013's
wake entry raises by one), and is not counted by the limit. (Note from the lead,
2026-10-15: an idle sender is woken even when its message is refused, as spec 013's
input rule and the code do.) Chat keeps working on a solved grid (spec 026).

### Server rule: `React` in `nock.room.handle_message`

`React(clue, reaction)` from joined player `p` is input (spec 013). A reaction is
never answered with an error. It is dropped (no entry of its own, no reply, nothing
relayed, the state unchanged apart from `last_seen_at`, `last_input_at` and, if `p`
was idle, their state; an idle sender is first woken by spec 013's entry, which a
drop does not undo) when `p.muted`, when `clue` names no word, or when, with
`recent = [t for t in p.recent_reactions if t > now - config.reaction_window_seconds]`,
`len(recent) >= config.reaction_limit`. (Note from the lead, 2026-10-15: an idle
sender is woken even when its message is refused, as spec 013's input rule and the
code do.)

Otherwise: `p.recent_reactions = (*recent, now)`, no entry (a reaction has no seq
and is never logged), and with
`shown = ReactionShown(player_id=p, clue=clue, reaction=reaction)`:
`reply = (shown,)` and `to_others = (shown,)`, so every joined connection receives
it exactly once. Reactions work on any word, full or not, and on a solved grid.

### Mute (spec 014 AC-6)

Spec 014's `mute_player` rule and its `player_muted` entry are unchanged. Its
effect is case 1 of `Chat` and the first drop case of `React`. A muted player can
still type letters, check, flag (spec 021) and use every other control.

### `snapshot_for` (spec 012), `replay` and `after_restart` (spec 018)

- `snapshot_for` sends `chat = state.chat`.
- `replay` of `chat_message`: the event is added at the end of `chat`.
- `recent_chat` and `recent_reactions` are not logged, like `recent_edits`
  (spec 018): replay does not restore them.
- `after_restart` (spec 018) sets `recent_chat = ()` and `recent_reactions = ()`
  on every player of the room, connected or disconnected, and adds no entry for
  it. Spec 018 clears `recent_edits` only on the players the restart disconnects
  (the players who were not disconnected yet, one `player_state_changed` entry
  each); a player already disconnected before the restart has no entry from it,
  and still gets both windows of this spec emptied. A room loaded from a snapshot
  (which stores them) and one rebuilt from the log alone thus give every player a
  fresh window after a restart. (Note from the lead, 2026-10-15: added;
  `after_restart` kept both tuples, so a restart from a snapshot kept limits that
  a restart from the log lost, decision 17 (review of spec 022).) (Note from the
  lead, 2026-10-15: "disconnected or not, as it clears `recent_edits`" became
  "connected or disconnected" and the difference with `recent_edits`, which spec
  018 clears only for the players the restart disconnects (second review of spec
  022).)

### Where chat is kept

A chat message exists on the server only in its room's log (`chat_message`
entries) and in its room's snapshots (`RoomState.chat`): no other table, file or
log output holds its text. Deleting a room's rows at expiry (spec 032 AC-1) thus
deletes its chat (spec 038 AC-2 checks it).

### Client: kept chat and reactions

`web/src/lib/roomSession.ts`:

```ts
export interface ChatLine {
  seq: number
  player_id: string
  text: string
}

export interface Snapshot {
  // ... fields of specs 012 to 040 and 021
  // The chat history of the room, in seq order (spec 022).
  chat: ChatLine[]
}
```

- A snapshot's `chat` becomes the kept history. A line that is not an object with
  an integer `seq` and a string `player_id` and `text` is skipped.
- An applied `chat_message` adds its line at the end of the history, unless a
  line with its seq is already there.
- A `reaction` frame has no seq. Like `selection_moved` (spec 040 rule 8), it is
  applied when it arrives, once the page has a snapshot, and ignored before. It
  does not touch `seq`, the buffer or `data-pending`.
- An `error` with code `muted` changes nothing on the page. Neither `muted` nor any
  error of this spec is an edit answer of spec 015, so the pending edits are never
  touched by chat or reactions.

### Client: chat toggle and panel

- `data-testid="chat-toggle"`: a `<button type="button">` at the start of spec
  024's `room-toolbar`, before the undo control (spec 027 later puts the timer
  before it), shown once the page has a snapshot. It comes first so that its
  unread count is in the toolbar's visible part when a small window has scrolled
  nothing yet. Spec 024's toolbar rules apply to it. It has `aria-expanded`
  (`true` while the panel is open), `aria-controls="chat-panel"` and the visible
  text `t("chat.toggle")` (`Discussion`). `aria-label`: `t("chat.toggle")` when no
  line is unread, else `t("chat.toggle_label_unread", { count })` with the number
  of unread lines.
- `data-testid="chat-unread"`: inside `chat-toggle`, with `aria-hidden="true"`,
  present only while the panel is closed and at least one line is unread. Its text
  is the number of unread lines in decimal digits, from 1 to 99, or
  `t("chat.unread_many")` (`99+`) above 99.
- Height of the toggle: the bounding box of `chat-toggle` keeps its height (1 px
  tolerance) with the panel closed and no unread line, with the panel closed and
  `chat-unread` showing (one digit, two digits or `99+`), and with the panel open.
  Its width may change with the count. How the toggle keeps its height is the
  implementer's choice. (Note from the lead, 2026-10-15: added; the toggle grew or
  shrank when the count appeared or went, decision 18 (review of spec 022).) (Note
  from the lead, 2026-10-15: reworded; the rule named a slot of fixed height for
  `chat-unread`, which is a way to keep the height and not what users see: it now
  requires the toggle's height only, decision 18 (second review of spec 022).)
- Unread lines. The page keeps `lastSeenChatSeq`. At the page's first snapshot it
  is that snapshot's `seq`. While the panel is open it is the seq of the newest
  line of the history. A line is unread when its seq is greater than
  `lastSeenChatSeq` and its `player_id` is not `you`. A later snapshot (after a
  reconnection) keeps `lastSeenChatSeq`, so lines that came while the page was
  away count.
- The panel is closed when the page loads. A click on `chat-toggle` opens or
  closes it. When it opens, the focus moves to `chat-input` if that input is
  enabled, else it stays on `chat-toggle`. `Escape` while the focus is inside the
  panel closes it and puts the focus on `chat-toggle`.
- `data-testid="chat-panel"`, `id="chat-panel"`, present only while open, outside
  `room-toolbar` (whose sideways scrolling would clip it), right after the toolbar
  in document order (after `reaction-picker` while both are open) and before the
  roster, the feed and the grid; `Tab` thus reaches it after the toolbar's last
  control (after the picker's last option while both are open), and opening it
  puts the focus inside it. (Note from the lead, 2026-10-15: the two parentheses
  are added; the picker and the panel may be open together, decision 15 (spec
  022's tests).) It is a `section` with `aria-labelledby="chat-heading"`. It holds, in
  document order: an `h2` with `id="chat-heading"` and the text
  `t("chat.heading")`; `chat-list`; `chat-moderation` when `you` is host; the chat
  form; the slot of the chat notes, which holds `chat-muted` or `chat-wait` when
  one applies ("Client: sending, pacing and mute"). (Note from the lead,
  2026-10-15: the slot replaces "`chat-muted` or `chat-wait` when they apply",
  decision 20 (second review of spec 022).)
- Placement: the panel is drawn over the page, like spec 025's vote banner.
  Opening or closing it changes the bounding box of no element outside it (1 px
  tolerance). It lies entirely inside the window, and `chat-toggle` stays
  uncovered: `document.elementFromPoint` at the toggle's centre returns the toggle
  or one of its descendants. It never covers spec 025's vote buttons: while both
  show, `document.elementFromPoint` at the centre of `vote-yes` and of `vote-no`
  returns that button. A size such as `min(22rem, 100vw - 1rem)` wide, below the
  header, is the implementer's choice.
- The vote banner wins over the panel. On a small window spec 025's
  `vote-banner` (laid over the top of `grid-viewport`) can overlap the panel.
  While `vote-banner` is on the page (an open vote, then its result for spec 025's
  `VOTE_RESULT_MS`), it is drawn above the panel: at the centre of the banner's
  bounding box and at each of its four corners moved 2 px inwards on both axes,
  `document.elementFromPoint` returns `vote-banner` or one of its descendants,
  never `chat-panel` or one of its descendants. Meanwhile the panel stays open and
  usable under it: `chat-panel` stays present with the bounding box it had before
  the banner came (1 px tolerance), the focus stays where it was, and text typed in
  `chat-input` then `Enter` sends its `chat` frame as at any other time. The part
  of the panel under the banner is hidden for that time, and the panel's own
  rules that would bring it into view are suspended: the page makes no scroll
  call on `chat-panel`, `chat-list` or the document to uncover it, `chat-list`
  keeps its `scrollTop` apart from what spec 013's scroll rules do on a new line,
  and the rule of "Client: the chat list" that the focused list's outline is fully
  visible does not apply to the part under the banner. Once `vote-banner` has
  left the page, the panel is fully visible again: at the centre of the panel's
  bounding box and at each of its four corners moved 2 px inwards,
  `document.elementFromPoint` returns `chat-panel` or one of its descendants (with
  the picker closed). (Note from the lead, 2026-10-15: added; at small windows the
  banner hid the top of an open panel and the spec did not say which wins,
  decision 16 (review of spec 022).)

### Client: the chat list

- `data-testid="chat-list"`: a `ul` with `role="list"` and
  `aria-labelledby="chat-heading"`, holding one `data-testid="chat-message"` `li`
  per line, oldest first, at most the last 200 lines of the history. Each has
  `data-seq`, `data-player-id`, `data-you` (`true` for my own lines), and two
  children: `data-testid="chat-author"`, the nickname of the line's player as text
  (known players include those who left; an unknown id gives `t("feed.someone")`),
  and `data-testid="chat-text"`, the line's text as text. Both are inserted as
  text, never as HTML (spec 037 AC-4).
- Reading position: the rules of spec 013's "Client: feed scroll position" apply,
  with `chat-list` in place of the feed list, `chat-message` in place of
  `feed-item` and 200 in place of 100. A line of my own gets no special case, as
  in spec 013.
- Keyboard: the list holds no focusable element, so the rules of spec 035's
  "Scrolling lists" for such a list apply: `tabindex="0"` while it scrolls, no
  `tabindex` attribute while it does not, the focused list keeps its attribute
  until the focus leaves it, and the attribute follows each change within 300 ms.
  The page handles no key on it; the arrow keys scroll it. While it has the focus
  after a keyboard move, its outline meets spec 035 AC-2 and is fully visible, as
  spec 035 requires of the feed's list ("Focus outline of the feed's scrolling
  list": not clipped, not covered), except, while spec 025's `vote-banner` is on
  the page, for the part under the banner ("Client: chat toggle and panel").
  (Note from the lead, 2026-10-15: the exception is added, decision 16 (review of
  spec 022).)

### Client: sending, pacing and mute

- The chat form holds a `label` for `chat-input` with `t("chat.input_label")`
  (it may be visually hidden), `data-testid="chat-input"` (an
  `<input type="text">` with `maxlength="280"`, `autocomplete="off"` and the
  placeholder `t("chat.placeholder")`), and `data-testid="chat-send"`, a submit
  button with the text `t("chat.send")`. `chat-input` is never inside
  `grid-viewport`, `clue-bar`, `keyboard` or `grid` (spec 009 AC-3).
- `chat-send` is disabled while the input's text, trimmed with `trim()`, is empty,
  while the page's `data-status` is not `joined`, while I am muted, and while the
  pacing rule below holds. A submit (a click or `Enter` in the input) when it is
  enabled sends `{"type": "chat", "text": <the trimmed text>}` and empties the
  input. The page shows a line only when its `chat_message` arrives: no local echo.
- Focus after sending: once a chat message is sent, the focus is on `chat-input`,
  whichever way it was sent: `Enter` in `chat-input`, or the activation of
  `chat-send` from the keyboard or by a click or tap. The submit empties the
  input, which disables `chat-send`, so a focus that was on `chat-send` moves to
  `chat-input`; it is never left on the disabled `chat-send` and never drops to
  `document.body`. It holds too when the send starts the pacing below (`chat-send`
  is then disabled, and `chat-input`, which pacing does not disable, has the
  focus). (Note from the lead, 2026-10-15: added; the spec said nothing about the
  focus after a send, so the focus of a keyboard or tap user could fall to
  `document.body`, decision 21 (second review of spec 022).)
- Pacing: the page sends a chat message only while fewer than 5 of its own chat
  messages were sent in the last 12,000 ms. While 5 were, `chat-send` is disabled
  and `data-testid="chat-wait"` shows `t("chat.wait")`. The page paces reactions
  the same way: while 5 reactions were sent in the last 12,000 ms, every
  `reaction-option` is disabled. The 12 seconds of the page against the 10 of the
  server leave 2 seconds for network jitter, so a working page is never dropped
  by the server's limit.
- Muted: while my own `muted` is true (snapshot, or `player_muted`, applied by
  spec 014), `chat-input` and `chat-send` are disabled, `data-testid="chat-muted"`
  shows `t("chat.muted")`, and `react-button` is disabled.
- Chat notes: `chat-muted` and `chat-wait` sit in one slot of the panel, after the
  chat form. The slot is always present, empty when neither note applies, and one
  line high; it shows one note at a time, and each note fits on that one line at
  every window size of spec 006 AC-5 (at the default root font size). A note
  coming or going thus leaves `chat-panel`'s bounding box unchanged (1 px
  tolerance). `t("chat.wait")` is short so that it fits at 320 px wide (`fr.json`
  keys). When both notes apply (a mute while the pacing holds), only `chat-muted`
  shows; `chat-wait` shows again after an unmute if the pacing still holds. (Note
  from the lead, 2026-10-15: added; the spec did not say that a note leaves the
  panel's box alone, and the long wait text did not fit one line at 320 px wide,
  decision 20 (second review of spec 022).) (Note from the lead, 2026-10-15: the
  last sentence is added; it was an open question, decision 22 (second review of
  spec 022).)
- Focus at a mute: when my `muted` becomes true while the focus is on `chat-input`
  or `chat-send`, the focus moves to `chat-toggle` at once, never to
  `document.body`; the panel stays open, and the text typed in `chat-input` stays
  in it. `chat-toggle` is the target because it is always present and is where
  `Escape` from the panel puts the focus. (Note from the lead, 2026-10-15: added;
  the disabled input kept or dropped the focus, decision 19 (review of spec 022).)

### Client: the host's mute buttons

While `you` is host, `chat-panel` holds `data-testid="chat-moderation"`, a section
with an `h3` holding `t("chat.moderation_heading")` and one
`data-testid="mute-row"` per other player, in roster order, with
`data-player-id`. Each row holds the player's nickname as text
(`data-testid="mute-name"`) and `data-testid="mute-player"`, a button with
`data-muted` (`true` or `false`, the player's `muted`), the text `t("chat.mute")`
or, while muted, `t("chat.unmute")`, and the `aria-label`
`t("chat.mute_label", { name })` or, while muted, `t("chat.unmute_label", { name })`.
A click sends `{"type": "mute_player", "player_id": <id>, "muted": <not data-muted>}`;
the page waits for the server's `player_muted`. A player who is not host never
sees `chat-moderation`.

### Client: the reaction button and picker

- `data-testid="react-button"`: a `<button type="button">` in spec 024's
  `room-toolbar`, right after `flag-button` (spec 021) and before
  `authors-switch` (spec 019, which stays last), shown once the page has a
  snapshot. Spec 024's toolbar rules apply to it. `aria-label`
  `t("reaction.button_label")`, `aria-expanded`, `aria-controls="reaction-picker"`,
  visible text `t("reaction.button")`. Disabled while nothing is selected and
  while I am muted.
- A click opens `data-testid="reaction-picker"` (`id="reaction-picker"`), present
  only while open, outside `room-toolbar` (whose sideways scrolling would clip
  it), right after the toolbar in document order and before `chat-panel`, with
  `role="group"` and the `aria-label` `t("reaction.picker_label")`. It holds five
  `data-testid="reaction-option"` buttons in the order of spec 039's `Reaction`
  (`thumbs_up`, `clap`, `laugh`, `wow`, `thinking`), each with `data-reaction`,
  the text `t("reaction.<value>")` (an emoji) and the `aria-label`
  `t("reaction.<value>_label")`. Opening puts the focus on the first option.
- A click on an option sends
  `{"type": "react", "clue": <the selected word's clue>, "reaction": <value>}`,
  closes the picker and puts the focus on `react-button`. `Escape` in the picker,
  or a second click on `react-button`, closes it without sending anything (Note
  from the lead, 2026-10-15: "sending anything" leaves aside the heartbeat `ping`
  frames of spec 017, which the page may send at any time once the socket is
  open), the focus on `react-button`. The picker lies inside the window, changes
  the bounding box of no element outside it, leaves `react-button` uncovered and
  never covers spec 025's vote buttons (the same `elementFromPoint` checks as the
  panel's).
- When `react-button` becomes disabled while the picker is open (I am muted, or
  nothing is selected any more), the picker closes at once, sending nothing, and
  `react-button` gets `aria-expanded="false"`; it never stays open with live
  options. If the focus was inside the picker, it moves to the `grid` element, as
  spec 025 does when the vote banner leaves while it holds the focus (its decision
  19), never to `document.body`. A focus on `react-button` itself when it becomes
  disabled gets no target from this spec. (Note from the lead, 2026-10-15: added;
  the picker stayed open with live options after a mute, decision 19 (review of
  spec 022).)
- The picker and the panel are independent: either may be open whether the other
  is open or not, and opening, using or closing one leaves the other as it was
  (open or closed, same bounding box, 1 px tolerance). While both are open, each
  keeps every placement rule it has alone, `chat-toggle` and `react-button` are
  both uncovered, and the two do not overlap: the intersection of their bounding
  boxes is at most 1 px wide or at most 1 px high. Where each sits is the
  implementer's choice within these rules, for example the picker beside the
  panel on a wide or low window and above or below it on a narrow one. In
  document order the toolbar comes first, then the picker, then the panel.
  (Note from the lead, 2026-10-15: added; the spec did not say whether both could
  be open at once, decision 15 (spec 022's tests).)

### Client: a shown reaction

- When a `reaction` frame is applied and its clue is a clue of the grid, the
  `clue` element of that clue (spec 006) holds one `data-testid="clue-reaction"`
  element with `data-reaction`, `data-player-id`, `aria-hidden="true"` and the
  text `t("reaction.<value>")`, plus one `data-testid="clue-reaction-label"` with
  the class `visually-hidden` and the text
  `t("reaction.shown_label", { name, reaction })`, where `name` is the player's
  nickname (`t("feed.someone")` when unknown) and `reaction` is
  `t("reaction.<value>_label")`.
- It stays 3,000 ms from the moment the frame arrived, then both elements go. A
  newer reaction on the same clue replaces it, and its own 3,000 ms start. A clue
  shows at most one reaction.
- Look: the centre of the `clue-reaction` box lies inside the clue cell's box, its
  computed `font-size` is at least 12 px and its `visibility` is `visible`; it
  may reach past the cell's edges and has an opaque background, so its text
  passes spec 035's contrast scan. It takes no room from the clue: the `clue-text`
  keeps its bounding box (1 px tolerance), as spec 021's marker. A reaction whose
  clue is not a clue of the grid shows nothing.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `chat.toggle` | `Discussion` |
| `chat.toggle_label_unread` | `Discussion, {count} messages non lus` |
| `chat.unread_many` | `99+` |
| `chat.heading` | `Discussion` |
| `chat.input_label` | `Message` |
| `chat.placeholder` | `Écrire au salon` |
| `chat.send` | `Envoyer` |
| `chat.wait` | `Patientez avant d'envoyer.` |
| `chat.muted` | `L'hôte a coupé votre discussion.` |
| `chat.moderation_heading` | `Sourdine` |
| `chat.mute` | `Couper` |
| `chat.unmute` | `Rétablir` |
| `chat.mute_label` | `Couper la discussion de {name}` |
| `chat.unmute_label` | `Rétablir la discussion de {name}` |
| `reaction.button` | `Réagir` |
| `reaction.button_label` | `Réagir sur ce mot` |
| `reaction.picker_label` | `Réactions` |
| `reaction.thumbs_up` | `👍` |
| `reaction.clap` | `👏` |
| `reaction.laugh` | `😂` |
| `reaction.wow` | `😮` |
| `reaction.thinking` | `🤔` |
| `reaction.thumbs_up_label` | `Pouce levé` |
| `reaction.clap_label` | `Bravo` |
| `reaction.laugh_label` | `Rire` |
| `reaction.wow_label` | `Waouh` |
| `reaction.thinking_label` | `Je réfléchis` |
| `reaction.shown_label` | `{name} : {reaction}` |

(Note from the lead, 2026-10-15: `chat.wait` was `Patientez un instant avant le
prochain message.`; it is shortened so that it fits on the one line of the chat
notes' slot at 320 px wide, decision 20 (second review of spec 022).)

The five emoji are U+1F44D, U+1F44F, U+1F602, U+1F62E and U+1F914.
Spec 035 AC-9's checker reads every `fr.json` value as a pattern and must still
flag `Loading…`, `Salon` and `Check word`; none of these values matches them (no
value is a bare placeholder or two placeholders around a space).

### Test harness

- Rule tests: `new_room("ABC123", fx01_grid, NOW)`, players `p1` (host) and `p2`
  added with `join_room` at `NOW` (seq 2); messages applied with
  `handle_message(state, player_id, message, now)`; mutes with `MutePlayer` from
  `p1`; a closed connection with `disconnect_player(state, player_id, now)`
  (spec 012). (Note from the lead, 2026-10-15: `disconnect_player` is added for
  AC-9's restart case (second review of spec 022).)
- WebSocket tests: spec 011's `TestClient` on a FX-01 room with
  `RoomConfig(max_edits_per_second=1000)`; AC-1 also sets `chat_limit=1000`; AC-9
  uses spec 011's `FakeClock` with
  `RoomConfig(tick_seconds=0.05, silence_timeout_seconds=3600)`, so that advancing
  the clock disconnects nobody for silence.
- Browser with mocked socket: spec 040's mock on `/r/ABC123`, FX-01 snapshots
  built with `grid_view`, players `p1` (`you`, `Ana`, host), `p2` (`Bob`) and `p3`
  (`Cy`), `chat` built with `ChatMessage`, `reaction` frames built with
  `ReactionShown`. A word is selected by tapping its clue, as in spec 021.
- Browser with live server: spec 040's `live_server`, one browser context per
  player, each entering through `enter_room`.
- Chat scroll states (AC-11, AC-12): spec 013's "Feed scroll states" with the
  panel open, `chat-list` in place of the feed list and `chat-message` in place of
  `feed-item`; a line event is a `chat_message` from `p2` with the text
  `Ligne <seq>`. "Settled", the scroll probe and "items in view" are spec 013's.
- Pacing (AC-10): real time, or Playwright's page clock as spec 017 AC-5 does.
- Votes and mutes (AC-15, AC-17, AC-18, AC-19): vote frames are built with spec
  039's `VoteOpened` and `VoteClosed`, as in spec 025's harness, and mutes with
  `PlayerMuted`. (Note from the lead, 2026-10-15: added with AC-17 and AC-18
  (review of spec 022).) (Note from the lead, 2026-10-15: AC-19 is added to the
  list, it mutes and unmutes `you` (second review of spec 022).)
- Scans: spec 035's contrast and language scans. Chat text is user content, not an
  interface string: a language scan run on a state with chat lines adds the texts
  of the lines the test sent (in the snapshot or in events) to its test data, as it
  does for the nicknames, so they pass whatever their language. The contrast scan
  treats them as any text. `tab_to` is spec 035's helper.
- Contexts and window sizes: as spec 021 (desktop and touch contexts, spec 006
  AC-5's eight sizes). Toolbar checks are spec 024 AC-8's, on its setup.
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check
  of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-5.4.1) (Python; WebSocket; browser with live server) The room has a text chat whose messages reach every player in the same order. Python: in the two-player room (seq 2), `Chat(text="Qui a une idée pour le 3 ?")` from `p1` gives exactly one entry, `ChatMessage(seq=3, player_id="p1", text="Qui a une idée pour le 3 ?")`, and no reply; `Chat(text="IDES, je crois")` from `p2` then gives `ChatMessage(seq=4, player_id="p2", text="IDES, je crois")`; `state.chat` and `snapshot_for(state, "p1").chat` are those two messages in that order. WebSocket: A and B join; from two threads at the same time A sends `A1` to `A20` and B sends `B1` to `B20`; once each client has received 40 `chat_message` events, the two clients' lists of `(seq, player_id, text)` are equal, their seqs are consecutive, and each sender's texts appear in the order it sent them; a client C joining afterwards gets a snapshot whose `chat` equals that list. Browser: Ana and Bob join one FX-01 room and each opens the chat with `chat-toggle`; Ana types `Qui a une idée pour le 3 ?` in `chat-input` and presses `Enter`; within 1 s both `chat-list`s end with a `chat-message` whose `chat-author` reads `Ana` and whose `chat-text` reads that text, and Ana's `chat-input` is empty; Bob then sends `IDES, je crois`, and both lists end with Ana's line followed by Bob's.
- **AC-2** (AC-5.4.1) (WebSocket; browser with mocked socket) A message holds 1 to 280 characters. WebSocket: on a FX-01 room with two joined clients, a `chat` with 280 times `a` gets its `chat_message`; a `chat` with 281 times `a`, one with `""` and one with `"   "` each get one `error` with code `invalid_message` (spec 039 AC-8), the other client receives nothing for them and the room's seq is unchanged; `" salut "` gets a `chat_message` whose text is `salut`. Browser: with the panel open, `chat-input` has `maxlength="280"`, and after the test types 300 times `a` its value holds 280 characters; with an empty input, and with an input of three spaces, `chat-send` is disabled and `Enter` sends no frame (Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted); with `  salut  ` in the input, a click on `chat-send` sends one frame whose JSON `text` is `salut`.
- **AC-3** (AC-5.4.2) (Python; WebSocket; browser with live server) A reaction from the set of 5 appears on the chosen word for every player. Python: in the two-player room, `React(clue=ClueRef(row=0, column=3, clue_index=0), reaction=Reaction.CLAP)` from `p2` gives no entry, `reply == (ReactionShown(player_id="p2", clue=ClueRef(row=0, column=3, clue_index=0), reaction=Reaction.CLAP),)`, `to_others` equal to the same tuple, and the same seq. WebSocket: A and B join; B sends `{"type": "react", "clue": {"row": 0, "column": 3, "clue_index": 0}, "reaction": "clap"}`; A and B each receive exactly one frame for it, a JSON object with no `seq` key that parses to that `ReactionShown`; the room's seq is unchanged and the registry's store holds no new log entry. Browser: Ana and Bob join one FX-01 room; Bob taps the clue cell (0, 3), clicks `react-button`, then the `reaction-option` with `data-reaction="clap"`; within 1 s both pages show, in the IDES clue, one `clue-reaction` with `data-reaction="clap"`, Bob's id in `data-player-id` and the text `fr.json["reaction.clap"]`.
- **AC-4** (AC-5.4.2) (browser with mocked socket) A shown reaction lasts 3 seconds, and a newer one on the same word replaces it. Given a FX-01 snapshot with `seq` 5, when the mock sends a `reaction` of `p2` on IDES with `wow`, the IDES clue holds one `clue-reaction` with `data-reaction="wow"` and `data-player-id="p2"` within 300 ms, its `clue-reaction-label` reads `Bob : Waouh`, it is still there 2,700 ms after it appeared, and no `clue-reaction` is left 3,500 ms after it appeared. In a second run, a `thinking` of `p3` on IDES arrives 1,000 ms after a `wow` of `p2`: IDES then holds one `clue-reaction`, `thinking` from `p3`, still there 2,700 ms after it appeared and gone 3,500 ms after. A `reaction` on `ClueRef(row=1, column=0, clue_index=0)` (a letter cell) shows nothing; no `reaction` frame changes `data-seq`, and a `letter_changed` with `seq` 6 sent after them is applied.
- **AC-5** (AC-5.4.2) (browser with mocked socket) The picker offers the 5 reactions and reacts on the selected word. At 1280 by 720, `react-button` is inside `room-toolbar`, right after `flag-button` and before `authors-switch` in document order, with the text `fr.json["reaction.button"]`, the `aria-label` `fr.json["reaction.button_label"]` and `aria-expanded="false"`, and it is disabled while nothing is selected. After a tap on the clue cell (2, 0) (VIDE), a click opens `reaction-picker` (`aria-expanded="true"`), which has `role="group"` and the `aria-label` `fr.json["reaction.picker_label"]` and holds five `reaction-option` whose `data-reaction` are `thumbs_up`, `clap`, `laugh`, `wow`, `thinking` in that order, each with the text `fr.json["reaction.<value>"]` and the `aria-label` `fr.json["reaction.<value>_label"]`; the first has the focus. A click on `laugh` sends exactly one frame, which parses to `React(clue=ClueRef(row=2, column=0, clue_index=0), reaction=Reaction.LAUGH)`, closes the picker and puts the focus on `react-button`. When the picker is opened again, `Escape` closes it, sends nothing and puts the focus on `react-button`. (Note from the lead, 2026-10-15: "exactly one frame" and "sends nothing" leave aside the heartbeat `ping` frames of spec 017, which the page may send at any time once the socket is open.) Last, with VIDE still selected, a click on `chat-toggle` opens the panel and then a click on `react-button` opens the picker while `chat-panel` stays present: neither is inside `room-toolbar`, and `reaction-picker` comes after `room-toolbar` and before `chat-panel` in document order; `Escape` in the picker then closes it, puts the focus on `react-button` and leaves `chat-panel` present. (Note from the lead, 2026-10-15: added; the picker and the panel may be open together, so their document order is tested with both open, decision 15 (spec 022's tests).)
- **AC-6** (AC-5.4.3) (browser with mocked socket) The chat can be collapsed, and then shows an unread count. Given a FX-01 snapshot with `seq` 5 whose `chat` holds `Salut` (seq 3, `p2`) and `Bonjour` (seq 4, `p1`):
  - At load: `chat-toggle` has `aria-expanded="false"` and the `aria-label` `fr.json["chat.toggle"]`; there is no `chat-panel` and no `chat-unread`.
  - After the mock's `chat_message` seq 6 (`p2`), 7 (`p3`) and 8 (`p1`): `chat-unread` reads `2` and the toggle's `aria-label` is `Discussion, 2 messages non lus`.
  - A click on `chat-toggle`: `aria-expanded="true"`, `chat-list` holds five `chat-message` with `data-seq` 3, 4, 6, 7, 8 in that order, no `chat-unread` exists, and the focus is on `chat-input`.
  - `chat_message` seq 9 (`p2`) arrives and is listed; `Escape` closes the panel and puts the focus on `chat-toggle`; no `chat-unread` exists. Then seq 10 (`p2`): `chat-unread` reads `1`.
  - The mock closes the socket with code 1011 and answers the page's next join with a snapshot with `seq` 12 whose `chat` holds the lines above plus seq 11 (`p2`) and seq 12 (`p3`): `chat-unread` reads `3`.
  - In a separate run, 100 `chat_message` from `p2` after the snapshot: `chat-unread` reads `fr.json["chat.unread_many"]` and the `aria-label` is `Discussion, 100 messages non lus`.
  - Toggle height: the steps above run at 1280 by 720 and again at 568 by 320. At each size, the height of `chat-toggle`'s bounding box is the same (1 px tolerance) in each of these states: at load (panel closed, no `chat-unread`), with `chat-unread` reading `2`, with the panel open, with `chat-unread` reading `1`, and, in the separate run, with `chat-unread` reading `99+`. (Note from the lead, 2026-10-15: added, decision 18 (review of spec 022).)
- **AC-7** (AC-5.4.4) (Python; WebSocket; browser with live server) The host can mute a player's chat. Python: after `MutePlayer(player_id="p2", muted=True)` from the host `p1` (spec 014 AC-6), `Chat(text="salut")` from `p2` is answered with one `ErrorMessage` with code `muted`, gives no entry and leaves `state.chat` unchanged, and `React` from `p2` gives no entry, no reply and an empty `to_others`; after `MutePlayer(player_id="p2", muted=False)`, the same chat gives its `ChatMessage`. WebSocket: host A and B join; A mutes B; B's `chat` gets `error` `muted` and A receives nothing for it; A unmutes B; B's next `chat` reaches A and B. Browser: Ana (host) and Bob join one FX-01 room and open their chat; Bob's panel holds no `chat-moderation`; Ana's holds one `mute-row` for Bob whose `mute-player` reads `fr.json["chat.mute"]`, with the `aria-label` `Couper la discussion de Bob` and `data-muted="false"`. Ana clicks it: within 1 s Bob's `chat-input` and `chat-send` are disabled, his `chat-muted` shows `fr.json["chat.muted"]` and his `react-button` is disabled, and Ana's button reads `fr.json["chat.unmute"]` with `data-muted="true"`. Ana clicks it again: within 1 s Bob's `chat-input` is enabled and his `chat-muted` is gone.
- **AC-8** (AC-5.4.4) (Python with a `RoomStore`; WebSocket with captured logs) Chat is kept only with its room, so that deleting the room at expiry deletes it. Python: a `RoomStore` on a file in `tmp_path` holds rooms `AAAAAA` and `BBBBBB`, each created with `create_room`; the entries of a play in `AAAAAA` where `p1` sends `Chat(text="secret-a-42")` are appended, and a snapshot of its state is saved; reading the file with `sqlite3`, at least one row holds the text `secret-a-42`, and every row of every table that holds it in one of its columns has a column `code` equal to `AAAAAA`. WebSocket: with `caplog` capturing every logger at level DEBUG, A and B join a FX-01 room and A sends `secret-b-77`; B receives it, and no captured log record's message holds `secret-b-77`. Deleting the room at expiry is tested by spec 032 AC-1 and spec 038 AC-2.
- **AC-9** (new) (Python; WebSocket with a fake clock) Each player may send at most 5 chat messages and 5 reactions in any 10 seconds; the server drops the rest without an answer. Python: in the two-player room, six `Chat` from `p1` at `NOW`: the first five give their `ChatMessage` (seq 3 to 7), the sixth gives no entry and no reply and leaves `state.chat` unchanged; at `NOW + 9.9` a `Chat` from `p1` is dropped as well; at `NOW + 10.0` it is accepted with seq 8; a `Chat` from `p2` at `NOW` is accepted whatever `p1` sent; a refused (`muted`) or dropped message is not counted. Six `React` from `p1` at `NOW`: the first five are relayed (`reply` and `to_others`), the sixth gives nothing; at `NOW + 10.0` one is relayed again. A dropped `React` (from a muted player, on a clue that names no word, or over the limit) is not counted either: it leaves `recent_reactions` unchanged. (Note from the lead, 2026-10-15: this sentence is added; "is not counted" was written for `Chat` only (review of spec 022).) Restart: after five `Chat` and five `React` from `p1` at `NOW`, a `Chat` and a `React` from `p2` at `NOW`, and `disconnect_player(state, "p2", NOW)` (spec 012), so that `p2` is already disconnected (`p1`'s two tuples hold 5 times each, `p2`'s hold 1), `after_restart(state, NOW + 1)` gives a state in which every player, connected or disconnected, has `recent_chat == ()` and `recent_reactions == ()`, and whose only entry is spec 018's `player_state_changed` (`disconnected`) of `p1`: the restart writes one such entry for each player who was not disconnected, in players order, and none for `p2`. (Note from the lead, 2026-10-15: added, decision 17 (review of spec 022).) (Note from the lead, 2026-10-15: the case now has `p2` disconnected before the restart; "every player" became "every player, connected or disconnected" and "one per player" became "one for each player who was not disconnected", because spec 018's `after_restart` writes an entry only for those (second review of spec 022).) WebSocket: with the fake clock frozen, B sends seven `chat` messages; A receives exactly five `chat_message`, B receives those five and no `error`; after `advance(10)`, B's next `chat` reaches A.
- **AC-10** (new) (browser with mocked socket) The page paces its own chat messages and reactions under the server's limit. With the panel open, the player sends `m1` to `m5` with `Enter`, and the mock answers each with its `chat_message` from `p1`: the mock received exactly five `chat` frames; `chat-send` is then disabled, `chat-wait` shows `fr.json["chat.wait"]`, and `Enter` in the non-empty input sends nothing (Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted); 12 seconds after the first send, `chat-send` is enabled again and `chat-wait` is gone. Likewise, after five reactions chosen in the picker within a few seconds, every `reaction-option` is disabled, and they are enabled again 12 seconds after the first. The mock sends no `error` in this test.
- **AC-11** (new) (browser with mocked socket) A new line brings the chat list to its newest line only when the list was at its end; otherwise the reader keeps their place. The rules are spec 013's "Client: feed scroll position" applied to the chat list ("Client: the chat list"); the setup, "settled", the probe and "items in view" are those of "Chat scroll states" in "Test harness". The cases of spec 013 AC-7 run in its order, at 1280 by 720 and at 360 by 740, with these changes: "Filling" sends seq 6 to 15; "My own action" is replaced by: the player types `moi` in `chat-input` and presses `Enter`, the mock answers with the `chat_message` of `p1` with the next seq once it received the `chat` frame, and the probe, started just before `Enter`, stays put; "Full feed" sends lines up to seq 205, so that the list holds 200 lines (seq 6 to 205), and the line with seq 206 leaves the first `chat-message` with `data-seq` 7. The cases of spec 013 AC-8 (smaller window, larger root font, larger window) then run on the chat list at its end.
- **AC-12** (new) (browser with mocked socket, keyboard only after the setup) The chat list can be scrolled from the keyboard in every engine. With `you` not host (the snapshot makes `p2` host, so the panel holds no `chat-moderation`), the panel open and 40 lines from `p2`, at 360 by 740, 568 by 320 and 1280 by 720: `chat-list` scrolls (the test checks it from its measures), has `role="list"` and `tabindex="0"`, and `page.get_by_role("list", name=fr.json["chat.heading"], exact=True)` resolves to exactly it; with the focus on `chat-input` (where opening the panel puts it), one `Shift+Tab` puts the focus on `chat-list`, whose outline then meets spec 035 AC-2 and passes spec 035's "Not clipped" and "Not covered" measures; `ArrowUp` makes its `scrollTop` smaller within 300 ms and it keeps the focus; a new line from `p2` then leaves its `scrollTop` within 1 px and the focus on it; `Tab` then puts the focus back on `chat-input`. With two lines only, the list does not scroll and has no `tabindex` attribute, and one `Shift+Tab` from `chat-input` puts the focus on an element outside `chat-panel`.
- **AC-13** (new) (browser with mocked socket) Chat texts and names show as plain text (spec 037 AC-4). Given a snapshot whose players include `p2` named `<b>Eve</b>` and `p3` named `<img src=x>`, and whose `chat` holds `<b>salut</b>` from `p2` and `<img src=x onerror=alert(1)>` from `p3`: with the panel open, the two `chat-text` read exactly those texts and the two `chat-author` read `<b>Eve</b>` and `<img src=x>`; after a `reaction` of `p3` with `clap`, the `clue-reaction-label` reads `<img src=x> : Bravo`; the page holds no `b` and no `img` element, and no dialog opens.
- **AC-14** (new) (WebSocket) Chat and reactions pass spec 037's traffic checker, which treats chat text as user content. In spec 037 AC-1's full game (its "Test harness"), Bob also sends the chat messages `IDES, je crois` (before any letter of IDES is typed) and `<b>VIDE</b> ?`, Ana sends `oui`, and Bob sends a `react` on IDES with `wow`, all before Cy joins, so that Cy's snapshot holds the three lines. Every recorded frame passes spec 037's three rules once the `text` of each `chat_message` and of each entry of a snapshot's `chat` is set aside; each of those texts equals a text that a client sent in a `chat`; and every `reaction` frame passes the three rules as it is.
- **AC-15** (new) (browser with mocked socket) The chat and reaction controls keep the room's layout on every window. Setup: spec 024 AC-8's (spec 013 AC-6's FX-01 snapshot with `you` host among 8 players, 100 feed items, (3, 1) tapped, help mode `free`). At each window size of spec 006 AC-5, in desktop and touch contexts:
  - Collapsed: with 100 unread lines added (`chat-unread` reads `99+`), every check of spec 013 AC-6 holds; `chat-toggle` is in `room-toolbar` before `undo-button` in document order, with no control of specs 018 to 024 before it (only spec 027's timer controls may come first); and spec 024 AC-8's toolbar checks hold with `chat-toggle` and `react-button` among the toolbar's buttons (on the four small windows, the one row; with the keyboard focus, inside the toolbar's client area with the outline not clipped; `elementFromPoint` at the centre after `scrollIntoView`). On the four small windows, with the toolbar's `scrollLeft` at 0, `chat-unread` lies inside the toolbar's client area.
  - Targets: `chat-toggle`, `react-button`, each `reaction-option`, each `mute-player` and `chat-send` have a bounding box of at least 24 by 24 CSS px.
  - Open: in that state with the panel open (a non-empty `chat-input`), and in a second state with the picker open after a tap on the clue cell (0, 3), the panel or the picker lies inside the window (1 px tolerance) and is outside `room-toolbar`; `chat-toggle` or `react-button` is uncovered (`document.elementFromPoint` at its centre returns it or a descendant); the page has no scroll (`document.documentElement.scrollWidth <= window.innerWidth` and `document.documentElement.scrollHeight <= window.innerHeight`); and `grid-viewport`, `clue-bar` and, in touch contexts, `keyboard` have the bounding boxes they had before it opened (1 px tolerance). In a third state with both open (after the tap on the clue cell (0, 3), the panel opened with a non-empty `chat-input`, then the picker), each of these checks holds for each of the two, `chat-toggle` and `react-button` are both uncovered, the intersection of the bounding boxes of `chat-panel` and `reaction-picker` is at most 1 px wide or at most 1 px high, and `chat-panel` has the bounding box it had before the picker opened (1 px tolerance). (Note from the lead, 2026-10-15: the third state is added; the picker and the panel may be open together, decision 15 (spec 022's tests).)
  - Votes: with spec 025's vote banner showing `vote-yes` and `vote-no` (a `vote_opened` from `p2` whose request is a grid check) and the panel open, and again once the picker is open too (both open), `document.elementFromPoint` at the centre of each vote button returns it. (Note from the lead, 2026-10-15: "then the picker open" became "and again once the picker is open too (both open)", decision 15 (spec 022's tests).)
  - `chat-input` is not inside `grid-viewport`, `clue-bar`, `keyboard` or `grid`.
- **AC-16** (new) (browser with mocked socket, keyboard only after the setup) The chat and reaction controls are reachable from the keyboard and readable in French. At 1280 by 720, `you` host, after a tap on the clue cell (0, 3): `tab_to` reaches `react-button` and `chat-toggle`, and with the picker open each `reaction-option`, and with the panel open `chat-input`, `chat-send` and the `mute-player` of `p2`; each shows spec 035 AC-2's outline; typing `Bonne idée !` in `chat-input` and pressing `Enter` sends it. With the panel open and then the picker opened too (its first option takes the focus), one `Tab` from the last `reaction-option` puts the focus on an element inside `chat-panel`. (Note from the lead, 2026-10-15: added; the keyboard side of "the picker comes before `chat-panel`", tested with both open, decision 15 (spec 022's tests).) At 1280 by 720 and 360 by 740, in a state with the panel open (lines `IDES, je crois` from `p2` and `Bonne idée !` from `p3`) and a `clap` reaction of `p2` shown on IDES, and in a state with the panel closed and 3 unread lines: spec 035's contrast scan finds no offending element, and its language scan, with the chat texts added to its test data ("Test harness"), finds no text outside `fr.json` and the test's data; it accepts `Discussion, 3 messages non lus`, `Bob : Bravo` and `👏`.
- **AC-17** (new) (browser with mocked socket) While the vote banner shows, it is drawn above an open chat panel, which stays open and usable under it and is fully visible again once the banner has gone. Setup: AC-15's, except that `p2` is host (so the panel holds no `chat-moderation` and `Shift+Tab` from `chat-input` reaches `chat-list`, as in AC-12), with the panel open, the picker closed and 100 lines from `p2` in the snapshot's `chat` (the test checks from its measures that `chat-list` scrolls, as AC-12 does); "the five banner points" are the centre of `vote-banner`'s bounding box and its four corners each moved 2 px inwards on both axes, and "the five panel points" are the same points of `chat-panel`'s box. At each window size of spec 006 AC-5, in desktop and touch contexts:
  - Typing: the test types `ok` in `chat-input` (which has the focus), reads the bounding box of `chat-panel` and the `scrollTop` of `chat-list`, then the mock sends `vote_opened` (the next seq, by `p2`, a grid check). Once `vote-banner` shows, and again 1,000 ms later: `document.elementFromPoint` at each of the five banner points returns `vote-banner` or a descendant; `chat-panel` is present with the bounding box read before (1 px tolerance); `chat-list`'s `scrollTop` is the one read before (1 px tolerance); `window.scrollX` and `window.scrollY` are 0; `document.activeElement` is `chat-input`. `Enter` then sends exactly one `chat` frame, whose `text` is `ok` (spec 017's heartbeat `ping` frames are not counted).
  - List focus: in a second run, before the `vote_opened`, the test presses `Shift+Tab` from `chat-input` so that `chat-list` has the focus, then reads the same values; after the `vote_opened`, at the same two moments, the same checks hold with `document.activeElement` being `chat-list`. No check of the outline of `chat-list` is made while the banner shows.
  - After the vote: in each run the mock then sends `vote_closed` (the next seq, `rejected`); once `vote-banner` has left the page (spec 025: between 2,500 and 4,500 ms later), `document.elementFromPoint` at each of the five panel points returns `chat-panel` or a descendant, and `chat-panel` still has the bounding box read before (1 px tolerance).
  (Note from the lead, 2026-10-15: added, decision 16 (review of spec 022).)
- **AC-18** (new) (browser with mocked socket) A mute closes the reaction picker and moves the focus off the disabled chat controls. Given a FX-01 snapshot with `seq` 5 in which `p2` is host (so `you`, `p1`, is not), at 1280 by 720 and at 360 by 740; "the mute" is the mock's `player_muted` with seq 6 for `p1` with `muted` true. In every case below, "within 300 ms" counts from the moment the mock sends the mute frame and is one deadline for all the checks of the case: each check holds at the latest 300 ms after that moment (the test gives each check the time left to that deadline, not 300 ms of its own):
  - Picker: after a tap on the clue cell (2, 0) (VIDE) and a click on `react-button`, the picker is open and its first `reaction-option` has the focus; after the mute, within 300 ms, there is no `reaction-picker`, `react-button` is disabled with `aria-expanded="false"`, and `document.activeElement` is the `grid` element; the mock received no `react` frame. In a second run, the test taps VIDE first, then opens the panel (a click on `chat-toggle`), then the picker (a click on `react-button`; its first option has the focus), in this order because on a narrow window the open panel may cover the clue cell: after the mute, within 300 ms, there is no `reaction-picker`, `document.activeElement` is the `grid` element, and `chat-panel` is present with the bounding box it had before the mute (1 px tolerance).
  - Chat input: with the panel open, the test types `salut` in `chat-input` (which has the focus); after the mute, within 300 ms, `chat-input` and `chat-send` are disabled, `chat-muted` shows, `chat-panel` is present, `chat-input`'s value is `salut`, and `document.activeElement` is `chat-toggle`.
  - Send button: as the previous case, but with one `Tab` from `chat-input` after typing, so that `chat-send` (enabled) has the focus before the mute; after it, within 300 ms, `document.activeElement` is `chat-toggle`.
  (Note from the lead, 2026-10-15: added, decision 19 (review of spec 022).) (Note from the lead, 2026-10-15: the second picker run now taps VIDE before it opens the panel, which on a narrow window may cover the cell; and the 300 ms count from the mute frame, one deadline for all the checks of a case, where each check could be read as having 300 ms of its own (second review of spec 022).)
- **AC-19** (new) (browser with mocked socket) The chat notes take no room from the panel, fit on one line and show one at a time. Setup: a FX-01 snapshot with `seq` 25 in which `p2` is host (so `you`, `p1`, is not, as in AC-18) and whose `chat` holds 20 lines from `p2` (seq 3 to 22), so that the list is full before and after the five lines of the wait and both runs; the panel is open. "The panel's box" is the left, top, width and height of the bounding box of `chat-panel`. A note is "on one line" when the rectangles that `Range.getClientRects()` returns for the contents of the note (`selectNodeContents`) all have the same `top` and all lie inside the panel's box, each within 1 px. Each run starts on a new page by reading the panel's box with neither `chat-muted` nor `chat-wait` on the page. At each window size of spec 006 AC-5, in a desktop context, the first two runs; at 1280 by 720 and at 320 by 568 only, the third:
  - Muted: the mock sends `player_muted` (seq 26, `p1`, `muted` true); once `chat-muted` shows `fr.json["chat.muted"]`, the panel's box is the one read at the start (1 px tolerance) and `chat-muted` is on one line. The mock then sends `player_muted` (seq 27, `p1`, `muted` false); once `chat-muted` is gone, the panel's box is still the one read at the start (1 px tolerance).
  - Wait: the test types `m1` to `m5` with the keyboard, each followed by `Enter`, the mock answering each with its `chat_message` from `p1` (seq 26 to 30); once `chat-wait` shows `fr.json["chat.wait"]`, the panel's box is the one read at the start (1 px tolerance) and `chat-wait` is on one line.
  - Both: the test sends `m1` to `m5` as in the wait run, and once `chat-wait` shows, the mock sends `player_muted` (seq 31, `p1`, `muted` true); once `chat-muted` shows `fr.json["chat.muted"]`, the page holds no `chat-wait` and the panel's box is the one read at the start (1 px tolerance). The mock then sends `player_muted` (seq 32, `p1`, `muted` false), less than 12 seconds after the first send, so that the pacing still holds; once `chat-muted` is gone, `chat-wait` shows `fr.json["chat.wait"]` again and the panel's box is still the one read at the start (1 px tolerance).
  (Note from the lead, 2026-10-15: added, decision 20 (second review of spec 022).) (Note from the lead, 2026-10-15: the "Both" run is added, and the title says "show one at a time", decision 22 (second review of spec 022).)
- **AC-20** (new) (browser with mocked socket) After a chat message is sent, the focus is on `chat-input`, whichever way it was sent (`Enter`, a keyboard activation of `chat-send`, a click or a tap), and also when the send starts the pacing. Given a FX-01 snapshot with `seq` 5 (the players of "Test harness", `p1` host) and the panel open (`chat-input` has the focus), at 1280 by 720 and at 360 by 740 in a desktop context, the player sends `m1` to `m5` in this order, the mock answering each with its `chat_message` from `p1` (seq 6 to 10): `m1` with `Enter` in `chat-input`; `m2` with one `Tab` (the focus is on `chat-send`, which is enabled) then `Enter`; `m3` with a click on `chat-send`; `m4` as `m2`; `m5` as `m3`. The test types each text with the keyboard into the focused field and does not set the value of `chat-input` directly, so that a lost focus fails the test. After each of the five sends, within 300 ms of the key or the click: the mock has received one `chat` frame whose `text` is that text (spec 017's heartbeat `ping` frames are not counted), `chat-input` is empty, and `document.activeElement` is `chat-input`, neither `chat-send` nor `document.body`. After `m5`, which starts the pacing, the same holds, and `chat-send` is disabled and `chat-wait` shows within that deadline too. Touch: at 360 by 740 in a touch context, with the panel open (opened by a tap on `chat-toggle`), the player types `t1` in `chat-input` and taps `chat-send`, the mock answering with its `chat_message` from `p1` (seq 6): within 300 ms of the tap, the mock has received one `chat` frame whose `text` is `t1`, `chat-input` is empty and `document.activeElement` is `chat-input`.
  (Note from the lead, 2026-10-15: added, decision 21 (second review of spec 022).) (Note from the lead, 2026-10-15: the touch case is added (second review of spec 022).)

## Edge cases and errors

- Order (AC-1): chat lines follow the room's seq, so every page lists them in the
  same order, whatever order the frames arrive in (spec 040 buffers out-of-order
  events).
- Length (AC-2): characters are code points (spec 039): an emoji made of several
  code points counts as several. `maxlength` counts UTF-16 units, which is never
  fewer than code points, so the page never sends more than 280. A text that the
  page's `trim()` keeps but Python's `str.strip()` empties (one made only of
  whitespace, with at least one of the characters that `trim()` keeps: the
  separators U+001C to U+001F and U+0085) fails spec 039's `ChatText`, which strips
  as `str.strip()` does (its AC-8, `"\u001c\u001d"` among its examples), and gets
  `invalid_message`, which the page ignores; the message is lost. (Note from the
  lead, 2026-10-15: this sentence now cites spec 039's refined `ChatText` rule
  (decision 14); U+0085, which `trim()` also keeps, is added to the list (spec
  022's tests).)
- Frame size (AC-2): a 280-character message stays far below spec 037's 4,096
  bytes, even with every character escaped in JSON.
- Own lines (AC-6): never unread. My own line arriving while the panel is closed
  does not open it.
- First snapshot (AC-6): its history is not unread, whatever its length.
- Reconnection (AC-6): lines sent while the page was away come with the new
  snapshot and count as unread. Sending is disabled while the page is not
  `joined`, so no chat is lost or queued during a reconnection.
- Departed authors (AC-1): the page names a line by the nickname it knows. A page
  that joined after the author left does not know that nickname, since the
  snapshot and `chat_message` carry only the player id, and shows
  `t("feed.someone")`.
- History size (AC-1, AC-11): the snapshot carries the whole history (spec 039
  decision 12); the page shows the last 200 lines. With the limit of AC-9, a room
  of 8 players cannot add more than 8 lines every 2 seconds; a normal game stays
  far below. Spec 036 measures loading with an empty chat.
- Limit window (AC-9): sliding, as spec 037's: 5 messages at `t` and one at
  `t + 9.999` drop the last; at `t + 10.0` the first five no longer count.
- Dropped silently (AC-9): the page would read a `rate_limited` error as the answer
  to its oldest pending edit (spec 015), so chat and reactions over the limit get
  no error. The page's pacing (AC-10) keeps a working page under the limit.
- Muted host (AC-7): spec 014 refuses a mute on one's own id, so a muted player who
  becomes host (spec 014 hand-over) stays muted until another host unmutes them.
- Muted and reactions (AC-7): a muted player's reactions are dropped too.
- Reactions are never logged or replayed (AC-3): a page that joins or reconnects
  does not see a reaction made before.
- Reaction on an unknown clue (AC-4): the server drops a reaction whose clue names
  no word, and the page shows nothing for one that is not a clue of its grid.
- Two reactions in a row on one clue (AC-4): the newer replaces the older, so a
  clue never shows more than one.
- Pending edits (AC-7, AC-9): no chat or reaction answer touches them.
- Escaping (AC-13): chat text, author names and reaction labels are inserted as
  text, never as HTML (spec 037 AC-4's static rule).
- Solved grid (AC-1, AC-3): chat and reactions keep working (spec 026).
- Phone keyboard (AC-15): on a touch screen, `chat-input` opens the system keyboard
  when the player taps it; the in-app keyboard of spec 009 stays for the grid.
  Whether a real phone's keyboard covers the panel cannot be checked headless.
- Small windows (AC-15): `chat-toggle` comes before the room's tools in the toolbar
  (only spec 027's timer comes before it), so its unread count shows before any
  sideways scroll; `react-button` may be scrolled out of view, and spec 024's edge
  fade shows that more controls follow.
- Popovers and the toolbar (AC-15): the toolbar scrolls sideways on a small window,
  and a scroll container clips what is drawn inside it, so the panel and the picker
  are outside it in the DOM, right after it.
- Votes (AC-15): the panel and the picker never cover spec 025's vote buttons, so a
  player who is chatting still sees a vote and can answer it within its 20 seconds.
- Vote banner over the panel (AC-17): on a small window the banner may hide the
  top of an open panel (its heading, the oldest visible lines) while it shows; the
  panel does not move or close, and the page does not scroll it into view. (Note
  from the lead, 2026-10-15: added, decision 16 (review of spec 022).)
- Restart (AC-9): a restart gives every player, connected or disconnected, a fresh
  chat and reaction window. For spec 037's edit limit it does so only for the
  players it disconnects (spec 018). (Note from the lead, 2026-10-15: added,
  decision 17 (review of spec 022).) (Note from the lead, 2026-10-15: "as it does
  for spec 037's edit limit" is replaced by the difference with `recent_edits`
  (second review of spec 022).)
- Mute while reacting or typing (AC-18): the picker closes and the focus goes to
  the `grid` element; a focus on `chat-input` or `chat-send` goes to
  `chat-toggle`. The typed text is kept, and can be sent once unmuted. (Note from
  the lead, 2026-10-15: added, decision 19 (review of spec 022).)
- Selection cleared while the picker is open (AC-18's rule): spec 007 clears the
  selection only when a second snapshot no longer has its word, which cannot
  happen on one room's grid, so only the mute case is tested. (Note from the
  lead, 2026-10-15: added (review of spec 022).)
- Notes and the panel's box (AC-19): `chat-muted` and `chat-wait` share one slot
  that is always there, so the panel is as high and as wide with a note as
  without; `t("chat.wait")` is short for the narrowest window, 320 px wide. The
  one-line rule is for the default root font size, at zoom 1 as the window sizes
  of spec 006 AC-5 are; no criterion tests a note at a larger root font. When
  both notes apply, only `chat-muted` shows, and `chat-wait` comes back after an
  unmute if the pacing still holds; `chat-wait` going away when its 12 seconds
  end is AC-10's, not AC-19's. (Note from the lead, 2026-10-15: added, decision 20
  (second review of spec 022).) (Note from the lead, 2026-10-15: the both-notes
  sentence is added, decision 22 (second review of spec 022).)
- Focus after a send (AC-20): the focus is on `chat-input` after a send, not on
  `chat-send`, which the send disables, and not on `document.body`. On a touch
  screen this keeps the system keyboard from being closed by a send; whether a
  real phone does keep it cannot be checked headless. A mute that comes later
  moves the focus as "Focus at a mute" says (AC-18). (Note from the lead,
  2026-10-15: added, decision 21 (second review of spec 022).)
- Feed (AC-1): chat adds no line to the activity feed (spec 013 decision 4).

## Out of scope

- Voice and video (epic E5).
- Authorship view: spec 019.
- Pencil letters: spec 020.
- Clue flag: spec 021.
- Deleting chat at room expiry: spec 032 AC-1 and spec 038 AC-2 (AC-8 checks only
  that chat is kept with its room).
- Editing or deleting a message, private messages, mentions, links, images, emoji
  pickers for chat text, typing indicators, read receipts, sounds and
  notifications.
- A history that loads older lines on demand, and keeping a draft message across a
  reload.
- Muting a player for everyone except the host, reporting a player, word filters.
- A screen reader announcement of new lines or reactions (spec 035 leaves other
  players' actions out of the live region); the chat list is readable as it is.
- A keyboard shortcut to open the chat (spec 035 out of scope).

## Work packages

None.

## Decisions

The backlog's numbers are kept, as the human answered on 2026-10-14 ("numeric
thresholds keep the backlog defaults"): 280 characters, a set of 5 reactions, 3
seconds. The items below were proposed in the Phase 6 refine (2026-10-14) and
approved by the human with this spec. Each one is already part of the spec above.
Items 1, 3, 4, 6 and 7 were also open questions: the human's answers to them are
items 9 to 13 below.

1. Limits (spec 037 throttles edits only). Pick: 5 chat messages and 5 reactions
   per player in any 10 seconds, sliding, counted separately from spec 037's 20
   edits a second. Over the limit the server drops the message without an answer,
   because the page matches every `rate_limited` to a pending edit (spec 015). The
   page paces itself at 5 in 12 seconds. Muting (spec 014 AC-6) stays the host's
   answer to abuse; spec 037's frame limit and spec 036's flood guard still apply.
2. Reactions are relayed through `reply` and `to_others`, so the hub needs no new
   delivery step; `Outcome.to_others` is widened to accept `ReactionShown`.
3. Mute covers chat and reactions; flags, letters and checks are not affected.
4. Mute buttons live in the chat panel, for the host only. The roster's low layout
   has room for one remove button and no more (spec 014 AC-10).
5. Unread lines are counted from the page's first snapshot, by seq, and lines that
   came during a reconnection count.
6. Small windows: the two buttons join spec 024's `room-toolbar` (one row that
   scrolls sideways), `chat-toggle` first so that its unread count shows, and
   `react-button` beside the other word actions. The panel and the picker are drawn
   over the page and move nothing, like spec 025's vote banner, so spec 013 AC-6's
   layout holds whether they are open or not; they come right after the toolbar in
   document order, before the grid, so spec 035's "nothing focusable after the
   grid" holds.
7. The page shows the last 200 lines; the snapshot keeps carrying the full history
   (spec 039 decision 12).
8. A shown reaction is drawn over the clue of its word, the newest one only, for
   3 seconds from its arrival.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question. Each one is already part of the spec above.

9. Limits: values and answer (former open question 1). Options: 5 chat messages and
   5 reactions per player in 10 seconds, dropped without an answer; the same values
   answered with `rate_limited`, accepting that a page past the limit may drop an
   unrelated pending edit (spec 015); or reopen spec 039 to add a chat-specific
   `ErrorCode`. Pick: 5 and 5 in 10 seconds, dropped without an answer (decision 1).
   Other values are a one-line change in `RoomConfig`.
10. Mute scope (former open question 2). Options: mute stops chat and reactions; or
    chat only, as the backlog's words say ("mute a player's chat"). Pick: chat and
    reactions (decision 3).
11. Where the host mutes (former open question 3). Options: in the chat panel; or a
    button beside `remove-player` in the roster, which needs spec 014 AC-9 and AC-10
    reworked for two buttons per player in the low layout. Pick: the chat panel
    (decision 4), so spec 014 does not change.
12. Lines on the page (former open question 4). Options: the last 200, like the
    feed's 100; or the whole history. Pick: the last 200 (decision 7).
13. Small windows (former open question 5). Options: one toolbar row that scrolls
    sideways, with an edge fade; or an `Aide` menu, where `react-button` could move
    while `chat-toggle` stays visible in the header for its unread count. Pick: the
    toolbar row, as spec 024 decision 12 decides for the whole toolbar. `chat-toggle`
    comes first in the row so that its unread count shows before any sideways
    scroll, and `react-button` sits beside the other word actions (decision 6).

Decided by the lead on 2026-10-15, under the owner's delegation of technical and
layout choices, on two questions of the test-writer. Each one is already part of
the spec above. (Note from the lead, 2026-10-15: added (spec 022's tests).)

14. Control characters in a chat text (AC-2, edge case "Length"). The edge case
    relied on Python's `str.strip()`, while spec 039's `ChatText` used pydantic's
    whitespace stripping, which keeps the separators U+001C to U+001F, so
    `"\u001c\u001d"` parsed as a valid chat of two invisible characters. Pick: both
    follow Python's `str.strip()`, since these separators are invisible and never
    meant as chat text. Spec 039 (`done`, status kept) is refined: its `ChatText`
    is stripped as `str.strip()` does, then holds 1 to 280 characters, and its
    AC-8 gains `"\u001fsalut\u001c"` (gives `"salut"`) and `"\u001c\u001d"`
    (refused). Its AC-8 tests are updated before its code.
15. The reaction picker and the chat panel at once (AC-5, AC-15, AC-16). The spec
    did not say whether both can be open together, so "the picker comes before
    `chat-panel`" could not be tested. Options: both may be open, each where it
    sits alone and without overlapping the other; or opening one closes the
    other, the order rule becoming that of `react-button` and `chat-toggle` in
    the toolbar. Pick: both may be open, with the document-order rule kept and
    tested with both open. The layout criteria do not rule it out: both are
    drawn over the page (decision 6), so together they still move nothing and
    take no room from the grid; at 568 by 320 a panel of the example width
    `min(22rem, 100vw - 1rem)` (352 px) leaves about 200 px of the width beside
    it, room for one row of five options of 24 px, and on a narrow window such as
    320 by 568 the picker fits above or below the panel. The other option would
    also lose the text typed in `chat-input`, which exists only while the panel
    is open, each time a player reacts.

Decided by the lead on 2026-10-15, under the human's delegation of layout and
accessibility choices, on the reviewer's suggestions (none blocking). Each one is
already part of the spec above. (Note from the lead, 2026-10-15: added (review of
spec 022).) (Note from the lead, 2026-10-15: decisions 20 to 22 are added, and
decisions 17 and 18 are reworded (second review of spec 022).)

16. Vote banner and chat panel (AC-17). On a small window spec 025's banner, laid
    over the top of `grid-viewport`, can overlap the panel, and the spec did not
    say which is on top. Pick: the banner, for as long as it shows (its 20 seconds
    and its result's 3 seconds): a vote is short and shared by the whole room,
    while the panel can wait. The panel stays open, keeps its box and the focus,
    and the page makes no scroll call to uncover it; the list's "fully visible
    outline" rule does not apply to the hidden part meanwhile.
17. Limit windows at a restart (AC-9). `after_restart` cleared `recent_edits` on
    the players it disconnects (spec 018) and kept `recent_chat` and
    `recent_reactions` on all of them, so a room loaded from a snapshot kept
    windows that one rebuilt from the log lost. Pick: it clears both, for every
    player, connected or disconnected, as spec 025 decision 16 makes the two loads
    give the same vote. (Note from the lead, 2026-10-15: "on the players it
    disconnects" and "connected or disconnected" are added; spec 018 clears
    `recent_edits` only for the players the restart disconnects (second review of
    spec 022).)
18. Height of `chat-toggle` (AC-6). Pick: the toggle keeps its height when the
    count appears or goes and when the panel opens; the toolbar row (spec 024)
    then never moves. How the toggle keeps it is the implementer's choice. (Note
    from the lead, 2026-10-15: reworded; the pick named a slot of fixed height for
    the count, a mechanism, where the rule is what users see: the toggle's height
    (second review of spec 022).)
19. Mute while the picker is open or the chat form has the focus (AC-18). Pick: the
    picker closes whenever `react-button` becomes disabled, with the focus, if it
    was inside, on the `grid` element (as spec 025 decision 19 for the banner); a
    focus on `chat-input` or `chat-send` moves to `chat-toggle`, the always-present
    control where `Escape` from the panel goes. Both targets are fixed, never
    `document.body`.
20. Chat notes (AC-19). The spec did not say that a note leaves the panel's box
    alone, nor how long a note may be, and the French wait text did not fit one
    line at 320 px wide. Pick: `chat-muted` and `chat-wait` sit in one slot of the
    panel that is always present, empty when neither applies, and one line high, so
    that a note coming or going never moves the panel's box; `chat.wait` becomes
    `Patientez avant d'envoyer.` so that it fits that line at every window size of
    spec 006 AC-5. Which note shows when both apply is decision 22. (Note from the
    lead, 2026-10-15: added (second review of spec 022).)
21. Focus after sending (AC-20). The submit empties `chat-input`, which disables
    `chat-send`, and the spec did not say where the focus goes after a send (a
    pre-existing gap). Pick: after a send, by `Enter` in `chat-input` or by
    activating `chat-send` (keyboard, click or tap), the focus is on `chat-input`,
    also when the send starts the pacing (`chat-send` is then disabled); it never
    drops to `document.body`. (Note from the lead, 2026-10-15: added (second review
    of spec 022).)
22. Both chat notes at once (AC-19). A player who sent 5 messages in the last 12
    seconds and is then muted has `chat-muted` and `chat-wait` both to show, in a
    slot one line high. Options: (a) only `chat-muted` shows while the mute lasts,
    then `chat-wait` shows if the pacing still holds after the unmute; (b) only
    `chat-wait` shows while the pacing lasts; (c) both show, one under the other,
    so that the slot and the panel grow by a line for that time (the panel's box
    then changes, which decision 20 is meant to prevent). Pick: (a): the mute is
    the host's decision and the reason why the form is disabled, the wait adds
    nothing while the player cannot send, and the panel's box never changes; it
    is also what the page does today. AC-19 tests it at 1280 by 720 and at 320 by
    568. (Note from the lead, 2026-10-15: added; the lead's answer, under the
    delegation of layout choices, to the question the spec-writer raised in the
    second review of spec 022.)

## Open questions

None.
