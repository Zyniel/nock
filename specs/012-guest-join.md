---
id: "012"
title: Guest join
status: draft
---

# 012 - Guest join

Epic E3 Rooms and presence (US-3.2) · Release: MVP · Epic depends on: E2

## Goal

As an invited player, I want to join with only a nickname, so that I am playing within seconds.

A room is one grid shared by up to 8 players and reached by a link.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-3.2.1) Given a valid link, when I enter a nickname of 2 to 20 characters, then I am in the room.
- **AC-2** (AC-3.2.2) Each player gets a colour no other player in the room has. A duplicate nickname gets a numeric suffix.
- **AC-3** (AC-3.2.3) I see the current letters, timer and hint budget within 1 second of joining.
- **AC-4** (AC-3.2.4) Joining a room that already has 8 players shows "room full" and does not add me.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Presence: spec 013.
- Host controls: spec 014.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- Which characters are allowed in a nickname besides letters and digits?
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
