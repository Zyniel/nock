---
area: lobby
file: host
status: done
---

# lobby/host - The host role and the creator

## Purpose

The room's host removes players, locks the room, sets its help and mutes; the
role passes on when the host stays away. A room created by a signed-in player has
a creator, whose player is host whenever connected and whom no stand-in can keep
out; the room goes with the creator's account.

## Depends on

- `lobby/rooms.md`: room creation (`POST /api/rooms`), the room engine and its
  ticks.
- `lobby/joining.md`: the join's steps, members, past players, resume, seat back.
- `account/account.md`: accounts on or off, the session cookie, erasure.

## Rules

### Host actions

1. Host actions are remove, lock, change settings and mute. Another player gets
   `not_host`. Removing or muting oneself, anyone not a player of the room, or,
   from a stand-in host, the creator's player (rule 13), gets `invalid_target`.
   An action that would change nothing gives no event and no reply.
2. Removing t: `player_left` with reason `removed`; t's seat, colour and nickname
   are freed, their letters keep their author, their token is banned (its join is
   `removed`, `lobby/joining.md` rule 4); a connected t gets `error` `removed`,
   then a close 1000. No confirmation. Another token, or none, is a new player.
3. Locking or unlocking announces `settings_changed` with the settings and the
   remaining budget. While locked, every join that is neither a resume nor a
   removed token's (`removed` comes first), a seat back included, is
   `room_locked`, except a join from the creator's session (rule 13).
4. Changing settings sets the help mode and the reveal allowance (any count from
   0), never the lock; locking never changes them. The remaining budget is, for
   letters and words apart, `max(0, new allowance - reveals of that kind used)`.
   One `settings_changed` carries both. Their effect: `gameplay/hints.md`.
5. Muting sets the player's `muted` with one `player_muted`, kept across a
   restart. Its effect: `social/chat.md`.

### The role

6. When the host has been disconnected more than the hand-over delay,
   `host_handover_seconds` (60 s), a tick gives the role to the player not
   disconnected (idle counts) with the smallest join seq, in one `host_changed`;
   with none, the host stays and the next tick tries again. A host who times out
   hands the role at once, after the `player_left`, to the remaining player with
   the smallest join seq, connected first; with nobody left the next joiner is
   host. A resume keeps one's join seq. A host back after a hand-over is an
   ordinary player, unless they are the creator's player (rule 13).
7. The room refuses with `not_joined`, changing nothing, any message from an id
   that is not one of its players (removed, timed out, unknown). On a socket,
   before its join, every message but `join` and `ping` gets `not_joined`
   (`platform/realtime.md` rule 4). Frames from a socket the room closed (a
   removal, a silence) reach nothing, from that step on; a new socket of that
   player is heard again.

### Host controls on the page

8. The host's row shows `roster.host`. Only the host sees « Retirer » in each
   other player's Joueurs row, named `host.remove_label`, which sends
   `remove_player` at once; and « Réglages de l'hôte » in the Menu, opening the
   host sheet (`settings.heading`): the switch `host.lock`; the help mode
   (`settings.help_mode_label`) as three choices (`settings.help_mode.*`); the
   counts `settings.reveal_letters_label` and `settings.reveal_words_label`
   (whole, 0 to 99); « Enregistrer », which sends `change_settings`, never with a
   count out of those bounds. The sheet shows the room's help mode and allowance,
   not the remaining budget, and follows `settings_changed`; the switch sends the
   opposite of the room's lock and shows the room's, not the click's. A
   `host_changed` gives or takes these controls at once.
9. `removed` or `room_locked`, on a join, during the game or a reconnection, ends
   the page on `removed` or `locked` with `room.status.removed` or
   `room.status.locked`, with no form, no reconnection band and no reconnection;
   `throttled` is final too. Before any snapshot it shows on the entry card of
   `lobby/joining.md` rule 11, after it on the status band. After `removed` the
   identity stays, so a reload is refused again.

### Members and accounts

10. An account player is a member linked to an account; an anonymous player is a
    member linked to none. A signed-in join (`lobby/joining.md` rule 4) links the
    new player it makes to the session's account, and links a member it resumes
    or seats back only when that member has none; a member's account never
    changes otherwise (`account/account.md` rule 18 apart). `PUT
    /api/account/rooms` links no member.
    An account is at most one player of a room: its signed-in joins reach its
    member, whatever token they carry. The link is stored with the member and
    reaches no browser.

### The creator

11. A room has a creator when its `POST /api/rooms` (`lobby/rooms.md` rule 6)
    carries a valid session (`account/account.md` rule 9) while accounts are on:
    that account, set once and never changed. Such a room is a creator room; any
    other is an anonymous room and stays one, whoever signs in later. The creator
    is stored with the room, in `room_times` (`src/nock/store.py`) beside
    `last_edit_at`, as a nullable column, added once at open to an older store
    (the schema's versions: `lobby/lifetime.md` rule 8); a stored room without
    one is anonymous. Nothing tells the creator apart: no mark in the roster, the
    snapshot or the page.
12. The creator's player is the member of a creator room whose account is the
    creator; a time-out and a seat back keep them so. A stand-in host is a host
    of a creator room other than the creator's player.
13. The creator's player is host whenever connected. Their join, as a new player,
    a resume or a seat back, gives them the role at once, in one `host_changed`
    after any `player_joined`, unless they hold it; a tick that finds them not
    disconnected (idle counts) without the role gives it back the same way; a
    tick never gives the role to a disconnected player. Away longer than the
    hand-over delay they lose it as rule 6 says, and have it back on their
    return. A stand-in host's remove or mute of them is `invalid_target` (rule
    1). A lock does not keep them out: a join from the creator's session skips
    the locked step, member or not; a full room refuses them like anyone
    (`lobby/joining.md` rule 4).
14. The erasure of the creator's account (`account/account.md` rule 18) deletes
    the room, live or stored, whoever is host then, as the deletion of an expired
    room does (`lobby/lifetime.md` rule 6): its sockets close with 4404 and
    nothing else, a page that had shown it shows the room-gone dialog
    (`client/hud.md` rule 16), one that had not the entry card
    (`client/shell.md` rule 7), and a later socket to its code counts as a wrong
    code. The other players' finished grids stay in their history
    (`gameplay/results.md` rule 15, `account/account.md` rule 22). Being host of
    an anonymous room deletes nothing: the erased account's player there is `--`
    (`account/account.md` rule 18), the room otherwise unchanged.
15. While accounts are off a stored creator stays and the room plays as an
    anonymous room, with an anonymous room's life (`lobby/lifetime.md` rule 3);
    `POST /api/rooms` sets no creator, whatever cookie it carries.

### Look

Joueurs rows and host buttons: `_design/room.md`, « Salon »; the Menu entry,
« Menu »; the host sheet, « Room sheets: host settings and account »; a final
status once the room has shown, the status band of « Connection lost »; before,
the entry card of `lobby/joining.md` rule 11, `_design/pages.md`, « Entry and
not-found pages ».

## Acceptance criteria

- **AC-1** Host Ana removes Bob: Ana and Cy get `player_left` (Bob, `removed`),
  Bob gets `error` `removed` then a close 1000, and his page shows « Vous avez
  été retiré de ce salon. », after a reload too, with no form; Bob's removal of
  Cy gets `not_host`, Ana's of herself or `zz` `invalid_target`. (← 014 AC-1)
- **AC-2** Ana locks: she and Bob get `settings_changed` locked; a new socket
  gets `room_locked` and its page « Ce salon est verrouillé. », the room keeps
  2 players and Bob's token resumes; locking again gives nothing, Bob's unlock
  `not_host`; once Ana unlocks, a newcomer joins. (← 014 AC-2)
- **AC-3** Host p1 disconnected at t, p2 active, p3 idle: a tick at t +
  `host_handover_seconds` (60 s) changes nothing, half a second later p2 is
  host; with p2 away too p3, with both away p1 stays; p1 back is no host and
  gets `not_host`; the new host's page gains « Retirer » and « Réglages de
  l'hôte », the old host's loses them. (← 014 AC-3)
- **AC-4** Ana sets vote, 3 letters, 0 words: both get `settings_changed`
  with these and remaining 3 and 0, and both feeds read « Ana a modifié les
  réglages : aide par vote, 3 lettres et 0 mots à révéler »; the same again
  gives nothing; with 3 letters and 1 word used, 1 and 1 leave 0 and 0, then
  10 and 5 leave 7 and 4. (← 014 AC-4)
- **AC-5** Just after Ana removes Bob, 40 `edit_letter` from Bob's socket are
  neither applied nor sent and no cell has Bob as author; a message from a
  timed-out or unknown id, or an `edit_letter` before any join, gets `not_joined`.
  (← 014 AC-5)
- **AC-6** Ana mutes Bob: one `player_muted` reaches everyone and his snapshot
  shows him muted, after a restart too; muting again gives nothing; Bob's mute
  gets `not_host`, Ana's of herself, `zz` or a removed player `invalid_target`.
  (← 014 AC-6)
- **AC-7** With the host among 8 players, in the windows of `product.md` rule
  11 and from 300 px wide with root fonts of 12 to 24 px, each « Retirer » and
  « Couper » is at least 24 px square and hit on every pixel once scrolled
  into the Joueurs tab, which never scrolls sideways, while the grid keeps its
  room; each « Retirer » reads so, shows whole with its focus ring from the
  keyboard, and keeps the baselines of `product.md`. (← 014 AC-7, 014 AC-8,
  014 AC-9)
- **AC-8** In the same windows and fonts, the host sheet lies inside the window
  with no sideways scroll, and the switch, the three choices, both counts and
  « Enregistrer » are each at least 24 px high, inside it and hit at their centre,
  the counts as wide as « Room sheets » says; opened from the Menu by keyboard,
  Tab reaches them in that order, each with the focus ring of `product.md` inside
  the sheet. (← 014 AC-7, 014 AC-10)
- **AC-9** Accounts on, Lea's signed-in `POST /api/rooms` makes a room whose
  stored `room_times` row names her account as creator, and `PRAGMA
  user_version` reads 3 (`lobby/lifetime.md` rule 8); a database written before
  the column (`user_version` 0) opens with it added, its stored rooms anonymous
  rooms, their other data kept; a request with no cookie, an unknown or expired
  session, or made while accounts are off with her cookie, makes a room with no
  creator; a host of such a room who signs in later, and sends `PUT
  /api/account/rooms` for it, gives it none.
- **AC-10** Lea joined R signed out; her next join, signed in with her token,
  resumes her and links her member, so a device signed in as Lea and holding no
  token then gets her seat. Bob's member, linked to Bob's account, resumed
  with his token by a device signed in as Zoé who has no member in R, stays
  Bob's: Zoé's next join without a token is a new player. Lea's `PUT
  /api/account/rooms` for a room where her member is unlinked links it not: a
  device signed in as Lea without a token shows the nickname form and joins as
  a new player.
- **AC-11** Lea creates R and Bob enters first by its link, host; Lea's join
  gives Bob `player_joined` (Lea) then `host_changed` (Lea), her snapshot shows
  her host, Bob's Menu loses « Réglages de l'hôte » and hers has it; her own
  room joined first, she is host with no `host_changed`.
- **AC-12** Lea, host, disconnected at t; a tick past t + `host_handover_seconds`
  (60 s) makes Bob host; her resume at once gives one `host_changed` (Lea) and no
  `player_joined`; timed out instead, her seat back gives `player_joined` then
  `host_changed`; a state where Lea is connected and Bob host gets Lea the role
  at the next tick, while a disconnected Lea gets nothing from any tick.
- **AC-13** Bob, stand-in host while Lea is away: his `remove_player` and
  `mute_player` of Lea get `invalid_target` and change nothing, his removal of
  Cy works; back, Lea removes Bob.
- **AC-14** Bob, stand-in host, locks R: Cy's seat back is `room_locked`, while
  Lea's, timed out, passes and ends in `host_changed`; from a new device, signed
  in with no token in a locked room she never joined, Lea is a new player and
  host; with 8 players she gets `room_full`.
- **AC-15** Lea, creator of R, where Bob, signed in, is connected stand-in host,
  and a player of Bob's creator room S, her identity recorded in both, deletes
  her account: Bob's R socket closes with 4404 and nothing else; R has no live
  state and no store rows, after a restart too, and a new socket to its code
  counts as a wrong code; R solved beforehand, Bob's history keeps its record,
  naming her `--`; in S her player is `--`, linked to no account, with no
  event, and S keeps its creator, players and host; an anonymous room where
  Lea was host keeps its players and its host, her player `--`.
- **AC-16** R, Lea's creator room, loaded by an app with accounts off: Bob, host
  after a hand-over, keeps the role when Lea resumes, and her `remove_player`
  gets `not_host`; the store still names her creator; an app with accounts on
  then gives her the role at her next join.

## Edge cases

- A disconnected player can be removed, with no socket to close; removed again,
  `invalid_target` (AC-1).
- A player away within the resume window resumes in a locked room; one timed out
  is refused, and seats back once it is unlocked (AC-2).
- A room with one account holding several members gets no backfill: the member
  whose token the device sends is the one a signed-in join reaches and links
  (AC-10).
- A removed account player comes back from another device, with no token, as a
  new player (AC-10).
- A signed-in page with no stored identity still shows the nickname form
  (AC-10).
- The creator's player removed by a stand-in is impossible (AC-13); one who
  leaves and comes back is host again (AC-12).
- The erasure deletes a creator room whether its creator's player is host,
  away, timed out or never joined; the room is gone before the 204 (AC-15).

## Out of scope

- Handing the host role on by hand, co-hosts, un-banning, banning by address or
  browser; a mark of the creator anywhere. Room lives and expiry:
  `lobby/lifetime.md`.
- Codes, creation, the throttle and the engine: `lobby/rooms.md`. The join's
  steps, members and takeover: `lobby/joining.md`. Accounts, the session and
  erasure: `account/account.md`. Feed lines of host, lock and settings changes,
  « Couper » and muting's effect: `social/chat.md`. The Menu, sheets and top
  bar: `client/hud.md`; the Joueurs tab: `client/room.md`.

## Code

- `src/nock/room.py`: host actions, the hand-over and the creator's return in
  `tick`, the join's member and its account; `RoomConfig` holds the hand-over
  delay. `src/nock/hub.py`: `register_room`, the creator rooms' deletion at an
  erasure. `src/nock/store.py`: the creator column. `src/nock/server.py`: the
  cookie of `POST /api/rooms` and of the room socket.
- `web/src/lib/PlayersPanel.svelte`, `HostSettings.svelte`: host controls;
  `RoomPage.svelte`, `roomSession.ts`: final statuses.
- Tests: `tests/test_spec_014_*`, `tests/test_host_*`.
