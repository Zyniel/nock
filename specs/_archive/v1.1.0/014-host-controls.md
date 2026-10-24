---
id: "014"
title: Host controls
status: done
---

# 014 - Host controls

Epic E3 Rooms and presence (US-3.4) · Release: MVP · Epic depends on: E2
The rooms engine and the fake-clock harness are defined in spec 011; joining, the
join order of refusals, the stored identity and the roster in spec 012; the feed in
spec 013; disconnection and time-out in spec 017. The messages are those of spec
039.

(Note from the lead, 2026-10-22: refined by spec 043, the design's room layout
(`_design.md` section 8). `remove-player` sits in each other player's row of the
Salon's Joueurs tab, beside spec 022's `mute-player`, and always reads
`t("host.remove")`; the host panel becomes the room sheet `host-settings`, opened
from the Menu's « Réglages de l'hôte », with `lock-room` drawn as a switch (its
label `t("host.lock")` fixed, `host.unlock` removed), `help-mode-select` a
fieldset of three radios drawn as a segmented control, and the two number inputs;
`settings.heading` reads « Réglages de l'hôte ». `host-panel`, `host-panel-more`,
the compact button (`host.remove_short`) and the low layout of "Small windows" go,
since nothing scrolls sideways any more. "Client", "Small windows", AC-1's browser
part and AC-7 to AC-10 change, so the test-writer updates their tests before the
implementer runs. The server rules and the other criteria do not change; the
tests that click `lock-room` or `settings-save` open the sheet first (spec 043's
"Test harness").)

## Goal

As a host, I want to manage who is in the room, so that an unwanted visitor can't spoil the game.

A room is one grid shared by up to 8 players and reached by a link.

## Public interface

### Server rules (`nock.room`)

Host actions are `remove_player`, `lock_room` and `change_settings` (and
`mute_player`, whose effect on chat is spec 022's). From a player who is not host,
each is refused with `ErrorMessage(code=NOT_HOST)` and changes nothing.

`RemovePlayer(player_id=t)` from host `h`:

- `t` is not a player of the room, or `t == h`: refused,
  `ErrorMessage(code=INVALID_TARGET)`.
- Otherwise, with `seq = state.seq + 1`: `t`'s resume token is added to
  `removed_tokens`; `t` is removed from `players` (seat, colour and nickname
  freed; letters keep their author id); one entry
  `PlayerLeft(seq, player_id=t, reason=removed)`; and
  `disconnects = (Disconnect(player_id=t, close_code=1000, error=ErrorMessage(code=REMOVED)),)`
  when `t` has an open connection (the hub skips it otherwise).

Join step 1 of spec 012 is built here: a join whose `resume_token` is in
`removed_tokens` is refused with `REMOVED` and `close_sender`.

`LockRoom(locked=x)` from the host: if `x == settings.locked`, nothing happens (no
entry, no reply). Otherwise `settings.locked = x` and one entry
`SettingsChanged(seq, player_id=h, settings=<new settings>, reveal_budget=state.reveal_budget)`.

Join step 3 of spec 012 is built here: while `settings.locked`, a join that is not
a resume (step 2) is refused with `ROOM_LOCKED` and `close_sender`. Players of the
room resume as usual; a past player of spec 032, though a member of the room there,
is refused like a newcomer, since a seat back is not a resume. (Note from the lead,
2026-10-16: the sentence after `close_sender` used to read "Members resume as
usual." Spec 032 counts past players among a room's members, and they do not
resume; the rule is unchanged.)

`ChangeSettings(help_mode, reveal_budget)` from the host: if both equal the
current `settings.help_mode` and `settings.reveal_budget`, nothing happens.
Otherwise `settings.help_mode` and `settings.reveal_budget` take the new values
(`locked` unchanged); the remaining budget becomes, for letters and for words
separately, `max(0, new_allowance - used)` where `used` is the number of reveals
of that kind the room has accepted so far (`state.reveals_used`, spec 024's
"Reveals used and allowance changes"). (Note from the lead, 2026-10-15: `used`
was `old_allowance - old_remaining`, which loses reveals once the remaining count
was cut at 0: 3 letter reveals with the allowance 5, then 1, then 5 again gave 4
letters instead of 2. Every example of this spec still holds, since none
changes the allowance after a reveal (review of spec 024).) One entry
`SettingsChanged(...)` with the new settings and remaining budget. What the help
mode and budget do is specs 023 to 025's.

`MutePlayer(player_id=t, muted=x)` from the host: `t` unknown: `INVALID_TARGET`;
`x` equal to `t.muted`: nothing; otherwise `t.muted = x` and one entry
`PlayerMuted(seq, player_id=t, muted=x)`. (Its effect on chat is spec 022's.)

Hand-over, added to `tick(state, now, config)` (after spec 013's idle step and
spec 017's steps): when the host is `disconnected` and
`now - host.disconnected_at > config.host_handover_seconds` (60), the host role
moves to the player with the smallest `joined_seq` among the players whose state
is not `disconnected`: `is_host` False on the old host, True on the new one, one
entry `HostChanged(seq, player_id=<new host>)`. If every other player is
disconnected, nothing happens and the rule is tried again at each tick.

When the host leaves the room (spec 017 time-out; a host cannot be removed), the
role moves at once, after the `player_left` entry, to the remaining player with the
smallest `joined_seq` among those not `disconnected`, or, if all remaining players
are disconnected, among all of them, with one `HostChanged` entry. If nobody is
left, the room has no host and the next joiner becomes host (spec 012).

A host who comes back after the hand-over is an ordinary player.

### Protocol (spec 039)

`ErrorCode.INVALID_TARGET = "invalid_target"` is part of spec 039 (added when
spec 039 was reopened on 2026-10-10, its decision 19); this spec gives it its
meaning (removing or muting an unknown player, removing oneself). No other
protocol change.

### Client

The kept snapshot is updated by `settings_changed` (`settings`, `reveal_budget`),
`host_changed` (`is_host` moves to that player) and `player_muted` (`muted`).

Roster (spec 012) additions, in each `roster-player`:

- `data-host`: `true` on the host's item, else `false`; the host's item shows
  `t("roster.host")`.
- When `you` is host, each other player's item holds a button
  `data-testid="remove-player"` with the text `t("host.remove")`, or
  `t("host.remove_short")` while the roster list is narrow (see "Small windows"
  below and AC-9), and, in both forms, the `aria-label`
  `t("host.remove_label", {name})`. Clicking it sends
  `{"type": "remove_player", "player_id": <that id>}` at once. (Note from the
  lead, 2026-10-14: the compact text was added.)

Host panel `data-testid="host-panel"`, shown only while `you` is host:

- `data-testid="lock-room"`: a button with `aria-pressed` equal to
  `settings.locked` (`true` / `false`) and the text `t("host.lock")` or
  `t("host.unlock")`; clicking it sends `{"type": "lock_room", "locked": <not current>}`.
- `data-testid="settings-form"`: a select `data-testid="help-mode-select"`
  (labelled `t("settings.help_mode_label")`, options `free`, `vote`, `none` with the
  texts `t("settings.help_mode.<mode>")` of spec 013), number inputs
  `data-testid="reveal-letters-input"` and `data-testid="reveal-words-input"`
  (labelled `t("settings.reveal_letters_label")` and
  `t("settings.reveal_words_label")`, minimum 0, maximum 99, whole numbers), and a
  submit button `data-testid="settings-save"` with `t("settings.save")`. The form
  shows the current settings; submitting sends
  `{"type": "change_settings", "help_mode": ..., "reveal_budget": {"letters": ..., "words": ...}}`.
- `data-testid="host-panel-more"`: the edge fade of AC-7, inside `host-panel`, with
  `aria-hidden="true"` and no text. It is visible at the panel's right edge while
  panel content is hidden past that edge. It is not visible (computed `visibility`
  `hidden` or `display` `none`) while a host panel control has the focus from the
  keyboard (AC-7). (Note from the lead, 2026-10-13: this element was already in the
  code and the tests, and is now written here.)

Small windows (Note from the lead, 2026-10-14: added with AC-9 and AC-10, from
measurements on Chromium with 8 players):

- The roster list is the `ul` element inside `roster` (`[data-testid="roster"] ul`)
  that holds the `roster-player` items. `w` is its `clientWidth`, and `r` is the
  computed `font-size` of the `html` element in CSS px (1rem).
- Compact remove button (AC-9): while `w < 4.5 × r`, every `remove-player` holds
  the text `t("host.remove_short")` in place of `t("host.remove")`. That text is
  the button's content in the DOM (its `textContent`), not CSS generated content
  or an image. These stay the same in both forms: the `aria-label`, the 24 by 24
  CSS px minimum (AC-7), the whole-box tap target (AC-8), and spec 035's visible
  focus and 4.5:1 contrast. All buttons have the same form at any time. The form
  follows `w` and `r` when they change (resize, rotation, root font).
- Low layout: the room page in a window 500 CSS px high or less
  (`window.innerHeight <= 500`). There `roster`, `activity-feed` and `host-panel`
  (when shown) sit side by side in one row, in that order.
- Minimum list width (AC-10): in the low layout, while the roster holds at least
  one `remove-player`, `w >= button.offsetWidth + 3` for every remove button: one
  button plus the 3 px of room after the last item. This holds in any window from
  300 px wide and with any root font from 12 to 24 px. The roster takes that width
  from `activity-feed` alone. `host-panel` keeps at least a third of the three
  boxes' total width and keeps scrolling sideways (AC-7). The feed's heading and
  line stay inside the feed's box: they are cut or end with an ellipsis, and may
  shrink to no width at all. Nothing overflows the page horizontally (spec 006
  AC-5).

Refused or removed:

- An `error` with code `room_locked` (on join) sets `data-status="locked"`; with
  code `removed` (on join, or during the game) sets `data-status="removed"`. Both are
  final (no form, no reconnection, spec 017). `room-status` shows
  `t("room.status.locked")` or `t("room.status.removed")`.
- On `removed`, the stored identity of the room (spec 012) is kept, so a reload
  sends the same token and is refused again.

New `fr.json` keys:

| Key | Value |
| --- | --- |
| `roster.host` | `hôte` |
| `host.remove` | `Retirer` |
| `host.remove_label` | `Retirer {name} du salon` |
| `host.remove_short` | `✕` |
| `host.lock` | `Verrouiller le salon` |
| `host.unlock` | `Déverrouiller le salon` |
| `settings.heading` | `Réglages` |
| `settings.help_mode_label` | `Aide` |
| `settings.reveal_letters_label` | `Lettres à révéler` |
| `settings.reveal_words_label` | `Mots à révéler` |
| `settings.save` | `Enregistrer` |
| `room.status.locked` | `Ce salon est verrouillé.` |
| `room.status.removed` | `Vous avez été retiré de ce salon.` |

(Note from the lead, 2026-10-14: `host.remove_short` was added for the compact
remove button of AC-9. Its value is the single character U+2715 (MULTIPLICATION
X). Spec 035 AC-9 needs every visible string to come from `fr.json`, so the sign
is not written in the markup. The key belongs to this spec, and spec 035's list of
keys does not change.)

The feed lines for these events (`room_locked`, `room_unlocked`,
`settings_changed`, `player_removed`, `host_changed`) are spec 013's.

### Test harness

As spec 011. Browser criteria with two players use two browser contexts on the live
server (two "browsers": separate `localStorage`), each through `enter_room`.

Small windows (AC-8 to AC-10). (Note from the lead, 2026-10-14: added.)

- Narrow and low windows: 300x480, 320x480, 360x500, 400x480 and 480x500 at root
  fonts of 16 and 20 px, and 300x480 at root fonts of 12 and 24 px. Each runs in a
  desktop context (that viewport, no touch) and a touch context, as AC-7 and AC-8
  already do. The touch context has that viewport, `has_touch=True`,
  `device_scale_factor=2`, and `is_mobile=True` except under Firefox. Under Firefox
  and WebKit it also has spec 009's `(pointer: coarse)` init script. The mocked
  snapshot is AC-8's: FX-01, `you` host, 8 players, so 7 `remove-player` buttons.
- Root font: 16 px is the browser default, with nothing added. For 12, 20 or 24 px,
  the test sets `document.documentElement.style.fontSize` to that size, with
  `page.evaluate` once the roster is shown or earlier from an init script. Before
  measuring, it waits until `getComputedStyle(document.documentElement).fontSize`
  reads that size and two animation frames have passed. A check of a button's text
  may poll for up to 1 s.
- Scans (AC-9): the contrast scan and the language scan of spec 035's "Test
  harness", run on the elements that AC-9 names.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-3.4.1) (Python; WebSocket; browser with live server) The host can remove a player, who then cannot rejoin from the same browser. Python: `handle_message` with `RemovePlayer(player_id="p2")` from host `p1` gives one entry `PlayerLeft(player_id="p2", reason="removed")`, `p2` gone from `players`, `p2`'s token in `removed_tokens`, and a `Disconnect` for `p2` with close code 1000 and error code `removed`; the same from `p2` gives `not_host`; `RemovePlayer(player_id="p1")` from `p1` and `RemovePlayer(player_id="zz")` give `invalid_target`; then `join_room` with `p2`'s old token gives `removed` and `close_sender`, and `join_room` without a token gives a new player. WebSocket: host A, players B and C; A removes B; A and C receive `PlayerLeft(<B>, removed)`; B receives `error` `removed` then a close with code 1000; a new socket joining with B's token receives `error` `removed` then a close; `room_state` holds A and C. Browser: Ana (host, context 1) and Bob (context 2) join; Ana clicks `remove-player` on Bob's item; Bob's page reaches `data-status="removed"` showing `fr.json["room.status.removed"]` and Ana's roster holds 1 player; Bob's page reloaded reaches `data-status="removed"` again without showing `nickname-form`. Before the removal, Bob's own page (not host) shows no `remove-player` button, no `host-settings-open` and no `host-settings`. (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout; this read "and no `host-panel`".)
- **AC-2** (AC-3.4.2) (WebSocket; browser with live server) The host can lock the room; new joiners then see "room locked". WebSocket: host A and player B join; A sends `lock_room` `true`; A and B receive `SettingsChanged` with `settings.locked` true and `player_id` A; a new socket without a token gets `error` `room_locked` then a close with code 1000, and the room keeps 2 players; B closes its socket and joins again with its token: accepted (`Snapshot`); a second `lock_room` `true` produces no event; `lock_room` `false` from B gets `not_host`; from A it unlocks, and a new socket then joins. Browser: Ana (host) clicks `lock-room`, which then has `aria-pressed="true"`; a second context opening the room and submitting `Bob` reaches `data-status="locked"` showing `fr.json["room.status.locked"]`.
- **AC-3** (AC-3.4.3) (Python; WebSocket with a fake clock) If the host is disconnected for more than 60 seconds, the longest-present player becomes host. Python: host `p1` (joined first) disconnected at `t`, `p2` (joined second, active), `p3` (joined third, idle): `tick` at `t + 60` changes no host; at `t + 60.5` gives `HostChanged(player_id="p2")` with `p2.is_host` True and `p1.is_host` False; with `p2` also disconnected, the host becomes `p3`; with every other player disconnected, no `host_changed` and `p1` stays host; when `p1` then reconnects after the hand-over, `p1.is_host` stays False. WebSocket: A (host), B, C join in that order; A's socket closes; after `advance(59)` and a tick, nobody has received `host_changed`; after `advance(2)`, B and C receive `HostChanged(<B>)` within one second of real time, and B's `remove_player` on C is then accepted while A's resumed `lock_room` gets `not_host`.
- **AC-4** (AC-3.4.4) (WebSocket; browser with live server) A change of room settings is announced to all players in the activity feed. WebSocket: host A and player B; A sends `change_settings` with help mode `vote` and budget 3 letters, 0 words; A and B receive `SettingsChanged(player_id=<A>, settings=RoomSettings(help_mode="vote", reveal_budget=RevealBudget(letters=3, words=0), locked=False), reveal_budget=RevealBudget(letters=3, words=0))`; the same message again produces no event; B's `change_settings` gets `not_host`. Browser: Ana (host) and Bob join; Ana sets `help-mode-select` to `vote`, `reveal-letters-input` to `3`, `reveal-words-input` to `0` and clicks `settings-save`; Bob's `activity-feed` gets a `feed-item` with `data-kind="settings_changed"` and the text `Ana a modifié les réglages : aide par vote, 3 lettres et 0 mots à révéler`; Ana's own feed gets the same line.
- **AC-5** (new) (Python; WebSocket) A removed player can do nothing more. Any message from a `player_id` that is not in the room's players (removed, timed out or unknown) is refused with `not_joined` and changes nothing: no entry, no broadcast, no change to any cell. In particular, when the host removes B and B's socket sends 40 `edit_letter` frames right after, none is committed or broadcast and no cell takes B as author; the hub stops routing B's connections to the room in the same step as the removal.
- **AC-6** (new) (Python; WebSocket) The host can mute a player's chat (the effect on chat belongs to spec 022). `mute_player` from a non-host is refused with `not_host`; for the host's own id or an unknown player with `invalid_target`; when the target's `muted` already has the requested value, nothing happens; otherwise the target's `muted` is set and one `PlayerMuted` entry is written and broadcast. The flag survives a restart (spec 018 replay).
- **AC-7** (new) (browser with mocked socket) The host controls stay usable on small screens. At every window size of spec 006 AC-5, in desktop and touch contexts, with `you` host among 8 players and the Salon on its Joueurs tab (spec 043's `show_tab`): each `remove-player` and each `mute-player` is at least 24 by 24 CSS pixels and, after `scrollIntoView({block: "nearest", inline: "nearest"})`, lies inside the Salon's box (1 px), while spec 013 AC-6's layout guarantees still hold. After `open_host_settings` (spec 043), `host-settings` lies inside the window (1 px), and each of `lock-room`, the labels of the three `help-mode-option` radios, `reveal-letters-input`, `reveal-words-input` and `settings-save` is at least 24 px high and, after `scrollIntoView({block: "nearest"})`, `elementFromPoint` at its centre returns it or one of its descendants. Keyboard only, in the desktop context at 320 by 568 and 1280 by 720, with the sheet opened from the keyboard (`tab_to` `menu-button`, `Enter`, `Tab` to `host-settings-open`, `Enter`): `Tab` reaches `lock-room`, a `help-mode-option`, `reveal-letters-input`, `reveal-words-input` and `settings-save` in this order, each with spec 035 AC-2's outline, whose box lies inside the dialog's box (1 px). (Note from the lead, 2026-10-22: since spec 041, the page is set in Source Sans 3 and a `button`, `input`, `select` or `textarea` that sets no font takes its parent's size and family, so the controls are wider and taller than before; the sizes of this criterion are measured after `document.fonts.ready`, and the focus ring is 2 px solid navy.) (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout. The host panel, which scrolled sideways with the edge fade `host-panel-more`, is now the room sheet `host-settings`. This criterion checked the 24 px remove buttons, the fade shown while panel content was hidden past the right edge, the fade hidden during a keyboard focus and kept after a pointer focus on `lock-room` at 320 by 568, and where the focus goes after that click in each engine (notes of 2026-10-13 and 2026-10-15); with nothing scrolling sideways, only the 24 px rule and the reach of each control remain, and the sheet's controls join them.)
- **AC-8** (new, from the review of 2026-10-13) (browser with mocked socket) The whole box of each remove button (`Retirer`, AC-9) can be tapped. At every window size of spec 006 AC-5, in desktop and touch contexts, with `you` host and at least two other players and the Salon on its Joueurs tab (spec 043's `show_tab`), the test first scrolls each `remove-player` into view (`scrollIntoView({block: "nearest", inline: "nearest"})`). Then, for the centre of every whole CSS pixel inside the button's bounding box (`x = k + 0.5` for each integer `k` with `left <= k` and `k + 1 <= right`, and the same for `y`), `document.elementFromPoint(x, y)` returns the button or one of its descendants. The same holds for each `mute-player` (spec 022). A button that sticks out of the Joueurs panel, which scrolls vertically when its rows are higher than it, fails, because the panel clips the part outside it. (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout; this read "(`Retirer` or `✕`, AC-9)", had no Salon step and no `mute-player`, and said "This includes 320 by 568, 568 by 320, 360 by 740 and 740 by 360, where the roster is one line that scrolls sideways. A button that sticks out of the scrolling roster list (for example with a negative `margin-block`) fails, because the list clips the part outside it.") (Note from the lead, 2026-10-13: added because `.remove-player` used `margin-block: -3px`. On phones the 24 px button stuck 2 px out of the list on each side, and only about 20 px of its height could be tapped.) The same check also runs at every narrow and low window of "Test harness", at each of its root fonts, in desktop and touch contexts. There the buttons follow AC-9. (Note from the lead, 2026-10-22: refined by spec 043; this ended "and the list keeps the minimum of AC-10".) (Note from the lead, 2026-10-14: these windows were added, and the first sentence now names both forms of the button. With a 16 px root font the list was 24.7 px wide at 300x480, 31.4 px at 320x480 and 44.7 px at 360x500. That is narrower than the 49.6 px "Retirer" button, so no scrolling could show the button whole, and no test covered those windows.) (Note from the lead, 2026-10-22: since spec 041, the widths quoted here and in AC-9 and AC-10 are those of the system font; with Source Sans 3 and the form-control font rule they are measured again after `document.fonts.ready`, and the rule of each criterion applies to the measured values.)
- **AC-9** (new, from the lead's measurements of 2026-10-14; refined by spec 043) (browser with mocked socket; static) A remove button always reads « Retirer » and stays inside the Joueurs tab, whatever the window and the root font. Setup: FX-01, `you` host and 8 players (7 `remove-player` buttons), the Salon on its Joueurs tab (spec 043's `show_tab`). (Note from the lead, 2026-10-22: since spec 041, the widths are measured in Source Sans 3 after `document.fonts.ready`.) (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout. This criterion read "A remove button shows a compact `✕` while the roster list is narrower than 4.5rem" and checked the compact text against the roster list's width, its named results, its live changes and `fr.json["host.remove_short"]`; the Joueurs rows of spec 043 have room for « Retirer » at every window, so the compact form goes.)
  - Rule: at every narrow and low window of "Test harness" at each of its root fonts, and at every window size of spec 006 AC-5, in desktop and touch contexts, every `remove-player` has the text (`textContent`, trimmed) `fr.json["host.remove"]` and the `aria-label` `fr.json["host.remove_label"]` with `{name}` replaced by that player's nickname; `page.get_by_role("button", name=<that label>, exact=True)` resolves to exactly that button; its bounding box is at least 24 by 24 CSS px and, after `scrollIntoView({block: "nearest", inline: "nearest"})`, lies inside the box of its `roster-player` row and of `salon` horizontally (1 px); and the Joueurs panel has no horizontal scroll (`scrollWidth <= clientWidth + 1`).
  - Focus, desktop context, keyboard only after the setup (`page.keyboard`, no click or tap), at 300x480 and 360x500 with root fonts of 16 and 20 px. With the focus on `salon-tab-players` (`focus()` from `page.evaluate`, setup), the test presses `Tab` until the first `remove-player` has the focus (at most 60 presses), then presses `Tab` until each of the seven has had it. Each, while focused, has a computed outline that meets spec 035 AC-2 (style neither `none` nor `auto`, width at least 2 px, a colour with contrast of at least 3:1 against white; Note from the lead, 2026-10-22: since spec 041, the outline is 2 px solid navy, 13.26:1 against white), and AC-8's pixel check finds no miss on it without the test's `scrollIntoView` step: the browser scrolls the focused button whole into the Joueurs panel.
  - Scans, desktop context, 300x480, 16 px root font. Spec 035's contrast scan, run on the seven `remove-player` elements, finds none below 4.5:1. Spec 035's language scan accepts their text and their `aria-label` values.
  - Static: `fr.json` holds no key `host.remove_short` and no key `host.unlock`.
- **AC-10** (new, from the lead's measurements of 2026-10-14; refined by spec 043) (browser with mocked socket) The host's settings sheet fits narrow and low windows and large root fonts. Setup as AC-9, then `open_host_settings` (spec 043), at every narrow and low window of "Test harness" at each of its root fonts, in desktop and touch contexts: `host-settings` lies inside the window (left and top at least 0, right at most `window.innerWidth`, bottom at most `window.innerHeight`, 1 px tolerance); it has no horizontal scroll (`scrollWidth <= clientWidth + 1`) and the page has none (`document.documentElement.scrollWidth <= window.innerWidth`); each control of AC-7, after `scrollIntoView({block: "nearest"})`, lies inside the dialog's box (1 px) and `elementFromPoint` at its centre returns it or one of its descendants; the two number fields keep their 64 px width. (Note from the lead, 2026-10-22: refined by spec 043, the design's room layout. This criterion read "In the low layout, the roster list keeps room for one whole remove button, and the activity feed gives up that width" and checked the row of `roster`, `activity-feed` and `host-panel` on windows at most 500 px high, its minimum list width, the host panel's share and the boxes' contents; that row is gone, and the settings it held are the sheet checked here.)

## Edge cases and errors

Note from the lead (2026-10-11, from the spec 017 review): after `room_locked`
or `removed` during a reconnection, spec 017 ends the attempts but the page
stays on `reconnecting` with the banner. This spec must give those two cases
their final status and text, and hide the banner.

- Removing a disconnected player (AC-1): allowed; their token is banned and their
  seat freed; no socket to close.
- Removed then another browser (AC-1): a join with no token, or a different token,
  is a new player (guests only, spec 012); this is the limit of "the same browser".
- Removal and letters (AC-1): the removed player's letters stay, with their author
  id; nothing is erased.
- Removing during a vote or with flags (AC-1): their effects are specs 021 and 025's.
- Locked room and members (AC-2): a player of the room who is disconnected within
  spec 017's 5-minute window resumes. A player who timed out is a past player of
  spec 032, still a member of the room in that spec's sense, but their join is not
  a resume: a locked room refuses it with `room_locked`, as it refuses a newcomer,
  and the same token seats them back once the room is unlocked (spec 012 step 4a).
  (Note from the lead, 2026-10-16: this item used to read "disconnected members
  within the 5-minute window resume; a member who timed out (spec 017) is no longer
  a member and is refused". Spec 032 counts past players among a room's members;
  the refusal is unchanged.)
- Locked and full (AC-2): `room_locked` is answered before `room_full` (spec 012
  order).
- Unlock (AC-2): `lock_room` `false` announces `settings_changed` with
  `locked` false (feed line `room_unlocked`, spec 013).
- Hand-over threshold (AC-3): strictly more than 60 seconds; checked at each tick
  (every second), so it happens between 60 and 61 seconds.
- Candidates (AC-3): `idle` players are candidates; `disconnected` ones are not.
  Longest-present means the smallest `joined_seq`; a resume does not change it.
- Several hand-overs (AC-3): if the new host also disconnects for more than 60
  seconds, the role moves again by the same rule.
- Host leaves for good (AC-3): when the host times out (spec 017), the role moves at
  once to the longest-present remaining player, even a disconnected one if nobody
  else remains connected (the role must not stay with a player who left).
- Settings values (AC-4): `reveal_budget` values are any count `>= 0` (spec 039);
  the form limits them to 0 to 99. Lowering the allowance below what was used gives
  a remaining budget of 0, never negative.
- `change_settings` does not change `locked` (AC-4), and `lock_room` does not
  change the help mode or budget (AC-2).
- Non-host UI (AC-1, AC-2, AC-4): a non-host sees no `host-panel` and no
  `remove-player`; a forged message gets `not_host`.
- Removal confirmation (AC-1): none; the button acts at once (decision 4).
- Keyboard then pointer in the host panel (AC-7): a pointer press anywhere ends the
  keyboard-focus exception, so the fade shows again if content is still hidden
  past the right edge. A focus that leaves the panel ends it too. (Note from the
  lead, 2026-10-13.)
- Remove button and the roster row height (AC-8): a target taller than the
  roster's one-line row must make the row or the list taller. It must not overflow
  the scrolling list. Spec 013 AC-6's layout guarantees (AC-7) still apply. (Note
  from the lead, 2026-10-13.)
- Switch threshold (AC-9): `clientWidth` is a whole number of pixels, and engines
  lay out fractions differently. So within 1 px of `4.5 × r` either form passes.
  The seven buttons never mix forms. (Note from the lead, 2026-10-14.)
- Live changes (AC-9, AC-10): a resize, a rotation or a change of the root font
  applies both rules again within 1 s, without a reload. (Note from the lead,
  2026-10-14.)
- Root font source (AC-9, AC-10): the tests change the root font with a style on
  `html`. A media query measures `em` and `rem` against the browser's default font
  size and ignores that style, so a media query alone cannot implement the rules.
  `r` is the computed `font-size` of `html`, which a browser font setting changes
  too. (Note from the lead, 2026-10-14.)
- Host alone, or not host (AC-10): with no `remove-player` in the roster, the
  minimum does not apply. (Note from the lead, 2026-10-14.)
- Scroll padding at the minimum width (AC-8, AC-10): AC-8's step and the page's
  own keyboard-focus scrolling both call `scrollIntoView` with
  `inline: "nearest"`. That call keeps a target clear of the list's inline scroll
  padding, which is 8 px in today's code. When a button is wider than the list
  minus twice that padding, the call lines the button up 8 px inside one edge of
  the list. The button then stays whole only if the list is at least 8 px wider
  than the button. For example, at 320x480 with a 16 px root font, a 24 px compact
  button in the 31.4 px list would stick 0.6 px out of it. At the minimum of AC-10
  the list is only 3 px wider than the button. The implementer must keep each
  button whole after that call, with a smaller inline scroll padding or a wider
  list. (Note from the lead, 2026-10-14: worked out from today's CSS and the
  CSSOM View "nearest" rule, not measured.)
- Feed squeezed (AC-10): at 300 px wide with a root font of 20 px or more, the feed
  can end up narrower than its heading, with no room for its line. That is
  accepted. The heading and line are cut inside the feed's box, never painted over
  the roster or the host panel. At the sizes of spec 006 AC-5 the roster never
  needs extra width (its narrowest list there is 114 px). So spec 013 AC-6's
  compact feed does not change at those sizes. (Note from the lead, 2026-10-14.)
- Text width across fonts (AC-9): "Retirer" is 49.6 px wide at a 16 px root font in
  the lead's Chromium. It is about 14% wider in DejaVu Sans, a common Linux
  fallback for `system-ui`, and the 4.5rem threshold leaves room for that
  (decisions). The `✕` may also come from a fallback font. Its button keeps the
  24 by 24 minimum either way. (Note from the lead, 2026-10-14.)

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Guest join: spec 012.
- Presence and the feed's display: spec 013.
- Handing the host role over by hand, co-hosts.
- Banning by address or across browsers; un-banning a removed player.
- The effect of help mode and budget on checks and reveals (specs 023 to 025), and
  of muting on chat (spec 022, which owns the mute button).
- Windows narrower than 300 px, and root fonts below 12 px or above 24 px (AC-10).
  (Note from the lead, 2026-10-14.)
- A short form for any other text: roster states, `hôte`, `(vous)`, the host
  panel's controls. Only the remove button has one (AC-9). (Note from the lead,
  2026-10-14.)
- Spec 013 AC-6's guarantees on the grid's height and the clue bar at the narrow
  and low windows of AC-10. They stay tested at the sizes of spec 006 AC-5. (Note
  from the lead, 2026-10-14.)

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written
(item 1 settled by reopening spec 039). Each one is already part of the spec
above.

1. Protocol: an error code for a bad target. Options: `invalid_message` (which
   spec 039 reserves for parse failures) or a new `invalid_target`. Pick: add
   `INVALID_TARGET`, used for removing or muting an unknown player and for
   removing oneself. Decision (human): spec 039 was reopened to add it (spec 039
   decision 19), so it is no longer a change this spec makes.
2. "Cannot rejoin from the same browser". Guests have no account. Options: ban the
   resume token, ban an extra browser id, or ban the address. Pick: ban the resume
   token, which the browser keeps in `localStorage` and always sends; clearing site
   data or another browser gets in as a new player. Not covered: a determined
   visitor.
3. Hand-over candidates. Options: longest-present among connected players (active
   or idle), or among all. Pick: connected players only, so the role never goes to
   someone who is also away; if nobody is connected, the host stays and the rule
   is retried each second.
4. Removal confirmation. Options: act at once, or a confirmation step. Pick: at once
   (a removed friend can be let back only from another browser, which is the cost).
5. Unchanged settings or lock. Pick: no event and no reply, so the feed never shows
   a change that did not happen.
6. Remaining budget after a change. Pick: new allowance minus what was already used,
   never below 0.
7. Settings form bounds. Pick: 0 to 99 letters and words in the form; the server
   accepts any count `>= 0` (spec 039).
8. "Announced to all players in the activity feed" (AC-4). Pick: the
   `settings_changed` event reaches every joined player, the changer included, and
   spec 013's feed shows the line; the browser check is made on both pages.

Added after the review, decided by the lead on 2026-10-11 under the human's
instruction to take technical decisions:
- A removed or unknown player's messages are refused (AC-5); found by the review as
  a reproduced hole.
- The `mute_player` server rule declared here is built and tested here (AC-6);
  spec 022 keeps the effect on chat and the button.
- Remove buttons meet a 24 px target size and the host panel shows when it scrolls
  (AC-7).

Added on 2026-10-13. The human allowed agents to refine approved and done specs,
and these are the lead's decisions:
- The edge fade is hidden while a host panel control has keyboard focus, so it
  never covers the focused control and its outline. A pointer focus keeps the fade:
  the user has just touched the control, so it does not need to be uncovered (AC-7).
  After a click or tap the fade is visible whether or not the control keeps the
  focus. Chromium, Firefox and WebKit on Linux keep the focus on the clicked button.
  WebKit on Windows and macOS does not, which is that platform's convention, and the
  page does not move the focus back (AC-7). (Note from the lead, 2026-10-15: added
  after the Windows CI failure of PR #6.)
- The 24 px target is useless if part of it cannot be tapped. The whole bounding box
  of a remove button must be hit-testable, which `elementFromPoint` checks (AC-8).

Added on 2026-10-14, from the lead's measurements on Chromium with 8 players
(FX-01). The human approved a compact remove button. The other points are the
lead's decisions, under the human's permission to refine approved and done specs:
- Compact remove button (AC-9). While the roster list is narrower than 4.5rem,
  every remove button shows `✕`, from the new key `host.remove_short` (U+2715). It
  keeps the same `aria-label`, the 24 px minimum, AC-8, and spec 035's focus and
  contrast. The threshold is in rem because the button grows with the root font:
  "Retirer" is 49.6 px (3.1rem) at a 16 px root font and 61 px (3.05rem) at 20 px,
  nearly the same in rem. Options: 3.5rem (first proposed) or 4.5rem. Pick: 4.5rem
  (72 px at 16 px, 90 px at 20 px). A text button needs more than its own width:
  the 3 px after the last item, up to about 14% more in a wider fallback font, and,
  while the list keeps its 8 px scroll padding, 8 px beside it when scrolled into
  view. With 3.5rem, 400x480 at 16 px would show "Retirer" in a 58.1 px list. The
  49.6 px button plus that 8 px leaves half a pixel to spare for AC-8, in the
  lead's font only. With 4.5rem it shows `✕`. Every size of spec 006 AC-5 keeps
  "Retirer": the narrowest list there, 114 px at 568x320, is 7.1rem.
- The compact text replaces the button's text in the DOM (`textContent`). It is not
  CSS generated content or an image. So spec 035's scans see `✕`, and the AC-1
  tests that read the button text at 1280 by 720 still pass. All buttons switch
  together, and they follow resizes and root font changes.
- Minimum list width (AC-10). In the low layout, while the roster holds a remove
  button, `ul.clientWidth >= button.offsetWidth + 3`. This holds at every window
  from 300 px wide and every root font from 12 to 24 px. The compact button alone
  is not enough at 300 px or with a larger font: the list is 24.7 px at 300x480
  with a 16 px root font, and 5.9 px with 20 px.
- The width comes from the activity feed alone, which already truncates its line.
  The host panel keeps at least a third of the row and keeps scrolling sideways
  (AC-7). At 300 px with large fonts the feed may lose its line and part of its
  heading. They stay cut inside its box.
- Test windows (AC-8 to AC-10). 300x480, 320x480, 360x500 and 400x480 are the
  lead's. 480x500 is added because it shows the rem rule: "Retirer" at 16 px and
  `✕` at 20 px. Each window runs at 16 and 20 px root fonts, and 300x480 also at 12
  and 24 px, the ends of the font range, in desktop and touch contexts. Spec 006
  AC-5 keeps its eight sizes. The tests set the root font with a style on `html`,
  and the rules read the computed font size of `html`.
- Two new criteria, AC-9 for the button and AC-10 for the list, one behaviour each.
  AC-8 runs at the new windows too.

## Open questions

None.
