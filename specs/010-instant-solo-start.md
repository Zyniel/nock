---
id: "010"
title: Instant solo start
status: approved
---

# 010 - Instant solo start

Epic E2 Solo solving (US-2.5) · Release: MVP · Epic depends on: E1

## Goal

As a player, I want to start a grid alone at once, so that I can invite people later without losing my letters.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-2.5.1) From the catalogue, a grid is playable in one tap, with no sign-up.
- **AC-2** (AC-2.5.2) A solo game becomes a shared room when I invite someone, and every letter is kept.
- **AC-3** (AC-2.5.3) Reloading the page restores my letters and my selected cell.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Printing and offline play (epic E2).
- Grid rendering: spec 006.
- Word selection and direction: spec 007.
- Letter entry: spec 008.
- Keyboard and navigation: spec 009.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
