---
id: "017"
title: Disconnection and reconnection
status: approved
---

# 017 - Disconnection and reconnection

Epic E4 Real-time sync (US-4.3) · Release: MVP · Epic depends on: E3

## Goal

As a player on a train, I want to keep my place when my connection drops, so that I rejoin without starting over.

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-4.3.1) A banner shows within 5 seconds of a lost connection, and I can keep typing.
- **AC-2** (AC-4.3.2) On reconnection, my offline letters are sent. Where the server's cell changed in the meantime, the server's letter is kept.
- **AC-3** (AC-4.3.3) Reconnecting within 5 minutes restores my nickname, colour and authorship with nothing to re-enter.
- **AC-4** (AC-4.3.4) Other players see my state change in the roster within 10 seconds.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Peer-to-peer sync (epic E4).
- Shared letters: spec 015.
- Same-cell conflicts: spec 016.
- Durable room state: spec 018.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
