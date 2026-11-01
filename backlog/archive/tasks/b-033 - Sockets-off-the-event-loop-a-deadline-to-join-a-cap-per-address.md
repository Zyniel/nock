---
id: B-033
title: 'Sockets: off the event loop, a deadline to join, a cap per address'
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:realtime
  - domain:server
  - domain:lifetime
  - domain:rooms
dependencies: []
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human, 2026-10-30: « Approve the B-033 brief with the
  lead's picks (1A, 2A, 3A, 4A, 5) and process it »; then the spec change
  « Approved as written »; both review rounds approved)
- Priority: fifth (before the first public test)
- Domains: platform/realtime (a join deadline and its close code, a cap on
  open sockets per address), platform/server (the lookup in one worker-thread
  call), lobby/lifetime (the expiry read again under the lock), lobby/rooms
  (an out-of-scope line)
- Criteria: realtime AC-21 to AC-23 (new), server AC-25, AC-26 (new),
  lifetime AC-14, AC-15 (new)
- Architecture decision: yes (a close code is part of the protocol,
  `platform/realtime.md` rule 13): options from the Plan agent on Fable
- Branch: feat/b-033-socket-hygiene · PR: #74
- Problem: `_serve_socket` calls `RoomRegistry.connect` on uvicorn's event
  loop; `connect` reads SQLite and can wait for the registry lock, which a
  deletion holds up to 5 seconds, and every request of the process waits
  meanwhile (B-028 M1). A socket that never sends `join` stays open for ever,
  and nothing caps the sockets of one address (M2). An expiry is decided
  outside the lock that deletes the room (L3). Since B-032, rooms leave
  memory, so a socket to a room not in memory is the common case: `connect`
  then always takes the registry lock and loads and replays the room on the
  event loop, after `room_socket` already replayed it once with `peek_room`
  (B-032 review, round 1).
- In scope: `connect` off the event loop, with one load of the room per
  socket; a socket not joined that sends nothing for some seconds is closed;
  a cap on the open sockets of an address; the expiry checked again under the
  registry lock.
- Out of scope: frame sizes and the flood and stall bounds (unchanged).
- Screens: none (an honest page pings every 2 seconds, so it never meets the
  deadline; the page treats both close codes below as a loss, as today).
- Options (Plan agent on Fable; lead's picks marked):
  1. The lookup. A (pick): one worker-thread call, `connect`, replaces
     `peek_room` in `room_socket`: the expiry check, one load and replay, and
     the socket counted, in one step under the registry lock (B-032's
     invariant kept); the wrong-code throttle decides on its `None`. A handler
     cancelled while the thread runs leaves the connection it gets back. B:
     keep `peek_room`, thread `connect` only: two loads per socket. C: thread
     the runner lookup, build the connection on the loop: same work, a private
     type crosses the module.
  2. The deadline. The page opens its socket, pings, and only then shows the
     nickname form, so a player on the form holds an unjoined socket as long
     as they think: an absolute deadline would close it again and again. A
     (pick): a silence before the join: no frame of any kind for 10 seconds
     (a ping resets it), held by the connection, its value in `RoomConfig`.
     B: an absolute 10 or 30 seconds from the open, with a page change on the
     form.
  3. Its close code. A (pick): 4408, the silence code, extended to sockets not
     yet joined; the page already retries on it. B: a new 44xx code.
  4. The cap. A (pick): 50 open sockets per address, counted by the server at
     accept and released at close, read at start from
     `NOCK_SOCKETS_PER_ADDRESS` (whole number, default 50, a bad value stops
     the start; no `/ops` override); over the cap, a close with a new code
     4503, a loss for the page (it retries every 8 seconds) since it clears
     when a tab closes; 4429 would be final and read « too many wrong codes ».
     B: 20, fixed: a class of 30 behind one school address would not fit.
  5. L3: `_delete_if_expired` reads the times again under the registry lock
     before deleting; the creator's deletion, which deletes rooms not expired,
     keeps its own path.
- Decisions: the lead's picks, 1A, 2A, 3A, 4A and 5.
<!-- SECTION:DESCRIPTION:END -->
