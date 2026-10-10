---
id: "007"
title: Word selection and direction
status: approved
---

# 007 - Word selection and direction

Epic E2 Solo solving (US-2.2) · Release: MVP · Epic depends on: E1
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a player, I want to pick a word with one tap, so that I always know which clue I am answering.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-2.2.1) Tapping a letter cell selects it and highlights its whole word and that word's clue.
- **AC-2** (AC-2.2.2) Tapping the selected cell again switches between its across and down word. On a cell with one word (N or T in FX-01), nothing changes.
- **AC-3** (AC-2.2.3) Tapping a clue selects the first empty cell of its word. In a two-clue cell, each half selects its own word.
- **AC-4** (AC-2.2.4) The selected word's clue is repeated at 14 px or more in a bar that stays visible above the keyboard.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Printing and offline play (epic E2).
- Grid rendering: spec 006.
- Letter entry: spec 008.
- Keyboard and navigation: spec 009.
- Instant solo start: spec 010.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
