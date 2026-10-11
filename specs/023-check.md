---
id: "023"
title: Check a letter, a word or the grid
status: approved
---

# 023 - Check a letter, a word or the grid

Epic E6 Help and validation (US-6.1) · Release: MVP · Epic depends on: E4

## Goal

As a player, I want to check what we wrote, so that an early mistake doesn't block the crossing words.

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-6.1.1) A check strikes through each wrong letter in its scope for all players and locks each correct letter.
- **AC-2** (AC-6.1.2) Empty cells in the scope are ignored.
- **AC-3** (AC-6.1.3) The result is computed on the server from the letters in place. The answer itself is not sent.
- **AC-4** (AC-6.1.4) Each check adds a line to the activity feed with the player and the scope.

## Edge cases and errors

Note from the lead (2026-10-11, from the spec 016 review): the client's
`LetterCellView` has no `wrong` field yet. This spec must add it on the page,
show it, and reset it to false when a `cell_locked` event or a new letter
arrives for the cell (spec 016 applies `cell_locked`, spec 015 `letter_changed`).

None stated in the backlog. To complete during review.

## Out of scope

- Generated hints and dictionary lookups (epic E6).
- Reveal a letter or a word: spec 024.
- Group decision on help: spec 025.
- Completion detection: spec 026.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
