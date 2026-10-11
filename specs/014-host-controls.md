---
id: "014"
title: Host controls
status: approved
---

# 014 - Host controls

Epic E3 Rooms and presence (US-3.4) · Release: MVP · Epic depends on: E2
The rooms engine and the fake-clock harness are defined in spec 011; joining, the
join order of refusals, the stored identity and the roster in spec 012; the feed in
spec 013; disconnection and time-out in spec 017. The messages are those of spec
039.

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
a resume (step 2) is refused with `ROOM_LOCKED` and `close_sender`. Members resume
as usual.

`ChangeSettings(help_mode, reveal_budget)` from the host: if both equal the
current `settings.help_mode` and `settings.reveal_budget`, nothing happens.
Otherwise `settings.help_mode` and `settings.reveal_budget` take the new values
(`locked` unchanged); the remaining budget becomes, for letters and for words
separately, `max(0, new_allowance - used)` where
`used = old_allowance - old_remaining`; one entry `SettingsChanged(...)` with the
new settings and remaining budget. What the help mode and budget do is specs 023
to 025's.

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
  `data-testid="remove-player"` with the text `t("host.remove")` and
  `aria-label` `t("host.remove_label", {name})`. Clicking it sends
  `{"type": "remove_player", "player_id": <that id>}` at once.

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
| `host.lock` | `Verrouiller le salon` |
| `host.unlock` | `Déverrouiller le salon` |
| `settings.heading` | `Réglages` |
| `settings.help_mode_label` | `Aide` |
| `settings.reveal_letters_label` | `Lettres à révéler` |
| `settings.reveal_words_label` | `Mots à révéler` |
| `settings.save` | `Enregistrer` |
| `room.status.locked` | `Ce salon est verrouillé.` |
| `room.status.removed` | `Vous avez été retiré de ce salon.` |

The feed lines for these events (`room_locked`, `room_unlocked`,
`settings_changed`, `player_removed`, `host_changed`) are spec 013's.

### Test harness

As spec 011. Browser criteria with two players use two browser contexts on the live
server (two "browsers": separate `localStorage`), each through `enter_room`.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-3.4.1) (Python; WebSocket; browser with live server) The host can remove a player, who then cannot rejoin from the same browser. Python: `handle_message` with `RemovePlayer(player_id="p2")` from host `p1` gives one entry `PlayerLeft(player_id="p2", reason="removed")`, `p2` gone from `players`, `p2`'s token in `removed_tokens`, and a `Disconnect` for `p2` with close code 1000 and error code `removed`; the same from `p2` gives `not_host`; `RemovePlayer(player_id="p1")` from `p1` and `RemovePlayer(player_id="zz")` give `invalid_target`; then `join_room` with `p2`'s old token gives `removed` and `close_sender`, and `join_room` without a token gives a new player. WebSocket: host A, players B and C; A removes B; A and C receive `PlayerLeft(<B>, removed)`; B receives `error` `removed` then a close with code 1000; a new socket joining with B's token receives `error` `removed` then a close; `room_state` holds A and C. Browser: Ana (host, context 1) and Bob (context 2) join; Ana clicks `remove-player` on Bob's item; Bob's page reaches `data-status="removed"` showing `fr.json["room.status.removed"]` and Ana's roster holds 1 player; Bob's page reloaded reaches `data-status="removed"` again without showing `nickname-form`. Before the removal, Bob's own page (not host) shows no `remove-player` button and no `host-panel`.
- **AC-2** (AC-3.4.2) (WebSocket; browser with live server) The host can lock the room; new joiners then see "room locked". WebSocket: host A and player B join; A sends `lock_room` `true`; A and B receive `SettingsChanged` with `settings.locked` true and `player_id` A; a new socket without a token gets `error` `room_locked` then a close with code 1000, and the room keeps 2 players; B closes its socket and joins again with its token: accepted (`Snapshot`); a second `lock_room` `true` produces no event; `lock_room` `false` from B gets `not_host`; from A it unlocks, and a new socket then joins. Browser: Ana (host) clicks `lock-room`, which then has `aria-pressed="true"`; a second context opening the room and submitting `Bob` reaches `data-status="locked"` showing `fr.json["room.status.locked"]`.
- **AC-3** (AC-3.4.3) (Python; WebSocket with a fake clock) If the host is disconnected for more than 60 seconds, the longest-present player becomes host. Python: host `p1` (joined first) disconnected at `t`, `p2` (joined second, active), `p3` (joined third, idle): `tick` at `t + 60` changes no host; at `t + 60.5` gives `HostChanged(player_id="p2")` with `p2.is_host` True and `p1.is_host` False; with `p2` also disconnected, the host becomes `p3`; with every other player disconnected, no `host_changed` and `p1` stays host; when `p1` then reconnects after the hand-over, `p1.is_host` stays False. WebSocket: A (host), B, C join in that order; A's socket closes; after `advance(59)` and a tick, nobody has received `host_changed`; after `advance(2)`, B and C receive `HostChanged(<B>)` within one second of real time, and B's `remove_player` on C is then accepted while A's resumed `lock_room` gets `not_host`.
- **AC-4** (AC-3.4.4) (WebSocket; browser with live server) A change of room settings is announced to all players in the activity feed. WebSocket: host A and player B; A sends `change_settings` with help mode `vote` and budget 3 letters, 0 words; A and B receive `SettingsChanged(player_id=<A>, settings=RoomSettings(help_mode="vote", reveal_budget=RevealBudget(letters=3, words=0), locked=False), reveal_budget=RevealBudget(letters=3, words=0))`; the same message again produces no event; B's `change_settings` gets `not_host`. Browser: Ana (host) and Bob join; Ana sets `help-mode-select` to `vote`, `reveal-letters-input` to `3`, `reveal-words-input` to `0` and clicks `settings-save`; Bob's `activity-feed` gets a `feed-item` with `data-kind="settings_changed"` and the text `Ana a modifié les réglages : aide par vote, 3 lettres et 0 mots à révéler`; Ana's own feed gets the same line.

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
- Locked room and members (AC-2): disconnected members within the 5-minute window
  resume; a member who timed out (spec 017) is no longer a member and is refused.
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

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Guest join: spec 012.
- Presence and the feed's display: spec 013.
- Handing the host role over by hand, co-hosts.
- Banning by address or across browsers; un-banning a removed player.
- The effect of help mode and budget on checks and reveals (specs 023 to 025), and
  of muting on chat (spec 022, which owns the mute button).

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

## Open questions

None.
