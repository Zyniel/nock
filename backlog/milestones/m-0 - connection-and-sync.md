---
id: m-0
title: "Connection and sync"
---

## Description

- Problem: the web client review (B-039) found that the room page's connection loses or reorders a player's work. A sign-out leaves the account's seats on a shared device; after a drop, an undo can erase another letter for everyone and the player's cursor disappears for the others; every frame redraws every letter cell; and rare cases (a final status, reactions sent offline, hidden tabs, a socket stuck connecting) misbehave.
- Size: M (4 tasks): B-040, B-041, B-043, B-047.
- In scope: the four tasks as their descriptions say, with the lead's defaults to their open questions.
- Out of scope: moving the connection out of `RoomPage.svelte` (B-049); server pings or any other protocol change.
- Look: none new. Looks that exist (the kept join form while the page reconnects, the clue bar while not joined) are drawn if the screens sheet lacks them.
- Risks: lasting architecture only if B-040 took option B (the identity record every page reads) or B-047 needed pings from the server; the lead's picks avoid both.
- Questions for you: none.
