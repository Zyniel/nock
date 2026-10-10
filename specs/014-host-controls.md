---
id: "014"
title: Host controls
status: draft
---

# 014 - Host controls

Epic E3 Rooms and presence (US-3.4) · Release: MVP · Epic depends on: E2

## Goal

As a host, I want to manage who is in the room, so that an unwanted visitor can't spoil the game.

A room is one grid shared by up to 8 players and reached by a link.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-3.4.1) The host can remove a player, who then cannot rejoin from the same browser.
- **AC-2** (AC-3.4.2) The host can lock the room; new joiners then see "room locked".
- **AC-3** (AC-3.4.3) If the host is disconnected for more than 60 seconds, the longest-present player becomes host.
- **AC-4** (AC-3.4.4) A change of room settings is announced to all players in the activity feed.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Guest join: spec 012.
- Presence: spec 013.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
