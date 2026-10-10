---
id: "026"
title: Completion detection
status: draft
---

# 026 - Completion detection

Epic E6 Help and validation (US-6.4) · Release: MVP · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a team, we want the game to recognise the finished grid, so that we don't have to press anything to win.

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-6.4.1) When the last empty cell is filled and every letter is right, the grid is marked solved for all players within 1 second and input is locked.
- **AC-2** (AC-6.4.2) When the grid is full with at least one wrong letter, all players see "grid full, not yet correct" with no hint of where.
- **AC-3** (AC-6.4.3) On FX-01, entering the 18 letters triggers completion. With the M at (1,2) replaced by N, it does not.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Generated hints and dictionary lookups (epic E6).
- Check a letter, a word or the grid: spec 023.
- Reveal a letter or a word: spec 024.
- Group decision on help: spec 025.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
