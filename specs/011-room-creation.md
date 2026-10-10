---
id: "011"
title: Room creation and invitation
status: approved
---

# 011 - Room creation and invitation

Epic E3 Rooms and presence (US-3.1) · Release: MVP · Epic depends on: E2

## Goal

As a host, I want a link to send to my friends, so that they land directly on our grid.

A room is one grid shared by up to 8 players and reached by a link.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-3.1.1) Creating a room gives a share link and a 6-character room code.
- **AC-2** (AC-3.1.2) The link opens the room on the grid, on phone and desktop, with no install.
- **AC-3** (AC-3.1.3) Room codes are random, not sequential. Ten wrong codes from one address within a minute are throttled.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Guest join: spec 012.
- Presence: spec 013.
- Host controls: spec 014.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
