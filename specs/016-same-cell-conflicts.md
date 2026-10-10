---
id: "016"
title: Same-cell conflicts
status: approved
---

# 016 - Same-cell conflicts

Epic E4 Real-time sync (US-4.2) · Release: MVP · Epic depends on: E3

## Goal

As a player, I want a clear rule when two of us type in one cell, so that nobody is surprised by a vanishing letter.

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-4.2.1) When two players type in the same cell at once, the edit the server receives last wins and every client shows it.
- **AC-2** (AC-4.2.2) The player whose letter was replaced sees the cell flash in the other player's colour.
- **AC-3** (AC-4.2.3) A cell confirmed correct by a check or a reveal is locked and rejects edits from everyone.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Peer-to-peer sync (epic E4).
- Shared letters: spec 015.
- Disconnection and reconnection: spec 017.
- Durable room state: spec 018.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
