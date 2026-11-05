---
area: lobby
file: creator
status: approved
---

# lobby/creator - Member accounts and the creator

## Purpose

A member of a room may be linked to an account. A room created by a signed-in
player has that account as creator, whose player is host whenever connected and
whom no stand-in can keep out; the room goes with the creator's account.

## Depends on

- `lobby/host.md`: the host actions and `invalid_target` (rule 1), the
  hand-over (rule 6).
- `lobby/joining.md`: the join's steps, members, past players, resume, seat back.
- `account/account.md`: accounts on or off, the session; the erasure, which
  deletes creator rooms, is `account/erasure.md`.

## Rules

### Members and accounts

1. An account player is a member linked to an account; an anonymous player is a
   member linked to none. A signed-in join (`lobby/joining.md` rule 4) links the
   new player it makes to the session's account, and links a member it resumes
   or seats back only when that member has none; a member's account never
   changes otherwise (`account/erasure.md` rules 1, 5 apart). `PUT
   /api/account/rooms` links no member.
   An account is at most one player of a room: its signed-in joins reach its
   member, whatever token they carry. The link is stored with the member and
   reaches no browser.

### The creator

2. A room has a creator when its `POST /api/rooms` (`lobby/rooms.md` rule 6)
   carries a valid session (`account/account.md` rule 9) while accounts are on:
   that account, set once and never changed. Such a room is a creator room; any
   other is an anonymous room and stays one, whoever signs in later. The creator
   is stored with the room, in `room_times` (`src/nock/store.py`) beside
   `last_edit_at`, as a nullable column, added once at open to an older store
   (the schema's versions: `lobby/lifetime.md` rule 8); a stored room without
   one is anonymous. Nothing tells the creator apart: no mark in the roster, the
   snapshot or the page.
3. The creator's player is the member of a creator room whose account is the
   creator; a time-out and a seat back keep them so. A stand-in host is a host
   of a creator room other than the creator's player.
4. The creator's player is host whenever connected. Their join, as a new player,
   a resume or a seat back, gives them the role at once, in one `host_changed`
   after any `player_joined`, unless they hold it; a tick that finds them not
   disconnected (idle counts) without the role gives it back the same way; a
   tick never gives the role to a disconnected player. Away longer than the
   hand-over delay they lose it as `lobby/host.md` rule 6 says, and have it
   back on their return. A stand-in host's remove or mute of them is
   `invalid_target` (`lobby/host.md` rule 1). A lock does not keep them out: a
   join from the creator's session skips the locked step, member or not; a full
   room refuses them like anyone (`lobby/joining.md` rule 4).
5. The erasure of the creator's account (`account/erasure.md` rule 1) deletes
   the room, live or stored, whoever is host then, as the deletion of an expired
   room does (`lobby/lifetime.md` rule 6): its sockets close with 4404 and
   nothing else, a page that had shown it shows the room-gone dialog
   (`client/hud.md` rule 16), one that had not the entry card
   (`client/shell.md` rule 7), and a later socket to its code counts as a wrong
   code. The other players' finished grids stay in their history
   (`gameplay/results.md` rule 15, `account/erasure.md` rule 8). Being host of
   an anonymous room deletes nothing: the erased account's player there is `--`
   (`account/erasure.md` rules 1, 5), the room otherwise unchanged.
6. While accounts are off a stored creator stays and the room plays as an
   anonymous room, with an anonymous room's life (`lobby/lifetime.md` rule 3);
   `POST /api/rooms` sets no creator, whatever cookie it carries.

### Look

Nothing on screen tells the creator apart (rule 2); the host's controls are
`lobby/host.md`.

## Acceptance criteria

- **AC-1** Accounts on, Lea's signed-in `POST /api/rooms` makes a room whose
  stored `room_times` row names her account as creator, and `PRAGMA
  user_version` reads 4 (`lobby/lifetime.md` rule 8); a database written before
  the column (`user_version` 0) opens with it added, its stored rooms anonymous
  rooms, their other data kept; a request with no cookie, an unknown or expired
  session, or made while accounts are off with her cookie, makes a room with no
  creator; a host of such a room who signs in later, and sends `PUT
  /api/account/rooms` for it, gives it none.
- **AC-2** Lea joined R signed out; her next join, signed in with her token,
  resumes her and links her member, so a device signed in as Lea and holding no
  token then gets her seat. Bob's member, linked to Bob's account, resumed
  with his token by a device signed in as Zoé who has no member in R, stays
  Bob's: Zoé's next join without a token is a new player. Lea's `PUT
  /api/account/rooms` for a room where her member is unlinked links it not: a
  device signed in as Lea without a token shows the nickname form and joins as
  a new player.
- **AC-3** Lea creates R and Bob enters first by its link, host; Lea's join
  gives Bob `player_joined` (Lea) then `host_changed` (Lea), her snapshot shows
  her host, Bob's Menu loses « Réglages de l'hôte » and hers has it; her own
  room joined first, she is host with no `host_changed`.
- **AC-4** Lea, host, disconnected at t; a tick past t + `host_handover_seconds`
  (60 s) makes Bob host; her resume at once gives one `host_changed` (Lea) and no
  `player_joined`; timed out instead, her seat back gives `player_joined` then
  `host_changed`; a state where Lea is connected and Bob host gets Lea the role
  at the next tick, while a disconnected Lea gets nothing from any tick.
- **AC-5** Bob, stand-in host while Lea is away: his `remove_player` and
  `mute_player` of Lea get `invalid_target` and change nothing, his removal of
  Cy works; back, Lea removes Bob.
- **AC-6** Bob, stand-in host, locks R: Cy's seat back is `room_locked`, while
  Lea's, timed out, passes and ends in `host_changed`; from a new device, signed
  in with no token in a locked room she never joined, Lea is a new player and
  host; with 8 players she gets `room_full`.
- **AC-7** Lea, creator of R, where Bob, signed in, is connected stand-in host,
  and a player of Bob's creator room S, her identity recorded in both, deletes
  her account: Bob's R socket closes with 4404 and nothing else; R has no live
  state and no store rows, after a restart too, and a new socket to its code
  counts as a wrong code; R solved beforehand, Bob's history keeps its record,
  naming her `--`; in S her player is `--`, linked to no account, with no
  event, and S keeps its creator, players and host; an anonymous room where
  Lea was host keeps its players and its host, her player `--`.
- **AC-8** R, Lea's creator room, loaded by an app with accounts off: Bob, host
  after a hand-over, keeps the role when Lea resumes, and her `remove_player`
  gets `not_host`; the store still names her creator; an app with accounts on
  then gives her the role at her next join.

## Edge cases

- A room with one account holding several members gets no backfill: the member
  whose token the device sends is the one a signed-in join reaches and links
  (AC-2).
- A removed account player comes back from another device, with no token, as a
  new player (AC-2).
- A signed-in page with no stored identity still shows the nickname form
  (AC-2).
- The creator's player removed by a stand-in is impossible (AC-5); one who
  leaves and comes back is host again (AC-4).
- The erasure deletes a creator room whether its creator's player is host,
  away, timed out or never joined; the room is gone before the 204 (AC-7).

## Out of scope

- A mark of the creator anywhere. Room lives and expiry: `lobby/lifetime.md`.
- The host's actions, the hand-over and the host controls: `lobby/host.md`.
  Codes and creation: `lobby/rooms.md`. The join's steps, members and
  takeover: `lobby/joining.md`. Accounts and the session:
  `account/account.md`; the erasure: `account/erasure.md`.

## Code

- `src/nock/room.py`: the join's member and its account, the creator's role at
  its join and in `tick`. `src/nock/hub.py`: `register_room`, the creator rooms'
  deletion at an erasure. `src/nock/store.py`: the creator column.
  `src/nock/server.py`: the cookie of `POST /api/rooms` and of the room socket.
- Tests: `tests/test_creator_*.py`, with `tests/host_harness.py` as their
  harness.
