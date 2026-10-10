---
id: "015"
title: Shared letters
status: approved
---

# 015 - Shared letters

Epic E4 Real-time sync (US-4.1) · Release: MVP · Epic depends on: E3
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a player, I want my friends' letters to appear as they type, so that the grid feels like one sheet of paper.

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-4.1.1) A letter typed by one player appears for the others within 300 ms at the 95th percentile on a 4G connection.
- **AC-2** (AC-4.1.2) My own letter appears at once, before the server confirms it.
- **AC-3** (AC-4.1.3) Given 4 simulated clients sending 1,000 random edits on FX-01, when the edits stop, then all clients and the server hold the same grid.
- **AC-4** (AC-4.1.4) Edits to different cells never delay or cancel each other.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Peer-to-peer sync (epic E4).
- Same-cell conflicts: spec 016.
- Disconnection and reconnection: spec 017.
- Durable room state: spec 018.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
