---
id: "013"
title: Presence
status: approved
---

# 013 - Presence

Epic E3 Rooms and presence (US-3.3) · Release: MVP · Epic depends on: E2
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine and the
fake-clock harness are defined in spec 011; players, colours and the roster in spec
012; disconnection detection in spec 017; the grid, selection and words on the page
in specs 006 and 007. The messages are those of spec 039.

## Goal

As a player, I want to see who is here and where they are working, so that we don't solve the same clue twice.

A room is one grid shared by up to 8 players and reached by a link.

## Public interface

### Server rules (`nock.room`)

Input: every message of a joined player except `join` and `ping` (spec 017). On an
input from player `p`, before the message's own effect:
`p.last_input_at = now`; if `p.state` is `idle`, it becomes `active` with one entry
`PlayerStateChanged(p, state=active)`, ahead of the message's own entries.

`handle_message` for `SelectCell(row, column, direction)` from `p`:

- `(row, column)` is not a letter cell of the grid: refused,
  `ErrorMessage(code=NOT_A_LETTER_CELL)`, selection unchanged.
- otherwise `p.selection = Selection(row, column, direction)`, no entry (selection
  has no `seq`, spec 039 decision 2), and
  `to_others = (SelectionMoved(player_id=p, selection=<it>),)`. A selection equal to
  the current one is still relayed.

`tick(state, now, config)` (built by spec 017; this spec adds a step after
spec 017's, and spec 014 adds one after this): each player with `state == active`
and `now - last_input_at >= config.idle_after_seconds` becomes `idle`, with one
entry `PlayerStateChanged(p, state=idle)`. Players are visited in `players` order.

`disconnect_player` (spec 012) gains: the player's `selection` becomes None and, if
it was not None, `to_others = (SelectionMoved(player_id=p, selection=None),)`,
after the state entry. A disconnected player's selection is never shown.

`snapshot_for` already carries each player's `state` and `selection` (spec 012);
the joiner thus sees the others' current selections.

### Client: roster

The roster of spec 012 gains, in each `roster-player`:
`data-testid="roster-state"` with the text `t("presence.<state>")`. `data-state`
and `data-colour` keep their meaning. Items keep the join order.

### Client: other players' selections

The page keeps each other player's last selection (from the snapshot and from
`selection_moved`; cleared by `selection_moved` with `null`, and when the player's
state becomes `disconnected` or the player leaves).

On a `cell` (spec 006):

- for each other player whose selection is that cell, one child
  `data-testid="remote-selection"` with `data-player-id` and `data-colour`, drawn
  as a dashed border (computed `border-style` `dashed`, at least 2 px wide) in that
  player's colour (computed `border-color` equal to the computed
  `background-color` of their `roster-colour`). With several, each is inset by a
  different amount (for example 3 px per rank in roster order), so all stay visible.
- `data-tinted-by`: the ids of the other players whose selected word holds that
  cell (word of their selected cell in their direction, spec 007 rules), separated
  by one space, in roster order; `""` when none. A tinted cell that is not in my
  own selected word has a computed `background-color` different from an untinted,
  unselected letter cell; the tint is the player's colour at low opacity (the first
  in roster order when several).

My own selection keeps the look of spec 007 (background fill, no dashed border),
and the page never draws a `remote-selection` for `you`.

### Client: activity feed

`data-testid="activity-feed"`, heading `t("feed.heading")`, a list of
`data-testid="feed-item"` elements, oldest first, at most the last 100 items. Each
item has `data-kind` and `data-seq` (the event's seq) and the text below, where
`{name}` is the nickname of the event's player (known players include those who
left; unknown: `t("feed.someone")`). An item is added when its event is applied
(spec 040), so items follow `seq` order. The snapshot adds no item (spec 039
decision 12).

| Event | `data-kind` | Text |
| --- | --- | --- |
| `player_joined` | `player_joined` | `t("feed.player_joined", {name})` |
| `player_left`, reason `left` | `player_left` | `t("feed.player_left", {name})` |
| `player_left`, reason `removed` | `player_removed` | `t("feed.player_removed", {name})` |
| `player_left`, reason `timed_out` | `player_timed_out` | `t("feed.player_timed_out", {name})` |
| `check_result`, scope letter / word / grid | `check` | `t("feed.check.letter" / "feed.check.word" / "feed.check.grid", {name})` |
| `reveal_result`, scope letter / word | `reveal` | `t("feed.reveal.letter" / "feed.reveal.word", {name})` |
| `flag_changed` with a clue | `flag` | `t("feed.flag", {name, clue})`, `clue` = the clue's text |
| `settings_changed`, only `locked` differs from the previous settings | `room_locked` or `room_unlocked` | `t("feed.room_locked", {name})` or `t("feed.room_unlocked", {name})` |
| `settings_changed`, otherwise | `settings_changed` | `t("feed.settings_changed", {name, help_mode, letters, words})`, `help_mode` = `t("settings.help_mode.<mode>")`, `letters` and `words` from `settings.reveal_budget` |
| `host_changed` | `host_changed` | `t("feed.host_changed", {name})` |

Other events (`letter_changed`, `cell_locked`, `player_state_changed`,
`flag_changed` with `null`, votes, chat, completion) add no item. The nickname is
the one known when the event is applied.

New `fr.json` keys:

| Key | Value |
| --- | --- |
| `presence.active` | `actif` |
| `presence.idle` | `inactif` |
| `presence.disconnected` | `déconnecté` |
| `feed.heading` | `Activité` |
| `feed.someone` | `Quelqu'un` |
| `feed.player_joined` | `{name} a rejoint le salon` |
| `feed.player_left` | `{name} a quitté le salon` |
| `feed.player_removed` | `{name} a été retiré du salon` |
| `feed.player_timed_out` | `{name} est parti (déconnecté trop longtemps)` |
| `feed.check.letter` | `{name} a vérifié une lettre` |
| `feed.check.word` | `{name} a vérifié un mot` |
| `feed.check.grid` | `{name} a vérifié la grille` |
| `feed.reveal.letter` | `{name} a révélé une lettre` |
| `feed.reveal.word` | `{name} a révélé un mot` |
| `feed.flag` | `{name} bloque sur « {clue} »` |
| `feed.room_locked` | `{name} a verrouillé le salon` |
| `feed.room_unlocked` | `{name} a déverrouillé le salon` |
| `feed.settings_changed` | `{name} a modifié les réglages : aide {help_mode}, {letters} lettres et {words} mots à révéler` |
| `feed.host_changed` | `{name} est maintenant l'hôte` |
| `settings.help_mode.free` | `libre` |
| `settings.help_mode.vote` | `par vote` |
| `settings.help_mode.none` | `désactivée` |

### Test harness

As spec 011. Mocked-socket tests send events built with the `nock.protocol` models
(the wire examples of spec 039 with chosen seqs). Relay timing uses
`time.monotonic()` on the test side.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-3.3.1) (Python; WebSocket with a fake clock; browser with mocked socket) A roster lists each player with a colour and a state: active, idle after 2 minutes without input, or disconnected. Python: with `p1` whose `last_input_at` is `t`, `tick` at `t + 119.9` changes nothing and at `t + 120` gives `PlayerStateChanged(p1, idle)`; a `SelectCell` from `p1` at `t + 130` gives `PlayerStateChanged(p1, active)` then the selection; a `Ping` at `t + 130` does not. WebSocket: A and B join; after `advance(120)` B receives `PlayerStateChanged(<A>, idle)` (and A receives B's) within one second of real time; A's next `select_cell` makes B receive `PlayerStateChanged(<A>, active)` before the `selection_moved`. Browser: given a snapshot with `p1` (`you`, colour 0, active), `p2` (colour 1, idle) and `p3` (colour 2, disconnected), the roster shows three items in that order with `data-colour` 0, 1, 2, pairwise different `roster-colour` background colours, `data-state` `active`, `idle`, `disconnected`, and `roster-state` texts `fr.json["presence.active"]`, `fr.json["presence.idle"]`, `fr.json["presence.disconnected"]`; a `player_state_changed` for `p2` `active` updates its item.
- **AC-2** (AC-3.3.2) (WebSocket; browser with mocked socket) Another player's selected cell is outlined in their colour and their word lightly tinted, within 300 ms of their move. WebSocket: A and B join a FX-01 room; A sends 100 `select_cell` messages on random letter cells, each after B received the previous `selection_moved`; B receives each as `SelectionMoved(player_id=<A>, selection=...)` with the same values, A receives none, and the 95th percentile of the relay times is at most 100 ms; a `select_cell` on (0, 0) is answered `not_a_letter_cell` to A and nothing to B. Browser: given the page joined with `p1` (`you`) and `p2` (colour 3), within 300 ms of the mock sending `selection_moved` for `p2` on (2, 2) `across`, (2, 2) holds one `remote-selection` with `data-player-id="p2"` and `data-colour="3"`, whose computed `border-style` is `dashed` and `border-color` equals `p2`'s `roster-colour` background colour; exactly (2, 1), (2, 2), (2, 3), (2, 4) have `data-tinted-by="p2"`, and (2, 1)'s background colour differs from that of (1, 1); a `selection_moved` for `p2` with `null` removes them.
- **AC-3** (AC-3.3.3) (browser with mocked socket) When two players select the same cell, both outlines are visible. Given `p1` (`you`), `p2` (colour 1) and `p3` (colour 2), when the mock sends `selection_moved` for `p2` and for `p3`, both on (1, 1) (`p2` across, `p3` down), then (1, 1) holds two `remote-selection` elements with `data-player-id` `p2` and `p3`, both visible, with different bounding boxes and different border colours; (1, 1) has `data-tinted-by="p2 p3"`. When `p1` also taps (1, 1), the two outlines stay visible and the cell also shows `p1`'s own selection (spec 007 `data-selected="true"`).
- **AC-4** (AC-3.3.4) (browser with mocked socket) My own selection is styled differently from every other player's. Given `p1` (`you`) and `p2`, after `p1` taps (3, 1) and the mock sends `p2`'s selection on (2, 2): (3, 1) has `data-selected="true"` and no `remote-selection` child; no cell has a `remote-selection` with `data-player-id="p1"`; the computed `border-style` of (3, 1) and of its children is never `dashed`; and the background colour of (3, 1) differs from the background colour of (2, 2) and of the tinted (2, 3).
- **AC-5** (AC-3.3.5) (browser with mocked socket) An activity feed lists joins, departures, checks, reveals, flags and setting changes in the order they happened. Given the page joined at `seq` 5 with players `p1` (`you`, `Ana`) and `p2` (`Bob`), when the mock sends, with seqs 6 to 12: `player_joined` (`p3`, `Cy`), `check_result` (`p2`, scope word), `reveal_result` (`p3`, scope letter), `flag_changed` (`p2`, clue (0, 3, 0)), `settings_changed` (`p1`, help mode `vote`, budget 5 letters and 1 word, unlocked), `settings_changed` (`p1`, same values but `locked` true), `player_left` (`p3`, reason `removed`), then `activity-feed` holds 7 `feed-item` elements with `data-seq` 6 to 12 in that order and `data-kind` `player_joined`, `check`, `reveal`, `flag`, `settings_changed`, `room_locked`, `player_removed`, whose texts are, in order, `Cy a rejoint le salon`, `Bob a vérifié un mot`, `Cy a révélé une lettre`, `Bob bloque sur « Fatales à César »`, `Ana a modifié les réglages : aide par vote, 5 lettres et 1 mots à révéler`, `Ana a verrouillé le salon` and `Cy a été retiré du salon` (each built from `fr.json`). Sending those events out of order (seq 8 before 7) still lists them by seq.

## Edge cases and errors

- Idle threshold (AC-1): `>=` 120 seconds; selections, edits, undo, chat, votes and
  host actions all count as input; pings and joins do not. A resume (spec 012)
  sets `last_input_at`, so a resumed player starts active.
- Disconnected players (AC-1): never turn idle; their state changes only by
  reconnection (active) or time-out (they leave, spec 017).
- Idle and selection (AC-2): an idle player's selection stays shown.
- Selection on a non-letter cell or off the grid (AC-2): `not_a_letter_cell`,
  nothing relayed; the page of spec 007 never sends one.
- Repeated selection (AC-2): relayed again; the page draws the same outline.
- Selection relay (AC-2): never sent back to the mover; never logged, so it has no
  `seq` and is lost on a server restart (spec 018 `after_restart`).
- Tint overlap (AC-3): two players on one word tint it with the first player's
  colour (roster order); both outlines remain distinct.
- My own word (AC-4): a cell in my selected word keeps spec 007's highlight even
  when also tinted by others; `data-tinted-by` still lists them.
- Unknown player id in an event (AC-5): `{name}` is `t("feed.someone")`; the page
  never fails on it.
- Departed players (AC-5): their nickname stays known for later feed items (for
  example a `player_left` after their own `player_joined`).
- Settings comparison (AC-5): against the settings the page held before the event
  (snapshot or previous `settings_changed`); a `settings_changed` that changes
  nothing (the server does not send one, spec 014) would read as `settings_changed`.
- Feed length (AC-5): the 101st item removes the oldest.
- Plural (AC-5): the text uses the numbers as they are (`1 mots`); proper plural
  forms are left to a later wording pass.
- Text injection (AC-5): names and clue texts are inserted as text (spec 037 AC-4).

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Guest join: spec 012.
- Host controls (the actions behind the lock and settings items): spec 014.
- Feed history before my arrival (spec 034), chat in the feed (spec 022), letters in
  the feed.
- Cursor trails, typing indicators, avatars.
- Showing selections of disconnected players.

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written.
Each one is already part of the spec above. (The `ping` message that item 1 and
AC-1 refer to is part of spec 039 since its reopening, decision 17 there.)

1. "Input" for idleness. Options: only edits, or any message. Pick: any message of
   the player except `join` and `ping`, so a player moving around without typing is
   active.
2. "Within 300 ms of their move" (AC-2). Pick: as spec 015, the server relay must
   stay within 100 ms at the 95th percentile on localhost, and the page draws the
   outline within 300 ms of receiving the message; the 4G network part is spec 036's.
3. Look of selections (AC-3, AC-4). Options: outline styles, corner badges, name
   labels. Pick: other players get a dashed border in their colour, inset per player
   so several stay visible, and a light tint of their word; my own selection keeps
   spec 007's fill and never a dashed border. Exact sizes and opacity are the
   implementer's.
4. Feed contents. The backlog lists joins, departures, checks, reveals, flags and
   setting changes. Picks: departures are `player_left` only (a disconnection is
   shown in the roster, not the feed); a cleared flag adds no line; lock and
   unlock get their own lines; host changes are shown (they matter to spec 014);
   the newest at the bottom; at most 100 items.
5. Feed wording. All texts are proposals in `fr.json`; plural forms are not handled.
6. Selections on the server. Pick: validated (letter cell) and relayed without a
   `seq`; cleared on disconnection, with a `selection_moved` to `null`.
7. Build order. The build plan builds this spec after spec 017 and before spec 014,
   so this spec writes the feed lines for lock, settings and host changes that
   spec 014 triggers. The lines for checks, reveals and flags are tested with mocked
   events, since specs 021, 023 and 024 come later.

## Open questions

None.
