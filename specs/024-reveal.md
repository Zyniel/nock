---
id: "024"
title: Reveal a letter or a word
status: approved
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

Note from the lead (2026-10-11, from the spec 037 review): spec 037 AC-1's
traffic check counts a letter as earned only when a player typed it. This
spec must extend that check: a `cell_locked` frame with `revealed: true` earns
its letter at that cell; any payload sent before the revealing frame that shows
the letter is a leak; the full game must reveal a cell nobody typed and a word,
with one late joiner's snapshot before the reveal (must not show the letter) and
one after; the same for the browser game. The earn rule keys on the revealing
frame, not on log order across clients.

Note from the lead (2026-10-12, from the spec 026 review): spec 026's
completion rule also triggers on `cell_locked` (`_with_completion` in
`src/nock/room.py`), and only a reveal can fill a cell through a lock. This
spec's tests must cover completion by a reveal: `grid_solved` after the last
revealed letter, or `grid_full_wrong` when the grid is then full but wrong.
Revealing on a solved grid is refused with `grid_solved` (spec 026 AC-4).

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
