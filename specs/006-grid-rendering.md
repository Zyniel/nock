---
id: "006"
title: Grid rendering
status: draft
---

# 006 - Grid rendering

Epic E2 Solo solving (US-2.1) · Release: MVP · Epic depends on: E1
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a player, I want the grid and its clues readable on my phone, so that I can play without a desktop.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-2.1.1) On a 360 px wide screen, FX-02 can be panned and pinch-zoomed, and no clue text is cut off at full zoom.
- **AC-2** (AC-2.1.2) Each clue draws its arrow on the side of its word's first letter cell.
- **AC-3** (AC-2.1.3) A cell with two clues shows both, separated by a line; FX-01 shows this at (0,0).
- **AC-4** (AC-2.1.4) A new game on FX-01 renders 7 clue cells and 18 empty letter cells.
- **AC-5** (AC-2.1.5) The game is a responsive web app with no native app and no install. Every screen works from 320 px wide up to desktop, in portrait and landscape, on current Chrome, Safari, Firefox and Edge.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Printing and offline play (epic E2).
- Word selection and direction: spec 007.
- Letter entry: spec 008.
- Keyboard and navigation: spec 009.
- Instant solo start: spec 010.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- FX-02, the full-size grid used by AC-1, is still to be chosen.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
