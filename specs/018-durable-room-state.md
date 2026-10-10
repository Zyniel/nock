---
id: "018"
title: Durable room state
status: approved
---

# 018 - Durable room state

Epic E4 Real-time sync (US-4.4) · Release: MVP · Epic depends on: E3

## Goal

As a player, I want the room to survive a server incident, so that an hour of solving is never lost.

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-4.4.1) Given a server restart during a game, when players reconnect, then at most the last second of edits is missing.
- **AC-2** (AC-4.4.2) A player joining mid-game receives the full state in one message, then every later edit with none skipped.
- **AC-3** (AC-4.4.3) Undo reverts my own last edit, and only when nobody has changed that cell since.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Peer-to-peer sync (epic E4).
- Shared letters: spec 015.
- Same-cell conflicts: spec 016.
- Disconnection and reconnection: spec 017.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- AC-3 (undo) sits in the sync epic in the backlog but is a player action. Keep it here or move it to its own spec?
