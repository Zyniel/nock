---
id: "035"
title: Accessibility
status: approved
---

# 035 - Accessibility

Epic E10 Quality bar (US-10.1) · Release: MVP · Epic depends on: All
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a player using a keyboard or a screen reader, I want the full game, so that I can play with my group.

These criteria apply to every story above and belong in each agent's definition of done.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-10.1.1) Every action is reachable from the keyboard, with a visible focus.
- **AC-2** (AC-10.1.2) On selecting a cell, a screen reader announces the clue, direction, word length and position. On FX-01 at (2,2) with the down word selected: "Artiste muet, vertical, 4 lettres, lettre 2".
- **AC-3** (AC-10.1.3) Colour is never the only signal: each player's cursor also carries their initials. Text contrast is at least 4.5:1.
- **AC-4** (AC-10.1.4) The interface is in French by default, with every string in a translation file.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Nothing stated in the backlog (epic E10).
- Performance: spec 036.
- Integrity: spec 037.
- Privacy and operations: spec 038.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
