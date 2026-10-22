---
id: "013"
title: Presence
status: done
---

# 013 - Presence

Epic E3 Rooms and presence (US-3.3) · Release: MVP · Epic depends on: E2
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine and the
fake-clock harness are defined in spec 011; players, colours and the roster in spec
012; disconnection detection in spec 017; the grid, selection and words on the page
in specs 006 and 007. The messages are those of spec 039.

(Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells
(`_design.md` section 6): another player's selected cell is a plain triangle in
their colour in a corner of the cell, corners given by order of arrival, at most
four, instead of a dashed border; the word tint is 16 % (spec 041) and each player
can turn it off with spec 042's « Mots des autres » switch. "Client: other
players' selections", decision 3, AC-2 and AC-3 change, so the test-writer updates
the tests of AC-2 and AC-3 before the implementer runs. The feed, the roster and
the other criteria do not change; the feed becomes the Salon's stream in step 3.)

(Note from the lead, 2026-10-22: refined by spec 043, the design's room layout
(`_design.md` section 8). The roster is the Salon's Joueurs tab, with each
player's current clue under the name; the feed is the Salon's stream, one list
shared with the chat messages (`chat-list` inside `activity-feed`), in seq order,
with its own cap of 100 event lines and spec 043's pictograms, which are drawn by
CSS and leave each `feed-item`'s text as below; its heading (`feed.heading`) goes,
and the list is named by the Discussion tab's hidden heading. "Client: activity
feed", "Client: feed height" (the list fills its tab panel, which is never above
the grid) and AC-6 change, so the test-writer updates the tests of AC-6 before the
implementer runs. The scroll rules (AC-7, AC-8) apply to the stream list
unchanged; their tests show the Discussion tab first (spec 043's "Test
harness"). The other criteria do not change.)

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

- for each other player whose selection is that cell and who holds one of its
  four corners, one child `data-testid="remote-selection"` with `data-player-id`,
  `data-colour` and `data-corner`, drawn as a plain right triangle in that corner
  whose fill is that player's colour (the computed `fill` of its `polygon` equal
  to the computed `background-color` of their `roster-colour`), with no outline
  and no text. Corners go by order of arrival on the cell, top-left, top-right,
  bottom-right, bottom-left; at most four players are drawn; the sizes, the
  arrival rules and the Accessibilité icons are spec 042's ("Other players on a
  cell"). (Note from the lead, 2026-10-22: refined by spec 042, the design's grid
  cells. This read "drawn as a dashed border (computed `border-style` `dashed`, at
  least 2 px wide) in that player's colour (computed `border-color` equal to the
  computed `background-color` of their `roster-colour`). With several, each is
  inset by a different amount (for example 3 px per rank in roster order), so all
  stay visible.")
- `data-tinted-by`: the ids of the other players whose selected word holds that
  cell (word of their selected cell in their direction, spec 007 rules), separated
  by one space, in roster order; `""` when none. A tinted cell that is not in my
  own selected word has a computed `background-color` different from an untinted,
  unselected letter cell; the tint is the player's colour at low opacity (the first
  in roster order when several). (Note from the lead, 2026-10-22: since spec 041
  AC-15, the tint is the player's colour at 16 % over white, not 28 %: for colour
  3 it is within 1 per channel of rgb(231, 223, 250).)

My own selection keeps the look of spec 007 (background fill, no dashed border;
note from the lead, 2026-10-22: since spec 041, a background of rgb(207, 221, 243)
and a 2 px solid navy outline inside the cell, where it was yellow with a 3 px
ink outline),
and the page never draws a `remote-selection` for `you`. (Note from the lead,
2026-10-22: with spec 042, my selection is the selected blue with a 2 px navy
border inside the cell, and never a triangle.)

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
| `vote_closed` | `vote` | `t("vote.result.<outcome>")` (Note from the lead, 2026-10-22: row added by spec 047, the design's room overlays, for the human's decision P6: a vote's result is a line in the stream; it names no player) |

Other events (`letter_changed`, `cell_locked`, `player_state_changed`,
`flag_changed` with `null`, `vote_opened`, chat, completion) add no item. The
nickname is the one known when the event is applied. (Note from the lead,
2026-10-22: refined by spec 047; "votes" became `vote_opened`. No criterion of this
spec changes: AC-5 sends no vote.)

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

### Client: feed height

(Note from the lead, 2026-10-15: this section is added. The review of spec 021
measured at 1280 by 720 that, with 1 or 2 lines shown, each new line made the feed
list about 15 px taller and moved the grid, and the clue text of its cells, down by
as much, because the list was as tall as its lines (review of spec 021).)

The feed list (the `ul` of "Client: feed scroll position") has a fixed height,
equal to its maximum, wherever its growth would move the grid. That height does not
depend on the number of items: it is the same with 0, 1, 2, 3 or 100 items. Items
beyond what it holds scroll (AC-7). The maximum is:

- on a roomy window (`window.innerHeight > 500` and `window.innerWidth > 480`),
  where the roster, the feed and the host panel are stacked above the grid: 3.6rem,
  about three lines of the feed's text, so that a fourth line makes the list scroll;
- on a small window (`window.innerHeight <= 500` or `window.innerWidth <= 480`):
  one line, 1.3rem (AC-6), in a row with the feed's heading, or on a low window
  beside the roster and the host panel.

The feed is never beside the grid: it is always above it. An empty or short feed
thus leaves empty room under its heading, on purpose: the grid does not move when a
line comes. (Note from the lead, 2026-10-15: added with this section (review of
spec 021).)

### Client: feed scroll position

(Note from the lead, 2026-10-14: added with AC-7 and AC-8. A new line used to
bring the feed list back to its newest item even when the player had scrolled up
to read older lines, with the arrow keys (spec 035 AC-12), the mouse or touch.
That pulled the text away from the reader. The feed's order does not change:
oldest first and the newest at the bottom (decision 4), and a list that nobody
scrolls still shows its newest item.)

Terms:

- The feed list is the `ul` element inside `activity-feed` that holds the
  `feed-item` elements (`[data-testid="activity-feed"] ul`). It scrolls vertically
  once its items do not fit, and on a small window it shows one line (AC-6).
  (Note from the lead, 2026-10-15: its height is fixed, whatever the number of
  items; see "Client: feed height" (review of spec 021).)
- Its distance to the end is `scrollHeight - clientHeight - scrollTop`, read from
  those properties of the list. The list is at its end while that distance is at
  most 1 px. A list that does not scroll is at its end. So the list starts at its
  end, and stays there while nobody scrolls it.

Rules:

- New line at the end (AC-7): when the page adds a `feed-item` (AC-5) and the list
  was at its end just before, the list is at its end again within 300 ms of the
  item showing, so the newest line is in view. Lines that come one right after
  another follow the same rule: if the list was at its end before the first, it is
  at its end within 300 ms after the last shows.
- New line while the player reads older lines (AC-7): when the page adds a
  `feed-item` and the list was not at its end just before, the page leaves the
  list where it is. Every item that stays in the list keeps its place in the
  window: the `top` of its bounding box moves by at most 1 px. While the feed
  holds fewer than 100 items, the new item goes below the others, and `scrollTop`
  keeps its value within 1 px. When the feed already holds 100 items, the new item
  also removes the oldest ("Feed length" in "Edge cases and errors"). `scrollTop`
  then goes down by the distance the other items moved up, so that they stay in
  place. If `scrollTop` is smaller than that distance, it becomes 0, and the items
  move up by the rest.
- No special case (AC-7): these two rules apply to every line, whatever it
  reports. A line about the player's own action (their check, their lock, their
  settings) does not bring the list to its end either.
- Layout change at the end (AC-8): when the list is at its end and its size or the
  height of its items changes for another reason than a new line (a resize or a
  rotation of the window, a change of the root font), the list is at its end again
  within 300 ms. When it is not at its end, the page does not scroll it then. The
  browser may still move it, for example to keep `scrollTop` within the new range.
- Only the position counts, not what put the list there: the arrow keys or
  `Page Up` on the focused list (spec 035 AC-12), the mouse wheel, the scrollbar,
  touch, or a script. Apart from these rules, the page never changes the list's
  scroll position.
- How the page keeps these rules (a `scroll` listener, a `ResizeObserver`, the
  browser's scroll anchoring and `overflow-anchor`, or its own script) is the
  implementer's choice, as long as they hold in Chromium, Firefox and WebKit.

### Test harness

As spec 011. Mocked-socket tests send events built with the `nock.protocol` models
(the wire examples of spec 039 with chosen seqs). Relay timing uses
`time.monotonic()` on the test side.

Feed scroll states (AC-7, AC-8). (Note from the lead, 2026-10-14: added.)

- Browser with mocked socket, desktop context (that viewport, no touch). The
  snapshot is AC-5's: FX-01, `seq` 5, `p1` (`you`, `Ana`, host) and `p2` (`Bob`).
  The window is 1280 by 720, where the feed list shows a few lines, or 360 by 740,
  where it shows one line (AC-6).
- A line event is a `check_result` by `p2` with scope `grid` and empty lists,
  with the `seq` given. Each one adds the line `Bob a vérifié la grille`.
- The feed list, its distance to the end and "at its end" are those of "Client:
  feed scroll position". "Once `room-page` has `data-seq` N" is spec 040's
  attribute.
- Settled: the test reads the list's `scrollTop` every 100 ms and goes on once two
  reads in a row are equal. It fails after 2 s.
- Scroll probe: a `requestAnimationFrame` loop, which the test starts in the page
  with `page.evaluate`, reads the list's `scrollTop` at every frame, from just
  before the test sends the event (or clicks) until 300 ms after `room-page` has
  that event's `data-seq`. "The probe stays put" means that every value it read is
  within 1 px of the `scrollTop` read just before it started. So a jump to the end
  and back also fails.
- Items in view: the `feed-item` elements whose bounding box overlaps the list's
  bounding box vertically by more than 1 px.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-3.3.1) (Python; WebSocket with a fake clock; browser with mocked socket) A roster lists each player with a colour and a state: active, idle after 2 minutes without input, or disconnected. Python: with `p1` whose `last_input_at` is `t`, `tick` at `t + 119.9` changes nothing and at `t + 120` gives `PlayerStateChanged(p1, idle)`; a `SelectCell` from `p1` at `t + 130` gives `PlayerStateChanged(p1, active)` then the selection; a `Ping` at `t + 130` does not. WebSocket: A and B join; after `advance(120)` B receives `PlayerStateChanged(<A>, idle)` (and A receives B's) within one second of real time; A's next `select_cell` makes B receive `PlayerStateChanged(<A>, active)` before the `selection_moved`. Browser: given a snapshot with `p1` (`you`, colour 0, active), `p2` (colour 1, idle) and `p3` (colour 2, disconnected), the roster shows three items in that order with `data-colour` 0, 1, 2, pairwise different `roster-colour` background colours, `data-state` `active`, `idle`, `disconnected`, and `roster-state` texts `fr.json["presence.active"]`, `fr.json["presence.idle"]`, `fr.json["presence.disconnected"]`; a `player_state_changed` for `p2` `active` updates its item.
- **AC-2** (AC-3.3.2) (WebSocket; browser with mocked socket) Another player's selected cell is outlined in their colour and their word lightly tinted, within 300 ms of their move. WebSocket: A and B join a FX-01 room; A sends 100 `select_cell` messages on random letter cells, each after B received the previous `selection_moved`; B receives each as `SelectionMoved(player_id=<A>, selection=...)` with the same values, A receives none, and the 95th percentile of the relay times is at most 100 ms; a `select_cell` on (0, 0) is answered `not_a_letter_cell` to A and nothing to B. Browser: given the page joined with `p1` (`you`) and `p2` (colour 3), within 300 ms of the mock sending `selection_moved` for `p2` on (2, 2) `across`, (2, 2) holds one `remote-selection` with `data-player-id="p2"`, `data-colour="3"` and `data-corner="top-left"`, whose `polygon` has a computed `fill` equal to `p2`'s `roster-colour` background colour (Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells; this read "whose computed `border-style` is `dashed` and `border-color` equals `p2`'s `roster-colour` background colour"); exactly (2, 1), (2, 2), (2, 3), (2, 4) have `data-tinted-by="p2"`, and (2, 1)'s background colour differs from that of (1, 1) (Note from the lead, 2026-10-22: since spec 041, the tint is the colour at 16 % over white); a `selection_moved` for `p2` with `null` removes them.
- **AC-3** (AC-3.3.3) (browser with mocked socket) When two players select the same cell, both outlines are visible. Given `p1` (`you`), `p2` (colour 1) and `p3` (colour 2), when the mock sends `selection_moved` for `p2` and for `p3`, both on (1, 1) (`p2` across, `p3` down), then (1, 1) holds two `remote-selection` elements with `data-player-id` `p2` and `p3`, both visible, `p2`'s with `data-corner="top-left"` and `p3`'s with `data-corner="top-right"`, with different bounding boxes and different `polygon` fill colours (Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells; this read "with different bounding boxes and different border colours"); (1, 1) has `data-tinted-by="p2 p3"`. When `p1` also taps (1, 1), the two outlines stay visible and the cell also shows `p1`'s own selection (spec 007 `data-selected="true"`).
- **AC-4** (AC-3.3.4) (browser with mocked socket) My own selection is styled differently from every other player's. Given `p1` (`you`) and `p2`, after `p1` taps (3, 1) and the mock sends `p2`'s selection on (2, 2): (3, 1) has `data-selected="true"` and no `remote-selection` child; no cell has a `remote-selection` with `data-player-id="p1"`; the computed `border-style` of (3, 1) and of its children is never `dashed`; and the background colour of (3, 1) differs from the background colour of (2, 2) and of the tinted (2, 3) (Note from the lead, 2026-10-22: since spec 041, (3, 1) has rgb(207, 221, 243), (2, 2) white and (2, 3) the 16 % tint, so the three still differ; (3, 1) has a 2 px solid navy outline inside the cell).
- **AC-5** (AC-3.3.5) (browser with mocked socket) An activity feed lists joins, departures, checks, reveals, flags and setting changes in the order they happened. Given the page joined at `seq` 5 with players `p1` (`you`, `Ana`) and `p2` (`Bob`), when the mock sends, with seqs 6 to 12: `player_joined` (`p3`, `Cy`), `check_result` (`p2`, scope word), `reveal_result` (`p3`, scope letter), `flag_changed` (`p2`, clue (0, 3, 0)), `settings_changed` (`p1`, help mode `vote`, budget 5 letters and 1 word, unlocked), `settings_changed` (`p1`, same values but `locked` true), `player_left` (`p3`, reason `removed`), then `activity-feed` holds 7 `feed-item` elements with `data-seq` 6 to 12 in that order and `data-kind` `player_joined`, `check`, `reveal`, `flag`, `settings_changed`, `room_locked`, `player_removed`, whose texts are, in order, `Cy a rejoint le salon`, `Bob a vérifié un mot`, `Cy a révélé une lettre`, `Bob bloque sur « Fatales à César »`, `Ana a modifié les réglages : aide par vote, 5 lettres et 1 mots à révéler`, `Ana a verrouillé le salon` and `Cy a été retiré du salon` (each built from `fr.json`). Sending those events out of order (seq 8 before 7) still lists them by seq.
- **AC-6** (new) (browser with mocked socket) The roster and the feed never take the grid's room. With a snapshot of 8 players and 100 feed items, at every window size of spec 006 AC-5, in desktop and touch contexts (touch with spec 009's on-screen keyboard), and after a tap on a cell, with the Salon closed and again with the Salon open on its Discussion tab: the `grid-viewport` is at least 100 px high, the page has no vertical or horizontal scroll, the grid fits the viewport at zoom 1, and the clue bar is fully inside the window above the keyboard (specs 006 AC-5 and AC-7, 009 AC-4); in the sheet layout, `grid-viewport` has the same box in both states (1 px). (Note from the lead, 2026-10-22: since spec 041, text is set in Source Sans 3 and controls without their own font take their parent's size and family; the room header's title, share and toolbar rows have explicit line heights so that the header keeps its 48 px, and the clue text has an explicit line height of about 1.42 em; the 100 px of the viewport at 568 by 320 still holds, and the test reads the page after `document.fonts.ready`.) (Note from the lead, 2026-10-22, second review of spec 041: the rows with an explicit line height are the title row, the status row, the share row and the toolbar row; `RoomPage.svelte` sets it on `.room-header h1`, `.room-header p`, `.share-panel` and `.room-toolbar`.) (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout; this read "On small windows the roster and the feed may be compact (for example one line each, the feed showing its newest item) as long as their content stays reachable." in place of the two Salon states.) Feed height: with the same snapshot of 8 players and no feed item, at 1280 by 720 and at each window size of spec 006 AC-5, in desktop and touch contexts and without a tap on a cell, the mock sends the line event of "Feed scroll states" (sent by a player of the snapshot) three times, one at a time with the next seq; with 0, 1, 2 and 3 items (once `room-page` has the `data-seq` of each), the bounding box of `grid-viewport` (x, y, width, height) is the same, with 1 px of tolerance; and the height of the feed list with 3 items is the one it has after 100 items (1 px tolerance). (Note from the lead, 2026-10-15: the feed height check is added to AC-6, keeping its other checks, for "Client: feed height" (review of spec 021).) (Note from the lead, 2026-10-22: refined by spec 043: the feed height check runs with the Salon open on its Discussion tab, where the feed list is the stream list.)
- **AC-7** (AC-3.3.5; new, from the lead's review of 2026-10-14) (browser with mocked socket) A new feed line brings the feed list to the newest line only when the list was already at its end; otherwise the player keeps their place. The rules are those of "Client: feed scroll position". The setup, "settled", the scroll probe and "items in view" are in "Feed scroll states" in "Test harness". The cases below run in this order on one page, at 1280 by 720 and again at 360 by 740, each from the state the case before it left. Wherever a case says that the list scrolls, or that it is or is not at its end before an event, the test first checks it from the list's measures and fails if it does not hold. (Note from the lead, 2026-10-14: added.)
  - Filling: the mock sends ten line events, `seq` 6 to 15, one right after another without waiting. Once `room-page` has `data-seq` 15, the list scrolls, and within 300 ms it is at its end.
  - At the end: the mock sends the line event with `seq` 16. Within 300 ms after `room-page` has `data-seq` 16, the list is at its end.
  - Scrolled up: the test sets the list's `scrollTop` to `Math.floor((scrollHeight - clientHeight) / 2)` with `page.evaluate` and waits until it is settled. The list is not at its end. The mock sends the line event with `seq` 17. The probe stays put, and the last `feed-item` has `data-seq` 17.
  - My own action: the list is still where the case before left it. The test clicks `lock-room` (spec 014). Once the page has sent `lock_room`, the mock answers with a `settings_changed` by `p1` that carries the snapshot's settings with `locked` true (`seq` 18), so the feed gets the line `Ana a verrouillé le salon`. The probe, started just before the click, stays put.
  - Back at the end: the test sets the list's `scrollTop` to its `scrollHeight` (the browser stops it at the end) and waits until it is settled. The list is at its end. The mock sends the line event with `seq` 19. Within 300 ms after `room-page` has `data-seq` 19, the list is at its end.
  - Within 1 px of the end: the test sets `scrollTop` to `scrollHeight - clientHeight - 1` and waits until it is settled. The distance to the end is at most 1, so the list is at its end. The mock sends the line event with `seq` 20. Within 300 ms after `room-page` has `data-seq` 20, the list is at its end, which it would not be if the page had left it where it was.
  - Full feed: the mock sends the line events with `seq` 21 to 105, one right after another. Once `room-page` has `data-seq` 105, the feed holds 100 items (`seq` 6 to 105), and within 300 ms the list is at its end. The test sets `scrollTop` to `Math.floor((scrollHeight - clientHeight) / 2)`, waits until it is settled, and notes the `data-seq` and the bounding box `top` of each item in view. The mock sends the line event with `seq` 106. 300 ms after `room-page` has `data-seq` 106, the first `feed-item` has `data-seq` 7 and the last has `data-seq` 106 (AC-5), and each noted item has its `top` within 1 px of the noted value.
- **AC-8** (new, from the lead's review of 2026-10-14) (browser with mocked socket) A feed list at its end stays at its end when the window or the root font changes, so the newest line stays in view. Setup: "Feed scroll states" in "Test harness", at 1280 by 720, with the ten line events of AC-7's "Filling" (`seq` 6 to 15) and the list at its end (the test checks it). The rules are those of "Client: feed scroll position". (Note from the lead, 2026-10-14: added with AC-7.)
  - Smaller window: the test calls `page.set_viewport_size` with 360 by 740. Once `window.innerWidth` reads 360, the list scrolls, and within 300 ms it is at its end.
  - Larger root font: the test then sets the root font to 20 px as spec 014's "Test harness" does: it sets `document.documentElement.style.fontSize` with `page.evaluate` and waits until the computed `font-size` of `html` reads `20px`. Within 300 ms after that, the list is at its end.
  - Larger window: the test calls `page.set_viewport_size` with 1280 by 720. Once `window.innerWidth` reads 1280, the list is at its end within 300 ms.

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
  colour (roster order); both outlines remain distinct. (Note from the lead,
  2026-10-22: with spec 042 the outlines are triangles in different corners.)
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
- Empty or short feed (AC-6): the list keeps the height of its maximum, so the
  first lines do not move the grid; the room under the heading stays empty until
  lines fill it. (Note from the lead, 2026-10-15: added (review of spec 021).)
- Plural (AC-5): the text uses the numbers as they are (`1 mots`); proper plural
  forms are left to a later wording pass.
- Text injection (AC-5): names and clue texts are inserted as text (spec 037 AC-4).
- Feed list that does not scroll (AC-7): it is at its end, so the line that first
  makes it scroll comes into view, and a list that nobody scrolls always shows its
  newest line. (Note from the lead, 2026-10-14.)
- Player scrolled up on a full feed (AC-7): each new line removes the oldest, and
  the lines in view stay in place until `scrollTop` reaches 0. From then on, each
  new line moves the items up by one. A player who stays there sees the oldest
  lines go, since the feed keeps 100 items. (Note from the lead, 2026-10-14.)
- Feed list with the focus (AC-7, spec 035 AC-12): a new line leaves the focus on
  the list, and the list keeps its place unless it was at its end. (Note from the
  lead, 2026-10-14.)
- Back at the end (AC-7): once the player scrolls the list back to within 1 px of
  its end, the next line brings it to its end again. Nothing else marks the
  change. (Note from the lead, 2026-10-14.)
- The player's own lines (AC-7): no special case. The player sees the result of
  their action where they made it (the lock button, the grid, the settings form),
  and a jump to the newest line would take their place away all the same
  (decisions). (Note from the lead, 2026-10-14.)
- Wheel, scrollbar and touch (AC-7): they move the list as the keys do, and the
  rules depend only on the position. The tests move the list with a script here
  and with the arrow keys in spec 035 AC-12, because Playwright cannot swipe in
  every engine. (Note from the lead, 2026-10-14.)
- Layout change while the player reads older lines (AC-8): the page does not
  scroll the list. The browser may move it, to keep `scrollTop` within the new
  range or by its own scroll anchoring. The list follows new lines again once it
  is at its end. (Note from the lead, 2026-10-14.)
- Rounding (AC-7, AC-8): `scrollHeight` and `clientHeight` are whole numbers,
  while `scrollTop` can have a fraction, so "at its end" allows 1 px. (Note from
  the lead, 2026-10-14.)

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Guest join: spec 012.
- Host controls (the actions behind the lock and settings items): spec 014.
- Feed history before my arrival (spec 034), chat in the feed (spec 022), letters in
  the feed.
- Cursor trails, typing indicators, avatars.
- Showing selections of disconnected players.
- A sign that new lines came in while the player reads older ones, or a control
  that jumps to the newest line (AC-7). The player scrolls back to the end with the
  keys, the wheel, the scrollbar or touch. (Note from the lead, 2026-10-14.)

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
   implementer's. (Note from the lead, 2026-10-22: replaced by the design the human
   validated on 2026-10-16, built by spec 042: a corner triangle per player, by
   order of arrival, at most four, a 16 % tint that each player can turn off, and
   the Accessibilité icons; the sizes are now the design's.)
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

Added after the review, decided by the lead on 2026-10-11 under the human's
instruction to take technical decisions:
- The roster and the feed must keep the layout guarantees of specs 006 and 009 with
  8 players and a full feed (AC-6). This also fixes the roster squeezing the grid
  on landscape phones, which predates this spec.
- A tick that disconnects a silent player clears their selection and relays the
  clearing to the others, never to the silent player.

Added on 2026-10-14, decided by the lead under the human's permission to refine
approved and done specs:
- Feed scroll position (AC-7). A new line used to bring the feed list back to its
  newest line even while the player was reading older lines, with the arrow keys
  (spec 035 AC-12), the mouse or touch. That pulled the text away from the reader:
  a usability problem, and the closest WCAG rule, 2.2.2 (Pause, Stop, Hide), asks
  that a reader can stop auto-updating content. Pick: a new line brings the list
  to its end only if the list was at its end, within 1 px, just before. Otherwise
  the page leaves the list where the player put it, and the lines in view keep
  their place, also when the 101st line removes the oldest. The feed's order
  (decision 4) does not change, and a list that nobody scrolls still shows its
  newest line.
- The player's own lines (AC-7). Options: bring the list to its end for a line
  about the player's own action, or treat it like any other line. Pick: like any
  other line. The spec had no such case, the player sees the result of the action
  where they made it, and a jump would still take their place away.
- Layout changes (AC-8). With the rule of AC-7 alone, a list at its end that a
  resize, a rotation or a new root font moves away from its end would stop
  following new lines, while before this change the next line brought it back.
  Pick: a list at its end stays at its end through such a change, within 300 ms,
  so the compact feed of AC-6 keeps showing its newest line.
- Tests (AC-7, AC-8). The measures are the list's `scrollTop`, `scrollHeight` and
  `clientHeight`, with 1 px of tolerance. A probe reads `scrollTop` at every frame,
  so that a jump to the end and back also fails. A script moves the list here, and
  stands for the wheel and touch. Spec 035 AC-12 checks the same rule after the
  arrow keys, because that needs the list to be a Tab stop in WebKit, which spec
  035 gives. AC-7 clicks spec 014's `lock-room`, which exists since spec 014 is
  done; decision 7's build order was for the first build of this spec.

Decided by the lead on 2026-10-15 after the review of spec 021, under the owner's
delegation of layout choices:
- Feed height (AC-6, "Client: feed height"). The feed list was as tall as its
  lines, so with 1 or 2 lines each new line moved the grid down by about 15 px,
  measured at 1280 by 720, and spec 021's rule on the clue text failed. Options:
  keep that and loosen spec 021's rule; reserve room for the first lines only;
  take the feed out of the flow (over the grid, with no height); or give the list
  a fixed height equal to its maximum. Pick: the fixed height, so that the grid
  never moves when a line comes, in any window, and the list still scrolls beyond
  its maximum (AC-7). Cost: on a roomy window the grid is about 40 px lower than
  before while the feed is empty or short. It was already that low with a full
  feed, which AC-6 measures, so its existing checks do not change. The small
  windows do not change, their list is already one line.

## Open questions

None.
