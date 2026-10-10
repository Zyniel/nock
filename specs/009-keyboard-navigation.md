---
id: "009"
title: Keyboard and navigation
status: draft
---

# 009 - Keyboard and navigation

Epic E2 Solo solving (US-2.4) · Release: MVP · Epic depends on: E1

## Goal

As a player, I want to move around the grid from the keyboard, so that I never need the mouse on desktop.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-2.4.1) Arrow keys move to the next letter cell in that direction and skip clue cells.
- **AC-2** (AC-2.4.2) Tab and Shift+Tab move to the next and previous unfinished word.
- **AC-3** (AC-2.4.3) On touch screens, an in-app AZERTY keyboard with 26 letters and a delete key replaces the system keyboard.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Printing and offline play (epic E2).
- Grid rendering: spec 006.
- Word selection and direction: spec 007.
- Letter entry: spec 008.
- Instant solo start: spec 010.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
