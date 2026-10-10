---
id: "024"
title: Reveal a letter or a word
status: draft
---

# 024 - Reveal a letter or a word

Epic E6 Help and validation (US-6.2) · Release: V1 · Epic depends on: E4

## Goal

As a blocked team, we want to reveal a letter or a word, so that the game keeps moving.

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-6.2.1) A revealed cell shows the right letter with a corner marker, is locked and has no author.
- **AC-2** (AC-6.2.2) Reveals draw on a room budget set by the host; the default is 5 letters and 1 word.
- **AC-3** (AC-6.2.3) At zero budget, the reveal controls are disabled and say why.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Generated hints and dictionary lookups (epic E6).
- Check a letter, a word or the grid: spec 023.
- Group decision on help: spec 025.
- Completion detection: spec 026.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
