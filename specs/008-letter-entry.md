---
id: "008"
title: Letter entry
status: approved
---

# 008 - Letter entry

Epic E2 Solo solving (US-2.3) · Release: MVP · Epic depends on: E1

## Goal

As a player, I want typing to flow along the word, so that I fill an answer without re-selecting cells.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-2.3.1) Typing a letter fills the cell and moves to the next cell of the word. At the last cell the cursor stays.
- **AC-2** (AC-2.3.2) Typing é, à or ç enters E, A or C. Digits, spaces and punctuation are ignored.
- **AC-3** (AC-2.3.3) Backspace clears the current cell. On an empty cell it moves back one cell and clears that one.
- **AC-4** (AC-2.3.4) Typing over a filled cell replaces its letter, unless the cell is locked (spec 016 AC-3, backlog AC-4.2.3).

## Edge cases and errors

- AC-4 depends on behaviour owned by spec 016; test only this spec's side of it here.

## Out of scope

- Printing and offline play (epic E2).
- Grid rendering: spec 006.
- Word selection and direction: spec 007.
- Keyboard and navigation: spec 009.
- Instant solo start: spec 010.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
