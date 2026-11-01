---
id: B-022
title: Creator rooms and host return
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:host
  - domain:rooms
  - domain:joining
  - domain:account
  - domain:realtime
  - domain:hud
  - domain:operations
  - domain:room
dependencies: []
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved the brief as written, with the lead's
  calls, then the spec change as written, `invalid_target` included,
  2026-10-28; in review round 1 the human made erasure delete the creator
  rooms and approved that spec change, 2026-10-29; built and reviewed in two
  rounds, 2026-10-29)
- Domains: lobby/host (new: the host role, moved from `lobby/rooms.md` rules
  13 to 21), lobby/rooms, lobby/joining, account/account, platform/realtime;
  `specs/_map.md` (a table row, the glossary); "guest" reworded in product,
  client/hud, admin/operations, `_reference.md`; citations of the host rules
  repointed in client/hud (rules 10 and 13), client/room, and wherever else
  `lobby/rooms.md` is cited for them
- Architecture decision: yes (a new domain file; stored data: the room's
  creator and each member's account; the room socket reads the session
  cookie). The options were weighed by the Plan agent on Fable for the first
  brief of this request; the human settled them, so no new Plan run.
- Criteria: host AC-1 to AC-8 (moved from rooms AC-13 to AC-20, pointers to
  014 kept), host AC-9 to AC-16 (new); rooms AC-13 to AC-20 (deleted, moved);
  joining AC-21 (new); account AC-13, hud AC-8, product AC-1 (wording only)
- Branch: feat/b-022-creator-rooms · PR: none yet
- Problem: the human asked: "Creator rooms and host return." Today the first
  joiner is host, a host away 60 s loses the role for good, an account may
  hold several members of one room, and "guest" means three things (an
  invited player, a player with no account, a player who is not host).
- In scope, the human's request as written:
  - Terms, in the glossary of `specs/_map.md` and used the same way in every
    domain; "guest" dropped as a spec term: account player (a member linked
    to an account); anonymous player (a member linked to no account);
    invited player (someone who enters by the room link and the nickname
    form); connection (one socket of a player; "session" stays the sign-in
    cookie); creator (the account whose session sent `POST /api/rooms`, set
    once at creation and never changed; none without a valid session or
    with accounts off); creator room and anonymous room (a room with and
    without a creator; a room created without a session stays anonymous
    even if its host signs in later); creator's player (the member of a
    creator room linked to its creator); stand-in host (a host of a creator
    room other than the creator's player); hand-over delay
    (`host_handover_seconds`, 60 s).
  - An account is at most one player in a room. A signed-in join to a room
    where the account already has a member gets that member back (seat,
    colour, letters, host role), and the older connection is closed with
    4001 as in today's takeover. The room socket learns the account from
    the session cookie.
  - The creator's player is host whenever connected: their join, resume or
    seat back gives them the role at once in one `host_changed`; while they
    are away longer than the hand-over delay, the role passes on as today.
  - A stand-in host cannot remove or mute the creator's player; a lock does
    not keep the creator's player out; a full room still does.
  - If the creator's account is erased, the room is deleted (the human's
    decision in review round 1, replacing "becomes an anonymous room").
  - Every duration or limit is written as its name with its default, never
    a bare number.
- Out of scope: any mark of the creator in the roster, the snapshot or the
  page; room lives (B-023); handing the role on by hand; co-hosts.
- Screens: none.
- Already decided by the human (on the first brief of this request and its
  spec change, 2026-10-28):
  - Where it lives: **A, a new file `lobby/host.md`**, "the host role: who
    holds it, how it passes, what it may do; the creator". It takes
    `rooms.md` rules 13 to 21 and AC-13 to AC-20 (pointers to 014 kept,
    renumbered from AC-1) and adds about eight criteria; `rooms.md` falls to
    12 criteria. The one-player-per-account rule changes in place in
    `joining.md` and `account.md`; `realtime.md` gets a sentence on the
    cookie and no criterion. Rejected: B, a `lobby/members.md`; C, edits in
    place in four files already at their budget.
  - Terms: **A, written in this item**, not in a wording-only item first.
  - Shape:
    - The room stores its creator's account id, set by `POST /api/rooms`
      from a valid `nock_session` (none with accounts off), in a nullable
      column of the store table `room_times`, beside `last_edit_at`, so that
      B-023's sweep reads a room's kind from one table. Stored rooms without
      it are anonymous rooms. The column makes `PRAGMA user_version` 1;
      B-023 takes 2.
    - Each member stores its account id, set at a signed-in join. The
      creator's player is the member whose account is the creator, not a
      stored member id, so a time-out and seat back keeps them.
      `PUT /api/account/rooms` stays for pages already open and links no
      member.
    - The join's member is chosen once, before the steps: signed in, the
      account's member of the room, player or past player, whatever token
      the join carries; else the member whose token it carries. A token
      that is not the join's member's is not used: its member is not
      touched and their connection stays open. Steps: removed token; the
      member a player: resume (older connection 4001), or time out and go
      on; locked (skipped for a join from the creator's session, member or
      not); full (for everyone); the member a past player: seat back;
      nickname; new player.
    - The hand-over tick also gives the role back to a connected creator's
      player who lacks it, so "whenever connected" holds after a plain
      reconnection; the tick never gives the role to a disconnected player.
    - Erasure deletes the account's creator rooms, live and stored, as an
      expired room's deletion does; in other rooms its recorded identities'
      players become `--`, unlinked. Its criterion lives in `host.md`
      (AC-15). (Review round 1; the first shape cleared the creator.)
    - Rooms where one account already holds several members get no
      backfill: the member whose token the device sends is stamped at the
      next signed-in join. A member linked to account A, joined with its
      token by a device signed in as B with no member there, is resumed and
      stays A's.
    - Accounts turned off after creation: the room keeps its creator in the
      store and plays as an anonymous room while accounts are off.
    - A signed-in page with no stored identity still shows the nickname
      form; a removed account player may come back from another device as a
      new player, as today.
- New since the first brief (the lead's calls; say if any should change):
  - B-025 split `client/hud.md`: the host rules are cited from hud rule 10
    (« Réglages de l'hôte » in the Menu) and rule 13 (the settings sheet),
    and the remove and mute buttons from `client/room.md` (the Salon's
    Joueurs tab). Those citations move to `lobby/host.md`.
  - `joining.md` gains one criterion (the account's member wins over a
    token) and goes to 21 criteria and about 17.5 KB, a little over the
    budget of about 15 KB and 20; `account.md` is already at about 19 KB.
    The lead keeps them there, since the rules belong there, and adds a
    small follow-up to trim or split both.
  - B-021 (room gone dialog) runs at the same time and may touch
    `joining.md` and `hud.md`; whichever merges second merges `origin/main`
    and resolves. B-023 waits for this item.
- Open questions: none.
- Review round 1 (2026-10-29): one blocking finding, `account.md` rule 18
  promising that erasure unlinks the account's members in every room while
  the code did it only in its creator rooms and through its identities. The
  human: "Make things simpler. When deleting an account, remove all rooms
  belonging to the host.", then "Go: erasure deletes the account's creator
  rooms, as you laid it out, with your defaults." The defaults: "belonging
  to the host" means the rooms the account created; their players' sockets
  close with 4404 (the room-gone dialog of B-021); other players' finished
  grids stay in their history; in other rooms the account's recorded
  identities' players become `--`, unlinked, and rule 18 says only that.
  B-023's "a room that changes kind (… its creator's account erased)" no
  longer happens: its brief drops that case.
<!-- SECTION:DESCRIPTION:END -->
