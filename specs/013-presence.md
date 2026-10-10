---
id: "013"
title: Presence
status: approved
---

# 013 - Presence

Epic E3 Rooms and presence (US-3.3) · Release: MVP · Epic depends on: E2

## Goal

As a player, I want to see who is here and where they are working, so that we don't solve the same clue twice.

A room is one grid shared by up to 8 players and reached by a link.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-3.3.1) A roster lists each player with a colour and a state: active, idle after 2 minutes without input, or disconnected.
- **AC-2** (AC-3.3.2) Another player's selected cell is outlined in their colour and their word lightly tinted, within 300 ms of their move.
- **AC-3** (AC-3.3.3) When two players select the same cell, both outlines are visible.
- **AC-4** (AC-3.3.4) My own selection is styled differently from every other player's.
- **AC-5** (AC-3.3.5) An activity feed lists joins, departures, checks, reveals, flags and setting changes in the order they happened.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Room creation and invitation: spec 011.
- Guest join: spec 012.
- Host controls: spec 014.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
